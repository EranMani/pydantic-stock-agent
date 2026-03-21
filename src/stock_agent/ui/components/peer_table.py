"""Peer comparison table component.

Renders a list[PeerReport] as a QTable (ui.table) with custom cell slots
for the recommendation badge and score colouring. Extracted from report_card.py
so it can be rendered independently (e.g. on a separate tab or refreshed
without rebuilding the full report card).

QTable gives us sortable columns, proper dark-mode styling via the "dark" prop,
and native slot injection for custom cell rendering — all with less code than
the previous manual row construction.

The body-cell-rec slot uses a q-chip with Quasar semantic colors (positive /
negative / warning) rather than Tailwind classes — these are theme-aware and
resolve correctly in both light and dark mode without requiring hardcoded hex.

The body-cell-score slot applies color classes based on threshold so the score
number is visually coded to green / yellow / red to match the circular gauges
in the report card above. The " / 10" suffix is rendered inline in the slot.

Note: table.add_slot() injects a Vue template string into the Quasar QTable's
named slot. This is NiceGUI's documented pattern for custom cell rendering —
it is NOT creating a separate HTML/CSS file. The string is passed as a prop
to the Quasar component and rendered by the Vue runtime in the browser.

Public API:
  peer_table(peers) — renders the peer comparison table, or a placeholder
                      label if the peers list is empty.
"""

from nicegui import ui

from stock_agent.models.report import PeerReport
from stock_agent.ui.theme import COLOURS


def peer_table(peers: list[PeerReport]) -> None:
    """Render a peer comparison table from a list of PeerReport objects.

    Shows ticker, weighted score (colour-coded), and a recommendation badge
    (QChip with Quasar semantic color) for each peer. Renders a placeholder
    label when the peers list is empty — peer discovery is currently
    non-functional (TASK-003).

    Uses ui.table() (QTable) with add_slot() for custom cell rendering.
    Props: flat (no Quasar shadow), dense (compact rows), dark (dark-mode
    palette), hide-bottom (removes the "X rows" pagination footer — not
    needed for this small peer list).

    Uses only NiceGUI Python API — no HTML, CSS, or JavaScript files.
    """
    if not peers:
        ui.label("No peer data available.").classes(f"text-sm text-{COLOURS['muted']} italic")
        return

    columns = [
        {
            "name":     "ticker",
            "label":    "Ticker",
            "field":    "ticker",
            "align":    "left",
            "sortable": True,
        },
        {
            "name":     "score",
            "label":    "Score",
            "field":    "weighted_score",
            "align":    "center",
            "sortable": True,
        },
        {
            "name":     "rec",
            "label":    "Recommendation",
            "field":    "recommendation",
            "align":    "center",
            "sortable": False,
        },
    ]

    rows = [
        {
            "ticker":         p.ticker,
            "weighted_score": round(p.weighted_score, 1),
            "recommendation": p.recommendation,
        }
        for p in peers
    ]

    table = ui.table(columns=columns, rows=rows, row_key="ticker")
    table.props("flat dense dark hide-bottom")
    table.classes("w-full")

    # Custom recommendation cell — QChip with Quasar semantic colors.
    # positive → green, negative → red, warning → yellow.
    # These are Quasar's own semantic palette names — theme-aware,
    # consistent with how Quasar resolves color tokens in dark mode.
    table.add_slot("body-cell-rec", """
        <q-td :props="props">
            <q-chip
                :color="props.value === 'BUY' ? 'positive' : props.value === 'AVOID' ? 'negative' : 'warning'"
                text-color="white"
                dense
                square
            >{{ props.value }}</q-chip>
        </q-td>
    """)

    # Custom score cell — colour-coded number matching the circular gauge thresholds.
    # >= 7: green-400, >= 4: yellow-400, < 4: red-400.
    # The " / 10" suffix is rendered inline so the column is self-explanatory.
    table.add_slot("body-cell-score", """
        <q-td :props="props">
            <span
                :class="props.value >= 7 ? 'text-green-400' : props.value >= 4 ? 'text-yellow-400' : 'text-red-400'"
                class="font-semibold"
            >{{ props.value }} / 10</span>
        </q-td>
    """)
