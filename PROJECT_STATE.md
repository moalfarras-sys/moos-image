# MoOS current state

Current measured facts only; Git owns history. Last measured 2026-09-17.

## Source and release truth

- `origin/main` is `2e6f7686`, the merge of wave W3 (PR #109). Wave W4 is on
  topic branch `feat/w4-moai-tool-harness`.
- **Production is W1**: revision `92248b5d`, version `44.20260916.848`, promoted
  by run `35156269206` from build `35148344935`, QCOW2 generic/NVIDIA/cloud
  `35150447739`/`35150452495`/`35150457478` and ISO `35150461926` (all attempt 1).
  Read back from the registry: generic `f1d62342…`, NVIDIA `2b4b04c4…`, cloud
  `51a3f37c…`. The hardened ISO proof passed both reboot channels.
- The first promotion attempt `35156091444` failed after copying the new
  `:20260916` tag: GHCR answered "manifest unknown" to the immediate read, and
  the tag resolved to the copied digest seconds later; `latest` never moved. The
  fresh dispatch succeeded. W2 makes that read a bounded wait for the exact digest.
- **ARM is not promoted.** ARM run `35150466421` built, then its second boot left
  `plymouth-start.service` failed: `plymouthd` SEGV in `on_new_frame` →
  `ply_list_node_get_data` (plymouth 24.004.60, aarch64). The same crash failed
  the 2026-09-15 ARM run, and a re-run passed, so it is an intermittent boot
  defect, not a flaky gate. The previous candidate `57874d6c` was never promoted
  (its ISO SSH channel timed out).
- A merged commit or locally built image is not an installed or released state.
  Production moves only after the exact candidate passes 3×QCOW2 + ISO; ARM is
  separately required evidence.

## Physical development station

| Area | Measured state |
| --- | --- |
| Install | Offline USB install completed; target-only write was observed |
| Target storage | `/dev/sdb`: 512 MiB ESP + 476.4 GiB Btrfs; `/var` 133/477 GiB used, 341 GiB free |
| CPU / RAM | Intel Core i5-14400F / 15.4 GiB |
| GPU | NVIDIA RTX 2080 SUPER, driver 615.71.09 |
| Desktop | Plasma/KWin 6.7.5, Wayland, 3840×2160@60, scale 250% |
| Kernel | `7.2.5-200.fc44.x86_64` |
| Network | Intel AX210 Wi-Fi/Bluetooth + RTL8125 Ethernet |
| Health | zero failed system units and zero failed user units |

The booted deployment is signed `moos-nvidia` `44.20260915.836`, digest
`sha256:086f70863c5bb37f05a35c01761bd7c246ab0487e323b5e7c99db9db46cc91ff`.
Signed `44.20260913.824` (`76861a3b…`) is retained for rollback. The NVIDIA
modules are loaded and the kernel journal has no fatal NVRM event.

A root-owned local administrator override at
`/etc/plasmalogin.conf.d/90-moos-development-autologin.conf` enables one-session
automatic login for `moos` during this dedicated development cycle. It is not
in the repository/image and sets `Relogin=false`. Remove it with
`pkexec rm /etc/plasmalogin.conf.d/90-moos-development-autologin.conf` when the
owner ends development; normal MoOS releases continue to require login.

## Delivered in the booted release

- Mo PC Remote types through KWin's actual `ara,de` keymap, including German,
  Arabic, dead keys and Caps Lock handling; physical iPhone/German-keyboard
  acceptance remains open.
- Mo AI offers a fixed, confirmed local-RPM install route. The root helper
  re-checks path, owner, digest, architecture and trusted signature; the model
  cannot execute arbitrary privileged commands.
- ARM UTM packaging, signed-origin switching, update locking, digest/version
  comparison, Baloo ownership, password policy and repository cleanup are in
  production.
- Free cloud AI returned English and Arabic responses through the live gateway
  with an explicitly free provider. This proves chat, not unrestricted system
  control or all provider-failure cases.

## Main beyond the installed release

Horizon 2 composes one MoOS Bar instead of overlapping controls:

- MoOS Search owns one anchored Milou results surface with recent apps, real
  destinations, keyboard hints and an explicit Mo AI hand-off.
- The island announces a Remote connection, settles to a 72 px live privacy
  chip, and preserves Remote priority when media is active.
- The clock rail sits between tray and date/time; the desktop hub uses the
  shared locale authority and bidi-isolated temperatures.
- Arabic-first `ara,de` defaults agree across source defaults, installer and
  scoped existing-profile migration.

The current topic batch (not released) makes Search refuse stale/deferred rows,
restores full Tab/Escape/Ctrl+Enter traversal, separates its reviewable view,
and gives the island stationary native keyboard/accessibility controls plus a
Remote/Media detail switch. It also makes `moplayer/` the only MoPlayer source,
removes the obsolete external workflow/download path and stale screenshots,
updates the pinned x86/ARM Flutter builder to 3.47.4, and preserves the installed
demo and GPU crash guard. `THEME_REV=58` carries the QML change to existing profiles.
That batch is wave W1 (PR #107); its exact revision `92248b5d` is being proven by
branch run `35148344935` (`scripts/release-candidate.sh --ref`) before merge.

Wave W2 (`feat/moos-experience-wave2-20260916`, on top of W1) gives MoOS Hub its
own controls in the desktop right-click menu (show/hide and per-card time,
weather, device health) and on the wallpaper page, bumps `THEME_REV=59`, extends
the update-time shadow sweep to `org.moos.search` and the desktop scene, and
unifies the instructions around the MoOS Experience Program in the plan.
Neither wave is true for users until gates, signed proof, promotion, update and
reboot.

Live review on this station (Arabic, 4K/250%) with temporary package shadows:
the desktop menu showed all four Hub controls; turning weather off redrew the Hub
as time + device health with one divider; MoOS Search received typed input and
listed grouped app, settings and folder rows for `firew` (German layout) and a
web row for Arabic input, each with its action chip and the Ask Mo AI row. The
keyboard layout and applet shortcuts were restored afterwards.
**Review shadows left on purpose:** `~/.local/share/plasma/plasmoids/`
`org.moos.{search,island,nova.clock}` and `~/.local/share/plasma/wallpapers/`
`org.moos.ui2.wallpaper` (W2 source) stay so the owner sees the new desktop before
the update. `THEME_REV=59` removes all four at the first login after W2 is
installed; W1's `THEME_REV=58` removes the island and clock copies only.

## Proven source/image behavior

- The last full NVIDIA local build passed repository gates, 179 MoPlayer tests,
  MoRemote tests/publish, first-party QML runtime smoke, identity firewalls,
  clean image state, all `bootc container lint` checks and initramfs inspection.
- Built-image inspection found `ostree-prepare-root`, MoOS Plymouth assets and
  six NVIDIA modules in the initramfs. `/boot` payload is intentional for the
  offline installer.
- Horizon motion gates cover finite settling, reversal, hidden state, reduced
  motion and pointer/key paths. Native sound files decode and map to KDE event
  IDs; installed playback/mute acceptance remains open.
- The source Settings harness passed Arabic 1400×760 and English 1100×700 on the
  installed Wayland/Qt stack, including keyboard routes and stale-status failure.

## Development environment

- VS Code is a Flatpak; host work uses `flatpak-spawn --host` or repository
  helpers. `just workstation-check` is a read-only inventory.
- Qt QML and ShellCheck editor support are installed. Native user-space .NET
  SDK `10.0.401` passed every MoRemote build/test target.
- Flutter 3.47.4 is installed on the host and is now the x86/ARM image-builder
  pin. Its generated analyzer exclusions and lock refresh are part of the
  in-tree MoPlayer source and are verified with that SDK.
- `.kilo/` is local untracked agent state and is not product source.

## Owner wallpaper reverted after reboot (fixed in source)

A wallpaper chosen in Plasma's Desktop and Wallpaper dialog, on the scene page
or with Dolphin's Set as Wallpaper never passed through `moos-theme`, so the
central state still said `profile`; the login reconcile and the 30-minute drift
timer re-applied the theme canvas. `moos-theme` now adopts the live choice first:
a desktop on Plasma's plain image plugin is carried back onto the MoOS scene with
the same image (MoOS Hub stays), and an image that is not this family's canvas is
recorded as custom. Reviewed live for both paths on the booted `44.20260916.848`
station (two reconcile passes each kept the image; the installed reconciler also
kept it once state said custom); the station was then reset to its Aurora Light
canvas. Choosing a MoOS theme still resets to that theme's canvas by design.

## Widget lock defect (fixed in source, THEME_REV 60)

`moos-bar-apply` wrote `immutability=0` into every containment and applet group.
Plasma's types are Mutable=1, UserImmutable=2, SystemImmutable=4 (read from
`PlasmaCore.Types` here), so 0 left every widget locked: in edit mode the desktop
Disk Activity widget showed rotate, configure and background buttons but no
Remove. The installed `THEME_REV=58` rewrote the zeros at the first login after the W1
update; the station was repaired live again (runtime unlock, then `0` to `1` in
the appletsrc with plasmashell stopped; backups in `~/.cache/moos-live/`). The source
repair now writes Mutable only over invalid values and keeps user/system locks.
A runtime KWin wobbly-windows trial was inconclusive in still captures and was
unloaded again; physical window motion stays planned for wave W4.

## Open evidence gaps

- Fix and rerun the exact ISO second-boot proof; then promote, stage, reboot and
  read back Horizon 2 from `/usr` on this workstation.
- Capture the M1 visual/accessibility matrix: English/German sessions, light/dark,
  reduced motion, 1080p–4K and 100–250%, including island Remote/Media switching
  (typed Search and Hub controls are reviewed in Arabic only).
- Prove two suspend/resume cycles, multi-monitor, audio/network recovery,
  deliberate rollback/roll-forward and photographed boot/login on hardware.
- Qualify broader Wi-Fi/Bluetooth/audio/camera, laptop/touch hardware, ARM
  provider behavior and cloud multi-account operation.
- Convert Mo AI/Store/core APIs to versioned, failure-tested contracts and a
  single application transaction authority; fixed `moai-do` confirmation and
  subsystem readback remain mandatory.

## Next execution

W1 is promoted. `moos-auto-update.timer` (04:36) stages the signed
`44.20260916.848` NVIDIA image on this station; the owner may also stage it now
from the Updater, and a reboot applies it. Merge W2, run one
`scripts/release-candidate.sh --promote`, then read the Hub controls, Search and
Island back from `/usr` after the next update and confirm the review shadows were
swept. Diagnose the ARM `plymouthd` crash with an ARM-only branch dispatch before
the next ARM promotion. W3 (Island jobs and privacy chips, Search answers) is the
next visual wave.
