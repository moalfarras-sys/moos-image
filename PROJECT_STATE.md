# MoOS current state

Current measured facts only; Git owns history. Last measured 2026-09-19 after owner reboot.

**This block is the only place in the repository that states a version number.** The plan,
the README and every wave row point here instead of repeating it. Four parallel copies of
"production is X" is how three of them came to be a release behind at once.

## Source and release truth

- **Two live findings, 2026-09-19.** Selfcheck warned "configure a cloud key" on a
  single-model catalogue, which a real free Arabic reply disproved; it now reads the
  catalogue without inferring inference readiness. And four Chrome launches failed with
  the document portal running without its FUSE mount — repaired by restarting
  `xdg-document-portal` alone, gated by five tests. **Root cause unproven.**
- **Published, and now running here.** Read back from the registry (`skopeo inspect
  …:latest`): `moos`, `moos-nvidia`, `moos-cloud` = **`44.20260919.894`**, `moos-arm` =
  **`44.20260919.507`** — **all four from revision `2e0d64dc`**, the second time both
  architectures sit on one revision and the first time a dispatched cycle put them there.
  Its cycle: build `35409127347`, disks `35410638993`/`35410641400`/`35410643663`, ISO
  `35410645542`, x86 promotion `35413165564`; ARM dispatch `35410647421` completed its own
  boot and promotion, which is the dispatch-promotion evidence P0.6 was waiting for.
  `main` and `origin/main` are both `2e0d64dc`, with no open PRs and no active runners.
  Later nightly builds are not new release evidence.
- **After owner reboot:** booted signed NVIDIA **`44.20260919.894`**, digest
  `47dc4c6d02984e47042ae165471387a30cc3c973669464006939d96cfeacce9c`;
  signed **`44.20260918.892`** retained for rollback; nothing staged.
  Post-update gate **55 passed**, source selfcheck **52 passed/one optional-tray note**;
  zero failed units, document portal mount healthy. Installed theme revision **71**.
- **Store file entry (source only):** the Store shows what this machine can run, from
  the engine registry, and takes a file by drag or picker into App Drop's default-No
  consent. Four reviewers plus an adversarial verifier: containment held under real
  probing (outside-home paths, symlink escapes, FIFOs, device nodes and non-owned files
  refused; argv never a shell); six defects fixed, five gaps recorded in the plan.
  Rendered on a real engine in Arabic. **Not proven:** a drop-to-launch journey; no
  image or signed artifact yet.

- `main` is the only long-lived branch; every merged topic branch is deleted. The intermittent
  `plymouthd` SEGV (P0.7) is open on ARM and, since cycle D, on x86.
- A merged commit or locally built image is not an installed or released state.
  Production moves only after the exact candidate passes 3×QCOW2 + ISO; ARM is
  separately required evidence.

## App engines — what this machine can actually run

Measured 2026-09-19: `wine` **installed** (`build.sh` `_core_power`, every desktop
edition), `waydroid` **installed but not initialized** (its ~1 GB image was never
fetched), `flatpak` from the base. `/usr/libexec/moos-app-engine` resolves a `.exe`
here as `chosen=wine, ready=true, needs_setup=false` — no download needed, which is
what `build.sh` intended and what the runner did not know until now; an `.apk`
resolves as `needs_setup=true`. **Not proven:** no real `.exe` or `.apk` has been run
end to end on the station. The decision is gated on a real engine; the execution is
not. Plan row A1.

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

Measured after owner reboot: installed `THEME_REV` **71**,
Global Theme `org.moos.ui2.amethyst`, visual tier **flagship**, motion `alive`,
`kwinrc/Plugins/blurEnabled=true`, Arabic session (`ar_SA.UTF-8`). **Source is at
`THEME_REV` 75** — newer local source is not installed.
Health checks do not qualify suspend, every app or all visual surfaces.

**Speed, measured on cycle H's `.890` five minutes after boot** (`moos-measure-speed`, P5.4;
the booted image is now `.894` and these have NOT been re-measured on it):
MoOS's share of boot **6.70 s** / 9.0, login to a ready desktop **1.10 s** / 3.0, an app's
window appearing **0.49 s** / 4.0, MoOS's own processes **0.12%** of the CPU while idle /
8.0. All four inside budget.

**Mo AI, measured on cycle H's `.890`:** the picker's first group is what this machine measured,
and `moai-measure-actions` read **80/80** and **79/80** across two runs of 40 fixed
Arabic/English cases — no wrong tool in either run; the one miss was the model answering
in words instead of calling (P3.3).

**Updating it:** MoOS origins are digest-pinned, so `bootc upgrade` reports "no
changes" forever. Use the MoOS Updater (Settings → Update MoOS, or Mo AI's "Update
my system"), or wait for the nightly train; then restart.

## Closed reviews — what they established

- **W2–W6 on the station** (2026-09-17/18, `.858` and `.862`): every row passed — booted
  version and retained deployment, the first-login shadow sweep, Hub controls from the
  desktop's own menu, a widget removed with an undo, MoOS Search's inline answer
  (`12*7` → **84**), the Island's privacy chip naming the capturing app, App Drop
  installing and removing a real 8.4 MB AppImage, a dismissed administrator prompt
  staging nothing and saying so. Frames in `~/.cache/moos-station-review{,2}/`.
  **Still owed on a desk:** an Island **Store** job in the foreground (the Remote chip
  outranks it while Mo PC Remote runs).
- **W6.1–W6.3** are in production: Settings' "About this device" (P2.9), Mo AI's twelve
  read-only repair playbooks (43 tools: 30 run at once, 13 ask first) with eight one-tap
  chips (P3.10), and Mo AI's rail corrected at the default 940 px window.
- **Mo AI's brain, measured since:** a real free model drives the tool loop (W8.3, PR
  #131), eight free models were ranked on this machine (W8.5), and action selection is
  measured (W9.1 — see the station block above). **Still owed:** the same 40 cases on a
  second model and a second machine.

## Proven source/image behavior

- Cycles B and C: the signed builds passed every image gate for all three x86 editions;
  every disk booted twice under QEMU/KVM; each final ISO installed offline, logged in,
  opened every first-party app twice, rebooted and powered off. `pr-image-gates.yml`
  builds the generic image on a pull request in 16 minutes and pushes nothing.
- Horizon motion gates cover finite settling, reversal, hidden state, reduced motion and
  pointer/key paths; MoOS motion roles follow the owner's animation speed on a real Qt
  runtime.

## Development environment

- On the station: VS Code is a Flatpak; host work uses `flatpak-spawn --host`.
  `just workstation-check` is a read-only inventory; .NET SDK `10.0.401` and Flutter
  3.47.4 (the image-builder pin) are installed. Pointer-driven review goes through
  `scripts/station/pointer.py` — KWin confirms every position before a click.
- Off the station: Windows 11 + WSL2 `FedoraLinux-44`. `scripts/review/` holds the
  toolchain installer, the gate mirror and the from-source renderers;
  `scripts/release-candidate.sh` needs `TMPDIR` under Git Bash. `.kilo/` is local
  untracked agent state, not product source.

## A1 live review (2026-09-18, ARM under `kwin --virtual`, Arabic)

- Input on a seatless session: KWin's `org.kde.KWin.EIS.RemoteDesktop.connectToEIS` (portal
  numbering: keyboard 1, pointer 2, touch 4) plus libei — never Mo PC Remote's portal token.
- Works: Search answers, launcher, About, What's new; Mo AI answered in 15–37 s (P3.2 open).
- ARM: Mo AI hides the NVIDIA and PC-games chips; `moai-do` refuses gaming/Windows setup on
  non-x86 before asking. Mo AI's real-window tests run in a Fedora 44 toolbox (Qt 6.11.2,
  Kirigami 6.30): rail green; the three agent-loop window tests fail on `main` too (P3.4).

## Open evidence gaps

- M1 visual/accessibility matrix: English/German, light/dark, reduced motion, 1080p–4K,
  100–250%, island Remote/Media switching (Arabic reviewed only).
- Hardware: suspend/resume, multi-monitor, audio/network recovery, deliberate rollback
  and photographed boot/login; laptop and touch hardware; ARM on a physical seat.
- Versioned, failure-tested Mo AI/Store/core contracts and a single application
  transaction authority.
- Owner decision P3.9: whether Mo AI ever gets a tool that runs a command the model
  wrote. Until it is taken, no such tool exists.

## A wallpaper cannot be clicked (2026-09-18)

Measured on the station: over a MoOS Hub card, neither a click nor a wheel arrives — the
desktop containment takes both, because the Hub lives in the wallpaper (which is also why
it can never cover an icon or a window). So every card's second face is turned from the
desktop's own menu, and anything the Hub gains follows that rule.

## The free brain is measured on the machine that uses it (2026-09-18)

A shipped preference list ages against a catalogue that turns over every few weeks — on
2026-09-18 the free catalogue carried **21 tool-capable zero-price models**.
`moai-measure-free` asks each candidate two fixed questions through the real gateway,
using MoOS's own shipped schemas, and writes the order that answered to
`~/.local/state/moai/free-ranking.json`; `moai_cloud_policy` prefers it for 30 days and
can never let it introduce a model, change a price or reach a billed route. Unmeasured
candidates rank by **context first**. It has run here twice (see the station block);
timings vary enough between runs to change the order, so the card reports when it was
measured. P0.5 still owes the key entered through Settings, surviving a reboot, and the
provider-failure surface.

**MoOS found a second desktop server on its own machine.** `moos-health scan` reported
KDE's `krdpserver` listening on `tcp *:3389` for the whole network with
`SystemUserEnabled=true`, beside Mo PC Remote (private tailnet, PIN, on-screen
indicator). The finding now carries `moos://privacy/stop-sharing`, and
`moos-remote-guard off` stops and un-autostarts the two named KDE sharing services with
no administrator rights and nothing removed. Run once on the station after the update.

## Next execution

Two backlogs in `docs/DEVELOPMENT_PLAN.md`: “Every app, one verb” (rows A1–A5) and
“Design completion handoff”. A1 is the nearest owed evidence — a real `.exe` and a real
`.apk` run end to end on this station. The next reboot must be followed by an actual
signed-version and `THEME_REV` readback. P0.7 remains unresolved.

## Local branch, not released — `feat/moos-design-studio-20260919`

Four commits, `just check` green (exit 0, 198 gates) on the station.

- **Glass reads the owner's answer the way KWin reads it.** The token reader consulted
  only the user's `kwinrc`, wrote a personal override while reading, and understood four
  of KConfig's twelve boolean spellings — so `blurEnabled=off`, which KWin honours, was
  skipped and the decision handed to `/etc/xdg`. Nine cases green on a real Qt engine.
- **The glass stops being decided once at start-up.** A session service publishes what
  the compositor is actually doing; surfaces follow it live. Closes the case where
  `moos-fast-remote` turns blur off mid-session and open windows keep painting thin
  glass. Five real-engine cases, proven to fail when the live half is removed.
  `THEME_REV` 75.
- **The lock screen was one `dnf5` transaction away from being Breeze.** MoOS overwrites
  six `plasma-desktop` files; the survival gate listed two, on both architectures.
- **One app-engine registry.** See the app-engine block above.

No user theme shadow or installed system artwork was replaced; no desktop capture is
committed.
