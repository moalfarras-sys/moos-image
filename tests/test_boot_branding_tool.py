#!/usr/bin/env python3
"""Prevent the identity repair tool from rewriting Atomic boot configuration."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
tool = (ROOT / "system_files/usr/bin/moos-fix-boot-branding").read_text()
build = (ROOT / "build_files/build.sh").read_text()
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
assert 'rglob("BOOT*.CSV")' in build
assert 'Path("/usr/lib/efi")' in build
assert 're.sub(re.escape(legacy), "MoOS", text, flags=re.IGNORECASE)' in build
assert "foreign firmware label survived" in build

print("OK: boot identity repair is honest, fail-safe and never rewrites bootupd GRUB")
