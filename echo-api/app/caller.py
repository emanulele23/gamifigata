"""Telegram voice delivery via Pyrogram userbot.

Nota: le chiamate VoIP 1:1 classiche di Telegram non sono stabilmente
supportate dalle librerie open-source. Questo modulo:
1) invia la nota vocale dall'userbot (consegna affidabile);
2) se py-tgcalls è disponibile, prova a riprodurre l'audio in una voice chat
   sul target configurato (gruppo/canale o chat che lo supporta).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from app.config import Settings

logger = logging.getLogger("echo.caller")

_client = None
_calls = None
_started = False


def _imports():
    from pyrogram import Client

    try:
        from pytgcalls import PyTgCalls
        from pytgcalls.types import MediaStream
    except Exception:  # noqa: BLE001
        PyTgCalls = None
        MediaStream = None
    return Client, PyTgCalls, MediaStream


async def _ensure_started(settings: Settings):
    global _client, _calls, _started
    if _started:
        return _client, _calls

    if not settings.telegram_api_id or not settings.telegram_api_hash:
        raise RuntimeError(
            "TELEGRAM_API_ID e TELEGRAM_API_HASH richiesti per le chiamate"
        )

    Client, PyTgCalls, _MediaStream = _imports()
    session_path = Path(settings.telegram_session_path)
    session_path.parent.mkdir(parents=True, exist_ok=True)
    _client = Client(
        name=session_path.name,
        api_id=settings.telegram_api_id,
        api_hash=settings.telegram_api_hash,
        workdir=str(session_path.parent),
    )
    await _client.start()

    if PyTgCalls is not None:
        _calls = PyTgCalls(_client)
        await _calls.start()
    else:
        _calls = None
        logger.warning("py-tgcalls non disponibile: invio solo nota vocale")

    _started = True
    return _client, _calls


async def place_call(
    settings: Settings,
    audio_path: Path,
    *,
    target: Optional[str] = None,
) -> Dict[str, Any]:
    if not settings.enable_voice_calls:
        return {
            "ok": False,
            "skipped": True,
            "reason": "ENABLE_VOICE_CALLS=false",
        }

    dest = target or settings.telegram_call_target
    if not dest:
        raise RuntimeError("TELEGRAM_CALL_TARGET mancante")

    client, calls = await _ensure_started(settings)
    _, _, MediaStream = _imports()

    result: Dict[str, Any] = {
        "ok": True,
        "target": dest,
        "voice_note_sent": False,
        "voice_chat_played": False,
    }

    # Consegna affidabile: nota vocale dall'userbot
    await client.send_voice(dest, str(audio_path))
    result["voice_note_sent"] = True

    # Tentativo voice chat / riproduzione (best effort)
    if calls is not None and MediaStream is not None:
        try:
            await calls.play(dest, MediaStream(str(audio_path)))
            result["voice_chat_played"] = True
        except Exception as exc:  # noqa: BLE001
            logger.exception("Voice chat play failed")
            result["voice_chat_error"] = str(exc)

    return result


async def shutdown_caller() -> None:
    global _client, _calls, _started
    if not _started:
        return
    try:
        if _calls is not None:
            await _calls.stop()
    except Exception:  # noqa: BLE001
        logger.exception("Error stopping pytgcalls")
    try:
        if _client is not None:
            await _client.stop()
    except Exception:  # noqa: BLE001
        logger.exception("Error stopping pyrogram")
    _client = None
    _calls = None
    _started = False
