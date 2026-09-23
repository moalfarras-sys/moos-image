#!/usr/bin/env python3
"""Every handler MoOS promises in mimeapps.list must exist in the finished image.

WHY THIS GATE EXISTS
  `system_files/etc/xdg/mimeapps.list` is copied verbatim into every edition, so
  it promises the same handlers on x86 and on ARM. The two images do NOT get
  their applications the same way: the x86 editions build FROM
  ghcr.io/ublue-os/kinoite-main, which already carries KDE's app set, while
  `Containerfile.arm` starts from bare fedora-bootc and gets only what
  `build_files/build-arm.sh` names. Anything the x86 image inherits for free has
  to be asked for by name on ARM, and nothing was checking that it had been.

  Measured on the Oracle A1 on 2026-09-21: the shipped list pointed
  application/pdf, application/postscript and application/epub+zip at
  org.kde.okular.desktop, and that file was not in the ARM image at all.
  `xdg-mime query default application/pdf` answered org.chromium.Chromium.desktop
  — a Flatpak the owner happened to have installed — and application/epub+zip
  answered nothing. On a fresh ARM install with no browser, a double-clicked PDF
  had no handler whatsoever. build.sh's own comment for that package reads
  "documents/PDF are a base OS capability, not an optional browser tab."

  The defect was invisible to the existing check, which greps build.sh for the
  package name and so can only ever describe the x86 editions.

  This reads the FINISHED image, which is the only thing that settles the
  question for both architectures at once: whether the base supplied the app,
  whether a build script installed it, or whether nobody did.

It reads files only — no session bus, no dnf, no network.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Where a .desktop may legitimately live in a finished image. A handler found in
# any of these is reachable by the XDG cascade at runtime.
APPLICATION_DIRS = (
    "usr/share/applications",
    "usr/local/share/applications",
    "var/lib/flatpak/exports/share/applications",
)


def promised_handlers(mimeapps: Path) -> dict[str, list[str]]:
    """Map each promised .desktop id to the mime types that named it.

    Parsed by hand rather than with configparser: a mimeapps.list may legally
    repeat a key across its groups, which configparser rejects outright, and a
    gate that cannot read the file it guards is worse than no gate.
    """
    handlers: dict[str, list[str]] = {}
    for raw in mimeapps.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("["):
            continue
        if "=" not in line:
            continue
        mime, _, value = line.partition("=")
        mime = mime.strip()
        # One mime type may list several handlers, ';'-separated, in preference
        # order. Every one of them is a promise, so every one is checked.
        for entry in value.split(";"):
            entry = entry.strip()
            if entry.endswith(".desktop"):
                handlers.setdefault(entry, []).append(mime)
    return handlers


def missing(root: Path, handlers: dict[str, list[str]]) -> list[tuple[str, list[str]]]:
    absent = []
    for desktop, mimes in sorted(handlers.items()):
        if not any((root / directory / desktop).is_file() for directory in APPLICATION_DIRS):
            absent.append((desktop, mimes))
    return absent


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="/",
                        help="image root to check (default: the running filesystem)")
    arguments = parser.parse_args()

    root = Path(arguments.root)
    mimeapps = root / "etc/xdg/mimeapps.list"
    if not mimeapps.is_file():
        print(f"GATE FAIL: {mimeapps} is missing — MoOS ships this file in every edition",
              file=sys.stderr)
        return 1

    handlers = promised_handlers(mimeapps)
    if not handlers:
        print("GATE FAIL: mimeapps.list promised no handlers at all, which means it was "
              "emptied or could not be parsed", file=sys.stderr)
        return 1

    absent = missing(root, handlers)
    if absent:
        print("GATE FAIL: mimeapps.list promises handlers this image does not contain.",
              file=sys.stderr)
        print("A double-click on these types falls through to whatever the user happens to "
              "have installed, or to nothing at all:", file=sys.stderr)
        for desktop, mimes in absent:
            print(f"  {desktop} is absent, but claims: {', '.join(sorted(set(mimes)))}",
                  file=sys.stderr)
        print("Install the application that owns the .desktop in the build script for THIS "
              "architecture (build.sh for x86, build-arm.sh for ARM — the ARM base ships no "
              "KDE apps), or stop promising the type.", file=sys.stderr)
        return 1

    print(f"MoOS mime handlers OK: {len(handlers)} promised handler(s) present in the image.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
