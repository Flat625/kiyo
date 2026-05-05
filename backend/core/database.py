# backend/core/database.py —— SQLite 数据库（建表 + 所有 CRUD）
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Generator, Optional
import sys
import os

# 添加当前目录到 sys.path
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from config.settings import DB_PATH
from core.logger import logger  


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db_connection() -> Generator[sqlite3.Connection, None, None]:
    """数据库连接上下文管理器，自动处理提交/回滚/关闭"""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""CREATE TABLE IF NOT EXISTS topics (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
        description TEXT DEFAULT '', color TEXT DEFAULT '#2B5A6C', created_at TEXT NOT NULL)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT, topic_id INTEGER NOT NULL,
        title TEXT DEFAULT '新对话', created_at TEXT NOT NULL,
        FOREIGN KEY (topic_id) REFERENCES topics(id) ON DELETE CASCADE)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id INTEGER NOT NULL,
        role TEXT CHECK(role IN ('user','assistant','thinking')) NOT NULL,
        content TEXT NOT NULL, created_at TEXT NOT NULL,
        FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS memories (
        id INTEGER PRIMARY KEY AUTOINCREMENT, topic_id INTEGER,
        content TEXT NOT NULL, source TEXT DEFAULT 'manual' CHECK(source IN ('auto','manual')),
        created_at TEXT NOT NULL,
        FOREIGN KEY (topic_id) REFERENCES topics(id) ON DELETE SET NULL)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT, topic_id INTEGER,
        title TEXT NOT NULL, content TEXT DEFAULT '', file_path TEXT DEFAULT '',
        file_type TEXT DEFAULT 'md', created_at TEXT NOT NULL,
        FOREIGN KEY (topic_id) REFERENCES topics(id) ON DELETE CASCADE)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS records (
        id INTEGER PRIMARY KEY AUTOINCREMENT, record_type TEXT NOT NULL CHECK(record_type IN ('meal','emotion','energy','note')),
        content TEXT NOT NULL, score INTEGER DEFAULT 0, created_at TEXT NOT NULL)""")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            estimated_minutes REAL DEFAULT 25,
            status TEXT DEFAULT 'active',
            created_at TEXT NOT NULL
        )
    """)

    cur.execute("CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_records_type ON records(record_type)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_records_created_at ON records(created_at)")

    conn.commit()
    conn.close()


# topic
def create_topic(name: str, description: str = '') -> int:
    return _insert("topics", {"name": name, "description": description, "created_at": _now()})


def get_all_topics() -> List[Dict[str, Any]]:
    return _fetch_all("SELECT * FROM topics ORDER BY created_at DESC")


def delete_topic(tid: int) -> None:
    _execute("DELETE FROM topics WHERE id=?", (tid,))


# con
def create_conversation(topic_id: int, title: str = '新对话') -> int:
    return _insert("conversations", {"topic_id": topic_id, "title": title, "created_at": _now()})


def get_conversations_by_topic(tid: int) -> List[Dict[str, Any]]:
    return _fetch_all("SELECT * FROM conversations WHERE topic_id=? ORDER BY created_at DESC", (tid,))


# msg
def add_message(conv_id: int, role: str, content: str) -> int:
    """添加消息，自动确保对话和话题都存在"""
    with db_connection() as conn:
        cur = conn.cursor()

        cur.execute("SELECT id FROM topics WHERE id = 1")
        if not cur.fetchone():
            now = _now()
            cur.execute(
                "INSERT INTO topics (id, name, description, color, created_at) VALUES (1, '默认话题', '系统自动创建', '#2B5A6C', ?)",
                (now,)
            )

        cur.execute("SELECT id FROM conversations WHERE id = ?", (conv_id,))
        if not cur.fetchone():
            now = _now()
            cur.execute(
                "INSERT INTO conversations (id, topic_id, title, created_at) VALUES (?, 1, '默认对话', ?)",
                (conv_id, now)
            )

    return _insert("messages", {
        "conversation_id": conv_id,
        "role": role,
        "content": content,
        "created_at": _now()
    })


def get_messages_by_conversation(cid: int) -> List[Dict[str, Any]]:
    return _fetch_all("SELECT * FROM messages WHERE conversation_id=? ORDER BY created_at ASC", (cid,))


# memo
def add_memory(topic_id: Optional[int], content: str, source: str = 'manual') -> int:
    return _insert("memories", {"topic_id": topic_id, "content": content, "source": source, "created_at": _now()})


def get_all_memories() -> List[Dict[str, Any]]:
    return _fetch_all("SELECT * FROM memories ORDER BY created_at DESC")


def delete_memory(mid: int) -> None:
    _execute("DELETE FROM memories WHERE id=?", (mid,))


# docx
def add_document(topic_id: Optional[int], title: str, content: str = '', file_path: str = '', file_type: str = 'md') -> int:
    return _insert("documents", {"topic_id": topic_id, "title": title, "content": content, "file_path": file_path, "file_type": file_type, "created_at": _now()})


def get_documents_by_topic(tid: int) -> List[Dict[str, Any]]:
    return _fetch_all("SELECT * FROM documents WHERE topic_id=? ORDER BY created_at DESC", (tid,))


def delete_document(did: int) -> None:
    _execute("DELETE FROM documents WHERE id=?", (did,))


# eat emotion
def add_record(record_type: str, content: str, score: int = 0) -> int:
    return _insert("records", {"record_type": record_type, "content": content, "score": score, "created_at": _now()})


def get_records_by_type(rtype: str, limit: int = 30) -> List[Dict[str, Any]]:
    return _fetch_all("SELECT * FROM records WHERE record_type=? ORDER BY created_at DESC LIMIT ?", (rtype, limit))


def get_records_by_date(date_str: str) -> List[Dict[str, Any]]:
    return _fetch_all("SELECT * FROM records WHERE created_at LIKE ? ORDER BY created_at DESC", (f"{date_str}%",))


# add_task
def add_task(name: str, description: str = '', estimated_minutes: float = 25) -> int:
    return _insert("tasks", {
        "name": name,
        "description": description,
        "estimated_minutes": estimated_minutes,
        "status": "active",
        "created_at": _now()
    })


def get_all_task() -> List[Dict[str, Any]]:
    return _fetch_all("SELECT * FROM tasks ORDER BY created_at DESC")


# inner
def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _insert(table: str, data: dict) -> int:
    with db_connection() as conn:
        cur = conn.cursor()
        cols = ','.join(data.keys())
        ph = ','.join(['?'] * len(data))
        cur.execute(f"INSERT INTO {table} ({cols}) VALUES ({ph})", tuple(data.values()))
        return cur.lastrowid


def _fetch_all(sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
    with db_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()
        return [dict(r) for r in rows]


def _execute(sql: str, params: tuple = ()) -> None:
    with db_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
