import chromadb
from chromadb.utils import embedding_functions
from pathlib import Path
import fitz
import os
import re
from typing import List, Dict, Any, Optional, Tuple
from .logger import logger
from rank_bm25 import BM25Okapi
import jieba 

_RERANKER_CACHE = {}
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

DB_PATH = Path(__file__).parent.parent / "storage" / "chroma_db"

EMBED_MODEL = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)


class SimpleTokenCounter:
    # 简单的字符级 token 计数回退方案
    
    @staticmethod
    def encode(text: str) -> list:
        # 将文本编码为字符列表（作为 token 的简化替代）
        return list(text)
    
    @staticmethod
    def decode(tokens: list) -> str:
        # 将 token 列表解码回文本
        return ''.join(tokens)


class TextChunker:
    # 文档分块器

    def __init__(self, chunk_size: int = 512, overlap: int = 64, model: str = "cl100k_base"):
        self.chunk_size = chunk_size
        self.overlap = overlap
        try:
            import tiktoken
            self.enc = tiktoken.get_encoding(model)
            self.use_tiktoken = True
            logger.debug(f"Successfully loaded tiktoken encoding: {model}")
        except Exception as e:
            logger.warning(f"Failed to load tiktoken encoding '{model}': {e}. Using simple character-based fallback.")
            self.enc = SimpleTokenCounter()
            self.use_tiktoken = False
  

    def chunk_text(self, text: str, metadata: Optional[Dict] = None) -> List[Dict[str, Any]]:
        # 基于 token 和语义边界的分块
        tokens = self.enc.encode(text)
        chunks = []

        start = 0
        while start < len(tokens):
            end = min(start + self.chunk_size, len(tokens))
            chunk_tokens = tokens[start:end]
            chunk_text = self.enc.decode(chunk_tokens)

            chunk_metadata = metadata.copy() if metadata else {}
            chunk_metadata["chunk_start"] = start
            chunk_metadata["chunk_end"] = end

            chunks.append({
                "text": chunk_text.strip(),
                "metadata": chunk_metadata
            })

            start = end - self.overlap if end < len(tokens) else end

        return chunks

    def chunk_by_semantic(self, text: str, metadata: Optional[Dict] = None) -> List[Dict[str, Any]]:
        # 基于语义边界（段落）的分块        
        paragraphs = re.split(r'\n\s*\n', text)
        chunks = []

        current_chunk = ""
        current_tokens = 0

        for para in paragraphs:
            para_tokens = len(self.enc.encode(para))

            if current_tokens + para_tokens > self.chunk_size and current_chunk:
                chunks.append({
                    "text": current_chunk.strip(),
                    "metadata": metadata.copy() if metadata else {}
                })
                overlap_text = " ".join(current_chunk.split()[-self.overlap:])
                current_chunk = overlap_text + " " + para
                current_tokens = len(self.enc.encode(current_chunk))
            else:
                current_chunk += " " + para
                current_tokens += para_tokens

        if current_chunk.strip():
            chunks.append({
                "text": current_chunk.strip(),
                "metadata": metadata.copy() if metadata else {}
            })

        return chunks


class RAGEngine:

    def __init__(self):
        self.client = chromadb.PersistentClient(path=str(DB_PATH))
        self.collection = self.client.get_or_create_collection(
            name="Kiyo_knowledge",
            embedding_function=EMBED_MODEL
        )
        self.chunker = TextChunker(chunk_size=512, overlap=64)
        self.logger = logger
        self.bm25 = None
        self.bm25_corpus = []
        self.build_bm25_index()

        global _RERANKER_CACHE
        if 'cross-encoder' not in _RERANKER_CACHE:
            try:
                from sentence_transformers import CrossEncoder
                _RERANKER_CACHE['cross-encoder'] = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
                self.logger.info("Cross-Encoder 加载成功")
            except Exception as e:
                _RERANKER_CACHE['cross-encoder'] = None
                self.logger.warning(f"Cross-Encoder 加载失败: {e}")
        
        self.reranker = _RERANKER_CACHE.get('cross-encoder')  # 使用缓存
    
    def add_text(self, text: str, metadata: dict = None):
        doc_id = str(hash(text))
        if not metadata:
            metadata = {"source": "manual"}
        self.collection.add(
            documents=[text],
            metadatas=[metadata],
            ids=[doc_id]
        )

    def add_pdf(self, pdf_path: str):
        doc = fitz.open(pdf_path)
        page_count = 0
        for i, page in enumerate(doc):
            text = page.get_text()
            if text.strip():
                self.add_text(
                    text,
                    metadata={
                        "source": pdf_path,
                        "page": str(i + 1),
                        "type": "pdf"
                    }
                )
                page_count += 1
        doc.close()
        logger.info(f"Successfully add {page_count} from PDF to knowledge database :{pdf_path}")

    def query(self, question: str, n_result: int = 3) -> list:
        results = self.collection.query(
            query_texts=[question],
            n_results=n_result
        )
        if results and results["documents"]:
            return results["documents"][0]
        return []

    def get_collection_stats(self) -> dict:
        count = self.collection.count()
        return {"count": count}

    def query_with_rerank(self, question: str, n_initial: int = 10, n_final: int = 3) -> Tuple[List[str], List[Dict]]:
        # 混合+cross-encoder
        candidates = self.query_with_hybird(question, n_initial)

        if not candidates:
            return [], []

        if not self.reranker:
            scored = []
            for doc in candidates:
                relevance = self._calculate_relevance(question, doc)
                scored.append((doc, relevance))
            scored.sort(key=lambda x: x[1], reverse=True)
            return [s[0] for s in scored[:n_final]], [{}]* n_final
        
        pairs = [[question, doc] for doc in candidates]
        scores = self.reranker.predict(pairs) 

        scored = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)
    
        self.logger.info(f"Cross-Encoder 精排完成，最高分数: {scored[0][1]:.3f}")
        return [s[0] for s in scored[:n_final]], [{}] * n_final

    def _calculate_relevance(self, question: str, document: str) -> float:
        # 简单的关键词重叠计算（可替换为 Cross-Encoder）
        q_words = set(re.findall(r'\w+', question.lower()))
        d_words = set(re.findall(r'\w+', document.lower()))
        overlap = q_words & d_words
        if not q_words:
            return 0.0
        return len(overlap) / len(q_words)

    def query_with_filter(self, question: str, filter_metadata: Dict, n_result: int = 5) -> List[str]:
        # 带元数据过滤的查询
        results = self.collection.query(
            query_texts=[question],
            n_results=n_result,
            where=filter_metadata,
            include=["documents"]
        )

        if results and results.get("documents"):
            return results["documents"][0]
        return []
    def build_bm25_index(self) -> None:
        results = self.collection.get(include=["documents"])

        if not results or not results.get("documents"):
            self.bm25_corpus = []
            self.bm25 = None
            return
        
        self.bm25_corpus = results["documents"]
        tokenized = [list(jieba.cut(doc)) for doc in self.bm25_corpus]
        self.bm25 = BM25Okapi(tokenized)
        self.logger.info(f"BM25 索引构建完成，共 {len(self.bm25_corpus)} 条文档")
    
    def query_bm25(self, question: str, n_result: int = 5) -> List[Tuple[int, float]]:
        if not self.bm25:
            return []
        
        tokenized_query = list(jieba.cut(question))
        scores = self.bm25.get_scores(tokenized_query)

        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        return ranked[:n_result]
    
    def query_with_hybird(self, question: str, n_result: int = 5, k: int = 60) -> List[str]:

        vector_result = self.collection.query(
            query_texts=[question],
            n_results=n_result *2,
            include=["documents"]
        )

        if not vector_result or not vector_result.get("documents"):
            return []
        vector_docs = vector_result["documents"][0]

        if not hasattr(self, 'bm25') or not self.bm25:
            self.build_bm25_index()

        bm25_results = self.query_bm25(question, n_result * 2)

        rrf_scores = {}
        for rank, doc in enumerate(vector_docs):
            if doc  not in rrf_scores:
                rrf_scores[doc] = 0
            rrf_scores[doc] += 1/(k + rank + 1)

        for idx, score in bm25_results:
            if idx < len(self.bm25_corpus):
                doc = self.bm25_corpus[idx]
                if doc not in rrf_scores:
                    rrf_scores[doc] = 0
                rrf_scores[doc] += 1/(k+ bm25_results.index((idx, score)) + 1)
        
        sorted_docs = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        return [doc for doc, score in sorted_docs[: n_result]]

class RAGEvaluator:
    # RAG 评估

    @staticmethod
    def context_precision(context: List[str], expected: List[str]) -> float:
        """Context Precision: 相关上下文在总上下文中的比例"""
        if not context:
            return 0.0

        relevant = sum(1 for ctx in context if any(e in ctx for e in expected))
        return relevant / len(context) if context else 0.0

    @staticmethod
    def context_recall(context: List[str], expected: List[str]) -> float:
        """Context Recall: 期望内容被检索到的比例"""
        if not expected:
            return 1.0

        covered = sum(1 for exp in expected if any(exp in ctx for ctx in context))
        return covered / len(expected) if expected else 0.0

    @staticmethod
    def faithfulness(context: List[str], answer: str) -> float:
        # Faithfulness: 答案对上下文的忠诚度
        if not context:
            return 0.0

        answer_words = set(re.findall(r'\w+', answer.lower()))
        context_words = set()
        for ctx in context:
            context_words.update(re.findall(r'\w+', ctx.lower()))

        if not answer_words:
            return 1.0

        overlap = answer_words & context_words
        return len(overlap) / len(answer_words)

    @staticmethod
    def answer_relevance(question: str, answer: str) -> float:
        # Answer Relevance: 答案与问题的相关度
        q_words = set(jieba.cut(question.lower()))
        a_words = set(jieba.cut(answer.lower()))

        q_words = {w for w in q_words if w.strip()}
        a_words = {w for w in a_words if w.strip()}

        if not q_words:
            return 0.0

        overlap = q_words & a_words
        return len(overlap) / len(q_words)

    @staticmethod
    def evaluate(context: List[str], answer: str, expected: List[str], question: str) -> Dict[str, float]:
        # 综合评估
        return {
            "context_precision": RAGEvaluator.context_precision(context, expected),
            "context_recall": RAGEvaluator.context_recall(context, expected),
            "faithfulness": RAGEvaluator.faithfulness(context, answer),
            "answer_relevance": RAGEvaluator.answer_relevance(question, answer)
        }
    
    @staticmethod
    def evaluate_and_report(context: List[str], answer: str, excepted: List[str], question: str) -> Dict[str,Any]:

        metrics = RAGEvaluator.evaluate(context, answer, excepted, question)

        report = {
            "metrics": metrics,
            "summary": {
                "overall_score": sum(metrics.values())/len(metrics),
                "grade": RAGEvaluator._get_grade(metrics)

            },
            "suggestions": RAGEvaluator._get_suggestions(metrics)
        }
        return report
    
    @staticmethod
    def _get_grade(metrics: Dict[str, float]) -> str:
        avg = sum(metrics.values()) / len(metrics)
        if avg >= 0.85:
            return "A"
        elif avg >= 0.7:
            return "B"
        elif avg >= 0.5:
            return "C"
        else:
            return "D"
    
    @staticmethod
    def _get_suggestions(metrics: Dict[str, float]) -> List[str]:
        suggestions = []
        if metrics["context_precision"] < 0.6:
            suggestions.append("建议增加检索过滤条件，减少不相关文档")
        if metrics["context_recall"] < 0.6:
            suggestions.append("建议增加知识库覆盖范围，或调整检索参数")
        if metrics["faithfulness"] < 0.6:
            suggestions.append("建议增加答案验证机制，确保答案来自上下文")
        if metrics["answer_relevance"] < 0.6:
            suggestions.append("建议优化 Prompt，引导模型关注问题核心")
        return suggestions if suggestions else ["当前 RAG 质量良好！"]



if __name__ == "__main__":
    logger.info("测试 RAG 引擎...")

    rag = RAGEngine()

    # 修改测试代码，添加更多相关知识
    logger.info("添加测试知识...")
    rag.add_text("分布式系统的一致性是指所有节点在同一时刻看到相同的数据。")
    rag.add_text("CAP 定理指出：分布式系统最多同时满足一致性、可用性和分区容错性中的两个。")
    rag.add_text("一致性模型包括：强一致性、弱一致性、最终一致性。")  # 添加这条
    rag.add_text("Paxos 和 Raft 是实现分布式一致性的经典算法。")     # 添加这条
    rag.add_text("Kiyo 是一个治愈系 AI 学习伴侣，帮助用户重建学习习惯。")
    stats = rag.get_collection_stats()
    logger.info(f"知识库条目数：{stats['count']}")

    logger.info("测试检索...")
    results = rag.query("什么是一致性？")
    for i, doc in enumerate(results, 1):
        logger.info(f"  结果{i}:{doc[:80]}...")

    logger.info("测试混合检索...")
    hybird_results = rag.query_with_hybird("什么是一致性？")
    for i, doc in enumerate(hybird_results, 1):
        logger.info(f"  结果{i}:{doc[:80]}...")
    
        # 测试 RAG 评估
    logger.info("\n=== 测试 RAG 评估 ===")
    question = "什么是一致性？"
    context = rag.query_with_rerank(question)[0]  # 获取检索到的上下文
    answer = "分布式系统的一致性是指所有节点在同一时刻看到相同的数据。"
    expected = ["一致性", "分布式系统", "节点"]

    metrics = RAGEvaluator.evaluate(context, answer, expected, question)
    logger.info(f"Context Precision: {metrics['context_precision']:.2f}")
    logger.info(f"Context Recall: {metrics['context_recall']:.2f}")
    logger.info(f"Faithfulness: {metrics['faithfulness']:.2f}")
    logger.info(f"Answer Relevance: {metrics['answer_relevance']:.2f}")

    # 生成评估报告
    logger.info("\n=== RAG 质量评估报告 ===")
    logger.info("="*50)
    logger.info("| 指标 | 分数 | 评价 |")
    logger.info("|------|------|------|")

    for metric, score in metrics.items():
        if score >= 0.8:
            rating = "优秀"
        elif score >= 0.6:
            rating = "良好"
        elif score >= 0.4:
            rating = "一般"
        else:
            rating = "较差"
        logger.info(f"| {metric} | {score:.2f} | {rating} |")

    logger.info("="*50)

    logger.info("RAG 引擎测试完成！")
