"""Themen-Definitionen für die Wissenswerkstatt.

Diese Liste wird der LLM als mögliche Themen mitgegeben
und im UI als Auswahl angezeigt.
"""
from __future__ import annotations

from typing import TypedDict


class TopicDef(TypedDict):
    id: str
    label: str
    description: str


TOPICS: list[TopicDef] = [
    {
        "id": "geschichte",
        "label": "Geschichte",
        "description": "Ereignisse, Epochen, Personen, Zusammenhänge — von Antike bis Zeitgeschichte.",
    },
    {
        "id": "geografie",
        "label": "Geografie",
        "description": "Länder, Städte, Klima, Ressourcen, geopolitische Lagen — mit Schwerpunkt Europa/Deutschland.",
    },
    {
        "id": "politik_gesellschaft",
        "label": "Politik & Gesellschaft",
        "description": "Staat, Verfassung, Institutionen, Wahlen, Gesellschaftsstruktur, Demokratie in D/EU.",
    },
    {
        "id": "wirtschaft_finanzen",
        "label": "Wirtschaft & Finanzen",
        "description": "Grundbegriffe der Wirtschaft, persönliche Finanzen, Inflation, Zinsen, Steuern, Aktien.",
    },
    {
        "id": "naturwissenschaften_technik",
        "label": "Naturwissenschaften & Technik",
        "description": "Physik, Chemie, Biologie, Technik — Konzepte und Alltagsanwendungen.",
    },
    {
        "id": "medien_statistik",
        "label": "Medien, Statistik & Argumentation",
        "description": "Quellenkritik, Statistik-Grundlagen, Manipulation erkennen, sauber argumentieren.",
    },
    {
        "id": "kultur_sprache",
        "label": "Kultur & Sprache",
        "description": "Literatur, Kunst, Musik, Sprachen — Epochen, Werke, Strömungen.",
    },
]


def topic_label(topic_id: str) -> str:
    for t in TOPICS:
        if t["id"] == topic_id:
            return t["label"]
    return topic_id


def topic_description(topic_id: str) -> str:
    for t in TOPICS:
        if t["id"] == topic_id:
            return t["description"]
    return ""
