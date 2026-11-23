#!/usr/bin/env python3
"""Generate the slim MoOS window frame (Aurorae v2) for every MoOS look.

Owner steering, 2026-11-23: the frames were liked but read heavy. They must be
slim, belong to the applications inside them, stay distinctive in every theme
and keep the window actions clear on tablets and large screens.

One generated geometry now serves all eighteen looks (the sixteen UI2 family
frames and both Bloom frames), each with its own colour-scheme roles:

* Title bar: 44 logical px, restored and maximized. Its base colour
  is the look's Header/Window background, the colour KDE toolbars paint right
  below it, so a toolbar continues the bar without a seam. A faint lift toward
  the top edge and a 1 px catch-light on the active window keep it glass.
* No side or bottom border. MoOS ships KWin's BorderSize=None
  (etc/xdg/kwinrc): the client reaches the frame edge and KWin's invisible
  resize-only borders take the drag, as Breeze does by default in Plasma 6.
  Aurorae 6.8.3 otherwise clamps the "Normal" size to a painted 4 px band on
  three sides, which is what made the old frames read thick. A user who picks
  a border size still gets it, painted in the title colour.
* A 1 px hairline traces the window just outside its rectangle and around the
  12 px top corners, over a soft shadow reaching 24 px to the sides and above
  and 34 px below. Qt SVG has no blur filter, so the shadow is built from
  gradients whose profiles agree at every 9-slice seam (the corner gradients
  are centred on the window's own corner geometry, not on the tile corner).
* Window actions keep a 44 px wide native input extent over the full bar
  height. The visible tile is 30 x 24 with the MoOS corner: three 8 px
  corners and the top-left squared (FrameSvg cannot mirror, so it is
  Arabic-first, like the popup and desktop-card frames). Glyphs are the
  original MoOS set; semantic colour appears on interaction and close turns
  solid. Aurorae's own ButtonSize factor (auroraerc) scales the bar, the
  targets and the artwork together.
"""

from __future__ import annotations

import pathlib
import re
import xml.etree.ElementTree as ET
from collections.abc import Mapping


FRAME_POSITIONS = (
    "topleft", "top", "topright",
    "left", "center", "right",
    "bottomleft", "bottom", "bottomright",
)

BUTTON_STATES = (
    "active",
    "inactive",
    "hover",
    "hover-inactive",
    "pressed",
    "pressed-inactive",
    "deactivated",
    "deactivated-inactive",
)

BUTTONS = (
    "close",
    "minimize",
    "maximize",
    "restore",
    "help",
    "alldesktops",
    "keepabove",
    "keepbelow",
    "shade",
    "appmenu",
)

# Geometry, logical px at ButtonSize "Normal".
TITLE = 44
ACTION_WIDTH = 44
ACTION_SPACING = 2
# kwinrc puts the three actions (XIA) on one side and one spacer `_` on the
# other; the spacer is exactly this wide so the caption centres on the window.
ACTION_GROUP = 3 * ACTION_WIDTH + 2 * ACTION_SPACING
RADIUS = 12
# Shadow reach. Sides and top are equal so one circle serves each top corner.
SIDE = 24
BOTTOM = 34
MIDDLE = 24
# The visible action tile inside its 44 x 44 target (x, y, width, height).
TILE = (7.0, (TITLE - 24) / 2, 30.0, 24.0)
TILE_RADIUS = 8.0
TILE_SQUARE = 2.5

# Frame template coordinates.
LEFT_EDGE = SIDE                       # the window's left edge
LEFT_COLUMN = SIDE + RADIUS            # end of the left 9-slice column
RIGHT_COLUMN = LEFT_COLUMN + MIDDLE    # start of the right column
RIGHT_EDGE = RIGHT_COLUMN + RADIUS     # the window's right edge
WIDTH = RIGHT_EDGE + SIDE
TOP_EDGE = SIDE                        # the window's top edge
ARC_Y = SIDE + RADIUS                  # centre row of the top corner arcs
TITLE_END = SIDE + TITLE               # end of the top 9-slice row
BOTTOM_EDGE = TITLE_END + MIDDLE       # the window's bottom edge
HEIGHT = BOTTOM_EDGE + BOTTOM

# Shadow opacity over its reach (0 = at the window edge, 1 = fully faded).
PROFILE = ((0.0, 1.0), (0.12, 0.72), (0.3, 0.42), (0.55, 0.17), (0.8, 0.05), (1.0, 0.0))
INKS = ("#14202D", "#F1F5F4")


def _write(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def _channels(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[index:index + 2], 16) for index in (0, 2, 4))


def mix(ink: str, background: str, alpha: float) -> str:
    return "#" + "".join(f"{round(a * alpha + b * (1 - alpha)):02X}"
                         for a, b in zip(_channels(ink), _channels(background)))


def luminance(value: str) -> float:
    rgb = [channel / 255 for channel in _channels(value)]
    linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in rgb]
    return sum(v * w for v, w in zip(linear, (.2126, .7152, .0722)))


def contrast(one: str, other: str) -> float:
    lo, hi = sorted((luminance(one), luminance(other)))
    return (hi + .05) / (lo + .05)


def is_light(surface: str) -> bool:
    return luminance(surface) > 0.35


def secondary_ink(text: str, surface: str) -> str:
    """The dimmest blend of *text* over *surface* that still reads at 4.5:1."""
    for percent in range(60, 101):
        candidate = mix(text, surface, percent / 100)
        if contrast(candidate, surface) >= 4.5:
            return candidate
    raise SystemExit(f"text {text} is unreadable on the title surface {surface}")


def _ink_for(fill: str, *preferred: str) -> tuple[str, str]:
    """(fill, ink) at >= 4.5:1, preferring the given inks, moving the fill least."""
    for ink in (*preferred, *INKS):
        if contrast(ink, fill) >= 4.5:
            if ink in preferred:
                return fill, ink
            break
    for amount in range(0, 26):
        fills = [fill] if amount == 0 else [mix(end, fill, amount / 100) for end in INKS]
        pairs = [(candidate, ink) for candidate in fills for ink in (*preferred, *INKS)
                 if contrast(ink, candidate) >= 4.5]
        if pairs:
            return min(pairs, key=lambda pair: (
                sum(abs(a - b) for a, b in zip(_channels(fill), _channels(pair[0]))),
                pair[1] not in preferred))
    raise SystemExit(f"no readable window-action ink on {fill}")


def _glyph(name: str, colour: str) -> str:
    glyphs = {
        "close": (
            f'<rect x="9.15" y="5.3" width="1.7" height="9.4" rx=".85" '
            f'fill="{colour}" transform="rotate(45 10 10)"/>'
            f'<rect x="9.15" y="5.3" width="1.7" height="9.4" rx=".85" '
            f'fill="{colour}" transform="rotate(-45 10 10)"/>'
        ),
        "minimize": (
            # y centres the dash on (10,10) like every other glyph in the set:
            # 9.15 + 1.7/2 = 10. It sat at y=11.55 (centre 12.4, 12% low) and
            # the sag was visible beside the centred close/maximize glyphs —
            # measured 6 device px below the pill centre on the live session.
            f'<rect x="6.25" y="9.15" width="7.5" height="1.7" rx=".85" '
            f'fill="{colour}"/>'
        ),
        "maximize": (
            f'<path fill-rule="evenodd" d="M5.8 5.8h8.4v8.4H5.8Zm1.65 '
            f'1.65v5.1h5.1v-5.1Z" fill="{colour}"/>'
        ),
        "restore": (
            f'<path d="M7.65 5.6h6.75v6.75h-1.55v-5.2h-5.2Z" '
            f'fill="{colour}"/>'
            f'<path fill-rule="evenodd" d="M5.6 7.65h6.75v6.75H5.6Zm1.55 '
            f'1.55v3.65h3.65V9.2Z" fill="{colour}"/>'
        ),
        "help": (
            f'<path d="M9.9 5.15c-2.12 0-3.55 1.18-3.62 3.1h1.8c.08-.91 '
            f'.74-1.48 1.76-1.48 1.04 0 1.7.52 1.7 1.32 0 .69-.36 '
            f'1.02-1.28 1.58-1.13.69-1.42 1.25-1.42 2.55h1.72c0-.78.2-1.08 '
            f'1.26-1.74 1.06-.66 1.58-1.42 1.58-2.42 0-1.74-1.42-2.92-3.5-2.92Z" '
            f'fill="{colour}"/>'
            f'<circle cx="9.7" cy="14.12" r="1.02" fill="{colour}"/>'
        ),
        "alldesktops": (
            f'<path fill-rule="evenodd" d="M10 2.65a7.35 7.35 0 1 1 0 '
            f'14.7 7.35 7.35 0 0 1 0-14.7Zm0 1.55a5.8 5.8 0 1 0 0 '
            f'11.6 5.8 5.8 0 0 0 0-11.6Z" fill="{colour}" fill-opacity=".48"/>'
            f'<circle cx="10" cy="10" r="3.35" fill="{colour}"/>'
        ),
        "keepabove": (
            f'<path d="m5.45 11.12 4.55-4.55 4.55 4.55-1.18 1.18L10 '
            f'8.93 6.63 12.3Zm0-4.05L10 2.52l4.55 4.55-1.18 1.18L10 '
            f'4.88 6.63 8.25Z" fill="{colour}"/>'
        ),
        "keepbelow": (
            f'<path d="m5.45 8.88 1.18-1.18L10 11.07l3.37-3.37 1.18 '
            f'1.18L10 13.43Zm0 4.05 1.18-1.18L10 15.12l3.37-3.37 '
            f'1.18 1.18L10 17.48Z" fill="{colour}"/>'
        ),
        "shade": (
            f'<rect x="5.5" y="5.75" width="9" height="1.6" rx=".8" fill="{colour}"/>'
            f'<rect x="7" y="9.2" width="6" height="1.6" rx=".8" fill="{colour}"/>'
            f'<rect x="8.5" y="12.65" width="3" height="1.6" rx=".8" fill="{colour}"/>'
        ),
        "appmenu": (
            f'<rect x="5.5" y="5.65" width="9" height="1.7" rx=".85" fill="{colour}"/>'
            f'<rect x="5.5" y="9.15" width="9" height="1.7" rx=".85" fill="{colour}"/>'
            f'<rect x="5.5" y="12.65" width="9" height="1.7" rx=".85" fill="{colour}"/>'
        ),
    }
    return glyphs[name]



def _tile(x: float, y: float, w: float, h: float, r: float, s: float) -> str:
    """Three rounded corners and the top-left one squared (the MoOS corner)."""
    return (f"M{x + s:g} {y:g}H{x + w - r:g}A{r:g} {r:g} 0 0 1 {x + w:g} {y + r:g}"
            f"V{y + h - r:g}A{r:g} {r:g} 0 0 1 {x + w - r:g} {y + h:g}"
            f"H{x + r:g}A{r:g} {r:g} 0 0 1 {x:g} {y + h - r:g}"
            f"V{y + s:g}A{s:g} {s:g} 0 0 1 {x + s:g} {y:g}Z")


def _solid(fill: str) -> tuple[str, str]:
    """A solid destructive face with white ink, deepened only as far as 4.5:1 needs."""
    for amount in range(0, 41):
        candidate = mix("#000000", fill, amount / 100)
        if contrast("#F4F7FA", candidate) >= 4.5:
            return candidate, "#F4F7FA"
    return _ink_for(fill)


def _button_svg(name: str, p: Mapping[str, str]) -> str:
    surface, text = p["surface"], p["text"]
    semantic = {
        "close": p["negative"],
        "minimize": p["secondary"],
        "maximize": p["primary"],
        "restore": p["primary"],
        "help": p["secondary"],
        "alldesktops": p["primary"],
        "keepabove": p["secondary"],
        "keepbelow": p["secondary"],
        "shade": p["primary"],
        "appmenu": p["primary"],
    }[name]
    quiet = secondary_ink(text, surface)
    x, y, w, h = TILE
    cx, cy = x + w / 2, y + h / 2
    shape = _tile(x, y, w, h, TILE_RADIUS, TILE_SQUARE)
    # All actions share one quiet material at rest; colour identifies a state,
    # never a red/yellow/green traffic-light arrangement. Close turns solid.
    body: list[str] = []
    for state in BUTTON_STATES:
        inactive = state.endswith("-inactive") or state == "inactive"
        disabled = state.startswith("deactivated")
        hover = state.startswith("hover")
        pressed = state.startswith("pressed")
        if disabled:
            fill = mix(text, surface, .035)
            ink = mix(text, fill, .38)
        elif (hover or pressed) and name == "close":
            fill, ink = _solid(p["negative"])
            if pressed:
                fill, ink = _solid(mix("#000000", fill, .14))
        elif hover or pressed:
            fill, ink = _ink_for(mix(semantic, surface, .34 if pressed else .22), text)
        else:
            fill, ink = _ink_for(mix(text, surface, .045 if inactive else .085),
                                 quiet if inactive else text)
        if not disabled and contrast(ink, fill) < 4.5:
            raise SystemExit(f"{name}/{state}: window button ink has insufficient contrast")
        press = (f' transform="translate({cx:g} {cy:g}) scale(.94) translate({-cx:g} {-cy:g})"'
                 if pressed else "")
        body.append(
            f'  <g id="{state}-center"><rect width="{ACTION_WIDTH}" height="{TITLE}" fill="#000" '
            f'fill-opacity="0"/><g{press}><path data-moos-role="face" d="{shape}" fill="{fill}"/>'
            f'<g data-moos-role="glyph" transform="translate({cx:g} {cy:g}) scale(1.08) '
            f'translate(-10 -10)">{_glyph(name, ink)}</g></g></g>'
        )
    return "\n".join((
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{ACTION_WIDTH}" height="{TITLE}" '
        f'viewBox="0 0 {ACTION_WIDTH} {TITLE}">',
        f"  <!-- MoOS {name}: MoOS-corner tile, glyph visible at rest, semantic colour on "
        f"interaction. -->",
        *body,
        "</svg>",
    ))


def _stops(colour: str, alpha: float, start: float = 0.0, span: float = 1.0) -> str:
    return "".join(
        f'<stop offset="{start + t * span:.4f}" stop-color="{colour}" '
        f'stop-opacity="{alpha * a:.4f}"/>' for t, a in PROFILE)


def _shadow_defs(key: str, colour: str, alpha: float) -> str:
    """One shadow profile, distance-true at every seam.

    Edges fade linearly away from the window. The top corners are circles
    centred on the corner arcs (the true distance to a 12 px rounded corner);
    the square bottom corners are ellipses centred on the window corner, 24 px
    across and 34 px down, so both seams meet the edge ramps exactly.
    """
    arc = RADIUS / (RADIUS + SIDE)

    def linear(name: str, x1: int, y1: int, x2: int, y2: int) -> str:
        return (f'<linearGradient id="{key}sh-{name}" gradientUnits="userSpaceOnUse" '
                f'x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}">{_stops(colour, alpha)}</linearGradient>')

    def circle(name: str, cx: int) -> str:
        return (f'<radialGradient id="{key}sh-{name}" gradientUnits="userSpaceOnUse" cx="{cx}" '
                f'cy="{ARC_Y}" r="{RADIUS + SIDE}">{_stops(colour, alpha, arc, 1 - arc)}'
                f'</radialGradient>')

    def ellipse(name: str, cx: int) -> str:
        return (f'<radialGradient id="{key}sh-{name}" gradientUnits="userSpaceOnUse" cx="0" cy="0" '
                f'r="1" gradientTransform="matrix({SIDE} 0 0 {BOTTOM} {cx} {BOTTOM_EDGE})">'
                f'{_stops(colour, alpha)}</radialGradient>')

    return "".join((
        linear("left", LEFT_EDGE, 0, 0, 0),
        linear("right", RIGHT_EDGE, 0, WIDTH, 0),
        linear("top", 0, TOP_EDGE, 0, 0),
        linear("bottom", 0, BOTTOM_EDGE, 0, HEIGHT),
        circle("topleft", LEFT_COLUMN),
        circle("topright", RIGHT_COLUMN),
        ellipse("bottomleft", LEFT_EDGE),
        ellipse("bottomright", RIGHT_EDGE),
    ))


BOUNDS = {
    "topleft": (0, 0, LEFT_COLUMN, TITLE_END),
    "top": (LEFT_COLUMN, 0, MIDDLE, TITLE_END),
    "topright": (RIGHT_COLUMN, 0, WIDTH - RIGHT_COLUMN, TITLE_END),
    "left": (0, TITLE_END, LEFT_COLUMN, MIDDLE),
    "center": (LEFT_COLUMN, TITLE_END, MIDDLE, MIDDLE),
    "right": (RIGHT_COLUMN, TITLE_END, WIDTH - RIGHT_COLUMN, MIDDLE),
    "bottomleft": (0, BOTTOM_EDGE, LEFT_COLUMN, BOTTOM),
    "bottom": (LEFT_COLUMN, BOTTOM_EDGE, MIDDLE, BOTTOM),
    "bottomright": (RIGHT_COLUMN, BOTTOM_EDGE, WIDTH - RIGHT_COLUMN, BOTTOM),
}


def _rect(x: float, y: float, w: float, h: float, fill: str, opacity: float | None = None) -> str:
    alpha = "" if opacity is None else f' fill-opacity="{opacity:.3f}"'
    return f'<rect x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" fill="{fill}"{alpha}/>'


def _frame(prefix: str, key: str, *, surface: str | None, hairline: tuple[str, float] | None,
           catch: tuple[str, float] | None, shadow: bool) -> list[str]:
    L, LC, RC, RE = LEFT_EDGE, LEFT_COLUMN, RIGHT_COLUMN, RIGHT_EDGE
    T, A, TE, BE, r = TOP_EDGE, ARC_Y, TITLE_END, BOTTOM_EDGE, RADIUS
    paint: dict[str, list[str]] = {position: [] for position in FRAME_POSITIONS}
    if shadow:
        def sh(name: str) -> str:
            return f"url(#{key}sh-{name})"
        paint["topleft"] += [_rect(0, 0, LC, A, sh("topleft")), _rect(0, A, L, TE - A, sh("left"))]
        paint["top"] += [_rect(LC, 0, MIDDLE, T, sh("top"))]
        paint["topright"] += [_rect(RC, 0, WIDTH - RC, A, sh("topright")),
                              _rect(RE, A, SIDE, TE - A, sh("right"))]
        paint["left"] += [_rect(0, TE, L, MIDDLE, sh("left"))]
        paint["right"] += [_rect(RE, TE, SIDE, MIDDLE, sh("right"))]
        paint["bottomleft"] += [_rect(0, BE, L, BOTTOM, sh("bottomleft")),
                                _rect(L, BE, r, BOTTOM, sh("bottom"))]
        paint["bottom"] += [_rect(LC, BE, MIDDLE, BOTTOM, sh("bottom"))]
        paint["bottomright"] += [_rect(RC, BE, r, BOTTOM, sh("bottom")),
                                 _rect(RE, BE, SIDE, BOTTOM, sh("bottomright"))]
    if hairline:
        colour, alpha = hairline
        o = r + 1

        def line(x: float, y: float, w: float, h: float) -> str:
            return _rect(x, y, w, h, colour, alpha)
        paint["topleft"] += [
            f'<path d="M{L - 1} {A}A{o} {o} 0 0 1 {LC} {T - 1}V{T}A{r} {r} 0 0 0 {L} {A}Z" '
            f'fill="{colour}" fill-opacity="{alpha:.3f}"/>', line(L - 1, A, 1, TE - A)]
        paint["top"] += [line(LC, T - 1, MIDDLE, 1)]
        paint["topright"] += [
            f'<path d="M{RC} {T - 1}A{o} {o} 0 0 1 {RE + 1} {A}H{RE}A{r} {r} 0 0 0 {RC} {T}Z" '
            f'fill="{colour}" fill-opacity="{alpha:.3f}"/>', line(RE, A, 1, TE - A)]
        paint["left"] += [line(L - 1, TE, 1, MIDDLE)]
        paint["right"] += [line(RE, TE, 1, MIDDLE)]
        paint["bottomleft"] += [line(L - 1, BE, r + 1, 1)]
        paint["bottom"] += [line(LC, BE, MIDDLE, 1)]
        paint["bottomright"] += [line(RC, BE, r + 1, 1)]
    if surface is not None:
        title = f"url(#{key}title)"
        paint["topleft"].append(f'<path d="M{L} {TE}V{A}A{r} {r} 0 0 1 {LC} {T}V{TE}Z" fill="{title}"/>')
        paint["top"].append(_rect(LC, T, MIDDLE, TITLE, title))
        paint["topright"].append(f'<path d="M{RC} {T}A{r} {r} 0 0 1 {RE} {A}V{TE}H{RC}Z" fill="{title}"/>')
        # Only a user-chosen border size reveals these; Aurorae clamps it to >= 4 px.
        paint["left"].append(_rect(L, TE, r, MIDDLE, surface))
        paint["center"].append(_rect(LC, TE, MIDDLE, MIDDLE, surface))
        paint["right"].append(_rect(RC, TE, r, MIDDLE, surface))
    if catch:
        colour, alpha = catch
        i = r - 1
        paint["topleft"].append(
            f'<path d="M{L} {A}A{r} {r} 0 0 1 {LC} {T}V{T + 1}A{i} {i} 0 0 0 {L + 1} {A}Z" '
            f'fill="{colour}" fill-opacity="{alpha:.3f}"/>')
        paint["top"].append(_rect(LC, T, MIDDLE, 1, colour, alpha))
        paint["topright"].append(
            f'<path d="M{RC} {T}A{r} {r} 0 0 1 {RE} {A}H{RE - 1}A{i} {i} 0 0 0 {RC} {T + 1}Z" '
            f'fill="{colour}" fill-opacity="{alpha:.3f}"/>')
    pieces = []
    for position in FRAME_POSITIONS:
        x, y, w, h = BOUNDS[position]
        pieces.append(f'<g id="{prefix}-{position}"><rect x="{x}" y="{y}" width="{w}" '
                      f'height="{h}" fill="#000" fill-opacity="0"/>{"".join(paint[position])}</g>')
    return pieces


def frame_tones(p: Mapping[str, str]) -> dict[str, object]:
    """Every frame colour, derived from the look's title surface and text."""
    surface, text = p["surface"], p["text"]
    light = is_light(surface)
    return {
        "light": light,
        "surface": surface,
        "lift": mix("#F4F7FA", surface, .26 if light else .055),
        "lift_inactive": mix("#F4F7FA", surface, .10 if light else .02),
        "shadow": mix(text, "#000000", .35) if light else "#000000",
        "shadow_alpha": (.20, .12) if light else (.42, .26),
        "hairline": (("#000000", .14), ("#000000", .09)) if light else
                    (("#F4F7FA", .11), ("#F4F7FA", .07)),
        "catch": ("#F4F7FA", .70 if light else .10),
    }


def frame_svg(p: Mapping[str, str]) -> str:
    tone = frame_tones(p)
    surface = tone["surface"]
    defs = "".join((
        _shadow_defs("", tone["shadow"], tone["shadow_alpha"][0]),
        _shadow_defs("i-", tone["shadow"], tone["shadow_alpha"][1]),
        f'<linearGradient id="title" gradientUnits="userSpaceOnUse" x1="0" y1="{TOP_EDGE}" x2="0" '
        f'y2="{TITLE_END}"><stop offset="0" stop-color="{tone["lift"]}"/>'
        f'<stop offset="1" stop-color="{surface}"/></linearGradient>',
        f'<linearGradient id="i-title" gradientUnits="userSpaceOnUse" x1="0" y1="{TOP_EDGE}" x2="0" '
        f'y2="{TITLE_END}"><stop offset="0" stop-color="{tone["lift_inactive"]}"/>'
        f'<stop offset="1" stop-color="{surface}"/></linearGradient>',
    ))
    active_line, inactive_line = tone["hairline"]
    pieces: list[str] = []
    pieces += _frame("decoration", "", surface=surface, hairline=active_line,
                     catch=tone["catch"], shadow=True)
    pieces += _frame("decoration-inactive", "i-", surface=surface, hairline=inactive_line,
                     catch=None, shadow=True)
    # Inner-border consumers draw the edge over the client, leaving its centre transparent.
    for prefix, line in (("innerborder", active_line), ("innerborder-inactive", inactive_line)):
        pieces += _frame(prefix, "", surface=None, hairline=line, catch=None, shadow=False)
    # Aurorae v1's names for a compositor without translucency: no shadow ring.
    pieces += _frame("decoration-opaque", "", surface=surface, hairline=None,
                     catch=tone["catch"], shadow=False)
    pieces += _frame("decoration-opaque-inactive", "i-", surface=surface, hairline=None,
                     catch=None, shadow=False)
    # The maximized bar is one FLAT cell that FrameSvg stretches over the whole
    # bar, so it carries no gradient: it is the ramp's terminal colour, the
    # same surface the restored bar lands on and the toolbar below continues.
    for prefix in ("decoration-maximized", "decoration-maximized-inactive",
                   "decoration-maximized-opaque", "decoration-maximized-opaque-inactive"):
        pieces.append(f'<rect id="{prefix}-center" x="0" y="0" width="24" height="24" fill="{surface}"/>')
    return "\n".join((
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" '
        f'viewBox="0 0 {WIDTH} {HEIGHT}">',
        "<!-- MoOS slim window frame: original art, generated by artwork/generate_moos_aurorae.py. -->",
        f"<defs>{defs}</defs>",
        *pieces,
        "</svg>",
    ))


def aurorae_rc(p: Mapping[str, str]) -> str:
    def rgba(value: str, alpha: int = 255) -> str:
        return ",".join(str(channel) for channel in _channels(value)) + f",{alpha}"

    inactive = secondary_ink(p["text"], p["surface"])
    return f"""[General]
# A centred title remains balanced for both LTR and RTL window captions.
TitleAlignment=Center
TitleVerticalAlignment=Center
Animation=140
ActiveTextColor={rgba(p['text'])}
InactiveTextColor={rgba(inactive)}
UseTextShadow=false
HaloActive=false
HaloInactive=false
Shadow=true
LeftButtons=M
RightButtons=HIAX

[Layout]
# The slim MoOS frame (owner steering 2026-11-23). etc/xdg/kwinrc ships KWin's
# BorderSize=None, so no side or bottom band is painted and KWin's invisible
# resize-only borders take the drag. A border size the user chooses is clamped
# by Aurorae to at least 4 px and painted in the title colour.
BorderLeft=0
BorderRight=0
BorderBottom=0
TitleEdgeTop=0
TitleEdgeBottom=0
TitleEdgeLeft=1
TitleEdgeRight=1
TitleBorderLeft=1
TitleBorderRight=1
TitleHeight={TITLE}

TitleEdgeTopMaximized=0
TitleEdgeBottomMaximized=0
TitleEdgeLeftMaximized=0
TitleEdgeRightMaximized=0

# Each action's native input spans the whole bar: {ACTION_WIDTH} px wide and
# {TITLE} px tall around its 30x24 tile; maximized targets reach the screen
# edges. Aurorae's ButtonSize factor (auroraerc) scales bar and targets together.
ButtonWidth={ACTION_WIDTH}
ButtonHeight={TITLE}
ButtonSpacing={ACTION_SPACING}
ButtonMarginTop=0
ButtonMarginTopMaximized=0
# Aurorae v2 centres the caption between the two button groups, not in the
# window. MoOS keeps all three actions on one side (kwinrc XIA, mirrored by
# KDecoration for RTL) and puts one explicit spacer `_` on the other side. The
# spacer is exactly the action group (3 x {ACTION_WIDTH} + 2 x {ACTION_SPACING} = {ACTION_GROUP}), so the caption is
# centred on the window in both directions. KDecoration disables spacer input,
# so the title bar still drags and double-clicks through it. Measured in a
# private native KWin (scripts/review/window-frames-native.py).
ExplicitButtonSpacer={ACTION_GROUP}

# The shadow and hairline ring outside the window.
PaddingLeft={SIDE}
PaddingRight={SIDE}
PaddingTop={SIDE}
PaddingBottom={BOTTOM}
"""


def render_aurorae_suite(
    target: pathlib.Path,
    p: Mapping[str, str],
    *,
    plugin_name: str,
) -> None:
    """Write one complete MoOS Aurorae package: frame, every action and its layout."""
    _write(target / "decoration.svg", frame_svg(p))
    for name in BUTTONS:
        _write(target / f"{name}.svg", _button_svg(name, p))
    _write(target / f"{plugin_name}rc", aurorae_rc(p))


def _svg_ids(path: pathlib.Path) -> set[str]:
    try:
        tree = ET.parse(path)
    except (OSError, ET.ParseError) as error:
        raise SystemExit(f"invalid generated Aurorae SVG {path}: {error}") from error
    return {
        identifier
        for element in tree.iter()
        if (identifier := element.attrib.get("id"))
    }


def _title_end_stop(text: str, base: str, path: pathlib.Path) -> str:
    """Return the last stop colour of the `title`/`i-title` ramp."""
    source = re.search(
        rf'<linearGradient id="{base}" [^>]*>(.*?)</linearGradient>', text, re.S)
    if source is None:
        raise SystemExit(f"{path}: frame has no `{base}` gradient")
    stops = re.findall(r'stop-color="(#[0-9A-Fa-f]{6})"', source.group(1))
    if not stops:
        raise SystemExit(f"{path}: `{base}` gradient has no colour stops")
    return stops[-1]


def validate_aurorae_suite(
    target: pathlib.Path,
    *,
    plugin_name: str,
) -> None:
    """Fail loudly if Aurorae would receive a partial decoration package."""
    decoration = target / "decoration.svg"
    ids = _svg_ids(decoration)
    for prefix in (
        "decoration",
        "decoration-inactive",
        "innerborder",
        "innerborder-inactive",
        "decoration-opaque",
        "decoration-opaque-inactive",
    ):
        missing = {
            f"{prefix}-{position}" for position in FRAME_POSITIONS
        } - ids
        if missing:
            raise SystemExit(
                f"{decoration} is missing the {prefix} frame: "
                f"{sorted(missing)[0]}"
            )

    # The mask contract is deliberately ABSENT: hasElementPrefix("mask") makes
    # aurorae.v2 declare a blur region, and KWin then blurs every frame behind
    # an opaque title bar. A mask returning here means either wasted GPU per
    # frame or an undocumented move to translucent titlebars — both need a
    # reviewed decision, not drift.
    stray_mask = sorted(i for i in ids if i.startswith("mask-"))
    if stray_mask:
        raise SystemExit(
            f"{decoration} declares a blur mask ({stray_mask[0]}) but the "
            f"title bar is opaque — remove it or make the material decision explicit"
        )

    required_maximized = {
        "decoration-maximized-center",
        "decoration-maximized-inactive-center",
        "decoration-maximized-opaque-center",
        "decoration-maximized-opaque-inactive-center",
    }
    missing = required_maximized - ids
    if missing:
        raise SystemExit(
            f"{decoration} is missing its maximized contract: "
            f"{sorted(missing)[0]}"
        )

    # The maximized bar must be FLAT in the title ramp's terminal colour:
    # FrameSvg stretches this one cell over the whole bar and every gradient
    # basis was measured rendering wrong there.
    svg_text = decoration.read_text(encoding="utf-8")
    active_end = _title_end_stop(svg_text, "title", decoration)
    inactive_end = _title_end_stop(svg_text, "i-title", decoration)
    for rect_id, flat in (
        ("decoration-maximized-center", active_end),
        ("decoration-maximized-inactive-center", inactive_end),
    ):
        element = re.search(rf'<rect id="{rect_id}"[^>]*/>', svg_text)
        if element is None:
            raise SystemExit(f"{decoration} is missing {rect_id}")
        if "url(" in element.group(0):
            raise SystemExit(
                f"{decoration}: {rect_id} references a gradient — FrameSvg "
                f"stretches this cell and every gradient basis renders wrong; "
                f"it must be flat {flat}"
            )
        if f'fill="{flat}"' not in element.group(0):
            raise SystemExit(
                f"{decoration}: {rect_id} must be flat {flat} (the title "
                f"ramp's terminal colour) so the docked bar matches where the "
                f"floating ramp lands"
            )

    required_button_states = {
        f"{state}-center" for state in BUTTON_STATES
    }
    for name in BUTTONS:
        button = target / f"{name}.svg"
        button_ids = _svg_ids(button)
        missing = required_button_states - button_ids
        if missing:
            raise SystemExit(
                f"{button} is missing its button-state contract: "
                f"{sorted(missing)[0]}"
            )

    expected_rc = target / f"{plugin_name}rc"
    rc_files = sorted(target.glob("*rc"))
    if rc_files != [expected_rc]:
        names = ", ".join(path.name for path in rc_files) or "none"
        raise SystemExit(
            f"{target} must contain only {expected_rc.name}; found {names}"
        )
    rc = expected_rc.read_text(encoding="utf-8")
    for setting in (
        "Animation=140",
        f"TitleHeight={TITLE}",
        f"ButtonWidth={ACTION_WIDTH}",
        f"ButtonHeight={TITLE}",
        "RightButtons=HIAX",
        "ButtonMarginTop=0",
        "ButtonMarginTopMaximized=0",
        f"ExplicitButtonSpacer={ACTION_GROUP}",
    ):
        if setting not in rc:
            raise SystemExit(f"{expected_rc} is missing required setting {setting}")
