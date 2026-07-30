#!/usr/bin/env python3
"""generate_login_scene.py — deterministic MoOS doorway assets.

Splash, Login, Lock and Logout use the code-native Tidal Horizon Portal. This
script synchronises that reviewed QML byte-for-byte across every doorway and
all 16 look-and-feel palettes. It also retains deterministic glow/ring sprites
for the separate panel-brand, Hero Clock and Mo AI scenes that still consume
them. Doorway QML itself is loop-free and does not reference those rasters.

Deterministic: same inputs -> same bytes (PIL, no randomness, no timestamps).

The Tidal Horizon Portal is code-native QML, not a rendered bitmap. Its reviewed
master lives at artwork/tidal-portal/TidalHorizon.qml and is copied byte-for-byte
into Splash, Login, Lock and Logout. That relationship matters more than four
similar-looking implementations: when the horizon geometry changes, every
doorway changes together.

Usage:
    python3 artwork/generate_login_scene.py
"""
from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parent.parent
SHARE = REPO / "system_files/usr/share"
PORTAL_MASTER = REPO / "artwork/tidal-portal/TidalHorizon.qml"
PORTAL_OUTS = (
    SHARE / "plasma/wallpapers/org.moos.ui2.greeter/contents/ui/TidalHorizon.qml",
    SHARE / "plasma/shells/org.kde.plasma.desktop/contents/lockscreen/TidalHorizon.qml",
    SHARE / "plasma/look-and-feel/org.moos.ui2/contents/splash/TidalHorizon.qml",
    SHARE / "plasma/look-and-feel/org.moos.ui2.light/contents/splash/TidalHorizon.qml",
    SHARE / "plasma/look-and-feel/org.moos.ui2/contents/logout/TidalHorizon.qml",
    SHARE / "plasma/look-and-feel/org.moos.ui2.light/contents/logout/TidalHorizon.qml",
)
SPLASH_MASTER = REPO / "artwork/tidal-portal/Splash.qml"
SPLASH_OUTS = (
    SHARE / "plasma/look-and-feel/org.moos.ui2/contents/splash/Splash.qml",
    SHARE / "plasma/look-and-feel/org.moos.ui2.light/contents/splash/Splash.qml",
)
SESSION_QML_MIRRORS = (
    (
        SHARE / "plasma/look-and-feel/org.moos.ui2/contents/logout/Logout.qml",
        SHARE / "plasma/look-and-feel/org.moos.ui2.light/contents/logout/Logout.qml",
    ),
    (
        SHARE / "plasma/look-and-feel/org.moos.ui2/contents/logout/MoOSUI2ActionButton.qml",
        SHARE / "plasma/look-and-feel/org.moos.ui2.light/contents/logout/MoOSUI2ActionButton.qml",
    ),
)
FAMILY_QML = (
    (
        "splash/Splash.qml",
        SHARE / "plasma/look-and-feel/org.moos.ui2/contents/splash/Splash.qml",
    ),
    (
        "splash/TidalHorizon.qml",
        SHARE / "plasma/look-and-feel/org.moos.ui2/contents/splash/TidalHorizon.qml",
    ),
    (
        "logout/Logout.qml",
        SHARE / "plasma/look-and-feel/org.moos.ui2/contents/logout/Logout.qml",
    ),
    (
        "logout/MoOSUI2ActionButton.qml",
        SHARE / "plasma/look-and-feel/org.moos.ui2/contents/logout/MoOSUI2ActionButton.qml",
    ),
    (
        "logout/TidalHorizon.qml",
        SHARE / "plasma/look-and-feel/org.moos.ui2/contents/logout/TidalHorizon.qml",
    ),
)
OUTS = (
    SHARE / "plasma/plasmoids/org.moos.brand/contents/images",
    SHARE / "plasma/plasmoids/org.moos.heroclock/contents/images",
    # The canonical shared copy for APPS (Mo AI's glass backdrop reads these
    # absolute paths — plasma packages keep their own package-local copies).
    SHARE / "moos/brand",
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


def comet_ring(size: int, head: tuple[int, int, int], tail: tuple[int, int, int],
               sweep_deg: float = 250.0, radius_frac: float = 0.465,
               width_frac: float = 0.016, peak: int = 235) -> Image.Image:
    """A thin luminous ring arc with a comet tail: brightest at its head,
    fading to nothing along `sweep_deg`, colour travelling head→tail. Rotating
    this sprite behind the emblem gives the orbit a direction and a life that
    a full uniform circle (which reads as a static border) never has."""
    from math import atan2, degrees, exp, hypot
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    px = img.load()
    centre = (size - 1) / 2
    ring_r = size * radius_frac
    sigma = size * width_frac
    for y in range(size):
        for x in range(size):
            dx, dy = x - centre, y - centre
            r = hypot(dx, dy)
            radial = exp(-((r - ring_r) ** 2) / (2 * sigma * sigma))
            if radial < 0.01:
                continue
            ang = (degrees(atan2(dy, dx)) + 360.0) % 360.0
            if ang > sweep_deg:
                continue
            t = ang / sweep_deg              # 0 at the head, 1 at the tail tip
            fade = (1.0 - t) ** 1.8
            # The head needs a cap. fade peaks at ang=0 while `ang > sweep_deg`
            # zeroes the wrapped neighbour one degree behind it, so the arc
            # terminated in a full-brightness razor chop — at 4K it read as a
            # rendering glitch orbiting the boot splash on every boot. Ramping
            # the first 6 degrees rounds the tip into an actual comet head.
            fade *= min(1.0, ang / 6.0)
            a = int(peak * radial * fade)
            if a <= 0:
                continue
            c = tuple(int(head[i] + (tail[i] - head[i]) * t) for i in range(3))
            px[x, y] = c + (a,)
    return img


def main() -> None:
    portal = PORTAL_MASTER.read_bytes()
    for out in PORTAL_OUTS:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(portal)
        print(f"wrote {out}")

    splash = SPLASH_MASTER.read_bytes()
    for out in SPLASH_OUTS:
        out.write_bytes(splash)
        print(f"wrote {out}")

    for source, out in SESSION_QML_MIRRORS:
        out.write_bytes(source.read_bytes())
        print(f"mirrored {source.name} -> {out}")

    family_root = SHARE / "plasma/look-and-feel"
    for package in sorted(family_root.glob("org.moos.ui2*")):
        if not package.is_dir():
            continue
        for relative, source in FAMILY_QML:
            out = package / "contents" / relative
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(source.read_bytes())
        print(f"synced Tidal Portal QML -> {package.name}")

    # The brand halo behind the emblem — wide, quiet falloff.
    glow_cyan = radial_glow(640, CYAN, peak=170, gamma=2.6)
    glow_violet = radial_glow(640, VIOLET, peak=170, gamma=2.6)
    # The orbiting spark — small, bright core, fast falloff.
    spark = radial_glow(96, (196, 240, 255), peak=255, gamma=1.6)
    # The comet ring — the emblem's orbit made visible, cyan head, violet tail.
    ring = comet_ring(640, CYAN, VIOLET)
    for out in OUTS:
        out.mkdir(parents=True, exist_ok=True)
        glow_cyan.save(out / "glow-cyan.png")
        glow_violet.save(out / "glow-violet.png")
        spark.save(out / "spark.png")
        ring.save(out / "ring.png")
        print(f"wrote {out}/{{glow-cyan,glow-violet,spark,ring}}.png")


if __name__ == "__main__":
    main()
