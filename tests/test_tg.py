"""
Tests für das Aufteilen langer Telegram-Nachrichten.

tg.py liest seine Zugangsdaten beim Import aus der Umgebung; für die Tests
genügen Platzhalter, es wird nichts gesendet.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("JOBS_TELEGRAM_TOKEN", "test-token")
os.environ.setdefault("JOBS_TELEGRAM_CHAT_ID", "test-chat")

import tg


def make_job(i: int) -> dict:
    return {
        "firma": f"Firma {i}",
        "titel": f"Senior Blockchain Engineer {i}",
        "ort": "Zürich",
        "url": f"https://example.ch/job/{i}",
        "score": 8,
        "remote": "Hybrid",
        "zusammenfassung": "Betreuung von Krypto-Anlageprodukten. " * 5,
        "anforderungen": ["Erfahrung im Digital-Asset-Umfeld", "Deutsch und Englisch"],
    }


class TestPackMessages(unittest.TestCase):

    HEADER = "🪙 *Krypto & Digital Assets*"

    def test_wenige_stellen_passen_in_eine_nachricht(self):
        messages = tg._pack_messages(self.HEADER, [make_job(1), make_job(2)])

        self.assertEqual(len(messages), 1)
        self.assertEqual(len(messages[0][1]), 2)

    def test_viele_stellen_werden_aufgeteilt(self):
        jobs = [make_job(i) for i in range(20)]

        messages = tg._pack_messages(self.HEADER, jobs)

        self.assertGreater(len(messages), 1)

    def test_keine_nachricht_ueberschreitet_das_telegram_limit(self):
        jobs = [make_job(i) for i in range(20)]

        for text, _ in tg._pack_messages(self.HEADER, jobs):
            self.assertLessEqual(len(text), tg.MAX_MESSAGE_LEN)

    def test_beim_aufteilen_geht_keine_stelle_verloren(self):
        jobs = [make_job(i) for i in range(20)]

        verteilt = [job for _, chunk in tg._pack_messages(self.HEADER, jobs) for job in chunk]

        self.assertEqual(len(verteilt), len(jobs))
        self.assertEqual([j["titel"] for j in verteilt], [j["titel"] for j in jobs])

    def test_jede_nachricht_traegt_die_kategorie_ueberschrift(self):
        jobs = [make_job(i) for i in range(20)]

        for text, _ in tg._pack_messages(self.HEADER, jobs):
            self.assertTrue(text.startswith(self.HEADER))

    def test_leere_kategorie_ergibt_keine_nachricht(self):
        self.assertEqual(tg._pack_messages(self.HEADER, []), [])


class TestScoreBadge(unittest.TestCase):

    def test_badge_nach_score(self):
        self.assertEqual(tg.score_badge(10), "🟢")
        self.assertEqual(tg.score_badge(7), "🟡")
        self.assertEqual(tg.score_badge(6), "🔵")


if __name__ == "__main__":
    unittest.main()
