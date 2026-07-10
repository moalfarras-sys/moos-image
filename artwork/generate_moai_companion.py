#!/usr/bin/env python3
"""Generate the original Mo AI Nova Companion visual family.

The companion is a deterministic, palette-locked asset rather than an
animated GIF. QML can preload the seven same-size PNG states and cross-fade
opacity/scale on the scene graph without decoding or layout jumps.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

import generate_nova_visuals as nova


ROOT = Path(__file__).resolve().parents[1]
SHARE = ROOT / "system_files" / "usr" / "share"
MASCOT_DIR = SHARE / "moos" / "branding" / "moai" / "mascot"
ICON_ROOT = SHARE / "icons" / "hicolor"
SOURCE_DIR = ROOT / "artwork" / "moai"

P = nova.P
RESAMPLE = nova.RESAMPLE

STATES = (
    "idle",
    "attentive",
    "thinking",
    "success",
    "warning",
    "error",
    "offline",
)

STATE_ACCENT = {
    "idle": P["cyan"],
    "attentive": P["ice"],
    "thinking": P["violet"],
    "success": P["success"],
    "warning": P["warning"],
    "error": P["error"],
    "offline": P["secondary"],
}


def glow(mask: Image.Image, color: str, blur: int, opacity: float) -> Image.Image:
    layer = Image.new("RGBA", mask.size, nova.rgba(color, 255))
    alpha = mask.filter(ImageFilter.GaussianBlur(blur)).point(
        lambda value: round(value * opacity)
    )
    layer.putalpha(alpha)
    return layer


def line_layer(
    size: tuple[int, int],
    points: list[tuple[int, int]],
    color: str,
    width: int,
    *,
    blur: int = 0,
    opacity: int = 255,
) -> Image.Image:
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    draw.line(points, fill=nova.rgba(color, opacity), width=width, joint="curve")
    return layer.filter(ImageFilter.GaussianBlur(blur)) if blur else layer


def capsule_mask(
    size: tuple[int, int], box: tuple[int, int, int, int], radius: int
) -> Image.Image:
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(box, radius=radius, fill=255)
    return mask


def draw_orbit(base: Image.Image, state: str) -> None:
    """Draw the open Horizon halo that gives the companion its silhouette."""

    halo = Image.new("RGBA", base.size, (0, 0, 0, 0))
    hd = ImageDraw.Draw(halo)
    opacity = 185
    first = P["secondary"] if state == "offline" else P["cyan"]
    second = P["secondary"] if state == "offline" else P["violet"]
    hd.arc((128, 102, 896, 870), 202, 331, fill=nova.rgba(first, opacity), width=13)
    hd.arc((128, 102, 896, 870), 26, 151, fill=nova.rgba(second, opacity), width=13)
    hd.arc((170, 144, 854, 828), 212, 314, fill=nova.rgba(P["secondary"] if state == "offline" else P["blue"], opacity), width=5)
    base.alpha_composite(halo.filter(ImageFilter.GaussianBlur(24)))
    base.alpha_composite(halo)


def draw_shell(base: Image.Image, state: str) -> None:
    size = base.size
    accent = STATE_ACCENT[state]

    # Floating side pods keep the mascot unmistakably robotic without using a
    # generic antenna or borrowing another assistant's silhouette.
    pod_mask = Image.new("L", size, 0)
    pd = ImageDraw.Draw(pod_mask)
    pd.rounded_rectangle((130, 392, 224, 620), radius=46, fill=255)
    pd.rounded_rectangle((800, 392, 894, 620), radius=46, fill=255)
    base.alpha_composite(glow(pod_mask, accent, 34, 0.38))
    pods = nova.gradient_fill(
        pod_mask,
        [(0.0, P["raised"]), (0.45, P["blue_deep"]), (1.0, P["violet_deep"])],
    )
    if state == "offline":
        pods.putalpha(pod_mask.point(lambda value: round(value * 0.55)))
    base.alpha_composite(pods)

    shell = capsule_mask(size, (182, 188, 842, 822), 202)
    inner = capsule_mask(size, (211, 221, 813, 790), 174)
    rim = ImageChops.subtract(shell, inner)
    base.alpha_composite(glow(shell, accent, 52, 0.30))
    base.alpha_composite(
        nova.gradient_fill(
            shell,
            [(0.0, P["ice"]), (0.20, P["cyan"]), (0.55, P["blue"]), (1.0, P["violet"])],
        )
    )

    face = nova.gradient_fill(
        inner,
        [(0.0, P["raised"]), (0.42, P["surface"]), (1.0, P["deepest"])],
    )
    if state == "offline":
        desaturated = Image.new("RGBA", size, nova.rgba(P["surface"], 255))
        desaturated.putalpha(inner.point(lambda value: round(value * 0.88)))
        face = Image.alpha_composite(face, desaturated)
    base.alpha_composite(face)

    # The rim is redrawn with a horizontal signature gradient so the shell
    # reads as ceramic/glass rather than a flat rounded rectangle.
    rim_gradient = Image.new("RGBA", size, (0, 0, 0, 0))
    strips = ImageDraw.Draw(rim_gradient)
    colors = (P["cyan"], P["blue"], P["violet"])
    for x in range(1024):
        t = x / 1023
        if t < 0.5:
            a, b, u = nova.rgb(colors[0]), nova.rgb(colors[1]), t * 2
        else:
            a, b, u = nova.rgb(colors[1]), nova.rgb(colors[2]), (t - 0.5) * 2
        color = tuple(round(a[i] + (b[i] - a[i]) * u) for i in range(3))
        strips.line((x, 0, x, 1024), fill=(*color, 255))
    rim_gradient.putalpha(rim)
    base.alpha_composite(rim_gradient)

    # Visor: a long smoked-glass horizon instead of a generic robot face tile.
    visor = capsule_mask(size, (264, 342, 760, 558), 104)
    visor_fill = nova.gradient_fill(
        visor,
        [(0.0, P["navy"]), (0.50, P["deepest"]), (1.0, P["surface"])],
    )
    base.alpha_composite(visor_fill)
    vd = ImageDraw.Draw(base)
    vd.rounded_rectangle(
        (264, 342, 760, 558),
        radius=104,
        outline=nova.rgba(accent, 152 if state != "offline" else 65),
        width=6,
    )

    # A restrained ceramic highlight makes the head feel dimensional at large
    # sizes while disappearing naturally in the pixel-tuned small export.
    highlight = Image.new("RGBA", size, (0, 0, 0, 0))
    hmask = capsule_mask(size, (245, 246, 779, 506), 150)
    ImageDraw.Draw(highlight).ellipse((250, 210, 774, 510), fill=(255, 255, 255, 30))
    highlight.putalpha(ImageChops.multiply(highlight.getchannel("A"), hmask))
    base.alpha_composite(highlight.filter(ImageFilter.GaussianBlur(14)))


def eye_mask(state: str) -> Image.Image:
    mask = Image.new("L", (1024, 1024), 0)
    d = ImageDraw.Draw(mask)
    if state == "attentive":
        d.rounded_rectangle((333, 408, 423, 492), radius=40, fill=255)
        d.rounded_rectangle((601, 408, 691, 492), radius=40, fill=255)
    elif state == "success":
        d.arc((324, 405, 432, 500), 205, 335, fill=255, width=24)
        d.arc((592, 405, 700, 500), 205, 335, fill=255, width=24)
    elif state == "warning":
        d.rounded_rectangle((326, 438, 430, 470), radius=16, fill=255)
        d.rounded_rectangle((594, 438, 698, 470), radius=16, fill=255)
    elif state == "error":
        d.line((337, 422, 417, 492), fill=255, width=24)
        d.line((417, 422, 337, 492), fill=255, width=24)
        d.line((607, 422, 687, 492), fill=255, width=24)
        d.line((687, 422, 607, 492), fill=255, width=24)
    elif state == "offline":
        d.rounded_rectangle((334, 445, 422, 464), radius=9, fill=155)
        d.rounded_rectangle((602, 445, 690, 464), radius=9, fill=155)
    elif state == "thinking":
        d.rounded_rectangle((332, 432, 424, 474), radius=21, fill=255)
        d.ellipse((620, 421, 682, 483), fill=255)
    else:
        d.rounded_rectangle((332, 430, 424, 476), radius=22, fill=255)
        d.rounded_rectangle((600, 430, 692, 476), radius=22, fill=255)
    return mask


def draw_expression(base: Image.Image, state: str) -> None:
    accent = STATE_ACCENT[state]
    eyes = eye_mask(state)
    base.alpha_composite(glow(eyes, accent, 32, 0.74 if state != "offline" else 0.28))
    eye_color = P["secondary"] if state == "offline" else accent
    eye_layer = Image.new("RGBA", base.size, nova.rgba(eye_color, 255))
    eye_layer.putalpha(eyes)
    base.alpha_composite(eye_layer)

    # Small ice highlights give open eyes optical depth without becoming pupils.
    if state in {"idle", "attentive", "thinking"}:
        d = ImageDraw.Draw(base)
        d.rounded_rectangle((350, 439, 382, 451), radius=6, fill=nova.rgba(P["white"], 205))
        if state != "thinking":
            d.rounded_rectangle((618, 439, 650, 451), radius=6, fill=nova.rgba(P["white"], 205))

    # Nova Horizon response line and core. The line changes color with state,
    # but its geometry remains stable so cross-fades never jump.
    horizon = Image.new("RGBA", base.size, (0, 0, 0, 0))
    hd = ImageDraw.Draw(horizon)
    if state == "error":
        hd.line((390, 650, 470, 622), fill=nova.rgba(accent, 238), width=14)
        hd.line((470, 622, 554, 650), fill=nova.rgba(accent, 238), width=14)
        hd.line((554, 650, 634, 622), fill=nova.rgba(accent, 238), width=14)
    elif state == "warning":
        hd.line((390, 634, 634, 634), fill=nova.rgba(accent, 238), width=13)
    elif state == "offline":
        hd.arc((374, 548, 650, 700), 24, 156, fill=nova.rgba(accent, 95), width=10)
    else:
        hd.arc((374, 548, 650, 700), 24, 156, fill=nova.rgba(accent, 235), width=12)
    base.alpha_composite(horizon.filter(ImageFilter.GaussianBlur(18)))
    base.alpha_composite(horizon)

    core = Image.new("L", base.size, 0)
    cd = ImageDraw.Draw(core)
    cd.polygon([(512, 670), (540, 704), (512, 738), (484, 704)], fill=255)
    base.alpha_composite(glow(core, accent, 22, 0.70 if state != "offline" else 0.22))
    core_layer = nova.gradient_fill(
        core,
        [(0.0, P["ice"] if state != "offline" else P["secondary"]), (1.0, accent)],
    )
    base.alpha_composite(core_layer)


def draw_state_badge(base: Image.Image, state: str) -> None:
    if state == "idle":
        return
    accent = STATE_ACCENT[state]
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    if state == "thinking":
        for index, radius in enumerate((10, 13, 16)):
            x, y = 680 + index * 44, 247 - index * 22
            d.ellipse((x - radius, y - radius, x + radius, y + radius), fill=nova.rgba(accent, 230))
    else:
        d.ellipse((716, 208, 812, 304), fill=nova.rgba(P["deepest"], 238), outline=nova.rgba(accent, 245), width=7)
        if state == "success":
            d.line((741, 258, 759, 276, 790, 237), fill=nova.rgba(accent, 255), width=11, joint="curve")
        elif state == "warning":
            d.rounded_rectangle((758, 230, 770, 269), radius=6, fill=nova.rgba(accent, 255))
            d.ellipse((758, 278, 770, 290), fill=nova.rgba(accent, 255))
        elif state == "error":
            d.line((744, 236, 784, 276), fill=nova.rgba(accent, 255), width=11)
            d.line((784, 236, 744, 276), fill=nova.rgba(accent, 255), width=11)
        elif state == "offline":
            d.arc((739, 231, 789, 281), 205, 335, fill=nova.rgba(accent, 220), width=8)
            d.line((742, 279, 786, 233), fill=nova.rgba(accent, 220), width=8)
        elif state == "attentive":
            d.ellipse((752, 244, 776, 268), fill=nova.rgba(accent, 255))

    base.alpha_composite(layer.filter(ImageFilter.GaussianBlur(18)))
    base.alpha_composite(layer)


def companion_master(state: str) -> Image.Image:
    if state not in STATES:
        raise ValueError(f"unknown Mo AI state: {state}")
    image = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    draw_orbit(image, state)
    draw_shell(image, state)
    draw_expression(image, state)
    draw_state_badge(image, state)
    return image


def micro_icon_master() -> Image.Image:
    """Pixel-tuned icon master with thicker forms and no transient detail."""

    image = nova.icon_base(P["violet"])
    shell = capsule_mask(image.size, (244, 270, 780, 736), 148)
    image.alpha_composite(glow(shell, P["cyan"], 30, 0.42))
    image.alpha_composite(
        nova.gradient_fill(shell, [(0.0, P["cyan"]), (0.50, P["blue"]), (1.0, P["violet"])])
    )
    face = capsule_mask(image.size, (274, 300, 750, 706), 120)
    image.alpha_composite(
        nova.gradient_fill(face, [(0.0, P["raised"]), (1.0, P["deepest"])])
    )
    d = ImageDraw.Draw(image)
    d.rounded_rectangle((332, 430, 426, 480), radius=24, fill=nova.rgba(P["cyan"], 255))
    d.rounded_rectangle((598, 430, 692, 480), radius=24, fill=nova.rgba(P["violet"], 255))
    d.arc((388, 526, 636, 650), 24, 156, fill=nova.rgba(P["ice"], 255), width=18)
    return image


def app_icon_master() -> Image.Image:
    image = nova.icon_base(P["violet"])
    mascot = companion_master("idle").resize((820, 820), RESAMPLE)
    image.alpha_composite(mascot, (102, 126))
    return image


def mascot_svg(app_icon: bool) -> str:
    prefix = "" if not app_icon else """
  <rect x="52" y="44" width="920" height="936" rx="218" fill="url(#appShell)" stroke="#FFFFFF" stroke-opacity=".82" stroke-width="8"/>
  <rect x="96" y="132" width="832" height="770" rx="166" fill="url(#appPanel)" stroke="#FFFFFF" stroke-opacity=".56" stroke-width="8"/>
  <path d="M176 930H848" stroke="#8B5CF6" stroke-opacity=".82" stroke-width="10" stroke-linecap="round"/>
"""
    transform = ' transform="translate(102 126) scale(.8)"' if app_icon else ""
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024" viewBox="0 0 1024 1024">
  <!-- Original Mo AI Nova Companion, © Moalfarras. -->
  <defs>
    <linearGradient id="nova" x1="160" y1="150" x2="850" y2="840" gradientUnits="userSpaceOnUse">
      <stop stop-color="#22D3EE"/><stop offset=".52" stop-color="#2E7BFF"/><stop offset="1" stop-color="#8B5CF6"/>
    </linearGradient>
    <linearGradient id="face" x1="512" y1="220" x2="512" y2="790" gradientUnits="userSpaceOnUse">
      <stop stop-color="#1A2740"/><stop offset=".48" stop-color="#111A2E"/><stop offset="1" stop-color="#050A14"/>
    </linearGradient>
    <linearGradient id="appShell" x1="110" y1="70" x2="900" y2="960" gradientUnits="userSpaceOnUse">
      <stop stop-color="#7DEBFF"/><stop offset=".22" stop-color="#22D3EE"/><stop offset=".58" stop-color="#2E7BFF"/><stop offset="1" stop-color="#8B5CF6"/>
    </linearGradient>
    <linearGradient id="appPanel" x1="512" y1="132" x2="512" y2="902" gradientUnits="userSpaceOnUse">
      <stop stop-color="#1A2740"/><stop offset=".52" stop-color="#111A2E"/><stop offset="1" stop-color="#050A14"/>
    </linearGradient>
  </defs>
{prefix}
  <g{transform}>
    <path d="M168 748A384 384 0 0 1 155 342" fill="none" stroke="#22D3EE" stroke-opacity=".78" stroke-width="13" stroke-linecap="round"/>
    <path d="M856 748A384 384 0 0 0 869 342" fill="none" stroke="#8B5CF6" stroke-opacity=".78" stroke-width="13" stroke-linecap="round"/>
    <rect x="130" y="392" width="94" height="228" rx="46" fill="url(#face)" stroke="#22D3EE" stroke-width="7"/>
    <rect x="800" y="392" width="94" height="228" rx="46" fill="url(#face)" stroke="#8B5CF6" stroke-width="7"/>
    <rect x="182" y="188" width="660" height="634" rx="202" fill="url(#nova)"/>
    <rect x="211" y="221" width="602" height="569" rx="174" fill="url(#face)"/>
    <path d="M295 301C384 230 640 230 729 301" fill="none" stroke="url(#nova)" stroke-width="15" stroke-linecap="round"/>
    <rect x="264" y="342" width="496" height="216" rx="104" fill="#050A14" stroke="#22D3EE" stroke-opacity=".66" stroke-width="6"/>
    <rect x="332" y="430" width="92" height="46" rx="22" fill="#22D3EE"/>
    <rect x="600" y="430" width="92" height="46" rx="22" fill="#8B5CF6"/>
    <rect x="350" y="439" width="32" height="12" rx="6" fill="#FFFFFF" fill-opacity=".82"/>
    <rect x="618" y="439" width="32" height="12" rx="6" fill="#FFFFFF" fill-opacity=".82"/>
    <path d="M386 588C438 664 586 664 638 588" fill="none" stroke="url(#nova)" stroke-width="12" stroke-linecap="round"/>
    <path d="M512 670 540 704 512 738 484 704Z" fill="url(#nova)"/>
  </g>
</svg>
'''


def generate_preview() -> None:
    tile_width = 280
    canvas = Image.new("RGBA", (tile_width * len(STATES), 410), nova.rgba(P["navy"], 255))
    canvas = nova.radial_glow(canvas, (0.18, 0.22), 0.48, P["cyan"], 0.16)
    canvas = nova.radial_glow(canvas, (0.82, 0.70), 0.48, P["violet"], 0.14)
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    for index, state in enumerate(STATES):
        asset = Image.open(MASCOT_DIR / f"{state}.png").convert("RGBA").resize((244, 244), RESAMPLE)
        x = index * tile_width + 18
        canvas.alpha_composite(asset, (x, 48))
        accent = STATE_ACCENT[state]
        draw.rounded_rectangle((x + 40, 330, x + 204, 366), radius=18, fill=nova.rgba(P["surface"], 235), outline=nova.rgba(accent, 180), width=2)
        label_box = draw.textbbox((0, 0), state.upper(), font=font)
        label_width = label_box[2] - label_box[0]
        draw.text((x + 122 - label_width / 2, 342), state.upper(), fill=nova.rgba(P["text"], 255), font=font)
    nova.save_png(canvas, SOURCE_DIR / "nova-companion-states.png")


def main() -> None:
    MASCOT_DIR.mkdir(parents=True, exist_ok=True)
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    for state in STATES:
        master = companion_master(state)
        nova.save_png(master.resize((512, 512), RESAMPLE), MASCOT_DIR / f"{state}.png")

    full = app_icon_master()
    micro = micro_icon_master()
    for size in (16, 22, 24, 32, 48, 64, 128, 256):
        source = micro if size <= 32 else full
        nova.save_png(
            source.resize((size, size), RESAMPLE),
            ICON_ROOT / f"{size}x{size}" / "apps" / "moos-moai.png",
        )

    scalable = ICON_ROOT / "scalable" / "apps" / "moos-moai.svg"
    scalable.parent.mkdir(parents=True, exist_ok=True)
    scalable.write_text(mascot_svg(app_icon=True), encoding="utf-8", newline="\n")
    (SOURCE_DIR / "mascot-master.svg").write_text(
        mascot_svg(app_icon=False), encoding="utf-8", newline="\n"
    )
    generate_preview()
    print(f"generated {len(STATES)} Mo AI states, 8 app-icon sizes, and SVG masters")


if __name__ == "__main__":
    main()
