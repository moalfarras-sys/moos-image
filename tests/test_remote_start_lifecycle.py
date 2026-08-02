#!/usr/bin/env python3
"""Behavioural gate for Mo PC Remote's optional sleep-inhibitor launcher."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "system_files/usr/libexec/mo-remote-start"
UNIT = ROOT / "system_files/usr/lib/systemd/user/mo-remote-personal.service"


def executable(path: Path, source: str) -> None:
    path.write_text(textwrap.dedent(source), encoding="utf-8")
    path.chmod(0o755)


class RemoteStartLifecycleTests(unittest.TestCase):
    def run_launcher(self, root: Path, inhibitor: Path, agent: Path):
        resolver = root / "resolver"
        executable(resolver, """\
            #!/bin/sh
            echo wayland-private
        """)
        environment = {
            **os.environ,
            "MO_REMOTE_WAYLAND_RESOLVER": str(resolver),
            "MO_REMOTE_INHIBIT": str(inhibitor),
            "MO_REMOTE_AGENT": str(agent),
            "MO_REMOTE_ACQUIRE_ATTEMPTS": "4",
        }
        return subprocess.run(
            [str(LAUNCHER)], env=environment, text=True, capture_output=True,
            timeout=3, check=False,
        )

    def test_hung_inhibitor_falls_back_to_the_real_agent(self):
        with tempfile.TemporaryDirectory(prefix="mo-remote-start-") as temporary:
            root = Path(temporary)
            marker = root / "agent.env"
            inhibitor = root / "inhibitor"
            agent = root / "agent"
            executable(inhibitor, """\
                #!/usr/bin/python3
                import time
                time.sleep(20)
            """)
            executable(agent, f"""\
                #!/bin/sh
                printf '%s' "$WAYLAND_DISPLAY" > '{marker}'
            """)
            result = self.run_launcher(root, inhibitor, agent)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(marker.read_text(encoding="utf-8"), "wayland-private")
            self.assertIn("acquisition timed out", result.stderr)
            self.assertIn("starting agent directly", result.stderr)

    def test_acquired_inhibitor_runs_the_agent_exactly_once(self):
        with tempfile.TemporaryDirectory(prefix="mo-remote-start-") as temporary:
            root = Path(temporary)
            marker = root / "count"
            inhibitor = root / "inhibitor"
            agent = root / "agent"
            executable(inhibitor, """\
                #!/bin/sh
                shift 4
                "$@"
            """)
            executable(agent, f"""\
                #!/bin/sh
                printf 'run\n' >> '{marker}'
                sleep 0.3
            """)
            result = self.run_launcher(root, inhibitor, agent)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(marker.read_text(encoding="utf-8").splitlines(), ["run"])
            self.assertIn("sleep inhibitor acquired", result.stderr)
            self.assertNotIn("starting agent directly", result.stderr)

    def test_acquired_agent_failure_reaches_systemd(self):
        with tempfile.TemporaryDirectory(prefix="mo-remote-start-") as temporary:
            root = Path(temporary)
            inhibitor = root / "inhibitor"
            agent = root / "agent"
            executable(inhibitor, """\
                #!/bin/sh
                shift 4
                "$@"
            """)
            executable(agent, """\
                #!/bin/sh
                sleep 0.3
                exit 7
            """)
            result = self.run_launcher(root, inhibitor, agent)
            self.assertEqual(result.returncode, 7, result.stderr)
            self.assertIn("sleep inhibitor acquired", result.stderr)
            self.assertNotIn("starting agent directly", result.stderr)

    def test_unit_uses_the_bounded_launcher(self):
        unit = UNIT.read_text(encoding="utf-8")
        directives = [
            line.strip() for line in unit.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        self.assertIn("ExecStart=/usr/libexec/mo-remote-start", directives)
        self.assertFalse(any("/bin/sh -c" in line for line in directives))
        source = LAUNCHER.read_text(encoding="utf-8")
        self.assertIn('resolve_timeout="${MO_REMOTE_RESOLVE_TIMEOUT:-5}"', source)
        self.assertIn('acquire_attempts="${MO_REMOTE_ACQUIRE_ATTEMPTS:-100}"', source)
        self.assertIn('timeout --foreground --signal=TERM "${resolve_timeout}s"', source)
        self.assertIn("sleep 0.05", source)
        self.assertIn('setsid "$inhibitor"', source)
        self.assertIn('/proc/${inhibit_pid}/task/${inhibit_pid}/children', source)
        self.assertIn('kill -TERM -- "-${inhibit_pid}"', source)
        self.assertIn('wait "$inhibit_pid"', source)
        self.assertNotIn("python", source.splitlines()[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
