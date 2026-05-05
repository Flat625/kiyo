# backend/main.py —— Kiyo API 入口
import sys
import os

# 添加当前目录到 sys.path，支持直接运行
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.database import init_db
from api.chat import router as chat_router
from api.records import router as records_router
from api.learning import router as learning_router
from api.analytics import router as analytics_router

init_db()

app = FastAPI(title="Kiyo API", version="3.0", description="治愈系 AI 学习伴侣后端")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

app.include_router(chat_router, prefix="/api/chat", tags=["💬 对话"])
app.include_router(records_router, prefix="/api/records", tags=["🍽️ 记录"])
app.include_router(learning_router, prefix="/api/learning", tags=["📝 学习"])
app.include_router(analytics_router, prefix="/api/analytics", tags=["📊 分析"])

@app.get("/")
def root():
    return {"message": "Kiyo API is running", "version": "3.0"}
