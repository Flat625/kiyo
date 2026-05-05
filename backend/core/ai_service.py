import json, re, os
import sys

# 在导入 OpenAI 之前，确保代理变量被移除
os.environ.pop('HTTP_PROXY', None)
os.environ.pop('HTTPS_PROXY', None)
os.environ.pop('http_proxy', None)
os.environ.pop('https_proxy', None)

# 添加当前目录到 sys.path
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from openai import OpenAI
from config.settings import DOUBAO_API_KEY, DOUBAO_BASE_URL, DOUBAO_MODEL
from core.prompts import CHAT_SYSTEM, ANALYZE_RECORD, PLAN_LEARNING
from core.logger import logger

class AIService:
    def __init__(self):
        self.client = OpenAI(api_key=DOUBAO_API_KEY, base_url=DOUBAO_BASE_URL)
        self.model = DOUBAO_MODEL
        logger.info(f"API Key: {DOUBAO_API_KEY[:10]}..." if DOUBAO_API_KEY else "API Key: 未设置")


    def chat(self, message: str, context: list = None) -> str:
        system_prompt = CHAT_SYSTEM
        messages = [{"role": "system", "content": system_prompt}]
        if context:
            messages.extend(context)
        messages.append({"role": "user", "content": message})
        resp = self.client.chat.completions.create(model=self.model, messages=messages, temperature=0.7)
        return resp.choices[0].message.content

    def generate_learning_plan(self, idea: str) -> list:
        prompt = PLAN_LEARNING.format(idea=idea)
        resp = self.client.chat.completions.create(model=self.model,
            messages=[{"role":"user","content":prompt}], temperature=0.7)
        content = resp.choices[0].message.content
        m = re.search(r'\[.*\]', content, re.DOTALL)
        return json.loads(m.group()) if m else []

    def analyze_record(self, content: str) -> dict:
        prompt = ANALYZE_RECORD.format(content=content)
        resp = self.client.chat.completions.create(model=self.model,
            messages=[{"role":"user","content":prompt}], temperature=0.3)
        try:
            m = re.search(r'\{.*\}', resp.choices[0].message.content, re.DOTALL)
            return json.loads(m.group()) if m else {}
        except:
            return {}