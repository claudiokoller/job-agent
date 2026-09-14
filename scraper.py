"""
job_agent/scraper.py
Scrapt Jobs von Schweizer Plattformen und direkten Arbeitgeber-Karriereseiten.
Fokus: Digital Assets, Blockchain, DLT, Fintech – Schweiz;
       allgemeine IT-Stellen – Region Zürich / Zug.
"""

from __future__ import annotations
import re
import hashlib
import logging
import requests
from bs4 import BeautifulSoup
from dataclasses import dataclass, field

try:
    from jobspy import scrape_jobs as jobspy_scrape
    JOBSPY_AVAILABLE = True
except ImportError:
    JOBSPY_AVAILABLE = False

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "de-CH,de;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

TIMEOUT = 10

# Keywords für Suche auf Plattformen
KEYWORDS = [
    "digital assets", "blockchain", "DLT", "crypto", "Bitcoin",
    "tokenization", "custody", "fintech", "decentralized"
]

# Direkte Arbeitgeber-Karriereseiten
# Alle CH-Banken / Finanzinstitute mit Digital Asset / Blockchain Relevanz
# Entfernt (liefern via HTML nichts – Kandidaten für eigene API-Scraper):
#   Bitcoin Suisse, Crypto Finance → bereits via DIRECT_APIS
#   Sygnum, Taurus, Twint → Cloudflare-Block
#   ZKB, Luzerner KB, Zuger KB, Basler KB, Hypothekarbank Lenzburg → SPAs ohne Job-Links
#   AMINA (SSL-Fehler), Metaco (Verbindung abgebrochen), Vontobel (Verbindung verweigert),
#   Pictet, Swissquote (Domain existiert nicht mehr)
DIRECT_EMPLOYERS = [
    # ── Crypto-native Banken & Broker ──────────────────────────────────────
    {"name": "Mt Pelerin",          "url": "https://www.mtpelerin.com/careers"},

    # ── Grossbanken ─────────────────────────────────────────────────────────
    {"name": "UBS",                 "url": "https://www.ubs.com/global/en/careers/search-jobs.html?q=digital+assets"},
    {"name": "Julius Bär",          "url": "https://www.juliusbaer.com/en/careers/job-opportunities/?q=digital+assets"},
    {"name": "Lombard Odier",       "url": "https://www.lombardodier.com/careers.html"},
    {"name": "Maerki Baumann",      "url": "https://www.maerki-baumann.ch/de/ueber-uns/karriere"},

    # ── Infrastruktur & Börsen ───────────────────────────────────────────────
    {"name": "SIX Group",           "url": "https://jobs.six-group.com/search?q=digital+assets+blockchain"},
    {"name": "PostFinance",         "url": "https://www.postfinance.ch/de/ueber-uns/jobs.html"},

    # ── Versicherungen / Asset Manager mit DLT-Fokus ────────────────────────
    {"name": "Zurich Insurance",    "url": "https://www.zurich.com/en/careers/search-jobs?q=blockchain+digital"},
    {"name": "Swiss Life",          "url": "https://jobs.swisslife.ch/search?q=digital+assets"},
]


@dataclass
class Job:
    id:          str        # Hash aus Titel + Firma
    titel:       str
    firma:       str
    ort:         str
    url:         str
    quelle:      str
    beschreibung: str = ""
    pensum:      str = ""   # z.B. "80-100%"
    raw:         dict = field(default_factory=dict)


# Zusätze, die je nach Quelle bei derselben Stelle variieren
_TITEL_NOISE = re.compile(
    r"\(\s*[mwfdx](?:\s*/\s*[mwfdx]){1,3}\s*\)"   # (m/w/d), (w/m/d), (f/m/x)
    r"|\b[mwfd](?:/[mwfd]){2}\b"                   # m/w/d ohne Klammern
    r"|\(\s*(?:a|d|all genders|alle)\s*\)"         # (a), (all genders)
    r"|\d{1,3}\s*(?:[-–]\s*\d{1,3}\s*)?%",         # 80-100%, 100 %
    re.IGNORECASE,
)
_FIRMA_NOISE = re.compile(r"\b(?:ag|gmbh|sa|ltd|inc|llc|schweiz|switzerland)\b", re.IGNORECASE)


def _normalize(text: str, noise: re.Pattern) -> str:
    text = noise.sub(" ", text.lower())
    return " ".join(re.sub(r"[^\w]+", " ", text).split())


def make_id(titel: str, firma: str) -> str:
    """
    Eindeutige ID via Hash – verhindert Duplikate, auch quellenübergreifend
    (z.B. "SIX Group AG" = "SIX Group", "Engineer (m/w/d) 100%" = "Engineer").
    """
    raw = f"{_normalize(titel, _TITEL_NOISE)}|{_normalize(firma, _FIRMA_NOISE)}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


# ─── Scraper: LinkedIn ───────────────────────────────────────────────────────
# LinkedIn rendert Job-Karten server-side für SEO – kein Login nötig.

# Krypto / Digital Assets → ganze Schweiz
JOBSPY_QUERIES = [
    "digital assets blockchain fintech",
    "Bitcoin DLT custody Schweiz",
    "blockchain engineer crypto",
    "fintech payments tokenization",
]

# Allgemeine IT-Stellen → nur Region Zürich / Zug
IT_QUERIES = [
    "Software Engineer",
    "Softwareentwickler",
    "Data Analyst Data Engineer",
    "IT Business Analyst",
    "Product Owner IT",
    "IT Projektleiter",
    "System Engineer Cloud DevOps",
    "IT Security Engineer",
    "Application Manager Applikationsverantwortlicher",
    "IT Consultant",
]
IT_LOCATIONS = ["Zürich, Switzerland", "Zug, Switzerland"]
IT_DISTANCE_MILES = 15  # ~25 km Umkreis

def scrape_jobspy() -> list[Job]:
    """
    Nutzt python-jobspy um LinkedIn und Indeed zu scrapen
    (Google Jobs liefert via JobSpy keine Treffer).
    Krypto-Suchen schweizweit, IT-Suchen im Umkreis von Zürich und Zug.
    """
    if not JOBSPY_AVAILABLE:
        logger.warning("python-jobspy nicht installiert – überspringe")
        return []

    import warnings
    warnings.filterwarnings("ignore")

    searches = [(q, "Switzerland", None) for q in JOBSPY_QUERIES]
    searches += [(q, loc, IT_DISTANCE_MILES) for loc in IT_LOCATIONS for q in IT_QUERIES]

    jobs = []
    seen: set[str] = set()

    for query, location, distance in searches:
        city = location.split(",")[0]
        try:
            df = jobspy_scrape(
                site_name                = ["linkedin", "indeed"],
                search_term              = query,
                location                 = location,
                distance                 = distance,
                results_wanted           = 15,
                hours_old                = 168,   # letzte 7 Tage
                country_indeed           = "Switzerland",
                linkedin_fetch_description = False,
                verbose                  = 0,
            )
            for _, row in df.iterrows():
                titel   = str(row.get("title",   "") or "").strip()
                firma   = str(row.get("company", "") or "").strip()
                ort_raw = str(row.get("location","") or "").strip()
                url     = str(row.get("job_url", "") or "").strip()
                site    = str(row.get("site",    "") or "").strip()

                if not titel or not url or url in seen:
                    continue
                seen.add(url)

                # Ort vereinfachen: "Zürich, ZH, CH" → "Zürich"
                ort = ort_raw.split(",")[0].strip() if ort_raw else "Schweiz"

                jobs.append(Job(
                    id     = make_id(titel, firma),
                    titel  = titel,
                    firma  = firma,
                    ort    = ort,
                    url    = url,
                    quelle = site.capitalize(),
                ))
        except Exception as e:
            logger.warning(f"JobSpy Fehler ({query[:30]} / {city}): {e}")

    return _deduplicate(jobs)


# ─── Scraper: Direkte Arbeitgeber ────────────────────────────────────────────

def scrape_direct_employers() -> list[Job]:
    """
    Scrapt Karriereseiten von seriösen CH-Arbeitgebern direkt.
    Generischer Parser der Job-Links und Titel extrahiert.
    """
    jobs = []

    for employer in DIRECT_EMPLOYERS:
        try:
            resp = requests.get(employer["url"], headers=HEADERS, timeout=TIMEOUT)
            soup = BeautifulSoup(resp.text, "html.parser")

            # Generisch: alle Links die nach Job-Posting aussehen
            for a in soup.find_all("a", href=True):
                text = a.get_text(strip=True)
                href = a["href"]

                if len(text) < 5 or len(text) > 120:
                    continue

                # Nur Links die nach Jobs aussehen
                if not _looks_like_job(text, href, employer["url"]):
                    continue

                # Vollständige URL
                if href.startswith("/"):
                    base = "/".join(employer["url"].split("/")[:3])
                    href = base + href
                elif not href.startswith("http"):
                    continue

                jobs.append(Job(
                    id     = make_id(text, employer["name"]),
                    titel  = text,
                    firma  = employer["name"],
                    ort    = _extract_city(href),
                    url    = href,
                    quelle = "Direkt",
                ))

            logger.info(f"  {employer['name']}: {len([j for j in jobs if j.firma == employer['name']])} Jobs")

        except Exception as e:
            logger.warning(f"Direkt-Scraping Fehler {employer['name']}: {e}")

    return _deduplicate(jobs)


# ─── Scraper: Direkte APIs (Bitcoin Suisse, Crypto Finance) ──────────────────

# Firmen mit bekannten internen/externen Job-APIs
DIRECT_APIS = [
    {
        "name":   "Bitcoin Suisse",
        "url":    "https://bitcoinsuisse.com/api/careers",
        "type":   "bitcoinsuisse",
    },
    {
        "name":   "Crypto Finance AG",
        "url":    "https://apply.workable.com/api/v1/widget/accounts/488913?origin=embed",
        "type":   "workable_widget",
    },
]


def scrape_direct_apis() -> list[Job]:
    """Scrapt Firmen die eine öffentliche JSON-API für Stellenangebote haben."""
    jobs = []

    for src in DIRECT_APIS:
        try:
            resp = requests.get(src["url"], headers=HEADERS, timeout=TIMEOUT)

            if src["type"] == "bitcoinsuisse":
                for item in resp.json():
                    titel = item.get("title", "").strip()
                    url   = item.get("url", "")
                    if not titel: continue
                    jobs.append(Job(
                        id     = make_id(titel, src["name"]),
                        titel  = titel,
                        firma  = src["name"],
                        ort    = "Zug",
                        url    = url,
                        quelle = "Direkt",
                    ))

            elif src["type"] == "workable_widget":
                import re as _re
                text = _re.sub(r"^whrcallback\(", "", resp.text.strip()).rstrip(")")
                import json as _json
                for item in _json.loads(text).get("jobs", []):
                    titel = item.get("title", "").strip()
                    url   = item.get("url", "")
                    city  = (item.get("location") or {}).get("city") or "Zürich"
                    if not titel: continue
                    jobs.append(Job(
                        id     = make_id(titel, src["name"]),
                        titel  = titel,
                        firma  = src["name"],
                        ort    = city,
                        url    = url,
                        quelle = "Direkt",
                    ))

            logger.info(f"  {src['name']} (API): {len([j for j in jobs if j.firma == src['name']])} Jobs")

        except Exception as e:
            logger.warning(f"API-Scraping Fehler {src['name']}: {e}")

    return jobs


# ─── Hauptfunktion ───────────────────────────────────────────────────────────

def scrape_all() -> list[dict]:
    """Scrapt alle Quellen und gibt eine Liste von Job-Dicts zurück."""
    all_jobs: list[Job] = []

    logger.info("Scraping LinkedIn / Indeed (JobSpy)...")
    all_jobs.extend(scrape_jobspy())

    logger.info("Scraping direkte APIs (Bitcoin Suisse, Crypto Finance)...")
    all_jobs.extend(scrape_direct_apis())

    logger.info("Scraping direkte Arbeitgeber (HTML)...")
    all_jobs.extend(scrape_direct_employers())

    # Globale Deduplizierung
    all_jobs = _deduplicate(all_jobs)
    logger.info(f"Total: {len(all_jobs)} Jobs nach Deduplizierung")

    return [_to_dict(j) for j in all_jobs]


# ─── Hilfsfunktionen ─────────────────────────────────────────────────────────

def _looks_like_job(text: str, href: str, career_url: str = "") -> bool:
    """Prüft ob ein Link eine echte Stellenausschreibung mit direktem Link ist."""

    BLOCKLIST_TEXT = [
        "karriere", "career", "jobs", "stellenangebote", "offene stellen",
        "join us", "join our team", "work with us", "arbeite mit uns",
        "team", "über uns", "about us", "unser team", "our team",
        "privacy", "datenschutz", "impressum", "kontakt", "contact",
        "login", "newsletter", "abonnieren", "mehr erfahren", "learn more",
        "keine offenen", "no open", "currently no", "derzeit keine",
        "bewerben", "apply here", "initiativbewerbung",
        "instagram", "linkedin", "twitter", "facebook", "youtube",
        "docs", "documentation", "developer docs",
        "advisory board", "board of", "board of directors",
        "studierende", "students and", "students &",
    ]

    ROLE_KEYWORDS = [
        "manager", "analyst", "engineer", "developer", "officer",
        "specialist", "consultant", "head of", "director", "lead",
        "associate", "trader", "advisor", "architect", "leiter",
        "berater", "entwickler", "spezialist", "sachbearbeiter",
        "coordinator", "coordinateur", "controller", "strategist",
        "quantitative", "researcher", "scientist", "product owner",
        "project manager", "risk", "compliance",
        "relationship manager", "intern", "trainee", "graduate",
        "stagaire", "praktikant",
    ]

    text_lower = text.lower().strip()
    href_lower = href.lower()

    # Satzzeichen/Symbole am Ende → Beschreibung, kein Titel
    if text.rstrip().endswith((".", "→", "»", "›", ":")):
        return False

    # Kein Artikel/Pronomen am Anfang → Beschreibung
    if re.match(r"^(our|the|your|ihr|ihre|unser|diese|this|a |an )", text_lower):
        return False

    if any(text_lower == b or text_lower.startswith(b) for b in BLOCKLIST_TEXT):
        return False

    # href muss sich vom career_url unterscheiden (kein Link zurück auf die Karriereseite)
    if career_url:
        norm_career = career_url.rstrip("/").lower().split("?")[0]
        norm_href   = href_lower.rstrip("/").split("?")[0]
        if norm_href == norm_career or norm_href == norm_career.rsplit("/", 1)[0]:
            return False

    # Reine Anker (#) oder JavaScript → raus
    if href_lower.startswith(("#", "mailto:", "javascript:")):
        return False

    # Sektionsseiten auf Karriere-Subdomains (keine spezifischen Jobs)
    SECTION_HREF_PATTERNS = [
        "/students", "/graduates", "/students-graduates",
        "/apprentice", "/internship-program", "/early-career",
        "/organisation/", "/management/", "/leadership/",
    ]
    if any(p in href_lower for p in SECTION_HREF_PATTERNS):
        # Ausnahme: URL hat eine Job-ID (numerisch oder langer Slug nach dem Pattern)
        if not re.search(r"/\d{6,}", href_lower):
            return False

    # Muss mindestens ein Rollenwort enthalten
    if not any(kw in text_lower for kw in ROLE_KEYWORDS):
        return False

    # Mind. 2 Wörter – keine Einzel-Schlagwörter
    if len(text.split()) < 2:
        return False

    return True


def _extract_city(href: str) -> str:
    """Extrahiert Stadt aus Job-URL-Slug (z.B. /job/Zurich-Senior-... → Zürich)."""
    CITY_MAP = {
        "zurich": "Zürich", "zuerich": "Zürich", "zürich": "Zürich",
        "zug": "Zug", "bern": "Bern", "basel": "Basel",
        "geneva": "Genf", "geneve": "Genf", "genf": "Genf",
        "lausanne": "Lausanne", "lugano": "Lugano",
        "winterthur": "Winterthur", "olten": "Olten", "aarau": "Aarau",
        "luzern": "Luzern", "lucerne": "Luzern",
        "london": "London 🇬🇧", "madrid": "Madrid 🇪🇸",
        "warsaw": "Warschau 🇵🇱", "singapore": "Singapur 🇸🇬",
        "remote": "Remote",
    }
    slug = href.lower().split("/job/")[-1] if "/job/" in href.lower() else href.lower()
    first_segment = slug.split("-")[0].split("/")[0]
    return CITY_MAP.get(first_segment, "Schweiz")


def _deduplicate(jobs: list[Job]) -> list[Job]:
    seen = set()
    result = []
    for j in jobs:
        if j.id not in seen:
            seen.add(j.id)
            result.append(j)
    return result


def _to_dict(job: Job) -> dict:
    return {
        "id":           job.id,
        "titel":        job.titel,
        "firma":        job.firma,
        "ort":          job.ort,
        "url":          job.url,
        "quelle":       job.quelle,
        "beschreibung": job.beschreibung,
    }


# ─── Test ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    jobs = scrape_all()
    print(f"\n💼 {len(jobs)} Jobs gefunden:\n")
    for j in jobs[:10]:
        print(f"  [{j['quelle']}] {j['firma']}: {j['titel'][:60]}")
        print(f"   → {j['url'][:80]}\n")
