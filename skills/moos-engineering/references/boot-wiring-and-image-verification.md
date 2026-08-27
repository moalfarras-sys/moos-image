# Boot wiring & image verification — concrete recipes (MoOS)

Session-proven commands for the traps documented in the parent SKILL.md. Reproduce,
don't re-derive.

## 1. Prove a `systemctl enable` actually wires (not just a string in build.sh)

The unit file MUST carry `[Install]` or `systemctl enable` is a silent no-op:

```ini
[Install]
WantedBy=graphical.target
```

Gate (in the repo test, e.g. `tests/test_boot_path_authorities.py`): enable the unit
against a throw-away root and assert the symlink appears — a unit without `[Install]`
returns rc=0 from `systemctl enable` but creates NO symlink, so the assert bites:

```python
import subprocess, tempfile, shutil, os
from pathlib import Path
tmp = tempfile.mkdtemp()
usr = Path(tmp) / "usr/lib/systemd/system"
etc = Path(tmp) / "etc/systemd/system"
usr.mkdir(parents=True); etc.mkdir(parents=True)
shutil.copy(VISUAL_TIER_SERVICE, usr / "moos-visual-tier.service")
r = subprocess.run(["systemctl", "enable", f"--root={tmp}", "moos-visual-tier.service"],
                   capture_output=True, text=True)
assert r.returncode == 0
link = etc / "graphical.target.wants" / "moos-visual-tier.service"
assert link.is_symlink(), "no wants symlink => unit stays static, never runs at boot"
```

Bite-test: delete the `[Install]` section from a temp copy; `systemctl enable` still
returns 0 and `link.is_symlink()` is False => the assert correctly fails.

## 2. Inspect the built image's actual bytes (green build != landed fix)

```bash
podman run --rm --entrypoint bash localhost/moos-nvidia:latest -c '
set -e
grep -A1 "\[Install\]" /usr/lib/systemd/system/moos-visual-tier.service
tmp=$(mktemp -d); mkdir -p $tmp/usr/lib/systemd/system $tmp/etc/systemd/system
cp /usr/lib/systemd/system/moos-visual-tier.service $tmp/usr/lib/systemd/system/
systemctl enable --root=$tmp moos-visual-tier.service >/dev/null 2>&1
[ -L $tmp/etc/systemd/system/graphical.target.wants/moos-visual-tier.service ] \
  && echo PASS: wants symlink created || echo FAIL
[ -e /usr/bin/moos-store-browse ] && echo FAIL: shim present || echo PASS: shim absent
'
```

Always check `IDENTITY FIREWALL OK` and `bootc container lint` in the build log too.

## 3. Fake-root limitation for `moos-visual-tier`

`MOOS_TIER_ROOT` / `MOOS_TIER_CONFIG_HOME` / `MOOS_TIER_STATE_HOME` are honored by the
script's own read functions, but `apply()` writes via `kwriteconfig6 --file <name>`,
which always targets the real `/etc/xdg`. So a fake-root `--apply` validates kwinrc/
kdeglobals reads but CANNOT prove `kscreenlockerrc` was written. Validate kscreenlockerrc
against the built image (section 2) or via the source gate asserting the key is in PROFILES
and the apply loop covers `"kwinrc", "kdeglobals", "kscreenlockerrc"`.

## 4. Deploy a locally-built image

```bash
bootc switch localhost/moos-nvidia:latest   # stages new deployment; old one stays for rollback
# reboot from the MoOS power UI, then verify:
systemctl is-enabled moos-visual-tier.service
journalctl -u moos-visual-tier.service --no-pager | tail
rpm-ostree rollback                         # if the new deployment is broken
```

`bootc upgrade` pulls from the registry; `bootc switch` targets a local/any reference.
