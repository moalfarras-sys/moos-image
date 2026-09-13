# Oracle Remote input and release checkpoint

Worktree: `moos-remote-oracle`, branch `feat/remote-oracle-experience-20260912`.
This continues the owner's Oracle desktop work without modifying the parallel
`moos-remote-ui` or `moos-verify` checkouts. No local VM or system backup was made.

## Source integration

The branch contains `main` through `84a8108c` (including #85, #86 and #87),
the Remote follow-up `2f47ad92`, and release #91 through `d2688109` (including #88/#89/#90).
The earlier local search repair from `fix/system-search-20260912` is ported here.
That older worktree is retained; its uncommitted files were not reset or discarded.

## Input changes

Ordinary desktop text uses the character chosen by the viewer's keyboard layout.
US-position heuristics cannot establish the host's active layout after Arabic
typing. Navigation and Ctrl/Alt/Meta shortcuts retain physical key positions;
explicit pointer lock retains held game keys. A desktop textarea receives native
IME commits while local dialogs and controls retain their own focus.

Shift is suspended while committing exact text, restored before selection keys,
mouse presses and wheel input, and released even when an IME is composing.
AltGr's synthetic Control is released before its character. Local Caps Lock
controls local text case rather than toggling the remote lock a second time.

The Linux injector reads KWin's lock state over a short, read-only Wayland
connection using the version-1
[KDE keystate protocol](https://github.com/KDE/plasma-wayland-protocols/blob/master/src/protocols/keystate.xml).
It creates no surface and never toggles a lock. Locked, unsupported, malformed
or timed-out state uses the existing exact clipboard paste for the whole commit.
Connect/read deadlines and message bounds prevent an unavailable compositor
from blocking the input queue indefinitely. Live Oracle readback returned
`CAPS_LOCK=False`; isolated socket fixtures prove unlocked, latched, locked,
unknown, malformed, absent and stalled compositor responses.

The phone handles `beforeinput: deleteContentBackward` when Android emits
Process/229 without a usable Backspace key event. Deletion of an empty local
typing context still reaches existing remote text, including a selected Ctrl
modifier. The bilingual typing bar names MoOS and explains that the device's
keyboard language is used; reconnecting keeps the draft local until authentication.

Compatibility limit: clipboard-backed input leaves the committed text in the
remote clipboard, as the existing Unicode path does. Restoring an old clipboard
on a timer would race the receiving application. Native EIS text negotiation is
still future work; installed libei version alone does not establish that path.

## Visual and executable evidence

The production bundle was rebuilt and exercised in native ARM Chromium, with
all API and WebSocket traffic intercepted. These tests cannot type into the
owner's active apps. The fixture desktop is the existing tracked Remote capture,
not evidence of a new signed deployment.

- [Arabic typing, light](evidence/remote-oracle-20260912/after/keyboard-light-ar.png)
- [Arabic typing, dark](evidence/remote-oracle-20260912/after/keyboard-dark-ar.png)
- [Landscape control](evidence/remote-oracle-20260912/after/phone-landscape-ar.png)

The typing header's measured RGB is (52,63,69) against the adjacent dark
(35,45,50), and (178,209,203) against light (225,240,236). Both exceed the
design plan's 15-level weighted luminance separation. Arabic labels, input,
44px controls and the Done button remain visible. Headless viewport emulation
does not prove a physical iPhone or Android keyboard's complete behavior.

Completed before integration of the newer boot fixes:

- Controller typecheck, all unit suites (20 desktop cases), production build.
- Full Chromium suite: Unicode, Arabic composition, native desktop IME commit,
  mobile deletion, clipboard failures, reconnect drafts, touch/trackpad, wheel
  direction, rotation, modal focus and keyboard viewport geometry.
- All seven .NET projects compile; all four test executables pass, including
  27 Linux input/lock-state assertions.
- 145 workflow source checks: 143 passed initially; device architecture and
  free-provider fixtures passed after isolation. Main subsequently supplied
  equivalent isolation; its versions were retained in the integration.

Reproduction uses the existing browser rather than installing another copy:

```sh
cd moremote/controller
npm run typecheck
npm test
npm run build
MO_REMOTE_CHROME=/path/to/native/chrome \
MO_REMOTE_PLAYWRIGHT=/path/to/playwright npm run test:browser
```

Build the PWA before .NET: .NET consumes the generated static assets, so these
two builds must not run concurrently while Vite replaces their hashed files.

## Search repair

Baloo reads `only basic indexing` from `[General]`, not `[Basic Settings]`.
The policy and fallback reader now use the real section. Diagnostics compare
`balooctl6 config list contentIndexing` with the visual-tier budget rather than
requiring content extraction on an essential-tier cloud machine. The fixture
uses isolated real KConfig/Baloo readback when those tools exist.

The earlier live repair enabled filename search: Baloo reported Idle, 25,077
indexed files, no queued/failed files, and a real filename query returned results.
The source repair still needs the signed image; no user override counts as one.

## ARM release blocker and ordered completion

The #89 manual build `34717090843` produced an image, but its first boot failed.
Its diagnostics prove zram activated successfully, then hardware adaptation
exhausted its 90-second service timeout: 14.696s CPU, 90.114s wall clock.
The fwupd timer enable alone took 31 seconds because it reloaded all units.

This branch keeps #89's first-boot zram fix, avoids that unnecessary reload
(`enable --no-reload` still enables the timer for subsequent boots), and gives
the post-desktop service the integration branch's finite 10-minute deadline.
That branch already passed an ARM boot proof on `ff7bb39c`; later review fixes
changed its revision, so the combined source still needs its own proof. The ARM runtime gate
now waits for the timer's actual oneshot completion, requiring active/success/0;
an empty failed-unit list before the timer runs can no longer qualify a disk.
The lifecycle gate executes delayed-success, failure, bad-exit and never-started
fixtures against that exact acceptance block.

Remaining sequence:

1. Re-run integrated gates and the local ARM build after absorbing #91. The
   earlier `4e7c5bb6` build passed all image gates and `bootc container lint`;
   its container contained the new PWA and effective Baloo section.
2. Publish this branch, review it, and run the signed ARM candidate and exact
   disk/boot proof. Earlier failed runs do not qualify the changed source.
3. Merge only after release acceptance; verify the promoted immutable ARM digest
   and revision before `moai-do update` stages it on Oracle.
4. Verify booted version, services, Remote, search and actual app input after reboot.
5. Complete physical Android/iOS keyboard and Caps Lock app readback, and the
   multiple-viewer H.264 recovery work documented in `REMOTE_V40_CLOUD_DESKTOP.md`.

The Oracle host last audited was signed `44.20260912.353`; this work has not
staged an update or restarted its Remote service. Full image, boot and phone
hardware acceptance are not claimed by the browser screenshots.
