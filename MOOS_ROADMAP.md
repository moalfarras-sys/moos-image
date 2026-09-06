# MoOS release roadmap

Only completed evidence closes an item. Source code, a package, or a green
parser alone is not runtime proof. Current facts live in `PROJECT_STATE.md`.

**Current release audit:** `docs/SYSTEM_AUDIT_RESUME_20260906.md`. The desktop
OOM incident is unresolved (S03); short healthy samples do not close it. Source
motion settings are not a performance benchmark. Launcher routing has executable
coverage; native focus/scale acceptance remains open.

## Active development plan

The next work should keep MoOS moving as a complete operating system, not as a
theme layer. Order matters:

1. **Release train hygiene:** keep one clean candidate branch, merge only
   reviewed fixes, run host-aware checks through `moos-host-run` when Codex is
   inside Flatpak, and retire already-merged remote branches after proof.
2. **Boot-to-login experience:** continue the single MoOS visual sequence from
   Plymouth to the login, lock and logout surfaces. Source now includes bounded
   boot overlays and the responsive clock/calendar; the next closure is measured
   signed-artifact frames with no fallback flash across scale and locale.
3. **Simple daily use:** one obvious place for updates, recovery, apps, Remote,
   language and theme. Keep technical logs collapsed at rest, make every action
   explainable, and preserve Arabic/RTL as a first-class path. The Remote control
   centre now fits short displays with diagnostics collapsed, and the Horizon
   island shows authenticated active/paused viewers immediately; preserve both
   contracts while extending the same clarity to the remaining first-party apps.
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
   as blocked. (Plan B01/B02.)
6. **Artifact proof before promotion:** x86 generic, NVIDIA, cloud and ARM must
   each have exact digest boot evidence. A beautiful source tree is not a
   release until the artifact has booted, logged in, smoked apps, rebooted and
   powered off cleanly.

## Remote v38 acceptance

v39 extends this work with Liquid Glass phone controls, viewport-aware sheets,
explicit clipboard directions and RTL rail/keyboard geometry repairs. Evidence
and deployment status: [mobile workspace](docs/REMOTE_V39_MOBILE_WORKSPACE.md).
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

## Release blockers

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
  pre-expansion backup is retained. See docs/ORACLE_STORAGE_HEALTH_20260905.md. UEFI, signed exact
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
