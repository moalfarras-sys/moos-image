# MoOS current state
Current measured facts only; Git owns history. Last measured 2026-09-20 on the running station.

**This block is the only place in the repository that states a version number.** The plan,
the README and every wave row point here instead of repeating it. Four parallel copies of
"production is X" is how three of them came to be a release behind at once.

## Source and release truth

- **`44.20260920.912` is released and running on this station.** Booted origin is the
  signed NVIDIA image at digest
  `sha256:2802d58aed183f5fc94382b15a49f6f378d7bb453979623327809685166cca0c`;
  `.907` is retained as rollback. The exact revision is `22b9725f`. Its complete proof
  set is green: signed build `35521450125`, generic/NVIDIA/cloud QCOW2
  `35522602100` / `35522604429` / `35522606800`, ISO `35522608956`, ARM
  `35522610892`, and x86 promotion `35525068423`.
- **Installed readback after reboot is clean:** `tests/post-update-check.sh` reports
  55 passed / 0 failed, `moos-selfcheck` reports 53 passed plus the intentional tray
  preference note, and both system and user failed-unit sets are empty. Installed
  `THEME_REV` is **83**. Search was then exercised on the booted Arabic 4K/265% desktop:
  its bar button opens the embedded MoOS Search rather than the launcher, keyboard input
  `الملفات` returned apps/settings/recent-file rows, and the compact Island stayed fixed.
- The previous App Drop default-accept defect and the staged-update replacement defect
  are therefore no longer merely source fixes: both are in the signed image this machine
  boots. P0.7 remains an intermittent risk with a captured historical mechanism, but this
  boot has no Plymouth failure.
- `main` and `origin/main` are `22b9725f`. Current work is isolated on
  `feat/glass-clarity-control-20260920`; merging source still deploys nothing until a new
  candidate completes the artifact proof and promotion path.
- `main` is the only long-lived branch; every merged topic branch is deleted.
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
| Kernel | `7.2.5-200.fc44.x86_64` |
| Network | Intel AX210 Wi-Fi/Bluetooth + RTL8125 Ethernet |
| Health | zero failed system units; zero failed user units (P0.7 remains intermittent) |

Measured after reboot onto the current signed image: installed `THEME_REV` **83**,
Global Theme `org.moos.ui2.midnight`, visual tier **flagship**, motion `alive`,
`kwinrc/Plugins/blurEnabled=true`, Arabic session (`ar_SA.UTF-8`). Source and desk are on
the same revision for the first time since W9.6. Health checks do not qualify suspend,
every app or all visual surfaces.

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

## Development environment

- On the station: VS Code is a Flatpak; host work uses `flatpak-spawn --host`. There is
  **no C++ toolchain**, so any gate needing one skips here. `just workstation-check` is a
  read-only inventory; .NET `10.0.401` and Flutter 3.47.4 are installed. Pointer review
  goes through `scripts/station/pointer.py` — KWin confirms every position before a click.
- Off the station: Windows 11 + WSL2 `FedoraLinux-44`. `scripts/review/` holds the
  toolchain installer, the gate mirror and the from-source renderers;
  `scripts/release-candidate.sh` needs `TMPDIR` under Git Bash.

## A1 live review (2026-09-18, ARM under `kwin --virtual`, Arabic)

- Input on a seatless session: KWin's `org.kde.KWin.EIS.RemoteDesktop.connectToEIS`
  (portal numbering: keyboard 1, pointer 2, touch 4) plus libei — never Mo PC Remote's
  portal token. Works: Search, launcher, About, What's new; Mo AI 15–37 s (P3.2 open).
- ARM: Mo AI hides the NVIDIA and PC-games chips; `moai-do` refuses gaming/Windows setup
  on non-x86 before asking. Its real-window tests run in a Fedora 44 toolbox: rail green;
  the three agent-loop window tests fail on `main` too (P3.4).

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

Finish and review the clarity-control slice, then batch it with the remaining M1 visual
work before the next release cycle. The next signed candidate still owes the same build,
three QCOW2, ISO and ARM evidence before promotion. P0.7's intermittent Plymouth crash,
P4.2–P4.5, English/German session coverage, touch/laptop/multi-output hardware and the
full accessibility/visual matrix remain open.
