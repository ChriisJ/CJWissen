"""Pydantic-Modelle für die API."""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


# --- Topics -------------------------------------------------

Topic = Literal[
    "geschichte",
    "geografie",
    "politik_gesellschaft",
    "wirtschaft_finanzen",
    "naturwissenschaften_technik",
    "medien_statistik",
    "kultur_sprache",
]


# --- Sessions -----------------------------------------------

class SessionStart(BaseModel):
    topic: Optional[Topic] = Field(default=None, description="Optional Themenfokus")


class SessionEnd(BaseModel):
    self_rating: int = Field(ge=0, le=5, description="0..5, Antwortsicherheit")


class SessionOut(BaseModel):
    id: int
    started_at: str
    ended_at: Optional[str] = None
    topic: Optional[str] = None
    self_rating: Optional[int] = None


# --- Messages -----------------------------------------------

class ChatRequest(BaseModel):
    session_id: int
    message: str = Field(min_length=1, max_length=4000)


class ChatResponse(BaseModel):
    session_id: int
    reply: str
    evaluation: Optional[str] = None        # korrekt | teilweise | unklar | falsch | nicht_beantwortet
    new_cards: list["CardOut"] = Field(default_factory=list)


# --- Cards --------------------------------------------------

class CardOut(BaseModel):
    id: int
    front: str
    back: str
    topic: str
    ease: float
    interval_days: int
    repetitions: int
    due_at: str


class ReviewIn(BaseModel):
    quality: int = Field(ge=0, le=5, description="0..5 SM-2 Qualität")


class ReviewOut(BaseModel):
    card_id: int
    next_due_at: str
    next_interval_days: int
    ease: float


# --- Progress -----------------------------------------------

class ProgressOut(BaseModel):
    cards_total: int
    cards_due: int
    cards_learned: int          # repetitions >= 1
    reviews_total: int
    sessions_total: int
    average_self_rating: Optional[float] = None
    by_topic: dict[str, int] = Field(default_factory=dict)


ChatResponse.model_rebuild()
