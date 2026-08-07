"""
Gestion de la base de donnees PostgreSQL (persistante, via Supabase).
Stocke chaque session de conversation avec son historique, ses infos
extraites, son score de qualification, et maintenant le resume + l'action
recommandee generes par l'agent d'analyse commerciale.
"""
import psycopg2
from psycopg2.extras import RealDictCursor
import os
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


def get_connection():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


def init_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            session_id TEXT PRIMARY KEY,
            messages TEXT NOT NULL DEFAULT '[]',
            extracted_info TEXT NOT NULL DEFAULT '{}',
            score INTEGER DEFAULT 0,
            category TEXT DEFAULT 'inconnu',
            justification TEXT DEFAULT '',
            alerted BOOLEAN DEFAULT FALSE,
            resume TEXT DEFAULT '',
            action_recommandee TEXT DEFAULT '',
            priorite TEXT DEFAULT '',
            created_at TEXT,
            updated_at TEXT
        )
    """)
    # Ajoute les colonnes si la table existait deja sans (mise a jour progressive)
    cur.execute("ALTER TABLE leads ADD COLUMN IF NOT EXISTS alerted BOOLEAN DEFAULT FALSE")
    cur.execute("ALTER TABLE leads ADD COLUMN IF NOT EXISTS resume TEXT DEFAULT ''")
    cur.execute("ALTER TABLE leads ADD COLUMN IF NOT EXISTS action_recommandee TEXT DEFAULT ''")
    cur.execute("ALTER TABLE leads ADD COLUMN IF NOT EXISTS priorite TEXT DEFAULT ''")
    conn.commit()
    cur.close()
    conn.close()


def get_or_create_session(session_id: str) -> dict:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM leads WHERE session_id = %s", (session_id,))
    row = cur.fetchone()
    if row is None:
        now = datetime.utcnow().isoformat()
        cur.execute(
            "INSERT INTO leads (session_id, created_at, updated_at) VALUES (%s, %s, %s)",
            (session_id, now, now),
        )
        conn.commit()
        cur.execute("SELECT * FROM leads WHERE session_id = %s", (session_id,))
        row = cur.fetchone()
    cur.close()
    conn.close()
    return dict(row)


def update_session(session_id: str, messages: list, extracted_info: dict = None,
                    score: int = None, category: str = None, justification: str = None,
                    alerted: bool = None, resume: str = None,
                    action_recommandee: str = None, priorite: str = None):
    conn = get_connection()
    cur = conn.cursor()
    fields = ["messages = %s", "updated_at = %s"]
    values = [json.dumps(messages, ensure_ascii=False), datetime.utcnow().isoformat()]

    if extracted_info is not None:
        fields.append("extracted_info = %s")
        values.append(json.dumps(extracted_info, ensure_ascii=False))
    if score is not None:
        fields.append("score = %s")
        values.append(score)
    if category is not None:
        fields.append("category = %s")
        values.append(category)
    if justification is not None:
        fields.append("justification = %s")
        values.append(justification)
    if alerted is not None:
        fields.append("alerted = %s")
        values.append(alerted)
    if resume is not None:
        fields.append("resume = %s")
        values.append(resume)
    if action_recommandee is not None:
        fields.append("action_recommandee = %s")
        values.append(action_recommandee)
    if priorite is not None:
        fields.append("priorite = %s")
        values.append(priorite)

    values.append(session_id)
    cur.execute(f"UPDATE leads SET {', '.join(fields)} WHERE session_id = %s", values)
    conn.commit()
    cur.close()
    conn.close()


def list_leads(min_score: int = 0) -> list:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM leads WHERE score >= %s ORDER BY score DESC, updated_at DESC",
        (min_score,),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(r) for r in rows]
