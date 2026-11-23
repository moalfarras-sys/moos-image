#!/usr/bin/env python3
"""Gate: the MoOS corner is on every MoOS card, and its glass is frosted exactly where it is painted.

WHY THIS EXISTS (owner steering, 2026-11-22)

"The geometric shape: one square corner and curved ones, like the buttons were before — on
every card." MoOS's signature is three rounded corners and a square TOP-TRAILING one (top-right
reading left to right, top-left in Arabic), softened only by Design Core's radiusSquare. It lives
in four places that drift independently:

  1. Design Core (artwork/moos-design/tokens.json -> Tokens.qml): radiusSquare.
  2. The shared surface every MoOS card is built from (org.moos.ui Surface/GlassSurface).
  3. Plasma's FrameSvgs that MoOS generates: the popup frame (dialogs/background.svg) and the
     desktop-widget cards (widgets/background.svg, widgets/translucentbackground.svg) in all
     eighteen desktop themes. FrameSvg cannot mirror, so MoOS (Arabic-first) squares the
     top-left piece. Its mask-* twin is the KWin blur region: if paint and mask disagree, the
     frost spills past the square corner or a rounded notch of unfrosted wallpaper shows in it.
  4. The hand-drawn card Rectangles of MoOS's apps and plasmoids that bind a card radius, and
     the command pills apps draw for themselves (a Rectangle that is itself the button). The
     installer and Welcome drew seventeen such commands — Begin, Next, Install, Restart — as
     plain pills beside cornered cards and cornered shared Buttons, and the card scanner could
     not see them: their radius is `height / 2`, not a card token.

A card added later with a plain `radius:` would quietly be the one rounded card on a screen of
MoOS cards. Both scanners below are proven to bite on a synthetic case before they judge the tree.
Circles, a model's delegates (chips, rows, choice cards) and a pill whose block declares
`MoOS corner: round` (a link chip, say) stay round, as artwork/MOOS_UI2_DESIGN.md says.
"""

from __future__ import annotations

import json
import re
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QML = ROOT / "system_files/usr/lib64/qt6/qml/org/moos/ui"
THEMES = ROOT / "system_files/usr/share/plasma/desktoptheme"
CARD_FRAMES = ("dialogs/background.svg", "widgets/background.svg", "widgets/translucentbackground.svg")
CARD_TOKEN = re.compile(r"^(\s*)radius:\s*((?:[A-Za-z]+\.)?design\.radius(?:Card|Panel|Dialog))\s*$")
# A card made of the shared surface inherits the corner; a Rectangle must state it.
SHARED_SURFACES = ("GlassSurface {", "Surface {", "Card {")


def ids(path: Path) -> dict[str, ET.Element]:
    return {e.get("id"): e for e in ET.parse(path).getroot().iter() if e.get("id")}


def first_path(element: ET.Element) -> str:
    if element.tag.endswith("path"):
        return element.get("d", "")
    for child in element.iter():
        if child.tag.endswith("path"):
            return child.get("d", "")
    return ""


def numbers(d: str) -> list[float]:
    return [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", d)]


ARITY = {"M": 2, "L": 2, "H": 1, "V": 1, "A": 7, "Z": 0}


def translated(d: str, dx: float) -> list[tuple[str, tuple[float, ...]]]:
    """The absolute path's commands with every x coordinate moved by dx (M/L/H/V/A/Z only)."""
    tokens = re.findall(r"[A-Za-z]|-?\d+(?:\.\d+)?", d)
    out, i = [], 0
    while i < len(tokens):
        command = tokens[i]
        if command not in ARITY:
            raise AssertionError(f"unexpected path command {command!r} in {d!r}")
        i += 1
        args = [float(v) for v in tokens[i:i + ARITY[command]]]
        i += ARITY[command]
        if command in ("M", "L"):
            args[0] += dx
        elif command == "H":
            args[0] += dx
        elif command == "A":
            args[5] += dx
        out.append((command, tuple(args)))
    return out


def bare_card_rectangles(text: str) -> list[int]:
    """1-based lines of Rectangles that bind a card radius but not the MoOS corner."""
    lines = text.splitlines()
    found = []
    for n, line in enumerate(lines):
        m = CARD_TOKEN.match(line)
        if not m:
            continue
        indent = len(m.group(1))
        start = next((k for k in range(n - 1, -1, -1)
                      if lines[k].rstrip().endswith("{")
                      and len(lines[k]) - len(lines[k].lstrip()) < indent), None)
        if start is None:
            continue
        head = lines[start].strip()
        if any(head.endswith(surface) for surface in SHARED_SURFACES) or not head.endswith("Rectangle {"):
            continue
        depth, body = 0, []
        for k in range(start, len(lines)):
            depth += lines[k].count("{") - lines[k].count("}")
            body.append(lines[k])
            if depth == 0:
                break
        own = "\n".join(body)
        if "topLeftRadius:" not in own or "topRightRadius:" not in own:
            found.append(n + 1)
    return found


PILL_RADIUS = re.compile(r"^radius:\s*height\s*/\s*2$")
ROUND_MARK = "MoOS corner: round"


def direct_properties(lines: list[str], start: int) -> tuple[int, list[str]]:
    """(last line, stripped direct-child lines) of the block opened on `start`."""
    depth, end = 0, start
    for k in range(start, len(lines)):
        depth += lines[k].count("{") - lines[k].count("}")
        if depth == 0:
            end = k
            break
    inner = [k for k in range(start + 1, end) if lines[k].strip()]
    if not inner:
        return end, []
    child = min(len(lines[k]) - len(lines[k].lstrip()) for k in inner)
    return end, [lines[k].strip() for k in inner if len(lines[k]) - len(lines[k].lstrip()) == child]


def bare_command_pills(text: str) -> list[int]:
    """1-based lines of hand-drawn command pills that do not wear the MoOS corner."""
    lines = text.splitlines()
    found = []
    for n, line in enumerate(lines):
        if line.strip() != "Rectangle {":
            continue  # `delegate: Rectangle {` is a model's choice (chip, row, card), not a command
        end, props = direct_properties(lines, n)
        if "Accessible.role: Accessible.Button" not in props or not any(PILL_RADIUS.match(p) for p in props):
            continue
        if ROUND_MARK in "\n".join(lines[n:end + 1]):
            continue
        widths = {p.split(":", 1)[1].strip() for p in props
                  if p.startswith(("Layout.preferredWidth:", "width:", "implicitWidth:"))}
        heights = {p.split(":", 1)[1].strip() for p in props
                   if p.startswith(("Layout.preferredHeight:", "height:", "implicitHeight:"))}
        if widths & heights or "height" in widths:
            continue  # a circle stays round
        if not any(p.startswith("topLeftRadius:") for p in props) \
                or not any(p.startswith("topRightRadius:") for p in props):
            found.append(n + 1)
    return found


class DesignCoreOwnsTheCorner(unittest.TestCase):
    def test_the_token_is_generated_into_tokens_qml(self):
        tokens = json.loads((ROOT / "artwork/moos-design/tokens.json").read_text(encoding="utf-8"))
        square = [v for k, v in self._flat(tokens) if k == "radiusSquare"]
        self.assertEqual(square, [3], "Design Core must own exactly one radiusSquare")
        self.assertIn("readonly property int radiusSquare: 3", (QML / "Tokens.qml").read_text(encoding="utf-8"))

    def _flat(self, node, key=""):
        if isinstance(node, dict):
            for k, v in node.items():
                yield from self._flat(v, k)
        else:
            yield key, node

    def test_the_shared_surface_squares_its_top_trailing_corner(self):
        surface = (QML / "Surface.qml").read_text(encoding="utf-8")
        for contract in (
            "readonly property real squareRadius: Math.min(radius, Tokens.radiusSquare)",
            "topLeftRadius: cornerApplies && LayoutMirroring.enabled ? squareRadius : radius",
            "topRightRadius: cornerApplies && !LayoutMirroring.enabled ? squareRadius : radius",
            # pills and circles stay round: a square corner belongs to a card
            "radius * 2 < Math.min(width, height) - 1",
        ):
            self.assertIn(contract, surface)
        glass = (QML / "GlassSurface.qml").read_text(encoding="utf-8")
        # its sheen follows the corner, and its catch-light stops short of the square one
        self.assertIn("glass.topLeftRadius", glass)
        self.assertIn("squareInset: glass.cornerApplies ? glass.squareRadius + 2 : roundInset", glass)

    def test_the_focus_ring_follows_the_corner(self):
        ring = (QML / "FocusRing.qml").read_text(encoding="utf-8")
        self.assertIn('topLeftRadius: followsCorners ? parent["topLeftRadius"] + Tokens.focusGap : radius', ring)
        self.assertIn('topRightRadius: followsCorners ? parent["topRightRadius"] + Tokens.focusGap : radius', ring)


class ThePlasmaFramesWearItAndFrostIt(unittest.TestCase):
    def frames(self):
        found = sorted(THEMES.glob("*/dialogs/background.svg"))
        self.assertEqual(len(found), 18, "every MoOS desktop theme owns its popup frame")
        for theme in sorted({p.parents[1] for p in found}):
            for relative in CARD_FRAMES:
                yield theme.name, relative, theme / relative

    def test_paint_and_blur_mask_share_one_square_top_left(self):
        for theme, relative, path in self.frames():
            with self.subTest(theme=theme, frame=relative):
                elements = ids(path)
                painted = numbers(first_path(elements["topleft"]))
                mask = numbers(first_path(elements["mask-topleft"]))
                # M x y+3 A 3 3 0 0 1 x+3 y H ...: a 3-unit softening, not the frame radius.
                self.assertEqual(painted[2:4], [3, 3], f"painted top-left is not square: {painted}")
                self.assertEqual(mask[2:4], [3, 3], f"blur mask top-left is not square: {mask}")
                # The mask is the painted piece, moved sideways to its own column.
                offset = mask[0] - painted[0]
                self.assertEqual(translated(first_path(elements["topleft"]), offset),
                                 translated(first_path(elements["mask-topleft"]), 0),
                                 "KWin would frost a different top-left than the one painted")

    def test_the_other_three_corners_stay_round(self):
        for theme, relative, path in self.frames():
            with self.subTest(theme=theme, frame=relative):
                elements = ids(path)
                for corner in ("topright", "bottomleft", "bottomright"):
                    for prefix in ("", "mask-"):
                        d = first_path(elements[prefix + corner])
                        radius = numbers(d)[2]
                        self.assertGreaterEqual(radius, 12, f"{prefix}{corner} is not a rounded corner: {d}")

    def test_tooltips_are_not_cards(self):
        for path in sorted(THEMES.glob("*/widgets/tooltip.svg")):
            with self.subTest(theme=path.parents[1].name):
                self.assertGreaterEqual(numbers(first_path(ids(path)["topleft"]))[2], 10)


class EveryHandDrawnCardStatesTheCorner(unittest.TestCase):
    def test_mira_s_glass_wears_it(self):
        mira = ROOT / "mira/qml/Mira"
        self.assertIn("readonly property int rSquare: 3", (mira / "Theme.qml").read_text(encoding="utf-8"))
        glass = (mira / "Glass.qml").read_text(encoding="utf-8")
        self.assertIn("topLeftRadius: cornerApplies && LayoutMirroring.enabled ? squareRadius : radius", glass)
        self.assertIn("topRightRadius: cornerApplies && !LayoutMirroring.enabled ? squareRadius : radius", glass)
        self.assertIn("topLeftRadius: Math.max(0, parent.topLeftRadius - 1)", glass)

    def test_the_scanner_bites_on_a_plain_card(self):
        plain = ("Item {\n    Rectangle {\n        radius: design.radiusCard\n        color: \"red\"\n    }\n}\n")
        self.assertEqual(bare_card_rectangles(plain), [3])
        cornered = plain.replace("        color:", "        topLeftRadius: 1\n        topRightRadius: 1\n        color:")
        self.assertEqual(bare_card_rectangles(cornered), [])
        shared = plain.replace("Rectangle {", "MoUI.GlassSurface {")
        self.assertEqual(bare_card_rectangles(shared), [])

    def test_no_moos_card_rectangle_lacks_the_corner(self):
        offenders = []
        sources = [*(ROOT / "system_files/usr").rglob("*.qml"), *(ROOT / "moos-settings-kcm").rglob("*.qml")]
        for path in sorted(sources):
            for line in bare_card_rectangles(path.read_text(encoding="utf-8")):
                offenders.append(f"{path.relative_to(ROOT)}:{line}")
        self.assertEqual(offenders, [], "these MoOS cards are the only rounded ones on their screen; "
                                        "give them the MoOS corner (topLeftRadius/topRightRadius by "
                                        "LayoutMirroring, Math.min(radius, design.radiusSquare))")

    def test_the_command_scanner_bites_on_a_plain_command_pill(self):
        command = ("Item {\n    Rectangle {\n        implicitWidth: row.implicitWidth + 48\n"
                   "        radius: height / 2\n        activeFocusOnTab: true\n"
                   "        Accessible.role: Accessible.Button\n        TapHandler { onTapped: go() }\n    }\n}\n")
        self.assertEqual(bare_command_pills(command), [2])
        cornered = command.replace("        activeFocusOnTab:",
                                   "        topLeftRadius: 1\n        topRightRadius: 1\n        activeFocusOnTab:")
        self.assertEqual(bare_command_pills(cornered), [])
        # A choice in a model, a circle and a declared link chip stay round.
        self.assertEqual(bare_command_pills(command.replace("    Rectangle {", "    delegate: Rectangle {")), [])
        circle = command.replace("implicitWidth: row.implicitWidth + 48",
                                 "Layout.preferredWidth: 36\n        Layout.preferredHeight: 36")
        self.assertEqual(bare_command_pills(circle), [])
        link = command.replace("        activeFocusOnTab:", "        // MoOS corner: round. A link chip.\n"
                                                           "        activeFocusOnTab:")
        self.assertEqual(bare_command_pills(link), [])
        # A pill that only CONTAINS a button (its role is on a child) is not itself the command.
        nested = command.replace("        Accessible.role: Accessible.Button\n",
                                 "        Item { Accessible.role: Accessible.Button }\n")
        self.assertEqual(bare_command_pills(nested), [])

    def test_no_hand_drawn_command_pill_lacks_the_corner(self):
        offenders = []
        sources = [*(ROOT / "system_files/usr").rglob("*.qml"), *(ROOT / "moos-settings-kcm").rglob("*.qml"),
                   *(ROOT / "mira/qml").rglob("*.qml")]
        for path in sorted(sources):
            for line in bare_command_pills(path.read_text(encoding="utf-8")):
                offenders.append(f"{path.relative_to(ROOT)}:{line}")
        self.assertEqual(offenders, [], "these hand-drawn commands are round pills beside cornered "
                                        "cards and Buttons; give them the MoOS corner, or declare "
                                        "'MoOS corner: round' in the block of a link chip")


if __name__ == "__main__":
    unittest.main(verbosity=2)
