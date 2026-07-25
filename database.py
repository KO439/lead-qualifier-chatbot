"""
Gestion de la base de donnees SQLite.
Stocke chaque session de conversation avec son historique, ses infos extraites
et son score de qualification.
"""
import sqlite3
import json
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "leads.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            session_id TEXT PRIMARY KEY,
            messages TEXT NOT NULL DEFAULT '[]',
            extracted_info TEXT NOT NULL DEFAULT '{}',
            score INTEGER DEFAULT 0,
            category TEXT DEFAULT 'inconnu',
            justification TEXT DEFAULT '',
            created_at TEXT,
            updated_at TEXT
        )
    """)
    conn.commit()
    conn.close()


def get_or_create_session(session_id: str) -> dict:
    conn = get_connection()
    row = conn.execute("SELECT * FROM leads WHERE session_id = ?", (session_id,)).fetchone()
    if row is None:
        now = datetime.utcnow().isoformat()
        conn.execute(
            "INSERT INTO leads (session_id, created_at, updated_at) VALUES (?, ?, ?)",
            (session_id, now, now),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM leads WHERE session_id = ?", (session_id,)).fetchone()
    conn.close()
    return dict(row)


def update_session(session_id: str, messages: list, extracted_info: dict = None,
                    score: int = None, category: str = None, justification: str = None):
    conn = get_connection()
    fields = ["messages = ?", "updated_at = ?"]
    values = [json.dumps(messages, ensure_ascii=False), datetime.utcnow().isoformat()]

    if extracted_info is not None:
        fields.append("extracted_info = ?")
        values.append(json.dumps(extracted_info, ensure_ascii=False))
    if score is not None:
        fields.append("score = ?")
        values.append(score)
    if category is not None:
        fields.append("category = ?")
        values.append(category)
    if justification is not None:
        fields.append("justification = ?")
        values.append(justification)

    values.append(session_id)
    conn.execute(f"UPDATE leads SET {', '.join(fields)} WHERE session_id = ?", values)
    conn.commit()
    conn.close()


def list_leads(min_score: int = 0) -> list:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM leads WHERE score >= ? ORDER BY score DESC, updated_at DESC",
        (min_score,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
