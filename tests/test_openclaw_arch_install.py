#!/usr/bin/env python3
"""The per-user OpenClaw runtime must match both supported MoOS CPU families."""

from pathlib import Path
import re
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "system_files/usr/bin/moai-do"
SOURCE = INSTALLER.read_text(encoding="utf-8")


def shell_function(name: str) -> str:
    match = re.search(
        rf"^{re.escape(name)}\(\) \{{\n.*?^\}}$", SOURCE, re.MULTILINE | re.DOTALL
    )
    if match is None:
        raise AssertionError(f"missing shell function {name}")
    return match.group(0)


class OpenClawArchitectureTests(unittest.TestCase):
    def run_function(self, name: str, argument: str) -> subprocess.CompletedProcess[str]:
        script = shell_function(name) + f'\n{name} "$1"\n'
        return subprocess.run(
            ["bash", "-c", script, "test", argument],
            text=True, capture_output=True, check=False,
        )

    def test_node_archive_mapping_covers_x86_and_arm(self) -> None:
        for machine, expected in (
            ("x86_64", "x64"), ("amd64", "x64"),
            ("aarch64", "arm64"), ("arm64", "arm64"),
        ):
            with self.subTest(machine=machine):
                result = self.run_function("node_dist_arch", machine)
                self.assertEqual(result.returncode, 0)
                self.assertEqual(result.stdout.strip(), expected)
        self.assertNotEqual(self.run_function("node_dist_arch", "riscv64").returncode, 0)
        self.assertIn('node-${OPENCLAW_NODE}-linux-${node_arch}.tar.xz', SOURCE)
        self.assertNotIn('node-${OPENCLAW_NODE}-linux-x64.tar.xz', SOURCE)

    def test_nvidia_edition_switch_is_x86_only(self) -> None:
        self.assertEqual(
            self.run_function("nvidia_edition_supported", "x86_64").returncode, 0
        )
        for machine in ("aarch64", "arm64", "riscv64"):
            with self.subTest(machine=machine):
                self.assertNotEqual(
                    self.run_function("nvidia_edition_supported", machine).returncode, 0
                )
        function = shell_function("do_install_nvidia")
        self.assertLess(function.index("nvidia_edition_supported"),
                        function.index("bootc switch"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
