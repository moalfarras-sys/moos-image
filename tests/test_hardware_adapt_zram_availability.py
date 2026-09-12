#!/usr/bin/env python3
"""Gate: moos-hardware-adapt succeeds on a system without zram, and still sizes zram where it exists.

WHY THIS EXISTS
`moos-hardware-adapt.timer` was switched on for ARM (f15998e9). The ARM image is built FROM
fedora-bootc:44, which ships no zram-generator: none of the ARM boot-proof serial logs on
2026-09-12 has a single zram line, while the x86 ISO install proof's first boot activates
dev-zram0.swap. The adapter's zram step assumed that swap exists, so every ARM first boot tried
`systemctl start dev-zram0.swap`, recorded two failed mutations and exited 1. The ARM runtime
gate reported `moos-hardware-adapt.service loaded failed failed` and the release was not
promoted for ARM (runs 34707148234 and 34710449602).

This runs the REAL script against fake roots, with stub `systemctl`/`sysctl` on an isolated PATH,
so nothing on the host is touched:
  * ARM shape (no zram generator): exit 0, swap never touched, no zram config written, the
    memory-reserve sysctl still applied and the success stamp written;
  * x86 shape (generator present, no active zram yet): the zram path still runs exactly as before.
"""
import os
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

SYSTEMCTL = r'''#!/bin/sh
echo "systemctl $*" >> "$STUB_LOG"
case "$*" in
  "list-unit-files thermald.service"|"list-unit-files fwupd-refresh.timer") exit 1 ;;
  "start dev-zram0.swap")
    if [ -n "$STUB_HAS_ZRAM" ]; then : > "$STUB_ZRAM_ACTIVE"; exit 0; fi
    echo "Failed to start dev-zram0.swap: Unit dev-zram0.swap not found." >&2; exit 5 ;;
  "is-active dev-zram0.swap")
    if [ -e "$STUB_ZRAM_ACTIVE" ]; then echo active; exit 0; fi
    echo inactive; exit 3 ;;
  *) exit 0 ;;
esac
'''


def machine(has_zram: bool) -> dict:
    tmp = Path(tempfile.mkdtemp(prefix="hwadapt-zram-"))
    root, sysfs, procfs, bindir = tmp / "root", tmp / "sys", tmp / "proc", tmp / "bin"
    for d in (root / "etc", root / "run", sysfs / "class/power_supply", sysfs / "bus/pci/devices",
              sysfs / "class/drm", procfs, bindir):
        d.mkdir(parents=True)
    (procfs / "cpuinfo").write_text("processor\t: 0\nCPU implementer\t: 0x41\n")
    (procfs / "meminfo").write_text("MemTotal:        3997540 kB\n")
    (procfs / "swaps").write_text("")
    if has_zram:
        generator = root / "usr/lib/systemd/system-generators/zram-generator"
        generator.parent.mkdir(parents=True)
        generator.write_text("#!/bin/sh\n")
        generator.chmod(0o755)
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
    env = {
        "PATH": str(bindir),
        "HOME": str(tmp),
        "STUB_LOG": str(tmp / "calls.log"),
        "STUB_ZRAM_ACTIVE": str(tmp / "zram-active"),
        "MOOS_HW_ROOT": str(root),
        "MOOS_HW_SYSFS": str(sysfs),
        "MOOS_HW_PROCFS": str(procfs),
        "MOOS_HW_DRYRUN": "0",
    }
    if has_zram:
        env["STUB_HAS_ZRAM"] = "1"
    result = subprocess.run([str(bindir / "bash"), str(SCRIPT)], env=env,
                            capture_output=True, text=True, timeout=60)
    log = tmp / "calls.log"
    calls = log.read_text().splitlines() if log.exists() else []
    return {"tmp": tmp, "root": root, "result": result, "calls": calls}


def main() -> int:
    errors = []

    arm = machine(has_zram=False)
    try:
        out = arm["result"].stdout + arm["result"].stderr
        if arm["result"].returncode != 0:
            errors.append(f"without zram the adapter exited {arm['result'].returncode}; "
                          f"ARM first boot gets a failed unit:\n{out}")
        if any("dev-zram0.swap" in call for call in arm["calls"]):
            errors.append(f"without zram the adapter touched dev-zram0.swap: {arm['calls']}")
        if (arm["root"] / "etc/systemd/zram-generator.conf").exists():
            errors.append("without zram the adapter wrote a zram-generator.conf nothing will read")
        if not (arm["root"] / "etc/sysctl.d/90-moos-hardware.conf").is_file():
            errors.append("the memory reserve sysctl must still apply on a system without zram")
        if not (arm["root"] / "etc/moos/hardware-adapt.state").is_file():
            errors.append("a successful adaptation without zram must write its success stamp")
    finally:
        shutil.rmtree(arm["tmp"], ignore_errors=True)

    x86 = machine(has_zram=True)
    try:
        out = x86["result"].stdout + x86["result"].stderr
        if x86["result"].returncode != 0:
            errors.append(f"with zram present the adapter exited {x86['result'].returncode}:\n{out}")
        if "systemctl start dev-zram0.swap" not in x86["calls"]:
            errors.append(f"with zram present the zram path no longer runs: {x86['calls']}")
        if not (x86["root"] / "etc/systemd/zram-generator.conf").is_file():
            errors.append("with zram present the RAM-tier zram config must still be written")
    finally:
        shutil.rmtree(x86["tmp"], ignore_errors=True)

    if errors:
        print("GATE FAIL: moos-hardware-adapt zram availability")
        for error in errors:
            print("  -", error)
        return 1
    print("hardware-adapt zram availability gate passed (ARM shape and x86 shape)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
