## Unused imports cleanup — batch_selection_dialog.py

**Status:** ✅ Complete (651 tests pass)

### What was removed
Four unused imports from an older QListWidget-based design:
- `QAbstractItemView`
- `QDialogButtonBox`
- `QListWidget`
- `QListWidgetItem`

These were remnants before the current `_FixItem` frame approach was implemented.

### What was fixed
1. Merged stray imports block (lines 27–29) into main block
2. Removed unnecessary `# noqa: E402` comments
3. Alphabetized all QtWidgets imports
4. Consolidated Qt and Signal into one QtCore import line

### Result
Imports are now clean, readable, and follow PEP8. No behavioral changes — all tests pass.

This is a good pattern to apply elsewhere if unused imports are found.
