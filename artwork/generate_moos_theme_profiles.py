#!/usr/bin/env python3
"""Generate the runtime MoOS theme-profile database from one owned source."""

from __future__ import annotations

import json
import os
from pathlib import Path


TEST_ROOT = os.environ.get("MOOS_THEME_PROFILE_TEST_ROOT")
ROOT = Path(TEST_ROOT).resolve() if TEST_ROOT else Path(__file__).resolve().parents[1]
SOURCE = ROOT / "artwork/moos-design/theme-profiles.json"
OUTPUT = ROOT / "system_files/usr/share/moos"
PROFILE_FIELDS = (
    "id", "scheme", "style", "konsole", "icons", "gtkCss", "cursor",
    "decoration", "wallpaper", "wallpaperBranch", "mode", "displayName",
    "family", "accent", "surfaceTreatment",
)
ENGINE_FIELDS = ("qtWidgetStyle", "gtkTheme")
FIELDS = PROFILE_FIELDS + ENGINE_FIELDS


def load_profiles() -> dict:
    document = json.loads(SOURCE.read_text(encoding="utf-8"))
    if document.get("schema") != 1:
        raise SystemExit("MoOS theme profiles: unsupported schema")
    engines = document.get("engines")
    if not isinstance(engines, dict) or set(engines) != set(ENGINE_FIELDS):
        raise SystemExit("MoOS theme profiles: Qt and GTK engines are required")
    for name in ENGINE_FIELDS:
        value = engines[name]
        if not isinstance(value, str) or not value.strip():
            raise SystemExit(f"MoOS theme profiles: invalid engine {name}")
        if "\t" in value or "\n" in value:
            raise SystemExit("MoOS theme profiles: tabs/newlines are forbidden")
    profiles = document.get("profiles")
    if not isinstance(profiles, list) or len(profiles) != 16:
        raise SystemExit("MoOS theme profiles: exactly 16 profiles are required")

    ids: set[str] = set()
    families: dict[str, set[str]] = {}
    for profile in profiles:
        missing = set(PROFILE_FIELDS).difference(profile)
        if missing:
            raise SystemExit(f"MoOS theme profiles: missing {sorted(missing)}")
        if profile["id"] in ids or not profile["id"].startswith("org.moos.ui2"):
            raise SystemExit(f"MoOS theme profiles: invalid/duplicate id {profile['id']}")
        ids.add(profile["id"])
        families.setdefault(profile["family"], set()).add(profile["mode"])
        if profile["mode"] not in {"light", "dark"}:
            raise SystemExit(f"MoOS theme profiles: invalid mode {profile['mode']}")
        if profile["wallpaperBranch"] not in {"images", "images_dark"}:
            raise SystemExit("MoOS theme profiles: invalid wallpaper branch")
        for value in profile.values():
            if isinstance(value, str) and ("\t" in value or "\n" in value):
                raise SystemExit("MoOS theme profiles: tabs/newlines are forbidden")
    if any(modes != {"light", "dark"} for modes in families.values()):
        raise SystemExit("MoOS theme profiles: every family needs light and dark")
    return document


def render_tsv(document: dict) -> str:
    header = "# " + "\t".join(FIELDS)
    rows = [header]
    for profile in document["profiles"]:
        values = [str(profile[field]) for field in PROFILE_FIELDS]
        values.extend(str(document["engines"][field]) for field in ENGINE_FIELDS)
        rows.append("\t".join(values))
    return "\n".join(rows) + "\n"


def write_if_changed(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    path.write_text(content, encoding="utf-8")


def main() -> None:
    document = load_profiles()
    write_if_changed(
        OUTPUT / "theme-profiles.json",
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
    )
    write_if_changed(OUTPUT / "theme-profiles.tsv", render_tsv(document))
    print(f"MoOS theme profiles generated at {OUTPUT}")


if __name__ == "__main__":
    main()
