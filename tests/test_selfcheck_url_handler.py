#!/usr/bin/env python3
"""moos:// must be checked by what it RUNS, not by what it is called.

WHY THIS GATE EXISTS
--------------------
`xdg-mime query default x-scheme-handler/moos` returns a desktop-entry NAME.
Which FILE that name resolves to is decided by XDG precedence, and
~/.local/share/applications wins over /usr/share/applications. The name can
therefore be exactly right while the entry that actually runs is a stale copy in
$HOME pointing at a program that no longer exists.

MEASURED ON THE ORACLE A1, 2026-09-08.
~/.local/share/applications/org.moos.urlhandler.desktop carried

    Exec=/var/home/moos/moos-desktop-edit/system_files/usr/bin/moos-open %u

-- a path inside a working copy that had since been deleted. Every moos:// link
on the machine (Mo Store install links, Settings routes, Mo AI's app links) was
dead, and moos-selfcheck printed "moos:// links route to MoOS" the whole time,
because the NAME matched. That is the same green-check trap as the $HOME unit
shadowing, on a different surface.

The check now resolves the file by XDG precedence, extracts argv[0] of Exec=
with the field codes dropped, and requires it to be executable -- and warns
separately when the winning entry is not the image's copy, because a $HOME entry
that happens to work today still freezes at whatever it said when it was written.

This gate executes the REAL section out of the shipped script against stubbed
`xdg-mime` and synthetic data dirs, so it cannot drift from what runs.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SELFCHECK = ROOT / "system_files/usr/bin/moos-selfcheck"

START = "# THE NAME IS NOT THE HANDLER.\n"
END = "esac\n"


def extract_section() -> str:
    text = SELFCHECK.read_text()
    assert text.count(START) == 1, "the moos:// handler section's marker moved"
    body = text[text.index(START):]
    body = body[: body.index(END) + len(END)]
    assert "xdg-mime query default" in body, "extracted the wrong block"
    return (
        "set -uo pipefail\n"
        'ok()   { printf "OK %s\\n" "$1"; }\n'
        'bad()  { printf "BAD %s\\n" "$1"; }\n'
        'note() { printf "NOTE %s\\n" "$1"; }\n'
        + body
    )


def run(entries, handler_name="org.moos.urlhandler.desktop"):
    """Build a synthetic machine and run the real section against it.

    entries maps 'home'/'system' to the program its Exec= should name, or None
    to omit that file entirely.
    """
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        data_home = tmp / "home/.local/share"
        system = tmp / "usr/share"
        for root in (data_home, system):
            (root / "applications").mkdir(parents=True)

        # A program that really is executable, for the healthy cases.
        real = tmp / "usr/bin/moos-open"
        real.parent.mkdir(parents=True, exist_ok=True)
        real.write_text("#!/usr/bin/env bash\nexit 0\n")
        real.chmod(0o755)

        for where, program in entries.items():
            if program is None:
                continue
            root = data_home if where == "home" else system
            (root / "applications" / handler_name).write_text(
                "[Desktop Entry]\nType=Application\nName=MoOS\n"
                f"Exec={program.replace('__REAL__', str(real))} %u\n"
                "MimeType=x-scheme-handler/moos;\n")

        bindir = tmp / "bin"; bindir.mkdir()
        stub = bindir / "xdg-mime"
        stub.write_text(f'#!/usr/bin/env bash\nprintf "%s\\n" "{handler_name}"\n')
        stub.chmod(0o755)

        script = tmp / "section.sh"
        script.write_text(extract_section())
        proc = subprocess.run(
            ["bash", str(script)], capture_output=True, text=True, timeout=60,
            env={"PATH": f"{bindir}:/usr/bin:/bin", "HOME": str(tmp / "home"),
                 "XDG_DATA_HOME": str(data_home), "XDG_DATA_DIRS": str(system)},
        )
        return (proc.stdout + proc.stderr).strip()


CASES = [
    # (name, entries, must_contain, must_not_contain)
    ("the real A1 failure: $HOME entry naming a deleted program",
     {"home": "/var/home/moos/moos-desktop-edit/usr/bin/moos-open", "system": "__REAL__"},
     "is not executable", None),
    ("a WORKING $HOME entry still shadows the image and freezes it",
     {"home": "__REAL__", "system": "__REAL__"},
     "not the image copy", None),
    ("the healthy case: only the image's entry, program present",
     {"home": None, "system": "__REAL__"},
     "OK moos:// links route to MoOS", "BAD"),
    ("the name resolves to no file at all",
     {"home": None, "system": None},
     "no such entry exists", None),
]


def main():
    problems = []
    for name, entries, must_contain, must_not in CASES:
        out = run(entries)
        if must_contain not in out:
            problems.append(f"{name}: expected {must_contain!r}, got {out!r}")
        if must_not and must_not in out:
            problems.append(f"{name}: unexpected {must_not!r} in {out!r}")

    out = run({"home": None, "system": None}, handler_name="")
    if "nothing handles moos://" not in out:
        problems.append(f"an absent handler was not reported; got {out!r}")

    if problems:
        print("FAIL: the moos:// handler check is wrong:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    print(f"OK: moos:// is judged by the program it would run, not by its name "
          f"({len(CASES) + 1} cases)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
