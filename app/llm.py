"""LLM-Client: OpenAI-kompatibel, einheitlich via httpx.

Funktioniert mit OpenAI, Azure OpenAI (mit /openai/v1-Endpunkt),
Ollama (/v1), LM Studio, vLLM, etc.
"""
from __future__ import annotations

import json
from typing import Any

import httpx

from .config import settings


class LLMError(RuntimeError):
    pass


async def chat(
    messages: list[dict[str, str]],
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
    json_mode: bool = False,
) -> str:
    """Schickt eine Chat-Completion-Anfrage und gibt den Text zurück."""
    if not settings.llm_api_key and "api.openai.com" in settings.llm_base_url:
        raise LLMError(
            "LLM_API_KEY ist leer. Setze den Key in der .env-Datei oder "
            "ändere LLM_BASE_URL auf einen lokalen Endpunkt (z.B. Ollama)."
        )

    url = settings.llm_base_url.rstrip("/") + "/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.llm_api_key}",
    }
    payload: dict[str, Any] = {
        "model": settings.llm_model,
        "messages": messages,
        "temperature": temperature if temperature is not None else settings.llm_temperature,
        "max_tokens": max_tokens if max_tokens is not None else settings.llm_max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(url, headers=headers, json=payload)
    except httpx.RequestError as exc:
        raise LLMError(f"LLM-Endpunkt nicht erreichbar: {exc}") from exc

    if r.status_code != 200:
        # Lieber Klartext als Cryptic
        raise LLMError(f"LLM-Fehler {r.status_code}: {r.text[:500]}")

    data = r.json()
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        raise LLMError(f"Unerwartete LLM-Antwort: {json.dumps(data)[:500]}") from exc


async def chat_json(messages: list[dict[str, str]], **kwargs: Any) -> dict[str, Any]:
    """Wie chat(), aber versucht JSON zu parsen. Fällt auf Text zurück."""
    text = await chat(messages, json_mode=True, **kwargs)
    text = text.strip()
    # Robuster Parser: erstes {...}-Objekt
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise LLMError(f"LLM lieferte kein JSON: {text[:200]}")
    snippet = text[start : end + 1]
    try:
        return json.loads(snippet)
    except json.JSONDecodeError as exc:
        raise LLMError(f"LLM-JSON kaputt: {exc} | {snippet[:200]}") from exc
