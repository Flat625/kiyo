"""统一入口文件 - 同时启动 FastAPI 和 Streamlit"""
import subprocess
import threading
import time
import uvicorn
import os

def start_streamlit():
    """在子进程中启动 Streamlit"""
    subprocess.run([
        "streamlit", "run", "app.py",
        "--server.port", "8501",
        "--server.address", "127.0.0.1",
        "--server.headless", "true",
        "--browser.gatherUsageStats", "false"
    ])

def start_fastapi():
    """启动 FastAPI"""
    port = int(os.environ.get("PORT", 8000))
    print(f"🚀 启动 FastAPI 在端口 {port}")
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=port,
        reload=False
    )

if __name__ == "__main__":
    # 先启动 Streamlit（在后台线程）
    print("🔧 启动 Streamlit...")
    streamlit_thread = threading.Thread(target=start_streamlit, daemon=True)
    streamlit_thread.start()
    
    # 等待 Streamlit 启动
    print("⏳ 等待 Streamlit 启动...")
    time.sleep(8)
    
    # 启动 FastAPI（主线程）
    print("🚀 启动 FastAPI...")
    start_fastapi()