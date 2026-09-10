"""Fortschritt & Themen-Übersicht."""
from __future__ import annotations

from fastapi import APIRouter

from .. import database as db
from ..models import ProgressOut
from ..topics import TOPICS

router = APIRouter(prefix="/api", tags=["progress"])


@router.get("/progress", response_model=ProgressOut)
async def progress() -> ProgressOut:
    with db.get_conn() as conn:
        cards_total = conn.execute("SELECT COUNT(*) AS c FROM cards").fetchone()["c"]
        cards_due = conn.execute(
            "SELECT COUNT(*) AS c FROM cards WHERE due_at <= ?", (_now_iso(),)
        ).fetchone()["c"]
        cards_learned = conn.execute(
            "SELECT COUNT(*) AS c FROM cards WHERE repetitions >= 1"
        ).fetchone()["c"]
        reviews_total = conn.execute("SELECT COUNT(*) AS c FROM reviews").fetchone()["c"]
        sessions_total = conn.execute("SELECT COUNT(*) AS c FROM sessions").fetchone()["c"]
        avg_rating = conn.execute(
            "SELECT AVG(self_rating) AS a FROM sessions WHERE self_rating IS NOT NULL"
        ).fetchone()["a"]

        by_topic: dict[str, int] = {t["id"]: 0 for t in TOPICS}
        for row in conn.execute("SELECT topic, COUNT(*) AS c FROM cards GROUP BY topic").fetchall():
            if row["topic"] in by_topic:
                by_topic[row["topic"]] = row["c"]

    return ProgressOut(
        cards_total=cards_total,
        cards_due=cards_due,
        cards_learned=cards_learned,
        reviews_total=reviews_total,
        sessions_total=sessions_total,
        average_self_rating=round(avg_rating, 2) if avg_rating is not None else None,
        by_topic=by_topic,
    )


@router.get("/topics")
async def topics() -> list[dict]:
    return TOPICS


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
