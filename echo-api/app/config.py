from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict

# Carica prima .env sulla Pi, poi secrets salvati dalla pagina /setup
ENV_FILES = (
    ".env",
    "/app/data/secrets.env",
    "echo-api/data/secrets.env",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILES,
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
    # Note vocali Telegram (affidabili). Le "chiamate" restano opzione avanzata.
    enable_voice_calls: bool = False
    prefer_calls_on_checkin: bool = False
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

    @property
    def is_configured(self) -> bool:
        return bool(
            self.telegram_bot_token
            and self.deepseek_api_key
            and self.fish_api_key
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reload_settings() -> Settings:
    get_settings.cache_clear()
    return get_settings()


def write_secrets_file(
    path: str,
    *,
    telegram_bot_token: str = "",
    deepseek_api_key: str = "",
    fish_api_key: str = "",
    fish_reference_id: str = "",
) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Generato dalla pagina /setup — non condividere",
        f"TELEGRAM_BOT_TOKEN={telegram_bot_token}",
        f"DEEPSEEK_API_KEY={deepseek_api_key}",
        f"FISH_API_KEY={fish_api_key}",
        f"FISH_REFERENCE_ID={fish_reference_id}",
        "",
    ]
    p.write_text("\n".join(lines))
