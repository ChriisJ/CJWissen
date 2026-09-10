"""Karten-Endpunkte: fällige Karten, Review, Karten erstellen."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from .. import coach
from ..models import CardOut, ReviewIn, ReviewOut
from ..topics import TOPICS, topic_label

router = APIRouter(prefix="/api/cards", tags=["cards"])


@router.get("/due", response_model=list[CardOut])
async def list_due(limit: int = Query(default=10, ge=1, le=50)):
    return coach.get_due_cards(limit=limit)


@router.post("", response_model=CardOut)
async def create_card(payload: dict):
    front = (payload.get("front") or "").strip()
    back = (payload.get("back") or "").strip()
    topic = (payload.get("topic") or "").strip()
    if not front or not back:
        raise HTTPException(400, "front und back sind Pflicht")
    if not any(t["id"] == topic for t in TOPICS):
        raise HTTPException(400, f"Unbekanntes Thema: {topic}")
    return coach.add_card(front=front, back=back, topic=topic)


@router.post("/{card_id}/review", response_model=ReviewOut)
async def review_card(card_id: int, payload: ReviewIn):
    try:
        result = coach.review_card(card_id, payload.quality)
    except KeyError:
        raise HTTPException(404, "Karte nicht gefunden")
    return ReviewOut(**result)


@router.post("/{card_id}/question")
async def make_question(card_id: int):
    """Erzeugt aus einer Karte eine mündliche Frage (LLM-formuliert)."""
    card = coach.get_card(card_id)
    if not card:
        raise HTTPException(404, "Karte nicht gefunden")
    question = await coach.build_review_question(
        CardOut(
            id=card["id"],
            front=card["front"],
            back=card["back"],
            topic=card["topic"],
            ease=card["ease"],
            interval_days=card["interval_days"],
            repetitions=card["repetitions"],
            due_at=card["due_at"],
        )
    )
    return {
        "card_id": card_id,
        "question": question,
        "topic_label": topic_label(card["topic"]),
    }
