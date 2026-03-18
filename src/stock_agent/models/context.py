"""Runtime dependency and scoring configuration models for the stock analyst agent.

ScoringStrategy defines which metrics to include and how to weight them —
passed via AgentDependencies into every agent tool call through PydanticAI's
dependency injection system (ctx.deps).
"""

from dataclasses import dataclass

from pydantic import BaseModel, Field, model_validator


class ScoringStrategy(BaseModel):
    """Dynamic configuration for which metrics to score and how to weight them.

    Controls both which fundamental/technical indicators are active and the
    relative weight of each pipeline in the final weighted score.
    """

    fundamental_metrics: list[str] = Field(
        default=["pe_ratio", "revenue_growth"],
        description="List of fundamental metric names to include in scoring. Must match keys in METRIC_WEIGHTS in config.py.",
    )
    technical_indicators: list[str] = Field(
        default=["trend_template", "vcp"],
        description="List of technical indicator names to include in scoring. Must match keys in INDICATOR_MODULES in technical_scorer.py.",
    )
    fundamental_weight: float = Field(
        default=0.50,
        description="Proportion of the final score attributed to fundamental analysis. Must sum to 1.0 with technical_weight.",
    )
    technical_weight: float = Field(
        default=0.50,
        description="Proportion of the final score attributed to technical analysis. Must sum to 1.0 with fundamental_weight.",
    )

    @model_validator(mode="after")
    def weights_sum_to_one(self) -> "ScoringStrategy":
        """Ensure fundamental and technical weights sum to exactly 1.0."""
        total = self.fundamental_weight + self.technical_weight
        if round(total, 10) != 1.0:
            raise ValueError(
                f"fundamental_weight + technical_weight must equal 1.0, got {total}"
            )
        return self


@dataclass
class AgentDependencies:
    """Dependency injection container passed to every PydanticAI agent tool.

    Carries the user-configured ScoringStrategy so each tool can dynamically
    route calculations based on active metrics and weights (ctx.deps.strategy).
    """

    strategy: ScoringStrategy
