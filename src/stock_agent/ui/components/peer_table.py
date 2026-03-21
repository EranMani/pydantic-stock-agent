"""Peer comparison table component.

Renders a list[PeerReport] as a styled table with coloured recommendation
badges per row. Extracted from report_card.py so it can be rendered
independently (e.g. on a separate tab or refreshed without rebuilding
the full report card).

Public API:
  peer_table(peers) — renders the peer comparison table, or a placeholder
                      label if the peers list is empty.
"""

from nicegui import ui

from stock_agent.models.report import PeerReport
from stock_agent.ui.theme import COLOURS, RECOMMENDATION_BADGE, TYPOGRAPHY


def peer_table(peers: list[PeerReport]) -> None:
    """Render a peer comparison table from a list of PeerReport objects.

    Shows ticker, weighted score, and a coloured recommendation badge
    for each peer. Renders a placeholder label when the peers list is
    empty — peer discovery is currently non-functional (TASK-003).

    Uses only NiceGUI Python API — no HTML, CSS, or JavaScript.
    """
    if not peers:
        ui.label("No peer data available.").classes(f"text-sm text-{COLOURS['muted']} italic")
        return

    with ui.column().classes("w-full gap-1"):
        # Header row — bg-gray-700 (surface_raised) is the correct dark-mode elevated surface
        with ui.row().classes(
            f"w-full px-2 py-1 bg-{COLOURS['surface_raised']} rounded "
            f"{TYPOGRAPHY['section_label']} text-{COLOURS['subtle']}"
        ):
            ui.label("Ticker").classes("w-24")
            ui.label("Score").classes("w-20 text-center")
            ui.label("Rating").classes("flex-1 text-center")

        # Data rows — border-gray-700 (border token) is visible on the dark surface
        for peer in peers:
            badge_classes = RECOMMENDATION_BADGE.get(
                peer.recommendation,
                f"bg-{COLOURS['surface_raised']} text-{COLOURS['body']}",
            )
            with ui.row().classes(
                f"w-full px-2 py-2 items-center border-b border-{COLOURS['border']}"
            ):
                ui.label(peer.ticker).classes(f"w-24 text-sm font-medium text-{COLOURS['body']}")
                ui.label(f"{peer.weighted_score:.1f} / 10").classes(
                    f"w-20 text-sm text-center text-{COLOURS['body']}"
                )
                with ui.row().classes("flex-1 justify-center"):
                    ui.label(peer.recommendation).classes(
                        f"px-3 py-0.5 rounded-full text-xs font-semibold {badge_classes}"
                    )
