"""What an update brought — the one reader of /usr/share/moos/whats-new.json.

WHY THIS EXISTS

On 2026-09-17 the owner updated two machines across six waves of work and reported, accurately,
"I felt no change". Every one of those waves had shipped something a person can use — a page, a
shortcut, a drop target, a chip that names the app on the microphone — and nothing on the desktop
said so. A feature nobody is told about is, to the person at the keyboard, a feature that was
never built.

So the image carries a short list of what a person can SEE or DO, written for them and not for a
developer. Two surfaces read it, and both go through this module so they can never disagree:

  * MoOS Settings → System → What's new (through moos-settings-status), always available;
  * moos-whats-new-notify, which says it once after an update.

`fresh` is the useful part. An entry is fresh when the system this machine ran BEFORE its last
update was built before the change reached main. After a jump of several releases everything the
owner has not had yet is marked, not just the newest item; on a fresh install (no previous
system) nothing is, because nothing changed under anyone.

The file is data and is treated as hostile: size-capped, shape-checked, one bad entry dropped
rather than the whole list, routes confined to MoOS's own `moos://` grammar. A missing or
malformed file is an empty list — the page then says so instead of inventing news.
"""

from __future__ import annotations

import calendar
import json
from pathlib import Path
import platform
import re

# Beside this module in the image (/usr/lib/moos → /usr/share/moos) and in a source checkout.
WHATS_NEW_FILE = Path(__file__).resolve().parent.parent.parent / "share/moos/whats-new.json"
MAX_BYTES = 64 * 1024
MAX_ENTRIES = 32
TITLE_LIMIT = 80
BODY_LIMIT = 320

_ENTRY_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,39}\Z")
_GLYPH = re.compile(r"[a-z][a-z-]{0,23}\Z")
# What's new may only send a person somewhere Settings itself may go.
_ROUTE = re.compile(r"moos://settings/[a-z0-9][a-z0-9-]{0,39}\Z")
_MERGED = re.compile(r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})Z\Z")
# An entry may name the architectures it is true on. The editions do not always change
# together: a fix that brings the ARM edition level with x86 is news on ARM and a false
# "new" card on every x86 machine. No `arch` means every machine.
_ARCH = re.compile(r"[a-z0-9_]{1,16}\Z")


def merged_epoch(value: object) -> int:
    """Seconds since the epoch for an exact `YYYY-MM-DDTHH:MM:SSZ`, or 0."""
    match = _MERGED.match(value) if isinstance(value, str) else None
    if not match:
        return 0
    try:
        return calendar.timegm(tuple(int(part) for part in match.groups()) + (0, 0, 0))
    except (ValueError, OverflowError):
        return 0


def _bilingual(value: object, limit: int) -> dict[str, str] | None:
    if not isinstance(value, dict):
        return None
    texts = {}
    for language in ("ar", "en"):
        text = value.get(language)
        if not isinstance(text, str) or not text.strip() or len(text) > limit:
            return None
        texts[language] = text.strip()
    return texts


def applies_here(raw: dict, machine: str) -> bool | None:
    """True when the entry is for this machine, False when it names others, None when malformed."""
    arch = raw.get("arch")
    if arch is None:
        return True
    if (not isinstance(arch, list) or not arch or len(arch) > 4
            or not all(isinstance(name, str) and _ARCH.match(name) for name in arch)):
        return None
    return machine in arch


def whats_new_state(previous_built: int, path: Path | None = None,
                    machine: str | None = None) -> dict[str, object]:
    """The shipped list for this machine, newest first, as the page and the notification show it."""
    source = WHATS_NEW_FILE if path is None else path
    machine = machine or platform.machine()
    empty: dict[str, object] = {"entries": [], "fresh": 0}
    try:
        if source.stat().st_size > MAX_BYTES:
            return empty
        document = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return empty
    if not isinstance(document, dict) or document.get("schema") != 1:
        return empty
    raw_entries = document.get("entries")
    if not isinstance(raw_entries, list):
        return empty

    entries: list[dict[str, object]] = []
    seen: set[str] = set()
    for raw in raw_entries:
        if not isinstance(raw, dict):
            continue
        identifier, glyph = raw.get("id"), raw.get("glyph")
        merged = merged_epoch(raw.get("merged"))
        title = _bilingual(raw.get("title"), TITLE_LIMIT)
        body = _bilingual(raw.get("body"), BODY_LIMIT)
        if (not isinstance(identifier, str) or not _ENTRY_ID.match(identifier)
                or identifier in seen or not isinstance(glyph, str) or not _GLYPH.match(glyph)
                or not merged or title is None or body is None):
            continue
        here = applies_here(raw, machine)
        if not here:
            continue  # malformed (None) is dropped like any invalid entry; another machine's is skipped
        route = raw.get("route", "")
        if not isinstance(route, str) or (route and not _ROUTE.match(route)):
            route = ""
        keys = raw.get("keys", [])
        if (not isinstance(keys, list) or len(keys) > 4
                or not all(isinstance(key, str) and 0 < len(key) <= 8 for key in keys)):
            keys = []
        seen.add(identifier)
        entries.append({
            "id": identifier, "glyph": glyph, "merged": merged, "title": title, "body": body,
            "route": route, "keys": list(keys),
            "fresh": bool(previous_built > 0 and merged > previous_built),
        })
    # Stable: entries that merged together keep the order the file gives them.
    entries.sort(key=lambda entry: entry["merged"], reverse=True)
    entries = entries[:MAX_ENTRIES]
    return {"entries": entries, "fresh": sum(1 for entry in entries if entry["fresh"])}
