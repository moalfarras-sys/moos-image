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

    # The blur mask follows the visible decoration inside the established
    # 18/12/24 px shadow padding. Transparent bounding rectangles deliberately
    # keep the mask pieces aligned with the painted FrameSvg pieces.
    for region in (
        "topleft", "top", "topright", "left", "center", "right",
        "bottomleft", "bottom", "bottomright",
    ):
        pieces.append(_frame_piece(
            f"mask-{region}", region=region, fill="#000000", accent="#000000",
            opacity=1.0, rim_opacity=0.0,
        ))

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


def _augment_decoration(path: pathlib.Path, p: Mapping[str, str]) -> None:
    text = path.read_text(encoding="utf-8")
    marker = "<!-- MoOS Aurorae v3:"
    if marker in text:
        text = text[:text.index(marker)] + "</svg>\n"
    if "</svg>" not in text:
        raise SystemExit(f"invalid Aurorae decoration SVG: {path}")
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
            f'<rect x="6.25" y="11.55" width="7.5" height="1.7" rx=".85" '
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
    body: list[str] = []
    for state in BUTTON_STATES:
        inactive = state.endswith("-inactive") or state == "inactive"
        disabled = state.startswith("deactivated")
        hover = state.startswith("hover")
        pressed = state.startswith("pressed")
        if disabled:
            disc, disc_opacity = p["surface"], 0.18
            glyph, glyph_opacity = p["muted"], 0.34
        elif pressed:
            disc, disc_opacity = semantic, 0.92
            glyph, glyph_opacity = p["selected_text"], 1.0
        elif hover:
            disc, disc_opacity = semantic, 0.26 if inactive else 0.34
            glyph, glyph_opacity = semantic, 0.78 if inactive else 1.0
        elif inactive:
            disc, disc_opacity = p["surface"], 0.10
            glyph, glyph_opacity = p["muted"], 0.58
        else:
            disc, disc_opacity = p["surface"], 0.16
            glyph, glyph_opacity = p["text"], 0.84
        scale = ' transform="translate(10 10) scale(.92) translate(-10 -10)"' if pressed else ""
        body.append(
            f'  <g id="{state}-center"{scale}>'
            f'<rect x="1" y="1" width="18" height="18" rx="6.2" fill="{semantic}" '
            f'fill-opacity="{disc_opacity * 0.78:.3f}"/>'
            f'<rect x="2" y="2" width="16" height="16" rx="5.2" fill="{disc}" '
            f'fill-opacity="{disc_opacity:.3f}"/>'
            f'<g opacity="{glyph_opacity:.3f}">{_glyph(name, glyph)}</g></g>'
        )
    return "\n".join((
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 20 20">',
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
TitleEdgeTop=5
TitleEdgeBottom=5
TitleEdgeLeft=10
TitleEdgeRight=10
TitleBorderLeft=10
TitleBorderRight=10
TitleHeight=32

TitleEdgeTopMaximized=0
TitleEdgeBottomMaximized=0
TitleEdgeLeftMaximized=0
TitleEdgeRightMaximized=0

ButtonWidth=20
ButtonHeight=20
ButtonSpacing=6
ButtonMarginTop=1
ExplicitButtonSpacer=8

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
        "mask",
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
        "TitleHeight=32",
        "ButtonWidth=20",
        "RightButtons=HIAX",
    ):
        if setting not in rc:
            raise SystemExit(f"{expected_rc} is missing required setting {setting}")
