"""Setup-Wizard-Endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .. import settings as app_settings
from ..llm import LLMError, test_connection

router = APIRouter(prefix="/api/setup", tags=["setup"])


# Reihenfolge ist UI-relevant: zuerst die wichtigsten, dann optionale
ALL_KEYS = [
    "llm_base_url",
    "llm_api_key",
    "llm_model",
    "llm_max_tokens",
    "llm_temperature",
    "app_secret",
]


@router.get("")
async def get_setup() -> dict:
    """Liefert aktuelle Einstellungen (Secrets maskiert) + Status."""
    return {
        "configured": app_settings.is_configured(),
        "has_overrides": app_settings.has_overrides(),
        "values": app_settings.get_all(include_secrets=False),
        "keys": [
            {
                "key": k,
                "label": app_settings.SETTING_KEYS[k]["label"],
                "type": app_settings.SETTING_KEYS[k]["type"],
                "secret": bool(app_settings.SETTING_KEYS[k].get("secret")),
            }
            for k in ALL_KEYS
        ],
    }


@router.post("")
async def post_setup(payload: dict) -> dict:
    """Speichert die übermittelten Settings. Leere Strings löschen den Override."""
    if not isinstance(payload, dict):
        raise HTTPException(400, "Body muss ein JSON-Objekt sein")

    for k in ALL_KEYS:
        if k in payload:
            v = payload[k]
            if v is None:
                v = ""
            app_settings.set_value(k, str(v))

    return {"ok": True, "configured": app_settings.is_configured()}


@router.post("/test")
async def post_test() -> dict:
    """Testet die aktuelle Konfiguration gegen den LLM-Endpunkt."""
    try:
        return await test_connection()
    except LLMError as exc:
        raise HTTPException(400, str(exc))


@router.post("/reset")
async def post_reset() -> dict:
    """Setzt alle UI-Overrides zurück — Env-Variablen/Defaults greifen wieder."""
    from .. import database as db
    with db.get_conn() as conn:
        conn.execute("DELETE FROM settings_kv")
    return {"ok": True, "configured": app_settings.is_configured()}
