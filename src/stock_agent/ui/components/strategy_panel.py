"""ScoringStrategy configuration panel — collapsible metric toggle pills.

Renders a collapsible ui.expansion("Scoring Strategy") containing two groups of
pill-toggle buttons:
  - Fundamental metrics: P/E Ratio, Revenue Growth, Market Cap, Beta
  - Technical indicators: Trend Template, VCP

The expansion is collapsed by default and lives INSIDE the main control card
in app.py (below the Analyse button, after a separator). This keeps the entire
primary action surface in one card — no floating panel below.

Each pill toggles between active (indigo-600) and inactive (gray-700) state.
Root cause of previous pill toggle failure: ui.button() defaults to
color='primary', which applies Quasar's scoped CSS and overrides Tailwind bg
classes. Fix: pass color=None to every pill button so Tailwind classes are the
sole authority over visual state.

Pill toggle class-swap fix: NiceGUI's .classes() does not accept `replace` as a
keyword argument in this version — passing replace=True causes AttributeError
('bool' object has no attribute 'split'). Fix: clear _classes directly via
b._classes.clear() then call b.classes(NEW_CLASSES) to set the full string.
This is reliable and avoids class accumulation across multiple toggles.

The weight slider lives in app.py's control card, not here — this panel is
purely the metric selection layer.

Active metrics are stored as sets inside StrategyState and converted to
sorted lists when building a ScoringStrategy. The StrategyState class also
holds fundamental_pct which is mutated by the weight slider in app.py.

Public API:
  StrategyState  — mutable container: weight split + active metric sets
  strategy_panel(state) — renders collapsible pill toggle groups bound to state
"""

from nicegui import ui

from stock_agent.models.context import ScoringStrategy
from stock_agent.ui.theme import COLOURS, PILL_ACTIVE, PILL_INACTIVE, SPACING, TYPOGRAPHY

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


def strategy_panel(state: StrategyState) -> None:
    """Render collapsible metric toggle pill groups bound to state.

    Renders a ui.expansion() that lives INSIDE the main control card in app.py
    (after a separator, below the Analyse button). No card wrapper inside — the
    parent card provides the surface. Two pill groups: fundamentals and technicals.

    Pill toggle fix: every ui.button() pill passes color=None to strip Quasar's
    scoped color CSS, making Tailwind bg classes authoritative. On toggle, classes
    are swapped by clearing b._classes then calling b.classes(NEW_STRING) — this
    avoids the AttributeError caused by passing replace=True as a keyword argument
    (not valid in this NiceGUI version) and prevents class accumulation across
    multiple toggle cycles.

    Direct button references are captured in closures via default argument binding
    (b=btn) to avoid the late-binding closure problem across loop iterations.

    Uses only NiceGUI Python API — no HTML, CSS, or JavaScript.
    """
    # Expansion collapsed by default (value=False is the NiceGUI default — no param needed).
    # .classes("w-full") ensures it spans the full column width within the parent card.
    with ui.expansion("Scoring Strategy", icon="tune").classes("w-full"):
        with ui.column().classes(f"w-full {SPACING['compact_gap']} pt-2"):

            # --- Fundamental metric pills ---
            with ui.column().classes(f"w-full {SPACING['tight_gap']}"):
                ui.label("Fundamentals").classes(
                    f"{TYPOGRAPHY['section_label']} text-{COLOURS['subtle']}"
                )
                with ui.row().classes(f"flex-wrap {SPACING['tight_gap']}"):
                    for key, label in _ALL_FUNDAMENTAL:
                        is_active = key in state.active_fundamental
                        # color=None: removes Quasar's scoped color CSS so Tailwind classes win.
                        btn = ui.button(label, color=None).classes(
                            PILL_ACTIVE if is_active else PILL_INACTIVE
                        )

                        def make_toggle(k: str = key, b: ui.button = btn) -> None:
                            """Toggle metric key and swap pill visual state."""
                            def toggle() -> None:
                                """Handle pill click: update state set and swap classes.

                                Class-swap via _classes.clear() + .classes(full_string) to avoid
                                the AttributeError from replace=True (not valid in this NiceGUI
                                version) and to prevent class accumulation across toggle cycles.
                                """
                                if k in state.active_fundamental:
                                    state.active_fundamental.discard(k)
                                    b._classes.clear()
                                    b.classes(PILL_INACTIVE)
                                else:
                                    state.active_fundamental.add(k)
                                    b._classes.clear()
                                    b.classes(PILL_ACTIVE)
                                b.update()
                            return toggle

                        btn.on_click(make_toggle())

            # --- Technical indicator pills ---
            with ui.column().classes(f"w-full {SPACING['tight_gap']}"):
                ui.label("Technicals").classes(
                    f"{TYPOGRAPHY['section_label']} text-{COLOURS['subtle']}"
                )
                with ui.row().classes(f"flex-wrap {SPACING['tight_gap']}"):
                    for key, label in _ALL_TECHNICAL:
                        is_active = key in state.active_technical
                        # Same color=None fix applied to technical pills.
                        btn = ui.button(label, color=None).classes(
                            PILL_ACTIVE if is_active else PILL_INACTIVE
                        )

                        def make_tech_toggle(k: str = key, b: ui.button = btn) -> None:
                            """Toggle indicator key and swap pill visual state."""
                            def toggle() -> None:
                                """Handle pill click: update state set and swap classes.

                                Same _classes.clear() pattern as fundamental pills — avoids
                                AttributeError from replace=True keyword argument.
                                """
                                if k in state.active_technical:
                                    state.active_technical.discard(k)
                                    b._classes.clear()
                                    b.classes(PILL_INACTIVE)
                                else:
                                    state.active_technical.add(k)
                                    b._classes.clear()
                                    b.classes(PILL_ACTIVE)
                                b.update()
                            return toggle

                        btn.on_click(make_tech_toggle())
