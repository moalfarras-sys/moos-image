#!/usr/bin/env python3
"""Product gate for the original MoOS system sound family."""

from __future__ import annotations

from pathlib import Path
import struct
import unittest
import zlib


ROOT = Path(__file__).resolve().parents[1]
THEME = ROOT / "system_files/usr/share/sounds/moos"
STEREO = THEME / "stereo"

REQUIRED_EVENTS = {
    "audio-volume-change.oga",
    "battery-caution.oga",
    "battery-low.oga",
    "button-pressed.oga",
    "button-pressed-modifier.oga",
    "complete-download.oga",
    "completion-fail.oga",
    "completion-success.oga",
    "desktop-login.oga",
    "desktop-logout.oga",
    "device-added.oga",
    "device-removed.oga",
    "dialog-error.oga",
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
    def test_semantic_system_family_is_complete_and_decodable(self) -> None:
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
