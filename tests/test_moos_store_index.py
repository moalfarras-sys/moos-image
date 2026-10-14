#!/usr/bin/env python3
"""Black-box unit tests for Mo Store's offline AppStream indexer."""

from __future__ import annotations

import gzip
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
# A negative control runs these tests against a deliberately broken copy.
INDEXER = Path(os.environ.get("MOOS_STORE_INDEX_UNDER_TEST")
               or ROOT / "system_files/usr/bin/moos-store-index")


def isolate(environment: dict[str, str] | None, fallback_home: Path) -> dict[str, str]:
    """A private HOME, private XDG directories and no session bus for every run.

    The indexer reads the person's App Drop records, web-app launchers and machine
    facts under HOME and the XDG directories. Inherited from a developer's shell (or
    the editor's sandbox, which shares the real home), a run would index the
    developer's own machine instead of the fixture.
    """

    source = dict(os.environ if environment is None else environment)
    home = Path(source["HOME"]) if environment is not None and "HOME" in source \
        else fallback_home
    result = {key: value for key, value in source.items() if not key.startswith("XDG_")}
    result.update({
        "HOME": str(home),
        "XDG_DATA_HOME": str(home / ".local/share"),
        "XDG_CACHE_HOME": str(home / ".cache"),
        "XDG_STATE_HOME": str(home / ".local/state"),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "DBUS_SESSION_BUS_ADDRESS": "unix:path=/nonexistent",
    })
    for key in ("XDG_CONFIG_DIRS",):
        if environment is not None and key in environment:
            result[key] = environment[key]
    return result


PRIMARY_XML = """<?xml version="1.0" encoding="UTF-8"?>
<components>
  <component type="desktop-application">
    <!-- The desktop id is deliberately wrong: bundle is the authority. -->
    <id>not.the.Flatpak.desktop</id>
    <name>Writer</name>
    <name xml:lang="ar">الكاتب</name>
    <summary>Write focused documents</summary>
    <summary xml:lang="ar">اكتب مستندات بتركيز</summary>
    <description>
      <p>A focused writing tool with a deliberately long description.</p>
      <ul><li>One</li><li>Two</li></ul>
      <p xml:lang="ar">أداة كتابة عربية جميلة وسريعة.</p>
    </description>
    <project_license>MPL-2.0</project_license>
    <developer>
      <name>Example Studio</name>
      <name xml:lang="ar">استوديو المثال</name>
    </developer>
    <categories>
      <category>Office</category>
      <category>WordProcessor</category>
    </categories>
    <icon type="cached" width="128" height="128">org.example.Writer.png</icon>
    <icon type="remote" width="128" height="128">https://cdn.example.org/writer.png</icon>
    <screenshots>
      <screenshot>
        <image type="thumbnail">https://cdn.example.org/thumb.png</image>
        <image type="source">https://cdn.example.org/full.png</image>
      </screenshot>
      <screenshot type="default">
        <image type="source">https://cdn.example.org/not-first.png</image>
      </screenshot>
    </screenshots>
    <releases><release version="2.4.1" timestamp="42"/></releases>
    <custom>
      <value key="flathub::verification::verified">true</value>
    </custom>
    <bundle type="flatpak">app/org.example.Writer/x86_64/stable</bundle>
  </component>
  <component type="desktop-application">
    <id>some.desktop.launcher</id>
    <name>Desktop Suffix App</name>
    <!-- Some real canonical Flatpak ids end in .desktop. -->
    <bundle type="flatpak">app/org.example.Ends.desktop/x86_64/stable</bundle>
  </component>
  <component type="desktop-application">
    <id>org.example.Bad</id>
    <name>Bad ref</name>
    <bundle type="flatpak">app/org.example..Bad/x86_64/stable</bundle>
  </component>
</components>
"""


DUPLICATE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<components>
  <component type="desktop-application">
    <id>org.example.Writer.desktop</id>
    <name>Writer Beta</name>
    <summary>Secondary metadata</summary>
    <categories><category>Utility</category></categories>
    <icon type="remote">http://insecure.example.org/icon.png</icon>
    <screenshots>
      <screenshot><image type="source">file:///etc/passwd</image></screenshot>
    </screenshots>
    <bundle type="flatpak">app/org.example.Writer/x86_64/stable</bundle>
  </component>
</components>
"""


def write_catalog(path: Path, unsafe_url: str | None = None) -> None:
    # The retired `appimage` recipe is no longer a kind the index offers, so the
    # fixture's developer tool is an npm recipe; `unsafe_url` turns it into a
    # publisher-page entry whose address must never reach the index.
    codex_install = {
        "kind": "npm",
        "pkg": "@openai/codex",
        "bin": "codex",
        "name": "Codex",
        "risk": "runs-package-scripts",
        "requires_review": True,
    }
    if unsafe_url:
        codex_install = {
            "kind": "web",
            "url": unsafe_url,
            "risk": "external-download",
            "requires_review": True,
            "external": True,
        }
    catalog = {
        "categories": [
            {"id": "dev", "en": "Development", "ar": "التطوير", "glyph": "code"}
        ],
        "bundles": [
            {
                "id": "starter",
                "en": "Starter",
                "ar": "البداية",
                "glyph": "spark",
                "apps": ["org.example.Writer", "codex"],
            }
        ],
        "apps": [
            {
                "id": "org.example.Writer",
                "source": "flathub",
                "cat": "work",
                "glyph": "doc",
                "en": "Curated Writer",
                "ar": "الكاتب المختار",
                "desc_en": "A curated description.",
                "desc_ar": "وصف عربي منسّق.",
                "popular": True,
            },
            {
                "id": "org.example.Missing",
                "source": "flathub",
                "cat": "dev",
                "glyph": "code",
                "en": "Missing from AppStream",
                "ar": "غير موجود في الفهرس",
                "desc_en": "Catalog fallback.",
                "desc_ar": "بديل من الكتالوج.",
            },
            {
                "id": "codex",
                "source": "moos",
                "cat": "ai",
                "glyph": "spark",
                "en": "Codex",
                "ar": "كودكس",
                "desc_en": "A local coding agent.",
                "desc_ar": "وكيل برمجة محلي.",
                "install": codex_install,
            },
        ],
    }
    path.write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")


def write_source(root: Path, remote: str, xml: str, compressed: bool) -> Path:
    revision = root / remote / "x86_64" / ("a" * 64)
    revision.mkdir(parents=True)
    if compressed:
        target = revision / "appstream.xml.gz"
        with gzip.open(target, "wb") as handle:
            handle.write(xml.encode("utf-8"))
    else:
        target = revision / "appstream.xml"
        target.write_text(xml, encoding="utf-8")
    return revision


class StoreIndexTests(unittest.TestCase):
    def run_indexer(
        self,
        output: Path,
        catalog: Path,
        appstream: Path,
        installation: Path,
        *,
        locale: str = "ar_EG.UTF-8",
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        command = [
            sys.executable,
            str(INDEXER),
            "--output",
            str(output),
            "--catalog",
            str(catalog),
            "--appstream-root",
            str(appstream),
            "--installation-root",
            str(installation),
            "--locale",
            locale,
            # Build for a machine that has every engine. These tests are about
            # merging, locales and lifecycle state, not about which engines the
            # DEVELOPER happens to have: without this the Android recipe below is
            # correctly filtered out on any machine with no waydroid, and the
            # suite passed in a Flatpak sandbox while failing on the host.
            "--engines",
            "all",
        ]
        return subprocess.run(
            command,
            text=True,
            capture_output=True,
            check=False,
            env=isolate(env, output.parent / "private-home"),
        )

    def test_unified_index_uses_bundle_locales_and_merges_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            appstream = base / "flatpak/appstream"
            installation = base / "flatpak"
            primary = write_source(appstream, "flathub", PRIMARY_XML, compressed=True)
            write_source(appstream, "beta", DUPLICATE_XML, compressed=False)
            icon = primary / "icons/128x128/org.example.Writer.png"
            icon.parent.mkdir(parents=True)
            icon.write_bytes(b"\x89PNG\r\n\x1a\nfixture")

            active = (
                installation
                / "app/org.example.Writer/x86_64/stable/active"
            )
            active.mkdir(parents=True)
            (active / "deploy").write_bytes(b"flathub\0opaque fixture")
            fallback_active = (
                installation
                / "app/org.example.Missing/x86_64/stable/active"
            )
            fallback_active.mkdir(parents=True)
            (fallback_active / "deploy").write_bytes(b"flathub\0opaque fixture")

            catalog = base / "catalog.json"
            output = base / "cache/index.json"
            write_catalog(catalog)
            environment = dict(os.environ)
            environment["HOME"] = str(base / "home")
            environment["FLATPAK_USER_DIR"] = str(installation)
            environment["SOURCE_DATE_EPOCH"] = "123"

            result = self.run_indexer(
                output,
                catalog,
                appstream,
                installation,
                env=environment,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(output.read_text(encoding="utf-8"))
            apps = {app["id"]: app for app in data["apps"]}

            self.assertEqual(
                set(apps),
                {
                    "org.example.Writer",
                    "org.example.Ends.desktop",
                    "org.example.Missing",
                    "codex",
                },
            )
            writer = apps["org.example.Writer"]
            self.assertEqual(writer["id"], "org.example.Writer")
            self.assertEqual(
                writer["flatpak_ref"], "app/org.example.Writer/x86_64/stable"
            )
            self.assertEqual(writer["name"], "الكاتب المختار")
            self.assertEqual(writer["summary"], "وصف عربي منسّق.")
            self.assertEqual(
                writer["description"], "أداة كتابة عربية جميلة وسريعة."
            )
            self.assertEqual(writer["developer"], "استوديو المثال")
            self.assertEqual(writer["license"], "MPL-2.0")
            self.assertEqual(writer["category"], "office")
            self.assertEqual(
                writer["categories"], ["Office", "WordProcessor", "Utility"]
            )
            self.assertEqual(writer["screenshot"], "https://cdn.example.org/full.png")
            self.assertTrue(writer["icon"].startswith("file://"))
            self.assertTrue(writer["verified"])
            self.assertTrue(writer["installed"])
            self.assertEqual(writer["installed_origin"], "flathub")
            self.assertEqual(writer["installed_scope"], "user")
            self.assertEqual(writer["installed_scopes"], ["user"])
            self.assertEqual(writer["version"], "2.4.1")
            self.assertEqual(
                [(item["origin"], item["scope"]) for item in writer["origins"]],
                [("beta", "user"), ("flathub", "user")],
            )

            fallback = apps["org.example.Missing"]
            self.assertEqual(fallback["source"], "flatpak")
            self.assertTrue(fallback["installable"])
            self.assertEqual(fallback["category"], "development")
            self.assertTrue(fallback["installed"])
            self.assertEqual(fallback["installed_scope"], "user")
            self.assertEqual(fallback["installed_scopes"], ["user"])
            self.assertEqual(fallback["description"], fallback["summary"])

            codex = apps["codex"]
            self.assertEqual(codex["source"], "moos")
            self.assertEqual(codex["scope"], "user")
            self.assertEqual(codex["category"], "ai")
            self.assertTrue(codex["installable"])
            self.assertFalse(codex["installed"])
            self.assertEqual(codex["kind"], "npm")
            self.assertEqual(codex["install"]["risk"], "runs-package-scripts")
            self.assertTrue(codex["install"]["requires_review"])
            self.assertEqual(codex["description"], codex["summary"])
            self.assertEqual(writer["kind"], "flatpak")
            self.assertEqual(fallback["kind"], "flatpak")

            self.assertEqual(data["schema_version"], 1)
            self.assertTrue(data["generation"]["offline"])
            self.assertEqual(len(data["generation"]["input_token"]), 64)
            self.assertEqual(len(data["generation"]["metadata_token"]), 64)
            self.assertEqual(len(data["generation"]["installed_token"]), 64)
            self.assertEqual(data["generation"]["locale"], "ar-eg")
            self.assertEqual(data["generation"]["generated_at"], "1970-01-01T00:02:03Z")
            self.assertEqual(len(data["generation"]["id"]), 20)
            self.assertEqual(data["stats"]["total_apps"], 4)
            self.assertEqual(data["stats"]["duplicates_merged"], 1)
            self.assertEqual(data["stats"]["invalid_components"], 1)
            self.assertEqual(data["stats"]["catalog_fallback_apps"], 2)
            self.assertEqual(len(data["sources"]), 3)
            self.assertEqual(data["categories"][0]["id"], "dev")
            self.assertEqual(data["bundles"][0]["id"], "starter")
            self.assertEqual(list(output.parent.glob(f".{output.name}.*.tmp")), [])
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)

            # An unchanged run is a true cache hit: it does not rewrite output.
            unchanged_mtime = output.stat().st_mtime_ns
            cached = self.run_indexer(
                output,
                catalog,
                appstream,
                installation,
                env=environment,
            )
            self.assertEqual(cached.returncode, 0, cached.stderr)
            self.assertEqual(output.stat().st_mtime_ns, unchanged_mtime)

            # Installed refs are part of the token, so a cache hit can never
            # leave installed=false stale after a new deployment appears.
            newly_active = (
                installation
                / "app/org.example.Ends.desktop/x86_64/stable/active"
            )
            newly_active.mkdir(parents=True)
            (newly_active / "deploy").write_bytes(b"flathub\0opaque fixture")
            refreshed = self.run_indexer(
                output,
                catalog,
                appstream,
                installation,
                env=environment,
            )
            self.assertEqual(refreshed.returncode, 0, refreshed.stderr)
            refreshed_data = json.loads(output.read_text(encoding="utf-8"))
            refreshed_apps = {
                app["id"]: app for app in refreshed_data["apps"]
            }
            self.assertTrue(refreshed_apps["org.example.Ends.desktop"]["installed"])
            self.assertEqual(
                refreshed_apps["org.example.Ends.desktop"]["installed_scopes"],
                ["user"],
            )
            self.assertNotEqual(
                refreshed_data["generation"]["input_token"],
                data["generation"]["input_token"],
            )

            # The installed-only cache refresh must also remove every lifecycle
            # scope field once a deployment disappears.
            active.rename(active.with_name("inactive"))
            removed = self.run_indexer(
                output,
                catalog,
                appstream,
                installation,
                env=environment,
            )
            self.assertEqual(removed.returncode, 0, removed.stderr)
            removed_apps = {
                app["id"]: app
                for app in json.loads(
                    output.read_text(encoding="utf-8")
                )["apps"]
            }
            self.assertFalse(removed_apps["org.example.Writer"]["installed"])
            self.assertNotIn("installed_scope", removed_apps["org.example.Writer"])
            self.assertNotIn("installed_scopes", removed_apps["org.example.Writer"])

    def test_long_description_is_plain_localized_and_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            appstream = base / "flatpak/appstream"
            installation = base / "flatpak"
            long_text = " ".join(f"word{index}" for index in range(600))
            xml = f"""<components><component type="desktop-application">
  <id>org.example.Long</id><name>Long</name><summary>Short</summary>
  <description><p>{long_text}</p><p xml:lang="ar">نص عربي منفصل</p></description>
  <bundle type="flatpak">app/org.example.Long/x86_64/stable</bundle>
</component></components>"""
            write_source(appstream, "flathub", xml, compressed=False)
            catalog = base / "catalog.json"
            catalog.write_text(
                '{"categories":[],"bundles":[],"apps":[]}', encoding="utf-8"
            )
            output = base / "index.json"
            result = self.run_indexer(
                output, catalog, appstream, installation, locale="en"
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            app = json.loads(output.read_text(encoding="utf-8"))["apps"][0]
            self.assertEqual(len(app["description"]), 2048)
            self.assertTrue(app["description"].endswith("…"))
            self.assertNotIn("نص عربي", app["description"])

    def test_cached_icon_uri_survives_active_revision_rotation(self) -> None:
        """Cached indexes must not pin an AppStream revision Flatpak deletes."""

        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            appstream = base / "flatpak/appstream"
            installation = base / "flatpak"
            first = write_source(appstream, "flathub", PRIMARY_XML, compressed=False)
            first_icon = first / "icons/128x128/org.example.Writer.png"
            first_icon.parent.mkdir(parents=True)
            first_icon.write_bytes(b"\x89PNG\r\n\x1a\nfirst")
            active = first.parent / "active"
            active.symlink_to(first.name, target_is_directory=True)

            catalog = base / "catalog.json"
            output = base / "cache/index.json"
            write_catalog(catalog)
            result = self.run_indexer(
                output, catalog, appstream, installation, locale="en"
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(output.read_text(encoding="utf-8"))
            writer = next(
                app for app in data["apps"] if app["id"] == "org.example.Writer"
            )
            self.assertEqual(
                writer["description"],
                "A focused writing tool with a deliberately long description.\n\n"
                "• One\n• Two",
            )
            icon_path = Path(unquote(urlsplit(writer["icon"]).path))
            self.assertIn("active", icon_path.parts)
            self.assertTrue(icon_path.is_file())

            # A Flatpak AppStream refresh repoints `active` and removes the old
            # content-addressed revision. The cached URI must follow the link.
            second = first.parent / ("b" * 64)
            second_icon = second / "icons/128x128/org.example.Writer.png"
            second_icon.parent.mkdir(parents=True)
            second_icon.write_bytes(b"\x89PNG\r\n\x1a\nsecond")
            active.unlink()
            active.symlink_to(second.name, target_is_directory=True)
            first.rename(first.with_name("retired-revision"))

            self.assertTrue(
                icon_path.is_file(),
                "cached icon URI pinned the retired AppStream revision",
            )

    def test_same_revision_is_parsed_once_across_user_and_system_scopes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            user_installation = base / "user-flatpak"
            system_installation = base / "system-flatpak"
            user_appstream = user_installation / "appstream"
            system_appstream = system_installation / "appstream"
            write_source(user_appstream, "flathub", PRIMARY_XML, compressed=True)
            write_source(system_appstream, "flathub", PRIMARY_XML, compressed=False)
            for installation in (user_installation, system_installation):
                active = (
                    installation
                    / "app/org.example.Writer/x86_64/stable/active"
                )
                active.mkdir(parents=True)
                (active / "deploy").write_bytes(b"flathub\0opaque fixture")
            catalog = base / "catalog.json"
            output = base / "index.json"
            write_catalog(catalog)
            environment = dict(os.environ)
            environment.update(
                {
                    "HOME": str(base / "home"),
                    "FLATPAK_USER_DIR": str(user_installation),
                    "FLATPAK_SYSTEM_DIR": str(system_installation),
                }
            )
            command = [
                sys.executable,
                str(INDEXER),
                "--output",
                str(output),
                "--catalog",
                str(catalog),
                "--appstream-root",
                str(user_appstream),
                "--appstream-root",
                str(system_appstream),
                "--installation-root",
                str(user_installation),
                "--installation-root",
                str(system_installation),
                "--locale",
                "en",
            ]
            result = subprocess.run(
                command,
                text=True,
                capture_output=True,
                check=False,
                env=isolate(environment, base / "home"),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(output.read_text(encoding="utf-8"))
            flatpak_sources = [
                source
                for source in data["sources"]
                if source["kind"] == "flatpak-appstream"
            ]
            self.assertEqual(len(flatpak_sources), 2)
            self.assertEqual(
                [source["metadata_reused"] for source in flatpak_sources],
                [False, True],
            )
            self.assertEqual(data["stats"]["metadata_indexes_parsed"], 1)
            self.assertEqual(data["stats"]["metadata_indexes_reused"], 1)
            writer = next(
                app for app in data["apps"] if app["id"] == "org.example.Writer"
            )
            self.assertEqual(
                {(item["origin"], item["scope"]) for item in writer["origins"]},
                {("flathub", "user"), ("flathub", "system")},
            )
            self.assertTrue(writer["installed"])
            self.assertEqual(writer["installed_scope"], "user")
            self.assertEqual(writer["installed_scopes"], ["user", "system"])

    def test_unsafe_catalog_entry_is_skipped_with_a_reason_and_never_indexed(self) -> None:
        """One bad entry is left out and logged; it may never take the index down.

        Until 2026-10-14 an unsafe URL raised out of the whole catalogue load, so a
        single bad entry meant no index at all. The safety property is that the
        unsafe recipe never reaches the index, and that still holds.
        """
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            appstream = base / "appstream"
            installation = base / "flatpak"
            appstream.mkdir()
            installation.mkdir()
            catalog = base / "catalog.json"
            write_catalog(catalog, unsafe_url="http://localhost/unsafe")
            output = base / "index.json"
            output.write_text('{"sentinel":true}\n', encoding="utf-8")

            result = self.run_indexer(
                output, catalog, appstream, installation, locale="en"
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("not safe HTTPS", result.stderr)
            self.assertIn("codex", result.stderr)
            text = output.read_text(encoding="utf-8")
            self.assertNotIn("localhost/unsafe", text)
            data = json.loads(text)
            ids = {app["id"] for app in data["apps"]}
            self.assertNotIn("codex", ids)
            self.assertIn("org.example.Writer", ids)
            self.assertEqual(data["stats"]["catalog_skipped_entries"], 1)
            curated = next(s for s in data["sources"] if s["kind"] == "curated-catalog")
            self.assertEqual(curated["invalid"], 1)
            self.assertEqual(list(base.glob(f".{output.name}.*.tmp")), [])

    def test_an_unreadable_catalog_still_fails_without_replacing_output(self) -> None:
        for label, content in (
            ("not json", "{not json"),
            ("not an object", "[]"),
            ("apps not a list", '{"apps": {}}'),
        ):
            with self.subTest(case=label), tempfile.TemporaryDirectory() as temporary:
                base = Path(temporary)
                appstream = base / "appstream"
                installation = base / "flatpak"
                appstream.mkdir()
                installation.mkdir()
                catalog = base / "catalog.json"
                catalog.write_text(content, encoding="utf-8")
                output = base / "index.json"
                output.write_text('{"sentinel":true}\n', encoding="utf-8")
                result = self.run_indexer(
                    output, catalog, appstream, installation, locale="en"
                )
                self.assertEqual(result.returncode, 2)
                self.assertEqual(
                    json.loads(output.read_text(encoding="utf-8")), {"sentinel": True}
                )
                self.assertEqual(list(base.glob(f".{output.name}.*.tmp")), [])

    def test_auto_discovery_ignores_orphan_and_untrusted_remotes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            user_installation = base / "user-flatpak"
            system_installation = base / "system-flatpak"
            appstream = user_installation / "appstream"
            write_source(appstream, "flathub", PRIMARY_XML, compressed=False)
            write_source(appstream, "orphan", DUPLICATE_XML, compressed=False)
            repo = user_installation / "repo"
            repo.mkdir(parents=True)
            (repo / "config").write_text(
                '[core]\nrepo_version=1\n'
                '[remote "flathub"]\n'
                'url=https://dl.flathub.org/repo/\n'
                'gpg-verify=true\n'
                '[remote "orphan"]\n'
                'url=https://attacker.invalid/repo/\n'
                'gpg-verify=true\n',
                encoding="utf-8",
            )
            catalog = base / "catalog.json"
            output = base / "index.json"
            write_catalog(catalog)
            environment = dict(os.environ)
            environment.update(
                {
                    "HOME": str(base / "home"),
                    "FLATPAK_USER_DIR": str(user_installation),
                    "FLATPAK_SYSTEM_DIR": str(system_installation),
                }
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(INDEXER),
                    "--output",
                    str(output),
                    "--catalog",
                    str(catalog),
                    "--locale",
                    "en",
                ],
                text=True,
                capture_output=True,
                check=False,
                env=isolate(environment, base / "home"),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(output.read_text(encoding="utf-8"))
            origins = {
                source["origin"]
                for source in data["sources"]
                if source["kind"] == "flatpak-appstream"
            }
            self.assertEqual(origins, {"flathub"})


    def test_android_recipe_is_installable_and_tracks_local_package_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            home = base / "home"
            package = "org.fdroid.fdroid"
            package_state = home / ".local/share/waydroid/data/data" / package
            package_state.mkdir(parents=True)
            appstream = base / "appstream"
            installation = base / "flatpak"
            appstream.mkdir()
            installation.mkdir()
            catalog = base / "catalog.json"
            catalog.write_text(
                json.dumps(
                    {
                        "apps": [
                            {
                                "id": package,
                                "source": "moos",
                                "cat": "droid",
                                "glyph": "store",
                                "en": "F-Droid",
                                "ar": "إف-درويد",
                                "install": {
                                    "kind": "android",
                                    "url": "https://example.test/fdroid.apk",
                                    "sha256": "0" * 64,
                                    "package": package,
                                    "external": True,
                                    "risk": "external-download",
                                    "requires_review": True,
                                },
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            output = base / "index.json"
            environment = os.environ.copy()
            environment["HOME"] = str(home)

            result = self.run_indexer(
                output, catalog, appstream, installation, env=environment
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            app = json.loads(output.read_text(encoding="utf-8"))["apps"][0]
            self.assertTrue(app["installable"])
            self.assertTrue(app["installed"])
            self.assertEqual(app["install"]["package"], package)

            package_state.rmdir()
            result = self.run_indexer(
                output, catalog, appstream, installation, env=environment
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            app = json.loads(output.read_text(encoding="utf-8"))["apps"][0]
            self.assertFalse(app["installed"])


class StoreEditorialPicksTests(unittest.TestCase):
    """MoOS picks are editorial, not alphabetical (plan M1.4)."""

    CATALOG = ROOT / "system_files/usr/share/moos/store/catalog.json"
    STORE = ROOT / "system_files/usr/share/moos/apps/store/main.qml"

    def ranked(self, limit):
        apps = json.loads(self.CATALOG.read_text(encoding="utf-8"))["apps"]
        order = sorted(range(len(apps)),
                       key=lambda index: (0 if apps[index].get("popular") is True else 1, index))
        return [apps[index]["id"] for index in order[:limit]]

    # A runtime is not an app somebody chooses. Mo Store used to lead with the
    # Windows RUNTIME so that "MoOS runs Windows programs" was visible in the
    # first row — the promise was right and the vehicle was wrong: it put an
    # engine's brand in front of a person who only wanted to run a program they
    # had downloaded. The promise now lives in the capability strip, which is
    # generated from app-engines.json and can therefore only ever speak in the
    # registry's own words. These two tests are a pair: the first says no engine
    # leads the picks, the second says the promise is still on the page.
    ENGINE_APPS = {"com.usebottles.bottles", "net.lutris.Lutris",
                   "net.davidotek.pupgui2"}

    def test_no_runtime_leads_the_picks(self):
        picks = self.ranked(8)
        self.assertEqual(picks[:3], ["org.mozilla.firefox", "com.google.Chrome",
                                     "com.valvesoftware.Steam"])
        leading = self.ENGINE_APPS & set(self.ranked(6))
        self.assertFalse(
            leading,
            "these are engines, not apps a person picks, and leading with them puts a "
            "runtime's brand on the Store's front page: " + ", ".join(sorted(leading)))
        local_only = {"com.jeffser.Alpaca", "io.gpt4all.gpt4all", "lmstudio"}
        self.assertFalse(local_only & set(picks),
                         "Mo AI is cloud-only; local-model apps must not lead MoOS picks")

    def test_the_store_still_says_what_moos_can_run(self):
        """Removing the runtime from the first row may not remove the promise."""
        source = self.STORE.read_text(encoding="utf-8")
        self.assertIn("app-engines.json", source,
                      "the Store must read the engine registry, so the capability it "
                      "advertises is the one the system actually has")
        self.assertIn("engineCapabilities", source)
        self.assertIn("openPickerFor", source,
                      "each capability must be actionable — a label that does nothing is "
                      "the dead button rule")

    def test_store_ranks_by_popular_flag_and_catalogue_order(self):
        source = self.STORE.read_text(encoding="utf-8")
        start = source.index("function curatedFeatured(limit)")
        body = source[start:source.index("\n    function ", start + 1)]
        self.assertIn("win.curatedApps", body, "picks must follow catalog.json's own order")
        self.assertIn("popular", body)
        self.assertIn("a.rank - b.rank || a.order - b.order", body)
        self.assertNotIn("win.allApps[i]\n            if (app.curated", body,
                         "the store-wide alphabetical list must not decide MoOS picks")


if __name__ == "__main__":
    unittest.main()
