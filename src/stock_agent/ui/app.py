"""NiceGUI web application — entry point for the UI server.

Mounts NiceGUI onto the existing FastAPI app from api.py so both the
REST API (POST /analyze) and the NiceGUI web UI share a single server
on the same port. No separate process or port required.

Entry point:
  uv run python -m stock_agent.ui.app

Dashboard layout — three zones:
  Zone 1: Toolbar — full-bleed fixed header (app_header). gray-900 background,
            indigo bottom border, brand name left, live status right. 56px tall.
            Fixed position (z-50); does not scroll with content.
  Zone 2: Control card — single card containing everything the user touches:
            Row 1: Ticker input (full width)
            Row 2: Weight label (live update)
            Row 3: Weight slider (full width)
            Row 4: Analyse button (full width, visually dominant)
            Separator
            Scoring Strategy expansion (collapsed by default) — fundamental
            and technical pill groups; expands inline within the card
  Zone 3: Progress panel — spinner while running, result card when done

Layout notes:
  - The toolbar is rendered OUTSIDE the content column — it is full-bleed and
    fixed. The content column carries pt-14 (56px) to clear the toolbar.
  - Page column: max-w-2xl, centred — wide enough for structure, narrow enough
    for visual calm.
  - All primary interaction lives in Zone 2's single card. The strategy
    expansion lives inside the card so configuration expands in context, not
    as a separate floating card beneath the controls. One surface, one purpose.
  - The Scoring Strategy expansion is collapsed by default — the main screen
    shows only the essential controls. Users expand when they want to tune weights.

Phase 9 note: POST /analyze is currently synchronous. When Celery is
introduced, the button handler will dispatch a task and poll
GET /jobs/{job_id}/status for real-time progress updates instead.
"""

import asyncio

import httpx
from nicegui import ui

from stock_agent.api import app
from stock_agent.config import settings
from stock_agent.models.report import StockReport
from stock_agent.ui.components.progress_panel import AnalysisState, progress_panel
from stock_agent.ui.components.strategy_panel import StrategyState, strategy_panel
from stock_agent.ui.theme import COLOURS, HEADER, SPACING, TRANSITIONS, TYPOGRAPHY, apply_theme

# Analyse button — dominant indigo, full width, min 44px touch target.
# Applied at initial render and re-applied after enable/disable to preserve classes.
# color=None strips Quasar's scoped color CSS so Tailwind bg-indigo-600 is authoritative.
_ANALYSE_BTN_CLASSES: str = (
    f"w-full bg-{COLOURS['primary_bg']} hover:bg-indigo-700 "
    "text-white font-semibold min-h-[44px] rounded-lg "
    f"{TRANSITIONS['normal']} ease-in-out"
)


def app_header() -> None:
    """Render the full-bleed sticky toolbar at the top of the page.

    Fixed position (z-50), gray-900 background, indigo bottom border.
    Brand name left, live status indicator right.
    Inner content constrained to max-w-2xl so it aligns with the body column.

    Height contract: 56px (h-14). The main content column must offset by
    pt-14 to clear this header — that offset lives in HEADER['body_offset'].
    """
    with ui.element("div").classes(HEADER["bar"]):
        with ui.element("div").classes(HEADER["inner"]):
            # Left side — brand identity
            with ui.row().classes("items-center gap-0"):
                ui.label("Stock Agent").classes(HEADER["brand_name"])
                ui.label("Autonomous PydanticAI stock analyst").classes(HEADER["brand_sub"])

            # Right side — live status indicator
            with ui.row().classes("items-center"):
                ui.element("div").classes(HEADER["status_dot"])
                ui.label("Live").classes(HEADER["status_label"])


def create_ui() -> None:
    """Register all NiceGUI pages and components on the shared FastAPI app.

    Called once at startup before ui.run_with(). Steps 34-37 will add
    the full report card, peer table, and dev tools panel to this page.
    """
    @ui.page("/")
    def index() -> None:
        """Main dashboard — four-zone layout with card surfaces."""
        apply_theme()

        # Full-bleed sticky toolbar — outside the content column intentionally.
        # Fixed position clears the page flow; the content column below is offset
        # by pt-14 (56px) to compensate. See HEADER token in theme.py.
        app_header()

        # Page-level state — one instance per browser session
        strategy_state = StrategyState()
        analysis_state = AnalysisState()

        # max-w-2xl: content doesn't need to be wide — it needs to be well-structured.
        # pt-14: 56px offset to clear the fixed sticky header above.
        with ui.column().classes(
            f"w-full max-w-2xl mx-auto {SPACING['page_padding']} {SPACING['section_gap']} "
            f"{HEADER['body_offset']}"
        ):

            # ------------------------------------------------------------------
            # Zone 2 — Control card: all primary interaction in one surface
            #
            # Layout inside the card:
            #   Row 1: Ticker input (full width)
            #   Row 2: "Scoring Weights" label left + live percentage right
            #   Row 3: Weight slider (full width)
            #   Row 4: Analyse button (full width, dominant)
            #   ── separator ──
            #   Row 5: Scoring Strategy expansion (collapsed by default)
            #           └─ Fundamental pills
            #           └─ Technical pills
            #
            # Everything the user touches lives in one card. The strategy
            # expansion opens inline — no separate panel floating below.
            # ------------------------------------------------------------------
            # Quasar prop: flat — removes Quasar's default card shadow so Tailwind's
            # shadow-sm is the sole elevation authority. Without flat, Quasar and Tailwind
            # both apply shadows and the result is a muddy double-shadow.
            with ui.card().classes(
                f"w-full {SPACING['card_padding_lg']} {SPACING['component_gap']} "
                f"bg-{COLOURS['surface']} rounded-xl shadow-sm"
            ).props("flat"):

                # Row 1 — Ticker input
                # Quasar props: outlined (bordered container — reads clearly on dark surface),
                # rounded (matches card's rounded-xl personality), label (floating Material
                # label replaces the separate ui.label() above — cleaner DOM and better UX).
                # The separate label row is removed; the QInput label prop handles it natively.
                ticker_input = ui.input(
                    placeholder="e.g. AAPL, NVDA, ONDS",
                ).classes("w-full").props('outlined rounded label="Ticker Symbol"')

                # Row 2 — Scoring weight label + live percentage display
                weight_label = ui.label(
                    f"Fundamental {strategy_state.fundamental_pct}%"
                    f" · Technical {strategy_state.technical_pct}%"
                ).classes(f"{TYPOGRAPHY['section_label']} text-{COLOURS['subtle']}")

                # Row 3 — Weight slider (full width)
                # Quasar prop: label — shows the current value in a floating bubble
                # while dragging. Real-time feedback during interaction without adding
                # static noise. The persistent text label above still shows the split
                # at rest; this bubble confirms the value mid-drag.
                # color=indigo maps to Quasar's built-in indigo palette — matches brand.
                slider = ui.slider(
                    min=0, max=100, step=1, value=strategy_state.fundamental_pct
                ).classes("w-full").props("label color=indigo")

                def on_weight_change(e) -> None:
                    """Update state and refresh weight display label on slider change."""
                    strategy_state.fundamental_pct = int(e.value)
                    weight_label.set_text(
                        f"Fundamental {strategy_state.fundamental_pct}%"
                        f" · Technical {strategy_state.technical_pct}%"
                    )

                slider.on_value_change(on_weight_change)

                # Row 4 — Analyse button (full width, visually dominant)
                # color=None: strips Quasar color prop so Tailwind bg-indigo-600 wins.
                # Quasar props: unelevated (removes default Material shadow — not needed on a
                # flat dark card surface), rounded (Quasar's structural border-radius, consistent
                # with the button's own sizing system rather than a raw Tailwind rounded-lg).
                analyse_btn = ui.button("Analyse", color=None).classes(_ANALYSE_BTN_CLASSES).props("unelevated rounded")

                async def on_analyse() -> None:
                    """Dispatch POST /analyze and update analysis_state with the result.

                    Disables the button while running to prevent double-submit.
                    Runs as an asyncio coroutine so the NiceGUI event loop stays
                    responsive while the synchronous pipeline executes.
                    Phase 9 replaces this with a Celery task dispatch + Redis polling.
                    """
                    ticker = ticker_input.value.strip().upper()
                    if not ticker:
                        ui.notify("Enter a ticker symbol", type="warning")
                        return

                    # Lock the button to prevent double-submit
                    analyse_btn.set_enabled(False)

                    analysis_state.is_running = True
                    analysis_state.message = f"Analysing {ticker}..."
                    analysis_state.result = None
                    analysis_state.error = None

                    try:
                        async with httpx.AsyncClient(timeout=120.0) as client:
                            response = await client.post(
                                f"http://localhost:{settings.PORT}/analyze",
                                json={
                                    "ticker": ticker,
                                    "strategy": strategy_state.to_scoring_strategy().model_dump(),
                                },
                            )
                            response.raise_for_status()
                            analysis_state.result = StockReport(**response.json())
                    except httpx.HTTPStatusError as exc:
                        analysis_state.error = (
                            f"API error {exc.response.status_code}: {exc.response.text}"
                        )
                    except Exception as exc:
                        analysis_state.error = str(exc)
                    finally:
                        analysis_state.is_running = False
                        analysis_state.message = ""
                        # Re-enable the button regardless of outcome
                        analyse_btn.set_enabled(True)

                analyse_btn.on_click(on_analyse)

                # Separator + strategy expansion inside the card — strategy
                # configuration expands in context, not as a separate surface.
                ui.separator()
                strategy_panel(strategy_state)

            # ------------------------------------------------------------------
            # Zone 3 — Progress panel and result card
            # ------------------------------------------------------------------
            progress_panel(analysis_state)


if __name__ == "__main__":
    import uvicorn
    create_ui()
    ui.run_with(app)
    uvicorn.run(app, host="0.0.0.0", port=settings.PORT)
