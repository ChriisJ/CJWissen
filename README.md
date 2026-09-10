# Wissenswerkstatt

Persönlicher deutschsprachiger Lerncoach für belastbares Allgemeinwissen.
Läuft komplett self-hosted als Docker-Container, mit Auto-Update über
GitHub Actions → GHCR → Watchtower in Portainer.

## Was die App tut

- **Aktives Erinnern statt passiver Antworten** — die LLM bewertet jede deiner
  Antworten (`korrekt` / `teilweise` / `unklar` / `falsch` / `nicht beantwortet`).
- **Wiederholungen zuerst** — zu Beginn jeder Sitzung kommen fällige Karteikarten
  aus dem SM-2-Algorithmus.
- **Themenfelder** — Geschichte, Geografie, Politik & Gesellschaft, Wirtschaft
  & Finanzen, Naturwissenschaften & Technik, Medien/Statistik/Argumentation,
  Kultur & Sprache.
- **Sitzungsabschluss** — 3 Merksätze, max. 5 Karteikarten, Bewertung der
  Antwortsicherheit, Vorschlag für den nächsten Wiederholungstermin.
- **Quellen kritisch** — bei aktuellen oder umstrittenen Fakten verlangt die
  Persona verifizierte Quellen und trennt Fakt, Vereinfachung und Unsicherheit.
- **LLM-agnostisch** — funktioniert mit OpenAI, Azure OpenAI, Ollama,
  LM Studio, vLLM, etc. (jeder OpenAI-kompatible Endpunkt).

## Architektur

```
                ┌──────────────────────────────┐
   Browser ──▶  │  Wissenswerkstatt (FastAPI)  │  ◀── LLM (OpenAI-kompatibel)
                │  - Chat-UI                   │
                │  - SM-2 SRS                  │
                │  - SQLite (Volume)           │
                └──────────────┬───────────────┘
                               │ updates
                ┌──────────────▼───────────────┐
                │  Watchtower                  │  ◀── neuer Image-Tag in GHCR
                │  (Auto-Update)               │
                └──────────────────────────────┘
                               ▲
                               │  GitHub Actions
                ┌──────────────┴───────────────┐
                │  ghcr.io/USER/wissenswerkstatt│
                └──────────────────────────────┘
                               ▲
                ┌──────────────┴───────────────┐
                │  GitHub Repo (dieses hier)    │
                └──────────────────────────────┘
```

## Setup in 5 Schritten

### 1) Repo auf GitHub anlegen

```bash
cd wissenswerkstatt
git init
git add .
git commit -m "Initial commit: Wissenswerkstatt v1"
git branch -M main
git remote add origin git@github.com:<DEIN-USER>/wissenswerkstatt.git
git push -u origin main
```

> Das Repo heißt hier z.B. `dein-user/wissenswerkstatt`. Daraus ergibt sich
> der Image-Pfad `ghcr.io/dein-user/wissenswerkstatt`.

### 2) GitHub Actions baut das Image automatisch

Bei jedem Push auf `main` startet der Workflow
`.github/workflows/docker-publish.yml`. Er baut Multi-Arch
(`linux/amd64` + `linux/arm64`) und pusht das Image nach
`ghcr.io/<USER>/wissenswerkstatt` mit den Tags `latest`, `<branch>` und `<sha>`.

Du brauchst nichts weiter einzurichten — `GITHUB_TOKEN` reicht für GHCR.
Falls das Image trotzdem „private" bleibt, in GitHub unter
**Packages → Package settings** auf **Public** stellen.

### 3) `.env` für Portainer vorbereiten

Kopiere `.env.example` zu `.env` und trage deine LLM-Daten ein:

```env
# OpenAI
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini

# Oder lokal mit Ollama (auf dem Host):
# LLM_BASE_URL=http://host.docker.internal:11434/v1
# LLM_API_KEY=ollama
# LLM_MODEL=llama3.1
```

Für Ollama/Local LLMs: `host.docker.internal` funktioniert auf Docker Desktop
(Win/Mac) und Linux mit Docker ≥ 20.10. Sonst die IP des Host-Interfaces eintragen.

### 4) Portainer-Stack anlegen

**Portainer → Stacks → Add Stack** mit folgenden Optionen:

- Name: `wissenswerkstatt`
- Build method: **Git repository** (empfohlen) **oder Web editor**
- Repository URL: `https://github.com/<DEIN-USER>/wissenswerkstatt.git`
- Compose path: `docker-compose.yml`
- **Environment variables**: `.env`-Inhalt hier reinkopieren
  (Portainer fragt nach den Vars — am einfachsten vorher die `GHCR_USER`/`IMAGE_NAME` setzen):

```env
GHCR_USER=ghcr.io/<DEIN-USER>
IMAGE_NAME=wissenswerkstatt
IMAGE_TAG=latest
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini
APP_PORT=8080
WATCHTOWER_POLL_INTERVAL=86400
```

> **Wichtig:** In Portainer den Stack **nicht** mit `Build method = Web editor`
> UND dem Git-Repo-Build mischen. Eine Methode wählen.

**Deploy the stack** — fertig.

Die App läuft auf `http://<server-ip>:8080/`.

### 5) Auto-Update ist bereits eingebaut

Der `watchtower`-Service im selben Compose prüft alle 24h (per Default) das
Image `ghcr.io/<USER>/wissenswerkstatt:latest` und ersetzt den laufenden
Container, sobald ein neuer Tag da ist. Das Volume `wissenswerkstatt_data`
bleibt dabei unangetastet — deine Daten überleben jedes Update.

**Schnellerer Update-Zyklus:** `WATCHTOWER_POLL_INTERVAL=3600` (jede Stunde).

**Manuell updaten ohne Watchtower:** In Portainer auf den Stack → **Pull and redeploy**.

## Bedienung

1. Tab **Sitzung** → Themenfeld wählen (oder freilassen) → *Sitzung starten*.
2. Die Wissenswerkstatt beginnt mit fälligen Wiederholungen.
3. Antworte in eigenen Worten — du bekommst eine Bewertung.
4. *Sitzung beenden* → 3 Merksätze + max. 5 Karteikarten + Antwortsicherheit.
5. Tab **Wiederholung** → fällige Karten mit 0–5 bewerten (SM-2 plant nächsten Termin).
6. Tab **Fortschritt** → Übersicht nach Thema, Gesamtzahlen, durchschnittliche Sicherheit.

## API

`GET  /api/health` — Healthcheck  
`GET  /api/topics` — Themenfelder  
`GET  /api/progress` — Statistik  
`GET  /api/cards/due?limit=10` — fällige Karten  
`POST /api/cards/{id}/review` — Karte bewerten (0..5)  
`POST /api/cards/{id}/question` — Frage zur Karte generieren (LLM)  
`POST /api/session/start` — neue Sitzung  
`POST /api/session/{id}/message` — Chat-Nachricht  
`POST /api/session/{id}/preview-summary` — Merksätze + Karten-Entwurf  
`POST /api/session/{id}/confirm-end` — Sitzung final schließen  

OpenAPI-Doku unter `/docs`.

## Entwicklung lokal

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r app/requirements.txt
cp .env.example .env   # ausfüllen
uvicorn app.main:app --reload --port 8080
```

## Datenspeicherung

- SQLite-Datei: `/app/data/wissenswerkstatt.db` (im Volume `wissenswerkstatt_data`)
- WAL-Modus aktiv, Foreign Keys aktiv
- Backups: `docker run --rm -v wissenswerkstatt_data:/data -v $PWD:/out alpine cp /data/wissenswerkstatt.db /out/`

## Persona „Wissenswerkstatt"

Der vollständige System-Prompt lebt in [`app/prompts.py`](app/prompts.py). Er
definiert Verhalten, Bewertungsstufen, Themenfelder, Stil und das JSON-Schema
für die Sitzungs-Zusammenfassung.

## Lizenz

MIT — nutze, ändere, hoste wie du willst.
