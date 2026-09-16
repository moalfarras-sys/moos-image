#!/usr/bin/env python3
"""Gate: P1.4 — the support bundle is bounded and redacted by construction.

WHY THIS EXISTS

A support bundle is the one artifact MoOS asks a person to send to a stranger. It is only
safe if redaction is a property of the collector, not of the person reading it afterwards:
every line written passes through one redactor, the collector never opens a credential
file, and the result has a hard size ceiling.

This gate feeds the real redactor the shapes that actually leak — provider keys, bearer
tokens, Tailscale keys, GitHub tokens, private key headers, MAC and IP addresses, Wi-Fi
names, serial numbers, e-mail addresses and home paths — and fails if any survives. It also
drives `collect()` with stubbed commands whose output is hostile, and checks the caps.
"""

import importlib.machinery
import importlib.util
from pathlib import Path
import re
import sys
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
COLLECTOR = ROOT / "system_files/usr/libexec/moos-support-bundle"
MOAI_DO = ROOT / "system_files/usr/bin/moai-do"

LEAKS = (
    "OPENROUTER_API_KEY=sk-or-v1-0123456789abcdef0123456789abcdef",
    "api_key: sk-abcdef0123456789abcdef",
    "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
    "tailscale up --authkey tskey-auth-k7Rd9fQwEXAMPLE1234",
    "token=ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
    "-----BEGIN OPENSSH PRIVATE KEY-----",
    "link/ether 9c:6b:00:11:22:33 brd ff:ff:ff:ff:ff:ff",
    "inet 192.168.178.42/24 brd 192.168.178.255",
    "inet6 2a02:8109:abcd:1234:5678:9abc:def0:1234/64",
    'SSID: "Al Farras Home 5G"',
    "Serial Number: PF2XYZ99",
    "machine-id: 7d8c936c78b84d1bb521fb32e9c8ffd9",
    "owner: someone@example.com",
    "/var/home/moos/.config/MoRemote/portal-restore-token",
    "password = hunter2",
)
SURVIVORS = (
    "sk-or-v1-0123456789abcdef0123456789abcdef", "sk-abcdef0123456789abcdef",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9", "tskey-auth-k7Rd9fQwEXAMPLE1234",
    "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", "9c:6b:00:11:22:33",
    "192.168.178.42", "2a02:8109:abcd:1234:5678:9abc:def0:1234", "Al Farras Home 5G",
    "PF2XYZ99", "7d8c936c78b84d1bb521fb32e9c8ffd9", "someone@example.com",
    "/var/home/moos", "hunter2",
)


def commands_of(bundle) -> str:
    """Every argument of every command the collector would run, as one string."""
    return " ".join(part for _title, argv in bundle.SECTIONS for part in argv)


def load_collector():
    loader = importlib.machinery.SourceFileLoader("moos_support_bundle", str(COLLECTOR))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class SupportBundleRedaction(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = load_collector()

    def test_every_known_leak_shape_is_redacted(self):
        redacted = self.bundle.redact("\n".join(LEAKS))
        for secret in SURVIVORS:
            self.assertNotIn(secret, redacted, f"the redactor let {secret!r} through")
        self.assertIn(self.bundle.PLACEHOLDER, redacted)

    def test_diagnostic_addresses_that_identify_nobody_are_kept(self):
        kept = self.bundle.redact("listening on 127.0.0.1:7777 from 10.0.2.2")
        self.assertIn("127.0.0.1", kept)
        self.assertIn("10.0.2.2", kept)

    def test_collect_redacts_hostile_command_output_and_states_its_own_policy(self):
        hostile = "\n".join(LEAKS)
        with mock.patch.object(self.bundle, "run", return_value=hostile), \
             mock.patch.object(self.bundle, "deployment_facts",
                               return_value={"edition": "moos-nvidia", "version": "44.1",
                                             "digest": "abc", "origin": "ostree-image-signed:docker://x"}):
            body = self.bundle.collect()
        for secret in SURVIVORS:
            self.assertNotIn(secret, body, f"collect() leaked {secret!r}")
        self.assertIn("This report is redacted", body)
        self.assertIn("edition: moos-nvidia", body)

    def test_the_bundle_is_bounded(self):
        with mock.patch.object(self.bundle, "run", return_value="A" * 200_000), \
             mock.patch.object(self.bundle, "deployment_facts",
                               return_value={"edition": "moos", "version": "", "digest": "", "origin": ""}):
            body = self.bundle.collect()
        self.assertLessEqual(len(body.encode("utf-8")),
                             self.bundle.MAX_BUNDLE_BYTES,
                             "a bundle nobody can send is a bundle nobody reads")
        self.assertLessEqual(self.bundle.JOURNAL_LINES, 500, "journals must stay bounded")

    def test_a_whole_bundle_backstop_survives_if_sections_multiply(self):
        """Per-section caps keep today's 13 sections well under the ceiling, so the global
        cap can only fire if someone adds many more. It must still work when they do."""
        with mock.patch.object(self.bundle, "run", return_value="A" * 200_000), \
             mock.patch.object(self.bundle, "MAX_BUNDLE_BYTES", 8 * 1024), \
             mock.patch.object(self.bundle, "deployment_facts",
                               return_value={"edition": "moos", "version": "", "digest": "", "origin": ""}):
            body = self.bundle.collect()
        self.assertIn("[truncated: bundle size limit]", body)
        self.assertLessEqual(len(body.encode("utf-8")), 8 * 1024 + 64)

    def test_no_single_section_can_crowd_out_the_others(self):
        """Measured on a real machine: 200 journal entries came back as 104 KB."""
        with mock.patch.object(self.bundle, "run", return_value="B" * 200_000), \
             mock.patch.object(self.bundle, "deployment_facts",
                               return_value={"edition": "moos", "version": "", "digest": "", "origin": ""}):
            body = self.bundle.collect()
        sections = body.split("\n===== ")[1:]
        self.assertEqual(len(sections), len(self.bundle.SECTIONS),
                         "every section must still be present after trimming")
        for section in sections:
            self.assertLessEqual(len(section.encode("utf-8")),
                                 self.bundle.MAX_SECTION_BYTES + 256,
                                 "one noisy section must not consume the bundle")
        self.assertNotIn("[truncated: bundle size limit]", body,
                         "per-section caps should keep the whole bundle under its ceiling")

    def test_a_trimmed_journal_keeps_its_newest_lines(self):
        """`journalctl -n` prints oldest first, so the failure is at the end."""
        lines = "\n".join(f"entry-{index}" for index in range(40_000))
        trimmed = self.bundle.bounded(lines, tail=True)
        self.assertIn("entry-39999", trimmed, "the newest journal line must survive")
        self.assertNotIn("entry-0\n", trimmed)
        head_trimmed = self.bundle.bounded(lines, tail=False)
        self.assertIn("entry-0", head_trimmed, "non-journal sections keep their start")

    def test_no_collected_command_reads_a_credential_store(self):
        """Redaction is the second line of defence; not reading the file is the first."""
        commands = commands_of(self.bundle).lower()
        for forbidden in ("credential", "portal-restore-token", ".ssh/", "cosign.key",
                          "settings.local.json", "/etc/shadow", "secret", "openrouter",
                          "tailscale", "nmcli", "/etc/moos/"):
            self.assertNotIn(forbidden, commands,
                             f"a support bundle must never collect {forbidden}")

    def test_every_collected_command_is_a_known_read_only_one(self):
        allowed = {"cat", "uname", "rpm-ostree", "systemctl", "journalctl", "df", "sh",
                   "/usr/libexec/moos-image-update"}
        for title, argv in self.bundle.SECTIONS:
            self.assertIn(argv[0], allowed, f"section {title} runs an unreviewed command")
        commands = commands_of(self.bundle)
        for verb in ("rm ", "tee ", "dd ", "mv ", "cp ", "rpm-ostree install",
                     "systemctl start", "systemctl stop", "pkexec", "sudo "):
            self.assertNotIn(verb, commands, f"a collector must never run {verb.strip()!r}")
        # `2>/dev/null` is fine; a redirect into a real path means the collector writes.
        self.assertIsNone(re.search(r">\s*/(?!dev/null)", commands),
                          "the collector must not redirect output into a file")

    def test_moai_do_offers_it_as_a_read_only_action(self):
        source = MOAI_DO.read_text(encoding="utf-8")
        self.assertIn("support-bundle) do_support_bundle ;;", source,
                      "moai-do must dispatch the action so the assistant can name it")
        self.assertIn("moos-support-bundle", source)
        self.assertIn("${C}support-bundle${N}", source, "the action must appear in the help")


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=1).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(SupportBundleRedaction))
    sys.exit(0 if result.wasSuccessful() else 1)
