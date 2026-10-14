#!/usr/bin/env python3
"""MoOS web apps: the catalogue is the only authority, and an app stays where it belongs.

What this proves, without Qt (the policy module) and through the real command line:
  * only a valid catalogue entry of kind "webapp" is a web app — an http address, credentials in
    the address, a start page outside the app's own hosts, an unknown identity provider or an
    unknown permission are each refused;
  * host matching cannot be fooled by look-alike or suffixed domains;
  * an app's own hosts and its sign-in providers stay inside the window, every other address goes
    to the browser, and file:, data:, javascript:, blob: and moos: addresses go nowhere;
  * a permission the entry does not offer is refused without asking, answers are remembered in a
    private file, and a damaged file means "ask again", never "allowed";
  * the launcher Mo Store writes names only `moos-webapp <id>`, its name is the window's app id,
    catalogue text cannot add lines to it, and removal touches only launchers MoOS wrote;
  * `moos-webapp` takes a catalogue id and nothing else: an address on the command line is refused;
  * every web app in the shipped catalogue parses.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "system_files/usr/lib/moos"))
import moos_webapp_policy as policy  # noqa: E402

CLI = ROOT / "system_files/usr/bin/moos-webapp"
RUNTIME = ROOT / "system_files/usr/lib/moos/moos_webapp_runtime.py"
CATALOG = ROOT / "system_files/usr/share/moos/store/catalog.json"


def entry(**changes) -> dict:
    base = {
        "id": "chatgpt", "source": "moos", "cat": "ai", "glyph": "spark",
        "en": "ChatGPT", "ar": "تشات جي بي تي",
        "desc_en": "OpenAI's assistant in its own window.", "desc_ar": "مساعد OpenAI في نافذته.",
        "developer": "OpenAI",
        "install": {
            "kind": "webapp", "url": "https://chatgpt.com/",
            "hosts": ["chatgpt.com", "*.chatgpt.com", "*.openai.com"],
            "identity": ["google", "microsoft", "apple"],
            "permissions": ["notifications", "microphone", "clipboard"],
            "accent": "#10A37F",
        },
    }
    install = dict(base["install"])
    for key, value in changes.items():
        if key.startswith("install_"):
            install[key[len("install_"):]] = value
        else:
            base[key] = value
    base["install"] = install
    return base


class EntryValidation(unittest.TestCase):
    def test_a_valid_entry_parses(self):
        app = policy.parse_entry(entry())
        self.assertEqual(app.id, "chatgpt")
        self.assertEqual(app.desktop_id, "org.moos.webapp.chatgpt")
        self.assertEqual(app.accent, "#10a37f")
        self.assertEqual(app.permissions, ("notifications", "microphone", "clipboard"))

    def test_refusals(self):
        cases = {
            "bad_id": entry(id="ChatGPT!"),
            "not_webapp": entry(source="flathub"),
            "bad_url": entry(install_url="http://chatgpt.com/"),
            "start_outside_hosts": entry(install_url="https://evil.example/"),
            "bad_hosts": entry(install_hosts=["chat gpt.com"]),
            "bad_identity": entry(install_identity=["myspace"]),
            "bad_permissions": entry(install_permissions=["root"]),
            "bad_accent": entry(install_accent="red"),
            "bad_name": entry(en=""),
        }
        for code, value in cases.items():
            with self.subTest(code=code):
                with self.assertRaises(policy.WebAppError) as caught:
                    policy.parse_entry(value)
                self.assertEqual(caught.exception.code, code)
        for url in ("https://user:pw@chatgpt.com/", "https://chatgpt.com:8443/",
                    "https://chatgpt.com/ x", "javascript:alert(1)", "https:///nohost"):
            with self.subTest(url=url):
                with self.assertRaises(policy.WebAppError):
                    policy.parse_entry(entry(install_url=url))
        with self.assertRaises(policy.WebAppError):
            policy.parse_entry(entry(install_permissions=["microphone", "microphone"]))
        with self.assertRaises(policy.WebAppError):
            policy.parse_entry(entry(install_kind="appimage"))

    def test_invalid_entries_are_skipped_not_trusted(self):
        catalog = {"apps": [entry(), entry(id="broken", install_url="http://x.example/"),
                            {"id": "firefox", "source": "flathub"}]}
        self.assertEqual(sorted(policy.webapps(catalog)), ["chatgpt"])


class Navigation(unittest.TestCase):
    def setUp(self):
        self.app = policy.parse_entry(entry())

    def test_host_matching_cannot_be_fooled(self):
        patterns = ["chatgpt.com", "*.openai.com"]
        self.assertTrue(policy.host_matches("chatgpt.com", patterns))
        self.assertTrue(policy.host_matches("CHATGPT.COM.", patterns))
        self.assertTrue(policy.host_matches("auth.openai.com", patterns))
        for host in ("openai.com", "evilchatgpt.com", "chatgpt.com.evil.example",
                     "openai.com.evil.example", "xopenai.com", ""):
            with self.subTest(host=host):
                self.assertFalse(policy.host_matches(host, patterns))

    def test_where_each_address_goes(self):
        expected = {
            "https://chatgpt.com/c/123": "inside",
            "https://cdn.chatgpt.com/x": "inside",
            "https://auth.openai.com/authorize": "inside",
            "https://accounts.google.com/o/oauth2/v2/auth": "inside",
            "https://login.microsoftonline.com/common": "inside",
            "https://appleid.apple.com/auth": "inside",
            "about:blank": "inside",
            "https://en.wikipedia.org/wiki/OpenAI": "external",
            "http://chatgpt.com/": "external",
            "mailto:someone@example.com": "external",
            "tel:+491234": "external",
            "file:///etc/passwd": "block",
            "data:text/html,<h1>x</h1>": "block",
            "javascript:alert(1)": "block",
            "blob:https://chatgpt.com/1234": "block",
            "moos://store/install/x": "block",
            "about:config": "block",
            "https://": "block",
        }
        for url, verdict in expected.items():
            with self.subTest(url=url):
                self.assertEqual(policy.navigation(url, self.app), verdict)

    def test_identity_providers_are_only_the_ones_named(self):
        app = policy.parse_entry(entry(install_identity=["apple"]))
        self.assertEqual(policy.navigation("https://accounts.google.com/x", app), "external")
        self.assertEqual(policy.navigation("https://appleid.apple.com/x", app), "inside")

    def test_permissions_are_answered_only_for_the_apps_own_hosts(self):
        self.assertTrue(policy.origin_allowed("https://chatgpt.com", self.app))
        self.assertFalse(policy.origin_allowed("https://accounts.google.com", self.app))
        self.assertFalse(policy.origin_allowed("http://chatgpt.com", self.app))
        self.assertFalse(policy.origin_allowed("https://evil.example", self.app))


class Permissions(unittest.TestCase):
    def setUp(self):
        self.app = policy.parse_entry(entry())
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / "permissions.json"
        self.store = policy.PermissionStore(self.app, self.path)

    def tearDown(self):
        self.folder.cleanup()

    def test_answers_are_remembered_privately(self):
        self.assertEqual(self.store.decision("microphone"), "ask")
        self.store.set("microphone", "allow")
        self.store.set("notifications", "deny")
        self.assertEqual(self.store.decision("microphone"), "allow")
        self.assertEqual(self.store.decision("notifications"), "deny")
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)
        self.store.set("microphone", None)
        self.assertEqual(self.store.decision("microphone"), "ask")
        self.assertEqual(self.store.snapshot(),
                         {"notifications": "deny", "microphone": "ask", "clipboard": "ask"})

    def test_a_permission_the_entry_does_not_offer_is_refused(self):
        self.assertEqual(self.store.decision("camera"), "refused")
        with self.assertRaises(policy.WebAppError):
            self.store.set("camera", "allow")
        with self.assertRaises(policy.WebAppError):
            self.store.set("microphone", "always")

    def test_a_damaged_or_forged_file_never_means_allowed(self):
        self.path.write_text("{not json", encoding="utf-8")
        self.assertEqual(self.store.decision("microphone"), "ask")
        self.path.write_text(json.dumps({"decisions": {"camera": "allow", "microphone": "yes"}}),
                             encoding="utf-8")
        self.assertEqual(self.store.decision("camera"), "refused")
        self.assertEqual(self.store.decision("microphone"), "ask")


class Launcher(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.TemporaryDirectory()
        self.root = Path(self.home.name)

    def tearDown(self):
        self.home.cleanup()

    def test_install_writes_one_launcher_that_names_only_the_id(self):
        app = policy.parse_entry(entry())
        found = policy.install(app, self.root)
        text = found.launcher.read_text(encoding="utf-8")
        self.assertEqual(found.launcher.name, "org.moos.webapp.chatgpt.desktop")
        self.assertIn("\nExec=/usr/bin/moos-webapp chatgpt\n", text)
        self.assertIn("\nStartupWMClass=org.moos.webapp.chatgpt\n", text)
        self.assertIn("\nX-MoOS-WebApp=chatgpt\n", text)
        self.assertIn("\nName[ar]=تشات جي بي تي\n", text)
        self.assertNotIn("https://", text)
        self.assertTrue(found.icon_svg.is_file())
        self.assertIn(f"\nIcon={found.icon_svg}\n", text)
        self.assertEqual(policy.installed_ids(self.root), ["chatgpt"])

    def test_catalogue_text_cannot_add_lines(self):
        app = policy.parse_entry(entry(en="Chat\nExec=rm -rf ~", desc_en="x\n[Desktop Action evil]"))
        text = policy.launcher_text(app, Path("/icon.svg"))
        self.assertEqual(sum(line.startswith("Exec=") for line in text.splitlines()), 1)
        self.assertNotIn("\n[Desktop Action", text)

    def test_the_sites_icon_replaces_the_fallback(self):
        app = policy.parse_entry(entry())
        found = policy.install(app, self.root)
        with self.assertRaises(policy.WebAppError):
            policy.set_icon(app, b"GIF89a....", self.root)
        png = b"\x89PNG\r\n\x1a\n" + b"\0" * 64
        policy.set_icon(app, png, self.root)
        self.assertIn(f"\nIcon={found.icon_png}\n", found.launcher.read_text(encoding="utf-8"))

    def test_removal_keeps_data_unless_asked_and_ignores_foreign_launchers(self):
        app = policy.parse_entry(entry())
        found = policy.install(app, self.root)
        (found.profile).mkdir(parents=True)
        (found.profile / "Cookies").write_text("x")
        self.assertTrue(policy.remove("chatgpt", self.root))
        self.assertFalse(found.launcher.exists())
        self.assertTrue((found.profile / "Cookies").exists())
        self.assertTrue(policy.remove("chatgpt", self.root, delete_data=True))
        self.assertFalse(found.data.exists())

        foreign = policy.paths("claude", self.root).launcher
        foreign.parent.mkdir(parents=True, exist_ok=True)
        foreign.write_text("[Desktop Entry]\nName=Someone else's\nExec=true\n", encoding="utf-8")
        self.assertFalse(policy.is_installed("claude", self.root))
        self.assertFalse(policy.remove("claude", self.root))
        self.assertTrue(foreign.exists())


class CommandLine(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.catalog = Path(self.folder.name) / "catalog.json"
        self.catalog.write_text(json.dumps({"apps": [entry()]}), encoding="utf-8")
        self.env = os.environ | {"MOOS_STORE_CATALOG": str(self.catalog),
                                 "HOME": self.folder.name, "XDG_DATA_HOME": "",
                                 "DISPLAY": "", "WAYLAND_DISPLAY": ""}

    def tearDown(self):
        self.folder.cleanup()

    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-I", str(CLI), *args], env=self.env,
                              capture_output=True, text=True, timeout=30)

    def test_check_and_list_read_only_the_catalogue(self):
        done = self.run_cli("--check", "chatgpt")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout)["url"], "https://chatgpt.com/")
        listed = json.loads(self.run_cli("--list").stdout)
        self.assertEqual([row["id"] for row in listed], ["chatgpt"])
        self.assertFalse(listed[0]["installed"])

    def test_an_address_or_an_unknown_id_is_refused_before_any_window(self):
        for args in (("https://evil.example/",), ("--check", "https://evil.example/"),
                     ("claude",), ("--url", "https://evil.example/"), ()):
            with self.subTest(args=args):
                done = self.run_cli(*args)
                self.assertEqual(done.returncode, 2, done.stdout)


class Runtime(unittest.TestCase):
    """The Qt half is exercised live; these hold the shape that keeps it inside the policy."""

    source = RUNTIME.read_text(encoding="utf-8")

    def test_the_window_only_ever_loads_the_catalogue_address(self):
        self.assertIn("self.view.load(QUrl(self.app.url))", self.source)
        self.assertEqual(self.source.count(".load("), 1)
        self.assertNotIn("setUrl(", self.source)

    def test_navigation_and_permissions_go_through_the_policy(self):
        self.assertIn("policy.navigation(address, self.shell.app)", self.source)
        self.assertIn("policy.origin_allowed(origin, self.app)", self.source)
        self.assertNotIn("QWebChannel", self.source)
        self.assertNotIn("DeveloperExtras", self.source)

    def test_notifications_are_filed_under_the_apps_own_launcher(self):
        self.assertIn('f"--hint=string:desktop-entry:{app.desktop_id}"', self.source)


class ShippedCatalogue(unittest.TestCase):
    def test_every_shipped_web_app_parses(self):
        catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        kinds = [item for item in catalog["apps"]
                 if isinstance(item.get("install"), dict) and item["install"].get("kind") == "webapp"]
        for item in kinds:
            with self.subTest(id=item.get("id")):
                policy.parse_entry(item)
        self.assertEqual(len(policy.webapps(catalog)), len(kinds))


if __name__ == "__main__":
    unittest.main(verbosity=2)
