# MoOS current state

Current measured facts only; Git owns history. Last measured 2026-09-19 after owner reboot.

**This block is the only place in the repository that states a version number.** The plan,
the README and every wave row point here instead of repeating it. Four parallel copies of
"production is X" is how three of them came to be a release behind at once.

## Source and release truth

- **Production moved, but the station must not take it yet.** Registry readback on
  2026-09-19: `moos`, `moos-nvidia`, `moos-cloud` = **`44.20260919.899`** and
  `moos-arm` = **`44.20260919.515`**, all revision **`fbf393f4`**. The x86 cycle passed
  signed build `35461545885`, QCOW2 `35462838874`/`35462840914`/`35462843175`, ISO
  `35462844969`, and promotion `35465072636`; ARM also reached the same revision.
  A real KDialog test then proved its App Drop primary button accepts Enter. Production
  tags moved before the local release process could be stopped. Treat this release as
  superseded: build and promote the corrective revision before updating a workstation.
- `main` and `origin/main` are `fbf393f4`; the corrective work is on
  `fix/app-consent-and-runner-20260919`. Merging source never updates this machine.
- **After owner reboot:** booted signed NVIDIA **`44.20260919.894`**, digest
  `47dc4c6d02984e47042ae165471387a30cc3c973669464006939d96cfeacce9c`;
  the updater has since staged affected **`44.20260919.899`** for the next boot, and signed
  **`44.20260918.892`** remains retained. **Do not reboot:** the corrective signed update
  must replace the staged deployment first.
  Post-update gate **55 passed**, source selfcheck **52 passed/one optional-tray note**;
  zero failed units, document portal mount healthy. Installed theme revision **71**.
- **Corrective source, not released:** App Drop now makes KDialog's focused primary
  button Cancel and accepts only the secondary action. On isolated Xvfb/KDialog 26:
  Enter rejects, Escape rejects, Tab+Enter accepts. APK mutation is inside
  `moos-storectl`'s job/lock authority; `.xapk`/`.apks` are refused before consent.
  The Store bridge's six compiled Qt cases passed in a disposable SDK. All 204 source
  gates and one full local generic image build passed; the built image also passed its
  bootc, initramfs, QML-runtime, motion, image-state and identity-firewall gates. Still
  unproven: a pointer drop through an installed image and a signed corrective candidate.

- `main` is the only long-lived branch; every merged topic branch is deleted. The intermittent
  `plymouthd` SEGV (P0.7) is open on ARM and, since cycle D, on x86.
- A merged commit or locally built image is not an installed or released state.
  Production moves only after the exact candidate passes 3×QCOW2 + ISO; ARM is
  separately required evidence.

## App engines — what this machine can actually run

Measured 2026-09-19: `wine` **installed** (`build.sh` `_core_power`, every desktop
edition), `waydroid` **installed but not initialized** (~1 GB image never fetched),
`flatpak` from the base. A `.exe` resolves as `chosen=wine, ready=true,
needs_setup=false` — no download needed, which is what `build.sh` intended and what the
runner did not know until now; an `.apk` resolves as `needs_setup=true`.

**A real PE32+ Windows program ran here (2026-09-19)** with the runner's exact prefix
and printed `Microsoft Windows 10.0.19045`, exit 0. PE32 fails although the complete
new-WoW64 payload is present. The earlier “missing i686, add ~1 GiB” diagnosis was wrong.
Fresh-prefix execution and the audit log establish the immediate cause: SELinux denies
`execmod` while mapping the i386 PE DLL from composefs (`kernel_t` → `lib_t`). Do not
weaken SELinux globally. Corrective source probes MoOS's own PE32 command once per image;
on failure it launches no downloaded code and offers optional isolated support instead.
Native errors are supervised and retained in a user-owned log, never discarded.

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
| Health | zero failed system units and zero failed user units |

Measured after owner reboot: installed `THEME_REV` **71**, Global Theme
`org.moos.ui2.amethyst`, visual tier **flagship**, motion `alive`,
`kwinrc/Plugins/blurEnabled=true`, Arabic session (`ar_SA.UTF-8`). **Source is at
`THEME_REV` 75**, not installed. Health checks do not qualify suspend, every app or all
visual surfaces.

**Speed and Mo AI, both measured on cycle H's `.890`** and NOT re-measured since (the
booted image is `.894`). `moos-measure-speed` (P5.4): MoOS's share of boot **6.70 s**/9.0,
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
