#!/usr/bin/env python3
"""Gates for the MoOS Plymouth boot splash.

WHAT THESE ARE FOR
    The splash is the one surface whose failure is invisible to every other
    check in this repo. `Theme=moos` can be set, the theme directory can be
    installed, the script can be in the initramfs — and the user can still get a
    grey text console, because Plymouth's script plugin falls back to text the
    moment it cannot load something the script asks for.

    So these gate the things that actually break it in practice:
      * a UTF-8 BOM, which makes Plymouth's parser reject the whole script —
        and plugin.c ignores that failure and reports success, so the user
        gets a pure black screen (no text fallback on Fedora 44),
      * the script asking for a file that is not there, and
      * the script doing unbounded work on every refresh.

    They deliberately do NOT gate the artistic content. The previous version of
    this file asserted on specific variable names from the sprite-based reveal
    (`logo_settled`, `field_settled`, `pulse_done`) and on an exact count of
    `logo_image.Scale` calls. All of that described one implementation rather
    than any property of a working splash, and all of it went stale the moment
    the theme became a frame sequence.
"""

from __future__ import annotations

import re
import struct
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
THEME = ROOT / "system_files/usr/share/plymouth/themes/moos"
SCRIPT = THEME / "moos.script"


def png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()[:24]
    if data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise AssertionError(f"not a PNG with an IHDR header: {path}")
    return struct.unpack(">II", data[16:24])


def script_text() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def loaded_assets() -> list[str]:
    return sorted(set(re.findall(r'Image\("([^"]+)"\)', script_text())))


def scalar(name: str) -> float:
    m = re.search(rf"^\s*{name}\s*=\s*(-?[0-9]*\.?[0-9]+)\s*;", script_text(), re.MULTILINE)
    if not m:
        raise AssertionError(f"moos.script no longer defines {name}")
    return float(m.group(1))


def intro_frames() -> list[Path]:
    fs = list(THEME.glob("intro*.png"))
    return sorted(fs, key=lambda p: int("".join(c for c in p.stem if c.isdigit())))


class BootSplashTests(unittest.TestCase):
    # ── the failure that produces a BLACK screen, not even text ────────────
    def test_script_has_no_utf8_bom(self) -> None:
        # A UTF-8 BOM (EF BB BF) at byte 0 makes Plymouth's scanner emit three
        # SYMBOL tokens before the first comment. The parser then rejects the
        # whole file ("Unparsed characters at end of file", L:1 C:0) and
        # script_parse_file() returns NULL — which plugin.c does NOT check: it
        # calls start_script_animation() anyway and reports success. plymouthd
        # therefore runs a theme that draws nothing (not even its background,
        # which this script sets), shows a pure black screen for the whole
        # splash window, and no gate on file presence can see it. Proven on
        # 2026-08-24 with the real Fedora 44 parser (plymouth 24.004.60):
        # with BOM -> PARSE FAILED; identical bytes minus BOM -> PARSE OK.
        raw = SCRIPT.read_bytes()
        self.assertFalse(raw.startswith(b"\xef\xbb\xbf"),
                         "moos.script starts with a UTF-8 BOM: Plymouth's parser "
                         "rejects the entire theme and boots a black splash "
                         "(plugin.c ignores the NULL parse result)")

    def test_theme_ships_no_bom_in_any_asset(self) -> None:
        for path in sorted(THEME.iterdir()):
            if not path.is_file():
                continue
            with self.subTest(asset=path.name):
                self.assertFalse(path.read_bytes()[:3] == b"\xef\xbb\xbf",
                                 f"{path.name} starts with a UTF-8 BOM")

    # ── the failure that produces a text console ────────────────────────────
    def test_every_image_the_script_loads_is_installed(self) -> None:
        assets = loaded_assets()
        self.assertTrue(assets, "moos.script loads no images at all")
        for name in assets:
            with self.subTest(asset=name):
                self.assertTrue((THEME / name).is_file(),
                                f"moos.script loads {name}, which is not in the theme — "
                                f"Plymouth would abort this splash to its text fallback")

    def test_intro_count_matches_the_frames_on_disk(self) -> None:
        self.assertEqual(int(scalar("INTRO_COUNT")), len(intro_frames()),
                         "INTRO_COUNT and the installed intro frames disagree: either the "
                         "tail of the animation never plays, or the script loads a file "
                         "that is not there")

    def test_frame_filenames_are_literal_not_built_by_concatenation(self) -> None:
        # Plymouth's script language has no string formatting and its
        # number-to-string conversion is not specified to yield "1" rather than
        # "1.000000". A filename built by concatenation can therefore resolve to
        # nothing on some Plymouth build, and the whole splash drops to text —
        # on a user's machine, never here.
        self.assertNotRegex(script_text(), r'Image\(\s*"[^"]*"\s*\+',
                            "an Image() filename is being built by concatenation")

    # ── the failure that makes boot slow or memory-hungry ──────────────────
    def test_refresh_scales_at_most_one_image(self) -> None:
        body = script_text().split("fun refresh()", 1)
        self.assertEqual(len(body), 2, "moos.script has no refresh() function")
        refresh = body[1].split("\nPlymouth.SetRefreshFunction", 1)[0]
        self.assertLessEqual(refresh.count(".Scale("), 1,
                             "refresh() scales more than one image per call; at 50 Hz on a "
                             "cold boot that is the splash competing with the boot it is "
                             "supposed to be covering")

    def test_frames_are_not_prescaled_into_memory(self) -> None:
        # Pre-scaling the whole sequence at load time costs frames x screen x 4
        # bytes inside the initramfs — ~219 MiB at 1080p for 32 frames, on
        # machines that may have 1 GB.
        setup = script_text().split("fun refresh()", 1)[0]
        self.assertNotRegex(setup, r"frames\[\s*i\s*\]\s*=\s*Image\([^)]*\)\.Scale",
                            "the intro sequence is being scaled at load time")

    def test_intro_frames_fit_the_initramfs_budget(self) -> None:
        frames = intro_frames()
        self.assertTrue(frames, "no intro frames installed")
        w, h = png_size(frames[0])
        decoded_mib = len(frames) * w * h * 4 / 1048576
        # The sequence is stored at the render's own crop width rather than
        # downscaled, because the splash now rests on its last frame and that
        # frame is what the user looks at longest. That buys sharpness and costs
        # RAM inside the initramfs; this is where the trade is pinned.
        self.assertLess(decoded_mib, 72,
                        f"the intro sequence decodes to {decoded_mib:.0f} MiB in the "
                        f"initramfs; that is charged to every boot on every machine")
        on_disk_mib = sum(p.stat().st_size for p in frames) / 1048576
        self.assertLess(on_disk_mib, 16,
                        f"the intro sequence is {on_disk_mib:.1f} MiB on disk and is copied "
                        f"into the initramfs")

    # ── the failure that shows a stretched or frozen frame ─────────────────
    def test_the_script_declares_the_aspect_its_frames_actually_have(self) -> None:
        fw, fh = png_size(intro_frames()[0])
        self.assertAlmostEqual(scalar("INTRO_ASPECT"), fw / fh, delta=0.005,
                               msg="INTRO_ASPECT does not match the frames, so the sequence "
                                   "is drawn stretched")

    def test_quit_leaves_a_composed_frame_not_a_frozen_one(self) -> None:
        text = script_text()
        self.assertIn("Plymouth.SetQuitFunction", text,
                      "no quit handler: `plymouth quit --retain-splash` would leave whatever "
                      "mid-animation frame happened to be showing on screen for the whole "
                      "login-manager bring-up")
        quit_body = text.split("fun quit_callback()", 1)[1].split("}", 1)[0]
        # It must PIN the last frame, not leave whatever was mid-flight.
        self.assertIn("frames[INTRO_COUNT]", quit_body,
                      "quit does not jump to the sequence's resting frame")
        self.assertIn("intro_sprite.SetOpacity(1)", quit_body)
        for moving in ("ring_sprite", "head_sprite"):
            self.assertIn(f"{moving}.SetOpacity(0)", quit_body,
                          f"{moving} is still visible in the retained frame; a stopped "
                          f"animation reads as a hang")

    def test_the_ground_is_the_desktop_canvas(self) -> None:
        # #14191C is the UI2 canvas the desktop opens on. Any other colour here
        # is a full-screen hue flip at the splash-to-desktop handoff.
        text = script_text()
        for fn in ("SetBackgroundTopColor", "SetBackgroundBottomColor"):
            self.assertIn(f"Window.{fn}(0.078, 0.098, 0.110)", text,
                          f"{fn} is not the #14191C UI2 canvas token")

    def test_boot_text_overlays_are_screen_bounded(self) -> None:
        # Plymouth messages can be long: fsck paths, recovery notices, device
        # waits, or encrypted-volume prompts. If they are centered at natural
        # width, small screens and VMs clip them off both edges during the boot
        # moment where the user has the least context. Scale those event-driven
        # text images to the screen, but keep refresh() cheap.
        text = script_text()
        self.assertIn("OVERLAY_MAX_W = sw * 0.78;", text)
        for marker, image_var in (
            ("fun message_callback(text)", "img"),
            ("fun display_password(prompt, bullets)", "pimg"),
            ("fun display_password(prompt, bullets)", "bimg"),
        ):
            with self.subTest(marker=marker, image=image_var):
                end_marker = (
                    "fun hide_message()"
                    if marker == "fun message_callback(text)"
                    else "fun clear_password()"
                )
                body = text.split(marker, 1)[1].split(end_marker, 1)[0]
                self.assertIn(f"{image_var}.GetWidth() > OVERLAY_MAX_W", body)
                self.assertIn(
                    f"{image_var}.Scale(OVERLAY_MAX_W, "
                    f"{image_var}.GetHeight() * OVERLAY_MAX_W / {image_var}.GetWidth())",
                    body,
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
