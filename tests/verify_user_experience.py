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

# The v4 migration is what makes the redesign visible to existing users.
apply_theme = read("system_files/usr/bin/moos-apply-theme")
require("THEME_REV=4" in apply_theme, "Nova visual schema must be revision 4")
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
