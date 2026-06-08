"""
job_agent/db.py
SQLite für Job-Deduplizierung.
Verhindert dass gleiche Stellen mehrfach gesendet werden.
"""

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
        # Alte Einträge nach 60 Tagen löschen
        conn.execute("""
            DELETE FROM seen_jobs
            WHERE seen_at < datetime('now', '-60 days')
        """)
        logger.info("✅ Job DB initialisiert")


def is_seen(job_id: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM seen_jobs WHERE id = ?", (job_id,)
        ).fetchone()
        return row is not None


def mark_seen(job: dict):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO seen_jobs (id, titel, firma, seen_at) VALUES (?, ?, ?, ?)",
            (job["id"], job.get("titel", ""), job.get("firma", ""), datetime.now().isoformat())
        )
