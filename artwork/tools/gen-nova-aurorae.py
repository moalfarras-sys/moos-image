#!/usr/bin/env python3
"""Generate the "MoOS Nova" Aurorae window decoration.

Why Aurorae
-----------
/etc/xdg/kwinrc shipped `library=org.kde.kwin.breeze`: MoOS windows were Breeze
windows with a Nova palette poured over them, and the title-bar buttons were
Breeze's X / v / ^ glyphs. Fedora 44 packages no richer C++ decoration (klassy,
lightly, sierrabreeze are all absent from the repos), and building one inside the
image would put a compiler on the boot-critical build path for a cosmetic gain.
Aurorae is already installed (`aurorae-6.7.2`, org.kde.kwin.aurorae.so) and is
driven entirely by SVG + an ini file, so it costs the image nothing.

The contract (read out of /usr/share/kwin/aurorae/*.qml, not guessed)
--------------------------------------------------------------------
* decoration.svg is a KSvg FrameSvg addressed by element PREFIX:
  `decoration`, `decoration-inactive`, `decoration-maximized`,
  `decoration-maximized-inactive`.
* Each button is its own FrameSvg file (close.svg, minimize.svg, maximize.svg,
  restore.svg) with prefixes `active`, `hover`, `pressed`, `inactive`.
  AuroraeButton.qml probes them with hasElementPrefix(), which only checks for
  `<prefix>-center` — so a button needs nothing but a centre element, and the
  FrameSvg stretches it over the whole button.
* aurorae.qml: borders.* is the frame KWin reserves for the client, padding.* is
  the region OUTSIDE the window. The decoration FrameSvg is painted across BOTH,
  which means the drop shadow is the theme's job, drawn into the padding.

That last point is the one that matters. Ship a decoration with no shadow and
windows land flat on the wallpaper — visibly *worse* than the Breeze it replaces.
Qt's SVG renderer has no feGaussianBlur, so the shadow here is built from linear
gradients on the four sides and radial gradients in the four corners, which is
the same technique Breeze's own SVGs use.

Also carried over from the Plasma Style work: 9-patch pieces are FILL-ONLY. A
stroke inflates the element's bounding box past its cell and FrameSvg magnifies
the overflow by the stretch factor.

Run:  python3 artwork/tools/gen-nova-aurorae.py
"""

from __future__ import annotations

import pathlib

# ------------------------------------------------------------------ Nova tokens
TITLE_TOP = "#263557"      # lifted navy, top of the title bar
TITLE_BOTTOM = "#161F38"   # settled navy, bottom of the title bar
BODY = "#0B1220"           # window body (sits behind the client, rarely seen)
SHADOW = "#03060D"         # shadow ink — deeper than any surface
RIM = "#FFFFFF"            # rim light, always at low alpha
OUTLINE = "#04070F"        # 1px outline that separates the window from wallpaper

# Nova's own semantic colours, straight out of NovaDark.colors. Circular buttons
# in a red/amber/green triplet are the universal window-control idiom; using
# Nova's *own* negative/neutral/positive hues keeps them MoOS rather than a 1:1
# copy of somebody else's traffic lights.
CLOSE = "#F87171"          # ForegroundNegative
MINIMIZE = "#FBBF24"       # ForegroundNeutral
MAXIMIZE = "#34D399"       # ForegroundPositive
MUTED = "#46536B"          # unfocused window: all three go quiet

# ------------------------------------------------------------------- geometry
R = 12                     # window corner radius
TITLE_H = 30               # title bar height
EDGE_TOP, EDGE_BOTTOM = 5, 5
BORDER = 1                 # side / bottom frame thickness
PAD_L = PAD_R = 18         # shadow reach
PAD_T = 12
PAD_B = 24                 # biased downward: light comes from above

BORDER_TOP = EDGE_TOP + TITLE_H + EDGE_BOTTOM     # 40

# FrameSvg cell sizes. The side cells are deliberately R wide rather than BORDER
# wide: the cell has to be big enough to *contain* the rounded corner art. KWin
# only reserves BORDER px for the client, and the extra is simply painted under
# the client window, which is opaque.
CELL_L = PAD_L + R          # 30
CELL_R = PAD_R + R          # 30
CELL_T = PAD_T + BORDER_TOP  # 52
CELL_B = PAD_B + R          # 36
EDGE = 24                    # stretchable span

W = CELL_L + EDGE + CELL_R   # 84
H = CELL_T + EDGE + CELL_B   # 112

# The window rectangle inside the canvas.
WL, WT = PAD_L, PAD_T
WR, WB = W - PAD_R, H - PAD_B

BTN = 18                     # button cell
DOT = 13                     # coloured disc diameter

REPO = pathlib.Path(__file__).resolve().parents[2]
OUT = REPO / "system_files/usr/share/aurorae/themes/MoOSNova"


def _no_strokes(name: str, body: str) -> None:
    if "stroke" in body:
        raise SystemExit(f"{name}: 9-patch art must be fill-only (see module docstring)")


# --------------------------------------------------------------------- shadow
def shadow_defs(alpha: float) -> str:
    """Side + corner gradients. `alpha` is the shadow's peak opacity."""
    def stops_linear() -> str:
        return (f'<stop offset="0" stop-color="{SHADOW}" stop-opacity="0"/>'
                f'<stop offset="0.55" stop-color="{SHADOW}" stop-opacity="{alpha*0.35:.3f}"/>'
                f'<stop offset="1" stop-color="{SHADOW}" stop-opacity="{alpha:.3f}"/>')

    def stops_radial() -> str:
        # Mirrored: a radial shadow is strongest at the window corner (centre of
        # the gradient) and dies out at the padding edge.
        return (f'<stop offset="0" stop-color="{SHADOW}" stop-opacity="{alpha:.3f}"/>'
                f'<stop offset="0.45" stop-color="{SHADOW}" stop-opacity="{alpha*0.35:.3f}"/>'
                f'<stop offset="1" stop-color="{SHADOW}" stop-opacity="0"/>')

    g = []
    # sides: gradient runs from the outer padding edge inward to the window
    g.append(f'<linearGradient id="sh-top" gradientUnits="userSpaceOnUse" '
             f'x1="0" y1="0" x2="0" y2="{WT}">{stops_linear()}</linearGradient>')
    g.append(f'<linearGradient id="sh-bottom" gradientUnits="userSpaceOnUse" '
             f'x1="0" y1="{H}" x2="0" y2="{WB}">{stops_linear()}</linearGradient>')
    g.append(f'<linearGradient id="sh-left" gradientUnits="userSpaceOnUse" '
             f'x1="0" y1="0" x2="{WL}" y2="0">{stops_linear()}</linearGradient>')
    g.append(f'<linearGradient id="sh-right" gradientUnits="userSpaceOnUse" '
             f'x1="{W}" y1="0" x2="{WR}" y2="0">{stops_linear()}</linearGradient>')
    # corners: centred on the centre of each rounded corner's arc
    for name, cx, cy, rad in (
        ("tl", WL + R, WT + R, R + max(PAD_L, PAD_T)),
        ("tr", WR - R, WT + R, R + max(PAD_R, PAD_T)),
        ("bl", WL + R, WB - R, R + max(PAD_L, PAD_B)),
        ("br", WR - R, WB - R, R + max(PAD_R, PAD_B)),
    ):
        g.append(f'<radialGradient id="sh-{name}" gradientUnits="userSpaceOnUse" '
                 f'cx="{cx}" cy="{cy}" r="{rad}">{stops_radial()}</radialGradient>')
    return "".join(g)


def title_defs(top: str, bottom: str) -> str:
    return (f'<linearGradient id="title" gradientUnits="userSpaceOnUse" '
            f'x1="0" y1="{WT}" x2="0" y2="{WT + BORDER_TOP}">'
            f'<stop offset="0" stop-color="{top}"/>'
            f'<stop offset="1" stop-color="{bottom}"/></linearGradient>')


# ---------------------------------------------------------------- decoration
def decoration_prefix(prefix: str, *, active: bool, maximized: bool) -> str:
    """One FrameSvg prefix: nine cells, each pinned exactly to its cell rect."""
    p: list[str] = []
    title = "url(#title)"
    rim_a = 0.11 if active else 0.05
    out_a = 0.55 if active else 0.35

    if maximized:
        # A maximized window has no padding and no corners: KWin gives the
        # decoration only the title-bar strip and disables every border, so the
        # centre element is the ONLY one that gets painted. It has to BE the
        # title bar. (Getting this wrong paints a maximized title bar in the
        # window-body colour, which is the flat grey slab bug.)
        p.append(f'<rect id="{prefix}-center" x="0" y="0" width="{EDGE}" '
                 f'height="{EDGE}" fill="{title}"/>')
        p.append(f'<rect id="{prefix}-top" x="0" y="0" width="{EDGE}" '
                 f'height="1" fill="{RIM}" fill-opacity="{rim_a}"/>')
        for cell in ("left", "right", "bottom", "topleft", "topright",
                     "bottomleft", "bottomright"):
            p.append(f'<rect id="{prefix}-{cell}" x="0" y="0" width="1" '
                     f'height="1" fill="{title}"/>')
        return "".join(p)

    # ---- top-left: shadow + rounded title-bar corner ------------------------
    p.append(f'<g id="{prefix}-topleft">')
    p.append(f'<rect x="0" y="0" width="{CELL_L}" height="{CELL_T}" fill="url(#sh-tl)"/>')
    p.append(f'<path d="M {WL},{CELL_T} L {WL},{WT+R} A {R},{R} 0 0 1 {WL+R},{WT} '
             f'L {CELL_L},{WT} L {CELL_L},{CELL_T} Z" fill="{title}"/>')
    # 1px outline hugging the same curve, drawn as a filled ring, never a stroke
    p.append(f'<path d="M {WL},{CELL_T} L {WL},{WT+R} A {R},{R} 0 0 1 {WL+R},{WT} '
             f'L {CELL_L},{WT} L {CELL_L},{WT+1} L {WL+R},{WT+1} '
             f'A {R-1},{R-1} 0 0 0 {WL+1},{WT+R} L {WL+1},{CELL_T} Z" '
             f'fill="{OUTLINE}" fill-opacity="{out_a}"/>')
    p.append(f'<path d="M {WL+1},{CELL_T} L {WL+1},{WT+R} A {R-1},{R-1} 0 0 1 {WL+R},{WT+1} '
             f'L {CELL_L},{WT+1} L {CELL_L},{WT+2} L {WL+R},{WT+2} '
             f'A {R-2},{R-2} 0 0 0 {WL+2},{WT+R} L {WL+2},{CELL_T} Z" '
             f'fill="{RIM}" fill-opacity="{rim_a}"/>')
    p.append("</g>")

    # ---- top: shadow strip + title bar + rim --------------------------------
    p.append(f'<g id="{prefix}-top">')
    p.append(f'<rect x="{CELL_L}" y="0" width="{EDGE}" height="{CELL_T}" fill="url(#sh-top)"/>')
    p.append(f'<rect x="{CELL_L}" y="{WT}" width="{EDGE}" height="{BORDER_TOP}" fill="{title}"/>')
    p.append(f'<rect x="{CELL_L}" y="{WT}" width="{EDGE}" height="1" '
             f'fill="{OUTLINE}" fill-opacity="{out_a}"/>')
    p.append(f'<rect x="{CELL_L}" y="{WT+1}" width="{EDGE}" height="1" '
             f'fill="{RIM}" fill-opacity="{rim_a}"/>')
    p.append("</g>")

    # ---- top-right ----------------------------------------------------------
    p.append(f'<g id="{prefix}-topright">')
    p.append(f'<rect x="{CELL_L+EDGE}" y="0" width="{CELL_R}" height="{CELL_T}" fill="url(#sh-tr)"/>')
    p.append(f'<path d="M {CELL_L+EDGE},{WT} L {WR-R},{WT} A {R},{R} 0 0 1 {WR},{WT+R} '
             f'L {WR},{CELL_T} L {CELL_L+EDGE},{CELL_T} Z" fill="{title}"/>')
    p.append(f'<path d="M {CELL_L+EDGE},{WT} L {WR-R},{WT} A {R},{R} 0 0 1 {WR},{WT+R} '
             f'L {WR},{CELL_T} L {WR-1},{CELL_T} L {WR-1},{WT+R} '
             f'A {R-1},{R-1} 0 0 0 {WR-R},{WT+1} L {CELL_L+EDGE},{WT+1} Z" '
             f'fill="{OUTLINE}" fill-opacity="{out_a}"/>')
    p.append("</g>")

    # ---- left / right: shadow + 1px outline (body is under the client) ------
    p.append(f'<g id="{prefix}-left">')
    p.append(f'<rect x="0" y="{CELL_T}" width="{CELL_L}" height="{EDGE}" fill="url(#sh-left)"/>')
    p.append(f'<rect x="{WL}" y="{CELL_T}" width="{CELL_L-WL}" height="{EDGE}" fill="{BODY}"/>')
    p.append(f'<rect x="{WL}" y="{CELL_T}" width="1" height="{EDGE}" '
             f'fill="{OUTLINE}" fill-opacity="{out_a}"/>')
    p.append("</g>")

    p.append(f'<g id="{prefix}-right">')
    p.append(f'<rect x="{CELL_L+EDGE}" y="{CELL_T}" width="{CELL_R}" height="{EDGE}" fill="url(#sh-right)"/>')
    p.append(f'<rect x="{CELL_L+EDGE}" y="{CELL_T}" width="{WR-(CELL_L+EDGE)}" height="{EDGE}" fill="{BODY}"/>')
    p.append(f'<rect x="{WR-1}" y="{CELL_T}" width="1" height="{EDGE}" '
             f'fill="{OUTLINE}" fill-opacity="{out_a}"/>')
    p.append("</g>")

    # ---- centre: behind the client, never actually seen ---------------------
    p.append(f'<rect id="{prefix}-center" x="{CELL_L}" y="{CELL_T}" width="{EDGE}" '
             f'height="{EDGE}" fill="{BODY}"/>')

    # ---- bottom row ---------------------------------------------------------
    p.append(f'<g id="{prefix}-bottomleft">')
    p.append(f'<rect x="0" y="{CELL_T+EDGE}" width="{CELL_L}" height="{CELL_B}" fill="url(#sh-bl)"/>')
    p.append(f'<path d="M {WL},{CELL_T+EDGE} L {WL},{WB-R} A {R},{R} 0 0 0 {WL+R},{WB} '
             f'L {CELL_L},{WB} L {CELL_L},{CELL_T+EDGE} Z" fill="{BODY}"/>')
    p.append(f'<path d="M {WL},{CELL_T+EDGE} L {WL},{WB-R} A {R},{R} 0 0 0 {WL+R},{WB} '
             f'L {CELL_L},{WB} L {CELL_L},{WB-1} L {WL+R},{WB-1} '
             f'A {R-1},{R-1} 0 0 1 {WL+1},{WB-R} L {WL+1},{CELL_T+EDGE} Z" '
             f'fill="{OUTLINE}" fill-opacity="{out_a}"/>')
    p.append("</g>")

    p.append(f'<g id="{prefix}-bottom">')
    p.append(f'<rect x="{CELL_L}" y="{CELL_T+EDGE}" width="{EDGE}" height="{CELL_B}" fill="url(#sh-bottom)"/>')
    p.append(f'<rect x="{CELL_L}" y="{CELL_T+EDGE}" width="{EDGE}" height="{WB-(CELL_T+EDGE)}" fill="{BODY}"/>')
    p.append(f'<rect x="{CELL_L}" y="{WB-1}" width="{EDGE}" height="1" '
             f'fill="{OUTLINE}" fill-opacity="{out_a}"/>')
    p.append("</g>")

    p.append(f'<g id="{prefix}-bottomright">')
    p.append(f'<rect x="{CELL_L+EDGE}" y="{CELL_T+EDGE}" width="{CELL_R}" height="{CELL_B}" fill="url(#sh-br)"/>')
    p.append(f'<path d="M {CELL_L+EDGE},{WB} L {WR-R},{WB} A {R},{R} 0 0 0 {WR},{WB-R} '
             f'L {WR},{CELL_T+EDGE} L {CELL_L+EDGE},{CELL_T+EDGE} Z" fill="{BODY}"/>')
    p.append(f'<path d="M {CELL_L+EDGE},{WB} L {WR-R},{WB} A {R},{R} 0 0 0 {WR},{WB-R} '
             f'L {WR},{CELL_T+EDGE} L {WR-1},{CELL_T+EDGE} L {WR-1},{WB-R} '
             f'A {R-1},{R-1} 0 0 1 {WR-R},{WB-1} L {CELL_L+EDGE},{WB-1} Z" '
             f'fill="{OUTLINE}" fill-opacity="{out_a}"/>')
    p.append("</g>")

    return "".join(p)


def decoration_svg() -> str:
    body = [f'<?xml version="1.0" encoding="UTF-8"?>',
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
            f'viewBox="0 0 {W} {H}">',
            "<!-- MoOS Nova window decoration. Original art. -->"]

    # Active.
    body.append(f'<defs>{shadow_defs(0.42)}{title_defs(TITLE_TOP, TITLE_BOTTOM)}</defs>')
    body.append(decoration_prefix("decoration", active=True, maximized=False))
    body.append(decoration_prefix("decoration-maximized", active=True, maximized=True))

    # Inactive: quieter title bar, and a shadow that pulls back so the focused
    # window reads as the one lifted off the desktop.
    body.append('<defs>'
                + shadow_defs(0.22).replace('id="sh-', 'id="i-sh-')
                + title_defs("#1B2540", "#131B31").replace('id="title"', 'id="i-title"')
                + '</defs>')
    inactive = decoration_prefix("decoration-inactive", active=False, maximized=False)
    inactive = inactive.replace("url(#sh-", "url(#i-sh-").replace("url(#title)", "url(#i-title)")
    body.append(inactive)
    maxi = decoration_prefix("decoration-maximized-inactive", active=False, maximized=True)
    body.append(maxi.replace("url(#title)", "url(#i-title)"))

    body.append("</svg>")
    return "\n".join(body) + "\n"


# ------------------------------------------------------------------- buttons
def button_svg(colour: str, glyph: str) -> str:
    """A window-control button: quiet disc, glyph revealed on hover."""
    c = BTN / 2
    rr = DOT / 2

    def disc(fill: str, op: float = 1.0) -> str:
        return f'<circle cx="{c}" cy="{c}" r="{rr}" fill="{fill}" fill-opacity="{op}"/>'

    def frame(prefix: str, inner: str) -> str:
        # Only `-center` is needed: hasElementPrefix() checks for it, and with no
        # border elements FrameSvg stretches the centre across the whole button.
        return f'<g id="{prefix}-center">{inner}</g>'

    # Glyph strokes are drawn as filled rects/paths — a stroke would inflate the
    # element bbox and shift the glyph off-centre when FrameSvg rescales it.
    g = {
        "close": (f'<path d="M {c-3},{c-3.7} L {c+3.7},{c+3} L {c+3},{c+3.7} '
                  f'L {c-3.7},{c-3} Z" fill="#2A1113"/>'
                  f'<path d="M {c+3},{c-3.7} L {c+3.7},{c-3} L {c-3},{c+3.7} '
                  f'L {c-3.7},{c+3} Z" fill="#2A1113"/>'),
        "minimize": f'<rect x="{c-3.7}" y="{c-0.7}" width="7.4" height="1.4" fill="#2E2205"/>',
        "maximize": (f'<rect x="{c-3.7}" y="{c-0.7}" width="7.4" height="1.4" fill="#06291D"/>'
                     f'<rect x="{c-0.7}" y="{c-3.7}" width="1.4" height="7.4" fill="#06291D"/>'),
        "restore": (f'<rect x="{c-3.7}" y="{c-0.7}" width="7.4" height="1.4" fill="#06291D"/>'),
    }[glyph]

    parts = [f'<?xml version="1.0" encoding="UTF-8"?>',
             f'<svg xmlns="http://www.w3.org/2000/svg" width="{BTN}" height="{BTN}" '
             f'viewBox="0 0 {BTN} {BTN}">',
             frame("active", disc(colour)),
             frame("hover", disc(colour) + g),
             frame("pressed", disc(colour, 0.72) + g),
             # An unfocused window's controls all go quiet — colour is reserved
             # for the window you are actually looking at.
             frame("inactive", disc(MUTED)),
             frame("hover-inactive", disc(colour) + g),
             "</svg>"]
    return "\n".join(parts) + "\n"


# ---------------------------------------------------------------------- theme
THEMERC = f"""[General]
# Title centred, macOS-style, rather than hugged to the button cluster.
TitleAlignment=Center
TitleVerticalAlignment=Center
Animation=120
ActiveTextColor=230,237,247,255
InactiveTextColor=150,166,190,255
UseTextShadow=false
HaloActive=false
HaloInactive=false

[Layout]
BorderLeft={BORDER}
BorderRight={BORDER}
BorderBottom={BORDER}
TitleEdgeTop={EDGE_TOP}
TitleEdgeBottom={EDGE_BOTTOM}
TitleEdgeLeft=10
TitleEdgeRight=10
TitleBorderLeft=8
TitleBorderRight=8
TitleHeight={TITLE_H}

# Maximized: no side/bottom frame, no shadow — just the title bar.
TitleEdgeTopMaximized=0
TitleEdgeBottomMaximized=0
TitleEdgeLeftMaximized=10
TitleEdgeRightMaximized=10

ButtonWidth={BTN}
ButtonHeight={BTN}
ButtonSpacing=8
ButtonMarginTop=0

# The shadow lives here. Aurorae paints the decoration SVG across padding too,
# so this is the room the drop shadow gets to breathe in.
PaddingLeft={PAD_L}
PaddingRight={PAD_R}
PaddingTop={PAD_T}
PaddingBottom={PAD_B}
"""

METADATA = """[Desktop Entry]
Name=MoOS Nova
Comment=Nova navy glass window decoration for MoOS
X-KDE-PluginInfo-Author=Moalfarras
X-KDE-PluginInfo-Name=MoOSNova
X-KDE-PluginInfo-Version=1.0
X-KDE-PluginInfo-License=GPL-3.0-or-later
X-KDE-ServiceTypes=KWin/Decoration
Type=Service
"""


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    files = {
        "decoration.svg": decoration_svg(),
        "close.svg": button_svg(CLOSE, "close"),
        "minimize.svg": button_svg(MINIMIZE, "minimize"),
        "maximize.svg": button_svg(MAXIMIZE, "maximize"),
        "restore.svg": button_svg(MAXIMIZE, "restore"),
        "MoOSNovarc": THEMERC,
        "metadata.desktop": METADATA,
    }
    for name, body in files.items():
        if name.endswith(".svg"):
            _no_strokes(name, body)
        (OUT / name).write_text(body, encoding="utf-8")
        print(f"wrote {(OUT / name).relative_to(REPO)}")


if __name__ == "__main__":
    main()
