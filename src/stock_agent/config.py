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

# Base weights for each fundamental metric — re-normalised dynamically by the
# scorer based on which metrics are active in the ScoringStrategy
METRIC_WEIGHTS: dict[str, float] = {
    "pe_ratio": 0.4,
    "revenue_growth": 0.4,
    "market_cap": 0.1,
    "beta": 0.1,
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
