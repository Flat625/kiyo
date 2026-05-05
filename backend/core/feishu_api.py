# backend/core/feishu_api.py —— 飞书集成模块
import requests
import logging
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

import lark_oapi as lark
from .logger import logger

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

FEISHU_APP_ID = os.getenv("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")

BASE_URL = "https://open.feishu.cn"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
log = logging.getLogger(__name__)


class FeishuClient:
    def __init__(self):
        self.app_id = FEISHU_APP_ID
        self.app_secret = FEISHU_APP_SECRET
        self.base_url = BASE_URL
        self.token = None
        self._token_expires_at = 0
        
        app_id_preview = self.app_id[:10] + "..." if self.app_id and len(self.app_id) > 10 else self.app_id
        logger.info(f"FeishuClient initialized, APP ID: {app_id_preview}")

    def _common_post(self, path: str, data: dict, need_token: bool = False) -> Optional[dict]:
        url = self.base_url + path
        headers = {"Content-Type": "application/json"}

        if need_token:
            token = self.get_tenant_token()
            if not token:
                logger.error("Failed to get token, request cancelled")
                return None
            headers["Authorization"] = f"Bearer {token}"

        try:
            response = requests.post(url=url, headers=headers, json=data, timeout=15)
            response.raise_for_status()
            result = response.json()

            if result.get("code", 0) != 0:
                log.error(f"Feishu API error: code={result.get('code')}, msg={result.get('mag')}")
                return None
            
            return result
        except requests.ConnectionError:
            log.error("Network connection failed")
        except requests.Timeout:
            log.error("Network connection timeout")
        except Exception as e:
            log.error(f"Request failed: {str(e)}")

        return None

    def get_tenant_token(self) -> Optional[str]:
        if self.token and time.time() < (self._token_expires_at - 60):
            return self.token

        path = "/open-apis/auth/v3/tenant_access_token/internal"
        data = {
            "app_id": self.app_id,
            "app_secret": self.app_secret
        }

        result = self._common_post(path, data, need_token=False)

        if result:
            self.token = result.get("tenant_access_token")
            expire = result.get("expire", 7200)
            self._token_expires_at = time.time() + expire
            log.info("Token refreshed successfully")
            return self.token

        log.error("Token acquisition failed")
        return None

    def send_message(self, receive_id: str, content: str, receive_id_type: str = "open_id") -> Optional[dict]:
        if not self.token:
            self.get_tenant_token()

        path = "/open-apis/im/v1/message"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        params = {"receive_id_type": receive_id_type}

        data = {
            "receive_id": receive_id,
            "content": content,
            "msg_type": "text"
        }

        try:
            response = requests.post(
                self.base_url + path,
                headers=headers,
                json=data,
                params=params
            )
            return response.json()
        except Exception as e:
            log.error(f"Failed to send message: {e}")
            return None

    def send_card(self, receive_id: str, card_json: str, receive_id_type: str = "open_id") -> bool:
        client = (
            lark.Client.builder()
            .app_id(self.app_id)
            .app_secret(self.app_secret)
            .build()
        )

        request = (
            lark.im.v1.message.CreateMessageRequest.builder()
            .receive_id_type(receive_id_type)
            .request_body(
                lark.im.v1.message.CreateMessageRequestBody.builder()
                .receive_id(receive_id)
                .msg_type("interactive")
                .content(card_json)
                .build()
            )
            .build()
        )

        response = lark.im.v1.message.Message.create(client, request)

        if response.success():
            log.info("Card message sent successfully!")
            return True
        else:
            log.error(f"Card message failed: {response.msg}")
            return False

    def send_learning_reminder(self, receive_id: str, curve_data: dict) -> bool:
        card = {
            "config": {"wide_screen_mode": True},
            "elements": [
                {
                    "tag": "markdown",
                    "content": "**📚 学习提醒**"
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"最近 {curve_data.get('days', 30)} 天学习数据：\n"
                                   f"• 总记录数：{curve_data.get('total_records', 0)} 条\n"
                                   f"• 活跃天数：{curve_data.get('active_days', 0)} 天\n"
                                   f"• 今日学习：{curve_data.get('today_count', 0)} 条"
                    }
                },
                {"tag": "hr"},
                {
                    "tag": "markdown",
                    "content": "💡 坚持每天学习，效果会更好哦！"
                }
            ]
        }
        return self.send_card(receive_id, card)

    def create_calendar_event(self, summary: str, start_time: str, end_time: str, 
                              calendar_id: str = None, timezone: str = "Asia/Shanghai") -> Optional[dict]:
        if not calendar_id:
            calendar_id = os.getenv("FEISHU_CALENDER_ID", "primary")
        if not self.token:
            self.get_tenant_token()

        url_path = f"/open-apis/calendar/v4/calendars/{calendar_id}/events"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        data = {
            "summary": summary,
            "start_time": {
                "date_time": start_time,
                "timezone": timezone
            },
            "end_time": {
                "date_time": end_time,
                "timezone": timezone
            }
        }

        try:
            response = requests.post(
                self.base_url + url_path,
                headers=headers,
                json=data,
                timeout=15
            )
            return response.json()
        except Exception as e:
            log.error(f"Failed to create calendar event: {e}")
            return None

    def get_calendar_events(self, start_time: str, end_time: str) -> Optional[List[dict]]:
        if not self.token:
            self.get_tenant_token()

        url = f"{self.base_url}/open-apis/calendar/v4/events"
        headers = {"Authorization": f"Bearer {self.token}"}
        params = {
            "start_time": start_time,
            "end_time": end_time
        }

        try:
            response = requests.get(url, headers=headers, params=params, timeout=15)
            response.raise_for_status()
            result = response.json()
            
            if result.get("code", 0) == 0:
                return result.get("data", {}).get("items", [])
            return None
        except Exception as e:
            log.error(f"Failed to get calendar events: {e}")
            return None

    def sync_calendar_to_tasks(self, days: int = 7) -> List[Dict[str, Any]]:
        from .database import add_task

        start_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00")
        end_time = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S+08:00")

        events = self.get_calendar_events(start_time, end_time)
        if not events:
            return []

        added_tasks = []
        for event in events:
            task_name = event.get("summary", "Untitled Event")
            description = event.get("description", "")
            start = event.get("start_time", {}).get("date_time", "")
            
            task_id = add_task(
                name=task_name,
                description=f"{description}\n来源: 飞书日历".strip(),
                estimated_minutes=30
            )
            added_tasks.append({"id": task_id, "name": task_name, "start": start})

        logger.info(f"Synced {len(added_tasks)} calendar events to tasks")
        return added_tasks

    def add_record(self, app_token: str, table_id: str, fields: dict) -> bool:
        path = f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records"
        data = {"fields": fields}
        result = self._common_post(path, data, need_token=True)

        if result:
            log.info(f"Record added successfully: {fields}")
            return True

        log.error(f"Record addition failed: {fields}")
        return False

    def list_records(self, app_token: str, table_id: str, page_size: int = 100) -> List[dict]:
        path = f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records"
        all_records = []
        page_token = None

        while True:
            params = {"page_size": page_size}
            if page_token:
                params["page_token"] = page_token

            query_string = "&".join([f"{k}={v}" for k, v in params.items()])
            full_path = f"{path}?{query_string}" if query_string else path

            url = self.base_url + full_path
            token = self.get_tenant_token()

            if not token:
                break

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }

            try:
                response = requests.get(url, headers=headers, timeout=15)
                response.raise_for_status()
                result = response.json()

                if result.get("code", 0) != 0:
                    log.error(f"Failed to get records: {result.get('mag')}")
                    break

                data = result.get("data", {})
                items = data.get("items", [])
                all_records.extend(items)

                page_token = data.get("page_token")
                if not page_token or not data.get("has_more", False):
                    break

            except Exception as e:
                log.error(f"Exception while getting records: {str(e)}")
                break

        log.info(f"Retrieved {len(all_records)} records")
        return all_records

    def update_record(self, app_token: str, table_id: str, record_id: str, fields: dict) -> bool:
        path = f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}"
        data = {"fields": fields}
        result = self._common_post(path, data, need_token=True)

        if result:
            log.info(f"Record updated successfully: record_id={record_id}")
            return True

        return False

    def send_daily_summary(self, receive_id: str, summary_data: dict) -> bool:
        card = {
            "config": {"wide_screen_mode": True},
            "elements": [
                {"tag": "markdown", "content": "**🌙 每日学习总结**"},
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": (
                            f"**日期**：{summary_data.get('date', 'N/A')}\n\n"
                            f"📖 **学习记录**：{summary_data.get('learning_count', 0)} 条\n"
                            f"😀 **情绪指数**：{summary_data.get('emotion_score', 0)}/5\n"
                            f"⚡ **能量水平**：{summary_data.get('energy_score', 0)}/5\n\n"
                            f"💪 今日加油！"
                        )
                    }
                }
            ]
        }
        return self.send_card(receive_id, card)


if __name__ == "__main__":
    client = FeishuClient()
    
    token = client.get_tenant_token()
    if not token:
        print("❌ Token acquisition failed, please check FEISHU_APP_ID and FEISHU_APP_SECRET in .env")
        exit(1)
    print(f"✅ Token acquired successfully")

    test_open_id = os.getenv("FEISHU_TEST_OPEN_ID", "")
    if test_open_id:
        result = client.send_message(test_open_id, "🧪 Kiyo Feishu Integration Test")
        print(f"✅ Message sent: {result}")
    else:
        print("⚠️ FEISHU_TEST_OPEN_ID not set, skipping message test")
