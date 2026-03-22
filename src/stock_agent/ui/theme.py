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
  SCORE_COLOUR       — Tailwind color fragments keyed by score tier (high/medium/low)
  SCORE_GLOW         — raw drop-shadow style strings keyed by recommendation
  PAGE_BG            — Tailwind color fragment for the page body background

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
#
# Dark-mode badge design: bg-*-900 + text-*-300.
# This pairing passes WCAG AA on gray-800 card surfaces:
#   green-300 (#86EFAC) on green-900 (#14532D) ≈ 5.1:1 — AA pass
#   yellow-300 (#FDE047) on yellow-900 (#713F12) ≈ 5.4:1 — AA pass
#   red-300 (#FCA5A5) on red-900 (#7F1D1D) ≈ 4.8:1 — AA pass
# Previously bg-*-100 text-*-800 (light-mode only) — rendered as jarring
# light islands on dark card surfaces. Fixed by Aria, 2026-03-21.
# ---------------------------------------------------------------------------
RECOMMENDATION_BADGE: dict[str, str] = {
    "BUY":   "bg-green-900 text-green-300",
    "WATCH": "bg-yellow-900 text-yellow-300",
    "AVOID": "bg-red-900 text-red-300",
}

# ---------------------------------------------------------------------------
# Page background — deepest surface, one step darker than card surfaces.
# gray-950 gives cards (gray-900) and the verdict inset (gray-950) clear
# contrast without resorting to pure black. Use as: f"bg-{PAGE_BG}"
# ---------------------------------------------------------------------------
PAGE_BG: str = "gray-950"

# ---------------------------------------------------------------------------
# Score colour — Tailwind color fragments keyed by score tier.
# Shared across report_card.py and any future score display surface.
# Promoted from _GAUGE_COLOUR in report_card.py — it was always a design
# token masquerading as a local implementation detail.
#
# Colour rationale:
#   emerald-400 replaces green-400 — emerald reads richer and more distinct
#     on dark surfaces; green-400 sits slightly flat on gray-950.
#   yellow-400 — unchanged, it's the right amber for "caution" intent.
#   rose-400 replaces red-400 — rose is warmer and more intentional than raw
#     red on dark; pure red-400 is harsh without being more legible.
#
# Contrast checks (on gray-950 ≈ #030712):
#   emerald-400 (#34D399)  → ~7.2:1 — AAA
#   yellow-400  (#FACC15)  → ~10.4:1 — AAA
#   rose-400    (#FB7185)  → ~5.4:1 — AA
# ---------------------------------------------------------------------------
SCORE_COLOUR: dict[str, str] = {
    "high":   "emerald-400",   # score ≥ 7.0
    "medium": "yellow-400",    # score ≥ 4.0
    "low":    "rose-400",      # score < 4.0
}

# ---------------------------------------------------------------------------
# Score glow — raw CSS drop-shadow filter strings keyed by recommendation.
# Applied via .style() on the score label in the verdict panel.
# Not a Tailwind class — Tailwind has no drop-shadow with RGBA control at
# this precision. Raw style string is the correct tool here.
#
# Glow intent: a soft halo colour-matched to the recommendation outcome.
# Opacity 0.45 — present without dominating the typography.
# 24px spread — visible at a glance, doesn't bleed into adjacent elements.
# ---------------------------------------------------------------------------
SCORE_GLOW: dict[str, str] = {
    "BUY":   "filter: drop-shadow(0 0 24px rgba(52,211,153,0.45))",   # emerald glow
    "WATCH": "filter: drop-shadow(0 0 24px rgba(251,191,36,0.45))",   # yellow glow
    "AVOID": "filter: drop-shadow(0 0 24px rgba(251,113,133,0.45))",  # rose glow
}

# ---------------------------------------------------------------------------
# Header / toolbar tokens — full-bleed sticky header at the top of every page.
# Height is 56px (h-14). Content inside is constrained to max-w-2xl so it
# aligns visually with the body content column below.
#
# Design decisions:
#   - bg-gray-900: distinct from the near-black page body without fighting it.
#     Indigo tint was rejected — indigo is the primary CTA color; using it in
#     chrome creates hierarchy competition.
#   - border-b border-indigo-600: single accent thread tying header chrome to
#     the primary action color. Provides visual termination so header doesn't
#     bleed into content.
#   - fixed top-0 z-50: always visible; z-50 clears NiceGUI card surfaces.
#   - pt-14 on body: 56px offset to clear the fixed header.
#   - brand_sub removed: subtitle was visual clutter at 56px. At this height
#     the brand name alone is the right signal — the subtitle was doing nothing
#     except crowding the left side of a compact header.
# ---------------------------------------------------------------------------
HEADER: dict[str, str] = {
    "bar":          "fixed top-0 left-0 right-0 z-50 h-14 bg-gray-900 border-b border-indigo-600",
    "inner":        "w-full max-w-2xl mx-auto px-4 h-full flex items-center justify-between",
    "brand_name":   "text-base font-semibold tracking-tight text-gray-100",
    # brand_sub removed — subtitle was visual clutter in a fixed 56px header.
    # The brand name alone is sufficient; the subtitle added nothing at this scale.
    "status_dot":   "w-2 h-2 rounded-full bg-green-500 animate-pulse",
    "status_label": "text-xs text-gray-500 ml-1.5",
    "body_offset":  "pt-14",
}


def apply_theme() -> None:
    """Apply the dark theme to the current NiceGUI page session.

    Must be called inside a @ui.page function — NiceGUI applies theme
    settings per browser session, not globally at server startup.
    """
    ui.dark_mode().enable()
