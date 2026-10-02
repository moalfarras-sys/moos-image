# MoOS current state — measured 2026-10-02

**Installed readback, 2026-10-02:** the NVIDIA station boots signed
`44.20261001.967` from source `59e97672` (digest `sha256:f55e1594…`), with `.964`
available for rollback. `post-update-check.sh` passed 55/55 after an older local
MoPlayer launcher and bundle were backed up outside the launch path; `moos-selfcheck`
passed 53 checks with two notes. System and user units have no failures. User apps
are current and fwupd offers no updates. Mo PC Remote is active behind Tailscale
Serve. The two online tailnet peers observed during this check used relays; the
station's UDP probe passed. Fast Remote was enabled live, and KWin blur/slide read
back disabled without restarting the desktop.

**Remote interruption diagnosis, 2026-10-01:** the installed portal repeatedly
renewed after `1536x864+0+0@3 -> no outputs`. Source `59e97672` ignores an empty
GDK snapshot until a real output returns, preserving renewal on actual geometry
change. A temporary user process ran that exact helper and stopped those false
geometry renewals, but KDE still closed the portal session when HDMI dropped.
The DRM connector was observed changing `connected -> disconnected -> connected`
within one second, simultaneous with `There are no outputs` from the portal,
PowerDevil, plasmashell and other KDE processes. 1920×1080@60 with matching
logical desktop size also dropped; 3840×2160@60 and 250% scale were restored.
KWin stayed running, NVIDIA reported no Xid, and memory pressure was zero. The
physical HDMI link, monitor power or port needs inspection. The software change
is merged, signed, booted and the portal helper runs from `/usr/lib/mo-remote`.
The first live iPhone session delivered pointer input and H.264 via NVENC.
After reboot, no portal renewal appeared in the observed log window; the phone
still reported freezes on cellular Tailscale. The `source 0x0` log line also
records a streaming-off event and alone does not prove HDMI dropped. The fix
cannot keep a disconnected physical output available to KDE. A cellular-link
endurance/control proof is still needed.

**MoPlayer, merged and delivered on `.964`:** the "freeze" was a 278 MB Hive catalogue decoded on the UI isolate each launch (~6 s, 1.4 GB) plus a 4.9 GB idle GPU reservation from Impeller gradient shaders and window-sized layers. The merged source moves catalogue work to isolates (~1.3 s, 0.5 GB), reduces idle GPU use to ~0.6 GB, reads get.php links as Xtream accounts, sorts playlists, supports MAC portals and ships Horizon UI. A 4K HEVC live stream and 1080p VOD played on the station from the source bundle; 255 Flutter tests passed. The local launcher that shadowed `.964` is now backed up, and the signed launcher is selected. Open: a real MAC portal, ~1 GB kept after Stop and installed playback readback (plan P2.13).

**Mira, 2026-10-02:** PRs #177–#180 integrate her six pages, approvals inbox, chat history, KDE entry, new Mo AI actions and ARM packaging. Signed x86/ARM builds include her; the station's earlier user install proved Arabic voice, a live approval and the page renders. Installed `.967` face was captured. A topic-source live Gemini voice turn on 2026-10-02 proved mouth energy returning to zero in pauses and at idle; 89 controller/QML/voice tests pass. New registered eye/lip patches preserve original portraits. Signed motion delivery and owner-spoken endurance remain open. See `mira/README.md`.

## Source and release truth
- **Proven production source is `59e97672`, `44.20261001.967`**: signed x86 build
  `36914573577`, QCOW2 `36922199025`/`36922205044`/`36922210323`, offline ISO
  `36922215953`, x86 promotion `36927117927`; ARM build/boot proof
  `36914559982`. The NVIDIA station boots its signed digest, with `.964` retained.
- Candidate `36940680423` failed on upstream registry HTTP 503 (generic/cloud); no x86 promotion. ARM `36940635747` passed. A new coherent motion/Remote candidate is needed.
- Remote v46 and the geometry fix are installed. iPhone pointer input reached
  the host; continuous phone/WAN endurance remains open. HDMI hotplug is an
  independent blocker.
- The two-icon design approval remains pending. Post-`.967` checks passed 55/0
  and 53 checks with two notes; the HDMI disconnect remains open.
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
| Desktop | Plasma/KWin 6.7.5, Wayland, 3840×2160@60, scale 250% (1536×864 logical) on 2026-10-01 |
| Kernel | `7.2.7-200.fc44.x86_64` (2026-10-01) |
| Network | Intel AX210 Wi-Fi/Bluetooth + RTL8125 Ethernet |
| Health | Baloo recovered; post-update 55/0; powersave changed to balanced, turbo read back enabled |
| Freeze audit (2026-10-01) | 3.7 GiB in zram, no OOM this boot. Mo PC Remote renewed its portal grant ~2,600 times in the previous boot; `.964` logged repeated `1536x864+0+0@3 -> no outputs`. Live monitoring found the HDMI connector itself disconnecting for about one second, and KDE closed its portal session when that happened. The signed `.967` fix suppresses an extra geometry-triggered restart during the dropout; live cellular endurance proof is pending. `moai-control` woke rpm-ostreed 59× in 2 h 50 min, now once per boot. The Echo gadget's USB microphone floods the kernel log (~60 xHCI "buffer overrun" warnings/s, journald ~3% CPU): the 500 MB journal spans only ~5 h, so the previous boot's user logs were already gone. The fix is the gadget's packet size (Mira) |

**Remote control:** signed `.967` includes the weak-link ladder, H.264 recovery and
flat pointer mapping. Live iPhone/DERP testing found Auto returning to a 1320 px
Balanced stream despite ~50–60 ms RTT; manually choosing 1024 px Data Saver
stabilized the reported session. Source v49 now caps phone Auto at Data Saver when
Safari hides its link class. The temporary user service serves v49; sustained
owner reported a stable short v49 cellular trial at 1024 px; longer endurance and signed delivery remain open (plan P2.14).
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

- **W9.10 — Mo AI's desktop hands (source, `THEME_REV` 96, 2026-09-28).** `moos-control` gains
  14 fixed verbs so the brain runs the whole desktop: a window BY NAME (focus/min/max/full/
  keep-above/close), move/go/add/remove desktop, media, lock, reminders, open a page or folder,
  animation speed, auto-lock, click. Each read back through KDE's own interfaces (KWin window
  search + `getWindowInfo`, `VirtualDesktop`, MPRIS, ScreenSaver, `systemd-run --user`, KConfig);
  free text is only a search term/reminder/http(s), free-text verbs stay OFF `moos://`; close and
  auto-lock-off ask first. Exercised live on the A1 KDE session, read back from KWin; `just check`
  green. Owed: installed-image + new-case action measurement. **P3.9 `run_command` still NOT
  built** (owner re-asked 2026-09-28).
- A signed build passes every image gate for all three x86 editions; every disk boots
  twice under QEMU/KVM; each final ISO installs offline, logs in, opens every first-party
  app twice, reboots and powers off. `pr-image-gates.yml` builds the generic image on a
  pull request and pushes nothing (16m54s on PR #141).
- Horizon motion gates cover finite settling, reversal, hidden state, reduced motion and
  pointer/key paths on a real Qt runtime.
- **W8 material arrival is in source (`THEME_REV` 85):** one finite glint/1.5% settle on shared
  glass, still under Reduced Motion; real Qt changed at 60 ms and rested by 900 ms. **W9 source:**
  Settings deep-links Update, Recovery and Remote to their transaction owners, with owner-read
  busy/superseded update, queued rollback and failed Remote rows (Arabic/English light/dark Qt
  captures passed). Installed routes and real transactions remain unproven; neither is installed.

## Development environment

- On the station: VS Code is a Flatpak; host work uses `flatpak-spawn --host`. There is
  **no C++ toolchain**, so any gate needing one skips here. `just workstation-check` is a
  read-only inventory; .NET `10.0.401` and Flutter 3.47.4 are installed. Pointer review
  goes through `scripts/station/pointer.py` — KWin confirms every position before a click.
- Off the station: Windows 11 + WSL2 `FedoraLinux-44`. `scripts/review/` holds the toolchain
  installer, the gate mirror and the from-source renderers; `release-candidate.sh` needs `TMPDIR`.

## ARM station `moos-arm-oracle` (Oracle A1, measured 2026-09-21)

The only ARM MoOS machine: 2 vCPU / 11 GiB, `kwin_wayland --virtual 1920x1080 --xwayland`.
**Read back 2026-09-24:** signed `moos-arm@sha256:eff234df…` = `44.20260923.568` (ARM
`latest`), kernel `7.2.7-200.fc44.aarch64`, Plasma 6.7.5, Qt 6.11.2, no failed units. The rest
was measured on `.545`: `blessed`/`attempts: 0`, `post-update-check.sh` 55/0, `moos-selfcheck`
50 passed + 3 owner-choice notes. Idle cost over 10 s of `/proc/<pid>/stat`: `kwin_wayland`
**2.1%**, `plasmashell` **0.6%** of one core (`ps`'s ~26% is a lifetime average with startup).

**Seen on the live A1 on 2026-09-24, and fixed in source with a gate:** the MoOS Bar and Dolphin
read LTR in Arabic, GTK windows drew Adwaita light, App Drop's `ask()` returned False (no
kdialog), the privacy monitor ran blind (no pw-dump). All eight capabilities come from x86's base;
`build-arm.sh` now names them and `verify_desktop_parity.py` passes on the published x86 image and
a full local ARM build. Mo AI's chat texture drew stray logos on the software scene graph (fixed,
runtime-gated); it answered in 0.65 s on the free route, APIs loopback-only. Three readings look
like defects and are not (`cost_policy: "paid"`, `"gateway": false`, sandboxed
`systemd-tmpfiles`): see the plan.

## Plasma 6.8 readiness (measured 2026-09-24; detail in plan row P6.7)

On KDE SIG's 6.8 beta (`6.7.90`) MoOS's 6.7 lock screen falls back to the emergency locker (6.8
removed `VirtualKeyboardLoader`). **Canary run `35980381601` built the whole generic image on
6.7.90 with every in-image gate green:** the seam gate picked set 6.8, matched ten digests and
loaded the merged lock screen in the real greeter; PR #161's 6.7.5 builds pass it too. CI also
fixed Breeze Global Themes hidden on x86 (one shared step) and flagged a libplasma soname bump
that removes `kcm-fcitx5` until Fedora rebuilds it. No 6.8 candidate yet.

## Open evidence gaps

- **W9.9 source, live from the worktree (2026-09-25):** the seven System Settings modules on the
  station — MoOS group first; "Linux 7.2.7", "MoOS for NVIDIA graphics"; Update's three rows; Mo
  AI GET-only; MoOS Themes marks the Arena look. `moai-measure-actions` (65 cases, ar+en):
  **126/130 = 96.9%** on `nex-n2.5-pro:free` (3 timeouts, 1 wrong tool). The installed one-module
  `.929` KCM (packager kernel tag, English Input Method, wrong window class) is fixed in W9.9
  source. Owed: installed image, THEME_REV 86 migration, Meta+Space after login, update/rollback.
- **Testing side effects, now gated (2026-09-24/25):** repo tests wrote fake `moai-do`/`moos-update`
  audit lines and dumped `bluetoothctl` core; tests now stub `logger` under a meta-gate and skip
  Bluetooth without a system bus.

- M1 visual/accessibility matrix: English/German, light/dark, reduced motion, 1080p–4K,
  100–250%, island Remote/Media (Arabic only so far).
- Hardware: suspend/resume, multi-monitor, audio/network recovery, deliberate rollback,
  photographed boot/login, laptop and touch hardware, ARM on a physical seat.
- Versioned, failure-tested Mo AI/Store/core contracts and one lifecycle across every
  adapter. APK installation now has the Store authority; shared cancel/remove/retry and
  stable cross-engine app IDs remain P4.1 work.
- Owner decision P3.9: a Mo AI tool that runs a command the model wrote. Re-asked
  2026-09-28; not built. W9.10's 14 fixed desktop hands cover the control it wanted safely.
## Other measured facts

**The free brain is measured where it runs (2026-09-18):** the catalogue carried **21**
tool-capable zero-price models. `moai-measure-free` asks each two fixed questions through the
real gateway and writes `~/.local/state/moai/free-ranking.json`, which `moai_cloud_policy`
prefers for 30 days without adding a model, a price or a billed route. P0.5 owes the key
entered through Settings, a reboot and the provider-failure surface.

**A second desktop server:** `moos-health scan` found `krdpserver` on `tcp *:3389` beside Mo PC
Remote; the finding carries `moos://privacy/stop-sharing`, and `moos-remote-guard off` stops and
un-autostarts both with no administrator rights.
