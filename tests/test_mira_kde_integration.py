#!/usr/bin/env python3
"""Mira inside KDE Plasma: the launcher, her login unit, Dolphin's menus and the shell's words.

MoOS and Mira must read as one system. These gates hold the image side of that:

- /usr/bin/mira passes Plasma's and Dolphin's arguments through unchanged, picks Qt's software
  scene graph on a machine with no real GPU (the rule /usr/bin/moai measured) and tells Mira to
  hold still there (MIRA_STILL=1: her shaders cannot run on it), and on an edition without her
  tree opens the assistant that IS installed instead of failing;
- mira.service starts her in the background at sign-in only for a person who turned it on: it is
  never enabled by an image build;
- every Dolphin entry runs an argument the launcher documents and Mira parses
  (mira/kde_integration.py), on local files only, named in both languages; Mira's behavioural
  suite for those arguments (mira/test_kde_integration.py) runs in the image build;
- the staged tree the image receives carries her pages and kde_integration.py;
- the shell names the assistant Mira: the Island's job chip and search hand-off, the launcher's
  card and the Welcome app. "Mo AI" stays only where it names the engine.

The launcher runs against a stand-in app and a fake /sys/class/drm; nothing starts a real
window, touches the session or reaches the owner's desktop.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "system_files/usr/bin/mira"
UNIT = ROOT / "system_files/usr/lib/systemd/user/mira.service"
TRANSIENT_GUARD = (ROOT / "system_files/usr/lib/systemd/user/"
                   "app-org.moos.moai@.service.d/50-moos-memory-guard.conf")
MENUS = ROOT / "system_files/usr/share/kio/servicemenus"
KDE_MODULE = ROOT / "mira/kde_integration.py"
ISLAND = ROOT / "system_files/usr/share/plasma/plasmoids/org.moos.island/contents/ui"
STAGE = ROOT / "mira/packaging/stage.sh"
LAUNCHER_VIEW = ROOT / "system_files/usr/share/plasma/plasmoids/org.moos.brand/contents/ui/LauncherView.qml"
WELCOME = ROOT / "system_files/usr/share/moos/apps/welcome/main.qml"

FAKE_APP = """import json, os, sys
keys = ('QT_QUICK_BACKEND', 'MIRA_STILL', 'QT_QUICK_CONTROLS_STYLE', 'PYTHONPATH')
print(json.dumps({'argv': sys.argv[1:], 'env': {k: os.environ.get(k) for k in keys},
                  'no_user_site': sys.flags.no_user_site}))
"""
FAKE_CLASSIC = """#!/bin/sh
printf '%s\\n' "MOAI_CLASSIC=${MOAI_CLASSIC:-}" "$@"
"""


def code_lines(text):
    """QML/JS without whole-line comments (words a person never reads)."""
    return "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("//"))


class Launcher(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="mira-launcher-test-")
        base = Path(self.tmp.name)
        self.app = base / "app"
        self.app.mkdir()
        (self.app / "app.py").write_text(FAKE_APP, encoding="utf-8")
        self.drm = base / "drm"
        self.drm.mkdir()
        self.home = base / "home"
        self.home.mkdir()
        self.classic = base / "moai"
        self.classic.write_text(FAKE_CLASSIC, encoding="utf-8")
        self.classic.chmod(0o755)

    def tearDown(self):
        self.tmp.cleanup()

    def card(self, name, driver):
        device = self.drm / name / "device"
        device.mkdir(parents=True)
        (device / "uevent").write_text(f"DRIVER={driver}\nPCI_ID=1234:5678\n" if driver else "PCI_ID=1\n",
                                       encoding="utf-8")

    def launch(self, *args, app=None, **env):
        clean = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(self.home),
                 "XDG_CACHE_HOME": str(self.home / ".cache"),
                 "MIRA_APP": str(app or self.app), "MIRA_SITE": "/opt/mira-site",
                 "MIRA_PYTHON": sys.executable, "MIRA_DRM_ROOT": str(self.drm),
                 "MIRA_CLASSIC_LAUNCHER": str(self.classic)}
        clean.update(env)
        done = subprocess.run(["bash", str(LAUNCHER), *args], env=clean, capture_output=True,
                              text=True, timeout=30)
        return done

    def run_app(self, *args, **env):
        done = self.launch(*args, **env)
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout.strip().splitlines()[-1])

    def test_arguments_reach_the_app_unchanged(self):
        args = ["--background", "--ask-about", "/home/a b/x.pdf", "/home/c.txt", "--add-project", "/home/p",
                "--panel", "system", "--ask", "مرحبا «ميرا»"]
        self.card("card0", "nvidia")
        result = self.run_app(*args)
        self.assertEqual(result["argv"], args)
        self.assertTrue(result["no_user_site"], "a person's ~/.local packages must stay out (-s)")
        self.assertEqual(result["env"]["QT_QUICK_CONTROLS_STYLE"], "Basic")
        self.assertTrue(result["env"]["PYTHONPATH"].startswith("/opt/mira-site"))

    def test_a_real_gpu_keeps_the_gpu_scene_graph(self):
        for driver in ("nvidia", "amdgpu", "i915", "xe", "virtio_gpu", "some_future_driver"):
            with self.subTest(driver=driver):
                for child in self.drm.iterdir():
                    subprocess.run(["rm", "-rf", str(child)], check=True)
                self.card("card0", "simpledrm")
                self.card("card1", driver)
                env = self.run_app()["env"]
                self.assertIsNone(env["QT_QUICK_BACKEND"])
                self.assertIsNone(env["MIRA_STILL"])

    def test_no_real_gpu_means_software_and_still(self):
        for driver in ("bochs-drm", "qxl", "vmwgfx", "simpledrm", "hyperv_drm", "ast", "faux_driver",
                       "vgem", "vkms", "virtio-pci", ""):
            with self.subTest(driver=driver or "no driver line"):
                for child in self.drm.iterdir():
                    subprocess.run(["rm", "-rf", str(child)], check=True)
                self.card("card0", driver)
                env = self.run_app()["env"]
                self.assertEqual(env["QT_QUICK_BACKEND"], "software")
                self.assertEqual(env["MIRA_STILL"], "1")

    def test_no_drm_at_all_means_software_and_still(self):
        env = self.run_app()["env"]
        self.assertEqual((env["QT_QUICK_BACKEND"], env["MIRA_STILL"]), ("software", "1"))

    def test_a_two_digit_card_is_seen(self):
        self.card("card0", "simpledrm")
        self.card("card12", "amdgpu")
        self.assertIsNone(self.run_app()["env"]["MIRA_STILL"])

    def test_a_chosen_backend_is_respected(self):
        self.card("card0", "bochs-drm")
        env = self.run_app(QT_QUICK_BACKEND="rhi")["env"]
        self.assertEqual(env["QT_QUICK_BACKEND"], "rhi")
        self.assertIsNone(env["MIRA_STILL"])
        self.card("card1", "nvidia")
        env = self.run_app(QT_QUICK_BACKEND="software")["env"]
        self.assertEqual(env["MIRA_STILL"], "1", "her shaders cannot run on the software backend")

    def test_the_launch_is_logged_where_moos_inspect_reads(self):
        self.run_app()
        log = (self.home / ".cache/moai.log").read_text(encoding="utf-8")
        self.assertRegex(log, r"=== mira launch \d{4}-\d\d-\d\dT[\d:]+Z \(software scene graph, still\) ===")

    # An edition without her tree (no app.py): never a dead end.
    def test_without_mira_the_login_start_has_nothing_to_start(self):
        done = self.launch("--background", app=self.home / "absent")
        self.assertEqual((done.returncode, done.stdout), (0, ""))

    def test_without_mira_dolphin_opens_the_installed_assistant(self):
        done = self.launch("--add-project", "/home/p", app=self.home / "absent")
        self.assertEqual(done.stdout.splitlines(), ["MOAI_CLASSIC=1", "--workspace", "projects"])
        done = self.launch("--ask-about", "/home/a.txt", "/home/b.txt", "--panel", "chat", app=self.home / "absent")
        self.assertEqual(done.stdout.splitlines(), ["MOAI_CLASSIC=1", "--panel", "chat"],
                         "file paths are never handed to an assistant that would send them")
        done = self.launch("--panel", "device", app=self.home / "absent")
        self.assertEqual(done.stdout.splitlines(), ["MOAI_CLASSIC=1", "--panel", "device"])

    def test_without_mira_a_value_is_never_read_as_an_option(self):
        for words in ("--background", "--add-project=/home/p", "--ask-about=/home/a/.ssh/id_ed25519"):
            with self.subTest(words=words):
                done = self.launch("--panel", "chat", "--ask", words, app=self.home / "absent")
                self.assertEqual(done.stdout.splitlines(), ["MOAI_CLASSIC=1", "--panel", "chat", "--ask", words])
        done = self.launch("--add-project", "--background", app=self.home / "absent")
        self.assertEqual((done.returncode, done.stdout), (0, ""), "a folder-less --add-project leaves --background")

    def test_without_any_assistant_it_says_so(self):
        done = self.launch(app=self.home / "absent", MIRA_CLASSIC_LAUNCHER=str(self.home / "none"))
        self.assertEqual(done.returncode, 1)
        self.assertIn("ميرا غير مثبّتة", done.stderr)


class LoginUnit(unittest.TestCase):
    def setUp(self):
        self.unit = UNIT.read_text(encoding="utf-8")

    def keys(self, section):
        body = self.unit.split(f"[{section}]", 1)[1].split("\n[", 1)[0]
        pairs = [l.split("=", 1) for l in body.splitlines() if "=" in l and not l.lstrip().startswith("#")]
        out = {}
        for key, value in pairs:
            out.setdefault(key.strip(), []).append(value.strip())
        return out

    def test_it_starts_her_in_the_background_with_the_session(self):
        unit, service, install = self.keys("Unit"), self.keys("Service"), self.keys("Install")
        self.assertEqual(service["ExecStart"], ["/usr/bin/mira --background"])
        self.assertEqual(unit["PartOf"], ["graphical-session.target"])
        self.assertIn("graphical-session.target", unit["After"][0].split())
        self.assertIn("plasma-plasmashell.service", unit["After"][0].split(), "a tray needs the shell")
        self.assertEqual(service["Restart"], ["on-failure"], "quitting from the tray must stay quit")
        self.assertEqual(install["WantedBy"], ["graphical-session.target"])

    def test_it_never_runs_where_it_cannot(self):
        unit = self.keys("Unit")
        self.assertIn("!@system", unit["ConditionUser"])
        self.assertIn("/usr/lib/mira/app/app.py", unit["ConditionPathExists"])

    def test_no_image_enables_it_for_everyone(self):
        for script in ("build_files/build.sh", "build_files/build-arm.sh"):
            text = (ROOT / script).read_text(encoding="utf-8")
            for match in re.finditer(r"systemctl --global enable((?:[^\n\\]|\\\n)*)", text):
                self.assertNotIn("mira.service", match.group(1),
                                 f"{script} enables Mira's login start for every account; it is a "
                                 "person's own switch in her Settings")

    def test_the_switch_that_turns_it_on_names_this_unit(self):
        module = KDE_MODULE.read_text(encoding="utf-8")
        self.assertIn("UNIT = 'mira.service'", module)
        self.assertIn("['systemctl', '--user', 'enable' if enabled else 'disable', UNIT]", module)

    def test_both_launch_paths_contain_a_runaway_without_starving_healthy_mira(self):
        service = self.keys("Service")
        for key, value in (("MemoryAccounting", "yes"), ("MemoryHigh", "1G"),
                           ("MemoryMax", "1536M"), ("MemorySwapMax", "512M"),
                           ("OOMPolicy", "stop")):
            self.assertEqual(service[key], [value])
        guard = TRANSIENT_GUARD.read_text(encoding="utf-8")
        self.assertTrue(TRANSIENT_GUARD.parent.name.startswith("app-org.moos.moai@"))
        for line in ("MemoryAccounting=yes", "MemoryHigh=1G", "MemoryMax=1536M",
                     "MemorySwapMax=512M", "OOMPolicy=stop"):
            self.assertIn(line, guard)


class DolphinMenus(unittest.TestCase):
    def menu(self, name):
        text = (MENUS / name).read_text(encoding="utf-8")
        groups, current = {}, None
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("["):
                current = line.strip("[]")
                groups[current] = {}
            elif current and "=" in line and not line.startswith("#"):
                key, value = line.split("=", 1)
                groups[current][key] = value
        return groups

    def test_ask_about_files(self):
        menu = self.menu("mira-ask.desktop")
        entry, action = menu["Desktop Entry"], menu["Desktop Action miraAsk"]
        self.assertEqual((entry["Type"], entry["Actions"]), ("Service", "miraAsk"))
        self.assertEqual(entry["MimeType"], "all/allfiles;", "files, not folders (folders are projects)")
        self.assertEqual(entry["X-KDE-Protocols"], "file", "Mira reads local paths only")
        self.assertEqual(action["Exec"], "mira --ask-about %F")

    def test_add_a_folder_as_a_project(self):
        menu = self.menu("mira-project.desktop")
        entry, action = menu["Desktop Entry"], menu["Desktop Action miraProject"]
        self.assertEqual(entry["MimeType"], "inode/directory;")
        self.assertEqual(entry["X-KDE-Protocols"], "file")
        self.assertEqual(entry["X-KDE-RequiredNumberOfUrls"], "1")
        self.assertEqual(action["Exec"], "mira --add-project %f")

    def test_every_entry_is_named_in_both_languages_with_her_icon(self):
        icons = ROOT / "system_files/usr/share/icons/hicolor/scalable/apps"
        for name in ("mira-ask.desktop", "mira-project.desktop"):
            with self.subTest(menu=name):
                menu = self.menu(name)
                actions = [g for g in menu if g.startswith("Desktop Action ")]
                self.assertEqual(len(actions), 1)
                action = menu[actions[0]]
                self.assertIn("Mira", action["Name"])
                self.assertIn("ميرا", action["Name[ar]"])
                self.assertNotIn("Mo AI", " ".join(action.values()))
                # Not a key of a [Desktop Action] group (desktop-file-validate: "keys extending the
                # format should start with X-"), and KIO ignores it there: a guard that guards nothing.
                self.assertNotIn("TryExec", action)
                self.assertTrue((icons / f"{action['Icon']}.svg").is_file(), action["Icon"])

    def test_every_argument_a_menu_runs_is_one_the_launcher_and_mira_know(self):
        launcher = LAUNCHER.read_text(encoding="utf-8")
        module = KDE_MODULE.read_text(encoding="utf-8")
        for path in sorted(MENUS.glob("mira-*.desktop")):
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.startswith("Exec="):
                    continue
                words = line.split("=", 1)[1].split()
                self.assertEqual(words[0], "mira", path.name)
                for flag in (w for w in words[1:] if w.startswith("--")):
                    self.assertIn(f"#   mira {flag}", launcher, f"{path.name}: the launcher does not document {flag}")
                    self.assertIn(f"'{flag}'", module, f"{path.name}: Mira does not parse {flag}")

    def test_the_behaviour_behind_the_menus_is_proven_in_the_image_build(self):
        # The grep above only proves the flag's name is written down. mira/test_kde_integration.py
        # proves app.py parses it, the controller routes it and a web page's words cannot fake it;
        # it must run where a failure stops the image.
        for containerfile in ("Containerfile", "Containerfile.arm"):
            text = (ROOT / containerfile).read_text(encoding="utf-8")
            suites = re.search(r"python3 -s -m unittest ((?:[^\n\\]|\\\n)*)", text)
            if suites is None or '"$module"' in suites.group(1):
                suites = re.search(
                    r"for module in((?:\s+\\?\s*test_\w+)+);\s*do\s*\\?\s*"
                    r'(?:if )?python3(?: -X faulthandler)? -s -m unittest(?: -v)? "\$module"',
                    text,
                )
            self.assertIsNotNone(suites, f"{containerfile}: Mira's suites are not run")
            if 'if python3' in suites.group(0):
                tail = text[suites.end():].split('done', 1)[0]
                self.assertIn('status=$?', tail)
                self.assertIn('exit "$status"', tail)
            self.assertIn("test_kde_integration", suites.group(1).split(),
                          f"{containerfile}: the Dolphin/login/D-Bus suite never runs in the build")


class LoginStartMigration(unittest.TestCase):
    """moos-ui-migrate moves a development login start (~/.local/bin/mira) to the image's launcher
    once the image carries Mira. The entry Mira's Settings writes names the launcher in TryExec and
    Exec with `--background`: both lines move and the argument stays, or systemd's autostart
    generator skips the entry (its TryExec file is gone) and she silently stops starting."""

    def migrate(self, body):
        text = (ROOT / "system_files/usr/bin/moos-ui-migrate").read_text(encoding="utf-8")
        start = text.index("if [ -f /usr/lib/mira/app/app.py ]; then")
        end = text.index("\nfi\n", start) + 4
        with tempfile.TemporaryDirectory(prefix="mira-migrate-test-") as tmp:
            home = Path(tmp) / "home"
            (home / ".config/autostart").mkdir(parents=True)
            entry = home / ".config/autostart/mira.desktop"
            entry.write_text(body.replace("@HOME@", str(home)), encoding="utf-8")
            marker = Path(tmp) / "app.py"
            marker.write_text("", encoding="utf-8")
            block = text[start:end].replace("/usr/lib/mira/app/app.py", str(marker))
            script = f'legacy_bin="$HOME/.local/bin/moai"\nlegacy_desktop="$HOME/.local/share/applications/x"\n{block}'
            done = subprocess.run(["bash", "-c", script], env={"HOME": str(home), "PATH": os.environ.get("PATH", "/usr/bin")},
                                  capture_output=True, text=True, timeout=30)
            self.assertEqual(done.returncode, 0, done.stderr)
            return entry.read_text(encoding="utf-8")

    def test_the_settings_entry_keeps_background_and_moves_try_exec(self):
        after = self.migrate("[Desktop Entry]\nType=Application\nTryExec=@HOME@/.local/bin/mira\n"
                             "Exec=@HOME@/.local/bin/mira --background\n")
        self.assertIn("\nTryExec=/usr/bin/mira\n", after)
        self.assertIn("\nExec=/usr/bin/mira --background\n", after)

    def test_the_older_window_entry_still_moves(self):
        after = self.migrate("[Desktop Entry]\nType=Application\nExec=@HOME@/.local/bin/mira\n")
        self.assertIn("\nExec=/usr/bin/mira\n", after)

    def test_another_program_s_entry_is_left_alone(self):
        body = "[Desktop Entry]\nType=Application\nExec=@HOME@/.local/bin/miracle --x\n"
        self.assertNotIn("/usr/bin/mira", self.migrate(body))


class StagedTree(unittest.TestCase):
    """The tree the image receives (mira/packaging/stage.sh), not the source tree: it once shipped
    without pages/, so every destination of her window was empty and kde_integration never loaded,
    with every suite green."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="mira-stage-test-")
        cls.out = Path(cls.tmp.name) / "app"
        cls.done = subprocess.run(["sh", str(STAGE), str(ROOT / "mira"), str(cls.out)],
                                  capture_output=True, text=True, timeout=120)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_it_stages(self):
        self.assertEqual(self.done.returncode, 0, self.done.stderr)

    def test_her_pages_and_her_place_in_plasma_are_there(self):
        pages = re.findall(r"\('(\w+)', '\w+Page'\)", (ROOT / "mira/pages/__init__.py").read_text(encoding="utf-8"))
        self.assertTrue(pages, "no pages listed: the scan is broken")
        for name in ["kde_integration.py", "pages/__init__.py", "pages/base.py"] + [f"pages/{p}.py" for p in pages]:
            self.assertTrue((self.out / name).is_file(), f"the image's Mira lacks {name}")

    def test_no_test_reaches_the_image(self):
        self.assertEqual(sorted(str(p.relative_to(self.out)) for p in self.out.rglob("test_*")), [])

    def test_the_stage_gate_names_them(self):
        stage = STAGE.read_text(encoding="utf-8")
        for name in ("kde_integration.py", "pages/__init__.py", "pages/base.py"):
            self.assertTrue(name in stage, f"stage.sh's own gate does not require {name}")


class ShellNamesMira(unittest.TestCase):
    """The assistant a person meets in the shell is Mira; "Mo AI" is only her engine."""

    SURFACES = {
        ISLAND / "main.qml": ['root.local("فتح ميرا", "Open Mira")', '"Working · details in Mira"',
                              'root.local(label + " · ميرا", "Mira · " + label)',
                              '"You confirmed this action in Mira; its steps and result are shown there."'],
        ISLAND / "SearchView.qml": ['{ keys: "Ctrl Enter", ar: "اسأل ميرا", en: "Ask Mira" }',
                                    'root.local("افتح ميرا", "Open Mira")', '"Try another word, or ask Mira below."'],
        # the job chip's words for a tool it has no label for: "Mira · A Mo AI action" otherwise
        ISLAND / "IslandTokens.js": ['["إجراء من ميرا", "A Mira action"]'],
        LAUNCHER_VIEW: ['view.local("ابدأ مع ميرا", "Create with Mira")'],
        WELCOME: ['"افتح ميرا" : "Open Mira"', 'Mira helps with everything'],
    }

    def test_each_surface_names_her(self):
        for path, phrases in self.SURFACES.items():
            text = path.read_text(encoding="utf-8")
            for phrase in phrases:
                self.assertTrue(phrase in text, f"{path.relative_to(ROOT)} lost «{phrase}»")

    def test_no_string_a_person_reads_says_mo_ai(self):
        literal = re.compile(r'"(?:[^"\\]|\\.)*"')
        for path in self.SURFACES:
            with self.subTest(surface=str(path.relative_to(ROOT))):
                strings = literal.findall(code_lines(path.read_text(encoding="utf-8")))
                said = [s for s in strings if "Mo AI" in s]
                self.assertEqual(said, [], "the assistant is Mira in the shell")

    def test_the_owner_is_told_in_whats_new(self):
        news = json.loads((ROOT / "system_files/usr/share/moos/whats-new.json").read_text(encoding="utf-8"))
        entry = next((e for e in news["entries"] if e.get("id") == "mira-in-plasma"), None)
        self.assertIsNotNone(entry, "the Dolphin entries and the login start are changes he can see")
        self.assertIn("Dolphin", entry["body"]["en"])
        # No "Try it": moos://settings/assistant opens MoOS Settings, not Mira's own Settings, where
        # the login switch lives, and a whats-new route may only name a settings page.
        self.assertNotIn("route", entry)

    def test_the_routes_still_reach_her(self):
        island = code_lines((ISLAND / "main.qml").read_text(encoding="utf-8"))
        self.assertIn('Qt.openUrlExternally("moos://app/moai")', island,
                      "moos://app/moai → moai → Mira: the route keeps Mo AI's name, the words do not")
        self.assertIn('view.launcher.openDesktop("org.moos.moai.desktop")',
                      LAUNCHER_VIEW.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
