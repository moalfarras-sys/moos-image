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

A root-owned local override `/etc/plasmalogin.conf.d/90-moos-development-autologin.conf`
enables one-session automatic login for `moos` during this development cycle. It is
not in the image and sets `Relogin=false`; remove it with `pkexec rm` on that path.

Review shadows: the four W2 ones are **gone** — `THEME_REV` 62 swept them at the
first login after the update, which is checklist item 2 and it passed
(`~/.local/share/plasma/{plasmoids,wallpapers}/` are both empty).

One new shadow is left on purpose, from the W7 review:
`~/.local/share/kwin/tabbox/org.moos.ui2.switcher`, with
`~/.config/kwinrc [TabBox] LayoutName` and `[TabBoxAlternative] LayoutName`
pointing at it, so the owner has the new Alt+Tab before the next release carries
it. `THEME_REV` does not sweep `kwin/tabbox`. Remove both by hand when the update
that ships the package is installed:
`rm -rf ~/.local/share/kwin/tabbox/org.moos.ui2.switcher` and
`kwriteconfig6 --file kwinrc --group TabBox --key LayoutName --delete` (same for
`TabBoxAlternative`).

The station moved W1 → W6 in one update, carrying W2 (Hub controls), W3 (removable
widgets, a wallpaper that stays), W4 (Mo AI's tool harness), W5 (Island jobs and
privacy chips, inline Search answers), the #114 integration and W6, and landing on
`THEME_REV` 62. W2 and W3 had been reviewed live before the update; W4, W5 and W6 were
first seen on a MoOS desktop on 2026-09-17, below.

## W8 on the running station (2026-09-18, `44.20260918.868`)

Reviewed with review shadows and `scripts/station/pointer.py`, frames in
`~/.cache/moos-w8/`. Every row below was seen on the desk, not rendered from source.

| What | Before | After |
| --- | --- | --- |
| Island capsule | the source line was drawn through the pill's bottom curve and sat outside it | one line inside the capsule at the bar's real 40 px |
| Island icon | the theme's "unknown file" sheet beside a working player | MoPlayer's own icon |
| MoOS Search | a 140–196 px pill of empty glass carrying words | one icon-sized button; the bar is shorter |
| Status cluster | nine glyphs in a row | four and an arrow |
| Aurora Glass | alpha only | a palette-derived rim and one specular hairline, per depth |
| Search while playing | the popup hid what was playing | the player is the first row, with its control |

**MoPlayer, measured on the bus, not guessed.** `dbus-monitor` caught the desktop asking
the new MPRIS name for its properties 2 ms after it appeared and MoPlayer answering
`org.freedesktop.DBus.Error.UnknownObject` — the object was one `await` behind the name,
and Plasma drops such a player for the life of that shell (a shell that STARTS with the
player already there enumerates it, which is why this looked intermittent). Its metadata
also arrived as `variant variant string`, so every reader saw an empty title. Both are
fixed in `moplayer/lib/services/system/mpris.dart` and gated; they reach the desk with
the next image, so the capsule still showed "وسائط قيد التشغيل" during this review.

## Station review of W2–W6 (2026-09-17 and 2026-09-18) — closed

Walked on `44.20260917.858` and `.862`; frames in `~/.cache/moos-station-review/` and
`~/.cache/moos-station-review2/`. **Every row passed**: the booted version and retained
deployment, the shadow sweep at first login (`THEME_REV` 62), Hub controls from the
desktop's own menu (a card off and on, `HubWeather=false` written), a widget removed
through its own menu with an undo notification (zero `immutability=0` left), MoOS Search's
inline answer (`12*7` → **84** with a copy action; unit conversion still untested because
the session's layout is Arabic), the Island's privacy chip naming the capturing app with a
one-tap stop, App Drop installing and removing a real 8.4 MB AppImage, a dismissed
administrator prompt staging nothing and saying so, and secondary text readable on
`MoOSUI2AuroraLight`.

Two findings came out of the last row and are fixed in source (`org.moos.install-local-rpm`
policy and `run_priv`): the administrator prompt read an English sentence naming a helper
path, and pkexec's "This incident has been reported." came before MoOS's own line.

**Still owed:** an Island **Store** job in the foreground (the Remote chip outranks it while
Mo PC Remote runs), and Mo AI's tool loop, cards and identity answers — all four need a
cloud brain, which is plan row P0.5 and an owner action.

The W7 facts measured on the same session are in `docs/DEVELOPMENT_PLAN.md`.

## W6.1 — production, and booted on the station (`44.20260917.862`)

Settings' own "About this device" page (P2.9); Mo AI skills — twelve read-only repair
playbooks (`list_skills`/`read_skill`, 43 tools: 30 run at once, 13 ask first) with eight
one-tap chips (P3.10); Mo AI's rail corrected at the default 940 px window.

## Released with cycle D, still unseen on a MoOS desktop: W6.2 and W6.3

W6.2 (`012eac13`) came from the first renders of the desktop itself off the station
(`scripts/review/render-desktop.sh` runs the real `plasmashell` under Xvfb): in Arabic the
Hub's English date line hung on the far side of a right-aligned column, the Island's
privacy chip was sized by counting characters, and MoOS Search assigned `undefined` to two
labels on every start. W6.3 (`a0dd4b33`) is **What's new** — after an update MoOS says once
what it brought, with "Try it" routes (P2.11). Both are rendered from source only.

**Not proven anywhere yet:** tool choice by a real free model (P3.3).

## ISO proof (P0.8) — closed

The image's CI proof-channel helper read the IPv4 default route ONCE, and MoOS disables
NetworkManager-wait-online, so nothing ordered that read after DHCP; the helper died on it
and never added its SSH rule. Run `35265328509` shows the retry working (the route arrived
16 ms after the daemons on the first boot, 1.02 s on the second), and the ISO proofs of
cycles C and D were the second and third consecutive green install-and-reboot.

## Proven source/image behavior

- Cycles B and C: the signed builds passed every image gate for all three x86 editions;
  every disk booted twice under QEMU/KVM; each final ISO installed offline, logged in,
  opened every first-party app twice, rebooted and powered off.
- `pr-image-gates.yml` builds the generic image on a pull request and runs its in-image
  gates in 16 minutes, pushing nothing.
- Horizon motion gates cover finite settling, reversal, hidden state, reduced motion and
  pointer/key paths; MoOS motion roles follow the owner's animation speed on a real Qt
  runtime (`THEME_REV` 65). Free cloud AI returned English and Arabic replies through the
  live gateway with an explicitly free provider: chat, not system control.

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
