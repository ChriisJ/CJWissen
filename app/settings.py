"""Settings-Repository: lädt/löscht Werte aus der DB mit Env-Fallback.

Reihenfolge der Auflösung:
  1. Wert in SQLite-Tabelle `settings_kv`
  2. Wert in Umgebungsvariable (über Pydantic-Settings)
  3. Pydantic-Default
"""
from __future__ import annotations

import os
from typing import Any

from . import database as db
from .config import settings

# Welche Keys werden in der DB gespeichert (Whitelist — keine beliebigen Writes)
SETTING_KEYS: dict[str, dict[str, Any]] = {
    "llm_base_url":   {"label": "LLM Base URL",   "type": "string",  "default": settings.llm_base_url},
    "llm_api_key":    {"label": "LLM API Key",    "type": "string",  "default": settings.llm_api_key, "secret": True},
    "llm_model":      {"label": "LLM Modell",     "type": "string",  "default": settings.llm_model},
    "llm_max_tokens": {"label": "LLM max Tokens", "type": "int",     "default": settings.llm_max_tokens},
    "llm_temperature":{"label": "LLM Temperature","type": "float",   "default": settings.llm_temperature},
    "app_secret":     {"label": "App-Geheimnis",  "type": "string",  "default": settings.app_secret, "secret": True},
}


def get(key: str) -> Any:
    """Liest einen Wert: erst DB, dann Env/Default."""
    if key not in SETTING_KEYS:
        raise KeyError(f"Unbekannter Setting-Key: {key}")
    with db.get_conn() as conn:
        row = conn.execute("SELECT value FROM settings_kv WHERE key = ?", (key,)).fetchone()
        if row is not None:
            return _coerce(row["value"], SETTING_KEYS[key]["type"])
    return SETTING_KEYS[key]["default"]


def set_value(key: str, value: str) -> None:
    """Schreibt einen Wert in die DB. Leerer String löscht den Override."""
    if key not in SETTING_KEYS:
        raise KeyError(f"Unbekannter Setting-Key: {key}")
    with db.get_conn() as conn:
        if value is None or value == "":
            conn.execute("DELETE FROM settings_kv WHERE key = ?", (key,))
        else:
            conn.execute(
                "INSERT INTO settings_kv (key, value, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
                (key, value, _now_iso()),
            )


def get_all(include_secrets: bool = False) -> dict[str, Any]:
    """Gibt alle Settings zurück. Secrets werden maskiert, wenn nicht explizit gewünscht."""
    out: dict[str, Any] = {}
    for k, meta in SETTING_KEYS.items():
        v = get(k)
        if meta.get("secret") and not include_secrets and v:
            v = _mask(v)
        out[k] = v
    return out


def has_overrides() -> bool:
    """True, wenn mindestens ein Wert explizit via UI gesetzt wurde."""
    with db.get_conn() as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM settings_kv").fetchone()
        return (row["c"] or 0) > 0


def is_configured() -> bool:
    """True, wenn das System arbeitsfähig aussieht: LLM-Key vorhanden (oder lokaler Endpunkt)."""
    base = (get("llm_base_url") or "").lower()
    if "localhost" in base or "127.0.0.1" in base or "host.docker.internal" in base:
        return True
    return bool(get("llm_api_key"))


# ---------- helpers ----------

def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _coerce(value: str, t: str) -> Any:
    if t == "int":
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0
    if t == "float":
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
    return value


def _mask(s: str) -> str:
    s = str(s)
    if len(s) <= 8:
        return "•" * len(s)
    return s[:4] + "•" * (len(s) - 8) + s[-4:]


# Aktive Settings — wird vom LLM-Client bei jedem Call gelesen
def active() -> dict[str, Any]:
    return {
        "llm_base_url":   get("llm_base_url"),
        "llm_api_key":    get("llm_api_key"),
        "llm_model":      get("llm_model"),
        "llm_max_tokens": int(get("llm_max_tokens") or 1500),
        "llm_temperature": float(get("llm_temperature") or 0.4),
        "app_secret":     get("app_secret"),
    }
