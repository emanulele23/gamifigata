from pathlib import Path
from typing import Any, Dict, Optional

import httpx

from app.config import Settings


class TelegramBotError(RuntimeError):
    pass


def _api_url(settings: Settings, method: str) -> str:
    token = settings.telegram_bot_token
    if not token:
        raise TelegramBotError("TELEGRAM_BOT_TOKEN mancante")
    return f"https://api.telegram.org/bot{token}/{method}"


async def send_message(
    settings: Settings,
    text: str,
    *,
    chat_id: Optional[str] = None,
) -> Dict[str, Any]:
    target = chat_id or settings.telegram_chat_id
    if not target:
        raise TelegramBotError("TELEGRAM_CHAT_ID mancante")

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            _api_url(settings, "sendMessage"),
            json={"chat_id": target, "text": text},
        )
        body = resp.json()
        if not body.get("ok"):
            raise TelegramBotError(f"sendMessage failed: {body}")
        return body["result"]


async def send_voice(
    settings: Settings,
    audio_path: Path,
    *,
    chat_id: Optional[str] = None,
    caption: Optional[str] = None,
) -> Dict[str, Any]:
    target = chat_id or settings.telegram_chat_id
    if not target:
        raise TelegramBotError("TELEGRAM_CHAT_ID mancante")

    data = {"chat_id": str(target)}
    if caption:
        data["caption"] = caption

    async with httpx.AsyncClient(timeout=120.0) as client:
        with audio_path.open("rb") as fh:
            resp = await client.post(
                _api_url(settings, "sendVoice"),
                data=data,
                files={"voice": (audio_path.name, fh, "audio/ogg")},
            )
        body = resp.json()
        if not body.get("ok"):
            raise TelegramBotError(f"sendVoice failed: {body}")
        return body["result"]


async def download_file(settings: Settings, file_id: str) -> bytes:
    async with httpx.AsyncClient(timeout=120.0) as client:
        meta = await client.get(
            _api_url(settings, "getFile"),
            params={"file_id": file_id},
        )
        meta_body = meta.json()
        if not meta_body.get("ok"):
            raise TelegramBotError(f"getFile failed: {meta_body}")
        file_path = meta_body["result"]["file_path"]
        url = f"https://api.telegram.org/file/bot{settings.telegram_bot_token}/{file_path}"
        content = await client.get(url)
        content.raise_for_status()
        return content.content


async def get_updates(
    settings: Settings,
    *,
    offset: Optional[int] = None,
    timeout: int = 25,
) -> list:
    params: Dict[str, Any] = {"timeout": timeout}
    if offset is not None:
        params["offset"] = offset
    async with httpx.AsyncClient(timeout=timeout + 10) as client:
        resp = await client.get(_api_url(settings, "getUpdates"), params=params)
        body = resp.json()
        if not body.get("ok"):
            raise TelegramBotError(f"getUpdates failed: {body}")
        return body.get("result") or []
