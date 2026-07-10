#!/usr/bin/env python3
"""Fast, deterministic QA for MoOS Nova raster and theme assets."""

from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SHARE = ROOT / "system_files" / "usr" / "share"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def inspect_image(
    path: Path,
    size: tuple[int, int],
    modes: tuple[str, ...],
    *,
    alpha: bool = False,
    max_bytes: int | None = None,
) -> None:
    require(path.is_file(), f"missing: {path.relative_to(ROOT)}")
    with Image.open(path) as image:
        image.load()
        require(image.size == size, f"bad size {image.size}: {path.relative_to(ROOT)}")
        require(image.mode in modes, f"bad mode {image.mode}: {path.relative_to(ROOT)}")
        require(bool(image.info.get("icc_profile")), f"missing ICC: {path.relative_to(ROOT)}")
        if alpha:
            require("A" in image.getbands(), f"missing alpha: {path.relative_to(ROOT)}")
            corners = [image.getpixel((0, 0)), image.getpixel((size[0] - 1, 0)), image.getpixel((0, size[1] - 1))]
            # LANCZOS can leave a mathematically negligible alpha=1 fringe at
            # 16px even when the source corners are fully transparent.
            require(all(pixel[-1] <= 1 for pixel in corners), f"opaque icon corner: {path.relative_to(ROOT)}")
    if max_bytes is not None:
        require(path.stat().st_size < max_bytes, f"oversize file: {path.relative_to(ROOT)}")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_wallpapers() -> None:
    for package in ("NovaAurora", "NovaDeep", "NovaPulse"):
        root = SHARE / "wallpapers" / package
        metadata = json.loads((root / "metadata.json").read_text(encoding="utf-8"))
        require(metadata["KPlugin"]["Id"] == package, f"wrong package id: {package}")
        for folder in ("images", "images_dark"):
            inspect_image(root / "contents" / folder / "3840x2160.png", (3840, 2160), ("RGB",), max_bytes=8 * 1024 * 1024)
            inspect_image(root / "contents" / folder / "3440x1440.png", (3440, 1440), ("RGB",), max_bytes=8 * 1024 * 1024)
            inspect_image(root / "contents" / folder / "2560x1600.png", (2560, 1600), ("RGB",), max_bytes=8 * 1024 * 1024)
        inspect_image(root / "contents" / "screenshot.png", (1920, 1080), ("RGB",), max_bytes=8 * 1024 * 1024)


def verify_icons() -> None:
    names = ("moos-hardware", "moos-compat", "moos-updater", "moos-recovery", "moos-welcome")
    sizes = (16, 22, 24, 32, 48, 64, 128, 256)
    for name in names:
        seen: set[str] = set()
        for size in sizes:
            path = SHARE / "icons" / "hicolor" / f"{size}x{size}" / "apps" / f"{name}.png"
            inspect_image(path, (size, size), ("RGBA",), alpha=True)
            seen.add(digest(path))
        require(len(seen) == len(sizes), f"duplicate size exports: {name}")
    for size in (16, 22, 24, 32):
        inspect_image(
            SHARE / "icons" / "hicolor" / f"{size}x{size}" / "apps" / "moos-moai.png",
            (size, size),
            ("RGBA",),
            alpha=True,
        )


def verify_installer_and_grub() -> None:
    authored = SHARE / "anaconda" / "pixmaps"
    canonical = SHARE / "moos" / "branding" / "anaconda"
    specs = {
        "sidebar-bg.png": (200, 800),
        "sidebar-logo.png": (200, 160),
        "topbar-bg.png": (900, 64),
    }
    for name, size in specs.items():
        inspect_image(authored / name, size, ("RGBA",), alpha=name == "sidebar-logo.png")
        inspect_image(canonical / name, size, ("RGBA",), alpha=name == "sidebar-logo.png")
        require(digest(authored / name) == digest(canonical / name), f"canonical mismatch: {name}")
    inspect_image(SHARE / "moos" / "grub-theme" / "background.png", (1920, 1080), ("RGB",))


def verify_sddm() -> None:
    theme = SHARE / "sddm" / "themes" / "moos-nova"
    inspect_image(theme / "backgrounds" / "default.jpg", (3840, 2160), ("RGB",))
    require(not (theme / "backgrounds" / "smoky.jpg").exists(), "stock SDDM fallback remains")
    require(not (theme / "fonts").exists(), "bundled Red Hat fonts remain")
    require([path.name for path in (theme / "configs").glob("*.conf")] == ["moos-nova.conf"], "unused SDDM presets remain")
    source = (ROOT / "artwork" / "nova-session-icon.svg").read_bytes()
    for path in (theme / "icons" / "sessions").glob("*.svg"):
        require(path.read_bytes() == source, f"foreign session art: {path.name}")
    qml_and_config = b"\n".join(path.read_bytes() for path in [
        theme / "components" / "Config.qml",
        theme / "components" / "IconButton.qml",
        theme / "configs" / "moos-nova.conf",
    ])
    require(b"RedHatDisplay" not in qml_and_config, "RedHatDisplay reference remains")


def verify_previews() -> None:
    root = SHARE / "plasma" / "look-and-feel" / "org.moos.nova" / "contents" / "previews"
    inspect_image(root / "fullscreenpreview.jpg", (1920, 1080), ("RGB",))
    inspect_image(root / "preview.png", (600, 337), ("RGBA", "RGB"))
    inspect_image(root / "lockscreen.png", (600, 337), ("RGBA", "RGB"))
    inspect_image(root / "splash.png", (300, 169), ("RGB", "RGBA"))


def verify_plasma_identity_svgs() -> None:
    theme = SHARE / "plasma" / "desktoptheme" / "Nova"
    branding = ET.parse(theme / "widgets" / "branding.svg").getroot()
    start = ET.parse(theme / "icons" / "start.svg").getroot()
    branding_ids = {element.attrib.get("id") for element in branding.iter()}
    start_ids = {element.attrib.get("id") for element in start.iter()}
    require("brilliant" in branding_ids, "Plasma branding element id is missing")
    require(
        {"16-16-start-here-kde", "22-22-start-here-kde", "start-here-kde"}.issubset(start_ids),
        "Plasma 6.7 start icon element ids are missing",
    )


def verify_text_files() -> None:
    candidates = list((ROOT / "artwork").glob("*"))
    candidates += list((SHARE / "wallpapers").glob("Nova*/metadata.json"))
    candidates += list((SHARE / "wallpapers").glob("Nova*/README.md"))
    candidates += list((SHARE / "sddm" / "themes" / "moos-nova").rglob("*.qml"))
    candidates += list((SHARE / "sddm" / "themes" / "moos-nova").rglob("*.conf"))
    for path in candidates:
        if not path.is_file() or path.suffix.lower() in {".png", ".jpg", ".jpeg"}:
            continue
        data = path.read_bytes()
        require(not data.startswith(b"\xef\xbb\xbf"), f"UTF-8 BOM: {path.relative_to(ROOT)}")
        require(b"\r\n" not in data, f"CRLF: {path.relative_to(ROOT)}")


def main() -> None:
    verify_wallpapers()
    verify_icons()
    verify_installer_and_grub()
    verify_sddm()
    verify_previews()
    verify_plasma_identity_svgs()
    verify_text_files()
    print("PASS: Nova visual assets are complete and internally consistent")


if __name__ == "__main__":
    main()
