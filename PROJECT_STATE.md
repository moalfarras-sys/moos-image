# MoOS current state — measured 2026-09-25
Current measured facts only; Git owns history.

**This block is the only place in the repository that states a version number.** The plan,
the README and every wave row point here instead of repeating it. Four parallel copies of
"production is X" is how three of them came to be a release behind at once.

## Source and release truth
- **The NVIDIA station boots signed production `44.20260924.929`** (revision `ecd82c38`,
  PR #162, promoted by `36039015449`; `moos-nvidia@sha256:38745293…`), with `.925` retained
  for rollback. Read back 2026-09-24: zero failed system and user units,
  `post-update-check.sh` 55/0, `moos-selfcheck` 53 passed / 0 failed / 1 stale note (its own
  tray list, fixed in W9.9 source). `moos-nvidia:latest` still resolves to `.929`.
- **W9.9 "MoOS One inside KDE" is source on `feat/moos-one-kde-20260924`, not an image.**
  `just check` passes on the host; the seven `kcm_moos*` modules compiled in the build image
  and were reviewed live from source in the station's Arabic 4K session (a private-bus
  System Settings with the worktree's plugins); a full local image build, PR image gates, a
  signed candidate and installed proof are still owed.
- PR #157 integrated W8/W9, ARM app parity, Store honesty and the NVIDIA device gate.
  PR #158 raised ARM's finite first-boot Flatpak timeout
  from 30 to 120 seconds. The no-GPU NVIDIA VM boots twice with zero failed units.
- **ARM's PR #160 image** passed signed build, UEFI QCOW2 proof and production promotion
  in `35963023960`. PR #161 (Plasma seam compatibility and ARM parity) is merged at
  `aeb3e070`; its automatic x86/ARM image runs are still separate from a proven release.
  Intermittent upstream Plymouth issue P0.7 remains open.
- **P0.7 is no longer only a captured stack.** Read out of plymouth 24.004.60's source on
  2026-09-21: `ply_boot_splash_free()` frees `pixel_displays` without disarming the
  `on_new_frame` timeout that only `ply_boot_splash_hide()` disarms, and `--retain-splash`
  is the path that skips that hide. Both recorded workarounds are disproven, and upstream
  `main` still has the defect (2026-09-24), so Fedora 45's Plymouth 26.x will not close it.
- A merged commit or locally built image is not an installed or released state.
  Production moves only after the exact candidate passes 3×QCOW2 + ISO; ARM is
  separately required evidence.

## App engines — what this machine can actually run

`wine` is installed by the image on every desktop edition, the Android environment is now
initialized and running, and Linux applications use the image's application service. A
`.exe` resolves as `chosen=wine, ready=true, needs_setup=false`; an `.apk` installs only
through App Drop → `moos-storectl`, with the same job and lock as catalogue installs.

**All three app engines ran on the station (2026-09-20).** Windows Notepad, Minesweeper
and PuTTY PE32+ used `moos-run-foreign` with MoOS decoration and taskbar presence; Linux
apps completed install → launch → remove through `moos-storectl`. Correct Waydroid OTA
channels let 2.3 GB download, the container run, and F-Droid open after App Drop install.
VLC's real window is captured in `test-results/android-vlc-source-live.png`. The 4K Windows
UI density is measured. PE32 remains blocked by an SELinux `execmod` denial for an i386 PE
DLL from composefs; do not weaken SELinux globally.

## Physical development station

| Area | Measured state |
| --- | --- |
| Install | Offline USB install completed; target-only write was observed |
| Target storage | `/dev/sdb`: 512 MiB ESP + 476.4 GiB Btrfs; `/var` 163/477 GiB used, 313 GiB free |
| CPU / RAM | Intel Core i5-14400F / 15.4 GiB |
| GPU | NVIDIA RTX 2080 SUPER, driver 615.71.09 |
| Desktop | Plasma/KWin 6.7.5, Wayland, 3840×2160@60, scale 265% (1450×816 logical) |
| Kernel | `7.2.6-200.fc44.x86_64` |
| Network | Intel AX210 Wi-Fi/Bluetooth + RTL8125 Ethernet |
| Health | zero failed system units; zero failed user units (P0.7 remains intermittent) |

Measured after reboot onto the current signed image: installed `THEME_REV` **85**,
Global Theme `org.moos.ui2`, `kwinrc/Plugins/blurEnabled=true`, Arabic session
(`ar_SA.UTF-8`). The W8/W9 image is running and passed live post-update checks;
that does not qualify suspend, every app or the full visual matrix.

**Speed and Mo AI, both measured on cycle H's `.890`** and NOT re-measured since.
`moos-measure-speed` (P5.4): MoOS's share of boot **6.70 s**/9.0,
login to a ready desktop **1.10 s**/3.0, an app's window **0.49 s**/4.0, MoOS's processes
**0.12%** of CPU while idle/8.0 — all four inside budget. `moai-measure-actions` read
**80/80** then **79/80** over two runs of 40 fixed Arabic/English cases, no wrong tool in
either; the one miss was the model answering in words instead of calling (P3.3).

**Updating it:** origins are digest-pinned, so `bootc upgrade` reports "no changes"
forever. Use the MoOS Updater (Settings → Update MoOS, or Mo AI's "Update my system"),
or the nightly train; then restart.

## Closed reviews — what they established

- **W2–W6 on the station** (2026-09-17/18, `.858`/`.862`): every row passed — booted
  version and retained deployment, first-login shadow sweep, Hub controls from the
  desktop's menu, a widget removed with an undo, Search's inline answer (`12*7` → **84**),
  the Island's privacy chip naming the capturing app, App Drop installing and removing a
  real 8.4 MB AppImage, a dismissed administrator prompt staging nothing and saying so.
  **Still owed:** an Island **Store** job in the foreground (the Remote chip outranks it
  while Mo PC Remote runs).
- **W6.1–W6.3** in production: Settings' "About this device" (P2.9), Mo AI's twelve
  read-only repair playbooks (42 tools then, 13 ask first; 51 in W9.9 source) with eight chips (P3.10), and Mo
  AI's rail corrected at the default 940 px window.
- **Mo AI's brain, measured since:** a real free model drives the tool loop (W8.3, PR
  #131), eight free models were ranked on this machine (W8.5), and action selection is
  measured (W9.1 — see the station block above). **Still owed:** the same 40 cases on a
  second model and a second machine.

## Proven source/image behavior

- A signed build passes every image gate for all three x86 editions; every disk boots
  twice under QEMU/KVM; each final ISO installs offline, logs in, opens every first-party
  app twice, reboots and powers off. `pr-image-gates.yml` builds the generic image on a
  pull request and pushes nothing (16m54s on PR #141).
- Horizon motion gates cover finite settling, reversal, hidden state, reduced motion and
  pointer/key paths, on a real Qt runtime.
- **W8 material arrival is in source (`THEME_REV` 85):** one finite glint/1.5% settle on
  shared glass, still under Reduced Motion; real Qt changed at 60 ms and rested by 900 ms.
  **W9 source:** Settings deep-links Update, Recovery and Remote to their existing transaction
  owners. On 2026-09-23 it gained owner-read busy/superseded update, queued rollback and failed
  Remote rows; Arabic/English light/dark Qt captures and interaction assertions passed.
  A superseded staged image is no longer called ready to restart. Installed routes and real
  transactions remain unproven; neither W8 nor W9 source is installed.

## Development environment

- On the station: VS Code is a Flatpak; host work uses `flatpak-spawn --host`. There is
  **no C++ toolchain**, so any gate needing one skips here. `just workstation-check` is a
  read-only inventory; .NET `10.0.401` and Flutter 3.47.4 are installed. Pointer review
  goes through `scripts/station/pointer.py` — KWin confirms every position before a click.
- Off the station: Windows 11 + WSL2 `FedoraLinux-44`. `scripts/review/` holds the
  toolchain installer, the gate mirror and the from-source renderers;
  `scripts/release-candidate.sh` needs `TMPDIR` under Git Bash.

## ARM station `moos-arm-oracle` (Oracle A1, measured 2026-09-21)

The only ARM MoOS machine: 2 vCPU / 11 GiB, `kwin_wayland --virtual 1920x1080 --xwayland`.
**Read back 2026-09-24:** signed `moos-arm@sha256:eff234df…` = `44.20260923.568` (ARM
`latest`), kernel `7.2.7-200.fc44.aarch64`, Plasma 6.7.5, Qt 6.11.2, no failed units. The rest
was measured on `.545`: `blessed`/`attempts: 0`, `post-update-check.sh` 55/0, `moos-selfcheck`
50 passed + 3 owner-choice notes. Idle
cost over 10 s of `/proc/<pid>/stat`: `kwin_wayland` **2.1%**, `plasmashell` **0.6%** of
one core (`ps` shows ~26% only because that is a lifetime average including startup).

**Seen on the live A1 on 2026-09-24, and fixed in source with a gate:** the MoOS Bar read LTR
in Arabic (x86's is mirrored) and Dolphin did too, GTK windows drew Adwaita light, App Drop's
`ask()` returned False (no kdialog), and the privacy monitor ran blind (no pw-dump). All eight
capabilities come from x86's base; `build-arm.sh` now names them and `verify_desktop_parity.py`
passes on the published x86 image and a full local ARM build. Frames of the fix come from the
built image and a probe container on this session. Mo AI's chat texture drew stray logos on
the software scene graph every GPU-less machine uses; fixed and runtime-gated. Mo AI answered
in 0.65 s on the free route; its APIs bind loopback only. Three readings look like defects and
are not (`cost_policy: "paid"`, `"gateway": false`, sandboxed `systemd-tmpfiles`): see the plan.

## Plasma 6.8 readiness (measured 2026-09-24; detail in plan row P6.7)

On KDE SIG's 6.8 beta (`6.7.90`) MoOS's 6.7 lock screen falls back to the emergency locker:
6.8 removed `VirtualKeyboardLoader`. **Canary run `35980381601` built the whole generic image on
6.7.90 with every in-image gate green:** the seam gate picked set 6.8, matched ten digests and
loaded the merged lock screen in the real greeter. PR #161's 6.7.5 x86 and ARM builds pass the
same gate. CI also found Breeze's Global Themes hidden on x86 only, now one shared step, and a
libplasma soname bump that removes `kcm-fcitx5` until Fedora rebuilds it. No 6.8 candidate yet.

## Open evidence gaps

- **Settings, installed (`.929`, 2026-09-24):** the one-module `kcm_moos` opens inside System
  Settings in Arabic (photographed). Measured defects it carries, fixed in W9.9 source: the
  About row shows the packager kernel tag (`7.2.7-200.fc44.x86_64`), raw edition/GPU labels,
  MoOS last in the System group, an English "Input Method" page for an engine MoOS removed,
  and Plasma's window is `systemsettings` (KWin readback), so the `org.kde.systemsettings`
  StartupWMClass on the MoOS entries never matched.
- **W9.9 source, reviewed live (2026-09-25):** a private-bus System Settings loaded the
  worktree's seven modules on the station: the MoOS group is first in the sidebar; Overview
  shows "Linux 7.2.7", "MoOS for NVIDIA graphics", signed/not-checked-recently chips; Update
  shows the System, Applications and Firmware rows; Mo AI read the live brain (OpenRouter
  free, key saved, phone agent at tier `full` shown as "without confirmation") with GET
  requests only; MoOS Themes lists the 16 looks under Appearance & Style and marks the
  owner's current Arena look. Not yet proven: installed image, existing-user migration
  (THEME_REV 86), Meta+Space registration after a login, real update/rollback transactions.
- **Side effects found and fixed while testing (2026-09-24/25):** repository tests wrote 36
  fabricated `moai-do` audit lines and 22 `moos-update` records into the station's journal
  (22:00:23–40 on 2026-09-24; journal lines cannot be deleted selectively), and the build
  container's status helper made `bluetoothctl` dump core 64 times with no system bus. Tests
  now stub `logger` under a meta-gate, and the helper skips Bluetooth without a bus.

- **Mo PC Remote, 2026-09-24:** on the NVIDIA station the service, portal, input daemon and
  watchdog are active, loopback `:8765` answers, `/dev/uinput` grants the owner, no failed
  units; the installed Arabic PIN screen was inspected. Source serializes input across
  controllers (two-WebSocket test passes) and the PIN keypad fits a 360×640 phone (last row
  498 px). Still owed: signed candidate, booted editions, authenticated video/input.
- M1 visual/accessibility matrix: English/German, light/dark, reduced motion, 1080p–4K,
  100–250%, island Remote/Media (Arabic only so far).
- Hardware: suspend/resume, multi-monitor, audio/network recovery, deliberate rollback,
  photographed boot/login, laptop and touch hardware, ARM on a physical seat.
- Versioned, failure-tested Mo AI/Store/core contracts and one lifecycle across every
  adapter. APK installation now has the Store authority; shared cancel/remove/retry and
  stable cross-engine app IDs remain P4.1 work.
- Owner decision P3.9: whether Mo AI ever gets a tool that runs a command the model
  wrote. Until it is taken, no such tool exists.

## Other measured facts

**A wallpaper cannot be clicked (2026-09-18):** over a Hub card neither click nor wheel
arrives, so every card's second face is turned from the desktop's own menu.

**The free brain is measured where it runs (2026-09-18):** the catalogue carried **21**
tool-capable zero-price models. `moai-measure-free` asks each two fixed questions through the
real gateway and writes `~/.local/state/moai/free-ranking.json`, which `moai_cloud_policy`
prefers for 30 days without ever adding a model, a price or a billed route. P0.5 still owes
the key entered through Settings, a reboot and the provider-failure surface.

**A second desktop server:** `moos-health scan` found `krdpserver` on `tcp *:3389` for the
whole network beside Mo PC Remote; the finding carries `moos://privacy/stop-sharing`, and
`moos-remote-guard off` stops and un-autostarts both with no administrator rights.

## Next execution
Qualify the unified native Settings image and finish P2.12's app/firmware records; boot the
staged NVIDIA image and run post-update checks. Then finish W9's real transaction lifecycle
and W8's three-size mark. Pursue upstream P0.7;
P4.2–P4.5, German, touch/laptop/multi-output and full accessibility remain open.
