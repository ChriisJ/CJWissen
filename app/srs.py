"""SM-2 Spaced-Repetition-Algorithmus.

Standardformel nach Piotr Wozniak (1990). Wird für jede
Karteikarte angewendet, wenn der Nutzer die Qualität
bewertet (0..5).

Qualität:
  0  komplett falsch / Blackout
  1  falsch, aber die richtige Antwort kam einem in den Sinn
  2  falsch, aber leicht zu merken
  3  korrekt mit ernster Schwierigkeit
  4  korrekt nach kurzer Überlegung
  5  perfekte, prompte Antwort
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Tuple


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sm2_update(
    *,
    quality: int,
    repetitions: int,
    ease: float,
    interval_days: int,
) -> Tuple[int, float, int, str]:
    """Berechnet neue SM-2-Werte.

    Returns: (new_repetitions, new_ease, new_interval_days, new_due_at_iso)
    """
    q = max(0, min(5, int(quality)))
    e = float(ease)
    r = int(repetitions)
    i = int(interval_days)

    if q < 3:
        # Antwort war zu schlecht — von vorne anfangen
        r = 0
        i = 1
    else:
        if r == 0:
            i = 1
        elif r == 1:
            i = 6
        else:
            i = max(1, round(i * e))
        r += 1

    # EF-Update (immer)
    e = e + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
    if e < 1.3:
        e = 1.3

    due = datetime.now(timezone.utc) + timedelta(days=i)
    return r, round(e, 4), i, due.isoformat(timespec="seconds")


def new_card_due_iso() -> str:
    """Start-Due für eine frisch erstellte Karte: sofort fällig."""
    return _now_iso()
