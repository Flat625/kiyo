# backend/api/records.py —— 饮食/情绪记录接口
from fastapi import APIRouter
from pydantic import BaseModel
import sys
import os

# 添加当前目录到 sys.path
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from core.database import add_record, get_records_by_type
from core.ai_service import AIService

router = APIRouter()
ai = AIService()

class RecordReq(BaseModel):
    record_type: str  # meal / emotion / energy / note
    content: str
    score: int = 0

class RecordRes(BaseModel):
    id: int
    analysis: dict = {}

@router.post("/add", response_model=RecordRes)
def add(req: RecordReq):
    rid = add_record(req.record_type, req.content, req.score)
    analysis = ai.analyze_record(req.content) if req.record_type == 'meal' else {}
    return RecordRes(id=rid, analysis=analysis)

@router.get("/list/{record_type}")
def list_records(record_type: str, limit: int = 30):
    return get_records_by_type(record_type, limit)
