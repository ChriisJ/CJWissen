"""FastAPI-App: Wissenswerkstatt."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import database as db
from . import settings as app_settings
from .config import settings
from .routers import cards, progress, session, setup

app = FastAPI(
    title="Wissenswerkstatt",
    description="Persönlicher Lerncoach für belastbares Allgemeinwissen.",
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# DB beim Start initialisieren
@app.on_event("startup")
def _startup() -> None:
    db.init_db()


# API-Routen
app.include_router(setup.router)
app.include_router(session.router)
app.include_router(cards.router)
app.include_router(progress.router)


@app.get("/api/health")
async def health() -> dict:
    cfg = app_settings.active()
    return {
        "status": "ok",
        "configured": app_settings.is_configured(),
        "model": cfg["llm_model"],
        "base_url": cfg["llm_base_url"],
        "has_api_key": bool(cfg["llm_api_key"]),
        "version": "1.1.0",
    }


# Statische UI ausliefern
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/setup")
async def setup_page() -> FileResponse:
    """Setup-Wizard-Seite (auch erreichbar, wenn schon konfiguriert)."""
    return FileResponse(STATIC_DIR / "setup.html")


@app.get("/")
async def index(request: Request) -> FileResponse:
    """Hauptseite oder Redirect zum Setup, wenn nicht konfiguriert."""
    if not app_settings.is_configured():
        # Nicht konfiguriert → direkt in den Wizard
        return RedirectResponse(url="/setup", status_code=307)
    return FileResponse(STATIC_DIR / "index.html")


# Optionaler Geheimnisschutz — gilt für alles AUẞER Setup und Health
@app.middleware("http")
async def secret_guard(request: Request, call_next):
    path = request.url.path
    if (
        settings.app_secret
        and not path.startswith("/api/health")
        and not path.startswith("/api/setup")
        and not path.startswith("/setup")
        and not path.startswith("/static")
    ):
        token = (
            request.headers.get("x-app-secret")
            or request.query_params.get("secret")
        )
        if token != settings.app_secret:
            if path.startswith("/api/"):
                return JSONResponse({"detail": "unauthorized"}, status_code=401)
    return await call_next(request)
