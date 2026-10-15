#!/usr/bin/env python3
"""Mo Store offers applications, not the machinery they are built from.

Measured in the live index on 2026-10-14: four `*.BaseApp` ids, `org.winehq.Wine` (a BaseApp
in nine branches, listed as "Wine" under More), the Nautilus previewer add-on and fifty
console tools were all offered as apps. And an app published in several branches (QGIS:
`lts` and `stable`) must be offered on its stable branch, the one the backend installs.

Every run uses a private HOME and private XDG directories.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
INDEXER = Path(os.environ.get("MOOS_STORE_INDEX_UNDER_TEST")
               or ROOT / "system_files/usr/bin/moos-store-index")


def component(app_id: str, *, kind: str | None = "desktop-application", branch: str = "stable",
              launchable: bool = False, name: str | None = None, ref_kind: str = "app") -> str:
    type_attribute = f' type="{kind}"' if kind is not None else ""
    launcher = (f'<launchable type="desktop-id">{app_id}.desktop</launchable>'
                if launchable else "")
    return (f"<component{type_attribute}><id>{app_id}</id><name>{name or app_id}</name>"
            f"<summary>s</summary>{launcher}"
            f'<bundle type="flatpak">{ref_kind}/{app_id}/x86_64/{branch}</bundle></component>')


FIXTURE = "<components>" + "".join([
    component("org.example.Editor"),
    component("org.example.Legacy", kind="desktop"),
    component("org.example.Picross", kind="generic", launchable=True),
    component("org.example.PasswordCli", kind="generic"),
    component("org.example.Untyped", kind=None, launchable=True),
    component("org.example.UntypedCli", kind=None),
    component("org.example.Tool", kind="console-application"),
    component("org.example.Previewer", kind="addon"),
    component("io.qt.PySide.BaseApp", kind="runtime", branch="6.9"),
    component("io.qt.qtwebengine.BaseApp", kind="generic", branch="6.4", launchable=True),
    component("com.riverbankcomputing.PyQt.BaseApp", kind=None, branch="6.11"),
    component("org.winehq.Wine", kind="console-application", branch="stable-25.08"),
    component("org.winehq.Wine", kind="desktop-application", branch="stable"),
    component("org.example.Platform", kind="runtime", ref_kind="runtime"),
    component("org.example.Fonts", kind="font"),
    component("org.qgis.qgis", kind="desktop", branch="lts", name="QGIS LTS"),
    component("org.qgis.qgis", branch="stable", name="QGIS"),
    component("org.example.BetaFirst", branch="beta", name="Beta build"),
    component("org.example.BetaFirst", branch="stable", name="Stable build"),
]) + "</components>"

KEPT = {"org.example.Editor", "org.example.Legacy", "org.example.Picross",
        "org.example.Untyped", "org.qgis.qgis", "org.example.BetaFirst"}


def private_environment(base: Path) -> dict[str, str]:
    home = base / "home"
    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith(("XDG_", "FLATPAK_"))}
    environment.update({
        "HOME": str(home),
        "XDG_DATA_HOME": str(home / ".local/share"),
        "XDG_CACHE_HOME": str(home / ".cache"),
        "XDG_STATE_HOME": str(home / ".local/state"),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "DBUS_SESSION_BUS_ADDRESS": "unix:path=/nonexistent",
        "FLATPAK_USER_DIR": str(base / "flatpak"),
        "FLATPAK_SYSTEM_DIR": str(base / "system-flatpak"),
    })
    return environment


def build(base: Path, installed_branch: str | None = None) -> dict:
    appstream = base / "flatpak/appstream"
    revision = appstream / "flathub/x86_64" / ("c" * 64)
    revision.mkdir(parents=True, exist_ok=True)
    (revision / "appstream.xml").write_text(FIXTURE, encoding="utf-8")
    installation = base / "flatpak"
    if installed_branch:
        active = installation / f"app/org.qgis.qgis/x86_64/{installed_branch}/active"
        active.mkdir(parents=True, exist_ok=True)
        (active / "deploy").write_bytes(b"flathub\0fixture")
    catalog = base / "catalog.json"
    catalog.write_text('{"categories":[],"bundles":[],"apps":[]}', encoding="utf-8")
    output = base / "cache/index.json"
    result = subprocess.run(
        [sys.executable, str(INDEXER), "--output", str(output), "--catalog", str(catalog),
         "--appstream-root", str(appstream), "--installation-root", str(installation),
         "--locale", "en", "--engines", "all"],
        text=True, capture_output=True, check=False, env=private_environment(base))
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    return json.loads(output.read_text(encoding="utf-8"))


class NotAppsAreNotOffered(unittest.TestCase):
    def test_only_applications_reach_the_index(self):
        with tempfile.TemporaryDirectory() as raw:
            data = build(Path(raw))
            listed = {app["id"] for app in data["apps"]}
            self.assertEqual(listed, KEPT)
            for app_id in ("org.winehq.Wine", "io.qt.PySide.BaseApp", "org.example.Tool",
                           "org.example.Previewer", "org.example.PasswordCli",
                           "org.example.UntypedCli", "org.example.Fonts"):
                with self.subTest(app=app_id):
                    self.assertNotIn(app_id, listed)

    def test_exclusions_are_counted_apart_from_invalid_and_skipped_components(self):
        with tempfile.TemporaryDirectory() as raw:
            data = build(Path(raw))
            stats = data["stats"]
            self.assertEqual(stats["excluded_components"], 10)
            self.assertEqual(stats["skipped_components"], 1)
            self.assertEqual(stats["invalid_components"], 0)
            source = next(s for s in data["sources"] if s["kind"] == "flatpak-appstream")
            self.assertEqual(source["excluded"], 10)


class StableBranchIsOffered(unittest.TestCase):
    def test_the_stable_branch_wins_whatever_order_appstream_lists_it_in(self):
        with tempfile.TemporaryDirectory() as raw:
            apps = {app["id"]: app for app in build(Path(raw))["apps"]}
            self.assertEqual(apps["org.qgis.qgis"]["branch"], "stable")
            self.assertEqual(apps["org.qgis.qgis"]["flatpak_ref"],
                             "app/org.qgis.qgis/x86_64/stable")
            self.assertEqual(apps["org.example.BetaFirst"]["branch"], "stable")
            self.assertEqual(apps["org.example.BetaFirst"]["name"], "Stable build")

    def test_an_installed_branch_stays_the_entry_so_open_and_remove_act_on_it(self):
        with tempfile.TemporaryDirectory() as raw:
            apps = {app["id"]: app for app in build(Path(raw), installed_branch="lts")["apps"]}
            self.assertEqual(apps["org.qgis.qgis"]["branch"], "lts")
            self.assertTrue(apps["org.qgis.qgis"]["installed"])


if __name__ == "__main__":
    unittest.main()
