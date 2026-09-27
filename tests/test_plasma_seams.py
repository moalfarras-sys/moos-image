#!/usr/bin/env python3
"""Gate: MoOS's forks of Plasma files are keyed to the Plasma they were reviewed against.

WHY THIS EXISTS (plan row P6.7)

MoOS replaces ten files inside plasma-desktop and plasma-workspace. tests/test_plasma_shell_overlay.py
proves the build checks those files SURVIVED; nothing proved they still FIT. The base tag moves by
itself, and on 2026-09-24 Plasma 6.8 beta 1 was measured to remove `VirtualKeyboardLoader` from
org.kde.breeze.components while MoOS's 6.7 LockScreenUi.qml instantiates it: kscreenlocker's real
greeter printed "Failed to load lockscreen QML, falling back to built-in locker".

build_files/plasma_seams.py now selects a reviewed set per Plasma version, refuses upstream drift
and unregistered modifications (from rpm, not memory), and loads the real greeter. This test holds
the registry to the tree and proves every refusal actually refuses.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "build_files"))
import plasma_seams  # noqa: E402

REGISTRY = plasma_seams.load_registry()
SEAM_PATHS = [s["path"] for s in REGISTRY["seams"]]
SYSTEM = ROOT / "system_files"
LOCK = "/usr/share/plasma/shells/org.kde.plasma.desktop/contents/lockscreen"
# Files MoOS ADDS beside Plasma's (rpm owns none of them, so no upstream can drift under them).
MOOS_ADDITIONS = {
    f"{LOCK}/MoOSClock.qml",
    f"{LOCK}/images/ring.png",
    f"{LOCK}/images/spark.png",
}
# Namespaces whose files belong to Plasma's own packages when MoOS ships a file there.
PLASMA_OWNED = (
    "usr/share/plasma/shells/org.kde.plasma.desktop/",
    "usr/share/plasma/layout-templates/org.kde.",
    "usr/lib64/qt6/qml/org/kde/",
)


def code(text: str) -> str:
    """Shell/Python: drop comment lines, so prose cannot satisfy or trip a gate."""
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))


def qml_code(text: str) -> str:
    """QML: drop /* */ blocks and // comments (the header names what 6.8 removed, as prose)."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return "\n".join(re.sub(r"(^|\s)//.*$", "", line) for line in text.splitlines())


class TheRegistryIsTheTree(unittest.TestCase):
    def test_every_plasma_file_moos_replaces_is_a_registered_seam(self):
        shipped = {"/" + str(p.relative_to(SYSTEM)) for p in SYSTEM.rglob("*")
                   if p.is_file() and str(p.relative_to(SYSTEM)).startswith(PLASMA_OWNED)}
        replaced = shipped - MOOS_ADDITIONS
        self.assertTrue(replaced, "no Plasma-owned files under system_files: the scan is looking elsewhere")
        self.assertEqual(sorted(replaced - set(SEAM_PATHS)), [],
                         "MoOS replaces these Plasma files without a seam: the next Plasma would "
                         "never be reviewed for them")
        self.assertEqual(sorted(set(SEAM_PATHS) - shipped), [],
                         "seams.json names files MoOS does not ship")

    def test_every_set_reviews_every_seam_with_real_digests(self):
        for chosen in REGISTRY["sets"]:
            self.assertEqual(sorted(chosen["reviewed"]), sorted(SEAM_PATHS),
                             f"set {chosen['id']} does not review every seam")
            for path, digests in chosen["reviewed"].items():
                self.assertTrue(digests, f"set {chosen['id']}: {path} reviewed against nothing")
                for d in digests:
                    self.assertRegex(d, r"^[0-9a-f]{64}$", f"set {chosen['id']}: {path}")
            self.assertTrue(chosen.get("reviewed_on"), f"set {chosen['id']} does not say what was reviewed")

    def test_set_sources_exist_and_are_seams(self):
        base = ROOT / "build_files/plasma-seams"
        for chosen in REGISTRY["sets"]:
            for path, source in chosen["sources"].items():
                self.assertIn(path, SEAM_PATHS)
                self.assertTrue((base / source).is_file(), f"set {chosen['id']}: {source} is missing")
                self.assertTrue(source.endswith(path), f"{source} is not stored under its image path")

    def test_ranges_do_not_overlap_and_each_version_has_one_set(self):
        spans = sorted((plasma_seams.version_key(s["plasma"]["from"]),
                        plasma_seams.version_key(s["plasma"]["before"]), s["id"])
                       for s in REGISTRY["sets"])
        for (lo, hi, sid), (lo2, _hi2, sid2) in zip(spans, spans[1:]):
            self.assertLess(lo, hi, sid)
            self.assertLessEqual(hi, lo2, f"sets {sid} and {sid2} overlap")
        cases = {"6.7.0": "6.7", "6.7.5": "6.7", "6.7.90": "6.8", "6.7.91": "6.8-beta2", "6.8.0": "6.8-beta2", "6.8.6": "6.8-beta2"}
        for version, expected in cases.items():
            self.assertEqual(plasma_seams.select_set(REGISTRY, version)["id"], expected, version)
        for version in ("6.6.5", "6.8.90", "6.9.0", "7.0.0"):
            with self.assertRaises(plasma_seams.SeamError, msg=version):
                plasma_seams.select_set(REGISTRY, version)

    def test_both_builds_run_the_seam_gate_before_the_survival_gate(self):
        for script in ("build.sh", "build-arm.sh"):
            text = code((ROOT / "build_files" / script).read_text(encoding="utf-8"))
            call = text.find("python3 /ctx/plasma_seams.py build")
            survival = text.find('"/usr/share/plasma/shells/org.kde.plasma.desktop/contents/lockscreen/LockScreenUi.qml:MoOSClock"')
            self.assertGreater(call, 0, f"{script} never runs the seam gate")
            self.assertGreater(survival, call, f"{script} checks survival before the seams are installed")
            # A Plasma transaction after the gate could restore upstream bytes under the review.
            self.assertNotRegex(text[call:], r"dnf5? -y (install|reinstall|upgrade)[^\n]*\b(plasma|kscreenlocker|kwin)",
                                f"{script} changes a Plasma package after the seam gate")


class TheSixEightSetFitsSixEight(unittest.TestCase):
    """Static half of what the canary and the real greeter prove on 6.8."""

    def variant(self, name: str) -> str:
        chosen = next(s for s in REGISTRY["sets"] if s["id"] == "6.8")
        src = chosen["sources"][f"{LOCK}/{name}"]
        return (ROOT / "build_files/plasma-seams" / src).read_text(encoding="utf-8")

    def test_no_type_or_id_that_six_eight_removed(self):
        text = qml_code(self.variant("LockScreenUi.qml"))
        for gone in ("VirtualKeyboardLoader", "inputPanel", "graceLockTimer",
                     "PW.KeyboardLayoutSwitcher", "org.kde.plasma.workspace.components"):
            self.assertFalse(gone in text, f"the 6.8 lock screen still uses {gone}, which 6.8 removed")
        self.assertNotIn("graceLocked", qml_code(self.variant("MainBlock.qml")))

    def test_upstream_six_eight_auth_path_is_kept(self):
        text = self.variant("LockScreenUi.qml")
        for kept in ("pragma ComponentBehavior: Bound", "LoginLockScreen.Footer",
                     "ScreenLocker.AuthenticatorModel", "function onPamTimeoutChanged",
                     "authenticator.respond(lockScreenUi.pendingPassword)",
                     "onTriggered: authenticator.startAuthenticating()",
                     "ScreenLocker.ActiveScreenMonitor"):
            self.assertIn(kept, text, f"the 6.8 lock screen lost upstream's {kept!r}")
        self.assertIn("property alias passwordInputVisible: passwordLayout.visible",
                      self.variant("MainBlock.qml"))

    def test_the_survival_markers_hold_for_the_variant_too(self):
        # build.sh checks these markers on whatever the seam gate installed.
        self.assertIn("MoOSClock", self.variant("LockScreenUi.qml"))
        self.assertIn("org.moos.ui", self.variant("MainBlock.qml"))

    def test_no_merge_residue(self):
        for name in ("LockScreenUi.qml", "MainBlock.qml"):
            for marker in ("<<<<<<<", "=======\n", ">>>>>>>"):
                self.assertNotIn(marker, self.variant(name), name)


def fake_rpm(version: str, digests: dict[str, str], verify: dict[str, str]):
    """Patch the three rpm readers plasma_seams uses."""
    def rpm(*args, root="/"):
        if args[:2] == ("-q", "--qf") and args[2] == "%{VERSION}":
            return version
        if args[:2] == ("-q", "--qf") and args[2] == "%{FILEDIGESTALGO}":
            return "8"
        if args[:2] == ("-q", "--qf"):
            package = args[3]
            owned = {p: d for p, d in digests.items()
                     if next(s["package"] for s in REGISTRY["seams"] if s["path"] == p) == package}
            return "".join(f"{p}\t{d}\n" for p, d in owned.items())
        if args[0] == "-q":
            return args[1]
        raise AssertionError(args)
    return (mock.patch.object(plasma_seams, "rpm", rpm),
            mock.patch.object(plasma_seams, "rpm_verify", lambda pkg, root="/": verify.get(pkg, "")))


class TheGateRefuses(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="moos-seams-"))
        for path in SEAM_PATHS:  # the image after COPY system_files/ /
            target = self.root / path.lstrip("/")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(SYSTEM / path.lstrip("/"), target)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def run_gate(self, version, digests, verify=None):
        a, b = fake_rpm(version, digests, verify or {})
        with a, b:
            return plasma_seams.apply_and_verify(REGISTRY, str(self.root))

    def reviewed(self, set_id):
        chosen = next(s for s in REGISTRY["sets"] if s["id"] == set_id)
        return {p: d[0] for p, d in chosen["reviewed"].items()}

    def test_a_reviewed_six_seven_passes_and_installs_nothing(self):
        before = {p: (self.root / p.lstrip("/")).read_bytes() for p in SEAM_PATHS}
        report = self.run_gate("6.7.5", self.reviewed("6.7"))
        self.assertIn("seam set 6.7", report[0])
        for p in SEAM_PATHS:
            self.assertEqual((self.root / p.lstrip("/")).read_bytes(), before[p], p)

    def test_six_eight_installs_its_variants(self):
        self.run_gate("6.7.90", self.reviewed("6.8"))
        chosen = next(s for s in REGISTRY["sets"] if s["id"] == "6.8")
        for path, source in chosen["sources"].items():
            self.assertEqual((self.root / path.lstrip("/")).read_bytes(),
                             (ROOT / "build_files/plasma-seams" / source).read_bytes(), path)

    def test_beta_two_requires_its_review_and_installs_the_new_prompt_path(self):
        with self.assertRaises(plasma_seams.SeamError):
            self.run_gate("6.7.91", self.reviewed("6.8"))
        self.run_gate("6.7.91", self.reviewed("6.8-beta2"))
        text = (self.root / f"{LOCK}/LockScreenUi.qml".lstrip("/")).read_text()
        self.assertIn("required property bool showPrompt", text)
        self.assertIn("lockScreenUi.showPrompt = showPrompt", text)
        self.assertIn("PW.KeyboardLayoutSwitcher", text)
        self.assertNotIn("LoginLockScreen.Footer", text)

    def test_upstream_drift_is_refused(self):
        digests = self.reviewed("6.7")
        digests[f"{LOCK}/LockScreenUi.qml"] = hashlib.sha256(b"a 6.7.6 bug fix").hexdigest()
        with self.assertRaisesRegex(plasma_seams.SeamError, "LockScreenUi.qml.*Upstream changed"):
            self.run_gate("6.7.6", digests)

    def test_six_eight_bytes_under_a_six_seven_version_are_refused(self):
        # The exact case measured: 6.8's lock screen, judged by the 6.7 review.
        digests = self.reviewed("6.7")
        digests[f"{LOCK}/LockScreenUi.qml"] = self.reviewed("6.8")[f"{LOCK}/LockScreenUi.qml"]
        with self.assertRaises(plasma_seams.SeamError):
            self.run_gate("6.7.5", digests)

    def test_a_file_upstream_stopped_shipping_is_refused(self):
        digests = self.reviewed("6.7")
        del digests[f"{LOCK}/MainBlock.qml"]
        with self.assertRaisesRegex(plasma_seams.SeamError, "no longer ships"):
            self.run_gate("6.7.5", digests)

    def test_an_unreviewed_plasma_is_refused(self):
        with self.assertRaisesRegex(plasma_seams.SeamError, "no reviewed MoOS seam set"):
            self.run_gate("6.8.90", self.reviewed("6.8"))

    def test_an_unregistered_modified_plasma_file_is_refused(self):
        verify = {"plasma-workspace": "S.5....T.    /usr/share/plasma/look-and-feel/org.kde.breeze.desktop/contents/splash/Splash.qml\n"}
        with self.assertRaisesRegex(plasma_seams.SeamError, "neither a registered seam"):
            self.run_gate("6.7.5", self.reviewed("6.7"), verify)

    def test_registered_edits_seams_and_config_are_accounted_for(self):
        verify = {
            "plasma-workspace": "S.5....T.    /usr/lib64/qt6/qml/org/kde/breeze/components/qmldir\n"
                                "S.5....T.    /usr/share/wayland-sessions/plasma.desktop\n"
                                "S.5....T.  c /etc/xdg/plasmanotifyrc\n"
                                "S.5....T.    /usr/lib64/qt6/qml/org/kde/breeze/components/Clock.qml\n"
                                ".M.......    /usr/share/plasma/whatever.qml\n",
        }
        self.run_gate("6.7.5", self.reviewed("6.7"), verify)


import hide_breeze_global_themes as hide_breeze  # noqa: E402


class BothEditionsHideBreezeTheSameWay(unittest.TestCase):
    """The seam gate's rpm -V found Breeze hidden on x86 only (CI, PR #161, 2026-09-24)."""

    def test_both_builds_call_the_one_shared_step(self):
        for script in ("build.sh", "build-arm.sh"):
            text = code((ROOT / "build_files" / script).read_text(encoding="utf-8"))
            self.assertIn("python3 /ctx/hide_breeze_global_themes.py /", text, script)
            self.assertNotIn('["Hidden"] = True', text, f"{script} carries a second, inline copy")

    def test_it_hides_every_wrapper_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for path in hide_breeze.metadata_paths(root):
                path.parent.mkdir(parents=True)
                path.write_text(json.dumps({"KPlugin": {"Id": path.parent.name}}), encoding="utf-8")
            self.assertEqual(len(hide_breeze.verify(root)), 3, "an unhidden wrapper must be reported")
            hide_breeze.hide(root)
            first = [p.read_text(encoding="utf-8") for p in hide_breeze.metadata_paths(root)]
            hide_breeze.hide(root)
            self.assertEqual(first, [p.read_text(encoding="utf-8") for p in hide_breeze.metadata_paths(root)])
            self.assertEqual(hide_breeze.verify(root), [])
            self.assertEqual(hide_breeze.main(["x", str(root)]), 0)

    def test_the_edits_it_makes_are_the_edits_the_seam_gate_accepts(self):
        edited = {"/" + str(p.relative_to("/")) for p in hide_breeze.metadata_paths(Path("/"))}
        registered = {path for path in plasma_seams.REGISTERED_EDITS if "/look-and-feel/" in path}
        self.assertEqual(edited, registered)

    def test_the_rpm_lines_that_failed_ci_now_pass(self):
        verify = {"plasma-workspace": "".join(
            f"S.5....T.    /usr/share/plasma/look-and-feel/{name}/metadata.json\n"
            for name in hide_breeze.WRAPPERS)}
        gate = TheGateRefuses("run_gate")
        gate.setUp()
        try:
            gate.run_gate("6.7.5", gate.reviewed("6.7"), verify)
        finally:
            gate.tearDown()

# Lines captured from kscreenlocker_greet on the ARM station, 2026-09-24 (Plasma 6.7.5).
CLEAN_RUN = [
    "kf.windowsystem: Could not find any platform plugin",
    'Couldn\'t start kglobalaccel from org.kde.kglobalaccel.service: QDBusError("org.freedesktop.DBus.Error.Disconnected", "Not connected to D-Bus server")',
    "file:///usr/lib64/qt6/qml/org/moos/ui/Tokens.qml:302:50: QML Settings: The Settings type from Qt.labs.settings is deprecated and will be removed in a future release. Please use the one from QtCore instead.",
    "This plugin does not support raise()",
    "Locked at 1790233193",
]
BROKEN_RUN = [
    "QQmlComponent: Component is not ready",
    ' "Error loading QML file.\\n25: Type LockScreenUi unavailable\\n675: VirtualKeyboardLoaderRemovedIn68 is not a type\\n"',
    "kscreenlocker_greet: Failed to load lockscreen QML, falling back to built-in locker",
    "kscreenlocker_greet: file:///tmp/p/contents/lockscreen/LockScreenUi.qml:675:9: VirtualKeyboardLoaderRemovedIn68 is not a type ",
    "Locked at 1790233218",
]


class TheProbeReadsTheGreeter(unittest.TestCase):
    def test_a_clean_greeter_passes(self):
        self.assertEqual(plasma_seams.classify_greeter_output(CLEAN_RUN), [])

    def test_the_measured_six_eight_failure_fails(self):
        bad = plasma_seams.classify_greeter_output(BROKEN_RUN)
        self.assertTrue(any("Failed to load lockscreen QML" in line for line in bad))
        self.assertTrue(any("is not a type" in line for line in bad))

    def test_script_errors_count_only_in_moos_owned_files(self):
        upstream = "file:///usr/share/plasma/look-and-feel/x/Foo.qml:3: TypeError: Cannot read property 'x' of null"
        ours = "file:///usr/share/plasma/shells/org.kde.plasma.desktop/contents/lockscreen/LockScreenUi.qml:40: ReferenceError: accentB is not defined"
        self.assertEqual(plasma_seams.classify_greeter_output([upstream]), [])
        self.assertEqual(plasma_seams.classify_greeter_output([ours]), [ours])

    def test_the_probe_cannot_reach_a_live_session(self):
        source = (ROOT / "build_files/plasma_seams.py").read_text(encoding="utf-8")
        body = source[source.index("def probe_lockscreen"):source.index("def main")]
        self.assertIn('"DBUS_SESSION_BUS_ADDRESS": f"unix:path={dirs[\'runtime\']}/no-bus"', body)
        self.assertIn('"QT_QPA_PLATFORM": "offscreen"', body)
        self.assertIn("env=env", body)
        self.assertNotIn("os.environ", body, "the greeter must not inherit the caller's session")
        for var in ("HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_RUNTIME_DIR"):
            self.assertIn(f'"{var}": str(dirs[', body, var)

    @unittest.skipUnless(os.access(plasma_seams.GREETER, os.X_OK), "kscreenlocker is not installed here")
    def test_the_real_greeter_loads_the_installed_lock_screen_and_refuses_a_broken_one(self):
        ok, lines = plasma_seams.probe_lockscreen(timeout=40)
        self.assertTrue(ok, "\n".join(lines))
        shell = Path("/usr/share/plasma/shells/org.kde.plasma.desktop")
        with tempfile.TemporaryDirectory(prefix="moos-seams-broken-") as tmp:
            broken = Path(tmp) / "shell"
            shutil.copytree(shell, broken, symlinks=True)
            ui = broken / "contents/lockscreen/LockScreenUi.qml"
            ui.chmod(0o644)
            text = ui.read_text(encoding="utf-8")
            text, n = re.subn(r"^(\s*)(RejectPasswordAnimation|WallpaperFader|MainBlock) \{",
                              r"\1MoOSTypeThatDoesNotExist {", text, count=1, flags=re.M)
            self.assertEqual(n, 1, "no instantiation to break in the installed lock screen")
            ui.write_text(text, encoding="utf-8")
            ok, lines = plasma_seams.probe_lockscreen(str(broken), timeout=40)
            self.assertFalse(ok, "the probe passed a lock screen that instantiates a missing type")
            self.assertTrue(any("is not a type" in line for line in lines), "\n".join(lines))


if __name__ == "__main__":
    unittest.main(verbosity=2)
