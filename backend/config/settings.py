# backend/config/settings.py
import os
from dotenv import load_dotenv
from pathlib import Path

# 加载 .env 文件 —— 指向 backend 目录
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# AI 配置：优先从环境变量读取，没有则使用默认值
DOUBAO_API_KEY = os.getenv("DOUBAO_API_KEY", "未设置")
DOUBAO_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
DOUBAO_MODEL = "doubao-seed-2-0-lite-260215"

# 数据库
DB_PATH = Path(__file__).parent.parent / "storage" / "kiyo.db"

# 飞书配置
FEISHU_APP_ID = os.getenv("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")