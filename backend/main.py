# backend/main.py —— Kiyo API 入口
import sys
import os
# 禁用代理环境变量，避免 OpenAI SDK 报错
import os
os.environ.pop('HTTP_PROXY', None)
os.environ.pop('HTTPS_PROXY', None)
os.environ.pop('http_proxy', None)
os.environ.pop('https_proxy', None)

# 添加当前目录到 sys.path，支持直接运行
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from core.database import init_db
from api.chat import router as chat_router
from api.records import router as records_router
from api.learning import router as learning_router
from api.analytics import router as analytics_router
import requests

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

# ==================== Streamlit 代理路由 ====================
STREAMLIT_URL = "http://127.0.0.1:8501"

@app.get("/streamlit/")
async def streamlit_index():
    """代理 Streamlit 首页"""
    try:
        response = requests.get(f"{STREAMLIT_URL}/", stream=True)
        return StreamingResponse(
            response.iter_content(chunk_size=1024),
            media_type=response.headers.get("Content-Type", "text/html"),
            status_code=response.status_code
        )
    except Exception as e:
        return {"error": f"Streamlit 服务未启动: {str(e)}"}

@app.get("/streamlit/{path:path}")
async def streamlit_proxy_get(path: str):
    """代理 Streamlit GET 请求"""
    try:
        response = requests.get(f"{STREAMLIT_URL}/{path}", stream=True)
        return StreamingResponse(
            response.iter_content(chunk_size=1024),
            media_type=response.headers.get("Content-Type", "application/octet-stream"),
            status_code=response.status_code
        )
    except Exception as e:
        return {"error": f"Streamlit 代理失败: {str(e)}"}

@app.post("/streamlit/{path:path}")
async def streamlit_proxy_post(path: str):
    """代理 Streamlit POST 请求"""
    try:
        response = requests.post(f"{STREAMLIT_URL}/{path}", stream=True)
        return StreamingResponse(
            response.iter_content(chunk_size=1024),
            media_type=response.headers.get("Content-Type", "application/octet-stream"),
            status_code=response.status_code
        )
    except Exception as e:
        return {"error": f"Streamlit 代理失败: {str(e)}"}
