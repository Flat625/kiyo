"""
Prompt 工程模块 - 结构化 Prompt 管理和版本控制
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import json
import re


class BasePrompt(ABC):
    """Prompt 基类"""
    version: str = "1.0"
    description: str = ""

    @abstractmethod
    def format(self, **kwargs) -> str:
        """格式化 Prompt"""
        pass

    def add_few_shot(self, examples: List[Dict[str, str]]) -> str:
        """添加 Few-Shot 示例"""
        if not examples:
            return ""
        shots = "\n\n## 示例:\n"
        for ex in examples:
            shots += f"输入: {ex.get('input', '')}\n"
            shots += f"输出: {ex.get('output', '')}\n"
        return shots


class ChatPrompt(BasePrompt):
    """对话 Prompt"""
    version = "1.0"
    description = "Kiyo AI 学习伴侣对话"

    def __init__(self):
        self.system_template = """你是 Kiyo,一个温暖、耐心的 AI 学习伴侣。
你的用户正在从进食障碍中康复，也在努力学习编程和系统架构。
请用温和、不带评判的语气回应。鼓励但不施压。用"你"称呼用户。
如果用户分享饮食或情绪，先接纳再温和回应。
如果用户问技术问题，用清晰、易懂的方式解释。
每次回复控制在 3-5 句话以内。"""

    def format(self, message: str, context: Optional[List[Dict]] = None) -> List[Dict[str, str]]:
        messages = [{"role": "system", "content": self.system_template}]
        if context:
            messages.extend(context)
        messages.append({"role": "user", "content": message})
        return messages


class RecordAnalysisPrompt(BasePrompt):
    """记录分析 Prompt"""
    version = "1.0"
    description = "分析用户饮食/情绪记录"

    JSON_SCHEMA = {
        "type": "object",
        "properties": {
            "emotion": {"type": "string", "enum": ["positive", "neutral", "negative"]},
            "meal_type": {"type": "string", "enum": ["breakfast", "lunch", "dinner", "snack", "other"]},
            "summary": {"type": "string"}
        },
        "required": ["emotion", "meal_type", "summary"]
    }

    FEW_SHOT_EXAMPLES = [
        {
            "input": "今天吃了早餐，面包和牛奶，感觉还不错",
            "output": '{"emotion": "positive", "meal_type": "breakfast", "summary": "用户早餐摄入充足，情绪积极"}'
        },
        {
            "input": "午餐只喝了一杯咖啡，没什么胃口",
            "output": '{"emotion": "neutral", "meal_type": "lunch", "summary": "用户午餐摄入不足，需要关注"}'
        }
    ]

    def format(self, content: str) -> str:
        prompt = f"""请分析并返回 JSON(不要加任何其他文字):
输入: {content}

请严格遵循以下 JSON Schema:
{json.dumps(self.JSON_SCHEMA, ensure_ascii=False, indent=2)}

{self.add_few_shot(self.FEW_SHOT_EXAMPLES)}"""
        return prompt


class LearningPlanPrompt(BasePrompt):
    """学习计划 Prompt"""
    version = "1.0"
    description = "生成结构化学习计划"

    FEW_SHOT_EXAMPLES = [
        {
            "input": "我想学习系统架构设计",
            "output": '[{"name":"基础概念","description":"了解系统架构基本概念和原则","estimated_minutes":30},{"name":"架构风格","description":"学习常用架构风格如微服务、 monolith","estimated_minutes":45},{"name":"实战项目","description":"设计一个简单的电商系统架构","estimated_minutes":60}]'
        }
    ]

    def format(self, idea: str) -> str:
        prompt = f"""用户想学：{idea}

请拆解为 3-5 个具体可执行的学习任务，每个任务包含三字段：
- name: 简短任务名
- description: 一句话描述
- estimated_minutes: 建议专注时长（分钟）

严格只返回 JSON 列表，不要加任何解释或代码块标记。

{self.add_few_shot(self.FEW_SHOT_EXAMPLES)}"""
        return prompt


class InsightGeneratorPrompt(BasePrompt):
    """洞察生成 Prompt"""
    version = "1.0"
    description = "生成个性化周洞察"

    def format(self, records_text: str, stats_text: str) -> str:
        return f"""你是一位温暖、专业的学习与生活教练。
请基于以下用户本周的记录数据，生成一段个性化洞察报告。

## 用户本周记录：
{records_text}

## 本周统计摘要：
{stats_text}

请从以下角度分析，用温暖、鼓励的语气，像朋友一样说话：
1. 整体状态概述(1-2句)
2. 情绪变化趋势
3. 饮食/能量规律
4. 一个具体、可执行的微建议

请用中文回复,控制在200字以内。用"你"称呼用户。"""


class CalendarParsePrompt(BasePrompt):
    """日程解析 Prompt"""
    version = "1.0"
    description = "解析自然语言日程"

    JSON_SCHEMA = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "date": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
            "time": {"type": "string", "pattern": "^\\d{2}:\\d{2}$"},
            "duration_minutes": {"type": "integer", "minimum": 1}
        },
        "required": ["title"]
    }

    FEW_SHOT_EXAMPLES = [
        {
            "input": "明天下午3点复习系统架构,2小时",
            "output": '{"title":"复习系统架构","date":"2026-04-30","time":"15:00","duration_minutes":120}'
        },
        {
            "input": "周五晚上8点瑜伽课",
            "output": '{"title":"瑜伽课","date":"2026-05-01","time":"20:00","duration_minutes":60}'
        }
    ]

    def format(self, event_text: str) -> str:
        prompt = f"""请将以下用户的日程请求解析为结构化 JSON。
用户请求：{event_text}

请提取以下字段，如果无法确定则设为 null:
- title: 事件标题（必须）
- date: 日期，格式 YYYY-MM-DD(如果用户没说哪天，默认用明天)
- time: 开始时间，格式 HH:MM(如果用户没说,默认用 09:00)
- duration_minutes: 时长分钟数（如果用户没说，默认用 60)

严格只返回 JSON,不要加任何其他文字。

{self.add_few_shot(self.FEW_SHOT_EXAMPLES)}"""
        return prompt


class RAGEnhancePrompt(BasePrompt):
    """RAG 增强 Prompt"""
    version = "1.0"
    description = "基于知识库增强回答"

    def format(self, context_text: str, user_input: str) -> str:
        return f"""下面是知识库中的相关资料：
{context_text}

请基于以上资料，用温和的语气回答用户问题。如果资料中没有直接答案，就坦诚说没有找到，然后基于自身知识回答。

用户问题：{user_input}"""


class PromptValidator:
    """Prompt 输出验证器"""

    @staticmethod
    def validate_json(response: str, schema: Dict) -> tuple[bool, Optional[Dict], str]:
        """验证 JSON 格式和 schema"""
        try:
            json_match = re.search(r'\{.*\}|\[.*\]', response, re.DOTALL)
            if not json_match:
                return False, None, "未找到 JSON"

            data = json.loads(json_match.group())

            if isinstance(data, dict):
                for key in schema.get("required", []):
                    if key not in data:
                        return False, None, f"缺少必需字段: {key}"

            return True, data, "OK"
        except json.JSONDecodeError as e:
            return False, None, f"JSON 解析失败: {str(e)}"

    @staticmethod
    def fix_and_retry(response: str, prompt: str, max_retries: int = 2) -> tuple[Optional[Dict], str]:
        """尝试修复 JSON 并重试"""
        for attempt in range(max_retries):
            success, data, _ = PromptValidator.validate_json(response, {})
            if success:
                return data, "OK"

            cleaned = re.sub(r'[^\{\}\[\]\w:,"\'\s]', '', response)
            try:
                data = json.loads(cleaned)
                return data, "Fixed"
            except:
                pass

        return None, "Failed after max retries"


# 全局 Prompt 实例
CHAT_PROMPT = ChatPrompt()
RECORD_ANALYSIS_PROMPT = RecordAnalysisPrompt()
LEARNING_PLAN_PROMPT = LearningPlanPrompt()
INSIGHT_GENERATOR_PROMPT = InsightGeneratorPrompt()
CALENDAR_PARSE_PROMPT = CalendarParsePrompt()
RAG_ENHANCE_PROMPT = RAGEnhancePrompt()
PROMPT_VALIDATOR = PromptValidator()


# 向后兼容的常量（deprecated, 仅用于兼容旧代码）
CHAT_SYSTEM = ChatPrompt().system_template
ANALYZE_RECORD = lambda content: RECORD_ANALYSIS_PROMPT.format(content)
PLAN_LEARNING = lambda idea: LEARNING_PLAN_PROMPT.format(idea)
INSIGHT_GENERATOR = lambda records, stats: INSIGHT_GENERATOR_PROMPT.format(records, stats)
CALENDAR_PARSE = lambda event: CALENDAR_PARSE_PROMPT.format(event)
RAG_ENHANCE = lambda context, user: RAG_ENHANCE_PROMPT.format(context, user)

# ============ Agent 相关 Prompt ============

class AgentThinkPrompt(BasePrompt):
    """Agent 思考 Prompt - 决定下一步行动"""
    version = "1.0"
    description = "指导 Agent 进行推理和决策"
    
    TOOLS_DESCRIPTION = """
可用工具列表：
1. get_records - 获取用户最近的学习/生活记录
2. search_knowledge - 搜索知识库获取知识
3. get_memories - 获取用户的记忆信息
4. get_tasks - 获取待办任务列表
5. direct_answer - 直接回答（不需要调用工具）
"""
    
    def format(self, context: str, thought_history: Optional[List[str]] = None) -> str:
        history = "\n".join(thought_history) if thought_history else ""
        
        return f"""
你是一个智能助手，需要根据上下文决定下一步行动。

{self.TOOLS_DESCRIPTION}

已有的思考历史：
{history}

当前上下文：
{context}

请输出你的思考，格式如下：
思考：[你的分析和推理]
下一步：[工具名称] 或 [总结]

注意：
- 如果问题明确且你有足够信息，选择"总结"直接回答
- 如果需要获取更多信息，选择相应的工具
- 工具名称必须从列表中选择，不要自定义
"""


class AgentSummarizePrompt(BasePrompt):
    """Agent 总结 Prompt - 生成最终回答"""
    version = "1.0"
    description = "根据收集到的信息生成自然友好的总结回答"
    
    def format(self, question: str, context: str, thought_history: Optional[List[str]] = None) -> str:
        history = "\n".join(thought_history) if thought_history else ""
        
        return f"""
请根据以下信息，用自然友好的语言回答用户的问题。

用户问题：
{question}

收集到的信息：
{context}

思考过程：
{history}

回答要求：
1. 简洁明了，控制在 3-5 句话
2. 用中文口语化表达，像朋友聊天一样
3. 如果有数据，用清晰的方式呈现
4. 语气温暖、鼓励，符合 Kiyo 的人设
5. 不要暴露思考过程，直接给出最终回答
"""


class ToolResultPrompt(BasePrompt):
    """工具结果格式化 Prompt"""
    version = "1.0"
    description = "格式化工具返回结果"
    
    def format(self, tool_name: str, result: str) -> str:
        tool_names = {
            "get_records": "学习/生活记录",
            "search_knowledge": "知识库搜索",
            "get_memories": "用户记忆",
            "get_tasks": "待办任务"
        }
        
        return f"""【{tool_names.get(tool_name, tool_name)}】\n{result}"""


# Agent 全局实例
AGENT_THINK_PROMPT = AgentThinkPrompt()
AGENT_SUMMARIZE_PROMPT = AgentSummarizePrompt()
TOOL_RESULT_PROMPT = ToolResultPrompt()