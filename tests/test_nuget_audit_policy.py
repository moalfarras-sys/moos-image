#!/usr/bin/env python3
"""Official Remote builds refuse known NuGet advisories and unanswered audits."""
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class NugetAuditPolicy(unittest.TestCase):
    def test_all_projects_inherit_a_fail_closed_audit(self):
        remote = ROOT / "moremote"
        policy = ET.parse(remote / "Directory.Build.props").getroot()
        self.assertEqual(policy.findtext(".//NuGetAudit"), "true")
        self.assertEqual(policy.findtext(".//NuGetAuditMode"), "all")
        self.assertEqual(policy.findtext(".//NuGetAuditLevel"), "low")
        codes = set(policy.findtext(".//WarningsAsErrors", "").split(";"))
        self.assertTrue({f"NU190{i}" for i in range(6)} <= codes)
        projects = list(remote.rglob("*.csproj"))
        self.assertGreaterEqual(len(projects), 7)
        for project in projects:
            with self.subTest(project=project.relative_to(remote)):
                body = ET.parse(project).getroot()
                self.assertNotEqual(body.findtext(".//NuGetAudit"), "false")
                suppressed = body.findtext(".//NoWarn", "")
                self.assertFalse(any(code in suppressed for code in codes if code.startswith("NU190")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
