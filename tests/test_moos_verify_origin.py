#!/usr/bin/env python3
"""Execute the signed-origin repair against real rpm-ostree-shaped fixtures."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "system_files/usr/libexec/moos-verify-origin"
CHECKSUM = "a" * 64


def write_executable(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)


def run_case(origin_ref: str, *, valid_status: bool = True) -> tuple[subprocess.CompletedProcess[str], str]:
    with tempfile.TemporaryDirectory(prefix="moos-origin-test-") as temporary:
        root = Path(temporary)
        bindir = root / "bin"
        deploy_root = root / "ostree/deploy"
        origin = deploy_root / "default/deploy" / f"{CHECKSUM}.0.origin"
        bindir.mkdir(parents=True)
        origin.parent.mkdir(parents=True)
        origin.write_text(f"[origin]\ncontainer-image-reference={origin_ref}\n", encoding="utf-8")
        status = {
            "deployments": ([{
                "booted": True,
                "osname": "default",
                "checksum": CHECKSUM,
                "serial": 0,
                "container-image-reference": origin_ref,
            }] if valid_status else [])
        }
        write_executable(
            bindir / "rpm-ostree",
            "#!/usr/bin/env bash\nprintf '%s\\n' '" + json.dumps(status) + "'\n",
        )
        calls = root / "bootc.calls"
        write_executable(
            bindir / "bootc",
            "#!/usr/bin/env bash\nprintf '%s\\n' \"$*\" >> \"$MOOS_TEST_CALLS\"\n",
        )
        env = os.environ.copy()
        env.update({
            "PATH": f"{bindir}:{env.get('PATH', '')}",
            "MOOS_ORIGIN_DEPLOY_ROOT": str(deploy_root),
            "MOOS_ORIGIN_RPM_OSTREE": str(bindir / "rpm-ostree"),
            "MOOS_ORIGIN_BOOTC": str(bindir / "bootc"),
            "MOOS_ORIGIN_RETRY_DELAY": "0",
            "MOOS_TEST_CALLS": str(calls),
        })
        result = subprocess.run([str(SCRIPT)], env=env, capture_output=True, text=True)
        return result, calls.read_text(encoding="utf-8") if calls.exists() else ""


def main() -> int:
    signed, signed_calls = run_case(
        "ostree-image-signed:docker://ghcr.io/moalfarras-sys/moos@sha256:" + "b" * 64
    )
    assert signed.returncode == 0, signed.stdout + signed.stderr
    assert not signed_calls, "an already-signed origin must never stage a deployment"

    image = "ghcr.io/moalfarras-sys/moos-arm@sha256:" + "c" * 64
    repaired, repair_calls = run_case("ostree-unverified-registry:" + image)
    assert repaired.returncode == 0, repaired.stdout + repaired.stderr
    assert repair_calls.strip() == f"switch --enforce-container-sigpolicy {image}", repair_calls

    custom, custom_calls = run_case("ostree-unverified-registry:example.invalid/custom:latest")
    assert custom.returncode == 0, custom.stdout + custom.stderr
    assert not custom_calls, "a custom origin must be reported but never rebound to the MoOS key"

    malformed, malformed_calls = run_case(
        "ostree-unverified-registry:" + image, valid_status=False
    )
    assert malformed.returncode != 0, "missing booted deployment data must fail closed"
    assert not malformed_calls

    print("OK: signed-origin audit reads the real rpm-ostree deployment, repairs only MoOS, and fails closed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
