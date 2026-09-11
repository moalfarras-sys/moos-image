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


def owned_path(root: Path, relative: str) -> Path:
    path = root / relative
    if (not path.resolve().is_relative_to(root)
            or any(parent.is_symlink() for parent in (path, *path.parents)
                   if parent != root and parent.is_relative_to(root))):
        raise RuntimeError(f"unexpected symlink in compose state: {relative}")
    return path


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
                     "run/selinux-policy", "run/systemd/resolve",
                     "run/systemd/systemd-units-load"):
        path = owned_path(root, relative)
        # Buildah binds the builder's DNS file here when /etc/resolv.conf is
        # a systemd-resolved symlink. It is not image content and cannot be
        # unlinked. Leave this injected mount and its containing directory.
        if relative == "run/systemd/resolve" and os.path.ismount(path / "stub-resolv.conf"):
            continue
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()
    unexpected = []
    for base, dirs, files in os.walk(root / "var", followlinks=False):
        # buildah cache mounts are not part of the resulting layer.
        dirs[:] = [name for name in dirs
                   if not os.path.ismount(Path(base) / name)]
        unexpected.extend(str((Path(base) / name).relative_to(root))
                          for name in files if not (Path(base) / name).is_symlink())
    if unexpected:
        raise RuntimeError("unexpected mutable image files: " + ", ".join(unexpected))
    # RPMs create these empty service directories during compose, but bootc
    # needs a tmpfiles declaration to recreate them on the machine's /var.
    # Only declare paths provided by installed packages on this edition. Copy
    # their actual modes and named owners instead of guessing cross-arch GIDs.
    declarations = []
    for relative in ("var/lib/livesys", "var/lib/lxc", "var/lib/lxcfs",
                     "var/lib/rpm-state", "var/lib/samba/winbindd_privileged",
                     "var/lib/xkb"):
        path = owned_path(root, relative)
        if not path.exists():
            continue
        if path.is_symlink() or not path.is_dir() or any(path.iterdir()):
            raise RuntimeError(f"expected empty package state directory: {relative}")
        info = path.stat()
        declarations.append(f"d /{relative} {stat.S_IMODE(info.st_mode):04o} "
                            f"{pwd.getpwuid(info.st_uid).pw_name} "
                            f"{grp.getgrgid(info.st_gid).gr_name} -")
    if declarations:
        policy = owned_path(root, "usr/lib/tmpfiles.d/moos-image-state.conf")
        policy.parent.mkdir(parents=True, exist_ok=True)
        policy.write_text("# Package-owned directories on mutable /var. Generated at compose.\n"
                          + "\n".join(declarations) + "\n")
    # systemd.conf already recreates this empty runtime directory at boot.
    ask_password = root / "run/systemd/ask-password"
    if ask_password.is_dir() and not ask_password.is_symlink():
        ask_password.rmdir()  # fail if unexpected content is present


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    finalize(args.root)
    print("MoOS image state gate passed: no mutable files ship in /var")
