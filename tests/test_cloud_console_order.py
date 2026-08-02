#!/usr/bin/env python3
"""The MoOS Cloud console ordering — the karg that wedged a live server.

On 2026-08-02 the owner's netcup VPS stopped launching applications and could
not be rebooted from its own shell. It was not overloaded (load average 0.02):
PID 1 was blocked inside write(2) to /dev/console —

    /proc/1/stack: wait_woken -> n_tty_write -> iterate_tty_write
                   -> redirected_tty_write -> vfs_writev

— because MoOS listed `console=ttyS0,115200n8` LAST, which is how the kernel
decides who gets /dev/console, and nothing on the provider side was draining
that UART. A systemd stuck in write() answers no D-Bus and reaps no children,
so every service start, every app launch and `systemctl` itself hung.

The rules this file holds:
  * the kernel log still goes to the serial console (the karg stays), and
  * /dev/console is a virtual terminal, which cannot block on a missing reader.

Both are one property of the ORDER of the console= arguments, so the order is
what gets gated — a set-comparison would pass the broken configuration.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD_SH = (ROOT / "build_files/build.sh").read_text(encoding="utf-8")
SCRIPT = ROOT / "system_files/usr/libexec/moos-cloud-console-order"
UNIT = ROOT / "system_files/usr/lib/systemd/system/moos-cloud-console-order.service"
BASH = "/usr/bin/bash" if Path("/usr/bin/bash").exists() else "bash"

errors: list[str] = []


def check(condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


# ── 1. The shipped kargs: serial present, but tty0 last ────────────────────────
karg_lines = [
    line for line in BUILD_SH.splitlines()
    if line.strip().startswith("kargs = [") and "console=" in line
]
check(len(karg_lines) == 1,
      f"expected exactly one cloud console kargs line in build.sh, found {len(karg_lines)}")
if karg_lines:
    consoles = re.findall(r'"(console=[^"]+)"', karg_lines[0])
    check(any(c.startswith("console=ttyS") for c in consoles),
          "the serial console karg is gone — a boot that fails before the network "
          "would be invisible, which is why it was added")
    check(consoles and consoles[-1] == "console=tty0",
          f"console=tty0 must be LAST so /dev/console is a virtual terminal; got "
          f"{consoles!r}. With a ttyS last, a provider console that stops draining "
          f"blocks PID 1 inside write() and the whole machine stops launching apps")

# ── 2. The one-shot repair for machines already installed ─────────────────────
check(SCRIPT.is_file() and os.access(SCRIPT, os.X_OK),
      "moos-cloud-console-order must ship executable: bootc's kargs.d diff cannot "
      "reorder an unchanged argument set, so existing installs never get the fix")
check("systemctl enable moos-cloud-console-order.service" in BUILD_SH,
      "the repair unit must be enabled by the cloud build, or it never runs")
unit = UNIT.read_text(encoding="utf-8")
check("ConditionPathExists=!/var/lib/moos/console-order-repaired.v1" in unit,
      "the repair must be marker-guarded so it stages a deployment at most once")
check("WantedBy=multi-user.target" in unit, "the repair unit must be wanted by a target")

# ── 3. The script's decision, exercised for real ──────────────────────────────
# Command doubles only; nothing here touches rpm-ostreed or a real /proc.
def run_with_cmdline(cmdline: str, *, transaction: str = "") -> tuple[int, str, str]:
    """Run the script against a fake /proc/cmdline and a recording rpm-ostree."""
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        bindir = work / "bin"
        bindir.mkdir()
        log = work / "kargs.log"
        cmdline_file = work / "cmdline"
        cmdline_file.write_text(cmdline, encoding="utf-8")
        transaction_json = f'"{transaction}"' if transaction else "null"
        (bindir / "rpm-ostree").write_text(
            "#!/bin/sh\n"
            'if [ "$1" = "status" ]; then\n'
            f"    printf '%s\\n' '{{\"transaction\":{transaction_json}}}'\n"
            'elif [ "$1" = "kargs" ]; then\n'
            '    printf "%s\\n" "$@" > "$MOOS_TEST_KARGS_LOG"\n'
            "fi\n",
            encoding="utf-8",
        )
        (bindir / "rpm-ostree").chmod(0o755)
        # The script reads /proc/cmdline and writes /var/lib/moos; redirect both
        # by running a copy whose two absolute paths point into the sandbox.
        source = SCRIPT.read_text(encoding="utf-8")
        source = source.replace("/proc/cmdline", str(cmdline_file))
        source = source.replace("state_dir=/var/lib/moos", f"state_dir={work}/state")
        patched = work / "script"
        patched.write_text(source, encoding="utf-8")
        patched.chmod(0o755)
        env = os.environ.copy()
        env["PATH"] = f"{bindir}{os.pathsep}{env.get('PATH', '')}"
        env["MOOS_TEST_KARGS_LOG"] = str(log)
        result = subprocess.run(
            [BASH, str(patched)], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=30, env=env,
        )
        return (
            result.returncode,
            log.read_text(encoding="utf-8") if log.exists() else "",
            result.stdout,
        )


UNSAFE = "root=UUID=x rw console=tty0 console=ttyS0,115200n8 video=Virtual-1:1920x1080@60"
SAFE = "root=UUID=x rw console=ttyS0,115200n8 console=tty0 video=Virtual-1:1920x1080@60"

# The machine that wedged: repair it, and append the safe order.
code, kargs, out = run_with_cmdline(UNSAFE)
check(code == 0, f"the unsafe case must exit 0 after repairing; stdout={out!r}")
check("--delete=console=ttyS0,115200n8" in kargs and "--delete=console=tty0" in kargs,
      f"both console kargs must be deleted before re-appending; got {kargs!r}")
appends = [line for line in kargs.splitlines() if line.startswith("--append=console=")]
check(appends == ["--append=console=ttyS0,115200n8", "--append=console=tty0"],
      f"the repair must re-append serial first and tty0 last; got {appends!r}")

# A machine that is already safe must not stage a deployment for nothing.
code, kargs, out = run_with_cmdline(SAFE)
check(code == 0, "the safe case must exit 0")
check(kargs == "", f"a safe machine must never be rewritten; got {kargs!r}")

# A machine with no console= at all is not ours to reconfigure.
code, kargs, _ = run_with_cmdline("root=UUID=x rw quiet")
check(code == 0 and kargs == "", "a machine with no console karg must be left alone")

# Never race the updater.
code, kargs, _ = run_with_cmdline(UNSAFE, transaction="upgrade")
check(code == 0, "a busy sysroot must be a clean skip, not a failure")
check(kargs == "", f"the repair must not run during a transaction; got {kargs!r}")

if errors:
    print("MoOS cloud console-order test failed:", file=sys.stderr)
    for error in errors:
        print(f" - {error}", file=sys.stderr)
    raise SystemExit(1)

print("OK: /dev/console is a virtual terminal on MoOS Cloud, the serial log survives, "
      "and installed machines repair their own karg order exactly once")
