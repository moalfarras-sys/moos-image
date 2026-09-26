#!/usr/bin/env python3
"""Gate: moos-inspect reads, redacts and changes nothing.

WHY THIS EXISTS

moos-inspect is the executor whose tools AUTO-RUN for a cloud model: no confirmation card stands
between the model's request and the command. That is only acceptable while three things hold,
and each is proven here by running the real script against doubles:

  1. CLOSED GRAMMAR. A unit name, a priority, a time range, a line count and a log name are the
     only free values. Anything else exits 2 before a single process starts.
  2. REDACTED OUTPUT. What it prints is read by a model on someone else's server. The doubles
     print an address, a MAC, a home path, an e-mail, a serial and an API key; none may survive.
     The redaction is the support bundle's own (one implementation, already gated).
  3. NOTHING BUT READS. Every process it starts is recorded by the doubles; the set must stay
     inside a read-only allowlist, with read-only verbs.
"""

from __future__ import annotations

import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSPECT = ROOT / "system_files/usr/bin/moos-inspect"

SECRETS = {
    "address": "192.168.178.41",
    "mac": "a4:bb:6d:12:9f:e0",
    "home": "/var/home/mohammad",
    "email": "owner@example.org",
    "key": "sk-or-v1-abcdef0123456789abcdef",
    "serial": "PF3XK9Q2",
}
LEAKY = (f"unit started from {SECRETS['home']}/bin peer {SECRETS['address']} hw {SECRETS['mac']}\n"
         f"contact {SECRETS['email']} OPENROUTER_API_KEY={SECRETS['key']}\n"
         f"Serial Number: {SECRETS['serial']}\n")
READ_ONLY_TOOLS = {"systemctl", "journalctl", "ps", "free", "swapon", "df", "nmcli", "ip",
                   "resolvectl", "flatpak", "rpm-ostree"}
MUTATING_WORDS = {"start", "stop", "restart", "reload", "enable", "disable", "mask", "kill",
                  "install", "uninstall", "update", "upgrade", "rollback", "rebase", "set",
                  "add", "del", "delete", "connection", "up", "down", "vacuum", "rotate"}


class Inspector(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.bin = Path(self.tmp.name) / "bin"
        self.bin.mkdir()
        self.calls = Path(self.tmp.name) / "calls.log"
        for tool in READ_ONLY_TOOLS:
            double = self.bin / tool
            double.write_text("#!/bin/sh\n"
                              f'printf "%s\\n" "{tool} $*" >> "{self.calls}"\n'
                              f"printf '%s' '{LEAKY}'\n", encoding="utf-8")
            double.chmod(double.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        self.cache = Path(self.tmp.name) / "cache"
        self.cache.mkdir()
        self.env = {"PATH": f"{self.bin}{os.pathsep}/usr/bin{os.pathsep}/bin",
                    "HOME": self.tmp.name, "XDG_CACHE_HOME": str(self.cache), "LC_ALL": "C.UTF-8"}

    def tearDown(self):
        self.tmp.cleanup()

    def inspect(self, *argv: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(INSPECT), *argv], capture_output=True,
                              text=True, encoding="utf-8", env=self.env, timeout=60)

    def started(self) -> list[list[str]]:
        if not self.calls.exists():
            return []
        return [line.split() for line in self.calls.read_text(encoding="utf-8").splitlines()]

    def test_every_verb_answers_and_nothing_private_leaves(self):
        verbs = (["failed-units"], ["unit", "pipewire.service", "--user"],
                 ["journal", "--unit", "NetworkManager.service", "--priority", "err",
                  "--since", "1h", "--lines", "50"],
                 ["processes", "memory"], ["memory"], ["disk"], ["network"], ["apps"], ["os"])
        for argv in verbs:
            with self.subTest(verb=argv[0]):
                done = self.inspect(*argv)
                self.assertEqual(done.returncode, 0, done.stderr)
                self.assertIn("[redacted]", done.stdout, "the doubles print secrets; none was redacted")
                for label, secret in SECRETS.items():
                    self.assertNotIn(secret, done.stdout, f"{argv[0]} leaked the {label}")

    def test_only_reads_are_ever_started(self):
        for argv in (["failed-units"], ["unit", "sshd.service"], ["journal"], ["processes", "cpu"],
                     ["memory"], ["disk"], ["network"], ["apps"], ["os"]):
            self.inspect(*argv)
        calls = self.started()
        self.assertGreater(len(calls), 10, "the doubles were never reached; this test proves nothing")
        for call in calls:
            self.assertIn(call[0], READ_ONLY_TOOLS)
            self.assertFalse(MUTATING_WORDS & set(call[1:]),
                             f"moos-inspect started a command that can change the machine: {call}")

    def test_the_grammar_is_closed(self):
        for argv in (["unit", "x; rm -rf ~"], ["unit", "../../etc/shadow"], ["unit", "--version"],
                     ["journal", "--unit", "$(id)"], ["journal", "--lines", "5000"],
                     ["journal", "--since", "forever"], ["journal", "--priority", "debug"],
                     ["processes", "everything"], ["log", "../../.ssh/id_ed25519"],
                     ["log", "/etc/shadow"], ["run", "id"], ["shell"]):
            with self.subTest(argv=argv):
                done = self.inspect(*argv)
                self.assertEqual(done.returncode, 2, f"{argv} must be refused, got {done.returncode}")
                self.assertEqual(self.started(), [], f"{argv} was refused AFTER starting a process")

    def test_a_named_log_is_read_redacted_and_never_followed_through_a_symlink(self):
        (self.cache / "moai.log").write_text("line one\n" + LEAKY, encoding="utf-8")
        done = self.inspect("log", "moai")
        self.assertEqual(done.returncode, 0)
        self.assertIn("line one", done.stdout)
        self.assertNotIn(SECRETS["key"], done.stdout)
        secret = Path(self.tmp.name) / "private"
        secret.write_text("TOP-SECRET-BODY", encoding="utf-8")
        (self.cache / "moos-apply-theme.log").symlink_to(secret)
        done = self.inspect("log", "theme")
        self.assertNotIn("TOP-SECRET-BODY", done.stdout, "a log name must never follow a symlink")

    def test_remote_reads_the_agents_actual_data_log_and_redacts_it(self):
        data = Path(self.tmp.name) / ".local/share/MoRemotePersonal"
        data.mkdir(parents=True)
        remote_log = data / "log.txt"
        remote_log.write_text("Video codec: h264 (nvh264enc)\n" + LEAKY, encoding="utf-8")
        done = self.inspect("log", "remote")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("Video codec: h264 (nvh264enc)", done.stdout)
        for secret in SECRETS.values():
            self.assertNotIn(secret, done.stdout)
        remote_log.unlink()
        remote_log.symlink_to(self.calls)
        self.assertIn("this log does not exist", self.inspect("log", "remote").stdout)

    def test_output_is_bounded_and_keeps_the_newest_lines(self):
        flood = self.bin / "journalctl"
        flood.write_text("#!/bin/sh\ni=0; while [ $i -lt 4000 ]; do echo \"filler line $i of the journal\"; "
                         "i=$((i+1)); done; echo THE-NEWEST-LINE\n", encoding="utf-8")
        done = self.inspect("journal")
        self.assertLess(len(done.stdout.encode("utf-8")), 14 * 1024)
        self.assertIn("THE-NEWEST-LINE", done.stdout, "a trimmed log must keep its END")
        self.assertIn("truncated", done.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
