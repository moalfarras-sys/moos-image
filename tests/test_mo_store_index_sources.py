#!/usr/bin/env python3
"""Which AppStream catalogue Mo Store's indexer reads, and how often.

Two defects measured on the station on 2026-10-14:

* The person's own user-scope Flathub remote was never indexed. `flatpak remote-add --user`
  writes no `gpg-verify` line, OSTree's default for a missing line is "verify", and the
  indexer read the missing key as false. The live index had only the system copy, so the
  Store's refresh button (which refreshes the user copy) could not change what it showed.
* Trusting both scopes naively doubles a cold build (3.2 s -> 6.2 s) to produce the same
  apps twice. Only the newest revision of one remote URL may be parsed.

Every run here uses a private HOME, private XDG directories and fixture installations.
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

ROOT = Path(__file__).resolve().parents[1]
INDEXER = Path(os.environ.get("MOOS_STORE_INDEX_UNDER_TEST")
               or ROOT / "system_files/usr/bin/moos-store-index")


def load_indexer():
    loader = importlib.machinery.SourceFileLoader("moos_store_index_sources", str(INDEXER))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[loader.name] = module
    loader.exec_module(module)
    return module


index = load_indexer()

APP_XML = """<?xml version="1.0" encoding="UTF-8"?>
<components origin="flathub">
{body}
</components>
"""

COMPONENT = """  <component type="desktop-application">
    <id>{app_id}</id>
    <name>{name}</name>
    <summary>{name} summary</summary>
    <bundle type="flatpak">app/{app_id}/x86_64/stable</bundle>
  </component>"""

FLATHUB_REMOTE = '[remote "flathub"]\nurl=https://dl.flathub.org/repo/\n'


def components(*apps: tuple[str, str]) -> str:
    return APP_XML.format(body="\n".join(COMPONENT.format(app_id=a, name=n) for a, n in apps))


def make_installation(root: Path, remote_section: str, *, keyring: bool, revision: str,
                      xml: str, checked_out_ns: int) -> None:
    repo = root / "repo"
    repo.mkdir(parents=True)
    (repo / "config").write_text("[core]\nrepo_version=1\n" + remote_section, encoding="utf-8")
    if keyring:
        (repo / "flathub.trustedkeys.gpg").write_bytes(b"\x99\x01\x0dfixture-key")
    revision_dir = root / "appstream/flathub/x86_64" / (revision * 64)
    revision_dir.mkdir(parents=True)
    (revision_dir / "appstream.xml").write_text(xml, encoding="utf-8")
    (revision_dir.parent / "active").symlink_to(revision_dir.name, target_is_directory=True)
    os.utime(revision_dir, ns=(checked_out_ns, checked_out_ns))


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
        "XDG_CONFIG_DIRS": str(base / "no-config-dirs"),
        "DBUS_SESSION_BUS_ADDRESS": "unix:path=/nonexistent",
        "FLATPAK_USER_DIR": str(base / "user"),
        "FLATPAK_SYSTEM_DIR": str(base / "system"),
        "SOURCE_DATE_EPOCH": "123",
    })
    return environment


def run_auto_discovery(base: Path) -> dict:
    catalog = base / "catalog.json"
    catalog.write_text('{"categories":[],"bundles":[],"apps":[]}', encoding="utf-8")
    output = base / "cache/index.json"
    result = subprocess.run(
        [sys.executable, str(INDEXER), "--output", str(output), "--catalog", str(catalog),
         "--locale", "en", "--engines", "all"],
        text=True, capture_output=True, check=False, env=private_environment(base),
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    return json.loads(output.read_text(encoding="utf-8"))


class UserRemoteIsTrusted(unittest.TestCase):
    """The user scope's Flathub is the same publisher as the system's: index it."""

    def test_a_user_remote_without_a_gpg_line_but_with_its_keyring_is_indexed(self):
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            make_installation(base / "user", FLATHUB_REMOTE, keyring=True, revision="a",
                              xml=components(("org.example.UserOnly", "User Only")),
                              checked_out_ns=2_000_000_000_000_000_000)
            data = run_auto_discovery(base)
            sources = [s for s in data["sources"] if s["kind"] == "flatpak-appstream"]
            self.assertEqual([(s["origin"], s["scope"]) for s in sources], [("flathub", "user")])
            self.assertIn("org.example.UserOnly", {app["id"] for app in data["apps"]})

    def test_a_missing_gpg_line_without_a_keyring_is_not_trusted(self):
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            make_installation(base / "user", FLATHUB_REMOTE, keyring=False, revision="a",
                              xml=components(("org.example.UserOnly", "User Only")),
                              checked_out_ns=2_000_000_000_000_000_000)
            data = run_auto_discovery(base)
            self.assertEqual([s for s in data["sources"] if s["kind"] == "flatpak-appstream"], [])

    def test_an_explicit_gpg_verify_false_is_still_refused(self):
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            make_installation(base / "user", FLATHUB_REMOTE + "gpg-verify=false\n", keyring=True,
                              revision="a", xml=components(("org.example.UserOnly", "User Only")),
                              checked_out_ns=2_000_000_000_000_000_000)
            self.assertEqual(index.official_flatpak_remotes(base / "user/appstream"), {})
            data = run_auto_discovery(base)
            self.assertEqual([s for s in data["sources"] if s["kind"] == "flatpak-appstream"], [])

    def test_a_disabled_or_foreign_remote_is_refused(self):
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            make_installation(
                base / "user",
                FLATHUB_REMOTE + "xa.disable=true\n"
                + '[remote "mirror"]\nurl=https://mirror.invalid/repo/\ngpg-verify=true\n',
                keyring=True, revision="a", xml=components(("org.example.A", "A")),
                checked_out_ns=2_000_000_000_000_000_000)
            self.assertEqual(index.official_flatpak_remotes(base / "user/appstream"), {})


class OneRemoteIsParsedOnce(unittest.TestCase):
    """Both scopes carry Flathub: parse the newest revision, never both."""

    def build_two_scopes(self, base: Path, *, user_ns: int, system_ns: int) -> dict:
        make_installation(base / "user", FLATHUB_REMOTE, keyring=True, revision="a",
                          xml=components(("org.example.Shared", "Shared (user copy)"),
                                         ("org.example.OnlyInUserCopy", "Only user")),
                          checked_out_ns=user_ns)
        make_installation(base / "system", FLATHUB_REMOTE + "gpg-verify=true\n", keyring=True,
                          revision="b",
                          xml=components(("org.example.Shared", "Shared (system copy)"),
                                         ("org.example.OnlyInSystemCopy", "Only system")),
                          checked_out_ns=system_ns)
        return run_auto_discovery(base)

    def test_the_newer_system_revision_is_the_only_one_parsed(self):
        with tempfile.TemporaryDirectory() as raw:
            data = self.build_two_scopes(Path(raw), user_ns=1_000_000_000_000_000_000,
                                         system_ns=2_000_000_000_000_000_000)
            ids = {app["id"] for app in data["apps"]}
            self.assertIn("org.example.OnlyInSystemCopy", ids)
            self.assertNotIn("org.example.OnlyInUserCopy", ids)
            self.assertEqual(data["stats"]["metadata_indexes_parsed"], 1)
            self.assertEqual(data["stats"]["metadata_indexes_superseded"], 1)
            superseded = [s for s in data["sources"] if s.get("superseded_by")]
            self.assertEqual([(s["scope"], s["accepted"]) for s in superseded], [("user", 0)])
            self.assertIn("/system/appstream/", superseded[0]["superseded_by"])

    def test_the_newer_user_revision_wins_the_other_way_round(self):
        with tempfile.TemporaryDirectory() as raw:
            data = self.build_two_scopes(Path(raw), user_ns=3_000_000_000_000_000_000,
                                         system_ns=2_000_000_000_000_000_000)
            ids = {app["id"] for app in data["apps"]}
            self.assertIn("org.example.OnlyInUserCopy", ids)
            self.assertNotIn("org.example.OnlyInSystemCopy", ids)
            shared = next(app for app in data["apps"] if app["id"] == "org.example.Shared")
            self.assertEqual(shared["name"], "Shared (user copy)")
            self.assertEqual(shared["scope"], "user")

    def test_a_tie_goes_to_the_user_installation(self):
        with tempfile.TemporaryDirectory() as raw:
            data = self.build_two_scopes(Path(raw), user_ns=2_000_000_000_000_000_000,
                                         system_ns=2_000_000_000_000_000_000)
            shared = next(app for app in data["apps"] if app["id"] == "org.example.Shared")
            self.assertEqual(shared["scope"], "user")
            self.assertEqual(data["stats"]["metadata_indexes_parsed"], 1)

    def test_sources_without_a_known_url_are_never_merged_away(self):
        kept, superseded = index.supersede_older_sources([
            {"origin": "flathub", "scope": "user", "arch": "x86_64", "path": Path("/a"),
             "url": None, "revision_mtime_ns": 1},
            {"origin": "flathub", "scope": "system", "arch": "x86_64", "path": Path("/b"),
             "url": None, "revision_mtime_ns": 2},
        ])
        self.assertEqual([str(item["path"]) for item in kept], ["/a", "/b"])
        self.assertEqual(superseded, [])

    def test_different_architectures_of_one_remote_are_both_kept(self):
        kept, superseded = index.supersede_older_sources([
            {"origin": "flathub", "scope": "system", "arch": "x86_64", "path": Path("/a"),
             "url": "https://dl.flathub.org/repo/", "revision_mtime_ns": 1},
            {"origin": "flathub", "scope": "system", "arch": "i386", "path": Path("/b"),
             "url": "https://dl.flathub.org/repo/", "revision_mtime_ns": 2},
        ])
        self.assertEqual(len(kept), 2)
        self.assertEqual(superseded, [])


if __name__ == "__main__":
    unittest.main()
