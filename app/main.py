"""FastAPI-App: Wissenswerkstatt."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import database as db
from .config import settings
from .routers import cards, progress, session

app = FastAPI(
    title="Wissenswerkstatt",
    description="Persönlicher Lerncoach für belastbares Allgemeinwissen.",
    version="1.0.0",
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
app.include_router(session.router)
app.include_router(cards.router)
app.include_router(progress.router)


@app.get("/api/health")
async def health() -> dict:
    return {
        "status": "ok",
        "model": settings.llm_model,
        "base_url": settings.llm_base_url,
        "has_api_key": bool(settings.llm_api_key),
    }


# Statische UI ausliefern
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


# Optionaler Geheimnisschutz
@app.middleware("http")
async def secret_guard(request, call_next):
    if settings.app_secret and not request.url.path.startswith("/api/health"):
        token = (
            request.headers.get("x-app-secret")
            or request.query_params.get("secret")
        )
        if token != settings.app_secret:
            if request.url.path.startswith("/api/"):
                return JSONResponse({"detail": "unauthorized"}, status_code=401)
    return await call_next(request)
