"""LLM-Client: OpenAI-kompatibel, einheitlich via httpx.

Liest Konfiguration zur Laufzeit aus `app.settings` (DB > Env).
Funktioniert mit OpenAI, Azure OpenAI, Ollama, LM Studio, vLLM, etc.
"""
from __future__ import annotations

import json
from typing import Any

import httpx

from . import settings as app_settings


class LLMError(RuntimeError):
    pass


def _looks_local(base_url: str) -> bool:
    base = (base_url or "").lower()
    return any(x in base for x in ("localhost", "127.0.0.1", "host.docker.internal"))


async def chat(
    messages: list[dict[str, str]],
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
    json_mode: bool = False,
) -> str:
    """Schickt eine Chat-Completion-Anfrage und gibt den Text zurück."""
    cfg = app_settings.active()
    base_url = cfg["llm_base_url"]
    api_key = cfg["llm_api_key"]
    model = cfg["llm_model"]

    if not api_key and "api.openai.com" in (base_url or "") and not _looks_local(base_url):
        raise LLMError(
            "LLM_API_KEY ist leer. Setze den Key in der .env-Datei, "
            "über die Setup-Seite oder ändere LLM_BASE_URL auf einen lokalen Endpunkt."
        )

    url = (base_url or "").rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature if temperature is not None else float(cfg["llm_temperature"]),
        "max_tokens": max_tokens if max_tokens is not None else int(cfg["llm_max_tokens"]),
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(url, headers=headers, json=payload)
    except httpx.RequestError as exc:
        raise LLMError(f"LLM-Endpunkt nicht erreichbar: {exc}") from exc

    if r.status_code != 200:
        raise LLMError(f"LLM-Fehler {r.status_code}: {r.text[:500]}")

    data = r.json()
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        raise LLMError(f"Unerwartete LLM-Antwort: {json.dumps(data)[:500]}") from exc


async def chat_json(messages: list[dict[str, str]], **kwargs: Any) -> dict[str, Any]:
    """Wie chat(), aber versucht JSON zu parsen."""
    text = await chat(messages, json_mode=True, **kwargs)
    text = text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise LLMError(f"LLM lieferte kein JSON: {text[:200]}")
    snippet = text[start : end + 1]
    try:
        return json.loads(snippet)
    except json.JSONDecodeError as exc:
        raise LLMError(f"LLM-JSON kaputt: {exc} | {snippet[:200]}") from exc


async def test_connection() -> dict[str, Any]:
    """Prüft, ob der LLM-Endpunkt erreichbar ist und das Modell antwortet."""
    cfg = app_settings.active()
    base_url = (cfg["llm_base_url"] or "").rstrip("/")
    if not base_url:
        raise LLMError("LLM Base URL fehlt.")

    headers = {"Content-Type": "application/json"}
    if cfg["llm_api_key"]:
        headers["Authorization"] = f"Bearer {cfg['llm_api_key']}"

    # 1. /models abfragen (wenn verfügbar — OpenAI/Ollama/vLLM)
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(base_url + "/models", headers=headers)
            if r.status_code == 200:
                data = r.json()
                models = [m.get("id") or m.get("name") for m in data.get("data", []) if m]
                models = [m for m in models if m]
                return {
                    "ok": True,
                    "endpoint": base_url,
                    "model": cfg["llm_model"],
                    "models_sample": models[:20],
                    "model_available": (cfg["llm_model"] in models) if models else None,
                }
    except httpx.RequestError:
        pass  # Fallback unten

    # 2. Minimal-Ping mit chat/completions
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post(
                base_url + "/chat/completions",
                headers=headers,
                json={
                    "model": cfg["llm_model"],
                    "messages": [{"role": "user", "content": "ping"}],
                    "max_tokens": 5,
                },
            )
    except httpx.RequestError as exc:
        raise LLMError(f"Endpunkt nicht erreichbar: {exc}") from exc

    if r.status_code != 200:
        raise LLMError(f"HTTP {r.status_code}: {r.text[:200]}")
    return {
        "ok": True,
        "endpoint": base_url,
        "model": cfg["llm_model"],
        "models_sample": [],
        "model_available": None,
    }
