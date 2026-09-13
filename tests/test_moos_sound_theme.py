#!/usr/bin/env python3
"""Product gate for the original MoOS system sound family."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest
import zlib


ROOT = Path(__file__).resolve().parents[1]
THEME = ROOT / "system_files/usr/share/sounds/moos"
STEREO = THEME / "stereo"

REQUIRED_EVENTS = {
    "alarm-clock-elapsed.oga",
    "audio-volume-change.oga",
    "battery-caution.oga",
    "battery-low.oga",
    "battery-full.oga",
    "bell-window-system.oga",
    "button-pressed.oga",
    "button-pressed-modifier.oga",
    "complete-download.oga",
    "completion-fail.oga",
    "completion-rotation.oga",
    "completion-success.oga",
    "desktop-login.oga",
    "desktop-logout.oga",
    "device-added.oga",
    "device-removed.oga",
    "dialog-error.oga",
    "dialog-error-critical.oga",
    "dialog-error-serious.oga",
    "dialog-information.oga",
    "dialog-question.oga",
    "dialog-warning.oga",
    "dialog-warning-auth.oga",
    "message-new-email.oga",
    "message-new-instant.oga",
    "outcome-failure.oga",
    "outcome-success.oga",
    "power-plug.oga",
    "power-unplug.oga",
    "service-login.oga",
    "service-logout.oga",
    "trash-empty.oga",
}

spec = importlib.util.spec_from_file_location(
    "moos_sound_gate", ROOT / "build_files/verify_sound_theme.py"
)
assert spec is not None and spec.loader is not None
sound_gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sound_gate)


def ogg_serials(payload: bytes) -> set[int]:
    serials: set[int] = set()
    offset = 0
    while offset < len(payload):
        if payload[offset:offset + 4] != b"OggS" or offset + 27 > len(payload):
            raise AssertionError(f"invalid Ogg page at byte {offset}")
        segment_count = payload[offset + 26]
        header_end = offset + 27 + segment_count
        page_end = header_end + sum(payload[offset + 27:header_end])
        serials.add(struct.unpack("<I", payload[offset + 14:offset + 18])[0])
        offset = page_end
    return serials


class MoOSSoundThemeTests(unittest.TestCase):
    def test_semantic_system_family_has_valid_ogg_containers(self) -> None:
        index = (THEME / "index.theme").read_text(encoding="utf-8")
        self.assertIn("Name=MoOS", index)
        self.assertIn("Directories=stereo", index)
        self.assertIn("Example=message-new-instant", index)

        shipped = {path.name for path in STEREO.glob("*.oga")}
        self.assertTrue(REQUIRED_EVENTS <= shipped, REQUIRED_EVENTS - shipped)
        for event in sorted(REQUIRED_EVENTS):
            path = STEREO / event
            with self.subTest(event=event):
                payload = path.read_bytes()
                self.assertGreater(len(payload), 2_000)
                self.assertEqual(payload[:4], b"OggS")
                self.assertEqual(
                    ogg_serials(payload),
                    {zlib.crc32(event.encode("utf-8")) & 0xFFFFFFFF},
                    "Ogg serial must be name-derived so rerunning the generator "
                    "does not dirty every sound with random container metadata",
                )

    def test_generator_owns_every_shipped_event(self) -> None:
        generator = (ROOT / "artwork/generate_nova_sounds.py").read_text(
            encoding="utf-8"
        )
        for event in REQUIRED_EVENTS:
            self.assertIn(f'"{event}"', generator)
        self.assertIn("No recorded samples or third-party audio are used", generator)

    def test_native_defaults_use_real_sound_assets(self) -> None:
        config = sound_gate.read_config(
            ROOT / "system_files/etc/xdg/plasma_workspace.notifyrc"
        )
        expected = {
            "Event/startkde": ("Sound", "desktop-login"),
            "Event/exitkde": ("Sound", "desktop-logout"),
            "Event/notification": ("Popup|Sound", "message-new-instant"),
        }
        self.assertEqual(set(config.sections()), set(expected))
        for event, (actions, sound) in expected.items():
            self.assertEqual(config[event]["Action"], actions)
            self.assertEqual(config[event]["Sound"], sound)
            self.assertTrue((STEREO / f"{sound}.oga").is_file())

    def test_image_gate_rejects_missing_sound_and_unknown_event(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            events = root / "usr/share/knotifications6"
            events.mkdir(parents=True)
            (events / "plasma_workspace.notifyrc").write_text(
                "[Event/startkde]\nAction=\nSound=desktop-login\n"
                "[Event/exitkde]\nAction=\nSound=desktop-logout\n"
                "[Event/notification]\nAction=Popup\n", encoding="utf-8"
            )
            power = events / "powerdevil.notifyrc"
            power.write_text("[Global]\nName=Power\n", encoding="utf-8")
            overlay = ROOT / "system_files"
            self.assertEqual(sound_gate.verify(root, overlay), [])
            power.write_text(
                "[Event/lowbattery]\nAction=Sound|Popup\nSound=missing-tone\n",
                encoding="utf-8",
            )
            self.assertTrue(any("missing-tone" in error
                                for error in sound_gate.verify(root, overlay)))
            power.write_text("[Global]\nName=Power\n", encoding="utf-8")
            (events / "plasma_workspace.notifyrc").write_text(
                "[Event/notification]\nAction=Popup\n", encoding="utf-8"
            )
            self.assertTrue(any("unknown KDE event" in error
                                for error in sound_gate.verify(root, overlay)))

    @unittest.skipUnless(shutil.which("kreadconfig6"), "requires native KDE KConfig")
    def test_kconfig_preserves_explicit_mute_and_custom_sound(self) -> None:
        # Execute the real KDE reader, with no path to the live user's settings,
        # session bus or display. Reading twice must not mutate the fixture.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            user = root / "config"
            user.mkdir()
            env = dict(os.environ, HOME=directory, XDG_CONFIG_HOME=str(user),
                       XDG_CONFIG_DIRS=str(ROOT / "system_files/etc/xdg"),
                       XDG_DATA_HOME=str(root / "data"),
                       XDG_CACHE_HOME=str(root / "cache"),
                       DBUS_SESSION_BUS_ADDRESS="unix:path=/nonexistent",
                       DISPLAY="", WAYLAND_DISPLAY="")

            def read(file: str, group: str, key: str) -> str:
                return subprocess.run(
                    ["kreadconfig6", "--file", file, "--group", group, "--key", key],
                    env=env, check=True, capture_output=True, text=True,
                ).stdout.rstrip("\n")

            self.assertEqual(read("plasma_workspace.notifyrc", "Event/startkde", "Action"), "Sound")
            personal = user / "plasma_workspace.notifyrc"
            personal.write_text(
                "[Event/startkde]\nAction=\n"
                "[Event/notification]\nAction=Popup\nSound=/custom/chime.ogg\n",
                encoding="utf-8",
            )
            (user / "kdeglobals").write_text("[Sounds]\nEnable=false\n", encoding="utf-8")
            before = personal.read_bytes()
            for _ in range(2):
                self.assertEqual(read("plasma_workspace.notifyrc", "Event/startkde", "Action"), "")
                self.assertEqual(read("plasma_workspace.notifyrc", "Event/notification", "Action"), "Popup")
                self.assertEqual(read("plasma_workspace.notifyrc", "Event/notification", "Sound"), "/custom/chime.ogg")
                self.assertEqual(read("kdeglobals", "Sounds", "Enable"), "false")
            self.assertEqual(personal.read_bytes(), before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
