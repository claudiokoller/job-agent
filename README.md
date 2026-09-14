# Job Alert Agent

Ein kleiner Agent, der automatisch Stellenangebote sucht, sie von Claude nach
deinem persönlichen Profil bewerten lässt und die besten Treffer per Telegram
schickt. Voreingestellt auf **Digital Assets / Blockchain / Fintech in der
Schweiz** sowie **allgemeine IT-Stellen in der Region Zürich / Zug** – lässt
sich aber einfach anpassen.

## Wie es funktioniert

1. **Scraping** – Jobs von LinkedIn, Indeed, Google (via [JobSpy](https://github.com/Bunsly/JobSpy)) sowie direkt von Arbeitgeber-Karriereseiten.
2. **Filtern** – Claude bewertet jeden Job (Score 1–10) anhand deines Profils und sortiert Scams & irrelevante Stellen aus.
3. **Benachrichtigen** – die besten Treffer kommen gruppiert per Telegram.
4. **Dedup & Warteschlange** – bereits gesehene Jobs (SQLite) werden nicht erneut gesendet. Passende Jobs über dem Limit pro Nachricht warten auf den nächsten Lauf (max. 14 Tage).

## Setup

```bash
pip install -r requirements.txt

# Konfigurieren
cp .env.example .env            # API-Keys & Telegram eintragen
cp profile.example.txt profile.txt   # eigenes Profil eintragen

python main.py
```

Du brauchst einen [Anthropic API-Key](https://console.anthropic.com) und einen
Telegram-Bot (via [@BotFather](https://t.me/BotFather)).

## Anpassen

| Was | Wo |
|-----|-----|
| Dein Profil & Bewertungskriterien | `profile.txt` |
| Suchbegriffe & Arbeitgeber | `JOBSPY_QUERIES` / `DIRECT_EMPLOYERS` in `scraper.py` |
| IT-Suchbegriffe, Orte & Umkreis | `IT_QUERIES` / `IT_LOCATIONS` / `IT_DISTANCE_MILES` in `scraper.py` |
| Mindest-Score | `MIN_SCORE` in `filter.py` |
| Max. Jobs pro Sendung | `MAX_JOBS` in `main.py` |

## Automatisieren

Per Cron (Linux) z.B. Mo/Mi/Fr um 09:00:

```
0 9 * * 1,3,5 /usr/bin/python3 /pfad/zu/job_agent/main.py >> job_agent.log 2>&1
```

Unter Windows mit dem Task-Scheduler (`schtasks`).

## Lizenz

MIT
