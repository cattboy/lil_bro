# Screenshots

README images of the live app, generated from the real `MainWindow` + `Dashboard`
fed by `scripts/mock_fixtures.py` (no system access, no real scan).

## Regenerate

Run on a desktop with fonts available (a headless/CI box with an empty Qt font
database renders text as tofu boxes):

```bash
python scripts/mock_gui.py --screenshots
```

Writes into this directory:

| File | What it shows |
|------|----------------|
| `dashboard.png` | Hero — Dashboard with quick-fix cards + the first-run coachmark pointing at Start Optimization |
| `dashboard-coachmark-fix.png` | The quick-fix beat — arrow callout on a live Fix Now card |
| `dashboard-optimal.png` | All-optimal state — no issue cards, just live monitoring |

For the exact brand fonts (JetBrains Mono / DM Sans) drop the `.ttf` files into
`resources/fonts/` first (see that folder's README); otherwise Qt falls back to
the closest system fonts.
