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
- `main` has one long-lived branch and no open pull request other than the one that carries
  this file; 22 merged topic branches were deleted after each was proven an ancestor of `main`.
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

Last measured ON the station: signed `moos-nvidia` `44.20260915.836`
(`sha256:086f7086…`), with `44.20260913.824` retained for rollback; a later live
review names `44.20260916.848` as booted. **Not re-measured on 2026-09-17** — that
day's work was done from a Windows workstation. Re-measure with `bootc status`.

**Updating it:** MoOS origins are digest-pinned, so `bootc upgrade` reports "no
changes" forever. Use the MoOS Updater (Settings → Update MoOS, or Mo AI's "Update
my system"), or wait for the nightly train; then restart.

A root-owned local override `/etc/plasmalogin.conf.d/90-moos-development-autologin.conf`
enables one-session automatic login for `moos` during this development cycle. It is
not in the image and sets `Relogin=false`; remove it with `pkexec rm` on that path.

Review shadows left on purpose: `~/.local/share/plasma/plasmoids/org.moos.{search,island,nova.clock}`
and `~/.local/share/plasma/wallpapers/org.moos.ui2.wallpaper` (W2 source). Any
`THEME_REV` ≥ 59 removes all four at the first login after the update (W6 is 62).

## What an x86 machine gets with this update (W2 → W6)

| Wave | PR | What the user gets | `THEME_REV` |
| --- | --- | --- | --- |
| W2 | #108 | MoOS Hub controls in the desktop menu and wallpaper page; shadow sweep covers Search and the scene | 59 |
| W3 | #109 | every widget removable again; an owner-chosen wallpaper survives login and drift checks | 60 |
| W4 | #110 | Mo AI tool harness: tool schemas from the fixed grammar, confirmation cards, result read-back | — |
| W5 | #111 | Island Store jobs and camera/microphone/screen-share chips; inline Search answers | 61 (added by #114) |
| fix | #114 | x86 `main` green again; ARM cache staleness; Baloo budget group; `moos-control status` 30 s → 0.2 s | 61 |
| W6 | #115 | what W4/W5 promised, working; App Drop; readable secondary text; identity wording | 62 |

W2 and W3 were reviewed live on the station. **W4, W5 and W6 have never been seen on
a MoOS desktop.**

## Wave W6 — what was found, and what kind of evidence exists

Found by rendering first-party apps from source and by running the shipped code, while
every gate was green:

- **W4 never sent tools to the model unless Hermes was ready**, ran ONE step, killed
  long actions at 90 s, and let the window claim `confirmed`. Now: tools on every
  machine, up to 8 steps, confirmed actions are jobs whose exit status is the result,
  and the executor (`needs_confirmation()`) decides what needs a card. Ten read-only
  `moos-inspect` tools (closed grammar, redacted, 12 KB) let it look before it acts.
- **W5's Island read files through `XMLHttpRequest`, which plasmashell refuses**
  (measured on Qt 6.11.2), so Store jobs never appeared and the privacy chip always
  said "Application". State now travels as file-name tokens through `FolderListModel`.
- **`moai-do` printed success after a dismissed password prompt** in four actions.
- Mo AI's privileged-action card used an undefined colour; four apps painted secondary
  text with the DISABLED role (1.6:1 on light schemes, now ≥4.66:1 on all 16 schemes);
  `[Icons]` and `[Theme]` headers in `/etc/xdg` had been commented out since 2026-08-28;
  17 MoOS-owned strings named another desktop or distribution.
- **App Drop (new):** an AppImage, portable `.tar.*`/`.zip` or `.flatpakref` opened,
  dropped on `~/Applications` or sent from the file manager becomes an app after a
  default-No dialog, with no administrator rights; an `.rpm` is handed to the existing
  signed route. Type is decided by magic bytes; AppImages are only ever extracted
  inside bubblewrap; MoOS writes the launcher entry.

Evidence class: repository gates on Fedora 44 under WSL2 (Qt 6.11.2, Kirigami 6.29,
bubblewrap, node); Mo AI's loop in a real window against a scripted provider and the
real `moai-control`; the sandbox argv under real `bwrap`; the signed image build and
all four boot proofs of cycle B. **Not proven:** anything on a MoOS desktop; tool choice
by a real free model (P3.3); a real AppImage, the dialog, the file-manager action and
the folder watch (P4.6).

## W6.1 — released with cycle C, never seen on a MoOS desktop

- **About this device** is a page of MoOS Settings, not the desktop's own module (which
  names the projects MoOS is built from): edition in words, version, build date, signed
  image, rollback, kernel as its number, hardware, Copy details (P2.9).
- **Mo AI skills:** twelve repair playbooks shipped read-only, found with `list_skills`
  and read with `read_skill` (43 tools: 30 run at once, 13 ask first); a gate reads
  every skill the way the model will. Eight one-tap chips on the home screen (P3.10).
- **Mo AI's rail at the DEFAULT 940 px window** laid icon and label out in opposite
  corners of the pill; every earlier review had been rendered at 1400 px. Measured in
  the real window now. The Device panel printed the raw kernel release (`…fc44…`).

## In review (`fix/hub-polish-20260917`) — needs release cycle D

Found the first time the desktop ITSELF could be looked at off the station
(`scripts/review/render-desktop.sh`: the real `plasmashell` with MoOS's layout, scene, Hub,
bar and plasmoids under Xvfb; `render-lockscreen.sh` for the lock screen):

- In an Arabic session the Hub's English date line hung on the LEFT edge of a right-aligned
  clock column (each line aligned by its own script).
- The Island's privacy chip read "الميكروفون قيد الاستخ…": the capsule was sized by counting
  characters and ignored its always-shown Stop button.
- MoOS Search assigned `undefined` to two labels on every desktop start.
- `THEME_REV` 63. The same renders are the first time W6's Island repair was SEEN working in
  a real shell (a Store job token shows "تثبيت Firefox - 45%"; a privacy token names the app).
  Source-harness evidence: no compositor effects, X11 not Wayland, stock icons blank.

## ISO proof (P0.8) — cause measured

The image's CI proof-channel helper read the IPv4 default route ONCE, and MoOS
disables NetworkManager-wait-online, so nothing orders that read after DHCP. Run
`35265328509` — the first green ISO proof since, and the first where the helper speaks
on the console — shows it: first boot, route 16 ms after the daemons were active;
second boot, 1.02 s (the first read was empty; one retry found it). The old helper
died on that read and never added its SSH rule. The harness change written on the
other theory (a fresh slirp forward per boot) was measured by the same run as
irrelevant (`first-boot-forward=alive`). Cycle C's ISO proof (`35276847573`) was the second
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

- Station and A1 review of W4–W6 after the update: Hub controls, Search answers, Island
  jobs and privacy chips, Mo AI's tool loop and cards with a real free model, App Drop
  with a real AppImage, `THEME_REV=62` sweeping the review shadows. Record it here.
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

1. Owner: update the station and the A1 with the MoOS Updater, restart, and walk "Station
   review owed for W4–W6.1" in `docs/DEVELOPMENT_PLAN.md`; record PASS/FAIL here.
2. Merge the polish pull request once its checks are green (repo gates, x86 image gates, ARM
   build), then release cycle D: `TMPDIR=<dir> scripts/release-candidate.sh --promote` on
   `main`. If ONE proof fails for an external reason, dispatch that workflow alone again with
   the same image reference and promote by hand with the new run id (see `RELEASE.md`).
3. The visible programme the owner asked for — desktop, widgets, login, motion (W7–W9) — now
   has an off-station loop: render the desktop, the launcher, the lock screen and any app from
   source, change, render again. Compositor work (blur, window animation, Overview) still
   needs the station.
4. P0.8 closes after one more green ISO proof; P0.7 stays open.
