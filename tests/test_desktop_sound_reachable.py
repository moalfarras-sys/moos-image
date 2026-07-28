#!/usr/bin/env python3
"""Gate: the desktop's own sound reaches the phone, and reaches nobody else.

TWO FAILURES, POINTING IN OPPOSITE DIRECTIONS

1. IT DID NOT WORK AT ALL ON A DESKTOP. `systemctl --global enable moos-cloud-audio.service` lived
   inside build.sh's cloud-only branch, so the desktop editions shipped the binary and the unit and
   never started either. Measured on a MoOS desktop:

       $ systemctl --user is-enabled moos-cloud-audio.service   -> disabled
       $ ss -tnl | grep 8775                                    -> (nothing)
       $ tailscale serve status                                 -> only  / -> 8765
       $ curl https://<host>/audio/stream.webm                  -> 404

   So the Sound button in Mo PC Remote worked on a headless VPS and did nothing on the desktop the
   owner actually sits at. It failed the way a missing feature fails — silently — rather than the
   way a broken one does, which is why it survived.

2. AND ENABLING IT NAIVELY WOULD HAVE BEEN WORSE. This service has NO authentication: no PIN, no
   token, no session. Whoever opens the socket hears everything the machine is playing. It used to
   bind 0.0.0.0, which was defensible on the cloud edition — FedoraServer zone, ssh only, just
   tailscale0 trusted. A desktop runs FedoraWorkstation:

       $ firewall-cmd --list-ports
       1025-65535/tcp 1025-65535/udp

   Every port above 1024 is open to the local network by design. A wildcard bind plus the enable in
   (1) publishes unauthenticated live audio to every device on the WiFi — a café, a hotel, a shared
   flat. So the bind is loopback and `tailscale serve` is the only route in. That is not a
   preference to be tidied away later; it is the reason (1) is safe.

The two must therefore be checked together, and a future edit that "simplifies" the host back to
0.0.0.0 has to fail here rather than on somebody's network.
"""

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
AUDIO = ROOT / "system_files/usr/bin/moos-cloud-audio"
BUILD = ROOT / "build_files/build.sh"
PANEL = ROOT / "system_files/usr/bin/mo-pc-remote"
UNIT = ROOT / "system_files/usr/lib/systemd/user/moos-cloud-audio.service"


def main() -> int:
    for f in (AUDIO, BUILD, PANEL, UNIT):
        if not f.is_file():
            print(f"GATE FAIL: {f.relative_to(ROOT)} is missing.")
            return 1

    audio = AUDIO.read_text(encoding="utf-8")
    build = BUILD.read_text(encoding="utf-8")
    panel = PANEL.read_text(encoding="utf-8")
    errors: list[str] = []

    # --- 1. it must not bind a wildcard address ---------------------------------------------
    m = re.search(r'^HOST\s*=\s*os\.environ\.get\(\s*"MOOS_AUDIO_HOST"\s*,\s*"([^"]+)"\s*\)',
                  audio, re.M)
    if not m:
        errors.append("cannot find the HOST default in moos-cloud-audio — if the bind address is no\n"
                      "        longer a single reviewable line, this gate cannot protect it.")
    elif m.group(1) not in ("127.0.0.1", "localhost", "::1"):
        errors.append(f"moos-cloud-audio binds '{m.group(1)}' by default. The service has NO\n"
                      f"        authentication, and a desktop's FedoraWorkstation firewall zone opens\n"
                      f"        1025-65535/tcp to the local network — so this publishes unauthenticated\n"
                      f"        live audio to every device on the WiFi. It must bind loopback and be\n"
                      f"        reached through `tailscale serve --set-path=/audio`.")

    # --- 2. it must be enabled for EVERY edition, not only cloud -----------------------------
    if "systemctl --global enable moos-cloud-audio.service" not in build:
        errors.append("build.sh never enables moos-cloud-audio, so the unit ships and no account ever\n"
                      "        runs it — the Sound button answers 404 with nothing to explain why.")
    else:
        # The cloud-only branch is `if [ "${MOOS_IMAGE_NAME:-moos}" = "moos-cloud" ]`. The enable
        # must not be inside one: that is exactly the bug this file documents.
        idx = build.index("systemctl --global enable moos-cloud-audio.service")
        before = build[:idx]
        # Count unclosed cloud-edition guards before the enable.
        opens = len(re.findall(r'if \[ "\$\{MOOS_IMAGE_NAME:-moos\}" = "moos-cloud" \]', before))
        closes = len(re.findall(r"^fi$", before, re.M))
        if opens > 0 and closes < opens:
            errors.append("the enable sits inside a cloud-edition-only branch again. That is the original\n"
                          "        defect: sound works on the VPS and is silently absent on the desktop.")

    # --- 3. the /audio mount must self-heal --------------------------------------------------
    if "mount_audio" not in panel:
        errors.append("mo-pc-remote has no mount_audio at all.")
    elif panel.count("mount_audio(") < 2:
        errors.append("mount_audio is called only once — from the first-run 'Enable access from\n"
                      "        anywhere' path. Every machine whose serve was set up before that code, or\n"
                      "        by hand, has a desktop mount and no sound mount, forever. The panel must\n"
                      "        re-assert it (tailscale serve is idempotent) so opening it repairs the box.")

    if errors:
        print("GATE FAIL: the desktop's sound is unreachable, or reachable by the wrong people.\n")
        for e in errors:
            print(f"  - {e}")
        return 1

    print(f"OK: audio binds {m.group(1)} (no auth, so loopback only), enabled for every edition, "
          f"and the /audio mount self-heals")
    return 0


if __name__ == "__main__":
    sys.exit(main())
