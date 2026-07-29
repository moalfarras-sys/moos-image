#!/usr/bin/env python3
"""Gate: moos-open's session routes must resolve the D-Bus CLI by its real name.

WHY THIS EXISTS

Plasma 6 ships the Qt D-Bus tool as `qdbus-qt6`; there is no `qdbus6` on the image.
moos-open hardcoded `qdbus6` for session/logout and session/power as their SOLE mechanism:

    confirm "…" && command -v qdbus6 >/dev/null 2>&1 && qdbus6 org.kde.Shutdown … || true

With qdbus6 absent, `command -v qdbus6` is false, the && chain short-circuits to `|| true`,
and the route confirmed the action, took the user's Yes, and did NOTHING — a
confirm-then-nothing dead action on the public moos:// dispatcher. The installer routes put
qdbus6 as a 3rd fallback after systemctl/loginctl, so they still worked, but silently lost
their intended last-resort branch.

This runs the REAL qdbus_run resolver (extracted from the script) against a PATH where only
qdbus-qt6 exists, and asserts the session routes go through it rather than a bare qdbus6.
"""

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "system_files/usr/bin/moos-open"


def extract_function(name: str, text: str) -> str:
    m = re.search(rf"^{re.escape(name)}\(\)\s*\{{.*?^\}}", text, re.S | re.M)
    return m.group(0) if m else ""


def main() -> int:
    if not SCRIPT.is_file():
        print(f"GATE FAIL: {SCRIPT.relative_to(ROOT)} is missing.")
        return 1

    text = SCRIPT.read_text(encoding="utf-8")
    errors: list[str] = []

    qdbus_run = extract_function("qdbus_run", text)
    if not qdbus_run:
        errors.append("moos-open defines no qdbus_run() resolver — the session routes would depend "
                      "on a hardcoded binary name again.")

    # Functional: with ONLY qdbus-qt6 on PATH (the real Plasma 6 case), qdbus_run must find and run
    # it. We stub qdbus-qt6 as a script that records it was called with the right first arg.
    if qdbus_run:
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / "called"
            stub = Path(tmp) / "qdbus-qt6"
            stub.write_text(f'#!/bin/sh\necho "$@" > "{marker}"\nexit 0\n')
            stub.chmod(0o755)
            # A deliberately minimal PATH: coreutils for `command`, plus our stub dir. No qdbus6.
            harness = f'{qdbus_run}\nqdbus_run org.kde.Shutdown /Shutdown logout\n'
            env = dict(os.environ, PATH=f"{tmp}:/usr/bin:/bin")
            result = subprocess.run(["bash", "-c", harness], env=env, capture_output=True, text=True, timeout=15)
            if result.returncode != 0:
                errors.append(f"qdbus_run failed to resolve qdbus-qt6 (rc={result.returncode}, "
                              f"stderr={result.stderr.strip()!r}) — the session action would do nothing.")
            elif not marker.exists() or "org.kde.Shutdown" not in marker.read_text():
                errors.append("qdbus_run did not invoke qdbus-qt6 with the Shutdown args.")

    # Source-level: no bare `qdbus6` invocation may remain outside the resolver's candidate list, and
    # the session routes must call qdbus_run.
    for lineno, line in enumerate(text.splitlines(), 1):
        if re.search(r"\bqdbus6\s+org\.kde", line):
            errors.append(f"line {lineno}: a bare `qdbus6 org.kde…` invocation remains — it must go "
                          f"through qdbus_run so qdbus-qt6 is found.")
    if re.search(r"session/logout\).*command -v qdbus6", text, re.S):
        errors.append("session/logout still gates on `command -v qdbus6`, which is always false on "
                      "the image, so it confirms then does nothing.")
    for route in ("session/logout)", "session/power)"):
        idx = text.find(route)
        if idx != -1 and "qdbus_run" not in text[idx:idx + 400]:
            errors.append(f"{route} does not use qdbus_run — its logout/shutdown call would not run.")

    if errors:
        print("GATE FAIL: moos-open's session routes would silently do nothing.\n")
        for e in errors:
            print(f"  - {e}")
        return 1

    print("OK: qdbus_run resolves qdbus-qt6 and the session routes use it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
