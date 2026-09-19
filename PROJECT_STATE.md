# MoOS current state

Current measured facts only; Git owns history. Last measured 2026-09-19 after owner reboot.

**This block is the only place in the repository that states a version number.** The plan,
the README and every wave row point here instead of repeating it. Four parallel copies of
"production is X" is how three of them came to be a release behind at once.

## Source and release truth

- **`44.20260919.899` is released AND now running on this station.** Registry readback
  2026-09-19: `moos`, `moos-nvidia`, `moos-cloud` = **`44.20260919.899`**, `moos-arm` =
  **`44.20260919.515`**, all revision **`fbf393f4`**. Its cycle: signed build
  `35461545885`, QCOW2 `35462838874`/`35462840914`/`35462843175`, ISO `35462844969`,
  promotion `35465072636` — every x86 proof green before the tag moved.
- **The station rebooted onto it at 23:02** (readback: booted digest `57a64063…` =
  `44.20260919.899`, `44.20260919.894` retained for rollback, `THEME_REV` **75** applied
  on bar and shell). An earlier note here said "do not reboot" because a corrective fix
  was pending; the reboot happened anyway, so the correction is now owed as a release
  rather than as a hold.
- **What `.899` therefore ships, and what it is missing.** It carries the live clarity
  bridge, the lock-screen overlay gate, the app-engine registry and the Store's
  capability row. It does NOT carry the App Drop consent fix: the running
  `/usr/bin/moos-app-drop` still calls `kdialog --warningcontinuecancel`, whose focused
  button is Continue, so **Enter accepts a consent prompt** for running a downloaded
  file. `main` (`460bfee1`, PR #143) puts Cancel on the focused button and accepts only
  the secondary action, so Enter and Escape both fail closed. **That fix is unreleased.**
- **One failed unit after this boot: `plymouth-start.service` (P0.7).** For the first
  time the stack was captured — a use-after-free in the QUIT path, 13 ms after
  `plymouth-quit` reports success, in `on_new_frame` → `ply_list_node_get_data`. Rate on
  this journal: 1 crash in 26 boots. Mechanism and next step are in the plan's P0.7 row.
- `main` is `460bfee1`, ahead of the released `fbf393f4`. Merging source never updates
  this machine.
- `main` is the only long-lived branch; every merged topic branch is deleted.
- A merged commit or locally built image is not an installed or released state.
  Production moves only after the exact candidate passes 3×QCOW2 + ISO; ARM is
  separately required evidence.

## App engines — what this machine can actually run

Measured 2026-09-19: `wine` **installed** (`build.sh` `_core_power`, every desktop
edition), `waydroid` **installed but not initialized** (~1 GB image never fetched),
`flatpak` from the base. A `.exe` resolves as `chosen=wine, ready=true,
needs_setup=false` — no download needed, which is what `build.sh` intended and what the
runner did not know until now; an `.apk` resolves as `needs_setup=true`.

**All three app engines run here (2026-09-20, on `.899`).** **Windows:** Notepad and
Minesweeper launched through `moos-run-foreign` — the double-click path — appeared wearing
**MoOS's own decoration** and listed in the **MoOS Bar**; resolver `ready=true,
chosen=wine`, no download. **Linux:** install → launch → remove entirely through
`moos-storectl`. **Android: it had never worked, and now does.** `moai-do setup-waydroid`
called `waydroid init` without the mandatory OTA channels, which neither MoOS nor Fedora's
package supplies a config for, so it failed every time before downloading a byte — every
gate read the source, where each half looked right. Passing the channels fixed it: **2.3 GB
downloaded**, container `RUNNING`, a real APK installed via `moos-storectl install-file`,
and **F-Droid opened on the desktop** with its icon in the MoOS Bar. Frames in
`test-results/a1-live/`. PE32 (32-bit) still fails although the new-WoW64 payload is
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
| Health | **one** failed system unit (`plymouth-start`, P0.7); zero failed user units |

Measured after the 23:02 reboot onto `.899`: installed `THEME_REV` **75** (bar and
shell), Global Theme `org.moos.ui2.amethyst`, visual tier **flagship**, motion `alive`,
`kwinrc/Plugins/blurEnabled=true`, Arabic session (`ar_SA.UTF-8`). Source and desk are on
the same revision for the first time since W9.6. Health checks do not qualify suspend,
every app or all visual surfaces.

**Speed and Mo AI, both measured on cycle H's `.890`** and NOT re-measured since (the
booted image is now `.899`, two releases later). `moos-measure-speed` (P5.4): MoOS's share of boot **6.70 s**/9.0,
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

Review and merge the corrective source as one slice, then use
`scripts/release-candidate.sh --promote` once. Its 204 source gates, isolated KDialog
runtime proof and full local generic image build are green. Promotion
requires the signed build, three QCOW2 boots and ISO installed-system proof for the exact
revision; ARM remains separate evidence. Only then stage the signed NVIDIA digest on
this station, reboot, and read back version, signature origin, theme revision, failed
units and the real double-click journeys. A1/A4 remain open until installed evidence.
P0.7's intermittent Plymouth crash, P4.2–P4.5 and the visual/hardware matrix remain open.
