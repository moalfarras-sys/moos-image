#!/usr/bin/env python3
"""generate_login_scene.py — the animated-brand glow sprites.

Every surface that animates the MoOS emblem — the login scene
(org.moos.ui2.greeter), the logout greeter (org.moos.ui2*/contents/logout),
and the lock screen (the plasma-desktop shell override) — lights it the same
way: a breathing brand glow behind the mark and a small orbiting spark. QML
has no radial gradients without a shader, and shaders are banned from MoOS
always-on scenes (they run forever, on every boot, on every GPU), so the
light is pre-baked here as tiny alpha sprites the scenes only move and fade —
the exact philosophy the boot splash already uses (translucent discs,
Animators only).

The family look-and-feel packages (nova/amethyst/midnight/aurora) do NOT get
sprites from here: generate_moos_themes.py copies the base logout tree —
sprites included — when it builds them. Only the two hand-maintained LNF
halves and the two non-LNF surfaces are written directly.

Deterministic: same inputs -> same bytes (PIL, no randomness, no timestamps).

Usage:
    python3 artwork/generate_login_scene.py
"""
from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parent.parent
SHARE = REPO / "system_files/usr/share"
OUTS = (
    SHARE / "plasma/wallpapers/org.moos.ui2.greeter/contents/images",
    SHARE / "plasma/look-and-feel/org.moos.ui2/contents/logout/images",
    SHARE / "plasma/look-and-feel/org.moos.ui2.light/contents/logout/images",
    SHARE / "plasma/shells/org.kde.plasma.desktop/contents/lockscreen/images",
    SHARE / "plasma/plasmoids/org.moos.brand/contents/images",
)

# Brand light colours — the emblem's own cyan/violet, the UI2 identity accents.
CYAN = (34, 211, 238)      # #22D3EE
VIOLET = (139, 92, 246)    # #8B5CF6


def radial_glow(size: int, rgb: tuple[int, int, int], peak: int, gamma: float) -> Image.Image:
    """A soft circular glow: colour constant, alpha falls off radially."""
    img = Image.new("RGBA", (size, size), rgb + (0,))
    alpha = Image.new("L", (size, size), 0)
    px = alpha.load()
    centre = (size - 1) / 2
    for y in range(size):
        for x in range(size):
            dx = (x - centre) / centre
            dy = (y - centre) / centre
            r = (dx * dx + dy * dy) ** 0.5
            if r < 1.0:
                px[x, y] = int(peak * (1.0 - r) ** gamma)
    img.putalpha(alpha)
    return img


def main() -> None:
    # The brand halo behind the emblem — wide, quiet falloff.
    glow_cyan = radial_glow(640, CYAN, peak=170, gamma=2.6)
    glow_violet = radial_glow(640, VIOLET, peak=170, gamma=2.6)
    # The orbiting spark — small, bright core, fast falloff.
    spark = radial_glow(96, (196, 240, 255), peak=255, gamma=1.6)
    for out in OUTS:
        out.mkdir(parents=True, exist_ok=True)
        glow_cyan.save(out / "glow-cyan.png")
        glow_violet.save(out / "glow-violet.png")
        spark.save(out / "spark.png")
        print(f"wrote {out}/{{glow-cyan,glow-violet,spark}}.png")


if __name__ == "__main__":
    main()
