#!/usr/bin/env python3
"""Gate: MoOS's forks of Plasma files are keyed to the Plasma they were reviewed against.

WHY THIS EXISTS (plan row P6.7)

MoOS replaces twelve files inside plasma-desktop and plasma-workspace. tests/test_plasma_shell_overlay.py
proves the build checks those files SURVIVED; nothing proved they still FIT. The base tag moves by
itself, and on 2026-09-24 Plasma 6.8 beta 1 was measured to remove `VirtualKeyboardLoader` from
org.kde.breeze.components while the 6.7 LockScreenUi.qml MoOS then forked instantiated it:
kscreenlocker's real greeter printed "Failed to load lockscreen QML, falling back to built-in locker".

build_files/plasma_seams.py now selects a reviewed set per Plasma version, refuses upstream drift
and unregistered modifications (from rpm, not memory), and loads the real greeter. This test holds
the registry to the tree and proves every refusal actually refuses.

Since 2026-10-05 the registry also holds a boundary: MoOS forks NO file that carries authentication.
LockScreenUi.qml and MainBlock.qml are upstream's own, on every Plasma, and the MoOS session design
lives in the breeze components both greeters instantiate — files that never see a password or an
authenticator. `NoAuthenticationFileIsForked` below is that boundary.
"""

from __future__ import annotations

import difflib
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
# Which package rpm says owns a path: every seam, and every module qmldir a seam relies on.
PACKAGE_OF = {s["path"]: s["package"] for s in REGISTRY["seams"]}
PACKAGE_OF.update({s["qmldir"]: s["package"] for s in REGISTRY["seams"] if s.get("qmldir")})
KEYBOARD_SEAMS = [s["path"] for s in REGISTRY["seams"] if s["package"] == "plasma-keyboard"]
# plasma-keyboard 6.8.3-1.fc44's two module qmldirs, byte for byte (rpm digests in set 6.8.3).
KEYBOARD_QMLDIRS = {
    "/usr/lib64/qt6/qml/org/kde/plasma/keyboard/lib/qmldir": (
        "module org.kde.plasma.keyboard.lib\nlinktarget keyboardlib\noptional plugin keyboardlib\n"
        "classname org_kde_plasma_keyboard_libPlugin\ntypeinfo keyboardlib.qmltypes\ndepends QtQuick\n"
        "prefer :/qt/qml/org/kde/plasma/keyboard/lib/\nBreezeKeyPanel 254.0 BreezeKeyPanel.qml\n"
        "singleton BreezeConstants 254.0 BreezeConstants.qml\nBreezePopup 254.0 BreezePopup.qml\n\n"),
    "/usr/lib64/qt6/qml/QtQuick/VirtualKeyboard/Styles/Breeze/qmldir": (
        "module QtQuick.VirtualKeyboard.Styles.Breeze\nlinktarget breezestyle\n"
        "optional plugin breezestyle\nclassname QtQuick_VirtualKeyboard_Styles_BreezePlugin\n"
        "typeinfo breezestyle.qmltypes\ndepends QtQuick\n"
        "prefer :/qt/qml/QtQuick/VirtualKeyboard/Styles/Breeze/\n\n"),
}
SYSTEM = ROOT / "system_files"
LOCK = "/usr/share/plasma/shells/org.kde.plasma.desktop/contents/lockscreen"
COMPONENTS = "/usr/lib64/qt6/qml/org/kde/breeze/components"
SESSION_SCREEN = f"{COMPONENTS}/SessionManagementScreen.qml"
BACKDROP = f"{COMPONENTS}/WallpaperFader.qml"
# The two lock-screen files that carry the authenticator wiring. Upstream's, never MoOS's.
AUTH_FILES = (f"{LOCK}/LockScreenUi.qml", f"{LOCK}/MainBlock.qml")
# Files MoOS ADDS beside Plasma's (rpm owns none of them, so no upstream can drift under them).
# None today: the lock screen's own clock and its two images went with the fork that used them.
MOOS_ADDITIONS: set[str] = set()
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
        # Version-specific replacements are installed by their reviewed set,
        # never copied into older packages by the common filesystem overlay.
        replaced |= {path for chosen in REGISTRY['sets'] for path in chosen['sources']}
        shipped |= replaced
        self.assertTrue(replaced, "no Plasma-owned files under system_files: the scan is looking elsewhere")
        self.assertEqual(sorted(replaced - set(SEAM_PATHS)), [],
                         "MoOS replaces these Plasma files without a seam: the next Plasma would "
                         "never be reviewed for them")
        self.assertEqual(sorted(set(SEAM_PATHS) - shipped), [],
                         "seams.json names files MoOS does not ship")

    def test_every_set_reviews_every_seam_with_real_digests(self):
        for chosen in REGISTRY["sets"]:
            active = [s['path'] for s in plasma_seams.active_seams(REGISTRY, chosen)]
            self.assertEqual(sorted(chosen["reviewed"]), sorted(active),
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
        cases = {"6.7.0": "6.7", "6.7.5": "6.7", "6.7.91": "6.8-beta2", "6.8.0": "6.8.0", "6.8.1": "6.8.1", "6.8.2": "6.8.2", "6.8.3": "6.8.3"}
        for version, expected in cases.items():
            self.assertEqual(plasma_seams.select_set(REGISTRY, version)["id"], expected, version)
        # 6.7.90 (6.8 beta 1) had a set until 2026-10-05. Its lock-screen variants went with the
        # fork, and no beta-1 stack exists to load the greeter on, so it is unreviewed again.
        for version in ("6.6.5", "6.7.90", "6.8.6", "6.8.90", "6.9.0", "7.0.0"):
            with self.assertRaises(plasma_seams.SeamError, msg=version):
                plasma_seams.select_set(REGISTRY, version)

    def test_both_builds_run_the_seam_gate_before_the_survival_gate(self):
        for script in ("build.sh", "build-arm.sh"):
            text = code((ROOT / "build_files" / script).read_text(encoding="utf-8"))
            call = text.find("python3 /ctx/plasma_seams.py build")
            survival = text.find('"/usr/share/plasma/shells/org.kde.plasma.desktop/contents/lockscreen/MediaControls.qml:org.moos.ui"')
            self.assertGreater(call, 0, f"{script} never runs the seam gate")
            self.assertGreater(survival, call, f"{script} checks survival before the seams are installed")
            # A Plasma transaction after the gate could restore upstream bytes under the review.
            self.assertNotRegex(text[call:], r"dnf5? -y (install|reinstall|upgrade)[^\n]*\b(plasma|kscreenlocker|kwin)",
                                f"{script} changes a Plasma package after the seam gate")


class NoAuthenticationFileIsForked(unittest.TestCase):
    """The lock screen's LockScreenUi.qml and MainBlock.qml are upstream's, on every Plasma."""

    def test_the_tree_ships_neither_file(self):
        for path in AUTH_FILES:
            self.assertFalse((SYSTEM / path.lstrip("/")).exists(),
                             f"system_files replaces {path}: it carries the authenticator wiring and "
                             "upstream rewrites it every release — restyle the breeze components")

    def test_no_set_reviews_or_installs_either_file(self):
        self.assertFalse(set(AUTH_FILES) & set(SEAM_PATHS), "an authentication file is a seam again")
        for chosen in REGISTRY["sets"]:
            for path in AUTH_FILES:
                self.assertNotIn(path, chosen["reviewed"], chosen["id"])
                self.assertNotIn(path, chosen["sources"], chosen["id"])
        variants = [p for p in (ROOT / "build_files/plasma-seams").rglob("*.qml")
                    if p.name in ("LockScreenUi.qml", "MainBlock.qml")]
        self.assertEqual(variants, [], "a seam variant would install a fork of an authentication file")

    def test_both_builds_refuse_a_fork_in_the_finished_image(self):
        for script in ("build.sh", "build-arm.sh"):
            text = code((ROOT / "build_files" / script).read_text(encoding="utf-8"))
            gate = text[text.find("for _f in LockScreenUi.qml MainBlock.qml; do"):]
            self.assertTrue(gate.startswith("for _f in"), f"{script} no longer holds the boundary")
            gate = gate[:gate.index("unset -v _f")]
            self.assertIn('grep -q -e "org.moos" -e "Moalfarras" "$_f"', gate, script)
            self.assertIn("exit 1", gate, script)

    def test_the_session_design_carries_no_authentication(self):
        # What replaced the forks must not grow the thing the forks were retired for.
        names = ("SessionManagementScreen.qml", "WallpaperFader.qml", "Clock.qml",
                 "UserList.qml", "UserDelegate.qml", "ActionButton.qml")
        sources = [SYSTEM / COMPONENTS.lstrip("/") / name for name in names]
        sources += [p for p in (ROOT / "build_files/plasma-seams").rglob("*.qml")
                    if p.name in names]
        for source in sources:
            text = qml_code(source.read_text(encoding="utf-8"))
            for wiring in ("authenticator", "Authenticator", "PasswordSync", "kcheckpass",
                           ".respond(", "startAuthenticating", "loginRequest", ".text ="):
                self.assertNotIn(wiring, text,
                                 f"{source.relative_to(ROOT)} touches {wiring!r}: the session design "
                                 "may paint the password row, never read or drive it")


class TheSixEightSetFitsSixEight(unittest.TestCase):
    """Static half of what the canary and the real greeter prove on 6.8."""

    def variant(self, path: str, set_id: str = "6.8-beta2") -> str:
        chosen = next(s for s in REGISTRY["sets"] if s["id"] == set_id)
        return (ROOT / "build_files/plasma-seams" / chosen["sources"][path]).read_text(encoding="utf-8")

    def test_upstream_six_eight_additions_are_kept(self):
        # 6.7.90 gave the session screen an authentication-type indicator and rewrote the
        # backdrop's footer state change; both are upstream's, taken verbatim.
        for set_id in ("6.8-beta2",):
            screen = qml_code(self.variant(SESSION_SCREEN, set_id))
            for kept in ("property Item authenticationTypeItem: null",
                         "visible: root.authenticationTypeItem !== null",
                         "children: [root.authenticationTypeItem]"):
                self.assertIn(kept, screen, f"the {set_id} session screen lost upstream's {kept!r}")
            backdrop = qml_code(self.variant(BACKDROP, set_id))
            self.assertEqual(backdrop.count("target: footer"), 2, set_id)
            self.assertNotIn("footer.opacity:", backdrop, set_id)

    def test_the_six_seven_files_do_not_carry_six_eight_api(self):
        # The other direction: a 6.8 file left at the 6.7 path would still load, and hide the drift.
        screen = qml_code((SYSTEM / SESSION_SCREEN.lstrip("/")).read_text(encoding="utf-8"))
        self.assertNotIn("authenticationTypeItem", screen)
        backdrop = qml_code((SYSTEM / BACKDROP.lstrip("/")).read_text(encoding="utf-8"))
        self.assertEqual(backdrop.count("footer.opacity:"), 2)

    def test_the_variants_differ_from_six_seven_only_by_upstream(self):
        # Comments aside, a variant IS MoOS's 6.7 file plus upstream's own 6.7.5 -> 6.7.90 hunks,
        # line for line. The design cannot fork between Plasma versions, and a hunk nobody
        # reviewed cannot ride in on a variant.
        upstream = {
            SESSION_SCREEN: sorted([
                "+property Item authenticationTypeItem: null",
                "+RowLayout {",
                "+Layout.maximumWidth: Kirigami.Units.gridUnit * 16",
                "+Layout.alignment: Qt.AlignHCenter",
                "+Layout.fillWidth: true",
                "+Layout.fillHeight: false",
                "+Layout.topMargin: Kirigami.Units.largeSpacing",
                "+spacing: 0",
                "+visible: root.authenticationTypeItem !== null",
                "+children: [root.authenticationTypeItem]",
                "+}",
            ]),
            BACKDROP: sorted([
                "-footer.opacity: 1", "-footer.opacity: 0",
                "+PropertyChanges {", "+target: footer", "+opacity: 1", "+}",
                "+PropertyChanges {", "+target: footer", "+opacity: 0", "+}",
            ]),
        }
        for path, expected in upstream.items():
            base = [line.strip() for line in
                    qml_code((SYSTEM / path.lstrip("/")).read_text(encoding="utf-8")).splitlines()]
            other = [line.strip() for line in qml_code(self.variant(path)).splitlines()]
            changed = sorted(line[0] + line[1:].strip()
                             for line in difflib.unified_diff(base, other, lineterm="", n=0)
                             if line[:1] in "+-" and line[:3] not in ("+++", "---")
                             and line[1:].strip())
            self.assertEqual(changed, expected,
                             f"{path}: the 6.8 variant differs from MoOS's 6.7 file by more "
                             "than upstream's own change")

    def test_the_moos_markers_hold_for_the_variants_too(self):
        # verify_image_experience.py checks this marker on whatever the seam gate installed.
        for path in (SESSION_SCREEN, BACKDROP):
            self.assertIn("MoOS", self.variant(path))
            self.assertIn("org.moos.ui", self.variant(path))

    def test_no_merge_residue(self):
        for path in (SESSION_SCREEN, BACKDROP):
            for marker in ("<<<<<<<", "=======\n", ">>>>>>>"):
                self.assertNotIn(marker, self.variant(path), path)


def fake_rpm(version: str, digests: dict[str, str], verify: dict[str, str]):
    """Patch the three rpm readers plasma_seams uses."""
    def rpm(*args, root="/"):
        if args[:2] == ("-q", "--qf") and args[2] == "%{VERSION}":
            return version
        if args[:2] == ("-q", "--qf") and args[2] == "%{FILEDIGESTALGO}":
            return "8"
        if args[:2] == ("-q", "--qf"):
            package = args[3]
            owned = {p: d for p, d in digests.items() if PACKAGE_OF[p] == package}
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
            if not (SYSTEM / path.lstrip('/')).is_file():
                # A version-specific seam arrives only from its reviewed set.
                continue
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
        before = {p: (self.root / p.lstrip("/")).read_bytes() for p in SEAM_PATHS
                  if (self.root / p.lstrip('/')).is_file()}
        report = self.run_gate("6.7.5", self.reviewed("6.7"))
        self.assertIn("seam set 6.7", report[0])
        for p in before:
            self.assertEqual((self.root / p.lstrip("/")).read_bytes(), before[p], p)
        self.assertFalse((self.root / 'usr/share/plasma/shells/org.kde.plasma.desktop/contents/logout/LogoutControls.qml').exists())

    def test_current_power_controls_install_only_with_exact_reviewed_rpm(self):
        path = '/usr/share/plasma/shells/org.kde.plasma.desktop/contents/logout/LogoutControls.qml'
        self.run_gate('6.8.1', self.reviewed('6.8.1'))
        target = self.root / path.lstrip('/')
        self.assertEqual(target.read_bytes(), (ROOT/'build_files/plasma-seams/6.8.1'/path.lstrip('/')).read_bytes())
        digests = self.reviewed('6.8.1'); digests[path] = 'a'*64
        with self.assertRaisesRegex(plasma_seams.SeamError, 'Upstream changed'):
            self.run_gate('6.8.1', digests)

    def test_inactive_power_modification_still_fails_the_generic_gate(self):
        path = '/usr/share/plasma/shells/org.kde.plasma.desktop/contents/logout/LogoutControls.qml'
        with self.assertRaisesRegex(plasma_seams.SeamError, 'neither a registered seam'):
            self.run_gate('6.7.5', self.reviewed('6.7'), {'plasma-desktop': 'S.5....T.    '+path})

    def test_invalid_scopes_or_missing_variant_are_never_a_gate_bypass(self):
        def power(data):
            return next(s for s in data['seams'] if s['path'].endswith('/logout/LogoutControls.qml'))
        for scopes in ([], ['unknown'], ['6.8.1','6.8.1'], '6.8.1', [1]):
            data = json.loads(json.dumps(REGISTRY))
            power(data)['sets'] = scopes
            with self.assertRaises(plasma_seams.SeamError):
                plasma_seams.active_seams(data, next(s for s in data['sets'] if s['id']=='6.8.1'))
        data = json.loads(json.dumps(REGISTRY))
        chosen = next(s for s in data['sets'] if s['id']=='6.8.1')
        del chosen['sources'][power(data)['path']]
        with self.assertRaisesRegex(plasma_seams.SeamError, 'no installed variant'):
            plasma_seams.active_seams(data, chosen)

    def test_six_eight_installs_its_variants(self):
        self.run_gate("6.7.91", self.reviewed("6.8-beta2"))
        chosen = next(s for s in REGISTRY["sets"] if s["id"] == "6.8-beta2")
        for path, source in chosen["sources"].items():
            self.assertEqual((self.root / path.lstrip("/")).read_bytes(),
                             (ROOT / "build_files/plasma-seams" / source).read_bytes(), path)

    def test_beta_two_installs_the_session_screen_reviewed_for_it(self):
        # Beta 2 changed only LockScreenUi.qml, which MoOS no longer replaces: its set reviews the
        # same upstream bytes as beta 1 and installs the same two component variants.
        self.run_gate("6.7.91", self.reviewed("6.8-beta2"))
        text = (self.root / SESSION_SCREEN.lstrip("/")).read_text()
        self.assertIn("property Item authenticationTypeItem: null", text)
        self.assertIn("children: [root.authenticationTypeItem]", text)
        backdrop = (self.root / BACKDROP.lstrip("/")).read_text()
        self.assertIn("target: footer", backdrop)

    def test_upstream_drift_is_refused(self):
        digests = self.reviewed("6.7")
        digests[SESSION_SCREEN] = hashlib.sha256(b"a 6.7.6 bug fix").hexdigest()
        with self.assertRaisesRegex(plasma_seams.SeamError,
                                    "SessionManagementScreen.qml.*Upstream changed"):
            self.run_gate("6.7.6", digests)

    def test_six_eight_bytes_under_a_six_seven_version_are_refused(self):
        # The exact case this gate exists for: 6.8's session screen, judged by the 6.7 review.
        digests = self.reviewed("6.7")
        self.assertNotEqual(digests[SESSION_SCREEN], self.reviewed("6.8-beta2")[SESSION_SCREEN])
        digests[SESSION_SCREEN] = self.reviewed("6.8-beta2")[SESSION_SCREEN]
        with self.assertRaises(plasma_seams.SeamError):
            self.run_gate("6.7.5", digests)

    def test_six_seven_bytes_under_a_six_eight_version_are_refused(self):
        digests = self.reviewed("6.8-beta2")
        digests[BACKDROP] = self.reviewed("6.7")[BACKDROP]
        with self.assertRaises(plasma_seams.SeamError):
            self.run_gate("6.7.91", digests)

    def test_beta_one_is_unreviewed_again(self):
        with self.assertRaisesRegex(plasma_seams.SeamError, "no reviewed MoOS seam set"):
            self.run_gate("6.7.90", self.reviewed("6.8-beta2"))

    def test_a_file_upstream_stopped_shipping_is_refused(self):
        digests = self.reviewed("6.7")
        del digests[BACKDROP]
        with self.assertRaisesRegex(plasma_seams.SeamError, "no longer ships"):
            self.run_gate("6.7.5", digests)

    # ── plasma-keyboard: Plasma's on-screen keyboard, restyled for 6.8.3 ─────────────────
    def plant_keyboard_qmldirs(self):
        for path, text in KEYBOARD_QMLDIRS.items():
            target = self.root / path.lstrip("/")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")

    def keyboard_digests(self):
        chosen = next(s for s in REGISTRY["sets"] if s["id"] == "6.8.3")
        digests = self.reviewed("6.8.3")
        digests.update({path: reviewed[0] for path, reviewed in chosen["qmldirs"].items()})
        return digests

    def test_the_upstream_qmldirs_here_are_the_reviewed_bytes(self):
        chosen = next(s for s in REGISTRY["sets"] if s["id"] == "6.8.3")
        self.assertEqual(sorted(chosen["qmldirs"]), sorted(KEYBOARD_QMLDIRS))
        self.assertEqual(sorted({s["qmldir"] for s in REGISTRY["seams"] if s.get("qmldir")}),
                         sorted(KEYBOARD_QMLDIRS))
        for path, text in KEYBOARD_QMLDIRS.items():
            self.assertIn(hashlib.sha256(text.encode()).hexdigest(), chosen["qmldirs"][path], path)
            self.assertEqual(sum(line.startswith("prefer ") for line in text.splitlines()), 1, path)

    def test_six_eight_three_restyles_the_keyboard_and_reads_it_from_disk(self):
        self.plant_keyboard_qmldirs()
        report = self.run_gate("6.8.3", self.keyboard_digests())
        chosen = next(s for s in REGISTRY["sets"] if s["id"] == "6.8.3")
        self.assertEqual(sum(path.startswith("/usr/lib64/") for path in KEYBOARD_SEAMS), 4)
        self.assertEqual(sum("/layouts/" in path for path in KEYBOARD_SEAMS), 13)
        for path in KEYBOARD_SEAMS:
            self.assertEqual((self.root / path.lstrip("/")).read_bytes(),
                             (ROOT / "build_files/plasma-seams" / chosen["sources"][path]).read_bytes(), path)
        for path, text in KEYBOARD_QMLDIRS.items():
            self.assertEqual((self.root / path.lstrip("/")).read_text(encoding="utf-8"),
                             "".join(line for line in text.splitlines(keepends=True)
                                     if not line.startswith("prefer ")), path)
        self.assertEqual(sum("dropped `prefer`" in line for line in report), 2, report)

    def test_a_keyboard_qmldir_upstream_changed_is_refused(self):
        self.plant_keyboard_qmldirs()
        digests = self.keyboard_digests()
        digests[next(iter(KEYBOARD_QMLDIRS))] = "b" * 64
        with self.assertRaisesRegex(plasma_seams.SeamError, "changed how this module resolves"):
            self.run_gate("6.8.3", digests)

    def test_an_unreviewed_keyboard_qmldir_is_refused(self):
        self.plant_keyboard_qmldirs()
        data = json.loads(json.dumps(REGISTRY))
        del next(s for s in data["sets"] if s["id"] == "6.8.3")["qmldirs"]
        a, b = fake_rpm("6.8.3", self.keyboard_digests(), {})
        with a, b, self.assertRaisesRegex(plasma_seams.SeamError, "reviewed nothing"):
            plasma_seams.apply_and_verify(data, str(self.root))

    def test_a_keyboard_qmldir_is_edited_once_and_only_from_upstream_bytes(self):
        self.plant_keyboard_qmldirs()
        self.run_gate("6.8.3", self.keyboard_digests())
        with self.assertRaisesRegex(plasma_seams.SeamError, "already ran"):
            self.run_gate("6.8.3", self.keyboard_digests())

    def test_six_seven_never_touches_the_keyboard(self):
        self.plant_keyboard_qmldirs()
        self.run_gate("6.7.5", self.reviewed("6.7"))
        for path, text in KEYBOARD_QMLDIRS.items():
            self.assertEqual((self.root / path.lstrip("/")).read_text(encoding="utf-8"), text, path)
        for path in KEYBOARD_SEAMS:
            self.assertFalse((self.root / path.lstrip("/")).exists(), path)
        verify = {"plasma-keyboard": f"S.5....T.    {next(iter(KEYBOARD_QMLDIRS))}\n"}
        with self.assertRaisesRegex(plasma_seams.SeamError, "neither a registered seam"):
            self.run_gate("6.7.5", self.reviewed("6.7"), verify)

    def test_rpm_accounts_for_every_keyboard_edit_on_six_eight_three(self):
        self.plant_keyboard_qmldirs()
        verify = {"plasma-keyboard": "".join(f"S.5....T.    {path}\n"
                                             for path in [*KEYBOARD_SEAMS, *KEYBOARD_QMLDIRS])}
        self.run_gate("6.8.3", self.keyboard_digests(), verify)
        verify["plasma-keyboard"] += "S.5....T.    /usr/share/plasma/keyboard/layouts/de_DE/main.qml\n"
        self.plant_keyboard_qmldirs()
        with self.assertRaisesRegex(plasma_seams.SeamError, "de_DE/main.qml.*neither a registered seam"):
            self.run_gate("6.8.3", self.keyboard_digests(), verify)

    def test_an_unreviewed_plasma_is_refused(self):
        with self.assertRaisesRegex(plasma_seams.SeamError, "no reviewed MoOS seam set"):
            self.run_gate("6.8.90", self.reviewed("6.8-beta2"))

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


# plasma-keyboard 6.8.3 offscreen with MoOS's style, outside KWin (V3, 2026-11-22).
CLEAN_KEYBOARD = [
    "qt.qml.propertyCache.append: Member contentWidth of the object PopupList_QMLTYPE_47 overrides a member of the base object. Consider renaming it or adding final or override specifier",
    "kf.windowsystem: Could not find any platform plugin",
    "Failed to create wl_display (No such file or directory)",
    "OverlayWindow_QMLTYPE_87(0x563a9ab39050) is not a wayland window. Not creating input panel surface.",
    "InputPanelWindow(0x563a9ab123b0) is not a wayland window. Not creating input panel surface.",
    "org.kde.plasma.keyboard: Cannot run plasma-keyboard standalone. You can enable it in Plasma's System Settings app, on the \u201cVirtual Keyboard\u201d page.",
]
# The first MoOS popup draft read `theme` in a child before the style assigned it (measured).
NULL_THEME = "file:///usr/lib64/qt6/qml/org/kde/plasma/keyboard/lib/BreezePopup.qml:41:9: TypeError: Cannot read property 'popupRadius' of null"
BROKEN_KEYBOARD = [
    "file:///usr/lib64/qt6/qml/org/kde/plasma/keyboard/lib/BreezeKeyPanel.qml:89:5: MoosNoSuchKeyType is not a type",
    "qrc:/qt/qml/org/kde/plasma/keyboard/LanguagePopupDelegate.qml:59: TypeError: Cannot read property 'scaleHint' of null",
    "file:///usr/lib64/qt6/qml/org/kde/plasma/keyboard/lib/BreezeConstants.qml:81: ReferenceError: moosNoSuchScale is not defined",
    NULL_THEME,
]


class TheKeyboardProbeReadsPlasmaKeyboard(unittest.TestCase):
    def test_a_clean_keyboard_passes(self):
        self.assertEqual(plasma_seams.keyboard_problems(1, CLEAN_KEYBOARD), [])

    def test_the_measured_failures_fail(self):
        for line in BROKEN_KEYBOARD:
            self.assertEqual(plasma_seams.classify_keyboard_output([line]), [line])
            self.assertTrue(plasma_seams.keyboard_problems(1, [*CLEAN_KEYBOARD, line]))

    def test_an_unfinished_or_crashed_keyboard_fails(self):
        self.assertTrue(plasma_seams.keyboard_problems(1, CLEAN_KEYBOARD[:-1]))
        self.assertTrue(plasma_seams.keyboard_problems(-11, CLEAN_KEYBOARD))
        self.assertTrue(plasma_seams.keyboard_problems(None, CLEAN_KEYBOARD))

    def test_script_errors_elsewhere_are_not_the_keyboards(self):
        line = "file:///usr/share/plasma/look-and-feel/x/Foo.qml:3: TypeError: Cannot read property 'x' of null"
        self.assertEqual(plasma_seams.classify_keyboard_output([line]), [])

    def test_the_build_runs_it_only_where_the_set_restyles_the_keyboard(self):
        for version, expected in (("6.8.3", True), ("6.8.2", False), ("6.7.5", False)):
            with mock.patch.object(plasma_seams, "package_version", lambda pkg, root="/": version):
                self.assertEqual(plasma_seams.restyles_keyboard(REGISTRY), expected, version)


def native_keyboard_version() -> str | None:
    if not os.access(plasma_seams.KEYBOARD, os.X_OK) or not shutil.which("rpm"):
        return None
    try:
        return plasma_seams.package_version("plasma-keyboard")
    except plasma_seams.SeamError:
        return None


@unittest.skipUnless(native_keyboard_version() == "6.8.3",
                     "needs native plasma-keyboard 6.8.3; both image builds run this probe")
class TheRealKeyboardLoadsTheseFiles(unittest.TestCase):
    """The real plasma-keyboard, offscreen and isolated, with this tree's style in a shadow copy."""

    def overlay(self, popup: Path | None = None) -> dict[str, Path]:
        chosen = next(s for s in REGISTRY["sets"] if s["id"] == "6.8.3")
        files = {path: ROOT / "build_files/plasma-seams" / chosen["sources"][path] for path in KEYBOARD_SEAMS}
        if popup is not None:
            files[next(p for p in KEYBOARD_SEAMS if p.endswith("/BreezePopup.qml"))] = popup
        return files

    def run_shadow(self, tmp: Path, name: str, **kwargs) -> tuple[Path, int | None, list[str]]:
        shadow = plasma_seams.shadow_keyboard_modules(tmp / name, **kwargs)
        status, lines = plasma_seams.run_keyboard(shadow, timeout=60)
        return shadow, status, lines

    def test_the_style_loads_clean_and_a_planted_error_is_seen(self):
        with tempfile.TemporaryDirectory(prefix="moos-kbt-") as tmp:
            _shadow, status, lines = self.run_shadow(Path(tmp), "clean", overlay=self.overlay())
            self.assertEqual(plasma_seams.keyboard_problems(status, lines), [], "\n".join(lines))
            shadow, _status, lines = self.run_shadow(Path(tmp), "planted", overlay=self.overlay(), plant=True)
            self.assertTrue(any(plasma_seams.KEYBOARD_CONTROL in line and str(shadow) in line
                                for line in lines), "\n".join(lines))

    def test_the_first_popup_drafts_null_theme_fails_for_real(self):
        source = self.overlay()[next(p for p in KEYBOARD_SEAMS if p.endswith("/BreezePopup.qml"))]
        fixed = source.read_text(encoding="utf-8")
        light = "x: popup.typingRightToLeft ? popup.squareRadius + 1 : popup.roundRadius * 0.7"
        self.assertIn(light, fixed)
        with tempfile.TemporaryDirectory(prefix="moos-kbt-") as tmp:
            draft = Path(tmp) / "BreezePopup.qml"
            draft.write_text(fixed.replace(light, "x: popup.typingRightToLeft ? popup.theme.squareRadius + 1"
                                                  " : popup.theme.popupRadius * 0.7"), encoding="utf-8")
            _shadow, status, lines = self.run_shadow(Path(tmp), "draft", overlay=self.overlay(draft))
            problems = plasma_seams.keyboard_problems(status, lines)
            self.assertTrue(any("BreezePopup.qml" in line and "of null" in line for line in problems),
                            "\n".join(lines))


class TheProbeReadsTheGreeter(unittest.TestCase):
    def test_a_clean_greeter_passes(self):
        self.assertEqual(plasma_seams.classify_greeter_output(CLEAN_RUN), [])

    def test_the_measured_six_eight_failure_fails(self):
        bad = plasma_seams.classify_greeter_output(BROKEN_RUN)
        self.assertTrue(any("Failed to load lockscreen QML" in line for line in bad))
        self.assertTrue(any("is not a type" in line for line in bad))

    def test_script_errors_count_only_in_moos_owned_files(self):
        upstream = "file:///usr/share/plasma/look-and-feel/x/Foo.qml:3: TypeError: Cannot read property 'x' of null"
        ours = "file:///usr/lib64/qt6/qml/org/kde/breeze/components/SessionManagementScreen.qml:40: ReferenceError: accentB is not defined"
        media = "file:///usr/share/plasma/shells/org.kde.plasma.desktop/contents/lockscreen/MediaControls.qml:9: TypeError: x"
        # Upstream's again since 2026-10-05, and so not MoOS's to judge with no session bus.
        theirs = "file:///usr/share/plasma/shells/org.kde.plasma.desktop/contents/lockscreen/LockScreenUi.qml:40: TypeError: Cannot read property 'x' of null"
        self.assertEqual(plasma_seams.classify_greeter_output([upstream]), [])
        self.assertEqual(plasma_seams.classify_greeter_output([theirs]), [])
        self.assertEqual(plasma_seams.classify_greeter_output([ours]), [ours])
        self.assertEqual(plasma_seams.classify_greeter_output([media]), [media])

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
