# Bundled fonts

`theme.py:load_fonts()` registers any `.ttf` files dropped into this
directory at GUI startup via `QFontDatabase.addApplicationFont`.

## What to drop here

- `JetBrainsMono-Regular.ttf`, `JetBrainsMono-Bold.ttf` (and any other
  weights the app references)
- `DMSans-Regular.ttf`, `DMSans-Medium.ttf`, `DMSans-Bold.ttf`

Per CLAUDE.md, **no runtime font CDN** — the app must not phone home
to Google Fonts. Bundling locally satisfies the privacy-first
contract. If this directory is empty (the default in version control),
Qt falls back to the closest matching system fonts.

## Where to get them

- JetBrains Mono — <https://www.jetbrains.com/lp/mono/> (Apache 2.0)
- DM Sans — <https://fonts.google.com/specimen/DM+Sans> (Open Font License)

Download once during build setup, drop the `.ttf` files in this
directory, and `lil_bro.spec` will auto-bundle them.
