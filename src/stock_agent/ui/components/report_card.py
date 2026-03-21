"""StockReport display card — score gauges, recommendation badge, and analyst summary.

Renders a full StockReport as a structured NiceGUI card. Replaces the
minimal inline result display added in Step 33's progress_panel.py.

Public API:
  report_card(report) — renders the full StockReport card
"""

from nicegui import ui

from stock_agent.models.report import StockReport

# Recommendation badge: background + text colour classes
_BADGE: dict[str, str] = {
    "BUY":   "bg-green-100 text-green-800",
    "WATCH": "bg-yellow-100 text-yellow-800",
    "AVOID": "bg-red-100 text-red-800",
}

# Score gauge colours by theshold
_GAUGE_COLOUR = {
    "high":   "text-green-600",
    "medium": "text-yellow-600",
    "low":    "text-red-600",
}


def _score_colour(score: float) -> str:
    """Return a Tailwind text colour class based on score value (1–10)."""
    if score >= 7.0:
        return _GAUGE_COLOUR["high"]
    if score >= 4.0:
        return _GAUGE_COLOUR["medium"]
    return _GAUGE_COLOUR["low"]


def _score_gauge(label: str, score: float) -> None:
    """Render a labelled progress bar for a single score value.

    Score is in [1.0, 10.0] — normalised to [0.0, 1.0] for ui.linear_progress.
    """
    normalised = max(0.0, min(1.0, (score - 1.0) / 9.0))
    colour_class = _score_colour(score)

    with ui.row().classes("w-full items-center gap-3"):
        ui.label(label).classes("w-32 text-sm text-gray-600")
        ui.linear_progress(value=normalised).classes("flex-1")
        ui.label(f"{score:.1f} / 10").classes(f"w-16 text-sm font-semibold text-right {colour_class}")


def report_card(report: StockReport) -> None:
    """Render the full StockReport as a structured NiceGUI card.

    Sections:
      1. Header — ticker, recommendation badge, analysis date
      2. Score gauges — weighted, fundamental, technical
      3. Analyst summary — LLM-generated narrative
      4. Peer table — comparison table (hidden if no peers)

    Uses only NiceGUI Python API — no HTML, CSS, or JavaScript.
    """
    badge_classes = _BADGE.get(report.recommendation, "bg-gray-100 text-gray-800")

    with ui.card().classes("w-full gap-3"):

        # --- Header ---
        with ui.row().classes("w-full items-center justify-between"):
            with ui.column().classes("gap-0"):
                ui.label(report.ticker).classes("text-2xl font-bold")
                ui.label(
                    report.analysis_date.strftime("%Y-%m-%d %H:%M UTC")
                ).classes("text-xs text-gray-400")
            ui.label(report.recommendation).classes(
                f"px-4 py-1 rounded-full text-sm font-bold {badge_classes}"
            )

        ui.separator()

        # --- Score gauges ---
        ui.label("Scores").classes("text-sm font-semibold text-gray-500 uppercase tracking-wide")
        _score_gauge("Weighted", report.weighted_score)
        _score_gauge("Fundamental", report.fundamental_score)
        _score_gauge("Technical", report.technical_score)

        ui.separator()

        # --- Analyst summary ---
        ui.label("Analyst Summary").classes("text-sm font-semibold text-gray-500 uppercase tracking-wide")
        ui.label(report.summary).classes("text-sm text-gray-700 leading-relaxed")

        # --- Peer comparison table (only if peers exist) ---
        if report.peers:
            ui.separator()
            ui.label("Peer Comparison").classes("text-sm font-semibold text-gray-500 uppercase tracking-wide")

            columns = [
                {"name": "ticker", "label": "Ticker", "field": "ticker", "align": "left"},
                {"name": "score",  "label": "Score",  "field": "score",  "align": "center"},
                {"name": "rec",    "label": "Rating", "field": "rec",    "align": "center"},
            ]
            rows = [
                {
                    "ticker": p.ticker,
                    "score":  f"{p.weighted_score:.1f}",
                    "rec":    p.recommendation,
                }
                for p in report.peers
            ]
            ui.table(columns=columns, rows=rows).classes("w-full text-sm")
