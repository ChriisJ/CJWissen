"""Konfiguration der Wissenswerkstatt-App.

Werte werden aus Umgebungsvariablen geladen (siehe .env.example).
"""
from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- LLM ----------------------------------------------
    llm_base_url: str = Field(default="https://api.openai.com/v1")
    llm_api_key: str = Field(default="")
    llm_model: str = Field(default="gpt-4o-mini")
    llm_max_tokens: int = Field(default=1500)
    llm_temperature: float = Field(default=0.4)

    # --- App ----------------------------------------------
    app_host: str = Field(default="0.0.0.0")
    app_port: int = Field(default=8080)
    app_secret: str = Field(default="")
    app_timezone: str = Field(default="Europe/Berlin")
    data_dir: str = Field(default="/app/data")

    @property
    def db_path(self) -> Path:
        path = Path(self.data_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path / "wissenswerkstatt.db"


settings = Settings()
