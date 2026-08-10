from pathlib import Path
from typing import Optional

import httpx

from app.config import Settings


class FishAudioError(RuntimeError):
    pass


async def text_to_speech(
    settings: Settings,
    text: str,
    output_path: Path,
    *,
    reference_id: Optional[str] = None,
) -> Path:
    if not settings.fish_api_key:
        raise FishAudioError("FISH_API_KEY mancante")

    payload = {
        "text": text,
        "format": settings.fish_tts_format or "ogg",
    }
    ref = reference_id or settings.fish_reference_id
    if ref:
        payload["reference_id"] = ref

    headers = {
        "Authorization": f"Bearer {settings.fish_api_key}",
        "Content-Type": "application/json",
        "model": settings.fish_tts_model or "s2.1-pro",
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            "https://api.fish.audio/v1/tts",
            headers=headers,
            json=payload,
        )
        if resp.status_code >= 400:
            raise FishAudioError(
                f"TTS failed ({resp.status_code}): {resp.text[:500]}"
            )
        output_path.write_bytes(resp.content)
    return output_path


async def speech_to_text(
    settings: Settings,
    audio_bytes: bytes,
    *,
    language: str = "it",
    filename: str = "audio.ogg",
) -> str:
    if not settings.fish_api_key:
        raise FishAudioError("FISH_API_KEY mancante")

    headers = {"Authorization": f"Bearer {settings.fish_api_key}"}
    files = {"audio": (filename, audio_bytes, "application/octet-stream")}
    data = {"language": language}

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            "https://api.fish.audio/v1/asr",
            headers=headers,
            files=files,
            data=data,
        )
        if resp.status_code >= 400:
            raise FishAudioError(
                f"ASR failed ({resp.status_code}): {resp.text[:500]}"
            )
        body = resp.json()
    text = body.get("text") or ""
    return text.strip()
