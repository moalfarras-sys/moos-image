# MoOS current state

Current measured facts only; Git owns history. Last measured 2026-09-16.

## Source and release truth

- `origin/main` is `57874d6c` (PR #106, Horizon 2). All historical remote topic
  heads are ancestors of `main`; no unique branch commit is waiting to merge.
- The physical release is revision `5fce15df`, version `44.20260915.836`.
  Promotion run `35060599655` moved and read back the x86 production tags:
  generic `fa5cbfe3…`, NVIDIA `086f7086…`, cloud `42a95f1d…`.
- The next signed candidate was built from exact revision `57874d6c` in run
  `35088882717`: generic `946549c7…`, NVIDIA `0301e6f6…`, cloud `19d0f44c…`.
  Generic/NVIDIA/cloud QCOW2 runs `35091019991`/`35091023951`/`35091027313`
  and ARM run `35091035163` passed.
- ISO run `35091031129` installed offline, booted the target disk, reached the
  desktop, opened/closed/reopened all ten first-party apps, and serial proved a
  different second kernel reached the MoOS login. Its SSH proof channel timed
  out before a banner on that second boot, so the workflow failed and **no tag
  was promoted**. The active branch is repairing and diagnosing that proof path.
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
Remote/Media detail switch. `THEME_REV=58` carries the QML change to existing
profiles. This state becomes true for users only after gates, signed proof,
promotion, update and reboot.

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
- Flutter on the host is newer than the image-pinned toolchain. The local
  `moplayer/analysis_options.yaml` and `moplayer/pubspec.lock` changes came from
  that host run and are intentionally excluded from MoOS commits until the
  toolchain upgrade is planned.
- `.kilo/` is local untracked agent state and is not product source.

## Open evidence gaps

- Fix and rerun the exact ISO second-boot proof; then promote, stage, reboot and
  read back Horizon 2 from `/usr` on this workstation.
- Capture the M1 visual/accessibility matrix: Arabic/English/German, light/dark,
  reduced motion, 1080p–4K and 100–250%, including typed Search and island
  Remote/Media switching.
- Prove two suspend/resume cycles, multi-monitor, audio/network recovery,
  deliberate rollback/roll-forward and photographed boot/login on hardware.
- Qualify broader Wi-Fi/Bluetooth/audio/camera, laptop/touch hardware, ARM
  provider behavior and cloud multi-account operation.
- Convert Mo AI/Store/core APIs to versioned, failure-tested contracts and a
  single application transaction authority; fixed `moai-do` confirmation and
  subsystem readback remain mandatory.

## Next execution

Finish the current M1 Search/Island + ISO-proof batch; run targeted gates,
`just check` and one local image build; integrate one reviewed pull request;
confirm there is no active release runner; execute
`scripts/release-candidate.sh --promote`; update/reboot this signed NVIDIA
station; then capture live Arabic and English readback. Continue with M2 only
after recording the exact proof outcome.
