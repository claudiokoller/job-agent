"""
Tests für die Job-Erkennung und Deduplizierung.

scraper.py kommt ohne Umgebungsvariablen aus und lässt sich direkt importieren.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import scraper
from scraper import Job, make_id, _looks_like_job, _extract_city, _deduplicate


class TestMakeId(unittest.TestCase):
    """Dieselbe Stelle muss über Quellen hinweg dieselbe ID bekommen."""

    def test_gender_zusatz_und_pensum_werden_ignoriert(self):
        self.assertEqual(
            make_id("Blockchain Engineer (m/w/d) 80-100%", "SIX Group AG"),
            make_id("Blockchain Engineer", "SIX Group"),
        )

    def test_rechtsform_wird_ignoriert(self):
        self.assertEqual(
            make_id("Data Analyst", "Beispiel GmbH"),
            make_id("Data Analyst", "Beispiel"),
        )

    def test_grossschreibung_und_leerzeichen_egal(self):
        self.assertEqual(
            make_id("  DATA   Analyst ", "Beispiel AG"),
            make_id("data analyst", "beispiel"),
        )

    def test_verschiedene_stellen_bleiben_verschieden(self):
        self.assertNotEqual(
            make_id("Data Analyst", "Beispiel AG"),
            make_id("Data Engineer", "Beispiel AG"),
        )

    def test_gleiche_stelle_andere_firma_bleibt_verschieden(self):
        self.assertNotEqual(
            make_id("Data Analyst", "Firma A"),
            make_id("Data Analyst", "Firma B"),
        )


class TestLooksLikeJob(unittest.TestCase):
    """Generischer HTML-Parser: Stellenlinks ja, Navigation nein."""

    def test_echte_stelle_wird_erkannt(self):
        self.assertTrue(_looks_like_job("Senior Blockchain Engineer", "/jobs/12345"))

    def test_navigationslinks_werden_verworfen(self):
        for text in ("Karriere", "Datenschutz", "Offene Stellen", "Jetzt bewerben"):
            with self.subTest(text=text):
                self.assertFalse(_looks_like_job(text, "/karriere"))

    def test_beschreibungssatz_ist_keine_stelle(self):
        self.assertFalse(
            _looks_like_job("Unser Team sucht laufend neue Talente.", "/jobs/1")
        )

    def test_einzelwort_ohne_rollenbezug_ist_keine_stelle(self):
        self.assertFalse(_looks_like_job("Engineer", "/jobs/1"))

    def test_link_zurueck_auf_die_karriereseite_wird_verworfen(self):
        self.assertFalse(
            _looks_like_job(
                "Product Owner", "https://firma.ch/careers", "https://firma.ch/careers"
            )
        )


class TestExtractCity(unittest.TestCase):

    def test_stadt_aus_job_slug(self):
        self.assertEqual(_extract_city("https://x.ch/job/Zurich-Senior-Analyst"), "Zürich")

    def test_unbekannter_ort_faellt_auf_schweiz_zurueck(self):
        self.assertEqual(_extract_city("https://x.ch/job/Foobar-Analyst"), "Schweiz")


class TestDeduplicate(unittest.TestCase):

    def test_doppelte_ids_fallen_raus_reihenfolge_bleibt(self):
        a = Job(id="1", titel="A", firma="F", ort="Zug", url="u1", quelle="q")
        b = Job(id="2", titel="B", firma="F", ort="Zug", url="u2", quelle="q")
        a2 = Job(id="1", titel="A", firma="F", ort="Zug", url="u3", quelle="q")

        result = _deduplicate([a, b, a2])

        self.assertEqual([j.id for j in result], ["1", "2"])


if __name__ == "__main__":
    unittest.main()
