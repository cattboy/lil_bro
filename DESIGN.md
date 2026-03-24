# Design System — lil_bro

## Product Context
- **What this is:** A local, privacy-first AI agent that diagnoses and optimizes gaming PCs
- **Who it's for:** Gamers who want peak performance without cloud tools or telemetry
- **Space/industry:** Gaming PC optimization (Razer Cortex, NZXT CAM, MSI Afterburner, NVIDIA App)
- **Project type:** Desktop utility — terminal CLI now, PyQt GUI planned, Windows installer

## Aesthetic Direction
- **Direction:** Retro-Futuristic Terminal — CRT warmth meets modern clarity
- **Decoration level:** Intentional — subtle scanline texture on dark surfaces, soft glow on accent elements, terminal-style bordered panels
- **Mood:** A sci-fi ship's diagnostic console that's actually friendly. Not pixel-art retro, not cyberpunk neon — warm, readable, trustworthy with personality. "The friend who knows computers."
- **Reference sites:** NZXT CAM (clean monitoring), NVIDIA App (restrained modern), Razer Cortex (brand personality)

## Typography
- **Display/Hero:** JetBrains Mono Bold — section headers, banner, navigation titles. Monospace for a terminal tool feels authentic, not forced.
- **Body:** DM Sans Regular/Medium — explanations, descriptions, proposal text. Clean geometric sans that reads well at any size, pairs beautifully with monospace headers.
- **UI/Labels:** DM Sans Medium (same as body)
- **Data/Tables:** JetBrains Mono Regular — hardware specs, file paths, status values, benchmark scores. Must support `font-variant-numeric: tabular-nums`.
- **Code:** JetBrains Mono
- **Loading:** Google Fonts CDN (`https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&family=JetBrains+Mono:wght@300;400;500;600;700;800&display=swap`)
- **Scale:**
  - `3xl` — 3.5rem (hero brand)
  - `2xl` — 2rem (section display)
  - `xl` — 1.5rem (stat values)
  - `lg` — 1.15rem (large body)
  - `md` — 1rem (body)
  - `sm` — 0.875rem (data, UI)
  - `xs` — 0.8rem (nav items, small text)
  - `2xs` — 0.75rem (labels, section titles)
  - `3xs` — 0.7rem (meta, timestamps)
  - `4xs` — 0.65rem (micro labels)

## Color
- **Approach:** Restrained with one signature accent
- **Primary accent:** `#00E5CC` (Electric Cyan) — diagnostic/tech intelligence. Deliberately not green (Razer/NVIDIA), purple (NZXT), or red (MSI). Light mode variant: `#00B8A3`.
- **Backgrounds (dark):**
  - Deep: `#1A1B23` — main background, not pure black (warmer, easier on eyes)
  - Surface: `#24252F` — cards, panels, containers
  - Elevated: `#2E2F3A` — sidebars, title bars, raised elements
  - Hover: `#363745` — interactive hover states
- **Backgrounds (light):**
  - Deep: `#F0EDE8`
  - Surface: `#FAFAF8`
  - Elevated: `#FFFFFF`
  - Hover: `#E8E5E0`
- **Semantic:**
  - Success: `#4ADE80` (Mint)
  - Warning: `#FFB547` (Amber)
  - Error: `#FF6B6B` (Coral)
  - Info: `#60A5FA` (Blue)
- **Text (dark):**
  - Primary: `#E8E6E3` (off-white, not pure white — reduces eye strain)
  - Secondary: `#9B9AA0`
  - Muted: `#6B6A70`
- **Text (light):**
  - Primary: `#1A1B23`
  - Secondary: `#5A5960`
  - Muted: `#8A8990`
- **Borders:**
  - Default: `#363745` (dark) / `#D8D5D0` (light)
  - Accent: `rgba(0, 229, 204, 0.25)`
- **Accent derived:**
  - Dim: `rgba(0, 229, 204, 0.15)` — backgrounds, active nav items
  - Glow: `rgba(0, 229, 204, 0.3)` — box-shadow on primary buttons, stat highlights
- **Dark mode:** Primary (default). All tokens defined as CSS custom properties for easy theming.
- **Terminal colorama mapping:**
  - `Fore.CYAN` → accent (#00E5CC equivalent)
  - `Fore.GREEN` → success (#4ADE80 equivalent)
  - `Fore.YELLOW` → warning (#FFB547 equivalent)
  - `Fore.RED` → error (#FF6B6B equivalent)
  - `Fore.BLUE` → info/secondary (#60A5FA equivalent)
  - `Fore.MAGENTA` → brand/banner (#D183E8)
  - `Fore.WHITE` → text primary
  - `Style.DIM` → text muted

## Spacing
- **Base unit:** 8px
- **Density:** Comfortable — terminal tools need breathing room between diagnostic blocks
- **Scale:**
  - `2xs` — 2px
  - `xs` — 4px
  - `sm` — 8px (base)
  - `md` — 16px
  - `lg` — 24px
  - `xl` — 32px
  - `2xl` — 48px
  - `3xl` — 64px

## Layout
- **Approach:** Grid-disciplined with terminal heritage — monospace-influenced alignment, clear information hierarchy
- **Grid:** Single column for terminal, sidebar + content for PyQt GUI
- **Max content width:** 1120px
- **Border radius:**
  - `sm` — 4px (buttons, inputs, check items, alert left border)
  - `md` — 8px (cards, panels, swatches, stat cards)
  - `lg` — 12px (mockup containers, major sections)
  - `full` — 9999px (dots, status indicators, progress bars)

## Motion
- **Approach:** Minimal-functional — subtle fade-in for scan results, quick state transitions. No bouncing or sliding. Feels responsive and competent, not playful.
- **Easing:** enter(`ease-out`) exit(`ease-in`) move(`ease-in-out`)
- **Duration:**
  - micro — 50-100ms (hover states, toggles)
  - short — 150ms (button transitions, border color changes)
  - medium — 250-400ms (fade-in for scan results, panel transitions)
  - long — 400-700ms (progress bar fills, initial load animations)
- **Glow effect:** Primary accent elements get `box-shadow: 0 0 20px rgba(0, 229, 204, 0.3)` on hover/active. Subtle CRT warmth.
- **Scanline texture:** `repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,0,0,0.03) 2px, rgba(0,0,0,0.03) 4px)` overlaid at low opacity on dark surfaces. Adds retro-terminal character without reducing readability.

## Brand Voice (UI Copy)
- Casual, knowledgeable, slightly cheeky — "the friend who knows computers"
- Use contractions: "that's leaving smoothness on the table" not "that is suboptimal"
- Severity labels are direct: "HIGH", "MEDIUM", "LOW" — no softening
- Exit message: "stay sweaty lil_bro" — the personality shows in small moments
- AI recommendations use plain language: "Your PC is in Balanced mode which throttles CPU clocks mid-game" not "The active power plan configuration is suboptimal for sustained workloads"

## Decisions Log
| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-03-23 | Initial design system created | Created by /design-consultation based on competitive research of gaming tools (NZXT CAM, Razer Cortex, NVIDIA App, MSI Afterburner) |
| 2026-03-23 | Electric Cyan (#00E5CC) as primary accent | Every competitor uses green, purple, or red. Cyan says "diagnostic intelligence" and gives lil_bro a unique visual identity |
| 2026-03-23 | Retro-futuristic terminal aesthetic | lil_bro is a conversational agent, not a monitoring dashboard. Lean into the terminal heritage instead of mimicking hardware gauge UIs |
| 2026-03-23 | JetBrains Mono + DM Sans pairing | Monospace for a diagnostic tool is authentic. DM Sans provides clean body text that doesn't fight the monospace headers |
| 2026-03-23 | Dark-mode-first | Universal in gaming tools — users expect it. Light mode available but not primary |
