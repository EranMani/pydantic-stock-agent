"""StockReport display card — verdict panel, linear score bars, and analyst summary.

Renders a full StockReport as a structured NiceGUI card. Replaces the
minimal inline result display added in Step 33's progress_panel.py.

Design redesign (2026-03-22):
  - Verdict panel: deep gray-950 inset surface inside the gray-900 card.
    Ticker in display-scale type, weighted score as a 6xl number with glow,
    recommendation as an outlined pill (no fill — border + text only).
  - Linear progress bars replace QCircularProgress gauges — two horizontal
    bars (Fundamental, Technical) are faster to scan and less spatially heavy.
  - Separators removed — replaced with vertical spacing (gap-4 / py-3).
  - key_points rendered as sentiment-colored bullet rows (●) — emerald-400
    positive, rose-400 negative, gray-500 neutral; q-list removed to avoid
    Quasar item padding fighting the custom bullet layout.

Public API:
  report_card(report) — renders the full StockReport card
"""

from nicegui import ui

from stock_agent.models.report import KeyPoint, StockReport
from stock_agent.ui.components.peer_table import peer_table
from stock_agent.ui.theme import COLOURS, SCORE_COLOUR, SCORE_GLOW


def _score_colour(score: float) -> str:
    """Return a Tailwind/Quasar color fragment based on score value (1–10).

    Returns a fragment like "emerald-400" — callers prefix with "text-" for
    Tailwind text classes, or pass directly to Quasar's color prop.
    Thresholds: high ≥ 7.0, medium ≥ 4.0, low < 4.0.
    """
    if score >= 7.0:
        return SCORE_COLOUR["high"]
    if score >= 4.0:
        return SCORE_COLOUR["medium"]
    return SCORE_COLOUR["low"]


def _linear_bar(label: str, score: float) -> None:
    """Render a labelled QLinearProgress bar for a single score value.

    Layout:
      Label: metric name only (left-aligned, uppercase, subtle colour)
      Bar: full-width QLinearProgress below

    The numeric score label has been removed — the bar communicates the value
    visually. Less noise, cleaner scan.

    Value is normalised to 0–1 for QLinearProgress (score is on a 1–10 scale,
    so value = score / 10). Track colour grey-8 is Quasar's near-black swatch —
    visible as the unfilled track on gray-950/gray-900 surfaces.

    Quasar props:
      color          — Quasar color fragment for the filled portion
      track-color    — grey-8 (dark track, visible on dark surface)
      rounded-borders — pill-shaped bar ends
      size=8px       — bar height; 8px is the minimum for clear readability

    Uses ui.column / ui.row — no HTML, CSS, or JavaScript.
    """
    colour = _score_colour(score)
    with ui.column().classes("w-full gap-1"):
        ui.label(label).classes(f"text-xs font-semibold uppercase tracking-wide text-{COLOURS['subtle']}")
        ui.linear_progress(value=score / 10).props(
            f"color={colour} track-color=grey-8 rounded-borders size=8px"
        )


def _outlined_badge(recommendation: str, colour: str) -> None:
    """Render an outlined recommendation badge — border + text, no fill.

    Uses Tailwind border and text classes composed from the score colour
    fragment. The outlined style reads as a label, not a status chip —
    more appropriate for a summary verdict than a filled pill.

    Outline badge classes: border-2 rounded-full px-4 py-1 — matches
    the geometry of the old filled pill without the visual weight.
    """
    ui.label(recommendation).classes(
        f"border-2 border-{colour} text-{colour} rounded-full px-4 py-1 "
        f"text-sm font-bold"
    )


def report_card(report: StockReport) -> None:
    """Render the full StockReport as a structured NiceGUI card.

    Sections:
      1. Verdict panel — ticker, company name, date, weighted score with glow, outlined badge
      2. Score bars — Fundamental and Technical QLinearProgress bars (label only, no numeric)
      3. Analyst summary — key_points as sentiment-colored bullet rows
      4. Peer table — comparison table (hidden if no peers)

    Card surface: bg-gray-900 (one step above the gray-950 page body).
    Verdict inset: bg-gray-950 — deepest surface, creates inner contrast.
    No separators inside the card — vertical spacing (gap-4 / py-3) does the work.

    Uses only NiceGUI Python API — no HTML, CSS, or JavaScript.
    """
    score_colour = _score_colour(report.weighted_score)
    glow_style = SCORE_GLOW.get(report.recommendation, "")

    with ui.card().classes("w-full gap-4 bg-gray-900 shadow-sm").props("flat"):

        # ------------------------------------------------------------------
        # Verdict panel — dark inset surface, primary read target of the card
        # ------------------------------------------------------------------
        # The gray-950 inset sits inside the gray-900 card creating a subtle
        # depth plane. Ticker, date, score, and recommendation live here —
        # the user's eye lands here first and gets the complete verdict.
        with ui.element("div").classes("w-full bg-gray-950 rounded-xl p-5 gap-3 flex flex-col"):

            # Ticker + company name + date column
            with ui.column().classes("gap-0"):
                ui.label(report.ticker).classes(
                    "text-4xl font-black text-gray-50 tracking-tight"
                )
                ui.label(report.company_name).classes(
                    "text-xl font-medium text-gray-400"
                )
                ui.label(
                    report.analysis_date.strftime("%Y-%m-%d %H:%M UTC")
                ).classes("text-xs text-gray-500")

            # Weighted score + outlined recommendation badge
            with ui.row().classes("items-center gap-3 pt-1"):
                # 6xl score number with colour-matched glow via .style()
                ui.label(f"{report.weighted_score:.1f}").classes(
                    f"text-6xl font-black text-{score_colour}"
                ).style(glow_style)
                _outlined_badge(report.recommendation, score_colour)

        # ------------------------------------------------------------------
        # Score bars — Fundamental and Technical
        # ------------------------------------------------------------------
        with ui.column().classes("w-full gap-3 px-1"):
            _linear_bar("Fundamental", report.fundamental_score)
            _linear_bar("Technical", report.technical_score)

        # ------------------------------------------------------------------
        # Analyst summary — sentiment-colored bullet rows
        # ------------------------------------------------------------------
        # Each KeyPoint carries a sentiment classification. The bullet dot (●)
        # reflects that sentiment: emerald-400 positive, rose-400 negative,
        # gray-500 neutral. q-list/q-item removed — the Quasar item padding
        # fights with the custom bullet layout, creating uneven left margins.
        # A simple column of rows is flatter and gives us full layout control.
        _SENTIMENT_COLOUR: dict[str, str] = {
            "positive": "text-emerald-400",
            "negative": "text-rose-400",
            "neutral": "text-gray-500",
        }
        with ui.column().classes("w-full gap-2 px-1"):
            ui.label("Analyst Summary").classes(
                f"text-xs font-semibold uppercase tracking-wide text-{COLOURS['subtle']}"
            )
            with ui.column().classes("w-full gap-1"):
                for point in report.key_points:
                    bullet_colour = _SENTIMENT_COLOUR.get(point.sentiment, "text-gray-500")
                    with ui.row().classes("items-start gap-2"):
                        ui.label("●").classes(f"{bullet_colour} shrink-0")
                        ui.label(point.text).classes("text-sm text-gray-300")

        # ------------------------------------------------------------------
        # Peer comparison table
        # ------------------------------------------------------------------
        with ui.column().classes("w-full gap-2 px-1"):
            ui.label("Peer Comparison").classes(
                f"text-xs font-semibold uppercase tracking-wide text-{COLOURS['subtle']}"
            )
            peer_table(report.peers)
