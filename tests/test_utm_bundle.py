#!/usr/bin/env python3
"""Gate the UTM bundle generator.

The ARM image provisions its user exclusively through cloud-init NoCloud —
that is the release contract tests/boot_arm_qcow2.sh proves. A UTM bundle
without a seed drive boots to a login screen with no account on it, so the
bundle MUST carry one. And the seed's password is generated per bundle
(secrets.token_urlsafe), never a fixed string committed to this repository.
This gate fails the build if either rule regresses.
"""

import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
GENERATOR = ROOT / "artwork/generate_utm_bundle.py"

script = GENERATOR.read_text(encoding="utf-8")

# ── static contract ───────────────────────────────────────────────────────────
assert "secrets.token_urlsafe" in script, \
    "the seed password must be generated per bundle with the secrets module"
assert not re.search(r"passwd:\s*[\"']?[A-Za-z0-9]{6,}", script), \
    "a literal password must never appear in the generator"
assert re.search(r'type: text', script), \
    "cloud-init needs type:text for an unhashed chpasswd value"
assert "expire: true" in script, \
    "the generated password must be expired at first login"
assert '"ImageName": "seed.iso"' in script, \
    "the UTM config must attach the NoCloud seed as a second drive"
assert '"ImageName": "moos-arm.qcow2"' in script, \
    "the UTM config must attach the release qcow2"
assert '"Architecture": "aarch64"' in script
assert '"ConfigurationVersion": 4' in script
assert "actions/runs/" not in script and "actions?query" not in script, \
    "per-run URLs rot within days; point at the workflow page instead"

# ── behavioural contract: run it ─────────────────────────────────────────────
with tempfile.TemporaryDirectory(prefix="moos-utm-gate-") as tmp:
    out = pathlib.Path(tmp) / "bundle"
    result = subprocess.run(
        [sys.executable, str(GENERATOR), "--output", str(out)],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 2, (
        "a bundle without a qcow2 must exit 2 (incomplete), not succeed"
    )
    config = (out / "config.plist").read_bytes()
    assert b"seed.iso" in config and b"moos-arm.qcow2" in config
    readme = (out / "README-FIRST.txt").read_text(encoding="utf-8")
    assert "one-time password is" in readme
    assert "actions/workflows/build-arm.yml" in readme, \
        "the README must point at the workflow, not one expiring run"
    # Two runs must NOT share a password.
    second = subprocess.run(
        [sys.executable, str(GENERATOR), "--output", str(out) + "2"],
        capture_output=True, text=True, timeout=60,
    )
    assert second.returncode == 2
    readme2 = (pathlib.Path(str(out) + "2") / "README-FIRST.txt").read_text(encoding="utf-8")
    passwords = []
    for text in (readme, readme2):
        match = re.search(r"one-time password is:\s*\n\s+(\S+)", text)
        assert match, "the README must print the generated password exactly once"
        passwords.append(match.group(1))
    assert passwords[0] != passwords[1], \
        "every generated bundle must get its own password"

print("UTM bundle generator gate passed")
