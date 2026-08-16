#!/usr/bin/env python3
"""Gate: retire_legacy_gateway_unit must retire EVERY installer-generated unit.

WHY THIS EXISTS

`openclaw service install` writes a complete unit into ~/.config/systemd/user.
systemd ranks that above /usr/lib/systemd/user, so it shadows the image's
openclaw-gateway.service forever — and with it the shipped
`ExecStartPre=/usr/libexec/moai-openclaw-preflight`, which is the entire Mo AI
link: it starts the speech engine, resolves and starts the selected Ollama /
moai-brain engine, and the unit supplies OLLAMA_API_KEY plus the
ConditionUser=!@system guard that keeps a root session off uid 1000's ports.

retire_legacy_gateway_unit() exists to move that stray file aside. It matched on
three strings from the EARLY installer's unit:

    Description=OpenClaw Gateway (local agent, Telegram channel)
    Requires=ollama.service
    ExecStart=%h/.local/bin/openclaw gateway

The current installer (OPENCLAW_SERVICE_VERSION=2026.7.1-2) shares none of them:
it renames Description, drops Requires=ollama.service, and calls node by
absolute path with `--port`. `all(...)` was therefore False, the function
returned False, and the stray unit survived every boot and every image update.

Measured on the maintainer's own machine: the gateway answered HTTP 200 on
127.0.0.1:18789 and systemd reported it active — while preflight had never run
once. Green and half-connected, the exact failure shape this repo keeps
re-learning.

This gate drives the REAL function against both generations plus the cases that
must stay untouched.
"""

import importlib.util
import os
import tempfile
from importlib.machinery import SourceFileLoader
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "system_files/usr/libexec/moai-openclaw-bootstrap"

EARLY_UNIT = """[Unit]
Description=OpenClaw Gateway (local agent, Telegram channel)
Requires=ollama.service

[Service]
ExecStart=%h/.local/bin/openclaw gateway
Restart=on-failure
"""

MODERN_UNIT = """[Unit]
Description=OpenClaw Gateway (v2026.7.1-2)
After=network-online.target

[Service]
ExecStart=/var/home/u/.nvm/versions/node/v24.19.0/bin/node \
/var/home/u/.local/lib/node_modules/openclaw/dist/index.js gateway --port 18789
Restart=always
Environment=OPENCLAW_SERVICE_MARKER=openclaw
Environment=OPENCLAW_SERVICE_KIND=gateway
Environment=OPENCLAW_SERVICE_VERSION=2026.7.1-2
"""

HAND_WRITTEN_UNIT = """[Unit]
Description=My own gateway tweak

[Service]
ExecStart=%h/.local/bin/openclaw gateway --verbose
Restart=always
"""


def load_module():
    loader = SourceFileLoader("_openclaw_retire_under_test", str(SCRIPT))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def run_case(module, tmp: Path, label: str, body: str | None, *,
             symlink: bool = False, system_unit: bool = True) -> bool:
    """Point the module's globals at a sandbox and call the real function."""
    home = tmp / label
    user_dir = home / ".config/systemd/user"
    user_dir.mkdir(parents=True, exist_ok=True)
    legacy = user_dir / "openclaw-gateway.service"
    system = home / "usr/lib/systemd/user/openclaw-gateway.service"
    system.parent.mkdir(parents=True, exist_ok=True)
    if system_unit:
        system.write_text("[Unit]\nDescription=Mo AI phone agent gateway\n", encoding="utf-8")

    if symlink:
        target = home / "elsewhere.service"
        target.write_text(body or "", encoding="utf-8")
        legacy.symlink_to(target)
    elif body is not None:
        legacy.write_text(body, encoding="utf-8")

    module.LEGACY_GATEWAY_UNIT = legacy
    module.SYSTEM_GATEWAY_UNIT = system
    module.MIGRATION_DIR = home / "migrations"
    return module.retire_legacy_gateway_unit()


def main() -> int:
    if not SCRIPT.is_file():
        print(f"GATE FAIL: {SCRIPT.relative_to(ROOT)} is missing.")
        return 1

    module = load_module()
    errors: list[str] = []

    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)

        # The regression: the CURRENT installer's unit must be retired.
        if not run_case(module, tmp, "modern", MODERN_UNIT):
            errors.append(
                "the current installer's unit (OPENCLAW_SERVICE_MARKER=openclaw, "
                "_KIND=gateway) was NOT retired — it will shadow the image unit "
                "forever and preflight will never run")
        else:
            leftover = tmp / "modern/.config/systemd/user/openclaw-gateway.service"
            if leftover.exists():
                errors.append("modern unit reported retired but is still in place")

        # The original case must keep working.
        if not run_case(module, tmp, "early", EARLY_UNIT):
            errors.append("the early installer's unit is no longer retired (regression)")

        # Things that must NEVER be touched.
        if run_case(module, tmp, "handwritten", HAND_WRITTEN_UNIT):
            errors.append("a hand-written unit was retired — customisation must be preserved")
        if run_case(module, tmp, "symlinked", MODERN_UNIT, symlink=True):
            errors.append("a symlinked unit was retired — symlinks must never be touched")
        if run_case(module, tmp, "nolegacy", None):
            errors.append("reported a retirement with no legacy unit present")
        if run_case(module, tmp, "nosystem", MODERN_UNIT, system_unit=False):
            errors.append("retired the user unit while no /usr unit exists to take over")

    if errors:
        for err in errors:
            print(f"GATE FAIL: {err}")
        return 1
    print("OK: both installer generations retire; hand-written, symlinked and "
          "unbacked units are left alone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
