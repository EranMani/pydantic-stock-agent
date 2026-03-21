"""NiceGUI web application — entry point for the UI server.

Mounts NiceGUI onto the existing FastAPI app from api.py so both the
REST API (POST /analyze) and the NiceGUI web UI share a single server
on the same port. No separate process or port required.

Entry point:
  uv run python -m stock_agent.ui.app

Dashboard layout (Steps 32-33):
  / — ticker input + scoring weight sliders + Analyse button.
      Calls POST /analyze via httpx, shows spinner while running,
      renders a minimal result card on completion.

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
from stock_agent.ui.theme import apply_theme


def create_ui() -> None:
    """Register all NiceGUI pages and components on the shared FastAPI app.

    Called once at startup before ui.run_with(). Steps 34-37 will add
    the full report card, peer table, and dev tools panel to this page.
    """
    @ui.page("/")
    def index() -> None:
        """Main dashboard — ticker input, weight config, and analysis trigger."""
        apply_theme()

        # Page-level state — one instance per browser session
        strategy_state = StrategyState()
        analysis_state = AnalysisState()

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
            strategy_panel(strategy_state)

            # Analyse button
            async def on_analyse() -> None:
                """Dispatch POST /analyze and update analysis_state with the result.

                Runs as an asyncio coroutine so the NiceGUI event loop stays
                responsive while the synchronous pipeline executes.
                Phase 9 replaces this with a Celery task dispatch + Redis polling.
                """
                ticker = ticker_input.value.strip().upper()
                if not ticker:
                    ui.notify("Enter a ticker symbol", type="warning")
                    return

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
                    analysis_state.error = f"API error {exc.response.status_code}: {exc.response.text}"
                except Exception as exc:
                    analysis_state.error = str(exc)
                finally:
                    analysis_state.is_running = False
                    analysis_state.message = ""

            ui.button("Analyse", on_click=on_analyse).classes("w-full")

            # Progress panel — spinner while running, result card when done
            progress_panel(analysis_state)


if __name__ == "__main__":
    import uvicorn
    create_ui()
    ui.run_with(app)
    uvicorn.run(app, host="0.0.0.0", port=settings.PORT)
