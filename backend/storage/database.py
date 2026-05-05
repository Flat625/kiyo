# storage/database.py —— SQLite 数据库初始化 + 所有 CRUD 操作
import sqlite3
from pathlib import Path
from datetime import datetime

# 数据库文件路径：storage/data/Agent.db
DB_DIR = Path(__file__).parent / "data"
DB_PATH = DB_DIR / "Agent.db"

def get_connection():
    """获取数据库连接，自动创建目录和文件"""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row  # 让查询结果支持 dict 访问
    conn.execute("PRAGMA foreign_keys = ON")  # 开启外键约束
    return conn

def init_db():
    """初始化数据库：创建所有表（如果不存在）"""
    conn = get_connection()
    cursor = conn.cursor()

    # ----- 话题表 -----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            color TEXT DEFAULT '#2B5A6C',
            created_at TEXT NOT NULL
        )
    """)

    # ----- 对话表 -----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic_id INTEGER NOT NULL,
            title TEXT DEFAULT '新对话',
            created_at TEXT NOT NULL,
            FOREIGN KEY (topic_id) REFERENCES topics(id) ON DELETE CASCADE
        )
    """)

    # ----- 消息表 -----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
        )
    """)

    # ----- 记忆表 -----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic_id INTEGER,
            content TEXT NOT NULL,
            source TEXT DEFAULT 'manual' CHECK(source IN ('auto', 'manual')),
            created_at TEXT NOT NULL,
            FOREIGN KEY (topic_id) REFERENCES topics(id) ON DELETE SET NULL
        )
    """)

    # ----- 文档表 -----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic_id INTEGER,
            title TEXT NOT NULL,
            content TEXT DEFAULT '',
            file_path TEXT DEFAULT '',
            file_type TEXT DEFAULT 'md',
            created_at TEXT NOT NULL,
            FOREIGN KEY (topic_id) REFERENCES topics(id) ON DELETE CASCADE
        )
    """)

    # ----- 任务表（保留，用于专注功能）-----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            estimated_minutes REAL DEFAULT 0,
            status TEXT DEFAULT 'active',
            created_at TEXT NOT NULL
        )
    """)

    # ----- 专注记录表（保留）-----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS focus_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            task_name TEXT NOT NULL,
            planned_minutes REAL NOT NULL,
            actual_minutes REAL DEFAULT 0,
            difficulty INTEGER DEFAULT 0,
            focus_level INTEGER DEFAULT 0,
            notes TEXT DEFAULT '',
            finish_time TEXT NOT NULL,
            FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
        )
    """)

    conn.commit()
    conn.close()
    print("✅ 数据库初始化成功")

# ===================== 话题 CRUD =====================
def add_topic(name, description='', color='#2B5A6C'):
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "INSERT INTO topics (name, description, color, created_at) VALUES (?, ?, ?, ?)",
        (name, description, color, now)
    )
    conn.commit()
    tid = cursor.lastrowid
    conn.close()
    return tid

def get_all_topics():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM topics ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def delete_topic(tid):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM topics WHERE id=?", (tid,))
    conn.commit()
    conn.close()

# ===================== 对话 CRUD =====================
def add_conversation(topic_id, title='新对话'):
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "INSERT INTO conversations (topic_id, title, created_at) VALUES (?, ?, ?)",
        (topic_id, title, now)
    )
    conn.commit()
    cid = cursor.lastrowid
    conn.close()
    return cid

def get_conversations_by_topic(topic_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM conversations WHERE topic_id=? ORDER BY created_at DESC",
        (topic_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def delete_conversation(cid):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM conversations WHERE id=?", (cid,))
    conn.commit()
    conn.close()

# ===================== 消息 CRUD =====================
def add_message(conversation_id, role, content):
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "INSERT INTO messages (conversation_id, role, content, created_at) VALUES (?, ?, ?, ?)",
        (conversation_id, role, content, now)
    )
    conn.commit()
    mid = cursor.lastrowid
    conn.close()
    return mid

def get_messages_by_conversation(conversation_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM messages WHERE conversation_id=? ORDER BY created_at ASC",
        (conversation_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ===================== 记忆 CRUD =====================
def add_memory(topic_id, content, source='manual'):
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "INSERT INTO memories (topic_id, content, source, created_at) VALUES (?, ?, ?, ?)",
        (topic_id, content, source, now)
    )
    conn.commit()
    mid = cursor.lastrowid
    conn.close()
    return mid

def get_memories_by_topic(topic_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM memories WHERE topic_id=? ORDER BY created_at DESC",
        (topic_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_all_memories():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM memories ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def delete_memory(mid):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM memories WHERE id=?", (mid,))
    conn.commit()
    conn.close()

# 注意：tasks 和 focus_sessions 的 CRUD 保留旧代码，暂不贴出，需要时再补