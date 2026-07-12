#!/usr/bin/env python3
"""Generate the MoOS Nova FrameSvg set for the Plasma Style (desktoptheme).

Why this exists
---------------
The Nova Plasma Style used to ship only branding/button/viewitem, so Plasma
resolved panel-background, tasks and tooltip through the FallbackTheme chain
(Nova -> breeze-dark -> default). The panel, the task buttons and the tooltips
were therefore literally Breeze geometry with Nova colours poured over them —
which is exactly why the desktop still read as "stock KDE".

These are original MoOS Nova FrameSvgs: a floating, rounded, translucent glass
dock; a calm task indicator (glass tile + Nova accent underline) instead of
Breeze's filled blue slab; and a matching tooltip.

The FrameSvg contract (verified against the installed Breeze
widgets/panel-background.svgz and libplasma 6.7.2)
-------------------------------------------------
* Nine-patch element ids: center, top, bottom, left, right, topleft, topright,
  bottomleft, bottomright. Their element sizes drive DRAWING.
* hint-{top,bottom,left,right}-margin drive the CONTENT inset independently of
  the drawn corner size — that is how a 16px corner radius can coexist with a
  6px content margin.
* hint-{top,bottom,left,right}-inset are ~0 in Breeze (1e-8): the floating-panel
  gap is produced by PanelView, NOT by the SVG. Kept at ~0 to match.
* mask-* mirrors the shape and defines the region KWin is allowed to blur.
  Without a rounded mask the blur bleeds out past the rounded corners.
* tasks.svg prefixes: the task delegate asks for ["south-<state>", "<state>"]
  on a bottom panel, so the unprefixed set is what a bottom dock actually uses.

Qt's SVG renderer does NOT support feGaussianBlur, so every soft edge here is
built from gradients — the same technique the existing Nova button.svg uses.

Run:  python3 artwork/tools/gen-nova-plasma-svgs.py
Writes into system_files/usr/share/plasma/desktoptheme/Nova/widgets/.
"""

from __future__ import annotations

import pathlib

# ---------------------------------------------------------------- Nova tokens
GLASS_TOP = "#263557"  # lifted navy — top of the glass
GLASS_BOTTOM = "#0B1220"  # deep navy — bottom of the glass
CYAN = "#22D3EE"
BLUE = "#2E7BFF"
AMBER = "#FBBF24"

HAIRLINE = "#FFFFFF"  # rim light / borders are white at low alpha

REPO = pathlib.Path(__file__).resolve().parents[2]
OUT = REPO / "system_files/usr/share/plasma/desktoptheme/Nova/widgets"

STYLE = """  <style id="current-color-scheme" type="text/css">
    .ColorScheme-Background { color: #111A2E; }
    .ColorScheme-Highlight  { color: #2E7BFF; }
    .ColorScheme-Text       { color: #E6EDF7; }
  </style>"""


# ------------------------------------------------------------------- geometry
def corner_fill(x: float, y: float, r: float, which: str) -> str:
    """Filled quarter-disc for one corner of a rounded rect.

    Points are emitted clockwise, so every arc uses sweep-flag 1.
    """
    if which == "topleft":  # arc centre (x+r, y+r)
        return f"M {x},{y+r} A {r},{r} 0 0 1 {x+r},{y} L {x+r},{y+r} Z"
    if which == "topright":  # arc centre (x, y+r)
        return f"M {x},{y} A {r},{r} 0 0 1 {x+r},{y+r} L {x},{y+r} Z"
    if which == "bottomright":  # arc centre (x, y)
        return f"M {x+r},{y} A {r},{r} 0 0 1 {x},{y+r} L {x},{y} Z"
    if which == "bottomleft":  # arc centre (x+r, y)
        return f"M {x+r},{y+r} A {r},{r} 0 0 1 {x},{y} L {x+r},{y} Z"
    raise ValueError(which)


def corner_ring(x: float, y: float, r: float, which: str, w: float = 1.0) -> str:
    """The rim-light arc for one corner, as a FILLED ring segment `w` thick.

    NEVER draw a 9-patch rim with `stroke`. Qt's boundsOnElement includes half
    the stroke width, so a 1px stroke inflates the element's bounding box by
    0.5px past the cell it is supposed to occupy. FrameSvg then maps that
    inflated box onto the target rect — and on a stretched edge the sub-pixel of
    empty bbox is magnified by the stretch factor. On this 4K dock the top edge
    stretches ~25px of art across ~2500px, turning 0.5px of slop into a *50px
    transparent band* punched through the dock right next to the corner. It was
    measured, not guessed: the band appeared only in the row whose pieces carried
    a stroke, and vanished in the strokeless centre row.

    A filled ring keeps the bounding box exactly equal to the cell.
    """
    ri = r - w
    if which == "topleft":      # outer arc (0,r)->(r,0), inner arc back
        return (f"M {x},{y+r} A {r},{r} 0 0 1 {x+r},{y} L {x+r},{y+w} "
                f"A {ri},{ri} 0 0 0 {x+w},{y+r} Z")
    if which == "topright":
        return (f"M {x},{y} A {r},{r} 0 0 1 {x+r},{y+r} L {x+r-w},{y+r} "
                f"A {ri},{ri} 0 0 0 {x},{y+w} Z")
    if which == "bottomright":
        return (f"M {x+r},{y} A {r},{r} 0 0 1 {x},{y+r} L {x},{y+r-w} "
                f"A {ri},{ri} 0 0 0 {x+r-w},{y} Z")
    if which == "bottomleft":
        return (f"M {x+r},{y+r} A {r},{r} 0 0 1 {x},{y} L {x+w},{y} "
                f"A {ri},{ri} 0 0 0 {x+r},{y+r-w} Z")
    raise ValueError(which)


def hint(name: str, x: float, y: float, w: float, h: float) -> str:
    """A zero-alpha rect whose *bounding box* carries a number to Plasma."""
    return (f'  <rect id="{name}" x="{x}" y="{y}" width="{w}" height="{h}" '
            f'fill="none" opacity="0"/>')


# ------------------------------------------------------- panel-background.svg
def panel_background() -> str:
    r = 16          # corner radius == corner element size
    edge = 24       # length of the stretchable edge pieces
    # The nine cells are laid out CONTIGUOUSLY — no gutters between them.
    # This matters: the glass is a single userSpaceOnUse gradient spanning the
    # whole canvas, and each piece samples the slice of it that sits under that
    # piece. Leave a 4px gutter between rows and the gradient *skips* 4px at
    # every seam, so the top strip ends on a lighter tone than the centre strip
    # begins on — which paints two hard horizontal steps across the dock. That
    # bug was visible on-device before the gutters came out. Keep them touching.
    x0, x1, x2 = 0, r, r + edge
    y0, y1, y2 = 0, r, r + edge
    total = x2 + r  # 56

    def rim(op: float) -> str:
        # Filled, never stroked — see corner_ring().
        return f'fill="{HAIRLINE}" fill-opacity="{op}"'

    # The rim is brightest along the top (light comes from above) and fades
    # toward the bottom, which is what sells "a pane of glass" rather than
    # "a rectangle with a border".
    TOP_RIM, SIDE_RIM, BOT_RIM = 0.20, 0.11, 0.05

    # The canvas has to cover the parked mask column and the hint column too —
    # QSvgRenderer clips to the viewBox, so an element outside it renders empty.
    canvas_w, canvas_h = 160, 70

    p: list[str] = []
    p.append('<?xml version="1.0" encoding="UTF-8"?>')
    p.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_w}" '
             f'height="{canvas_h}" viewBox="0 0 {canvas_w} {canvas_h}">')
    p.append("  <!-- MoOS Nova — floating glass dock. Original art. -->")
    p.append(STYLE)
    p.append("  <defs>")
    p.append(f'    <linearGradient id="nova-glass" gradientUnits="userSpaceOnUse" '
             f'x1="0" y1="0" x2="0" y2="{total}">')  # spans all three rows
    p.append(f'      <stop offset="0" stop-color="{GLASS_TOP}" stop-opacity="0.62"/>')
    p.append(f'      <stop offset="0.55" stop-color="#16203A" stop-opacity="0.66"/>')
    p.append(f'      <stop offset="1" stop-color="{GLASS_BOTTOM}" stop-opacity="0.74"/>')
    p.append("    </linearGradient>")
    p.append("  </defs>")

    fill = 'fill="url(#nova-glass)"'

    # --- nine-patch: fill then rim, one group per element id -----------------
    for which, (cx, cy) in (
        ("topleft", (x0, y0)), ("topright", (x2, y0)),
        ("bottomleft", (x0, y2)), ("bottomright", (x2, y2)),
    ):
        rim_op = TOP_RIM if "top" in which else BOT_RIM
        p.append(f'  <g id="{which}">')
        p.append(f'    <path d="{corner_fill(cx, cy, r, which)}" {fill}/>')
        p.append(f'    <path d="{corner_ring(cx, cy, r, which)}" {rim(rim_op)}/>')
        p.append("  </g>")

    p.append('  <g id="top">')
    p.append(f'    <rect x="{x1}" y="{y0}" width="{edge}" height="{r}" {fill}/>')
    p.append(f'    <rect x="{x1}" y="{y0}" width="{edge}" height="1" {rim(TOP_RIM)}/>')
    p.append("  </g>")

    p.append('  <g id="bottom">')
    p.append(f'    <rect x="{x1}" y="{y2}" width="{edge}" height="{r}" {fill}/>')
    p.append(f'    <rect x="{x1}" y="{y2+r-1}" width="{edge}" height="1" {rim(BOT_RIM)}/>')
    p.append("  </g>")

    p.append('  <g id="left">')
    p.append(f'    <rect x="{x0}" y="{y1}" width="{r}" height="{edge}" {fill}/>')
    p.append(f'    <rect x="{x0}" y="{y1}" width="1" height="{edge}" {rim(SIDE_RIM)}/>')
    p.append("  </g>")

    p.append('  <g id="right">')
    p.append(f'    <rect x="{x2}" y="{y1}" width="{r}" height="{edge}" {fill}/>')
    p.append(f'    <rect x="{x2+r-1}" y="{y1}" width="1" height="{edge}" {rim(SIDE_RIM)}/>')
    p.append("  </g>")

    p.append(f'  <rect id="center" x="{x1}" y="{y1}" width="{edge}" '
             f'height="{edge}" {fill}/>')

    # --- mask: same silhouette, flat opaque. Bounds the KWin blur ------------
    # Parked in its own column (MX) rather than on top of the visible art:
    # FrameSvg renders strictly by element id so overlap would work, but a file
    # you cannot eyeball is a file you cannot debug. Breeze parks them too.
    MX = 80
    mfill = 'fill="#000000"'
    for which, (cx, cy) in (
        ("topleft", (MX + x0, y0)), ("topright", (MX + x2, y0)),
        ("bottomleft", (MX + x0, y2)), ("bottomright", (MX + x2, y2)),
    ):
        p.append(f'  <path id="mask-{which}" d="{corner_fill(cx, cy, r, which)}" {mfill}/>')
    p.append(f'  <rect id="mask-top" x="{MX+x1}" y="{y0}" width="{edge}" height="{r}" {mfill}/>')
    p.append(f'  <rect id="mask-bottom" x="{MX+x1}" y="{y2}" width="{edge}" height="{r}" {mfill}/>')
    p.append(f'  <rect id="mask-left" x="{MX+x0}" y="{y1}" width="{r}" height="{edge}" {mfill}/>')
    p.append(f'  <rect id="mask-right" x="{MX+x2}" y="{y1}" width="{r}" height="{edge}" {mfill}/>')
    p.append(f'  <rect id="mask-center" x="{MX+x1}" y="{y1}" width="{edge}" height="{edge}" {mfill}/>')

    # --- hints ---------------------------------------------------------------
    # Content margins are deliberately far smaller than the 16px drawn corner:
    # the dock needs a tight, airy gutter, not a 16px dead border.
    m = 6
    p.append(hint("hint-top-margin", 100, 0, 4, m))
    p.append(hint("hint-bottom-margin", 100, 10, 4, m))
    p.append(hint("hint-left-margin", 100, 20, m, 4))
    p.append(hint("hint-right-margin", 100, 30, m, 4))
    # Insets stay ~0, exactly like Breeze: the floating gap is PanelView's job.
    eps = 1e-8
    p.append(hint("hint-top-inset", 100, 40, 4, eps))
    p.append(hint("hint-bottom-inset", 100, 44, 4, eps))
    p.append(hint("hint-left-inset", 100, 48, eps, 4))
    p.append(hint("hint-right-inset", 100, 54, eps, 4))
    # KSvg TILES the borders and the centre by default; `hint-stretch-borders`
    # is the documented opt-in to stretch them instead (breeze's background.svgz
    # and dragger.svgz use it). Breeze's panel gets away with tiling because its
    # art is a flat fill — Nova's glass is a gradient, so tiling printed a
    # visible lattice of seams right across the dock. Stretch, and do NOT ship
    # `hint-tile-center`, which is what tiles the middle.
    p.append(hint("hint-stretch-borders", 100, 60, 4, 4))

    p.append("</svg>")
    return "\n".join(p) + "\n"


# ------------------------------------------------------------------ tasks.svg
def tasks() -> str:
    r = 10           # task tile corner radius
    edge = 12
    # Contiguous, for the same reason as the panel: the accent underline is one
    # gradient running across three separate pieces (left cap, stretched bar,
    # right cap), and a gutter would make the colour jump at each cap.
    x0, x1, x2 = 0, r, r + edge
    block_w = x2 + r  # 32
    block_h = 32

    # state -> (tile fill, tile alpha, rim colour, rim alpha, accent or None)
    #
    # Breeze paints the active task as a saturated filled slab, which is the
    # single loudest "this is stock KDE" tell on the whole dock.
    #
    # Nova does NOT put a bordered tile behind the icon. The MoOS launcher icons
    # already carry their own rounded, coloured plates, so a second rounded plate
    # behind them reads as noise and fights the icon it is meant to support (this
    # was tried on-device first, and it looked busy). The active window is marked
    # the way a dock should mark it: a whisper of a tile plus one confident Nova
    # accent underline. Hover is the only state that leans on a fill.
    states = {
        "normal":    (None, 0.00, None, 0.0, None),
        "hover":     ("#FFFFFF", 0.09, None, 0.0, None),
        "focus":     ("#FFFFFF", 0.06, None, 0.0, "accent"),
        "minimized": ("#FFFFFF", 0.04, None, 0.0, None),
        "attention": (AMBER, 0.16, AMBER, 0.40, None),
    }

    p: list[str] = []
    p.append('<?xml version="1.0" encoding="UTF-8"?>')
    total_h = block_h * len(states)
    # Wide enough to keep the parked hint column inside the viewBox — anything
    # outside it is clipped away and would silently read back as a zero margin.
    canvas_w = 80
    p.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_w}" '
             f'height="{total_h}" viewBox="0 0 {canvas_w} {total_h}">')
    p.append("  <!-- MoOS Nova — task tiles. Original art. -->")
    p.append(STYLE)
    p.append("  <defs>")
    # userSpaceOnUse across the block width, NOT objectBoundingBox: with a
    # per-object gradient each of the three pieces would run the full cyan->blue
    # ramp inside itself, so the underline would read as three repeated gradients
    # instead of one. In user space each piece samples only its own slice.
    p.append('    <linearGradient id="nova-accent" gradientUnits="userSpaceOnUse" '
             f'x1="0" y1="0" x2="{block_w}" y2="0">')
    p.append(f'      <stop offset="0" stop-color="{CYAN}"/>')
    p.append(f'      <stop offset="1" stop-color="{BLUE}"/>')
    p.append("    </linearGradient>")
    p.append("  </defs>")

    for i, (state, (fc, fa, sc, sa, accent)) in enumerate(states.items()):
        by = i * block_h
        y0, y1, y2 = by, by + r, by + r + edge

        def paint(op: float) -> str:
            if fc is None or op == 0.0:
                return 'fill="none"'
            return f'fill="{fc}" fill-opacity="{op}"'

        def rim(op: float) -> str:
            # Filled, never stroked — same bounding-box trap as the panel.
            if sc is None or op == 0.0:
                return 'fill="none"'
            return f'fill="{sc}" fill-opacity="{op}"'

        # accent underline: 3px tall, sits on the bottom edge of the tile
        ah = 3.0
        ay = y2 + r - ah  # bottom of the block minus bar height

        for which, (cx, cy) in (
            ("topleft", (x0, y0)), ("topright", (x2, y0)),
            ("bottomleft", (x0, y2)), ("bottomright", (x2, y2)),
        ):
            p.append(f'  <g id="{state}-{which}">')
            p.append(f'    <path d="{corner_fill(cx, cy, r, which)}" {paint(fa)}/>')
            p.append(f'    <path d="{corner_ring(cx, cy, r, which)}" {rim(sa)}/>')
            if accent and which in ("bottomleft", "bottomright"):
                # rounded cap of the underline, tucked inside the tile corner
                if which == "bottomleft":
                    cap = (f'M {cx+3},{ay} H {cx+r} V {ay+ah} H {cx+3} '
                           f'A {ah/2},{ah/2} 0 0 1 {cx+3},{ay} Z')
                else:
                    cap = (f'M {cx},{ay} H {cx+r-3} '
                           f'A {ah/2},{ah/2} 0 0 1 {cx+r-3},{ay+ah} '
                           f'H {cx} V {ay} Z')
                p.append(f'    <path d="{cap}" fill="url(#nova-accent)"/>')
            p.append("  </g>")

        p.append(f'  <g id="{state}-top">')
        p.append(f'    <rect x="{x1}" y="{y0}" width="{edge}" height="{r}" {paint(fa)}/>')
        p.append(f'    <rect x="{x1}" y="{y0}" width="{edge}" height="1" {rim(sa)}/>')
        p.append("  </g>")

        p.append(f'  <g id="{state}-bottom">')
        p.append(f'    <rect x="{x1}" y="{y2}" width="{edge}" height="{r}" {paint(fa)}/>')
        p.append(f'    <rect x="{x1}" y="{y2+r-1}" width="{edge}" height="1" {rim(sa)}/>')
        if accent:
            p.append(f'    <rect x="{x1}" y="{ay}" width="{edge}" height="{ah}" '
                     f'fill="url(#nova-accent)"/>')
        p.append("  </g>")

        p.append(f'  <g id="{state}-left">')
        p.append(f'    <rect x="{x0}" y="{y1}" width="{r}" height="{edge}" {paint(fa)}/>')
        p.append(f'    <rect x="{x0}" y="{y1}" width="1" height="{edge}" {rim(sa)}/>')
        p.append("  </g>")

        p.append(f'  <g id="{state}-right">')
        p.append(f'    <rect x="{x2}" y="{y1}" width="{r}" height="{edge}" {paint(fa)}/>')
        p.append(f'    <rect x="{x2+r-1}" y="{y1}" width="1" height="{edge}" {rim(sa)}/>')
        p.append("  </g>")

        p.append(f'  <rect id="{state}-center" x="{x1}" y="{y1}" width="{edge}" '
                 f'height="{edge}" {paint(fa)}/>')

    # Icon inset inside a task tile.
    p.append(hint("normal-hint-top-margin", 60, 0, 4, 4))
    p.append(hint("normal-hint-bottom-margin", 60, 8, 4, 4))
    p.append(hint("normal-hint-left-margin", 60, 16, 4, 4))
    p.append(hint("normal-hint-right-margin", 60, 24, 4, 4))
    # Stretch, don't tile — otherwise the accent underline is chopped into one
    # repeat per 12px of tile width and reads as a dashed line. One hint per
    # state prefix: KSvg looks the hint up under the prefix it is drawing.
    for st in states:
        p.append(hint(f"{st}-hint-stretch-borders", 60, 32, 4, 4))

    p.append("</svg>")
    return "\n".join(p) + "\n"


def simple_rounded_frame(prefix: str, y: int, fill: str, opacity: float,
                         rim: str, rim_opacity: float, radius: int = 12,
                         edge: int = 24) -> list[str]:
    """One fill-only FrameSvg state laid out in a horizontal-safe 9-patch."""
    x0, x1, x2 = 0, radius, radius + edge
    y0, y1, y2 = y, y + radius, y + radius + edge
    attr = f'fill="{fill}" fill-opacity="{opacity}"'
    out: list[str] = []
    for which, (x, yy) in (("topleft", (x0, y0)), ("topright", (x2, y0)),
                            ("bottomleft", (x0, y2)), ("bottomright", (x2, y2))):
        out.append(f'  <g id="{prefix}{which}">')
        out.append(f'    <path d="{corner_fill(x, yy, radius, which)}" {attr}/>')
        out.append(f'    <path d="{corner_ring(x, yy, radius, which)}" fill="{rim}" fill-opacity="{rim_opacity}"/>')
        out.append("  </g>")
    out.extend([
        f'  <g id="{prefix}top"><rect x="{x1}" y="{y0}" width="{edge}" height="{radius}" {attr}/><rect x="{x1}" y="{y0}" width="{edge}" height="1" fill="{rim}" fill-opacity="{rim_opacity}"/></g>',
        f'  <g id="{prefix}bottom"><rect x="{x1}" y="{y2}" width="{edge}" height="{radius}" {attr}/><rect x="{x1}" y="{y2+radius-1}" width="{edge}" height="1" fill="{rim}" fill-opacity="{rim_opacity * .55}"/></g>',
        f'  <g id="{prefix}left"><rect x="0" y="{y1}" width="{radius}" height="{edge}" {attr}/><rect x="0" y="{y1}" width="1" height="{edge}" fill="{rim}" fill-opacity="{rim_opacity * .7}"/></g>',
        f'  <g id="{prefix}right"><rect x="{x2}" y="{y1}" width="{radius}" height="{edge}" {attr}/><rect x="{x2+radius-1}" y="{y1}" width="1" height="{edge}" fill="{rim}" fill-opacity="{rim_opacity * .7}"/></g>',
        f'  <rect id="{prefix}center" x="{x1}" y="{y1}" width="{edge}" height="{edge}" {attr}/>',
    ])
    return out


def kickoff_popup_background() -> str:
    """Nova glass popup used by Kickoff and other expanded panel applets."""
    p = ['<?xml version="1.0" encoding="UTF-8"?>',
         '<svg xmlns="http://www.w3.org/2000/svg" width="120" height="72" viewBox="0 0 120 72">',
         '  <!-- MoOS Nova overlay: opaque enough without blur, luminous with it. -->', STYLE]
    p += simple_rounded_frame("", 0, "#0B1220", .965, "#76DDF7", .24, 18, 28)
    for side, x, y, w, h in (("top", 86, 0, 4, 12), ("bottom", 86, 16, 4, 12),
                              ("left", 82, 32, 12, 4), ("right", 98, 32, 12, 4)):
        p.append(hint(f"hint-{side}-margin", x, y, w, h))
    p.append(hint("hint-stretch-borders", 86, 44, 4, 4))
    p.append('</svg>')
    return "\n".join(p) + "\n"


def kickoff_lineedit() -> str:
    """Search field states consumed by PlasmaExtras.SearchField."""
    p = ['<?xml version="1.0" encoding="UTF-8"?>',
         '<svg xmlns="http://www.w3.org/2000/svg" width="112" height="180" viewBox="0 0 112 180">', STYLE]
    states = (("base-", "#111A2E", .94, "#4B6287", .55),
              ("hover-", "#162743", .98, CYAN, .62),
              ("focus-", "#13213A", 1.0, "#4FC3FF", .98),
              ("focusframe-", "#13213A", .01, "#8B5CF6", .92))
    for i, state in enumerate(states):
        prefix, fill, opacity, rim, rim_opacity = state
        p += simple_rounded_frame(prefix, i * 44, fill, opacity, rim,
                                  rim_opacity, radius=10, edge=24)
    for prefix in ("base-", "hover-", "focus-"):
        for side, x, y, w, h in (("top", 80, 0, 4, 8), ("bottom", 80, 10, 4, 8),
                                  ("left", 76, 20, 10, 4), ("right", 90, 20, 10, 4)):
            p.append(hint(f"{prefix}hint-{side}-margin", x, y, w, h))
    p.append(hint("hint-tile-center", 104, 0, 1, 1))
    p.append('</svg>')
    return "\n".join(p) + "\n"


def kickoff_heading() -> str:
    """Quiet translucent header/footer bands with a Nova separator glow."""
    p = ['<?xml version="1.0" encoding="UTF-8"?>',
         '<svg xmlns="http://www.w3.org/2000/svg" width="128" height="96" viewBox="0 0 128 96">', STYLE]
    p += simple_rounded_frame("header-", 0, "#111A2E", .72, "#4FC3FF", .13, 8, 32)
    p += simple_rounded_frame("footer-", 48, "#0E1728", .78, "#8B5CF6", .14, 8, 32)
    for side, x, y, w, h in (("top", 100, 0, 4, 6), ("bottom", 100, 8, 4, 6),
                              ("left", 96, 16, 8, 4), ("right", 108, 16, 8, 4)):
        p.append(hint(f"hint-{side}-margin", x, y, w, h))
    p.append(hint("hint-stretch-borders", 100, 28, 4, 4))
    p.append('</svg>')
    return "\n".join(p) + "\n"


def kickoff_listitem() -> str:
    p = ['<?xml version="1.0" encoding="UTF-8"?>',
         '<svg xmlns="http://www.w3.org/2000/svg" width="112" height="148" viewBox="0 0 112 148">', STYLE]
    for i, state in enumerate((("normal-", "#111A2E", .01, "#9FB0C9", .01),
                               ("pressed-", "#163059", .94, "#4FC3FF", .82),
                               ("section-", "#111A2E", .01, "#9FB0C9", .01))):
        prefix, fill, opacity, rim, rim_opacity = state
        p += simple_rounded_frame(prefix, i * 44, fill, opacity, rim,
                                  rim_opacity, radius=9, edge=24)
        for side, x, y, w, h in (("top", 80, 0, 4, 5), ("bottom", 80, 7, 4, 5),
                                  ("left", 76, 14, 7, 4), ("right", 87, 14, 7, 4)):
            p.append(hint(f"{prefix}hint-{side}-margin", x, y + i * 24, w, h))
    p.append('  <rect id="separator" x="0" y="140" width="32" height="1" fill="#7F94B5" fill-opacity="0.24"/>')
    p.append(hint("hint-tile-center", 104, 0, 1, 1))
    p.append('</svg>')
    return "\n".join(p) + "\n"


def kickoff_line() -> str:
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">
{STYLE}
  <rect id="horizontal-line" x="0" y="8" width="32" height="1" fill="#7F94B5" fill-opacity="0.24"/>
  <rect id="vertical-line" x="8" y="0" width="1" height="32" fill="#7F94B5" fill-opacity="0.24"/>
</svg>
'''


def assert_no_strokes(name: str, body: str) -> None:
    """Guard the bounding-box invariant that cost a long debug session.

    Any `stroke` inside a 9-patch piece inflates that piece's bounding box past
    its cell, and FrameSvg magnifies the overflow by the stretch factor. Keep the
    art fill-only so every element's bbox is exactly its cell.
    """
    if "stroke" in body:
        raise SystemExit(
            f"{name}: found a 'stroke' attribute. 9-patch pieces must be "
            f"fill-only — a stroke inflates the element bbox and FrameSvg "
            f"stretches that slop into a visible transparent band. Use a filled "
            f"rect or corner_ring() instead."
        )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, body in (("panel-background.svg", panel_background()),
                       ("tasks.svg", tasks()),
                       ("lineedit.svg", kickoff_lineedit()),
                       ("plasmoidheading.svg", kickoff_heading()),
                       ("listitem.svg", kickoff_listitem()),
                       ("line.svg", kickoff_line())):
        assert_no_strokes(name, body)
        path = OUT / name
        path.write_text(body, encoding="utf-8")
        print(f"wrote {path.relative_to(REPO)}  ({len(body)} bytes)")
    dialogs = OUT.parent / "dialogs"
    dialogs.mkdir(parents=True, exist_ok=True)
    popup = kickoff_popup_background()
    assert_no_strokes("dialogs/background.svg", popup)
    path = dialogs / "background.svg"
    path.write_text(popup, encoding="utf-8")
    print(f"wrote {path.relative_to(REPO)}  ({len(popup)} bytes)")


if __name__ == "__main__":
    main()
