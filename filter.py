"""
job_agent/filter.py
Claude bewertet Jobs auf Relevanz und Seriosität.
Filtert Scams, irrelevante Stellen und unpassende Positionen raus.

Das Kandidaten-Profil wird aus einer separaten Datei geladen
(PROFILE_PATH, Default: profile.txt) und ist NICHT Teil des Repos.
Als Vorlage dient profile.example.txt.
"""

from __future__ import annotations
import os
import json
import logging
from anthropic import Anthropic

logger = logging.getLogger(__name__)

client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

MIN_SCORE = 6  # Nur Jobs mit Score ≥ 6 werden gesendet
MAX_JOBS  = 15 # Max. Jobs pro Sendung


def _load_profile() -> str:
    """Lädt das persönliche Kandidaten-Profil aus einer (gitignored) Datei."""
    for path in (os.getenv("PROFILE_PATH", "profile.txt"), "profile.example.txt"):
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                return f.read().strip()
    raise FileNotFoundError(
        "Kein Profil gefunden. Kopiere profile.example.txt nach profile.txt "
        "und passe es an."
    )


CANDIDATE_PROFILE = _load_profile()

SYSTEM_PROMPT = f"""
Du bist ein Karriereberater. Bewerte Stellenangebote für diesen Kandidaten:

{CANDIDATE_PROFILE}

GESUCHT werden zwei Arten von Stellen:
A) Krypto / Digital Assets / Fintech → ganze Schweiz
B) Allgemeine IT-Stellen (Software, Data, Cloud, Security, IT-Business-Analyse, Product Owner, IT-Projekte, Application Management, IT-Consulting) → NUR Region Zürich / Zug
   (Stadt & Kanton Zürich, Kanton Zug, angrenzende Pendelorte wie Baar, Cham, Rotkreuz, Pfäffikon SZ, Baden)
   - IT-Stelle ausserhalb dieser Region und nicht Remote → nicht anzeigen

SCORING nach Passung:
1. Relevanz zum Profil: Krypto/Digital-Assets-Stelle ODER IT-Stelle in Zürich/Zug → wichtigster Faktor
   - IT-Stelle mit Bezug zu Bitcoin, Blockchain, Fintech, Banking, Payments → +1 Punkt
   - Rein technische Stelle, die tiefe Spezialisierung voraussetzt (z.B. Embedded, Hardware, Research, ML-Forschung) → max. Score 5
   - Keine IT- oder Krypto-Stelle (z.B. Verkauf, Pflege, Gastro) → nicht anzeigen
2. Sprache: bevorzugte Sprache der Stelle → +1 Punkt; unpassende Sprache → -1 Punkt
3. Seriosität: bekannte, regulierte Unternehmen bevorzugt; Personalvermittler ohne Firmennamen → -1 Punkt
4. Niveau – realistisch zum Profil:
   - Einstiegs-/Fachstellen passend zum Profil → ideal
   - Senior-Fachstellen → erreichbar, Score 7-8
   - Head of, Director, VP, MD → meist unrealistisch; max. Score 4
   - Praktikum → nur Score 5-6, nicht priorisiert
   - Vom Profil ausgeschlossene Bereiche → nicht anzeigen (anzeigen: false)
   - Reine Kaltakquise, kein Fachbezug → nicht anzeigen

Score 1-10:
- 8-10: hochrelevante Fachstelle, passende Sprache, seriöse Firma
- 6-7: relevant, evtl. unpassende Sprache oder etwas zu viel Erfahrung verlangt
- 4-5: Stretch-Rolle oder schwacher Bezug
- 1-3: nicht relevant → nicht anzeigen

Kategorie (wähle eine):
- "Krypto & Digital Assets": direkt Bitcoin/Blockchain/DLT/Custody/Tokenization
- "Software & Data": Softwareentwicklung, Data, Cloud, DevOps, IT-Infrastruktur, IT-Security
- "IT Business & Projekte": Business Analyst, Product Owner, IT-Projektleitung, Application Management, IT-Consulting
- "Finance & Operations": Analyse, Risk, Payments, Asset Management

Felder pro Job:
- zusammenfassung: 1-2 Sätze auf Deutsch was die Stelle beinhaltet
- anforderungen: 2-3 typische Anforderungen als kurze Strings auf Deutsch
- remote: "Remote" | "Hybrid" | "Vor Ort"
- kategorie: eine der vier Kategorien oben

Antworte NUR in JSON:
[{{"id": "...", "score": 8, "anzeigen": true, "grund": "1 Satz", "zusammenfassung": "...", "anforderungen": ["...", "..."], "remote": "Hybrid", "kategorie": "Krypto & Digital Assets"}}]
"""


def filter_and_score(jobs: list[dict]) -> list[dict]:
    """
    Lässt Claude alle Jobs bewerten.
    Gibt nur Jobs mit Score ≥ MIN_SCORE zurück, sortiert nach Score.
    """
    if not jobs:
        return []

    # In Batches von 10 (Prompt-Länge begrenzen)
    results = []
    for batch in _chunks(jobs, 10):
        scored = _score_batch(batch)
        results.extend(scored)

    # Filtern und sortieren
    filtered = [j for j in results if j.get("anzeigen") and j.get("score", 0) >= MIN_SCORE]
    filtered.sort(key=lambda x: x["score"], reverse=True)

    logger.info(f"{len(filtered)}/{len(jobs)} Jobs nach Claude-Filter (Score ≥ {MIN_SCORE})")
    return filtered[:MAX_JOBS]


def _score_batch(jobs: list[dict]) -> list[dict]:
    """Bewertet einen Batch von Jobs via Claude API."""

    jobs_text = json.dumps([{
        "id":     j["id"],
        "titel":  j["titel"],
        "firma":  j["firma"],
        "ort":    j["ort"],
        "quelle": j["quelle"],
    } for j in jobs], ensure_ascii=False, indent=2)

    try:
        response = client.messages.create(
            model      = "claude-sonnet-4-6",
            max_tokens = 4000,
            system     = SYSTEM_PROMPT,
            messages   = [{"role": "user", "content": f"Bewerte diese Jobs:\n{jobs_text}"}],
        )

        raw = response.content[0].text.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        scores = json.loads(raw)

        # Scores mit Original-Job-Daten zusammenführen
        job_by_id = {j["id"]: j for j in jobs}
        result = []
        for s in scores:
            job = job_by_id.get(s["id"], {})
            result.append({
                **job,
                "score":          s["score"],
                "grund":          s.get("grund", ""),
                "zusammenfassung": s.get("zusammenfassung", ""),
                "anforderungen":  s.get("anforderungen", []),
                "remote":         s.get("remote", ""),
                "kategorie":      s.get("kategorie", ""),
                "anzeigen":       s.get("anzeigen", False),
            })

        return result

    except json.JSONDecodeError as e:
        logger.error(f"JSON-Parsing Fehler: {e}")
        return []
    except Exception as e:
        logger.error(f"Claude API Fehler: {e}")
        return []


def _chunks(lst: list, n: int):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


# ─── Test ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    test_jobs = [
        {"id": "abc1", "titel": "Digital Asset Analyst", "firma": "Sygnum Bank", "ort": "Zürich", "quelle": "Direkt", "url": "https://example.com", "beschreibung": ""},
        {"id": "abc2", "titel": "Blockchain Engineer", "firma": "SIX Group", "ort": "Zürich", "quelle": "Jobs.ch", "url": "https://example.com", "beschreibung": ""},
        {"id": "abc3", "titel": "Verkäufer 80%", "firma": "Beispiel AG", "ort": "Bern", "quelle": "Indeed.ch", "url": "https://example.com", "beschreibung": ""},
        {"id": "abc4", "titel": "IT Business Analyst (m/w/d)", "firma": "Beispiel Bank AG", "ort": "Zug", "quelle": "Linkedin", "url": "https://example.com", "beschreibung": ""},
        {"id": "abc5", "titel": "Fullstack Software Engineer Java", "firma": "Beispiel Software AG", "ort": "Zürich", "quelle": "Linkedin", "url": "https://example.com", "beschreibung": ""},
        {"id": "abc6", "titel": "Data Analyst 100%", "firma": "Beispiel Telecom AG", "ort": "Bern", "quelle": "Indeed", "url": "https://example.com", "beschreibung": ""},
    ]

    results = filter_and_score(test_jobs)
    print(f"\n✅ {len(results)} relevante Jobs:\n")
    for j in results:
        print(f"  [{j['score']}/10] {j['firma']}: {j['titel']}")
        print(f"   → {j['grund']}\n")
