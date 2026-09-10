"""Session-Endpunkte: starten, chatten, Vorschau, abschließen."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from .. import coach, database as db
from ..models import SessionEnd, SessionOut, SessionStart
from ..topics import TOPICS

router = APIRouter(prefix="/api/session", tags=["session"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@router.post("/start", response_model=SessionOut)
async def start_session(payload: SessionStart) -> SessionOut:
    if payload.topic and not any(t["id"] == payload.topic for t in TOPICS):
        raise HTTPException(400, f"Unbekanntes Thema: {payload.topic}")

    session_id = coach.start_session(payload.topic)
    # Intro direkt generieren und persistieren
    await coach.session_intro(session_id)
    info = coach.get_session(session_id)
    return SessionOut(
        id=session_id,
        started_at=info["started_at"],   # type: ignore[index]
        topic=payload.topic,
    )


@router.post("/{session_id}/message")
async def send_message(session_id: int, payload: dict):
    if not coach.get_session(session_id):
        raise HTTPException(404, "Session nicht gefunden")
    text = (payload.get("message") or "").strip()
    if not text:
        raise HTTPException(400, "Leere Nachricht")
    result = await coach.send_user_message(session_id, text)
    return {
        "session_id": session_id,
        "reply": result["reply"],
        "evaluation": result["evaluation"],
    }


@router.get("/{session_id}/history")
async def history(session_id: int):
    if not coach.get_session(session_id):
        raise HTTPException(404, "Session nicht gefunden")
    with db.get_conn() as conn:
        rows = conn.execute(
            "SELECT role, content, created_at FROM messages "
            "WHERE session_id = ? ORDER BY id ASC",
            (session_id,),
        ).fetchall()
    return [dict(r) for r in rows]


@router.post("/{session_id}/preview-summary")
async def preview_summary(session_id: int):
    """Erzeugt die Abschluss-Zusammenfassung, OHNE die Session zu schließen.

    Das eigentliche Schließen (mit self_rating) passiert in /confirm-end.
    """
    if not coach.get_session(session_id):
        raise HTTPException(404, "Session nicht gefunden")

    # Wir generieren die Daten serverseitig, ohne sie zu persistieren.
    from ..llm import LLMError, chat, chat_json
    from ..prompts import BASE_SYSTEM_PROMPT, build_closing_request_prompt

    sys_prompt = BASE_SYSTEM_PROMPT + build_closing_request_prompt()
    history = [{"role": "system", "content": sys_prompt}]
    history.extend(coach.get_messages(session_id))
    history.append({
        "role": "user",
        "content": (
            "Sitzung geht gleich zu Ende. Bitte fasse die wichtigsten "
            "Erkenntnisse in 3 Merksätzen zusammen und schlage max. 5 "
            "Karteikarten vor. Am Ende: nur der JSON-Block wie beschrieben."
        ),
    })

    try:
        data = await chat_json(history, max_tokens=1200, temperature=0.3)
    except LLMError:
        raw = await chat(history, max_tokens=900, temperature=0.3)
        data = coach._parse_loose_summary(raw)  # type: ignore[attr-defined]

    merksaetze = [str(s).strip() for s in data.get("merksaetze", []) if str(s).strip()][:3]
    while len(merksaetze) < 3:
        merksaetze.append("(kein weiterer Merksatz)")

    valid_topic_ids = {t["id"] for t in TOPICS}
    draft_cards: list[dict] = []
    for k in data.get("karteikarten", [])[:5]:
        front = str(k.get("front", "")).strip()
        back = str(k.get("back", "")).strip()
        topic = str(k.get("topic", "")).strip()
        if front and back and topic in valid_topic_ids:
            draft_cards.append({"front": front, "back": back, "topic": topic})

    return {"merksaetze": merksaetze, "karteikarten": draft_cards}


@router.post("/{session_id}/confirm-end")
async def confirm_end(session_id: int, payload: SessionEnd):
    """Persistiert die im Vorschau generierten Karten und schließt die Session."""
    s = coach.get_session(session_id)
    if not s:
        raise HTTPException(404, "Session nicht gefunden")

    # Falls der User die Vorschau übersprungen hat: jetzt generieren.
    preview = await preview_summary(session_id)

    valid_topic_ids = {t["id"] for t in TOPICS}
    new_cards = []
    for k in preview["karteikarten"]:
        if k["topic"] not in valid_topic_ids:
            continue
        new_cards.append(coach.add_card(
            front=k["front"], back=k["back"], topic=k["topic"],
            source_session=session_id,
        ))

    coach.end_session(session_id, payload.self_rating)

    # Nächsten Wiederholungstermin-Vorschlag
    due_cards = coach.get_due_cards(limit=50)
    next_due_in = None
    if due_cards:
        next_due_in = 0  # sofort
    else:
        with db.get_conn() as conn:
            row = conn.execute(
                "SELECT MIN(due_at) AS d FROM cards"
            ).fetchone()
        if row and row["d"]:
            try:
                d = datetime.fromisoformat(row["d"])
                now = datetime.now(d.tzinfo or timezone.utc)
                next_due_in = max(0, (d - now).days)
            except Exception:
                next_due_in = None

    return {
        "session_id": session_id,
        "merksaetze": preview["merksaetze"],
        "karteikarten": [c.model_dump() for c in new_cards],
        "next_review_in_days": next_due_in,
    }


@router.get("/{session_id}")
async def get_session_info(session_id: int):
    s = coach.get_session(session_id)
    if not s:
        raise HTTPException(404, "Session nicht gefunden")
    return s
