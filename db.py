"""
job_agent/db.py
SQLite für Job-Deduplizierung.
Verhindert dass gleiche Stellen mehrfach gesendet werden.
"""

import json
import sqlite3
import logging
from datetime import datetime
from contextlib import contextmanager

logger = logging.getLogger(__name__)
DB_PATH = "job_agent.db"


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS seen_jobs (
                id         TEXT PRIMARY KEY,
                titel      TEXT,
                firma      TEXT,
                seen_at    TEXT
            )
        """)
        # Relevante, aber noch nicht gesendete Jobs (Warteschlange)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pending_jobs (
                id         TEXT PRIMARY KEY,
                data       TEXT,
                score      INTEGER,
                added_at   TEXT
            )
        """)
        # Alte Einträge nach 60 Tagen löschen
        conn.execute("""
            DELETE FROM seen_jobs
            WHERE seen_at < datetime('now', '-60 days')
        """)
        # Wartende Jobs nach 14 Tagen verwerfen (Inserat vermutlich weg)
        conn.execute("""
            DELETE FROM pending_jobs
            WHERE added_at < datetime('now', '-14 days')
        """)
        logger.info("✅ Job DB initialisiert")


def is_seen(job_id: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM seen_jobs WHERE id = ?", (job_id,)
        ).fetchone()
        return row is not None


def is_pending(job_id: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM pending_jobs WHERE id = ?", (job_id,)
        ).fetchone()
        return row is not None


def add_pending(job: dict):
    """Legt einen bewerteten, relevanten Job in die Warteschlange."""
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO pending_jobs (id, data, score, added_at) VALUES (?, ?, ?, ?)",
            (job["id"], json.dumps(job, ensure_ascii=False), job.get("score", 0), datetime.now().isoformat())
        )


def get_pending() -> list[dict]:
    """Alle wartenden Jobs, beste zuerst (bei Gleichstand ältere zuerst)."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT data FROM pending_jobs ORDER BY score DESC, added_at ASC"
        ).fetchall()
        return [json.loads(r[0]) for r in rows]


def remove_pending(job_id: str):
    with get_conn() as conn:
        conn.execute("DELETE FROM pending_jobs WHERE id = ?", (job_id,))


def mark_seen(job: dict):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO seen_jobs (id, titel, firma, seen_at) VALUES (?, ?, ?, ?)",
            (job["id"], job.get("titel", ""), job.get("firma", ""), datetime.now().isoformat())
        )
