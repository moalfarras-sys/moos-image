#!/usr/bin/env python3
"""Gate: every edition ships what MoOS's own desktop depends on, whoever supplied it.

WHY THIS EXISTS

The x86 editions build FROM kinoite-main, which carries KDE's full desktop; the ARM edition starts
from bare fedora-bootc and gets only what build-arm.sh names. Anything x86 inherits for free has
to be asked for by name on ARM, and no gate asked. Read on the A1 (moos-arm 44.20260923.568) on
2026-09-24, against the published x86 base:

  * qt6-qttranslations was absent, so Qt never learned that Arabic is right-to-left. The MoOS Bar
    in the Arabic session read left-to-right (brand left, clock right), while the x86 station's
    bar is mirrored, as the design contract requires.
  * pw-dump was absent. moos-privacy-monitor was "active (running)" for the whole session and
    spawned a failing pw-dump every 1.5 s, so the Island's camera/microphone/screen chip could
    never name an app on ARM.
  * moos-theme writes gtk-theme-name=Breeze, and /usr/share/themes held only Default and Emacs;
    kde-gtk-config's gtkconfig module was absent too. Every GTK app fell back to Adwaita.
  * No Sonnet plugin existed, so no KDE text field could spell-check, although the Arabic and
    English Hunspell dictionaries were installed.
  * No ALSA configuration routed ALSA clients into PipeWire.
  * Neither kdialog nor zenity existed, and App Drop's consent question treats "no dialog tool"
    as No: `ask()` returned False on the live A1, so no AppImage or dropped file could ever
    install there, and moos-run-foreign could not prompt either.

This gate names CAPABILITIES, not packages, and checks the finished filesystem of either
architecture, so it does not care which base supplied them. Each check says what the owner loses.
It also reads the bar's own layout template, so an applet the MoOS Bar places, or a status item it
pins, can never be missing from the edition that draws it.
Hardware enumeration also belongs to this contract: lspci and lsusb must be
executable files, so a missing ARM dependency cannot silently hide device gaps.
Store's curated npm recipes likewise require executable system Node/npm. The
image-only runtime proof installs, runs and removes a dependency-free local
package offline, in a private prefix; it never updates owner applications.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

LAYOUT = "usr/share/plasma/layout-templates/org.kde.plasma.desktop.defaultPanel/contents/layout.js"
APPLET_DIRS = ("usr/share/plasma/plasmoids/{id}/metadata.json",
               "usr/lib64/qt6/plugins/plasma/applets/{id}.so",
               "usr/lib/qt6/plugins/plasma/applets/{id}.so")
EXECUTABLE_CAPABILITIES = frozenset(("usr/bin/lspci", "usr/bin/lsusb",
                                     "usr/bin/node", "usr/bin/npm"))
NODE = "/usr/bin/node"
NPM = "/usr/bin/npm"

# (what the owner loses, [alternatives — any one satisfies the check])
CAPABILITIES: list[tuple[str, list[str]]] = [
    ("the device plan identifying PCI graphics/network/audio devices and their bound drivers",
     ["usr/bin/lspci"]),
    ("the hardware report identifying attached USB devices",
     ["usr/bin/lsusb"]),
    ("Store installing and updating its curated npm developer tools",
     ["usr/bin/npm"]),
    ("the system Node runtime used by Store's curated npm developer tools",
     ["usr/bin/node"]),
    ("Arabic right-to-left detection for every Qt and KDE surface, including the MoOS Bar's mirroring",
     ["usr/share/qt6/translations/qtbase_ar.qm"]),
    ("the Island's privacy chip: moos-privacy-monitor reads PipeWire through pw-dump",
     ["usr/bin/pw-dump"]),
    ("GTK 3 apps wearing the theme moos-theme selects (gtk-theme-name=Breeze)",
     ["usr/share/themes/Breeze/gtk-3.0/gtk.css"]),
    ("GTK 4 apps wearing the theme moos-theme selects (gtk-theme-name=Breeze)",
     ["usr/share/themes/Breeze/gtk-4.0/gtk.css"]),
    ("Plasma keeping GTK fonts, icons and cursor in step with the MoOS look",
     ["usr/lib64/qt6/plugins/kf6/kded/gtkconfig.so", "usr/lib/qt6/plugins/kf6/kded/gtkconfig.so"]),
    ("spell checking in KDE text fields",
     ["usr/lib64/qt6/plugins/kf6/sonnet/sonnet_hunspell.so",
      "usr/lib/qt6/plugins/kf6/sonnet/sonnet_hunspell.so"]),
    ("ALSA-only applications playing through PipeWire instead of seizing the sound card",
     ["usr/share/alsa/alsa.conf.d/99-pipewire-default.conf",
      "etc/alsa/conf.d/99-pipewire-default.conf"]),
    ("App Drop's default-No consent dialog: without it every dropped or double-clicked app is refused",
     ["usr/bin/kdialog"]),
]


def applet_exists(root: Path, plugin: str) -> bool:
    return any((root / pattern.format(id=plugin)).exists() for pattern in APPLET_DIRS)


def bar_applets(layout_js: str) -> tuple[list[str], list[str]]:
    """Plugins the MoOS Bar template places, and the status items it pins as always shown."""
    code = re.sub(r"/\*.*?\*/", "", layout_js, flags=re.S)
    code = "\n".join(line.split("//", 1)[0] for line in code.splitlines())
    placed = re.findall(r'panel\.addWidget\("([^"]+)"\)', code)
    shown = re.search(r'writeConfig\("shownItems",\s*"([^"]*)"\)', code)
    pinned = [item for item in (shown.group(1).split(",") if shown else []) if item]
    return placed, pinned


def problems(root: Path) -> list[str]:
    found = []
    for loss, alternatives in CAPABILITIES:
        if not any((root / path).is_file() and os.access(root / path, os.X_OK)
                   if path in EXECUTABLE_CAPABILITIES else (root / path).exists()
                   for path in alternatives):
            found.append(f"{loss} — missing or unusable: {', '.join('/' + p for p in alternatives)}")
    layout = root / LAYOUT
    if not layout.is_file():
        found.append(f"the MoOS Bar template is missing: /{LAYOUT}")
        return found
    placed, pinned = bar_applets(layout.read_text(encoding="utf-8"))
    if not placed:
        found.append("the MoOS Bar template places no applet: the parser no longer matches it")
    for plugin in placed:
        if not applet_exists(root, plugin):
            found.append(f"the MoOS Bar places {plugin}, which this edition does not ship")
    for plugin in pinned:
        if not applet_exists(root, plugin):
            found.append(f"the MoOS Bar pins status item {plugin}, which this edition does not ship")
    return found


def npm_runtime() -> None:
    """Exercise the finished image's fixed providers without a registry or user state."""
    for provider in (NODE, NPM):
        if not Path(provider).is_file() or not os.access(provider, os.X_OK):
            raise RuntimeError(f"Store npm runtime provider is missing or unusable: {provider}")
    with tempfile.TemporaryDirectory(prefix="moos-store-npm-") as temporary:
        base = Path(temporary)
        package = base / "package"
        package.mkdir()
        (package / "package.json").write_text(json.dumps({
            "name": "moos-store-runtime-proof", "version": "1.0.0", "private": True,
            "bin": {"moos-store-runtime-proof": "proof.js"},
        }), encoding="utf-8")
        proof = package / "proof.js"
        proof.write_text(f"#!{NODE}\nprocess.stdout.write('MOOS_NODE_NPM_OK\\n');\n",
                         encoding="utf-8")
        proof.chmod(0o755)
        archive = base / "package.tgz"
        with tarfile.open(archive, "w:gz") as stream:
            stream.add(package, arcname="package")
        prefix = base / "prefix"
        prefix.mkdir()
        sentinel = prefix / "preserve-owner-data"
        sentinel.write_bytes(b"unchanged\n")
        for name in ("user.npmrc", "global.npmrc"):
            (base / name).touch()
        env = {
            "PATH": "/usr/bin:/bin", "HOME": str(base), "LANG": "C.UTF-8",
            "npm_config_cache": str(base / "cache"),
            "npm_config_userconfig": str(base / "user.npmrc"),
            "npm_config_globalconfig": str(base / "global.npmrc"),
            "npm_config_update_notifier": "false",
        }

        def run(argv: list[str], phase: str) -> str:
            try:
                result = subprocess.run(argv, env=env, cwd=base, capture_output=True,
                                        text=True, timeout=30)
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise RuntimeError(f"Store npm runtime {phase} failed: {type(exc).__name__}") from exc
            if result.returncode:
                raise RuntimeError(f"Store npm runtime {phase} exited {result.returncode}")
            return result.stdout

        if run([NODE, "--eval", "process.stdout.write('MOOS_NODE_OK')"], "Node execution") != "MOOS_NODE_OK":
            raise RuntimeError("Store npm runtime Node execution returned unexpected output")
        flags = ["--global", "--prefix", str(prefix), "--offline", "--ignore-scripts",
                 "--no-audit", "--no-fund"]
        run([NPM, "install", *flags, "--", str(archive)], "offline install")
        binary = prefix / "bin/moos-store-runtime-proof"
        if not binary.is_file() or not os.access(binary, os.X_OK):
            raise RuntimeError("Store npm runtime install did not publish its executable")
        if run([str(binary)], "installed executable") != "MOOS_NODE_NPM_OK\n":
            raise RuntimeError("Store npm runtime installed executable returned unexpected output")
        run([NPM, "uninstall", *flags, "--", "moos-store-runtime-proof"], "offline remove")
        if binary.exists() or binary.is_symlink() or sentinel.read_bytes() != b"unchanged\n":
            raise RuntimeError("Store npm runtime remove did not preserve the prefix contract")
    print("MoOS Store npm runtime OK: fixed Node/npm, offline install/run/remove, private prefix")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default="/")
    ap.add_argument("--npm-runtime", action="store_true",
                    help="run the finished image's fixed Node/npm offline lifecycle proof")
    args = ap.parse_args(argv)
    root = Path(args.root)
    found = problems(root)
    for item in found:
        print(f"GATE FAIL: {item}", file=sys.stderr)
    if found:
        print("           An edition that lacks these draws a MoOS that does less than the other "
              "one. Install the capability in that edition's build script.", file=sys.stderr)
        return 1
    if args.npm_runtime:
        if root.resolve() != Path("/"):
            ap.error("--npm-runtime requires the running image root /")
        try:
            npm_runtime()
        except RuntimeError as exc:
            print(f"GATE FAIL: {exc}", file=sys.stderr)
            return 1
    placed, pinned = bar_applets((root / LAYOUT).read_text(encoding="utf-8"))
    print(f"MoOS desktop parity OK: {len(CAPABILITIES)} capabilities, "
          f"{len(placed)} bar applets, {len(pinned)} pinned status items")
    return 0


if __name__ == "__main__":
    sys.exit(main())
