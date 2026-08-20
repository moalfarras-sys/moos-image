#!/usr/bin/env python3
"""Finished-image gates specific to the MoOS ARM cloud/UTM edition."""

from __future__ import annotations

import configparser
import json
import os
import platform
import subprocess
from pathlib import Path

import yaml


ROOT = Path("/")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"ARM IMAGE FATAL: {message}")


def read(path: str) -> str:
    target = ROOT / path.lstrip("/")
    require(target.is_file(), f"missing required file: {target}")
    return target.read_text(encoding="utf-8", errors="replace")


def enabled(unit: str, targets: tuple[str, ...]) -> bool:
    return any(
        (ROOT / root / unit).exists() or (ROOT / root / unit).is_symlink()
        for root in targets
    )


def main() -> None:
    require(platform.machine() == "aarch64",
            f"finished image was built on {platform.machine()}, not aarch64")

    qml_shell = ROOT / "usr/bin/moos-qml-shell"
    require(qml_shell.is_file() and os.access(qml_shell, os.X_OK),
            "the native MoOS QML host is missing or not executable")

    session_path = ROOT / "usr/share/wayland-sessions/plasma.desktop"
    require(session_path.is_file(), "the Plasma Wayland session is missing")
    session = configparser.ConfigParser(interpolation=None, strict=False)
    session.optionxform = str
    session.read(session_path, encoding="utf-8")
    require(session.get("Desktop Entry", "Name", fallback="") == "MoOS",
            "the Wayland session is not branded MoOS")
    x11_sessions = list((ROOT / "usr/share/xsessions").glob("*.desktop"))
    require(not x11_sessions,
            f"X11 sessions reached the Wayland-only image: {x11_sessions}")

    for package in (
        "plasma-workspace",
        "plasma-login-manager",
        "kwin-libs",
        "plasma-breeze",
        "cloud-init",
        "cloud-utils-growpart",
        "krdp",
        "rpm-ostree",
        "skopeo",
    ):
        result = subprocess.run(
            ["rpm", "-q", package],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        require(result.returncode == 0, f"required aarch64 package is absent: {package}")

    # Fedora 44 folded plasma-workspace-wayland into plasma-workspace. The
    # binary is the proof the session can actually start on Wayland.
    require((ROOT / "usr/bin/startplasma-wayland").is_file(),
            "startplasma-wayland is missing — the ARM image cannot start Plasma")
    x11_pkg = subprocess.run(
        ["rpm", "-q", "plasma-workspace-x11"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    require(x11_pkg.returncode != 0,
            "plasma-workspace-x11 reached the Wayland-only ARM image")

    require((ROOT / "usr/lib/systemd/system/plasmalogin.service").is_file(),
            "Plasma Login Manager service is missing")
    display_manager = ROOT / "etc/systemd/system/display-manager.service"
    require(display_manager.is_symlink()
            and os.path.basename(os.readlink(display_manager)) == "plasmalogin.service",
            "display-manager.service does not select Plasma Login Manager")
    default_target = ROOT / "etc/systemd/system/default.target"
    require(default_target.is_symlink()
            and os.path.basename(os.readlink(default_target)) == "graphical.target",
            "the ARM image does not boot to graphical.target")

    service_targets = (
        "etc/systemd/system/multi-user.target.wants",
        "usr/lib/systemd/system/multi-user.target.wants",
    )
    for unit in ("NetworkManager.service", "sshd.service", "firewalld.service"):
        require(enabled(unit, service_targets), f"{unit} is not enabled")

    timer_targets = (
        "etc/systemd/system/timers.target.wants",
        "usr/lib/systemd/system/timers.target.wants",
    )
    update_backend = ROOT / "usr/libexec/moos-image-update"
    require(update_backend.is_file() and os.access(update_backend, os.X_OK),
            "the single signed image-update backend is missing or not executable")
    require(enabled("moos-auto-update.timer", timer_targets),
            "automatic signed day-2 image updates are not enabled")
    for rival in ("rpm-ostreed-automatic.timer", "bootc-fetch-apply-updates.timer"):
        require(not enabled(rival, timer_targets),
                f"duplicate OS deployment writer is enabled: {rival}")

    cloud_units = (
        "cloud-init-local.service",
        "cloud-init-network.service",
        "cloud-config.service",
        "cloud-final.service",
    )
    for unit in cloud_units:
        require((ROOT / "usr/lib/systemd/system" / unit).is_file(),
                f"cloud-init 26 unit is missing: {unit}")
    require(not (ROOT / "usr/lib/systemd/system/cloud-init.service").exists(),
            "the retired cloud-init.service unexpectedly returned")

    cloud_cfg = read("/etc/cloud/cloud.cfg.d/10-moos-arm.cfg")
    require("datasource_list: [ Oracle, ConfigDrive, NoCloud, None ]" in cloud_cfg,
            "Oracle is not the first pinned cloud-init datasource")
    require("name: moos" in cloud_cfg and "groups: [wheel]" in cloud_cfg,
            "cloud-init does not create the password-authenticated moos account")
    parsed_cloud_cfg = yaml.safe_load(cloud_cfg)
    grow_mode = parsed_cloud_cfg.get("growpart", {}).get("mode")
    require(type(grow_mode) is str and grow_mode == "off",
            "cloud-init growpart mode must be the string 'off', not YAML Boolean false")
    require(parsed_cloud_cfg.get("resize_rootfs") is False,
            "cloud-init resize_rootfs must be disabled for composefs /")
    grow_unit_path = ROOT / "usr/lib/systemd/system/bootc-generic-growpart.service"
    require(grow_unit_path.is_file(), "Fedora bootc's physical root grow service is missing")
    local_fs_targets = (
        "etc/systemd/system/local-fs.target.wants",
        "usr/lib/systemd/system/local-fs.target.wants",
    )
    require(enabled("bootc-generic-growpart.service", local_fs_targets),
            "the single bootc physical root grow authority is not enabled")
    for retired in (
        "usr/libexec/moos-cloud-grow-root",
        "usr/lib/systemd/system/moos-cloud-grow-root.service",
        "usr/lib/systemd/system/moos-cloud-grow-root.timer",
    ):
        require(not (ROOT / retired).exists(),
                f"duplicate MoOS disk-growth authority still ships: {retired}")
    require("preserve_hostname: true" in cloud_cfg,
            "cloud-init would call hostnamectl before D-Bus and degrade first boot")
    hostname_helper = read("/usr/libexec/moos-cloud-hostname")
    require("instance-data.json" in hostname_helper and "hostnamectl set-hostname" in hostname_helper,
            "the post-D-Bus provider hostname authority is incomplete")
    require(enabled("moos-cloud-hostname.service", service_targets),
            "the post-D-Bus provider hostname authority is not enabled")
    account_helper = read("/usr/libexec/moos-cloud-account-ready")
    require("CacheUser" in account_helper and "id \"$target\"" in account_helper,
            "the cloud greeter does not publish the provisioned user")
    graphical_targets = (
        "etc/systemd/system/graphical.target.wants",
        "usr/lib/systemd/system/graphical.target.wants",
    )
    require(enabled("moos-cloud-account-ready.service", graphical_targets),
            "the cloud account-ready gate is not enabled for graphical boot")
    account_unit = read("/usr/lib/systemd/system/moos-cloud-account-ready.service")
    require("Before=display-manager.service plasmalogin.service" in account_unit,
            "the cloud account gate does not hold the greeter until its user exists")

    ssh_cfg = read("/etc/ssh/sshd_config.d/10-moos-arm.conf")
    for directive in (
        "PasswordAuthentication no",
        "KbdInteractiveAuthentication no",
        "PermitRootLogin no",
    ):
        require(directive in ssh_cfg, f"public-cloud SSH policy lacks: {directive}")

    kargs = read("/usr/lib/bootc/kargs.d/50-moos-arm-console.toml")
    for argument in (
        "console=ttyAMA0,115200n8",
        "console=tty0",
        "rhgb",
        "quiet",
        "splash",
    ):
        require(argument in kargs, f"ARM kernel arguments lack {argument}")
    require("console=ttyS0" not in kargs,
            "the x86 serial console was configured on an Ampere image")

    dracut = read("/usr/lib/dracut/dracut.conf.d/50-moos-arm.conf")
    for driver in ("virtio_blk", "virtio_net", "virtio_gpu", "virtio_console"):
        require(driver in dracut, f"the portable initramfs lacks {driver}")
    require('hostonly="no"' in dracut,
            "the cloud initramfs is host-bound instead of portable")
    require(not (ROOT / "usr/lib/bootc/kargs.d/30-moos-latency.toml").exists(),
            "x86 gaming latency kargs leaked into the ARM image")
    mokernel = read("/usr/bin/mokernel")
    require('if [ "$(uname -m)" = "x86_64" ]' in mokernel,
            "MoKernel does not scope x86-only kernel policy by architecture")

    firewall = subprocess.run(
        ["firewall-offline-cmd", "--get-default-zone"],
        capture_output=True,
        text=True,
        check=False,
    )
    require(firewall.returncode == 0 and firewall.stdout.strip() == "public",
            "firewalld default zone is not public")
    ssh_service = subprocess.run(
        ["firewall-offline-cmd", "--zone=public", "--query-service=ssh"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    rdp_service = subprocess.run(
        ["firewall-offline-cmd", "--zone=public", "--query-service=rdp"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    require(ssh_service.returncode == 0, "the host firewall does not allow SSH")
    require(rdp_service.returncode != 0,
            "RDP is exposed by the host firewall instead of staying behind SSH")

    policy = json.loads(read("/etc/containers/policy.json"))
    entries = policy.get("transports", {}).get("docker", {}).get(
        "ghcr.io/moalfarras-sys", []
    )
    require(len(entries) == 1 and entries[0].get("type") == "sigstoreSigned",
            "the ARM image does not enforce signatures for the MoOS registry")
    require(entries[0].get("keyPath") == "/etc/pki/containers/moos.pub",
            "the ARM signature policy does not use the shipped MoOS public key")
    require((ROOT / "etc/pki/containers/moos.pub").is_file(),
            "the ARM image lacks the container signing public key")

    for absent in (
        "usr/bin/moplayer",
        "usr/bin/mo-pc-remote",
        "usr/share/applications/org.moos.moplayer.desktop",
        "usr/share/applications/org.moos.remote.desktop",
    ):
        require(not (ROOT / absent).exists(),
                f"x86-only payload survived in the ARM image: /{absent}")
    require((ROOT / "usr/share/doc/moos-arm/OMITTED.md").is_file(),
            "the ARM edition does not document its intentional x86-only omissions")

    print("ARM IMAGE OK: aarch64, Wayland, Oracle boot, SSH and firewall gates passed")


if __name__ == "__main__":
    main()
