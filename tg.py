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


MAX_MESSAGE_LEN = 4000  # Telegram erlaubt max. 4096 Zeichen pro Nachricht


def _pack_messages(header: str, group: list[dict]) -> list[tuple[str, list[dict]]]:
    """Verteilt die Jobs einer Kategorie so auf Nachrichten, dass keine zu lang wird."""
    messages = []
    text, chunk = header + "\n", []
    for job in group:
        block  = _format_job(job)[:MAX_MESSAGE_LEN - len(header) - 2]
        joiner = "\n" + "─" * 20 + "\n" if chunk else "\n"
        if chunk and len(text) + len(joiner) + len(block) > MAX_MESSAGE_LEN:
            messages.append((text, chunk))
            text, chunk, joiner = header + "\n", [], "\n"
        text += joiner + block
        chunk.append(job)
    if chunk:
        messages.append((text, chunk))
    return messages


async def _send_text(bot: Bot, text: str) -> bool:
    """Sendet mit Markdown, bei Fehler als Klartext. Gibt zurück, ob es geklappt hat."""
    try:
        await bot.send_message(
            chat_id                  = TELEGRAM_CHAT_ID,
            text                     = text,
            parse_mode               = ParseMode.MARKDOWN,
            disable_web_page_preview = True,
        )
        return True
    except Exception as e:
        logger.error(f"Telegram Fehler (Markdown): {e}")
    try:
        plain = text.replace("*", "").replace("_", "")
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=plain, disable_web_page_preview=True)
        return True
    except Exception as e:
        logger.error(f"Telegram Fehler (Klartext): {e}")
        return False


async def send_alert(problems: list[str]):
    """Warnt per Telegram über Probleme im Lauf. Wirft nie – der Lauf soll daran nicht scheitern."""
    text = "⚠️ Job Agent – Probleme im Lauf:\n" + "\n".join(f"• {p}" for p in problems)
    try:
        await Bot(token=TELEGRAM_TOKEN).send_message(chat_id=TELEGRAM_CHAT_ID, text=text[:MAX_MESSAGE_LEN])
    except Exception as e:
        logger.error(f"Telegram-Warnung fehlgeschlagen: {e}")


async def send_jobs(jobs: list[dict]) -> list[dict]:
    """
    Sendet Jobs gruppiert nach Kategorie; lange Kategorien werden auf mehrere
    Nachrichten verteilt. Gibt die erfolgreich gesendeten Jobs zurück.
    """
    if not jobs:
        return []

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

    sent = []
    for kat in KATEGORIE_ORDER:
        for text, chunk in _pack_messages(KATEGORIE_HEADER[kat], by_kategorie.get(kat, [])):
            if await _send_text(bot, text):
                sent.extend(chunk)

    logger.info(f"✅ {len(sent)}/{len(jobs)} Jobs gesendet")
    return sent


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
