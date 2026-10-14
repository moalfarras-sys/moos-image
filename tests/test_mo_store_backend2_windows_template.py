#!/usr/bin/env python3
"""Windows programs from Mo Store share ONE template settings folder and still keep their own.

Each catalogue Windows program gets its own prefix (its own settings and registry). Made from
scratch, every one cost 876 MB, because Wine 11 copies its libraries into it. moos-storectl now
makes one template, headless, once per runtime version
(~/.local/share/moos/windows-apps/.template, its record .template.json written last), and each
program's prefix is `cp -a --reflink=auto` of it: on btrfs, MoOS's default, the copy shares the
template's extents; elsewhere it is an ordinary full copy.

  Template          made once and reused; rebuilt when the runtime's version changes or it is
                    incomplete; a link in its place is refused; the last program's removal (or a
                    first install that did not finish) retires it; a failed copy leaves nothing;
  RealTemplateProof opt-in (MOOS_WINDOWS_TEMPLATE_PROOF=<a folder on the disk to measure>): the
                    image's own runtime makes the template and two programs' prefixes in a
                    private HOME there, and the extents each copy really adds are measured. The
                    two "programs" are 64-bit headers that are never started.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
# The first wave's Windows fixtures: a recording runtime (wineboot leaves a prefix's files, the
# copy is made by the real cp), the 64-bit header and the download opener.
import test_mo_store_backend_windows as winfix  # noqa: E402

MODULE = winfix.MODULE
appdrop = winfix.appdrop


def recipe(opener, app_id: str, *, version: str = "1.0", tail: bytes = b"") -> dict:
    body = winfix.pe(tail=tail or app_id.encode())
    url = f"https://publisher.example/{app_id}-{version}.exe"
    opener.files[url] = body
    return {"id": app_id, "source": "moos", "en": app_id.title(), "ar": "برنامج", "cat": "win",
            "engine": "windows", "arch": ["x86_64"],
            "install": {"kind": "windows-portable", "version": version, "exe": f"{app_id}.exe",
                        "downloads": {"x86_64": {"url": url, "sha256": hashlib.sha256(body).hexdigest(),
                                                 "size": len(body)}},
                        "risk": "downloaded-executable", "requires_review": True, "external": True}}


class Template(winfix.Isolated):
    def setUp(self):
        super().setUp()
        tools = self.base / "image-tools"
        tools.mkdir()
        for name in ("WINE", "WINESERVER", "TIMEOUT_TOOL", "ENV_TOOL", "XRDB"):
            path = tools / name.lower()
            path.write_text("#!/bin/false\n", encoding="utf-8")
            patcher = mock.patch.object(MODULE, name, str(path))
            patcher.start()
            self.addCleanup(patcher.stop)
        for target, name, value in ((MODULE, "running_arch", lambda: "x86_64"),
                                    (appdrop, "_refresh_menu", lambda: None)):
            patcher = mock.patch.object(target, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.opener = winfix.Opener()
        self.runtime = winfix.Runtime()
        self.recipes = {app_id: recipe(self.opener, app_id) for app_id in ("alpha", "beta")}
        self.template = self.windows / ".template"
        self.record = self.windows / ".template.json"

    def controller(self) -> MODULE.Controller:
        path = self.base / "catalog.json"
        path.write_text(json.dumps({"apps": list(self.recipes.values())}), encoding="utf-8")
        return MODULE.Controller(MODULE.JobStore(self.home / ".cache/moos-store"),
                                 adapter_factory=lambda: None, runner=self.runtime,
                                 catalog_path=path, opener=self.opener)

    def install(self, app_id: str) -> dict:
        code, document = self.controller().install([app_id])
        self.assertEqual(document["state"], "success", document)
        return document

    def boots(self) -> list[list[str]]:
        return [argv for argv in self.runtime.commands if "wineboot" in argv]

    def copies(self) -> list[list[str]]:
        return [argv for argv in self.runtime.commands if argv[0] == MODULE.CP_TOOL]

    def prefix(self, app_id: str) -> Path:
        return self.windows / app_id / "prefix"

    def test_the_template_is_made_once_and_every_program_gets_its_own_copy(self):
        self.install("alpha")
        self.install("beta")
        self.assertEqual(len(self.boots()), 1, "the template was made more than once")
        self.assertEqual(winfix.Runtime.environment(self.boots()[0])["WINEPREFIX"],
                         str(self.windows / ".template.new"))
        self.assertEqual(self.copies(), [
            [MODULE.CP_TOOL, "-a", "--reflink=auto", "--no-target-directory", "--", str(self.template),
             str(self.prefix(app_id))] for app_id in ("alpha", "beta")])
        record = json.loads(self.record.read_text(encoding="utf-8"))
        self.assertEqual((record["schema"], record["wine"], record["dpi"]), (1, "wine-11.0 (Staging)", 192))
        for app_id in ("alpha", "beta"):
            self.assertTrue((self.prefix(app_id) / "system.reg").is_file())
            self.assertFalse(self.prefix(app_id).is_symlink())
            self.assertEqual((self.home / f".local/state/moos-foreign/{app_id}/windows-dpi").read_text(),
                             "192\n", "the program's density stamp is not the template's")
        self.assertEqual(sorted(path.name for path in self.windows.iterdir()),
                         [".template", ".template.json", "alpha", "alpha.json", "beta", "beta.json"])

    def test_each_program_keeps_its_own_settings(self):
        self.install("alpha")
        self.install("beta")
        (self.prefix("alpha") / "user.reg").write_text("alpha's own settings\n", encoding="utf-8")
        self.assertEqual((self.prefix("beta") / "user.reg").read_text(), "WINE REGISTRY Version 2\n")
        self.assertEqual((self.template / "user.reg").read_text(), "WINE REGISTRY Version 2\n")
        self.assertNotEqual(os.stat(self.prefix("alpha") / "user.reg").st_ino,
                            os.stat(self.template / "user.reg").st_ino, "a copy may never be a hard link")

    def test_a_new_runtime_version_rebuilds_only_the_template(self):
        self.install("alpha")
        (self.prefix("alpha") / "user.reg").write_text("alpha's own settings\n", encoding="utf-8")
        self.runtime.version = "wine-11.1"
        self.install("beta")
        self.assertEqual(len(self.boots()), 2)
        self.assertEqual(json.loads(self.record.read_text())["wine"], "wine-11.1")
        self.assertEqual((self.prefix("alpha") / "user.reg").read_text(), "alpha's own settings\n",
                         "a program installed earlier lost its settings to the new template")
        self.assertFalse((self.windows / ".template.new").exists())

    def test_an_incomplete_template_is_rebuilt_and_a_leftover_staging_folder_cleared(self):
        (self.template / "drive_c").mkdir(parents=True)          # no registry, no record
        (self.windows / ".template.new/junk").mkdir(parents=True)
        self.install("alpha")
        self.assertEqual(len(self.boots()), 1)
        self.assertTrue((self.template / "system.reg").is_file())
        self.assertFalse((self.windows / ".template.new").exists())
        # A record that names this runtime but a template without its registry is not trusted.
        (self.template / "system.reg").unlink()
        self.install("beta")
        self.assertEqual(len(self.boots()), 2)

    def test_a_link_in_the_templates_place_is_refused(self):
        outside = self.base / "outside"
        outside.mkdir()
        (outside / "keep").write_text("untouched")
        self.windows.mkdir(parents=True)
        self.template.symlink_to(outside, target_is_directory=True)
        code, document = self.controller().install(["alpha"])
        self.assertEqual(document["state"], "failed")
        self.assertEqual(sorted(path.name for path in outside.iterdir()), ["keep"])
        self.assertEqual(self.boots(), [])
        self.assertFalse((self.windows / "alpha").exists())

    def test_removing_the_last_program_retires_the_template(self):
        self.install("alpha")
        self.install("beta")
        code, document = self.controller().remove("alpha")
        self.assertEqual(document["state"], "success", document)
        self.assertTrue((self.template / "system.reg").is_file(), "beta still needs the template")
        code, document = self.controller().remove("beta")
        self.assertEqual(document["state"], "success", document)
        self.assertEqual(sorted(path.name for path in self.windows.iterdir()), [])

    def test_a_copy_that_fails_leaves_no_half_prefix(self):
        real = self.runtime.run_cancellable

        def failing(argv, should_cancel):
            if argv[0] == MODULE.CP_TOOL:
                self.runtime.commands.append(list(argv))
                Path(argv[-1]).mkdir(parents=True)
                (Path(argv[-1]) / "half").write_text("x")
                return MODULE.CommandResult(1, "No space left on device")
            return real(argv, should_cancel)

        self.runtime.run_cancellable = failing
        code, document = self.controller().install(["alpha"])
        self.assertEqual(document["state"], "failed", document)
        self.assertIn("No space left on device", document["items"][0]["message"])
        # A first install that did not finish leaves nothing, the template included.
        self.assertEqual(sorted(path.name for path in self.windows.iterdir()), [])


@unittest.skipUnless(os.environ.get("MOOS_WINDOWS_TEMPLATE_PROOF"),
                     "opt-in: MOOS_WINDOWS_TEMPLATE_PROOF=<a folder on the disk to measure>")
class RealTemplateProof(unittest.TestCase):
    """The image's own runtime, headless, in a private HOME on the disk being measured.

    Two 64-bit program headers are "installed": their prefixes are made from the template and
    measured, then removed. Neither is ever started (they are headers, not programs)."""

    @staticmethod
    def exclusive_bytes(path: Path) -> tuple[int | None, str]:
        """Bytes no other file shares, by `btrfs filesystem du` when the filesystem can say."""
        if shutil.which("btrfs"):
            done = subprocess.run(["btrfs", "filesystem", "du", "-s", "--raw", str(path)],
                                  capture_output=True, text=True, timeout=600)
            lines = done.stdout.strip().splitlines()
            if done.returncode == 0 and len(lines) >= 2:
                total, exclusive, *_ = lines[-1].split()
                return int(exclusive), f"btrfs du total {int(total)}"
        return None, "no btrfs du"

    @staticmethod
    def apparent(path: Path) -> int:
        done = subprocess.run(["du", "-s", "--block-size=1", str(path)], capture_output=True, text=True)
        return int(done.stdout.split()[0])

    def test_template_and_two_programs_for_real(self):
        where = Path(os.environ["MOOS_WINDOWS_TEMPLATE_PROOF"])
        self.assertTrue(where.is_dir(), where)
        base = Path(tempfile.mkdtemp(prefix="template-proof-", dir=where))
        self.addCleanup(shutil.rmtree, base, ignore_errors=True)
        home = base / "home"
        home.mkdir()
        environment = {"HOME": str(home), "PATH": "/usr/bin:/bin", "XDG_RUNTIME_DIR": str(base / "run"),
                       "DBUS_SESSION_BUS_ADDRESS": "unix:path=/nonexistent", "LANG": "C.UTF-8"}
        (base / "run").mkdir(mode=0o700)
        with mock.patch.dict(os.environ, environment, clear=True), \
                mock.patch.object(appdrop, "_refresh_menu", lambda: None):
            opener = winfix.Opener()
            apps = {app_id: recipe(opener, app_id) for app_id in ("alpha", "beta")}
            catalog = base / "catalog.json"
            catalog.write_text(json.dumps({"apps": list(apps.values())}), encoding="utf-8")
            windows = home / ".local/share/moos/windows-apps"
            free_before = shutil.disk_usage(base).free
            timings = {}
            for app_id in apps:
                controller = MODULE.Controller(MODULE.JobStore(home / ".cache/moos-store"),
                                               adapter_factory=lambda: None, catalog_path=catalog,
                                               opener=opener)
                started = time.monotonic()
                code, document = controller.install([app_id])
                timings[app_id] = round(time.monotonic() - started, 2)
                self.assertEqual(document["state"], "success", document)
            free_after = shutil.disk_usage(base).free
            template = windows / ".template"
            report = {
                "filesystem": subprocess.run(["stat", "-f", "-c", "%T", str(base)], capture_output=True,
                                             text=True).stdout.strip(),
                "wine": json.loads((windows / ".template.json").read_text())["wine"],
                "install_seconds": timings,
                "template_apparent_bytes": self.apparent(template),
                "prefix_apparent_bytes": {app_id: self.apparent(windows / app_id / "prefix") for app_id in apps},
                "exclusive_bytes": {name: self.exclusive_bytes(path)[0] for name, path in (
                    ("template", template), ("alpha", windows / "alpha/prefix"),
                    ("beta", windows / "beta/prefix"))},
                "df_used_delta_bytes": free_before - free_after,
                # The copy must not name the template: a prefix that pointed back at it would not
                # be its own.
                "template_path_in_copies": [str(path) for path in (windows / "beta/prefix").rglob("*.reg")
                                            if ".template" in path.read_text(errors="replace")],
                "menu_entries_outside_prefixes": sorted(
                    str(path.relative_to(home)) for path in home.rglob("*")
                    if "wine" in path.name.lower() and not str(path).startswith(str(windows))),
            }
            print("\nWINDOWS TEMPLATE PROOF " + json.dumps(report, sort_keys=True), file=sys.stderr)
            self.assertEqual(report["template_path_in_copies"], [])
            self.assertEqual(report["menu_entries_outside_prefixes"], [])
            for app_id in apps:
                controller = MODULE.Controller(MODULE.JobStore(home / ".cache/moos-store"),
                                               adapter_factory=lambda: None, catalog_path=catalog,
                                               opener=opener)
                code, document = controller.remove(app_id)
                self.assertEqual(document["state"], "success", document)
            self.assertEqual(sorted(path.name for path in windows.iterdir()), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
