"""
job_agent/tg.py
Sendet Job-Benachrichtigungen via Telegram.
Eigener Bot / Chat separiert von News und Invoice Agent.
"""

import os
import logging
import asyncio
from datetime import datetime
from telegram import Bot
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)

TELEGRAM_TOKEN   = os.environ["JOBS_TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["JOBS_TELEGRAM_CHAT_ID"]

# Score-Badge
def score_badge(score: int) -> str:
    if score >= 9: return "🟢"
    if score >= 7: return "🟡"
    return "🔵"


KATEGORIE_HEADER = {
    "Krypto & Digital Assets": "🪙 *Krypto & Digital Assets*",
    "Software & Data":         "💻 *Software & Data*",
    "IT Business & Projekte":  "🧩 *IT Business & Projekte*",
    "Finance & Operations":    "📊 *Finance & Operations*",
}
KATEGORIE_ORDER = list(KATEGORIE_HEADER)


def _format_job(job: dict) -> str:
    badge = score_badge(job.get("score", 0))
    remote_icons = {"Remote": "🏠 Remote", "Hybrid": "🔀 Hybrid", "Vor Ort": "🏢 Vor Ort"}
    remote_str = remote_icons.get(job.get("remote", ""), "")

    ort_line = f"📍 {job['ort']}"
    if remote_str:
        ort_line += f"  {remote_str}"

    block = (
        f"{badge} *{job['firma']}*\n"
        f"_{job['titel']}_\n"
        f"{ort_line}"
    )
    zusammenfassung = job.get("zusammenfassung", "").strip()
    if zusammenfassung:
        block += f"\n\n{zusammenfassung}"

    anforderungen = job.get("anforderungen", [])
    if anforderungen:
        block += "\n" + "\n".join(f"• {r}" for r in anforderungen)

    block += f"\n[Stelle ansehen]({job['url']})"
    return block


async def send_jobs(jobs: list[dict]):
    """Sendet Jobs gruppiert nach Kategorie – eine Nachricht pro Kategorie."""
    if not jobs:
        return

    bot  = Bot(token=TELEGRAM_TOKEN)
    date = datetime.now().strftime("%A, %d. %B")

    # Einleitungsnachricht
    await bot.send_message(
        chat_id    = TELEGRAM_CHAT_ID,
        text       = f"💼 *Job Alert – {date}*\n_{len(jobs)} neue Stellen gefunden_",
        parse_mode = ParseMode.MARKDOWN,
    )

    # Gruppieren nach Kategorie
    by_kategorie: dict[str, list] = {}
    for job in jobs:
        kat = job.get("kategorie")
        if kat not in KATEGORIE_HEADER:
            kat = "Finance & Operations"
        by_kategorie.setdefault(kat, []).append(job)

    for kat in KATEGORIE_ORDER:
        group = by_kategorie.get(kat, [])
        if not group:
            continue

        lines = [KATEGORIE_HEADER[kat] + "\n"]
        for i, job in enumerate(group):
            lines.append(_format_job(job))
            if i < len(group) - 1:
                lines.append("─" * 20)

        text = "\n".join(lines)
        try:
            await bot.send_message(
                chat_id                  = TELEGRAM_CHAT_ID,
                text                     = text,
                parse_mode               = ParseMode.MARKDOWN,
                disable_web_page_preview = True,
            )
        except Exception as e:
            logger.error(f"Telegram Fehler ({kat}): {e}")
            plain = text.replace("*", "").replace("_", "")
            await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=plain)

    logger.info(f"✅ {len(jobs)} Jobs gesendet")


# ─── Test ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    test_jobs = [
        {"firma": "Sygnum Bank", "titel": "Digital Asset Analyst", "ort": "Zürich",
         "quelle": "Direkt", "url": "https://sygnum.com/careers", "score": 9,
         "grund": "Direkte Relevanz, regulierte Krypto-Bank"},
        {"firma": "SIX Group", "titel": "Blockchain Engineer", "ort": "Zürich",
         "quelle": "Jobs.ch", "url": "https://jobs.ch/xyz", "score": 7,
         "grund": "SDX Projekt, guter Arbeitgeber"},
    ]

    asyncio.run(send_jobs(test_jobs))
