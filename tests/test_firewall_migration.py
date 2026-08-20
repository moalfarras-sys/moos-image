#!/usr/bin/env python3
"""Behaviour fixtures for the narrow, owner-preserving firewall migration."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "system_files/usr/libexec/moos-firewall-migrate"
ZONE = ROOT / "system_files/usr/lib/firewalld/zones/moos-desktop.xml"
TRUSTED = ROOT / "system_files/etc/firewalld/zones/trusted.xml"


def run_case(*, current: str, vendor: str, custom: bool = False) -> list[str]:
    with tempfile.TemporaryDirectory(prefix="moos-firewall-test-") as raw:
        base = Path(raw)
        vendor_dir = base / "vendor"
        custom_dir = base / "custom"
        vendor_dir.mkdir()
        custom_dir.mkdir()
        (vendor_dir / f"{current}.xml").write_text(vendor, encoding="utf-8")
        if custom:
            (custom_dir / f"{current}.xml").write_text("<zone/>\n", encoding="utf-8")
        log = base / "calls"
        fake = base / "firewall-cmd"
        fake.write_text(
            "#!/usr/bin/env bash\n"
            f"printf '%s\\n' \"$*\" >> {log}\n"
            f"if [ \"$1\" = --get-default-zone ]; then printf '%s\\n' {current!r}; fi\n"
            "exit 0\n",
            encoding="utf-8",
        )
        fake.chmod(0o755)
        env = os.environ | {
            "MOOS_FIREWALL_CMD": str(fake),
            "MOOS_FIREWALL_VENDOR_DIR": str(vendor_dir),
            "MOOS_FIREWALL_ETC_DIR": str(custom_dir),
        }
        result = subprocess.run([SCRIPT], env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
        return log.read_text(encoding="utf-8").splitlines()


def main() -> int:
    broad = (
        '<zone>\n<port protocol="tcp" port="1025-65535"/>\n'
        '<port protocol="udp" port="1025-65535"/>\n</zone>\n'
    )
    calls = run_case(current="vendor-desktop", vendor=broad)
    assert "--set-default-zone=moos-desktop" in calls
    calls = run_case(current="vendor-desktop", vendor=broad, custom=True)
    assert "--set-default-zone=moos-desktop" not in calls
    calls = run_case(current="public", vendor='<zone><service name="ssh"/></zone>\n')
    assert "--set-default-zone=moos-desktop" not in calls
    calls = run_case(current="moos-desktop", vendor="<zone/>\n")
    assert "--set-default-zone=moos-desktop" not in calls

    zone = ZONE.read_text(encoding="utf-8")
    assert "1025-65535" not in zone
    assert '<service name="kdeconnect"/>' in zone
    assert '<service name="mdns"/>' in zone
    assert '<interface name="tailscale0"/>' in TRUSTED.read_text(encoding="utf-8")
    print("OK: inherited all-high-port policy narrows to MoOS; custom zones stay untouched; tailnet stays trusted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
