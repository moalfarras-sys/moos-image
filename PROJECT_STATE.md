# MoOS current state

Current measured facts only; Git owns history. Last measured 2026-09-17.

## Source and release truth

- `main` holds waves W2–W5 (`7f182689` is the W5 merge) plus the 2026-09-17
  integration described under "x86 `main` was red" below. None of W2–W5 is in an
  x86 release: the W2 cycle stopped on its ISO proof (run `35158666486`: second
  boot healthy on QGA, SSH "timed out during banner exchange"), W3 built green
  and was never proven, the W4 build was cancelled by the W5 push, and the W5
  build failed.
- **x86 production is W1**: revision `92248b5d`, version `44.20260916.848`, promoted
  by run `35156269206` from build `35148344935`, QCOW2 generic/NVIDIA/cloud
  `35150447739`/`35150452495`/`35150457478` and ISO `35150461926` (all attempt 1).
  Read back from the registry: generic `f1d62342…`, NVIDIA `2b4b04c4…`, cloud
  `51a3f37c…`. The hardened ISO proof passed both reboot channels.
- The first promotion attempt `35156091444` failed after copying the new
  `:20260916` tag: GHCR answered "manifest unknown" to the immediate read, and
  the tag resolved to the copied digest seconds later; `latest` never moved. The
  fresh dispatch succeeded. W2 makes that read a bounded wait for the exact digest.
- **ARM production is W5**, read back from the registry on 2026-09-17:
  `moos-arm:latest` = `44.20260917.431`, revision `7f182689`, digest
  `e92466a996a5…`. `build-arm.yml` promotes every green push to `main`, so ARM
  moved W1 → W3 (`2e6f7686`) → W5 the same day while x86 stayed on W1. The two
  architectures are one release apart until the next x86 promotion.
- The intermittent ARM second-boot crash is still open (P0.7): `plymouthd` SEGV
  in `on_new_frame` → `ply_list_node_get_data` (plymouth 24.004.60, aarch64)
  failed run `35150466421` and the 2026-09-15 run. The W3 and W5 ARM runs passed
  with no fix applied, which is what "intermittent" means, not a resolution.
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

W1 (PR #107, `THEME_REV=58`) is the x86 release: keyboard-safe Search and Island,
the Remote/Media detail switch and `moplayer/` as the only MoPlayer source. On
top of it `main` carries, unreleased for x86 and already promoted for ARM:

| Wave | PR | What the user gets | `THEME_REV` |
| --- | --- | --- | --- |
| W2 | #108 | MoOS Hub controls in the desktop menu and wallpaper page; shadow sweep covers Search and the scene | 59 |
| W3 | #109 | every widget removable again; an owner-chosen wallpaper survives login and drift checks | 60 |
| W4 | #110 | Mo AI tool harness: native tool schemas from the fixed `moai-do`/`moos-control` grammar, confirmation cards, result readback | — (app QML; its launcher disables the disk cache) |
| W5 | #111 | Island Store jobs and camera/microphone/screen-share chips with one-tap stop; inline Search answers | **61**, added afterwards — see below |

None of it is true for an x86 user until signed proof, promotion, update and
reboot. W4 and W5 were merged without a station review recorded here.

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

## x86 `main` was red after W5 (fixed in source 2026-09-17)

Build run `35215425618` failed all three x86 editions at the end of `build.sh`:
"the settings route parser found almost nothing … (got 4)". `moos-open` was
correct. `verify_image_experience.py` read it through `source(router, "#")`,
which stripped `/* … */` from every language; W5's `${privacy_act#*/}` closed a
span opened 235 lines earlier by the comment "settings/kcm/* wildcard" and hid
24 of 28 settings routes. Reproduced offline with the gate's own code: 28 routes
visible at W3 and W4, 4 at W5. `source()` now strips block comments only for
`//` languages, so the gate sees more of the router than before.

No pull-request check could see it: that gate runs only inside the x86 image
build, `build.yml` does not run on pull requests and `build-arm.sh` does not
call it. `tests/test_image_gate_source_parser.py` lifts the gate's parser with
`ast` and runs it on this tree's `moos-open` in Repo gates; with the old gate
file it fails with the same "4 … needs 25".

W5 also changed `org.moos.island` and `org.moos.search` at `THEME_REV=60`. ARM
had already promoted W3 at rev 60, so an A1 that logged in on W3 keeps its cached
W3 widgets after the W5 update (frozen mtimes, caches keyed on mtime). The
revision is 61 and `tests/test_theme_rev_fingerprint.py` now fails any change to
a cache-served package (58 of them) that leaves the revision alone; recorded on
the W3 tree it fails on the W5 tree and names both plasmoids. **Not yet seen:**
an ARM profile picking up the W5 island after this lands.

Verified on Fedora 44 under WSL2 (no Bluetooth, no desktop session):
`bash tests/repo-gates.sh` fails on pristine `7f182689` at
`test_moai_confirmation_flow.py`'s 10 s timeout and exits 0 on this integration
(162 gates). The x86 image build on `main` is the proof still owed.

## Fixed 2026-09-17 on the A1 (merged, not yet in a signed x86 image)

PRs #112 and #113 are integrated. Installed copies carry both defects until the
next promoted image.

- `moos-index-policy` wrote `only basic indexing` under `[Basic Settings]`, but
  Baloo reads it from `[General]`, so the `file_indexing` budget never applied
  (`balooctl6` still answered `contentIndexing: yes`). Both diagnostics also
  demanded `yes` unconditionally, failing a correct filenames-only machine.
- `moos-control status` never returned: with no Bluetooth hardware,
  `bluetoothctl show` activated bluez and waited forever. An 8 s budget plus a
  bus-ownership check give 30128 ms -> 218 ms, unhanging `get_system_status`.

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

1. Merge the 2026-09-17 integration and confirm `Build MoOS image` is green on
   `main` for all three editions; that build is the only proof the gate repair
   works inside an image.
2. Run one `scripts/release-candidate.sh --promote` for W2–W5. The ISO proof has
   failed the same way on two of the last three `main` candidates (`57874d6c`,
   `8b272b87`: SSH banner timeout while QGA is healthy) and passed on `92248b5d`.
   Read the `moos-iso-install-proof` artifact before dispatching again; never
   "Re-run jobs".
3. On the station: stage, reboot, then read Hub controls, Search answers, Island
   jobs/privacy chips and the Mo AI confirmation cards back from `/usr`; confirm
   `THEME_REV=61` swept the review shadows. The booted-deployment paragraph above
   was not re-measured from the Windows workstation that prepared this
   integration and may be one update behind the wallpaper review, which names
   `44.20260916.848` as booted: re-measure with `bootc status`.
4. On the A1: after the next ARM promotion, confirm the W5 island and search are
   what plasmashell actually runs (rev 61 purge), and that `moos-control status`
   returns in well under a second.
5. P0.7 stays open; the experience waves continue from `docs/DEVELOPMENT_PLAN.md`.
