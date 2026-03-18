"""Runtime dependency and scoring configuration models for the stock analyst agent.

ScoringStrategy defines which metrics to include and how to weight them —
passed via AgentDependencies into every agent tool call through PydanticAI's
dependency injection system (ctx.deps).
"""

from dataclasses import dataclass

from pydantic import BaseModel, model_validator


class ScoringStrategy(BaseModel):
    """Dynamic configuration for which metrics to score and how to weight them.

    Controls both which fundamental/technical indicators are active and the
    relative weight of each pipeline in the final weighted score.
    """

    fundamental_metrics: list[str] = ["pe_ratio", "revenue_growth"]
    technical_indicators: list[str] = ["trend_template", "vcp"]
    fundamental_weight: float = 0.50
    technical_weight: float = 0.50

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
