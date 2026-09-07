#!/usr/bin/env python3
"""moos-selfcheck must see code shadowed from $HOME, not just assets.

WHY THIS GATE EXISTS
--------------------
The "Nothing shadowing the image" section of moos-selfcheck states the rule it
exists to enforce: a MoOS file staged into ~/.local or ~/.config outranks the
copy in /usr and freezes it at whatever it said the day it was written, and
that is the most common way a MoOS fix reaches the image and never reaches the
user.

It then checked only ~/.local/share theme assets and one fontconfig file.

MEASURED ON THE ORACLE A1, 2026-09-08. Mo AI's agent-api, control and gateway
services and Mo PC Remote were all executing binaries under ~/.local/lib
(moai-cloud-20260906, mo-remote-v39-20260905), repointed by drop-ins written
during a migration two days earlier, and moai-hermes.service had an entire
replacement unit in $HOME. Four MoOS units were masked to /dev/null. The
image's own copies of all of it had never run on this machine -- and this
section printed "no user-level copy is shadowing a MoOS asset" every time.

That is the green-check trap AGENTS.md describes: the gate was green while the
thing it names was broken.

This gate executes the REAL section out of the shipped moos-selfcheck against a
synthetic pair of trees, so it cannot drift from the code that runs on the
machine, and asserts each of the four shadow shapes is reported -- and that
legitimate user units are NOT reported, because a check that cries wolf about a
user's own service teaches them to ignore it.
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SELFCHECK = ROOT / "system_files/usr/bin/moos-selfcheck"

START = "unit_shadows=0\n"
END = '[ "$unit_shadows" -eq 0 ] && ok "no user unit or drop-in is shadowing MoOS code"'


def extract_section() -> str:
    text = SELFCHECK.read_text()
    assert text.count(START) == 1, "the unit-shadow section's start marker moved"
    assert text.count(END) == 1, "the unit-shadow section's end marker moved"
    body = text[text.index(START): text.index(END) + len(END)]
    # Stubs for the report helpers, so the section runs standalone and every
    # verdict is machine-readable. The logic under test is untouched.
    return (
        "set -uo pipefail\n"
        'ok()   { printf "OK %s\\n" "$1"; }\n'
        'bad()  { printf "BAD %s\\n" "$1"; }\n'
        'note() { printf "NOTE %s\\n" "$1"; }\n'
        + body
        + "\n"
    )


def build_world(tmp: Path):
    """A machine with every shadow shape the real Oracle A1 had, plus decoys."""
    image = tmp / "image-units"
    user = tmp / "home/.config/systemd/user"
    (image / "plasma-kwin_wayland.service.d").mkdir(parents=True)
    user.mkdir(parents=True)

    for unit in ("moai-hermes.service", "moai-gateway.service", "moai-idle.timer",
                 "mo-remote-personal.service", "plasma-kwin_wayland.service"):
        (image / unit).write_text("[Service]\nExecStart=/usr/libexec/real\n")
    (image / "plasma-kwin_wayland.service.d/50-moos-memory-guard.conf").write_text(
        "[Service]\nMemoryHigh=3G\n")

    home = str(tmp / "home")

    # 1. whole-unit replacement of a unit the image ships
    (user / "moai-hermes.service").write_text(
        f"[Service]\nExecStart={home}/.local/lib/staged/moai-hermes serve\n")
    # 2. drop-in repointing ExecStart into $HOME
    d = user / "moai-gateway.service.d"; d.mkdir()
    (d / "99-cloud.conf").write_text(
        f"[Service]\nExecStart=\nExecStart={home}/.local/lib/staged/moai-gateway\n")
    # 2b. same, via Environment= (how Mo Remote was repointed)
    d = user / "mo-remote-personal.service.d"; d.mkdir()
    (d / "99-agent.conf").write_text(
        f"[Service]\nEnvironment=MO_REMOTE_AGENT={home}/.local/lib/staged/MoRemotePersonal\n")
    # 3. drop-in with the same filename as one the image ships
    d = user / "plasma-kwin_wayland.service.d"; d.mkdir()
    (d / "50-moos-memory-guard.conf").write_text("[Service]\nMemoryHigh=1G\n")
    # 4. mask over a unit the image ships
    (user / "moai-idle.timer").symlink_to("/dev/null")

    # ---- decoys that must NOT be reported ----
    # the owner's own service, with no counterpart in the image
    (user / "moos-web-studio.service").write_text(
        f"[Service]\nExecStart={home}/.local/bin/code-server\n")
    # a mask over a unit the image does not ship (already-retired subsystem)
    (user / "ollama.service").symlink_to("/dev/null")
    # a drop-in on a MoOS unit that stays inside the image
    d = user / "moai-idle.timer.d"; d.mkdir()
    (d / "10-cadence.conf").write_text("[Timer]\nOnUnitActiveSec=10min\n")
    return image, home


def main():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        image, home = build_world(tmp)
        script = tmp / "section.sh"
        script.write_text(extract_section())
        proc = subprocess.run(
            ["bash", str(script)],
            capture_output=True, text=True, timeout=60,
            env={
                "PATH": "/usr/bin:/bin", "HOME": home,
                "XDG_CONFIG_HOME": f"{home}/.config",
                "MOOS_SELFCHECK_UNIT_ROOT": str(image),
            },
        )
    out = proc.stdout

    required = [
        ("BAD", "moai-hermes.service", "a unit replacing one the image ships"),
        ("BAD", "moai-gateway.service.d/99-cloud.conf", "ExecStart repointed into $HOME"),
        ("BAD", "mo-remote-personal.service.d/99-agent.conf", "Environment repointed into $HOME"),
        ("BAD", "plasma-kwin_wayland.service.d/50-moos-memory-guard.conf",
         "a drop-in shadowing the image drop-in of the same name"),
        ("NOTE", "moai-idle.timer is masked", "a mask over a unit the image ships"),
    ]
    forbidden = [
        ("moos-web-studio", "the owner's own service has no image counterpart"),
        ("ollama.service", "a mask over a unit the image does not ship"),
        ("10-cadence.conf", "a drop-in that keeps the unit inside the image"),
    ]

    problems = []
    for verdict, needle, why in required:
        if not any(l.startswith(verdict) and needle in l for l in out.splitlines()):
            problems.append(f"not reported as {verdict}: {why} ({needle!r})")
    for needle, why in forbidden:
        if needle in out:
            problems.append(f"false positive: {why} ({needle!r})")
    if "OK no user unit or drop-in is shadowing MoOS code" in out:
        problems.append("reported a clean bill of health on a machine full of shadows")

    if problems:
        print("FAIL: moos-selfcheck's unit-shadow section is wrong:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        print("\n--- section output ---\n" + out, file=sys.stderr)
        if proc.stderr:
            print("--- stderr ---\n" + proc.stderr, file=sys.stderr)
        return 1

    print(f"OK: moos-selfcheck reports all {len(required)} shadow shapes "
          f"and none of the {len(forbidden)} decoys")
    return 0


if __name__ == "__main__":
    sys.exit(main())
