"""UI theme — dark mode configuration and shared visual constants.

Single source of truth for all visual decisions. Import any constant into
any component that needs it. Call apply_theme() at the top of every
@ui.page function to apply the dark theme to that session.

Why a dedicated theme.py:
  If the colour scheme changes, only this file changes — no hunting through
  component files. Same principle as config.py for application constants.

Design token layers:
  COLOURS            — semantic colour roles → Tailwind color fragments
                       Use as: f"text-{COLOURS['muted']}"  or  f"bg-{COLOURS['primary_bg']}"
  TYPOGRAPHY         — semantic type composites → full Tailwind class strings
                       Use as: ui.label("x").classes(TYPOGRAPHY["section_label"])
  SPACING            — semantic spacing tokens → Tailwind gap/padding classes
                       Use as: ui.column().classes(SPACING["section_gap"])
  RADIUS             — border radius scale → Tailwind rounded classes
  SHADOW             — elevation scale → Tailwind shadow classes
  TRANSITIONS        — motion tokens → Tailwind transition + duration classes
  RECOMMENDATION_BADGE — badge classes keyed by recommendation value

Public API:
  apply_theme()      — enables dark mode for the current page session
"""

from nicegui import ui

# ---------------------------------------------------------------------------
# Colour tokens — Tailwind color *fragments* (no text-/bg- prefix).
# Apply as: f"text-{COLOURS['heading']}"  or  f"bg-{COLOURS['primary_bg']}"
# ---------------------------------------------------------------------------
COLOURS: dict[str, str] = {
    # Brand
    "primary":        "indigo-500",
    "primary_bg":     "indigo-600",    # solid brand button fill
    "primary_subtle": "indigo-50",     # brand tint (light); use indigo-950 for dark tint

    # Feedback
    "success":        "green-500",
    "success_subtle": "green-50",
    "warning":        "yellow-500",
    "warning_subtle": "yellow-50",
    "danger":         "red-500",
    "danger_subtle":  "red-50",

    # Text hierarchy (dark-mode optimised — white-on-dark)
    "heading":        "gray-100",      # primary headings on dark background
    "body":           "gray-300",      # body copy on dark background
    "muted":          "gray-400",      # secondary / supporting text
    "subtle":         "gray-500",      # captions, disabled text

    # Surface (dark-mode)
    "surface":        "gray-800",      # card / panel background
    "surface_raised": "gray-700",      # elevated surface (hover, dropdown)
    "border":         "gray-700",      # dividers and borders
}

# ---------------------------------------------------------------------------
# Typography tokens — full Tailwind class strings (size + weight + spacing).
# Apply as: ui.label("x").classes(TYPOGRAPHY["section_label"])
# ---------------------------------------------------------------------------
TYPOGRAPHY: dict[str, str] = {
    # Semantic composites
    "page_title":    "text-3xl font-bold tracking-tight",
    "section_label": "text-xs font-semibold uppercase tracking-wide",
    "card_title":    "text-xl font-semibold",
    "body":          "text-sm leading-relaxed",
    "caption":       "text-xs",
    "badge":         "text-xs font-semibold uppercase tracking-wide",

    # Size-only scale (combine with weight/color as needed)
    "xs":   "text-xs",     # 12px — labels, metadata
    "sm":   "text-sm",     # 14px — secondary text
    "base": "text-base",   # 16px — body (never below this for reading text)
    "lg":   "text-lg",     # 18px — lead paragraphs
    "xl":   "text-xl",     # 20px — card headings
    "2xl":  "text-2xl",    # 24px — section headings
    "3xl":  "text-3xl",    # 30px — page headings
    "4xl":  "text-4xl",    # 36px — hero headings
}

# ---------------------------------------------------------------------------
# Spacing tokens — Tailwind gap / padding classes.
# Apply as: ui.column().classes(f"w-full {SPACING['section_gap']}")
# ---------------------------------------------------------------------------
SPACING: dict[str, str] = {
    # Gap variants (for ui.row / ui.column / ui.grid)
    "tight_gap":      "gap-2",     # 8px  — tight component internals
    "compact_gap":    "gap-3",     # 12px — compact sections
    "component_gap":  "gap-4",     # 16px — standard between elements
    "section_gap":    "gap-6",     # 24px — between major sections
    "page_gap":       "gap-8",     # 32px — between top-level blocks

    # Padding variants (for cards, panels)
    "card_padding":   "p-4",       # 16px — standard card
    "card_padding_lg":"p-6",       # 24px — roomy card / panel
    "page_padding":   "px-4 py-6", # page edge breathing room
}

# ---------------------------------------------------------------------------
# Border radius tokens — Tailwind rounded classes.
# This project uses a rounded personality (8-12px). Do not mix freely.
# ---------------------------------------------------------------------------
RADIUS: dict[str, str] = {
    "sm":   "rounded",       # 4px   — small badges, tight inputs
    "md":   "rounded-lg",    # 8px   — buttons, standard cards
    "lg":   "rounded-xl",    # 12px  — larger cards, panels
    "xl":   "rounded-2xl",   # 16px  — feature panels
    "full": "rounded-full",  # pill  — status badges, avatars
}

# ---------------------------------------------------------------------------
# Shadow / elevation tokens — Tailwind shadow classes.
# Maximum 2 levels in active use at any time to avoid elevation chaos.
# ---------------------------------------------------------------------------
SHADOW: dict[str, str] = {
    "sm": "shadow-sm",   # subtle lift — cards at rest
    "md": "shadow-md",   # moderate lift — hovered cards, dropdowns
    "lg": "shadow-lg",   # strong lift — modals, popovers
}

# ---------------------------------------------------------------------------
# Transition tokens — Tailwind transition + duration classes.
# NiceGUI has no animation API; all motion is via these Tailwind utilities.
# ---------------------------------------------------------------------------
TRANSITIONS: dict[str, str] = {
    "fast":   "transition duration-100",   # instant feedback — button press
    "normal": "transition duration-200",   # micro-interactions — toggle, check
    "slow":   "transition duration-300",   # small transitions — dropdown
}

# ---------------------------------------------------------------------------
# Recommendation badge — full Tailwind class strings keyed by enum value.
# Canonical definition: report_card.py and peer_table.py import from here.
# ---------------------------------------------------------------------------
RECOMMENDATION_BADGE: dict[str, str] = {
    "BUY":   "bg-green-100 text-green-800",
    "WATCH": "bg-yellow-100 text-yellow-800",
    "AVOID": "bg-red-100 text-red-800",
}

# ---------------------------------------------------------------------------
# Pill button states — metric toggle pills in the strategy panel.
# Two states only: PILL_ACTIVE (selected metric) and PILL_INACTIVE (unselected).
# Swapped on toggle via: b._classes.clear(); b.classes(PILL_ACTIVE or PILL_INACTIVE); b.update()
# Invariant classes (rounded-full, px-3, py-1, text-xs, font-medium, transition,
# duration-150, cursor-pointer) are repeated in both strings so a full replace is always safe.
# ---------------------------------------------------------------------------
PILL_ACTIVE: str = (
    "rounded-full px-3 py-1 text-xs font-medium "
    "transition duration-150 cursor-pointer "
    "bg-indigo-600 text-white"
)
PILL_INACTIVE: str = (
    "rounded-full px-3 py-1 text-xs font-medium "
    "transition duration-150 cursor-pointer "
    "bg-gray-700 text-gray-300 hover:bg-gray-600"
)


def apply_theme() -> None:
    """Apply the dark theme to the current NiceGUI page session.

    Must be called inside a @ui.page function — NiceGUI applies theme
    settings per browser session, not globally at server startup.
    """
    ui.dark_mode().enable()
