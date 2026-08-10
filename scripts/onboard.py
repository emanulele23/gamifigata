#!/usr/bin/env python3
"""Wizard di configurazione iniziale Echo — esegui dopo git clone.

  python3 scripts/onboard.py

Crea/aggiorna .env, profilo utente, obiettivi e streak nel database SQLite.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "echo-api"))

from app import db  # noqa: E402
from app.deepseek import chat as deepseek_chat  # noqa: E402
from app.prompt import GOAL_COACH_PROMPT  # noqa: E402


def ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    val = input(f"{prompt}{suffix}: ").strip()
    return val or default


def ask_yes(prompt: str, default: bool = True) -> bool:
    d = "s" if default else "n"
    val = ask(f"{prompt} (s/n)", d).lower()
    return val in ("s", "si", "sì", "y", "yes", "1")


def load_env(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists():
        return data
    for line in path.read_text().splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        data[k.strip()] = v.strip()
    return data


def save_env(path: Path, data: dict[str, str]) -> None:
    lines = [
        "# Generato da scripts/onboard.py — non committare",
        "",
        f"TELEGRAM_BOT_TOKEN={data.get('TELEGRAM_BOT_TOKEN', '')}",
        f"TELEGRAM_CHAT_ID={data.get('TELEGRAM_CHAT_ID', '')}",
        "",
        f"DEEPSEEK_API_KEY={data.get('DEEPSEEK_API_KEY', '')}",
        f"DEEPSEEK_BASE_URL={data.get('DEEPSEEK_BASE_URL', 'https://api.deepseek.com')}",
        f"DEEPSEEK_MODEL={data.get('DEEPSEEK_MODEL', 'deepseek-chat')}",
        "",
        f"FISH_API_KEY={data.get('FISH_API_KEY', '')}",
        f"FISH_REFERENCE_ID={data.get('FISH_REFERENCE_ID', '')}",
        f"FISH_TTS_MODEL={data.get('FISH_TTS_MODEL', 's2.1-pro')}",
        f"FISH_TTS_FORMAT={data.get('FISH_TTS_FORMAT', 'ogg')}",
        "",
        f"TZ={data.get('TZ', 'Europe/Rome')}",
        f"REMINDER_TIMES={data.get('REMINDER_TIMES', '09:00,14:00,21:00')}",
        f"ENABLE_INTERNAL_REMINDERS={data.get('ENABLE_INTERNAL_REMINDERS', 'true')}",
        f"STANDALONE_BOT={data.get('STANDALONE_BOT', 'true')}",
        f"ENABLE_VOICE_CALLS={data.get('ENABLE_VOICE_CALLS', 'true')}",
        f"PREFER_CALLS_ON_CHECKIN={data.get('PREFER_CALLS_ON_CHECKIN', 'true')}",
        "",
        f"TELEGRAM_API_ID={data.get('TELEGRAM_API_ID', '')}",
        f"TELEGRAM_API_HASH={data.get('TELEGRAM_API_HASH', '')}",
        f"TELEGRAM_CALL_TARGET={data.get('TELEGRAM_CALL_TARGET', '')}",
        f"TELEGRAM_SESSION_PATH={data.get('TELEGRAM_SESSION_PATH', '/app/data/echo_userbot')}",
        "",
        f"APPLE_HEALTH_SECRET={data.get('APPLE_HEALTH_SECRET', '')}",
        f"ECHO_PUBLIC_URL={data.get('ECHO_PUBLIC_URL', 'http://localhost:5000')}",
        "",
        f"N8N_HOST={data.get('N8N_HOST', '0.0.0.0')}",
        f"N8N_PORT={data.get('N8N_PORT', '5678')}",
        f"N8N_PROTOCOL={data.get('N8N_PROTOCOL', 'http')}",
        f"GENERIC_TIMEZONE={data.get('GENERIC_TIMEZONE', data.get('TZ', 'Europe/Rome'))}",
        "",
    ]
    path.write_text("\n".join(lines))


async def suggest_goals(settings_like, user_story: str) -> list[dict]:
    from app.config import Settings

    settings = Settings(
        deepseek_api_key=settings_like["DEEPSEEK_API_KEY"],
        deepseek_base_url=settings_like.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        deepseek_model=settings_like.get("DEEPSEEK_MODEL", "deepseek-chat"),
    )
    raw = await deepseek_chat(
        settings,
        user_story,
        system_prompt=GOAL_COACH_PROMPT,
    )
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not match:
        return []
    try:
        goals = json.loads(match.group(0))
        return goals if isinstance(goals, list) else []
    except json.JSONDecodeError:
        return []


def main() -> None:
    print("\n=== Echo — Configurazione iniziale ===\n")
    env_path = ROOT / ".env"
    env = load_env(env_path)
    db_path = str(ROOT / "echo-api" / "data" / "echo.db")
    db.init_db(db_path)

    name = ask("Come ti chiami?", env.get("USER_NAME", ""))
    tz = ask("Fuso orario", env.get("TZ", "Europe/Rome"))

    print("\n--- Telegram ---")
    print("Crea un bot con @BotFather e incolla il token.")
    env["TELEGRAM_BOT_TOKEN"] = ask("TELEGRAM_BOT_TOKEN", env.get("TELEGRAM_BOT_TOKEN", ""))
    env["TELEGRAM_CHAT_ID"] = ask(
        "TELEGRAM_CHAT_ID (opzionale, si auto-rileva al primo messaggio)",
        env.get("TELEGRAM_CHAT_ID", ""),
    )

    print("\n--- API Keys ---")
    env["DEEPSEEK_API_KEY"] = ask("DEEPSEEK_API_KEY", env.get("DEEPSEEK_API_KEY", ""))
    env["FISH_API_KEY"] = ask("FISH_API_KEY", env.get("FISH_API_KEY", ""))
    env["FISH_REFERENCE_ID"] = ask(
        "FISH_REFERENCE_ID (voce clonata su fish.audio)",
        env.get("FISH_REFERENCE_ID", ""),
    )

    print("\n--- Check-in vocali (2-3 volte al giorno) ---")
    default_times = env.get("REMINDER_TIMES", "09:00,14:00,21:00")
    times = ask(
        "Orari check-in (HH:MM separati da virgola)",
        default_times,
    )
    env["REMINDER_TIMES"] = times
    checkin_list = [t.strip() for t in times.split(",") if t.strip()]

    prefer_calls = ask_yes(
        "Vuoi che Echo ti contatti con chiamata/nota vocale agli check-in?",
        True,
    )
    env["ENABLE_VOICE_CALLS"] = "true" if prefer_calls else "false"
    env["PREFER_CALLS_ON_CHECKIN"] = "true" if prefer_calls else "false"
    env["STANDALONE_BOT"] = "true"
    env["ENABLE_INTERNAL_REMINDERS"] = "true"
    env["TZ"] = tz

    if prefer_calls:
        print("\n--- Chiamate Telegram (userbot) ---")
        print("Serve un secondo account Telegram + app su https://my.telegram.org")
        env["TELEGRAM_API_ID"] = ask("TELEGRAM_API_ID", env.get("TELEGRAM_API_ID", ""))
        env["TELEGRAM_API_HASH"] = ask("TELEGRAM_API_HASH", env.get("TELEGRAM_API_HASH", ""))
        env["TELEGRAM_CALL_TARGET"] = ask(
            "Username o ID Telegram da chiamare (es. @tuonome)",
            env.get("TELEGRAM_CALL_TARGET", ""),
        )

    print("\n--- Chi sei e cosa vuoi migliorare ---")
    print("Scrivi liberamente: lavoro, salute, abitudini, obiettivi...")
    story = ask("Raccontami di te")
    goals: list[dict] = []
    if story and env.get("DEEPSEEK_API_KEY"):
        print("\nEcho sta preparando micro-obiettivi su misura...")
        try:
            goals = asyncio.run(suggest_goals(env, story))
        except Exception as exc:  # noqa: BLE001
            print(f"Non sono riuscito a generare obiettivi automatici: {exc}")

    if goals:
        print("\nObiettivi proposti:")
        for i, g in enumerate(goals, 1):
            print(f"  {i}. {g.get('title')} — {g.get('description', '')}")
        if ask_yes("Accetti questi obiettivi?", True):
            for g in goals:
                db.add_goal(
                    db_path,
                    title=str(g.get("title", "Obiettivo")),
                    description=str(g.get("description", "")),
                    category=str(g.get("category", "crescita")),
                    target_value=g.get("target_value"),
                    unit=str(g.get("unit", "")),
                )
    else:
        print("\nAggiungi almeno un obiettivo manualmente.")
        while ask_yes("Aggiungere un obiettivo?", True):
            title = ask("Titolo obiettivo")
            if title:
                db.add_goal(db_path, title=title, description=ask("Descrizione breve"))

    print("\n--- Apple Salute (iPhone) ---")
    apple = ask_yes(
        "Vuoi collegare Apple Salute? (iPhone invia passi/esercizio via Shortcut)",
        False,
    )
    apple_secret = secrets.token_urlsafe(24)
    env["APPLE_HEALTH_SECRET"] = apple_secret if apple else env.get("APPLE_HEALTH_SECRET", "")
    public_url = ask(
        "URL pubblico della Raspi (per Shortcut iPhone)",
        env.get("ECHO_PUBLIC_URL", "http://IP_RASPI:5000"),
    )
    env["ECHO_PUBLIC_URL"] = public_url

    db.save_profile(
        db_path,
        name=name,
        timezone=tz,
        checkin_times=checkin_list,
        prefer_calls=prefer_calls,
        apple_health_enabled=apple,
        onboarding_complete=True,
    )

    save_env(env_path, env)

    print("\n=== Configurazione completata ===")
    print(f"  .env salvato in {env_path}")
    print(f"  Profilo e obiettivi in {db_path}")
    if apple:
        print("\nApple Salute:")
        print(f"  Secret: {apple_secret}")
        print(f"  Leggi: docs/apple-health-shortcut.md")
    if prefer_calls and env.get("TELEGRAM_API_ID"):
        print("\nProssimo passo chiamate:")
        print("  python3 scripts/login_userbot.py")
    print("\nAvvia Echo:")
    print("  ./scripts/setup.sh")
    print("  # oppure: make up")


if __name__ == "__main__":
    main()
