"""The settings-destinations registry: one list of the settings pages MoOS can open.

WHY ONE FILE
The same token -> page table used to be written out seven times (moos-control, Mo AI's
tool schema, the status helper, the search runner, the router, Mo AI's grammar and its
prompt), and tests only noticed a disagreement after it shipped. SPEC D3 makes
/usr/share/moos/settings-destinations.json the one list. Everything that OFFERS a page
reads it through this module; moos-open keeps a literal case arm per token because the
moos: scheme is public, and tests/test_settings_destinations.py proves the arms and this
file agree in both directions.

FAIL SAFE
A reader never guesses. A file that is missing, unparsable or has one malformed entry is
rejected as a whole (`RegistryError`); `safe_load()` turns that into "no pages", so a
broken registry can only make a settings button unavailable, never point it somewhere
unexpected.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

# /usr/lib/moos/<this file> -> /usr/share/moos/settings-destinations.json. The source tree
# has the same layout under system_files/, so tests read the file the image ships.
REGISTRY = Path(__file__).resolve().parent.parent.parent / "share/moos/settings-destinations.json"

HOSTS = ("moos-settings", "systemsettings", "kinfocenter", "app")
TOKEN = re.compile(r"[a-z][a-z0-9-]{1,31}")
TARGETS = {
    "moos-settings": re.compile(r"[a-z][a-z-]{1,31}"),
    "systemsettings": re.compile(r"kcm_[A-Za-z0-9_-]{1,60}"),
    "kinfocenter": re.compile(r"kcm_[A-Za-z0-9_-]{1,60}"),
    "app": re.compile(r"[a-z][a-z0-9.-]{1,63}"),
}
FIELDS = frozenset({"host", "target", "label", "moai"})


class RegistryError(ValueError):
    """The registry cannot be trusted, so nothing in it is offered."""


def _check(token: object, entry: object) -> dict:
    if not isinstance(token, str) or not TOKEN.fullmatch(token):
        raise RegistryError(f"invalid token {token!r}")
    if not isinstance(entry, dict) or set(entry) != FIELDS:
        raise RegistryError(f"{token}: an entry has exactly {sorted(FIELDS)}")
    host, target, label = entry["host"], entry["target"], entry["label"]
    if host not in HOSTS:
        raise RegistryError(f"{token}: unknown host {host!r}")
    if not isinstance(target, str) or not TARGETS[host].fullmatch(target):
        raise RegistryError(f"{token}: invalid {host} target {target!r}")
    if not isinstance(label, dict) or set(label) != {"ar", "en"}:
        raise RegistryError(f"{token}: the label is {{ar, en}}")
    for language in ("ar", "en"):
        text = label[language]
        if not isinstance(text, str) or not text.strip() or len(text) > 60 \
                or any(ord(c) < 32 for c in text):
            raise RegistryError(f"{token}: invalid {language} label")
    if not isinstance(entry["moai"], bool):
        raise RegistryError(f"{token}: moai is true or false")
    return {"host": host, "target": target, "moai": entry["moai"],
            "label": {"ar": label["ar"], "en": label["en"]}}


def load(path: Path | str = REGISTRY) -> dict[str, dict]:
    """Every destination, in file order. Raises RegistryError on anything unexpected."""
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise RegistryError(f"cannot read {path}: {error}") from error
    if not isinstance(document, dict) or document.get("schema") != 1:
        raise RegistryError("unknown registry schema")
    destinations = document.get("destinations")
    if not isinstance(destinations, dict) or not destinations:
        raise RegistryError("the registry lists no destinations")
    return {token: _check(token, entry) for token, entry in destinations.items()}


def safe_load(path: Path | str = REGISTRY) -> dict[str, dict]:
    """load(), or no destinations at all when the file cannot be trusted."""
    try:
        return load(path)
    except RegistryError:
        return {}


def moai_tokens(registry: dict[str, dict]) -> tuple[str, ...]:
    """The pages Mo AI may offer (its open_settings enum), in file order."""
    return tuple(token for token, entry in registry.items() if entry["moai"])


def argv(entry: dict) -> tuple[str, ...]:
    """The fixed command moos-open runs for one destination (it keeps its own literal copy)."""
    host, target = entry["host"], entry["target"]
    if host == "moos-settings":
        return ("moos-settings", f"--section={target}")
    if host == "app":
        return (target,)
    return (host, target)
