#!/usr/bin/env python3
"""Finished-image gates specific to the MoOS ARM cloud/UTM edition."""

from __future__ import annotations

import configparser
import json
import os
import platform
import subprocess
from pathlib import Path

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


def verify_appstream_refresh() -> None:
    """A delayed timer must resolve to an executable service in the image."""
    timer = configparser.ConfigParser(interpolation=None)
    timer.read_string(read("usr/lib/systemd/system/moos-appstream-refresh.timer"))
    require(timer.get("Timer", "OnBootSec", fallback="") == "3min",
            "AppStream refresh must remain outside the boot critical path")
    require(timer.get("Timer", "Unit", fallback="moos-appstream-refresh.service")
            == "moos-appstream-refresh.service", "AppStream timer targets the wrong service")
    service = configparser.ConfigParser(interpolation=None)
    service.read_string(read("usr/lib/systemd/system/moos-appstream-refresh.service"))
    require(service.get("Service", "Type", fallback="") == "oneshot"
            and service.get("Service", "ExecStart", fallback="")
            == "/usr/bin/appstreamcli refresh-cache --force",
            "ARM AppStream refresh has no working cache-refresh command")
    executable = ROOT / "usr/bin/appstreamcli"
    require(executable.is_file() and os.access(executable, os.X_OK),
            "AppStream refresh executable is missing")
    require(any((ROOT / base / "moos-appstream-refresh.timer").is_file() for base in (
        "etc/systemd/system/timers.target.wants",
        "usr/lib/systemd/system/timers.target.wants",
    )), "AppStream timer is disabled or has a dangling enable link")


def main() -> None:
    import yaml

    require(platform.machine() == "aarch64",
            f"finished image was built on {platform.machine()}, not aarch64")
    verify_appstream_refresh()

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
        "plasma-milou",
        "plasma-login-manager",
        "kwin-libs",
        "plasma-breeze",
        "papirus-icon-theme",
        "cloud-init",
        "cloud-utils-growpart",
        "krdp",
        "tailscale",
        "rpm-ostree",
        "skopeo",
        "mpv-libs",
        "ydotool",
        "gstreamer1",
        "gstreamer1-plugins-good",
        "ramalama",
        "plasma-discover",
        "plasma-discover-flatpak",
        "plasma-discover-kns",
        "kinfocenter",
        "bluedevil",
        "plasma-print-manager",
        "flatpak-kcm",
    ):
        result = subprocess.run(
            ["rpm", "-q", package],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        require(result.returncode == 0, f"required aarch64 package is absent: {package}")

    for executable in ("ramalama", "plasma-discover", "kinfocenter"):
        path = ROOT / "usr/bin" / executable
        require(path.is_file() and os.access(path, os.X_OK),
                f"ARM control surface backend is not executable: {path}")

    # The frontend is architecture-independent and always calls these loopback
    # authorities. An installed unit is not enough: the failed ARM release had
    # every Mo AI unit present but disabled, so the window opened with no live
    # backend. Read the finished image's enable links, not the build script.
    user_default_targets = (
        "etc/systemd/user/default.target.wants",
        "usr/lib/systemd/user/default.target.wants",
    )
    user_timer_targets = (
        "etc/systemd/user/timers.target.wants",
        "usr/lib/systemd/user/timers.target.wants",
    )
    user_plasma_targets = (
        "etc/systemd/user/plasma-workspace.target.wants",
        "usr/lib/systemd/user/plasma-workspace.target.wants",
    )
    for unit in (
        "moai-gateway.service",
        "moai-control.service",
        "moai-agent-api.service",
        "moai-wake.service",
        "moos-cloud-audio.service",
    ):
        require(enabled(unit, user_default_targets),
                f"first-party ARM user authority is disabled: {unit}")
    for unit in (
        "moai-idle.timer",
        "openclaw-idle.timer",
        "moos-ensure-brain.timer",
        "moos-update-ready.timer",
        "moos-reclaim-disk.timer",
    ):
        require(enabled(unit, user_timer_targets),
                f"first-party ARM user timer is disabled: {unit}")
    require(enabled("moos-theme-sync.path", user_plasma_targets),
            "ARM theme state does not have its live synchronization authority")

    # Real-root udevd is ordered after systemd-hwdb-update. The RPM-generated
    # database under /etc forced a 14 MB rebuild on every clean deployment and,
    # under the release gate's TCG boot, /boot and /boot/efi timed out before
    # their UUID links were recreated. The immutable compiled database belongs
    # in /usr; /etc remains available only for later machine-local overrides.
    usr_hwdb = ROOT / "usr/lib/udev/hwdb.bin"
    etc_hwdb = ROOT / "etc/udev/hwdb.bin"
    require(usr_hwdb.is_file() and usr_hwdb.stat().st_size > 1_000_000,
            "immutable compiled hardware database is missing from /usr")
    require(not etc_hwdb.exists(),
            "package-generated /etc hardware database would block udevd at boot")
    etc_hwdb_sources = ROOT / "etc/udev/hwdb.d"
    require(not etc_hwdb_sources.exists() or not any(etc_hwdb_sources.iterdir()),
            "image-owned hwdb overrides under /etc would force a boot-time rebuild")

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

    # The shared source tree is not the finished desktop. MoOSUI2/MoOSDark are
    # generated after RPM installation, and Plasma's qmldir must be changed so
    # the greeter loads the shipped MoOS controls rather than AOT Breeze copies.
    # The first boot-proven ARM release omitted this finalization and visibly
    # produced wallpaper plus a language label with no usable login card.
    for theme in ("MoOSUI2", "MoOSUI2Light"):
        theme_root = ROOT / "usr/share/icons" / theme
        index = theme_root / "index.theme"
        require(index.is_file() and (theme_root / "apps").is_dir(),
                f"generated broad icon theme is invalid: {theme}")
        index_text = index.read_text(encoding="utf-8", errors="replace")
        require("Directories=moos/actions/scalable,moos/apps/scalable," in index_text,
                f"generated icon theme does not prioritize MoOS controls: {theme}")
        require((theme_root / "moos/apps/scalable/moos-store.svg").is_file(),
                f"generated icon theme lacks first-party application marks: {theme}")
    for cursor in ("MoOS", "MoOSDark"):
        require((ROOT / "usr/share/icons" / cursor / "cursors/left_ptr").exists(),
                f"generated MoOS pointer theme is missing: {cursor}")
    require("Inherits=MoOS" in read("/usr/share/icons/default/index.theme"),
            "the pre-session default pointer does not resolve to MoOS")

    breeze_qmldir = read("/usr/lib64/qt6/qml/org/kde/breeze/components/qmldir")
    require(not any(line.startswith("prefer ") for line in breeze_qmldir.splitlines()),
            "Plasma Login Manager still prefers compiled Breeze controls over MoOS QML")
    for component in ("ActionButton.qml", "Clock.qml", "UserDelegate.qml"):
        require((ROOT / "usr/lib64/qt6/qml/org/kde/breeze/components" / component).is_file(),
                f"MoOS login control is absent: {component}")
    greeter_palette = read("/usr/share/moos/plasmalogin/kdeglobals")
    require("ColorScheme=MoOSUI2Dark" in greeter_palette
            and "Theme=MoOSUI2" in greeter_palette,
            "the greeter account is not pinned to the MoOS dark palette and icons")
    greeter_tmpfiles = read("/usr/lib/tmpfiles.d/moos-plasmalogin-greeter.conf")
    require("r! /var/lib/plasmalogin/.config/kdeglobals" in greeter_tmpfiles
            and "C+ /var/lib/plasmalogin/.config/kdeglobals" in greeter_tmpfiles,
            "the immutable greeter palette is not materialized on every boot")

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
    for unit in (
        "NetworkManager.service", "sshd.service", "firewalld.service",
        "tailscaled.service",
    ):
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
    grow_helper_path = ROOT / "usr/libexec/bootc-generic-growpart"
    require(grow_unit_path.is_file(), "Fedora bootc's physical root grow service is missing")
    require(grow_helper_path.is_file() and os.access(grow_helper_path, os.X_OK),
            "Fedora bootc's physical root grow helper is missing or not executable")
    grow_unit = grow_unit_path.read_text(encoding="utf-8", errors="replace")
    for contract in (
        "ConditionVirtualization=vm",
        "ConditionPathIsMountPoint=/sysroot",
        "ConditionPathExists=/usr/bin/growpart",
        "Before=basic.target",
        "ExecStart=/usr/libexec/bootc-generic-growpart",
    ):
        require(contract in grow_unit, f"bootc grow unit lacks contract: {contract}")
    grow_helper = grow_helper_path.read_text(encoding="utf-8", errors="replace")
    for contract in (
        "findmnt -vno SOURCE /sysroot",
        "/usr/bin/growpart",
        "^NOCHANGE: ",
        "mount -o remount,rw /sysroot",
        "/usr/lib/systemd/systemd-growfs /sysroot",
    ):
        require(contract in grow_helper, f"bootc grow helper lacks contract: {contract}")
    grow_links = (
        ROOT / "etc/systemd/system/local-fs.target.wants/bootc-generic-growpart.service",
        ROOT / "usr/lib/systemd/system/local-fs.target.wants/bootc-generic-growpart.service",
    )
    linked = False
    for candidate in grow_links:
        if candidate.is_symlink():
            try:
                linked = candidate.resolve(strict=True) == grow_unit_path.resolve(strict=True)
            except OSError:
                linked = False
            if linked:
                break
    require(linked, "the bootc physical root grow enable link is missing or dangling")

    block_unit_path = ROOT / "usr/lib/systemd/system/moos-arm-block-coldplug.service"
    block_helper_path = ROOT / "usr/libexec/moos-arm-block-coldplug"
    require(block_unit_path.is_file(), "ARM block coldplug unit is missing")
    require(block_helper_path.is_file() and os.access(block_helper_path, os.X_OK),
            "ARM block coldplug helper is missing or not executable")
    block_unit = block_unit_path.read_text(encoding="utf-8", errors="replace")
    for contract in (
        "ConditionArchitecture=arm64",
        "After=systemd-udev-trigger.service",
        "Before=local-fs-pre.target boot.mount boot-efi.mount",
        "ExecStart=/usr/libexec/moos-arm-block-coldplug",
    ):
        require(contract in block_unit, f"ARM block coldplug unit lacks contract: {contract}")
    block_helper = block_helper_path.read_text(encoding="utf-8", errors="replace")
    require("--subsystem-match=block" in block_helper
            and "--action=change" in block_helper
            and "/dev/disk/by-uuid/" in block_helper,
            "ARM block coldplug helper does not republish and verify filesystem links")
    block_links = (
        ROOT / "etc/systemd/system/local-fs-pre.target.wants/moos-arm-block-coldplug.service",
        ROOT / "usr/lib/systemd/system/local-fs-pre.target.wants/moos-arm-block-coldplug.service",
    )
    block_linked = False
    for candidate in block_links:
        if candidate.is_symlink():
            try:
                block_linked = candidate.resolve(strict=True) == block_unit_path.resolve(strict=True)
            except OSError:
                block_linked = False
            if block_linked:
                break
    require(block_linked, "ARM block coldplug enable link is missing or dangling")
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
    require(policy.get("default") == [{"type": "reject"}],
            "the ARM container policy has a permissive global default, which bootc refuses")
    require(policy.get("transports", {}).get("docker", {}).get("") ==
            [{"type": "insecureAcceptAnything"}],
            "ordinary ARM user container pulls lack the docker transport fallback")
    require(policy.get("transports", {}).get("containers-storage", {}).get("") ==
            [{"type": "insecureAcceptAnything"}],
            "ARM disk composition cannot import its local containers-storage image")
    require((ROOT / "etc/pki/containers/moos.pub").is_file(),
            "the ARM image lacks the container signing public key")

    # First-party parity is native, not a launcher-only promise. Both ELF entry
    # points must identify as AArch64 and every route must land on a real bundle.
    for binary in (
        ROOT / "usr/lib/moplayer/moplayer",
        ROOT / "usr/lib/mo-remote/MoRemotePersonal",
    ):
        require(binary.is_file() and os.access(binary, os.X_OK),
                f"native ARM first-party binary is missing: {binary}")
        header = binary.read_bytes()[:20]
        require(header[:4] == b"\x7fELF" and int.from_bytes(header[18:20], "little") == 183,
                f"first-party binary is not AArch64 ELF: {binary}")
        linked = subprocess.run(
            ["ldd", str(binary)], text=True, capture_output=True, check=False,
        )
        linkage = linked.stdout + linked.stderr
        require(linked.returncode == 0 and "not found" not in linkage,
                f"first-party ARM binary has unresolved runtime linkage: {binary}\n{linkage}")
    for payload in (
        "usr/bin/moplayer",
        "usr/bin/mo-pc-remote",
        "usr/share/applications/org.moos.moplayer.desktop",
        "usr/share/applications/org.moos.remote.desktop",
        "usr/lib/moplayer/data/icudtl.dat",
        "usr/lib/mo-remote/mo-remote-portal.py",
    ):
        require((ROOT / payload).is_file(), f"ARM first-party payload is missing: /{payload}")
    portal = read("/usr/lib/mo-remote/mo-remote-portal.py")
    for contract in ("pipewiresrc", "H264_ENCODERS", '"codec": "jpeg"'):
        require(contract in portal, f"ARM Remote lacks capability fallback contract: {contract}")
    require(not (ROOT / "usr/share/doc/moos-arm/OMITTED.md").exists(),
            "the retired ARM first-party omission marker still ships")

    print("ARM IMAGE OK: aarch64, first-party apps, Wayland, Oracle boot, SSH and firewall gates passed")


if __name__ == "__main__":
    main()
