"""
job_agent/main.py
Schweizer Jobsuche – Digital Assets / Blockchain / Finance + IT-Jobs Region Zürich / Zug
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
from db       import init_db, is_seen, mark_seen, is_pending, add_pending, get_pending, remove_pending
from tg       import send_jobs

logging.basicConfig(
    level  = logging.INFO,
    format = "%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

MAX_JOBS = 15  # Max. Jobs pro Sendung – Rest bleibt in der Warteschlange


async def run():
    logger.info("▶️  Job Agent gestartet")

    # 1. Jobs von allen Quellen holen
    raw_jobs = scrape_all()
    logger.info(f"{len(raw_jobs)} Jobs gescrapt")

    if not raw_jobs:
        logger.warning("Keine Jobs gefunden")

    # 2. Bereits gesehene oder wartende Jobs rausfiltern
    new_jobs = [j for j in raw_jobs if not is_seen(j["id"]) and not is_pending(j["id"])]
    logger.info(f"{len(new_jobs)} neue Jobs (noch nicht gesehen)")

    # 3. Claude bewertet: relevante Jobs in die Warteschlange,
    #    irrelevante als gesehen markieren (nicht bewertete bleiben offen)
    relevant, scored_ids = filter_and_score(new_jobs)
    relevant_ids = {j["id"] for j in relevant}
    for job in relevant:
        add_pending(job)
    for job in new_jobs:
        if job["id"] in scored_ids and job["id"] not in relevant_ids:
            mark_seen(job)

    # 4. Beste Jobs aus der Warteschlange senden (inkl. Rest früherer Läufe)
    pending = get_pending()
    if not pending:
        logger.info("Keine relevanten Jobs – fertig")
        return

    to_send = pending[:MAX_JOBS]
    await send_jobs(to_send)

    # 5. Erst nach erfolgreichem Versand als gesehen markieren
    for job in to_send:
        mark_seen(job)
        remove_pending(job["id"])
    logger.info(f"✅ {len(to_send)} Jobs gesendet, {len(pending) - len(to_send)} warten auf den nächsten Lauf")


if __name__ == "__main__":
    init_db()
    asyncio.run(run())
