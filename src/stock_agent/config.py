"""Central configuration for the stock analyst agent.

All constants, API keys, and environment-driven settings live here.
Nothing is hardcoded in logic files — import `settings` to access values.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    TV_USERNAME: str = Field(
        default="",
        description="TradingView username for tvDatafeed authenticated session. Leave empty for anonymous access.",
    )
    TV_PASSWORD: str = Field(
        default="",
        description="TradingView password for tvDatafeed authenticated session. Leave empty for anonymous access.",
    )
    LOGFIRE_TOKEN: str = Field(
        default="",
        description="Logfire API token for structured observability. Optional — logging is skipped if empty.",
    )
    APP_ENV: str = Field(
        default="development",
        description="Runtime environment: 'development' enables dev tools and auto-migration; 'production' disables them.",
    )
    PORT: int = Field(
        default=8080,
        description="Port the NiceGUI/FastAPI web server listens on.",
    )


# Module-level singleton — import this throughout the codebase
settings = Settings()
