"""NiceGUI web application — entry point for the UI server.

Mounts NiceGUI onto the existing FastAPI app from api.py so both the
REST API (POST /analyze) and the NiceGUI web UI share a single server
on the same port. No separate process or port required.

Entry point:
  uv run python -m stock_agent.ui.app

Dashboard layout (Step 32):
  / — ticker input + scoring weight sliders; state bound to a live
      ScoringStrategy instance before any API call is made.
"""

from nicegui import ui

from stock_agent.api import app
from stock_agent.config import settings
from stock_agent.ui.components.strategy_panel import StrategyState, strategy_panel


def create_ui() -> None:
    """Register all NiceGUI pages and components on the shared FastAPI app.

    Called once at startup before ui.run_with(). Steps 33-37 will add
    the analysis trigger, progress panel, and report card to this page.
    """
    @ui.page("/")
    def index() -> None:
        """Main dashboard — ticker input and scoring weight configuration."""
        # Page-level state — one instance per browser session
        state = StrategyState()

        with ui.column().classes("w-full max-w-2xl mx-auto p-6 gap-4"):
            # Header
            ui.label("Stock Agent").classes("text-2xl font-bold")
            ui.label("Autonomous PydanticAI stock analyst").classes("text-sm text-gray-500")

            # Ticker input
            with ui.card().classes("w-full"):
                ui.label("Ticker Symbol").classes("text-base font-semibold mb-2")
                ticker_input = ui.input(
                    placeholder="e.g. AAPL, NVDA, ONDS",
                ).classes("w-full")

            # Scoring weight sliders
            strategy_panel(state)

            # Debug readout — shows live ScoringStrategy state (removed in Step 33)
            strategy_display = ui.label(
                f"Strategy: {state.to_scoring_strategy().model_dump_json()}"
            ).classes("text-xs text-gray-400")

            def refresh_strategy_display() -> None:
                """Refresh debug readout when strategy state changes."""
                strategy_display.set_text(
                    f"Strategy: {state.to_scoring_strategy().model_dump_json()}"
                )

            # Wire slider changes to the debug display
            # Step 33 replaces this with the real analysis trigger
            ui.timer(0.3, refresh_strategy_display)


if __name__ == "__main__":
    import uvicorn
    create_ui()
    ui.run_with(app)
    uvicorn.run(app, host="0.0.0.0", port=settings.PORT)
