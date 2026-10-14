#!/usr/bin/env python3
"""moos-store-index: a publisher's own signed package (kind `vendor`), and what a Windows program
really costs on this disk.

  VendorCatalogue  a `vendor-rpm` entry keeps its fields, is offered only when
                   usr/lib/moos/moos_vendor_rpm.parse_entry() accepts it (a reviewed repository
                   and its own key) and its processor is one the publisher builds for; the module
                   is imported only when an index is BUILT, never on a launch that reuses one;
  VendorInstalled  installed means MoOS's record, its marked folder and its own launcher, all
                   three (the module's intact()); the version reads version-release; the icon is
                   the record's, only as a file under the home; an app the catalogue stopped
                   offering is listed as installed (listed=false) so it stays removable; the
                   refresh path sees an install without parsing AppStream again;
  WindowsCost      low_disk counts a Windows program's own settings folder: 2 MiB where a copy
                   shares the template's extents (btrfs, measured), 0.9 GB elsewhere or unknown,
                   plus the template while it does not exist; the facts come from mountinfo.

Every run uses a private HOME and fixture files; nothing is installed and nothing is downloaded.
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
INDEXER = Path(os.environ.get("MOOS_STORE_INDEX_UNDER_TEST")
               or ROOT / "system_files/usr/bin/moos-store-index")
LOADER = importlib.machinery.SourceFileLoader("moos_store_index_backend2", str(INDEXER))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
index = importlib.util.module_from_spec(SPEC)
sys.modules[LOADER.name] = index
LOADER.exec_module(index)
sys.path.insert(0, str(ROOT / "system_files/usr/lib/moos"))
import moos_vendor_rpm as vendor  # noqa: E402

GIB = 1024 ** 3
MIB = 1024 ** 2
# The catalogue entry the vendor module documents for the official ChatGPT app.
CHATGPT = {"kind": "vendor-rpm",
           "repo": "https://persistent.oaistatic.com/codex-app-prod/linux/rpm/$basearch",
           "package": "chatgpt", "key_fingerprint": "3BFA0E4AE8B8CC16A2D9BA684A3B4A566C4660E4",
           "install_root": "/usr/lib/chatgpt", "exec": "ChatGPT",
           "icon": "/usr/share/pixmaps/chatgpt.png",
           "desktop": "/usr/share/applications/chatgpt.desktop", "wm_class": "ChatGPT",
           "schemes": ["codex"], "risk": "downloaded-executable", "requires_review": True,
           "external": True}
WATCH_IMPORTS = """
import runpy, sys
class Watch:
    def find_spec(self, name, path=None, target=None):
        if name == "moos_vendor_rpm":
            sys.stderr.write("LOADING moos_vendor_rpm\\n")
        return None
sys.meta_path.insert(0, Watch())
sys.argv = sys.argv[1:]
runpy.run_path(sys.argv[0], run_name="__main__")
"""
APPSTREAM = """<components>
  <component type="desktop-application"><id>org.example.Listed</id><name>Listed</name>
    <bundle type="flatpak">app/org.example.Listed/x86_64/stable</bundle></component>
</components>"""


def entry(app_id: str, **install) -> dict:
    return {"id": app_id, "source": "moos", "cat": "ai", "glyph": "spark", "en": app_id.title(),
            "ar": "تطبيق", "arch": ["x86_64", "aarch64"], "install": {**CHATGPT, **install}}


class Machine:
    def __init__(self, base: Path, apps: list[dict]):
        self.base = base
        self.home = base / "home"
        self.data = self.home / ".local/share"
        self.installation = base / "flatpak"
        self.appstream = self.installation / "appstream"
        revision = self.appstream / "flathub/x86_64" / ("e" * 64)
        revision.mkdir(parents=True)
        self.xml = revision / "appstream.xml"
        self.xml.write_text(APPSTREAM, encoding="utf-8")
        self.catalog = base / "catalog.json"
        self.catalog.write_text(json.dumps({"apps": apps}), encoding="utf-8")
        self.output = base / "cache/index.json"

    def write(self, relative: str, data: str | bytes) -> Path:
        path = self.home / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, bytes):
            path.write_bytes(data)
        else:
            path.write_text(data, encoding="utf-8")
        return path

    def vendor_install(self, app_id: str, *, version: str = "26.1007.71326", release: str = "1",
                       icon: str = ".moos-icon.png", launcher: bool = True, marker: bool = True,
                       name: str = "ChatGPT") -> None:
        """What moos_vendor_rpm.install() leaves: folder + marker, launcher, record."""
        self.write(f"Applications/{app_id}/ChatGPT", b"\x7fELF")
        if marker:
            self.write(f"Applications/{app_id}/.moos-vendor", f"{app_id}\n")
        if icon:
            self.write(f"Applications/{app_id}/{icon}", b"\x89PNG\r\n\x1a\nicon")
        if launcher:
            self.write(f".local/share/applications/org.moos.vendor.{app_id}.desktop",
                       f"[Desktop Entry]\nType=Application\nName={name}\nX-MoOS-Vendor={app_id}\n")
        self.write(f".local/share/moos/vendor/{app_id}.json", json.dumps({
            "schema": 1, "id": app_id, "kind": "vendor-rpm", "epoch": 0, "version": version,
            "release": release, "name": name, "icon": icon,
            "directory": "/somewhere/else/entirely", "desktop": f"org.moos.vendor.{app_id}.desktop"}))

    def environment(self) -> dict:
        environment = {key: value for key, value in os.environ.items()
                       if not key.startswith(("XDG_", "FLATPAK_"))}
        environment.update({
            "HOME": str(self.home), "XDG_DATA_HOME": str(self.data),
            "XDG_CACHE_HOME": str(self.home / ".cache"),
            "XDG_STATE_HOME": str(self.home / ".local/state"),
            "XDG_CONFIG_HOME": str(self.home / ".config"),
            "DBUS_SESSION_BUS_ADDRESS": "unix:path=/nonexistent",
            "FLATPAK_USER_DIR": str(self.installation),
            "FLATPAK_SYSTEM_DIR": str(self.base / "system-flatpak"),
        })
        return environment

    def run(self, *, watch_imports: bool = False) -> tuple[dict, str]:
        # `-X importtime` cannot see a module loaded by importlib.import_module(), so a finder
        # on sys.meta_path reports every attempt to load the vendor module instead.
        prefix = [sys.executable, "-c", WATCH_IMPORTS] if watch_imports else [sys.executable]
        result = subprocess.run(
            [*prefix, str(INDEXER), "--output", str(self.output), "--catalog",
             str(self.catalog), "--appstream-root", str(self.appstream),
             "--installation-root", str(self.installation), "--locale", "en", "--engines", "all"],
            text=True, capture_output=True, check=False, env=self.environment())
        if result.returncode != 0:
            raise AssertionError(result.stderr)
        return json.loads(self.output.read_text(encoding="utf-8")), result.stderr


class VendorCatalogue(unittest.TestCase):
    def test_the_entry_keeps_its_fields_and_kind(self):
        clean = index.sanitize_catalog_app(entry("chatgpt"))
        install = clean["install"]
        self.assertEqual(install["kind"], "vendor-rpm")
        for key in ("repo", "package", "key_fingerprint", "install_root", "exec", "desktop", "icon",
                    "wm_class"):
            self.assertEqual(install[key], CHATGPT[key], key)
        self.assertEqual(install["schemes"], ["codex"])
        self.assertEqual(index.catalog_kind(clean), "vendor")
        self.assertEqual(index.catalog_app_engine(clean), "", "a Linux program needs no engine")

    def test_malformed_fields_are_refused_by_shape(self):
        bad = {
            "plain http": {"repo": "http://persistent.oaistatic.com/rpm/$basearch"},
            "no basearch": {"repo": "https://persistent.oaistatic.com/rpm/x86_64"},
            "package": {"package": "chatgpt;rm"},
            "short key": {"key_fingerprint": "4A3B4A566C4660E4"},
            "relative root": {"install_root": "usr/lib/chatgpt"},
            "root with dotdot": {"install_root": "/usr/lib/../../etc"},
            "desktop": {"desktop": "/usr/share/applications/chatgpt.sh"},
            "icon": {"icon": "/usr/share/pixmaps/chatgpt.xpm"},
            "exec escape": {"exec": "../../bin/sh"},
            "wm_class": {"wm_class": "ChatGPT\nX=1"},
            "schemes": {"schemes": ["bad scheme"]},
            "too many schemes": {"schemes": ["a1", "b1", "c1", "d1", "e1"]},
            "a repository cleaning would change": {
                "repo": "https://persistent.oaistatic.com/codex-app-prod/linux/rpm/$basearch "},
        }
        for label, change in bad.items():
            with self.subTest(label), self.assertRaises(index.CatalogError):
                index.sanitize_catalog_app(entry("chatgpt", **change))

    def test_offered_only_when_the_module_accepts_it_and_builds_exist_for_this_processor(self):
        cases = {
            "the reviewed ChatGPT entry": ({}, True),
            "an unreviewed repository": ({"repo": "https://mirror.example/linux/rpm/$basearch"}, False),
            "the reviewed repository with another key": (
                {"key_fingerprint": "36F612DCF27F7D1A48A835E4DBFCF71C6D9F90A6"}, False),
            "a reserved scheme": ({"schemes": ["https"]}, False),
            "a shared system folder as the app": ({"install_root": "/usr/lib"}, False),
            # Invisible to the shape check, not to the reviewed list: never offered.
            "a look-alike repository": (
                {"repo": "https://persistent.oaistatic.com/codex-app-prod/linux/rpm/$basearch\u200b"},
                False),
        }
        for label, (change, expected) in cases.items():
            with self.subTest(label):
                clean = index.sanitize_catalog_app(entry("chatgpt", **change))
                self.assertEqual(index.catalog_installable(clean, "x86_64"), expected)
                try:
                    vendor.parse_entry(clean["install"])
                    accepted = True
                except vendor.VendorError:
                    accepted = False
                self.assertEqual(accepted, expected, "the index and the module disagree")
        clean = index.sanitize_catalog_app(entry("chatgpt"))
        self.assertTrue(index.catalog_installable(clean, "aarch64"))
        self.assertFalse(index.catalog_installable(clean, "riscv64"))
        with mock.patch.object(index, "vendor_module", lambda: None):
            self.assertFalse(index.catalog_installable(clean, "x86_64"),
                             "an image without the module offered a dead button")

    def test_a_launch_that_reuses_the_index_never_imports_the_module(self):
        with tempfile.TemporaryDirectory() as raw:
            machine = Machine(Path(raw), [entry("chatgpt")])
            built, stderr = machine.run(watch_imports=True)
            self.assertIn("LOADING moos_vendor_rpm", stderr, "the build did not ask the module at all")
            reused, stderr = machine.run(watch_imports=True)
            self.assertEqual(reused["generation"], built["generation"])
            self.assertNotIn("LOADING moos_vendor_rpm", stderr,
                             "the launch path paid for the vendor module's network imports")
        apps = {app["id"]: app for app in built["apps"]}
        self.assertEqual((apps["chatgpt"]["kind"], apps["chatgpt"]["installable"]), ("vendor", True))
        self.assertEqual(apps["chatgpt"]["cat"], "ai")
        self.assertEqual(apps["chatgpt"]["compat"], {"verdict": "ok", "reasons": []},
                         "no new compatibility reason for an unsandboxed publisher app")


class VendorInstalled(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        base = Path(cls.temporary.name)
        cls.machine = Machine(base, [entry("chatgpt"), entry("halfway"), entry("linked"),
                                     entry("escape")])
        machine = cls.machine
        machine.vendor_install("chatgpt")
        machine.vendor_install("halfway", launcher=False)          # its launcher is gone
        machine.vendor_install("linked", marker=False)             # its marker is a link
        outside = base / "outside-marker"
        outside.write_text("linked\n")
        (machine.home / "Applications/linked/.moos-vendor").symlink_to(outside)
        machine.vendor_install("escape", icon="../../../../etc/passwd")
        machine.vendor_install("retired", name="Retired Tool", version="1.2", release="3")
        machine.vendor_install("Bad_Id")
        cls.data, _ = machine.run()
        cls.apps = {app["id"]: app for app in cls.data["apps"]}

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_installed_means_all_three_files_and_reads_version_release(self):
        chatgpt = self.apps["chatgpt"]
        self.assertEqual((chatgpt["installed"], chatgpt["installed_version"], chatgpt["update_available"]),
                         (True, "26.1007.71326-1", False))
        self.assertTrue(chatgpt["icon"].startswith("file://"))
        self.assertTrue(chatgpt["icon"].endswith("/Applications/chatgpt/.moos-icon.png"),
                        "the icon must come from the app's own folder, never the record's 'directory'")
        for app_id in ("halfway", "linked"):
            self.assertFalse(self.apps[app_id]["installed"], app_id)
        self.assertTrue(self.apps["escape"]["installed"])
        self.assertIsNone(self.apps["escape"]["icon"], "an icon path that leaves the folder was published")

    def test_an_app_the_catalogue_stopped_offering_stays_listed_as_installed(self):
        retired = self.apps["retired"]
        self.assertEqual((retired["kind"], retired["installed"], retired["listed"], retired["installable"]),
                         ("vendor", True, False, False))
        self.assertEqual((retired["name"], retired["installed_version"]), ("Retired Tool", "1.2-3"))
        self.assertIn("retired", retired["search"])
        self.assertNotIn("Bad_Id", self.apps, "a record whose name cannot be an app id was listed")
        self.assertEqual(sum(app["id"] == "chatgpt" for app in self.data["apps"]), 1)

    def test_the_refresh_path_sees_an_install_without_appstream(self):
        with tempfile.TemporaryDirectory() as raw:
            machine = Machine(Path(raw), [entry("chatgpt")])
            first, _ = machine.run()
            self.assertFalse({app["id"]: app for app in first["apps"]}["chatgpt"]["installed"])
            machine.xml.chmod(0)
            try:
                machine.vendor_install("chatgpt")
                second, _ = machine.run()
            finally:
                machine.xml.chmod(0o644)
        apps = {app["id"]: app for app in second["apps"]}
        self.assertEqual(second["generation"]["metadata_token"], first["generation"]["metadata_token"])
        self.assertNotEqual(second["generation"]["installed_token"], first["generation"]["installed_token"])
        self.assertTrue(apps["org.example.Listed"]["listed"])
        self.assertEqual((apps["chatgpt"]["installed"], apps["chatgpt"]["installed_version"]),
                         (True, "26.1007.71326-1"))


class WindowsCost(unittest.TestCase):
    def machine(self, *, free: int, reflink, template) -> dict:
        return {"arch": "x86_64", "engines": ["linux", "windows"], "free_bytes": {"apps": free},
                "windows": {"ready": True, "x86_32": False, "reflink": reflink, "template": template}}

    def verdict(self, machine: dict, **app) -> tuple:
        program = {"id": "putty", "kind": "windows", "installed": False, "needs": {"size": 2 * MIB}, **app}
        result = index.compat_verdict(program, machine, None)
        return result["verdict"], result["reasons"]

    def test_the_settings_folder_is_counted_as_measured(self):
        self.assertEqual(index.windows_settings_bytes(self.machine(free=0, reflink=True, template=True)),
                         2 * MIB)
        self.assertEqual(index.windows_settings_bytes(self.machine(free=0, reflink=True, template=False)),
                         2 * MIB + 900 * 1000 ** 2)
        self.assertEqual(index.windows_settings_bytes(self.machine(free=0, reflink=False, template=True)),
                         900 * 1000 ** 2)
        self.assertEqual(index.windows_settings_bytes(self.machine(free=0, reflink=None, template=False)),
                         1800 * 1000 ** 2)
        self.assertEqual(index.windows_settings_bytes({}), 1800 * 1000 ** 2, "unknown must not mean free")

    def test_low_disk_follows_the_filesystem_and_the_template(self):
        tight = 300 * MIB
        self.assertEqual(self.verdict(self.machine(free=tight, reflink=True, template=True)), ("ok", []))
        self.assertEqual(self.verdict(self.machine(free=tight, reflink=False, template=True)),
                         ("blocked", ["low_disk"]))
        self.assertEqual(self.verdict(self.machine(free=tight, reflink=True, template=False)),
                         ("blocked", ["low_disk"]))
        self.assertEqual(self.verdict(self.machine(free=tight, reflink=False, template=True), installed=True),
                         ("ok", []), "an installed program is never judged on its install size")
        # Only Windows programs carry a settings folder.
        appdrop = {"id": "tool", "kind": "appdrop", "installed": False, "needs": {"size": 2 * MIB}}
        self.assertEqual(index.compat_verdict(appdrop, self.machine(free=tight, reflink=False,
                                                                     template=False), None)["verdict"], "ok")

    def test_the_filesystem_is_read_from_mountinfo(self):
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            root = base / "root"
            home = base / "home with space"
            (home / ".local/share/elsewhere").mkdir(parents=True)
            (root / "proc/self").mkdir(parents=True)
            escaped = str(home).replace(" ", "\\040")

            def mounts(home_type: str) -> None:
                (root / "proc/self/mountinfo").write_text(
                    "22 1 0:21 / / rw,relatime shared:1 - ext4 /dev/sda1 rw\n"
                    f"80 22 0:35 /root/var {escaped} rw,relatime shared:9 master:4 - {home_type} "
                    "/dev/sdb3 rw,space_cache=v2\n"
                    f"81 80 0:36 / {escaped}/.local/share/elsewhere rw - xfs /dev/sdc1 rw\n",
                    encoding="ascii")

            environment = {"HOME": str(home), "XDG_DATA_HOME": str(home / ".local/share")}
            with mock.patch.dict(os.environ, environment):
                mounts("btrfs")
                self.assertEqual(index.mount_filesystem(root, home / ".local/share/moos/windows-apps"), "btrfs")
                self.assertTrue(index.windows_reflink(root))
                self.assertEqual(index.mount_filesystem(root, home / ".local/share/elsewhere"), "xfs")
                mounts("ext4")
                self.assertFalse(index.windows_reflink(root))
                (root / "proc/self/mountinfo").unlink()
                self.assertIsNone(index.windows_reflink(root))
                self.assertFalse(index.windows_template_ready())
                template = home / ".local/share/moos/windows-apps/.template"
                template.mkdir(parents=True)
                (template / "system.reg").write_text("WINE REGISTRY Version 2\n")
                self.assertFalse(index.windows_template_ready(), "a template without its record counted")
                (template.parent / ".template.json").write_text("{}")
                self.assertTrue(index.windows_template_ready())
                facts = index.machine_facts(["linux", "windows"], root)
                self.assertEqual((facts["windows"]["reflink"], facts["windows"]["template"]), (None, True))

    def test_a_new_template_refreshes_the_verdicts(self):
        before = index.context_state(self.machine(free=GIB, reflink=True, template=False), None)
        after = index.context_state(self.machine(free=GIB, reflink=True, template=True), None)
        self.assertNotEqual(index.digest_json(before), index.digest_json(after))


if __name__ == "__main__":
    unittest.main(verbosity=2)
