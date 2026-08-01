# Mo PC Remote test report — 2026-07-12

## Executed

- Located and audited both source trees.
- Confirmed desktop launcher path and reproduced its explicit external-browser behavior from source.
- Confirmed legacy backend HTTP status on localhost and listener on TCP 8765.
- Confirmed capture failure from journal: Spectacle/XCB display failure and coredump.
- Confirmed Wayland session, PipeWire, portal, Avahi, firewalld, SELinux enforcing, uinput ACL and private ydotool socket.
- Confirmed Android-class device is visible on LAN through mDNS/ADB, but no authorized physical-phone interaction was performed.
- Native GTK application launched through the real desktop entry on KDE Wayland and registered `org.moos.MoPCRemote`; it did not launch a browser.
- Built the React controller and .NET Linux agent with zero warnings/errors; controller and 17 backend tests passed.
- Repeated in the source-image integration pass using the exact .NET 10 SDK
  container stage; build completed with zero warnings/errors and all 17 tests
  passed. The controller coordinate/orientation suite passed on Node 24.
- Opened an authenticated WebSocket against the rebuilt desktop source, received a real 525,900-byte JPEG frame at 3840x2160, received pong and confirmed the KDE portal + ydotool input backend.
- Visible pointer/click/right-click/drag/scroll/shortcut paths passed on the live Plasma desktop.
- Installed the official Sunshine v2026.516.143833 AppImage for a non-root runtime test after verifying SHA-256 `d0ee0a...c7a2`.
- Sunshine successfully used KWin ScreenCast + PipeWire at 3840x2160, requested 60 fps, initialized libx264 H.264, advertised `_nvstream._tcp`, and listened on the expected GameStream ports.
- A real Tailscale ping to the connected iPhone measured 86 ms.

## Not passed / not claimed

- A real Moonlight client paired successfully (`/api/pin` returned `status:true`) and its certificate-backed identity was stored in Sunshine's trusted-device state.
- Two real `Desktop` streaming sessions connected. Sunshine captured the 3840x2160 KWin output through PipeWire, accepted a 60 fps request, encoded H.264 at 7.308 Mbps with a ~30 fps minimum target, and streamed Opus 48 kHz stereo at 96 kbps LOWDELAY. The first session lasted about 10 seconds and the reconnect test also succeeded.
- The connected client is the user's mobile Moonlight client; host-side logs do not expose whether it is Android or iOS, so Android-specific attribution is not claimed.
- The legacy frame path measured 868 ms RTT and is rejected for production. Sunshine end-to-end latency is not printed by the host; Tailscale RTT to the previously visible mobile peer measured 86 ms.
- Unicode text injection is still under investigation: clipboard transport works, but the automated focus-sensitive paste test did not produce the expected file.
- A full MoOS image build was attempted twice. The Mo PC Remote image gate passed after updating the renamed-launcher assertion, but the build later failed in the pre-existing Anaconda package transaction (`cockpit-ws-selinux` followed by rpm transaction failures), before producing an ISO. ISO/live/install/reboot therefore remain unpassed.

Therefore the full success definition is **not yet met**. The truthful current milestone is: native control-center launcher and diagnosed legacy stack, with production streaming architecture selected.
