# Linux input repair and operations

## Final architecture

The React PWA keeps one authenticated WebSocket. Input messages carry a monotonic sequence,
timestamp, mode, normalized coordinates (when applicable), viewport/DPR/orientation, rendered
content rectangle, video source dimensions, and display id. The server rejects stale, duplicate,
non-finite, out-of-range, wrong-display, or geometry-less packets.

On KDE Wayland the server uses the restored XDG RemoteDesktop portal session for pointer and
keyboard injection. The portal helper owns ordering and switches named keyboard groups through the
same event stream as the keys they qualify. ASCII and Arabic use real key positions. Unsupported
Unicode is grouped safely, written and read back exactly through Wayland, then pasted by one
synchronous shortcut; it is never silently replaced or dropped. The web server remains an
unprivileged user process. On disconnect, all tracked buttons and keys are released.

Direct mode maps the phone point within the actual rendered content rectangle to normalized
coordinates, then into KWin's logical virtual desktop geometry. Trackpad mode sends real relative
deltas and never warps to a synthetic absolute cursor. Obsolete browser move events are coalesced
by animation-frame scheduling; reliable button/key release messages are not coalesced.

Absolute targeting is sent through the RemoteDesktop portal in KWin's logical virtual-desktop
geometry. Relative Trackpad deltas remain relative and are never converted through an artificial
absolute cursor calibration.

## Services

- `mo-remote-personal.service` (user): unprivileged ASP.NET server after the graphical session,
  restart-on-failure, correct Wayland/DBus/runtime environment, and a sleep/idle inhibitor.
- `mo-remote-portal.py`: one restored RemoteDesktop + ScreenCast session, PipeWire video and
  ordered input. A one-second source keepalive plus a five-second progress watchdog restarts a
  starved portal instead of advertising a frozen picture as healthy.
- No login-manager or autologin change is required or installed.

## Install and operations

```sh
cd ~/Schreibtisch/MoPC
sh scripts/install-linux.sh
systemctl --user restart mo-remote-personal.service
systemctl --user stop mo-remote-personal.service
systemctl --user start mo-remote-personal.service
journalctl --user -u mo-remote-personal.service -f
sudo journalctl -u ydotool.service -f
```

## Verification commands

```sh
dotnet run --project tests/MoRemote.Tests/MoRemote.Tests.csproj -c Release
cd controller && npm test && npm run build
cd .. && dotnet run --project tests/VisualInputTest/VisualInputTest.csproj -c Release
```

## Security

- Network middleware remains loopback/Tailscale-only unless the owner explicitly enables LAN.
- PIN/Argon2 authentication remains mandatory; input is rejected before authentication.
- WebSocket origins whose host differs from the requested server host are rejected.
- Sequence/timestamp checks reduce replay and duplicate-event risk.
- No shell is used for input; numeric events are encoded into fixed binary records.
- The portal session grants only the selected screen and pointer/keyboard devices. The full server
  is never root.
- Clipboard content, tokens, PINs, and typed text are not logged.

## Rollback

The pre-repair source snapshot is:

`backups/mopc-source-before-input-repair-20260711-1500.tar.gz`

Stop the service, extract that archive into a separate directory, review it, then run its
`scripts/install-linux.sh`. The original SDDM file was also saved as
`backups/sddm-moos.conf.before-rollback`; current SDDM has no Mo Remote autologin section.

## User controls

- Trackpad (default): drag one finger to move relatively; tap to left-click; two-finger tap or
  long press to right-click; double tap to double-click; double-tap then drag to hold/drag; two
  fingers scroll horizontally/vertically.
- Direct: touch maps to the corresponding desktop point; drag holds the left button.
- Touch: tap targets directly and one-finger swipes scroll.
- Keys opens the phone keyboard. Shortcut buttons provide modifiers, clipboard shortcuts,
  arrows, Escape, Tab, and desktop shortcuts.
- Clipboard is explicit in both directions; text and PNG can be set or sent-and-pasted, and there
  is no background clipboard polling.

## Known limitation

KDE Wayland does not expose the greeter/locked desktop to this user-session capture process.
Remote control begins after the owner logs into Plasma. The active video path is already a
persistent PipeWire H.264 stream; the next architectural step is per-viewer WebRTC transport and
quality layers, not a return to screenshot-per-frame capture. See `MOOS_REMOTE_ARCHITECTURE.md`.

## Verification result (2026-07-11)

- 17 C# mapping, scaling, negative-origin, invalid-coordinate, sequence, stale-event and Unicode
  checks passed.
- Client portrait/landscape/letterbox/clamp/NaN tests passed; production PWA build passed.
- Linux and Windows agent builds passed with zero warnings/errors.
- Authenticated WebSocket integration sent direct, relative, button-down/up and key events through
  the running server and received an input-backend acknowledgement.
- Foreign WebSocket origin returned 403; unauthenticated WebSocket input was rejected; the
  temporary loopback diagnostic-token endpoint returned 404 after its test flag was removed.
- `libinput debug-events` observed real KWin events from the final backend: pointer motion plus
  `BTN_RIGHT pressed/released`. A real Meta event visibly opened Plasma's launcher. A real
  keyboard sequence opened Firefox, focused its address bar and entered `https://example.com`.
  The relative-calibration algorithm was compared against the official client and visibly opened
  Konsole's context menu at a non-corner location. Corner paths, slow/fast circles, scroll, drag press/release and Alt-Tab paths completed
  with a final release-all.
- Tailscale ping to the paired iPhone passed (8 ms at final check), and the phone had established
  authenticated sessions during the repair. A post-final-build hands-on phone gesture and the
  destructive reboot/Wi-Fi-loss tests still require the owner to perform/confirm them; they are not
  represented as completed here.
