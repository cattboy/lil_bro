"""
Content-aware readiness and parse helpers for NVIDIA Profile Inspector (.nip)
files.

NPI's CLI spawns a child writer that outlives the parent ``subprocess.run``.
Reading the .nip immediately after the parent exits can yield a truncated
UTF-16-LE file (odd byte count, half-written closing tag), which raises
``'utf-16-le' codec can't decode byte 0x3e ... truncated data``.

``wait_for_nip_ready`` blocks until the file is structurally complete.
``parse_nip_with_retry`` is a belt-and-braces guard around ``parse_nip`` for
the rare case where readiness passes but decode still hiccups.
"""

from __future__ import annotations

import os
import time
import xml.etree.ElementTree as ET

from .action_logger import action_logger
from .errors import SetterError

from pathlib import Path


_UTF16_LE_BOM = b"\xff\xfe"
_CLOSING_TAG = "</ArrayOfProfile>"
_TAIL_BYTES = 128  # enough to capture `</ArrayOfProfile>` + trailing whitespace


def _check_ready(path: str) -> tuple[bool, str, int, bool, str]:
    """Return (ready, reason, size, bom_present, tail_repr).

    reason is '' when ready; otherwise names the failing check. Diagnostics
    are returned even on the happy path so the caller can log slow readiness.
    """
    try:
        size = os.path.getsize(path)
    except OSError as e:
        return False, f"stat failed: {e}", 0, False, ""

    if size <= 0:
        return False, "size <= 0", size, False, ""
    if size % 2 != 0:
        return False, "odd byte count", size, False, ""

    try:
        with open(path, "rb") as f:
            head = f.read(2)
            if size > _TAIL_BYTES:
                f.seek(-_TAIL_BYTES, os.SEEK_END)
                tail = f.read()
            else:
                tail = head + f.read()
    except OSError as e:
        return False, f"read failed: {e}", size, False, ""

    bom_present = head == _UTF16_LE_BOM
    if not bom_present:
        return False, "missing UTF-16-LE BOM", size, False, tail[-32:].hex()

    try:
        tail_text = tail.decode("utf-16-le", errors="replace").rstrip()
    except Exception as e:
        return False, f"tail decode failed: {e}", size, bom_present, tail[-32:].hex()

    if not tail_text.endswith(_CLOSING_TAG):
        return False, f"tail does not end with {_CLOSING_TAG}", size, bom_present, tail[-32:].hex()

    return True, "", size, bom_present, tail[-32:].hex()


def wait_for_nip_ready(
    path: str,
    timeout: float = 15.0,
    poll_interval: float = 0.2,
) -> None:
    """Block until ``path`` is a complete UTF-16-LE .nip document.

    Ready means, in a single tick: file exists, size > 0, size is even,
    starts with the UTF-16-LE BOM, the last ~128 bytes decode and (after
    rstrip) end with ``</ArrayOfProfile>``, AND the size is unchanged since
    the previous tick. The size-stable check guards against a writer that
    happens to have a valid tail mid-flush.

    Raises ``SetterError`` on timeout with a diagnostic suffix. Emits one
    ``action_logger`` note when readiness takes longer than 2.0 s.
    """
    started = time.monotonic()
    deadline = started + timeout
    prev_size = -1
    last_reason = "not yet polled"
    last_size = 0
    last_bom = False
    last_tail_hex = ""

    while time.monotonic() < deadline:
        ready, reason, size, bom, tail_hex = _check_ready(path)
        last_reason, last_size, last_bom, last_tail_hex = reason, size, bom, tail_hex
        if ready and size == prev_size:
            elapsed = time.monotonic() - started
            if elapsed > 2.0:
                action_logger.log_action(
                    "NPI Readiness",
                    "Slow",
                    f"{elapsed:.2f}s, size={size}",
                )
            return
        prev_size = size
        time.sleep(poll_interval)

    raise SetterError(
        f"NPI .nip not ready after {timeout:.1f}s "
        f"(reason={last_reason}, size={last_size}, bom={last_bom}, tail={last_tail_hex})"
    )


def parse_nip(nip_path: str) -> dict[int, int]:
    """Parse a .nip XML file and return ``{SettingID: SettingValue}``.

    The .nip format is UTF-16 encoded XML with structure:
      <ArrayOfProfile> / <Profile> / <Settings> / <ProfileSetting>
    Each ProfileSetting has <SettingID> (decimal int) and <SettingValue> (decimal int).
    """
    raw = Path(nip_path).read_bytes()
    text = raw.decode("utf-16")
    root = ET.fromstring(text)

    settings: dict[int, int] = {}
    for profile in root.findall("Profile"):
        for ps in profile.findall("Settings/ProfileSetting"):
            sid_text = ps.findtext("SettingID")
            val_text = ps.findtext("SettingValue")
            if sid_text is not None and val_text is not None:
                try:
                    settings[int(sid_text)] = int(val_text)
                except ValueError:
                    continue
    return settings


def parse_nip_with_retry(
    path: str,
    attempts: int = 3,
    delay: float = 0.5,
) -> dict[int, int]:
    """Call ``parse_nip`` up to ``attempts`` times, sleeping ``delay`` between.

    Only retries on ``ET.ParseError``, ``UnicodeDecodeError``, and ``ValueError``
    — the exception types ``parse_nip`` can raise from a truncated/corrupt file.
    Re-raises the last exception after attempts are exhausted.
    """
    last_exc: Exception | None = None
    for i in range(attempts):
        try:
            return parse_nip(path)
        except (ET.ParseError, UnicodeDecodeError, ValueError) as e:
            last_exc = e
            if i < attempts - 1:
                time.sleep(delay)
    assert last_exc is not None
    raise last_exc
