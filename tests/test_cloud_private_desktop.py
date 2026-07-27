#!/usr/bin/env python3
"""Gate the second developer's private desktop so it cannot go dark again.

`moos-cloud-desktop own <user>` gives an account without a seat a full Plasma
desktop that Mo PC Remote can stream. Two separate things had to be true for that
to work, and both failed silently for a week on the cloud server — no failed unit,
no error, just a black picture and a screen nobody could use:

  1. ONE compositor. The command used to run its own
     `kwin_wayland --virtual … --exit-with-session=/usr/bin/startplasma-wayland`,
     but startplasma-wayland starts the systemd-managed Plasma session, whose
     plasma-kwin_wayland.service is a compositor of its own — which came up NESTED
     inside ours. The portal then captured the outer one, which had nothing on it,
     and streamed a healthy black framebuffer at full frame rate.

  2. OpenGL. KWin refuses to screencast a session that is not compositing with
     OpenGL, and its virtual backend only offers OpenGL when it finds a DRM device.
     A cloud VPS has one KMS-only device with no render node, so the session
     composited with QPainter and every stream request came back "Unsupported
     compositing type". vgem supplies the missing device; forcing Mesa's software
     path stops it dying on zink first.

Per AGENTS.md the assertions read the CODE with comments stripped, so the prose
above (and the script's own long comments) cannot satisfy a gate on its own.
"""

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = "system_files/usr/bin/moos-cloud-desktop"

errors: list[str] = []


def code_of(rel: str) -> str:
    path = ROOT / rel
    if not path.is_file():
        errors.append(f"{rel}: missing")
        return ""
    return "\n".join(
        line for line in path.read_text().splitlines()
        if not line.lstrip().startswith("#")
    )


code = code_of(SCRIPT)

if code:
    # ── 1. one compositor ────────────────────────────────────────────────────
    if "--exit-with-session=/usr/bin/startplasma-wayland" in code:
        errors.append(
            f"{SCRIPT}: starts a compositor of its own and hands it "
            "startplasma-wayland — that nests a SECOND compositor and the portal "
            "streams the empty outer one (black screen)"
        )

    if "plasma-kwin_wayland.service.d" not in code:
        errors.append(
            f"{SCRIPT}: no drop-in for plasma-kwin_wayland.service — the account's "
            "own compositor is what must be told to render to a virtual output"
        )

    # The wrapper, not kwin_wayland directly: the wrapper is what creates the
    # Wayland socket and publishes WAYLAND_DISPLAY into the systemd user
    # environment, which is how plasmashell, the portal and Mo PC Remote find the
    # session at all.
    virtual_exec = re.search(
        r"ExecStart=/usr/bin/kwin_wayland_wrapper[^\n]*--virtual", code
    )
    if not virtual_exec:
        errors.append(
            f"{SCRIPT}: the compositor drop-in must run kwin_wayland_wrapper with "
            "--virtual (the wrapper publishes WAYLAND_DISPLAY; kwin_wayland alone "
            "does not)"
        )

    # A pin at a compositor this command no longer creates is worse than no pin.
    if re.search(r"Environment=WAYLAND_DISPLAY=\$\{?socket", code):
        errors.append(
            f"{SCRIPT}: still pins Mo PC Remote at a per-user compositor socket "
            "that is no longer created"
        )

    # ── 2. OpenGL, or nothing streams ────────────────────────────────────────
    if "LIBGL_ALWAYS_SOFTWARE=1" not in code:
        errors.append(
            f"{SCRIPT}: the private compositor must force Mesa's software path — "
            "without it Mesa tries zink, EGL fails, KWin falls back to QPainter, "
            "and KWin will not screencast QPainter"
        )

    if "vgem" not in code:
        errors.append(
            f"{SCRIPT}: no render device is arranged — KWin's virtual backend only "
            "offers OpenGL when it finds a DRM device, and a VPS has none with a "
            "render node"
        )

    if "modules-load.d" not in code:
        errors.append(
            f"{SCRIPT}: vgem is loaded but not persisted — the desktop would go "
            "dark again on the next reboot"
        )

    # The udev rule must stay scoped to the dummy device. Widening it to the real
    # DRM device would hand one developer the other's framebuffer.
    for rule in re.findall(r'^SUBSYSTEM=="drm"[^\n]*', code, re.MULTILINE):
        if "/devices/faux/vgem/" not in rule:
            errors.append(
                f"{SCRIPT}: a drm udev rule is not scoped to the vgem device: "
                f"{rule.strip()!r} — card0's seat ACL is what keeps the two "
                "desktops apart"
            )

    # A session that leaves DISPLAY behind poisons the next one: Xwayland comes
    # back on a different number, the autostart apps read the dead one, and at
    # least one of them aborts loudly enough to fill the coredump cap.
    if not re.search(r"ExecStopPost=[^\n]*unset-environment[^\n]*DISPLAY", code):
        errors.append(
            f"{SCRIPT}: the session unit must clear DISPLAY/WAYLAND_DISPLAY when it "
            "stops — the user manager outlives the session and hands the stale "
            "value to the next one"
        )

    # ── 3. the portal grant ──────────────────────────────────────────────────
    if "PermissionStore" not in code:
        errors.append(
            f"{SCRIPT}: does not seed the RemoteDesktop portal grant — a headless "
            "session has nobody to answer the portal's dialog, and the only way to "
            "click it would be the remote that is asking for it"
        )

    # xdp_is_valid_token() requires D-Bus name characters ([A-Za-z0-9_]).
    # urlsafe_b64encode emits '-', and the portal answers "Restore token is not
    # valid" — which looks like a broken grant rather than a broken token.
    if "urlsafe_b64encode" in code:
        errors.append(
            f"{SCRIPT}: mints the restore token with urlsafe_b64encode — its '-' is "
            "not a D-Bus name character, so xdp_is_valid_token() rejects it"
        )
    if 'replace("+", "_")' not in code or 'replace("/", "_")' not in code:
        errors.append(
            f"{SCRIPT}: the restore token must be standard base64 with '+' and '/' "
            "aliased to '_', the way xdp_generate_token() mints them"
        )

    # The stored record is what the portal restores from: pointer|keyboard (3) and
    # screen sharing on. Getting these wrong yields a grant that restores into a
    # session with no input, which is exactly the failure that is hardest to see.
    if '"devices"' not in code or "quint(3)" not in code:
        errors.append(
            f"{SCRIPT}: the seeded grant must ask for devices=3 (pointer|keyboard)"
        )
    if '"screenShareEnabled"' not in code:
        errors.append(f"{SCRIPT}: the seeded grant must enable screen sharing")


if errors:
    print("FAIL: cloud private desktop gate")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)

print("OK: private desktop keeps one compositor, an OpenGL path, and its portal grant")
