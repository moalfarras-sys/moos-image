# MoOS release roadmap

Only completed evidence closes an item. Source code, a package, or a green
parser alone is not runtime proof. Current facts live in `PROJECT_STATE.md`.

**Master program (2026-09-11):** [the MoOS completion plan](docs/MOOS_COMPLETION_PLAN.md)
orders the work from release unblock (P0) through one product (P1), Mo AI as the
system operator (P2), Android/Windows apps (P3), form factors (P4) and world-class
trust (P5), with a measured scorecard. This file remains the release-gate list.

**Current release evidence (2026-09-11):** the formal five-proof promotion
completed in run `34432578942` for `c0cc94e7`. The daily-driver NVIDIA PC is
booted on signed `44.20260910.796`, retaining signed `44.20260908.782` for
rollback. New changes need their own candidate, disk and ISO proofs; earlier
success does not qualify a changed image. See `PROJECT_STATE.md`.

Candidate `a0e7ef96` is explicitly rejected: its three x86 images and three
QCOW2 proofs passed, but ISO run `34583782652` proved the MoOS Flatpak bootstrap
lost its enablement during installer presets while the inherited foreign-remote
bootstrap ran. ARM run `34581668929` also exposed their race and an early
graphical readiness sample. Source now gives MoOS one preset-backed store owner,
masks the inherited unit, rejects hidden disabled remotes, waits for ARM
readiness and strictly owns empty mutable directories. All five x86 proofs and
the ARM pipeline must start again from the corrected commit.

Candidate `e10181f9` is also rejected: build `34648333190`, all three QCOW2 proofs
and ARM passed, but ISO run `34650456175` failed at the installed system's Plasma
Login step — PAM rejected the correct disposable password on all three attempts.
The proof now empties the password field before typing (gate-pinned); it and the
Mo AI/Settings fixes ride on `feat/moos-completion-20260911`, whose next candidate
must pass all five x86 proofs again.

**Release integration 2026-09-07:** `main` was unbuildable for all three x86
editions (a comment inside a backslash continuation truncated a `sed`); fixed
and gated. The Device page named hardware that does not exist on aarch64; fixed
against `lscpu` ground truth. Bubblewrap, which Mo AI's sandbox depends on, was
reaching the image only by inheritance; now required by name and asserted in the
finished image. Wallpaper drift now repairs itself on a timer. Settings and the
Mo AI agent workspace are merged. Host suite 115/115.

**Current release audit:** `PROJECT_STATE.md`. The desktop
OOM incident is unresolved (S03); short healthy samples do not close it. Source
motion settings are not a performance benchmark. Launcher routing has executable
coverage; native focus/scale acceptance remains open.

**Unified platform pass (2026-09-10, source):** Settings and Mo AI now share
CPU identity and the visual-tier GPU description, with executable ARM/x86 and
malformed-backend fixtures in `test_settings_hardware_identity.py`. Architecture,
remaining API work and ordered acceptance are in
[the integration audit](docs/MOOS_UNIFIED_PLATFORM.md). Native dark/light and Arabic captures now prove the Settings workspace
cards and keyboard navigation. Full image and hardware acceptance remain separate.

## Active development plan

The next work should keep MoOS moving as a complete operating system, not as a
theme layer. Order matters:

1. **Release train hygiene:** keep one clean candidate branch, merge only
   reviewed fixes, run host-aware checks through `moos-host-run` when Codex is
   inside Flatpak, and retire already-merged remote branches after proof.
2. **Boot-to-login experience:** continue the single MoOS visual sequence from
   Plymouth to the login, lock and logout surfaces. Source now includes bounded
   boot overlays and the responsive clock/calendar. The 2026-09-08 source pass
   places the rendered sting over the exact Graphite login landscape and retains
   that ground through the measured Plymouth→login compositor gap; 16:9 and 4:3
   previews plus source/initramfs gates are green. A clean local x86 image build
   also passed and independently proved the exact backdrop inside the final
   107 MiB initramfs. The next closure remains measured signed-artifact frames
   with no fallback flash across scale and locale; a built image without a
   visible UEFI boot does not close the release item.
3. **Simple daily use:** one obvious place for updates, recovery, apps, Remote,
   language and theme. Keep technical logs collapsed at rest, make every action
   explainable, and preserve Arabic/RTL as a first-class path. The Remote control
   centre now fits short displays with diagnostics collapsed, and the Horizon
   island shows authenticated active/paused viewers immediately; preserve both
   contracts while extending the same clarity to the remaining first-party apps.
   *Progress:* the desktop itself now has one obvious place to change it —
   Settings → Appearance → Customize Desktop, a MoOS UI2 widget explorer that
   overlays Plasma's own shell while leaving Plasma the owner of every applet and
   all persistence. It also repairs Arrange on the software-rendered editions
   (ARM, cloud), where upstream's shader-based edit mode drew an opaque black
   screen. Both overlays are gated on the finished image in `build.sh` and
   `build-arm.sh`. Still open: the same pass over the panel/dock editor.
4. **Adaptive performance for everyone:** extend `moos-visual-tier` from motion
   policy into a broader local resource policy: compositor cost, indexing,
   update concurrency, AI defaults and Remote encoding based on real capability,
   not product names. *Progress:* `moos-visual-tier` now publishes an advisory
   `budget` block (file_indexing / update_concurrency / ai_default /
   remote_encode) from the same probe, in `--json` and the state file. Still
   open: the consumers (baloo, `moai-do`, the Remote encoder) reading it under
   their own owners, and the P01 before/after workload measurement.
5. **Boot-partition headroom is a release contract.** `/boot` is 974 MiB and
   holds two complete deployments; measured 2026-09-06 on the live A1 it was 78%
   full, so the next signed update had nowhere to stage. The ARM initramfs is now
   gated for size and omits four desktop GPU modules while retaining ARM Tegra
   firmware. Include kernel and DTB trees in headroom calculations, not only the
   initramfs. This host recovered ~97 MiB by consolidating identical DTBs with
   every boot file and security attribute verified unchanged. Do the same measurement
   for the x86 editions — `moos-nvidia` must keep its kmod in-initramfs, so its
   answer will differ — and treat a release that cannot stage an N+1 deployment
   as blocked. (Plan B01/B02.) *Re-measured 2026-09-07 on the live A1:* `/boot`
   is 214 MiB of 974 MiB (**24%**, 693 MiB free) holding two deployments, so the
   pressure that blocked staging on 2026-09-06 is gone on this host. The contract
   stands and the x86 measurement is still owed.
6. **Artifact proof before promotion:** x86 generic, NVIDIA, cloud and ARM must
   each have exact digest boot evidence. A beautiful source tree is not a
   release until the artifact has booted, logged in, smoked apps, rebooted and
   powered off cleanly.

## Mo AI cloud-only and Hermes acceptance

The latest owner policy permits free or paid **cloud** models on every edition:
free is the default; paid requires an explicit labelled choice and never follows
a free quota failure automatically. Local model downloads, inference and speech
models are unavailable through Mo AI's public paths. The former four-provider
catalogue and cross-provider fallback plan are superseded by the current
OpenRouter policy. See [the cloud-only plan](docs/MOAI_CLOUD_ONLY_PLAN.md) and
[current session checkpoint](PROJECT_STATE.md).

- [x] Source policy enforces free model identity and zero price ceilings, with
  an explicit paid selection covered by fixtures. No paid inference was made.
- [x] Public local-engine entry points refuse; migration retires fixed legacy
  units while preserving private backups, existing weights and unrelated files.
  Unreachable legacy helper bodies remain for C2b cleanup.
- [x] Real installed Hermes 0.21.0 answers through the authenticated isolated
  adapter and Mo AI cloud gateway. Production free-cloud Arabic response took
  about 3 seconds. The adapter preserves supplied text/history; tools are empty,
  subprocess execution is blocked, and system actions remain with `moai-do`.
- [ ] Desktop chat answers without an installed Hermes runtime. *Progress:* on the
  daily driver every desktop message failed with HTTP 503 because the absent
  runtime was treated as unavailable; source on `feat/moos-completion-20260911`
  answers through the direct free route with an honest `direct-fallback` label
  (live: HTTP 200 in 2.2 s and a real in-app reply with its Remove chip). Signed
  image acceptance remains; packaging Hermes itself remains the item below.
- [ ] App lifecycle through one authority (plan M2.1). *Progress:* source on
  `feat/moos-completion-20260911` routes install, uninstall and update-apps
  through `moos-storectl` with confirmation, and a live daily-driver run of the
  branch's `moai-do` installed, removed and updated apps with readback. Signed
  image and in-app chip acceptance remain.
- [ ] Brain latency (plan M2.2). The automatic `openrouter/free` route selected a
  550B reasoning model (36.7 s, 13.1 s, and 15.5 s with no answer). *Progress:*
  source on `feat/moos-completion-20260911` orders verified free models by measured
  preference, cools down refused models and asks the next free candidate before any
  byte is sent; live answers took 2.0 s and 1.8 s and a tool call 1.9 s. Remaining:
  a recurring evaluation instead of a one-sample list, and signed-image acceptance.
- [ ] Migrate existing OpenCode configs that still name the retired local model.
- [ ] Finish C2b legacy-body cleanup while preserving HTTP, identity and
  privilege guards; prove first-login and upgrade migration from historic layouts.
- [ ] Package/prove Hermes availability on fresh systems across all four
  editions. The installed-runtime adapter reports absence and uses direct cloud;
  the owner's working runtime is not proof that the dependency ships.
- [ ] Complete native QML/phone and bounded-memory acceptance. Incremental
  streaming, persistent memory and plugins are not currently provided; SSE
  delivers a final-answer frame.
- [ ] Inspect the finished native image, then prove the signed exact artifact
  and post-update runtime. The current native build is in progress; these source
  and local runtime checks do not close the signed-release gate.

## Remote v38 acceptance

v39 extends this work with Liquid Glass phone controls, viewport-aware sheets,
explicit clipboard directions and RTL rail/keyboard geometry repairs. Evidence
and deployment status: [mobile workspace](docs/MO_PC_REMOTE_ARCHITECTURE.md).
The owner confirmed keyboard/bar visibility on their phone in both orientations;
browser viewport emulation does not close the wider physical-device gate below.

- [x] Local ARM agent/controller built and activated with previous binary retained.
- [x] Real Wayland capture, Arabic/emoji readback, click and relative motion in a
  dedicated focused test window; browser portrait/landscape/desktop input checks.
- [ ] Physical Android/iOS keyboard and Safari matrix, including IME, selection,
  autocorrect, background/resume and weak Internet connections.
- [ ] Windows runtime input and signed image integration of this revision.
- [ ] Per-controller held-key ownership for simultaneous active controllers;
  view-only teardown is fixed, but active controllers still share one injector.

## Remote v40 — the cloud desktop (2026-09-12)

Measured on the shipped bundle in a real Chromium and on the live Oracle A1. Detail and the
honest limits: [v40 cloud desktop](docs/REMOTE_V40_CLOUD_DESKTOP.md).

- [x] The real mouse wheel scrolls the right way. One wire convention (positive dy = down) across
  the controller, the portal helper and both injectors; the Win32 difference absorbed at the
  Win32 boundary. Gated by `tests/test_remote_scroll_direction.py` and by the sign that actually
  leaves the production bundle in `browser-input.test.mjs`.
- [x] An upright phone can fill itself with the desktop in one tap: 28.6% → 90.5% of the stage,
  measured. Nothing rotates automatically; the offer is the change.
- [x] `moos-visual-tier`'s `remote_encode` has a reader. Auto is bounded by what the host said it
  can encode, an explicit preset is not, and the Display sheet names the limit.
- [x] `npm run test:browser` has a runner. The only test that exercises the production bundle
  end to end previously had none, which is how an inverted wheel shipped past a green suite.
- [x] `moos-visual-tier.service`, `moos-hardware-adapt.timer` and `moos-verify-origin.timer` are
  enabled on ARM. They shipped `disabled` on the maintainer's A1; `mokernel` reported "this
  machine has not been adapted yet" and there was no `hardware-adapt.state` to contradict it.
  `tests/test_arm_unit_enablement.py` keeps the two build scripts comparable.
- [x] **The three ARM enables are proven in the BUILT image, not just in the script.** The ARM
  workflow's "Verify the built image" step now runs the image and asserts each wants symlink
  exists under `/usr/etc/systemd/system/{graphical,timers}.target.wants/` before anything is
  signed — the same class of check that would have caught this the first time, since a
  `systemctl enable` in a build script proves nothing about the bytes.
- [ ] **The A1 must show `enabled` after its update reboot.** The image gate proves the symlink
  ships; only the running machine proves it takes effect.
- [ ] **The H.264 give-up is diagnosed, not fixed.** A viewer's decoder gives up roughly 80s into
  session after session and takes the whole room to JPEG. The reason now travels with the vote
  and is logged; the cause is still unknown.
- [ ] **`budget.update_concurrency` still has no reader.** `moai-do update` does not consult it,
  so a 32-core machine and a 2-core A1 fan out identically. Pinned by
  `tests/test_moos_visual_tier.py` so it cannot be forgotten again.
- [x] One user-visible product name. The login screen said "Mo Remote", the launcher says
  "Mo PC Remote", the About line said "Mo Remote Personal"; the surfaces a person reads now agree.
  Load-bearing identifiers are untouched.
- [x] The .NET tree has a local, complete build check. Seven .csproj files with seven hand-written
  lists of the shared sources cost a 25-minute ARM build to report one missing line; `just
  dotnet-check` now says the same in under a minute, `tests/test_dotnet_project_coverage.py` keeps
  it complete, and `moremote-fast.yml` runs it on pull requests — which `build.yml`, triggered
  only on pushes to main, never did.
- [ ] Physical Android/iOS keyboard and Safari matrix — unchanged from v38/v39, still open.

## Release blockers

- [ ] **Clean-state and first-boot Store proof.** Known DNF and empty Flatpak
  files are removed during compose, unknown mutable files fail the new gate,
  and sysusers owns `plugdev`. Offline recreation of the store, Flathub remote
  and locale policy passed in a disposable container. Full candidate boot/install
  proof remains required. Package-owned empty directories are now declared via
  tmpfiles; the disposable image retains only the EFI/GRUB boot-asset warning. [Integration audit](docs/MOOS_UNIFIED_PLATFORM.md).

- [x] **Make the x86 proof chain readable.** Diagnostic redirections, KSplash
  startup and ISO session UID were repaired without weakening the zero-failed-unit
  check. The complete chain subsequently passed on 2026-09-10.
- [x] **Unstick production `latest` (emergency channel repair, 2026-09-09).**
  `moos` / `moos-nvidia` / `moos-cloud` `:latest` were still on `44.20260823.650`
  while the daily-driver NVIDIA PC already ran signed candidate
  `44.20260908.782`. `moos-image-update` correctly returned `blocked-downgrade`,
  and the Updater UI painted that protective state as a red "invalid state"
  failure — so the owner saw "system update is broken". Tags were moved to the
  cosign-verified digests from successful build run `34213809427`
  (revision `ae31af5e…`, also tagged `20260908`). Resolve at that time returned
  `state=current`. This did **not** run `promote-x86.yml` (ISO proof still
  red); it only restored the update channel to the signed digests already
  running on hardware / QCOW2-proven. The subsequent full promotion is recorded below.
- [x] **Run `promote-x86.yml` through the full proof chain.** Run `34432578942`
  succeeded on 2026-09-10 for `c0cc94e7`, consuming the signed build, three
  QCOW2 proofs and offline ISO install. Repeat all proofs for the new candidate.
- [ ] **NVIDIA hardware acceptance.** `docs/NVIDIA_HARDWARE_ACCEPTANCE.md` is
  written and entirely unrun: boot, Plymouth, login, desktop, module, KWin on
  Wayland, displays, suspend/resume, update, rollback, reboot. Nothing in CI
  can substitute for it — a runner has no GPU.

- [ ] Boot the final ARM QCOW2 twice through AArch64 UEFI with zero critical
  failures; capture serial, journal and non-blank login/desktop frames.
- [ ] Log into that ARM artifact and open/use/close/reopen Launcher, Dolphin,
  Konsole, Settings, Mo AI, Store, Updater, Recovery, theme picker, MoPlayer and
  Mo PC Remote. Prove native ARM binaries and real backend status.
- [ ] Package that exact QCOW2 as `MoOS-ARM.utm.zip` and validate its schema,
  seed, manifest, icon and hashes. Perform a visible UTM-equivalent login.
- [ ] Build the final signed generic/NVIDIA/cloud x86 images and run exact
  UEFI QCOW2 boots, reboot and poweroff gates.
- [ ] Build the final signed-digest ISO, boot its LiveOS, perform the offline
  installation to a blank disk, detach the ISO, log in, smoke apps, reboot and
  power off the installed system.
- [ ] Complete representative visual captures for 1080p/1440p/4K,
  100/125/150/200/225%, English/German/Arabic and dark/light. Every responsive,
  RTL and rendering class needs a real frame.
- [ ] Exercise Mo PC Remote end to end from representative Android, iOS and
  desktop browsers over LAN and Tailscale: pair, reconnect, rotate, type in
  Arabic/English, transfer files, copy text/images, stream audio, pause/resume,
  revoke trust and recover from a network handoff. Source/live-host evidence now
  covers the responsive control centre and authenticated desktop presence, but
  it does not replace those physical-client proofs.
- [ ] Merge only the proven tree; verify exact GHCR digests/signatures and
  artifact manifests.
- [ ] Reconfirm the signed rollback on the real NVIDIA host, stage the exact
  release, reboot visually, run selfcheck/post-update/journal/hardware/app
  proofs, suspend/resume, reboot again and power off.

## External proofs

- [ ] Import the exact boot-proven ARM disk into OCI Ampere A1 and prove serial,
  cloud-init, SSH key, root growth, update/rollback and tunneled KRDP. If OCI
  credentials or capacity are unavailable, report READY-BUT-NOT-DEPLOYED.
  Current state (2026-09-05): LIVE on Frankfurt A1 with a 200 GiB boot disk.
  Online expansion, reboot and a full read-only Btrfs scrub passed; the
  pre-expansion backup is retained. See docs/MOOS_ARM_ORACLE.md. UEFI, signed exact
  origin, cloud-init, SSH key, root growth, graphical target, browser-rendered
  private desktop, input portal, HTTPS/audio and a real reboot are proven with
  zero failed units. Deliberate update/rollback proof remains open, so this item
  is not checked complete.
- [ ] Import `MoOS-ARM.utm.zip` on the owner's iPhone/iPad and record boot time,
  idle RAM, desktop responsiveness and core app launches. Without access to the
  physical device, report OWNER-DEVICE-TEST-REQUIRED.
- [ ] Run the final ISO installation on real hardware. QEMU is the release gate;
  firmware/disk-specific proof remains a separate hardware exercise.

## Continuous quality

- A test that executes a MoOS desktop tool must isolate the session bus, display and
  XDG directories. Until 2026-09-12 `test_moos_theme_safety.py` rewrote the live
  desktop wallpaper whenever the gates ran on a workstation.
- Every runtime bug follows reproduce → root cause → fix → regression → artifact
  proof. A gate that passed the broken behavior must be strengthened, not edited
  merely to stay green.
- One UI routes to one backend authority and one state store. No duplicate update,
  theme, hardware, AI, remote or install writer is allowed.
- Keep signed updates, SELinux, Polkit, Secure Boot compatibility, atomicity and
  rollback. Development root access never becomes a product privilege shortcut.
- Preserve one MoOS identity from EFI-controlled surfaces through Plymouth,
  Plasma Login Manager, desktop, applications, recovery and installation.
- Checkpoint and push after every coherent phase and before long builds, reboots,
  risky system changes or context compaction.

Settings source product pass: [audit, native English/Arabic evidence and integration limits](docs/MOOS_SYSTEM_DEVELOPMENT_PLAN.md). Signed-image and hardware acceptance remain with release integration.
