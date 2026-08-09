#!/usr/bin/python3
"""Fail the image build when a user-facing MoOS identity surface regresses."""

from __future__ import annotations

import configparser
import hashlib
import json
import re
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
        "VARIANT": "MoOS",
        "VARIANT_ID": "moos",
        "LOGO": "moos-logo",
    }
    for key, value in expected.items():
        require(os_release.get(key) == value, f"os-release {key} must be {value!r}")
    # PRETTY_NAME is exactly "MoOS" — no codename after it. It used to be "MoOS 0.1 (Nova)", and
    # that parenthesised codename is what the Anaconda installer prints as its title: the first
    # sentence of a fresh install introduced a name the user had never heard. One name now.
    require(os_release.get("PRETTY_NAME", "") == "MoOS",
            "PRETTY_NAME must be exactly 'MoOS' — no codename, no version suffix")
    # And the inherited codename must be gone from VERSION too — same reason, same screen.
    require("(" not in os_release.get("VERSION", ""),
            "os-release VERSION must not carry a parenthesised codename (the installer prints it)")
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
    # The contract is "the first screen of a new machine carries MoOS identity",
    # not one hardcoded basename. Pinning a single name blocked moving to
    # moos-installer — MoOS-owned exactly like the mark, but shipped 16→1024 px
    # plus SVG and already used by org.moos.installer.desktop, so the live-USB
    # launcher and the installed app finally agree. Both halves below are
    # STRICTER than the string they replace: an upstream/Fedora icon still
    # fails, AND the name must now actually resolve to a file in this image —
    # a typo used to pass and leave the live launcher on a generic placeholder,
    # which is precisely the identity leak this gate exists to catch.
    installer_icon = installer.get("Icon", "")
    require(installer_icon.startswith("moos-"),
            f"installer icon {installer_icon!r} is not a MoOS-owned icon name")
    icon_files = [
        path
        for root, pattern in (
            ("usr/share/icons", f"**/{installer_icon}.png"),
            ("usr/share/icons", f"**/{installer_icon}.svg"),
            ("usr/share/pixmaps", f"{installer_icon}.*"),
        )
        for path in (ROOT / root).glob(pattern)
    ]
    require(bool(icon_files),
            f"installer icon {installer_icon!r} resolves to no file in this image")

    # "hardware" and "compathub" are gone on purpose: the Hardware Centre and the
    # Compatibility Hub are panels inside Mo AI now, reached by `moai --panel …`.
    # They have no launchers of their own to check. "store" is Mo Store — the
    # standalone storefront the Welcome hands over to.
    for app in ("moai", "welcome", "store", "updater", "recovery", "remote", "moplayer"):
        entry = desktop(f"/usr/share/applications/org.moos.{app}.desktop")
        require(entry.get("Icon", "").startswith("moos-")
                or entry.get("Icon", "").startswith("mo-remote"),
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
    # The two wordmark aliases have no same-directory MoOS twin to compare against,
    # and build.sh deliberately never rewrites them — so an existence check would
    # stay green if a package (fedora-logos, generic-logos) overwrote them with the
    # genuine upstream wordmark. Pin the exact MoOS art shipped from system_files;
    # regenerating that art means updating these digests in the same commit.
    wordmarks = {
        "/usr/share/pixmaps/fedora_logo_med.png":
            "3cd3e6ed5f79a4caedb9211b893d3b37f69f2793381755ec2ea8184479ec0e13",
        "/usr/share/pixmaps/system-logo-white.png":
            "14f6de4dace33dabe13785a38f35b28367c5fbee232dc7529c0fef82cefe841b",
    }
    for alias, expected_digest in wordmarks.items():
        require(digest(ROOT / alias.lstrip("/")) == expected_digest,
                f"legacy wordmark alias no longer carries the MoOS art: {alias}")

    # plasma-welcome must never draw its Fedora-branded window, and must never
    # raise a red "Launching plasma-welcome (Failed)" toast. DELETING the binary
    # and desktop entry does the SECOND wrong (proven live on the installed 179
    # ISO, 2026-07-16): KDE still resolves the launch by desktop-id and fails
    # loudly when the target is gone. The contract is now SILENT NO-OP on every
    # path — the binary exits 0 and draws nothing, the desktop entry is a hidden
    # /bin/true — so the launch always succeeds and shows nothing. MoOS's own
    # Welcome is what actually greets the user (moos-firstrun).
    pw_bin = ROOT / "usr/bin/plasma-welcome"
    require(pw_bin.is_file(), "the plasma-welcome no-op stub is missing — a bare "
            "launch of it would raise a failed-launch toast on first boot")
    if pw_bin.is_file():
        body = pw_bin.read_text(encoding="utf-8", errors="replace")
        require(body.startswith("#!") and "exit 0" in body and len(body) < 1024,
                "usr/bin/plasma-welcome is not the MoOS no-op stub — it must exit "
                "0 and draw nothing, not run the upstream Fedora-branded welcome")
    pw_desktop = ROOT / "usr/share/applications/org.kde.plasma-welcome.desktop"
    require(pw_desktop.is_file(), "the plasma-welcome desktop stub is missing — "
            "the service-id launch would fail loudly without it")
    if pw_desktop.is_file():
        entry = pw_desktop.read_text(encoding="utf-8", errors="replace")
        require("NoDisplay=true" in entry and "Exec=/bin/true" in entry,
                "the plasma-welcome desktop entry is not the hidden no-op stub — "
                "it must be NoDisplay with Exec=/bin/true so the launch is silent")

    # Mo AI's system prompt is fed to the model verbatim, so any base-distro name
    # in it can be repeated to the user in conversation — the one runtime path a
    # filename scrub cannot close. Comments are stripped first: a comment naming
    # what was removed must not keep this gate red (or, worse, be all it checks).
    for qml in (ROOT / "usr/share/moos/apps").rglob("*.qml"):
        source = re.sub(r"/\*.*?\*/", "", qml.read_text(encoding="utf-8"), flags=re.DOTALL)
        source = re.sub(r"(?m)//.*$", "", source)
        require("fedora" not in source.lower(),
                f"a MoOS app feeds the base distro's name to the user at runtime: {qml}")

    require((ROOT / "usr/lib/systemd/user/moai.service").is_file(),
            "Mo AI user service is missing")
    sanitizer = ROOT / "usr/libexec/moos-fstab-sanitize"
    require(sanitizer.is_file() and sanitizer.stat().st_mode & 0o111,
            "bootc fstab sanitizer is missing or not executable")
    require((ROOT / "usr/lib/systemd/system/moos-fstab-sanitize.service").is_file(),
            "bootc fstab sanitizer service is missing")

    # Hardware adaptation — MoOS plants itself into the machine. The service and
    # its script must ship together (a service with no script is a boot-time
    # failure), and the script must keep its anti-brick contract: it must NEVER
    # flash firmware, raise thermal limits, or install GPU drivers at runtime.
    hw = ROOT / "usr/libexec/moos-hardware-adapt"
    require(hw.is_file() and hw.stat().st_mode & 0o111,
            "moos-hardware-adapt is missing or not executable")
    require((ROOT / "usr/lib/systemd/system/moos-hardware-adapt.service").is_file(),
            "moos-hardware-adapt.service is missing")
    hw_text = hw.read_text(encoding="utf-8")
    # The dangerous operations must not appear as ACTIONS. `fwupdmgr update -y`
    # would auto-apply firmware (brick risk); the service may only refresh
    # metadata (fwupd-refresh.timer). Guard the exact unsafe invocation.
    require("fwupdmgr update" not in hw_text,
            "moos-hardware-adapt must NEVER auto-apply firmware (fwupdmgr update) — brick risk")
    require("ryzenadj" not in hw_text and "--overclock" not in hw_text,
            "moos-hardware-adapt must NEVER overclock/undervolt on generic hardware")
    # It must be idempotent (state-gated) so a rebase re-adapts and an ordinary
    # boot no-ops — the fstab-sanitize discipline.
    require("hardware-adapt.state" in hw_text or "MOOS_HW_STATE" in hw_text,
            "moos-hardware-adapt must be idempotent via a versioned state file")

    # The MoOS theme FAMILY. One design engine (UI2), several MoOS-branded looks the user picks
    # between — Graphite (dark) and Tidal (light) are the base pair; Nova/Amethyst/Midnight/Aurora
    # are recoloured members of the same engine (see artwork/generate_moos_themes.py). The OLD
    # top-level generations (org.moos.nova, org.moos.ui) are a DIFFERENT thing: they shipped three
    # separate engines at once and are still forbidden — they are not in this allow-set and are
    # gated for absence in verify_image_experience.py. This gate keeps the picker all-MoOS: it
    # must contain EXACTLY the known family, every member id-correct and named "MoOS …", so a
    # foreign look or a reintroduced old generation fails the build rather than reaching the user.
    # Every family is a matched light+dark PAIR; the light sibling's id is the
    # dark id + ".light" and its name is "… Light" (midnight's light is "Daylight").
    # The visual system is unified under ONE name: "MoOS UI". The base pair is
    # "MoOS UI" / "MoOS UI Light"; every family member is "MoOS UI · <Colour>"
    # (midnight's light keeps its own colour name, Daylight). Still MoOS-branded,
    # never a bare codename — the check below also requires the "MoOS" prefix.
    ALLOWED_LOOKS = {
        "org.moos.ui2": "MoOS UI",
        "org.moos.ui2.light": "MoOS UI Light",
        "org.moos.ui2.nova": "MoOS UI · Nova",
        "org.moos.ui2.nova.light": "MoOS UI · Nova Light",
        "org.moos.ui2.amethyst": "MoOS UI · Amethyst",
        "org.moos.ui2.amethyst.light": "MoOS UI · Amethyst Light",
        "org.moos.ui2.midnight": "MoOS UI · Midnight",
        "org.moos.ui2.midnight.light": "MoOS UI · Daylight",
        "org.moos.ui2.aurora": "MoOS UI · Aurora",
        "org.moos.ui2.aurora.light": "MoOS UI · Aurora Light",
        # Purpose-built editions, each a light+dark pair.
        "org.moos.ui2.gaming": "MoOS UI · Arena",
        "org.moos.ui2.gaming.light": "MoOS UI · Arena Light",
        "org.moos.ui2.dev": "MoOS UI · Forge",
        "org.moos.ui2.dev.light": "MoOS UI · Forge Light",
        "org.moos.ui2.study": "MoOS UI · Scholar",
        "org.moos.ui2.study.light": "MoOS UI · Scholar Light",
    }
    lnf_root = ROOT / "usr/share/plasma/look-and-feel"
    moos_looks = sorted(p.name for p in lnf_root.glob("org.moos.*"))
    require(set(moos_looks) == set(ALLOWED_LOOKS),
            f"the picker must show exactly the MoOS theme family {sorted(ALLOWED_LOOKS)}; "
            f"found {moos_looks}")
    for look, expected_name in ALLOWED_LOOKS.items():
        meta = json.loads((lnf_root / look / "metadata.json").read_text(encoding="utf-8"))
        require(meta.get("KPlugin", {}).get("Id") == look,
                f"{look} look-and-feel metadata has the wrong id")
        name = meta.get("KPlugin", {}).get("Name", "")
        require(name == expected_name and name.startswith("MoOS"),
                f"{look} must be named {expected_name!r} (MoOS-branded), not a codename")

    print("IDENTITY OK: MoOS owns os-release, session, installer, apps, logos and its theme family")


if __name__ == "__main__":
    main()
