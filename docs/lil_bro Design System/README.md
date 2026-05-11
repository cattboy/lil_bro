# lil_bro Design System

> **lil_bro.exe** — A local, privacy-first AI agent that diagnoses and optimizes gaming PCs. Detects misconfigurations (refresh rates, mouse polling, G-Sync, power plans, XMP/EXPO, NVIDIA GPU profiles), proposes fixes via a local LLM (Qwen2.5-Coder-7B), applies them with a session manifest for one-command revert, and never sends data off the device.

**Aesthetic direction:** _Retro-Futuristic Terminal_ — CRT warmth meets modern clarity. A sci-fi ship's diagnostic console that's actually friendly. Not pixel-art retro, not cyberpunk neon — warm, readable, trustworthy, with personality. "The friend who knows computers."

**Surfaces represented:**
- Windows desktop app (PyQt GUI) — primary product surface, see `ui_kits/desktop/`.

**Sources consulted:**
- `uploads/DESIGN.md` — canonical design tokens and rationale (mirrored from `cattboy/lil_bro@feat:DESIGN.md`).
- `uploads/figma-prototype.html` — pre-rendered HTML-to-Figma export of 9 screens (splash, dashboard, output, approval/batch/confirm/AI-setup dialogs, debug log, polling widget).
- GitHub `cattboy/lil_bro` repo browsed (`default branch`, root tree). Project is structured around `src/`, `tests/`, `memory-bank/`, `docs/`. The frontend was specified in the `feat` branch but is not accessible via the public tree — design extraction came from the Figma prototype HTML, which is verbatim from the same branch.

---

## Index

- `README.md` — this file
- `SKILL.md` — Claude Code Agent Skill manifest
- `colors_and_type.css` — design tokens (colors, type, spacing, motion, semantic helpers)
- `assets/` — `logo.svg` (wordmark), `logo-mark.svg` (app icon)
- `preview/` — 20 design-system cards (registered in the asset review pane)
- `ui_kits/desktop/` — desktop app UI kit + interactive demo
- `uploads/` — original DESIGN.md and figma prototype

---

## Content fundamentals

**Tone:** Casual, knowledgeable, slightly cheeky — _"the friend who knows computers."_ Contractions always: _"that's leaving smoothness on the table"_ over _"that is suboptimal."_

**Voice rules**
- Severity labels are blunt and unhedged: **HIGH**, **MEDIUM**, **LOW**. No softening words.
- Recommendations name the actual symptom in plain language: _"Your PC is in Balanced mode which throttles CPU clocks mid-game"_ — not _"The active power plan configuration is suboptimal for sustained workloads."_
- Status messages are short and confident: _"Excellent — no jitter detected"_, _"Power plan switched"_, _"3 fixes: 1 HIGH, 1 MEDIUM, 1 LOW"_.
- Personality shows in the seams. Exit message: **"stay sweaty lil_bro"**. Not on every screen — just where it earns a smile.
- Lower-case wordmark always: `lil_bro` (with cyan underscore). Never `Lil_bro`, never `LIL_BRO`.

**Casing**
- Window titles: Title Case — _"System Dashboard"_, _"Pipeline Output"_, _"Apply These Fixes?"_.
- Section labels / category tags / log levels: ALL CAPS MONO with letter-spacing: 0.10–0.14em — `CPU USAGE`, `HIGH · POWER PLAN`, `[WARN]`, `PHASE 04`.
- Buttons: sentence-cased, short verbs — _"Apply 2 Selected"_, _"Skip All"_, _"Yes, Continue"_, _"Test Polling"_. Counts inline (_"Apply 3 Selected"_).

**Pronouns:** _Your PC_, _your system_, _your shader cache_. The product addresses **you** directly, like a friend. Never first-person — lil_bro narrates in third about itself: _"lil_bro identified 3 improvements"_, _"lil_bro will create a Windows System Restore Point"_.

**Emoji:** Not used in UI. Personality lives in tone + the cyan underscore, not emoji.

**Numbers + units:** Tabular-num mono, unit always present, unit color desaturated against the value: `68°C`, `1000 Hz`, `12.4 GB`. Path/version strings stay literal: `Qwen2.5-7B-Instruct`, `Driver 552.44`, `2026-05-11_1234`.

---

## Visual foundations

**Color philosophy:** restrained. One signature accent (`#00E5CC` Electric Cyan) does **all** the heavy lifting — every CTA, every "running" state, every selected fix. Competitors went green (Razer/NVIDIA), purple (NZXT), or red (MSI); cyan reads as _diagnostic intelligence_ and stays distinct. Magenta (`#D183E8`) is reserved for the brand banner and the GPU line in charts — it appears, but rarely.

**Surfaces** are a 4-step warm dark ramp — never pure black. `#1A1B23` (deep) → `#24252F` (surface) → `#2E2F3A` (elevated) → `#363745` (hover). The hex deltas are tight so cards sit one half-step above their canvas without screaming. Light mode (`#F0EDE8` → `#FFFFFF`) is supported via `.theme-light` but dark is default everywhere.

**Type** pairs JetBrains Mono (display, data, labels, code) with DM Sans (body, UI copy, button labels). Mono headers are non-negotiable — this is a terminal tool and the monospace _is_ the brand. All numeric readouts use `font-variant-numeric: tabular-nums`.

**Spacing:** 8px base, geometric scale `2 · 4 · 8 · 16 · 24 · 32 · 48 · 64`. Density is _comfortable_, not tight — diagnostic blocks need breathing room so the user can read severity at a glance.

**Backgrounds:** flat warm-dark fills, **never** gradients except the animated `linear-gradient(90deg, accent, #00FFE0, accent)` "plasma" sweep on progress bars. No photographs. No illustrations. The only ambient effect is the **scanline texture** (see below).

**Signature textures**
- **Scanlines** — `repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,0,0,0.03) 2px, rgba(0,0,0,0.03) 4px)` overlaid at 0.22–0.30 opacity on dark surfaces. Adds CRT warmth without reducing readability. Apply to: main canvas, cards, dialogs.
- **Accent glow** — `box-shadow: 0 0 20px rgba(0,229,204,0.30)` on primary buttons, active phase cards, and the brand wordmark. Optional `text-shadow: 0 0 16–40px var(--accent-glow)` on hero/stat values for ambient terminal phosphor feel.

**Borders:** 1px solid, default `#363745` (dark) / `#D8D5D0` (light). Accent borders use `rgba(0,229,204,0.25)`. Cards always carry a border — they don't float on shadow alone.

**Shadows**
- Card resting: `0 1px 0 rgba(255,255,255,0.02) inset, 0 8px 24px rgba(0,0,0,0.25)` (subtle).
- Glow (interactive hover, active state): `0 0 20px rgba(0,229,204,0.30)`.
- Dialog: `0 24px 64px rgba(0,0,0,0.55)`.
- No multi-stop pretty-shadow stacks. Two values max per element.

**Corner radii:** `4px` buttons/inputs/check items · `8px` cards/panels/swatches/stat cards · `12px` dialogs/major sections · `9999px` dots/status indicators/progress bars.

**Hover / press states**
- Buttons: `filter: brightness(1.08)` + intensified glow on primary; bg fade to `--bg-hover` on ghost; `--accent-dim` background on secondary.
- Nav items: bg fades to `--bg-hover`, text to `--text-primary`. Active state uses cyan dim + 2px left border.
- Press: no scale shrink. State changes are color-only — this is a tool, not a toy.

**Motion** — minimal-functional. Subtle fade-in for results, quick state transitions. Easings: `enter: ease-out · exit: ease-in · move: ease-in-out`. Durations: `micro 50–100ms · short 150ms · medium 250–400ms · long 400–700ms`. No bounce, no slide.

**Transparency / blur:** dialogs use `rgba(0,0,0,0.65) + backdrop-filter: blur(2px)` for backdrop. That's the only blur. Cards never blur their backdrops; the OS would, the app shouldn't pretend.

**Layout:**
- App shell is **title bar (36px) · sidebar (220px) · main · status bar (28px)**. All four are fixed-position relative to the window.
- Max content column 1120px (rare; most content is sidebar+main).
- Single-column information density — vertical scroll for logs, no horizontal scroll anywhere.

**Imagery vibe:** lil_bro doesn't ship marketing imagery. If a screenshot or chart is needed, it's warm-dark with cyan/magenta data lines on a faintly red→amber→green safety-zone gradient (see Dashboard chart). No grain. No noise. No filters.

---

## Iconography

**Approach:** Iconography is **intentionally minimal**. The terminal aesthetic means most "icons" are typographic — unicode glyphs in JetBrains Mono — and the visual energy goes into colored dots, severity badges, and the cyan accent. lil_bro is not an icon-heavy product; it's a text-heavy diagnostic console.

**What's used in production**
- **Unicode glyph "icons" (mono-font)** for nav and inline status:
  - `◆` Dashboard · `≡` Output · `📄` Debug Log · `↩` Revert · `✕` Exit · `⚡` (highlight/lightning) · `▢` `−` (window controls)
  - `✓` (done) · `●` (running/active) · `○` (pending)
  - `█` (blinking cursor at end of log)
- **Status dots** (8–10px filled circles with semantic glow) for run/idle/ok/warn/error.
- **Severity badges** (pill-shaped mono caps in semantic color) for HIGH/MEDIUM/LOW/AUTO/MANUAL.
- **No SVG icon set, no icon font.** No Heroicons, no Lucide. The product is happy with unicode + dots.
- **No emoji.** Despite the casual tone, emoji would break the terminal vibe.

**Logo / brand mark**
- Primary wordmark: `lil_bro` set in JetBrains Mono 800, letter-spacing −0.02em, underscore in `--accent` (`#00E5CC`) with a `text-shadow: 0 0 24–40px` glow. See `assets/logo.svg`.
- App mark: square 64px tile with `lb_` (underscore cyan). See `assets/logo-mark.svg`.
- Inverted variant: cyan tile + dark `lb_` for over-light placements.

**If you need iconography this set doesn't cover**, _ask the user before adding anything_. Don't reach for a CDN icon font reflexively — the absence of icons _is_ the design. If something truly needs an icon (e.g. a settings cog for a screen lil_bro doesn't have yet), prefer a mono 1.5px-stroke linear icon, ~14–16px, in `--text-secondary`.

---

## Font substitution flag

The brief calls for **JetBrains Mono** and **DM Sans**. Both are loaded from Google Fonts CDN in every file — no local `.ttf`/`.woff2` files are bundled in this design system. If you need to ship offline, run `python -m fonttools subset` against the families or grab the Google Fonts zip and add them under `fonts/` with `@font-face` declarations. **No substitutions are made — both families are first-party Google Fonts choices from the original brief.**
