"""ScoringStrategy configuration panel — weight sliders and metric toggles.

Renders a card with:
  - A single slider controlling the fundamental/technical weight split
  - Checkboxes for each fundamental metric (pe_ratio, revenue_growth,
    market_cap, beta) and technical indicator (trend_template, vcp)

Technical weight is always derived as (100 - fundamental_pct),
guaranteeing the two weights always sum to 1.0 without runtime validation
on every slider move. Active metrics are stored as sets and converted to
sorted lists when building a ScoringStrategy.

Public API:
  StrategyState  — mutable container holding the current weight + metric config
  strategy_panel(state) — renders the NiceGUI card and binds it to state
"""

from nicegui import ui

from stock_agent.models.context import ScoringStrategy

# All available fundamental metrics — keys must match METRIC_WEIGHTS in config.py
_ALL_FUNDAMENTAL: list[tuple[str, str]] = [
    ("pe_ratio",        "P/E Ratio"),
    ("revenue_growth",  "Revenue Growth"),
    ("market_cap",      "Market Cap"),
    ("beta",            "Beta"),
]

# All available technical indicators — keys must match INDICATOR_WEIGHTS in technical_scorer.py
_ALL_TECHNICAL: list[tuple[str, str]] = [
    ("trend_template",  "Trend Template"),
    ("vcp",             "VCP"),
]


class StrategyState:
    """Mutable container for the current scoring weight and metric configuration.

    Holds fundamental_pct (0–100 integer) and sets of active metric/indicator
    keys. Call to_scoring_strategy() to produce a validated ScoringStrategy.
    """

    def __init__(self) -> None:
        """Initialise with default 50/50 weight split and all metrics active."""
        self.fundamental_pct: int = 50
        self.active_fundamental: set[str] = {key for key, _ in _ALL_FUNDAMENTAL}
        self.active_technical: set[str] = {key for key, _ in _ALL_TECHNICAL}

    @property
    def technical_pct(self) -> int:
        """Derived technical weight percentage — always (100 - fundamental_pct)."""
        return 100 - self.fundamental_pct

    def to_scoring_strategy(self) -> ScoringStrategy:
        """Build a validated ScoringStrategy from the current weight and metric state.

        Active sets are converted to sorted lists so the output is deterministic
        regardless of the order toggles were changed.
        """
        return ScoringStrategy(
            fundamental_weight=round(self.fundamental_pct / 100, 2),
            technical_weight=round(self.technical_pct / 100, 2),
            fundamental_metrics=sorted(self.active_fundamental),
            technical_indicators=sorted(self.active_technical),
        )


def strategy_panel(state: StrategyState) -> None:
    """Render the scoring strategy configuration card and bind it to state.

    Sections:
      1. Weight slider — fundamental/technical split (0–100)
      2. Fundamental metric toggles — checkboxes for each metric
      3. Technical indicator toggles — checkboxes for each indicator

    Uses only NiceGUI Python API — no HTML, CSS, or JavaScript.
    """
    with ui.card().classes("w-full gap-3"):
        ui.label("Scoring Strategy").classes("text-base font-semibold")

        # --- Weight slider ---
        ui.label("Weights").classes("text-xs font-semibold text-gray-500 uppercase tracking-wide")
        with ui.row().classes("w-full items-center gap-4"):
            ui.label("Fundamental").classes("w-24 text-sm")
            slider = ui.slider(min=0, max=100, step=1, value=state.fundamental_pct).classes("flex-1")
            weight_display = ui.label(
                f"F {state.fundamental_pct}% / T {state.technical_pct}%"
            ).classes("w-28 text-sm text-right")

        def on_weight_change(e) -> None:
            """Update state and refresh weight display on slider change."""
            state.fundamental_pct = int(e.value)
            weight_display.set_text(f"F {state.fundamental_pct}% / T {state.technical_pct}%")

        slider.on_value_change(on_weight_change)

        ui.separator()

        # --- Fundamental metric toggles ---
        ui.label("Fundamental Metrics").classes("text-xs font-semibold text-gray-500 uppercase tracking-wide")
        with ui.row().classes("flex-wrap gap-x-6 gap-y-1"):
            for key, label in _ALL_FUNDAMENTAL:
                checkbox = ui.checkbox(label, value=key in state.active_fundamental)

                def make_fundamental_handler(k: str):
                    def handler(e) -> None:
                        """Toggle a fundamental metric in the active set."""
                        if e.value:
                            state.active_fundamental.add(k)
                        else:
                            state.active_fundamental.discard(k)
                    return handler

                checkbox.on_value_change(make_fundamental_handler(key))

        ui.separator()

        # --- Technical indicator toggles ---
        ui.label("Technical Indicators").classes("text-xs font-semibold text-gray-500 uppercase tracking-wide")
        with ui.row().classes("flex-wrap gap-x-6 gap-y-1"):
            for key, label in _ALL_TECHNICAL:
                checkbox = ui.checkbox(label, value=key in state.active_technical)

                def make_technical_handler(k: str):
                    def handler(e) -> None:
                        """Toggle a technical indicator in the active set."""
                        if e.value:
                            state.active_technical.add(k)
                        else:
                            state.active_technical.discard(k)
                    return handler

                checkbox.on_value_change(make_technical_handler(key))
