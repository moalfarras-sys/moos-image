# MoOS current state

Current measured facts only; Git owns history. Last measured 2026-09-17.

## Source and release truth

- **All four editions are one revision, `6c4f73c0`** (cycle E: W6.3 + PR #121), read back from
  the registry 2026-09-18 03:32 UTC after promotion run `35303529066`: `moos`, `moos-nvidia`
  and `moos-cloud` `:latest` = `44.20260918.868` (digests `33fef3f39cd5…`, `68c27fffc3cd…`,
  `43791828c947…`, the ones the candidate build signed); `moos-arm:latest` = `44.20260918.458`
  (`build-arm.yml` promotes every green push). Read the registry, not this line.
- **Cycle E** (`6c4f73c0`): build `35295680548`, QCOW2 `35297281876`/`35297284491`/`35297287185`,
  ISO `35297289852`, ARM `35297292391`, promotion `35303529066` — one command. **Cycle D** (`96e34695` = W7 + W6.2 + What's new, proven on its branch, merged as `a0dd4b33`
  → x86 `44.20260917.865`, ARM `.450`): build `35287475147`, QCOW2 `35292262511`/`35289170881`/
  `35289173878`, ISO `35289177072`, ARM `35289180443`, promotion `35294288086`. Its first generic
  QCOW2 run (`35289168012`) was lost to P0.7 (`plymouthd` core-dump on the first boot, the first
  on x86); that ONE proof was dispatched again. Between C and D, ARM took W7 alone at `THEME_REV`
  63 (`44.20260917.445`): the case a shared 63 would have stranded (W6.2 is 64).
- **Cycle C** (`291361ad`, W6.1 → x86 `44.20260917.862`, ARM `.441`): build `35272501490`,
  QCOW2 `35275702835`/`35275707229`/`35275711589`, ISO `35276847573` (its first ISO run
  `35275716160` lost the distribution's mirrors: dispatched again, promotion by hand,
  `RELEASE.md`), promotion `35280675992`. **Cycle B** (`a8622f95`, W6 → `44.20260917.858`):
  build `35261411076`, QCOW2 `35265314956`/`35265319663`/`35265323922`, ISO `35265328509`,
  promotion `35269505270`. Before that x86 was W1 (`92248b5d`); cycle A lost its ISO to P0.8.
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

## Station review of W2–W6 on the running desktop (2026-09-17 and 2026-09-18)

Keyboard- and CLI-driven rows walked on `44.20260917.858`; the four pointer-driven rows on
`44.20260917.862` the next morning, once `scripts/station/pointer.py` made a click land where
it is aimed (KWin reports `workspace.cursorPos`, the pointer is walked there with relative
moves; absolute `ydotool` moves were measured again and stay in the corner). Frames are in
`~/.cache/moos-station-review/` and `~/.cache/moos-station-review2/`.

| # | Item | Result |
| --- | --- | --- |
| 1, 2 | Booted version, shadows swept | **PASS.** `44.20260917.858` with the previous deployment retained; both shadow directories empty at the first login, `THEME_REV` 62 applied |
| 3 | Hub controls from the desktop | **PASS.** The desktop's own menu lists the four Hub actions; unchecking «لوحة MoOS: الطقس» removed the weather card and wrote `HubWeather=false`, the Hub reflowed to two cards, and checking it restored the card |
| 4 | A widget can be removed | **PASS.** A widget added for the review reported `locked=false`, its menu offered «أزل ساعة تناظرية», the click removed it, a notification offered an undo, and the appletsrc has zero `immutability=0` entries |
| 5 | MoOS Search inline answers | **PASS.** `12*7` returns one `آلة حاسبة` row reading **84** above the file results, with a copy action; an unparseable query offers the `اسأل Mo AI` hand-off. Unit conversion is still untested (Arabic layout) |
| 6 | Island privacy chips | **PASS.** Detection and naming were measured in the first review; on 2026-09-18 the chip itself appeared in the Island — «مشاركة الشاشة نشطة», naming the capturing app, with a one-tap stop |
| 10 | App Drop with a real AppImage | **PASS.** A real 8.4 MB AppImage dropped into `~/Applications` raised the MoOS question (name, size, kind, destination, unverified-publisher sentence, default No); «تثبيت» installed it as a desktop entry and `--remove` took it away |
| 11 | A dismissed authentication | **PASS on the result, two defects on the words.** Nothing was staged and MoOS printed «لم تُجهَّز الحزمة…», but the prompt itself read "Authentication is needed to run `/usr/libexec/moos-install-local-rpm …'" in English and pkexec's "This incident has been reported." came first. **Both fixed in source** (`org.moos.install-local-rpm.policy`, `run_priv`), not yet on a desktop |
| 12 | Secondary text on a light scheme | **PASS.** Mo Store's hero sentence and publisher lines are clearly readable on `MoOSUI2AuroraLight` |
| 7, 8, 9, 13 | Mo AI rail, tool loop, cards, identity answers | **Blocked.** They need a cloud brain: no provider key is configured (plan row P0.5, an owner action) |

The W7 facts measured on the same session are in `docs/DEVELOPMENT_PLAN.md`.

## W6.1 — production, and now booted on the station

Released with cycle C and **installed here on 2026-09-18** (`44.20260917.862`):
Settings' own "About this device" page (P2.9); Mo AI skills — twelve read-only repair
playbooks found with `list_skills` and read with `read_skill` (43 tools: 30 run at
once, 13 ask first), with eight one-tap chips (P3.10); Mo AI's rail corrected at the
default 940 px window; the Device panel no longer printing the raw kernel release.

## Released with cycle D, still unseen on a MoOS desktop: W6.2 and W6.3

W6.2 (`012eac13`, PR #119) came from the first renders of the desktop itself off the station
(`scripts/review/render-desktop.sh` runs the real `plasmashell` with MoOS's layout, scene,
Hub, bar and plasmoids under Xvfb): in Arabic the Hub's English date line hung on the LEFT of
a right-aligned clock column, the Island's privacy chip read "الميكروفون قيد الاستخ…" (sized
by counting characters), and MoOS Search assigned `undefined` to two labels on every start.

W6.3 (`a0dd4b33`, PR #120) is **What's new** — the answer to "I felt no change": Settings →
System → What's new lists what each update brought with "Try it" routes, and
`moos-whats-new-notify` says it once at the first login on a new version (P2.11). Rendered
from source and proven under bubblewrap; **not seen on a MoOS desktop**. W7 (`411a470c`,
PR #118) shipped in the same cycle and was reviewed live before it merged.

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
- `pr-image-gates.yml` built the generic image on a pull request and ran its in-image
  gates in 16 minutes, pushing nothing (run `35266474587`).
- Horizon motion gates cover finite settling, reversal, hidden state, reduced motion
  and pointer/key paths. Native sounds decode and map to KDE event IDs; installed
  playback/mute acceptance remains open.
- Free cloud AI returned English and Arabic replies through the live gateway with an
  explicitly free provider: chat, not system control. `moos-privacy-monitor`'s polling
  costs 0.66% of one core off the station (P5.4).

## Development environment

- On the station: VS Code is a Flatpak; host work uses `flatpak-spawn --host`.
  `just workstation-check` is a read-only inventory. .NET SDK `10.0.401` and Flutter
  3.47.4 (the image-builder pin) are installed.
- Off the station: Windows 11 + WSL2 `FedoraLinux-44`.
  `scripts/review/setup-review-distro.sh` installs the toolchain,
  `scripts/review/mirror-gates.sh` runs gates on a mirror with git's file modes, and
  `scripts/review/render-app.sh` renders a first-party app from source with a real
  MoOS colour scheme and prints QML binding errors. Render at the size the window
  really opens at. `scripts/release-candidate.sh` needs `TMPDIR` set under Git Bash.
- `.kilo/` is local untracked agent state and is not product source.

## Open evidence gaps

- Station review of W4–W6: Search answers, privacy-chip detection and naming, the shadow
  sweep, light-scheme text, Hub controls, widget removal, App Drop with a real AppImage and
  the dismissed-authentication result are all measured now (see the review section above).
  Still owed there: an Island **Store** job in the foreground (the Remote chip outranks it
  while Mo PC Remote runs), and Mo AI's tool loop and cards with a real free model once a
  provider key exists (P0.5). The **A1 review is untouched**.
- M1 visual/accessibility matrix: English/German sessions, light/dark, reduced motion,
  1080p–4K, 100–250%, island Remote/Media switching (Arabic reviewed only).
- Two suspend/resume cycles, multi-monitor, audio/network recovery, deliberate
  rollback/roll-forward and photographed boot/login on hardware.
- Broader Wi-Fi/Bluetooth/audio/camera, laptop/touch hardware, ARM provider behavior
  and cloud multi-account operation.
- Versioned, failure-tested Mo AI/Store/core contracts and a single application
  transaction authority.
- Owner decision P3.9: whether Mo AI ever gets a tool that runs a command the model
  wrote. Until it is taken, no such tool exists.

## Next execution

1. Owner: update the station and the **A1** to `44.20260918.868` / `.458` (MoOS Updater), walk the
   checklist, and
   configure a free Mo AI provider key (P0.5) — the only thing blocking the four Mo AI
   rows of the station checklist.
2. Cycle E is production on all four editions (`44.20260918.868` / `.458`): Updater and
   Recovery windows show their buttons, the update notice names features, a failed boot
   proof prints the crashed process's stack. Next cycle: `--promote` when `main` has news.
3. P0.8 is closed (three consecutive green install proofs); P0.7 stays open.
4. Still open in W7: a live preview in the Arrange surface, touchpad and gesture
   defaults (P5.2), and carrying `Tokens.scaled()` to the per-surface motion aliases.
   The visible programme (W8, W9) now has an off-station render loop; compositor work
   (blur, window animation, Overview) still needs the station.
5. Pointer-driven review works now: `scripts/station/pointer.py click <x> <y>` in LOGICAL
   pixels, verified against KWin before every click. Absolute `ydotool` moves are still
   useless on this screen; never go back to them. Who holds which files is in
   `docs/AGENT_COORDINATION.md`.
