# MoOS current state — measured 2026-09-23
Current measured facts only; Git owns history.

**This block is the only place in the repository that states a version number.** The plan,
the README and every wave row point here instead of repeating it. Four parallel copies of
"production is X" is how three of them came to be a release behind at once.

## Source and release truth
- **`44.20260923.920` is released and booted on the NVIDIA station:** signed digest
  `sha256:7583f605753780dedf6c364ba43ff04242a86d0a918ae33e10fbe6de2b7fea44`,
  candidate revision `3b6f8e94`, signed build `35878094873`, generic/NVIDIA/cloud QCOW2
  `35881259100`/`35881263671`/`35881269531`, ISO `35881275455`, and promotion
  `35887376140` all green. Live `post-update-check.sh` passed 55/0 against that digest;
  `moos-selfcheck` passed 53 with one owner-configurable tray note, zero failed units,
  and signed `.914` retained for rollback. `fwupd` was restored and offered no update.
- PR #157 integrated W8/W9, ARM app parity, Store honesty and the NVIDIA device gate.
  PR #158 raised ARM's finite first-boot Flatpak timeout
  from 30 to 120 seconds. The no-GPU NVIDIA VM boots twice with zero failed units.
- **ARM `latest` is boot-proven** `sha256:1d281ceb04f888739da4c9ed55607a24498a3a7ed100611154c347586b41fe4c`
  from `f2e798ab` (build/boot/promotion `35887322112`). The 120-second fix passed
  exact branch image and two-boot proof `35889416840`; merged tree equals that proof.
  `main` run `35912079424` is building before the fixed image can promote. P0.7 remains open.
- **P0.7 is no longer only a captured stack.** Read out of plymouth 24.004.60's source on
  2026-09-21: `ply_boot_splash_free()` frees `pixel_displays` without disarming the
  `on_new_frame` timeout that only `ply_boot_splash_hide()` disarms, and `--retain-splash`
  is the path that skips that hide. An upstream defect MoOS's flag exposes; both recorded
  workarounds are disproven. See the plan, P0.7.
- A merged commit or locally built image is not an installed or released state.
  Production moves only after the exact candidate passes 3×QCOW2 + ISO; ARM is
  separately required evidence.

## App engines — what this machine can actually run

`wine` is installed by the image on every desktop edition, the Android environment is now
initialized and running, and Linux applications use the image's application service. A
`.exe` resolves as `chosen=wine, ready=true, needs_setup=false`; an `.apk` installs only
through App Drop → `moos-storectl`, with the same job and lock as catalogue installs.

**All three app engines run here (2026-09-20; evidence acquired before `.912`, whose
source contains the same paths).** **Windows:** Notepad and
Minesweeper launched through `moos-run-foreign` — the double-click path — appeared wearing
**MoOS's own decoration** and listed in the **MoOS Bar**; resolver `ready=true,
chosen=wine`, no download. **Linux:** install → launch → remove entirely through
`moos-storectl`. **Android: it had never worked, and now does.** `moai-do setup-waydroid`
called `waydroid init` without the mandatory OTA channels, which neither MoOS nor Fedora's
package supplies a config for, so it failed every time before downloading a byte — every
gate read the source, where each half looked right. Passing the channels fixed it: **2.3 GB
downloaded**, container `RUNNING`, a real APK installed via `moos-storectl install-file`,
and **F-Droid opened on the desktop** with its icon in the MoOS Bar. Since then, publisher
APK builds of VLC and Organic Maps were digest-checked and installed; VLC was installed,
launched and removed through the source Store adapter, and its real resizable window is
recorded in `test-results/android-vlc-source-live.png`. PuTTY PE32+ ran through the MoOS
file route with the MoOS decoration. The active source now derives the Windows UI density
from the live desktop (96–192 DPI); on this 4K station PuTTY grew from 178×331 to 348×591
logical pixels with its controls genuinely scaled, not an empty stretched frame. PE32
(32-bit) still fails although the new-WoW64 payload is
complete; the audit log gives the cause — SELinux denies `execmod` while mapping the i386
PE DLL from composefs (`kernel_t` → `lib_t`). The earlier "missing i686, add ~1 GiB"
diagnosis was wrong. Do not weaken SELinux globally.

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
  read-only repair playbooks (43 tools, 13 ask first) with eight chips (P3.10), and Mo
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

The second real MoOS machine and the only ARM one, so ARM regressions surface here outside
CI. 2 vCPU / 11 GiB, kernel `7.2.5-200.fc44.aarch64`, Wayland/KDE under `kwin_wayland
--virtual 1920x1080 --xwayland`. Booted origin is signed `moos-arm@sha256:513ab151…` =
`44.20260920.545`, which **is** `moos-arm:latest` — the station is current, `.542` is its
rollback, `boot-assessment.json` reads `blessed`/`attempts: 0`/no failed units,
`post-update-check.sh` 55/0 and `moos-selfcheck` 50 passed + 3 owner-choice notes. Idle
cost over 10 s of `/proc/<pid>/stat`: `kwin_wayland` **2.1%**, `plasmashell` **0.6%** of
one core (`ps` shows ~26% only because that is a lifetime average including startup).

Apps were run, not just started: Mo AI, MoPlayer and Mo Store rendered on the live desktop
(Arabic RTL, Liquid Glass, MoOS Bar), Mo Store rebuilt its index to **2941 apps**, and all
closed with both failed-unit sets still empty. Mo PC Remote is active on loopback `:8765`
only, over Tailscale. No duplicate desktop `Name=`, no broken `moos-*`/`moai*` symlinks.
Mo AI answers: `POST /v1/chat/completions` returned in **0.65 s** via
`nex-agi/nex-n2.5-pro:free` with `"cost": 0` and `X-MoAI-Route-Reason: free-cloud-only`;
its three APIs bind loopback only and reject unauthenticated calls in ~1 ms. Earlier A1
findings hold: seatless input uses KWin's EIS/libei, `moai-do` refuses gaming/Windows
setup on non-x86. Three readings here look like defects and are not — `cost_policy:
"paid"`, `"gateway": false`, and `just check` failing on `systemd-tmpfiles` in the Flatpak
sandbox; the plan says why, under its own heading. Do not "fix" them.

## Open evidence gaps

- M1 visual/accessibility matrix: English/German, light/dark, reduced motion, 1080p–4K,
  100–250%, island Remote/Media (Arabic only so far).
- Hardware: suspend/resume, multi-monitor, audio/network recovery, deliberate rollback,
  photographed boot/login, laptop and touch hardware, ARM on a physical seat.
- Versioned, failure-tested Mo AI/Store/core contracts and one lifecycle across every
  adapter. APK installation now has the Store authority; shared cancel/remove/retry and
  stable cross-engine app IDs remain P4.1 work.
- Owner decision P3.9: whether Mo AI ever gets a tool that runs a command the model
  wrote. Until it is taken, no such tool exists.

## A wallpaper cannot be clicked (2026-09-18)

Measured: over a MoOS Hub card neither a click nor a wheel arrives — the desktop
containment takes both, because the Hub lives in the wallpaper. Every card's second face
is therefore turned from the desktop's own menu, and anything the Hub gains follows.

## The free brain is measured on the machine that uses it (2026-09-18)

A shipped preference list ages against a catalogue that turns over every few weeks — on
2026-09-18 the free catalogue carried **21 tool-capable zero-price models**.
`moai-measure-free` asks each candidate two fixed questions through the real gateway
using MoOS's own schemas, and writes the order that answered to
`~/.local/state/moai/free-ranking.json`; `moai_cloud_policy` prefers it for 30 days and
can never let it introduce a model, change a price or reach a billed route. It has run
here twice; timings vary enough to change the order, so the card says when it was
measured. P0.5 still owes the key entered through Settings, a reboot, and the
provider-failure surface.

**MoOS found a second desktop server on its own machine.** `moos-health scan` reported
`krdpserver` listening on `tcp *:3389` for the whole network with
`SystemUserEnabled=true`, beside Mo PC Remote (private tailnet, PIN, on-screen
indicator). The finding carries `moos://privacy/stop-sharing`, and `moos-remote-guard
off` stops and un-autostarts both sharing services with no administrator rights.

## Next execution
Finish W9's real transaction lifecycle and W8's three-size mark. Resolve P0.7 before
another ARM promotion; P4.2–P4.5, German, touch/laptop/multi-output and full accessibility remain open.
