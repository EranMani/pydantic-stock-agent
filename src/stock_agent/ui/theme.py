"""UI theme — dark mode configuration and shared visual constants.

Single source of truth for all visual decisions. Import colour constants
into any component that needs them. Call apply_theme() at the top of
every @ui.page function to apply the dark theme to that session.

Why a dedicated theme.py:
  If the colour scheme changes, only this file changes — no hunting through
  component files. Same principle as config.py for application constants.

Public API:
  COLOURS        — dict of semantic colour roles → Tailwind class fragments
  apply_theme()  — enables dark mode for the current page session
"""

from nicegui import ui

# Semantic colour palette — Tailwind class fragments used across components.
# Use as: ui.label("text").classes(f"text-{COLOURS['muted']}")
COLOURS: dict[str, str] = {
    "primary":    "indigo-500",
    "primary_bg": "indigo-600",
    "success":    "green-500",
    "warning":    "yellow-500",
    "danger":     "red-500",
    "muted":      "gray-400",
    "heading":    "gray-100",
    "body":       "gray-300",
}

# Recommendation badge classes — duplicated here as the canonical definition;
# report_card.py and peer_table.py import from here in future refactors.
RECOMMENDATION_BADGE: dict[str, str] = {
    "BUY":   "bg-green-100 text-green-800",
    "WATCH": "bg-yellow-100 text-yellow-800",
    "AVOID": "bg-red-100 text-red-800",
}


def apply_theme() -> None:
    """Apply the dark theme to the current NiceGUI page session.

    Must be called inside a @ui.page function — NiceGUI applies theme
    settings per browser session, not globally at server startup.
    """
    ui.dark_mode().enable()
