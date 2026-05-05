from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from collections import Counter, defaultdict
import statistics
import sys
import os

# 添加当前目录到 sys.path
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from core.database import db_connection
from core.logger import get_logger

logger = get_logger("enhanced_analytics")


class AnomalyDetector:
    """异常检测器"""

    @staticmethod
    def detect_score_anomalies(record_type: str, days: int = 30, threshold: float = 2.0) -> List[Dict]:
        """
        检测评分异常（基于 Z-score）
        threshold: Z-score 阈值，超过则视为异常
        """
        with db_connection() as conn:
            cur = conn.cursor()

            start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            cur.execute(
                "SELECT score, created_at FROM records WHERE record_type=? AND created_at >= ? AND score > 0",
                (record_type, start_date)
            )
            rows = cur.fetchall()

        if len(rows) < 5:
            return []

        scores = [r[0] for r in rows]
        mean = statistics.mean(scores)
        stdev = statistics.stdev(scores) if len(scores) > 1 else 0

        if stdev == 0:
            return []

        anomalies = []
        for score, created_at in rows:
            z_score = abs((score - mean) / stdev)
            if z_score > threshold:
                anomalies.append({
                    "score": score,
                    "created_at": created_at,
                    "z_score": round(z_score, 2),
                    "mean": round(mean, 2),
                    "type": "high" if score > mean else "low"
                })

        return anomalies

    @staticmethod
    def detect_missing_records(record_type: str, days: int = 7) -> List[str]:
        """检测缺失的记录日期"""
        dates = []
        with db_connection() as conn:
            cur = conn.cursor()

            for i in range(days):
                date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
                cur.execute(
                    "SELECT COUNT(*) FROM records WHERE record_type=? AND created_at LIKE ?",
                    (record_type, f"{date}%")
                )
                count = cur.fetchone()[0]
                if count == 0:
                    dates.append(date)

        return dates


class PatternRecognizer:
    """模式识别器"""

    @staticmethod
    def find_weekly_pattern(record_type: str, days: int = 56) -> Dict[str, Any]:
        """
        识别周模式（8周数据）
        返回每天的平均评分和计数
        """
        day_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        pattern = defaultdict(list)

        with db_connection() as conn:
            cur = conn.cursor()

            start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            cur.execute(
                "SELECT score, created_at FROM records WHERE record_type=? AND created_at >= ?",
                (record_type, start_date)
            )
            rows = cur.fetchall()

        for score, created_at in rows:
            dt = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")
            weekday = dt.weekday()
            pattern[weekday].append(score)

        result = {}
        for weekday in range(7):
            scores = pattern.get(weekday, [])
            if scores:
                result[day_names[weekday]] = {
                    "avg_score": round(statistics.mean(scores), 2),
                    "count": len(scores)
                }
            else:
                result[day_names[weekday]] = {"avg_score": 0, "count": 0}

        return result

    @staticmethod
    def find_time_pattern(record_type: str, days: int = 30) -> Dict[str, Any]:
        """
        识别时间模式
        返回不同时段的平均评分
        """
        time_slots = {
            "凌晨 (0-6)": [],
            "上午 (6-12)": [],
            "下午 (12-18)": [],
            "晚上 (18-24)": []
        }

        with db_connection() as conn:
            cur = conn.cursor()

            start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            cur.execute(
                "SELECT score, created_at FROM records WHERE record_type=? AND created_at >= ?",
                (record_type, start_date)
            )
            rows = cur.fetchall()

        for score, created_at in rows:
            hour = int(created_at.split()[1].split(":")[0])
            if 0 <= hour < 6:
                time_slots["凌晨 (0-6)"].append(score)
            elif 6 <= hour < 12:
                time_slots["上午 (6-12)"].append(score)
            elif 12 <= hour < 18:
                time_slots["下午 (12-18)"].append(score)
            else:
                time_slots["晚上 (18-24)"].append(score)

        result = {}
        for slot, scores in time_slots.items():
            result[slot] = {
                "avg_score": round(statistics.mean(scores), 2) if scores else 0,
                "count": len(scores)
            }

        return result

    @staticmethod
    def detect_streak(record_type: str, target_score: int = 3) -> Dict[str, Any]:
        """
        检测连续记录天数
        """
        with db_connection() as conn:
            cur = conn.cursor()

            cur.execute(
                "SELECT created_at, score FROM records WHERE record_type=? ORDER BY created_at DESC LIMIT 100",
                (record_type,)
            )
            rows = cur.fetchall()

        if not rows:
            return {"current_streak": 0, "best_streak": 0, "last_date": None}

        current_streak = 0
        best_streak = 0
        temp_streak = 0
        last_date = None

        prev_date = None
        for created_at, score in reversed(rows):
            date = created_at[:10]

            if score >= target_score:
                if prev_date is None:
                    temp_streak = 1
                else:
                    curr = datetime.strptime(date, "%Y-%m-%d")
                    expected = datetime.strptime(prev_date, "%Y-%m-%d") + timedelta(days=1)
                    if curr == expected:
                        temp_streak += 1
                    else:
                        temp_streak = 1

                best_streak = max(best_streak, temp_streak)
                prev_date = date
            else:
                if temp_streak > current_streak:
                    current_streak = temp_streak
                temp_streak = 0
                prev_date = None

        current_streak = max(current_streak, temp_streak)

        return {
            "current_streak": current_streak,
            "best_streak": best_streak,
            "last_date": rows[-1][0][:10] if rows else None
        }


class CorrelationAnalyzer:
    """相关性分析器"""

    @staticmethod
    def analyze_correlation(days: int = 30) -> Dict[str, Any]:
        """
        分析不同记录类型之间的相关性
        """
        data = {}
        with db_connection() as conn:
            cur = conn.cursor()

            start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

            for record_type in ["meal", "emotion", "energy"]:
                cur.execute(
                    "SELECT created_at, score FROM records WHERE record_type=? AND created_at >= ?",
                    (record_type, start_date)
                )
                rows = cur.fetchall()

                daily_scores = defaultdict(list)
                for created_at, score in rows:
                    date = created_at[:10]
                    daily_scores[date].append(score)

                data[record_type] = {
                    date: scores[0] for date, scores in daily_scores.items()
                }

        common_dates = set(data["meal"].keys()) & set(data["emotion"].keys()) & set(data["energy"].keys())

        correlations = {}
        pairs = [
            ("meal_emotion", "meal", "emotion"),
            ("meal_energy", "meal", "energy"),
            ("emotion_energy", "emotion", "energy")
        ]

        for name, type1, type2 in pairs:
            scores1 = [data[type1].get(d, 0) for d in common_dates]
            scores2 = [data[type2].get(d, 0) for d in common_dates]

            if len(scores1) >= 5:
                corr = statistics.correlation(scores1, scores2) if hasattr(statistics, 'correlation') else 0
                correlations[name] = {
                    "coefficient": round(corr, 3) if corr else 0,
                    "interpretation": CorrelationAnalyzer._interpret_correlation(corr) if corr else "数据不足"
                }
            else:
                correlations[name] = {"coefficient": 0, "interpretation": "数据不足"}

        return correlations

    @staticmethod
    def _interpret_correlation(r: float) -> str:
        """解释相关系数"""
        if r is None or abs(r) < 0.1:
            return "无相关性"
        elif 0.1 <= r < 0.3:
            return "弱正相关" if r > 0 else "弱负相关"
        elif 0.3 <= r < 0.6:
            return "中等正相关" if r > 0 else "中等负相关"
        elif 0.6 <= r < 0.8:
            return "较强正相关" if r > 0 else "较强负相关"
        elif r >= 0.8:
            return "强正相关" if r > 0 else "强负相关"
        return "无相关性"


class LearningTracker:

    SKILL_TREE = {
        "编程基础": ["变量与数据类型", "控制流", "函数", "面向对象"],
        "数据结构": ["数组与链表", "栈与队列", "树与图", "哈希表"],
        "算法": ["排序算法", "搜索算法", "动态规划", "贪心算法"],
        "系统设计": ["架构基础", "数据库设计", "API设计", "微服务"]
    }

    @staticmethod
    def get_skill_progress() -> Dict[str, Any]:
        """获取技能树进度"""
        progress = {}
        with db_connection() as conn:
            cur = conn.cursor()

            for category, skills in LearningTracker.SKILL_TREE.items():
                progress[category] = {
                    "total": len(skills),
                    "completed": 0,
                    "skills": []
                }

                for skill in skills:
                    cur.execute(
                        "SELECT COUNT(*) FROM memories WHERE content LIKE ? AND source='auto'",
                        (f"%{skill}%",)
                    )
                    count = cur.fetchone()[0]
                    is_completed = count >= 3

                    if is_completed:
                        progress[category]["completed"] += 1

                    progress[category]["skills"].append({
                        "name": skill,
                        "completed": is_completed,
                        "mentions": count
                    })

        return progress

    @staticmethod
    def get_achievements() -> List[Dict[str, Any]]:
        """获取成就列表"""
        achievements = []

        with db_connection() as conn:
            cur = conn.cursor()

            cur.execute("SELECT COUNT(*) FROM records WHERE record_type='learning' AND created_at >= date('now', '-7 days')")
            weekly_learning = cur.fetchone()[0]
            if weekly_learning >= 7:
                achievements.append({
                    "id": "learning_streak_7",
                    "name": "连续学习一周",
                    "description": "连续7天有学习记录",
                    "icon": "📚",
                    "unlocked": True
                })

            cur.execute("SELECT COUNT(*) FROM memories WHERE source='auto'")
            total_memories = cur.fetchone()[0]
            if total_memories >= 50:
                achievements.append({
                    "id": "memory_master",
                    "name": "记忆大师",
                    "description": "积累50条以上记忆",
                    "icon": "🧠",
                    "unlocked": True
                })

        default_achievements = [
            {"id": "first_chat", "name": "初次对话", "description": "开始第一次对话", "icon": "👋", "unlocked": False},
            {"id": "first_plan", "name": "制定计划", "description": "创建第一个学习计划", "icon": "📝", "unlocked": False},
            {"id": "first_record", "name": "记录生活", "description": "添加第一条生活记录", "icon": "📖", "unlocked": False}
        ]

        for ach in default_achievements:
            if ach["id"] not in [a["id"] for a in achievements]:
                achievements.append({**ach, "unlocked": False})

        return achievements
    

    @staticmethod
    def get_learning_curve(days: int = 30) -> Dict[str, Any]:
        daily_data = defaultdict(list)
        
        with db_connection() as conn:
            cur = conn.cursor()

            start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            cur.execute(
                "SELECT created_at, score FROM records WHERE record_type='note' AND created_at >= ?",
                (start_date,)
            )
            rows = cur.fetchall()

        for created_at, score in rows:
            date = created_at[:10]
            daily_data[date].append(score)

        dates = []
        counts = []
        avg_scores = []

        for i in range(days):
            date = (datetime.now() - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
            scores = daily_data.get(date, [])
            
            dates.append(date[-5:])
            counts.append(len(scores))
            avg_scores.append(round(statistics.mean(scores), 1) if scores else 0)

        return {
            "dates": dates,
            "counts": counts,
            "avg_scores": avg_scores,
            "total_records": len(rows),
            "active_days": len([d for d in daily_data.values() if d])
        }

    @staticmethod
    def get_knowledge_growth(days: int = 90) -> Dict[str, Any]:
        with db_connection() as conn:
            cur = conn.cursor()

            start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            cur.execute(
                "SELECT created_at FROM memories WHERE created_at >= ? ORDER BY created_at ASC",
                (start_date,)
            )
            rows = cur.fetchall()

        cumulative = []
        dates = []
        count = 0
        prev_date = None

        for created_at in rows:
            date = created_at[0][:10]
            if date != prev_date:
                dates.append(date[-5:])
                prev_date = date
            count += 1
            cumulative.append(count)

        return {
            "dates": dates,
            "cumulative": cumulative,
            "total_memories": count
        }

    @staticmethod
    def get_learning_time_distribution(days: int = 30) -> Dict[str, Any]:
   
        time_slots = {
            "早晨 (6-9)": 0,
            "上午 (9-12)": 0,
            "下午 (12-18)": 0,
            "晚上 (18-22)": 0,
            "深夜 (22-24)": 0
        }

        with db_connection() as conn:
            cur = conn.cursor()

            start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            cur.execute(
                "SELECT created_at FROM records WHERE record_type='note' AND created_at >= ?",
                (start_date,)
            )
            rows = cur.fetchall()

        for created_at in rows:
            hour = int(created_at[0].split()[1].split(":")[0])
            if 6 <= hour < 9:
                time_slots["早晨 (6-9)"] += 1
            elif 9 <= hour < 12:
                time_slots["上午 (9-12)"] += 1
            elif 12 <= hour < 18:
                time_slots["下午 (12-18)"] += 1
            elif 18 <= hour < 22:
                time_slots["晚上 (18-22)"] += 1
            elif 22 <= hour < 24:
                time_slots["深夜 (22-24)"] += 1

        return {
            "time_slots": list(time_slots.keys()),
            "counts": list(time_slots.values()),
            "total": sum(time_slots.values())
        }
