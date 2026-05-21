"""DESIGN.md → QSS bridge. Single source of truth for colors, fonts, and tokens.

Token assignment reference (kept inline so future contributors don't need
to re-derive which token lands on which surface):

    Color: deep        #1A1B23  → main window background
    Color: surface     #24252F  → cards, panels, output panel, dialog body
    Color: elevated    #2E2F3A  → sidebar, dialog title bars, splash background
    Color: hover       #363745  → card / button hover state
    Color: accent      #00E5CC  → primary buttons, active phase border, focus ring,
                                  brand mark, current dashboard tile highlight
    Color: accent_dim  rgba(0,229,204,0.15) → active sidebar item background,
                                              in-progress phase card fill
    Color: accent_glow rgba(0,229,204,0.30) → primary button + brand mark glow
    Color: success     #4ADE80  → phase complete, "AI features enabled", checks
    Color: warning     #FFB547  → thermal 75°C threshold, dashboard caution
    Color: error       #FF6B6B  → thermal 85°C threshold, phase failed, errors
    Color: text_primary   #E8E6E3 → all body text on dark surfaces (WCAG AA 14.5:1)
    Color: text_secondary #9B9AA0 → card labels, dim section titles (WCAG AA 5.1:1)
    Color: text_muted     #6B6A70 → status bar timestamps, meta text
    Color: border_default #363745 → terminal-style bordered panels
    Color: border_accent  rgba(0,229,204,0.25) → active phase border, focused inputs

AI slop guardrails (do/don't):
    ✓ DO use full borders on cards (DESIGN.md "terminal-style bordered panels")
    ✗ DON'T `border-left: 3px solid cyan` on cards (AI slop blacklist #8)
    ✓ DO left-align labels, right-align numeric values (terminal convention)
    ✗ DON'T center-align everything (AI slop blacklist #4)
    ✗ DON'T use emoji as design elements (AI slop blacklist #7); use Qt icons or text
    ✗ DON'T "Welcome to lil_bro" hero copy (AI slop blacklist #9); splash shows brand mark
    ✓ DO use scanline texture on dark surfaces (DESIGN.md line 109)
    ✓ DO use accent glow on hover/active (DESIGN.md line 108)
"""

from __future__ import annotations


COLORS: dict[str, str] = {
    "deep":           "#1A1B23",
    "surface":        "#24252F",
    "elevated":       "#2E2F3A",
    "hover":          "#363745",
    "accent":         "#00E5CC",
    "accent_dim":     "rgba(0, 229, 204, 0.15)",
    "accent_glow":    "rgba(0, 229, 204, 0.3)",
    "success":        "#4ADE80",
    "warning":        "#FFB547",
    "error":          "#FF6B6B",
    "info":           "#60A5FA",
    "text_primary":   "#E8E6E3",
    "text_secondary": "#9B9AA0",
    "text_muted":     "#6B6A70",
    "border_default": "#363745",
    "border_accent":  "rgba(0, 229, 204, 0.25)",
}

FONTS: dict[str, str] = {
    "mono": "JetBrains Mono",
    "sans": "DM Sans",
}
