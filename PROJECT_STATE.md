# MoOS current state

Current measured facts only; Git owns history. Last measured 2026-09-17.

## Source and release truth

- **All four editions are one revision, `291361ad` (W6.1)**, read back from the registry on
  2026-09-17 after promotion run `35280675992`: `moos`, `moos-nvidia` and `moos-cloud`
  `:latest` = `44.20260917.862` (digests `63d72fde231a…`, `44d8c317df0c…`, `0b57dbdda41f…` —
  the digests the candidate build signed), and `moos-arm:latest` = `44.20260917.441`. x86 and
  ARM had been a release apart since W1.
- Two x86 promotions that day. **Cycle B**, candidate `a8622f95` (W6): build `35261411076`,
  QCOW2 generic/NVIDIA/cloud `35265314956`/`35265319663`/`35265323922`, ISO `35265328509`,
  promotion `35269505270` → `44.20260917.858`. **Cycle C**, candidate `291361ad` (W6.1): build
  `35272501490`, QCOW2 `35275702835`/`35275707229`/`35275711589`, ISO `35276847573`, promotion
  `35280675992`. Cycle C's first ISO run (`35275716160`) died building the ISO when the runner
  could not reach the distribution's mirrors; a fresh dispatch of that one workflow with the
  same image reference passed, and promotion was dispatched by hand with its id
  (`release-candidate.sh --promote` rightly refuses once one of ITS proofs has failed).
  Before that day x86 production was W1 (`92248b5d`, `44.20260916.848`).
- Release cycle A (candidate `51cc2ac3`) passed the signed build and all three QCOW2 boots and
  lost its ISO proof to plan row P0.8; nothing was promoted from it.
- `main` is the only long-lived branch; 22 merged topic branches were deleted (each an ancestor).
- The intermittent ARM second-boot `plymouthd` SEGV is still open (P0.7); green ARM runs since
  then had no fix applied.
- A merged commit or locally built image is not an installed or released state. Production
  moves only after the exact candidate passes 3×QCOW2 + ISO; ARM is separately required
  evidence.

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

## In review (`fix/hub-polish-20260917`, W6.2) and on `main` (W7) — both need cycle D

W6.2, found the first time the desktop ITSELF could be looked at off the station
(`scripts/review/render-desktop.sh` runs the real `plasmashell` with MoOS's layout,
scene, Hub, bar and plasmoids under Xvfb; `render-lockscreen.sh` the lock screen):

- In an Arabic session the Hub's English date line hung on the LEFT edge of a
  right-aligned clock column (each line aligned by its own script).
- The Island's privacy chip read "الميكروفون قيد الاستخ…": the capsule was sized by
  counting characters and ignored its always-shown Stop button.
- MoOS Search assigned `undefined` to two labels on every desktop start.
- The same renders are the first time W6's Island repair was SEEN working in a real
  shell. Source-harness evidence: no compositor effects, X11 not Wayland, icons blank.

W7 (merged into `main` as `411a470c`): the MoOS Switcher, `Tokens.scaled()` and MoOS
Arrange, all reviewed on the live session.

**W7 is `THEME_REV` 63 and W6.2 is 64.** ARM promotes every green push to `main`, so W7
can reach an ARM machine at 63 before W6.2 does; a shared 63 would strand its caches.

**Not proven anywhere yet:** tool choice by a real free model (P3.3); a real AppImage,
its dialog, the file-manager action and the `~/Applications` watch on a desktop (P4.6).

## ISO proof (P0.8) — cause measured

The image's CI proof-channel helper read the IPv4 default route ONCE, and MoOS disables
NetworkManager-wait-online, so nothing ordered that read after DHCP; the helper died on it
and never added its SSH rule. Run `35265328509` shows the repair on the console: the route
arrived 16 ms after the daemons on the first boot and 1.02 s on the second, where one retry
found it. The rival theory (a fresh slirp forward per boot) was measured irrelevant by the
same run (`first-boot-forward=alive`). Cycle C's ISO proof (`35276847573`) was the second
consecutive green install-and-reboot; the row closes after one more.

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

1. The station is updated to `44.20260917.862` and reviewed. Owner: update the **A1**,
   and configure a free Mo AI provider key (P0.5) — the only thing blocking the four
   Mo AI rows of the station checklist.
2. Merge W6.2 (#119) once its checks are green, then release cycle D:
   `TMPDIR=<dir> scripts/release-candidate.sh --promote` on `main`. Cycle D carries W6.2
   AND W7. If ONE proof fails for an external reason, dispatch that workflow alone again
   with the same image reference and promote by hand with the new run id (`RELEASE.md`).
3. P0.8 closes after one more green ISO proof; P0.7 stays open.
4. Still open in W7: a live preview in the Arrange surface, touchpad and gesture
   defaults (P5.2), and carrying `Tokens.scaled()` to the per-surface motion aliases.
   The visible programme (W8, W9) now has an off-station render loop; compositor work
   (blur, window animation, Overview) still needs the station.
5. A pointer-driven review needs `ydotool`'s absolute axis calibrated against this 4K
   screen first, or it silently clicks somewhere else. Who holds which files is in
   `docs/AGENT_COORDINATION.md`.
