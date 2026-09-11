#!/usr/bin/env python3
"""Remove compose-only state; fail if unexpected mutable files would ship.

Runs only in a build container. Flatpak's empty installation is recreated by
moos-flatpak-init at boot from /etc/flatpak/remotes.d, preserving existing users.
Never remove a populated app/runtime store, boot assets or unrecognized state.
"""
import argparse
import os
from pathlib import Path
import shutil
import grp
import pwd
import stat


# Empty paths created by packages during compose. Their modes and named owners
# are captured into a generated tmpfiles policy before the paths are removed.
# Keep this list explicit: an unknown empty directory is state drift, not a new
# authority that the finalizer may silently bless.
PACKAGE_STATE_DIRECTORIES = (
    "var/lib",
    "var/lib/AccountsService",
    "var/lib/AccountsService/icons",
    "var/lib/AccountsService/users",
    "var/lib/bluetooth",
    "var/lib/bluetooth/mesh",
    "var/lib/cloud",
    "var/lib/color",
    "var/lib/color/icc",
    "var/lib/colord",
    "var/lib/colord/icc",
    "var/lib/dhcpcd",
    "var/lib/dnf",
    "var/lib/geoclue",
    "var/lib/livesys",
    "var/lib/lxc",
    "var/lib/lxcfs",
    "var/lib/plasmalogin",
    "var/lib/plymouth",
    "var/lib/rpm-state",
    "var/lib/samba",
    "var/lib/samba/winbindd_privileged",
    "var/lib/xkb",
    "run/cloud-init",
    "run/cups",
    "run/cups/certs",
    "run/plasmalogin",
)

STATIC_STATE_DIRECTORIES = (
    ("var/lib/authselect", "usr/lib/tmpfiles.d/moos-authselect-state.conf"),
    ("var/lib/waydroid", "usr/lib/tmpfiles.d/waydroid.conf"),
)


# systemd 259 keeps this compose marker as an empty regular file (native ARM
# compose, run 34646190268; the Fedora 44 daily driver shows the same). Only the
# entries listed here may be a single regular file; every other cleanup root must
# still be a real directory, and links, mounts and special nodes always fail.
CLEANUP_FILE_OR_DIRECTORY = frozenset({"run/systemd/systemd-units-load"})


def owned_path(root: Path, relative: str) -> Path:
    path = root / relative
    if (not path.resolve().is_relative_to(root)
            or any(parent.is_symlink() for parent in (path, *path.parents)
                   if parent != root and parent.is_relative_to(root))):
        raise RuntimeError(f"unexpected symlink in compose state: {relative}")
    return path


def unexpected_mutable_entries(root: Path, relative: str,
                               allowed_directories: set[str],
                               allowed_files: set[str],
                               allowed_mounts: set[str]) -> list[str]:
    """Return image-owned entries below a mutable tree that have no authority.

    Buildah injects a few mounts into /run and may mount package caches below
    /var. Mounts are host/container runtime state and cannot enter the image
    layer, so skip the mount itself. Everything else counts, including empty
    directories, symlinks, sockets and device nodes.
    """
    base = root / relative
    if base.is_symlink():
        return [relative]
    if not base.exists():
        return []
    if not base.is_dir():
        return [relative]
    unexpected: list[str] = []
    for current, dirs, files in os.walk(base, followlinks=False):
        kept_dirs = []
        for name in dirs:
            path = Path(current) / name
            rel = str(path.relative_to(root))
            if os.path.ismount(path) and rel in allowed_mounts:
                continue
            if os.path.ismount(path):
                unexpected.append(rel)
                continue
            if path.is_symlink():
                unexpected.append(rel)
                continue
            kept_dirs.append(name)
            if rel not in allowed_directories:
                unexpected.append(rel)
        dirs[:] = kept_dirs
        for name in files:
            path = Path(current) / name
            rel = str(path.relative_to(root))
            if os.path.ismount(path) and rel in allowed_mounts:
                continue
            if rel not in allowed_files:
                unexpected.append(rel)
    return unexpected


def reject_unsafe_cleanup_entries(root: Path, relative: str) -> None:
    """Never let recursive cleanup hide a link or special filesystem node."""
    path = owned_path(root, relative)
    if not path.exists():
        return
    if os.path.ismount(path):
        raise RuntimeError(f"unsafe mount in compose cleanup state: {relative}")
    if relative in CLEANUP_FILE_OR_DIRECTORY and stat.S_ISREG(path.lstat().st_mode):
        return  # a single regular file is unlinked below, never walked or rmtree'd
    if not path.is_dir():
        raise RuntimeError(f"cleanup state is not a directory: {relative}")
    for current, dirs, files in os.walk(path, followlinks=False):
        for name in (*dirs, *files):
            child = Path(current) / name
            child_relative = str(child.relative_to(root))
            if os.path.ismount(child):
                raise RuntimeError(
                    f"unsafe mount in compose cleanup state: {child_relative}"
                )
            mode = child.lstat().st_mode
            if stat.S_ISLNK(mode) or not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
                raise RuntimeError(
                    f"unsafe entry in compose cleanup state: {child_relative}"
                )


def require_scaffold(root: Path, relative: str, mode: int) -> None:
    """Validate a retained empty directory against the synthetic root owner."""
    path = owned_path(root, relative)
    if not path.exists():
        raise RuntimeError(f"missing mutable scaffold: {relative}")
    info = path.stat()
    root_info = root.stat()
    if (not path.is_dir() or any(path.iterdir())
            or stat.S_IMODE(info.st_mode) != mode
            or info.st_uid != root_info.st_uid or info.st_gid != root_info.st_gid):
        raise RuntimeError(f"invalid mutable scaffold: {relative}")


def finalize(root: Path) -> None:
    root = root.resolve()
    if root == Path("/") and (
        not Path("/run/.containerenv").exists() or Path("/run/ostree-booted").exists()
    ):
        raise RuntimeError("image finalization requires an unbooted build container")
    for relative in ("var/lib/flatpak/app", "var/lib/flatpak/runtime"):
        path = root / relative
        if path.exists() and any(path.iterdir()):
            raise RuntimeError(f"refusing to remove installed applications: {relative}")
    refs = root / "var/lib/flatpak/repo/refs"
    if refs.exists() and any(path.is_file() for path in refs.rglob("*")):
        raise RuntimeError("refusing to remove a Flatpak repository with committed refs")
    # Both are required to reconstruct the store without network access at boot.
    for relative in ("etc/flatpak/remotes.d/flathub.flatpakrepo",
                     "usr/lib/systemd/system/moos-flatpak-init.service"):
        if not (root / relative).is_file():
            raise RuntimeError(f"missing first-boot store authority: {relative}")
    for relative in ("var/lib/flatpak", "var/lib/dnf/repos", "run/cockpit",
                     "run/dnf", "run/selinux-policy",
                     "run/systemd/systemd-units-load"):
        reject_unsafe_cleanup_entries(root, relative)
    # xorg-x11-server-common puts documentation in its mutable keymap cache.
    # Preserve those bytes in /usr; tmpfiles below recreates the cache itself.
    xkb_readme = owned_path(root, "var/lib/xkb/README.compiled")
    if xkb_readme.is_file():
        destination = owned_path(root, "usr/share/doc/moos-xkb/README.compiled")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(xkb_readme, destination)
        xkb_readme.unlink()
    # Known derived state only. In particular /boot and RPM's immutable database
    # are outside this list; new unknown /var files fail instead of disappearing.
    for relative in ("var/lib/flatpak", "var/lib/dnf/repos",
                     "var/lib/dnf/system-repo.lock", "run/cockpit", "run/dnf",
                     "run/selinux-policy", "run/systemd/systemd-units-load"):
        path = owned_path(root, relative)
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()
    # These paths already have a dedicated immutable policy, including the
    # copy-if-absent authselect seed and Waydroid's SELinux relabel operation.
    for relative, authority in STATIC_STATE_DIRECTORIES:
        path = owned_path(root, relative)
        if not path.exists():
            continue
        if path.is_symlink() or not path.is_dir() or any(path.iterdir()):
            raise RuntimeError(f"expected empty package state directory: {relative}")
        if not (root / authority).is_file():
            raise RuntimeError(f"missing tmpfiles authority for {relative}")
        path.rmdir()

    # RPMs create empty service directories during compose, but bootc needs a
    # tmpfiles declaration to recreate persistent and runtime ownership. Work
    # leaf-first so a listed parent is accepted only after every listed child
    # vanished; any unknown child keeps the parent nonempty and fails loudly.
    captured = {}
    for relative in sorted(PACKAGE_STATE_DIRECTORIES,
                           key=lambda item: (item.count("/"), item), reverse=True):
        path = owned_path(root, relative)
        if not path.exists():
            continue
        if relative == "var/lib" and path.is_dir() and not path.is_symlink() \
                and any(path.iterdir()):
            # Unknown children belong to the final sweep, which reports their
            # exact paths instead of mislabeling the parent as package state.
            continue
        if path.is_symlink() or not path.is_dir() or any(path.iterdir()):
            raise RuntimeError(f"expected empty package state directory: {relative}")
        info = path.stat()
        captured[relative] = (
            f"d /{relative} {stat.S_IMODE(info.st_mode):04o} "
            f"{pwd.getpwuid(info.st_uid).pw_name} "
            f"{grp.getgrgid(info.st_gid).gr_name} -"
        )
        path.rmdir()
    if captured:
        policy = owned_path(root, "usr/lib/tmpfiles.d/moos-image-state.conf")
        policy.parent.mkdir(parents=True, exist_ok=True)
        policy.write_text("# Package-owned mutable directories. Generated at compose.\n"
                          + "\n".join(captured[key] for key in sorted(captured)) + "\n")
    # systemd.conf already recreates this empty runtime directory at boot.
    ask_password = root / "run/systemd/ask-password"
    if ask_password.is_dir() and not ask_password.is_symlink():
        ask_password.rmdir()  # fail if unexpected content is present

    # The synthetic test root has no resolver mount, so discard the empty
    # ancestor left by the ask-password fixture. A real compose retains
    # run/systemd because it contains the validated resolver placeholder below.
    systemd_run = owned_path(root, "run/systemd")
    if systemd_run.is_dir() and not systemd_run.is_symlink() \
            and not any(systemd_run.iterdir()):
        systemd_run.rmdir()

    # The base deliberately carries a zero-byte mountpoint for resolv.conf.
    # Buildah mounts its generated file over that exact path during compose;
    # the zero-byte placeholder, not host DNS content, remains in the layer.
    # Validate the immutable relationship before granting this narrow exception.
    allowed_run_directories: set[str] = set()
    allowed_run_files: set[str] = set()
    allowed_mounts: set[str] = set()
    injected_resolver = root / "run/systemd/resolve/stub-resolv.conf"
    resolv_link = root / "etc/resolv.conf"
    if injected_resolver.exists() or os.path.ismount(injected_resolver):
        if not resolv_link.is_symlink() \
                or os.readlink(resolv_link) != "../run/systemd/resolve/stub-resolv.conf":
            raise RuntimeError("resolver scaffold is not owned by /etc/resolv.conf")
        allowed_run_directories.update(("run/systemd", "run/systemd/resolve"))
        if os.path.ismount(injected_resolver):
            if root != Path("/"):
                raise RuntimeError("unexpected resolver mount outside the compose root")
            allowed_mounts.add("run/systemd/resolve/stub-resolv.conf")
        else:
            info = injected_resolver.stat()
            root_info = root.stat()
            if (not injected_resolver.is_file() or injected_resolver.is_symlink()
                    or info.st_size != 0 or stat.S_IMODE(info.st_mode) != 0o700
                    or info.st_uid != root_info.st_uid or info.st_gid != root_info.st_gid):
                raise RuntimeError("invalid resolver mountpoint scaffold")
            allowed_run_files.add("run/systemd/resolve/stub-resolv.conf")

    # These are the only mounts supplied by the Containerfiles/container
    # runtime. An unexpected mount is rejected instead of becoming an implicit
    # exemption from the state gate.
    if root == Path("/"):
        for path in (root / "var/cache", root / "var/log",
                     root / "run/.containerenv", root / "run/secrets"):
            if os.path.ismount(path):
                allowed_mounts.add(str(path.relative_to(root)))

    # The mutable roots themselves must be real root-owned directories. A
    # symlink here could redirect every later check outside the image root.
    root_info = root.stat()
    for relative in ("var", "run"):
        path = owned_path(root, relative)
        info = path.stat()
        if (not path.is_dir() or stat.S_IMODE(info.st_mode) != 0o755
                or info.st_uid != root_info.st_uid or info.st_gid != root_info.st_gid):
            raise RuntimeError(f"invalid mutable root: {relative}")
    require_scaffold(root, "var/tmp", 0o1777)
    unexpected = unexpected_mutable_entries(
        root, "var", {"var/tmp"}, set(),
        {entry for entry in allowed_mounts if entry.startswith("var/")}
    )
    unexpected.extend(unexpected_mutable_entries(
        root, "run", allowed_run_directories, allowed_run_files,
        {entry for entry in allowed_mounts if entry.startswith("run/")}
    ))
    if unexpected:
        raise RuntimeError("unexpected mutable image entries: "
                           + ", ".join(sorted(unexpected)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    finalize(args.root)
    print("MoOS image state gate passed: /var and /run contain no unowned image state")
