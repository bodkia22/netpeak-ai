import sys

from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables / .env file."""

    anthropic_api_key: str
    anthropic_model: str
    max_retries: int = 3

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8"
    )


try:
    settings = Settings()
except ValidationError as exc:
    sys.exit(
        f"Configuration error: missing or invalid environment variables.\n"
        f"Check that .env exists and matches .env.example.\n\n{exc}"
    )