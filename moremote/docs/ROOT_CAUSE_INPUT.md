# Mo Remote input failure: root-cause report

Date: 2026-07-11

## Inspected architecture

- Linux server: ASP.NET Core/.NET 10 (`agent-linux/Program.cs`) on TCP 8765.
- Mobile client: React/TypeScript PWA (`controller/`).
- Transport: authenticated WebSocket `/ws`; JPEG frames are binary messages and input is JSON.
- Capture: a KDE Spectacle fullscreen PNG per frame, converted to JPEG by ImageSharp.
- Input: persistent system `ydotoold` owning one uinput device; the server previously launched a
  separate `ydotool` client process for every event.
- Clipboard: `wl-copy`/`wl-paste`.
- Runtime: KDE Plasma/KWin 6.7.2, Wayland, Fedora 44/MoOS.

## Reproduced system geometry

- Physical capture/mode: 3840x2160.
- KDE scale: 2.75.
- KWin logical desktop: 1397x786.
- Rotation: normal.
- Current outputs: one enabled HDMI-A-1 output at origin 0,0.
- `ydotoold virtual device` advertises relative motion capabilities (`capabilities/rel=147`) and
  no absolute axes (`capabilities/abs=0`). Its `mousemove --absolute` implementation therefore
  expects compositor/logical desktop coordinates, not an EV_ABS 0..65535 coordinate.

## Confirmed root causes

1. **Physical/logical coordinate mismatch.** The video is 3840x2160 physical pixels while KWin
   input coordinates are 1397x786 logical pixels. Mapping normalized phone input to the capture
   dimensions overshoots by 2.75x and drives/clamps the pointer against an edge/corner.
2. **Incorrect attempted 0..65535 repair.** The installed ydotool virtual device has no ABS axes.
   Scaling normalized coordinates to 65535 is invalid for this backend and sends the pointer to an
   edge. Official ydotool usage also describes `mousemove --absolute -x 100 -y 100` in desktop
   coordinates.
3. **ydotool's absolute reset is incompatible with this KWin setup.** `mousemove --absolute`
   first emits `REL_X/REL_Y = INT32_MIN`. Visible reproduction showed this triggering KWin's
   top-left screen edge/Overview and leaving the pointer at the corner. The repair no longer emits
   that sentinel: it uses bounded relative calibration from the bottom-right plus tracked deltas.
4. **Broken button syntax in the original Linux injector.** Button hold/release was formatted as
   strings such as `0x40|0`, while ydotool requires combined numeric codes (`0x40`, `0x80`,
   `0x41`, etc.). This broke drag and click-and-hold.
5. **Unordered per-event processes.** Mouse move and click were separate un-awaited processes, so
   a click could execute before the move. High-rate phone movement also caused process churn,
   lag, and obsolete events.
6. **Trackpad was not relative.** The client maintained its own normalized virtual cursor and sent
   absolute `move` messages. It did not continue from the actual desktop cursor position and could
   desynchronize after local mouse use or reconnect.
7. **Protocol lacked delivery metadata and validation.** Input packets had no sequence number,
   timestamp, display id, mode, viewport, content rectangle, or source dimensions. The server did
   not reject NaN/infinite/stale/duplicate events and could not diagnose phone-side mapping.
8. **No release recovery.** Disconnecting during a drag or modifier key press could leave a
   logical button/key held. Button-up and key-up had no dedicated reliability treatment.
9. **Misleading health state.** The UI marked the session connected after WebSocket/video hello,
   without independently proving that the input backend and clipboard were ready.

## Contributing issues

- The user service initially lacked Wayland/DBus environment variables, causing Spectacle to fall
  back to XCB and fail. This is separate from input but made the UI report the desktop as locked.
- Repeated Spectacle processes are expensive and limit video smoothness. Receive and input can be
  made independent, but capture remains a performance limitation.
- Multi-monitor metadata in the Linux implementation was a single synthetic full-desktop entry;
  physical and logical per-output geometries were not represented.

## Security/runtime facts

- `/dev/uinput` is mode 0660 root:root with an ACL granting only user `mo` read/write.
- `/tmp/.ydotool_socket` is mode 0660 and owned by `mo:mo`; it is not world writable.
- The full remote server runs as user `mo`, not root.
- Network middleware permits loopback/Tailscale by default and PIN-authenticates WebSocket input.
- SDDM autologin is not required for correct operation and has been removed.

This report is the pre-implementation baseline. Final architecture and verification results are
documented in `docs/INPUT_REPAIR.md`.
