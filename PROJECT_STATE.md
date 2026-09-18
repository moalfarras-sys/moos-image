# MoOS current state

Current measured facts only; Git owns history. Last measured 2026-09-18 17:5x UTC.

**This block is the only place in the repository that states a version number.** The plan,
the README and every wave row point here instead of repeating it. Four parallel copies of
"production is X" is how three of them came to be a release behind at once.

## Source and release truth

- **x86 and ARM are NOT on one revision.** Read back from the registry 2026-09-18 18:2x:
  `moos`, `moos-nvidia`, `moos-cloud` `:latest` = **`44.20260918.887`**, revision
  **`af779abb`** (cycle G, promotion `35372398530`), digests `326bc5a7053f…`,
  `07f843515b63…`, `23141f74093b…` — the three the candidate build signed, and the first
  image carrying W8.4, W8.5, #132, #133 and #135. `moos-arm:latest` = **`44.20260918.484`**,
  revision **`447248ac`**. They differ because x86 `:latest` moves only through
  `promote-x86.yml` after exact-revision proofs, while `build-arm.yml` promoted only on a
  push — and a cycle dispatches it, so that job was skipped every time and **no cycle had
  ever promoted ARM**. It now accepts a dispatch on main, so the next cycle moves both.
- **Cycle G's lesson.** Its four x86 proofs passed while the ARM build ran for over 90
  minutes, and the script waited on an ARM result it had already excluded from the x86
  decision. The promotion was dispatched by hand with the same six inputs;
  `release-candidate.sh` no longer blocks on it.
- **Release cycles, newest first.** G (`af779abb`, x86 `44.20260918.887`): build
  `35362187941`, QCOW2 `35364822749`/`35364828069`/`35364832784`, ISO `35364837291`,
  promotion `35372398530`. F (`6996afaf`, x86 `44.20260918.881`): promotion
  `35351916872`. E (`6c4f73c0`, x86 `.868` / ARM `.458`): promotion `35303529066` — the
  last cycle whose ARM number is still the live one. Earlier promotions are in Git.
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

Last measured ON the station, 2026-09-18 17:5x local: the station is running
**`44.20260918.881`**, `ostree-image-signed`
`moos-nvidia@sha256:793dc956379e549306b1bd7b3a0a31a9b8265a8d0813704cce25ee496d02dc70` —
the digest cycle F signed and promoted — with `44.20260918.868` retained for
rollback. `THEME_REV` 68 is applied (`~/.local/state/moos-ui2-theme-applied.v68`),
zero failed system units and zero failed user units, KWin/Plasma 6.7.5 on Wayland,
3840×2160 at 265% (1450×816 logical), Arabic session, scheme `MoOSUI2AuroraLight`,
visual tier `flagship` (`AnimationDurationFactor=1`, blur on).

**What the station does NOT have yet.** It boots `881`/`6996afaf`; `887`/`af779abb` is
promoted and waiting. That image carries #134 (the hub cards' second faces), #135, #132,
#133 and #136 (W8.5's measured free-brain picker), and `THEME_REV` 69 against the
station's 68. One update and a restart closes the gap.

**Updating it:** MoOS origins are digest-pinned, so `bootc upgrade` reports "no
changes" forever. Use the MoOS Updater (Settings → Update MoOS, or Mo AI's "Update
my system"), or wait for the nightly train; then restart.

## W8 on the running station (2026-09-18) — closed

Reviewed with review shadows and `scripts/station/pointer.py`; frames in
`~/.cache/moos-w8/`. Seen on the desk, not rendered: the Island capsule's caption moved
inside the pill (its two pinned lines assumed `panelHeight` 54 while the bar gives 40)
and now names the app that is playing; MoOS Search became an icon-sized button (the old
pill was as wide as four app icons and its field could never take focus); the status
cluster went from nine glyphs to four and an arrow; Aurora Glass gave every MoOS surface
a palette-derived rim and one specular hairline per depth.

**MoPlayer, measured on the bus.** `dbus-monitor` caught the desktop asking the new MPRIS
name for its properties 2 ms after it appeared and MoPlayer answering
`org.freedesktop.DBus.Error.UnknownObject` — the object was one `await` behind the name,
and Plasma drops such a player for the life of that shell. Its metadata also went out as
`variant variant string`, so every reader saw an empty title. Both fixed and gated.

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
  #131) and eight free models were ranked on this machine (W8.5). **Still not proven:**
  the ≥95% action-selection rate over a fixed Arabic/English case set — no case set and
  no runner exist (P3.3).
- **ISO proof (P0.8) closed:** the CI proof-channel helper read the IPv4 default route
  once while MoOS disables NetworkManager-wait-online, so it died before adding its SSH
  rule. With a retry, cycles C, D and E were three consecutive green install-and-reboot
  runs.

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

1. `887` is promoted. Owner updates the station and reboots → record the booted version
   here. That is the only way W8.4 and W8.5 reach a desk.
2. **P3.3** is the largest open Mo AI gap: no case set and no runner exist for the ≥95%
   action-selection measurement. `moai-measure-free` is not it — it asks one tool
   question to rank models.
3. **P5.4**: not one performance budget exists in the tree. Boot, login, app launch and
   idle, per hardware tier, measured and stored in Git.
4. Open in W8: one clarity control (needs a config bridge a QML singleton can read), the
   MoOS mark at exactly three sizes, and the specular sweeping once as a surface arrives.
5. Open in W7: touchpad and gesture defaults (P5.2 — this station has no touchpad) and a
   live preview in Arrange. P0.7 (`plymouthd` SEGV) stays open on ARM and x86.
6. Pointer-driven review works: `scripts/station/pointer.py click <x> <y>` in LOGICAL
   pixels, verified against KWin before every click. Absolute `ydotool` moves are useless
   on this screen. Who holds which files is in `docs/AGENT_COORDINATION.md`.
