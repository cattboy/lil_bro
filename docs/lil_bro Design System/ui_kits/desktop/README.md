# lil_bro Desktop UI Kit

Components for the lil_bro Windows desktop app — the agent screen the gamer actually sees.

## Files
- `index.html` — interactive demo. Boots through splash → restore-point confirm → app shell with an approval dialog, then lets you switch between **Dashboard** and **Output** views.
- `Chrome.jsx` — title bar, sidebar nav, status bar (bottom), stat card, phase card, severity badge, status pill, button.
- `DashboardView.jsx` — full Dashboard screen: 4-stat grid, temperature history chart, USB polling widget.
- `OutputView.jsx` — Output screen with phase cards + colored pipeline log. Also contains the **Approval**, **Confirm** and **Splash** dialogs.
- `app.css` — component styles (depends on `../../colors_and_type.css` for tokens).

## Design width
Built for **1280 × 800** application window. The chrome includes a custom 36px title bar and a 28px bottom status bar.

## Try it
Open `index.html` in a browser. The splash auto-advances, then the restore-point dialog appears; click through and the approval dialog will surface ~1.2s after the app shell mounts. Nav between Dashboard and Output via the sidebar.
