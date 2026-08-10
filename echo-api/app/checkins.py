"""Check-in slots: 2-3 chiamate al giorno con domande mirate."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

SLOTS: Dict[str, Dict[str, Any]] = {
    "morning": {
        "label": "Mattina",
        "hour_range": (5, 11),
        "focus": ["umore", "sonno", "energia", "intenzione del giorno"],
        "question_hint": (
            "Chiedi come ha dormito e come si sente stamattina. "
            "Una sola domanda calda e breve."
        ),
    },
    "lunch": {
        "label": "Pranzo",
        "hour_range": (11, 17),
        "focus": ["pasto", "attività fisica finora", "umore"],
        "question_hint": (
            "Chiedi cosa ha mangiato e se si è mosso. "
            "Se hai dati Apple Salute, incrociali gentilmente (es. 'vedo X passi...'). "
            "Una sola domanda."
        ),
    },
    "evening": {
        "label": "Sera",
        "hour_range": (17, 24),
        "focus": ["pasto", "umore", "attività", "obiettivi", "micro-vittorie"],
        "question_hint": (
            "Fai un check-in serale: umore, cibo, movimento, un micro-obiettivo. "
            "Celebra una piccola vittoria se c'è. Una sola domanda."
        ),
    },
}


def slot_for_time(hhmm: str) -> str:
    hour = int(hhmm.split(":")[0])
    for name, cfg in SLOTS.items():
        lo, hi = cfg["hour_range"]
        if lo <= hour < hi:
            return name
    return "evening"


def slot_for_now(tz: str) -> str:
    now = datetime.now(ZoneInfo(tz))
    return slot_for_time(now.strftime("%H:%M"))


def slot_label(slot: str) -> str:
    return SLOTS.get(slot, SLOTS["evening"])["label"]


def checkin_times_from_profile(profile: Dict[str, Any]) -> List[str]:
    times = profile.get("checkin_times") or ["09:00", "14:00", "21:00"]
    return [str(t).strip() for t in times if str(t).strip()]


def build_checkin_prompt_context(
    *,
    slot: str,
    user_name: str,
    diary_context: str,
    goals_context: str,
    apple_context: str,
    streak_context: str,
    hhmm: str,
) -> str:
    cfg = SLOTS.get(slot, SLOTS["evening"])
    name = user_name or "amico"
    return f"""Check-in programmato ({cfg['label']}, ore {hhmm}).
Stai chiamando {name} — apri con tono caldo da amico, non da questionario.

Focus di questo check-in: {', '.join(cfg['focus'])}.
Istruzione: {cfg['question_hint']}

Diario recente:
{diary_context}

Obiettivi attivi:
{goals_context}

Streak:
{streak_context}

Apple Salute oggi:
{apple_context}

Scrivi SOLO il messaggio di apertura (max 2 frasi, una domanda).
Non includere <data> in questo messaggio.
"""
