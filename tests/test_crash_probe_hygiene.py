#!/usr/bin/env python3
"""A deliberate crash in a test must not reach the host's crash collector.

WHY THIS GATE EXISTS
--------------------
Review probes and negative controls crash on purpose (a mutant QML seam, an old
teardown, an aborting converter). The development station pipes every core to
systemd-coredump, and on Plasma that starts a DrKonqi launcher in the owner's
session for each one. Measured 2026-11-24 on the V3: eight launchers for test
crashes (python3 probes, a teardown proof, private plasmashells) were still
running 5-13 hours later, about 50 MB each, while the probes had set
RLIMIT_CORE to 0 believing that made them silent.

It does not: for a piped core_pattern the kernel ignores a zero limit, and
systemd-coredump only declines to STORE the core. A limit of exactly 1 byte is
the kernel's own value for aborting a piped core before the handler starts
(fs/coredump.c logs "RLIMIT_CORE is set to 1, aborting core"). Measured on the
V3: the child still dies by SIGABRT, coredumpctl gains no entry and no DrKonqi
launcher starts.

In a shell, `ulimit -c` counts kilobytes, so `ulimit -c 1` is 1024 bytes and
NOT that value: use `prlimit --pid "$$" --core=1:1`.
"""
import re
import resource
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ROOTS = ("tests", "scripts", "build_files")
SUFFIXES = {".py", ".sh", ".c"}

LEAKING = [
    (re.compile(r"RLIMIT_CORE\s*,\s*\(\s*0\s*,\s*0\s*\)"), "RLIMIT_CORE (0, 0)"),
    (re.compile(r"struct\s+rlimit\s+\w+\s*=\s*\{\s*0\s*,\s*0\s*\}"), "struct rlimit {0, 0}"),
]
# A bare zero shell limit is only acceptable as the fallback after prlimit.
SHELL_ZERO = re.compile(r"^\s*ulimit\s+-c\s+0\b", re.M)
SHELL_ONE_KIB = re.compile(r"^[^#\n]*\bulimit\s+-c\s+1\b", re.M)


def sources():
    for root in ROOTS:
        for path in sorted((REPO / root).rglob("*")):
            if path.suffix in SUFFIXES and path.is_file() and path != Path(__file__).resolve():
                yield path


class CrashProbeHygiene(unittest.TestCase):
    def test_no_probe_uses_a_limit_the_pipe_ignores(self):
        offenders = []
        for path in sources():
            text = path.read_text(encoding="utf-8", errors="replace")
            for pattern, label in LEAKING:
                if pattern.search(text):
                    offenders.append(f"{path.relative_to(REPO)}: {label}")
            if path.suffix == ".sh":
                if SHELL_ZERO.search(text):
                    offenders.append(f"{path.relative_to(REPO)}: bare `ulimit -c 0`")
                if SHELL_ONE_KIB.search(text):
                    offenders.append(f"{path.relative_to(REPO)}: `ulimit -c 1` is 1024 bytes")
        self.assertEqual(offenders, [],
                         "a zero core limit still reaches systemd-coredump and leaves "
                         "a DrKonqi launcher in the owner's session; use 1 byte")

    def test_the_gate_bites(self):
        """Negative control: the patterns must recognise the exact old spellings."""
        old_py = "resource.setrlimit(resource.RLIMIT_CORE, (0, 0))"
        old_c = "    struct rlimit limit = {0, 0};"
        self.assertTrue(any(p.search(old_py) for p, _ in LEAKING))
        self.assertTrue(any(p.search(old_c) for p, _ in LEAKING))
        self.assertTrue(SHELL_ZERO.search("set -e\nulimit -c 0\n"))
        self.assertFalse(SHELL_ZERO.search('prlimit --pid "$$" --core=1:1 2>/dev/null || ulimit -c 0\n'))
        self.assertTrue(SHELL_ONE_KIB.search("ulimit -c 1"))

    def test_an_aborting_child_still_reports_its_signal(self):
        """The abort value must not hide the crash from the test itself."""
        def abort_value():
            resource.setrlimit(resource.RLIMIT_CORE, (1, 1))
        proc = subprocess.run(
            [sys.executable, "-I", "-c",
             "import os\n"
             "print([l for l in open('/proc/self/limits') if l.startswith('Max core')][0], flush=True)\n"
             "os.abort()\n"],
            preexec_fn=abort_value, capture_output=True, text=True, timeout=30)
        self.assertEqual(proc.returncode, -6, proc.stderr)
        self.assertRegex(proc.stdout, r"Max core file size\s+1\s+1\s+bytes")

    def test_shell_prlimit_sets_bytes_not_kilobytes(self):
        proc = subprocess.run(
            ["bash", "-c", 'prlimit --pid "$$" --core=1:1 && ulimit -c && '
                           'grep "^Max core" /proc/$$/limits'],
            capture_output=True, text=True, timeout=30)
        if proc.returncode != 0 and "prlimit" in proc.stderr and "not found" in proc.stderr:
            self.skipTest("prlimit unavailable: shell abort value not executed")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertRegex(proc.stdout, r"Max core file size\s+1\s+1\s+bytes")


if __name__ == "__main__":
    unittest.main(verbosity=2)
