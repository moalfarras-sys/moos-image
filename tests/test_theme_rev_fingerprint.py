#!/usr/bin/env python3
"""Gate: shipped shell QML or theme SVG may not change while THEME_REV stands still.

WHY THIS EXISTS

OSTree pins every mtime under /usr to the epoch. Qt's QML disk cache and Plasma's SVG cache are
keyed on mtime, so after an update a changed widget still looks "unchanged" and plasmashell keeps
executing the compiled OLD one. `moos-apply-theme` purges those caches, but only inside its
once-per-`THEME_REV` migration. docs/AGENT_GUIDE.md therefore says: any change to shipped theme
SVGs or plasmoid QML requires bumping THEME_REV.

That rule had no gate. Two tests pin the literal number, which proves only that three files agree
with each other; nothing compared the number with the bytes it stands for.

Wave W5 (PR #111) rewrote org.moos.island and org.moos.search and merged with THEME_REV still at
60, the value W3 had set hours earlier. Every check was green. The ARM pipeline promotes each
green push to `main`, so ARM machines took W3 at rev 60 and then W5 at rev 60: the v60 marker was
already in their home, the purge never ran again, and the Store-job and privacy chips the wave
existed for stayed invisible behind the cached W3 island.

HOW IT WORKS

`tests/theme-rev-fingerprint.json` records, for one THEME_REV, a digest of every shipped file a
frozen-mtime cache can serve stale: QML/JS executed by plasmashell, KWin and the lock screen
(plasmoids, wallpapers, look-and-feel, shells, layout templates, the shared org.moos.ui module,
KWin's MoOS task switcher and scripts) and the Plasma Style and Aurorae SVGs. First-party apps are not covered on purpose: their
launchers export QML_DISABLE_DISK_CACHE=1, so they never read a stale cache.

    bytes changed, THEME_REV unchanged  -> FAIL, and --record refuses. Bump the revision.
    THEME_REV changed, record stale     -> FAIL until `--record` is run.

A revision may also rise with no byte change here (rev 60 repaired config only); that is fine and
only needs `--record`.

    python3 tests/test_theme_rev_fingerprint.py            # the gate
    python3 tests/test_theme_rev_fingerprint.py --record   # after bumping THEME_REV
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APPLY = ROOT / "system_files/usr/bin/moos-apply-theme"
RECORD = ROOT / "tests/theme-rev-fingerprint.json"

# (tree, path components below it that name one package). A package is the unit the failure
# message reports, so a reviewer reads "org.moos.island changed", not one opaque digest.
COVERED: tuple[tuple[str, int], ...] = (
    ("system_files/usr/share/plasma/plasmoids", 1),
    ("system_files/usr/share/plasma/wallpapers", 1),
    ("system_files/usr/share/plasma/look-and-feel", 1),
    ("system_files/usr/share/plasma/shells", 1),
    ("system_files/usr/share/plasma/layout-templates", 1),
    ("system_files/usr/share/plasma/desktoptheme", 1),
    ("system_files/usr/share/aurorae/themes", 1),
    ("system_files/usr/lib64/qt6/qml/org/moos", 1),
    # KWin loads MoOS's task switcher (tabbox) and scripts from /usr/share/kwin and caches their
    # QML/JS in ~/.cache/kwin/qmlcache, which moos-apply-theme purges only on a revision change.
    # Uncovered until THEME_REV 86: a switcher edit without a bump would have been served stale.
    ("system_files/usr/share/kwin/tabbox", 1),
    ("system_files/usr/share/kwin/scripts", 1),
)
SUFFIXES = {".qml", ".js", ".mjs", ".svg", ".svgz"}


def theme_rev() -> int:
    match = re.search(r"^THEME_REV=(\d+)\s*$", APPLY.read_text(encoding="utf-8"), re.MULTILINE)
    if not match:
        raise LookupError("system_files/usr/bin/moos-apply-theme no longer sets THEME_REV=<n>")
    return int(match.group(1))


def package_digests() -> dict[str, str]:
    """One digest per shipped package, over (relative path, content) of every cacheable file."""
    digests: dict[str, str] = {}
    for tree, depth in COVERED:
        base = ROOT / tree
        if not base.is_dir():
            raise LookupError(f"{tree} is missing — if it moved, move it in COVERED too, or the "
                              "files it held silently leave this gate")
        groups: dict[str, list[Path]] = {}
        for path in base.rglob("*"):
            if path.is_file() and path.suffix.lower() in SUFFIXES:
                parts = path.relative_to(base).parts
                name = "/".join(parts[:depth]) if len(parts) > depth else "."
                groups.setdefault(f"{tree.removeprefix('system_files')}/{name}", []).append(path)
        for name, files in groups.items():
            digest = hashlib.sha256()
            for path in sorted(files, key=lambda p: p.relative_to(base).as_posix()):
                digest.update(path.relative_to(base).as_posix().encode("utf-8"))
                digest.update(b"\0")
                digest.update(hashlib.sha256(path.read_bytes()).digest())
            digests[name] = digest.hexdigest()
    return dict(sorted(digests.items()))


def load_record() -> dict:
    if not RECORD.is_file():
        return {}
    return json.loads(RECORD.read_text(encoding="utf-8"))


def changed_packages(old: dict[str, str], new: dict[str, str]) -> list[str]:
    names = sorted(set(old) | set(new))
    out = []
    for name in names:
        if name not in old:
            out.append(f"+ {name} (new)")
        elif name not in new:
            out.append(f"- {name} (removed)")
        elif old[name] != new[name]:
            out.append(f"~ {name}")
    return out


def main(argv: list[str]) -> int:
    try:
        rev = theme_rev()
        current = package_digests()
    except LookupError as exc:
        print(f"GATE FAIL: {exc}")
        return 1
    record = load_record()
    recorded_rev = record.get("theme_rev")
    recorded = record.get("packages", {})
    delta = changed_packages(recorded, current)

    if "--record" in argv:
        if record and delta and recorded_rev == rev:
            print(f"REFUSED: shipped QML/SVG changed but THEME_REV is still {rev}. Recording it "
                  "would hide exactly what this gate exists to catch. Bump THEME_REV in "
                  "system_files/usr/bin/moos-apply-theme (say why in its revision log), move the "
                  "pinned literal in tests/test_moos_ui2.py and tests/verify_user_experience.py, "
                  "then run --record again.\nChanged:")
            for line in delta:
                print(f"   {line}")
            return 1
        RECORD.write_text(json.dumps({
            "_": "Generated by tests/test_theme_rev_fingerprint.py --record. Do not hand-edit: "
                 "a digest that changes without THEME_REV rising is the defect this file exists "
                 "to make visible in review.",
            "theme_rev": rev,
            "packages": current,
        }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        print(f"recorded THEME_REV={rev}: {len(current)} packages")
        return 0

    if not record:
        print("GATE FAIL: tests/theme-rev-fingerprint.json is missing — run "
              "`python3 tests/test_theme_rev_fingerprint.py --record`.")
        return 1
    if delta and recorded_rev == rev:
        print(f"GATE FAIL: shipped shell QML / theme SVG changed but THEME_REV is still {rev}.\n"
              " Existing users already hold the v{0} marker, so moos-apply-theme will never purge "
              "their QML and SVG caches again and they keep running the OLD bytes after the "
              "update (OSTree freezes mtimes; both caches are keyed on mtime).\n"
              " Bump THEME_REV, move the two pinned literals, then run --record.\n"
              " Changed since the recorded revision:".format(rev))
        for line in delta:
            print(f"   {line}")
        return 1
    if recorded_rev != rev or delta:
        print(f"GATE FAIL: THEME_REV is {rev} but tests/theme-rev-fingerprint.json records "
              f"{recorded_rev}. Run `python3 tests/test_theme_rev_fingerprint.py --record` so the "
              "next QML/SVG change is compared with this revision, not an older one.")
        return 1
    print(f"THEME_REV fingerprint gate passed (rev {rev}, {len(current)} cache-served packages "
          "match their recorded bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
