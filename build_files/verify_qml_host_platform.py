#!/usr/bin/env python3
"""Prove Basic controls retain KDE's actual animation setting in the shipped host."""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile

PROBE = '''import QtQuick
import QtQuick.Controls
import org.kde.kirigami as Kirigami
Item {
    Component.onCompleted: {
        console.log("MOOS_KDE_MOTION=" + Kirigami.Units.longDuration)
        Qt.exit(Kirigami.Units.longDuration)
    }
}
'''


def verify(runtime: str, defaults: Path) -> None:
    baseline = defaults.read_text(encoding="utf-8")
    for factor, expected in (("0", 1), ("0.5", 100)):
        with tempfile.TemporaryDirectory(prefix="moos-kde-platform-") as temporary:
            root = Path(temporary)
            config = root / "config"
            config.mkdir()
            (config / "kdeglobals").write_text(baseline, encoding="utf-8")
            subprocess.run(["kwriteconfig6", "--file", str(config / "kdeglobals"),
                            "--group", "KDE", "--key", "AnimationDurationFactor", factor],
                           check=True, capture_output=True, timeout=10)
            run = root / "run"
            run.mkdir(mode=0o700)
            qml = root / "probe.qml"
            qml.write_text(PROBE, encoding="utf-8")
            env = {
                "PATH": "/usr/bin:/bin", "HOME": str(root), "XDG_CONFIG_HOME": str(config),
                "XDG_CONFIG_DIRS": str(config), "XDG_DATA_HOME": str(root / "data"),
                "XDG_DATA_DIRS": "/usr/share", "XDG_CACHE_HOME": str(root / "cache"),
                "XDG_RUNTIME_DIR": str(run), "DBUS_SESSION_BUS_ADDRESS": "unix:path=" + str(root / "no-bus"),
                "QT_QPA_PLATFORM": "offscreen", "QT_QPA_PLATFORMTHEME": "kde",
                "QT_QUICK_BACKEND": "software", "QT_QUICK_CONTROLS_STYLE": "Basic",
                "QML_DISABLE_DISK_CACHE": "1", "QT_FORCE_STDERR_LOGGING": "1",
                "QT_LOGGING_RULES": "qml.debug=true", "LANG": "C.UTF-8", "XDG_CURRENT_DESKTOP": "KDE", "KDE_SESSION_VERSION": "6",
            }
            result = subprocess.run([runtime, "--app-id", "org.moos.platform.review", "--qml", str(qml)],
                                    env=env, capture_output=True, text=True, timeout=20)
            markers = [line.split("MOOS_KDE_MOTION=", 1)[1].strip()
                       for line in (result.stdout + result.stderr).splitlines()
                       if "MOOS_KDE_MOTION=" in line]
            if result.returncode != expected or markers != [str(expected)]:
                raise RuntimeError(f"factor {factor}: expected {expected}, got {markers}; exit={result.returncode}\n"
                                   + (result.stdout + result.stderr)[-3000:])
            print(f"MoOS KDE platform: Basic controls, factor={factor}, duration={expected} ms")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", default="/usr/bin/moos-qml-shell")
    parser.add_argument("--defaults", type=Path, default=Path("/etc/xdg/kdeglobals"))
    args = parser.parse_args()
    try:
        verify(args.runtime, args.defaults)
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        parser.exit(1, f"MoOS KDE platform gate failed: {error}\n")
