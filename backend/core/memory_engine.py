# backend/core/memory_engine.py —— 记忆引擎
import sys
import os

# 添加当前目录到 sys.path
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from core.database import add_memory, get_all_memories

class MemoryEngine:
    @staticmethod
    def summarize_conversation(messages: list, topic_id: int = None) -> str:
        """从对话列表中提取关键记忆"""
        text = ' '.join([m.get('content','') for m in messages[-10:]])
        summary = f"对话摘要（{len(messages)}条消息）：{text[:200]}"
        add_memory(topic_id, summary, source='auto')
        return summary

    @staticmethod
    def get_all(): return get_all_memories()