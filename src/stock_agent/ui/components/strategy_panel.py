"""ScoringStrategy configuration panel — weight sliders for the dashboard.

Renders a card with a single slider controlling the fundamental/technical
weight split. Technical weight is always derived as (100 - fundamental),
guaranteeing the two weights always sum to 1.0 without needing a validator.

Public API:
  StrategyState  — mutable container holding the current weight split
  strategy_panel(state) — renders the NiceGUI card and binds it to state
"""

from nicegui import ui

from stock_agent.models.context import ScoringStrategy


class StrategyState:
    """Mutable container for the current scoring weight configuration.

    Holds fundamental_pct (0–100 integer). technical_pct is always derived
    as (100 - fundamental_pct) — the two values are guaranteed to sum to 100.
    Call to_scoring_strategy() to produce a validated ScoringStrategy instance.
    """

    def __init__(self) -> None:
        """Initialise with a default 50/50 weight split."""
        self.fundamental_pct: int = 50

    @property
    def technical_pct(self) -> int:
        """Derived technical weight percentage — always (100 - fundamental_pct)."""
        return 100 - self.fundamental_pct

    def to_scoring_strategy(self) -> ScoringStrategy:
        """Build a validated ScoringStrategy from the current weight state."""
        return ScoringStrategy(
            fundamental_weight=round(self.fundamental_pct / 100, 2),
            technical_weight=round(self.technical_pct / 100, 2),
        )


def strategy_panel(state: StrategyState) -> None:
    """Render the scoring weight configuration card and bind it to state.

    Renders a single slider (0–100) for the fundamental weight. The technical
    weight label updates reactively as the slider moves. Uses only NiceGUI
    Python API — no HTML, CSS, or JavaScript.
    """
    with ui.card().classes("w-full"):
        ui.label("Scoring Weights").classes("text-base font-semibold mb-2")

        with ui.row().classes("w-full items-center gap-4"):
            ui.label("Fundamental").classes("w-24 text-sm")
            slider = ui.slider(min=0, max=100, step=1, value=state.fundamental_pct).classes("flex-1")
            weight_display = ui.label(
                f"F {state.fundamental_pct}% / T {state.technical_pct}%"
            ).classes("w-28 text-sm text-right")

        def on_weight_change(e) -> None:
            """Update state and refresh the weight display label on slider change."""
            state.fundamental_pct = int(e.value)
            weight_display.set_text(f"F {state.fundamental_pct}% / T {state.technical_pct}%")

        slider.on_value_change(on_weight_change)
