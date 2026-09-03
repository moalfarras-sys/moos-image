#!/usr/bin/env python3
"""Prevent the identity repair tool from rewriting Atomic boot configuration."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
tool = (ROOT / "system_files/usr/bin/moos-fix-boot-branding").read_text()
build = (ROOT / "build_files/build.sh").read_text()
arm_build = (ROOT / "build_files/build-arm.sh").read_text()
firmware_rewrite = (ROOT / "build_files/rewrite_firmware_label.py").read_text()
defaults = (ROOT / "system_files/etc/default/grub").read_text()
theme_dir = ROOT / "system_files/usr/share/moos/grub-theme"
executable = "\n".join(
    line for line in tool.splitlines() if not line.lstrip().startswith("#")
)

assert not any(
    line.lstrip().startswith("grub2-mkconfig") for line in executable.splitlines()
), "the installed bootupd config must never be regenerated"
assert "menu configuration owner: bootupd" in tool
assert '[ "$(id -u)" = 0 ]' in tool, "mutating mode must require root explicitly"
assert "replacement entry could not be verified; old entry retained" in tool
assert 'plymouth-set-default-theme -R moos' in tool
assert 'GRUB_THEME=' not in defaults and 'GRUB_TIMEOUT=' not in defaults
assert not theme_dir.exists(), "a retired, unreachable GRUB theme must not ship as fake polish"
for image_build in (build, arm_build):
    assert "python3 /ctx/rewrite_firmware_label.py" in image_build
assert 'rglob("BOOT*.CSV")' in firmware_rewrite
assert '"usr/lib/efi"' in firmware_rewrite
assert 're.sub(re.escape(LEGACY_LABEL), "MoOS", text, flags=re.IGNORECASE)' in firmware_rewrite
assert "foreign firmware label survived" in firmware_rewrite

with tempfile.TemporaryDirectory(prefix="moos-firmware-label-") as temporary:
    root = Path(temporary)
    csv = root / "usr/lib/efi/vendor/BOOTAA64.CSV"
    csv.parent.mkdir(parents=True)
    legacy = "".join(map(chr, (70, 101, 100, 111, 114, 97)))
    csv.write_bytes(f"shim.efi,{legacy},,\n".encode("utf-16"))
    subprocess.run(
        ["python3", str(ROOT / "build_files/rewrite_firmware_label.py"), "--root", str(root)],
        check=True,
    )
    decoded = csv.read_bytes().decode("utf-16")
    assert "MoOS" in decoded and legacy.casefold() not in decoded.casefold()

print("OK: boot identity repair is honest, fail-safe and never rewrites bootupd GRUB")
