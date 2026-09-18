# MoOS current state

Current measured facts only; Git owns history. Last measured 2026-09-17.

## Source and release truth

- **All four editions are one tree, W6.3** (`96e34695` = W7 + W6.2 + What's new), read back from
  the registry after promotion run `35294288086`: `moos`, `moos-nvidia` and `moos-cloud`
  `:latest` = `44.20260917.865` (digests `70da603d186d…`, `a4ac408722b3…`, `003908745c12…`, the ones
  the candidate build signed); `moos-arm:latest` = `44.20260917.450` at `a0dd4b33` (the merge of
  the same tree; `build-arm.yml` promotes every green push). Read the registry, not this line.
- **Cycle D**, candidate `96e34695` proven on its branch and merged as `a0dd4b33`: build
  `35287475147`, QCOW2 `35292262511`/`35289170881`/`35289173878`, ISO `35289177072`, ARM `35289180443`, promotion
  `35294288086`. Its first generic QCOW2 run (`35289168012`) was lost to P0.7 — `plymouthd`
  core-dumped on the FIRST boot, the first time on x86 — and that ONE proof was dispatched
  again on the same image reference. Between cycles C and D, ARM had taken W7 alone at
  `THEME_REV` 63 (`44.20260917.445`): the case a shared 63 would have stranded (W6.2 is 64).
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

## Station review of W2–W6 on the running desktop (2026-09-17)

Walked on `44.20260917.858`; each row says what was actually seen. Frames are in
`~/.cache/moos-station-review/`.

| # | Item | Result |
| --- | --- | --- |
| 1 | Booted version | **PASS.** `44.20260917.858`, digest `c8f94adde60d…`, previous deployment retained. "About this device" is W6.1 and is **not in this image**, so its half of the row is untested |
| 2 | Review shadows swept | **PASS.** Both shadow directories empty at the first login after the update; `THEME_REV` 62 applied |
| 5 | MoOS Search inline answers | **PASS.** `12*7` returns one `آلة حاسبة` row reading **84**, above the file-result group, with a copy action. The unit-conversion half is **untested**: the session's keyboard layout is Arabic, so synthetic Latin typing produces Arabic letters — the calculator was driven with layout-independent key codes. Typing an unparseable query did produce the `اسأل Mo AI` hand-off row |
| 6 | Island privacy chips | **PASS for detection and naming.** `moos-privacy-monitor` wrote `active-mic-98-pw%2Drecord` within 3 s of a real PipeWire capture starting and held it for the capture's life, and it wrote `active-screen-98-Mo%20PC%20Remote` while Mo PC Remote was genuinely capturing (`MoRemotePersonal` and its portal were running). The Island rendered its Remote chip with the live green dot, which is the documented priority (Remote outranks a privacy chip), so the camera/mic chip's own foreground appearance is still **unseen**. The Store-job half is **untested** |
| 12 | Secondary text on a light scheme | **PASS.** Mo Store's hero sentence and every publisher line are clearly readable on `MoOSUI2AuroraLight` — this is the text that measured 1.6:1 before W6 |
| 3, 4, 10, 11 | Hub controls, widget removal, App Drop, dismissed auth | **Untested.** All need pointer input, and `ydotool`'s absolute pointer mapping does not match this screen (two calibration attempts landed the click elsewhere). Keyboard- and CLI-driven items were done instead; these need either a calibrated pointer or the owner |
| 7, 8, 9, 13 | Mo AI rail, tool loop, cards, identity answers | **Blocked.** Row 7 is W6.1 and not in this image. 8, 9 and 13 need a cloud brain: `moai-brain-mode` reports "free cloud only … configure with moai-config" and no provider key is configured, which is plan row P0.5 and an owner action |

The W7 facts measured on the same session are in `docs/DEVELOPMENT_PLAN.md`.

## W6.1 — production, and now booted on the station

Released with cycle C and **installed here on 2026-09-18** (`44.20260917.862`):
Settings' own "About this device" page (P2.9); Mo AI skills — twelve read-only repair
playbooks found with `list_skills` and read with `read_skill` (43 tools: 30 run at
once, 13 ask first), with eight one-tap chips (P3.10); Mo AI's rail corrected at the
default 940 px window; the Device panel no longer printing the raw kernel release.

## Released with cycle D, never seen on a MoOS desktop: W7, W6.2, W6.3

W6.2 (merged `012eac13`, PR #119), found the first time the desktop ITSELF could be looked at off the station
(`scripts/review/render-desktop.sh` runs the real `plasmashell` with MoOS's layout,
scene, Hub, bar and plasmoids under Xvfb; `render-lockscreen.sh` the lock screen):

- In Arabic the Hub's English date line hung on the LEFT of a right-aligned clock column;
  the Island's privacy chip read "الميكروفون قيد الاستخ…" (sized by counting characters,
  forgetting its Stop button); MoOS Search assigned `undefined` to two labels on every
  start. The same renders first SAW W6's Island repair working in a real shell.

W7 (`411a470c`, PR #118): MoOS Switcher, `Tokens.scaled()`, MoOS Arrange — reviewed live.

**W6.3 (merged `a0dd4b33`, PR #120): What's new** — the answer to "I felt no change".
Settings → System → What's new lists what each update brought with "Try it" routes and marks
what this machine lacked before its last update; `moos-whats-new-notify` says it once at the
first login on a new version (P2.11). Rendered from source (Arabic, English, the notice in
Plasma's popup); notifier proven end to end under bubblewrap; **not seen on a MoOS desktop**.

**Not proven anywhere yet:** tool choice by a real free model (P3.3); a real AppImage,
its dialog, the file-manager action and the `~/Applications` watch on a desktop (P4.6).

## ISO proof (P0.8) — cause measured

The image's CI proof-channel helper read the IPv4 default route ONCE, and MoOS disables
NetworkManager-wait-online, so nothing ordered that read after DHCP; the helper died on it
and never added its SSH rule. Run `35265328509` shows the repair on the console: the route
arrived 16 ms after the daemons on the first boot and 1.02 s on the second, where one retry
found it. The rival theory (a fresh slirp forward per boot) was measured irrelevant by the
same run (`first-boot-forward=alive`). Cycle C's ISO proof (`35276847573`) was the second
consecutive green install-and-reboot and cycle D's (`35289177072`) the third: **P0.8 is closed**.

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

- Station review of W4–W6: Search answers, privacy-chip detection, the shadow sweep and
  light-scheme text are now measured (see the review section above). Still owed there:
  Hub controls, widget removal, App Drop with a real AppImage and the dismissed-auth
  result — all pointer-driven — plus Island Store jobs, and Mo AI's tool loop and cards
  with a real free model once a provider key exists (P0.5). The **A1 review is untouched**.
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

1. Owner: update the station and the **A1** to `44.20260917.865` (MoOS Updater), walk the
   checklist, and
   configure a free Mo AI provider key (P0.5) — the only thing blocking the four Mo AI
   rows of the station checklist.
2. Cycle D is production. Cycle E (PR #121: Updater and Recovery open tall enough to show
   their buttons; the update notice names features; coredump stacks in the boot proof) is
   `scripts/release-candidate.sh --promote` on `main` after the merge; a lone external
   failure is handled as `RELEASE.md` says.
3. P0.8 is closed (three consecutive green install proofs); P0.7 stays open.
4. Still open in W7: a live preview in the Arrange surface, touchpad and gesture
   defaults (P5.2), and carrying `Tokens.scaled()` to the per-surface motion aliases.
   The visible programme (W8, W9) now has an off-station render loop; compositor work
   (blur, window animation, Overview) still needs the station.
5. A pointer-driven review needs `ydotool`'s absolute axis calibrated against this 4K
   screen first, or it silently clicks somewhere else. Who holds which files is in
   `docs/AGENT_COORDINATION.md`.
