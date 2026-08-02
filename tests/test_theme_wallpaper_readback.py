#!/usr/bin/env python3
"""The wallpaper readback must return a path, not a D-Bus tuple fragment.

`moos-apply-theme` reconciles wallpaper drift on EVERY login by comparing what
the desktop currently shows against the active look's package. That comparison
is only as good as the readback, and the readback parsed `gdbus` output with a
character class that excluded `"` — while gdbus quotes strings with `'`:

    ('WPV:/usr/share/wallpapers/MoOSUI2Arena',)

so the extracted value kept a trailing `',)` and could never equal the package
that had just been written. Measured on the Cloud host, every login logged

    steady-state: desktop wallpaper '…/MoOSUI2Arena',)' != '…/MoOSUI2Arena' — healing

and re-applied a scene that was already correct: a reconcile that cannot
converge, repeated for the life of the install.

This drives the real function with a stub `gdbus`, so it tests the parsing that
actually ships rather than asserting on the shape of a regex.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APPLY = ROOT / "system_files/usr/bin/moos-apply-theme"
BASH = "/usr/bin/bash" if Path("/usr/bin/bash").exists() else "bash"
PACKAGE = "/usr/share/wallpapers/MoOSUI2Arena"

errors: list[str] = []


def check(condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


def read_back(gdbus_stdout: str) -> str:
    """Run the shipped current_desktop_wallpaper_value against a stub gdbus."""
    source = APPLY.read_text(encoding="utf-8")
    start = source.index("current_desktop_wallpaper_value() {")
    end = source.index("\n}\n", start) + 3
    function = source[start:end]
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        bindir = work / "bin"
        bindir.mkdir()
        stub = bindir / "gdbus"
        stub.write_text("#!/bin/sh\ncat \"$MOOS_TEST_GDBUS_OUT\"\n", encoding="utf-8")
        stub.chmod(0o755)
        out = work / "gdbus.out"
        out.write_text(gdbus_stdout, encoding="utf-8")
        script = work / "probe"
        # HOME is redirected so the file fallback cannot accidentally answer.
        script.write_text(f"{function}\ncurrent_desktop_wallpaper_value\n", encoding="utf-8")
        env = dict(
            os.environ,
            PATH=f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}",
            MOOS_TEST_GDBUS_OUT=str(out),
            HOME=str(work / "home"),
            XDG_CONFIG_HOME=str(work / "home/.config"),
        )
        result = subprocess.run(
            [BASH, str(script)], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=30, env=env,
        )
        return result.stdout.strip()


# The real shape of a gdbus reply: a one-element tuple, single-quoted.
value = read_back(f"('WPV:{PACKAGE}',)\n")
check(value == PACKAGE,
      f"the readback must return the bare path; got {value!r}. A trailing quote or "
      f"tuple punctuation makes the steady-state comparison fail against a wallpaper "
      f"that is already correct, so every login re-applies a scene that never drifted")

# A path that legitimately contains no quote at all must survive unchanged, and a
# double-quoted variant (should gdbus ever change) must not reintroduce the bug.
value = read_back(f'("WPV:{PACKAGE}",)\n')
check(value == PACKAGE, f"double-quoted replies must parse too; got {value!r}")

# An empty desktop list prints nothing useful — the function must fall through
# rather than inventing a value (the file fallback answers, or it fails).
value = read_back("('',)\n")
check(value == "" or value.startswith("/"),
      f"an empty reply must not yield tuple punctuation; got {value!r}")

if errors:
    print("MoOS theme wallpaper-readback test failed:", file=sys.stderr)
    for error in errors:
        print(f" - {error}", file=sys.stderr)
    raise SystemExit(1)

print("OK: the wallpaper readback returns a clean path, so steady-state reconcile "
      "converges instead of healing a correct desktop on every login")
