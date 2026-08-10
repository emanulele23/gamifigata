from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from zoneinfo import ZoneInfo

from app import db
from app.caller import place_call, shutdown_caller
from app.config import get_settings
from app.fish import speech_to_text, text_to_speech
from app.parsing import normalize_log_payload
from app.service import (
    deliver_to_telegram,
    effective_chat_id,
    handle_user_audio,
    handle_user_text,
    run_reminder_pipeline,
)
from app.telegram_bot import download_file, get_updates

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("echo")


class LogIn(BaseModel):
    pasto: Optional[str] = None
    mood_score: Optional[int] = Field(default=None, ge=1, le=10)
    habits_done: Optional[Any] = None
    note_salute: Optional[str] = None
    raw_text: Optional[str] = None
    source: str = "api"
    data_ora: Optional[str] = None


class ChatIn(BaseModel):
    text: str
    send: bool = False
    chat_id: Optional[str] = None
    source: str = "chat"


class RemindIn(BaseModel):
    send: bool = True
    try_call: bool = False


class TTSIn(BaseModel):
    text: str


class CallIn(BaseModel):
    audio_path: Optional[str] = None
    text: Optional[str] = None
    target: Optional[str] = None


class TelegramFileIn(BaseModel):
    file_id: str
    send: bool = True
    chat_id: Optional[str] = None


scheduler: Optional[AsyncIOScheduler] = None
_poll_task: Optional[asyncio.Task] = None


async def _scheduled_reminder() -> None:
    settings = get_settings()
    logger.info("Running scheduled reminder")
    try:
        await run_reminder_pipeline(
            settings,
            send=True,
            try_call=settings.enable_voice_calls,
        )
    except Exception:  # noqa: BLE001
        logger.exception("Scheduled reminder failed")


async def _standalone_poll_loop() -> None:
    settings = get_settings()
    offset: Optional[int] = None
    logger.info("Standalone Telegram polling started")
    while True:
        try:
            # Rileggi settings/chat_id a runtime (può essere auto-appreso)
            settings = get_settings()
            known = effective_chat_id(settings)
            updates = await get_updates(settings, offset=offset, timeout=25)
            for update in updates:
                offset = update["update_id"] + 1
                message = update.get("message") or update.get("edited_message")
                if not message:
                    continue
                chat_id = str(message["chat"]["id"])
                db.remember_chat_id(settings.database_path, chat_id)

                if known and chat_id != str(known):
                    continue

                if message.get("voice") or message.get("audio"):
                    file_id = (message.get("voice") or message.get("audio"))["file_id"]
                    audio = await download_file(settings, file_id)
                    result = await handle_user_audio(
                        settings,
                        audio,
                        source="voice",
                        chat_id=chat_id,
                    )
                elif message.get("text"):
                    result = await handle_user_text(
                        settings,
                        message["text"],
                        source="chat",
                        chat_id=chat_id,
                    )
                else:
                    continue

                await deliver_to_telegram(
                    settings,
                    text=result["text"],
                    audio_path=result.get("audio_path"),
                    chat_id=chat_id,
                )
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            logger.exception("Polling loop error")
            await asyncio.sleep(3)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global scheduler, _poll_task
    settings = get_settings()
    Path(settings.tmp_audio_dir).mkdir(parents=True, exist_ok=True)
    db.init_db(settings.database_path)

    scheduler = AsyncIOScheduler(timezone=ZoneInfo(settings.tz))
    if settings.enable_internal_reminders and settings.reminder_times_list:
        for hhmm in settings.reminder_times_list:
            hour, minute = hhmm.split(":")
            scheduler.add_job(
                _scheduled_reminder,
                CronTrigger(
                    hour=int(hour),
                    minute=int(minute),
                    timezone=ZoneInfo(settings.tz),
                ),
                id=f"reminder-{hhmm}",
                replace_existing=True,
            )
        scheduler.start()
        logger.info(
            "Reminders scheduled at %s (%s)",
            settings.reminder_times_list,
            settings.tz,
        )
    else:
        scheduler.start()
        logger.info(
            "Internal reminders disabled "
            "(use n8n cron or set ENABLE_INTERNAL_REMINDERS=true)"
        )

    if settings.standalone_bot:
        _poll_task = asyncio.create_task(_standalone_poll_loop())

    yield

    if _poll_task:
        _poll_task.cancel()
        try:
            await _poll_task
        except asyncio.CancelledError:
            pass
    if scheduler:
        scheduler.shutdown(wait=False)
    await shutdown_caller()


app = FastAPI(title="Echo API", version="1.1.0", lifespan=lifespan)


@app.get("/health")
async def health() -> Dict[str, Any]:
    settings = get_settings()
    return {
        "ok": True,
        "service": "echo-api",
        "version": "1.1.0",
        "time": datetime.now(ZoneInfo(settings.tz)).isoformat(),
        "standalone_bot": settings.standalone_bot,
        "enable_voice_calls": settings.enable_voice_calls,
        "reminder_times": settings.reminder_times_list,
        "chat_id": effective_chat_id(settings),
    }


@app.get("/context")
async def context(limit: int = 10) -> Dict[str, Any]:
    settings = get_settings()
    logs = db.recent_logs(settings.database_path, limit=limit)
    return {
        "summary": db.context_summary(settings.database_path, limit=min(limit, 5)),
        "logs": logs,
        "chat_id": effective_chat_id(settings),
    }


@app.get("/logs")
async def logs(limit: int = 50) -> Dict[str, Any]:
    settings = get_settings()
    return {"logs": db.recent_logs(settings.database_path, limit=limit)}


@app.post("/log")
async def log_entry(body: LogIn) -> Dict[str, Any]:
    settings = get_settings()
    payload = normalize_log_payload(body.model_dump())
    saved = db.insert_log(
        settings.database_path,
        raw_text=body.raw_text,
        source=body.source,
        data_ora=body.data_ora,
        **payload,
    )
    return {"ok": True, "saved": saved}


@app.post("/chat")
async def chat_endpoint(body: ChatIn) -> Dict[str, Any]:
    settings = get_settings()
    try:
        result = await handle_user_text(
            settings,
            body.text,
            source=body.source,
            chat_id=body.chat_id,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if body.send:
        result["delivery"] = await deliver_to_telegram(
            settings,
            text=result["text"],
            audio_path=result.get("audio_path"),
            chat_id=body.chat_id,
        )
    return result


@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)) -> Dict[str, Any]:
    settings = get_settings()
    audio = await file.read()
    try:
        text = await speech_to_text(
            settings,
            audio,
            language="it",
            filename=file.filename or "audio.ogg",
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"text": text}


@app.post("/handle-audio")
async def handle_audio(
    file: UploadFile = File(...),
    send: bool = False,
    chat_id: Optional[str] = None,
) -> Dict[str, Any]:
    settings = get_settings()
    audio = await file.read()
    try:
        result = await handle_user_audio(
            settings,
            audio,
            filename=file.filename or "voice.ogg",
            chat_id=chat_id,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if send:
        result["delivery"] = await deliver_to_telegram(
            settings,
            text=result["text"],
            audio_path=result.get("audio_path"),
            chat_id=chat_id,
        )
    return result


@app.post("/telegram/file")
async def telegram_file(body: TelegramFileIn) -> Dict[str, Any]:
    """Scarica un file Telegram (voice) e lo processa."""
    settings = get_settings()
    try:
        audio = await download_file(settings, body.file_id)
        result = await handle_user_audio(
            settings,
            audio,
            chat_id=body.chat_id,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if body.send:
        result["delivery"] = await deliver_to_telegram(
            settings,
            text=result["text"],
            audio_path=result.get("audio_path"),
            chat_id=body.chat_id,
        )
    return result


@app.get("/telegram/discover-chat")
async def discover_chat() -> Dict[str, Any]:
    """Legge getUpdates e memorizza il primo chat_id trovato."""
    settings = get_settings()
    try:
        updates = await get_updates(settings, timeout=0)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    found = []
    for update in updates:
        message = update.get("message") or update.get("edited_message")
        if not message:
            continue
        chat = message.get("chat") or {}
        chat_id = str(chat.get("id", ""))
        if not chat_id:
            continue
        db.remember_chat_id(settings.database_path, chat_id)
        found.append(
            {
                "chat_id": chat_id,
                "type": chat.get("type"),
                "username": chat.get("username"),
                "first_name": chat.get("first_name"),
                "text": message.get("text"),
            }
        )

    current = effective_chat_id(settings)
    return {
        "ok": True,
        "current_chat_id": current,
        "candidates": found,
        "hint": (
            "Scrivi un messaggio al bot su Telegram, poi richiama questo endpoint "
            "oppure lascia STANDALONE_BOT=true: il chat_id viene appreso da solo."
        ),
    }


@app.post("/tts")
async def tts(body: TTSIn) -> FileResponse:
    settings = get_settings()
    stamp = datetime.now(timezone.utc).timestamp()
    out = Path(settings.tmp_audio_dir) / f"tts-{stamp}.{settings.fish_tts_format}"
    try:
        await text_to_speech(settings, body.text, out)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    media = "audio/ogg" if settings.fish_tts_format == "ogg" else "audio/mpeg"
    return FileResponse(out, media_type=media, filename=out.name)


@app.post("/remind")
async def remind(body: RemindIn) -> Dict[str, Any]:
    settings = get_settings()
    try:
        return await run_reminder_pipeline(
            settings,
            send=body.send,
            try_call=body.try_call,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/call")
async def call_endpoint(body: CallIn) -> Dict[str, Any]:
    settings = get_settings()
    if not settings.enable_voice_calls:
        raise HTTPException(status_code=400, detail="ENABLE_VOICE_CALLS=false")

    audio_path: Optional[Path] = Path(body.audio_path) if body.audio_path else None
    if audio_path is None:
        if not body.text:
            raise HTTPException(status_code=400, detail="Serve audio_path oppure text")
        stamp = datetime.now(timezone.utc).timestamp()
        audio_path = (
            Path(settings.tmp_audio_dir) / f"call-{stamp}.{settings.fish_tts_format}"
        )
        try:
            await text_to_speech(settings, body.text, audio_path)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    if not audio_path.exists():
        raise HTTPException(status_code=404, detail="Audio non trovato")

    try:
        result = await place_call(settings, audio_path, target=body.target)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return result


@app.get("/audio/{name}")
async def get_audio(name: str) -> FileResponse:
    settings = get_settings()
    path = Path(settings.tmp_audio_dir) / name
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="File non trovato")
    media = "audio/ogg" if path.suffix == ".ogg" else "audio/mpeg"
    return FileResponse(path, media_type=media, filename=path.name)
