#!/usr/bin/env python3
"""Gate: OpenClaw's installer and systemd unit must use one SQLite-safe Node.js.

OpenClaw persists its conversation state in SQLite, and the WAL path it uses
needs SQLite 3.51.3+ (or a patched 3.50.7+/3.44.6+). Node 22.23.1 — the Fedora
44 default when this was shipped — embeds SQLite 3.51.2, which carries the
upstream WAL-reset corruption bug: the agent could receive and answer messages
but never persist session state, so outbound replies were silently dropped.

The private runtime is installed under ~/.local/node by moai-do and selected by
the shipped gateway unit. This gate checks both ends of that contract. A bare
`node --version` check is no substitute because the CI runner has neither that
private runtime nor OpenClaw installed.
"""

from __future__ import annotations

import re
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "system_files/usr/bin/moai-do"
SERVICE = ROOT / "system_files/usr/lib/systemd/user/openclaw-gateway.service"
OVERRIDE = SERVICE.parent / "openclaw-gateway.service.d/10-node24.conf"

# The override must pin a Node that embeds safe SQLite. 22.23.x embeds the
# broken 3.51.2, so 22.x is NOT accepted here even though 22.22.3+ carries a
# patched build — accepting it would silently admit the exact version that
# caused the outage. Only 24.15.0+ (SQLite 3.51.3+) and 25+ qualify.
VERSION_RE = re.compile(r'^OPENCLAW_NODE="v(\d+)\.(\d+)\.(\d+)"$', re.MULTILINE)


def installed_version(installer: Path) -> tuple[int, int, int]:
    """Return the private Node version provisioned by moai-do."""
    match = VERSION_RE.search(installer.read_text(encoding="utf-8"))
    if match is None:
        raise AssertionError(
            f"{installer.relative_to(ROOT)} does not declare OPENCLAW_NODE; "
            "nothing guarantees a SQLite-safe runtime."
        )
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def is_sqlite_safe(version: tuple[int, int, int]) -> bool:
    major, minor, _patch = version
    return major >= 25 or (major == 24 and minor >= 15)


class TestOpenClawNodeOverride(unittest.TestCase):
    def test_obsolete_nvm_override_does_not_ship(self) -> None:
        self.assertFalse(
            OVERRIDE.exists(),
            "an nvm override bypasses the ~/.local/node runtime provisioned by moai-do",
        )

    def test_service_selects_installed_private_runtime(self) -> None:
        text = SERVICE.read_text(encoding="utf-8")
        self.assertIn(
            "Environment=PATH=%h/.local/node/bin:%h/.local/bin:/usr/bin:/bin",
            text,
        )

    def test_installed_node_is_sqlite_safe(self) -> None:
        version = installed_version(INSTALLER)
        self.assertTrue(
            is_sqlite_safe(version),
            f"installer provisions Node {'.'.join(map(str, version))}, which embeds "
            "SQLite 3.51.2 (the WAL-corruption bug) or older; pin 24.15.0+ / 25+",
        )

    def test_service_explains_private_runtime(self) -> None:
        self.assertIn("OpenClaw", SERVICE.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
