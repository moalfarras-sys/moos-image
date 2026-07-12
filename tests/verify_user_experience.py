#!/usr/bin/env python3
"""Static gates for the active MoOS login/desktop experience."""

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


errors: list[str] = []


def require(condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


# One product, one launcher. Ignore development templates and documentation.
launchers = []
for path in (ROOT / "system_files/usr/share/applications").glob("*.desktop"):
    text = path.read_text(encoding="utf-8")
    if re.search(r"^Name=Mo Remote(?: Personal)?$", text, re.MULTILINE):
        launchers.append(path.name)
require(launchers == ["org.moos.remote.desktop"],
        f"Mo Remote must have exactly one launcher; found {launchers}")

# The server must only join a real Plasma workspace. default.target caused
# root, SDDM, and the desktop user to race for port 8765 on real hardware.
unit = read("system_files/usr/lib/systemd/user/mo-remote-personal.service")
require("ConditionUser=!@system" in unit, "Mo Remote must reject system users")
require("WantedBy=plasma-workspace.target" in unit,
        "Mo Remote must start with the Plasma workspace")
require("WantedBy=default.target" not in unit,
        "Mo Remote must not be globally attached to default.target")
require("WAYLAND_DISPLAY=wayland-0" not in unit,
        "Mo Remote must not guess the Wayland socket name")

capture = read("moremote/agent-linux/ScreenCapture.cs")
require("File.Exists(socket)" in capture,
        "KScreen probing must be guarded by Wayland socket readiness")
require("public ScreenCapture() { }" in capture,
        "KScreen must not run from the service constructor")

control = read("system_files/usr/bin/moai-control")
gateway = read("system_files/usr/bin/moai-gateway")
require('"cloud_key":' not in control,
        "Mo AI must not persist cloud_key in JSON")
require('c.get("cloud_key")' not in gateway,
        "Mo AI gateway must not read plaintext cloud_key from JSON")
require("secret-tool" in control and "secret-tool" in gateway,
        "Mo AI cloud credentials must use Secret Service")
require('had_legacy_key = "cloud_key" in data' in control and
        "elif had_legacy_key:" in control,
        "Mo AI must remove even an empty legacy cloud_key field")

# The versioned migration is what makes the redesign visible to existing users.
apply_theme = read("system_files/usr/bin/moos-apply-theme")
require("THEME_REV=7" in apply_theme, "Nova visual schema must be revision 7")

ui_migrate = read("system_files/usr/bin/moos-ui-migrate")
require("MOOS_THEME_REV=7" in ui_migrate and "MOAI_UI_REV=3" in ui_migrate,
        "UI cache and Mo AI migrations must be explicitly revisioned")
require('rm -rf "$HOME/.cache"' not in ui_migrate,
        "UI migration must never erase the whole user cache")
require("secret-tool" not in ui_migrate,
        "UI migration must never inspect or mutate Mo AI credentials")

# Windows must wear the Nova decoration, not Breeze. Breeze here means Breeze's
# X / v / ^ title-bar glyphs on every window — the loudest remaining "this is
# stock KDE" tell after the dock.
kwinrc = read("system_files/etc/xdg/kwinrc")
require("library=org.kde.kwin.aurorae" in kwinrc,
        "KWin must load the Aurorae engine, not Breeze")
require("theme=__aurorae__svg__MoOSNova" in kwinrc,
        "KWin must use the MoOS Nova decoration; the __aurorae__svg__ prefix is "
        "what routes the theme to the Aurorae SVG engine")

aurorae = ROOT / "system_files/usr/share/aurorae/themes/MoOSNova"
for name in ("decoration.svg", "close.svg", "minimize.svg", "maximize.svg",
             "restore.svg", "MoOSNovarc"):
    require((aurorae / name).is_file(),
            f"the Nova decoration must ship {name}")

# The shadow is the theme's own job — Aurorae paints the decoration SVG across
# its Padding* region, and a decoration with no padding has no drop shadow, which
# lands windows flat on the wallpaper and looks WORSE than the Breeze it
# replaced. Guard the padding so a future edit cannot quietly delete the shadow.
themerc = read("system_files/usr/share/aurorae/themes/MoOSNova/MoOSNovarc")
for pad in ("PaddingLeft", "PaddingRight", "PaddingTop", "PaddingBottom"):
    match = re.search(rf"^{pad}=(\d+)$", themerc, re.MULTILINE)
    require(match is not None and int(match.group(1)) > 0,
            f"{pad} must be > 0 or the window decoration ships with no shadow")

# Same fill-only invariant as the Plasma Style: a stroke inflates the FrameSvg
# element bbox and the stretch factor magnifies the overflow.
for svg in sorted(aurorae.glob("*.svg")):
    require("stroke" not in svg.read_text(encoding="utf-8"),
            f"{svg.name} must be fill-only (stroke inflates the FrameSvg bbox)")

# Nova must own the panel and the task buttons. Without these two FrameSvgs the
# Plasma Style falls back down the chain to breeze-dark for the dock background
# and the task indicator, and the desktop reads as stock KDE with a repaint --
# which is the exact complaint the Nova redesign exists to answer.
widgets = ROOT / "system_files/usr/share/plasma/desktoptheme/Nova/widgets"
for svg in ("panel-background.svg", "tasks.svg"):
    require((widgets / svg).is_file(),
            f"Nova Plasma Style must ship its own {svg}, not inherit Breeze's")

# 9-patch pieces must be fill-only. A stroke inflates the element's bounding box
# by half the stroke width, and FrameSvg multiplies that overflow by the stretch
# factor -- on a 4K dock a 0.5px overhang became a 50px transparent band punched
# through the panel. Verified on hardware; keep the art strokeless.
for svg in ("panel-background.svg", "tasks.svg"):
    path = widgets / svg
    if path.is_file():
        require("stroke" not in path.read_text(encoding="utf-8"),
                f"{svg} must be fill-only; a stroke inflates the FrameSvg "
                f"element bbox and tears a gap in the stretched edge")

# Kickoff remains KDE's integrated plugin, but every presentation surface it
# asks Plasma Style for must be owned by Nova rather than falling back to Breeze.
kickoff_surfaces = {
    "dialogs/background.svg",
    "widgets/lineedit.svg",
    "widgets/plasmoidheading.svg",
    "widgets/viewitem.svg",
    "widgets/listitem.svg",
    "widgets/line.svg",
    "widgets/button.svg",
}
nova_theme = ROOT / "system_files/usr/share/plasma/desktoptheme/Nova"
for relative in kickoff_surfaces:
    path = nova_theme / relative
    require(path.is_file(), f"Nova Kickoff surface must exist: {relative}")
    if path.is_file():
        require("stroke" not in path.read_text(encoding="utf-8"),
                f"{relative} must remain fill-only for FrameSvg geometry")

# The dock has to actually leave the screen edge, or none of the rounded glass
# reads as floating.
layout = read("system_files/usr/share/plasma/layout-templates/"
              "org.kde.plasma.desktop.defaultPanel/contents/layout.js")
require("panel.floating = true" in layout, "the MoOS dock must float")
require('addWidget("org.kde.plasma.kickoff")' in layout,
        "MoOS must preserve the integrated Kickoff launcher")
require("org.moos.nova.launcher" not in layout,
        "MoOS must not ship a competing launcher in the panel")
require('addWidget("org.moos.nova.clock")' in layout,
        "new users must receive the compact Nova clock")
for package in ("org.moos.nova.clock",):
    root = ROOT / "system_files/usr/share/plasma/plasmoids" / package
    require((root / "metadata.json").is_file() and
            (root / "contents/ui/main.qml").is_file(),
            f"missing complete Plasma package: {package}")
require("try {" in layout,
        "the floating setter must be guarded -- a throw in the layout template "
        "leaves the session with NO panel")
require("NovaHorizonII/contents/images_dark/3840x2160.png" in apply_theme,
        "Existing users must migrate to Nova Horizon II")

lock_config = read("system_files/etc/xdg/kscreenlockerrc")
require("Image=/usr/share/wallpapers/NovaHorizonII" in lock_config,
        "Plasma lock screen must use Nova Horizon II")

sddm = read("system_files/etc/sddm.conf.d/moos.conf")
require(re.search(r"^Current=moos-nova$", sddm, re.MULTILINE) is not None,
        "SDDM must select the MoOS Nova theme")
sddm_preset = read("system_files/usr/share/sddm/themes/moos-nova/configs/moos-nova.conf")
require(sddm_preset.count('background = "nova-horizon-ii.png"') == 2,
        "SDDM idle and login screens must share Nova Horizon II")

wallpaper = ROOT / "system_files/usr/share/wallpapers/NovaHorizonII"
for relative in (
    "metadata.json", "contents/screenshot.png",
    "contents/images/3840x2160.png", "contents/images/3440x1440.png",
    "contents/images/2560x1600.png", "contents/images_dark/3840x2160.png",
    "contents/images_dark/3440x1440.png", "contents/images_dark/2560x1600.png",
):
    require((wallpaper / relative).is_file(), f"missing wallpaper asset: {relative}")

# These are the active selectors; comments and package metadata are deliberately
# outside this gate. The EFI shim directory name is also intentionally excluded.
active_selectors = {
    "SDDM": sddm,
    "lock screen": lock_config,
    "look and feel": read("system_files/usr/share/plasma/look-and-feel/org.moos.nova/contents/defaults"),
}
for surface, text in active_selectors.items():
    require(re.search(r"fedora|bgrt|spinner", text, re.IGNORECASE) is None,
            f"foreign branding selector is active in {surface}")

build = read("build_files/build.sh")
require("plymouth-set-default-theme moos-nova" in build,
        "image build must select MoOS Plymouth")
require("grep -qx 'Theme=moos-nova' /etc/plymouth/plymouthd.conf" in build,
        "image build must fail if the active Plymouth selector is not MoOS")
require("final initramfs contains the Fedora BGRT/spinner branding path" in build,
        "image build must reject Fedora BGRT/spinner paths in initramfs")

if errors:
    print("MoOS user-experience gate failed:", file=sys.stderr)
    for error in errors:
        print(f" - {error}", file=sys.stderr)
    raise SystemExit(1)

print("MoOS user-experience gate passed")
