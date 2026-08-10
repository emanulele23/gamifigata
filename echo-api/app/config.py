from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    fish_api_key: str = ""
    fish_reference_id: str = ""
    fish_tts_model: str = "s2.1-pro"
    fish_tts_format: str = "ogg"

    database_path: str = "/app/data/echo.db"
    tmp_audio_dir: str = "/app/tmp"

    reminder_times: str = "09:00,14:00,21:00"
    enable_internal_reminders: bool = True
    standalone_bot: bool = True
    enable_voice_calls: bool = True
    prefer_calls_on_checkin: bool = True
    tz: str = "Europe/Rome"

    telegram_api_id: int | None = None
    telegram_api_hash: str = ""
    telegram_call_target: str = ""
    telegram_session_path: str = "/app/data/echo_userbot"

    apple_health_secret: str = ""
    echo_public_url: str = "http://localhost:5000"

    @property
    def reminder_times_list(self) -> List[str]:
        return [t.strip() for t in self.reminder_times.split(",") if t.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
