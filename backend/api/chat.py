# backend/api/chat.py —— 对话接口
from fastapi import APIRouter
from pydantic import BaseModel
import sys
import os

# 添加当前目录到 sys.path
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from core.ai_service import AIService

router = APIRouter()
ai = AIService()

class ChatReq(BaseModel):
    message: str
    conversation_id: int = 1

class ChatRes(BaseModel):
    reply: str

class PlanReq(BaseModel):
    idea: str

class PlanRes(BaseModel):
    tasks: list

@router.post("/send", response_model=ChatRes)
def send(req: ChatReq):
    reply = ai.chat(req.message)
    from ..core.database import add_message
    add_message(req.conversation_id, 'user', req.message)
    add_message(req.conversation_id, 'assistant', reply)
    return ChatRes(reply=reply)

@router.post("/plan", response_model=PlanRes)
def plan(req: PlanReq):
    tasks = ai.generate_learning_plan(req.idea)
    return PlanRes(tasks=tasks)
