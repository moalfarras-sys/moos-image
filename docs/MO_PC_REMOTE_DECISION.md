# Mo PC Remote technical decision

## Comparison

| Option | KDE Wayland | Video/latency | Android touch | Security/operations | Decision |
|---|---|---|---|---|---|
| RustDesk | Experimental Wayland; no Wayland login screen | Good remote-desktop transport | Native client | Self-hosting adds server/relay maintenance | Reject as MoOS default |
| Sunshine + Moonlight | Native `kwin` capture in current Sunshine; KMS fallback | Best fit: GameStream, adaptive bitrate, H.264/HEVC/AV1, HW encode | Mature native Android/iOS client, touch/gamepad | PIN pairing, certificates; LAN-local possible | **Selected streaming stack** |
| Custom WebRTC | PipeWire is possible | Can be excellent | Custom UX possible | Largest security, codec and maintenance burden | Reject for v1 |
| KDE Connect | Excellent Wayland input/media | No desktop video/virtual display on Android | Excellent touchpad/keyboard/media | Mature pairing and narrow ports | Keep as companion/fallback |
| wayvnc | Upstream explicitly excludes KDE | VNC is weaker than GameStream | Client-dependent | TLS possible | Incompatible |

## Decision

Use a native MoOS control center as the system UI, Sunshine as the eventual streaming host, and Moonlight as the Android-first client. Retain KDE Connect for media/commands and emergency input. Do not grant Sunshine `cap_sys_admin`; use its KDE/KWin capture backend. If KWin capture is unavailable, fail visibly rather than silently adding near-root KMS capability.

The old ASP.NET/PWA server is retained only as a diagnostic fallback during migration. It is not represented as production-quality streaming.

## Hardware note

The generic MoOS image must support software/Vulkan fallback. The MoOS NVIDIA image is the supported route for NVENC on this host. Codec availability reported by FFmpeg does not prove that an encoder works; the current nouveau VA-API test fails.
