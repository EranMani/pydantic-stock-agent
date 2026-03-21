"""NiceGUI web application — entry point for the UI server.

Mounts NiceGUI onto the existing FastAPI app from api.py so both the
REST API (POST /analyze) and the NiceGUI web UI share a single server
on the same port. No separate process or port required.

Entry point:
  uv run python -m stock_agent.ui.app

NiceGUI components are added in subsequent steps (Step 32+).
"""

from nicegui import ui

from stock_agent.api import app
from stock_agent.config import settings


def create_ui() -> None:
    """Register all NiceGUI pages and components on the shared FastAPI app.

    Called once at startup before ui.run_with(). Steps 32-37 will populate
    this function with dashboard layout, report cards, and progress panels.
    """
    @ui.page("/")
    def index() -> None:
        """Placeholder home page — replaced with full dashboard in Step 32."""
        ui.label("Stock Agent — coming soon.")


if __name__ == "__main__":
    create_ui()
    ui.run_with(
        app,
        port=settings.PORT,
        title="Stock Agent",
        reload=False,
    )
