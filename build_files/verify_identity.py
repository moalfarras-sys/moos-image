#!/usr/bin/python3
"""Fail the image build when a user-facing MoOS identity surface regresses."""

from __future__ import annotations

import configparser
import hashlib
import json
from pathlib import Path


ROOT = Path("/")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"IDENTITY FATAL: {message}")


def digest(path: Path) -> str:
    require(path.is_file(), f"missing identity asset: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def desktop(path: str) -> configparser.SectionProxy:
    target = ROOT / path.lstrip("/")
    require(target.is_file(), f"missing desktop entry: {target}")
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.optionxform = str
    parser.read(target, encoding="utf-8")
    require(parser.has_section("Desktop Entry"), f"invalid desktop entry: {target}")
    return parser["Desktop Entry"]


def main() -> None:
    os_release: dict[str, str] = {}
    for line in (ROOT / "usr/lib/os-release").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            os_release[key] = value.strip().strip('"')

    expected = {
        "NAME": "MoOS",
        "ID": "moos",
        "VARIANT": "Nova",
        "VARIANT_ID": "nova",
        "LOGO": "moos-logo",
    }
    for key, value in expected.items():
        require(os_release.get(key) == value, f"os-release {key} must be {value!r}")
    require(os_release.get("PRETTY_NAME", "").startswith("MoOS "),
            "PRETTY_NAME must begin with MoOS")
    require(os_release.get("DEFAULT_HOSTNAME") == "moos",
            "DEFAULT_HOSTNAME must be moos")
    require(os_release.get("CPE_NAME") == "cpe:/o:moos:moos:44",
            "CPE identity must belong to MoOS")
    require(not any(key.startswith("REDHAT_") for key in os_release),
            "inherited Red Hat support identity must be removed")

    session = desktop("/usr/share/wayland-sessions/plasma.desktop")
    require(session.get("Name") == "MoOS", "session picker must display MoOS")
    localized_names = [value for key, value in session.items() if key.startswith("Name[")]
    require(all(value == "MoOS" for value in localized_names),
            "localized session names can leak the upstream desktop name")

    installer = desktop("/usr/share/applications/liveinst.desktop")
    require(installer.get("Name") == "Install MoOS", "installer name is not MoOS")
    require(installer.get("Icon") == "moos-logo", "installer icon is not moos-logo")

    for app in ("moai", "welcome", "hardware", "compathub", "updater", "recovery"):
        entry = desktop(f"/usr/share/applications/org.moos.{app}.desktop")
        require(entry.get("Icon", "").startswith("moos-"),
                f"org.moos.{app} does not use a MoOS icon")

    aliases = (
        "/usr/share/icons/hicolor/48x48/apps/fedora-logo-icon.png",
        "/usr/share/icons/hicolor/48x48/apps/org.fedoraproject.AnacondaInstaller.png",
        "/usr/share/icons/hicolor/48x48/apps/anaconda.png",
        "/usr/share/pixmaps/fedora_logo_med.png",
        "/usr/share/pixmaps/system-logo-white.png",
    )
    # Alias files deliberately keep upstream filenames for compatibility, but
    # their pixels must be the canonical MoOS mark.
    for alias in aliases[:3]:
        alias_path = ROOT / alias.lstrip("/")
        require(digest(alias_path) == digest(alias_path.with_name("moos-logo.png")),
                f"upstream icon alias does not contain the MoOS logo: {alias}")
    for alias in aliases[3:]:
        require((ROOT / alias.lstrip("/")).is_file(), f"missing logo alias: {alias}")

    require(not (ROOT / "usr/bin/plasma-welcome").exists(),
            "upstream welcome application is still installed")

    require((ROOT / "usr/lib/systemd/user/moai.service").is_file(),
            "Mo AI user service is missing")
    sanitizer = ROOT / "usr/libexec/moos-fstab-sanitize"
    require(sanitizer.is_file() and sanitizer.stat().st_mode & 0o111,
            "bootc fstab sanitizer is missing or not executable")
    require((ROOT / "usr/lib/systemd/system/moos-fstab-sanitize.service").is_file(),
            "bootc fstab sanitizer service is missing")

    theme = json.loads((ROOT / "usr/share/plasma/look-and-feel/org.moos.nova/metadata.json")
                       .read_text(encoding="utf-8"))
    require(theme.get("KPlugin", {}).get("Id") == "org.moos.nova",
            "Nova look-and-feel metadata has the wrong id")

    print("IDENTITY OK: MoOS owns os-release, session, installer, apps, logos and Nova theme")


if __name__ == "__main__":
    main()
