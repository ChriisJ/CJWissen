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
- **Web-Setup-Wizard** — kein `.env`-Gefrickel. Beim ersten Aufruf wählst du
  deinen LLM-Provider (OpenAI, Ollama, LM Studio, Azure, Custom), trägst den
  Key ein, klickst **Verbindung testen**, **Speichern & starten** — fertig.
  Später jederzeit über den **⚙ Setup**-Tab änderbar.
- **LLM-agnostisch** — funktioniert mit OpenAI, Azure OpenAI, Ollama,
  LM Studio, vLLM, etc. (jeder OpenAI-kompatible Endpunkt).

## Architektur

```
                ┌──────────────────────────────┐
   Browser ──▶  │  Wissenswerkstatt (FastAPI)  │  ◀── LLM (OpenAI-kompatibel)
                │  - Chat-UI                   │
                │  - Setup-Wizard              │
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
                │  ghcr.io/USER/CJWissen        │
                └──────────────────────────────┘
                               ▲
                ┌──────────────┴───────────────┐
                │  GitHub Repo (dieses hier)    │
                └──────────────────────────────┘
```

## Setup in 4 Schritten

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

### 2) GitHub Actions baut das Image automatisch

Bei jedem Push auf `main` startet der Workflow
`.github/workflows/docker-publish.yml`. Er baut Multi-Arch
(`linux/amd64` + `linux/arm64`) und pusht das Image nach
`ghcr.io/<USER>/<REPO>`. Dazu braucht dein PAT den Scope `workflow`.

### 3) Portainer-Stack anlegen

**Portainer → Stacks → Add Stack** mit:

- **Build method**: Git repository
- **Repository URL**: `https://github.com/<DEIN-USER>/wissenswerkstatt.git`
- **Compose path**: `docker-compose.yml`
- **Environment variables** — du brauchst jetzt **nur noch diese**:

```env
GHCR_USER=ghcr.io/<DEIN-USER>
IMAGE_NAME=<REPO-NAME>
IMAGE_TAG=latest
APP_PORT=8080
WATCHTOWER_POLL_INTERVAL=86400
```

> **Keine LLM-Variablen mehr nötig.** Die werden über den Wizard gesetzt.

**Deploy the stack** — fertig.

### 4) Im Browser öffnen & einrichten

`http://<server-ip>:8080/` aufrufen. Beim ersten Mal wirst du automatisch zum
**Setup-Wizard** weitergeleitet:

1. **Provider wählen** (OpenAI / Ollama / LM Studio / Azure / Custom) — die
   wichtigsten Felder werden automatisch ausgefüllt.
2. **API-Key eintragen** (bei lokalen Endpunkten leer lassen).
3. **Modellname** anpassen, falls dein Provider was anderes erwartet.
4. **Verbindung testen** klicken — grünes Häkchen = alles ok.
5. **Speichern & starten** → du landest in der Hauptapp.

Änderungen später jederzeit über den **⚙ Setup**-Tab in der App.

## Bedienung

1. Tab **Sitzung** → Themenfeld wählen (oder freilassen) → *Sitzung starten*.
2. Die Wissenswerkstatt beginnt mit fälligen Wiederholungen.
3. Antworte in eigenen Worten — du bekommst eine Bewertung.
4. *Sitzung beenden* → 3 Merksätze + max. 5 Karteikarten + Antwortsicherheit.
5. Tab **Wiederholung** → fällige Karten mit 0–5 bewerten (SM-2 plant nächsten Termin).
6. Tab **Fortschritt** → Übersicht nach Thema, Gesamtzahlen, durchschnittliche Sicherheit.
7. Tab **⚙ Setup** → Provider, API-Key, Modell jederzeit anpassbar.

## API

`GET  /api/health` — Healthcheck (zeigt `configured: true/false`)  
`GET  /api/setup` — aktuelle Konfiguration (Secrets maskiert)  
`POST /api/setup` — Konfiguration speichern  
`POST /api/setup/test` — Verbindung testen  
`POST /api/setup/reset` — UI-Overrides löschen, Env greift wieder  
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

## Optionale ENV-Konfiguration

Diese Variablen funktionieren weiterhin als Fallback, wenn der Setup-Wizard
nicht benutzt wird (z.B. für CI/CD oder headless-Deployments):

```env
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini
LLM_MAX_TOKENS=1500
LLM_TEMPERATURE=0.4
APP_SECRET=
```

**Wichtig**: Die im Wizard gesetzten Werte haben Vorrang vor den Env-Variablen.
Über `POST /api/setup/reset` kann man auf Env-Fallback zurücksetzen.

## Entwicklung lokal

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r app/requirements.txt
cp .env.example .env   # ausfüllen
uvicorn app.main:app --reload --port 8080
```

## Datenspeicherung

- SQLite-Datei: `/app/data/wissenswerkstatt.db` (im Volume `wissenswerkstatt_data`)
- Runtime-Config (LLM-Key, Modell etc.) in der Tabelle `settings_kv` — überlebt Updates
- WAL-Modus aktiv, Foreign Keys aktiv
- Backups: `docker run --rm -v wissenswerkstatt_data:/data -v $PWD:/out alpine cp /data/wissenswerkstatt.db /out/`

## Persona „Wissenswerkstatt"

Der vollständige System-Prompt lebt in [`app/prompts.py`](app/prompts.py). Er
definiert Verhalten, Bewertungsstufen, Themenfelder, Stil und das JSON-Schema
für die Sitzungs-Zusammenfassung.

## Lizenz

MIT — nutze, ändere, hoste wie du willst.
