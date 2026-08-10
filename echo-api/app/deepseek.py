from typing import Dict, List, Optional

import httpx

from app.config import Settings
from app.prompt import SYSTEM_PROMPT


class DeepSeekError(RuntimeError):
    pass


async def chat(
    settings: Settings,
    user_message: str,
    *,
    system_prompt: str = SYSTEM_PROMPT,
    history: Optional[List[Dict[str, str]]] = None,
) -> str:
    if not settings.deepseek_api_key:
        raise DeepSeekError("DEEPSEEK_API_KEY mancante")

    messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    base = settings.deepseek_base_url.rstrip("/")
    url = f"{base}/chat/completions"
    payload = {
        "model": settings.deepseek_model,
        "messages": messages,
        "temperature": 0.7,
        "stream": False,
    }
    headers = {
        "Authorization": f"Bearer {settings.deepseek_api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=90.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        if resp.status_code >= 400:
            raise DeepSeekError(
                f"DeepSeek failed ({resp.status_code}): {resp.text[:500]}"
            )
        body = resp.json()

    try:
        return body["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError, AttributeError) as exc:
        raise DeepSeekError(f"Risposta DeepSeek inattesa: {body}") from exc
