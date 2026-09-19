# MoOS current state

Current measured facts only; Git owns history. Last measured 2026-09-19 15:0x local.

**This block is the only place in the repository that states a version number.** The plan,
the README and every wave row point here instead of repeating it. Four parallel copies of
"production is X" is how three of them came to be a release behind at once.

## Source and release truth

- **Published now, read back from the registry 2026-09-19 15:4x** (`skopeo inspect
  …:latest`, `org.opencontainers.image.version`/`.revision`): `moos`, `moos-nvidia` and
  `moos-cloud` = **`44.20260919.894`**, `moos-arm` = **`44.20260919.507`** — **all four
  from revision `2e0d64dc`**. This is the SECOND time both architectures sit on one
  revision, and the first time a dispatched cycle put them there.
- **Current source audit:** local starting `main` and remote `main` both
  `2e0d64dc9c75748fce8a4bb86897e80b6dd6328c`. At the audit there were no open PRs
  or active release runners. Exact-revision dispatch build `35409127347`, disks
  `35410638993` / `35410641400` / `35410643663`, ISO `35410645542` and x86 promotion
  `35413165564` succeeded. ARM dispatch `35410647421` also ran its actual boot and
  promotion steps successfully: the formerly missing dispatch-promotion evidence
  now exists. Later nightly builds are not new x86 release evidence.
- **Current physical readback** (`/ostree/deploy/default/deploy/*.origin`, 2026-09-19
  15:3x): booted signed NVIDIA **`44.20260918.892`**, digest
  `4638eab3481f484d69a7a8404cec430d10d4ccd01b5647e17b45b9765720cf6b`; staged signed
  **`44.20260919.894`**, digest
  `47dc4c6d02984e47042ae165471387a30cc3c973669464006939d96cfeacce9c`; retained signed
  **`44.20260918.890`**, digest `3cb9d545…`, for rollback. Booted 11:07 local, the
  stage written 11:30 — **the desk is one release behind what is published**, and no
  reboot was performed during this audit. The stage is not the running desktop.

- `main` is the only long-lived branch; every merged topic branch is deleted. The intermittent
  `plymouthd` SEGV (P0.7) is open on ARM and, since cycle D, on x86.
- A merged commit or locally built image is not an installed or released state.
  Production moves only after the exact candidate passes 3×QCOW2 + ISO; ARM is
  separately required evidence.

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

Measured on the station 2026-09-19 15:3x: `THEME_REV` **70** applied (bar and shell both
`v70`), Global Theme `org.moos.ui2.amethyst`, visual tier **flagship**, motion `alive`,
`kwinrc/Plugins/blurEnabled=true`, Arabic session (`ar_SA.UTF-8`). **Source is at
`THEME_REV` 74** — the desk is four theme revisions behind, so nothing in W9.6 or later
has been seen here. Health checks do not qualify suspend, every app or all visual surfaces.

**Speed, measured on cycle H's `.890` five minutes after boot** (`moos-measure-speed`, P5.4;
the booted image is now `.892` and these have NOT been re-measured on it):
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
- Fixed (PR #130): bitten capsule ends in 50 icons ("pulse" was a
  speck), one moon for suspend and hibernate (`THEME_REV` 67), Discover's install rows.
- Open (station agent's files): without blur (llvmpipe) Liquid Glass is see-through (P2.5).
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

MoOS Hub lives in the WALLPAPER, which is why it can never cover an icon or a window. The
same property means no pointer event reaches it: measured on the station, neither a click
nor a wheel over a card arrived — the desktop containment takes both. Every card's second
face is therefore turned from the desktop's own menu, beside the card toggles, and
remembered in its own key. Anything the Hub ever gains follows the same rule.

## The free brain is measured on the machine that uses it (2026-09-18)

The shipped preference list was measured on one day against a catalogue that turns over
every few weeks: on 2026-09-18 the free catalogue carried **21 tool-capable zero-price
models**, several newer than that snapshot. `moai-measure-free` asks each candidate two
fixed questions through the real gateway — an Arabic sentence and one tool call, using
MoOS's OWN shipped schemas — and writes the order that answered into
`~/.local/state/moai/free-ranking.json`. `moai_cloud_policy` prefers it for 30 days and
can never let it introduce a model, change a price or reach a billed route; each list
holds only the models that passed the half it ranks. Unmeasured candidates are ranked by
**context first**: an OS agent carries tool schemas, results and confirmations in one
transcript, and parameter count is only guessable from the model id.

It has run here, twice. With the owner's own OpenRouter key: eight zero-price
tool-capable models, two questions each. Six answered in Arabic and emitted the call;
both `thinkingmachines/*` models were refused by the provider with **HTTP 403** in under
0.1 s — a refusal, not a bad answer, and the picker says so. Free-model timings vary
between runs by enough to change the order, so the card reports when it was measured.
What P0.5 still owes is the key entered through Settings, surviving a reboot, and the
provider-failure surface — not the key itself.

**MoOS found a second desktop server on its own machine.** `moos-health scan` reported
KDE's `krdpserver` listening on `tcp *:3389` for the whole network with
`SystemUserEnabled=true`, beside Mo PC Remote (private tailnet, PIN, on-screen
indicator). The finding now carries `moos://privacy/stop-sharing`, and
`moos-remote-guard off` stops and un-autostarts the two named KDE sharing services with
no administrator rights and nothing removed. Run once on the station after the update.

## Next execution

Follow “Design completion handoff” in `docs/DEVELOPMENT_PLAN.md`; it is the sole
execution backlog. P3.3's case runner and P5.4's budgets exist and have measurements;
second-model/machine and broader performance evidence remain open. The next reboot
must be followed by actual signed-version/theme readback. P0.7 remains unresolved.

## Local design foundation (not released)

`feat/moos-design-studio-20260919` repairs a shared material defect: the old token
reader checked only user `kwinrc`, defaulted to blur on and ignored system policy.
The source reader now traverses XDG configuration with user precedence, no writes,
and a readable fallback when policy is unknown. Seven real-Qt tests passed. This
is startup configuration, not runtime/per-window blur detection.

The source Design Studio uses actual shared components and palettes. Native Qt
captures were inspected in English dark and Arabic light, including a 3840×2160
capture; the Arabic studio also ran on the live Wayland session. A pointer click
at compositor-confirmed logical 1046,654 changed three columns into a main pane
and two companions. This is explicitly a sample preview, not live window tiling.
Evidence is local in `test-results/design-studio-20260919/`; no desktop capture is
committed. No user theme shadow or installed system artwork was replaced.
