#!/usr/bin/env python3
"""Login interattivo Pyrogram per le chiamate vocali (Fase 5).

Esegui UNA VOLTA sulla Raspi (fuori Docker o con volume montato):

  python3 -m venv .venv
  source .venv/bin/activate
  pip install pyrogram tgcrypto
  python scripts/login_userbot.py

Poi assicurati che il file di sessione sia in echo-api/data/
e che ENABLE_VOICE_CALLS=true nel .env.
"""

from __future__ import annotations

import os
from pathlib import Path

from pyrogram import Client


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    env_path = root / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

    api_id = os.environ.get("TELEGRAM_API_ID")
    api_hash = os.environ.get("TELEGRAM_API_HASH")
    session = os.environ.get("TELEGRAM_SESSION_PATH", str(root / "echo-api/data/echo_userbot"))

    if not api_id or not api_hash:
        raise SystemExit("Imposta TELEGRAM_API_ID e TELEGRAM_API_HASH nel .env")

    session_path = Path(session)
    session_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"Sessione: {session_path}")
    print("Usa il NUMERO del secondo account (userbot), non il bot.")

    app = Client(
        name=session_path.name,
        api_id=int(api_id),
        api_hash=api_hash,
        workdir=str(session_path.parent),
    )
    with app:
        me = app.get_me()
        print(f"Login OK: {me.first_name} (@{me.username}) id={me.id}")


if __name__ == "__main__":
    main()
