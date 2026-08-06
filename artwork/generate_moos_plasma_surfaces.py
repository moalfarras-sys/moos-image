#!/usr/bin/env python3
"""Render the high-visibility Plasma surfaces owned by the MoOS design system.

The main UI generator calls :func:`render_surface_suite` for Graphite and
Tidal.  The family generator then recolours the same geometry for the other
MoOS palettes.  Every file produced here is original, compact SVG art; Breeze
remains an upstream fallback and is never edited or overlaid in-place.
"""

from __future__ import annotations

import html
import pathlib
import re
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Mapping


POSITIONS = (
    "topleft", "top", "topright",
    "left", "center", "right",
    "bottomleft", "bottom", "bottomright",
)

SURFACE_FILENAMES = (
    "actionbutton.svg",
    "arrows.svg",
    "background.svg",
    "button.svg",
    "busywidget.svg",
    "checkmarks.svg",
    "frame.svg",
    "lineedit.svg",
    "listitem.svg",
    "menubaritem.svg",
    "pager.svg",
    "radiobutton.svg",
    "scrollbar.svg",
    "slider.svg",
    "switch.svg",
    "tabbar.svg",
    "toolbar.svg",
    "tooltip.svg",
    "translucentbackground.svg",
    "viewitem.svg",
)


def _write(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def _style(p: Mapping[str, str]) -> str:
    return f"""  <style id="current-color-scheme" type="text/css">
    .ColorScheme-Background {{ color: {p['surface']}; }}
    .ColorScheme-Highlight {{ color: {p['primary']}; }}
    .ColorScheme-Text {{ color: {p['text']}; }}
    .ColorScheme-ButtonBackground {{ color: {p['raised']}; }}
    .ColorScheme-ButtonText {{ color: {p['text']}; }}
  </style>"""


def _document(
    body: Iterable[str],
    p: Mapping[str, str],
    width: int,
    height: int,
    *,
    comment: str,
) -> str:
    safe_comment = html.escape(comment, quote=False)
    return "\n".join((
        '<?xml version="1.0" encoding="UTF-8"?>',
        (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
         f'height="{height}" viewBox="0 0 {width} {height}">'),
        f"  <!-- {safe_comment} -->",
        _style(p),
        *body,
        "</svg>",
    ))


def _id(prefix: str, name: str) -> str:
    return f"{prefix}-{name}" if prefix else name


def _frame(
    prefix: str,
    *,
    x: int,
    y: int,
    fill: str,
    fill_opacity: float,
    rim: str,
    rim_opacity: float,
    radius: int = 10,
    inner: int = 24,
    hints: bool = True,
    hint_margin: float | None = None,
) -> list[str]:
    """Return one rounded, scalable Plasma FrameSvg.

    Outlines are fill-only strips instead of strokes so fractional scaling
    cannot inflate them.  The 1 px optical rim stays crisp at 100–250% while
    the corner radius remains represented by unscaled corner pieces.
    """
    r = radius
    i = inner
    x0, x1, x2 = x, x + r, x + r + i
    y0, y1, y2 = y, y + r, y + r + i
    x3, y3 = x2 + r, y2 + r
    op = f"{fill_opacity:.3f}"
    rop = f"{rim_opacity:.3f}"
    out: list[str] = []

    out.append(
        f'  <g id="{_id(prefix, "topleft")}">'
        f'<path d="M{x0} {y1}A{r} {r} 0 0 1 {x1} {y0}V{y1}H{x0}Z" '
        f'fill="{fill}" fill-opacity="{op}"/>'
        f'<path d="M{x0} {y1}A{r} {r} 0 0 1 {x1} {y0}V{y0 + 1}'
        f'A{r - 1} {r - 1} 0 0 0 {x0 + 1} {y1}Z" '
        f'fill="{rim}" fill-opacity="{rop}"/></g>'
    )
    out.append(
        f'  <g id="{_id(prefix, "topright")}">'
        f'<path d="M{x2} {y0}A{r} {r} 0 0 1 {x3} {y1}H{x2}Z" '
        f'fill="{fill}" fill-opacity="{op}"/>'
        f'<path d="M{x2} {y0}A{r} {r} 0 0 1 {x3} {y1}H{x3 - 1}'
        f'A{r - 1} {r - 1} 0 0 0 {x2} {y0 + 1}Z" '
        f'fill="{rim}" fill-opacity="{rop}"/></g>'
    )
    out.append(
        f'  <g id="{_id(prefix, "bottomleft")}">'
        f'<path d="M{x0} {y2}A{r} {r} 0 0 0 {x1} {y3}V{y2}Z" '
        f'fill="{fill}" fill-opacity="{op}"/>'
        f'<path d="M{x0} {y2}A{r} {r} 0 0 0 {x1} {y3}V{y3 - 1}'
        f'A{r - 1} {r - 1} 0 0 1 {x0 + 1} {y2}Z" '
        f'fill="{rim}" fill-opacity="{rim_opacity * 0.62:.3f}"/></g>'
    )
    out.append(
        f'  <g id="{_id(prefix, "bottomright")}">'
        f'<path d="M{x3} {y2}A{r} {r} 0 0 1 {x2} {y3}V{y2}Z" '
        f'fill="{fill}" fill-opacity="{op}"/>'
        f'<path d="M{x3} {y2}A{r} {r} 0 0 1 {x2} {y3}V{y3 - 1}'
        f'A{r - 1} {r - 1} 0 0 0 {x3 - 1} {y2}Z" '
        f'fill="{rim}" fill-opacity="{rim_opacity * 0.62:.3f}"/></g>'
    )
    out.extend((
        (f'  <g id="{_id(prefix, "top")}"><rect x="{x1}" y="{y0}" '
         f'width="{i}" height="{r}" fill="{fill}" fill-opacity="{op}"/>'
         f'<rect x="{x1}" y="{y0}" width="{i}" height="1" fill="{rim}" '
         f'fill-opacity="{rop}"/></g>'),
        (f'  <g id="{_id(prefix, "bottom")}"><rect x="{x1}" y="{y2}" '
         f'width="{i}" height="{r}" fill="{fill}" fill-opacity="{op}"/>'
         f'<rect x="{x1}" y="{y3 - 1}" width="{i}" height="1" fill="{rim}" '
         f'fill-opacity="{rim_opacity * 0.62:.3f}"/></g>'),
        (f'  <g id="{_id(prefix, "left")}"><rect x="{x0}" y="{y1}" '
         f'width="{r}" height="{i}" fill="{fill}" fill-opacity="{op}"/>'
         f'<rect x="{x0}" y="{y1}" width="1" height="{i}" fill="{rim}" '
         f'fill-opacity="{rim_opacity * 0.78:.3f}"/></g>'),
        (f'  <g id="{_id(prefix, "right")}"><rect x="{x2}" y="{y1}" '
         f'width="{r}" height="{i}" fill="{fill}" fill-opacity="{op}"/>'
         f'<rect x="{x3 - 1}" y="{y1}" width="1" height="{i}" fill="{rim}" '
         f'fill-opacity="{rim_opacity * 0.78:.3f}"/></g>'),
        (f'  <rect id="{_id(prefix, "center")}" x="{x1}" y="{y1}" '
         f'width="{i}" height="{i}" fill="{fill}" fill-opacity="{op}"/>'),
    ))
    if hints:
        hx = x3 + 5
        hm = max(4, r - 2) if hint_margin is None else hint_margin
        out.extend((
            f'  <rect id="{_id(prefix, "hint-top-margin")}" x="{hx}" y="{y0}" width="3" height="{hm}" fill="none"/>',
            f'  <rect id="{_id(prefix, "hint-bottom-margin")}" x="{hx}" y="{y1}" width="3" height="{hm}" fill="none"/>',
            f'  <rect id="{_id(prefix, "hint-left-margin")}" x="{hx + 5}" y="{y0}" width="{hm}" height="3" fill="none"/>',
            f'  <rect id="{_id(prefix, "hint-right-margin")}" x="{hx + 5}" y="{y0 + 5}" width="{hm}" height="3" fill="none"/>',
        ))
    return out


def _mask_frame(prefix: str, *, x: int, y: int, radius: int = 10, inner: int = 24) -> list[str]:
    r, i = radius, inner
    x0, x1, x2, x3 = x, x + r, x + r + i, x + r + i + r
    y0, y1, y2, y3 = y, y + r, y + r + i, y + r + i + r
    return [
        f'  <path id="{_id(prefix, "topleft")}" d="M{x0} {y1}A{r} {r} 0 0 1 {x1} {y0}V{y1}Z" fill="#000"/>',
        f'  <rect id="{_id(prefix, "top")}" x="{x1}" y="{y0}" width="{i}" height="{r}" fill="#000"/>',
        f'  <path id="{_id(prefix, "topright")}" d="M{x2} {y0}A{r} {r} 0 0 1 {x3} {y1}H{x2}Z" fill="#000"/>',
        f'  <rect id="{_id(prefix, "left")}" x="{x0}" y="{y1}" width="{r}" height="{i}" fill="#000"/>',
        f'  <rect id="{_id(prefix, "center")}" x="{x1}" y="{y1}" width="{i}" height="{i}" fill="#000"/>',
        f'  <rect id="{_id(prefix, "right")}" x="{x2}" y="{y1}" width="{r}" height="{i}" fill="#000"/>',
        f'  <path id="{_id(prefix, "bottomleft")}" d="M{x0} {y2}A{r} {r} 0 0 0 {x1} {y3}V{y2}Z" fill="#000"/>',
        f'  <rect id="{_id(prefix, "bottom")}" x="{x1}" y="{y2}" width="{i}" height="{r}" fill="#000"/>',
        f'  <path id="{_id(prefix, "bottomright")}" d="M{x3} {y2}A{r} {r} 0 0 1 {x2} {y3}V{y2}Z" fill="#000"/>',
    ]


def _soft_shadow_frame(
    p: Mapping[str, str],
    *,
    x: int,
    y: int,
    radius: int = 10,
    inner: int = 24,
) -> list[str]:
    """Return a low-cost, outer-only shadow for Plasma's native buttons.

    PC3 expands the ``shadow`` FrameSvg by its margins before drawing the
    normal button above it. A filled shadow centre therefore becomes a large
    rectangular slab around every resting button. Keep the centre virtually
    transparent (as upstream FrameSvg consumers expect) and fade only the
    perimeter. This uses static SVG gradients; there is no runtime blur or
    shader cost.
    """
    r, i = radius, inner
    x0, x1, x2, x3 = x, x + r, x + r + i, x + r + i + r
    y0, y1, y2, y3 = y, y + r, y + r + i, y + r + i + r
    color = p["shadow"]
    return [
        "  <defs>",
        f'    <linearGradient id="moos-button-shadow-top" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{color}" stop-opacity="0"/>'
        f'<stop offset="1" stop-color="{color}" stop-opacity="0.11"/></linearGradient>',
        f'    <linearGradient id="moos-button-shadow-bottom" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{color}" stop-opacity="0.15"/>'
        f'<stop offset="1" stop-color="{color}" stop-opacity="0"/></linearGradient>',
        f'    <linearGradient id="moos-button-shadow-left" x1="0" y1="0" x2="1" y2="0">'
        f'<stop offset="0" stop-color="{color}" stop-opacity="0"/>'
        f'<stop offset="1" stop-color="{color}" stop-opacity="0.10"/></linearGradient>',
        f'    <linearGradient id="moos-button-shadow-right" x1="0" y1="0" x2="1" y2="0">'
        f'<stop offset="0" stop-color="{color}" stop-opacity="0.10"/>'
        f'<stop offset="1" stop-color="{color}" stop-opacity="0"/></linearGradient>',
        f'    <radialGradient id="moos-button-shadow-tl" cx="1" cy="1" r="1">'
        f'<stop offset="0" stop-color="{color}" stop-opacity="0.11"/>'
        f'<stop offset="1" stop-color="{color}" stop-opacity="0"/></radialGradient>',
        f'    <radialGradient id="moos-button-shadow-tr" cx="0" cy="1" r="1">'
        f'<stop offset="0" stop-color="{color}" stop-opacity="0.11"/>'
        f'<stop offset="1" stop-color="{color}" stop-opacity="0"/></radialGradient>',
        f'    <radialGradient id="moos-button-shadow-bl" cx="1" cy="0" r="1">'
        f'<stop offset="0" stop-color="{color}" stop-opacity="0.15"/>'
        f'<stop offset="1" stop-color="{color}" stop-opacity="0"/></radialGradient>',
        f'    <radialGradient id="moos-button-shadow-br" cx="0" cy="0" r="1">'
        f'<stop offset="0" stop-color="{color}" stop-opacity="0.15"/>'
        f'<stop offset="1" stop-color="{color}" stop-opacity="0"/></radialGradient>',
        "  </defs>",
        f'  <rect id="shadow-topleft" x="{x0}" y="{y0}" width="{r}" height="{r}" fill="url(#moos-button-shadow-tl)"/>',
        f'  <rect id="shadow-top" x="{x1}" y="{y0}" width="{i}" height="{r}" fill="url(#moos-button-shadow-top)"/>',
        f'  <rect id="shadow-topright" x="{x2}" y="{y0}" width="{r}" height="{r}" fill="url(#moos-button-shadow-tr)"/>',
        f'  <rect id="shadow-left" x="{x0}" y="{y1}" width="{r}" height="{i}" fill="url(#moos-button-shadow-left)"/>',
        f'  <rect id="shadow-center" x="{x1}" y="{y1}" width="{i}" height="{i}" fill="{color}" fill-opacity="0.001"/>',
        f'  <rect id="shadow-right" x="{x2}" y="{y1}" width="{r}" height="{i}" fill="url(#moos-button-shadow-right)"/>',
        f'  <rect id="shadow-bottomleft" x="{x0}" y="{y2}" width="{r}" height="{r}" fill="url(#moos-button-shadow-bl)"/>',
        f'  <rect id="shadow-bottom" x="{x1}" y="{y2}" width="{i}" height="{r}" fill="url(#moos-button-shadow-bottom)"/>',
        f'  <rect id="shadow-bottomright" x="{x2}" y="{y2}" width="{r}" height="{r}" fill="url(#moos-button-shadow-br)"/>',
        f'  <rect id="shadow-hint-top-margin" x="{x3 + 5}" y="{y0}" width="3" height="{max(4, r - 2)}" fill="none"/>',
        f'  <rect id="shadow-hint-bottom-margin" x="{x3 + 5}" y="{y1}" width="3" height="{max(4, r - 2)}" fill="none"/>',
        f'  <rect id="shadow-hint-left-margin" x="{x3 + 10}" y="{y0}" width="{max(4, r - 2)}" height="3" fill="none"/>',
        f'  <rect id="shadow-hint-right-margin" x="{x3 + 10}" y="{y0 + 5}" width="{max(4, r - 2)}" height="3" fill="none"/>',
    ]


def _background(
    p: Mapping[str, str],
    *,
    fill: str,
    opacity: float,
    rim: str,
    rim_opacity: float,
    radius: int,
    comment: str,
) -> str:
    body = _frame(
        "", x=0, y=0, fill=fill, fill_opacity=opacity,
        rim=rim, rim_opacity=rim_opacity, radius=radius,
    )
    body.extend(_mask_frame("mask", x=80, y=0, radius=radius))
    body.append('  <rect id="hint-stretch-borders" x="152" y="0" width="4" height="4" fill="none"/>')
    body.extend((
        '  <rect id="hint-top-inset" x="152" y="8" width="4" height="0.01" fill="none"/>',
        '  <rect id="hint-bottom-inset" x="152" y="12" width="4" height="0.01" fill="none"/>',
        '  <rect id="hint-left-inset" x="152" y="16" width="0.01" height="4" fill="none"/>',
        '  <rect id="hint-right-inset" x="156" y="16" width="0.01" height="4" fill="none"/>',
    ))
    return _document(body, p, 176, 64, comment=comment)


def _multi_frame(
    p: Mapping[str, str],
    states: list[tuple[str, str, float, str, float]],
    *,
    comment: str,
    radius: int = 9,
    inner: int = 24,
    pitch: int = 52,
) -> str:
    if radius * 2 + inner > pitch:
        raise SystemExit(
            "_multi_frame blocks would overlap: raise pitch above "
            f"{radius * 2 + inner}"
        )
    body: list[str] = []
    for index, (prefix, fill, opacity, rim, rim_opacity) in enumerate(states):
        body.extend(_frame(
            prefix, x=0, y=index * pitch, fill=fill, fill_opacity=opacity,
            rim=rim, rim_opacity=rim_opacity, radius=radius, inner=inner,
        ))
    body.append(f'  <rect id="hint-tile-center" x="104" y="0" width="4" height="4" fill="none"/>')
    return _document(body, p, 128, len(states) * pitch, comment=comment)


def _state_frames(
    p: Mapping[str, str],
    states: list[tuple[str, str, float, str, float]],
    *,
    radius: int,
    comment: str,
    include_masks: tuple[str, ...] = (),
) -> str:
    """Render a compact stack of native Plasma FrameSvg interaction states."""
    body: list[str] = []
    for index, (prefix, fill, opacity, rim, rim_opacity) in enumerate(states):
        body.extend(_frame(
            prefix,
            x=0,
            y=index * 52,
            fill=fill,
            fill_opacity=opacity,
            rim=rim,
            rim_opacity=rim_opacity,
            radius=radius,
        ))
    for index, prefix in enumerate(include_masks):
        body.extend(_mask_frame(
            f"mask-{prefix}",
            x=64,
            y=index * 52,
            radius=radius,
        ))
    body.append('  <rect id="hint-tile-center" x="116" y="0" width="4" height="4" fill="none"/>')
    return _document(
        body,
        p,
        128,
        max(1, len(states)) * 52,
        comment=comment,
    )


def _button(p: Mapping[str, str]) -> str:
    # The hint margin per state is a live PC3 contract, not styling freedom:
    # ButtonHover/ButtonFocus draw "hover"/"focus"/"toolbutton-focus" EXPANDED
    # outward by exactly these margins on top of the resting face, so a filled
    # state must stay contained (0.001) and a keyboard ring may spread only a
    # couple of px. "normal"/"pressed" margins become the button's padding and
    # "toolbutton-hover" margins the flat button's padding — those fill their
    # rect and never overhang.
    states = [
        ("normal", p["raised"], 0.82, p["outline"], 0.12, 8),
        ("hover", p["raised"], 0.96, p["luminous"], 0.20, 0.001),
        ("focus", p["surface"], 0.01, p["luminous"], 0.40, 2),
        ("pressed", p["card"], 0.98, p["primary"], 0.40, 8),
        ("toolbutton-hover", p["raised"], 0.58, p["luminous"], 0.15, 4),
        ("toolbutton-focus", p["surface"], 0.01, p["luminous"], 0.40, 2),
        ("toolbutton-pressed", p["primary"], 0.16, p["primary"], 0.40, 4),
    ]
    body = _soft_shadow_frame(p, x=64, y=0, radius=10)
    for index, (prefix, fill, opacity, rim, rim_opacity, hint_margin) in enumerate(states):
        body.extend(_frame(
            prefix,
            x=0,
            y=index * 52,
            fill=fill,
            fill_opacity=opacity,
            rim=rim,
            rim_opacity=rim_opacity,
            radius=10,
            hint_margin=hint_margin,
        ))
    body.extend(_mask_frame("mask-normal", x=64, y=52, radius=10))
    body.append('  <rect id="hint-tile-center" x="116" y="0" width="4" height="4" fill="none"/>')
    return _document(
        body,
        p,
        136,
        len(states) * 52,
        comment=(
            "MoOS native Plasma buttons: one quiet surface, separated hover, "
            "pressed and keyboard-focus states, plus an outer-only static shadow."
        ),
    )


def _lineedit(p: Mapping[str, str]) -> str:
    return _state_frames(
        p,
        [
            ("base", p["surface"], 0.90, p["outline"], 0.20),
            ("hover", p["surface"], 0.96, p["luminous"], 0.25),
            ("focus", p["surface"], 1.00, p["primary"], 0.60),
            ("focusframe", p["surface"], 0.01, p["luminous"], 0.60),
        ],
        radius=10,
        comment="MoOS native text fields with a calm resting edge and an unmistakable keyboard-focus rim.",
    )


def _listitem(p: Mapping[str, str]) -> str:
    text = _state_frames(
        p,
        [
            ("normal", p["surface"], 0.01, p["outline"], 0.01),
            ("hover", p["raised"], 0.54, p["luminous"], 0.10),
            ("pressed", p["primary"], 0.15, p["primary"], 0.35),
            ("section", p["surface"], 0.30, p["outline"], 0.10),
        ],
        radius=9,
        comment="MoOS native list rows: borderless at rest, quiet prelight, semantic pressed selection.",
    )
    separator = (
        f'  <rect id="separator" x="116" y="12" width="8" height="1" '
        f'fill="{p["outline"]}" fill-opacity="0.32"/>\n'
    )
    return text.replace("</svg>", separator + "</svg>")


def _viewitem(p: Mapping[str, str]) -> str:
    return _state_frames(
        p,
        [
            ("normal", p["surface"], 0.01, p["outline"], 0.01),
            ("hover", p["raised"], 0.50, p["luminous"], 0.10),
            ("selected", p["primary"], 0.16, p["primary"], 0.35),
            ("selected+hover", p["primary"], 0.24, p["luminous"], 0.40),
        ],
        radius=9,
        comment="MoOS native view items with low-noise hover and a palette-owned selected state.",
    )


def _arrows(p: Mapping[str, str]) -> str:
    body = [
        f'  <path id="up-arrow" d="M2 9L8 3l6 6-1.8 1.8L8 6.6l-4.2 4.2Z" fill="{p["text"]}"/>',
        f'  <path id="right-arrow" d="M19 2l6 6-6 6-1.8-1.8L21.4 8l-4.2-4.2Z" fill="{p["text"]}"/>',
        f'  <path id="down-arrow" d="M34 7.2L38.2 3 40 4.8l-6 6-6-6L29.8 3Z" fill="{p["text"]}"/>',
        f'  <path id="left-arrow" d="M49 2l1.8 1.8L46.6 8l4.2 4.2L49 14l-6-6Z" fill="{p["text"]}"/>',
    ]
    return _document(body, p, 54, 16, comment="MoOS directional glyphs with RTL-safe symmetric geometry.")


def _action_button(p: Mapping[str, str]) -> str:
    body: list[str] = []
    sizes = (("", 32), ("24-24", 24), ("22-22", 22), ("16-16", 16))
    states = (
        ("normal", p["raised"], 0.58, p["outline"], 0.34),
        ("hover", p["raised"], 0.88, p["luminous"], 0.78),
        ("pressed", p["card"], 0.98, p["primary"], 0.96),
        ("focus", p["surface"], 0.94, p["luminous"], 1.0),
    )
    x = 0
    for size_prefix, size in sizes:
        for state, fill, opacity, rim, rim_opacity in states:
            identifier = f"{size_prefix + '-' if size_prefix else ''}{state}"
            radius = max(5, size // 3)
            body.append(
                f'  <g id="{identifier}" transform="translate({x} 0)">'
                f'<rect width="{size}" height="{size}" rx="{radius}" fill="{fill}" '
                f'fill-opacity="{opacity:.3f}"/>'
                f'<rect x="0.5" y="0.5" width="{size - 1}" height="{size - 1}" '
                f'rx="{max(4, radius - 0.5)}" fill="none" stroke="{rim}" '
                f'stroke-opacity="{rim_opacity:.3f}"/></g>'
            )
            x += size + 6
    return _document(body, p, x, 34, comment="MoOS compact action buttons: normal, hover, pressed and keyboard focus.")


def _selection_controls(p: Mapping[str, str]) -> tuple[str, str]:
    radio = [
        f'  <g id="normal"><circle cx="10" cy="10" r="8" fill="{p["surface"]}" stroke="{p["outline"]}" stroke-width="1.2"/></g>',
        f'  <g id="hover"><circle cx="30" cy="10" r="8" fill="{p["raised"]}" stroke="{p["luminous"]}" stroke-width="1.4"/></g>',
        f'  <g id="focus"><circle cx="50" cy="10" r="8" fill="{p["surface"]}" stroke="{p["luminous"]}" stroke-width="2"/></g>',
        f'  <g id="checked"><circle cx="70" cy="10" r="8" fill="{p["primary"]}" stroke="{p["luminous"]}" stroke-width="1.2"/><circle cx="70" cy="10" r="3.2" fill="{p["selected_text"]}"/></g>',
        f'  <circle id="symbol" cx="90" cy="10" r="3.2" fill="{p["selected_text"]}"/>',
        f'  <circle id="shadow" cx="110" cy="11" r="4" fill="{p["shadow"]}" fill-opacity="0.24"/>',
        '  <rect id="hint-size" x="122" y="0" width="20" height="20" fill="none"/>',
    ]
    checks = [
        f'  <g id="checkbox"><rect x="0" width="16" height="16" rx="5" fill="{p["primary"]}"/><path d="M3.5 8.4L6.6 11.3 12.6 4.9" fill="none" stroke="{p["selected_text"]}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></g>',
        f'  <g id="radiobutton"><circle cx="8" cy="26" r="7.5" fill="{p["primary"]}"/><circle cx="8" cy="26" r="3" fill="{p["selected_text"]}"/></g>',
    ]
    return (
        _document(radio, p, 144, 20, comment="MoOS radio states with a clear focus halo."),
        _document(checks, p, 16, 34, comment="MoOS checked-state glyphs."),
    )


def _switch(p: Mapping[str, str]) -> str:
    body = [
        f'  <path id="inactive-left" d="M0 7A7 7 0 0 1 7 0v14A7 7 0 0 1 0 7Z" fill="{p["outline"]}" fill-opacity="0.46"/>',
        f'  <rect id="inactive-center" x="7" width="16" height="14" fill="{p["outline"]}" fill-opacity="0.46"/>',
        f'  <path id="inactive-right" d="M23 0a7 7 0 0 1 0 14Z" fill="{p["outline"]}" fill-opacity="0.46"/>',
        f'  <path id="active-left" d="M0 27a7 7 0 0 1 7-7v14a7 7 0 0 1-7-7Z" fill="{p["primary"]}"/>',
        f'  <rect id="active-center" x="7" y="20" width="16" height="14" fill="{p["primary"]}"/>',
        f'  <path id="active-right" d="M23 20a7 7 0 0 1 0 14Z" fill="{p["primary"]}"/>',
        f'  <g id="handle"><circle cx="43" cy="7" r="7" fill="{p["text"]}"/><circle cx="43" cy="7" r="6" fill="{p["card"]}"/></g>',
        f'  <g id="handle-hover"><circle cx="61" cy="7" r="8" fill="{p["luminous"]}" fill-opacity="0.42"/><circle cx="61" cy="7" r="6" fill="{p["text"]}"/></g>',
        f'  <g id="handle-focus"><circle cx="81" cy="7" r="9" fill="none" stroke="{p["luminous"]}" stroke-width="2"/><circle cx="81" cy="7" r="6" fill="{p["text"]}"/></g>',
        f'  <g id="handle-pressed"><circle cx="101" cy="7" r="7" fill="{p["primary"]}"/><circle cx="101" cy="7" r="4" fill="{p["selected_text"]}"/></g>',
        f'  <circle id="handle-shadow" cx="119" cy="8" r="7" fill="{p["shadow"]}" fill-opacity="0.28"/>',
        '  <rect id="hint-bar-size" x="130" width="30" height="14" fill="none"/>',
    ]
    return _document(body, p, 162, 36, comment="MoOS pill switch with luminous focus and restrained pressed feedback.")


def _slider(p: Mapping[str, str]) -> str:
    body: list[str] = []
    body.extend(_frame(
        "groove", x=0, y=0, fill=p["outline"], fill_opacity=0.44,
        rim=p["outline"], rim_opacity=0.18, radius=3, inner=14, hints=False,
    ))
    body.extend(_frame(
        "groove-highlight", x=34, y=0, fill=p["primary"], fill_opacity=0.94,
        rim=p["luminous"], rim_opacity=0.62, radius=3, inner=14, hints=False,
    ))
    body.extend((
        f'  <g id="horizontal-slider-handle"><circle cx="84" cy="10" r="8" fill="{p["card"]}" stroke="{p["primary"]}" stroke-width="2"/></g>',
        f'  <g id="horizontal-slider-hover"><circle cx="104" cy="10" r="9" fill="{p["raised"]}" stroke="{p["luminous"]}" stroke-width="2"/></g>',
        f'  <g id="horizontal-slider-focus"><circle cx="126" cy="10" r="9" fill="{p["card"]}" stroke="{p["luminous"]}" stroke-width="2.5"/></g>',
        f'  <g id="vertical-slider-handle"><circle cx="84" cy="32" r="8" fill="{p["card"]}" stroke="{p["primary"]}" stroke-width="2"/></g>',
        f'  <g id="vertical-slider-hover"><circle cx="104" cy="32" r="9" fill="{p["raised"]}" stroke="{p["luminous"]}" stroke-width="2"/></g>',
        f'  <g id="vertical-slider-focus"><circle cx="126" cy="32" r="9" fill="{p["card"]}" stroke="{p["luminous"]}" stroke-width="2.5"/></g>',
        '  <rect id="hint-handle-size" x="142" width="20" height="20" fill="none"/>',
        '  <rect id="hint-stretch-borders" x="166" width="4" height="4" fill="none"/>',
    ))
    return _document(body, p, 174, 44, comment="MoOS slider groove, accent progress and scalable focus handles.")


def _arrow_path(direction: str, x: int, y: int) -> str:
    points = {
        "top": f"{x + 8},{y + 4} {x + 3},{y + 11} {x + 13},{y + 11}",
        "right": f"{x + 12},{y + 8} {x + 5},{y + 3} {x + 5},{y + 13}",
        "bottom": f"{x + 8},{y + 12} {x + 3},{y + 5} {x + 13},{y + 5}",
        "left": f"{x + 4},{y + 8} {x + 11},{y + 3} {x + 11},{y + 13}",
    }
    return points[direction]


def _scrollbar(p: Mapping[str, str]) -> str:
    body: list[str] = []
    frame_specs = (
        ("background-vertical", 0, p["surface"], 0.22, p["outline"], 0.12),
        ("background-horizontal", 48, p["surface"], 0.22, p["outline"], 0.12),
        ("slider", 96, p["outline"], 0.62, p["outline"], 0.22),
        ("mouseover-slider", 144, p["primary"], 0.84, p["luminous"], 0.56),
        ("sunken-slider", 192, p["primary"], 1.0, p["luminous"], 0.82),
    )
    for prefix, x, fill, opacity, rim, rim_opacity in frame_specs:
        body.extend(_frame(
            prefix, x=x, y=0, fill=fill, fill_opacity=opacity,
            rim=rim, rim_opacity=rim_opacity, radius=5, inner=12, hints=False,
        ))
    x = 0
    for state, color, opacity in (
        ("", p["muted"], 0.78),
        ("mouseover", p["luminous"], 0.96),
        ("sunken", p["primary"], 1.0),
    ):
        for direction in ("top", "right", "bottom", "left"):
            identifier = f"{state + '-' if state else ''}arrow-{direction}"
            body.append(
                f'  <polygon id="{identifier}" points="{_arrow_path(direction, x, 38)}" '
                f'fill="{color}" fill-opacity="{opacity:.3f}"/>'
            )
            x += 18
    body.extend((
        '  <rect id="hint-scrollbar-size" x="220" y="38" width="12" height="12" fill="none"/>',
        '  <rect id="hint-tile-center" x="236" y="38" width="4" height="4" fill="none"/>',
    ))
    return _document(body, p, 244, 58, comment="MoOS slim scrollbar track, accent hover thumb and complete arrow states.")


def _busy(p: Mapping[str, str]) -> str:
    body = [
        f'  <g id="stopped"><circle cx="12" cy="12" r="9" fill="none" stroke="{p["outline"]}" stroke-width="2"/></g>',
        f'  <g id="busywidget"><circle cx="38" cy="12" r="9" fill="none" stroke="{p["outline"]}" stroke-width="2"/><path d="M38 3a9 9 0 0 1 8.6 6.4" fill="none" stroke="{p["luminous"]}" stroke-width="2.6" stroke-linecap="round"/></g>',
        f'  <g id="22-22-busywidget"><circle cx="64" cy="11" r="8" fill="none" stroke="{p["outline"]}" stroke-width="2"/><path d="M64 3a8 8 0 0 1 7.6 5.4" fill="none" stroke="{p["primary"]}" stroke-width="2.4" stroke-linecap="round"/></g>',
        f'  <g id="16-16-busywidget"><circle cx="86" cy="8" r="6" fill="none" stroke="{p["outline"]}" stroke-width="1.7"/><path d="M86 2a6 6 0 0 1 5.7 4" fill="none" stroke="{p["primary"]}" stroke-width="2" stroke-linecap="round"/></g>',
        '  <rect id="hint-rotation-angle" x="100" y="0" width="30" height="30" fill="none"/>',
    ]
    return _document(body, p, 132, 30, comment="Low-overdraw MoOS busy indicator; Plasma supplies the rotation animation.")


def render_surface_suite(target: pathlib.Path, p: Mapping[str, str]) -> None:
    """Write the MoOS-owned high-visibility Plasma SVG suite into *target*."""
    widgets = target / "widgets"
    _write(widgets / "background.svg", _background(
        p, fill=p["card"], opacity=0.88, rim=p["luminous"],
        rim_opacity=0.28, radius=16,
        comment="MoOS glass desktop-widget background with a rounded blur mask.",
    ))
    _write(widgets / "translucentbackground.svg", _background(
        p, fill=p["surface"], opacity=0.66, rim=p["primary"],
        rim_opacity=0.26, radius=16,
        comment="MoOS low-density glass for large visual plasmoids.",
    ))
    _write(widgets / "tooltip.svg", _background(
        p, fill=p["card"], opacity=0.92, rim=p["luminous"],
        rim_opacity=0.42, radius=12,
        comment="MoOS task tooltip glass with a precise rounded blur mask.",
    ))
    _write(widgets / "frame.svg", _multi_frame(p, [
        ("sunken", p["canvas"], 0.72, p["outline"], 0.44),
        ("plain", p["surface"], 0.38, p["outline"], 0.22),
        ("raised", p["raised"], 0.86, p["luminous"], 0.28),
    ], comment="MoOS grouping frames: sunken, plain and raised."))
    _write(widgets / "button.svg", _button(p))
    _write(widgets / "lineedit.svg", _lineedit(p))
    _write(widgets / "listitem.svg", _listitem(p))
    _write(widgets / "viewitem.svg", _viewitem(p))
    # THE MoOS RIM SCALE. An interaction state is told by its FILL; the rim is
    # only ever a hint of an edge. A rim drawn in an accent colour above ~0.40
    # stops reading as glass and starts reading as a drawn-on rectangle — the
    # "cheap box" the whole family was swept for. Structural rims on FLOATING
    # glass (tooltip, popup, dock) are exempt: there the edge is the only thing
    # separating the surface from live wallpaper.
    #   resting  <= 0.22 · hover <= 0.25 · selected/pressed <= 0.40
    #   keyboard focus 0.40..0.60 — it must stay unmistakable for accessibility
    _write(widgets / "menubaritem.svg", _multi_frame(p, [
        ("normal", p["surface"], 0.01, p["outline"], 0.01),
        ("hover", p["raised"], 0.54, p["luminous"], 0.20),
        ("pressed", p["primary"], 0.16, p["primary"], 0.35),
    ], comment="MoOS menu item interaction states."))
    _write(widgets / "pager.svg", _multi_frame(p, [
        ("normal", p["surface"], 0.36, p["outline"], 0.18),
        ("hover", p["raised"], 0.78, p["luminous"], 0.25),
        ("active", p["primary"], 0.34, p["luminous"], 0.40),
    ], comment="MoOS virtual desktop pager states."))
    _write(widgets / "toolbar.svg", _multi_frame(p, [
        ("", p["surface"], 0.62, p["outline"], 0.24),
    ], comment="MoOS translucent toolbar frame."))
    # Plasma reuses these four prefixes for TWO surfaces: the active tab of a
    # PlasmaComponents TabBar, and — via the shell's CompactApplet — the frame
    # painted behind a PANEL APPLET while its popup is open, picked by panel
    # edge (a bottom dock asks for "south-active-tab").  The old art was a
    # near-opaque slab with a 0.88 accent rim on all four edges, so opening the
    # MoOS launcher wrapped the button in a hard bordered rectangle sitting on
    # the dock glass — the "square in the bar" the owner asked us to remove.
    #
    # MoOS UI answers with a lit slot instead of a box: no rim at all, a low
    # accent tint, and a radius large enough (20 of a 56 px block) that the
    # frame reads as a capsule rather than a rectangle at every dock height.
    _write(widgets / "tabbar.svg", _multi_frame(p, [
        (f"{direction}-active-tab", p["primary"], 0.12, p["primary"], 0.0)
        for direction in ("north", "east", "south", "west")
    ], comment=("MoOS active tab and open-applet slot: borderless accent glass, "
                "capsule radius, never a bordered box."),
        radius=20, inner=16, pitch=64))
    _write(widgets / "arrows.svg", _arrows(p))
    _write(widgets / "actionbutton.svg", _action_button(p))
    radio, checks = _selection_controls(p)
    _write(widgets / "radiobutton.svg", radio)
    _write(widgets / "checkmarks.svg", checks)
    _write(widgets / "switch.svg", _switch(p))
    _write(widgets / "slider.svg", _slider(p))
    _write(widgets / "scrollbar.svg", _scrollbar(p))
    _write(widgets / "busywidget.svg", _busy(p))


def refine_task_surface(path: pathlib.Path) -> None:
    """Keep hover neutral while preserving task-state indicators.

    Plasma requests the hover frame for pinned launchers as well as running
    tasks. The running underline therefore belongs to normal, focus, and
    minimized only; a hover underline falsely says that a closed launcher is
    running. Keep the existing palette-specific geometry and remove only the
    hover indicator from the shared generated output.
    """
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(r'(<g id="hover-bottom">)(.*?)(</g>)', re.DOTALL)

    def without_indicator(match: re.Match[str]) -> str:
        body = match.group(2)
        elements = re.findall(r'<(?:rect|path)\b[^>]*/>', body)
        return match.group(1) + (elements[0] if elements else "") + match.group(3)

    refined, count = pattern.subn(without_indicator, text, count=1)
    if count != 1:
        raise SystemExit(f"{path}: missing hover task state")
    _write(path, refined)


def _svg_ids(path: pathlib.Path) -> set[str]:
    try:
        tree = ET.parse(path)
    except (OSError, ET.ParseError) as error:
        raise SystemExit(f"invalid generated Plasma SVG {path}: {error}") from error
    return {
        identifier
        for element in tree.iter()
        if (identifier := element.attrib.get("id"))
    }


def validate_surface_suite(target: pathlib.Path) -> None:
    """Fail loudly if a generated Plasma surface suite is incomplete.

    This validation deliberately lives beside the renderer, so adding a new
    high-visibility surface cannot leave the transactional main generator with
    an older, weaker list of files or FrameSvg identifiers.
    """
    widgets = target / "widgets"
    for filename in SURFACE_FILENAMES:
        path = widgets / filename
        if not path.is_file():
            raise SystemExit(f"missing generated Plasma surface: {path}")
        _svg_ids(path)

    for filename in ("background.svg", "tooltip.svg", "translucentbackground.svg"):
        path = widgets / filename
        ids = _svg_ids(path)
        required = set(POSITIONS) | {
            f"mask-{position}" for position in POSITIONS
        }
        missing = required - ids
        if missing:
            raise SystemExit(
                f"{path} is missing its rounded FrameSvg contract: "
                f"{sorted(missing)[0]}"
            )

    menu = widgets / "menubaritem.svg"
    menu_ids = _svg_ids(menu)
    for state in ("normal", "hover", "pressed"):
        missing = {
            f"{state}-{position}" for position in POSITIONS
        } - menu_ids
        if missing:
            raise SystemExit(
                f"{menu} is missing the {state} interaction frame: "
                f"{sorted(missing)[0]}"
            )

    state_contracts = {
        "button.svg": (
            "shadow", "normal", "hover", "focus", "pressed",
            "toolbutton-hover", "toolbutton-focus", "toolbutton-pressed",
        ),
        "lineedit.svg": ("base", "hover", "focus", "focusframe"),
        "listitem.svg": ("normal", "hover", "pressed", "section"),
        "viewitem.svg": ("normal", "hover", "selected", "selected+hover"),
    }
    for filename, states in state_contracts.items():
        path = widgets / filename
        ids = _svg_ids(path)
        for state in states:
            missing = {
                f"{state}-{position}" for position in POSITIONS
            } - ids
            if missing:
                raise SystemExit(
                    f"{path} is missing the {state} interaction frame: "
                    f"{sorted(missing)[0]}"
                )

    tabbar = widgets / "tabbar.svg"
    tab_ids = _svg_ids(tabbar)
    for direction in ("north", "east", "south", "west"):
        missing = {
            f"{direction}-active-tab-{position}" for position in POSITIONS
        } - tab_ids
        if missing:
            raise SystemExit(
                f"{tabbar} is missing the {direction} active-tab frame: "
                f"{sorted(missing)[0]}"
            )

    switch = widgets / "switch.svg"
    switch_ids = _svg_ids(switch)
    required_switch_ids = {
        "active-left", "active-center", "active-right",
        "inactive-left", "inactive-center", "inactive-right",
        "handle", "handle-hover", "handle-focus", "handle-pressed",
    }
    missing = required_switch_ids - switch_ids
    if missing:
        raise SystemExit(
            f"{switch} is missing its interaction contract: "
            f"{sorted(missing)[0]}"
        )
