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

# Recommendation badge colours — matches report_card.py
_BADGE: dict[str, str] = {
    "BUY":   "bg-green-100 text-green-800",
    "WATCH": "bg-yellow-100 text-yellow-800",
    "AVOID": "bg-red-100 text-red-800",
}


def peer_table(peers: list[PeerReport]) -> None:
    """Render a peer comparison table from a list of PeerReport objects.

    Shows ticker, weighted score, and a coloured recommendation badge
    for each peer. Renders a placeholder label when the peers list is
    empty — peer discovery is currently non-functional (TASK-003).

    Uses only NiceGUI Python API — no HTML, CSS, or JavaScript.
    """
    if not peers:
        ui.label("No peer data available.").classes("text-sm text-gray-400 italic")
        return

    with ui.column().classes("w-full gap-1"):
        # Header row
        with ui.row().classes("w-full px-2 py-1 bg-gray-50 rounded text-xs font-semibold text-gray-500 uppercase tracking-wide"):
            ui.label("Ticker").classes("w-24")
            ui.label("Score").classes("w-20 text-center")
            ui.label("Rating").classes("flex-1 text-center")

        # Data rows
        for peer in peers:
            badge_classes = _BADGE.get(peer.recommendation, "bg-gray-100 text-gray-800")
            with ui.row().classes("w-full px-2 py-2 items-center border-b border-gray-100"):
                ui.label(peer.ticker).classes("w-24 text-sm font-medium")
                ui.label(f"{peer.weighted_score:.1f} / 10").classes("w-20 text-sm text-center")
                with ui.row().classes("flex-1 justify-center"):
                    ui.label(peer.recommendation).classes(
                        f"px-3 py-0.5 rounded-full text-xs font-semibold {badge_classes}"
                    )
