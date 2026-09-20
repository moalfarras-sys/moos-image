#!/usr/bin/env python3
"""One registry decides what MoOS can run, and what it calls those things.

MoOS runs programs written for other systems: Windows programs through a Windows
runtime, Android apps through an Android container, Linux apps through Flatpak.
The owner's requirement is that none of that is their problem — they press
install, or drop a file, and it runs. So two things have to stay true, and
neither of them is visible by reading any single file:

1. THE ENGINE NEVER SAYS ITS NAME. A person who downloaded a `.exe` wants
   "Windows programs". Wine, Bottles, Waydroid and Proton are implementation,
   and an implementation detail in a dialog is a system admitting it is several
   systems. Every user-facing string in the registry and in the runner is
   checked here against the brands they are allowed to hide.

2. WHAT THE IMAGE SHIPS AND WHAT THE RUNNER USES MUST BE THE SAME SET. This is
   the defect that prompted the registry. `build.sh` installs wine on every
   desktop edition with the comment "so any .exe the user downloads actually
   runs" — and `moos-run-foreign` knew only about Bottles, so the first `.exe` on
   a fresh MoOS offered a large download on a machine that could already run the
   file. Both halves read green on their own; only comparing them shows it.

The resolver is also exercised for real, because a registry nothing reads is a
document, not a contract.
"""
from __future__ import annotations

import json
import importlib.machinery
import importlib.util
import os
from pathlib import Path
import re
import subprocess
import struct
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "system_files/usr/share/moos/app-engines.json"
RESOLVER = ROOT / "system_files/usr/libexec/moos-app-engine"
RUNNER = ROOT / "system_files/usr/bin/moos-run-foreign"
MIMEAPPS = ROOT / "system_files/etc/xdg/mimeapps.list"
BUILD = ROOT / "build_files/build.sh"

# The words that must never reach a person. Each is a real engine or vendor whose
# name would tell the owner they are using something other than MoOS.
ENGINE_BRANDS = ("wine", "bottles", "waydroid", "proton", "lutris",
                 "flatpak", "wayland", "kwin", "plasma", "qemu", "bubblewrap")

# The subset that is never legitimate in MoOS's voice, anywhere.
#
# The full list above is right for the registry and the file-manager runner, which
# are pure MoOS voice. Across the wider product one word needs a different rule.
# "Flatpak" is not only a runtime; it is a FILE FORMAT a person can physically
# hold — `.flatpak`, `.flatpakref` — exactly like `.exe`. "This Flatpak file is
# not valid" names the thing in their hand, and refusing to name it would make
# the message useless. Wine, Bottles, Waydroid, Proton and Lutris are different:
# nobody ever holds one, so naming one only tells a person MoOS is several
# systems wearing a coat.
#
# That exemption is for FILES ONLY, and it was quietly paying for SENTENCES: the
# storefront said "Flatpaks install for your user only" and "· AppImage", which
# name the mechanism, not anything a person holds. The copy is rewritten and
# test_the_storefront_names_a_file_but_never_the_mechanism below
# now holds the narrower line, so this
# constant stays a named subset instead of a shorter list.
RUNTIME_BRANDS = tuple(brand for brand in ENGINE_BRANDS
                       if brand not in ("flatpak", "wayland", "kwin", "plasma"))

DOCUMENT = json.loads(REGISTRY.read_text(encoding="utf-8"))


class WindowsFilePreflight(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        loader = importlib.machinery.SourceFileLoader("engine_preflight", str(RESOLVER))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        cls.engine = importlib.util.module_from_spec(spec)
        loader.exec_module(cls.engine)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def pe(self, name="sample.exe", machine=0x14c, magic=0x10b):
        data = bytearray(128)
        data[:2] = b"MZ"
        struct.pack_into("<I", data, 60, 64)
        data[64:68] = b"PE\0\0"
        struct.pack_into("<H", data, 68, machine)
        struct.pack_into("<H", data, 84, 2)
        struct.pack_into("<H", data, 88, magic)
        path = self.root / name
        path.write_bytes(data)
        return path

    def test_architecture_comes_from_both_pe_fields_not_name(self):
        for machine, magic, expected in [(0x14c, 0x10b, "x86"),
                                         (0x8664, 0x20b, "x86_64"),
                                         (0xaa64, 0x20b, "arm64"),
                                         (0x14c, 0x20b, "unknown")]:
            self.assertEqual(self.engine.pe_architecture(
                self.pe("misleading.txt", machine, magic)), expected)

    def test_malformed_and_unavailable_inputs_are_unknown(self):
        path = self.pe()
        original = path.read_bytes()
        for data in [b"", b"MZ", original[:88], original.replace(b"PE\0\0", b"NOPE")]:
            path.write_bytes(data)
            self.assertEqual(self.engine.pe_architecture(path), "unknown")
        data = bytearray(original)
        struct.pack_into("<I", data, 60, 0xffffffff)
        path.write_bytes(data)
        self.assertEqual(self.engine.pe_architecture(path), "unknown")
        self.assertEqual(self.engine.pe_architecture(self.root / "missing.exe"), "unknown")
        fifo = self.root / "fifo.exe"
        os.mkfifo(fifo)
        self.assertEqual(self.engine.pe_architecture(fifo), "unknown")
        self.assertEqual(self.engine.pe_architecture(self.root), "unknown")

    def test_missing_32bit_payload_blocks_before_launch_or_setup(self):
        definition = next(e for e in DOCUMENT["engines"] if e["id"] == "windows")
        def state(runtime):
            present = runtime["id"] == "wine"
            return {"id": runtime["id"], "ready": present, "needs_setup": False}
        with mock.patch.object(self.engine, "runtime_state", side_effect=state), \
                mock.patch.object(self.engine, "wine_x86_payload", return_value="missing"):
            answer = self.engine.describe(definition, str(self.pe()))
        self.assertFalse(answer["ready"])
        self.assertFalse(answer["needs_setup"])
        self.assertIsNone(answer["chosen"])
        self.assertEqual(answer["preflight"]["code"], "missing-windows-x86-runtime")
        self.assertEqual(set(answer["preflight"]["reason"]), {"ar", "en"})

    def test_new_wow64_is_not_rejected_for_missing_multilib(self):
        with mock.patch.object(self.engine, "wine_x86_payload", return_value="wow64"):
            answer = self.engine.file_preflight(str(self.pe()), {"id": "wine"})
        self.assertEqual(answer["status"], "available")

    def test_64bit_and_other_runtimes_do_not_inherit_32bit_failure(self):
        with mock.patch.object(self.engine, "wine_x86_payload", side_effect=AssertionError):
            answer = self.engine.file_preflight(str(self.pe(machine=0x8664, magic=0x20b)), {"id": "wine"})
            self.assertEqual(answer["status"], "unknown")
            answer = self.engine.file_preflight(str(self.pe()), {"id": "com.usebottles.bottles"})
            self.assertEqual(answer["status"], "unknown")

    def test_actual_payload_layouts_not_package_names_decide(self):
        def architecture(path):
            return "x86" if "i386-windows" in str(path) else "x86_64"
        with mock.patch.object(self.engine.shutil, "which", return_value="/usr/bin/wine"), \
                mock.patch.object(Path, "resolve", return_value=Path("/usr/bin/wine64")), \
                mock.patch.object(self.engine, "pe_architecture", side_effect=architecture), \
                mock.patch.object(Path, "is_file", side_effect=lambda: False):
            self.assertEqual(self.engine.wine_x86_payload(), "missing")
        with mock.patch.object(self.engine.shutil, "which", return_value="/usr/bin/wine"), \
                mock.patch.object(Path, "resolve", return_value=Path("/usr/bin/wine64")), \
                mock.patch.object(self.engine, "pe_architecture", side_effect=architecture), \
                mock.patch.object(Path, "is_file", autospec=True,
                                  side_effect=lambda p: "x86_64-unix" in str(p)):
            self.assertEqual(self.engine.wine_x86_payload(), "wow64")

    def test_unknown_custom_runtime_layout_is_not_claimed_missing(self):
        with mock.patch.object(self.engine.shutil, "which", return_value="/opt/custom/wine"):
            self.assertEqual(self.engine.wine_x86_payload(), "unknown")


class NativeX86CapabilityProbe(unittest.TestCase):
    """Run the shell probe with fixed stubs: cache, invalidation and argv are behavior."""

    def test_probe_uses_only_the_built_in_file_and_rechecks_after_an_image_update(self):
        source = RUNNER.read_text(encoding="utf-8")
        start = source.index("native_x86_ready() {")
        function = source[start:source.index("\nusage()", start)]
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            bindir = root / "bin"
            cache = root / "cache"
            bindir.mkdir()
            probe = root / "moos-command.exe"
            probe.write_bytes(b"MoOS-owned probe fixture")
            for shipped in (
                    "/usr/lib64/wine-wow64/wine/i386-windows/cmd.exe",
                    "/usr/lib64/wine/i386-windows/cmd.exe",
                    "/usr/lib/wine/i386-windows/cmd.exe"):
                function = function.replace(shipped, str(probe))

            rpm = bindir / "rpm-ostree"
            rpm.write_text(
                "#!/bin/sh\nprintf '{\"deployments\":[{\"booted\":true,"
                "\"checksum\":\"%s\"}]}' \"$CHECKSUM\"\n", encoding="utf-8")
            wine = bindir / "wine"
            wine.write_text(
                "#!/bin/sh\nprintf '%s\\n' \"$*\" >>\"$WINE_LOG\"\n"
                "exit \"$WINE_EXIT\"\n", encoding="utf-8")
            rpm.chmod(0o755)
            wine.chmod(0o755)
            harness = root / "probe.sh"
            harness.write_text(
                "#!/bin/bash\nset -uo pipefail\n" + function
                + "\nnative_x86_ready\ncode=$?\nprintf 'code=%s\\n' \"$code\"\nexit 0\n",
                encoding="utf-8")
            harness.chmod(0o755)
            log = root / "wine.log"
            env = dict(os.environ, PATH=f"{bindir}:/usr/bin:/bin",
                       XDG_CACHE_HOME=str(cache), WINE_LOG=str(log),
                       CHECKSUM="revision-a", WINE_EXIT="1")

            first = subprocess.run([str(harness)], env=env, text=True,
                                   capture_output=True, check=True)
            second = subprocess.run([str(harness)], env=env, text=True,
                                    capture_output=True, check=True)
            self.assertIn("code=1", first.stdout)
            self.assertIn("code=1", second.stdout)
            self.assertEqual(len(log.read_text(encoding="utf-8").splitlines()), 1,
                             "a blocked answer was not cached for this deployment")

            env.update(CHECKSUM="revision-b", WINE_EXIT="0")
            updated = subprocess.run([str(harness)], env=env, text=True,
                                     capture_output=True, check=True)
            calls = log.read_text(encoding="utf-8").splitlines()
            self.assertIn("code=0", updated.stdout)
            self.assertEqual(len(calls), 2, "an image update inherited a stale blocked result")
            self.assertTrue(all(call == f"{probe} /c exit" for call in calls), calls)


class UnifiedProductVoice(unittest.TestCase):
    def test_ordinary_surfaces_do_not_expose_compatibility_implementation_names(self):
        surfaces = {
            "Mo AI": ROOT / "system_files/usr/share/moos/apps/moai/main.qml",
            "Settings": ROOT / "system_files/usr/share/moos/apps/settings/main.qml",
            "Store": ROOT / "system_files/usr/share/moos/apps/store/main.qml",
            "first run": ROOT / "system_files/usr/bin/moos-firstrun",
            "app setup": ROOT / "system_files/usr/bin/moos-setup",
        }
        forbidden = ("title: \"Bottles\"", "title: \"Waydroid\"",
                     "Setup Windows Apps (Bottles)", "Setup Android (Waydroid)",
                     "MoOS desktop · Wayland", "Update Flatpak apps",
                     "حدّث تطبيقات Flatpak هنا", "Update Flatpaks now",
                     "Optional Flatpak engine",
                     "waydroid app install <file>")
        offenders = []
        for label, path in surfaces.items():
            text = path.read_text(encoding="utf-8")
            for phrase in forbidden:
                if phrase in text:
                    offenders.append(f"{label}: {phrase}")
        self.assertEqual(offenders, [], "implementation names escaped into product UI")


def user_facing_strings(node, path="") -> list[tuple[str, str]]:
    """Every string a person could read: `name` and `reason` values, recursively.

    Explicitly NOT `id`, `probe` or `_`: an engine's identifier has to be its
    real name for the resolver to find it, and `_` is a note to whoever reads the
    file next. Only what is rendered is policed.
    """
    found: list[tuple[str, str]] = []
    if isinstance(node, dict):
        for key, value in node.items():
            here = f"{path}.{key}" if path else key
            if key in ("name", "reason") and isinstance(value, dict):
                for language, text in value.items():
                    found.append((f"{here}.{language}", str(text)))
            else:
                found.extend(user_facing_strings(value, here))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            found.extend(user_facing_strings(value, f"{path}[{index}]"))
    return found


class TheRegistryIsWellFormed(unittest.TestCase):
    def test_schema_and_required_shape(self):
        self.assertEqual(DOCUMENT.get("schema"), 1)
        self.assertTrue(DOCUMENT.get("engines"), "no engines are declared")
        seen = set()
        for engine in DOCUMENT["engines"]:
            for field in ("id", "name", "claims", "runtimes"):
                self.assertIn(field, engine, f"engine {engine.get('id')} has no {field}")
            self.assertNotIn(engine["id"], seen, "two engines share an id")
            seen.add(engine["id"])
            self.assertEqual(set(engine["name"]), {"ar", "en"},
                             f"{engine['id']} must be named in both languages")
            self.assertTrue(engine["runtimes"],
                            f"{engine['id']} claims files it has nothing to run them with")
            for runtime in engine["runtimes"]:
                self.assertIn(runtime.get("carrier"), ("image", "flatpak"),
                              f"{engine['id']}/{runtime.get('id')} has no known carrier")

    def test_no_extension_is_claimed_by_two_engines(self):
        """Two engines claiming `.exe` is a coin toss the owner experiences as chaos."""
        owner: dict[str, str] = {}
        for engine in DOCUMENT["engines"]:
            for extension in engine["claims"].get("extensions", []):
                self.assertNotIn(
                    extension.lower(), owner,
                    f".{extension} is claimed by both {owner.get(extension.lower())} "
                    f"and {engine['id']}")
                owner[extension.lower()] = engine["id"]

    def test_what_cannot_be_run_is_written_down_with_a_reason(self):
        """"Can MoOS run Mac apps?" gets one answer, in the file, in both languages."""
        unsupported = {entry["id"]: entry for entry in DOCUMENT.get("unsupported", [])}
        self.assertIn("macos", unsupported,
                      "macOS must be listed as unsupported with a reason, not omitted — "
                      "an unanswered question gets re-answered differently every time")
        for entry in unsupported.values():
            self.assertEqual(set(entry.get("reason", {})), {"ar", "en"},
                             f"{entry['id']} must say WHY, in both languages")
            self.assertGreater(len(entry["reason"]["en"]), 60,
                               f"{entry['id']}'s reason is too short to be a reason")


class TheEngineNeverSaysItsName(unittest.TestCase):
    def test_no_user_facing_string_in_the_registry_names_an_engine(self):
        offenders = []
        for where, text in user_facing_strings(DOCUMENT):
            lowered = text.lower()
            for brand in ENGINE_BRANDS:
                # macOS's reason is allowed to discuss what does not work and why;
                # it is an explanation, not a label on a button.
                if where.startswith("unsupported"):
                    continue
                if re.search(rf"\b{brand}\b", lowered):
                    offenders.append(f"{where}: {text!r} names {brand!r}")
        self.assertEqual(offenders, [],
                         "these strings are shown to a person and name the engine:\n  "
                         + "\n  ".join(offenders))

    def test_the_runner_shows_the_kind_of_program_not_the_runtime(self):
        """Every dialog and popup string in moos-run-foreign, checked as text."""
        source = RUNNER.read_text(encoding="utf-8")
        # Only the arguments of the two functions that reach a screen.
        shown = re.findall(r'(?:notify|ask)\s+"((?:[^"\\]|\\.)*)"', source)
        self.assertTrue(shown, "found no user-facing strings in the runner to check")
        offenders = []
        for text in shown:
            for brand in ENGINE_BRANDS:
                if re.search(rf"\b{brand}\b", text.lower()):
                    offenders.append(f"{text!r} names {brand!r}")
        self.assertEqual(offenders, [],
                         "moos-run-foreign says these to a person:\n  " + "\n  ".join(offenders))

    def test_moos_own_voice_never_names_a_runtime_anywhere_it_speaks(self):
        """The rule, applied to every surface — not just the two it started on.

        The gate first read only the registry and the file-manager runner, and an
        audit found the same brands sitting on Mo Store's front page and in App
        Drop's dialogs. The rule was never about those two files; it is about
        MoOS's VOICE.

        The line is drawn at authorship. A catalogue entry's `en`/`ar` is a third
        party's own product name — calling Bottles something else would be a lie,
        and it is exempt. Everything else in these files is MoOS talking: the
        descriptions it writes, the dialogs it shows, the labels on its controls.
        MoOS does not get to tell a person that a runtime is how they run their
        Windows programs, because that is MoOS's own job now.
        """
        catalogue = json.loads(
            (ROOT / "system_files/usr/share/moos/store/catalog.json")
            .read_text(encoding="utf-8"))
        offenders = []
        for app in catalogue.get("apps", []):
            for field in ("desc_en", "desc_ar"):
                text = str(app.get(field, ""))
                for brand in RUNTIME_BRANDS:
                    if re.search(rf"\b{brand}\b", text.lower()):
                        offenders.append(
                            f"catalog.json {app['id']}.{field}: {text!r} names {brand!r}")
        self.assertEqual(
            offenders, [],
            "MoOS wrote these descriptions, so they are MoOS speaking:\n  "
            + "\n  ".join(offenders))

    def test_the_store_and_app_drop_speak_the_same_way(self):
        """Two more surfaces the rule always covered and the gate could not see."""
        surfaces = {
            "store/main.qml": (
                ROOT / "system_files/usr/share/moos/apps/store/main.qml",
                # Arabic and English literals the Store renders.
                r'"([^"\\]{4,}?)"'),
            "moos-app-drop": (
                ROOT / "system_files/usr/bin/moos-app-drop",
                r'"([^"\\]{4,}?)"'),
        }
        offenders = []
        for name, (path, pattern) in surfaces.items():
            source = path.read_text(encoding="utf-8")
            # Strip comments: a note to the next engineer explaining WHY a runtime
            # is hidden must be allowed to name it.
            stripped = re.sub(r"(?m)^\s*(#|//).*$", "", source)
            for text in re.findall(pattern, stripped):
                if "/" in text or text.startswith("org.") or text.startswith("com."):
                    continue          # a path or an application id, not prose
                for brand in RUNTIME_BRANDS:
                    if re.search(rf"\b{brand}\b", text.lower()):
                        offenders.append(f"{name}: {text!r} names {brand!r}")
        self.assertEqual(
            offenders, [],
            "these are strings MoOS shows a person:\n  " + "\n  ".join(offenders))

    def test_the_storefront_names_a_file_but_never_the_mechanism(self):
        """Where MoOS sells and installs apps, packaging may only name a FILE.

        RUNTIME_BRANDS lets "flatpak" through everywhere because a person can
        physically hold a `.flatpakref`, and a message about the file in their
        hand has to name it. An audit found that exemption covering sentences it
        was never written for: Mo Store's install sheet read "Flatpaks install
        for your user only", its review line appended "· AppImage", and MoAI
        described installing an app as "in sandboxed Flatpak container". None of
        those is a file; each is the mechanism, which is the one thing the owner
        asked never to see.

        So on these surfaces the packaging word is allowed only inside a file
        name -- `.flatpak`, `.flatpakref`, `.appimage`. Prose may not carry it.
        `appimage` is checked here and not in ENGINE_BRANDS because it is a
        format rather than a vendor: `install.kind === "appimage"` is code MoOS
        must keep, and only the rendered sentence is the offence.

        App Drop is deliberately NOT one of these surfaces, and that is not a
        hole. Its entire job is the file a person just dropped on the desk, so
        "This Flatpak file is not valid" and "this AppImage could not be
        unpacked" are the file in their hand, named -- the exact case the
        exemption exists for. Refusing the word there would leave a person
        holding a file MoOS will not name. The storefront is the opposite: there
        no file is in anyone's hand until MoOS puts it there, so the word can
        only be the mechanism. The older voice gate still holds App Drop to
        RUNTIME_BRANDS, so wine, Bottles and Waydroid stay hidden in both.
        """
        PACKAGING = ("flatpak", "flatpaks", "appimage")
        surfaces = {
            "store/main.qml": ROOT / "system_files/usr/share/moos/apps/store/main.qml",
            "welcome/main.qml": ROOT / "system_files/usr/share/moos/apps/welcome/main.qml",
            "moai/main.qml": ROOT / "system_files/usr/share/moos/apps/moai/main.qml",
        }
        offenders = []
        for name, path in surfaces.items():
            source = path.read_text(encoding="utf-8")
            stripped = re.sub(r"(?m)^\s*(#|//).*$", "", source)
            for text in re.findall(r'"([^"\\]{4,}?)"', stripped):
                lowered = text.lower()
                if " " not in text:
                    continue          # an id, an enum value or a path -- not prose
                if "/" in text:
                    continue          # a path
                if "`" in text or ("<" in text and ">" in text):
                    # MoAI's system prompt tells the MODEL which command to run.
                    # `moai-do install <flatpak-id>` has to be the real command
                    # or the tool call fails; no person reads this line.
                    continue
                if re.search(r"\.(flatpak|flatpakref|appimage)\b", lowered):
                    continue          # names a file, which is the whole exemption
                for brand in PACKAGING:
                    if re.search(rf"\b{brand}\b", lowered):
                        offenders.append(f"{name}: {text!r} names {brand!r}")
        self.assertEqual(
            offenders, [],
            "MoOS says these to a person, and they name the packaging rather "
            "than a file:\n  " + "\n  ".join(offenders))
    def test_the_android_menu_surfaces_are_hidden_or_renamed(self):
        """The launcher is not the only place a brand can sit.

        Every string gate in this file reads MoOS's own files, and all of them
        were green while the application menu on the station showed a folder
        called "Waydroid" containing a launcher called "Waydroid". Neither came
        from a MoOS file -- both ship inside the waydroid package, and the menu
        folder is the one that matters, because `waydroid.menu` collects every
        `X-WayDroid-App` into it, so it is where EVERY Android app the owner
        installs ends up.

        build.sh hides the launcher and relabels the folder to "Android apps"
        (the platform an app came from, which Mo Store's own category already
        says) with a MoOS icon, and fails the build if the files it edits are
        not where it expects or the edit did not take. This checks that all of
        that is still in build.sh -- deleting any half would silently return the
        brand to the menu.
        """
        build = BUILD.read_text(encoding="utf-8")
        for needle, why in (
            ("/usr/share/applications/Waydroid.desktop",
             "the container's own launcher must be masked"),
            ("/usr/share/desktop-directories/waydroid.directory",
             "the menu folder every Android app lands in must be relabelled"),
            ("s|^Name=.*|Name=Android apps|",
             "the folder must be named for the platform, not the engine"),
            ("Name[ar]=\u062a\u0637\u0628\u064a\u0642\u0627\u062a \u0623\u0646\u062f\u0631\u0648\u064a\u062f",
             "an Arabic session must not fall back to the English label"),
            ("Icon=moos-android-apps-symbolic",
             "the folder must not wear the engine's icon either"),
            ("GATE FAIL: the Android container's own launcher is still in the menu",
             "the build must fail, not warn, if the mask did not take"),
            ("GATE FAIL: the Android app folder still wears the engine's name",
             "the build must fail if the relabel did not take"),
        ):
            # assertIn would print all 5,000 lines of build.sh into the CI
            # log on failure, burying the one sentence that says what broke.
            self.assertTrue(needle in build, f"build.sh no longer has {needle!r}: {why}")
        icon = ROOT / ("system_files/usr/share/icons/MoOSUI2Aurora/moos/actions"
                       "/scalable/moos-android-apps-symbolic.svg")
        self.assertTrue(icon.is_file(),
                        "build.sh points the folder at an icon the image does not ship, "
                        "which would leave the folder blank instead of branded")

    def test_the_app_menu_carries_no_other_desktop_name(self):
        """A second settings app, and four foreign names, in the owner's menu.

        build.sh already had a section for this -- it hid the distribution's
        debug tools and Fedora's DUPLICATE settings launcher,
        `kdesystemsettings.desktop`. It left `systemsettings.desktop`, the real
        one, visible. So the menu offered "MoOS Settings" and "System Settings"
        side by side: two settings applications, which is the one thing the
        owner said he did not want, and the gate under that section only ever
        checked the duplicate. Beside it sat "Dolphin", "KDE Connect", "KDE
        Partition Manager" and "Info Center", in Arabic too.

        Hiding all five would be wrong -- a person needs a file manager and a
        disk tool, and MoOS Settings ROUTES its hardware panels into
        systemsettings and kinfocenter deliberately. So each is given MoOS's
        name and icon, and only the two that are reached exclusively through
        MoOS Settings also leave the menu. This checks both halves are still
        in build.sh, in both languages, since deleting either silently returns
        another desktop's name to the menu.
        """
        build = BUILD.read_text(encoding="utf-8")
        self.assertIn("moos_rebrand_entry()", build,
                      "the helper that puts MoOS's name on a kept entry is gone")
        for entry, english in (
            ("org.kde.dolphin.desktop", '"Files"'),
            ("org.kde.kdeconnect.app.desktop", '"Phone"'),
            ("org.kde.partitionmanager.desktop", '"Disks"'),
            ("systemsettings.desktop", '"MoOS Settings"'),
            ("org.kde.kinfocenter.desktop", '"System Report"'),
            ("nvidia-settings.desktop", '"Graphics Card"'),
        ):
            line = next((l for l in build.splitlines()
                         if l.startswith("moos_rebrand_entry") and entry in l), "")
            self.assertTrue(line, f"{entry} is no longer rebranded")
            self.assertIn(english, line,
                          f"{entry} must carry MoOS's English name")
            self.assertIn("moos-", line,
                          f"{entry} must carry a MoOS icon, not the vendor's")
        # The two that are only ever reached THROUGH MoOS Settings leave the menu.
        for entry in ("systemsettings.desktop", "org.kde.kinfocenter.desktop",
                      "nvidia-settings.desktop"):
            line = next((l for l in build.splitlines()
                         if l.startswith("moos_rebrand_entry") and entry in l), "")
            self.assertTrue(line.rstrip().endswith("hide"),
                            f"{entry} must be hidden: MoOS Settings is the one settings app")
        for entry in ("org.kde.dolphin.desktop", "org.kde.partitionmanager.desktop"):
            line = next((l for l in build.splitlines()
                         if l.startswith("moos_rebrand_entry") and entry in l), "")
            self.assertTrue(line.rstrip().endswith("show"),
                            f"{entry} is a tool a person needs; renaming it is the fix, "
                            f"not removing it from the menu")
        self.assertIn(
            "GATE FAIL: $_f is still in the menu — MoOS Settings is the one settings app",
            build,
            "the build must FAIL on a second settings app, not warn about it")
        self.assertIn(
            "GATE FAIL: $_f still wears another desktop's name in the menu", build,
            "the build must fail if a rebrand did not take")

    def test_the_runner_does_not_hint_a_terminal_command_at_the_owner(self):
        """"try: waydroid app install …" is the engine's name AND its CLI."""
        source = RUNNER.read_text(encoding="utf-8")
        for brand in ("waydroid", "wine", "flatpak"):
            self.assertNotRegex(
                source, rf'echo\s+"[^"]*\b{brand}\b[^"]*"',
                f"the runner echoes a {brand} command at the owner; a person who "
                f"double-clicked a file is not holding a terminal")


class TheImageAndTheRunnerAgree(unittest.TestCase):
    @staticmethod
    def installed_packages(build: str) -> set[str]:
        """Every package name build.sh puts into an install list.

        Collected from the `+=(...)` accumulators and the dnf5 install lines
        rather than matched loosely against the whole file, so a runtime that is
        only MENTIONED in a comment does not read as installed.
        """
        names: set[str] = set()
        for block in re.findall(r"\+=\(([^)]*)\)", build):
            names.update(re.findall(r"[\w.+-]+", block))
        for block in re.findall(r"dnf5[^\n]*install([^\n]*)", build):
            names.update(re.findall(r"[\w.+-]+", block))
        return names

    def test_every_shipped_runtime_is_actually_installed_by_the_build(self):
        """The defect the registry exists for, stated as a check.

        A runtime declared `carrier: image` is a promise that it is IN the signed
        image. If the build stops installing it, the runner silently falls
        through to offering a download on a machine that used to just work.
        """
        build = BUILD.read_text(encoding="utf-8")
        for engine in DOCUMENT["engines"]:
            for runtime in engine["runtimes"]:
                if runtime.get("carrier") != "image":
                    continue
                probe = runtime.get("probe") or runtime["id"]
                origin = runtime.get("from")
                self.assertIn(
                    origin, ("build", "base", "overlay"),
                    f"{engine['id']}/{probe} must say where it comes from, so this "
                    f"gate knows whether build.sh is supposed to install it")
                if origin == "overlay":
                    # MoOS's own tools: they are in the tree or they are not.
                    self.assertTrue(
                        (ROOT / "system_files/usr/bin" / probe).exists()
                        or (ROOT / "system_files/usr/libexec" / probe).exists(),
                        f"{engine['id']} declares the overlay tool {probe!r}, which "
                        f"system_files does not carry")
                    continue
                if origin == "base":
                    # From ghcr.io/ublue-os/kinoite-main; build.sh does not install
                    # it and this gate cannot see inside the base image. The image
                    # build's own gates are where a missing base tool surfaces.
                    continue
                self.assertIn(
                    probe, self.installed_packages(build),
                    f"{engine['id']} declares the shipped runtime {probe!r}, but "
                    f"build.sh never installs it — the registry would promise a "
                    f"runtime the image does not carry")

    def test_every_mime_routed_to_the_runner_is_claimed_by_an_engine(self):
        """mimeapps sends these to moos-run-foreign; something must know what they are."""
        mimeapps = MIMEAPPS.read_text(encoding="utf-8")
        routed = set(re.findall(r"(?m)^([\w.+-]+/[\w.+-]+)=org\.moos\.runforeign\.desktop",
                                mimeapps))
        self.assertTrue(routed, "nothing is routed to the MoOS runner any more")
        claimed = {mime.lower()
                   for engine in DOCUMENT["engines"]
                   for mime in engine["claims"].get("mime", [])}
        # Office documents go to the runner too and are opened by an application,
        # not by an engine; they are out of scope here and covered elsewhere.
        program_like = {mime for mime in routed
                        if "officedocument" not in mime and "opendocument" not in mime
                        and mime not in ("text/csv",)
                        and not mime.startswith("application/msword")
                        and not mime.startswith("application/vnd.ms-")
                        and not mime.startswith("text/rtf")
                        and not mime.startswith("application/rtf")}
        missing = sorted(mime for mime in program_like if mime.lower() not in claimed)
        self.assertEqual(
            missing, [],
            "mimeapps.list hands these to the runner but no engine claims them, so the "
            "resolver returns nothing and a double-click does nothing:\n  "
            + "\n  ".join(missing))

    def test_the_runner_asks_the_resolver_instead_of_deciding_alone(self):
        """Deciding in two places is how the two places came to disagree."""
        source = RUNNER.read_text(encoding="utf-8")
        self.assertIn("moos-app-engine", source,
                      "the runner must resolve through the shared registry")
        # The old shape: a hardcoded runtime id driving the decision.
        self.assertNotIn('BOTTLES_ID=', source,
                         "the runner still carries a hardcoded runtime constant")
        self.assertIn('engine "$target" preflight_reason', source,
                      "the resolver can block an incompatible file, but the runner hides why")
        self.assertIn('engine "$target" preflight_architecture', source,
                      "the runner cannot gate the real PE32 capability without the parsed header")
        self.assertIn('native_x86_ready', source,
                      "payload presence alone did not prove that PE32 mappings work")
        self.assertIn('wine "$probe" /c exit', source,
                      "the capability probe must execute MoOS's own file, never the download")
        self.assertIn('The file was not launched.', source,
                      "a failed PE32 probe must tell the owner the target did not run")
        self.assertIn('--warningyesno "$1"', source,
                      "pressing Enter on a runner consent dialog must remain No")
        self.assertIn('--wine-run', source)
        self.assertIn('windows-last.log', source,
                      "a detached Windows failure must leave evidence instead of stderr=/dev/null")


@unittest.skipIf(not os.access("/usr/bin/python3", os.X_OK), "no python3")
class TheResolverAnswers(unittest.TestCase):
    """Run the real resolver, because a registry nothing reads is a document."""

    def resolve(self, name: str):
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw) / name
            target.touch()
            result = subprocess.run(
                ["python3", str(RESOLVER), "resolve", str(target)],
                capture_output=True, text=True, timeout=60,
                env={**os.environ, "MOOS_APP_ENGINES": str(REGISTRY),
                     "PATH": "/usr/bin:/bin"})
        return result.returncode, json.loads(result.stdout or "{}")

    def test_each_claimed_extension_resolves_to_its_own_engine(self):
        for engine in DOCUMENT["engines"]:
            for extension in engine["claims"].get("extensions", []):
                code, answer = self.resolve(f"sample.{extension}")
                self.assertEqual(code, 0, f".{extension} did not resolve")
                self.assertEqual(answer.get("engine"), engine["id"],
                                 f".{extension} resolved to the wrong engine")
                self.assertEqual(set(answer.get("name", {})), {"ar", "en"})

    def test_a_file_no_engine_claims_says_so_instead_of_guessing(self):
        code, answer = self.resolve("notes.txt")
        self.assertEqual(code, 3)
        self.assertIsNone(answer.get("engine"))

    def test_the_answer_distinguishes_ready_from_needs_setup(self):
        """Three states, because 'installed' and 'can take a file' differ."""
        code, answer = self.resolve("program.exe")
        self.assertEqual(code, 0)
        for field in ("ready", "needs_setup", "runtimes", "chosen"):
            self.assertIn(field, answer)
        self.assertIsInstance(answer["ready"], bool)
        if answer["ready"]:
            self.assertIsNotNone(answer["chosen"])
            self.assertFalse(answer["needs_setup"],
                             "an engine cannot be both ready and awaiting setup")


if __name__ == "__main__":
    unittest.main(verbosity=2)
