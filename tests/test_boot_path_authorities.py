#!/usr/bin/env python3
"""Boot-path gates for on-demand NFS and non-duplicated Flatpak updates."""

import json
import os
import shutil
from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "system_files/usr/lib/systemd/system-generators/moos-nfs-client-generator"
DRACUT_ACCOUNTS = ROOT / "system_files/usr/lib/dracut/modules.d/91moos-accounts/module-setup.sh"
BUILD = (ROOT / "build_files/build.sh").read_text(encoding="utf-8")

assert GENERATOR.is_file() and os.access(GENERATOR, os.X_OK)
assert "systemctl disable nfs-client.target" in BUILD
assert DRACUT_ACCOUNTS.is_file() and os.access(DRACUT_ACCOUNTS, os.X_OK)
accounts = DRACUT_ACCOUNTS.read_text(encoding="utf-8")
assert 'vendor="${dracutsysrootdir-}/usr/lib/${name}"' in accounts
assert "awk -F: '!seen[$1]++'" in accounts
assert "moos-accounts" in BUILD
for group in ("audio", "video", "render", "disk", "kvm", "input", "tss", "utmp"):
    assert group in BUILD, f"the final initramfs gate does not require {group}"


def prove_account_merge() -> None:
    with tempfile.TemporaryDirectory(prefix="moos-dracut-accounts-") as tmp:
        root = Path(tmp)
        vendor = root / "source/usr/lib"
        initrd = root / "initrd/etc"
        vendor.mkdir(parents=True)
        initrd.mkdir(parents=True)
        (vendor / "passwd").write_text(
            "audio:x:63:63:Audio:/var/empty:/usr/sbin/nologin\n", encoding="utf-8"
        )
        (vendor / "group").write_text(
            "audio:x:63:pipewire\nrender:x:105:\n", encoding="utf-8"
        )
        (initrd / "passwd").write_text(
            "root:x:0:0:root:/root:/bin/sh\naudio:x:999:999:wrong:/nonexistent:/bin/false\n",
            encoding="utf-8",
        )
        (initrd / "group").write_text(
            "root:x:0:\naudio:x:999:\n", encoding="utf-8"
        )
        script = '. "$1"; install'
        subprocess.run(
            ["bash", "-eu", "-c", script, "bash", str(DRACUT_ACCOUNTS)],
            env=os.environ
            | {
                "dracutsysrootdir": str(root / "source"),
                "initdir": str(root / "initrd"),
            },
            check=True,
        )
        groups = (initrd / "group").read_text(encoding="utf-8").splitlines()
        passwd = (initrd / "passwd").read_text(encoding="utf-8").splitlines()
        assert "audio:x:63:pipewire" in groups
        assert "render:x:105:" in groups
        assert "root:x:0:" in groups
        assert sum(line.startswith("audio:") for line in groups) == 1
        assert "audio:x:63:63:Audio:/var/empty:/usr/sbin/nologin" in passwd
        assert "root:x:0:0:root:/root:/bin/sh" in passwd


prove_account_merge()


def generated_for(fstab_text: str) -> Path | None:
    with tempfile.TemporaryDirectory(prefix="moos-nfs-generator-") as tmp:
        root = Path(tmp)
        fstab = root / "fstab"
        output = root / "generator"
        target = root / "nfs-client.target"
        fstab.write_text(fstab_text, encoding="utf-8")
        output.mkdir()
        target.write_text("[Unit]\n", encoding="utf-8")
        env = os.environ | {
            "MOOS_FSTAB": str(fstab),
            "MOOS_NFS_CLIENT_TARGET": str(target),
        }
        subprocess.run([str(GENERATOR), str(output)], env=env, check=True)
        link = output / "remote-fs.target.wants/nfs-client.target"
        return Path(os.readlink(link)) if link.is_symlink() else None


assert generated_for("UUID=abc / ext4 defaults 0 1\n") is None
assert generated_for("server:/data /srv/data nfs4 nofail,_netdev 0 0\n") is not None
assert generated_for("# server:/old /old nfs defaults 0 0\n") is None
assert generated_for("//server/share /srv/share cifs nofail,_netdev 0 0\n") is None

uupd = json.loads((ROOT / "system_files/etc/uupd/config.json").read_text(encoding="utf-8"))
assert uupd["modules"]["flatpak"]["disable"] is True
assert uupd["modules"]["distrobox"]["disable"] is False

# The visual tier must actually be applied on every boot, not just shipped as a
# manual tool. A present-but-never-invoked moos-visual-tier leaves a software-
# rendered box or a small laptop paying for a full GPU blur pass it cannot afford.
VISUAL_TIER_SERVICE = ROOT / "system_files/usr/lib/systemd/system/moos-visual-tier.service"
assert VISUAL_TIER_SERVICE.is_file() and os.access(VISUAL_TIER_SERVICE, os.R_OK)
_vts = VISUAL_TIER_SERVICE.read_text(encoding="utf-8")
assert "moos-visual-tier --apply" in _vts, "the service must apply the tier, not just probe"
assert "After=graphical.target" in _vts, "the tier must apply post-desktop, never on the critical path"
BUILD_ASSERTS_VISUAL_TIER = (
    "systemctl enable moos-visual-tier.service" in BUILD
)
assert BUILD_ASSERTS_VISUAL_TIER, "build.sh must enable moos-visual-tier.service"
# The build must not enable it ON the critical path (a Wants=graphical.target
# without After= is the same trap as the legacy hardware-adapt direct enable).
assert "systemctl enable moos-visual-tier.timer" not in BUILD

# The lock screen must share the desktop's motion language: every tier now
# writes kscreenlockerrc (KDE/AnimationDurationFactor) so unlocking feels like a
# continuation of the session, not a second OS. Prove the script actually owns
# that key — a regression that drops it would silently split the motion system.
VISUAL_TIER_SCRIPT = ROOT / "system_files/usr/bin/moos-visual-tier"
assert VISUAL_TIER_SCRIPT.is_file() and os.access(VISUAL_TIER_SCRIPT, os.X_OK)
_vt_script = VISUAL_TIER_SCRIPT.read_text(encoding="utf-8")
assert "\"kscreenlockerrc\"" in _vt_script, (
    "moos-visual-tier must write kscreenlockerrc so the lock screen shares the "
    "desktop's AnimationDurationFactor per tier"
)
assert "for filename in (\"kwinrc\", \"kdeglobals\", \"kscreenlockerrc\")" in _vt_script, (
    "moos-visual-tier's apply loop must include kscreenlockerrc alongside "
    "kwinrc and kdeglobals"
)

# A present service file + an `enable` line in build.sh is NOT enough: if the
# unit has no [Install] section, `systemctl enable` wires nothing and the tier
# never runs at boot (this is exactly what shipped broken in 4bf615a6). Prove the
# enable actually creates the wants symlink by enabling the unit against a throw-
# away root, the same way systemd does on a real install.
def prove_visual_tier_is_actually_enabled() -> None:
    with tempfile.TemporaryDirectory(prefix="moos-vt-enable-") as tmp:
        usr = Path(tmp) / "usr/lib/systemd/system"
        etc = Path(tmp) / "etc/systemd/system"
        usr.mkdir(parents=True)
        etc.mkdir(parents=True)
        shutil.copy(VISUAL_TIER_SERVICE, usr / "moos-visual-tier.service")
        r = subprocess.run(
            ["systemctl", "enable", f"--root={tmp}", "moos-visual-tier.service"],
            capture_output=True,
            text=True,
        )
        assert r.returncode == 0, f"systemctl enable failed: {r.stderr}"
        link = etc / "graphical.target.wants" / "moos-visual-tier.service"
        assert link.is_symlink(), (
            "moos-visual-tier.service was not enabled into graphical.target.wants; "
            "it will never run at boot"
        )

prove_visual_tier_is_actually_enabled()

print("Boot-path authorities gate passed")
