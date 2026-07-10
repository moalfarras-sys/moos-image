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
    icon_profiles: set[str] = set()
    icon_profile_dates: set[bytes] = set()
    for name in names:
        seen: set[str] = set()
        for size in sizes:
            path = SHARE / "icons" / "hicolor" / f"{size}x{size}" / "apps" / f"{name}.png"
            inspect_image(path, (size, size), ("RGBA",), alpha=True)
            seen.add(digest(path))
            with Image.open(path) as image:
                profile = image.info["icc_profile"]
                icon_profiles.add(hashlib.sha256(profile).hexdigest())
                icon_profile_dates.add(profile[24:36])
        require(len(seen) == len(sizes), f"duplicate size exports: {name}")
    require(len(icon_profiles) == 1, "Nova app icons do not share one canonical sRGB profile")
    require(
        icon_profile_dates == {bytes.fromhex("07ea00010001000000000000")},
        "Nova app icon ICC profile date is not deterministic",
    )
    for size in sizes:
        apps = SHARE / "icons" / "hicolor" / f"{size}x{size}" / "apps"
        require(
            digest(apps / "moos-compat.png") != digest(apps / "moos-updater.png"),
            f"Compatibility and Updater icons collapsed at {size}px",
        )
    for size in (16, 22, 24, 32):
        inspect_image(
            SHARE / "icons" / "hicolor" / f"{size}x{size}" / "apps" / "moos-moai.png",
            (size, size),
            ("RGBA",),
            alpha=True,
        )


def verify_symbolic_icons() -> None:
    names = {
        "moos-identity",
        "moos-ai",
        "moos-gaming",
        "moos-android-apps",
        "moos-safe-update",
        "moos-nova-ui",
        "moos-cpu",
        "moos-memory",
        "moos-gpu",
        "moos-storage",
        "moos-network",
        "moos-system",
        "moos-copy",
        "moos-report",
        "moos-warning",
        "moos-phone",
    }
    root = SHARE / "icons" / "hicolor" / "scalable" / "actions"
    actual = {path.stem for path in root.glob("moos-*.svg")}
    require(actual == names, "Nova symbolic icon family is incomplete or contains stale output")
    for name in names:
        path = root / f"{name}.svg"
        svg = ET.parse(path).getroot()
        require(svg.attrib.get("viewBox") == "0 0 64 64", f"bad symbolic icon viewBox: {name}")
        ids = [element.attrib["id"] for element in svg.iter() if "id" in element.attrib]
        require(len(ids) == len(set(ids)), f"duplicate symbolic SVG id: {name}")
        require({"current-color-scheme", "nova"}.issubset(ids), f"missing Nova SVG definitions: {name}")
        tags = {element.tag.rsplit("}", 1)[-1] for element in svg.iter()}
        require("text" not in tags and "image" not in tags, f"font/raster dependency in symbolic icon: {name}")


def verify_no_foreign_visual_branding() -> None:
    """Guard compatibility aliases that upstream still requests by old names.

    The filenames must remain because Anaconda, icon themes, and SDDM request
    them directly. Their *visible content* is required to be MoOS artwork. If
    these aliases are deleted, the original package files can reappear later in
    the image build, so equality checks are safer than filename cleanup.
    """

    hicolor = SHARE / "icons" / "hicolor"
    for size in (48, 64, 128, 256):
        apps = hicolor / f"{size}x{size}" / "apps"
        canonical = apps / "moos-logo.png"
        for alias in ("fedora-logo-icon.png", "org.fedoraproject.AnacondaInstaller.png", "anaconda.png"):
            require(digest(apps / alias) == digest(canonical), f"foreign art returned in compatibility alias: {size}/{alias}")

    legacy_pixmap = SHARE / "pixmaps" / "fedora_logo_med.png"
    with Image.open(legacy_pixmap) as image:
        image.load()
        require(image.size == (279, 80) and image.mode == "RGBA", "bad legacy system-logo alias")
        require(image.getchannel("A").getbbox() == (111, 9, 168, 68), "legacy system-logo alias is not the centered MoOS mark")
    require(
        digest(legacy_pixmap) == "3cd3e6ed5f79a4caedb9211b893d3b37f69f2793381755ec2ea8184479ec0e13",
        "legacy system-logo alias is no longer the reviewed MoOS emblem",
    )

    session_source = (ROOT / "artwork" / "nova-session-icon.svg").read_bytes()
    session_dir = SHARE / "sddm" / "themes" / "moos-nova" / "icons" / "sessions"
    for path in session_dir.glob("*.svg"):
        require(path.read_bytes() == session_source, f"foreign session logo returned: {path.name}")

    liveinst = (SHARE / "applications" / "liveinst.desktop").read_text(encoding="utf-8")
    require("Name=Install MoOS" in liveinst, "installer launcher name is not MoOS")
    require("Icon=moos-logo" in liveinst, "installer launcher can expose an upstream icon")

    # Any foreign-looking visual filename must be one of the intentional lookup
    # aliases above, a neutralized SDDM session alias, or our non-logo Android
    # app-grid symbol. This catches newly added stock art immediately.
    markers = (
        "fedora",
        "kinoite",
        "ubuntu",
        "gnome",
        "plasma",
        "kde",
        "breeze",
        "xfce",
        "cinnamon",
        "hyprland",
        "windows",
        "apple",
        "android",
        "anaconda",
    )
    allowed_files = {
        legacy_pixmap,
        SHARE / "icons" / "hicolor" / "scalable" / "actions" / "moos-android-apps.svg",
    }
    for size in (48, 64, 128, 256):
        apps = hicolor / f"{size}x{size}" / "apps"
        allowed_files.update(
            {
                apps / "fedora-logo-icon.png",
                apps / "org.fedoraproject.AnacondaInstaller.png",
                apps / "anaconda.png",
            }
        )
    visual_suffixes = {".png", ".jpg", ".jpeg", ".svg", ".svgz"}
    for path in SHARE.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in visual_suffixes:
            continue
        if not any(marker in path.name.lower() for marker in markers):
            continue
        require(
            path in allowed_files or path.parent == session_dir,
            f"unreviewed foreign-named visual asset: {path.relative_to(ROOT)}",
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
    metadata = json.loads((theme / "metadata.json").read_text(encoding="utf-8"))
    require(metadata["KPlugin"]["Version"] == "0.3.0", "Plasma Style cache version was not bumped")
    require("FallbackTheme=breeze-dark" in (theme / "plasmarc").read_text(encoding="utf-8"), "Plasma fallback changed")

    parsed: dict[Path, set[str]] = {}
    for path in sorted(theme.rglob("*.svg")):
        root = ET.parse(path).getroot()
        ids = [element.attrib["id"] for element in root.iter() if "id" in element.attrib]
        require(len(ids) == len(set(ids)), f"duplicate SVG id: {path.relative_to(ROOT)}")
        parsed[path] = set(ids)

    branding_ids = parsed[theme / "widgets" / "branding.svg"]
    start_ids = parsed[theme / "icons" / "start.svg"]
    require("brilliant" in branding_ids, "Plasma branding element id is missing")
    require(
        {"16-16-start-here-kde", "22-22-start-here-kde", "start-here-kde"}.issubset(start_ids),
        "Plasma 6.7 start icon element ids are missing",
    )

    positions = {
        "top",
        "topright",
        "right",
        "bottomright",
        "bottom",
        "bottomleft",
        "left",
        "topleft",
        "center",
    }
    viewitem_ids = parsed[theme / "widgets" / "viewitem.svg"]
    expected_viewitem = {"hint-tile-center", "current-color-scheme"}
    for prefix in ("normal", "hover", "selected", "selected+hover"):
        expected_viewitem.update(f"{prefix}-{position}" for position in positions)
    require(expected_viewitem.issubset(viewitem_ids), "Plasma 6.7 view-item FrameSvg contract is incomplete")

    button_ids = parsed[theme / "widgets" / "button.svg"]
    button_prefixes = (
        "shadow",
        "normal",
        "mask-normal",
        "hover",
        "focus",
        "pressed",
        "toolbutton-hover",
        "toolbutton-focus",
        "toolbutton-pressed",
    )
    expected_button = {"current-color-scheme"}
    for prefix in button_prefixes:
        expected_button.update(f"{prefix}-{position}" for position in positions)
    for prefix in button_prefixes:
        if prefix == "mask-normal":
            continue
        expected_button.update(
            f"{prefix}-hint-{direction}-margin"
            for direction in ("top", "right", "bottom", "left")
        )
    expected_button.update(
        {
            "normal-hint-compose-over-border",
            "pressed-hint-compose-over-border",
        }
    )
    require(expected_button.issubset(button_ids), "Plasma 6.7 button FrameSvg contract is incomplete")


def verify_sounds() -> None:
    root = SHARE / "sounds" / "moos-nova"
    index = (root / "index.theme").read_text(encoding="utf-8")
    require("[Sound Theme]" in index, "sound theme header is missing")
    require("Directories=stereo" in index, "sound theme stereo directory is missing")
    events = (
        "desktop-login.oga",
        "message-new-instant.oga",
        "dialog-error.oga",
        "complete-download.oga",
    )
    for name in events:
        path = root / "stereo" / name
        require(path.is_file(), f"missing sound: {name}")
        require(path.read_bytes().startswith(b"OggS"), f"not an Ogg stream: {name}")
        require(path.stat().st_size > 2_000, f"implausibly small sound: {name}")


def verify_text_files() -> None:
    candidates = list((ROOT / "artwork").glob("*"))
    candidates += list((SHARE / "wallpapers").glob("Nova*/metadata.json"))
    candidates += list((SHARE / "wallpapers").glob("Nova*/README.md"))
    candidates += list((SHARE / "sddm" / "themes" / "moos-nova").rglob("*.qml"))
    candidates += list((SHARE / "sddm" / "themes" / "moos-nova").rglob("*.conf"))
    candidates += list((SHARE / "plasma" / "desktoptheme" / "Nova").rglob("*"))
    candidates += [SHARE / "plasma" / "look-and-feel" / "org.moos.nova" / "contents" / "defaults"]
    candidates += list((SHARE / "icons" / "hicolor" / "scalable" / "actions").glob("moos-*.svg"))
    for path in candidates:
        if not path.is_file() or path.suffix.lower() in {".png", ".jpg", ".jpeg"}:
            continue
        data = path.read_bytes()
        require(not data.startswith(b"\xef\xbb\xbf"), f"UTF-8 BOM: {path.relative_to(ROOT)}")
        require(b"\r\n" not in data, f"CRLF: {path.relative_to(ROOT)}")


def main() -> None:
    verify_wallpapers()
    verify_icons()
    verify_symbolic_icons()
    verify_no_foreign_visual_branding()
    verify_installer_and_grub()
    verify_sddm()
    verify_previews()
    verify_plasma_identity_svgs()
    verify_sounds()
    verify_text_files()
    print("PASS: Nova visual assets are complete and internally consistent")


if __name__ == "__main__":
    main()
