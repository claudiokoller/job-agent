"""
Tests für den Zustand einer Stelle: unbekannt -> wartend -> gesehen.

Jeder Test läuft gegen eine frische SQLite-Datei in einem temporären Ordner.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db


def make_job(job_id: str, score: int = 7) -> dict:
    return {
        "id": job_id,
        "titel": f"Titel {job_id}",
        "firma": f"Firma {job_id}",
        "ort": "Zug",
        "url": f"https://example.ch/{job_id}",
        "quelle": "Test",
        "score": score,
    }


class DbTestCase(unittest.TestCase):

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._orig_path = db.DB_PATH
        db.DB_PATH = os.path.join(self._tmpdir.name, "test.db")
        db.init_db()

    def tearDown(self):
        db.DB_PATH = self._orig_path
        self._tmpdir.cleanup()


class TestSeenJobs(DbTestCase):

    def test_unbekannte_stelle_gilt_nicht_als_gesehen(self):
        self.assertFalse(db.is_seen("unbekannt"))

    def test_markierte_stelle_gilt_als_gesehen(self):
        db.mark_seen(make_job("a1"))
        self.assertTrue(db.is_seen("a1"))

    def test_doppeltes_markieren_wirft_nicht(self):
        db.mark_seen(make_job("a1"))
        db.mark_seen(make_job("a1"))
        self.assertTrue(db.is_seen("a1"))


class TestPendingJobs(DbTestCase):

    def test_wartende_stelle_wird_gefunden(self):
        db.add_pending(make_job("b1"))
        self.assertTrue(db.is_pending("b1"))

    def test_warteschlange_gibt_beste_stelle_zuerst(self):
        db.add_pending(make_job("niedrig", score=6))
        db.add_pending(make_job("hoch", score=10))
        db.add_pending(make_job("mittel", score=8))

        self.assertEqual(
            [j["id"] for j in db.get_pending()], ["hoch", "mittel", "niedrig"]
        )

    def test_volle_stellendaten_ueberleben_die_warteschlange(self):
        db.add_pending(make_job("b1"))

        job = db.get_pending()[0]

        self.assertEqual(job["url"], "https://example.ch/b1")
        self.assertEqual(job["ort"], "Zug")

    def test_entfernte_stelle_wartet_nicht_mehr(self):
        db.add_pending(make_job("b1"))
        db.remove_pending("b1")

        self.assertFalse(db.is_pending("b1"))
        self.assertEqual(db.get_pending(), [])

    def test_gesendete_stelle_ist_gesehen_und_nicht_mehr_wartend(self):
        """Der Ablauf aus main.py nach erfolgreichem Telegram-Versand."""
        job = make_job("b1")
        db.add_pending(job)

        db.mark_seen(job)
        db.remove_pending(job["id"])

        self.assertTrue(db.is_seen("b1"))
        self.assertFalse(db.is_pending("b1"))


if __name__ == "__main__":
    unittest.main()
