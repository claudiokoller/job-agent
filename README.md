# Job Alert Agent

Sucht automatisch Stellen auf dem Schweizer Arbeitsmarkt, lässt sie von Claude
gegen ein Suchprofil bewerten und schickt die passenden per Telegram.
Läuft Mo/Mi/Fr per Cronjob.

[![Tests](https://github.com/claudiokoller/job-alert-agent/actions/workflows/tests.yml/badge.svg)](https://github.com/claudiokoller/job-alert-agent/actions/workflows/tests.yml)
![Python](https://img.shields.io/badge/Python-3.11-blue)
![License](https://img.shields.io/badge/License-MIT-green)

## Was der Agent macht

1. **Sammeln** – LinkedIn und Indeed über [JobSpy](https://github.com/speedyapply/JobSpy), dazu Karriere-APIs und Karriereseiten von Schweizer Arbeitgebern.
2. **Entdoppeln** – dieselbe Stelle taucht auf mehreren Portalen auf und wird über eine normalisierte ID zusammengeführt.
3. **Bewerten** – Claude vergibt Score 1–10, Kategorie und Kurzzusammenfassung; Irrelevantes fällt raus.
4. **Senden** – die besten Treffer gehen gruppiert per Telegram raus, der Rest wartet auf den nächsten Lauf.

```
💼 Job Alert – Montag, 22. September
   12 neue Stellen gefunden

🪙 Krypto & Digital Assets
🟢 Bitcoin Suisse
   Digital Asset Analyst
   📍 Zug  🔀 Hybrid

   Analyse von Krypto-Anlageprodukten für institutionelle Kunden.
   • Erfahrung im Digital-Asset-Umfeld
   • Deutsch und Englisch
   [Stelle ansehen]
```

## Architektur

```mermaid
flowchart LR
    A["Jobportale<br/>Karriereseiten"] --> B["scraper.py<br/>sammeln + entdoppeln"]
    B --> C["db.py<br/>schon gesehen?"]
    C --> D["filter.py<br/>Claude bewertet"]
    D --> E["tg.py<br/>Telegram"]
```

Mehr Details: [docs/architecture.md](docs/architecture.md)

## Setup

```bash
pip install -r requirements.txt

cp .env.example .env                  # API-Keys eintragen
cp profile.example.txt profile.txt    # eigenes Suchprofil eintragen

python main.py
```

Braucht Python 3.11+, einen [Anthropic API-Key](https://console.anthropic.com)
und einen Telegram-Bot (via [@BotFather](https://t.me/BotFather)).

Wonach gesucht wird, steht nicht im Code, sondern in `profile.txt` – Werdegang,
gesuchte Bereiche, passende Rollenstufen. Die Datei geht direkt in den
Bewertungs-Prompt ein und bleibt lokal.

Automatisch laufen lassen, z.B. Mo/Mi/Fr um 09:00:

```
0 9 * * 1,3,5 /usr/bin/python3 /pfad/zu/job_agent/main.py >> job_agent.log 2>&1
```

## Tests

```bash
python -m unittest discover -s tests
```

28 Tests, ohne zusätzliche Abhängigkeiten und ohne Netzzugriff.

## Designentscheide

- **Nichts geht still verloren.** Eine Stelle gilt erst als gesehen, wenn sie per Telegram angekommen ist. Schlägt Bewertung oder Versand fehl, wird sie beim nächsten Lauf erneut versucht.
- **Warteschlange statt Abschneiden.** Pro Lauf gehen maximal 15 Stellen raus, der Rest wartet nach Score sortiert.
- **Selbstüberwachung.** Leere Scrapes, API- und Telegram-Fehler meldet der Agent per Telegram – sonst merkt man einen stillen Ausfall erst nach Wochen.

Bekannte Grenzen: HTML-Karriereseiten brechen bei Layout-Änderungen, und bewertet
werden nur Titel, Firma und Ort statt des vollen Inserats – günstig, dafür
gelegentlich eine Fehleinschätzung.

## Lizenz

MIT – siehe [LICENSE](LICENSE).
