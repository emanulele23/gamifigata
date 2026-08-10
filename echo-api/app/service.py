from __future__ import annotations

import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

from app import db
from app.checkins import (
    build_checkin_prompt_context,
    slot_for_time,
    slot_label,
)
from app.config import Settings
from app.deepseek import chat as deepseek_chat
from app.fish import speech_to_text, text_to_speech
from app.goals_engine import streak_celebration, update_streaks_from_log
from app.parsing import normalize_log_payload, split_reply_and_data
from app.prompt import build_system_prompt
from app.telegram_bot import send_message, send_voice

logger = logging.getLogger("echo.service")


def _slot_label(settings: Settings) -> str:
    now = datetime.now(ZoneInfo(settings.tz))
    return now.strftime("%H:%M")


def effective_chat_id(settings: Settings, chat_id: Optional[str] = None) -> Optional[str]:
    if chat_id:
        return str(chat_id)
    return db.resolve_chat_id(settings.database_path, settings.telegram_chat_id)


def _system_prompt(settings: Settings) -> str:
    profile = db.get_profile(settings.database_path)
    return build_system_prompt(user_name=profile.get("name") or "")


def _full_context(settings: Settings) -> Dict[str, str]:
    return {
        "diary": db.context_summary(settings.database_path, limit=5),
        "goals": db.goals_summary(settings.database_path),
        "streaks": db.goals_summary(settings.database_path),
        "apple": db.apple_health_summary(settings.database_path),
    }


async def build_checkin(
    settings: Settings,
    *,
    hhmm: Optional[str] = None,
) -> Dict[str, Any]:
    profile = db.get_profile(settings.database_path)
    time_str = hhmm or _slot_label(settings)
    slot = slot_for_time(time_str)
    ctx = _full_context(settings)

    prompt = build_checkin_prompt_context(
        slot=slot,
        user_name=profile.get("name") or "",
        diary_context=ctx["diary"],
        goals_context=ctx["goals"],
        apple_context=ctx["apple"],
        streak_context=ctx["streaks"],
        hhmm=time_str,
    )
    reply = await deepseek_chat(
        settings,
        prompt,
        system_prompt=_system_prompt(settings),
    )
    spoken, _ = split_reply_and_data(reply)

    audio_path = (
        Path(settings.tmp_audio_dir)
        / f"checkin-{slot}-{uuid.uuid4().hex}.{settings.fish_tts_format}"
    )
    await text_to_speech(settings, spoken, audio_path)

    return {
        "text": spoken,
        "audio_path": str(audio_path),
        "slot": slot,
        "slot_label": slot_label(slot),
        "time": time_str,
        "context": ctx,
    }


async def handle_user_text(
    settings: Settings,
    text: str,
    *,
    source: str = "chat",
    chat_id: Optional[str] = None,
    checkin_slot: Optional[str] = None,
) -> Dict[str, Any]:
    target_chat = effective_chat_id(settings, chat_id)
    if target_chat and not settings.telegram_chat_id:
        db.remember_chat_id(settings.database_path, target_chat)

    profile = db.get_profile(settings.database_path)
    ctx = _full_context(settings)
    history = db.recent_messages(
        settings.database_path,
        limit=8,
        chat_id=target_chat,
    )
    user_msg = (
        f"Contesto diario:\n{ctx['diary']}\n\n"
        f"Obiettivi e streak:\n{ctx['goals']}\n\n"
        f"Apple Salute oggi:\n{ctx['apple']}\n\n"
        f"Messaggio utente:\n{text}"
    )
    reply = await deepseek_chat(
        settings,
        user_msg,
        system_prompt=_system_prompt(settings),
        history=history,
    )
    spoken, data = split_reply_and_data(reply)

    db.add_message(settings.database_path, "user", text, chat_id=target_chat)
    db.add_message(settings.database_path, "assistant", spoken, chat_id=target_chat)

    saved = None
    streak_updates: list = []
    if data:
        payload = normalize_log_payload(data)
        if payload:
            saved = db.insert_log(
                settings.database_path,
                raw_text=text,
                source=source,
                checkin_slot=checkin_slot,
                **payload,
            )
            streak_updates = update_streaks_from_log(settings.database_path, payload)

    celebration = streak_celebration(settings.database_path)
    if celebration and spoken and celebration not in spoken:
        spoken = f"{spoken} {celebration}"

    audio_path = (
        Path(settings.tmp_audio_dir)
        / f"reply-{uuid.uuid4().hex}.{settings.fish_tts_format}"
    )
    await text_to_speech(settings, spoken, audio_path)

    return {
        "text": spoken,
        "raw_reply": reply,
        "data": data,
        "saved": saved,
        "streak_updates": streak_updates,
        "audio_path": str(audio_path),
        "chat_id": target_chat,
        "user_name": profile.get("name"),
    }


async def handle_user_audio(
    settings: Settings,
    audio_bytes: bytes,
    *,
    filename: str = "voice.ogg",
    source: str = "voice",
    chat_id: Optional[str] = None,
) -> Dict[str, Any]:
    transcript = await speech_to_text(
        settings,
        audio_bytes,
        language="it",
        filename=filename,
    )
    result = await handle_user_text(
        settings,
        transcript,
        source=source,
        chat_id=chat_id,
    )
    result["transcript"] = transcript
    return result


async def deliver_to_telegram(
    settings: Settings,
    *,
    text: str,
    audio_path: Optional[str] = None,
    chat_id: Optional[str] = None,
) -> Dict[str, Any]:
    target = effective_chat_id(settings, chat_id)
    if not target:
        raise RuntimeError(
            "TELEGRAM_CHAT_ID mancante. Scrivi al bot o completa l'onboarding."
        )

    out: Dict[str, Any] = {"message": None, "voice": None, "chat_id": target}
    if audio_path and Path(audio_path).exists():
        caption = text if text and len(text) <= 900 else None
        out["voice"] = await send_voice(
            settings,
            Path(audio_path),
            chat_id=target,
            caption=caption,
        )
        if text and caption is None:
            out["message"] = await send_message(settings, text, chat_id=target)
    else:
        out["message"] = await send_message(settings, text, chat_id=target)
    return out


async def run_checkin_pipeline(
    settings: Settings,
    *,
    send: bool = True,
    try_call: bool = False,
    hhmm: Optional[str] = None,
) -> Dict[str, Any]:
    checkin = await build_checkin(settings, hhmm=hhmm)
    delivery = None
    call_result = None

    profile = db.get_profile(settings.database_path)
    should_call = try_call or (
        settings.enable_voice_calls
        and settings.prefer_calls_on_checkin
        and profile.get("prefer_calls", True)
    )

    if should_call and settings.enable_voice_calls:
        from app.caller import place_call

        try:
            call_result = await place_call(
                settings,
                Path(checkin["audio_path"]),
            )
            if call_result.get("voice_note_sent") or call_result.get("voice_chat_played"):
                delivery = {"call": call_result, "mode": "call"}
        except Exception:  # noqa: BLE001
            logger.exception("Call failed, fallback to voice message")
            call_result = {"ok": False, "error": "call_failed"}

    if send and delivery is None:
        delivery = await deliver_to_telegram(
            settings,
            text=checkin["text"],
            audio_path=checkin["audio_path"],
        )
        delivery["mode"] = "telegram_voice"

    return {
        "checkin": checkin,
        "delivery": delivery,
        "call": call_result,
    }


# Alias retrocompatibile
async def run_reminder_pipeline(
    settings: Settings,
    *,
    send: bool = True,
    try_call: bool = False,
) -> Dict[str, Any]:
    return await run_checkin_pipeline(settings, send=send, try_call=try_call)


async def build_reminder(settings: Settings) -> Dict[str, Any]:
    checkin = await build_checkin(settings)
    return {
        "text": checkin["text"],
        "audio_path": checkin["audio_path"],
        "context": checkin.get("context", {}).get("diary", ""),
    }
