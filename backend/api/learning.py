# backend/api/learning.py —— 学习相关接口
from fastapi import APIRouter
from pydantic import BaseModel
import sys
import os

# 添加当前目录到 sys.path
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from core.database import get_all_topics, create_topic, create_conversation
from core.analytics import Analytics

router = APIRouter()

class TopicReq(BaseModel):
    name: str
    description: str = ""

@router.get("/topics")
def list_topics():
    return get_all_topics()

@router.post("/topics")
def add_topic(req: TopicReq):
    tid = create_topic(req.name, req.description)
    return {"id": tid, "name": req.name}

@router.post("/conversations")
def add_conversation(topic_id: int, title: str = "新对话"):
    cid = create_conversation(topic_id, title)
    return {"id": cid, "title": title}

@router.get("/learning-curve")
def learning_curve(days: int = 30):
    return Analytics.learning_curve()

@router.get("/knowledge-growth")
def knowledge_growth(days: int = 90):
    return Analytics.knowledge_growth()

@router.get("/learning-time-dist")
def learning_time_distribution(days: int = 30):
    return Analytics.learning_time_distribution()

@router.get("/learning-summary")
def learning_summary():
    return Analytics.get_learning_summary()
