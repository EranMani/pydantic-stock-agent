"""ScoringStrategy configuration panel — collapsible metric toggle chips.

Renders a collapsible ui.expansion("Scoring Strategy") containing two groups of
chip-toggle selectors:
  - Fundamental metrics: P/E Ratio, Revenue Growth, Market Cap, Beta
  - Technical indicators: Trend Template, VCP

The expansion is collapsed by default and lives INSIDE the main control card
in app.py (below the Analyse button, after a separator). This keeps the entire
primary action surface in one card — no floating panel below.

Each chip uses ui.chip(selectable=True) which handles the toggle contract
natively via Quasar's QChip component. Active chips are styled indigo;
inactive chips are grey-8. The on("update:selected", ...) event fires on
every selection change with e.value as the new boolean state.

This replaces the previous ui.button(color=None) + _classes.clear() hack
which worked but was fragile and semantically wrong — a toggle should be a
chip, not a styled button.

The weight slider lives in app.py's control card, not here — this panel is
purely the metric selection layer.

Active metrics are stored as sets inside StrategyState and converted to
sorted lists when building a ScoringStrategy. The StrategyState class also
holds fundamental_pct which is mutated by the weight slider in app.py.

Public API:
  StrategyState  — mutable container: weight split + active metric sets
  strategy_panel(state) — renders collapsible chip toggle groups bound to state
"""

from nicegui import ui

from stock_agent.models.context import ScoringStrategy
from stock_agent.ui.theme import COLOURS, SPACING, TYPOGRAPHY

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
    keys. The weight slider in app.py mutates fundamental_pct directly.
    Call to_scoring_strategy() to produce a validated ScoringStrategy.
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


def _make_chip(label: str, key: str, active_set: set[str]) -> None:
    """Render a selectable QChip bound to a key in the given active metric set.

    Uses ui.chip(selectable=True) — NiceGUI's wrapper for Quasar QChip.
    The chip handles its own selected/unselected visual state; we listen to
    the "update:selected" Vue event to keep active_set in sync.

    Color prop: "indigo" (active) or "grey-8" (inactive). These are Quasar
    palette names — not Tailwind classes. They apply to the chip background.
    text_color="white" ensures legibility on both indigo and grey-8 backgrounds.

    Event handler uses default-argument binding (k=key, c=chip, s=active_set)
    to capture the correct loop-iteration values — standard Python closure fix.
    """
    chip = ui.chip(
        label,
        selectable=True,
        selected=key in active_set,
        color="indigo" if key in active_set else "grey-8",
        text_color="white",
    )

    def on_select(e, k: str = key, c: ui.chip = chip, s: set = active_set) -> None:
        """Handle chip selection change — update active set and swap chip color."""
        if e.value:
            s.add(k)
            c.props("color=indigo")
        else:
            s.discard(k)
            c.props("color=grey-8")

    chip.on("update:selected", on_select)


def strategy_panel(state: StrategyState) -> None:
    """Render collapsible metric toggle chip groups bound to state.

    Renders a ui.expansion() that lives INSIDE the main control card in app.py
    (after a separator, below the Analyse button). No card wrapper inside — the
    parent card provides the surface. Two chip groups: fundamentals and technicals.

    Chips use ui.chip(selectable=True) — the native Quasar toggle pattern.
    No color=None hacks, no _classes.clear() workarounds. The QChip component
    owns its own toggle state; we only update active_set on the event.

    Uses only NiceGUI Python API — no HTML, CSS, or JavaScript.
    """
    # Expansion collapsed by default (value=False is the NiceGUI default — no param needed).
    # .classes("w-full") ensures it spans the full column width within the parent card.
    # Quasar props: dense (compact header padding — appropriate for an in-card element that
    # does not need full Material expansion padding), expand-separator (adds a subtle line
    # between the header and the expanded content — clarifies the boundary when open).
    with ui.expansion("Scoring Strategy", icon="tune").classes("w-full").props("dense expand-separator"):
        with ui.column().classes(f"w-full {SPACING['compact_gap']} pt-2"):

            # --- Fundamental metric chips ---
            with ui.column().classes(f"w-full {SPACING['tight_gap']}"):
                ui.label("Fundamentals").classes(
                    f"{TYPOGRAPHY['section_label']} text-{COLOURS['subtle']}"
                )
                with ui.row().classes(f"flex-wrap {SPACING['tight_gap']}"):
                    for key, label in _ALL_FUNDAMENTAL:
                        _make_chip(label, key, state.active_fundamental)

            # --- Technical indicator chips ---
            with ui.column().classes(f"w-full {SPACING['tight_gap']}"):
                ui.label("Technicals").classes(
                    f"{TYPOGRAPHY['section_label']} text-{COLOURS['subtle']}"
                )
                with ui.row().classes(f"flex-wrap {SPACING['tight_gap']}"):
                    for key, label in _ALL_TECHNICAL:
                        _make_chip(label, key, state.active_technical)
