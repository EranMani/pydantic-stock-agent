"""Analysis progress panel — skeleton loading state, error banner, and result card.

Shows a QSkeleton card while an analysis is running (replacing the previous
plain spinner), a QBanner for error states, and the full report card when
analysis completes.

The skeleton card mirrors the report card layout — header row, gauge row,
summary rows — so the user has spatial context about what is loading. This
is a strict improvement over a generic spinner: users know what the result
will look like and where to look when it arrives.

The QBanner error state is semantically correct (a banner is the right
component for persistent, dismissible-ish inline messages) and visually
distinct from the rest of the panel without relying on a plain red label.

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


def _skeleton_card() -> None:
    """Render a QSkeleton placeholder matching the report card layout.

    Shown while is_running is True. Mirrors the structure of report_card.py
    so the user has spatial context about what is loading — a flat card with:
      - Header row: ticker name placeholder + recommendation badge placeholder
      - Score gauges row: three circle skeletons (matching QCircularProgress)
      - Summary section: three text-line skeletons

    q-skeleton type values used:
      "text"   — variable-width inline text block (full width by default)
      "circle" — perfect circle, matched to the 80px gauge size
      "QBadge" — pill-shaped block matching QBadge dimensions

    Uses ui.element("q-skeleton") with Quasar props via .props() —
    NiceGUI's standard pattern for Quasar elements without a dedicated wrapper.
    """
    with ui.card().props("flat").classes("w-full p-6 gap-4 bg-gray-800"):
        # Header row — ticker label placeholder + badge placeholder
        with ui.row().classes("w-full justify-between items-center"):
            ui.element("q-skeleton").props('type=text width="120px" height="32px"')
            ui.element("q-skeleton").props('type=QBadge width="80px"')

        ui.separator()

        # Score gauges row — three circle skeletons matching 80px QCircularProgress
        with ui.row().classes("w-full justify-around py-2"):
            for _ in range(3):
                with ui.column().classes("items-center gap-1"):
                    ui.element("q-skeleton").props('type=circle size="80px"')
                    ui.element("q-skeleton").props('type=text width="60px" height="14px"')

        ui.separator()

        # Summary text skeleton — three lines suggesting a paragraph
        with ui.column().classes("w-full gap-2"):
            ui.element("q-skeleton").props("type=text")
            ui.element("q-skeleton").props("type=text")
            ui.element("q-skeleton").props('type=text width="70%"')


def progress_panel(state: AnalysisState) -> None:
    """Render the analysis progress panel bound to state.

    Shows a QSkeleton card while is_running is True — replaces the previous
    spinner + status label. The skeleton mirrors the report card layout so
    the user has spatial context about what is loading.

    Shows a QBanner for error states — semantically correct, visually distinct
    from the result card. The banner is bound to state.error and only visible
    when an error exists.

    Renders the full report card when result is set.

    Uses only NiceGUI Python API — no HTML, CSS, or JavaScript.
    """
    with ui.column().classes("w-full gap-2"):

        # --- Skeleton loading state (visible while running) ---
        # bind_visibility_from shows this when is_running is True.
        # Replaces the previous spinner + status label. The skeleton gives
        # spatial context — users see the layout taking shape.
        skeleton_container = ui.column().classes("w-full").bind_visibility_from(
            state, "is_running"
        )
        with skeleton_container:
            _skeleton_card()

        # --- Error banner (visible when error is set) ---
        # ui.element("q-banner") is the correct Quasar component for persistent
        # inline messages. dense + rounded keeps it compact; bg-red-900 and
        # text-red-200 match the dark-mode danger palette from theme.py.
        # bind_visibility_from(state, "error") uses Python's truthiness — None
        # and empty string are both falsy, so the banner hides cleanly.
        with ui.element("q-banner").props("dense rounded").classes(
            "w-full bg-red-900 text-red-200 rounded-lg"
        ).bind_visibility_from(state, "error"):
            with ui.row().classes("items-center gap-3 p-3"):
                ui.icon("error_outline").classes("text-red-400 text-xl")
                ui.label().bind_text_from(
                    state, "error", backward=lambda e: e if e else ""
                ).classes("text-sm text-red-200")

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
