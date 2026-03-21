"""Analysis progress panel — spinner, status message, and minimal result display.

Shows a spinner + status label while an analysis is running, and a basic
result card when it completes. Step 34 replaces the inline result display
with a dedicated report_card.py component.

Phase 9 will replace the synchronous call pattern with a real-time Redis
progress bar (polling job:{job_id}:progress every second via ui.timer).
The AnalysisState container and panel structure are designed to support
that transition without interface changes.

Public API:
  AnalysisState  — mutable container holding running/result/error state
  progress_panel(state) — renders the NiceGUI panel and binds it to state
"""

from nicegui import ui

from stock_agent.models.report import StockReport
from stock_agent.ui.components.report_card import report_card


class AnalysisState:
    """Mutable container for the current analysis run state.

    Attributes are updated by the async analyse handler in app.py.
    NiceGUI's bind_*_from() polls these attributes to keep UI in sync.
    """

    def __init__(self) -> None:
        """Initialise with idle state — no analysis running or completed."""
        self.is_running: bool = False
        self.message: str = ""
        self.result: StockReport | None = None
        self.error: str | None = None


def progress_panel(state: AnalysisState) -> None:
    """Render the analysis progress panel bound to state.

    Shows a spinner while is_running is True. Renders a minimal result
    card when result is set, or an error label when error is set.
    Uses only NiceGUI Python API — no HTML, CSS, or JavaScript.
    """
    with ui.column().classes("w-full gap-2"):

        # --- Spinner + status (visible while running) ---
        with ui.row().classes("items-center gap-3 py-2").bind_visibility_from(
            state, "is_running"
        ):
            ui.spinner(size="sm")
            ui.label().bind_text_from(state, "message").classes("text-sm text-gray-600")

        # --- Error display ---
        error_label = ui.label().classes("text-sm text-red-500")
        error_label.bind_text_from(state, "error", backward=lambda e: f"Error: {e}" if e else "")
        error_label.bind_visibility_from(state, "error", backward=lambda e: bool(e))

        # --- Full report card (from report_card.py) ---
        @ui.refreshable
        def result_section() -> None:
            """Render the full StockReport card — rebuilt whenever .refresh() is called."""
            if state.result is not None:
                report_card(state.result)

        result_section()

        # Refresh the result section whenever a result arrives
        def _maybe_refresh() -> None:
            """Trigger result_section refresh when analysis completes."""
            if state.result is not None and not state.is_running:
                result_section.refresh()

        ui.timer(0.2, _maybe_refresh)
