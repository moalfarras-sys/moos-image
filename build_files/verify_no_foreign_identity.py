#!/usr/bin/python3
"""MoOS IDENTITY FIREWALL — the last line that keeps MoOS from ever booting as
something else.

WHY THIS EXISTS (read before touching it):
    MoOS is built FROM Fedora Kinoite. Every build starts with an image full of
    Fedora branding, and build_files/build.sh scrubs it. The other gates
    (verify_identity.py, verify_image_experience.py) check the SPECIFIC surfaces
    we already know about. This one is different: it SWEEPS the finished image
    for foreign branding by pattern, on the real bytes that will ship — so it
    catches the two things a named-surface gate cannot:

      1. A BASE-IMAGE UPDATE that adds a Fedora asset under a new name or in a
         new directory, which build.sh's fixed scrub list never touched.
      2. AN AGENT WHO DID NOT UNDERSTAND — an edit that removed a scrub step,
         layered a package that re-installs fedora-logos, or dropped the MoOS
         override, and did not realise the identity regressed.

    It runs INSIDE the image (see build.sh), so it reads what the user will
    actually get, not what the source hoped for.

IF YOU ARE AN AUTOMATED AGENT AND THIS GATE FAILED:
    You did not "break the test" — the test caught a real regression. A file the
    user can see now carries another OS's name or logo. DO NOT delete or weaken
    this gate to make the build pass. Instead: find where build.sh scrubs that
    surface and restore/extend it (the foreign-icon scrub is section (z2); the
    os-release identity is section (z); foreign themes are (z2a)). If a base
    update introduced a NEW foreign name, add it to build.sh's scrub — never to
    an allow-list here. The whole point of MoOS is that it is MoOS.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path("/")
CANON = ROOT / "usr/share/pixmaps/moos-logo.png"   # the canonical MoOS mark

failures: list[str] = []


def fail(message: str) -> None:
    failures.append(message)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# Filename stems that are, by definition, another distribution's brand. A file
# with one of these names is only allowed to ship if its BYTES are the MoOS mark
# (an intentional compatibility alias) — never as the real foreign artwork.
FOREIGN_LOGO_STEMS = (
    "fedora-logo", "fedora-logo-icon", "fedora-logo-small", "fedora-gdm-logo",
    "start-here-fedora", "org.fedoraproject.AnacondaInstaller",
    "org.fedoraproject.fedora", "redhat-logo", "redhat", "red-hat",
)

# The two wordmark pixmaps are MoOS art at legacy filenames, but they are NOT
# byte-identical to the round emblem master — they are their own shape. They are
# digest-pinned in verify_identity.py, so this sweep must skip them rather than
# demand they equal the emblem.
PINNED_ELSEWHERE = {
    ROOT / "usr/share/pixmaps/fedora_logo_med.png",
    ROOT / "usr/share/pixmaps/system-logo-white.png",
}


def sweep_foreign_logos() -> None:
    if not CANON.is_file():
        fail("the canonical MoOS logo /usr/share/pixmaps/moos-logo.png is gone — "
             "nothing can be checked against it; restore it before anything else")
        return

    roots = [ROOT / "usr/share/icons", ROOT / "usr/share/pixmaps"]
    for base in roots:
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if not path.is_file() and not path.is_symlink():
                continue
            if path in PINNED_ELSEWHERE:
                continue
            stem = path.name.rsplit(".", 1)[0]
            if stem not in FOREIGN_LOGO_STEMS:
                continue
            suffix = path.suffix.lower()
            if suffix in (".svg", ".svgz"):
                # A scalable foreign logo wins over the raster MoOS mark at large
                # sizes; the scrub deletes these. One surviving here is a real leak.
                fail(f"a foreign-brand vector logo survived the scrub and would "
                     f"outrank the MoOS mark: {path}")
                continue
            if suffix in (".png", ".xpm"):
                # The scrub replaces these with the SAME-SIZE moos-logo.png if the
                # directory has one, else the master — so compare against that.
                sibling = path.with_name("moos-logo.png")
                reference = sibling if sibling.is_file() else CANON
                try:
                    if digest(path) != digest(reference):
                        fail(f"a foreign-brand raster logo is NOT the MoOS mark "
                             f"(differs from {reference}): {path}")
                except OSError as exc:
                    fail(f"could not read a foreign-named logo to verify it: {path} ({exc})")


def check_os_release() -> None:
    osr = ROOT / "usr/lib/os-release"
    if not osr.is_file():
        fail("/usr/lib/os-release is missing — the machine has no identity at all")
        return
    values: dict[str, str] = {}
    for line in osr.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, val = line.split("=", 1)
            values[key.strip()] = val.strip().strip('"')

    if values.get("ID") != "moos":
        fail(f"os-release ID is {values.get('ID')!r}, not 'moos' — the whole "
             "system would identify as another distribution")
    if not values.get("PRETTY_NAME", "").startswith("MoOS"):
        fail(f"os-release PRETTY_NAME is {values.get('PRETTY_NAME')!r} — the name "
             "the user sees in About/neofetch is not MoOS")

    # ID_LIKE='fedora' is REQUIRED (dnf/COPR chroot resolution, derivative
    # detection) and is the ONE place 'fedora' may legitimately appear. Every
    # other value naming fedora/redhat is a leak — a HOME_URL, a REDHAT_* key a
    # base update re-added, a support address pointing at the wrong project.
    for key, val in values.items():
        if key in ("ID_LIKE", "VERSION_ID", "VERSION", "PLATFORM_ID"):
            continue
        low = val.lower()
        if "fedora" in low or "redhat" in low or "red hat" in low:
            fail(f"os-release {key}={val!r} still names another OS — a user-visible "
                 "identity field leaked from the base image")
    if any(k.startswith("REDHAT_") for k in values):
        fail("os-release still carries REDHAT_* support keys inherited from the base")


def check_foreign_packages() -> None:
    gone = (
        "usr/share/plasma/look-and-feel/org.fedoraproject.fedora.desktop",
        "usr/share/plasma/look-and-feel/org.fedoraproject.fedoradark.desktop",
        "usr/share/plasma/look-and-feel/org.fedoraproject.fedoralight.desktop",
        "usr/share/wallpapers/Fedora",
        "usr/share/backgrounds/fedora-workstation",
    )
    for rel in gone:
        if (ROOT / rel).exists():
            fail(f"another distribution's theme/wallpaper is installed and offered "
                 f"to the user in the pickers: /{rel}")

    # A base update can re-add a whole family of Fedora look-and-feel packages;
    # sweep for any org.fedoraproject.* the explicit list above did not name.
    lnf = ROOT / "usr/share/plasma/look-and-feel"
    if lnf.is_dir():
        for path in lnf.glob("org.fedoraproject.*"):
            fail(f"a Fedora Global Theme is selectable in Appearance: {path}")


def check_grub_distributor() -> None:
    grub = ROOT / "etc/default/grub"
    if not grub.is_file():
        return
    for line in grub.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith("GRUB_DISTRIBUTOR="):
            val = s.split("=", 1)[1].strip().strip('"').strip("'")
            if "moos" not in val.lower():
                fail(f"GRUB_DISTRIBUTOR is {val!r} — the boot menu would title the "
                     "system with another distribution's name")


def check_console_identity() -> None:
    """The TTY console login banner and the terminal fastfetch readout.

    These are the two user-visible surfaces the named-surface gates missed:
    /etc/issue is printed by agetty at every text login, and fastfetch draws its
    logo in every interactive shell. Both resolve to MoOS today, but /etc/issue's
    default is provided by the base `setup` package (a base update could reintroduce
    a Fedora banner) and fastfetch would auto-detect a distro logo if its inline
    MoOS wordmark were removed — neither had a gate.
    """
    issue = ROOT / "etc/issue"
    if issue.is_file():
        text = issue.read_text(encoding="utf-8", errors="replace")
        low = text.lower()
        if "moos" not in low:
            fail("/etc/issue does not name MoOS — the TTY login banner would show "
                 "the base distribution's name")
        for bad in ("fedora", "kinoite", "red hat", "redhat"):
            if bad in low:
                fail(f"/etc/issue contains {bad!r} — a foreign name on the console "
                     "login banner")

    cfg = ROOT / "etc/fastfetch/config.jsonc"
    if cfg.is_file():
        text = cfg.read_text(encoding="utf-8", errors="replace")
        # The MoOS wordmark is shipped inline as a "data" logo precisely so
        # fastfetch never auto-detects a distro logo. If that block is gone,
        # fastfetch falls back to ID_LIKE=fedora and prints a Fedora logo.
        # Markers chosen to avoid backslash-escaping ambiguity: the data logo
        # type, the MoOS brand-blue colour slot, and the wordmark's bottom row.
        if ('"type": "data"' not in text
                or "2E7BFF" not in text
                or "|_|  |_|" not in text):
            fail("/etc/fastfetch/config.jsonc no longer ships the inline MoOS "
                 "wordmark logo — fastfetch would auto-detect and draw a Fedora "
                 "logo in every terminal")


def main() -> None:
    sweep_foreign_logos()
    check_os_release()
    check_foreign_packages()
    check_grub_distributor()
    check_console_identity()

    if failures:
        print("MoOS IDENTITY FIREWALL: the finished image would ship another OS's "
              "identity on a surface the user can see.\n")
        for f in failures:
            print(f"  ✗ {f}")
        print("\nThis is a real regression, not a flaky test. See the header of "
              "build_files/verify_no_foreign_identity.py — fix the scrub in "
              "build.sh, do NOT weaken this gate.")
        raise SystemExit(1)

    print("IDENTITY FIREWALL OK: no foreign logo, name or theme reaches any "
          "user-visible surface of the built image.")


if __name__ == "__main__":
    main()
