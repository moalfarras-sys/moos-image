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
   flat. So the bind is loopback. That is not a preference to be tidied away later; it is the
   reason (1) is safe.

3. AND THE ROUTE THIS FILE ORIGINALLY PRESCRIBED WAS THE THIRD FAILURE. The sentence here used to
   read "the bind is loopback and `tailscale serve` is the only route in", and mo-pc-remote duly
   published the service with `tailscale serve --set-path=/audio`. But `tailscale serve`
   re-publishes a loopback socket to the WHOLE TAILNET, and this service still has no
   authentication — so "only reachable via loopback" quietly became "reachable, unauthenticated, by
   every device on the tailnet". Measured on the maintainer's machine on 2026-07-29:

       $ curl -o /dev/null -w '%{http_code}' https://<host>/api/login  -X POST -d '{"pin":"000000"}'
       401
       $ curl -o /dev/null -w '%{http_code}' https://<host>/audio/stream.webm
       200                                    <- a live Opus stream of everything the machine plays

   Loopback was never the security boundary. AUTHENTICATION is, and this service has none, so it
   must sit behind something that does. The sound now travels the agent's own authenticated route,
   /api/audio/stream.webm, which is covered by tests/test_remote_audio_is_authenticated.py.

The three must therefore be checked together: a future edit that "simplifies" the host back to
0.0.0.0 has to fail here rather than on somebody's network, and one that re-publishes this service
as its own tailnet mount has to fail in the audio-authentication gate.
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
                      f"        reached only through the agent's authenticated /api/audio/stream.webm route.")

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

    # --- 3. the panel must RETRACT the legacy mount, never create it -------------------------
    #
    # This block used to require the opposite: that `mount_audio` existed and was called at least
    # twice, so the /audio mount would "self-heal" on every panel open. That requirement was the
    # bug — see (3) in the module docstring — and the check outlived it by accident, because
    # `mount_audio` is a SUBSTRING of `unmount_audio`. Both `"mount_audio" in panel` and
    # `panel.count("mount_audio(")` matched the new, correct code and reported green while
    # asserting the old, wrong contract. A word boundary is the difference between a gate and a
    # coincidence.
    if re.search(r"\bmount_audio\s*\(", panel):
        errors.append("mo-pc-remote still defines or calls mount_audio() — publishing an\n"
                      "        unauthenticated service to the tailnet. The sound goes through the agent's\n"
                      "        authenticated /api/audio/stream.webm route now.")
    if not re.search(r"\bunmount_audio\s*\(", panel):
        errors.append("mo-pc-remote no longer retracts the legacy /audio mount. A machine that was\n"
                      "        exposed once stays exposed until something takes it down, and opening the\n"
                      "        panel is that something.")

    if errors:
        print("GATE FAIL: the desktop's sound is unreachable, or reachable by the wrong people.\n")
        for e in errors:
            print(f"  - {e}")
        return 1

    print(f"OK: audio binds {m.group(1)} (no auth of its own, so loopback only), enabled for every "
          f"edition, and the panel retracts the legacy unauthenticated /audio mount")
    return 0


if __name__ == "__main__":
    sys.exit(main())
