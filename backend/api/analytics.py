# backend/api/analytics.py —— 数据分析接口
from fastapi import APIRouter
import sys
import os

# 添加当前目录到 sys.path
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from core.analytics import Analytics

router = APIRouter()

@router.get("/weekly")
def weekly():
    return Analytics.weekly_summary()

@router.get("/mood-trend")
def mood_trend():
    return Analytics.daily_mood_trend()

@router.get("/meal-frequency")
def meal_frequency():
    return Analytics.meal_frequency()
