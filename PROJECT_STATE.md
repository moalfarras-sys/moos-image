# MoOS current state

Current measured facts only; Git owns history. Last measured 2026-09-17.

## Source and release truth

- **All four editions are one revision, `6c4f73c0`** (cycle E: W6.3 + PR #121), read back from
  the registry 2026-09-18 03:32 UTC after promotion run `35303529066`: `moos`, `moos-nvidia`
  and `moos-cloud` `:latest` = `44.20260918.868` (digests `33fef3f39cd5…`, `68c27fffc3cd…`,
  `43791828c947…`, the ones the candidate build signed); `moos-arm:latest` = `44.20260918.458`
  (`build-arm.yml` promotes every green push). Read the registry, not this line.
- **Release cycles, newest first.** E (`6c4f73c0`, x86 `44.20260918.868` / ARM `.458`):
  build `35295680548`, QCOW2 `35297281876`/`35297284491`/`35297287185`, ISO `35297289852`,
  ARM `35297292391`, promotion `35303529066`. D (`96e34695` → `.865`/`.450`): promotion
  `35294288086`; its first generic QCOW2 run was lost to P0.7 and that ONE proof was
  dispatched again. C (`291361ad` → `.862`/`.441`): promotion `35280675992`; its first ISO
  run lost the distribution's mirrors. B (`a8622f95` → `.858`): promotion `35269505270`.
  Between C and D, ARM took W7 alone at `THEME_REV` 63 — the case a shared 63 would have
  stranded (W6.2 is 64). Every run id is in Git history; this file keeps the current one.
- `main` is the only long-lived branch; every merged topic branch is deleted. The intermittent
  `plymouthd` SEGV (P0.7) is open on ARM and, since cycle D, on x86.
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
| Desktop | Plasma/KWin 6.7.5, Wayland, 3840×2160@60, scale 250% (1536×864 logical) |
| Kernel | `7.2.5-200.fc44.x86_64` |
| Network | Intel AX210 Wi-Fi/Bluetooth + RTL8125 Ethernet |
| Health | zero failed system units and zero failed user units |

Last measured ON the station, 2026-09-17 23:07 local: the station is running
**`44.20260917.858`**, `ostree-image-signed` `moos-nvidia@sha256:c8f94adde60d…` —
the digest cycle B signed and promoted — with `44.20260916.848` retained for
rollback. `THEME_REV` 62 is applied (`~/.local/state/moos-ui2-theme-applied.v62`),
zero failed system units and zero failed user units, KWin/Plasma 6.7.5 on Wayland,
3840×2160 at 265% (1450×816 logical), Arabic session, scheme `MoOSUI2AuroraLight`,
visual tier `flagship` (`AnimationDurationFactor=1`, blur on). **So W6 is no longer
unseen: the station is booted on it**, and the review below is the first time W2–W6
were exercised on a MoOS desktop.

**Updating it:** MoOS origins are digest-pinned, so `bootc upgrade` reports "no
changes" forever. Use the MoOS Updater (Settings → Update MoOS, or Mo AI's "Update
my system"), or wait for the nightly train; then restart.

## W8 on the running station (2026-09-18, `44.20260918.868`)

Reviewed with review shadows and `scripts/station/pointer.py`; frames in
`~/.cache/moos-w8/`. Seen on the desk, not rendered: the Island capsule's caption moved
inside the pill (the two pinned lines assumed `panelHeight` 54 while the bar gives 40),
the capsule shows MoPlayer's own icon instead of the theme's "unknown file" sheet, MoOS
Search became an icon-sized button (the old pill was as wide as four app icons and its
field could never take focus), the status cluster went from nine glyphs to four and an
arrow, Aurora Glass gave every MoOS surface a palette-derived rim and one specular
hairline per depth, and MoOS Search shows what is playing with its control.

**MoPlayer, measured on the bus.** `dbus-monitor` caught the desktop asking the new MPRIS
name for its properties 2 ms after it appeared and MoPlayer answering
`org.freedesktop.DBus.Error.UnknownObject` — the object was one `await` behind the name,
and Plasma drops such a player for the life of that shell. Its metadata also went out as
`variant variant string`, so every reader saw an empty title. Both fixed in
`moplayer/lib/services/system/mpris.dart` and gated; they reach the desk with the next
image.

## Station review of W2–W6 (2026-09-17 and 2026-09-18) — closed

Walked on `44.20260917.858` and `.862`; frames in `~/.cache/moos-station-review/` and
`~/.cache/moos-station-review2/`. **Every row passed**: booted version and retained
deployment, the shadow sweep at first login, Hub controls from the desktop's own menu, a
widget removed with an undo, MoOS Search's inline answer (`12*7` → **84**), the Island's
privacy chip naming the capturing app, App Drop installing and removing a real 8.4 MB
AppImage, a dismissed administrator prompt staging nothing and saying so, and secondary
text readable on `MoOSUI2AuroraLight`. Two findings from the last row are fixed in source
(a MoOS-worded polkit action, and pkexec's "This incident has been reported." dropped).

**Still owed on a desk:** an Island **Store** job in the foreground (the Remote chip
outranks it while Mo PC Remote runs), and Mo AI's tool loop, cards and identity answers —
all four need a cloud brain (P0.5, owner action).

## W6.1 — production, and booted on the station (`44.20260917.862`)

Settings' own "About this device" page (P2.9); Mo AI skills — twelve read-only repair
playbooks (`list_skills`/`read_skill`, 43 tools: 30 run at once, 13 ask first) with eight
one-tap chips (P3.10); Mo AI's rail corrected at the default 940 px window.

## Released with cycle D, still unseen on a MoOS desktop: W6.2 and W6.3

W6.2 (`012eac13`) came from the first off-station renders of the desktop itself: in Arabic
the Hub's English date line hung on the far side of a right-aligned column, the Island's
privacy chip was sized by counting characters, and MoOS Search assigned `undefined` to two
labels on every start. W6.3 (`a0dd4b33`) is **What's new** — after an update MoOS says once
what it brought, with "Try it" routes (P2.11). **Not proven anywhere yet:** tool choice by
a real free model (P3.3).

## ISO proof (P0.8) — closed

The image's CI proof-channel helper read the IPv4 default route ONCE while MoOS disables
NetworkManager-wait-online, so it died before adding its SSH rule; with a retry the ISO
proofs of cycles C, D and E were three consecutive green install-and-reboot runs.

## Proven source/image behavior

- Cycles B and C: the signed builds passed every image gate for all three x86 editions;
  every disk booted twice under QEMU/KVM; each final ISO installed offline, logged in,
  opened every first-party app twice, rebooted and powered off. `pr-image-gates.yml`
  builds the generic image on a pull request in 16 minutes and pushes nothing.
- Horizon motion gates cover finite settling, reversal, hidden state, reduced motion and
  pointer/key paths; MoOS motion roles follow the owner's animation speed on a real Qt
  runtime. Free cloud AI returned English and Arabic replies through the live gateway
  with an explicitly free provider: chat, not system control.

## Development environment

- On the station: VS Code is a Flatpak; host work uses `flatpak-spawn --host`.
  `just workstation-check` is a read-only inventory; .NET SDK `10.0.401` and Flutter
  3.47.4 (the image-builder pin) are installed. Pointer-driven review goes through
  `scripts/station/pointer.py` — KWin confirms every position before a click.
- Off the station: Windows 11 + WSL2 `FedoraLinux-44`. `scripts/review/` holds the
  toolchain installer, the gate mirror and the from-source renderers (render at the size
  the window really opens at); `scripts/release-candidate.sh` needs `TMPDIR` under Git
  Bash. `.kilo/` is local untracked agent state, not product source.

## Open evidence gaps

- The W2–W6 station review is closed (above). Still owed on a desk: an Island **Store**
  job in the foreground (the Remote chip outranks it while Mo PC Remote runs), and Mo AI's
  tool loop, cards and identity answers once a provider key exists (P0.5). The **A1 review
  is untouched**.
- M1 visual/accessibility matrix: English/German sessions, light/dark, reduced motion,
  1080p–4K, 100–250%, island Remote/Media switching (Arabic reviewed only).
- Hardware: two suspend/resume cycles, multi-monitor, audio/network recovery, deliberate
  rollback/roll-forward and photographed boot/login; broader Wi-Fi/Bluetooth/camera,
  laptop and touch hardware, ARM provider behaviour, cloud multi-account operation.
- Versioned, failure-tested Mo AI/Store/core contracts and a single application
  transaction authority.
- Owner decision P3.9: whether Mo AI ever gets a tool that runs a command the model
  wrote. Until it is taken, no such tool exists.

## A wallpaper cannot be clicked (2026-09-18)

MoOS Hub lives in the WALLPAPER, which is why it can never cover an icon or a window.
The same property means no pointer event reaches it: measured on the station, neither a
click nor a wheel over a card arrived — the desktop containment takes both. The clock
card's second face is therefore turned from the desktop's own menu, beside the card
toggles, and remembered in `HubClockPage`. Anything else the Hub ever gains follows the
same rule.

## The free brain is measured on the machine that uses it (2026-09-18)

The shipped preference list was measured on one day against a catalogue that turns
over every few weeks: on 2026-09-18 the free catalogue carried **21 tool-capable
zero-price models**, several newer than that snapshot (a 1M-context DeepSeek flash,
a 550B Nemotron, two Inkling sizes, Laguna, Qwen 3.8, Gemma 4). `moai-measure-free`
asks each candidate two fixed questions through the real gateway — an Arabic
sentence and one tool call — and writes the order that answered into
`~/.local/state/moai/free-ranking.json`; `moai_cloud_policy` prefers that for 30
days and can never let it introduce a model, change a price or reach a billed
route. Unmeasured candidates are now ranked by **context first**: a system agent
carries tool schemas, results and confirmations in one transcript, and parameter
count is only guessable from the model id.

It cannot run here yet: no provider key is configured (P0.5, an owner action).

**MoOS found a second desktop server on its own machine.** `moos-health scan` reported
one warning on 2026-09-18: KDE's `krdpserver` listening on `tcp *:3389` for the whole
network with `SystemUserEnabled=true`, beside Mo PC Remote (private tailnet, PIN,
on-screen indicator). The finding used to open Mo PC Remote, which does not close the
port; it now carries `moos://privacy/stop-sharing`, and `moos-remote-guard off` stops and
un-autostarts the two named KDE sharing services with no administrator rights and nothing
removed. **Still open on the station itself:** the port is still listening — stopping a
running service needed a permission this session did not have, so the owner runs
`moos-remote-guard off` (or presses the finding) once the update lands.

## Next execution

1. Owner: configure a free Mo AI provider key (P0.5) — the only thing blocking the four
   Mo AI rows of the station checklist.
2. **W8 is merged and reviewed live** (Aurora Glass, the Island capsule, the Search button,
   the status cluster, Search's now-playing row, MoPlayer's two MPRIS defects). It reaches
   the desk with the next release cycle; until then the station shows the pre-W8 bar.
3. Open in W8: one clarity control (needs a config bridge a QML singleton can read), the
   MoOS mark at exactly three sizes, and the specular sweeping once as a surface arrives.
4. Open in W7: touchpad and gesture defaults (P5.2 — this station has no touchpad) and a
   live preview in the Arrange surface. P0.7 (`plymouthd` SEGV) stays open on ARM and x86.
5. Pointer-driven review works: `scripts/station/pointer.py click <x> <y>` in LOGICAL
   pixels, verified against KWin before every click. Absolute `ydotool` moves are useless
   on this screen. Who holds which files is in `docs/AGENT_COORDINATION.md`.
