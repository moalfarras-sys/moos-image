#!/usr/bin/env python3
"""Keep the configuration qualified by greeter_recovery_probe.py intact.

The native probe executes old/fixed Requires/BindsTo/PartOf transactions, a
permanent failure, normal exit and explicit stop. This portable gate protects
the bounded restart policy and refuses any replacement of authentication.
"""
import configparser
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
DROP = ROOT / "system_files/usr/lib/systemd/user/plasma-login.service.d/20-moos-crash-recovery.conf"


def validate(text):
    config = configparser.ConfigParser(interpolation=None)
    config.read_string(text)
    expected = {"Unit": {"startlimitintervalsec": "60", "startlimitburst": "3"},
                "Service": {"restart": "on-failure", "restartmode": "direct", "restartsec": "2"}}
    if {section: dict(config[section]) for section in config.sections()} != expected:
        raise ValueError("unreviewed greeter recovery policy or authentication override")


class GreeterRecovery(unittest.TestCase):
    def test_qualified_policy_is_shipped(self):
        validate(DROP.read_text())

    def test_unbounded_restarts_and_authentication_changes_are_refused(self):
        source = DROP.read_text()
        for old, new in (("Restart=on-failure", "Restart=always"),
                         ("RestartMode=direct", "RestartMode=normal"),
                         ("RestartSec=2", "RestartSec=0"),
                         ("StartLimitBurst=3", "StartLimitBurst=0"),
                         ("StartLimitIntervalSec=60", "StartLimitIntervalSec=0")):
            with self.subTest(new=new), self.assertRaises(ValueError):
                validate(source.replace(old, new))
        with self.assertRaises(ValueError):
            validate(source + "ExecStart=/bin/true\n")


if __name__ == "__main__":
    unittest.main()
