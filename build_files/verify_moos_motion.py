#!/usr/bin/env python3
"""Execute the real shared QML interaction test without contacting a desktop."""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile


def verify(qml: Path, imports: Path | None = None) -> int:
    with tempfile.TemporaryDirectory(prefix="moos-motion-") as temporary:
        env = dict(os.environ)
        env.update({
            "HOME": temporary, "XDG_CONFIG_HOME": temporary + "/config",
            "XDG_DATA_HOME": temporary + "/data", "XDG_CACHE_HOME": temporary + "/cache",
            "XDG_CONFIG_DIRS": "/etc/xdg", "XDG_DATA_DIRS": "/usr/share",
            "DBUS_SESSION_BUS_ADDRESS": "unix:path=" + temporary + "/absent-bus",
            "DISPLAY": "", "WAYLAND_DISPLAY": "", "QT_QPA_PLATFORM": "offscreen",
            "QT_QUICK_BACKEND": "software", "QT_FORCE_STDERR_LOGGING": "1",
            "QML_DISABLE_DISK_CACHE": "1", "QT_QUICK_CONTROLS_STYLE": "Basic",
        })
        # Never inherit an editor/user import override in an image gate.
        for key in ("QML_IMPORT_PATH", "QML2_IMPORT_PATH", "QT_PLUGIN_PATH"):
            env.pop(key, None)
        if imports is not None:
            env["QML_IMPORT_PATH"] = str(imports.resolve())
        result = subprocess.run([
            "/usr/bin/moos-qml-shell", "--app-id", "org.moos.motion-review",
            "--qml", str(qml.resolve()),
        ], env=env, text=True, capture_output=True, timeout=20)
        output = result.stdout + result.stderr
        print(output, end="")
        if result.returncode or "MOOS_MOTION_PASSED:" not in output:
            print(f"MoOS motion gate failed (exit {result.returncode})")
            return 1
    print("MoOS motion gate passed on the real Qt runtime")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qml", type=Path, required=True)
    parser.add_argument("--imports", type=Path)
    args = parser.parse_args()
    try:
        return verify(args.qml, args.imports)
    except (OSError, subprocess.TimeoutExpired) as error:
        print(f"MoOS motion gate failed: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
