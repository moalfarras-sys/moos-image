#!/usr/bin/env python3
"""Gate: MoOS's settings are native System Settings modules — one family, one backend.

WHY THIS EXISTS

MoOS had two settings front ends: a 3151-line QML "Command Center" that nothing opened any
more, and one System Settings module whose six pages were buttons inside one page. Every
behaviour gate pointed at the dead one. The pages now are the kcm_moos* family
(moos-settings-kcm/): one plugin per MoOS page in a MoOS group of System Settings, one shared
C++ backend, one status helper. This gate holds what makes that true rather than merely
present:

  * every module directory is one plugin with honest metadata, and the build finds them all;
  * the backend is closed: one status helper, fixed routes, three environment values and a
    fixed verb list — nothing a page composes ever runs;
  * the status contract the C++ enforces is the document the helper really publishes;
  * a deep link is a module id, with no request file and no environment channel;
  * every page is a scrolling, mirrored, bilingual native module whose buttons report a
    route that could not open, and whose rows cover every state their owners publish;
  * the settings, updater, recovery and remote entries resolve to the right window.

Tests that execute the launcher isolate HOME, the XDG tree, the session bus and the display.
"""

from __future__ import annotations

import json
import os
import re
import runpy
import shutil
import stat
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
KCM = ROOT / "moos-settings-kcm"
MODULES = KCM / "modules"
COMMON = KCM / "common"
BACKEND = KCM / "src/moosbackend.cpp"
HEADER = KCM / "src/moosbackend.h"
LAUNCHER = ROOT / "system_files/usr/bin/moos-settings"
STATUS = ROOT / "system_files/usr/libexec/moos-settings-status"
THEME_TOOL = ROOT / "system_files/usr/bin/moos-theme"
CATEGORY = ROOT / "system_files/usr/share/systemsettings/categories/settings-moos.desktop"
GATE = ROOT / "build_files/verify_settings_modules.sh"
APPLICATIONS = ROOT / "system_files/usr/share/applications"
DESKTOP = APPLICATIONS / "org.moos.settings.desktop"
UPDATER_DESKTOP = APPLICATIONS / "org.moos.updater.desktop"
RECOVERY_DESKTOP = APPLICATIONS / "org.moos.recovery.desktop"
REMOTE_DESKTOP = APPLICATIONS / "org.moos.remote.desktop"
REMOTE_APP = ROOT / "system_files/usr/bin/mo-pc-remote"
ROUTER = ROOT / "system_files/usr/bin/moos-open"
ICONS = ROOT / "system_files/usr/share/icons/hicolor"
ICON_SIZES = (16, 22, 24, 32, 48, 64, 96, 128, 192, 256, 512)
NODE = shutil.which("node")

# id -> (directory, category, weight): the spec's table. The Mo AI and MoOS Themes modules
# are built by their own slices and are held to the same checks once their directory exists.
CORE = {
    "kcm_moos": ("overview", "moos", 1),
    "kcm_moos_update": ("update", "moos", 2),
    "kcm_moos_whatsnew": ("whatsnew", "moos", 3),
    "kcm_moos_remote": ("remote", "moos", 5),
    "kcm_moos_recovery": ("recovery", "moos", 6),
}
CONTRACTED = {
    "kcm_moos_ai": ("ai", "moos", 4),
    "kcm_moos_appearance": ("appearance", "appearance", 1),
}
SECTIONS = {
    "overview": "kcm_moos", "home": "kcm_moos", "system": "kcm_moos", "about": "kcm_moos",
    "update": "kcm_moos_update", "whats-new": "kcm_moos_whatsnew",
    "assistant": "kcm_moos_ai", "remote": "kcm_moos_remote", "recovery": "kcm_moos_recovery",
    "appearance": "kcm_moos_appearance", "themes": "kcm_moos_appearance",
    "wallpaper": "kcm_moos_appearance", "connectivity": "kcm_networkmanagement",
    "devices": "kcm_kscreen", "apps": "kcm_componentchooser", "privacy": "kcm_app-permissions",
}
# id -> (first fixed argument of moos-theme, argument kind)
FIXED_VERBS = {
    "theme-status": ("", "None"),
    "theme-motion-status": ("motion", "None"),
    "theme-clarity-status": ("clarity", "None"),
    "theme-apply-lnf": ("apply-lnf", "LookAndFeel"),
    "theme-undo": ("undo", "None"),
    "theme-motion": ("motion", "Motion"),
    "theme-clarity": ("clarity", "Clarity"),
    "theme-wallpaper-reset": ("wallpaper-reset", "None"),
    "theme-wallpaper-token": ("wallpaper-token", "WallpaperToken"),
}


def modules() -> dict[str, tuple[Path, dict]]:
    found: dict[str, tuple[Path, dict]] = {}
    for directory in sorted(p for p in MODULES.iterdir() if p.is_dir()):
        metadata = sorted(directory.glob("*.json"))
        if len(metadata) != 1:
            raise AssertionError(f"{directory} must hold exactly one <plugin id>.json")
        found[metadata[0].stem] = (directory, json.loads(metadata[0].read_text(encoding="utf-8")))
    return found


def kcm_qml() -> list[Path]:
    return sorted(KCM.rglob("*.qml"))


def page(name: str) -> str:
    return (MODULES / name / "ui/main.qml").read_text(encoding="utf-8")


def code(text: str, marker: str = "//") -> str:
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith(marker))


def qml_function(qml: str, name: str) -> str:
    start = qml.index("    function " + name + "(")
    end = qml.index("{", start) + 1
    depth = 1
    while depth:
        depth += {"{": 1, "}": -1}.get(qml[end], 0)
        end += 1
    return qml[start:end]


def isolated_env(**extra: str) -> dict[str, str]:
    env = {key: value for key, value in os.environ.items()
           if key not in {"DBUS_SESSION_BUS_ADDRESS", "DISPLAY", "WAYLAND_DISPLAY"}}
    env.update(extra)
    return env


def fixed_verbs() -> dict[str, tuple[str, str]]:
    table = BACKEND.read_text(encoding="utf-8").split("constexpr Verb FixedVerbs[] = {", 1)[1]
    table = table.split("};", 1)[0]
    verbs = {}
    for match in re.finditer(
            r'\{"([a-z-]+)", ThemeTool, \{(?:nullptr|"([a-z-]+)"), nullptr\}, Argument::(\w+)\}', table):
        verbs[match.group(1)] = (match.group(2) or "", match.group(3))
    return verbs


def status_shape() -> tuple[list[tuple[str | None, str, str]], list[str]]:
    source = BACKEND.read_text(encoding="utf-8")
    table = source.split("constexpr Field StatusShape[] = {", 1)[1].split("};", 1)[0]
    fields = [(None if group == "nullptr" else group.strip('"'), key, kind) for group, key, kind in
              re.findall(r'\{(nullptr|"[a-zA-Z]+"), "([a-zA-Z]+)", QJsonValue::(\w+)\}', table)]
    labels = re.findall(r'"([a-zA-Z]+)"', source.split("BilingualLabels[] = {", 1)[1].split("};", 1)[0])
    return fields, labels


class TheFamily(unittest.TestCase):
    def test_every_module_directory_is_one_plugin_and_the_build_finds_them_all(self) -> None:
        cmake = (KCM / "CMakeLists.txt").read_text(encoding="utf-8")
        self.assertIn('file(GLOB module_dirs LIST_DIRECTORIES true CONFIGURE_DEPENDS '
                      '"${CMAKE_CURRENT_SOURCE_DIR}/modules/*")', cmake)
        self.assertIn('moos_add_settings_module("${module_dir}")', cmake)
        self.assertIn('<qresource prefix=\\"/kcm/${plugin_id}\\">', cmake,
                      "KQuickConfigModule looks for main.qml at /kcm/<plugin id>/")
        self.assertIn('INSTALL_NAMESPACE "plasma/kcms/systemsettings"', cmake)
        self.assertIn("settings-modules.list", cmake)
        required = cmake.split("foreach(required", 1)[1].split(")", 1)[0]
        for plugin_id in CORE:
            self.assertIn(plugin_id, required.split())
        found = modules()
        self.assertTrue(set(CORE) <= set(found), sorted(set(CORE) - set(found)))
        common = {path.name for path in COMMON.glob("*.qml")}
        for plugin_id, (directory, metadata) in found.items():
            with self.subTest(module=plugin_id):
                self.assertRegex(plugin_id, r"^kcm_moos(_[a-z]+)?$")
                self.assertTrue((directory / "ui/main.qml").is_file())
                own = {path.name for path in (directory / "ui").rglob("*.qml")}
                self.assertFalse(own & common, "a module file shadows a shared common/ file")
                expected = CORE.get(plugin_id) or CONTRACTED.get(plugin_id)
                self.assertIsNotNone(expected, f"{plugin_id} is not in the spec's module table")
                self.assertEqual(directory.name, expected[0])
                self.assertEqual(metadata.get("X-KDE-System-Settings-Parent-Category"), expected[1])
                self.assertEqual(metadata.get("X-KDE-Weight"), expected[2])
                plugin = metadata["KPlugin"]
                for key in ("Name", "Name[ar]", "Description", "Description[ar]", "Icon"):
                    self.assertTrue(str(plugin.get(key, "")).strip(), key)
                self.assertRegex(plugin["Description[ar]"], r"[\u0600-\u06FF]")
                self.assertEqual(plugin.get("FormFactors"), ["desktop"])
                icon = plugin["Icon"]
                self.assertTrue(any(ICONS.glob(f"*/apps/{icon}.*")), f"no {icon} in hicolor")
                for key in ("X-KDE-Keywords", "X-KDE-Keywords[ar]"):
                    words = [k for k in metadata.get(key, "").split(",") if k.strip()]
                    self.assertGreaterEqual(len(words), 3, key)
        overview = found["kcm_moos"][1]
        for word in ("about", "version"):
            self.assertIn(word, overview["X-KDE-Keywords"].split(","),
                          "a search for About or version must find MoOS's own page")
        for word in ("حول", "إصدار"):
            self.assertIn(word, overview["X-KDE-Keywords[ar]"].split(","))

    def test_the_moos_group_leads_the_sidebar(self) -> None:
        lines = CATEGORY.read_text(encoding="utf-8").splitlines()
        for line in ("Type=Service", "X-KDE-System-Settings-Category=moos",
                     "X-KDE-System-Settings-Parent-Category=", "X-KDE-Weight=5",
                     "Icon=moos-control-center", "Name=MoOS", "Name[ar]=MoOS"):
            self.assertIn(line, lines)

    def test_both_images_build_install_and_gate_the_family(self) -> None:
        for image in (ROOT / "Containerfile", ROOT / "Containerfile.arm"):
            text = image.read_text(encoding="utf-8")
            with self.subTest(image=image.name):
                self.assertIn("COPY moos-settings-kcm/ /src/moos-settings-kcm/", text)
                self.assertIn("cmake -S /src/moos-settings-kcm", text)
                self.assertIn("COPY --from=qmlshell-build /out/kcm/usr/ /usr/", text)
        for build in (ROOT / "build_files/build.sh", ROOT / "build_files/build-arm.sh"):
            with self.subTest(build=build.name):
                self.assertIn("bash /ctx/verify_settings_modules.sh || exit 1",
                              code(build.read_text(encoding="utf-8"), "#"))
        gate = code(GATE.read_text(encoding="utf-8"), "#")
        self.assertTrue(os.access(GATE, os.X_OK))
        for contract in (
            "list=/usr/share/moos/settings-modules.list",
            "for core in kcm_moos kcm_moos_update kcm_moos_whatsnew kcm_moos_remote kcm_moos_recovery; do",
            '[ -s "$kcm_dir/$module.so" ]',
            "X-KDE-System-Settings-Category=moos",
            "for duplicate in kcm_updates kcm_about-distro; do",
            'find "$plugins/plasma/kcms" -name "$duplicate.so" -delete',
            'rm -f "/usr/share/applications/$duplicate.desktop"',
            "session=(env -u DISPLAY -u WAYLAND_DISPLAY",
            'HOME="$home" XDG_RUNTIME_DIR="$runtime"',
            "QT_QPA_PLATFORM=offscreen",
            # A private bus where the image has dbus-run-session (x86); where it has not
            # (ARM: dbus-broker only), the SAME load on an address that leads nowhere.
            'dbus-run-session -- "${session[@]}"',
            '"${session[@]}" DBUS_SESSION_BUS_ADDRESS="unix:path=$runtime/absent-bus"',
            'kcmshell6 "$module"',
            '[ "$rc" -ne 124 ]',
            "MOOS_KCM_READY $module",
        ):
            self.assertIn(contract, gate)
        self.assertEqual(gate.count('timeout --kill-after=5s 10 kcmshell6 "$module"'), 2,
                         "both bus modes must run the same load")
        self.assertNotIn("exit 0", gate, "the load test is never skipped")
        self.assertNotIn("dbus-run-session is required", gate,
                         "the ARM image has no dbus-run-session; the gate loads there without a bus")
        for error in ("Error loading QML", "is not a type", "ReferenceError", "TypeError",
                      "module .* is not installed"):
            self.assertIn(error, gate, f"the load gate no longer fails on '{error}'")
        backend = BACKEND.read_text(encoding="utf-8")
        self.assertIn('"MOOS_KCM_READY %s"', backend)
        self.assertIn("&KQuickConfigModule::mainUiReady", backend,
                      "the ready marker must come from a page that really loaded")


class TheBackend(unittest.TestCase):
    def test_it_is_closed(self) -> None:
        backend = code(BACKEND.read_text(encoding="utf-8"))
        self.assertIn('StatusHelper = "/usr/libexec/moos-settings-status"', backend)
        self.assertIn('ThemeTool = "/usr/bin/moos-theme"', backend)
        self.assertIn("setButtons(NoAdditionalButton)", backend)
        self.assertIn("QFileSystemWatcher", HEADER.read_text(encoding="utf-8"))
        for forbidden in ("/bin/sh", "startDetached", "QProcess::execute", "MOOS_SETTINGS_SECTION",
                          "moos-settings/request", "setInterval(10000)", "system(", "popen("):
            self.assertNotIn(forbidden, backend)
        # Every timer is a single shot: the helper runs because something happened, not blindly.
        self.assertEqual(backend.count("setInterval("), backend.count("setSingleShot(true)"))

    def test_the_fixed_verbs_are_exactly_the_contract(self) -> None:
        self.assertEqual(fixed_verbs(), FIXED_VERBS)
        backend = BACKEND.read_text(encoding="utf-8")
        self.assertIn(r'"^org\\.moos\\.ui2[a-z.]*$"', backend)
        self.assertIn(r'"^[A-Za-z0-9_.~%-]{1,4096}$"', backend)
        for word in ("still", "gentle", "alive", "clear", "balanced", "solid"):
            self.assertIn(f'QLatin1String("{word}")', backend)
        theme = THEME_TOOL.read_text(encoding="utf-8")
        for first, _kind in FIXED_VERBS.values():
            if first:
                self.assertRegex(theme, rf"(?m)^    {re.escape(first)}\)", f"moos-theme has no {first} verb")
        readme = (KCM / "README.md").read_text(encoding="utf-8")
        for verb in FIXED_VERBS:
            self.assertIn(f"| `{verb}` |", readme, f"the README does not document {verb}")

    def test_env_reads_only_the_three_ports(self) -> None:
        body = BACKEND.read_text(encoding="utf-8").split("QString MoOSSettingsModule::env(", 1)[1]
        body = body.split("\n}\n", 1)[0]
        self.assertEqual(sorted(set(re.findall(r'QLatin1String\("([A-Z_]+)"\)', body))),
                         ["MOAI_AGENT_PORT", "MOAI_CONTROL_PORT", "MOAI_GATEWAY_PORT"])
        self.assertIn('"^[0-9]{1,5}$"', body)

    def test_open_route_takes_only_a_plain_moos_route(self) -> None:
        source = BACKEND.read_text(encoding="utf-8")
        route = re.compile(re.search(r'route\(QStringLiteral\("(\^moos://[^"]+)"\)\)', source).group(1))
        for good in ("moos://settings/update", "moos://remote/fast-on", "moos://app/remote",
                     "moos://do/update-apps", "moos://settings/whats-new"):
            self.assertTrue(route.match(good), good)
        for bad in ("https://example.org", "file:///etc/passwd", "moos://", "moos://Settings/x",
                    "moos://settings/update x", "moos://settings//x", "moos://settings/x?y=1"):
            self.assertFalse(route.match(bad), bad)
        self.assertIn('url.contains(QLatin1String(".."))', source)
        self.assertIn("url.size() > 160", source)

    def test_the_status_contract_is_what_the_helper_publishes(self) -> None:
        fields, labels = status_shape()
        self.assertGreaterEqual(len(fields), 30, "the StatusShape table was not found")
        self.assertEqual(labels, ["editionLabel", "archLabel", "sessionLabel"])
        state = runpy.run_path(str(STATUS))["full_state"]()
        types = {"String": str, "Bool": bool, "Array": list, "Object": dict}
        for group, key, kind in fields:
            holder = state.get(group) if group else state
            with self.subTest(field=f"{group}.{key}" if group else key):
                self.assertIsInstance(holder, dict)
                self.assertIn(key, holder, "the helper does not publish a field the pages bind")
                value = holder[key]
                if kind == "Double":
                    self.assertTrue(isinstance(value, (int, float)) and not isinstance(value, bool))
                else:
                    self.assertIsInstance(value, types[kind])
        for label in labels:
            self.assertEqual(set(state[label]), {"ar", "en"})
            self.assertTrue(all(isinstance(text, str) for text in state[label].values()))
        self.assertTrue(all(isinstance(value, bool) for value in state["destinations"].values()))
        rules = BACKEND.read_text(encoding="utf-8") + HEADER.read_text(encoding="utf-8")
        for rule in ("schema.toDouble() != 1.0", 'QLatin1String("MoOS")', "MaximumStatusAge = 45",
                     'return fail("stale")', "age < -5 || age > MaximumStatusAge"):
            self.assertIn(rule, rules)


class TheLauncher(unittest.TestCase):
    def run_launcher(self, *arguments: str, contracted_installed: bool = True):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root)
            fake_bin = folder / "bin"
            fake_bin.mkdir()
            plugins = folder / "plugins"
            (plugins / "plasma/kcms/systemsettings").mkdir(parents=True)
            if contracted_installed:
                for plugin_id in CONTRACTED:
                    (plugins / f"plasma/kcms/systemsettings/{plugin_id}.so").touch()
            for name, body in (
                ("systemsettings", 'printf "systemsettings %s\\n" "$*" > "$XDG_RUNTIME_DIR/argv"'),
                ("moai", 'printf "moai %s\\n" "$*" > "$XDG_RUNTIME_DIR/argv"'),
                ("qtpaths6", f'[ "$*" = "--query QT_INSTALL_PLUGINS" ] && echo "{plugins}"'),
            ):
                tool = fake_bin / name
                tool.write_text("#!/bin/sh\n" + body + "\n", encoding="utf-8")
                tool.chmod(0o755)
            runtime = folder / "runtime"
            runtime.mkdir(mode=0o700)
            env = isolated_env(PATH=f"{fake_bin}:/usr/bin:/bin", XDG_RUNTIME_DIR=str(runtime),
                               HOME=str(folder / "home"))
            result = subprocess.run([str(LAUNCHER), *arguments], env=env, capture_output=True,
                                    text=True, timeout=10)
            argv_file = runtime / "argv"
            argv = argv_file.read_text(encoding="utf-8").strip() if argv_file.exists() else ""
            leftovers = sorted(p.name for p in runtime.iterdir() if p.name != "argv")
            return result, argv, leftovers

    def test_each_section_opens_its_module(self) -> None:
        result, argv, _ = self.run_launcher()
        self.assertEqual((result.returncode, argv), (0, "systemsettings kcm_moos"), result.stderr)
        for section, plugin_id in SECTIONS.items():
            with self.subTest(section=section):
                result, argv, leftovers = self.run_launcher(f"--section={section}")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(argv, f"systemsettings {plugin_id}")
                self.assertEqual(leftovers, [], "a deep link is a module id, never a request file")

    def test_a_module_that_is_not_installed_yet_opens_what_served_it_before(self) -> None:
        _, argv, _ = self.run_launcher("--section=assistant", contracted_installed=False)
        self.assertEqual(argv, "moai")
        for section in ("appearance", "themes", "wallpaper"):
            _, argv, _ = self.run_launcher(f"--section={section}", contracted_installed=False)
            self.assertEqual(argv, "systemsettings kcm_lookandfeel", section)

    def test_anything_else_is_refused(self) -> None:
        for argument in ("--section=bogus", "--section=", "--section=update;id", "update", "--help"):
            with self.subTest(argument=argument):
                result, argv, _ = self.run_launcher(argument)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(argv, "")

    def test_every_moos_module_it_names_exists_or_has_a_fallback(self) -> None:
        launcher = code(LAUNCHER.read_text(encoding="utf-8"), "#")
        self.assertNotIn("MOOS_SETTINGS_SECTION", launcher)
        self.assertNotIn("request", launcher)
        fallback = launcher.split('case "$module" in', 1)[1].split("esac\n\nexec", 1)[0]
        for plugin_id in set(re.findall(r"\bkcm_moos\w*", launcher)):
            with self.subTest(module=plugin_id):
                self.assertTrue(plugin_id in modules() or f"{plugin_id})" in fallback,
                                f"moos-settings opens {plugin_id}, which nothing builds")
        self.assertTrue(launcher.rstrip().endswith('exec systemsettings "$module"'))


class TheEntries(unittest.TestCase):
    @staticmethod
    def entry(path: Path) -> dict[str, str]:
        values: dict[str, str] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("[") and values:
                break
            if "=" in line and not line.startswith("#"):
                key, value = line.split("=", 1)
                values[key] = value
        return values

    def test_settings_entries_match_the_settings_window(self) -> None:
        settings = self.entry(DESKTOP)
        self.assertEqual(settings["Exec"], "moos-settings")
        self.assertEqual(settings["Icon"], "moos-control-center")
        self.assertEqual(settings["StartupWMClass"], "systemsettings",
                         "the System Settings window's app id is systemsettings (measured)")
        self.assertEqual(settings["NoDisplay"], "true", "one visible Settings entry, not two")
        actions = re.findall(r"(?m)^Exec=moos-settings --section=([a-z-]+)$",
                             DESKTOP.read_text(encoding="utf-8"))
        self.assertTrue(actions)
        for section in actions:
            self.assertIn(section, SECTIONS)
        for path, section in ((UPDATER_DESKTOP, "update"), (RECOVERY_DESKTOP, "recovery")):
            with self.subTest(deep_link=section):
                entry = self.entry(path)
                self.assertEqual(entry["Exec"], f"moos-settings --section={section}")
                self.assertEqual(entry["StartupWMClass"], "systemsettings")
                self.assertEqual(entry["NoDisplay"], "true")
        for size in ICON_SIZES:
            raster = ICONS / f"{size}x{size}/apps/moos-control-center.png"
            with self.subTest(size=size):
                self.assertTrue(raster.is_file(), raster)
                self.assertGreater(raster.stat().st_size, 256, raster)

    def test_the_remote_pin_and_its_window_are_one_icon(self) -> None:
        remote = self.entry(REMOTE_DESKTOP)
        self.assertEqual((remote["Exec"], remote["TryExec"]), ("mo-pc-remote", "mo-pc-remote"))
        self.assertEqual(remote["StartupWMClass"], "org.moos.remote")
        self.assertEqual(remote["NoDisplay"], "true")
        text = REMOTE_DESKTOP.read_text(encoding="utf-8")
        self.assertIn("Exec=/usr/bin/moos-fast-remote on", text)
        self.assertIn("Exec=/usr/bin/moos-fast-remote off", text)
        app = REMOTE_APP.read_text(encoding="utf-8")
        self.assertIn('application_id="org.moos.remote"', app)
        for stale in ("Meta+R", "MoPCRemote"):
            self.assertNotIn(stale, text + app, f"{stale} was never registered; it promises nothing")


class TheHelper(unittest.TestCase):
    def test_status_boundary_publishes_atomically_without_process_authority(self) -> None:
        source = STATUS.read_text(encoding="utf-8")
        self.assertIn('return base / "status.json"', source)
        self.assertIn("os.replace(temporary, path)", source)
        self.assertIn("os.chmod(temporary, 0o600)", source)
        self.assertIn("capture_output=True", source)
        self.assertNotIn("shell=True", source)
        self.assertNotIn("os.system", source)
        self.assertNotIn('add_argument("--output"', source)
        with tempfile.TemporaryDirectory() as runtime:
            result = subprocess.run([str(STATUS)], check=False, capture_output=True, text=True,
                                    timeout=30, env=isolated_env(XDG_RUNTIME_DIR=runtime))
            self.assertEqual(result.returncode, 0, result.stderr)
            output = Path(runtime) / "moos-settings/status.json"
            state = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual((state["schema"], state["product"]), (1, "MoOS"))
            for group in ("deployment", "network", "memory", "update", "remote", "apps"):
                self.assertIn(group, state)
            self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o600)
            self.assertNotRegex(state["kernelLabel"], r"fc\d|el\d|x86_64|aarch64")

    def test_network_distinguishes_portal_limited_offline_and_unknown(self) -> None:
        probe = runpy.run_path(str(STATUS))["network_state"]
        for raw, connected, full, known in (
            ("connected:full", True, True, True),
            ("connected:portal", True, False, True),
            ("connected (site only):limited", True, False, True),
            ("disconnected:none", False, False, True),
            ("", False, False, False),
        ):
            with self.subTest(raw=raw), patch.dict(
                    probe.__globals__, command=lambda args: raw if args[-1] == "general" else ""):
                state = probe()
                self.assertEqual((state["connected"], state["full"], state["known"]),
                                 (connected, full, known))

    def test_update_status_reads_only_a_fresh_backend_record(self) -> None:
        probe = runpy.run_path(str(STATUS))["update_state"]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "update-state.json"
            fresh = {"schema": 1, "updated": int(time.time()), "state": "available",
                     "event": "resolve", "latest_version": "44.2"}
            path.write_text(json.dumps(fresh), encoding="utf-8")
            self.assertEqual(probe(path), {"known": True, "state": "available", "event": "resolve",
                                           "updated": fresh["updated"], "latestVersion": "44.2"})
            for broken in ({**fresh, "schema": 2}, {**fresh, "updated": int(time.time()) - 901},
                           {**fresh, "updated": int(time.time()) + 60}, {**fresh, "state": "installed"}):
                path.write_text(json.dumps(broken), encoding="utf-8")
                self.assertFalse(probe(path)["known"])
            path.write_text("not json", encoding="utf-8")
            self.assertFalse(probe(path)["known"])

    def test_signature_requires_official_origin_and_known_deployment(self) -> None:
        probe = runpy.run_path(str(STATUS))["deployment_state"]
        for ref, signed in (
            ("ostree-image-signed:docker://ghcr.io/moalfarras-sys/moos-arm:latest", True),
            ("ostree-image-signed:docker://example.org/moos:latest", False),
            ("ostree-unverified-registry:ghcr.io/moalfarras-sys/moos-arm:latest", False),
        ):
            raw = json.dumps({"deployments": [{"booted": True, "container-image-reference": ref},
                                              {"staged": True}]})
            with self.subTest(ref=ref), patch.dict(probe.__globals__, command=lambda *a, **kw: raw):
                state = probe()
                self.assertTrue(state["known"])
                self.assertEqual(state["signed"], signed)
                self.assertEqual(state["rollback"], 0, "staged image is never a rollback")
                self.assertFalse(state["rollbackQueued"])
        for raw in ("", "null", '{"deployments":null}', '{"deployments":[null]}'):
            with patch.dict(probe.__globals__, command=lambda *a, **kw: raw):
                self.assertFalse(probe()["known"])

    def test_recovery_status_distinguishes_queued_rollback_from_staged_update(self) -> None:
        probe = runpy.run_path(str(STATUS))["deployment_state"]
        booted, saved = {"booted": True, "version": "44.3"}, {"version": "44.2"}
        staged = {"staged": True, "version": "44.4"}
        for deployments, queued, target in (
            ([booted, saved], False, "44.2"), ([staged, booted, saved], False, "44.2"),
            ([saved, booted], True, "44.2"), ([staged, saved, booted], True, "44.2"),
            ([booted], False, ""),
        ):
            raw = json.dumps({"deployments": deployments})
            with self.subTest(deployments=deployments), \
                    patch.dict(probe.__globals__, command=lambda *a, **kw: raw):
                state = probe()
                self.assertEqual((state["rollbackQueued"], state["rollbackTarget"]), (queued, target))

    def test_remote_state_reports_failure_and_fast_remote_from_its_journal(self) -> None:
        probe = runpy.run_path(str(STATUS))["remote_state"]

        def command(argv):
            return {"is-active": "failed", "is-enabled": "enabled", "is-failed": "failed"}.get(argv[2], "")
        with tempfile.TemporaryDirectory() as tmp, patch.dict(probe.__globals__, command=command), \
                patch.dict(os.environ, {"XDG_STATE_HOME": tmp}), \
                patch.object(shutil, "which", return_value="/usr/bin/mo-pc-remote"):
            self.assertEqual(probe(), {"available": True, "active": False, "enabled": True,
                                       "failed": True, "fast": False})
            (Path(tmp) / "moos").mkdir()
            (Path(tmp) / "moos/fast-remote.on").write_text("on\n", encoding="utf-8")
            self.assertTrue(probe()["fast"], "moos-fast-remote's journal file means Fast Remote is on")
        with patch.dict(probe.__globals__, command=command), patch.object(shutil, "which", return_value=None):
            self.assertFalse(probe()["fast"])

    def test_the_app_update_record_is_read_as_data(self) -> None:
        probe = runpy.run_path(str(STATUS))["apps_state"]
        now = int(time.time())
        unknown = {"known": False, "state": "", "updated": 0, "failures": []}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "app-updates.json"
            self.assertEqual(probe(path), unknown, "no record is not 'up to date'")
            good = {"schema": 1, "updated": now, "state": "failed",
                    "failures": [{"app": "org.example.App", "reason": "  the   server\nrefused  "},
                                 {"app": "not an id", "reason": "x"}, {"app": "org.example.Two"}, "junk"]}
            path.write_text(json.dumps(good), encoding="utf-8")
            self.assertEqual(probe(path), {"known": True, "state": "failed", "updated": now,
                                           "failures": [{"app": "org.example.App",
                                                         "reason": "the server refused"}]})
            for state in ("ok", "running"):
                path.write_text(json.dumps({**good, "state": state}), encoding="utf-8")
                self.assertEqual(probe(path)["state"], state)
            path.write_text(json.dumps({**good, "state": "running", "updated": now - 4 * 3600}),
                            encoding="utf-8")
            self.assertEqual(probe(path)["state"], "interrupted",
                             "a run that died must not say running forever")
            for broken in ({**good, "schema": 2}, {**good, "state": "done"}, {**good, "updated": now + 3600},
                           {**good, "updated": True}, {**good, "updated": 0}):
                path.write_text(json.dumps(broken), encoding="utf-8")
                self.assertEqual(probe(path), unknown, broken)
            many = [{"app": f"org.example.A{n}", "reason": "r" * 900} for n in range(40)]
            path.write_text(json.dumps({**good, "failures": many}), encoding="utf-8")
            state = probe(path)
            self.assertEqual(len(state["failures"]), 20)
            self.assertTrue(all(len(item["reason"]) == 200 for item in state["failures"]))
            path.write_bytes(b" " * 70000)
            self.assertEqual(probe(path), unknown, "an oversized record is refused unread")

    def test_destination_probe_matches_router_and_checks_modules(self) -> None:
        scope = runpy.run_path(str(STATUS))
        routes = {key: tuple(argv.split()) for key, argv in re.findall(
            r"^    settings/([a-z-]+)\)\s+gui ([^;]+?)\s*;;", ROUTER.read_text(encoding="utf-8"), re.M)}
        self.assertEqual(scope["DESTINATIONS"], routes)
        probe = scope["destinations_state"]
        token = next(k for k, argv in scope["DESTINATIONS"].items()
                     if argv[0] == "systemsettings" and len(argv) == 2)
        module = scope["DESTINATIONS"][token][1]
        with tempfile.TemporaryDirectory() as tmp:
            plugin = Path(tmp) / f"plasma/kcms/systemsettings_qwidgets/{module}.so"
            plugin.parent.mkdir(parents=True)
            plugin.touch()
            with patch.dict(probe.__globals__, command=lambda *a: tmp), \
                    patch.object(shutil, "which", return_value="/usr/bin/systemsettings"):
                self.assertTrue(probe()[token])
            with patch.object(shutil, "which", return_value=None):
                self.assertFalse(any(probe().values()))

    def test_publish_stamps_completed_snapshot(self) -> None:
        publish = runpy.run_path(str(STATUS))["publish"]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "status.json"
            publish(path, {"generatedAt": 1})
            self.assertLess(abs(json.loads(path.read_text())["generatedAt"] - time.time()), 2)


class ThePages(unittest.TestCase):
    def test_every_page_is_a_native_scrolling_bilingual_mirrored_module(self) -> None:
        for plugin_id, (directory, _metadata) in modules().items():
            qml = code((directory / "ui/main.qml").read_text(encoding="utf-8"))
            with self.subTest(module=plugin_id):
                self.assertRegex(qml, r"(?m)^KCM\.SimpleKCM \{", "a page must scroll: KCM.SimpleKCM")
                self.assertNotIn("ScrollViewKCM", qml)
                for contract in ("import org.moos.ui as MoUI",
                                 "import org.kde.kirigamiaddons.formcard as FormCard",
                                 "readonly property bool rtl: MoUI.Locale.rtl",
                                 "function t(ar, en) { return rtl ? ar : en }",
                                 "LayoutMirroring.enabled: rtl",
                                 "LayoutMirroring.childrenInherit: true"):
                    self.assertIn(contract, qml)
                if plugin_id in CORE:
                    for contract in ("kcm.ensureFresh()", "MoosStatusNotice", "backend: kcm"):
                        self.assertIn(contract, qml)
        for path in kcm_qml():
            qml = code(path.read_text(encoding="utf-8"))
            with self.subTest(file=path.relative_to(KCM).as_posix()):
                for forbidden in ("Qt.application.layoutDirection", "Qt.locale().textDirection",
                                  "Qt.openUrlExternally", "Animation.Infinite", "font.family:",
                                  "disabledTextColor", "horizontalAlignment: root.rtl ?",
                                  "horizontalAlignment: rtl ?"):
                    self.assertNotIn(forbidden, qml)
                # Motion is allowed only behind the owner's animation setting (MoUI's own
                # components already gate theirs), and nothing runs forever.
                if re.search(r"\b(?:Number|Color|Property|Sequential|Parallel|Rotation|Opacity)Animator?\b"
                             r"|\bBehavior on\b", qml):
                    self.assertIn("Kirigami.Units.longDuration > 1", qml,
                                  "an animation that ignores the owner's reduced-motion setting")

    def test_every_button_goes_through_the_backend_and_a_failure_is_shown(self) -> None:
        for path in kcm_qml():
            qml = code(path.read_text(encoding="utf-8"))
            calls = qml.count("kcm.openRoute(")
            handled = len(re.findall(r"(?:routeError = |var opened = )kcm\.openRoute\(", qml))
            with self.subTest(file=path.relative_to(KCM).as_posix()):
                self.assertEqual(calls, handled,
                                 "an openRoute() result is ignored: a dead button would be silent")
                if calls:
                    self.assertIn("MoosRouteNotice", qml)
                    self.assertIn("message: root.routeError", qml)
                self.assertNotRegex(qml, r'"moos://[a-z/-]*"\s*\+', "a route is a literal, never built")
        for name in ("overview", "whatsnew"):
            self.assertIn("ownPages.indexOf(token) >= 0 || "
                          "(ready && (kcm.status.destinations || {})[token] === true)", page(name))

    def test_the_update_page_shows_every_state_its_owners_publish(self) -> None:
        qml = code(page("update"))
        for state in ("busy", "replace-staged", "blocked-downgrade", "current", "available"):
            self.assertIn(f'updateRecord.state === "{state}"', qml)
        self.assertIn("deployment.staged", qml)
        states = runpy.run_path(str(STATUS))["APP_UPDATE_STATES"]
        for state in sorted(states | {"interrupted"}):
            self.assertIn(f'apps.state === "{state}"', qml)
        self.assertIn("model: root.failures", qml)
        for route in ("moos://app/updater", "moos://do/update-apps", "moos://do/update-firmware"):
            self.assertIn(f'root.open("{route}")', qml)

    def test_the_recovery_page_tells_a_queued_rollback_from_a_saved_image(self) -> None:
        qml = code(page("recovery"))
        for field in ("deployment.rollbackQueued", "deployment.rollbackTarget",
                      "deployment.previousVersion", "deployment.rollback"):
            self.assertIn(field, qml)
        self.assertIn('root.open("moos://app/recovery")', qml)

    def test_the_remote_page_switches_what_it_measured(self) -> None:
        qml = code(page("remote"))
        for route in ("moos://remote/start", "moos://remote/stop", "moos://remote/restart"):
            self.assertIn(route, qml)
        self.assertIn('root.open("moos://app/remote")', qml)
        self.assertIn("on: root.installed && root.remote.enabled === true", qml)
        self.assertNotRegex(qml, r"(?m)^\s*checked:",
                            "a page never sets a switch; MoosSwitchRow shows the measurement")
        switch = (COMMON / "MoosSwitchRow.qml").read_text(encoding="utf-8")
        self.assertIn("checked: row.on", switch)
        self.assertIn("checked = Qt.binding(function() { return row.on })", switch)

    @unittest.skipUnless(NODE, "Node required to execute the pages' JavaScript")
    def test_the_page_logic_says_what_the_records_say(self) -> None:
        overview, update, recovery, remote = page("overview"), page("update"), page("recovery"), page("remote")
        own = re.search(r"readonly property var ownPages: (\[[^\]]*\])", overview).group(1)
        script = "const assert = require('node:assert/strict');\nlet rtl = false;\n"
        script += "function t(ar, en) { return rtl ? ar : en }\n"
        script += "function text(value) { return typeof value === 'string' ? value : '' }\n"
        script += "function isolated(value) { return '[' + text(value) + ']' }\n"
        script += "function whenLabel(epoch) { return epoch > 0 ? 'WHEN' : '' }\n"
        script += "let unknownLabel = 'Unknown', ready = true, known = true, installed = true;\n"
        script += "let deployment = {}, updateRecord = {}, apps = {}, failures = [], remote = {};\n"
        script += f"const ownPages = {own};\nlet kcm = {{status: {{destinations: {{display: true}}}}}};\n"
        script += qml_function(overview, "routeAvailable") + "\n"
        script += qml_function(update, "systemSummary") + "\n" + qml_function(update, "appsSummary") + "\n"
        script += qml_function(recovery, "recoverySummary") + "\n" + qml_function(remote, "remoteSummary") + "\n"
        script += r"""
// Routes: MoOS's own pages never wait for the feed; the rest need a measured destination.
ready = false;
assert.equal(routeAvailable('moos://settings/about'), true);
assert.equal(routeAvailable('moos://settings/display'), false);
ready = true;
assert.equal(routeAvailable('moos://settings/display'), true);
assert.equal(routeAvailable('moos://settings/printers'), false);
assert.equal(routeAvailable('https://example.org'), false);
// System row.
ready = false; assert.equal(systemSummary().title, 'Update status unknown'); ready = true;
deployment = {version: '44.1', staged: false, stagedVersion: ''};
for (const [state, title] of [['busy', 'An update is being prepared'], ['current', 'MoOS is up to date'],
                              ['available', 'A signed update is available'],
                              ['blocked-downgrade', 'An older release was blocked'],
                              ['replace-staged', 'A corrective release replaces the staged update']]) {
    updateRecord = {known: true, state, latestVersion: '44.2'};
    assert.equal(systemSummary().title, title, state);
}
updateRecord = {known: false}; assert.equal(systemSummary().title, 'No recent check');
deployment = {version: '44.1', staged: true, stagedVersion: '44.2'};
assert.equal(systemSummary().title, 'A signed update is ready');
assert.ok(systemSummary().detail.includes('[44.2]'));
// Applications row: a missing record is never "up to date".
apps = {known: false}; assert.equal(appsSummary().title, 'No automatic update recorded yet');
apps = {known: true, state: 'ok', updated: 5}; assert.equal(appsSummary().title, 'Applications are up to date');
apps = {known: true, state: 'running', updated: 5}; assert.equal(appsSummary().title, 'Applications are updating now');
apps = {known: true, state: 'interrupted', updated: 5}; assert.equal(appsSummary().tone, 'warning');
apps = {known: true, state: 'failed', updated: 5}; failures = [{app: 'org.x.Y', reason: 'r'}];
assert.equal(appsSummary().title, 'Some applications could not be updated');
// Recovery: a queued rollback is not a saved image.
deployment = {known: true, rollbackQueued: true, rollbackTarget: '44.0', rollback: 1};
assert.equal(recoverySummary().title, 'A rollback is queued for the next restart');
assert.ok(recoverySummary().detail.includes('[44.0]'));
deployment = {known: true, rollbackQueued: false, rollbackTarget: '44.0', rollback: 1};
assert.equal(recoverySummary().title, 'A previous version is saved');
deployment = {known: true, rollbackQueued: false, rollbackTarget: '', rollback: 0};
assert.equal(recoverySummary().title, 'No previous version saved yet');
known = false; assert.equal(recoverySummary().title, 'Recovery status unknown');
// Remote: a failed service is not merely off.
remote = {available: true, failed: true}; assert.equal(remoteSummary().tone, 'negative');
remote = {available: true, active: true, enabled: true}; assert.equal(remoteSummary().tone, 'positive');
remote = {available: true, enabled: true}; assert.equal(remoteSummary().title, 'Starts with your session');
remote = {available: true}; assert.equal(remoteSummary().title, 'Remote control is off');
remote = {available: false}; assert.equal(remoteSummary().title, 'Not installed on this device');
rtl = true; remote = {available: true}; assert.ok(/[\u0600-\u06FF]/.test(remoteSummary().title));
"""
        result = subprocess.run([NODE, "-e", script], capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])

    def test_moos_owned_text_names_no_other_system(self) -> None:
        identity = runpy.run_path(str(ROOT / "tests/test_user_visible_identity.py"))
        errors = []
        for path in kcm_qml():
            text = path.read_text(encoding="utf-8")
            for number, literal in identity["qml_literals"](text):
                word = identity["hit"](literal) if identity["is_prose"](literal) else None
                if word:
                    errors.append(f"{path.relative_to(KCM)}:{number}: {literal[:80]}")
            for number, line in enumerate(text.splitlines(), 1):
                if re.search(r"\.kernel\b(?!Label)", line.split("//", 1)[0]):
                    errors.append(f"{path.relative_to(KCM)}:{number}: binds the raw kernel release")
        for plugin_id, (_directory, metadata) in modules().items():
            texts = [v for k, v in metadata["KPlugin"].items() if k.startswith(("Name", "Description"))]
            texts += [v for k, v in metadata.items() if k.startswith("X-KDE-Keywords")]
            errors += [f"{plugin_id}: {text}" for text in texts if identity["hit"](text)]
        errors += [f"category: {line}" for line in CATEGORY.read_text(encoding="utf-8").splitlines()
                   if line.startswith("Name") and identity["hit"](line)]
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
