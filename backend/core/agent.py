"""
Agent 系统 - 多步推理和工具调用
"""
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union
from dataclasses import dataclass, field
from datetime import datetime
import json
import sys
import os

# 添加当前目录到 sys.path
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from core.logger import get_logger
from core.ai_service import AIService
from core.prompts import RAG_ENHANCE_PROMPT, AGENT_THINK_PROMPT, AGENT_SUMMARIZE_PROMPT, TOOL_RESULT_PROMPT

logger = get_logger("agent")


class AgentState(Enum):
    """Agent 状态枚举"""
    IDLE = "idle"
    THINKING = "thinking"
    ACTING = "acting"
    OBSERVING = "observing"
    DONE = "done"
    ERROR = "error"


@dataclass
class Tool:
    """工具定义"""
    name: str
    description: str
    func: Callable
    schema: Dict[str, Any]


@dataclass
class AgentMessage:
    """Agent 消息"""
    role: str
    content: str
    tool_calls: Optional[List[Dict]] = None
    tool_results: Optional[List[Dict]] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class Agent:
    """轻量级 Agent 系统"""

    def __init__(self, ai_service: Optional[AIService] = None):
        self.state = AgentState.IDLE
        self.ai = ai_service or AIService()
        self.tools: Dict[str, Tool] = {}
        self.memory: List[AgentMessage] = []
        self.thought_chain: List[Dict] = []

        self._register_default_tools()

    def _register_default_tools(self):
        """注册默认工具"""
        from .database import get_all_memories, get_records_by_type, add_memory
        from .rag_engine import RAGEngine
        from .feishu_api import FeishuClient    

        self.register_tool(Tool(
            name="get_memories",
            description="获取用户的所有记忆",
            func=lambda: get_all_memories(),
            schema={"type": "object", "properties": {}, "required": []}
        ))

        self.register_tool(Tool(
            name="get_records",
            description="获取用户的记录（类型：meal/emotion/energy/note）",
            func=lambda record_type="emotion", limit=10: get_records_by_type(record_type, limit),
            schema={"type": "object", "properties": {"record_type": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["record_type"]}
        ))

        self.register_tool(Tool(
            name="search_knowledge",
            description="搜索知识库",
            func=lambda query: RAGEngine().query_with_rerank(query, n_initial=10, n_final=3),
            schema={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}
        ))

        self.register_tool(Tool(
            name="add_memory",
            description="添加记忆到知识库",
            func=lambda content, topic_id=1: add_memory(topic_id, content, source="auto"),
            schema={"type": "object", "properties": {"content": {"type": "string"}, "topic_id": {"type": "integer"}}, "required": ["content"]}
        ))

    def register_tool(self, tool: Tool):
        """注册工具"""
        self.tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name}")

    def think(self, user_input: str, max_steps: int = 5) -> str:
        """执行多步推理（正确使用 Prompt）"""
        self.state = AgentState.THINKING
        self.thought_chain = []
        context = user_input

        for step in range(max_steps):
            self.state = AgentState.THINKING

            think_prompt = AGENT_THINK_PROMPT.format(
                context=context,
                thought_history=[t["response"] for t in self.thought_chain] if self.thought_chain else None
            )

            response = self.ai.chat(message=think_prompt)

            thought = {
                "step": step + 1,
                "prompt": think_prompt[:100] + "..." if len(think_prompt) > 100 else think_prompt,
                "response": response,
                "state": self.state.value,
                "timestamp": datetime.now().isoformat()
            }
            self.thought_chain.append(thought)

            if "下一步：总结" in response or "下一步：direct_answer" in response:
                self.state = AgentState.DONE
                break

            tool_name = self._extract_tool_name(response)
            if tool_name and tool_name in self.tools:
                self.state = AgentState.ACTING
                tool_result = self._execute_tool(tool_name, context)
                formatted_result = TOOL_RESULT_PROMPT.format(tool_name, str(tool_result))
                context = f"{context}\n{formatted_result}"
                self.state = AgentState.OBSERVING
            else:
                context = f"{context}\n{response}"

        final_response = self._generate_summary(user_input, context)
        self._save_thinking_process(user_input, final_response)
        self.state = AgentState.IDLE
        return final_response

    def _extract_tool_name(self, response: str) -> Optional[str]:
        """从思考中提取工具名称"""
        import re
        match = re.search(r"下一步：(\w+)", response)
        return match.group(1) if match else None

    def _execute_tool(self, tool_name: str, context: str) -> Any:
        """执行工具调用"""
        tool = self.tools[tool_name]
        try:
            if tool_name == "search_knowledge":
                return tool.func(context)
            elif tool_name == "get_records":
                return tool.func("emotion", limit=5)
            elif tool_name == "get_memories":
                return tool.func()
            else:
                return tool.func()
        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            return f"工具调用失败: {str(e)}"

    def _generate_summary(self, question: str, context: str) -> str:
        """使用 AGENT_SUMMARIZE_PROMPT 生成总结"""
        summary_prompt = AGENT_SUMMARIZE_PROMPT.format(
            question=question,
            context=context,
            thought_history=[t["response"] for t in self.thought_chain] if self.thought_chain else None
        )
        return self.ai.chat(message=summary_prompt)

    def _is_complete(self, response: str) -> bool:
        """判断是否完成（简化版）"""
        complete_indicators = ["完成", "总结", "建议", "结论", "以上是", "希望对你"]
        return any(indicator in response for indicator in complete_indicators)

    def _save_thinking_process(self, user_input: str, final_response: str):
        """保存思考过程到数据库"""
        try:
            from .database import add_message
            thinking_content = json.dumps({
                "type": "agent_thinking",
                "user_input": user_input,
                "thought_chain": self.thought_chain,
                "final_response": final_response,
                "steps": len(self.thought_chain)
            }, ensure_ascii=False)

            add_message(conv_id=1, role="thinking", content=thinking_content)
            logger.info(f"Saved thinking process with {len(self.thought_chain)} steps")
        except Exception as e:
            logger.error(f"Failed to save thinking process: {e}")

    def reflect(self, task: str, result: str) -> str:
        """反思机制"""
        reflection_prompt = f"""请反思以下任务完成情况：

任务：{task}
结果：{result}

请从以下角度进行反思：
1. 哪些地方做得好？
2. 哪些地方可以改进？
3. 下次遇到类似任务应该怎么做？

用简洁的语言回复，控制在100字以内。"""

        reflection = self.ai.chat(reflection_prompt)

        try:
            from .database import add_memory
            add_memory(topic_id=1, content=f"[反思] {reflection}", source="auto")
        except Exception as e:
            logger.error(f"Failed to save reflection: {e}")

        return reflection

    def get_thought_chain(self) -> List[Dict]:
        """获取思考链"""
        return self.thought_chain

    def get_state(self) -> AgentState:
        """获取当前状态"""
        return self.state


class ToolCallingAgent(Agent):
    """支持工具调用的 Agent"""

    def __init__(self, ai_service: Optional[AIService] = None):
        super().__init__(ai_service)
        self.pending_tool_calls: List[Dict] = []

    def think_with_tools(self, user_input: str, max_steps: int = 3) -> str:
        """带工具调用的思考（简化版）"""
        self.state = AgentState.THINKING
        self.thought_chain = []
        context = user_input

        for step in range(max_steps):
            self.state = AgentState.THINKING

            think_prompt = AGENT_THINK_PROMPT.format(
                context=context,
                thought_history=[t["response"] for t in self.thought_chain] if self.thought_chain else None
            )

            response = self.ai.chat(message=think_prompt)
            tool_results = self._extract_and_execute_tools(response)

            thought = {
                "step": step + 1,
                "response": response,
                "tool_calls": self.pending_tool_calls,
                "tool_results": tool_results
            }
            self.thought_chain.append(thought)

            if tool_results:
                for result in tool_results:
                    formatted = TOOL_RESULT_PROMPT.format(result["tool"], result.get("output", ""))
                    context = f"{context}\n{formatted}"
            else:
                break

        summary_prompt = AGENT_SUMMARIZE_PROMPT.format(
            question=user_input,
            context=context,
            thought_history=[t["response"] for t in self.thought_chain]
        )
        final_response = self.ai.chat(message=summary_prompt)

        self._save_thinking_process(user_input, final_response)
        self.state = AgentState.IDLE
        return final_response

    def _build_system_prompt(self) -> str:
        """构建系统提示"""
        tool_schemas = [f"- {name}: {tool.description}" for name, tool in self.tools.items()]
        return f"""你是一个智能助手，可以调用以下工具来完成任务：

{chr(10).join(tool_schemas)}

如果你需要调用工具，请用以下格式：
Action: tool_name
Action Input: {{"param": "value"}}

完成所有步骤后，用"完成"标记结束。"""

    def _extract_and_execute_tools(self, response: str) -> List[Dict]:
        """提取并执行工具调用"""
        results = []
        self.pending_tool_calls = []

        import re
        pattern = r"Action:\s*(\w+)\s*Action Input:\s*(\{.*?\})"
        matches = re.findall(pattern, response, re.DOTALL)

        for tool_name, tool_input in matches:
            if tool_name in self.tools:
                try:
                    tool_args = json.loads(tool_input)
                    result = self.tools[tool_name].func(**tool_args)
                    results.append({
                        "tool": tool_name,
                        "input": tool_args,
                        "output": str(result)[:500]
                    })
                    self.pending_tool_calls.append({"tool": tool_name, "input": tool_args})
                except Exception as e:
                    results.append({
                        "tool": tool_name,
                        "error": str(e)
                    })

        return results


if __name__ == "__main__":
    agent = ToolCallingAgent()
    print("测试 Agent 工具调用...")
    response = agent.think_with_tools("我最近一周的情绪怎么样？")
    print(f"回答: {response}")
    
    print("\n思考过程:")
    for thought in agent.get_thought_chain():
        print(f"步骤{thought['step']}: {thought['response'][:50]}...")
