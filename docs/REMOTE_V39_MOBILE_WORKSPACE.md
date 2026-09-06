# Mo PC Remote v39 — mobile workspace

## Behavior

The controller uses MoOS Liquid Glass colors, static reflected-light gradients,
readable button plates and bounded modal panels. Toolbar and typing surfaces no
longer blur incoming video. No perpetual decorative animation was added.
The dark sensitivity-card interior at screenshot pixel (300, 1750) changed from
RGB (35, 45, 50), luminance 43.2, to (51, 69, 75), luminance 65.6.
This is a measured visible change, not a claim of better frame rate.

The phone keeps an upright, aspect-correct desktop in portrait and landscape.
Controller chrome occupies its own grid track. Fading a side rail previously
translated it toward +X, which enters the desktop in Arabic RTL; it now fades
in place. Rotation is tested with the rail faded as well as visible.

Typing prioritizes Select all, Copy, Paste on PC and Undo, followed by the
advanced keys in a scrollable strip. Text chooses its direction from its content.
Closed typing controls are inert; opening removes inert synchronously so the
original phone tap still focuses the input. The keyboard bar follows visualViewport
directly instead of interpolating a second animation behind the native keyboard.

Clipboard directions use explicit Arabic words instead of ambiguous arrows.
PC and phone text have separate glass groups. Paste from phone clipboard retrieves
an editable local draft; a denied/unavailable browser API focuses the manual-paste
field without discarding its text. Set only and Send & Paste remain separate actions.
Small text clipboard HTTP operations time out after 15 seconds. Failed uploads
never issue Paste against old PC content. Sheets track the visible viewport so
phone typing, emoji panels and browser panning cannot leave their bottom hidden.

## Review and evidence

The design borrows useful task organization, not another product's identity:

| Official reference | Relevant behavior | MoOS choice |
| --- | --- | --- |
| [AnyDesk on iOS](https://support.anydesk.com/docs/anydesk-for-ios-ipados-tvos) | Virtual/special keyboard and clipboard controls | Primary editing shortcuts with advanced keys in the same strip |
| [AnyDesk file transfer](https://support.anydesk.com/file-manager-and-file-transfer) | Clipboard and file-transfer entry points | Keep text/image transfer distinct from file browsing |
| [TeamViewer session toolbar](https://www.teamviewer.com/en/global/support/knowledge-base/teamviewer-remote/remote-control/remote-session-toolbar/) | Display scaling, monitor controls, clipboard and shortcuts | Retain aspect-correct fit and reserve space for phone controls |

These are feature references, not comparative performance benchmarks.

Production-bundle Chromium integration covers 390×844 portrait, 844×390 landscape,
1366×900 desktop, 360×800 light/reduced-motion, Arabic and English, IME commit,
emoji deletion, interrupted composition recovery, modal keyboard isolation, real
relative touch packets, clipboard directions/failure, and simulated visual viewport
heights 480/370/844 with a 20px pan. The simulated viewport tests do not substitute
for the native iOS/Android keyboard on a physical phone.

- [Dark settings](evidence/remote-v39-settings-dark-ar.png)
- [Light settings](evidence/remote-v39-settings-light-ar.png)
- [Clipboard](evidence/remote-v39-clipboard-dark-ar.png)
- [Typing](evidence/remote-v39-keyboard-dark-ar.png)
- [Landscape](evidence/remote-v39-phone-landscape-ar.png)

Screenshots use the repository's existing desktop frame with an isolated test
transport. They prove the rendered controller, not cellular speed or a live PC
clipboard round trip. The earlier real GTK Arabic/layout readback remains recorded
in [the Oracle health report](ORACLE_STORAGE_HEALTH_20260905.md).

All 98 repository gate commands passed on the host against the final changes;
controller typecheck/build and all 15 controller test programs passed. The final
production-bundle browser run also passed using the active service as its static
asset source, with API/WebSocket traffic intercepted. The owner then confirmed
that the typing bar stays above the keyboard on their physical phone in both
portrait and landscape. This does not cover the complete Safari/Android matrix
or weak cellular connections. Full native ARM image build and bootc container lint passed. The final built
image `c39840054b30` was opened to compare the controller and portal bytes against
the tested sources and verify the wired AppStream service. Registry publication
and post-update boot verification are separate steps.

## Local deployment and recovery

The active service uses `~/.local/lib/mo-remote-v39-20260905`, retaining the prior
`~/.local/lib/mo-remote-20260905` directory. Served JavaScript and the portal helper
were checked by SHA-256 against the tested source/bundle. Portal startup reports
ready at 1920×1080. Auth configuration was preserved; only Remote was restarted.

The legacy `10-restart.conf` disabled systemd start limits and forced endless
restarts. It is preserved with the previous v38 override under
`~/oracle-storage-maintenance/remote-v39/`; the active service again uses the shipped
on-failure policy and five-minute start-limit window. The v39 override only selects
the versioned executable. To roll back the app, restore the saved v38 override,
remove the v39 override, reload user systemd and restart `mo-remote-personal`.
The old infinite-restart override does not need to be restored.

The signed installed OS origin and previous boot deployment remain unchanged.
After a signed OS image containing v39 is installed, retire both the 90-oracle-live
and 99-remote-control-v39 executable overrides after verifying the image's own
Remote bundle. The local AppStream service override can then be retired as well.

## Branch preservation

`fix/remote-control-audit-20260904` is fully contained in main (PR 72). The active
storage/keyboard branch incorporated current main without conflicts. There are no
stashes or additional worktrees. `archive/arm-utm-20260827` retains 18 experimental
commits outside main; none concerns this controller change, and its obsolete
boot/UTM experiments were not merged wholesale. No branch was force-pushed or deleted.
