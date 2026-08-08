#!/usr/bin/env python3
"""The central theme owner must capture an exact, inert wallpaper identity."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OWNER = ROOT / "system_files/usr/bin/moos-theme"
BASH = "/usr/bin/bash" if Path("/usr/bin/bash").exists() else "bash"


def function(source: str, name: str) -> str:
    start = source.index(f"{name}() {{")
    end = source.index("\n}\n", start) + 3
    return source[start:end]


source = OWNER.read_text(encoding="utf-8")
capture = function(source, "capture_wallpaper_identity")

with tempfile.TemporaryDirectory(prefix="moos-wallpaper-state-") as temporary:
    root = Path(temporary)
    bindir = root / "bin"
    bindir.mkdir()
    stub = bindir / "gdbus"
    stub.write_text(
        "#!/bin/sh\nprintf \"%s\\n\" \"$MOOS_TEST_GDBUS_REPLY\"\n",
        encoding="utf-8",
    )
    stub.chmod(0o755)
    script = root / "probe"
    script.write_text(f"{capture}\ncapture_wallpaper_identity\n", encoding="utf-8")
    env = os.environ | {
        "PATH": f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}",
        "MOOS_TEST_GDBUS_REPLY":
            "('moos-wallpaper-state:profile:%2Fusr%2Fshare%2Fwallpapers%2FMoOSUI2Arena',)",
    }
    result = subprocess.run(
        [BASH, str(script)],
        env=env,
        check=True,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.stdout == (
        "profile\t%2Fusr%2Fshare%2Fwallpapers%2FMoOSUI2Arena\n"
    ), result.stdout

assert '"wallpaperMode": "%s"' in source
assert '"wallpaperEncoded": "%s"' in source
assert "theme_state_field wallpaperMode" in source
assert "theme_state_field wallpaperEncoded" in source
assert "custom_wallpapers_complete" in source
assert "apply_desktop_scene_token" in source
assert "current_desktop_wallpaper_value" not in source

print("OK: the central theme state captures an exact encoded profile/custom wallpaper identity")
