#!/usr/bin/env python3
"""Gate: moos-hardware-adapt's zram step succeeds on every zram shape a MoOS edition boots with.

WHY THIS EXISTS
`moos-hardware-adapt.timer` was switched on for ARM (f15998e9), and from then on every ARM qcow2
boot proof ended with `moos-hardware-adapt.service loaded failed failed`. PR #87 guarded the zram
step on "the fedora-bootc ARM base ships no zram-generator". That premise was false: the ARM image
ships zram-generator, zram.ko, zramctl and systemd-zram-setup@.service. What it lacks is the
DEFAULT zram config that x86 Kinoite ships, so on an ARM first boot the generator exists but has
produced no dev-zram0.swap. The adapter's apply then began with
`systemctl stop dev-zram0.swap systemd-zram-setup@zram0.service`, and real systemd answers a stop
of a unit that is not loaded with exit 5 (`reset-failed` with exit 1): a failed mutation, and a
failed unit, for a swap that was never running. The first version of this gate could not see it —
its stub systemctl answered 0 to everything except `start`.

The stub below models systemd's real answers: dev-zram0.swap exists only after a daemon-reload
with a zram config on disk (or from boot, when a default config shipped), and stop, reset-failed
and start of it fail with systemd's exit codes while it does not. The REAL script runs against
fake roots with stub `systemctl`/`sysctl` on an isolated PATH, so nothing on the host is touched:
  * ARM first boot (generator, no default config, no swap): exit 0, no command against a unit
    that does not exist, the tier config written, ONE start, swap active, success stamp written;
  * x86 re-tier (generator, default config, swap active at another size): the full
    stop -> daemon-reload -> reset-failed -> start apply still runs, in that order, exit 0;
  * the same re-tier while `systemctl show` cannot answer: /proc/swaps lists the active swap,
    so it is still stopped instead of the old size being stamped as adapted;
  * no generator at all: exit 0, the zram stack never touched, no zram config, and the
    reclaim reserve and success stamp still applied.
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "system_files/usr/libexec/moos-hardware-adapt"
# Real tools the script needs; anything else (ddcutil, thermald, ...) is deliberately absent.
TOOLS = ("bash", "sh", "cat", "grep", "awk", "sed", "sort", "tr", "mkdir", "rm", "date",
         "dirname", "basename", "sha256sum", "timeout", "python3", "env")
GIB = 1024 * 1024 * 1024

# Exit codes and messages are systemd's own, measured with `systemctl --user` on a unit that
# does not exist: stop -> 5 "not loaded", reset-failed -> 1 "not loaded".
SYSTEMCTL = r'''#!/bin/sh
echo "systemctl $*" >> "$STUB_LOG"
units_exist() { [ -e "$STUB_ZRAM_UNITS" ]; }
refuse() { echo "FAILED systemctl $1" >> "$STUB_LOG"; echo "$2" >&2; exit "$3"; }
case "$*" in
  "list-unit-files thermald.service"|"list-unit-files fwupd-refresh.timer") exit 1 ;;
  "show -p LoadState --value dev-zram0.swap")
    if [ -n "${STUB_SHOW_FAILS:-}" ]; then
      echo "Failed to get properties: Connection timed out" >&2; exit 1
    fi
    if units_exist; then echo loaded; else echo not-found; fi
    exit 0 ;;
  "daemon-reload")
    if [ -n "$STUB_HAS_GENERATOR" ] && { [ -e "$MOOS_HW_ROOT/etc/systemd/zram-generator.conf" ] \
        || [ -e "$MOOS_HW_ROOT/usr/lib/systemd/zram-generator.conf" ]; }; then
      : > "$STUB_ZRAM_UNITS"
    fi
    exit 0 ;;
  "stop dev-zram0.swap systemd-zram-setup@zram0.service")
    if units_exist; then rm -f "$STUB_ZRAM_ACTIVE"; exit 0; fi
    refuse "$*" "Failed to stop dev-zram0.swap: Unit dev-zram0.swap not loaded." 5 ;;
  "reset-failed dev-zram0.swap systemd-zram-setup@zram0.service")
    if units_exist; then exit 0; fi
    refuse "$*" "Failed to reset failed state of unit dev-zram0.swap: Unit dev-zram0.swap not loaded." 1 ;;
  "start dev-zram0.swap")
    if units_exist; then : > "$STUB_ZRAM_ACTIVE"; exit 0; fi
    refuse "$*" "Failed to start dev-zram0.swap: Unit dev-zram0.swap not found." 5 ;;
  "is-active dev-zram0.swap")
    if [ -e "$STUB_ZRAM_ACTIVE" ]; then echo active; exit 0; fi
    echo inactive; exit 3 ;;
  *zram*)
    refuse "$*" "unexpected zram command in the stub: $*" 1 ;;
  *) exit 0 ;;
esac
'''


def machine(*, generator: bool, default_config: bool, mem_kb: int, active_bytes: int = 0,
            show_fails: bool = False) -> dict:
    tmp = Path(tempfile.mkdtemp(prefix="hwadapt-zram-"))
    root, sysfs, procfs, bindir = tmp / "root", tmp / "sys", tmp / "proc", tmp / "bin"
    for d in (root / "etc", root / "run", sysfs / "class/power_supply", sysfs / "bus/pci/devices",
              sysfs / "class/drm", procfs, bindir):
        d.mkdir(parents=True)
    (procfs / "cpuinfo").write_text("processor\t: 0\nCPU implementer\t: 0x41\n")
    (procfs / "meminfo").write_text(f"MemTotal:        {mem_kb} kB\n")
    (procfs / "swaps").write_text("Filename\tType\tSize\tUsed\tPriority\n")
    env = {
        "PATH": str(bindir),
        "HOME": str(tmp),
        "STUB_LOG": str(tmp / "calls.log"),
        "STUB_ZRAM_UNITS": str(tmp / "zram-units-generated"),
        "STUB_ZRAM_ACTIVE": str(tmp / "zram-active"),
        "MOOS_HW_ROOT": str(root),
        "MOOS_HW_SYSFS": str(sysfs),
        "MOOS_HW_PROCFS": str(procfs),
        "MOOS_HW_DRYRUN": "0",
    }
    if show_fails:
        env["STUB_SHOW_FAILS"] = "1"
    if generator:
        path = root / "usr/lib/systemd/system-generators/zram-generator"
        path.parent.mkdir(parents=True)
        path.write_text("#!/bin/sh\n")
        path.chmod(0o755)
        env["STUB_HAS_GENERATOR"] = "1"
    if default_config:
        (root / "usr/lib/systemd").mkdir(parents=True, exist_ok=True)
        (root / "usr/lib/systemd/zram-generator.conf").write_text("[zram0]\nzram-size = min(ram, 8192)\n")
        Path(env["STUB_ZRAM_UNITS"]).touch()
    if active_bytes:
        (procfs / "swaps").write_text("Filename\tType\tSize\tUsed\tPriority\n"
                                      f"/dev/zram0\tpartition\t{active_bytes // 1024}\t0\t100\n")
        (sysfs / "block/zram0").mkdir(parents=True)
        (sysfs / "block/zram0/disksize").write_text(f"{active_bytes}\n")
        Path(env["STUB_ZRAM_ACTIVE"]).touch()
    for name in TOOLS:
        real = shutil.which(name)
        if real:
            (bindir / name).symlink_to(real)
    stubs = {
        "systemctl": SYSTEMCTL,
        "sysctl": '#!/bin/sh\necho "sysctl $*" >> "$STUB_LOG"\nexit 0\n',
        "hostnamectl": "#!/bin/sh\necho vm\n",
        "rpm-ostree": '#!/bin/sh\necho "{}"\n',
        "loginctl": "#!/bin/sh\nexit 0\n",
    }
    for name, body in stubs.items():
        path = bindir / name
        path.write_text(body)
        path.chmod(0o755)
    result = subprocess.run([str(bindir / "bash"), str(SCRIPT)], env=env,
                            capture_output=True, text=True, timeout=60)
    log = tmp / "calls.log"
    lines = log.read_text().splitlines() if log.exists() else []
    return {
        "tmp": tmp,
        "root": root,
        "result": result,
        "calls": [line for line in lines if not line.startswith("FAILED ")],
        "refused": [line[len("FAILED "):] for line in lines if line.startswith("FAILED ")],
        "swap_active": Path(env["STUB_ZRAM_ACTIVE"]).exists(),
    }


def check(name: str, run: dict, errors: list) -> str:
    out = run["result"].stdout + run["result"].stderr
    if run["result"].returncode != 0:
        errors.append(f"{name}: the adapter exited {run['result'].returncode} "
                      f"(a failed moos-hardware-adapt.service):\n{out}")
    if run["refused"]:
        errors.append(f"{name}: systemd would refuse {run['refused']} — a failed mutation on a "
                      f"machine where nothing is wrong")
    if "sysctl --system" not in run["calls"]:
        errors.append(f"{name}: the reclaim reserve was written but never applied: {run['calls']}")
    if not (run["root"] / "etc/sysctl.d/90-moos-hardware.conf").is_file():
        errors.append(f"{name}: the memory reserve sysctl must be written")
    if not (run["root"] / "etc/moos/hardware-adapt.state").is_file():
        errors.append(f"{name}: a successful adaptation must write its success stamp")
    return out


def main() -> int:
    errors: list = []

    # The ARM edition's first boot: fedora-bootc ships the generator but no default config.
    arm = machine(generator=True, default_config=False, mem_kb=3997540)
    try:
        check("ARM first boot", arm, errors)
        conf = arm["root"] / "etc/systemd/zram-generator.conf"
        if not conf.is_file() or "zram-size = ram" not in conf.read_text():
            errors.append("ARM first boot: the RAM-tier zram config must be written")
        starts = arm["calls"].count("systemctl start dev-zram0.swap")
        if starts != 1:
            errors.append(f"ARM first boot: expected ONE start of dev-zram0.swap, got {starts}: {arm['calls']}")
        if not arm["swap_active"]:
            errors.append(f"ARM first boot: zram swap is not active after the apply: {arm['calls']}")
    finally:
        shutil.rmtree(arm["tmp"], ignore_errors=True)

    # An x86 machine with 64 GiB whose default-config swap (8 GiB) is below its tier (16 GiB).
    x86 = machine(generator=True, default_config=True, mem_kb=65000000, active_bytes=8 * GIB)
    try:
        check("x86 re-tier", x86, errors)
        order = ["systemctl stop dev-zram0.swap systemd-zram-setup@zram0.service",
                 "systemctl daemon-reload",
                 "systemctl reset-failed dev-zram0.swap systemd-zram-setup@zram0.service",
                 "systemctl start dev-zram0.swap"]
        missing = [step for step in order if step not in x86["calls"]]
        if missing:
            errors.append(f"x86 re-tier: the apply lost {missing}: {x86['calls']}")
        elif [x86["calls"].index(step) for step in order] != sorted(x86["calls"].index(step) for step in order):
            errors.append(f"x86 re-tier: the apply must run stop -> daemon-reload -> reset-failed -> "
                          f"start, in that order: {x86['calls']}")
        conf = x86["root"] / "etc/systemd/zram-generator.conf"
        if not conf.is_file() or "zram-size = min(ram / 2, 16384)" not in conf.read_text():
            errors.append("x86 re-tier: the 64 GiB tier config must be written")
        if not x86["swap_active"]:
            errors.append(f"x86 re-tier: zram swap is not active after the apply: {x86['calls']}")
    finally:
        shutil.rmtree(x86["tmp"], ignore_errors=True)

    # The same re-tier while `systemctl show` cannot answer (a D-Bus timeout). /proc/swaps still
    # lists the active swap, so it must still be stopped: skipping that stop leaves the 8 GiB swap
    # active, the later start succeeds as a no-op, and the old size is stamped as adapted.
    blind = machine(generator=True, default_config=True, mem_kb=65000000, active_bytes=8 * GIB,
                    show_fails=True)
    try:
        check("x86 re-tier, systemctl show unanswered", blind, errors)
        if "systemctl stop dev-zram0.swap systemd-zram-setup@zram0.service" not in blind["calls"]:
            errors.append("x86 re-tier, systemctl show unanswered: the active swap was never stopped, "
                          f"so the old size would be stamped as adapted: {blind['calls']}")
    finally:
        shutil.rmtree(blind["tmp"], ignore_errors=True)

    bare = machine(generator=False, default_config=False, mem_kb=3997540)
    try:
        check("no zram-generator", bare, errors)
        if any("zram" in call for call in bare["calls"]):
            errors.append(f"no zram-generator: the adapter touched the zram stack: {bare['calls']}")
        if (bare["root"] / "etc/systemd/zram-generator.conf").exists():
            errors.append("no zram-generator: the adapter wrote a zram-generator.conf nothing will read")
    finally:
        shutil.rmtree(bare["tmp"], ignore_errors=True)

    if errors:
        print("GATE FAIL: moos-hardware-adapt zram availability")
        for error in errors:
            print("  -", error)
        return 1
    print("hardware-adapt zram availability gate passed (ARM first boot, x86 re-tier, no generator)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
