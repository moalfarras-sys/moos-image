#!/usr/bin/env python3
"""Complete the MoOS Aurorae decoration without touching upstream Breeze.

The shipped Graphite frame is kept because it is already live-tested.  This
module adds the pieces Aurorae needs for blur, inner borders and opaque mode,
then renders a full, original set of window-button states.  Normal buttons use
quiet MoOS glyphs; semantic colour appears on interaction, avoiding the
traffic-light look of the previous revision.
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


def _write(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def _frame_piece(
    identifier: str,
    *,
    region: str,
    fill: str,
    accent: str,
    opacity: float = 1.0,
    rim_opacity: float = 0.22,
) -> str:
    """Return one decoration piece with the same geometry as the proven frame."""
    op = f"{opacity:.3f}"
    rop = f"{rim_opacity:.3f}"
    transparent = {
        "topleft": '<rect width="30" height="52" fill="#000" fill-opacity="0"/>',
        "top": '<rect x="30" width="24" height="52" fill="#000" fill-opacity="0"/>',
        "topright": '<rect x="54" width="30" height="52" fill="#000" fill-opacity="0"/>',
        "left": '<rect y="52" width="30" height="24" fill="#000" fill-opacity="0"/>',
        "center": '<rect x="30" y="52" width="24" height="24" fill="#000" fill-opacity="0"/>',
        "right": '<rect x="54" y="52" width="30" height="24" fill="#000" fill-opacity="0"/>',
        "bottomleft": '<rect y="76" width="30" height="36" fill="#000" fill-opacity="0"/>',
        "bottom": '<rect x="30" y="76" width="24" height="36" fill="#000" fill-opacity="0"/>',
        "bottomright": '<rect x="54" y="76" width="30" height="36" fill="#000" fill-opacity="0"/>',
    }[region]
    paint = {
        "topleft": (
            f'<path d="M18 52V24A12 12 0 0 1 30 12v40Z" fill="{fill}" fill-opacity="{op}"/>'
            f'<path d="M18 52V24A12 12 0 0 1 30 12v1A11 11 0 0 0 19 24v28Z" fill="{accent}" fill-opacity="{rop}"/>'
        ),
        "top": (
            f'<rect x="30" y="12" width="24" height="40" fill="{fill}" fill-opacity="{op}"/>'
            f'<rect x="30" y="12" width="24" height="1" fill="{accent}" fill-opacity="{rop}"/>'
        ),
        "topright": (
            f'<path d="M54 12a12 12 0 0 1 12 12v28H54Z" fill="{fill}" fill-opacity="{op}"/>'
            f'<path d="M54 12a12 12 0 0 1 12 12v28h-1V24a11 11 0 0 0-11-11Z" fill="{accent}" fill-opacity="{rop}"/>'
        ),
        "left": (
            f'<rect x="18" y="52" width="12" height="24" fill="{fill}" fill-opacity="{op}"/>'
            f'<rect x="18" y="52" width="1" height="24" fill="{accent}" fill-opacity="{rim_opacity * 0.7:.3f}"/>'
        ),
        "center": f'<rect x="30" y="52" width="24" height="24" fill="{fill}" fill-opacity="{op}"/>',
        "right": (
            f'<rect x="54" y="52" width="12" height="24" fill="{fill}" fill-opacity="{op}"/>'
            f'<rect x="65" y="52" width="1" height="24" fill="{accent}" fill-opacity="{rim_opacity * 0.7:.3f}"/>'
        ),
        "bottomleft": (
            f'<path d="M18 76a12 12 0 0 0 12 12V76Z" fill="{fill}" fill-opacity="{op}"/>'
            f'<path d="M18 76a12 12 0 0 0 12 12v-1a11 11 0 0 1-11-11Z" fill="{accent}" fill-opacity="{rim_opacity * 0.62:.3f}"/>'
        ),
        "bottom": (
            f'<rect x="30" y="76" width="24" height="12" fill="{fill}" fill-opacity="{op}"/>'
            f'<rect x="30" y="87" width="24" height="1" fill="{accent}" fill-opacity="{rim_opacity * 0.62:.3f}"/>'
        ),
        "bottomright": (
            f'<path d="M66 76a12 12 0 0 1-12 12V76Z" fill="{fill}" fill-opacity="{op}"/>'
            f'<path d="M66 76a12 12 0 0 1-12 12v-1a11 11 0 0 0 11-11Z" fill="{accent}" fill-opacity="{rim_opacity * 0.62:.3f}"/>'
        ),
    }[region]
    return f'<g id="{identifier}">{transparent}{paint}</g>'


def _decoration_additions(p: Mapping[str, str]) -> str:
    pieces: list[str] = [
        "<!-- MoOS Aurorae v3: explicit blur, inner-border and opaque-mode contract. -->"
    ]
    for prefix, fill, accent, opacity, rim in (
        ("decoration-opaque", p["canvas"], p["luminous"], 1.0, 0.18),
        ("decoration-opaque-inactive", p["surface"], p["outline"], 1.0, 0.16),
    ):
        for region in (
            "topleft", "top", "topright", "left", "center", "right",
            "bottomleft", "bottom", "bottomright",
        ):
            pieces.append(_frame_piece(
                f"{prefix}-{region}", region=region, fill=fill, accent=accent,
                opacity=opacity, rim_opacity=rim,
            ))

    # There is deliberately NO mask-* frame here. The mask is Aurorae's opt-in
    # for KWin blur behind the decoration — and this decoration is 100% opaque
    # (measured: every titlebar pixel alpha=255). aurorae.v2 creates the blur
    # region iff hasElementPrefix("mask"), and KWin then computes blur every
    # frame behind pixels that fully cover it: pure GPU waste with zero visual
    # effect. The material decision is recorded here: in MoOS UI, PERSISTENT
    # surfaces (window frames) are solid for predictable caption contrast on
    # any content; glass is reserved for TRANSIENT shell surfaces (dock,
    # popups, notifications). If titlebars ever go translucent, reintroduce
    # the mask AND re-verify caption contrast on all 16 themes.

    # Inner-border FrameSvgs: only their edge is visible; the center stays
    # transparent as recommended by Aurorae for performance.
    inner = {
        "topleft": '<path d="M18 52V24A12 12 0 0 1 30 12v1a11 11 0 0 0-11 11v28Z"/>',
        "top": '<rect x="30" y="12" width="24" height="1"/>',
        "topright": '<path d="M54 12a12 12 0 0 1 12 12v28h-1V24a11 11 0 0 0-11-11Z"/>',
        "left": '<rect x="18" y="52" width="1" height="24"/>',
        "center": '<rect x="30" y="52" width="24" height="24" fill-opacity="0.001"/>',
        "right": '<rect x="65" y="52" width="1" height="24"/>',
        "bottomleft": '<path d="M18 76a12 12 0 0 0 12 12v-1a11 11 0 0 1-11-11Z"/>',
        "bottom": '<rect x="30" y="87" width="24" height="1"/>',
        "bottomright": '<path d="M66 76a12 12 0 0 1-12 12v-1a11 11 0 0 0 11-11Z"/>',
    }
    bounds = {
        "topleft": '<rect width="30" height="52" fill-opacity="0"/>',
        "top": '<rect x="30" width="24" height="52" fill-opacity="0"/>',
        "topright": '<rect x="54" width="30" height="52" fill-opacity="0"/>',
        "left": '<rect y="52" width="30" height="24" fill-opacity="0"/>',
        "center": '<rect x="30" y="52" width="24" height="24" fill-opacity="0"/>',
        "right": '<rect x="54" y="52" width="30" height="24" fill-opacity="0"/>',
        "bottomleft": '<rect y="76" width="30" height="36" fill-opacity="0"/>',
        "bottom": '<rect x="30" y="76" width="24" height="36" fill-opacity="0"/>',
        "bottomright": '<rect x="54" y="76" width="30" height="36" fill-opacity="0"/>',
    }
    for prefix, colour, opacity in (
        ("innerborder", p["luminous"], 0.34),
        ("innerborder-inactive", p["outline"], 0.22),
    ):
        for region, path in inner.items():
            pieces.append(
                f'<g id="{prefix}-{region}" fill="{colour}" fill-opacity="{opacity}">'
                f'{bounds[region]}{path}</g>'
            )

    for prefix, fill in (
        ("decoration-maximized-opaque", p["card"]),
        ("decoration-maximized-opaque-inactive", p["surface"]),
    ):
        pieces.append(
            f'<rect id="{prefix}-center" x="30" y="52" width="24" height="24" fill="{fill}"/>'
        )
    return "\n".join(pieces)


def _title_end_stop(text: str, base: str, path: pathlib.Path) -> str:
    """Return the last stop colour of the canonical `title`/`i-title` ramp."""
    source = re.search(
        rf'<linearGradient id="{base}" [^>]*>(.*?)</linearGradient>', text, re.S)
    if source is None:
        raise SystemExit(f"{path}: canonical frame has no `{base}` gradient")
    stops = re.findall(r'stop-color="(#[0-9A-Fa-f]{6})"', source.group(1))
    if not stops:
        raise SystemExit(f"{path}: `{base}` gradient has no colour stops")
    return stops[-1]


def _repair_maximized_paint(text: str, path: pathlib.Path) -> str:
    """Paint the maximized titlebar flat in the ramp's terminal colour.

    The canonical frame filled the maximized pieces with url(#title) — a
    userSpaceOnUse gradient over y=12..52, the RESTORED bar's rows — while the
    maximized rect sits at y=0..24. Sampling outside the span clamps to the
    START stop: the whole bar rendered as one flat wrong colour (#527F79 on
    Light), captions fell to 3.12:1, focus changes flashed the full bar
    dark<->light, and because every light palette shares that start colour,
    seven palettes produced one identical teal slab.

    A gradient cannot fix it either way: FrameSvg stretches the center cell,
    so userSpaceOnUse spans distort with the stretch, and the effective
    objectBoundingBox is the whole window rect, not the visible strip — both
    were measured rendering a barely-moving ramp across the bar. So the
    maximized bar is deliberately FLAT, in the exact colour the restored ramp
    lands on (#E1F0EC active / #C9E2DD inactive on Light). Grounded, calm,
    high-contrast, per-palette — the floating window keeps its ramp, the
    docked window rests on the ramp's terminal. Idempotent: re-running
    resolves to the same flat fills.
    """
    # Drop the -max gradient defs an earlier revision of this repair added.
    text = re.sub(
        r'<linearGradient id="i?-?title-max"[^>]*>.*?</linearGradient>',
        "", text, flags=re.S)

    active_end = _title_end_stop(text, "title", path)
    inactive_end = _title_end_stop(text, "i-title", path)

    def retarget(match: re.Match) -> str:
        element = match.group(0)
        for stale, flat in (
            ("url(#i-title-max)", inactive_end),
            ("url(#title-max)", active_end),
            ("url(#i-title)", inactive_end),
            ("url(#title)", active_end),
        ):
            element = element.replace(f'fill="{stale}"', f'fill="{flat}"')
        return element

    return re.sub(r'<rect id="decoration-maximized-[^"]*"[^>]*/>', retarget, text)


def _augment_decoration(path: pathlib.Path, p: Mapping[str, str]) -> None:
    text = path.read_text(encoding="utf-8")
    marker = "<!-- MoOS Aurorae v3:"
    if marker in text:
        text = text[:text.index(marker)] + "</svg>\n"
    if "</svg>" not in text:
        raise SystemExit(f"invalid Aurorae decoration SVG: {path}")
    text = _repair_maximized_paint(text, path)
    text = text.replace("</svg>", _decoration_additions(p) + "\n</svg>", 1)
    _write(path, text)


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


def _button_svg(name: str, p: Mapping[str, str]) -> str:
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
    def mix(ink: str, background: str, alpha: float) -> str:
        channels = lambda value: tuple(int(value.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))
        return "#" + "".join(f"{round(a * alpha + b * (1 - alpha)):02X}"
                             for a, b in zip(channels(ink), channels(background)))

    def contrast(one: str, other: str) -> float:
        def luminance(value: str) -> float:
            rgb = [int(value.lstrip("#")[i:i+2], 16) / 255 for i in (0, 2, 4)]
            linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in rgb]
            return sum(v * w for v, w in zip(linear, (.2126, .7152, .0722)))
        lo, hi = sorted((luminance(one), luminance(other)))
        return (hi + .05) / (lo + .05)

    # This small asymmetric cut belongs to the existing Tidal Horizon language.
    # All actions share one quiet material at rest; colour identifies a state,
    # never a red/yellow/green traffic-light arrangement.
    shape = "M17 10H27L34 17V27A7 7 0 0 1 27 34H17A7 7 0 0 1 10 27V17A7 7 0 0 1 17 10Z"
    body: list[str] = []
    for state in BUTTON_STATES:
        inactive = state.endswith("-inactive") or state == "inactive"
        disabled = state.startswith("deactivated")
        hover = state.startswith("hover")
        pressed = state.startswith("pressed")
        fill = mix(semantic, p["surface"], .32 if pressed else .18) if hover or pressed else mix(p["text"], p["surface"], .035 if inactive else .07)
        ink = mix(p["text"], fill, .38) if disabled else p["text"]
        if not disabled and contrast(ink, fill) < 4.5:
            ink = max((p["text"], "#14202D", "#F1F5F4"), key=lambda value: contrast(value, fill))
        if not disabled and contrast(ink, fill) < 4.5:
            raise SystemExit(f"{name}/{state}: window button ink has insufficient contrast")
        scale = ' transform="translate(22 22) scale(.94) translate(-22 -22)"' if pressed else ""
        body.append(
            f'  <g id="{state}-center"><rect width="44" height="44" fill="#000" fill-opacity="0"/>'
            f'<g{scale}><path data-moos-role="face" d="{shape}" fill="{fill}"/>'
            f'<path d="M17 10H27L34 17L33.3 17.7L26.6 11H17Z" fill="{mix(ink, fill, .2)}"/>'
            f'<g data-moos-role="glyph" transform="translate(12 12)">{_glyph(name, ink)}</g></g></g>'
        )
    return "\n".join((
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<svg xmlns="http://www.w3.org/2000/svg" width="44" height="44" viewBox="0 0 44 44">',
        f'  <!-- MoOS {name}: visible glyph at rest, semantic colour on interaction. -->',
        *body,
        "</svg>",
    ))


def aurorae_rc(p: Mapping[str, str]) -> str:
    def rgba(role: str, alpha: int = 255) -> str:
        value = p[role].lstrip("#")
        return ",".join(str(int(value[index:index + 2], 16)) for index in (0, 2, 4)) + f",{alpha}"

    return f"""[General]
# A centred title remains balanced for both LTR and RTL window captions.
TitleAlignment=Center
TitleVerticalAlignment=Center
Animation=140
ActiveTextColor={rgba('text')}
InactiveTextColor={rgba('muted')}
UseTextShadow=false
HaloActive=false
HaloInactive=false
Shadow=true
LeftButtons=M
RightButtons=HIAX

[Layout]
BorderLeft=1
BorderRight=1
BorderBottom=1
TitleEdgeTop=0
TitleEdgeBottom=0
TitleEdgeLeft=4
TitleEdgeRight=4
TitleBorderLeft=6
TitleBorderRight=6
TitleHeight=44

TitleEdgeTopMaximized=0
TitleEdgeBottomMaximized=0
TitleEdgeLeftMaximized=0
TitleEdgeRightMaximized=0

ButtonWidth=44
ButtonHeight=44
ButtonSpacing=2
# Native input remains 44px in both states; only the 24px artwork is inset.
# Maximized targets reach the screen edge. No client content enters this bar.
ButtonMarginTop=0
ButtonMarginTopMaximized=0
# Aurorae v2 centres the caption between the two button groups, not in the
# window. MoOS keeps all three actions on one side (kwinrc XIA, mirrored by
# KDecoration for RTL) and puts one explicit spacer `_` on the other side. The
# spacer is exactly the action group (3 x 44 + 2 x 2 = 136), so the caption is
# centred on the window in both directions. KDecoration disables spacer input,
# so the title bar still drags and double-clicks through it. Measured in a
# private native KWin (scripts/review/window-frames-native.py): +-36.5 px off
# centre with nothing opposite the actions, within 1.3 px with this spacer.
ExplicitButtonSpacer=136

PaddingLeft=18
PaddingRight=18
PaddingTop=12
PaddingBottom=24
"""


def render_aurorae_suite(
    target: pathlib.Path,
    p: Mapping[str, str],
    *,
    plugin_name: str,
) -> None:
    """Complete one Aurorae package already copied into *target*."""
    decoration = target / "decoration.svg"
    if not decoration.is_file():
        raise SystemExit(f"missing canonical Aurorae frame: {decoration}")
    _augment_decoration(decoration, p)
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


def validate_aurorae_suite(
    target: pathlib.Path,
    *,
    plugin_name: str,
) -> None:
    """Fail loudly if Aurorae would receive a partial decoration package."""
    decoration = target / "decoration.svg"
    ids = _svg_ids(decoration)
    for prefix in (
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
    # a decoration whose every pixel is opaque (alpha=255, measured). A mask
    # returning here means either wasted GPU per frame or an undocumented move
    # to translucent titlebars — both need a reviewed decision, not drift.
    stray_mask = sorted(i for i in ids if i.startswith("mask-"))
    if stray_mask:
        raise SystemExit(
            f"{decoration} declares a blur mask ({stray_mask[0]}) but the "
            f"frame is opaque — remove it or make the material decision "
            f"explicit (see _decoration_additions)"
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

    # The maximized bar must be FLAT in the title ramp's terminal colour.
    # It may reference NO gradient: the canonical url(#title) fill sampled the
    # restored bar's y=12..52 span from a rect at y=0..24 and clamped to the
    # start stop (the wrong-colour slab, 3.12:1 captions, one identical bar
    # across every light palette) — and no replacement span survives
    # FrameSvg's center-cell stretch (both userSpaceOnUse and
    # objectBoundingBox measured as a barely-moving ramp). See
    # _repair_maximized_paint.
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
        "TitleHeight=44",
        "ButtonWidth=44",
        "ButtonHeight=44",
        "RightButtons=HIAX",
        "ButtonMarginTop=0",
        "ButtonMarginTopMaximized=0",
        "ExplicitButtonSpacer=136",
    ):
        if setting not in rc:
            raise SystemExit(f"{expected_rc} is missing required setting {setting}")
