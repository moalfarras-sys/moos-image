# MoOS release roadmap

Only completed evidence closes an item. Source code, a package, or a green
parser alone is not runtime proof. Current facts live in `PROJECT_STATE.md`.

## Active development plan

The next work should keep MoOS moving as a complete operating system, not as a
theme layer. Order matters:

1. **Release train hygiene:** keep one clean candidate branch, merge only
   reviewed fixes, run host-aware checks through `moos-host-run` when Codex is
   inside Flatpak, and retire already-merged remote branches after proof.
2. **Boot-to-login experience:** continue the single MoOS visual sequence from
   Plymouth to Plasma Login Manager to lock/logout. High-impact work belongs on
   full-screen owned surfaces: bounded boot overlays, measured greeter frames,
   lock/logout clarity, and no generic fallback flash.
3. **Simple daily use:** one obvious place for updates, recovery, apps, Remote,
   language and theme. Keep technical logs collapsed at rest, make every action
   explainable, and preserve Arabic/RTL as a first-class path.
4. **Adaptive performance for everyone:** extend `moos-visual-tier` from motion
   policy into a broader local resource policy: compositor cost, indexing,
   update concurrency, AI defaults and Remote encoding based on real capability,
   not product names.
5. **Artifact proof before promotion:** x86 generic, NVIDIA, cloud and ARM must
   each have exact digest boot evidence. A beautiful source tree is not a
   release until the artifact has booted, logged in, smoked apps, rebooted and
   powered off cleanly.

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
- [ ] Merge only the proven tree; verify exact GHCR digests/signatures and
  artifact manifests.
- [ ] Reconfirm the signed rollback on the real NVIDIA host, stage the exact
  release, reboot visually, run selfcheck/post-update/journal/hardware/app
  proofs, suspend/resume, reboot again and power off.

## External proofs

- [ ] Import the exact boot-proven ARM disk into OCI Ampere A1 and prove serial,
  cloud-init, SSH key, root growth, update/rollback and tunneled KRDP. If OCI
  credentials or capacity are unavailable, report READY-BUT-NOT-DEPLOYED.
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
