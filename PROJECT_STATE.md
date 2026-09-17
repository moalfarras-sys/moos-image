# MoOS current state

Current measured facts only; Git owns history. Last measured 2026-09-17.

## Source and release truth

- **x86 production is W1**: revision `92248b5d`, version `44.20260916.848`, promoted
  by run `35156269206` from build `35148344935`, QCOW2 generic/NVIDIA/cloud
  `35150447739`/`35150452495`/`35150457478` and ISO `35150461926` (all attempt 1).
  Registry read-back: generic `f1d62342…`, NVIDIA `2b4b04c4…`, cloud `51a3f37c…`.
- **ARM production is W5**, read back 2026-09-17: `moos-arm:latest` =
  `44.20260917.431`, revision `7f182689`, digest `e92466a996a5…`. `build-arm.yml`
  promotes every green push to `main`, so ARM is ahead of x86 until an x86 cycle
  completes. ARM's build of the integration revision `51cc2ac3` passed its boot
  proof (run `35252524849`, branch dispatch — it promotes nothing).
- `main` (`7f182689`) holds W2–W5 and is RED for x86 (W5 broke an image-only gate).
  The integration that repairs it is PR #114 (`51cc2ac3`); wave W6 is stacked on it
  (`feat/w6-operator-appdrop-workspace-20260917`). None of W2–W6 is in an x86 release.
- **Release cycle A, candidate `51cc2ac3` (2026-09-17):** signed build of all three
  editions PASSED (`35250170484`) — the only proof that the gate repair works inside
  an image; QCOW2 generic/NVIDIA/cloud PASSED (`35252506869`, `35252511348`,
  `35252516097`); ISO proof FAILED (`35252520329`) at the installed reboot, exactly
  as on `57874d6c` and `8b272b87`: SSH "timed out during banner exchange" for 1000 s
  while QGA reported the second boot, `:22` listened and no unit had failed. Nothing
  was promoted. See "ISO proof" below (plan row P0.8).
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
| Desktop | Plasma/KWin 6.7.5, Wayland, 3840×2160@60, scale 250% |
| Kernel | `7.2.5-200.fc44.x86_64` |
| Network | Intel AX210 Wi-Fi/Bluetooth + RTL8125 Ethernet |
| Health | zero failed system units and zero failed user units |

Last measured ON the station: signed `moos-nvidia` `44.20260915.836`
(`sha256:086f7086…`), with `44.20260913.824` retained for rollback; a later live
review names `44.20260916.848` as booted. **Not re-measured on 2026-09-17** — that
day's work was done from a Windows workstation. Re-measure with `bootc status`.

A root-owned local override `/etc/plasmalogin.conf.d/90-moos-development-autologin.conf`
enables one-session automatic login for `moos` during this development cycle. It is
not in the image and sets `Relogin=false`; remove it with `pkexec rm` on that path.

Review shadows left on purpose: `~/.local/share/plasma/plasmoids/org.moos.{search,island,nova.clock}`
and `~/.local/share/plasma/wallpapers/org.moos.ui2.wallpaper` (W2 source). Any
`THEME_REV` ≥ 59 removes all four at the first login after the update.

## What `main` and the open branches carry beyond x86 production

| Wave | PR | What the user gets | `THEME_REV` |
| --- | --- | --- | --- |
| W2 | #108 | MoOS Hub controls in the desktop menu and wallpaper page; shadow sweep covers Search and the scene | 59 |
| W3 | #109 | every widget removable again; an owner-chosen wallpaper survives login and drift checks | 60 |
| W4 | #110 | Mo AI tool harness: tool schemas from the fixed grammar, confirmation cards, result read-back | — |
| W5 | #111 | Island Store jobs and camera/microphone/screen-share chips; inline Search answers | 61 (added by #114) |
| fix | #114 | x86 `main` green again; ARM cache staleness; Baloo budget group; `moos-control status` 30 s → 0.2 s | 61 |
| W6 | open | what W4/W5 promised, working; App Drop; readable secondary text; identity wording | 62 |

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
  default-No dialog, with no administrator rights. Type is decided by magic bytes;
  AppImages are only ever extracted inside bubblewrap; MoOS writes the launcher entry.

Evidence class: 171 repository gates pass on Fedora 44 under WSL2 (Qt 6.11.2, Kirigami
6.29, bubblewrap, node); Mo AI's loop is proven in a real window against a scripted
provider and the real `moai-control`; the sandbox argv is proven under real `bwrap`.
**Not proven:** anything on a MoOS desktop; tool choice by a real free model (P3.3); a
real AppImage, the dialog, the file-manager action and the folder watch (P4.6); the
signed image build of W6 (its image-only gates have never run).

## ISO proof (P0.8) — cause found, fix unproven

`tests/boot_x86_qcow2.sh` documented on 2026-09-03 that slirp can keep pre-reboot flow
state on a forward and then accept TCP without delivering a banner, and reserves one
forward per boot. The ISO proof got its reboot half on 2026-09-16 with one forward and
has failed three of four runs since. `ebd694fb` gives it a forward per boot, makes a
green run measure the old forward (`reboot-channel.txt`), and makes the proof-channel
helper wait for the default route and speak on the console. No ISO run has passed on
it yet.

## Proven source/image behavior

- Cycle A's signed build passed every image gate for `moos`, `moos-nvidia` and
  `moos-cloud` at `51cc2ac3`, and all three disks booted twice under QEMU/KVM.
- The last full NVIDIA local build passed repository gates, 179 MoPlayer tests,
  MoRemote tests/publish, QML runtime smoke, identity firewalls, clean image state,
  `bootc container lint` and initramfs inspection (`ostree-prepare-root`, Plymouth
  assets, six NVIDIA modules).
- Horizon motion gates cover finite settling, reversal, hidden state, reduced motion
  and pointer/key paths. Native sounds decode and map to KDE event IDs; installed
  playback/mute acceptance remains open.
- Free cloud AI returned English and Arabic replies through the live gateway with an
  explicitly free provider. That proves chat, not system control.

## Development environment

- On the station: VS Code is a Flatpak; host work uses `flatpak-spawn --host`.
  `just workstation-check` is a read-only inventory. .NET SDK `10.0.401` and Flutter
  3.47.4 (the image-builder pin) are installed.
- Off the station (2026-09-17): Windows 11 + WSL2 `FedoraLinux-44`.
  `scripts/review/setup-review-distro.sh` installs the toolchain,
  `scripts/review/mirror-gates.sh` runs gates on a mirror with git's file modes, and
  `scripts/review/render-app.sh` renders a first-party app from source with a real
  MoOS colour scheme and prints QML binding errors. Several gates cannot run on
  Windows itself (`termios`, `os.getuid`, exec bits).
- `.kilo/` is local untracked agent state and is not product source.

## Fixed earlier, waiting for an x86 promotion

- Owner wallpaper reverted after reboot → `moos-theme` adopts the live choice first
  (W3, reviewed live on the station for both paths).
- Widgets could not be removed: `immutability=0` is not Mutable (Plasma: 1/2/4) → W3,
  `THEME_REV` 60; the station was repaired live, backups in `~/.cache/moos-live/`.
- x86 `main` red after W5: the image gate's `source()` stripped `/* … */` from bash,
  and `${privacy_act#*/}` closed a span opened 235 lines earlier, hiding 24 of 28
  settings routes → #114; `tests/test_image_gate_source_parser.py` runs the gate's
  parser in Repo gates. No pull-request check can see image-only gates yet (P0.9).
- A1: `moos-index-policy` wrote Baloo's key under the wrong group; `moos-control
  status` hung 30 s without Bluetooth hardware (now 218 ms) → #112, #113 inside #114.

## Open evidence gaps

- One x86 promotion with a green ISO proof; then stage, reboot and read W2–W6 back
  from `/usr` on the station, and the W5/W6 island on the A1 after its ARM promotion.
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

1. Merge #114, then the W6 pull request, with merge commits and nothing else in
   between (promotion requires `main`'s tree to equal the candidate's).
2. Release cycle B on the W6 revision: `scripts/release-candidate.sh --ref <branch>`,
   then `--promote` once build, 3×QCOW2 and ISO are green on attempt 1. If the build
   fails an image-only gate, fix on the branch and dispatch a FRESH cycle. If only the
   ISO proof fails, read `reboot-channel*.txt` in `moos-iso-install-proof` first.
3. On the station: `bootc status`, update, reboot; read back Hub controls, Search
   answers, Island jobs/privacy chips, the Mo AI tool loop and cards, App Drop with a
   real AppImage; confirm `THEME_REV=62` swept the review shadows. Record it here.
4. On the A1 after the ARM promotion: the island and search plasmashell actually runs,
   and `moos-control status` in well under a second.
5. P0.7 stays open; the experience waves continue from `docs/DEVELOPMENT_PLAN.md`.
