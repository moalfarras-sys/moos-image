#!/usr/bin/env python3
"""Fast, deterministic image-integrity QA for MoOS's generated visual assets.

History: this was verify_nova_visuals.py, written for the pre-MoOSUI2 "Nova"
design generation (Nova wallpapers, an SDDM theme, an org.moos.nova look-and-feel,
a Nova desktop theme). All of that was superseded — SDDM was replaced by
plasma-login-manager, and the whole look became the MoOSUI2 family. The old gate
validated a design that no longer exists, so it was rewritten (not deleted) into
this: a lean check of the images the CURRENT engine actually ships and that no
other gate deep-inspects — the sixteen theme wallpapers, the four boot-splash
sprites, and the logo master. Identity/experience/theme correctness live in the
active build gates (verify_identity, verify_image_experience,
verify_user_experience, verify_no_foreign_identity, test_moos_theme_safety);
this one only asserts that the pixels are well-formed.

Run standalone: `python3 artwork/verify_visuals.py`. Wired into the CI "Repo gates"
step (.github/workflows/build.yml) and `just check` — both install Pillow first.
"""
from __future__ import annotations
import json
import pathlib
import sys

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
SHARE = ROOT / "system_files" / "usr" / "share"


class Fail(AssertionError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise Fail(message)


def rel(p: pathlib.Path) -> str:
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def check_image(path: pathlib.Path, *, size=None, modes=("RGB", "RGBA"),
                alpha=False, max_bytes=None):
    require(path.is_file(), f"missing image: {rel(path)}")
    if max_bytes is not None:
        require(path.stat().st_size <= max_bytes,
                f"oversize ({path.stat().st_size} B > {max_bytes}): {rel(path)}")
    with Image.open(path) as im:
        im.load()
        require(im.mode in modes, f"bad mode {im.mode}: {rel(path)}")
        if size is not None:
            require(im.size == size, f"bad size {im.size}, want {size}: {rel(path)}")
        if alpha:
            require("A" in im.getbands(), f"missing alpha channel: {rel(path)}")


# ── the sixteen theme wallpapers ─────────────────────────────────────────────
# Every family member ships three JPG masters (light in images/, dark in
# images_dark/) at the standard aspect set, a screenshot, and a metadata.json
# whose Id matches the package. A truncated/mis-sized master reaches the desktop.
WALLPAPERS = [
    "MoOSUI2Tide", "MoOSUI2Graphite", "MoOSUI2Nova", "MoOSUI2Aurora",
    "MoOSUI2Amethyst", "MoOSUI2Midnight",
    "MoOSUI2NovaLight", "MoOSUI2AuroraLight", "MoOSUI2AmethystLight", "MoOSUI2Daylight",
    "MoOSUI2Arena", "MoOSUI2Forge", "MoOSUI2Scholar",
    "MoOSUI2ArenaLight", "MoOSUI2ForgeLight", "MoOSUI2ScholarLight",
]
WALL_SIZES = [(3840, 2160), (3440, 1440), (2560, 1600)]


def verify_wallpapers() -> None:
    root = SHARE / "wallpapers"
    for pkg in WALLPAPERS:
        base = root / pkg
        meta = json.loads((base / "metadata.json").read_text(encoding="utf-8"))
        require(meta["KPlugin"]["Id"] == pkg, f"wallpaper Id != package name: {pkg}")
        for sub in ("images", "images_dark"):
            for w, h in WALL_SIZES:
                check_image(base / "contents" / sub / f"{w}x{h}.jpg", size=(w, h), modes=("RGB",))
        check_image(base / "contents" / "screenshot.png", modes=("RGB", "RGBA"))


# ── the boot-splash sprites (Plymouth Script theme) ──────────────────────────
def verify_boot_sprites() -> None:
    theme = SHARE / "plymouth" / "themes" / "moos"
    # each is transparent art the script moves; keep them small so the initramfs
    # stays light (the whole reason the theme is sprites, not baked frames).
    for name in ("logo.png", "ring.png", "head.png", "glow.png"):
        check_image(theme / name, modes=("RGBA",), alpha=True, max_bytes=600 * 1024)
    check_image(theme / "logo.png", size=(512, 512), modes=("RGBA",), alpha=True)


# ── the logo master ──────────────────────────────────────────────────────────
def verify_logo() -> None:
    logo = SHARE / "moos" / "moos-logo.png"
    check_image(logo, size=(1024, 1024), modes=("RGBA",), alpha=True)


def main() -> int:
    checks = (verify_wallpapers, verify_boot_sprites, verify_logo)
    failures = []
    for fn in checks:
        try:
            fn()
        except Fail as e:
            failures.append(str(e))
        except Exception as e:  # missing file mid-walk, decode error, etc.
            failures.append(f"{fn.__name__}: {type(e).__name__}: {e}")
    if failures:
        print("VISUALS GATE FAILED:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"VISUALS OK: {len(WALLPAPERS)} wallpapers, boot sprites, logo master all well-formed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
