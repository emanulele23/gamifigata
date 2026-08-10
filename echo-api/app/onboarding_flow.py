"""Onboarding semplice via Telegram — niente comandi tecnici."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional, Tuple

from app import db
from app.config import Settings

STEPS = ("welcome", "name", "goals_story", "goals_confirm", "done")


def _step(db_path: str) -> str:
    return db.get_meta(db_path, "onboarding_step") or "welcome"


def _set_step(db_path: str, step: str) -> None:
    db.set_meta(db_path, "onboarding_step", step)


def needs_onboarding(db_path: str) -> bool:
    if db.is_onboarding_complete(db_path):
        return False
    return _step(db_path) != "done"


def start_onboarding(db_path: str) -> None:
    if not db.get_meta(db_path, "onboarding_step"):
        _set_step(db_path, "welcome")


async def handle_onboarding_message(
    settings: Settings,
    text: str,
    *,
    chat_id: str,
) -> Tuple[bool, str]:
    """Ritorna (handled, reply_text). Se handled=True, non passare al LLM normale."""
    db_path = settings.database_path

    if db.is_onboarding_complete(db_path):
        if (text or "").strip().lower() in ("/start", "/inizia", "start"):
            return True, (
                f"Ciao {db.get_profile(db_path).get('name') or ''}! "
                "Sei già configurato. Scrivimi quando vuoi o aspetta il prossimo check-in.\n"
                "Comandi: /stato /obiettivi"
            ).replace("  ", " ")
        return False, ""

    start_onboarding(db_path)
    step = _step(db_path)
    msg = (text or "").strip()
    lower = msg.lower()

    if lower in ("/start", "/inizia", "ciao", "start"):
        _set_step(db_path, "name")
        return True, (
            "Ciao! Sono Echo, il tuo assistente personale.\n\n"
            "Ti scriverò 2-3 volte al giorno con una domanda veloce "
            "(umore, cibo, movimento). Tu rispondi a voce o a testo — "
            "io tengo traccia di tutto.\n\n"
            "Per iniziare: come ti chiami?"
        )

    if lower in ("/salta", "/skip") and step in ("goals_story", "goals_confirm"):
        _finish(db_path, chat_id)
        return True, _done_message(db_path)

    if step == "welcome":
        _set_step(db_path, "name")
        return True, "Benvenuto! Come ti chiami?"

    if step == "name":
        if len(msg) < 2:
            return True, "Scrivimi il tuo nome, anche solo il soprannome 🙂"
        db.save_profile(db_path, name=msg.strip())
        db.remember_chat_id(db_path, chat_id)
        _set_step(db_path, "goals_story")
        return True, (
            f"Piacere, {msg.strip()}!\n\n"
            "Ora raccontami in poche righe cosa vorresti migliorare "
            "(salute, energia, abitudini, sport…). "
            "Ti aiuto a definire piccoli obiettivi."
        )

    if step == "goals_story":
        db.set_meta(db_path, "onboarding_story", msg)
        _set_step(db_path, "goals_confirm")
        suggestions = await _suggest_goals(settings, msg)
        if suggestions:
            db.set_meta(db_path, "onboarding_goals_json", json.dumps(suggestions, ensure_ascii=False))
            lines = "\n".join(f"• {g['title']}" for g in suggestions)
            return True, (
                "Ecco cosa ti propongo:\n\n"
                f"{lines}\n\n"
                "Ti va bene? Rispondi «sì» per confermare, "
                "oppure scrivimi i tuoi obiettivi a modo tuo."
            )
        return True, (
            "Scrivimi 1-3 obiettivi semplici, uno per riga "
            "(es. «Camminare 20 min», «Dormire prima»)."
        )

    if step == "goals_confirm":
        if lower in ("sì", "si", "s", "yes", "ok", "va bene", "perfetto"):
            raw = db.get_meta(db_path, "onboarding_goals_json")
            if raw:
                for g in json.loads(raw):
                    db.add_goal(
                        db_path,
                        title=g.get("title", "Obiettivo"),
                        description=g.get("description", ""),
                        category=g.get("category", "crescita"),
                        target_value=g.get("target_value"),
                        unit=g.get("unit", ""),
                    )
        else:
            for line in msg.splitlines():
                line = line.strip().lstrip("•-* ").strip()
                if len(line) >= 3:
                    db.add_goal(db_path, title=line[:80], description="")

        _finish(db_path, chat_id)
        return True, _done_message(db_path)

    return False, ""


def _finish(db_path: str, chat_id: str) -> None:
    db.remember_chat_id(db_path, chat_id)
    db.save_profile(
        db_path,
        onboarding_complete=True,
        checkin_times=["09:00", "14:00", "21:00"],
        prefer_calls=False,
    )
    _set_step(db_path, "done")


def _done_message(db_path: str) -> str:
    profile = db.get_profile(db_path)
    name = profile.get("name") or "amico"
    goals = db.list_goals(db_path)
    gtxt = "\n".join(f"• {g['title']}" for g in goals[:5]) or "• (nessuno ancora)"
    return (
        f"Perfetto, {name}! Sei pronto.\n\n"
        f"I tuoi obiettivi:\n{gtxt}\n\n"
        "Ti contatterò verso le 9, 14 e 21 con una domanda veloce. "
        "Rispondi come preferisci — anche con un vocale.\n\n"
        "Comandi utili:\n"
        "• /stato — riepilogo\n"
        "• /obiettivi — i tuoi obiettivi e streak"
    )


async def _suggest_goals(settings: Settings, story: str) -> list[dict]:
    if not settings.deepseek_api_key:
        return []
    try:
        from app.deepseek import chat as deepseek_chat
        from app.prompt import GOAL_COACH_PROMPT
        import re

        raw = await deepseek_chat(settings, story, system_prompt=GOAL_COACH_PROMPT)
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if not match:
            return []
        goals = json.loads(match.group(0))
        return goals if isinstance(goals, list) else []
    except Exception:  # noqa: BLE001
        return []


def status_message(db_path: str) -> str:
    profile = db.get_profile(db_path)
    name = profile.get("name") or "amico"
    streaks = db.get_streaks(db_path)
    apple = db.apple_health_summary(db_path)
    lines = [f"Ciao {name}!"]
    if streaks:
        lines.append("\nStreak:")
        for s in streaks:
            lines.append(
                f"• {s['title']}: {s.get('current_streak') or 0} giorni"
            )
    lines.append(f"\nOggi (Salute): {apple}")
    return "\n".join(lines)
