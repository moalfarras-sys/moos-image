#!/usr/bin/env python3
"""Gate: a MoOS unit the shared overlay ships must be enabled on ARM too, or listed as an exception.

WHY THIS EXISTS

`system_files/` is copied byte-identical into every edition — that is the identity contract. The
ENABLEMENT is not shared: `build_files/build.sh` builds the three x86 editions and
`build_files/build-arm.sh` builds the native aarch64 one, and each has its own list of
`systemctl enable` lines. Nothing compared them, so units drifted out of the ARM image one at a
time and none of them failed anything.

Read off the maintainer's own Oracle A1, image 44.20260912.353, before this gate existed:

    $ systemctl is-enabled moos-hardware-adapt.timer moos-visual-tier.service \\
                           moos-verify-origin.timer
    disabled
    disabled
    disabled
    $ ls /etc/moos/hardware-adapt.state
    ls: cannot access '/etc/moos/hardware-adapt.state': No such file or directory
    $ mokernel | grep adapted
      ! this machine has not been adapted yet

Three units with correct `[Install]` sections, present in the image, wanted by nothing. The
machine-adaptation pass had never run on an ARM install; neither had the hardware-matched motion
profile, on the one edition — a 2-core software-rendered cloud box — that needs it most; nor the
signed-origin audit.

This is the same shape as the trap `.claude/skills/moos-engineering` already documents (a
`systemctl enable` whose unit has no `[Install]` returns 0 and wires nothing) and the same shape
as `tests/test_gate_coverage.py` (two gate lists, one of them quietly shorter). The rule here is
the same one: divergence is allowed, but it must be DELIBERATE and written down.

So: every `moos-*.service` / `moos-*.timer` in the shared overlay that has an `[Install]` section
and is enabled by build.sh must also be enabled by build-arm.sh, or appear in EXCEPTIONS below
with a reason that is about ARM. Adding a unit to one script and not the other now fails here
instead of shipping.
"""

import re
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UNITS = ROOT / "system_files/usr/lib/systemd/system"
X86 = ROOT / "build_files/build.sh"
ARM = ROOT / "build_files/build-arm.sh"
WORKFLOW = ROOT / ".github/workflows/build-arm.yml"
WANTS = (
    "graphical.target.wants/moos-visual-tier.service",
    "graphical.target.wants/moos-hardware-adapt.timer",
    "timers.target.wants/moos-verify-origin.timer",
    "timers.target.wants/moos-auto-update.timer",
    "timers.target.wants/moos-appstream-refresh.timer",
)

# Units build.sh enables that build-arm.sh deliberately does not. The reason must be about what
# ARM is, never "we did not get to it" — an unexplained entry here is the bug this gate exists to
# stop, dressed up as a decision.
EXCEPTIONS: dict[str, str] = {
    "moos-firstboot.service":
        "ARM is provisioned by cloud-init, which creates the interactive user first; the recipe "
        "file /etc/moos-setup.conf is written by moos-install-to-disk, the x86 installer.",
    "moos-fstab-sanitize.service":
        "the ARM root is assembled by bootc with no obsolete physical-root fstab entry to remove.",
    "moos-firewall-migrate.service":
        "ARM writes its firewall policy directly in build-arm.sh rather than migrating an "
        "inherited one, and re-zoning a machine reachable only over ssh and the tailnet is not a "
        "change to make blind.",
    "moos-live-polish.service":
        "requires livesys.service; there is no ARM live ISO.",
    "moos-cloud-console-order.service":
        "repairs the x86 cloud edition's own console=ttyS0 karg ordering. ARM boots "
        "console=ttyAMA0 then console=tty0, Oracle wires the port up, and serial-getty@ttyAMA0 "
        "runs with NRestarts=0.",
}


def enabled_units(script: Path) -> set[str]:
    """Units named on a `systemctl enable` line, ignoring commented-out lines."""
    found: set[str] = set()
    for line in script.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or "systemctl enable" not in stripped:
            continue
        # Everything after the verb, minus flags, split into words.
        tail = stripped.split("systemctl enable", 1)[1]
        for word in re.split(r"[\s\\]+", tail):
            if word.startswith("-") or not word:
                continue
            if word.endswith((".service", ".timer", ".socket", ".target", ".path")):
                found.add(word)
    return found


def check_image_gate() -> int:
    """Execute the workflow shell, with all writes confined to disposable roots."""
    workflow = WORKFLOW.read_text(encoding="utf-8")
    before, marker, after = workflow.partition("# BEGIN ARM UNIT WIRING GATE\n")
    assert marker, "ARM image wiring gate is missing from its workflow"
    body, marker, _ = after.partition("# END ARM UNIT WIRING GATE")
    assert marker, "ARM image wiring gate has no end marker"
    assert before.rfind("- name: Verify the built image") > before.rfind("- name: Build the image")
    assert workflow.index("# END ARM UNIT WIRING GATE") < workflow.index("- name: Log in to GHCR")
    gate = textwrap.dedent(body)
    checks = 0

    def run_gate(root: Path, healthy: bool, case: str) -> None:
        nonlocal checks
        result = subprocess.run(
            ["bash", "-c", gate, "arm-unit-gate", str(root)],
            text=True, capture_output=True, timeout=10,
        )
        assert (result.returncode == 0) == healthy, (
            f"ARM image wiring gate incorrectly accepted/rejected {case}:\n"
            f"{result.stdout}{result.stderr}"
        )
        if healthy:
            for want in WANTS:
                assert f"enabled: {want}" in result.stdout, f"Gate no longer checks {want}"
        else:
            assert "FATAL:" in result.stdout, f"{case} failed without a gate diagnostic"
        checks += 1

    def link_to(link: Path, target: Path) -> None:
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(os.path.relpath(target, link.parent))

    for layout in ("etc", "usr/etc"):
        with tempfile.TemporaryDirectory(prefix="moos-arm-wiring-") as tmp:
            root = Path(tmp).resolve()
            vendor = root / "usr/lib/systemd/system"
            vendor.mkdir(parents=True)
            config = root / layout / "systemd/system"
            for want in WANTS:
                unit = Path(want).name
                shutil.copyfile(UNITS / unit, vendor / unit)
                link_to(config / want, vendor / unit)
            run_gate(root, True, f"valid {layout} wiring")
            # Exercise every named unit, so omitting one from the workflow cannot go green.
            for want in WANTS:
                link = config / want
                expected = vendor / link.name
                link.unlink()
                run_gate(root, False, f"{layout}/{want} absent")
                link_to(link, vendor / "missing.service")
                run_gate(root, False, f"{layout}/{want} dangling")
                link.unlink()
                wrong = vendor / "wrong.service"
                wrong.write_text("[Service]\nExecStart=/usr/bin/true\n", encoding="utf-8")
                link_to(link, wrong)
                run_gate(root, False, f"{layout}/{want} targeting another unit")
                link.unlink()
                link_to(link, expected)
            if layout == "usr/etc":
                want = WANTS[0]
                # A good immutable link must not conceal bad stronger /etc wiring.
                shadow = root / "etc/systemd/system" / want
                link_to(shadow, root / "dev/null")
                run_gate(root, False, "bad /etc wants shadows correct /usr/etc")
                shadow.unlink()
                override = shadow.parent.parent / shadow.name
                link_to(override, root / "dev/null")
                run_gate(root, False, "masked unit with correct wants")
                override.unlink()
                override.write_text("[Service]\nExecStart=/usr/bin/false\n", encoding="utf-8")
                run_gate(root, False, "replacement unit with correct wants")
                override.unlink()
                link_to(override, vendor / shadow.name)
                run_gate(root, True, "unit alias to its own shipped definition")

    # Preserve the real enable mechanism: ask systemctl to read each shipped [Install].
    with tempfile.TemporaryDirectory(prefix="moos-arm-enable-") as tmp:
        root = Path(tmp).resolve()
        vendor = root / "usr/lib/systemd/system"
        vendor.mkdir(parents=True)
        for want in WANTS:
            unit = Path(want).name
            shutil.copyfile(UNITS / unit, vendor / unit)
        result = subprocess.run(
            ["systemctl", "enable", f"--root={root}", *(Path(want).name for want in WANTS)],
            text=True, capture_output=True, timeout=10,
        )
        assert result.returncode == 0, f"Enabling shipped ARM units failed: {result.stderr}"
        for want in WANTS:
            link = root / "etc/systemd/system" / want
            assert link.is_symlink(), f"systemctl did not create {want}"
            target = link.readlink()
            expected = Path("/usr/lib/systemd/system") / link.name
            if target.is_absolute():
                assert target == expected, f"systemctl enabled {want} to {target}"
                # Resolve against the disposable root without needing privileged chroot.
                link.unlink()
                link_to(link, root / target.relative_to("/"))
        run_gate(root, True, "real systemctl enable output")
    return checks


def main() -> int:
    if not UNITS.is_dir():
        print(f"GATE FAIL: {UNITS.relative_to(ROOT)} is missing.")
        return 1

    shared: set[str] = set()
    for unit in sorted(UNITS.glob("moos-*")):
        if unit.suffix not in (".service", ".timer"):
            continue
        # No [Install] means `systemctl enable` wires nothing at all — a different defect, and
        # tests/test_boot_wiring.py's territory rather than this one's.
        if "[Install]" in unit.read_text(encoding="utf-8"):
            shared.add(unit.name)

    x86 = enabled_units(X86) & shared
    arm = enabled_units(ARM) & shared
    errors: list[str] = []

    for unit in sorted(x86 - arm):
        reason = EXCEPTIONS.get(unit)
        if not reason:
            errors.append(
                f"{unit} is enabled by build.sh and by nothing in build-arm.sh. The overlay ships "
                f"it into the ARM image, so it is present and inert. Enable it in build-arm.sh, or "
                f"add it to EXCEPTIONS in this file with a reason that is about ARM."
            )

    # An exception that no longer describes a divergence is stale, and a stale exception is how a
    # unit gets silently disabled again later.
    for unit, reason in sorted(EXCEPTIONS.items()):
        if unit not in shared:
            errors.append(f"EXCEPTIONS lists {unit}, which is not a shared overlay unit with an [Install].")
        elif unit not in x86:
            errors.append(f"EXCEPTIONS lists {unit}, but build.sh does not enable it either — remove the entry.")
        elif unit in arm:
            errors.append(f"EXCEPTIONS lists {unit}, but build-arm.sh now enables it — remove the entry.")
        elif len(reason) < 40:
            errors.append(f"EXCEPTIONS[{unit}] needs a real reason, not a placeholder.")

    # The three this gate was written for. Named explicitly so a future edit cannot satisfy the
    # comparison above by dropping them from build.sh as well.
    for unit in ("moos-visual-tier.service", "moos-hardware-adapt.timer", "moos-verify-origin.timer"):
        if unit not in arm:
            errors.append(
                f"{unit} must be enabled on ARM. It shipped disabled on the maintainer's A1 for "
                f"months; that is what this gate is here to prevent."
            )

    if errors:
        print("GATE FAIL: the ARM image's unit enablement has drifted from the shared overlay.")
        for error in errors:
            print(f"  - {error}")
        return 1

    print(f"PASS: {len(x86 & arm)} shared MoOS units enabled on both x86 and ARM, "
          f"{len(EXCEPTIONS)} documented ARM exceptions")
    checks = check_image_gate()
    print(f"PASS: ARM workflow wiring shell passed {checks} valid and broken image fixtures")
    return 0


if __name__ == "__main__":
    sys.exit(main())
