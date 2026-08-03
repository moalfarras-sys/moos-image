#!/usr/bin/env python3
"""MoKernel must declare only what MoOS actually ships.

`mokernel` reads the RUNNING kernel and compares it against a declared policy.
That is only trustworthy while the declaration and the shipped configuration
agree — the moment they diverge, the tool becomes the most confident liar in
the image: it would report a value as "live" that no file sets, or report drift
against a value MoOS never asked for.

This gate holds the two halves together:

  * every sysctl mokernel declares must be set to that exact value by a file
    under system_files/usr/lib/sysctl.d/,
  * every module it declares must be preloaded by modules-load.d,
  * every karg it declares must appear in a bootc kargs.d entry,
  * and every knob those files set must be declared — the direction that
    catches a setting quietly added and never surfaced to the user.

The last one matters most. This repository already shipped
`net.core.default_qdisc=fq` that the kernel REJECTED on every boot for months,
because sch_fq is a module and nothing loaded it. The file was right, the
kernel disagreed, and nothing was watching. mokernel is the thing that watches;
this is the thing that watches mokernel.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "system_files/usr/bin/mokernel"
SYSCTL_DIR = ROOT / "system_files/usr/lib/sysctl.d"
MODULES_DIR = ROOT / "system_files/usr/lib/modules-load.d"
KARGS_DIR = ROOT / "system_files/usr/lib/bootc/kargs.d"

errors: list[str] = []


def check(condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


check(CLI.is_file(), "system_files/usr/bin/mokernel is missing")
cli_text = CLI.read_text(encoding="utf-8")
check(CLI.stat().st_mode & 0o111 != 0, "mokernel must be executable")

# ── Parse the declared policy out of the shipped script ───────────────────────
policy_block = re.search(r'^POLICY="\n(.*?)^"', cli_text, re.MULTILINE | re.DOTALL)
check(policy_block is not None, "mokernel no longer contains a POLICY block")

declared_sysctl: dict[str, str] = {}
declared_modules: set[str] = set()
declared_kargs: set[str] = set()
if policy_block:
    for line in policy_block.group(1).splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("|")
        check(len(parts) == 4,
              f"malformed policy line (want kind|name|expected|why): {line!r}")
        if len(parts) != 4:
            continue
        kind, name, want, why = parts
        check(len(why.strip()) > 20,
              f"policy entry {name!r} has no real justification — a knob nobody can "
              f"defend is one the next reader deletes")
        if kind == "sysctl":
            declared_sysctl[name] = want
        elif kind == "module":
            declared_modules.add(name)
            check(want == "loaded", f"module policy {name!r} must expect 'loaded'")
        elif kind == "karg":
            declared_kargs.add(name)
            check(want == "present", f"karg policy {name!r} must expect 'present'")
        else:
            errors.append(f"unknown policy kind {kind!r} in mokernel")

check(len(declared_sysctl) >= 8,
      f"only {len(declared_sysctl)} sysctls declared — the policy looks truncated")

# ── What the image actually ships ─────────────────────────────────────────────
shipped_sysctl: dict[str, str] = {}
for conf in sorted(SYSCTL_DIR.glob("*.conf")):
    for line in conf.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        shipped_sysctl[key.strip()] = value.strip()

shipped_modules: set[str] = set()
for conf in sorted(MODULES_DIR.glob("*.conf")):
    for line in conf.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            shipped_modules.add(line)

shipped_kargs: set[str] = set()
for toml in sorted(KARGS_DIR.glob("*.toml")):
    for match in re.finditer(r'"([^"]+)"', toml.read_text(encoding="utf-8")):
        shipped_kargs.add(match.group(1))

# ── Declaration → shipping: mokernel may not claim what nothing sets ──────────
for name, want in declared_sysctl.items():
    if name not in shipped_sysctl:
        errors.append(
            f"mokernel declares sysctl {name}={want}, but no file under "
            f"usr/lib/sysctl.d sets it — the tool would report the kernel's own "
            f"default as MoOS policy, or report drift MoOS never asked for")
    elif shipped_sysctl[name] != want:
        errors.append(
            f"mokernel declares {name}={want} but the image ships "
            f"{name}={shipped_sysctl[name]} — one of the two is wrong and the "
            f"tool is the one users will believe")

for module in declared_modules:
    check(module in shipped_modules,
          f"mokernel declares module {module!r} but modules-load.d never loads it. "
          f"This is the exact shape of the sch_fq bug: a policy that reads correct "
          f"and a kernel that silently ignores it")

for karg in declared_kargs:
    check(karg in shipped_kargs,
          f"mokernel declares karg {karg!r} but no kargs.d entry contains it")

# ── Shipping → declaration: nothing MoOS sets may be invisible ────────────────
# Scoped to the desktop policy file. Edition-specific and hardware files
# (cloud console, simpledrm, splash) are deliberately not user-facing policy.
desktop_conf = SYSCTL_DIR / "90-moos-desktop.conf"
if desktop_conf.is_file():
    for line in desktop_conf.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if "=" not in line:
            continue
        key = line.partition("=")[0].strip()
        check(key in declared_sysctl,
              f"90-moos-desktop.conf sets {key} but mokernel does not declare it — "
              f"a setting the user cannot see is one nobody can verify or defend")

if errors:
    print("MoKernel policy gate failed:", file=sys.stderr)
    for error in errors:
        print(f" - {error}", file=sys.stderr)
    raise SystemExit(1)

print(f"OK: MoKernel declares {len(declared_sysctl)} sysctls, {len(declared_modules)} "
      f"modules and {len(declared_kargs)} kargs, and every one of them is shipped "
      f"by a real file — and every desktop sysctl MoOS ships is declared")
