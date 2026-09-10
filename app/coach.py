"""Coach-Logik: LLM-Interaktion, Karten-Extraktion, Wiederholungs-Sessions."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from . import database as db
from .llm import LLMError, chat, chat_json
from .models import CardOut
from .prompts import (
    BASE_SYSTEM_PROMPT,
    build_closing_request_prompt,
    build_intro_message,
)
from .topics import TOPICS


# --- Hilfsfunktionen ----------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _row_to_card(row: Any) -> CardOut:
    return CardOut(
        id=row["id"],
        front=row["front"],
        back=row["back"],
        topic=row["topic"],
        ease=row["ease"],
        interval_days=row["interval_days"],
        repetitions=row["repetitions"],
        due_at=row["due_at"],
    )


# --- Session-Verwaltung -------------------------------------

def start_session(topic: str | None) -> int:
    """Legt eine neue Session an und gibt die ID zurück."""
    with db.get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO sessions (started_at, topic) VALUES (?, ?)",
            (_now_iso(), topic),
        )
        return int(cur.lastrowid)


def end_session(session_id: int, self_rating: int) -> None:
    with db.get_conn() as conn:
        conn.execute(
            "UPDATE sessions SET ended_at = ?, self_rating = ? WHERE id = ?",
            (_now_iso(), int(self_rating), session_id),
        )


def get_session(session_id: int) -> dict[str, Any] | None:
    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        return dict(row) if row else None


def get_due_cards(limit: int = 5) -> list[CardOut]:
    """Liefert fällige Karten (max. limit) — chronologisch."""
    with db.get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM cards WHERE due_at <= ? ORDER BY due_at ASC LIMIT ?",
            (_now_iso(), limit),
        ).fetchall()
        return [_row_to_card(r) for r in rows]


def get_messages(session_id: int) -> list[dict[str, str]]:
    with db.get_conn() as conn:
        rows = conn.execute(
            "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC",
            (session_id,),
        ).fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in rows]


def add_message(session_id: int, role: str, content: str) -> None:
    with db.get_conn() as conn:
        conn.execute(
            "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (session_id, role, content, _now_iso()),
        )


# --- Karten-CRUD --------------------------------------------

def add_card(
    *,
    front: str,
    back: str,
    topic: str,
    source_session: int | None = None,
    due_at: str | None = None,
) -> CardOut:
    from .srs import new_card_due_iso

    due = due_at or new_card_due_iso()
    with db.get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO cards (front, back, topic, source_session, due_at, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (front, back, topic, source_session, due, _now_iso()),
        )
        card_id = int(cur.lastrowid)
        row = conn.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()
        return _row_to_card(row)


def get_card(card_id: int) -> dict[str, Any] | None:
    with db.get_conn() as conn:
        row = conn.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()
        return dict(row) if row else None


def review_card(card_id: int, quality: int) -> dict[str, Any]:
    from .srs import sm2_update

    card = get_card(card_id)
    if not card:
        raise KeyError(f"Karte {card_id} existiert nicht")

    r, e, i, due = sm2_update(
        quality=quality,
        repetitions=card["repetitions"],
        ease=card["ease"],
        interval_days=card["interval_days"],
    )
    with db.get_conn() as conn:
        conn.execute(
            "UPDATE cards SET ease = ?, interval_days = ?, repetitions = ?, due_at = ? "
            "WHERE id = ?",
            (e, i, r, due, card_id),
        )
        conn.execute(
            "INSERT INTO reviews (card_id, quality, reviewed_at) VALUES (?, ?, ?)",
            (card_id, int(quality), _now_iso()),
        )
    return {
        "card_id": card_id,
        "next_due_at": due,
        "next_interval_days": i,
        "ease": e,
    }


# --- Wiederholungs-Phase (Karten → Frage an LLM) -----------

async def build_review_question(card: CardOut) -> str:
    """Baut aus einer Karte eine echte Frage — nicht nur die Vorderseite abschreiben."""
    msgs = [
        {"role": "system", "content": (
            "Du formulierst eine abwechslungsreiche, mündlich wirkende Frage "
            "zu folgender Karteikarte. Stelle die Frage so, dass der Nutzer "
            "die Antwort in 1-3 Sätzen geben muss. Gib NUR die Frage aus, "
            "keine Lösungen, keine Bewertung."
        )},
        {"role": "user", "content": (
            f"Thema: {card.topic}\nVorderseite (Begriff/Frage): {card.front}\n"
            f"Rückseite (Antwort, NICHT verraten!): {card.back}"
        )},
    ]
    return (await chat(msgs, temperature=0.5, max_tokens=200)).strip()


# --- LLM-Aufrufe --------------------------------------------

def _session_topic(session_id: int) -> str | None:
    s = get_session(session_id)
    return s.get("topic") if s else None


async def session_intro(session_id: int) -> str:
    """Generiert die erste Assistenten-Nachricht (mit fälligen Karten als Hook)."""
    due = get_due_cards(limit=3)
    if not due:
        intro = build_intro_message(has_due_cards=False)
    else:
        intro = build_intro_message(has_due_cards=True)
        # Optional: Eine Karte als Konkretisierung einbauen
        intro += "\n\nErste Wiederholung: " + due[0].front

    add_message(session_id, "assistant", intro)
    return intro


async def send_user_message(session_id: int, user_text: str) -> dict[str, Any]:
    """Sendet eine Nutzer-Nachricht, holt LLM-Antwort, wertet aus, speichert Karten."""
    topic = _session_topic(session_id)
    topic_hint = f"\n\nAKTUELLES THEMA DER SITZUNG: {topic}" if topic else ""

    sys_prompt = BASE_SYSTEM_PROMPT + topic_hint

    history = [{"role": "system", "content": sys_prompt}]
    history.extend(get_messages(session_id))
    history.append({"role": "user", "content": user_text})

    add_message(session_id, "user", user_text)

    try:
        reply = (await chat(history, max_tokens=900)).strip()
    except LLMError as exc:
        # Anwenderfreundlicher Fallback
        reply = (
            "Die Verbindung zum LLM ist gerade gestört. "
            f"Technische Info: {exc}\n\n"
            "Versuch es in einem Moment nochmal, oder prüfe LLM_BASE_URL / LLM_API_KEY."
        )

    add_message(session_id, "assistant", reply)

    # Bewertung & Karten werden am Sitzungsende in einem separaten Schritt
    # generiert. Pro Antwort nur eine leichte, optionale Bewertung.
    evaluation = await _try_evaluate_answer(user_text, reply)

    return {
        "reply": reply,
        "evaluation": evaluation,
    }


async def _try_evaluate_answer(user_text: str, coach_reply: str) -> str | None:
    """Versucht, aus der Coach-Antwort eine Bewertungsstufe zu extrahieren.

    Wir lassen die LLM nicht jede Nachricht neu bewerten — das wäre
    verschwenderisch. Stattdessen suchen wir im Reply nach Schlüsselwörtern.
    """
    txt = coach_reply.lower()
    if "nicht beantwortet" in txt or "keine antwort" in txt or "keine antwort von dir" in txt:
        return "nicht_beantwortet"
    if "falsch" in txt and "korrekt" not in txt[: txt.find("falsch") + 20]:
        return "falsch"
    if "teilweise" in txt or "nicht ganz" in txt or "fast richtig" in txt:
        return "teilweise"
    if "unklar" in txt or "bitte präziser" in txt or "meinst du" in txt:
        return "unklar"
    if re.search(r"\b(korrekt|richtig|stimmt|genau|exakt)\b", txt):
        return "korrekt"
    return None


# --- Sitzungsabschluss --------------------------------------

async def close_session(session_id: int, self_rating: int) -> dict[str, Any]:
    """Generiert Merksätze + Karten, speichert sie, schließt die Session ab."""
    sys_prompt = BASE_SYSTEM_PROMPT + build_closing_request_prompt()
    history = [{"role": "system", "content": sys_prompt}]
    history.extend(get_messages(session_id))
    history.append({
        "role": "user",
        "content": (
            "Sitzung ist beendet. Bitte fasse die wichtigsten Erkenntnisse "
            "in 3 Merksätzen zusammen und schlage max. 5 Karteikarten vor. "
            "Am Ende: nur der JSON-Block wie oben beschrieben."
        ),
    })

    end_session(session_id, self_rating)

    try:
        data = await chat_json(history, max_tokens=1200, temperature=0.3)
    except LLMError:
        # Fallback ohne JSON
        raw = await chat(history, max_tokens=900, temperature=0.3)
        data = _parse_loose_summary(raw)

    # --- Merksätze übernehmen -----------------------------
    merksaetze = [str(s).strip() for s in data.get("merksaetze", []) if str(s).strip()][:3]
    while len(merksaetze) < 3:
        merksaetze.append("(kein weiterer Merksatz)")

    # --- Karten übernehmen -------------------------------
    valid_topic_ids = {t["id"] for t in TOPICS}
    new_cards: list[CardOut] = []
    for k in data.get("karteikarten", [])[:5]:
        front = str(k.get("front", "")).strip()
        back = str(k.get("back", "")).strip()
        topic = str(k.get("topic", "")).strip()
        if not front or not back or topic not in valid_topic_ids:
            continue
        new_cards.append(add_card(
            front=front,
            back=back,
            topic=topic,
            source_session=session_id,
        ))

    return {
        "session_id": session_id,
        "merksaetze": merksaetze,
        "karteikarten": new_cards,
    }


def _parse_loose_summary(text: str) -> dict[str, Any]:
    """Grober Fallback: zieht erste 3 Sätze + Frage-Antwort-Paare aus Text."""
    sentences = re.split(r"(?<=[.!?])\s+", text.replace("\n", " ").strip())
    merksaetze = [s for s in sentences if 8 < len(s) < 200][:3]
    return {"merksaetze": merksaetze, "karteikarten": []}
