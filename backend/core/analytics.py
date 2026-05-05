# backend/core/analytics.py —— 数据分析模块
from datetime import datetime, timedelta
from collections import Counter
import sys
import os

# 添加当前目录到 sys.path
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from core.database import db_connection
from core.enhanced_analytics import AnomalyDetector, PatternRecognizer, CorrelationAnalyzer, LearningTracker

class Analytics:
    anomaly_detection = AnomalyDetector
    pattern_recognition = PatternRecognizer
    correlation_analysis = CorrelationAnalyzer
    learning_tracker = LearningTracker

    @staticmethod
    def weekly_summary():
        """本周饮食/情绪统计"""
        with db_connection() as conn:
            cur = conn.cursor()
            week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            cur.execute("SELECT record_type, COUNT(*), AVG(score) FROM records WHERE created_at >= ? GROUP BY record_type", (week_ago,))
            rows = cur.fetchall()
        return [{"type": r[0], "count": r[1], "avg_score": round(r[2], 1) if r[2] else 0} for r in rows]

    @staticmethod
    def daily_mood_trend():
        """近7天情绪变化趋势"""
        trend = []
        with db_connection() as conn:
            cur = conn.cursor()
            for i in range(6, -1, -1):
                day = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
                cur.execute("SELECT AVG(score) FROM records WHERE record_type='emotion' AND created_at LIKE ?", (f"{day}%",))
                row = cur.fetchone()
                trend.append({"date": day[-5:], "avg_score": round(row[0], 1) if row[0] else 0})
        return trend

    @staticmethod
    def meal_frequency():
        """近7天用餐频率"""
        with db_connection() as conn:
            cur = conn.cursor()
            week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            cur.execute("SELECT created_at FROM records WHERE record_type='meal' AND created_at >= ?", (week_ago,))
            rows = cur.fetchall()
        days = [r[0][:10] for r in rows]
        return dict(Counter(days))
    
    @staticmethod
    def mood_trend_for_chart():
        """返回情绪趋势图表数据（给 Streamlit 用）"""
        data = Analytics.daily_mood_trend()
        if not data:
            return {"dates": [], "scores": []}
        return {
            "dates": [d["date"] for d in data],
            "scores": [d["avg_score"] for d in data]
        }

    @staticmethod
    def meal_freq_for_chart():
        """返回用餐频率图表数据（给 Streamlit 用）"""
        freq = Analytics.meal_frequency()
        if not freq:
            return {"dates": [], "counts": []}
        dates = sorted(freq.keys())[-7:]
        counts = [freq.get(d, 0) for d in dates]
        return {"dates": dates, "counts": counts}
    
    @staticmethod
    def get_weekly_records():
        with db_connection() as conn:
            cur = conn.cursor()
            week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            cur.execute(
                "SELECT record_type, content, score, created_at FROM records WHERE created_at >= ? ORDER BY created_at ASC",
                (week_ago,)
            )
            rows = cur.fetchall()
        return [
            {
                "type": r[0],
                "content": r[1],
                "score": r[2],
                "time": r[3]
            }
            for r in rows
        ]

    @staticmethod
    def learning_curve():
        """获取学习曲线数据"""
        return LearningTracker.get_learning_curve(days=30)

    @staticmethod
    def knowledge_growth():
        """获取知识积累曲线"""
        return LearningTracker.get_knowledge_growth(days=90)

    @staticmethod  
    def learning_time_distribution():
        """获取学习时间分布"""
        return LearningTracker.get_learning_time_distribution(days=30)

    @staticmethod
    def get_learning_summary():
        """获取学习汇总信息"""
        curve = Analytics.learning_curve()
        growth = Analytics.knowledge_growth()
        time_dist = Analytics.learning_time_distribution()
        
        return {
            "learning_curve": curve,
            "knowledge_growth": growth,
            "time_distribution": time_dist
        }
