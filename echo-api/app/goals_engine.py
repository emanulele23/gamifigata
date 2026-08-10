"""Gamification: streak e progressi obiettivi."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from app import db


def match_goals_from_habits(
    db_path: str,
    habits: Any,
) -> List[int]:
    if not habits:
        return []
    if isinstance(habits, str):
        habits = [habits]
    titles = [str(h).lower() for h in habits]
    matched: List[int] = []
    for goal in db.list_goals(db_path):
        title = goal["title"].lower()
        for habit in titles:
            if title in habit or habit in title or _fuzzy_match(title, habit):
                matched.append(goal["id"])
                break
    return matched


def _fuzzy_match(a: str, b: str) -> bool:
    tokens_a = set(re.findall(r"\w+", a))
    tokens_b = set(re.findall(r"\w+", b))
    if not tokens_a or not tokens_b:
        return False
    return len(tokens_a & tokens_b) >= 1


def update_streaks_from_log(
    db_path: str,
    payload: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Aggiorna streak quando l'utente completa abitudini o attività fisica."""
    updated: List[Dict[str, Any]] = []
    habits = payload.get("habits_done") or []
    goal_ids = match_goals_from_habits(db_path, habits)

    if payload.get("attivita_fisica"):
        for goal in db.list_goals(db_path):
            cat = (goal.get("category") or "").lower()
            title = goal["title"].lower()
            if cat in ("fitness", "salute", "movimento") or any(
                w in title for w in ("sport", "corsa", "passi", "movimento", "allenamento")
            ):
                if goal["id"] not in goal_ids:
                    goal_ids.append(goal["id"])

    for gid in goal_ids:
        updated.append(db.record_goal_progress(db_path, gid, done=True))
    return updated


def streak_celebration(db_path: str) -> Optional[str]:
    streaks = db.get_streaks(db_path)
    hot = [s for s in streaks if (s.get("current_streak") or 0) >= 3]
    if not hot:
        return None
    best = max(hot, key=lambda s: s.get("current_streak") or 0)
    return (
        f"Streak {best['current_streak']} giorni su «{best['title']}» — "
        f"record personale {best.get('best_streak') or 0}."
    )
