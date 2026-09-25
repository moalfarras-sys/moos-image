#!/usr/bin/env python3
"""Gate: what the MoOS menu and Settings sidebar offer, and the words they show.

Three contracts, each executed on real files rather than grepped:

1. Wine's internal tools stay out of MoOS menus. The launcher's "All applications" showed ten
   Wine entries (Wine Boot, Wine Configuration, WineMine, ...). A Windows program runs by
   double-click through moos-run-foreign and Bottles, so the image hides those entries and
   fails the build if one is still visible. This exercises the exact sed used.

2. build_files/curate_app_menu.sh — the ONE menu curation, written for every edition. x86
   build.sh runs it; build-arm.sh is the ARM owner's file, so its wiring is a handoff whose
   exact change is checked here against today's build-arm.sh. It is run here, whole, on stock
   entries shaped like the booted station's with the REAL shipped overlay on top (MoOS's own
   entries are never stubbed), and then its finished-tree gate is run alone on states
   the curation steps would repair, so every rule is proven to fail the build when it breaks:
   exactly one visible settings entry (systemsettings.desktop, "MoOS Settings", MoOS icon,
   Exec=moos-settings), the duplicates hidden, no kept entry wearing another desktop's name or
   lacking Arabic, Discover hidden and not an updater, every Settings external module opening
   an installed program, and the firewall reachable once its menu entry is gone.

3. build_files/verify_no_foreign_identity.py sweeps launcher text — visible menu entries,
   Settings external modules and categories, menu folders — for another OS's name, in every
   language. Run on a fixture root it passes clean and fails on a planted name.
"""
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = (ROOT / "build_files/build.sh").read_text(encoding="utf-8")
BUILD_ARM = (ROOT / "build_files/build-arm.sh").read_text(encoding="utf-8")
CURATE = ROOT / "build_files/curate_app_menu.sh"
CURATE_TEXT = CURATE.read_text(encoding="utf-8")
FIREWALL = ROOT / "build_files/verify_no_foreign_identity.py"
SYSTEM = ROOT / "system_files"
CALL = "bash /ctx/curate_app_menu.sh / || exit 1"
STAGED = "usr/share/moos/settings-external-modules/moos-firewall.desktop"
INSTALLED = "usr/share/plasma/systemsettings/externalmodules/moos-firewall.desktop"
ARM_DISCOVER_SED = "_disc=/usr/share/applications/org.kde.discover.desktop"


class WineMenuTests(unittest.TestCase):
    def block(self):
        match = re.search(r"    for _wine_entry in /usr/share/applications/wine-\*\.desktop; do\n(.*?)\n    done\n", BUILD, re.S)
        self.assertIsNotNone(match, "the Wine hide loop is missing from build.sh")
        return match.group(1)

    def test_build_hides_wine_tools_and_gates_it(self):
        self.block()
        self.assertIn("GATE FAIL: Wine tools are still visible in menus", BUILD)
        self.assertLess(BUILD.index('dnf5 -y install "${_core_power[@]}"'),
                        BUILD.index("for _wine_entry in /usr/share/applications/wine-*.desktop"))

    def test_the_same_commands_hide_real_desktop_files(self):
        body = self.block()
        with tempfile.TemporaryDirectory() as tmp:
            apps = Path(tmp)
            (apps / "wine-winecfg.desktop").write_text("[Desktop Entry]\nName=Wine Configuration\nExec=winecfg\n")
            (apps / "wine-notepad.desktop").write_text("[Desktop Entry]\nName=Wine Notepad\nNoDisplay=false\n[Desktop Action x]\nName=x\n")
            script = "for _wine_entry in " + str(apps) + "/wine-*.desktop; do\n" + body + "\ndone\n"
            subprocess.run(["bash", "-c", script], check=True)
            for entry in apps.glob("wine-*.desktop"):
                text = entry.read_text()
                self.assertEqual(text.count("NoDisplay=true"), 1, text)
                self.assertTrue(text.startswith("[Desktop Entry]\nNoDisplay=true") or "NoDisplay=true" in text)
            self.assertIn("[Desktop Action x]", (apps / "wine-notepad.desktop").read_text())


# ── curate_app_menu.sh ─────────────────────────────────────────────────────────────────

# Shapes copied from the booted station (plasma-systemsettings 6.7.5, plasma-discover 6.7.5,
# htop/btop/nvtop, kfind, khelpcenter, firewall-config 2.4.4), trimmed to what the rules read.
STOCK = {
    "systemsettings.desktop": (
        "[Desktop Entry]\nExec=systemsettings\nIcon=preferences-system\nType=Application\n"
        "X-KDE-Shortcuts=Tools,Meta+I\nOnlyShowIn=KDE;\n"
        "Actions=kcm-lookandfeel;kcm-users;\n"
        "Name=System Settings\nName[ar]=إعدادات النّظام\nName[de]=Systemeinstellungen\n"
        "GenericName=System Settings\nGenericName[ar]=إعدادات النّظام\n"
        "Comment=Configure the system’s behavior and appearance\nComment[de]=Verhalten\n"
        "X-DBUS-StartupType=Unique\nCategories=Qt;KDE;Settings;\nKeywords=systemsettings\n"
        "\n[Desktop Action kcm-lookandfeel]\nName=Global Theme\nName[ar]=سمة شاملة\n"
        "Icon=preferences-desktop-theme-global\nExec=systemsettings kcm_lookandfeel\n"
        "\n[Desktop Action kcm-users]\nName=Users\nName[ar]=المستخدمين\n"
        "Icon=preferences-system-users\nExec=systemsettings kcm_users\n"),
    "kdesystemsettings.desktop": (
        "[Desktop Entry]\nExec=systemsettings\nIcon=preferences-system\nType=Application\n"
        "Name=System Settings\nName[ar]=إعدادات النّظام\n"),
    "org.kde.kinfocenter.desktop": (
        "[Desktop Entry]\nExec=kinfocenter\nIcon=hwinfo\nType=Application\n"
        "Name=Info Center\nName[ar]=مركز المعلومات\n"),
    "org.kde.dolphin.desktop": (
        "[Desktop Entry]\nExec=dolphin %u\nIcon=system-file-manager\nType=Application\n"
        "Name=Dolphin\nName[ar]=دولفين\nGenericName=File Manager\nActions=new-window;\n"
        "\n[Desktop Action new-window]\nName=Open a New Window\nName[ar]=افتح نافذة جديدة\n"
        "Exec=dolphin --new-window\n"),
    "org.kde.kdeconnect.app.desktop": (
        "[Desktop Entry]\nExec=kdeconnect-app\nIcon=kdeconnect\nType=Application\n"
        "Name=KDE Connect\nName[ar]=جسر كِيدِي\nComment=Make all your devices one\n"
        "Comment[ar]=اجعل أجهزتك كلّها واحدًا\n"),
    "org.kde.partitionmanager.desktop": (
        "[Desktop Entry]\nExec=partitionmanager\nIcon=partitionmanager\nType=Application\n"
        "Name=KDE Partition Manager\nName[ar]=مدير أقسام كِيدِي\n"),
    "org.kde.discover.desktop": (
        "[Desktop Entry]\nName=Discover\nName[ar]=المستكشف\nComment=Install and remove apps\n"
        "Exec=plasma-discover %F\nIcon=plasmadiscover\nType=Application\nActions=Updates;\n"
        "GenericName=Software Center\nGenericName[ar]=مركز البرمجيات\n"
        "\n[Desktop Action Updates]\nName=Updates\nName[ar]=التحديثات\n"
        "Exec=plasma-discover --mode update\n"),
    "htop.desktop": "[Desktop Entry]\nName=Htop\nExec=htop\nTerminal=true\nType=Application\n",
    "nvtop.desktop": "[Desktop Entry]\nName=nvtop\nExec=nvtop\nTerminal=true\nType=Application\n",
    "btop.desktop": "[Desktop Entry]\nName=btop++\nExec=btop\nTerminal=true\nType=Application\n",
    "org.kde.kfind.desktop": "[Desktop Entry]\nName=KFind\nExec=kfind %u\nType=Application\n",
    "org.kde.khelpcenter.desktop": (
        "[Desktop Entry]\nName=Help Center\nExec=khelpcenter %u\nType=Application\n"),
    "firewall-config.desktop": (
        "[Desktop Entry]\nName=Firewall\nExec=firewall-config\nIcon=firewall-config\n"
        "Categories=System;Settings;Security;\nType=Application\n"),
}
# MoOS's own entries are NOT stubbed here. The fixture lays down the real overlay
# (system_files/usr/share/applications/*.desktop, system_files/etc/xdg/autostart/*.desktop),
# exactly what `COPY system_files/ /` puts in place before build.sh (z1b) runs. A stub that
# already carried another slice's change once kept this suite green while every image build
# would have failed on the real org.moos.settings.desktop (review finding, 2026-09-24).
PROGRAMS = ("moos-settings", "systemsettings", "kinfocenter", "firewall-config")
UPSTREAM_NOTIFIER = ("[Desktop Entry]\nName=Discover\nExec=/usr/libexec/DiscoverNotifier "
                     "--check-delay 20\nType=Application\nNoDisplay=true\n")
UPSTREAM_POLICY = "[Global]\nUseUnattendedUpdates=true\nRequiredNotificationInterval=604800\n"
# What plasma-discover-notifier 6.7.5's binary carries (measured): the policy file's name as
# UTF-16 (a QStringLiteral) and the key in both encodings.
NOTIFIER_BINARY = (b"\x7fELF..." + "PlasmaDiscoverUpdates".encode("utf-16-le") + b"\0"
                   + b"UseUnattendedUpdates\0" + "UseUnattendedUpdates".encode("utf-16-le"))


def write(path: Path, text: str, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    if mode is not None:
        path.chmod(mode)


def fixture(tree: Path, *, overlay: bool = True) -> Path:
    """A root shaped like the station: stock entries, then MoOS's overlay copied on top."""
    apps = tree / "usr/share/applications"
    for name, text in STOCK.items():
        write(apps / name, text)
    for program in PROGRAMS:
        write(tree / "usr/bin" / program, "#!/bin/sh\n", 0o755)
    notifier = tree / "usr/libexec/DiscoverNotifier"
    notifier.parent.mkdir(parents=True, exist_ok=True)
    notifier.write_bytes(NOTIFIER_BINARY)
    notifier.chmod(0o755)
    write(tree / "usr/share/systemsettings/categories/settings-security-privacy.desktop",
          "[Desktop Entry]\nX-KDE-System-Settings-Category=security-privacy\n"
          "X-KDE-System-Settings-Parent-Category=\nName=Security & Privacy\n")
    write(tree / "etc/xdg/autostart/org.kde.discover.notifier.desktop", UPSTREAM_NOTIFIER)
    write(tree / "etc/xdg/PlasmaDiscoverUpdates", UPSTREAM_POLICY)
    if overlay:  # what `COPY system_files/ /` (x86) or `cp -a /moos-overlay/. /` (ARM) lays down
        overlay_files = [*sorted((SYSTEM / "usr/share/applications").glob("*.desktop")),
                         *sorted((SYSTEM / "etc/xdg/autostart").glob("*.desktop")),
                         SYSTEM / "etc/xdg/PlasmaDiscoverUpdates", SYSTEM / STAGED]
        for source in overlay_files:
            write(tree / source.relative_to(SYSTEM), source.read_text(encoding="utf-8"))
    return tree


APPEARANCE_KCM = "usr/lib64/qt6/plugins/plasma/kcms/systemsettings/kcm_moos_appearance.so"


def install_appearance_module(tree: Path) -> None:
    """What slice F's kcm_moos_appearance lays down (Containerfile copies the KCM stage's
    /usr before build.sh runs, so the curation sees it)."""
    write(tree / APPEARANCE_KCM, "ELF", 0o755)


def curate(tree: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(CURATE), str(tree)], capture_output=True, text=True,
                          timeout=120)


def gate_source() -> str:
    match = re.search(r"<<'MOOSMENUGATE'\n(.*?)\nMOOSMENUGATE\n", CURATE_TEXT, re.S)
    assert match, "curate_app_menu.sh has lost its finished-tree gate"
    return match.group(1)


def hidden_list() -> list[str]:
    match = re.search(r"\nMENU_HIDDEN=\(\n(.*?)\n\)\n", CURATE_TEXT, re.S)
    assert match, "curate_app_menu.sh has lost its MENU_HIDDEN list"
    return match.group(1).split()


def gate(tree: Path) -> subprocess.CompletedProcess:
    """The gate alone, on a tree the steps did not repair — exactly as the script runs it."""
    return subprocess.run(["python3", "-", str(tree), " ".join(hidden_list())],
                          input=gate_source(), capture_output=True, text=True, timeout=60)


def header(path: Path) -> dict[str, str]:
    out, group = {}, None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("["):
            group = line
        elif group == "[Desktop Entry]" and "=" in line:
            key, value = line.split("=", 1)
            out.setdefault(key, value)
    return out


def group_text(path: Path, name: str) -> str:
    text = path.read_text(encoding="utf-8")
    match = re.search(rf"^\[{re.escape(name)}\]\n(.*?)(?=^\[|\Z)", text, re.S | re.M)
    return match.group(1) if match else ""


def arm_wiring_problems(text: str) -> list[str]:
    """What is wrong with how build-arm.sh runs the curation; [] while it does not run it.

    build-arm.sh replaced its own `_disc` sed rewrite of Discover with CALL (2026-09-25), so
    ARM curates its menu with the same script as x86; every rule below applies to it.
    """
    if "curate_app_menu.sh" not in text:
        return []
    if CALL not in text:
        return ["names curate_app_menu.sh but does not run it as `" + CALL + "`"]
    problems, call = [], text.index(CALL)
    if text.count(CALL) != 1:
        problems.append("runs the curation more than once")
    installs = [m.start() for m in re.finditer(r"(?m)^dnf5 -y install", text)]
    if not installs or max(installs) > call:
        problems.append("runs it before its last package install")
    overlay = text.find("cp -a /moos-overlay/. /")
    if overlay < 0 or overlay > call:
        problems.append("runs it before the overlay (staged page, notifier override) is in place")
    firewall = text.find("python3 /ctx/verify_no_foreign_identity.py")
    if firewall < 0 or firewall < call:
        problems.append("runs it after the identity firewall, which must read the curated menu")
    if ARM_DISCOVER_SED in text:
        problems.append("still rewrites org.kde.discover.desktop with its own sed: two rewrites "
                        "of one file, and the sed renames Discover's Updates action 'Mo Store'")
    return problems


class CurateAppMenuWiring(unittest.TestCase):
    def test_x86_runs_the_one_script_after_its_last_package_transaction(self):
        self.assertEqual(BUILD.count(CALL), 1, "build.sh must run curate_app_menu.sh exactly once")
        self.assertLess(BUILD.index('dnf5 -y install "${_core_power[@]}"'), BUILD.index(CALL))
        self.assertLess(BUILD.index(CALL), BUILD.index("python3 /ctx/verify_image_experience.py"))
        self.assertLess(BUILD.index(CALL), BUILD.index("python3 /ctx/verify_no_foreign_identity.py"))

    def test_arm_runs_the_one_script_exactly_once_in_its_place(self):
        # ARM had none of the menu curation; since the 2026-09-25 integration it runs the same
        # script as x86, once, after its packages and overlay and before its identity firewall.
        self.assertEqual(BUILD_ARM.count(CALL), 1, "build-arm.sh must run curate_app_menu.sh once")
        self.assertNotIn(ARM_DISCOVER_SED, BUILD_ARM)
        self.assertEqual(arm_wiring_problems(BUILD_ARM), [])

    def test_the_arm_wiring_rules_bite(self):
        # The old ARM sed back beside the call: two rewrites of one file.
        kept_sed = BUILD_ARM.replace(CALL, ARM_DISCOVER_SED + "\n" + CALL, 1)
        self.assertIn("still rewrites org.kde.discover.desktop", " ".join(arm_wiring_problems(kept_sed)))
        early = BUILD_ARM.replace(CALL + "\n", "").replace("cp -a /moos-overlay/. /",
                                                             CALL + "\ncp -a /moos-overlay/. /", 1)
        self.assertIn("before the overlay", " ".join(arm_wiring_problems(early)))
        twice = BUILD_ARM.replace(CALL, CALL + "\n" + CALL, 1)
        self.assertIn("more than once", " ".join(arm_wiring_problems(twice)))
        loose = BUILD_ARM.replace(CALL, "bash /ctx/curate_app_menu.sh /", 1)
        self.assertIn("does not run it as", " ".join(arm_wiring_problems(loose)))

    def test_the_old_inline_curation_is_gone_from_build_sh(self):
        for leftover in ("hide_from_menu()", "moos_rebrand_entry()", "_disc=/usr/share/applications"):
            self.assertNotIn(leftover, BUILD, f"build.sh still carries {leftover}: two curations "
                             "drift apart, which is how ARM lost all of it")
        subprocess.run(["bash", "-n", str(CURATE)], check=True)

    def test_the_menu_keeps_out_what_the_owner_does_not_use(self):
        hidden = hidden_list()
        for name in ("kdesystemsettings.desktop", "org.kde.kwrite.desktop", "htop.desktop",
                     "nvtop.desktop", "btop.desktop", "org.kde.kfind.desktop",
                     "org.kde.khelpcenter.desktop", "firewall-config.desktop",
                     "org.kde.krfb.desktop", "org.kde.kjournaldbrowser.desktop"):
            self.assertIn(name, hidden)
        self.assertEqual(len(hidden), len(set(hidden)))


class CurateAppMenuRun(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tree = fixture(Path(self._tmp.name))
        self.apps = self.tree / "usr/share/applications"

    def tearDown(self):
        self._tmp.cleanup()

    def run_ok(self):
        result = curate(self.tree)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def test_the_shipped_overlay_on_stock_entries_passes_the_whole_curation(self):
        # Exactly what build.sh (z1b) runs: stock entries, the real overlay on top, the script.
        result = curate(self.tree)
        self.assertEqual(
            result.returncode, 0,
            "the shipped overlay fails the curation's gate, so every image build would fail in "
            "build.sh (z1b). If the gate names org.moos.settings.desktop, slice A's half of "
            "decision D2 (NoDisplay=true on that entry) is not in this tree: merge A with or "
            "before E.\n" + result.stdout + result.stderr)

    def test_settings_becomes_the_one_moos_entry(self):
        self.run_ok()
        path = self.apps / "systemsettings.desktop"
        entry = header(path)
        self.assertEqual(entry.get("Name"), "MoOS Settings")
        self.assertEqual(entry.get("Name[ar]"), "إعدادات MoOS")
        self.assertEqual(entry.get("Icon"), "moos-control-center")
        self.assertEqual(entry.get("Exec"), "moos-settings")
        self.assertNotIn("NoDisplay", entry)
        self.assertEqual(entry.get("X-KDE-Shortcuts"), "Tools,Meta+I", "Meta+I must survive")
        text = path.read_text(encoding="utf-8")
        head = text.split("\n[Desktop Action", 1)[0]
        for gone in ("GenericName", "Name[de]", "Comment[de]", "System Settings"):
            self.assertNotIn(gone, head, f"the header still carries {gone}")
        self.assertIn("Comment[ar]=", head)
        self.assertIn("Keywords[ar]=", head)
        self.assertTrue(entry["Actions"].startswith("moos-update;kcm-lookandfeel;kcm-users"))
        self.assertIn("Exec=systemsettings kcm_users", group_text(path, "Desktop Action kcm-users"),
                      "an upstream page MoOS does not duplicate stays as upstream wrote it")
        update = group_text(path, "Desktop Action moos-update")
        self.assertIn("Exec=moos-settings --section=update", update)
        self.assertIn("Name[ar]=التحديث", update)

    def test_without_moos_themes_the_upstream_theme_item_keeps_its_own_words(self):
        # Before slice F's module ships, `moos-settings --section=appearance` falls back to the
        # stock Global Theme page; a "MoOS Themes" label on it would be a lie.
        self.run_ok()
        themes = group_text(self.apps / "systemsettings.desktop", "Desktop Action kcm-lookandfeel")
        self.assertIn("Name=Global Theme\nName[ar]=سمة شاملة\n", themes)
        self.assertIn("Exec=systemsettings kcm_lookandfeel", themes)
        self.assertNotIn("MoOS Themes", themes)

    def test_with_moos_themes_installed_the_item_opens_it(self):
        install_appearance_module(self.tree)
        self.run_ok()
        themes = group_text(self.apps / "systemsettings.desktop", "Desktop Action kcm-lookandfeel")
        self.assertIn("Name=MoOS Themes\nName[ar]=ثيمات MoOS\n", themes)
        self.assertIn("Exec=moos-settings --section=appearance", themes)
        self.assertNotIn("Global Theme", themes)
        self.assertNotIn("kcm_lookandfeel", themes)

    def test_the_curation_is_idempotent(self):
        for module in (False, True):
            with self.subTest(moos_themes_installed=module):
                if module:
                    install_appearance_module(self.tree)
                self.run_ok()
                first = {p.name: p.read_text(encoding="utf-8") for p in self.apps.glob("*.desktop")}
                self.run_ok()
                second = {p.name: p.read_text(encoding="utf-8") for p in self.apps.glob("*.desktop")}
                self.assertEqual(first, second)

    def test_duplicates_leave_and_kept_tools_wear_moos_words(self):
        self.run_ok()
        for name in hidden_list():
            if (self.apps / name).is_file():
                self.assertEqual(header(self.apps / name).get("NoDisplay"), "true", name)
        for name in ("org.kde.kinfocenter.desktop",):
            self.assertEqual(header(self.apps / name).get("NoDisplay"), "true")
        dolphin = self.apps / "org.kde.dolphin.desktop"
        self.assertEqual(header(dolphin).get("Name"), "Files")
        self.assertNotIn("NoDisplay", header(dolphin))
        self.assertIn("Name=Open a New Window", group_text(dolphin, "Desktop Action new-window"),
                      "a header rebrand must not rename the jump-list action")
        self.assertEqual(header(self.apps / "org.kde.partitionmanager.desktop").get("Name"), "Disks")

    def test_discover_is_renamed_in_its_header_only(self):
        self.run_ok()
        path = self.apps / "org.kde.discover.desktop"
        entry = header(path)
        self.assertEqual((entry.get("Name"), entry.get("Icon"), entry.get("NoDisplay")),
                         ("Mo Store", "mo-store", "true"))
        self.assertNotIn("GenericName", entry)
        self.assertIn("Name=Updates\nName[ar]=التحديثات\n", group_text(path, "Desktop Action Updates"))

    def test_a_blind_sed_rename_before_the_script_fails_the_build(self):
        # What build-arm.sh's own sed leaves: every Name= and Icon= in the file rewritten. The
        # script no longer repairs it (one rewrite of one file); its gate refuses it instead,
        # which is why the ARM handoff deletes that sed.
        path = self.apps / "org.kde.discover.desktop"
        write(path, "[Desktop Entry]\nName=Mo Store\nName[ar]=متجر MoOS\nIcon=mo-store\n"
                    "Exec=plasma-discover %F\nNoDisplay=true\nActions=Updates;\n"
                    "\n[Desktop Action Updates]\nName=Mo Store\nName[ar]=متجر MoOS\n"
                    "Icon=mo-store\nExec=plasma-discover --mode update\n")
        result = curate(self.tree)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("leaked out of the header", result.stdout)

    def test_the_firewall_moves_into_settings(self):
        self.assertFalse((self.tree / INSTALLED).exists(),
                         "the overlay must only STAGE the page; an image that runs no curation "
                         "would otherwise show it where firewall-config is missing")
        self.run_ok()
        self.assertEqual(header(self.apps / "firewall-config.desktop").get("NoDisplay"), "true")
        module = self.tree / INSTALLED
        self.assertTrue(module.is_file(), "firewall-config is installed; its Settings page must be offered")
        self.assertEqual(module.read_bytes(), (SYSTEM / STAGED).read_bytes())

    def test_an_edition_without_the_program_gets_no_page_not_a_dead_one(self):
        (self.tree / "usr/bin/firewall-config").unlink()
        (self.apps / "firewall-config.desktop").unlink()
        result = self.run_ok()
        self.assertFalse((self.tree / INSTALLED).exists(),
                         "a page whose program is absent would sit in the sidebar doing nothing")
        self.assertIn("does not ship; not offered", result.stdout)

    def test_an_installed_page_whose_program_left_is_removed(self):
        write(self.tree / "usr/share/plasma/systemsettings/externalmodules/old.desktop",
              "[Desktop Entry]\nType=Service\nExec=gone-tool\nName=Old\nName[ar]=قديم\n"
              "X-KDE-System-Settings-Parent-Category=security-privacy\n")
        result = self.run_ok()
        self.assertFalse((self.tree / "usr/share/plasma/systemsettings/externalmodules"
                          / "old.desktop").exists())
        self.assertIn("old.desktop opens 'gone-tool', which this edition does not ship; removed",
                      result.stdout)

    def test_without_the_overlay_the_rival_updater_fails_the_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            tree = fixture(Path(tmp), overlay=False)
            result = curate(tree)
            self.assertEqual(result.returncode, 1)
            self.assertIn("starts Discover's updater at login", result.stdout)
            self.assertIn("UseUnattendedUpdates=false", result.stdout)
            self.assertIn("firewall would be unreachable", result.stdout)


class CurateAppMenuGateBites(unittest.TestCase):
    """Each rule of the finished-tree gate, broken on its own, fails the build."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tree = fixture(Path(self._tmp.name))
        self.apps = self.tree / "usr/share/applications"
        result = curate(self.tree)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        clean = gate(self.tree)
        self.assertEqual(clean.returncode, 0, clean.stdout + clean.stderr)

    def tearDown(self):
        self._tmp.cleanup()

    def assertBites(self, needle: str):
        result = gate(self.tree)
        self.assertEqual(result.returncode, 1, f"the gate passed a broken tree:\n{result.stdout}")
        self.assertIn(needle, result.stdout)

    def edit(self, name: str, old: str, new: str):
        path = self.apps / name
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text)
        path.write_text(text.replace(old, new, 1), encoding="utf-8")

    def test_a_second_visible_settings_app(self):
        self.edit("org.moos.settings.desktop", "NoDisplay=true\n", "")
        self.assertBites("exactly one settings entry")

    def test_settings_hidden_again(self):
        self.edit("systemsettings.desktop", "[Desktop Entry]\n", "[Desktop Entry]\nNoDisplay=true\n")
        self.assertBites("exactly one settings entry")

    def test_settings_with_another_name_or_icon(self):
        self.edit("systemsettings.desktop", "Name=MoOS Settings", "Name=System Settings")
        self.assertBites("must wear MoOS's name and icon")

    def test_settings_with_a_symbolic_icon(self):
        self.edit("systemsettings.desktop", "Icon=moos-control-center", "Icon=moos-settings-symbolic")
        self.assertBites("must wear MoOS's name and icon")

    def test_settings_that_opens_upstreams_start_page(self):
        self.edit("systemsettings.desktop", "Exec=moos-settings\n", "Exec=systemsettings\n")
        self.assertBites("does not run an installed moos-settings")

    def test_settings_whose_program_is_missing(self):
        (self.tree / "usr/bin/moos-settings").unlink()
        self.assertBites("does not run an installed moos-settings")

    def test_settings_without_meta_i(self):
        self.edit("systemsettings.desktop", "X-KDE-Shortcuts=Tools,Meta+I", "X-KDE-Shortcuts=")
        self.assertBites("lost its Meta+I shortcut")

    def test_a_dangling_jump_list_action(self):
        self.edit("systemsettings.desktop", "Actions=moos-update;", "Actions=moos-update;ghost;")
        self.assertBites("dead jump-list item")

    def test_moos_themes_offered_without_its_module(self):
        path = self.apps / "systemsettings.desktop"
        text = path.read_text(encoding="utf-8")
        text = text.replace("Name=Global Theme", "Name=MoOS Themes", 1).replace(
            "Exec=systemsettings kcm_lookandfeel", "Exec=moos-settings --section=appearance", 1)
        path.write_text(text, encoding="utf-8")
        self.assertBites("kcm_moos_appearance is not installed")

    def test_the_stock_theme_page_kept_beside_moos_themes(self):
        install_appearance_module(self.tree)  # the module arrived; the item was not retargeted
        self.assertBites("two theme pages")

    def test_a_hidden_duplicate_back_in_the_menu(self):
        self.edit("htop.desktop", "NoDisplay=true\n", "")
        self.assertBites("htop.desktop is still shown in the menu")

    def test_a_kept_tool_hidden(self):
        self.edit("org.kde.dolphin.desktop", "[Desktop Entry]\n", "[Desktop Entry]\nNoDisplay=true\n")
        self.assertBites("a person needs this tool")

    def test_another_desktops_name_on_a_kept_tool(self):
        self.edit("org.kde.dolphin.desktop", "Name=Files", "Name=Dolphin")
        self.assertBites("still wears another desktop's name")

    def test_another_desktops_name_anywhere_in_a_kept_header(self):
        # The review's probe: the inline gate this replaced read the whole header, so these
        # failed the build; a Name-only check shipped them.
        for name, line in (
                ("org.kde.kdeconnect.app.desktop", "Comment=KDE Connect for your phone"),
                ("org.kde.kdeconnect.app.desktop", "Keywords=KDE Connect;phone;"),
                ("org.kde.partitionmanager.desktop", "Comment=Manage disks with KDE Partition Manager"),
                ("org.kde.dolphin.desktop", "GenericName[de]=Dolphin Dateiverwaltung"),
                ("org.kde.dolphin.desktop", "X-KDE-Keywords=dolphin,files"),
                ("org.kde.kinfocenter.desktop", "Comment[en_GB]=The Info Center"),
                ("org.kde.kdeconnect.app.desktop", "Keywords[ar]=هاتف;جسر كِيدِي;"),
                ("org.kde.dolphin.desktop", "Comment[ar]=مدير ملفات دولفين"),
        ):
            with self.subTest(name=name, line=line):
                path = self.apps / name
                clean = path.read_text(encoding="utf-8")
                path.write_text(clean.replace("[Desktop Entry]\n", f"[Desktop Entry]\n{line}\n", 1),
                                encoding="utf-8")
                self.assertBites(f"{name} still wears another desktop's name")
                path.write_text(clean, encoding="utf-8")

    def test_a_program_path_is_not_a_label(self):
        # Exec=dolphin, StartupWMClass=dolphin and X-DocPath are not text a launcher shows;
        # flagging them would fail every build on upstream's own files.
        self.edit("org.kde.dolphin.desktop", "[Desktop Entry]\n",
                  "[Desktop Entry]\nStartupWMClass=dolphin\nX-DocPath=dolphin/index.html\n")
        result = gate(self.tree)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_a_kept_tool_without_arabic(self):
        self.edit("org.kde.partitionmanager.desktop", "Name[ar]=الأقراص\n", "")
        self.assertBites("has no Arabic name")

    def test_discover_back_in_the_menu(self):
        self.edit("org.kde.discover.desktop", "NoDisplay=true\n", "")
        self.assertBites("two storefronts")

    def test_a_store_name_leaking_into_an_action(self):
        self.edit("org.kde.discover.desktop", "Name=Updates", "Name=Mo Store")
        self.assertBites("leaked out of the header")

    def test_the_notifier_autostarting(self):
        write(self.tree / "etc/xdg/autostart/org.kde.discover.notifier.desktop", UPSTREAM_NOTIFIER)
        self.assertBites("starts Discover's updater at login")

    def test_the_notifier_renamed_upstream(self):
        # The review's probe: MoOS's override still sits at the old name, Hidden=true, while
        # the package now installs its entry under another one.
        write(self.tree / "etc/xdg/autostart/org.kde.discover.notifier-autostart.desktop",
              UPSTREAM_NOTIFIER)
        self.assertBites("org.kde.discover.notifier-autostart.desktop starts Discover's updater")

    def test_a_notifier_in_the_other_autostart_directory(self):
        write(self.tree / "usr/share/autostart/org.kde.discover.notifier.desktop", UPSTREAM_NOTIFIER)
        self.assertBites("usr/share/autostart/org.kde.discover.notifier.desktop starts")

    def test_an_update_run_started_at_login(self):
        write(self.tree / "etc/xdg/autostart/discover-update.desktop",
              "[Desktop Entry]\nType=Application\nName=Updates\n"
              "Exec=plasma-discover --mode update\n")
        self.assertBites("discover-update.desktop starts Discover's updater")

    def test_unattended_updates_on(self):
        write(self.tree / "etc/xdg/PlasmaDiscoverUpdates", UPSTREAM_POLICY)
        self.assertBites("UseUnattendedUpdates=false")

    def test_the_binary_moved_and_the_policy_restored(self):
        # The review's probe: the policy check used to run only if
        # /usr/libexec/DiscoverNotifier existed at exactly that path.
        (self.tree / "usr/libexec/DiscoverNotifier").rename(self.tree / "usr/libexec/Discover")
        write(self.tree / "etc/xdg/PlasmaDiscoverUpdates", UPSTREAM_POLICY)
        self.assertBites("UseUnattendedUpdates=false")

    def test_the_policy_file_missing(self):
        (self.tree / "etc/xdg/PlasmaDiscoverUpdates").unlink()
        self.assertBites("it is None")

    def test_a_notifier_that_no_longer_reads_the_policy_file(self):
        moved = self.tree / "usr/libexec/discover/DiscoverNotifier"
        moved.parent.mkdir(parents=True)
        moved.write_bytes(b"\x7fELF reads its switch from somewhere else")
        self.assertBites("/usr/libexec/discover/DiscoverNotifier no longer names")

    def test_a_notifier_found_through_the_entry_that_runs_it(self):
        entry = "[Desktop Entry]\nName=Discover\nExec=/opt/discover/DiscoverNotifier\nNoDisplay=true\n"
        write(self.tree / "usr/share/applications/org.kde.discover.notifier.desktop", entry)
        write(self.tree / "opt/discover/DiscoverNotifier", "no policy here", 0o755)
        self.assertBites("/opt/discover/DiscoverNotifier no longer names")

    def test_a_settings_page_that_opens_nothing(self):
        (self.tree / "usr/bin/firewall-config").unlink()
        self.assertBites("a sidebar page that does nothing")

    def test_a_settings_page_in_a_category_that_does_not_exist(self):
        module = self.tree / INSTALLED
        module.write_text(module.read_text(encoding="utf-8").replace(
            "Parent-Category=security-privacy", "Parent-Category=nowhere"), encoding="utf-8")
        self.assertBites("would never appear")

    def test_the_firewall_left_unreachable(self):
        (self.tree / INSTALLED).unlink()
        self.assertBites("firewall would be unreachable")

    def test_a_staged_page_left_in_staging(self):
        write(self.tree / "usr/share/moos/settings-external-modules/moos-second.desktop",
              "[Desktop Entry]\nType=Service\nExec=kinfocenter\nName=Second\nName[ar]=ثان\n"
              "X-KDE-System-Settings-Parent-Category=security-privacy\n")
        self.assertBites("moos-second.desktop is staged")


class FirewallExternalModule(unittest.TestCase):
    """The shipped file itself: the keys System Settings' external-module loader reads."""

    def test_the_module_is_staged_and_carries_what_system_settings_reads(self):
        self.assertFalse((SYSTEM / INSTALLED).exists(),
                         "shipped straight into externalmodules, the page reaches ARM, which has "
                         "no firewall-config and runs no curation: a dead sidebar page")
        path = SYSTEM / STAGED
        entry = header(path)
        self.assertEqual(entry.get("Exec"), "firewall-config")
        self.assertEqual(entry.get("TryExec"), "firewall-config")
        self.assertEqual(entry.get("X-KDE-System-Settings-Parent-Category"), "security-privacy")
        self.assertEqual((entry.get("Name"), entry.get("Name[ar]")), ("Firewall", "الجدار الناري"))
        self.assertTrue(entry.get("Comment[ar]"))


# ── verify_no_foreign_identity.py: launcher text ───────────────────────────────────────

class IdentityFirewallSweepsLauncherText(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tree = Path(self._tmp.name)
        # The smallest tree every other check of the firewall accepts.
        logo = self.tree / "usr/share/pixmaps/moos-logo.png"
        logo.parent.mkdir(parents=True)
        shutil.copyfile(SYSTEM / "usr/share/pixmaps/moos-logo.png", logo)
        write(self.tree / "usr/lib/os-release",
              'NAME="MoOS"\nID=moos\nID_LIKE="fedora"\nPRETTY_NAME="MoOS"\nVERSION_ID=44\n')
        write(self.tree / "usr/share/applications/org.moos.store.desktop",
              "[Desktop Entry]\nName=Mo Store\nName[ar]=متجر MoOS\nExec=moos-store\n")

    def tearDown(self):
        self._tmp.cleanup()

    def sweep(self):
        return subprocess.run(["python3", str(FIREWALL), "--root", str(self.tree)],
                              capture_output=True, text=True, timeout=60)

    def assertClean(self):
        result = self.sweep()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def assertLeak(self, needle: str):
        result = self.sweep()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("launcher text names another OS", result.stdout)
        self.assertIn(needle, result.stdout)

    def test_a_clean_tree_passes(self):
        self.assertClean()

    def test_a_visible_entry_naming_the_base_in_a_translation(self):
        write(self.tree / "usr/share/applications/org.example.tool.desktop",
              "[Desktop Entry]\nName=Tool\nComment[ar]=أداة من فيدورا\nExec=tool\n")
        self.assertLeak("org.example.tool.desktop")

    def test_an_action_name_on_a_visible_entry(self):
        write(self.tree / "usr/share/applications/org.example.tool.desktop",
              "[Desktop Entry]\nName=Tool\nExec=tool\nActions=a;\n"
              "\n[Desktop Action a]\nName=Open Fedora Magazine\nExec=tool a\n")
        self.assertLeak("Desktop Action a")

    def test_keywords_and_red_hat_spellings(self):
        for value in ("Keywords=rpm;RedHat;", "Keywords=rpm;red hat;", "GenericName=RHEL tools",
                      "X-KDE-Keywords=kinoite"):
            with self.subTest(value=value):
                write(self.tree / "usr/share/applications/org.example.tool.desktop",
                      f"[Desktop Entry]\nName=Tool\n{value}\nExec=tool\n")
                self.assertLeak("org.example.tool.desktop")

    def test_a_hidden_handler_is_not_launcher_text(self):
        write(self.tree / "usr/share/applications/org.example.handler.desktop",
              "[Desktop Entry]\nName=Fedora Media Handler\nExec=handler %u\nNoDisplay=true\n")
        self.assertClean()

    def test_settings_modules_categories_and_menu_folders(self):
        for rel, text in (
            ("usr/share/plasma/systemsettings/externalmodules/x.desktop",
             "[Desktop Entry]\nName=Fedora Firewall\nExec=x\n"),
            ("usr/share/plasma/kinfocenter/externalmodules/x.desktop",
             "[Desktop Entry]\nName=Monitor\nComment=Fedora hardware\nExec=x\n"),
            ("usr/share/systemsettings/categories/settings-x.desktop",
             "[Desktop Entry]\nName=Red Hat\nX-KDE-System-Settings-Category=x\n"),
            ("usr/share/desktop-directories/x.directory",
             "[Desktop Entry]\nName=Fedora Games\nIcon=x\n"),
        ):
            with self.subTest(rel=rel):
                path = self.tree / rel
                write(path, text)
                self.assertLeak(rel)
                path.unlink()
                self.assertClean()

    def test_the_build_still_runs_the_whole_firewall_on_slash(self):
        # --root exists for this test only; the build calls the script bare, in the image.
        self.assertIn("python3 /ctx/verify_no_foreign_identity.py\n", BUILD)
        self.assertIn("python3 /ctx/verify_no_foreign_identity.py\n", BUILD_ARM)
        source = FIREWALL.read_text(encoding="utf-8")
        self.assertIn("    check_launcher_identity()\n", source)
        self.assertIn('parser.add_argument("--root", default="/"', source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
