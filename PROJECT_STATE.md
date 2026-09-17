# MoOS current state

Current measured facts only; Git owns history. Last measured 2026-09-17.

## Source and release truth

- **x86 production is W6**, read back from the registry 2026-09-17 after promotion
  run `35269505270`: `moos`, `moos-nvidia` and `moos-cloud` `:latest` =
  `44.20260917.858`, revision `a8622f95`, digests `3b30e42c69d4…`, `c8f94adde60d…`,
  `143ec830db4f…` — the digests the candidate build signed. Proofs, all attempt 1
  on that revision: build `35261411076`, QCOW2 generic/NVIDIA/cloud
  `35265314956`/`35265319663`/`35265323922`, ISO `35265328509`. The previous x86
  production was W1 (`92248b5d`, `44.20260916.848`), so an x86 machine moves W1 → W6
  in one update.
- **ARM production**, read back at the same time: `moos-arm:latest` =
  `44.20260917.435`, revision `1b5f402f` (the #114 integration: `THEME_REV` 61, the
  Baloo budget group, `moos-control status` no longer hanging). `build-arm.yml`
  promotes every green push to `main`; the run for W6 (`35266924177`) was still in
  its boot proof when this was written. Read the registry, not this line.
- `main` holds W2–W6, the #114 integration and the pull-request image build (#116).
  Its x86 build is green again (`35261305751` for #114, `35266924175` for W6).
- Release cycle A (candidate `51cc2ac3`) passed the signed build and all three QCOW2
  boots and lost its ISO proof to plan row P0.8; nothing was promoted from it.
- The intermittent ARM second-boot `plymouthd` SEGV is still open (P0.7); green ARM
  runs since then had no fix applied.
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

Walked on the station against the ordered checklist, on `44.20260917.858`. Each
row says what was actually seen. Frames are in `~/.cache/moos-station-review/`.

| # | Item | Result |
| --- | --- | --- |
| 1 | Booted version | **PASS.** `44.20260917.858`, digest `c8f94adde60d…`, previous deployment retained. "About this device" is W6.1 and is **not in this image**, so its half of the row is untested |
| 2 | Review shadows swept | **PASS.** Both shadow directories empty at the first login after the update; `THEME_REV` 62 applied |
| 5 | MoOS Search inline answers | **PASS.** `12*7` returns one `آلة حاسبة` row reading **84**, above the file-result group, with a copy action. The unit-conversion half is **untested**: the session's keyboard layout is Arabic, so synthetic Latin typing produces Arabic letters — the calculator was driven with layout-independent key codes. Typing an unparseable query did produce the `اسأل Mo AI` hand-off row |
| 6 | Island privacy chips | **PASS for detection and naming.** `moos-privacy-monitor` wrote `active-mic-98-pw%2Drecord` within 3 s of a real PipeWire capture starting and held it for the capture's life, and it wrote `active-screen-98-Mo%20PC%20Remote` while Mo PC Remote was genuinely capturing (`MoRemotePersonal` and its portal were running). The Island rendered its Remote chip with the live green dot, which is the documented priority (Remote outranks a privacy chip), so the camera/mic chip's own foreground appearance is still **unseen**. The Store-job half is **untested** |
| 12 | Secondary text on a light scheme | **PASS.** Mo Store's hero sentence and every publisher line are clearly readable on `MoOSUI2AuroraLight` — this is the text that measured 1.6:1 before W6 |
| 3, 4, 10, 11 | Hub controls, widget removal, App Drop, dismissed auth | **Untested.** All need pointer input, and `ydotool`'s absolute pointer mapping does not match this screen (two calibration attempts landed the click elsewhere). Keyboard- and CLI-driven items were done instead; these need either a calibrated pointer or the owner |
| 7, 8, 9, 13 | Mo AI rail, tool loop, cards, identity answers | **Blocked.** Row 7 is W6.1 and not in this image. 8, 9 and 13 need a cloud brain: `moai-brain-mode` reports "free cloud only … configure with moai-config" and no provider key is configured, which is plan row P0.5 and an owner action |

Two W7 facts were measured on the same session and are recorded in
`docs/DEVELOPMENT_PLAN.md`: the stock switcher's reading order, and that
Overview's QML is compiled into `libkwin.so.6` and so cannot be re-shaped
without forking KWin.

## W6 and W6.1 in source

W6's findings are in git (PR #115) and its behaviour is now reviewed on the desktop
above. What matters here is what is true today:

- **W6 is production and is installed on the station.** Mo AI's tool loop runs in steps
  with ten read-only `moos-inspect` tools and truthful results; the Island reads state as
  file-name tokens through `FolderListModel` because plasmashell refuses
  `XMLHttpRequest`; `moai-do` no longer reports success after a dismissed password
  prompt; secondary text is the theme's text at 72% on all sixteen schemes; App Drop
  turns an AppImage, portable archive or `.flatpakref` into an app after a default-No
  dialog and with no administrator rights.
- **W6.1 is merged (`291361ad`) and NOT yet released**, so it is not on any machine:
  Settings' own "About this device" page (P2.9), Mo AI's twelve read-only skills with
  `list_skills`/`read_skill` and eight one-tap chips (P3.10), Mo AI's rail corrected at
  the default 940 px window, and the Device panel no longer printing the raw kernel
  release. It needs release cycle C.

**Not proven anywhere yet:** tool choice by a real free model (P3.3); a real AppImage,
its dialog, the file-manager action and the `~/Applications` watch on a desktop (P4.6).

## ISO proof (P0.8) — cause measured

The image's CI proof-channel helper read the IPv4 default route ONCE, and MoOS
disables NetworkManager-wait-online, so nothing orders that read after DHCP. Run
`35265328509` — the first green ISO proof since, and the first where the helper speaks
on the console — shows it: first boot, route 16 ms after the daemons were active;
second boot, 1.02 s (the first read was empty; one retry found it). The old helper
died on that read and never added its SSH rule. The harness change written on the
other theory (a fresh slirp forward per boot) was measured by the same run as
irrelevant (`first-boot-forward=alive`). One green run is one run: the row closes
after two more.

## Proven source/image behavior

- Cycle B's signed build passed every image gate for `moos`, `moos-nvidia` and
  `moos-cloud` at `a8622f95`; all three disks booted twice under QEMU/KVM; the final
  ISO installed offline, logged in, opened every first-party app twice, rebooted and
  powered off.
- `pr-image-gates.yml` built the generic image on a pull request and ran its in-image
  gates in 16 minutes, pushing nothing (run `35266474587`).
- Horizon motion gates cover finite settling, reversal, hidden state, reduced motion
  and pointer/key paths. Native sounds decode and map to KDE event IDs; installed
  playback/mute acceptance remains open.
- Free cloud AI returned English and Arabic replies through the live gateway with an
  explicitly free provider. That proves chat, not system control.
- `moos-privacy-monitor`'s polling costs 0.66% of one core off the station (P5.4).

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

1. The station is updated and reviewed (above). Owner: update the **A1** and review
   there; and configure a free Mo AI provider key (P0.5), which is the only thing
   blocking the four Mo AI rows of the station checklist.
2. W6.1 is merged (`291361ad`). Release cycle C is the next release; do not start a
   second one while `Build MoOS image` run `35272501490` is still working on `main`.
3. P0.8 closes after two more consecutive green ISO proofs; P0.7 stays open.
4. W7 (Workspace) is under way on the station on `feat/w7-workspace-20260917`: the
   MoOS Switcher, `Tokens.scaled()` and MoOS Arrange have landed on that branch and
   were reviewed live. Still open in W7: a live preview in the Arrange surface,
   touchpad and gesture defaults (P5.2), and carrying `Tokens.scaled()` to the
   per-surface motion aliases. Who holds which files is in
   `docs/AGENT_COORDINATION.md`.
5. A pointer-driven review needs `ydotool`'s absolute axis calibrated against this
   4K screen first, or it silently clicks somewhere else.
