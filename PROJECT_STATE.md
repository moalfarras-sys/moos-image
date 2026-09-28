# MoOS current state — measured 2026-09-27

**Mira (topic source, 2026-09-28):** `mira/` preserves both faces; a real lamp passed on/pink/off readback and Mo AI Hermes read the registered MoOS project with owner cloud consent. The journal's 09:54 local-computer wake led to one heard voice turn and Echo reply; it does not prove on-device wake. Latest capture/recognition and same-mic changes were installed in the user app with a backup. The Echo USB mic is too slow for local wake (0.9–1 frame/s in a later health sample); the faster analog port proved unplugged and was deselected. The tested microphone picker hides unplugged ports. Direct Echo console readback found seven-mic capture RUNNING at 16 kHz and the on-device model hash matching the app; neither proves recall for the owner's voice. The Echo's on-device cutoff is 0.50. A 4 dB room-sensitivity trial failed, so 6 dB was restored. Echo answers on Wi-Fi without USB and its built-in phone setup page returned HTTP 200. Mira's real setup, mic-mute and Bluetooth-pairing controls are installed locally; 34 UI/voice and seven wake tests pass, and the app restarted to `ready`. The current daemon ignores wake without a subscribed pipeline; computer-off voice and home control are not implemented. Owner-spoken hands-free proof, full button review and signed-image packaging remain open. See `mira/README.md`.
## Source and release truth
- **Proven x86 production is `e6fbd56c`, `44.20260927.945`**: signed build `36297160647`,
  QCOW2 `36298778749`/`36298780129`/`36298781296`, ISO `36298782489`, x86 promotion
  `36301001323`, ARM proof/promotion `36298783867`; all succeeded at attempt 1.
- PRs #169/#170/#171 are merged. THEME_REV 90 fixes dock/Hub material, Remote v44
  reports trusted-device failures honestly, and video/input/audio follow session revocation.
  Audio refuses buffered output after revocation and cancels idle connections within one
  second; 150 real session/stream assertions pass, Linux/Windows compile cleanly.
- **The NVIDIA station now boots signed `44.20260927.945`** (`e6fbd56c`), with signed
  `.938` retained for rollback; digest `sha256:b09cdc48…`. Live post-update check:
  **55 passed, 0 failed**, zero failed system/user units on 2026-09-27.
- Corrective THEME_REV 95 source keeps the configured floating capsule beside maximized
  windows, adds matching rounded solid artwork in all palettes and restores one finite Hub
  reveal with interruption/Still/re-enable proof. Plasma SVG frame render and 44 UI tests pass.
  Remote v45 rejects frozen-mtime validators (158 same-size worker assertions); hidden tools
  leave focus and settings opens on the real stream. #174 completes missing release notes.
  `.950` was superseded before x86 promotion; ARM `.614` on `65470b7e` passed/promoted.
  Station delivery and the two-icon design approval remain pending.
- **P0.7 is no longer only a captured stack.** Read out of plymouth 24.004.60's source on
  2026-09-21: `ply_boot_splash_free()` frees `pixel_displays` without disarming the
  `on_new_frame` timeout that only `ply_boot_splash_hide()` disarms, and `--retain-splash`
  is the path that skips that hide. Both recorded workarounds are disproven, and upstream
  `main` still has the defect (2026-09-24), so Fedora 45's Plymouth 26.x will not close it.
- A merge or local image is not an installed release. Production requires exact-candidate
  3×QCOW2 + ISO; ARM is separately required evidence.

## App engines — what this machine can actually run

**Corrective source work, 2026-09-27:** THEME_REV 90 adds a reviewed 6.7/6.8 dock material seam and shared Hub material; isolated clear/solid Hub renders and local image gates passed.
Windows setup folder access is temporary, confirmed and read-only. Generals Zero Hour
ran a real Alpine Assault Skirmish at 1080p fullscreen on the 4K station: Dozer selection,
movement and saving worked. Its local MoOS menu entry launches directly, but some reopen
attempts stay on the introductory background, also with the builtin renderer. The tested
DXVK configuration and save remain; all owned probes are closed. Repeated-launch/universal
Windows qualification and this corrective batch's physical-station proof remain open.

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
| Target storage | `/dev/sdb`: 512 MiB ESP + 476.4 GiB Btrfs; `/var` 244/477 GiB used, 230 GiB free (2026-09-27) |
| CPU / RAM | Intel Core i5-14400F / 15.4 GiB |
| GPU | NVIDIA RTX 2080 SUPER, driver 615.71.09 |
| Desktop | Plasma/KWin 6.7.5, Wayland, 3840×2160@60, scale 225% (1707×960 logical) on 2026-09-25 |
| Kernel | `7.2.6-200.fc44.x86_64` |
| Network | Intel AX210 Wi-Fi/Bluetooth + RTL8125 Ethernet |
| Health | Baloo recovered; post-update 55/0; powersave changed to balanced, turbo read back enabled |

Measured on the previous `.938`: installed `THEME_REV` **87**
and its existing-account marker, current Global Theme `org.moos.ui2.gaming`,
`kwinrc/Plugins/blurEnabled=true`, Arabic session (`ar_SA.UTF-8`). The W8/W9
image is running and passed live post-update checks;
that does not qualify suspend, every app or the full visual matrix.

**Mo PC Remote on `.938`, 2026-09-26:** authenticated v42 loopback H.264 Data Saver
measured 28–29 fps and 1 ms locally; zoom visibly enlarged the desktop; Auto restored.
External-network, typing, files and audio remain unproved. Installed Auto can step
down to Data Saver under sustained congestion; Island follows live glass clarity.
The scoped Baloo workaround is a user override pending signed delivery, not image proof.

**Speed and Mo AI measured on `.890`, not re-measured:** P5.4 boot **6.70 s**/9.0,
login to a ready desktop **1.10 s**/3.0, an app's window **0.49 s**/4.0, MoOS's processes
**0.12%** of CPU while idle/8.0 — all four inside budget. `moai-measure-actions` read
**80/80** then **79/80** over two runs of 40 fixed Arabic/English cases, no wrong tool in
either; the one miss was the model answering in words instead of calling (P3.3).

**Updating:** use MoOS Updater (Settings → Update MoOS, or Mo AI) to resolve and stage
a signed digest, then restart. Nightly builds alone never promote a release.

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

- **Settings on `.929` (installed, photographed 2026-09-24):** the one-module `kcm_moos`
  shows the packager kernel tag (`…fc44…`), raw edition/GPU labels and an English "Input
  Method" page, sits last under System, and its entries' `org.kde.systemsettings` class never
  matched the window (`systemsettings`, KWin readback). All fixed in W9.9 source.
- **W9.9 source, live from the worktree (2026-09-25):** the seven modules in a private-bus
  System Settings on the station — MoOS group first; "Linux 7.2.7", "MoOS for NVIDIA
  graphics"; Update's three rows; Mo AI read the live brain with GETs only; MoOS Themes marks
  the owner's Arena look. `moai-measure-actions` with the grown schema (65 cases, ar+en):
  **126/130 = 96.9%** on `nex-n2.5-pro:free`, three gateway timeouts and one wrong tool (mic
  unmute → fix_audio, Arabic). Owed: installed image, THEME_REV 86 migration on this
  account, Meta+Space after a login, real update/rollback runs.
- **Testing side effects, now gated (2026-09-24/25):** repo tests wrote 36 fake `moai-do` and
  22 `moos-update` audit lines into the station journal (22:00:23–40, not removable), and the
  build container made `bluetoothctl` dump core 64 times; tests stub `logger` under a
  meta-gate and the helper skips Bluetooth without a system bus.

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
Prove and promote the audio/material corrective batch, stage its signed NVIDIA digest,
reboot and run live post-update/clarity checks. Then finish P2.12, W9 transactions and
W8's three-size mark; pursue upstream P0.7.
P4.2–P4.5, German, touch/laptop/multi-output and full accessibility remain open.
