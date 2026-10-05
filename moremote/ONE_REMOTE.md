# Mo PC Remote — one remote, v53

MoOS Liquid Glass remains the visual contract (`artwork/MOOS_UI2_DESIGN.md`). The phone uses the existing Graphite/Tidal semantic tokens, font stack, AR/EN translations, glass edges and reduced-motion rules. The native panel uses the shared `moos_ui2` theme. No second application, theme framework or icon family is introduced.

## Interaction specification

The primary dock has **Desktop · Touchpad · Keyboard · Settings**. It stays outside the streamed picture. Desktop keeps the existing touch/drag/physical-mouse choices; Touchpad is a dedicated relative surface and does not require a video frame. Keyboard uses the same authenticated connection and provides Enter, Tab, Esc and Alt+Tab. Settings retains display, clipboard, sound, files, power, sensitivity and device revocation. Pointer/scroll preferences apply in both workspaces. Touch targets are at least 44 px; the touchpad buttons are 48 px. Phone landscape and desktop use the existing reserved rail. Input workspaces keep their controls visible.

Only Desktop votes to receive video. Switching workspaces releases held input and retires the decoder. A hide/show transition permits the first fresh IDR request even when the previous request was recent. Password typing is masked, requires the host's explicit `secureText` capability, is never queued across an outage, and never uses a clipboard fallback. A locked host automatically requests that path. Characters unavailable on a loaded keyboard layout are refused before a partial word is entered.

## System implementation

Linux owns two independent helper processes: the combined PipeWire display portal for capture and a libei sender on KWin's native session EIS endpoint for input. Capture renewal therefore does not destroy the keyboard or mouse device that owns a press. EIS coordinates use KWin's logical region instead of encoded pixels. This implementation captures one output; first-login/pre-session access and arbitrary multi-monitor selection are not implemented by this change.

The capture helper runs in `app-org.moos.remote-<pid>.scope`, so KDE resolves the shipped desktop entry. The native panel has an explicit unattended-access switch. It reads, grants and revokes only `kde-authorized/remote-desktop/org.moos.remote`, verifies the result and recreates the capture session. It never grants the empty application ID. Remote PIN/trusted-device authentication, tailnet-only HTTPS and normal account/Polkit authentication stay in place. A stopped service stays stopped when consent changes.

## Evidence and handoff

On 2026-10-05, the production controller passed type checking, unit tests and real Chromium phone/desktop tests, including independent touchpad operation, hidden-page recovery, IME and live-only secret input. All .NET projects compiled and the Linux input/stream/private helper tests passed. A separate KWin, private bus/HOME/runtime and nonexistent fallback socket received a real mouse click and `native53` in a QLineEdit from the authenticated production browser while capture was forced to fail. A real private KWin lock left all native input devices ready; modifier release worked while locked. **PAM unlock was not attempted**, and no test drove the owner's uinput socket.

Screenshots and transcripts are in ignored `test-results/remote-system-20261005/`. The native Arabic panel and phone touchpad were rendered and inspected. The owner's workstation runs a backed-up local v53 review over the signed `.989` system; that is not a signed v53 OS release. Owner phone acceptance, password unlock, cellular endurance and signed artifact delivery remain release exit criteria (P2.14).
