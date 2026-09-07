# MoOS x86 system plan

Status: historical x86 baseline, 2026-08-27. The current cross-edition plan is
[MOOS_SYSTEM_DEVELOPMENT_PLAN.md](MOOS_SYSTEM_DEVELOPMENT_PLAN.md). Native ARM
and Oracle are active; the old UTM experimental branch remains archived. Keep
the measurements below as historical evidence, not current machine readings.

MoOS is not defined by a package list or a theme. The product boundary is the
whole path from signed image and firmware hand-off to login, desktop, hardware
policy, applications, updates, recovery and remote use. Each capability must
have one owner, a runtime proof and a graceful low-resource mode.

## Measured baseline

Measured on the maintainer's real MoOS desktop (Core i5-14400F, RTX 2080 SUPER,
15 GiB RAM, SATA SSD):

| Surface | Current measurement | What it says |
|---|---:|---|
| Firmware | 10.232 s | Outside the OS image; report it separately |
| Boot loader | 4.103 s | Review only after preserving rollback/recovery access |
| Kernel + initrd | 10.204 s | The 202 MiB NVIDIA initramfs is the first owned size target |
| Userspace to graphical target | 5.893 s | Local desktop boot was unnecessarily coupled to NFS/network |
| Kernel start to login manager | about 15.55 s | Primary phase-one boot KPI |
| Login to workspace | 6.219 s | `plasma-kcminit.service` alone cost 3.174 s |

The same capture found three competing Flatpak update paths and a system update
failure caused by a static delta decompression limit. Those are correctness
problems, not merely performance numbers.

## Non-negotiable architecture

- One signed, immutable x86 base for generic, NVIDIA and cloud editions. A
  driver or role is layered; the base is never forked.
- One owner per capability. A timer, desktop tool and background service must
  not all independently update the same payload.
- Hardware adaptation is deterministic and reversible. It may tune experience;
  it must never invent drivers, replace the kernel or change the signed origin.
- The low-resource experience is intentionally designed. Reduced blur, motion
  and background work must still look like MoOS, not like a broken rich mode.
- Every user-visible surface is MoOS. The three identity gates remain hard
  release gates.
- A source-level green check is necessary but insufficient. Release requires a
  built image, VM boot, real login/desktop proof and offline install proof.

## Phase 1 — power button to desktop

This phase owns the critical path before adding features.

1. Remove false dependencies from the login path.
   `nfs-client.target` is disabled by default and a systemd generator enables it
   only when `/etc/fstab` contains a real NFS mount. A desktop without NFS no
   longer waits for network/RPC services; a workstation that uses NFS retains it.
2. Make early users/groups complete.
   The initramfs receives the image's canonical account databases, preventing
   early udev from discarding audio, video, render, input, disk, KVM, TPM and
   login-device permissions because their groups do not exist yet.
3. Consolidate Flatpak maintenance.
   System and user scopes use one bounded helper with a no-static-delta retry.
   The separate uupd Flatpak authority is disabled; it retains its Distrobox job.
4. Protect artifact truth.
   A failed ISO proof may upload an explicitly `unproven` diagnostic image, but
   the final `moos-live-iso` exists only after live boot and offline install both
   succeed.
5. Build and remeasure the image. Do not accept a source-only result.

Phase-one acceptance on the same machine:

- no failed system or user service after the desktop settles;
- a local-only desktop reaches the greeter without waiting for the network;
- kernel start to greeter below 12.5 s, or a documented hardware-bound remainder;
- login to usable workspace below 4.5 s;
- initramfs smaller than the measured 202 MiB baseline without dropping the
  OSTree, storage, encryption, NVIDIA or recovery boot paths;
- generic and NVIDIA images pass the same boot, identity and experience gates.

## Phase 2 — session and application coherence

- Profile the real Plasma session again and remove the measured
  `plasma-kcminit` bottleneck without skipping required migration or input work.
- Define one startup budget. Network discovery, update checks, indexing, AI and
  Remote start after the workspace is interactive or on demand.
- Make first-party applications share one MoUI component library, settings
  model, status vocabulary, transaction UI and accessibility behavior.
- Remove duplicate front doors and duplicated background agents. Compatibility
  shims may route old actions to the owner; they may not become a second owner.
- Add cold/warm launch budgets and real visual smoke tests for every first-party
  app in Arabic, English, light, dark and reduced-motion modes.

## Phase 3 — adaptive hardware platform

- Turn the existing `essential`, `balanced`, `integrated` and `flagship` visual
  tiers into a documented system resource policy covering compositor cost,
  indexing, AI defaults, update concurrency and Remote encoding.
- Validate Intel and AMD integrated graphics, AMD and NVIDIA discrete graphics,
  software-rendered VMs, SATA/NVMe storage and 4/8/16+ GiB RAM profiles.
- Detect capabilities, not marketing names: render node, driver health, codec
  support, memory pressure, storage latency, battery and display topology.
- Never promise every x86 device. Publish a tested hardware matrix and a clear
  degraded-mode result for unsupported acceleration or firmware.

## Phase 4 — reliability as a product surface

- Exercise rollback against a deliberately broken signed candidate.
- Add boot-health state and a MoOS recovery path that explains which deployment
  is running, queued and recoverable in plain language.
- Run install, update, rollback, suspend/resume, Wi-Fi, Bluetooth, audio,
  multi-monitor and hot-plug tests on real hardware, preserving evidence.
- Record performance and failure-state telemetry locally and privately; export
  a user-approved diagnostic bundle with secrets removed.
- Release only a run-and-revision-bound candidate that passed OCI build, disk
  boot, ISO live boot, offline install and second boot.

## Phase 5 — visual continuity and delight

- Treat firmware hand-off, boot loader, Plymouth, login, lock, desktop, logout
  and recovery as one motion and colour sequence, with no foreign identity or
  generic fallback flash.
- Keep the Liquid Glass language legible on the essential tier: hierarchy and
  silhouette survive even when blur and ambient animation are removed.
- Verify the result by captured frames and interaction, not asset existence.
  Review 1x/2x, 720p/1080p/4K, RTL/LTR, light/dark and reduced motion.

## Work order

Finish and prove phase 1 before visual expansion. Then optimize session startup,
consolidate application/runtime ownership, widen the hardware matrix, prove
rollback and hardware lifecycle, and only then polish cross-boot visual motion.
Each phase updates its measured baseline and adds a gate that is demonstrated to
fail when its protected behavior is deliberately broken.
