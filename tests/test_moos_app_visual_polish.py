#!/usr/bin/env python3
"""Release gate for first-party QML motion, palette and custom-control UX."""

from __future__ import annotations

import pathlib
import re
import unittest
import configparser


ROOT = pathlib.Path(__file__).resolve().parents[1]
QML = ROOT / "system_files/usr/share/moos/apps/moai/main.qml"
APPS = ROOT / "system_files/usr/share/moos/apps"
UI = APPS / "ui"
COLOR_SCHEMES = ROOT / "system_files/usr/share/color-schemes"


def qml_code(source: str) -> str:
    """Strip comments for structural counts; no contract below depends on strings."""
    return re.sub(r"/\*.*?\*/|//[^\n]*", "", source, flags=re.S)


class MoAIVisualPolishTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = QML.read_text(encoding="utf-8")
        cls.code = qml_code(cls.source)

    def test_every_hand_drawn_action_has_one_keyboard_and_at_seam(self) -> None:
        component = re.search(
            r"component\s+ActionArea\s*:\s*MouseArea\s*\{(.*?)\n\s*\}",
            self.code,
            re.S,
        )
        self.assertIsNotNone(component)
        contract = component.group(1)
        for token in (
            "activeFocusOnTab:",
            "Accessible.role:",
            "Accessible.name:",
            "Accessible.checked:",
            "Keys.onReturnPressed:",
            "Keys.onEnterPressed:",
            "Keys.onSpacePressed:",
            "signal triggered()",
        ):
            self.assertIn(token, contract)

        self.assertGreaterEqual(
            len(re.findall(r"\bActionArea\s*\{", self.code)),
            12,
            "rail, cards, picker choices and settings choices must remain "
            "keyboard/screen-reader reachable",
        )
        # Five are intentional: ActionArea's base and two modal backdrops plus
        # two click-swallowing card interiors. MoButton is now an
        # AbstractButton and must never add its own pointer-only MouseArea.
        self.assertEqual(
            len(re.findall(r"\bMouseArea\s*\{", self.code)),
            5,
            "a raw MouseArea was added instead of the accessible ActionArea",
        )

        button = re.search(
            r"component\s+MoButton\s*:\s*MoOSUi\.Button\s*\{(.*?)"
            r"component\s+ActionArea",
            self.code,
            re.S,
        )
        self.assertIsNotNone(button)
        for token in (
            "destructive: btn.danger",
            "enabled: btn.enabled_",
            "motionEnabled: root.motionEnabled",
            "surfaceColor: root.surface2",
            "accentColor: root.novaBlue",
        ):
            self.assertIn(token, button.group(1))

    def test_workspace_sidebar_expands_without_breaking_compact_layout(self) -> None:
        self.assertIn("readonly property bool workspaceSidebarExpanded: width >= 1120",
                      self.source)
        self.assertIn("? root.fs(188) : root.fs(76)", self.source)
        self.assertIn("root.typePx(root.workspaceSidebarExpanded ? 12 : 9)",
                      self.source)
        self.assertIn("visible: root.workspaceSidebarExpanded", self.source)
        self.assertIn("design.motionGeometry", self.source)
        self.assertNotIn("design.motionStructure", self.source)

    def test_visual_review_can_override_direction_without_changing_the_session(self) -> None:
        self.assertIn('argv.indexOf("--layout-direction")', self.source)
        self.assertIn('value === "rtl" || value === "ltr"', self.source)
        self.assertIn("LayoutMirroring.enabled: root.moaiRtl", self.source)
        self.assertEqual(self.source.count("Qt.application.layoutDirection"), 1)

    def test_settings_secrets_and_switches_have_screen_reader_labels(self) -> None:
        for object_id in ("keyField", "tokenField"):
            start = self.source.index(f"id: {object_id}")
            field = self.source[start:start + 800]
            self.assertIn("Accessible.name:", field)
            self.assertIn("Accessible.labelledBy:", field)
        for object_id in ("tgSwitch", "ttsSwitch", "webSwitch"):
            start = self.source.index(f"id: {object_id}")
            self.assertIn("Accessible.labelledBy:", self.source[start:start + 350])
        self.assertIn("Accessible.labelledBy: botDeviceControlLabel", self.source)
        self.assertGreaterEqual(self.source.count("Accessible.name: text"), 6)

    def test_modal_sheets_are_named_keyboard_dismissible_dialogs(self) -> None:
        for object_id in ("brainPickerDialog", "settingsDialog"):
            marker = f"id: {object_id}"
            start = self.code.index(marker)
            window = self.code[start:start + 900]
            with self.subTest(dialog=object_id):
                self.assertIn("focus: visible", window)
                self.assertIn("Accessible.role: Accessible.Dialog", window)
                self.assertIn("Accessible.name:", window)
                self.assertIn("Keys.onEscapePressed:", window)
                self.assertIn("forceActiveFocus()", window)

        self.assertGreaterEqual(
            self.source.count('label: root.local("إغلاق", "Close")'),
            2,
            "both modal sheets need a visible close action; backdrop clicks and "
            "Escape are supplementary, not the only exit",
        )

    def test_ambient_light_is_shared_palette_geometry_not_fixed_rasters(self) -> None:
        self.assertNotIn("glow-cyan.png", self.source)
        self.assertNotIn("glow-violet.png", self.source)
        ambient = self.source[
            self.source.index("id: ambient"):
            self.source.index("// ── Health")
        ]
        self.assertIn("MoOSUi.TidalHorizon {", ambient)
        for binding in (
            "surfaceColor: root.surface0",
            "primaryColor: root.novaBlue",
            "secondaryColor: root.novaViolet",
            "luminousColor: root.novaCyan",
            "motionEnabled: root.motionEnabled",
        ):
            self.assertIn(binding, ambient)
        horizon = (UI / "TidalHorizon.qml").read_text(encoding="utf-8")
        self.assertIn("fillGradient: LinearGradient", horizon)
        self.assertIn("PathMove {", horizon)
        self.assertIn("animateIn && motionEnabled", horizon)
        for forbidden in (
            "XAnimator on x",
            "SequentialAnimation on opacity",
            "SequentialAnimation on scale",
            "RotationAnimator on rotation",
            "Animation.Infinite",
        ):
            self.assertNotIn(
                forbidden,
                ambient,
                "the decorative Mo AI backdrop must stay static; state and "
                "interaction surfaces own motion",
            )

    def test_fixed_animation_durations_all_obey_reduced_motion(self) -> None:
        literal = re.findall(r"duration\s*:\s*\d+", self.code)
        self.assertFalse(
            literal,
            "fixed-duration animation bypasses the system animation setting: "
            + ", ".join(literal[:5]),
        )
        durations = re.findall(r"duration\s*:[^\n;}]+", self.code)
        self.assertGreaterEqual(len(durations), 20, "interactive motion system disappeared")
        for duration in durations:
            with self.subTest(duration=duration):
                self.assertIn(
                    "root.motionEnabled",
                    duration,
                    f"{duration} does not collapse when animations are disabled",
                )
        self.assertNotRegex(
            self.code,
            r"motionEnabled\s*\?\s*[^:\n;]+\s*:\s*0\s*\+",
            "the stagger was attached to the reduced-motion branch; `off` "
            "must evaluate to exactly zero",
        )

    def test_visible_copy_uses_one_session_language(self) -> None:
        visible_bilingual = re.findall(
            r"(?:text|label|placeholderText|goodText|badText)\s*:\s*"
            r'"[^"\n]*\|[^"\n]*"',
            self.code,
        )
        self.assertFalse(
            visible_bilingual,
            "visible text still stacks Arabic and English: "
            + ", ".join(visible_bilingual[:4]),
        )
        self.assertIn("function local(ar, en)", self.source)
        self.assertNotRegex(
            self.code,
            r"\.ar\s*\+\s*['\"][^'\"]*(?:\||·)[^'\"]*['\"]\s*\+\s*[^;\n]*\.en",
            "a model row still concatenates both languages",
        )


class FirstPartyAppMotionTests(unittest.TestCase):
    def test_every_fixed_app_transition_obeys_the_motion_setting(self) -> None:
        """Finite hover/sheet transitions must stop too, not only endless loops."""
        for app in ("welcome", "installer", "store"):
            path = ROOT / f"system_files/usr/share/moos/apps/{app}/main.qml"
            code = qml_code(path.read_text(encoding="utf-8"))
            durations = re.findall(r"duration\s*:[^\n;}]+", code)
            with self.subTest(app=app):
                self.assertGreater(
                    len(durations),
                    10,
                    f"{app} unexpectedly lost its designed transition system",
                )
                self.assertFalse(
                    re.findall(r"duration\s*:\s*\d+", code),
                    f"{app} has a fixed-duration transition that ignores "
                    "the user's reduced-motion setting",
                )
                for duration in durations:
                    self.assertIn(
                        "win.motionEnabled",
                        duration,
                        f"{app}: {duration} bypasses reduced motion",
                    )
                self.assertNotRegex(
                    code,
                    r"motionEnabled\s*\?\s*[^:\n;]+\s*:\s*0\s*\+",
                    f"{app}: reduced-motion false branch contains arithmetic",
                )

        welcome = (APPS / "welcome/main.qml").read_text(encoding="utf-8")
        installer = (APPS / "installer/main.qml").read_text(encoding="utf-8")
        self.assertGreaterEqual(
            len(re.findall(
                r"win\.motionEnabled\s*\?\s*2600\s*\+\s*ring\.index\s*\*\s*500\s*:\s*0",
                welcome,
            )),
            2,
        )
        self.assertGreaterEqual(
            len(re.findall(
                r"win\.motionEnabled\s*\?\s*2600\s*\+\s*ring\.index\s*\*\s*500\s*:\s*0",
                installer,
            )),
            2,
        )
        self.assertGreaterEqual(
            len(re.findall(
                r"win\.motionEnabled\s*\?\s*2200\s*\+\s*pring\.index\s*\*\s*400\s*:\s*0",
                installer,
            )),
            2,
        )


class SharedQmlDesignSystemTests(unittest.TestCase):
    def test_tokens_are_the_reviewed_app_contract_and_are_adopted(self) -> None:
        tokens = (UI / "Tokens.qml").read_text(encoding="utf-8")
        expected = {
            "space1": 4, "space2": 8, "space3": 12,
            "space4": 16, "space5": 24, "space6": 32,
            "radiusSmall": 8, "radiusControl": 12,
            "radiusCard": 16, "radiusPanel": 24,
            "typeCaption": 11, "typeSecondary": 13, "typeBody": 14,
            "typeLabel": 15, "typeTitle": 20, "typeHeadline": 24,
            "typeDisplay": 32,
            "motionFast": 120, "motionPress": 160,
            "motionGeometry": 220, "motionPage": 320,
        }
        for role, value in expected.items():
            with self.subTest(role=role):
                self.assertRegex(
                    tokens,
                    rf"readonly property int {role}:\s*{value}\b",
                )

        for app in ("welcome", "installer", "store", "moai"):
            source = (APPS / app / "main.qml").read_text(encoding="utf-8")
            with self.subTest(app=app):
                self.assertIn('import "../ui" as MoOSUi', source)
                self.assertIn("MoOSUi.Tokens { id: design }", source)
                self.assertIn("function typePx(px)", source)
                self.assertIn("component FocusRing: MoOSUi.FocusRing", source)
                self.assertGreaterEqual(source.count("design.space"), 4)
                self.assertGreaterEqual(source.count("design.radius"), 3)

    def test_all_functional_type_uses_the_role_ramp(self) -> None:
        for app in ("welcome", "installer", "store", "moai"):
            source = (APPS / app / "main.qml").read_text(encoding="utf-8")
            code = qml_code(source)
            declarations = re.findall(r"font\.pixelSize\s*:[^\n]+", code)
            with self.subTest(app=app):
                self.assertGreater(len(declarations), 40)
                self.assertNotRegex(code, r"font\.pixelSize\s*:\s*(?:win|root)\.fs\(")
                for declaration in declarations:
                    self.assertIn(
                        "typePx(",
                        declaration,
                        f"{app} bypasses the shared type ramp: {declaration}",
                    )

    def test_shared_button_is_semantic_and_destructive_pairing_is_safe(self) -> None:
        button = (UI / "Button.qml").read_text(encoding="utf-8")
        for token in (
            "QQC2.AbstractButton",
            "activeFocusOnTab: enabled && visible",
            "Accessible.role: Accessible.Button",
            "Accessible.name: label",
            "FocusRing {",
            "restingColor: primary ? accentColor : surfaceColor",
            "foregroundColor: !enabled ? mutedTextColor",
            ": primary ? accentForegroundColor",
            ": destructive ? dangerColor",
            "border.width: control.primary ? 0 : 1",
            "implicitHeight: compact ? tokens.targetCompact : tokens.targetControl",
        ):
            self.assertIn(token, button)
        self.assertNotIn("primary || destructive", button)
        self.assertNotIn("MouseArea", button)

        tokens_qml = (UI / "Tokens.qml").read_text(encoding="utf-8")
        self.assertIn("readonly property int targetCompact: 40", tokens_qml)
        self.assertIn("readonly property int targetControl: 44", tokens_qml)

        # The icon themes bake per-palette inks (FollowsColorScheme=false);
        # Buttons get their exact disabled/destructive/primary foregrounds
        # only because SymbolIcon renders the symbol as a mask. Without this
        # the app-side half of that contract can silently revert.
        symbol_icon = (UI / "SymbolIcon.qml").read_text(encoding="utf-8")
        self.assertIn("isMask: true", symbol_icon)
        self.assertIn("color: foreground", symbol_icon)

        for app, component in (
            ("welcome", "DeviceSettingsButton: MoOSUi.Button"),
            ("store", "ActionButton: MoOSUi.Button"),
            ("moai", "MoButton: MoOSUi.Button"),
        ):
            with self.subTest(app=app):
                source = (APPS / app / "main.qml").read_text(encoding="utf-8")
                self.assertIn(component, source)
                self.assertIn("surfaceColor:", source[source.index(component):])
                if app in ("store", "moai"):
                    self.assertIn("dangerColor:", source[source.index(component):])

    def test_negative_ink_contrast_on_every_app_surface(self) -> None:
        """Outlined destructive controls retain WCAG AA in every MoOS palette."""
        def rgb(value: str) -> tuple[int, int, int]:
            return tuple(int(part) for part in value.split(","))  # type: ignore[return-value]

        def channel(value: int) -> float:
            normalized = value / 255.0
            return (
                normalized / 12.92
                if normalized <= 0.04045
                else ((normalized + 0.055) / 1.055) ** 2.4
            )

        def luminance(color: tuple[int, int, int]) -> float:
            return (
                0.2126 * channel(color[0])
                + 0.7152 * channel(color[1])
                + 0.0722 * channel(color[2])
            )

        def contrast(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
            high, low = sorted((luminance(a), luminance(b)), reverse=True)
            return (high + 0.05) / (low + 0.05)

        schemes = sorted(COLOR_SCHEMES.glob("MoOSUI2*.colors"))
        self.assertGreaterEqual(len(schemes), 16)
        for path in schemes:
            config = configparser.ConfigParser(interpolation=None, strict=False)
            config.optionxform = str
            config.read(path, encoding="utf-8")
            for section in ("Colors:View", "Colors:Window"):
                negative = rgb(config[section]["ForegroundNegative"])
                for background_role in ("BackgroundNormal", "BackgroundAlternate"):
                    background = rgb(config[section][background_role])
                    ratio = contrast(negative, background)
                    with self.subTest(
                        scheme=path.name,
                        section=section,
                        background=background_role,
                    ):
                        self.assertGreaterEqual(
                            ratio,
                            4.5,
                            f"{path.name} {section} negative ink is only "
                            f"{ratio:.2f}:1 on {background_role}",
                        )


if __name__ == "__main__":
    unittest.main()
