"""
db.py — tiny SQLite wrapper for the bot.
Stores: notes, user violation counters (spam/bad-words), and per-chat settings.
No external DB server needed — works fine on a free host with a small group.
"""

import sqlite3
import time
from contextlib import contextmanager

DB_PATH = "bot_data.db"


def init_db():
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS notes (
                chat_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                content TEXT NOT NULL,
                added_by INTEGER,
                created_at INTEGER,
                PRIMARY KEY (chat_id, name)
            );

            CREATE TABLE IF NOT EXISTS violations (
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                kind TEXT NOT NULL,          -- 'spam' or 'badword'
                count INTEGER NOT NULL DEFAULT 0,
                last_ts INTEGER,
                PRIMARY KEY (chat_id, user_id, kind)
            );

            CREATE TABLE IF NOT EXISTS message_log (
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                ts INTEGER NOT NULL
            );
            """
        )


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# ---------- Notes ----------

def save_note(chat_id: int, name: str, content: str, added_by: int):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO notes (chat_id, name, content, added_by, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (chat_id, name.lower(), content, added_by, int(time.time())),
        )


def get_note(chat_id: int, name: str):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT content FROM notes WHERE chat_id=? AND name=?",
            (chat_id, name.lower()),
        ).fetchone()
        return row[0] if row else None


def delete_note(chat_id: int, name: str) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM notes WHERE chat_id=? AND name=?", (chat_id, name.lower())
        )
        return cur.rowcount > 0


def list_notes(chat_id: int):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT name FROM notes WHERE chat_id=? ORDER BY name", (chat_id,)
        ).fetchall()
        return [r[0] for r in rows]


# ---------- Violations (spam / bad words) ----------

def bump_violation(chat_id: int, user_id: int, kind: str) -> int:
    """Increment a violation counter and return the new count."""
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO violations (chat_id, user_id, kind, count, last_ts) "
            "VALUES (?, ?, ?, 1, ?) "
            "ON CONFLICT(chat_id, user_id, kind) DO UPDATE SET "
            "count = count + 1, last_ts = excluded.last_ts",
            (chat_id, user_id, kind, int(time.time())),
        )
        row = conn.execute(
            "SELECT count FROM violations WHERE chat_id=? AND user_id=? AND kind=?",
            (chat_id, user_id, kind),
        ).fetchone()
        return row[0] if row else 0


def get_violation_count(chat_id: int, user_id: int, kind: str) -> int:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT count FROM violations WHERE chat_id=? AND user_id=? AND kind=?",
            (chat_id, user_id, kind),
        ).fetchone()
        return row[0] if row else 0


def reset_violations(chat_id: int, user_id: int):
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM violations WHERE chat_id=? AND user_id=?", (chat_id, user_id)
        )


# ---------- Flood / spam detection ----------

def log_message(chat_id: int, user_id: int):
    now = int(time.time())
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO message_log (chat_id, user_id, ts) VALUES (?, ?, ?)",
            (chat_id, user_id, now),
        )
        # keep the table small — drop anything older than 5 minutes
        conn.execute("DELETE FROM message_log WHERE ts < ?", (now - 300,))


def recent_message_count(chat_id: int, user_id: int, window_seconds: int) -> int:
    cutoff = int(time.time()) - window_seconds
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM message_log WHERE chat_id=? AND user_id=? AND ts >= ?",
            (chat_id, user_id, cutoff),
        ).fetchone()
        return row[0] if row else 0
