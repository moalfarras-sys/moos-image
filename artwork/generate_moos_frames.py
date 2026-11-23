#!/usr/bin/env python3
"""Regenerate (or check) the slim MoOS window frame of all eighteen looks.

The frame, its window actions and its layout come from one renderer,
artwork/generate_moos_aurorae.py. Three theme generators own the packages and
call it with their own palette roles: generate_moos_ui2.py (Graphite/Tidal),
generate_moos_themes.py (the fourteen family members) and
generate_moos_bloom.py (both Bloom finishes). This driver calls exactly those
role sources for the Aurorae packages alone, so a frame change does not have to
re-export wallpapers, icons or styles, and `--check` proves the committed
packages are what the renderer produces for each look's roles.

    python3 artwork/generate_moos_frames.py          # write all 18 frames
    python3 artwork/generate_moos_frames.py --check  # compare only
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import sys
import tempfile

ART = pathlib.Path(__file__).resolve().parent
ROOT = ART.parent
SHARE = ROOT / "system_files/usr/share"
FRAMES = SHARE / "aurorae/themes"


def load(name: str):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), ART / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def jobs() -> list[tuple[str, object]]:
    """(Aurorae package name, a callable writing that package's frame files)."""
    ui2 = load("generate_moos_ui2")
    family = load("generate_moos_themes")
    bloom = load("generate_moos_bloom")
    art = ui2.aurorae_art
    found: list[tuple[str, object]] = []
    for variant, name in (("dark", "MoOSUI2"), ("light", "MoOSUI2Light")):
        found.append((name, lambda target, v=variant, n=name: art.render_aurorae_suite(
            target, ui2.variant_roles(v), plugin_name=n)))
    for key, meta in family.THEMES.items():
        found.append((meta["style"], lambda target, k=key, n=meta["style"]: art.render_aurorae_suite(
            target, family._roles(k), plugin_name=n)))
    profiles = {p["id"]: p for p in json.loads(
        (ROOT / "artwork/moos-design/theme-profiles.json").read_text(encoding="utf-8"))["profiles"]}
    for light in (False, True):
        profile = profiles["org.moos.ui2.bloom" + (".light" if light else "")]
        found.append((profile["decoration"], lambda target, p=profile: art.render_aurorae_suite(
            target, bloom.frame_roles(p), plugin_name=p["decoration"])))
    names = [name for name, _ in found]
    if len(names) != 18 or len(set(names)) != 18:
        raise SystemExit(f"expected 18 distinct MoOS frames, found {names}")
    return found


def frame_files(package: pathlib.Path, name: str) -> list[pathlib.Path]:
    art = load("generate_moos_aurorae")
    return [package / "decoration.svg", package / f"{name}rc",
            *(package / f"{button}.svg" for button in art.BUTTONS)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    found = jobs()
    if not arguments.check:
        for name, write in found:
            write(FRAMES / name)
        bloom = load("generate_moos_bloom")
        profiles = {p["id"]: p for p in json.loads(
            (ROOT / "artwork/moos-design/theme-profiles.json").read_text(encoding="utf-8"))["profiles"]}
        for light in (False, True):
            # Bloom's owner also writes the package metadata and retires notices.
            bloom.frame(light, profiles["org.moos.ui2.bloom" + (".light" if light else "")])
        print(f"wrote the slim MoOS frame for {len(found)} looks")
        return 0
    # Render each package into a private copy and compare the frame files.
    stale: list[str] = []
    with tempfile.TemporaryDirectory(prefix="moos-frames-") as temporary:
        for name, write in found:
            package = FRAMES / name
            private = pathlib.Path(temporary) / name
            write(private)
            for path in frame_files(private, name):
                shipped = package / path.name
                if not shipped.is_file() or shipped.read_bytes() != path.read_bytes():
                    stale.append(str(shipped.relative_to(ROOT)))
    if stale:
        print("window frames differ from their renderer; run python3 artwork/generate_moos_frames.py",
              file=sys.stderr)
        for path in stale[:20]:
            print(f"  {path}", file=sys.stderr)
        return 1
    print(f"window frames match the renderer for {len(found)} looks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
