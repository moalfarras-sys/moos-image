#!/usr/bin/env python3
"""Generate the MoOS "Tidal Cut" symbolic action-icon family.

The 24-unit source geometry in this file is the single source of truth for the
SVG assets, the QML review manifest, and the documented symbol inventory.
Every visible mark is a filled path.  That is deliberate: GTK 4 treats a
``-symbolic`` SVG as a mask and does not preserve stroked/currentColor artwork,
while KDE recolours the ``ColorScheme-*`` classes at load time.
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "system_files/usr/share/icons/hicolor/scalable/actions"
MANIFEST = ROOT / "artwork/moos_symbolic_manifest.js"
RUNTIME_MANIFEST = ROOT / "system_files/usr/share/moos/apps/ui/SymbolCatalog.js"
MAP = ROOT / "artwork/MOOS_UI_SYMBOL_MAP.md"

TEXT = "text"
HIGHLIGHT = "highlight"
WARNING = "warning"
ERROR = "error"


@dataclass(frozen=True)
class Shape:
    """One independently filled path.

    Keeping overlapping primitives as separate paths prevents even/odd fill
    cancellation.  A shape may itself be compound when it intentionally owns
    transparent counters or cuts.
    """

    d: str
    role: str = TEXT


@dataclass(frozen=True)
class Symbol:
    title: str
    category: str
    shapes: tuple[Shape, ...]
    min_holes: int = 0


def _n(value: float) -> str:
    value = round(value, 3)
    if value == 0:
        return "0"
    return f"{value:g}"


def _pt(x: float, y: float) -> str:
    return f"{_n(x)} {_n(y)}"


def path(d: str, role: str = TEXT) -> Shape:
    return Shape(" ".join(d.split()), role)


def compound(outer: str, *holes: str, role: str = TEXT) -> Shape:
    return Shape(" ".join((outer, *holes)), role)


def polygon(points: Iterable[tuple[float, float]]) -> str:
    points = tuple(points)
    return f"M{_pt(*points[0])} " + " ".join(
        f"L{_pt(x, y)}" for x, y in points[1:]
    ) + " Z"


def rect(x: float, y: float, width: float, height: float, radius: float = 0) -> str:
    right, bottom = x + width, y + height
    radius = min(radius, width / 2, height / 2)
    if radius <= 0:
        return f"M{_pt(x, y)} H{_n(right)} V{_n(bottom)} H{_n(x)} Z"
    return (
        f"M{_pt(x + radius, y)} H{_n(right - radius)} "
        f"A{_n(radius)} {_n(radius)} 0 0 1 {_pt(right, y + radius)} "
        f"V{_n(bottom - radius)} "
        f"A{_n(radius)} {_n(radius)} 0 0 1 {_pt(right - radius, bottom)} "
        f"H{_n(x + radius)} "
        f"A{_n(radius)} {_n(radius)} 0 0 1 {_pt(x, bottom - radius)} "
        f"V{_n(y + radius)} "
        f"A{_n(radius)} {_n(radius)} 0 0 1 {_pt(x + radius, y)} Z"
    )


def circle(cx: float, cy: float, radius: float) -> str:
    return (
        f"M{_pt(cx + radius, cy)} "
        f"A{_n(radius)} {_n(radius)} 0 1 1 {_pt(cx - radius, cy)} "
        f"A{_n(radius)} {_n(radius)} 0 1 1 {_pt(cx + radius, cy)} Z"
    )


def ellipse(cx: float, cy: float, rx: float, ry: float) -> str:
    return (
        f"M{_pt(cx + rx, cy)} "
        f"A{_n(rx)} {_n(ry)} 0 1 1 {_pt(cx - rx, cy)} "
        f"A{_n(rx)} {_n(ry)} 0 1 1 {_pt(cx + rx, cy)} Z"
    )


def capsule(x1: float, y1: float, x2: float, y2: float, width: float = 2) -> str:
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy)
    if length == 0:
        return circle(x1, y1, width / 2)
    radius = width / 2
    nx, ny = -dy / length * radius, dx / length * radius
    return (
        f"M{_pt(x1 + nx, y1 + ny)} L{_pt(x2 + nx, y2 + ny)} "
        f"A{_n(radius)} {_n(radius)} 0 0 1 {_pt(x2 - nx, y2 - ny)} "
        f"L{_pt(x1 - nx, y1 - ny)} "
        f"A{_n(radius)} {_n(radius)} 0 0 1 {_pt(x1 + nx, y1 + ny)} Z"
    )


def ring(cx: float, cy: float, outer: float, inner: float) -> str:
    return f"{circle(cx, cy, outer)} {circle(cx, cy, inner)}"


def ellipse_ring(cx: float, cy: float, orx: float, ory: float, irx: float, iry: float) -> str:
    return f"{ellipse(cx, cy, orx, ory)} {ellipse(cx, cy, irx, iry)}"


def rounded_ring(
    x: float,
    y: float,
    width: float,
    height: float,
    radius: float,
    weight: float,
) -> str:
    return (
        f"{rect(x, y, width, height, radius)} "
        f"{rect(x + weight, y + weight, width - 2 * weight, height - 2 * weight, max(0, radius - weight))}"
    )


def arc_band(
    cx: float,
    cy: float,
    outer: float,
    inner: float,
    start_degrees: float,
    end_degrees: float,
) -> str:
    """Return a filled annular sector; callers cap endpoints when needed."""

    start, end = map(math.radians, (start_degrees, end_degrees))
    span = (end_degrees - start_degrees) % 360
    large = int(span > 180)
    ox1, oy1 = cx + outer * math.cos(start), cy + outer * math.sin(start)
    ox2, oy2 = cx + outer * math.cos(end), cy + outer * math.sin(end)
    ix2, iy2 = cx + inner * math.cos(end), cy + inner * math.sin(end)
    ix1, iy1 = cx + inner * math.cos(start), cy + inner * math.sin(start)
    return (
        f"M{_pt(ox1, oy1)} "
        f"A{_n(outer)} {_n(outer)} 0 {large} 1 {_pt(ox2, oy2)} "
        f"L{_pt(ix2, iy2)} "
        f"A{_n(inner)} {_n(inner)} 0 {large} 0 {_pt(ix1, iy1)} Z"
    )


def rotated_ellipse_ring(
    cx: float,
    cy: float,
    orx: float,
    ory: float,
    irx: float,
    iry: float,
    angle_degrees: float,
    samples: int = 40,
) -> str:
    angle = math.radians(angle_degrees)

    def points(rx: float, ry: float) -> list[tuple[float, float]]:
        result = []
        for index in range(samples):
            theta = math.tau * index / samples
            x, y = rx * math.cos(theta), ry * math.sin(theta)
            result.append((
                cx + x * math.cos(angle) - y * math.sin(angle),
                cy + x * math.sin(angle) + y * math.cos(angle),
            ))
        return result

    return f"{polygon(points(orx, ory))} {polygon(reversed(points(irx, iry)))}"


def regular_polygon(
    cx: float,
    cy: float,
    radius: float,
    sides: int,
    rotation_degrees: float = -90,
) -> str:
    return polygon(
        (
            cx + radius * math.cos(math.radians(rotation_degrees + 360 * i / sides)),
            cy + radius * math.sin(math.radians(rotation_degrees + 360 * i / sides)),
        )
        for i in range(sides)
    )


def star(cx: float, cy: float, outer: float, inner: float, points: int, rotation: float = -90) -> str:
    return polygon(
        (
            cx + (outer if i % 2 == 0 else inner)
            * math.cos(math.radians(rotation + 180 * i / points)),
            cy + (outer if i % 2 == 0 else inner)
            * math.sin(math.radians(rotation + 180 * i / points)),
        )
        for i in range(points * 2)
    )


def sym(
    title: str,
    category: str,
    *shapes: Shape,
    min_holes: int = 0,
) -> Symbol:
    return Symbol(title, category, tuple(shapes), min_holes)


# Tidal Cut design grammar:
# - 24-unit optical grid; painted bounds remain inside 2.25…21.75.
# - 2.0–2.25-unit structural weight (>=1.33 px at the 16 px target).
# - soft terminals, solid silhouettes, and a deliberate open counter/cut.
# - Highlight is an optional wayfinding detail; the silhouette never depends on it.
# - Warning and error deliberately use different silhouettes.
SYMBOLS: dict[str, Symbol] = {
    "ai": sym(
        "Mo AI", "assistant",
        compound(
            "M5.5 3.25 H18.5 A3.25 3.25 0 0 1 21.75 6.5 V14 "
            "A3.25 3.25 0 0 1 18.5 17.25 H12.6 L7.1 21 V17.25 H5.5 "
            "A3.25 3.25 0 0 1 2.25 14 V6.5 A3.25 3.25 0 0 1 5.5 3.25 Z",
            circle(7.5, 10.25, 1.05),
            circle(12, 10.25, 1.05),
            circle(16.5, 10.25, 1.05),
        ),
        path(star(18.5, 4.25, 2.1, .72, 4), HIGHLIGHT),
        min_holes=3,
    ),
    "android-apps": sym(
        "Android apps", "platform",
        path(capsule(7.25, 5.5, 5.75, 3.25, 1.8)),
        path(capsule(16.75, 5.5, 18.25, 3.25, 1.8)),
        compound(
            rect(2.75, 5.25, 18.5, 14.75, 3.4),
            rect(5, 8, 14, 8.7, 1.7),
        ),
        path(rect(6.4, 9.4, 4.2, 2.6, .8)),
        path(rect(13.4, 9.4, 4.2, 2.6, .8), HIGHLIGHT),
        path(rect(6.4, 13.1, 4.2, 2.25, .75)),
        path(rect(13.4, 13.1, 4.2, 2.25, .75)),
        min_holes=1,
    ),
    "arrow": sym(
        "Next", "navigation",
        path(capsule(3.25, 12, 17.2, 12, 2.2)),
        path(polygon(((13.2, 4.5), (21.5, 12), (13.2, 19.5), (13.2, 15.8), (17.4, 12), (13.2, 8.2)))),
    ),
    "arrow-back": sym(
        "Back", "navigation",
        path(capsule(20.75, 12, 6.8, 12, 2.2)),
        path(polygon(((10.8, 4.5), (2.5, 12), (10.8, 19.5), (10.8, 15.8), (6.6, 12), (10.8, 8.2)))),
    ),
    "audio": sym(
        "Audio", "media",
        path(polygon(((2.5, 9), (6.7, 9), (12, 4.75), (12, 19.25), (6.7, 15), (2.5, 15)))),
        path(arc_band(11.5, 12, 6.15, 4.15, -48, 48)),
        path(arc_band(11.5, 12, 9.3, 7.25, -44, 44), HIGHLIGHT),
    ),
    "bluetooth": sym(
        "Bluetooth", "connectivity",
        path(rect(10.8, 2.25, 2.15, 19.5, 1.075)),
        path(polygon(((11.8, 2.4), (18.15, 8.1), (13, 12.35), (13, 9.55), (15.2, 7.9), (11.8, 4.8)))),
        path(polygon(((13, 11.65), (18.15, 15.9), (11.8, 21.6), (11.8, 19.2), (15.2, 16.1), (13, 14.45)))),
        path(capsule(6.3, 7.2, 16.7, 16.8, 1.9), HIGHLIGHT),
    ),
    "bolt": sym(
        "Power", "status",
        path(polygon(((13.4, 2.25), (4.75, 13.35), (10.25, 13.35), (8.85, 21.75), (19.25, 9.45), (13.2, 9.45)))),
    ),
    "boxes": sym(
        "Packages", "software",
        path(polygon(((3, 6.2), (7.6, 3.7), (12.2, 6.2), (7.6, 8.8)))),
        path(polygon(((12.45, 6.2), (17, 3.7), (21.4, 6.2), (17, 8.8))), HIGHLIGHT),
        path(polygon(((3, 7.9), (7.6, 10.5), (7.6, 16), (3, 13.4)))),
        path(polygon(((12.45, 7.9), (17, 10.5), (17, 16), (12.45, 13.4)))),
        path(polygon(((7.4, 16.1), (12, 13.55), (16.6, 16.1), (12, 18.75)))),
        path(polygon(((7.4, 17.8), (12, 20.45), (16.6, 17.8), (16.6, 20), (12, 21.75), (7.4, 20)))),
    ),
    "briefcase": sym(
        "Work", "places",
        compound(
            rect(7.5, 2.75, 9, 7.5, 2.2),
            rect(9.7, 4.8, 4.6, 4.7, .8),
        ),
        compound(
            rect(2.25, 7.25, 19.5, 13.5, 2.8),
            rect(4.4, 11.6, 15.2, 2.2, 1.1),
        ),
        path(rect(10.35, 11, 3.3, 3.4, 1), HIGHLIGHT),
        min_holes=2,
    ),
    "bulb": sym(
        "Idea", "status",
        compound(
            "M12 2.25 C6.9 2.25 3.8 6.1 4.8 10.45 C5.25 12.45 6.5 13.65 "
            "7.65 14.85 C8.35 15.55 8.6 16.2 8.7 17.15 H15.3 "
            "C15.4 16.2 15.65 15.55 16.35 14.85 C17.5 13.65 18.75 12.45 "
            "19.2 10.45 C20.2 6.1 17.1 2.25 12 2.25 Z",
            "M10.15 8.2 C10.15 6.9 11.05 6.1 12.25 6.1 "
            "C13.45 6.1 14.15 6.85 14.15 7.9 C14.15 9.05 13.2 9.55 "
            "12.55 10.25 C12.05 10.8 11.85 11.4 11.85 12.35 "
            "H9.8 C9.8 11.05 10.15 10.05 10.95 9.2 C11.45 8.65 12.05 8.3 "
            "12.05 7.85 C12.05 7.5 11.8 7.3 11.45 7.3 "
            "C11.1 7.3 10.85 7.6 10.8 8.2 Z",
        ),
        path(capsule(8.8, 19, 15.2, 19, 2)),
        path(capsule(10.1, 21.1, 13.9, 21.1, 1.6), HIGHLIGHT),
        min_holes=1,
    ),
    "camera": sym(
        "Camera", "media",
        path(rect(7.25, 3.25, 9.5, 5.5, 2)),
        compound(
            rect(2.25, 6.25, 19.5, 14.75, 3.1),
            circle(12, 13.6, 4.6),
        ),
        path(ring(12, 13.6, 3.3, 1.3)),
        path(circle(18.4, 9.35, 1.1), HIGHLIGHT),
        min_holes=2,
    ),
    "car": sym(
        "Vehicle", "devices",
        compound(
            "M2.25 12.5 L4.75 7.1 A2.5 2.5 0 0 1 7.05 5.65 H16.95 "
            "A2.5 2.5 0 0 1 19.25 7.1 L21.75 12.5 V17.7 "
            "A2.05 2.05 0 0 1 19.7 19.75 H4.3 A2.05 2.05 0 0 1 2.25 17.7 Z",
            polygon(((7, 7.65), (11.05, 7.65), (11.05, 11), (5.5, 11))),
            polygon(((12.95, 7.65), (17, 7.65), (18.5, 11), (12.95, 11))),
            circle(6.5, 18.2, 1.35),
            circle(17.5, 18.2, 1.35),
        ),
        path(capsule(5, 14.2, 8, 14.2, 1.5), HIGHLIGHT),
        min_holes=4,
    ),
    "chat": sym(
        "Chat", "communication",
        compound(
            "M5.2 3.25 H18.8 A3 3 0 0 1 21.8 6.25 V13.25 "
            "A3 3 0 0 1 18.8 16.25 H11.1 L5 21 V16.2 "
            "A3 3 0 0 1 2.2 13.25 V6.25 A3 3 0 0 1 5.2 3.25 Z",
            capsule(6.4, 8.2, 17.6, 8.2, 1.8),
            capsule(6.4, 12.05, 14.2, 12.05, 1.8),
        ),
        min_holes=2,
    ),
    "check": sym(
        "Complete", "status",
        path(capsule(4.1, 12.4, 9.5, 17.55, 2.5)),
        path(capsule(9.15, 17.4, 20.15, 6.4, 2.5), HIGHLIGHT),
    ),
    "close": sym(
        "Close", "navigation",
        path(capsule(6.15, 6.15, 17.85, 17.85, 2.35)),
        path(capsule(17.85, 6.15, 6.15, 17.85, 2.35)),
    ),
    "code": sym(
        "Code", "development",
        path(polygon(((9.2, 5.2), (2.75, 12), (9.2, 18.8), (10.8, 16.7), (6.35, 12), (10.8, 7.3)))),
        path(polygon(((14.8, 5.2), (21.25, 12), (14.8, 18.8), (13.2, 16.7), (17.65, 12), (13.2, 7.3)))),
        path(capsule(13.9, 3.8, 10.1, 20.2, 1.9), HIGHLIGHT),
    ),
    "compass": sym(
        "Explore", "navigation",
        path(ring(12, 12, 9.5, 7.25)),
        path(polygon(((16.9, 6.4), (13.65, 13.45), (7.1, 17.6), (10.35, 10.55)))),
        path(polygon(((16.9, 6.4), (13.65, 13.45), (10.35, 10.55))), HIGHLIGHT),
        min_holes=1,
    ),
    "container": sym(
        "Container", "software",
        compound(
            rect(2.25, 6.25, 19.5, 14.5, 2.1),
            rect(4.4, 9, 15.2, 8.9, .7),
        ),
        path(capsule(7.4, 9.6, 7.4, 17.3, 1.55)),
        path(capsule(12, 9.6, 12, 17.3, 1.55), HIGHLIGHT),
        path(capsule(16.6, 9.6, 16.6, 17.3, 1.55)),
        path(polygon(((4.2, 6.25), (7.2, 3.25), (16.8, 3.25), (19.8, 6.25)))),
        min_holes=1,
    ),
    "copy": sym(
        "Copy", "editing",
        path(rounded_ring(2.25, 6.2, 13.6, 15.55, 3, 2.15)),
        compound(
            rect(7.1, 2.25, 14.65, 15.5, 3),
            rect(9.35, 4.5, 10.15, 11, 1.15),
        ),
        path(capsule(11.25, 8, 17.6, 8, 1.65), HIGHLIGHT),
        min_holes=2,
    ),
    "cpu": sym(
        "Processor", "hardware",
        compound(rect(5.25, 5.25, 13.5, 13.5, 3), rect(8.1, 8.1, 7.8, 7.8, 1.2)),
        *tuple(path(capsule(x, 2.25, x, 5.25, 1.8)) for x in (8, 12, 16)),
        *tuple(path(capsule(x, 18.75, x, 21.75, 1.8)) for x in (8, 12, 16)),
        *tuple(path(capsule(2.25, y, 5.25, y, 1.8)) for y in (8, 12, 16)),
        *tuple(path(capsule(18.75, y, 21.75, y, 1.8)) for y in (8, 12, 16)),
        path(rect(10.1, 10.1, 3.8, 3.8, 1), HIGHLIGHT),
        min_holes=1,
    ),
    "cube": sym(
        "Cube", "objects",
        path(polygon(((12, 2.25), (21.3, 7.35), (12, 12.55), (2.7, 7.35)))),
        path(polygon(((2.7, 9.7), (10.85, 14.25), (10.85, 21.75), (2.7, 17.2)))),
        path(polygon(((13.15, 14.25), (21.3, 9.7), (21.3, 17.2), (13.15, 21.75))), HIGHLIGHT),
    ),
}

# ``sym`` keeps the common case concise.  The two semantic-state glyphs need a
# whole-symbol role, so they are assigned explicitly after the core literal.
SYMBOLS["danger"] = Symbol(
    "Critical warning",
    "status",
    (
        compound(
            regular_polygon(12, 12, 10, 8, -67.5),
            capsule(12, 7.2, 12, 13.7, 2.15),
            circle(12, 17, 1.15),
            role=ERROR,
        ),
    ),
    2,
)

SYMBOLS.update({
    "database": sym(
        "Database", "data",
        compound(
            "M12 2.5 C17.1 2.5 20.25 4.05 20.25 6.3 V17.75 "
            "C20.25 20.05 17.1 21.5 12 21.5 C6.9 21.5 3.75 20.05 3.75 17.75 "
            "V6.3 C3.75 4.05 6.9 2.5 12 2.5 Z",
            capsule(6.05, 9.25, 17.95, 9.25, 1.7),
            capsule(6.05, 14.15, 17.95, 14.15, 1.7),
        ),
        path(capsule(14.7, 18.1, 17.8, 18.1, 1.55), HIGHLIGHT),
        min_holes=2,
    ),
    "diamond": sym(
        "Diamond", "objects",
        compound(
            polygon(((12, 2.25), (21.25, 9.1), (12, 21.75), (2.75, 9.1))),
            polygon(((12, 6.1), (16.7, 9.55), (12, 16.1), (7.3, 9.55))),
        ),
        path(polygon(((12, 2.25), (16.55, 9.1), (12, 7.65), (7.45, 9.1))), HIGHLIGHT),
        min_holes=1,
    ),
    "document": sym(
        "Document", "files",
        compound(
            "M5 2.25 H14.2 L19.5 7.55 V21.75 H5 Z",
            polygon(((14.2, 2.25), (19.5, 7.55), (14.2, 7.55))),
            capsule(8.3, 12, 16.2, 12, 1.65),
            capsule(8.3, 16.1, 14.5, 16.1, 1.65),
        ),
        path(polygon(((14.2, 2.25), (19.5, 7.55), (16.25, 7.55), (14.2, 5.5))), HIGHLIGHT),
        min_holes=3,
    ),
    "external": sym(
        "Open externally", "navigation",
        path(rounded_ring(2.25, 5.5, 16.25, 16.25, 2.8, 2.2)),
        path(capsule(10.3, 13.7, 20.2, 3.8, 2.1), HIGHLIGHT),
        path(polygon(((13.25, 2.25), (21.75, 2.25), (21.75, 10.75), (19.25, 8.25), (19.25, 6.5), (17.5, 6.5)))),
        min_holes=1,
    ),
    "flask": sym(
        "Laboratory", "development",
        compound(
            "M7.25 2.25 H16.75 V4.45 H15.35 V8.5 L20.65 18.1 "
            "A2.45 2.45 0 0 1 18.5 21.75 H5.5 A2.45 2.45 0 0 1 3.35 18.1 "
            "L8.65 8.5 V4.45 H7.25 Z",
            "M10.7 4.45 V9.05 L6.15 17.55 A1.2 1.2 0 0 0 7.2 19.35 "
            "H16.8 A1.2 1.2 0 0 0 17.85 17.55 L13.3 9.05 V4.45 Z",
        ),
        path(
            "M7.2 15.25 C9.2 13.85 10.8 15.95 12.55 14.7 "
            "C14.2 13.55 15.55 14.5 16.8 16.8 L17.65 18.35 "
            "A.65 .65 0 0 1 17.05 19.35 H6.95 A.65 .65 0 0 1 6.35 18.35 Z",
            HIGHLIGHT,
        ),
        min_holes=1,
    ),
    "gaming": sym(
        "Gaming", "media",
        compound(
            "M7.1 6.4 H16.9 C19.25 6.4 20.55 8.1 21 11.15 L21.75 16.5 "
            "C22.15 19.25 19.1 21 17.15 19.05 L14.6 16.45 H9.4 L6.85 19.05 "
            "C4.9 21 1.85 19.25 2.25 16.5 L3 11.15 C3.45 8.1 4.75 6.4 7.1 6.4 Z",
            circle(7.1, 11.75, 1.25),
            circle(16.7, 10.35, 1.05),
            circle(18.8, 13.05, 1.05),
        ),
        path(capsule(7.1, 9.3, 7.1, 14.2, 1.65)),
        path(capsule(4.65, 11.75, 9.55, 11.75, 1.65)),
        path(circle(16.7, 10.35, .88), HIGHLIGHT),
        path(circle(18.8, 13.05, .88), HIGHLIGHT),
        min_holes=0,
    ),
    "gem": sym(
        "Gem", "objects",
        compound(
            polygon(((7, 3), (17, 3), (21.5, 9.1), (12, 21.5), (2.5, 9.1))),
            polygon(((8.05, 5.5), (10.45, 8.35), (5.9, 8.35))),
            polygon(((15.95, 5.5), (18.1, 8.35), (13.55, 8.35))),
            polygon(((8.1, 10.6), (15.9, 10.6), (12, 17.1))),
        ),
        path(polygon(((10.6, 3), (13.4, 3), (12, 7.3))), HIGHLIGHT),
        min_holes=3,
    ),
    "globe": sym(
        "Web", "connectivity",
        path(ring(12, 12, 9.75, 7.6)),
        path(ellipse_ring(12, 12, 4.8, 9.2, 2.75, 9.2)),
        path(capsule(3.15, 12, 20.85, 12, 1.8), HIGHLIGHT),
        min_holes=2,
    ),
    "gpu": sym(
        "Graphics", "hardware",
        compound(
            rect(2.25, 4.25, 19.5, 15.5, 2.8),
            circle(10.2, 12, 4.5),
            rect(16.6, 8, 2.7, 1.8, .6),
            rect(16.6, 11.1, 2.7, 1.8, .6),
        ),
        path(ring(10.2, 12, 3.25, 1.25)),
        path(circle(10.2, 12, 1.25), HIGHLIGHT),
        path(capsule(5.5, 19.75, 5.5, 21.75, 1.5)),
        path(capsule(9, 19.75, 9, 21.75, 1.5)),
        min_holes=3,
    ),
    "grid": sym(
        "Grid", "layout",
        path(rect(2.5, 2.5, 8, 8, 2.2)),
        path(rect(13.5, 2.5, 8, 8, 2.2), HIGHLIGHT),
        path(rect(2.5, 13.5, 8, 8, 2.2)),
        path(rect(13.5, 13.5, 8, 8, 2.2)),
    ),
    "home": sym(
        "Home", "places",
        compound(
            polygon(((2.25, 10.5), (12, 2.25), (21.75, 10.5), (19.5, 12.4), (19.5, 21.5), (4.5, 21.5), (4.5, 12.4))),
            rect(9.5, 14.2, 5, 7.3, 1.1),
            rect(6.2, 10.8, 3.1, 3.1, .7),
        ),
        path(rect(14.9, 10.8, 2.9, 2.9, .7), HIGHLIGHT),
        min_holes=1,
    ),
    "identity": sym(
        "MoOS identity", "identity",
        path(star(11.4, 10.8, 8.3, 2.55, 4)),
        path(arc_band(11.3, 12, 10.2, 8.15, 35, 145)),
        path(circle(19.4, 18.4, 1.65), HIGHLIGHT),
    ),
    "install": sym(
        "Install", "software",
        path(capsule(12, 2.5, 12, 13.6, 2.3)),
        path(polygon(((6.8, 10.3), (12, 16.3), (17.2, 10.3), (14.15, 10.3), (12, 12.8), (9.85, 10.3))), HIGHLIGHT),
        compound(
            rect(3.25, 14.15, 17.5, 7.6, 2.5),
            rect(5.5, 14.15, 13, 4.9, 1),
        ),
        min_holes=0,
    ),
    "joystick": sym(
        "Joystick", "devices",
        path(circle(12, 4.75, 2.5), HIGHLIGHT),
        path(capsule(12, 7.1, 12, 14.9, 2.2)),
        compound(
            "M12 13.4 C7.2 13.4 4.2 16.4 3.25 21.75 H20.75 "
            "C19.8 16.4 16.8 13.4 12 13.4 Z",
            capsule(8.4, 18.25, 15.6, 18.25, 1.8),
        ),
        min_holes=1,
    ),
    "keyboard": sym(
        "Keyboard", "devices",
        compound(rect(2.25, 4.5, 19.5, 15, 2.6), rect(4.35, 6.6, 15.3, 10.8, .8)),
        *tuple(path(rect(x, y, 2.15, 2.05, .55)) for y in (8, 11.25) for x in (5.2, 8.4, 11.6, 14.8)),
        path(rect(7.15, 14.55, 9.7, 1.9, .7), HIGHLIGHT),
        min_holes=1,
    ),
    "lock": sym(
        "Lock", "security",
        path(rounded_ring(6.3, 2.25, 11.4, 12.5, 5.7, 2.2)),
        compound(
            rect(3.75, 10, 16.5, 11.75, 2.8),
            "M12 13.45 C10.75 13.45 9.95 14.3 9.95 15.35 "
            "C9.95 16.15 10.35 16.7 10.95 17.05 V19 H13.05 "
            "V17.05 C13.65 16.7 14.05 16.15 14.05 15.35 "
            "C14.05 14.3 13.25 13.45 12 13.45 Z",
        ),
        min_holes=2,
    ),
    "mail": sym(
        "Mail", "communication",
        path(rounded_ring(2.25, 4.25, 19.5, 15.5, 2.8, 2.15)),
        path(capsule(4.5, 6.8, 12, 12.6, 1.9)),
        path(capsule(19.5, 6.8, 12, 12.6, 1.9), HIGHLIGHT),
        min_holes=1,
    ),
    "memory": sym(
        "Memory", "hardware",
        compound(
            rect(2.25, 6.2, 19.5, 11.6, 2.4),
            *tuple(rect(x, 9, 2.7, 5.7, .65) for x in (5, 9.2, 13.4, 17.6)),
        ),
        *tuple(path(capsule(x, 3.25, x, 6.2, 1.55)) for x in (6.2, 10.1, 14, 17.9)),
        *tuple(path(capsule(x, 17.8, x, 20.75, 1.55)) for x in (6.2, 10.1, 14, 17.9)),
        path(rect(17.6, 9, 2.7, 5.7, .65), HIGHLIGHT),
        # The fourth bay is the accent facet, so three remain transparent in
        # the monochrome mask while the module still reads as four-wide.
        min_holes=3,
    ),
    "microphone": sym(
        "Microphone", "media",
        compound(rect(8.1, 2.25, 7.8, 13.1, 3.9), capsule(12, 5.1, 12, 10.7, 1.8)),
        path(arc_band(12, 10.8, 7.5, 5.45, 0, 180)),
        path(capsule(12, 17.3, 12, 21.25, 2)),
        path(capsule(8.2, 21.25, 15.8, 21.25, 2), HIGHLIGHT),
        min_holes=1,
    ),
    "moon": sym(
        "Dark appearance", "appearance",
        path(
            "M20.35 14.45 A9.2 9.2 0 1 1 9.55 3.65 "
            "A8.35 8.35 0 0 0 20.35 14.45 Z"
        ),
        path(circle(17.8, 17.25, 1.15), HIGHLIGHT),
    ),
    "mouse": sym(
        "Mouse", "devices",
        compound(rect(6.1, 2.25, 11.8, 19.5, 5.9), rect(8.3, 4.45, 7.4, 14.9, 3.7)),
        path(capsule(12, 3.2, 12, 9, 1.8)),
        path(capsule(12, 6.1, 12, 8.4, 2.3), HIGHLIGHT),
        min_holes=1,
    ),
    "music": sym(
        "Music", "media",
        path(rect(8.2, 5, 2.15, 12.6, 1)),
        path(polygon(((8.2, 5), (20.2, 2.25), (20.2, 5.4), (8.2, 8.15)))),
        path(rect(18.05, 4.2, 2.15, 10.4, 1), HIGHLIGHT),
        path(ellipse(6.5, 18.2, 3.2, 2.55)),
        path(ellipse(16.35, 15.25, 3.2, 2.55), HIGHLIGHT),
    ),
    "network": sym(
        "Network", "connectivity",
        path(capsule(12, 6.2, 5.4, 17.5, 2)),
        path(capsule(12, 6.2, 18.6, 17.5, 2), HIGHLIGHT),
        path(capsule(5.4, 17.5, 18.6, 17.5, 2)),
        path(circle(12, 5, 3)),
        path(circle(4.75, 18.5, 3)),
        path(circle(19.25, 18.5, 3)),
    ),
    "optimize": sym(
        "Optimise", "system",
        path(capsule(2.25, 7.1, 21.75, 7.1, 2)),
        path(capsule(2.25, 16.9, 21.75, 16.9, 2)),
        path(ring(7.6, 7.1, 3.15, 1.15)),
        path(ring(16.4, 16.9, 3.15, 1.15)),
        path(star(19.25, 4, 2.3, .75, 4), HIGHLIGHT),
        min_holes=0,
    ),
    "orbit": sym(
        "Orbit", "science",
        path(rotated_ellipse_ring(12, 12, 10.4, 4.45, 8.25, 2.35, -34)),
        path(circle(12, 12, 3.2)),
        path(circle(12, 12, 1.2), HIGHLIGHT),
        path(circle(19.2, 7.25, 1.65), HIGHLIGHT),
        min_holes=2,
    ),
    "pen": sym(
        "Create", "editing",
        compound(
            polygon(((3.15, 20.85), (5.35, 14.75), (16.15, 3.95), (20.05, 7.85), (9.25, 18.65))),
            capsule(8, 15.15, 16.55, 6.6, 1.35),
        ),
        path(polygon(((3.15, 20.85), (5.35, 14.75), (9.25, 18.65))), HIGHLIGHT),
        path(capsule(16.3, 4.1, 19.9, 7.7, 1.8)),
        min_holes=1,
    ),
    "phone": sym(
        "Phone", "devices",
        compound(rect(5.5, 2.25, 13, 19.5, 3.4), rect(7.7, 5.1, 8.6, 12.8, 1.1)),
        path(capsule(10.2, 4, 13.8, 4, 1.25)),
        path(capsule(10.2, 19.7, 13.8, 19.7, 1.55), HIGHLIGHT),
        min_holes=1,
    ),
    "power": sym(
        "Power", "system",
        path(arc_band(12, 12.2, 9.55, 7.25, 48, 312)),
        path(circle(5.6, 6.8, 1.15)),
        path(circle(18.4, 6.8, 1.15)),
        path(capsule(12, 2.25, 12, 11.8, 2.4), HIGHLIGHT),
        min_holes=0,
    ),
    "refresh": sym(
        "Refresh", "navigation",
        path(arc_band(12, 12, 9.6, 7.35, 185, 345)),
        path(polygon(((18.4, 3.1), (21.75, 9.2), (14.85, 8.4)))),
        path(arc_band(12, 12, 9.6, 7.35, 5, 165), HIGHLIGHT),
        path(polygon(((5.6, 20.9), (2.25, 14.8), (9.15, 15.6)))),
    ),
    "repair": sym(
        "Repair", "system",
        path(
            "M14.2 2.45 C11.05 3.1 9.1 6.15 9.8 9.25 L3.1 15.95 "
            "A3.45 3.45 0 1 0 7.95 20.85 L14.65 14.15 "
            "C17.75 14.85 20.8 12.9 21.45 9.75 L17.55 11.45 "
            "L14.1 8 L15.8 4.55 Z"
        ),
        path(circle(6.05, 17.9, 1.2), HIGHLIGHT),
        path(star(19.2, 17.7, 2.55, .82, 4), HIGHLIGHT),
    ),
    "report": sym(
        "Report", "files",
        compound(
            "M4.5 2.25 H14 L19.5 7.75 V21.75 H4.5 Z",
            polygon(((14, 2.25), (19.5, 7.75), (14, 7.75))),
            capsule(7.7, 11.2, 15.9, 11.2, 1.55),
            capsule(7.7, 14.7, 12.1, 14.7, 1.55),
        ),
        path(capsule(12.1, 18.15, 14.35, 20.2, 1.75), HIGHLIGHT),
        path(capsule(14.15, 20.05, 19.8, 14.9, 1.75), HIGHLIGHT),
        min_holes=2,
    ),
    "safe-update": sym(
        "Safe update", "security",
        compound(
            "M12 2.25 L20 5.55 V11.7 C20 16.35 17.05 19.75 12 21.75 "
            "C6.95 19.75 4 16.35 4 11.7 V5.55 Z",
            "M12 5.1 L17.65 7.45 V11.55 C17.65 14.75 15.8 17.25 12 18.95 "
            "C8.2 17.25 6.35 14.75 6.35 11.55 V7.45 Z",
        ),
        path(arc_band(12, 11.9, 4.7, 2.85, 195, 345), HIGHLIGHT),
        path(polygon(((14.8, 7.35), (17.2, 11.2), (12.65, 10.65))), HIGHLIGHT),
        path(arc_band(12, 11.9, 4.7, 2.85, 15, 165)),
        path(polygon(((9.2, 16.45), (6.8, 12.6), (11.35, 13.15)))),
        min_holes=1,
    ),
    "search": sym(
        "Search", "navigation",
        path(ring(10.2, 10.2, 7.75, 5.5)),
        path(capsule(15.3, 15.3, 21, 21, 2.55), HIGHLIGHT),
        min_holes=1,
    ),
    "settings": sym(
        "Settings", "system",
        path(
            f"{regular_polygon(12, 12, 9.75, 12, -75)} "
            f"{circle(12, 12, 5.9)}"
        ),
        path(ring(12, 12, 4.45, 2.1), HIGHLIGHT),
        min_holes=2,
    ),
    "shield": sym(
        "Shield", "security",
        compound(
            "M12 2.25 L20.25 5.65 V11.7 C20.25 16.45 17.25 19.75 12 21.75 "
            "C6.75 19.75 3.75 16.45 3.75 11.7 V5.65 Z",
            "M12 6.2 L17.2 8.3 V11.6 C17.2 14.4 15.55 16.55 12 18.1 "
            "C8.45 16.55 6.8 14.4 6.8 11.6 V8.3 Z",
        ),
        path(polygon(((12, 6.2), (17.2, 8.3), (17.2, 11.6), (12, 12.8))), HIGHLIGHT),
        min_holes=1,
    ),
    "spark": sym(
        "Spark", "status",
        path(star(12, 12, 9.75, 2.65, 4)),
        path(star(18.9, 4.7, 2.4, .78, 4), HIGHLIGHT),
    ),
    "star": sym(
        "Favourite", "status",
        path(star(12, 12.2, 10, 4.5, 5)),
        path(circle(12, 12, 1.25), HIGHLIGHT),
    ),
    "storage": sym(
        "Storage", "hardware",
        compound(
            rect(2.5, 3.25, 19, 17.5, 3),
            rect(4.75, 5.5, 14.5, 4.4, 1),
            rect(4.75, 12.1, 14.5, 4.4, 1),
        ),
        path(capsule(6.3, 8.1, 13.2, 8.1, 1.55)),
        path(capsule(6.3, 14.7, 13.2, 14.7, 1.55)),
        path(circle(17.1, 14.7, 1.15), HIGHLIGHT),
        min_holes=2,
    ),
    "sun": sym(
        "Light appearance", "appearance",
        path(circle(12, 12, 4.8), HIGHLIGHT),
        *tuple(
            path(capsule(
                12 + 7.1 * math.cos(math.radians(angle)),
                12 + 7.1 * math.sin(math.radians(angle)),
                12 + 9.4 * math.cos(math.radians(angle)),
                12 + 9.4 * math.sin(math.radians(angle)),
                1.9,
            ))
            for angle in range(0, 360, 45)
        ),
    ),
    "system": sym(
        "System", "system",
        compound(rect(2.25, 3.25, 19.5, 14.8, 3), rect(4.55, 5.55, 14.9, 10.2, .9)),
        path(capsule(12, 18.05, 12, 21, 2)),
        path(capsule(7.8, 21, 16.2, 21, 2)),
        path(polygon(((12, 7.4), (15.4, 10.65), (12, 14), (8.6, 10.65))), HIGHLIGHT),
        min_holes=1,
    ),
    "target": sym(
        "Target", "navigation",
        path(ring(12, 12, 9.75, 7.65)),
        path(ring(12, 12, 5.9, 3.85)),
        path(circle(12, 12, 1.8), HIGHLIGHT),
        min_holes=2,
    ),
    "trash": sym(
        "Remove", "editing",
        compound(
            "M5 6.5 H19 L17.6 21.75 H6.4 Z",
            capsule(9.3, 10, 9.8, 18.2, 1.55),
            capsule(14.7, 10, 14.2, 18.2, 1.55),
        ),
        path(rect(3.25, 4.55, 17.5, 2.4, 1.2)),
        path(rounded_ring(8, 2.25, 8, 4.4, 2, 1.65), HIGHLIGHT),
        min_holes=3,
    ),
    "ui": sym(
        "MoOS UI", "identity",
        path(polygon(((12, 2.25), (21.4, 7.15), (12, 12.05), (2.6, 7.15))), HIGHLIGHT),
        path(polygon(((3.2, 11), (12, 15.6), (20.8, 11), (20.8, 13.65), (12, 18.25), (3.2, 13.65)))),
        path(polygon(((3.2, 16.1), (12, 20.7), (20.8, 16.1), (20.8, 18.75), (12, 21.75), (3.2, 18.75)))),
    ),
    "usb": sym(
        "USB", "devices",
        path(capsule(12, 4.1, 12, 19.5, 2)),
        path(polygon(((12, 2.25), (8.6, 6.25), (10.9, 6.25), (12, 4.9), (13.1, 6.25), (15.4, 6.25)))),
        path(capsule(12, 11.5, 17.8, 11.5, 2), HIGHLIGHT),
        path(capsule(17.8, 11.5, 17.8, 15, 2), HIGHLIGHT),
        path(circle(17.8, 16.7, 2.1), HIGHLIGHT),
        path(capsule(12, 14.1, 7, 14.1, 2)),
        path(capsule(7, 14.1, 7, 17.3, 2)),
        path(rect(4.9, 17.3, 4.2, 4.2, 1)),
        path(circle(12, 20.2, 1.8)),
    ),
    "video": sym(
        "Video", "media",
        compound(rect(2.25, 5.25, 14.5, 13.5, 3), rect(4.55, 7.55, 9.9, 8.9, .9)),
        path(polygon(((15.4, 9.5), (21.75, 6.5), (21.75, 17.5), (15.4, 14.5))), HIGHLIGHT),
        min_holes=1,
    ),
    "warning": Symbol(
        "Warning",
        "status",
        (
            compound(
                polygon(((12, 2.25), (21.75, 20.75), (2.25, 20.75))),
                capsule(12, 8.1, 12, 14.25, 2.05),
                circle(12, 17.45, 1.08),
                role=WARNING,
            ),
        ),
        2,
    ),
    "wave": sym(
        "Audio wave", "media",
        path(capsule(2.75, 12, 5.1, 12, 2)),
        path(capsule(8, 8.25, 8, 15.75, 2.15)),
        path(capsule(12, 4.25, 12, 19.75, 2.15), HIGHLIGHT),
        path(capsule(16, 7.2, 16, 16.8, 2.15)),
        path(capsule(18.9, 12, 21.25, 12, 2)),
    ),
})


ROLE_STYLE = {
    TEXT: ("ColorScheme-Text", "#2e3436"),
    # GTK has no accent channel.  It intentionally treats Highlight as the
    # foreground mask; KDE substitutes the live accent through this class.
    HIGHLIGHT: ("ColorScheme-Highlight", "#2e3436"),
    WARNING: ("ColorScheme-NeutralText warning", "#ff7800"),
    ERROR: ("ColorScheme-NegativeText error", "#e01b24"),
}

DEFAULT_PALETTE = {
    TEXT: "#243238",
    HIGHLIGHT: "#147d72",
    WARNING: "#8a5a00",
    ERROR: "#a9364b",
}


def palette_style(palette: dict[str, str] | None = None) -> str:
    """Return the KDE colour-role stylesheet for one icon-theme palette.

    KIconLoader resolves action icons through the active icon theme and keeps
    the stylesheet's fallback colours when rendering them as a normal QIcon.
    Therefore copying the same light fallback SVG into both light and dark icon
    themes makes the dark desktop draw almost-black symbols.  The geometry
    remains one source, while each generated icon-theme overlay receives the
    exact semantic ink/accent/warning/error roles of its look-and-feel.
    """
    roles = DEFAULT_PALETTE if palette is None else palette
    return f"""  <style id="current-color-scheme" type="text/css">
    .ColorScheme-Text {{ color: {roles[TEXT]}; fill: currentColor; }}
    .ColorScheme-Highlight {{ color: {roles[HIGHLIGHT]}; fill: currentColor; }}
    .ColorScheme-NeutralText {{ color: {roles[WARNING]}; fill: currentColor; }}
    .ColorScheme-NegativeText {{ color: {roles[ERROR]}; fill: currentColor; }}
  </style>"""


STYLE = palette_style()


def render(
    name: str,
    symbol: Symbol,
    palette: dict[str, str] | None = None,
) -> str:
    paths = []
    for shape in symbol.shapes:
        class_name, fallback = ROLE_STYLE[shape.role]
        paths.append(
            f'  <path class="{class_name}" fill="{fallback}" '
            f'fill-rule="evenodd" d="{shape.d}"/>'
        )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"
     role="img" aria-labelledby="{name}-title">
  <title id="{name}-title">{symbol.title}</title>
{palette_style(palette)}
{chr(10).join(paths)}
</svg>
"""


def expected_outputs() -> dict[Path, str]:
    return {
        OUTPUT / f"moos-{name}-symbolic.svg": render(name, symbol)
        for name, symbol in SYMBOLS.items()
    }


def manifest_source() -> str:
    lines = "\n".join(
        f'    "moos-{name}-symbolic",'
        for name in SYMBOLS
    )
    return f"""// Generated by generate_moos_symbolic_icons.py; do not edit.
.pragma library

var iconNames = [
{lines}
]
"""


def runtime_manifest_source() -> str:
    names = "\n".join(
        f'    "{name}": true,'
        for name in SYMBOLS
    )
    return f"""// Generated by generate_moos_symbolic_icons.py; do not edit.
.pragma library

var symbolNames = ({{
{names}
}})

function resolve(name) {{
    var candidate = String(name || "spark")
    return symbolNames[candidate]
        ? "moos-" + candidate + "-symbolic"
        : "moos-spark-symbolic"
}}
"""


def map_source() -> str:
    rows = "\n".join(
        f"| `{name}` | {symbol.title} | {symbol.category} |"
        for name, symbol in SYMBOLS.items()
    )
    return f"""# MoOS Tidal Cut symbolic icon map

`Tidal Cut` is MoOS's owned action-icon language. Its single geometry source is
[`generate_moos_symbolic_icons.py`](generate_moos_symbolic_icons.py), which
generates all {len(SYMBOLS)} SVGs and
[`moos_symbolic_manifest.js`](moos_symbolic_manifest.js). The visual harness
imports that manifest; it does not carry a second hand-maintained name list.
Application launch icons and the MoOS / Mo AI identity marks remain separate
full-colour assets. These symbols are interface actions, states, and categories.

## Measured rendering contract

- Grid: 24 × 24 units; painted geometry stays within 2.25…21.75 so the outer
  pixel remains empty at 16, 20, 24, 64, and 128 px.
- Structural weight: 2.0–2.25 units for primary ribbons and terminals
  (1.33–1.50 physical px at the 16 px target). Rounded capsules prevent brittle
  diagonal ends and make small icons read at a glance.
- Construction: filled `<path>` elements only. There are no SVG strokes,
  `fill="none"`, filters, gradients, raster images, or background plates.
- `ColorScheme-Text` follows the live foreground in KDE.
  `ColorScheme-Highlight` follows the live accent in KDE and degrades to the
  foreground channel under GTK's symbolic-mask renderer. Accent details are
  never required to understand the silhouette.
- Warning uses both KDE's `ColorScheme-NeutralText` and GTK's `warning`
  channel. Critical danger uses `ColorScheme-NegativeText` / GTK `error`, and
  has a deliberately different octagonal silhouette rather than relying on
  colour alone.
- Review targets: 16 and 20 px for compact chrome, 24 px for controls, 64 and
  128 px for feature surfaces. Glyph size never substitutes for a minimum
  40-logical-pixel hit target.

## Why the family is different

The family uses a solid silhouette plus one deliberate open counter — the
“cut” — instead of generic monoline outlines. Its rounded tidal ribbons carry
enough ink at 16 px, while offset highlight facets add depth in KDE without
turning the glyph into a multicolour illustration. Semantics remain legible in
one colour and in high-contrast GTK masking.

## Inventory

| Name (without `moos-` / `-symbolic`) | Meaning | Category |
|---|---|---|
{rows}

## Verification

```bash
python3 artwork/generate_moos_symbolic_icons.py --check
python3 tests/test_moos_symbolic_icons.py
python3 tests/test_moos_symbolic_runtime.py
```

The static gate proves source determinism and the path-only/role contract. The
runtime gate asks GTK's real `IconTheme` and KDE's `kiconfinder6` to resolve the
assets, then rasterises both light and dark symbolic palettes at all five
review sizes. It rejects empty or clipped output, missing internal counters,
and indistinguishable alpha silhouettes.
"""


def _write(path_: Path, content: str) -> None:
    path_.parent.mkdir(parents=True, exist_ok=True)
    path_.write_text(content, encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if committed SVG, manifest, or map output is stale",
    )
    args = parser.parse_args()

    expected = expected_outputs()
    generated = {
        **expected,
        MANIFEST: manifest_source(),
        RUNTIME_MANIFEST: runtime_manifest_source(),
        MAP: map_source(),
    }
    if args.check:
        stale = [
            path_.relative_to(ROOT)
            for path_, content in generated.items()
            if not path_.is_file() or path_.read_text(encoding="utf-8") != content
        ]
        legacy = sorted(
            path_.relative_to(ROOT)
            for path_ in OUTPUT.glob("moos-*.svg")
            if path_ not in expected
        )
        if stale or legacy:
            for path_ in stale:
                print(f"stale or missing: {path_}")
            for path_ in legacy:
                print(f"legacy unmanaged symbol: {path_}")
            raise SystemExit(1)
        print(f"MoOS Tidal Cut symbolic family is current ({len(expected)} SVGs)")
        return

    OUTPUT.mkdir(parents=True, exist_ok=True)
    for legacy in OUTPUT.glob("moos-*.svg"):
        if legacy not in expected:
            legacy.unlink()
    for path_, content in generated.items():
        _write(path_, content)
    print(f"generated {len(expected)} MoOS Tidal Cut symbolic action icons")


if __name__ == "__main__":
    main()
