"""StockReport display card — score gauges, recommendation badge, and analyst summary.

Renders a full StockReport as a structured NiceGUI card. Replaces the
minimal inline result display added in Step 33's progress_panel.py.

Public API:
  report_card(report) — renders the full StockReport card
"""

from nicegui import ui

from stock_agent.models.report import StockReport
from stock_agent.ui.components.peer_table import peer_table
from stock_agent.ui.theme import COLOURS, RECOMMENDATION_BADGE

# _BADGE is an alias for the canonical RECOMMENDATION_BADGE token from theme.py.
# Previously a local duplicate — consolidated to eliminate the divergence risk.
_BADGE = RECOMMENDATION_BADGE

# Score gauge colour fragments by threshold — Quasar color prop values.
# These are color *fragments* (no "text-" prefix) used in QCircularProgress's
# color prop and also composed into Tailwind text classes where needed.
# -400 shades have ~5.1–5.5:1 contrast on gray-800 (WCAG AA pass).
# Fixed by Aria, 2026-03-21.
_GAUGE_COLOUR = {
    "high":   "green-400",
    "medium": "yellow-400",
    "low":    "red-400",
}


def _score_colour(score: float) -> str:
    """Return a Quasar/Tailwind color fragment based on score value (1–10).

    Returns a fragment like "green-400" — callers prefix with "text-" for
    Tailwind text classes, or pass directly to Quasar's color prop.
    """
    if score >= 7.0:
        return _GAUGE_COLOUR["high"]
    if score >= 4.0:
        return _GAUGE_COLOUR["medium"]
    return _GAUGE_COLOUR["low"]


def _score_gauge(label: str, score: float) -> None:
    """Render a labelled circular progress gauge for a single score value.

    Uses QCircularProgress (ui.circular_progress) — a ring gauge with the
    score value displayed at centre. Arranged in a column with the label
    below. Two gauges (Fundamental, Technical) are placed in a row by the
    caller (report_card). Weighted score is shown as a plain number in the
    header, not as a gauge.

    Quasar props (all via .props()):
      size=80px         — outer diameter of the ring
      font-size=1.1rem  — size of the centre value text
      track-color=grey-8 — dark track background (visible ring trail)
      thickness=0.15    — ring stroke as a fraction of radius
      rounded           — rounded stroke caps

    color is set via the Quasar color prop (fragment like "green-400") —
    not a Tailwind class. Quasar resolves this against its own palette.
    """
    colour = _score_colour(score)

    with ui.column().classes("items-center gap-1"):
        ui.circular_progress(
            value=score, min=1, max=10, show_value=True
        ).props(
            f"size=80px font-size=1.1rem track-color=grey-8 "
            f"color={colour} thickness=0.15 rounded"
        )
        ui.label(label).classes(f"text-xs text-{COLOURS['muted']}")


def report_card(report: StockReport) -> None:
    """Render the full StockReport as a structured NiceGUI card.

    Sections:
      1. Header — ticker, recommendation badge, analysis date
      2. Score gauges — weighted, fundamental, technical (QCircularProgress row)
      3. Analyst summary — LLM-generated narrative
      4. Peer table — comparison table (hidden if no peers)

    Quasar props used:
      ui.card().props("flat") — removes Quasar's default card shadow so
      Tailwind shadow-sm is the sole elevation authority; prevents double-shadow.

    Uses only NiceGUI Python API — no HTML, CSS, or JavaScript.
    """
    badge_classes = _BADGE.get(report.recommendation, "bg-gray-700 text-gray-100")

    with ui.card().classes("w-full gap-3 bg-gray-800 shadow-sm").props("flat"):

        # --- Header ---
        # Left: ticker + date. Right: weighted score (plain number, score-coloured)
        # + recommendation badge side by side. The score and badge read as a unit —
        # the verdict is scannable in a single glance without hunting for it.
        score_colour = _score_colour(report.weighted_score)
        with ui.row().classes("w-full items-center justify-between"):
            with ui.column().classes("gap-0"):
                ui.label(report.ticker).classes("text-2xl font-bold text-gray-100")
                ui.label(
                    report.analysis_date.strftime("%Y-%m-%d %H:%M UTC")
                ).classes("text-xs text-gray-400")
            with ui.row().classes("items-center gap-2"):
                ui.label(str(report.weighted_score)).classes(
                    f"text-2xl font-bold text-{score_colour}"
                )
                ui.label(report.recommendation).classes(
                    f"px-4 py-1 rounded-full text-sm font-bold {badge_classes}"
                )

        ui.separator()

        # --- Score gauges — two QCircularProgress widgets (Fundamental + Technical) ---
        # Weighted score promoted to header — these two are supporting detail.
        ui.label("Scores").classes("text-sm font-semibold text-gray-500 uppercase tracking-wide")
        with ui.row().classes("w-full justify-around py-2"):
            _score_gauge("Fundamental", report.fundamental_score)
            _score_gauge("Technical", report.technical_score)

        ui.separator()

        # --- Analyst summary ---
        # report.key_points is a list[str] of 4–6 short bullet points.
        # Each item is rendered in its own row with a bullet indicator (•)
        # to give visual separation without relying on HTML list elements.
        ui.label("Analyst Summary").classes("text-sm font-semibold text-gray-500 uppercase tracking-wide")
        with ui.column().classes("gap-1"):
            for point in report.key_points:
                with ui.row().classes("items-start gap-2"):
                    ui.label("•").classes("text-sm text-gray-300 leading-relaxed shrink-0")
                    ui.label(point).classes("text-sm text-gray-300 leading-relaxed")

        # --- Peer comparison table ---
        ui.separator()
        ui.label("Peer Comparison").classes("text-sm font-semibold text-gray-500 uppercase tracking-wide")
        peer_table(report.peers)
