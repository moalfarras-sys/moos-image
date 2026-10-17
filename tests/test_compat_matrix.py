#!/usr/bin/env python3
"""Gate: MoOS application compatibility matrix (P4.5).

Verifies the generator at system_files/usr/bin/moos-compat-matrix:
  * Generates valid JSON with schema, editions, architectures, and app assessments.
  * Windows programs are NOT compatible with ARM or cloud editions.
  * Android apps are NOT compatible with cloud or ARM editions.
  * Android apps document the software rendering seam on NVIDIA.
  * macOS is documented as unsupported everywhere.
  * Output preserves bilingual names (en/ar) and avoids exposing internal engine brands.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "system_files/usr/bin/moos-compat-matrix"
CATALOG_PATH = ROOT / "system_files/usr/share/moos/store/catalog.json"
ENGINES_PATH = ROOT / "system_files/usr/share/moos/app-engines.json"

# Load the generator script as a module for direct unit testing
loader = importlib.machinery.SourceFileLoader("moos_compat_matrix", str(SCRIPT_PATH))
spec = importlib.util.spec_from_loader(loader.name, loader)
generator = importlib.util.module_from_spec(spec)
sys.modules[loader.name] = generator
loader.exec_module(generator)


class TestMoOSCompatibilityMatrix(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw_catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        cls.raw_engines = json.loads(ENGINES_PATH.read_text(encoding="utf-8"))

        # Generate matrix directly using actual repo files
        cls.matrix = generator.generate_matrix(CATALOG_PATH, ENGINES_PATH)
        cls.by_id = cls.matrix["by_id"]

    def test_script_is_executable_and_has_shebang(self):
        """The script must start with #!/usr/bin/env python3 and have executable permissions."""
        content = SCRIPT_PATH.read_text(encoding="utf-8")
        self.assertTrue(
            content.startswith("#!/usr/bin/env python3"),
            "Header must be #!/usr/bin/env python3",
        )
        self.assertTrue(
            SCRIPT_PATH.stat().st_mode & 0o111 != 0,
            "Script must be executable (chmod +x)",
        )

    def test_cli_produces_valid_json(self):
        """The CLI invocation must output valid JSON matching the matrix contract."""
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--catalog",
                str(CATALOG_PATH),
                "--engines",
                str(ENGINES_PATH),
                "--format",
                "json",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(proc.returncode, 0)
        data = json.loads(proc.stdout)

        self.assertEqual(data["schema"], 1)
        self.assertEqual(data["generator"], "moos-compat-matrix")
        self.assertEqual(
            data["editions"], ["moos", "moos-nvidia", "moos-cloud", "moos-arm"]
        )
        self.assertEqual(data["architectures"], ["x86_64", "aarch64"])
        self.assertIn("summary", data)
        self.assertIn("apps", data)
        self.assertIn("unsupported", data)
        self.assertEqual(len(data["apps"]), len(self.raw_catalog["apps"]))

    def test_windows_apps_not_compatible_with_arm_or_cloud(self):
        """Windows apps must only be compatible with x86_64 desktop editions, not cloud and not arm."""
        windows_apps = [
            a
            for a in self.raw_catalog["apps"]
            if a.get("engine") == "windows"
            or (a.get("install") or {}).get("kind") == "windows-portable"
        ]
        self.assertGreaterEqual(len(windows_apps), 6, "Expected at least 6 Windows apps in catalog")

        for app_raw in windows_apps:
            app_id = app_raw["id"]
            with self.subTest(app=app_id):
                item = self.by_id[app_id]

                # Desktop editions are supported
                self.assertIn("moos", item["editions"])
                self.assertIn("moos-nvidia", item["editions"])
                self.assertTrue(item["compatibility"]["moos"]["supported"])
                self.assertTrue(item["compatibility"]["moos-nvidia"]["supported"])

                # Cloud is NOT supported
                self.assertNotIn("moos-cloud", item["editions"])
                self.assertFalse(item["compatibility"]["moos-cloud"]["supported"])
                self.assertIn("moos-cloud", item["unsupported_editions"])
                self.assertTrue(
                    "not supported on cloud" in item["compatibility"]["moos-cloud"]["reason"].lower()
                )

                # ARM is NOT supported
                self.assertNotIn("moos-arm", item["editions"])
                self.assertFalse(item["compatibility"]["moos-arm"]["supported"])
                self.assertIn("moos-arm", item["unsupported_editions"])
                self.assertTrue(
                    "not supported on arm" in item["compatibility"]["moos-arm"]["reason"].lower()
                )

                # Architecture must be x86_64 only
                self.assertEqual(item["architectures"], ["x86_64"])
                self.assertNotIn("aarch64", item["architectures"])

    def test_android_apps_not_compatible_with_cloud(self):
        """Android apps must only be compatible with desktop editions, NOT cloud."""
        android_apps = [
            a
            for a in self.raw_catalog["apps"]
            if a.get("engine") == "android"
            or (a.get("install") or {}).get("kind") == "android"
        ]
        self.assertGreaterEqual(len(android_apps), 20, "Expected at least 20 Android apps in catalog")

        for app_raw in android_apps:
            app_id = app_raw["id"]
            with self.subTest(app=app_id):
                item = self.by_id[app_id]

                # Desktop editions are supported
                self.assertIn("moos", item["editions"])
                self.assertIn("moos-nvidia", item["editions"])
                self.assertTrue(item["compatibility"]["moos"]["supported"])
                self.assertTrue(item["compatibility"]["moos-nvidia"]["supported"])

                # Cloud is NOT supported
                self.assertNotIn("moos-cloud", item["editions"])
                self.assertFalse(item["compatibility"]["moos-cloud"]["supported"])
                self.assertIn("moos-cloud", item["unsupported_editions"])
                self.assertTrue(
                    "not supported on cloud" in item["compatibility"]["moos-cloud"]["reason"].lower()
                )

                # ARM is NOT supported
                self.assertNotIn("moos-arm", item["editions"])
                self.assertFalse(item["compatibility"]["moos-arm"]["supported"])
                self.assertIn("moos-arm", item["unsupported_editions"])
                self.assertTrue(
                    "not supported on arm" in item["compatibility"]["moos-arm"]["reason"].lower()
                )

                # Architecture must be x86_64 only
                self.assertEqual(item["architectures"], ["x86_64"])
                self.assertNotIn("aarch64", item["architectures"])

    def test_nvidia_software_rendering_seam_documented_for_android(self):
        """The NVIDIA software-rendering seam must be documented for every Android app."""
        android_apps = [
            a
            for a in self.raw_catalog["apps"]
            if a.get("engine") == "android"
            or (a.get("install") or {}).get("kind") == "android"
        ]

        expected_seam = "Android on NVIDIA: software rendering"

        for app_raw in android_apps:
            app_id = app_raw["id"]
            with self.subTest(app=app_id):
                item = self.by_id[app_id]

                # Check top-level seams and limitations
                self.assertIn(expected_seam, item["seams"])
                self.assertIn(expected_seam, item["limitations"])

                # Check moos-nvidia edition seams
                nvidia_compat = item["compatibility"]["moos-nvidia"]
                self.assertIn(expected_seam, nvidia_compat.get("seams", []))

                # moos (standard) must NOT have this seam
                moos_compat = item["compatibility"]["moos"]
                self.assertEqual(moos_compat.get("seams", []), [])

    def test_macos_shows_as_unsupported(self):
        """macOS must show as unsupported everywhere in the matrix."""
        unsupported = self.matrix.get("unsupported", [])
        macos_entries = [u for u in unsupported if u.get("id") == "macos"]
        self.assertEqual(len(macos_entries), 1, "macOS must be present in unsupported platforms")

        macos = macos_entries[0]
        self.assertFalse(macos["supported"])
        self.assertFalse(macos["compatible"])
        self.assertEqual(macos["editions"], [])
        self.assertEqual(macos["architectures"], [])
        self.assertIn("macOS apps", macos["name"]["en"])
        self.assertIn("تطبيقات ماك", macos["name"]["ar"])
        self.assertIn("not currently supported", macos["reason"]["en"])

        # Also test that a hypothetical app with engine: macos is rejected everywhere
        dummy_mac_app = {
            "id": "org.example.MacApp",
            "en": "Mac App",
            "ar": "تطبيق ماك",
            "engine": "macos",
        }
        eval_result = generator.evaluate_app_compatibility(dummy_mac_app)
        self.assertEqual(eval_result["editions"], [])
        self.assertEqual(eval_result["architectures"], [])
        for ed in generator.EDITIONS:
            self.assertFalse(eval_result["compatibility"][ed]["supported"])

    def test_bilingual_names_preserved(self):
        """Every app in the matrix must have bilingual (en/ar) names matching the catalog."""
        for app_raw in self.raw_catalog["apps"]:
            app_id = app_raw["id"]
            item = self.by_id[app_id]
            self.assertEqual(item["name"]["en"], app_raw.get("en", app_id))
            self.assertEqual(item["name"]["ar"], app_raw.get("ar", app_raw.get("en", app_id)))

    def test_brand_honesty_in_generated_labels(self):
        """Prohibited engine brands (wine, bottles, waydroid, flatpak, proton, lutris) must never appear in generated text."""
        forbidden = re.compile(r"\b(wine|bottles|waydroid|proton|lutris|flatpak)\b", re.I)

        for item in self.matrix["apps"]:
            # Check generated type names
            self.assertIsNone(forbidden.search(item["type"]["en"]))
            self.assertIsNone(forbidden.search(item["type"]["ar"]))

            # Check generated seams
            for seam in item.get("seams", []):
                self.assertIsNone(forbidden.search(seam))

            # Check reasons in compatibility map
            for ed, comp in item["compatibility"].items():
                reason = comp.get("reason")
                if reason:
                    self.assertIsNone(
                        forbidden.search(reason),
                        f"{item['id']} ({ed}): reason exposes engine brand: {reason!r}",
                    )

    def test_human_format_output(self):
        """The human format must produce a formatted table with table headers and summary."""
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--catalog",
                str(CATALOG_PATH),
                "--engines",
                str(ENGINES_PATH),
                "--format",
                "human",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        output = proc.stdout
        self.assertIn("MoOS Application Compatibility Matrix", output)
        self.assertIn("App ID", output)
        self.assertIn("Architectures", output)
        self.assertIn("Windows programs", output)
        self.assertIn("Android apps", output)
        self.assertIn("Linux apps", output)
        self.assertIn("Unsupported Platforms:", output)
        self.assertIn("macOS apps", output)
        self.assertIn("Summary:", output)

    def test_app_filter_cli_argument(self):
        """The --app argument must filter output to a single app."""
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--catalog",
                str(CATALOG_PATH),
                "--engines",
                str(ENGINES_PATH),
                "--app",
                "notepad-plus-plus",
                "--format",
                "json",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        data = json.loads(proc.stdout)
        self.assertEqual(len(data["apps"]), 1)
        self.assertEqual(data["apps"][0]["id"], "notepad-plus-plus")


if __name__ == "__main__":
    unittest.main()
