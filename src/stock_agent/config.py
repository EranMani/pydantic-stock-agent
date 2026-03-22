"""Central configuration for the stock analyst agent.

All constants, API keys, and environment-driven settings live here.
Nothing is hardcoded in logic files — import `settings` to access values.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

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
    OPENAI_API_KEY: str = Field(
        default="",
        description="OpenAI API key for cloud model inference. Takes precedence over GEMINI_API_KEY if both are set.",
    )
    GEMINI_API_KEY: str = Field(
        default="",
        description="Google Gemini API key for cloud model inference. Used when OPENAI_API_KEY is not set.",
    )
    OLLAMA_HOST: str = Field(
        default="http://localhost:11434",
        description="Ollama server base URL for local LLM inference (llama3.2). Use http://ollama:11434 inside Docker.",
    )
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://user:pass@localhost:5432/stockagent",
        description="PostgreSQL connection string for SQLAlchemy async engine. Use asyncpg driver. In Docker, host is 'postgres'.",
    )
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL for Celery broker and progress state whiteboard. Use redis://redis:6379/0 inside Docker.",
    )
    CELERY_BROKER_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Celery broker URL — must match REDIS_URL for this project's single-Redis setup.",
    )
    CELERY_RESULT_BACKEND: str = Field(
        default="redis://localhost:6379/1",
        description="Celery result backend URL — uses Redis DB 1 to separate results from the broker channel.",
    )


# Module-level singleton — import this throughout the codebase
settings = Settings()

# Base weights for each fundamental metric — re-normalised dynamically by the
# scorer based on which metrics are active in the ScoringStrategy
METRIC_WEIGHTS: dict[str, float] = {
    "pe_ratio": 0.4,
    "revenue_growth": 0.4,
    "market_cap": 0.1,
    "beta": 0.1,
}

# Base weights for each technical indicator — re-normalised dynamically by the
# scorer based on which indicators are active in the ScoringStrategy
INDICATOR_WEIGHTS: dict[str, float] = {
    "trend_template": 0.5,
    "vcp": 0.3,
    "macd": 0.1,
    "moving_averages": 0.1,
}

# Normalisation ranges for fundamental metric sub-scoring.
# Each entry is (max_value, higher_is_better).
# Calibrated for balanced/growth strategies — see QA.md for future scoring_profile enhancement.
METRIC_NORMALISATION: dict[str, tuple[float, bool]] = {
    "pe_ratio":       (50.0,  False),  # lower P/E is better; capped at 50
    "revenue_growth": (1.5,   True),   # higher growth is better; 150% ceiling for growth stocks
    "market_cap":     (1e12,  True),   # higher market cap = more stability; $1T ceiling
    "beta":           (2.0,   False),  # closer to 0 penalises inverse; >2 penalises excess risk
}
