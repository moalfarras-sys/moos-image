#!/usr/bin/python3
"""Read-only Android runtime state shared by setup, file admission and the Store.

APK identity, signatures and update verification stay in moos_android_apk.
"""
import re
import subprocess
import sys

_PREFIX = r"^\s*(?:\(\d+\)\s*)?(?:\[\d{2}:\d{2}:\d{2}\]\s*)?"
_FAILURE = re.compile(_PREFIX + r"(?:ERROR\s*:|Failure\s*\[|INSTALL_FAILED_[A-Z_]+\b|"
                      r"Failed to access IPlatform service\b|Failed to get service waydroidplatform\b|WayDroid session is stopped\b|"
                      r"WayDroid is not initialized\b)", re.IGNORECASE | re.MULTILINE)

def status_state(code, stdout, stderr=""):
    if code != 0 or len(stdout) + len(stderr) > 65536:
        return "unknown"
    uninitialized = re.compile(_PREFIX + r"WayDroid is not initialized(?:,.*)?\s*$",
                               re.IGNORECASE | re.MULTILINE)
    absent = uninitialized.search(stdout) or uninitialized.search(stderr)
    if any(_FAILURE.search(uninitialized.sub("", s)) for s in (stdout, stderr)):
        return "unknown"
    states = re.findall(r"^Session:\s*(STOPPED|RUNNING|FROZEN)\s*$", stdout, re.MULTILINE)
    if absent:
        return "uninitialized" if not states else "unknown"
    return states[0] if len(states) == 1 else "unknown"

def platform_ready(code, stdout, stderr=""):
    """A session process can run before Android's application service is usable."""
    return code == 0 and len(stdout) + len(stderr) <= 65536 and not any(
        _FAILURE.search(s) for s in (stdout, stderr))

def main():
    if sys.argv[1:] != ["status"]:
        return 2
    try:
        r = subprocess.run(["waydroid", "status"], capture_output=True, text=True, timeout=2)
        print(status_state(r.returncode, r.stdout, r.stderr))
    except (OSError, subprocess.SubprocessError):
        print("unknown")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
