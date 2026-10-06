# Mo PC Remote — one remote, v56 Glass Console

MoOS Liquid Glass remains the visual contract (`artwork/MOOS_UI2_DESIGN.md`). The phone uses the existing Graphite/Tidal semantic tokens, font stack, AR/EN translations, glass edges and reduced-motion rules. The native panel uses the shared `moos_ui2` theme. No second application, theme framework or icon family is introduced.

## Interaction specification (v56, Glass Console)

One permanent dock, outside the picture: a **connection orb** (state and round trip; it opens
Picture settings), the **mode switch** — **Touch** (the screen behaves as a touchscreen),
**Trackpad** (a relative pointer, like a laptop trackpad) and **Mouse & keys** (a real mouse and
keyboard, nothing interpreted) — and **Keyboard · MoOS · Transfer · Settings**. On a portrait phone
it is a two-row bottom dock in the band a 16:9 picture leaves empty; on a computer, a wide
landscape window or a phone on its side it is a side rail (`POINTER_BAR_QUERY`, then the
short-landscape rule, which wins). It is a sibling grid track of the stage and never hides: the
old auto-hiding bar kept its track reserved anyway, so hiding bought no pixels and added a
"Controls" handle to learn. Every target is at least 44 px.

Trackpad on a portrait phone lifts the picture to the top of the stage (`fitTop`) and outlines
the empty half as the pad (`placePadZone`, decoration only — the canvas owns the finger), so the
thumb never covers what it points at. **Pad only** (Settings ▸ Control, Trackpad) suspends video
for a computer whose own screen is in front of you and keeps left/right buttons and a way back.
Touch keeps its one-finger-drag switch. Mouse & keys keeps pointer lock, keyboard lock in
fullscreen and the ordered Ctrl/Cmd+V bridge.

**MoOS** opens the desktop's own commands as tiles: launcher (Meta), Mira (Meta+Space), search
(Alt+Space), Overview (Meta+W), show desktop, files, terminal, system settings, system monitor,
clipboard history, emoji, maximize/minimize/tile, previous/next desktop, close window, volume and
media keys, screenshot and region capture, then the confirmed power actions. The shortcuts were
read back from a running MoOS session; a Windows agent (`input.backend` "Win32 SendInput") gets
the Windows equivalents. Media and Print keys travel as physical codes (`keyTapCode`) through the
agents' existing `KeyTapCode`. `tests/host-actions.test.ts` parses both agents' key tables and
fails any tile they cannot press. No tile runs a command; each is a keystroke.

**Settings** has three tabs. *Picture*: a live readout (encoded size, frame rate, codec, round
trip, the H.264 budget), Auto or a resolution card with what it can cost (`estimateMbps`, the
helper's own `h264_bitrate_bps`), an independent frame rate (preset / 30 / 60, `effectiveFps`;
the weak-link rung still wins while Auto relieves a collapsing link), fit/100 %, zoom, the
rotation lock, monitor, sound and fullscreen. *Control*: the three modes explained, each mode's
own option, pointer and scroll speed, natural scroll, haptics, magnify while typing. *General*:
language, background alerts, trusted devices, refresh/disconnect and the version.

The **keyboard panel** puts two rows of PC keys above the phone's own keyboard: password typing,
one-shot Ctrl/Alt/Shift/Meta, Esc, Tab, arrows, Home/End/PgUp/PgDn/Del; copy to and paste from
this device, select all, undo, redo, cut, F1–F12. **Transfer** holds clipboard (both directions,
text and images) and files.

Every mode keeps the real screen while typing; only Pad only suspends video. Opening the phone keyboard keeps the picture above the typing controls. Switching modes releases held input. A hide/show transition permits the first fresh IDR request even when the previous request was recent. Password typing is masked, requires the host's explicit `secureText` capability, is never queued across an outage, and never uses a clipboard fallback, including when pasting from the phone. A locked host automatically requests that path, prepares the normal password prompt with a non-printing key, and explains how to enter the account password if the compositor hides its picture. Characters unavailable on a loaded keyboard layout are refused before a partial word is entered.

Auto starts conservatively on a phone without browser network information. Four fresh samples at up to 90 ms RTT and successful recent picture decoding permit one bounded detail trial; zoom/actual-size view can earn Sharp. Data Saver, a weak device and the host encode budget remain ceilings. Stale pongs, delayed decoding and congestion retire the trial. Explicit quality selections remain explicit. A successful ping is not a bandwidth estimate.

## System implementation

Linux owns two independent helper processes: the combined PipeWire display portal for capture and a libei sender on KWin's native session EIS endpoint for input. Capture renewal therefore does not destroy the keyboard or mouse device that owns a press. EIS coordinates use KWin's logical region instead of encoded pixels. This implementation captures one output; first-login/pre-session access and arbitrary multi-monitor selection are not implemented by this change.

The capture helper runs in `app-org.moos.remote-<pid>.scope`, so KDE resolves the shipped desktop entry. The native panel has an explicit unattended-access switch. It reads, grants and revokes only `kde-authorized/remote-desktop/org.moos.remote`, verifies the result and recreates the capture session. It never grants the empty application ID. Remote PIN/trusted-device authentication, tailnet-only HTTPS and normal account/Polkit authentication stay in place. A stopped service stays stopped when consent changes.

## Evidence and handoff

**v56 (2026-10-06, source, Oracle A1):** the view was replaced and the session engine kept. The
controller typecheck, the complete unit chain (including the new quick-action key-table gate,
which was proven to fail on an invented key) and the real-Chromium end-to-end test pass on the
production bundle: every v55 behaviour it covered plus the pad zone, MoOS and Windows commands,
the frame-rate choice and one-shot modifiers. Arabic/English, dark/light, 320 px to 1366 px,
portrait/landscape and desktop were rendered and reviewed from the shipped bundle with an
intercepted transport. Two `vite build` runs from the lockfile are byte-identical. Not yet:
owner iPhone acceptance of the new interface, a signed delivery, and use on a live session —
the A1's Remote is the owner's screen and was not touched.

**v55:**

On 2026-10-05, the production controller passed type checking, unit tests and real Chromium phone/desktop tests, including independent touchpad operation, hidden-page recovery, IME, live-only secret input and the actual settings wire for 6 ms direct, healthy 60 ms relay-shaped and congested 180 ms fixtures. All .NET projects compiled and the Linux input/stream/private helper tests passed. A separate KWin, private bus/HOME/runtime and nonexistent fallback socket received a real mouse click and `native53` in a QLineEdit from the authenticated production browser while capture was forced to fail. Native devices remained ready while locked.

A disposable KVM guest booted the exact SHA-256-checked signed NVIDIA QCOW2 from run `37269952260` (base revision `3dc45b3e`, read-only backing disk). Ordinary PAM login and authenticated SSH provisioned only its private review payload. The authenticated production phone controller drove a real GTK entry while decoded desktop pixels remained visible (40.3% nonblack pixels), and later captured the actual lock screen. Early password attempts were inconsistent: tight native batches lost uppercase modifiers in the greeter, while GTK received the same text correctly. A libei ping, modifier-only 4 ms and full 12 ms pacing did not establish reliable unlock. Sensitive native input now prepares the prompt and spaces key edges by 40 ms; ordinary typing keeps its existing fast path. Five consecutive password unlocks passed after a six-second wait beyond the greeter grace interval, with the guest still locked immediately before typing; an incorrect password stayed locked. PAM and account policy were unchanged, the fallback socket was absent, and no test used the owner's password or uinput socket. Final source payload hashes and repeat transcripts are retained in the ignored evidence directory. This is runtime evidence on a signed base with a local app review, not a signed v55 OS release.

Screenshots and transcripts are in ignored `test-results/remote-system-20261005/`. The native Arabic panel, phone touchpad and real guest typing were rendered and inspected. The owner's workstation serves backed-up local v55 web and native input assets and signed `.989` system; that is not a signed v55 OS release. Owner iPhone acceptance, cellular endurance, the physical display/portal loss cause and signed artifact delivery remain release exit criteria (P2.14). Tailscale's current iPhone peer address is direct LAN; a relay indicator alone is not evidence that the active connection is relayed.

## Product references

The implementation retains the existing gesture vocabulary described by [Chrome Remote Desktop for iOS](https://support.google.com/chrome/answer/1649523?co=GENIE.Platform%3DiOS&hl=en), adds separate workspaces on the same authenticated wire, and keeps the picture while typing. [TeamViewer's toolbar](https://www.teamviewer.com/en-us/global/support/knowledge-base/teamviewer-remote/remote-control/remote-session-toolbar/) informed the explicit speed/quality and fit/actual-size choices. [RustDesk's settings](https://rustdesk.com/docs/en/self-host/client-configuration/advanced-settings/) informed the bounded quality feedback and visible input capability. These are implemented product patterns, not a merger or dependency on those programs. [Tailscale connection types](https://tailscale.com/docs/reference/connection-types) explains the direct/relay distinction used in the diagnostics.
