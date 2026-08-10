from __future__ import annotations

import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

from app import db
from app.config import Settings
from app.deepseek import chat as deepseek_chat
from app.fish import speech_to_text, text_to_speech
from app.parsing import normalize_log_payload, split_reply_and_data
from app.prompt import REMINDER_USER_TEMPLATE
from app.telegram_bot import send_message, send_voice

logger = logging.getLogger("echo.service")


def _slot_label(settings: Settings) -> str:
    now = datetime.now(ZoneInfo(settings.tz))
    return now.strftime("%H:%M")


async def build_reminder(settings: Settings) -> Dict[str, Any]:
    context = db.context_summary(settings.database_path, limit=5)
    prompt = REMINDER_USER_TEMPLATE.format(
        context=context,
        slot=_slot_label(settings),
    )
    reply = await deepseek_chat(settings, prompt)
    spoken, _ = split_reply_and_data(reply)

    audio_path = Path(settings.tmp_audio_dir) / f"reminder-{uuid.uuid4().hex}.{settings.fish_tts_format}"
    await text_to_speech(settings, spoken, audio_path)

    return {
        "text": spoken,
        "audio_path": str(audio_path),
        "context": context,
    }


async def handle_user_text(
    settings: Settings,
    text: str,
    *,
    source: str = "chat",
) -> Dict[str, Any]:
    context = db.context_summary(settings.database_path, limit=5)
    user_msg = (
        f"Contesto recente:\n{context}\n\n"
        f"Messaggio utente:\n{text}"
    )
    reply = await deepseek_chat(settings, user_msg)
    spoken, data = split_reply_and_data(reply)

    saved = None
    if data:
        payload = normalize_log_payload(data)
        if payload:
            saved = db.insert_log(
                settings.database_path,
                raw_text=text,
                source=source,
                **payload,
            )

    audio_path = Path(settings.tmp_audio_dir) / f"reply-{uuid.uuid4().hex}.{settings.fish_tts_format}"
    await text_to_speech(settings, spoken, audio_path)

    return {
        "text": spoken,
        "raw_reply": reply,
        "data": data,
        "saved": saved,
        "audio_path": str(audio_path),
    }


async def handle_user_audio(
    settings: Settings,
    audio_bytes: bytes,
    *,
    filename: str = "voice.ogg",
    source: str = "voice",
) -> Dict[str, Any]:
    transcript = await speech_to_text(
        settings,
        audio_bytes,
        language="it",
        filename=filename,
    )
    result = await handle_user_text(settings, transcript, source=source)
    result["transcript"] = transcript
    return result


async def deliver_to_telegram(
    settings: Settings,
    *,
    text: str,
    audio_path: Optional[str] = None,
    chat_id: Optional[str] = None,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {"message": None, "voice": None}
    if audio_path and Path(audio_path).exists():
        caption = text if text and len(text) <= 900 else None
        out["voice"] = await send_voice(
            settings,
            Path(audio_path),
            chat_id=chat_id,
            caption=caption,
        )
        if text and caption is None:
            out["message"] = await send_message(settings, text, chat_id=chat_id)
    else:
        out["message"] = await send_message(settings, text, chat_id=chat_id)
    return out


async def run_reminder_pipeline(
    settings: Settings,
    *,
    send: bool = True,
    try_call: bool = False,
) -> Dict[str, Any]:
    reminder = await build_reminder(settings)
    delivery = None
    call_result = None

    if send:
        delivery = await deliver_to_telegram(
            settings,
            text=reminder["text"],
            audio_path=reminder["audio_path"],
        )

    if try_call and settings.enable_voice_calls:
        from app.caller import place_call

        call_result = await place_call(
            settings,
            Path(reminder["audio_path"]),
        )

    return {
        "reminder": reminder,
        "delivery": delivery,
        "call": call_result,
    }
