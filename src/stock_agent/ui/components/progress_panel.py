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


# Recommendation badge colours
_BADGE_COLOUR: dict[str, str] = {
    "BUY":   "bg-green-100 text-green-800",
    "WATCH": "bg-yellow-100 text-yellow-800",
    "AVOID": "bg-red-100 text-red-800",
}


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

        # --- Minimal result card (replaced by report_card.py in Step 34) ---
        @ui.refreshable
        def result_card() -> None:
            """Render a minimal result card — rebuilt whenever .refresh() is called."""
            if state.result is None:
                return

            r = state.result
            colour = _BADGE_COLOUR.get(r.recommendation, "")

            with ui.card().classes("w-full"):
                with ui.row().classes("items-center justify-between w-full"):
                    ui.label(r.ticker).classes("text-xl font-bold")
                    ui.label(r.recommendation).classes(
                        f"px-3 py-1 rounded-full text-sm font-semibold {colour}"
                    )

                with ui.row().classes("gap-6 mt-2"):
                    ui.label(f"Weighted Score: {r.weighted_score:.2f} / 10").classes("text-sm")
                    ui.label(f"Fundamental: {r.fundamental_score:.2f}").classes("text-sm text-gray-500")
                    ui.label(f"Technical: {r.technical_score:.2f}").classes("text-sm text-gray-500")

                ui.separator()
                ui.label(r.summary).classes("text-sm text-gray-700 mt-2")

        result_card()

        # Refresh the result card whenever state.result changes
        # ui.timer checks every 0.2s — replaced by event-driven refresh in Step 34
        def _maybe_refresh() -> None:
            """Trigger result_card refresh when a result arrives."""
            if state.result is not None and not state.is_running:
                result_card.refresh()

        ui.timer(0.2, _maybe_refresh)
