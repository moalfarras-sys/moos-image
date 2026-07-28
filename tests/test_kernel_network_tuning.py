#!/usr/bin/env python3
"""Gate: the kernel network tuning MoOS claims to ship is actually shippable.

WHY THIS EXISTS

Mo PC Remote is how a MoOS desktop is used from a phone, and the thing that decides whether that
feels instant or unusable is not in the agent at all — it is three lines of kernel tuning. That
makes those three lines a product surface, and a product surface with no gate is a product surface
that regresses quietly.

Two failures in particular are silent, and both were live in the tree before this landed:

  1. THE ALGORITHM THAT IS ASKED FOR BUT NEVER REGISTERED.
     sysctl.d asks for `net.ipv4.tcp_congestion_control = bbr`. If tcp_bbr is not loaded by the
     time systemd-sysctl runs, the write fails, systemd logs ONE line, and the machine spends its
     whole life on cubic. Nothing else ever mentions it. Measured on the maintainer's machine
     before the modules-load.d entry existed:

         net.ipv4.tcp_available_congestion_control = reno cubic

     bbr was not on offer at all, though tcp_bbr.ko.xz was sitting in the image. The symptom is
     not an error — it is "the remote is slow again today", which gets blamed on the ISP.

  2. A KEY THAT DOES NOT EXIST. A typo in a sysctl name is not a parse error; systemd-sysctl skips
     unknown keys with a warning nobody reads, and the setting simply never applies.

So: check that the pairing holds, and check that every key MoOS writes is one this kernel actually
has. The second half runs against the RUNNING kernel when there is one and skips honestly when
there is not (a container build host has no /proc/sys), because a gate that pretends to verify
something it cannot reach is worse than one that says so.
"""

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
SYSCTL = ROOT / "system_files/usr/lib/sysctl.d/90-moos-desktop.conf"
MODLOAD_DIR = ROOT / "system_files/usr/lib/modules-load.d"
PROC_SYS = Path("/proc/sys")

# Settings whose absence is a user-visible regression in Mo PC Remote, with the reason, so a future
# reader deleting one has to argue with the reason rather than with the value.
REQUIRED = {
    "net.ipv4.tcp_congestion_control": (
        "bbr", "cubic halves its window on any packet loss; on cellular and relayed links most "
        "loss is not congestion, so the stream collapses on a link with bandwidth to spare"),
    "net.ipv4.tcp_notsent_lowat": (
        None, "without a cap the kernel send buffer hides seconds of already-encoded video below "
        "the agent's own 12-frame latency budget, so the picture lags the input and every "
        "measurement still says the session is healthy"),
    "net.ipv4.tcp_mtu_probing": (
        "1", "Tailscale is WireGuard and its MTU is smaller than the interface claims; where ICMP "
        "is dropped the result is a PMTU black hole that looks exactly like a dead link"),
    "net.core.default_qdisc": (
        "fq", "BBR paces its send rate and needs a scheduler that honours that pacing; with the "
        "default fq_codel the pacing is fought instead of applied, so BBR's whole point is lost. "
        "And the write is not merely ineffective — sch_fq is a module, so on the primary "
        "systemd-sysctl pass it is rejected outright with 'Couldn't write fq', which is the same "
        "silent-on-boot failure as the congestion-control one below"),
}

# Which sysctl VALUES need a kernel module loaded before the sysctl can select them. Both entries
# are the same failure: the algorithm/scheduler is a module, systemd-sysctl runs before it is
# autoloaded, and the write is rejected with one unread log line. modules-load.d, ordered
# After=systemd-modules-load.service, is what registers them in time. Keyed by (sysctl key, value).
NEEDS_MODULE = {
    ("net.ipv4.tcp_congestion_control", "bbr"): "tcp_bbr",
    ("net.core.default_qdisc", "fq"): "sch_fq",
}


def parse(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith(("#", ";")) or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


def main() -> int:
    if not SYSCTL.is_file():
        print(f"GATE FAIL: {SYSCTL.relative_to(ROOT)} is missing — MoOS ships no desktop tuning.")
        return 1

    settings = parse(SYSCTL)
    errors: list[str] = []

    for key, (expected, why) in REQUIRED.items():
        if key not in settings:
            errors.append(f"{key} is not set.\n        Why it matters: {why}")
        elif expected is not None and settings[key] != expected:
            errors.append(f"{key} is '{settings[key]}', expected '{expected}'.\n"
                          f"        Why it matters: {why}")

    # The pairing. This is the class of bug that was actually broken — twice, for the same reason:
    # a module-backed sysctl value written before its module is loaded.
    loaded = {
        line.strip()
        for f in MODLOAD_DIR.glob("*.conf")
        for line in f.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    }
    for (key, value), module in NEEDS_MODULE.items():
        if settings.get(key) == value and module not in loaded:
            errors.append(
                f"sysctl sets {key} = '{value}', which needs the '{module}' module, but\n"
                f"        no file in {MODLOAD_DIR.relative_to(ROOT)} loads it.\n"
                f"        systemd-sysctl.service runs After=systemd-modules-load.service, so listing\n"
                f"        it there is what makes the value selectable before anything selects it.\n"
                f"        Without it the write is rejected and the setting silently never applies.")

    # Every key must be one this kernel has. Only meaningful where there is a kernel to ask.
    if PROC_SYS.is_dir():
        unknown = [k for k in settings if not (PROC_SYS / k.replace(".", "/")).exists()]
        for key in unknown:
            errors.append(f"{key} does not exist on this kernel ({Path('/proc/version').read_text().split()[2]}).\n"
                          f"        systemd-sysctl skips unknown keys with a warning nobody reads, so the\n"
                          f"        setting would never apply and nothing would say so.")
        # A congestion control that is merely *spelled* right is not one the kernel can use.
        cc = settings.get("net.ipv4.tcp_congestion_control", "")
        avail = (PROC_SYS / "net/ipv4/tcp_available_congestion_control")
        if cc and avail.is_file() and cc not in avail.read_text().split():
            print(f"NOTE: '{cc}' is not registered on the running kernel yet "
                  f"(available: {avail.read_text().strip()}).\n"
                  f"      That is expected on a machine that has not booted this image — "
                  f"modules-load.d is what fixes it at boot.")
    else:
        print("NOTE: no /proc/sys here (container build host) — key existence not verified.")

    if errors:
        print("GATE FAIL: the kernel tuning MoOS ships would not do what it says.\n")
        for e in errors:
            print(f"  - {e}")
        return 1

    paired = [f"{key}={value}→{module}" for (key, value), module in NEEDS_MODULE.items()
              if settings.get(key) == value]
    print(f"OK: {len(settings)} sysctl key(s) valid; module-backed values paired with "
          f"modules-load.d ({', '.join(paired) or 'none needed'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
