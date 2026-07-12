# Mo PC Remote audit — 2026-07-12

## Scope

Audited `~/Schreibtisch/MoPC` (12,775 files, 785 MiB) and the 94-file image copy in `moremote/`. Vendor/build trees (`node_modules`, `bin`, `obj`, `dist*`) were inventoried and identified by type; all authored source, manifests, launchers, units, scripts and image integration were reviewed.

## What exists

- Windows agent: C#/.NET 10 WinForms/ASP.NET with DXGI/GDI capture.
- Linux agent: C#/.NET 10 ASP.NET server, React/Vite PWA, WebSocket JPEG frames, Spectacle capture, KDE RemoteDesktop portal plus private ydotool/uinput fallback.
- Controller: responsive React PWA. This is a web application, not Electron, Tauri or native Android.
- Image integration: source is built in a .NET SDK container and copied to `/usr/lib/mo-remote`; user units, udev rule and desktop entry are shipped in `system_files`.

## Confirmed root causes

1. The icon opened Firefox because `org.moos.remote.desktop` executed `moos-open moos://app/remote`, whose exact action was `xdg-open http://127.0.0.1:8765/`. CompataHub documented the same browser command.
2. Linux capture was broken: the running unit lacked `WAYLAND_DISPLAY` and `QT_QPA_PLATFORM`; journal logs show every Spectacle child selecting XCB, reporting `could not connect to display`, then coredumping.
3. The apparent locked-screen UI is the controller's explicit `PC is locked` fallback when capture returns unavailable. It was copied from Windows assumptions. On this machine capture was unavailable because Spectacle crashed, not because the current KDE session was locked.
4. Even repaired, capture is PNG screenshots re-encoded as JPEG and pushed over WebSocket (default 8 FPS in Linux config). It is not PipeWire, WebRTC or adaptive video and cannot meet the requested latency/1080p/4K target.
5. Kestrel used `ListenAnyIP`; application middleware blocks LAN unless `AllowLan`, but the socket is still visible on all interfaces. The FedoraWorkstation firewall zone currently allows all high TCP/UDP ports, so it does not provide a narrow Mo Remote boundary.
6. Authentication is a six-or-more digit PIN hashed with Argon2id, token lockout and short-lived bearer sessions. It has no QR pairing approval, persistent trusted-device identities or device revoke list.

## Host audit

- Fedora Atomic MoOS 44, KDE Plasma Wayland.
- LAN `192.168.3.40/24`; Tailscale also active. Avahi and KDE Connect discovery work.
- PipeWire 1.6.8, WirePlumber and portal are active; KDE portal package is installed.
- `/dev/uinput` stays root/input and receives an ACL only for the active local user through `TAG+=uaccess`; ydotool uses a mode-0600 user-runtime socket.
- SELinux is enforcing. No disabling or broad policy exception is justified.
- RTX 2080 Super currently uses nouveau. VA-API initialization fails; reliable NVENC requires the NVIDIA image/driver.
- Existing `krdp`, `krfb`, KDE Connect, FFmpeg and GStreamer are installed. Sunshine/RustDesk/wayvnc are not installed.

## Immediate remediation

The launcher now opens the native GTK `mo-pc-remote` control center. The legacy service is disabled by default in new images and opens only when the user presses Start. The service receives its Wayland variables. The legacy server remains clearly labelled diagnostic-only until the streaming backend is replaced.
