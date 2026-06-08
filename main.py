"""
job_agent/main.py
Schweizer Jobsuche – Digital Assets / Blockchain / Finance
Läuft Mo/Mi/Fr um 09:00 via Cronjob.

Crontab:
0 9 * * 1,3,5 /usr/bin/python3 /home/user/job_agent/main.py >> /var/log/job_agent.log 2>&1
"""

import asyncio
import logging
from dotenv import load_dotenv
load_dotenv()
from scraper  import scrape_all
from filter   import filter_and_score
from db       import init_db, is_seen, mark_seen
from tg       import send_jobs

logging.basicConfig(
    level  = logging.INFO,
    format = "%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


async def run():
    logger.info("▶️  Job Agent gestartet")

    # 1. Jobs von allen Quellen holen
    raw_jobs = scrape_all()
    logger.info(f"{len(raw_jobs)} Jobs gescrapt")

    if not raw_jobs:
        logger.warning("Keine Jobs gefunden")
        return

    # 2. Bereits gesehene Jobs rausfiltern
    new_jobs = [j for j in raw_jobs if not is_seen(j["id"])]
    logger.info(f"{len(new_jobs)} neue Jobs (noch nicht gesehen)")

    if not new_jobs:
        logger.info("Keine neuen Jobs – fertig")
        return

    # 3. Claude bewertet und filtert
    scored_jobs = filter_and_score(new_jobs)
    logger.info(f"{len(scored_jobs)} Jobs nach Filter (Score ≥ 6)")

    if not scored_jobs:
        logger.info("Keine relevanten Jobs – fertig")
        return

    # 4. Als gesehen markieren (alle neuen, nicht nur gefilterte)
    for job in new_jobs:
        mark_seen(job)

    # 5. Via Telegram senden
    await send_jobs(scored_jobs)
    logger.info("✅ Jobs gesendet")


if __name__ == "__main__":
    init_db()
    asyncio.run(run())
