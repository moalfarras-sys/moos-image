# MoOS release readiness — verified 2026-10-07

The four production editions are signed and boot-proven at source
`fa85b2daf3db0f1f823b3159bb46b25571a99740`. The public launch is **not ready**:
the anonymous ISO route returns HTTP 503 and the existing public Blob store
returns HTTP 403, `Your store is blocked`. A valid CI ISO is preserved before
its seven-day artifact expiry; it is not yet a qualified public download.
This document records evidence and hardware sizing; the sole backlog remains
`DEVELOPMENT_PLAN.md`, especially P0.12, P5.1, P5.5 and P5.7.

## Exact release evidence

| Edition | Published version | Signed production digest |
| --- | --- | --- |
| Desktop (`moos`) | 44.20261007.1011 | `sha256:c3689b0e64c48cdf7d5de7d83b3dc156bf264f6381cce98d36376681b07ebf99` |
| NVIDIA | 44.20261007.1011 | `sha256:9b77fc3eaed85d2b3e9b38809c9ab91c1de22854f31706f79d6b4d2f76bd4e8e` |
| Cloud x86 | 44.20261007.1011 | `sha256:4e187edbcced76e0c134ee68ab45c83bf3f9bf4ebae259235ed1306a289162cb` |
| ARM | 44.20261006.724 | `sha256:f9441728f373cf19d59bdc4116c42833392a628e3ac01f33905cd76fce3c7305` |

All four actual signatures were independently verified with `cosign.pub`, and
manifest architecture, version and revision read back. Final first-attempt
proofs: x86 build [37552824167](https://github.com/moalfarras-sys/moos-image/actions/runs/37552824167),
generic/NVIDIA/cloud QCOW2 [37558743993](https://github.com/moalfarras-sys/moos-image/actions/runs/37558743993),
[37558747906](https://github.com/moalfarras-sys/moos-image/actions/runs/37558747906),
[37558751431](https://github.com/moalfarras-sys/moos-image/actions/runs/37558751431),
final ISO [37558755639](https://github.com/moalfarras-sys/moos-image/actions/runs/37558755639),
x86 promotion [37562359722](https://github.com/moalfarras-sys/moos-image/actions/runs/37562359722),
ARM build/two boots/promotion [37539003204](https://github.com/moalfarras-sys/moos-image/actions/runs/37539003204).
Scheduled image-only builds are not additional boot/promotion evidence.

The final generic x86 ISO is `moos-offline.iso`, **5,796,462,592 bytes**;
SHA-256 `cbe92573e620101f274081c884671e4b63ffbcdb765521713d21ada1dbe9cb1c`.
Preserved with its signature, checksum and `qualified-release.json` under
`~/moos-releases/44.20261007.1011/x86-iso/`, outside Git. Streaming verification
of its detached signature succeeded; its full hash matches the final CI ISO
boot manifest and embedded image digest. Offline install was completed with
networking disabled, followed by installed-system boot and clean shutdown;
ten actual desktop apps opened, closed and reopened. Reviewed screenshots
prove those rendered states, not every interaction or every hardware device.
The owner can also find these files in private
`CloudFiles/Releases/MoOS-44.20261007.1011/`; read-only copy-on-write copies
share disk extents while keeping the archive independent. This is authenticated tailnet access,
not the anonymous public download qualification.

CI artifact access requires a GitHub login and expires; it is not the public
release link. Follow [public delivery qualification](PUBLIC_DOWNLOADS.md)
before publishing: one stable anonymous HTTPS file, exact size/full hash and
both byte ranges, matching signature and successful promotion. Leave website
availability false until that passes. The blocked store also contains existing
MoPlayer downloads; do not delete unrelated files or silently upgrade billing.

## PC requirements and support scope

The available ISO targets **x86-64 Intel/AMD PCs**. UEFI boot/offline install is
qualified in CI. This does not qualify 32-bit CPUs, every laptop/GPU, legacy
BIOS, or all Secure Boot configurations. ARM uses separate QCOW2/UTM/Oracle
artifacts; the x86 ISO does not install on an Oracle A1 or an Apple ARM Mac.
The preserved ISO embeds the generic desktop; separate NVIDIA/cloud signed
images do not imply separate qualified consumer ISOs already exist.

The actual x86 live/disk proof uses **2 vCPUs and 4 GiB RAM**
(`tests/boot_live_iso.sh`, `tests/boot_x86_qcow2.sh`). That is a boot-test size,
not a measured minimum for smooth everyday work. No universal minimum or
cross-device performance guarantee has been qualified. Practical sizing below
is a recommendation based on workload, to be measured on the chosen hardware:

| Workload | RAM | CPU | Storage |
| --- | --- | --- | --- |
| Light desktop/browser | 8 GB | Modern 64-bit dual core; 4 threads preferable | 128 GB SSD recommended |
| Comfortable desktop and development | 16 GB | 4 cores / 8 threads, Core i5 or Ryzen 5 class | 256 GB SSD recommended |
| Parallel builds, many containers or large media libraries | 32 GB or more | 8 cores or more | 512 GB SSD or sized to the library |

A modern Intel/AMD integrated GPU with a working Linux graphics driver is
appropriate for ordinary desktop use; a discrete card is not a blanket
requirement. The NVIDIA edition uses the open kernel driver; NVIDIA specifies
**Turing or later** (for example GTX 16 / RTX 20 and newer; check the exact PCI
device in [NVIDIA's compatibility table](https://github.com/NVIDIA/open-gpu-kernel-modules#compatible-gpus)).
MoOS's physical RTX 2080 SUPER record is bounded evidence, not qualification
of every listed GPU. Suspend, multiple displays and rollback boot still need
the acceptance in [NVIDIA hardware qualification](NVIDIA_HARDWARE_ACCEPTANCE.md).
A 16 GB USB drive is a practical installation-media recommendation for this
5.8 GB ISO; it is not the target system disk requirement.

## Installed Oracle acceptance and remaining boundaries

This A1 actually rebooted into signed ARM `.724`, retaining signed `.710`.
The 06:48 CEST acceptance reports selfcheck **51 passed / 0 broken**,
post-update **55 / 0**, zero failed system/user units and no kernel errors.
Boot was 13.6 s, graphical target 8.6 s. Remote runs the immutable executable;
the exact delivered home override was archived/retired. Files, browser IDE,
photos and authenticated SMB services survived reboot; four containers are
healthy. User and system native Flatpak update/repair transactions complete
successfully with nothing left to update. Five OCI entries still appear in
`remote-ls --updates`, but every installed `xa.alt-id` matches the remote
manifest digest: these are false pending entries, not missing updates. A
targeted native transaction also reports nothing to update; the discrepancy
has an [upstream OCI report](https://github.com/flatpak/flatpak/issues/3748).
Installed
Plasma is 6.7.5, Qt 6.11.2, kernel 7.2.8 and Tailscale daemon/CLI 1.102.5;
the stale home CLI was backed up and replaced with the packaged CLI link.
This follows the signed approved release rather than an unqualified beta.

The current 2 OCPU / 12 GB / 200 GB profile suits serialized light development
and media work. Workload estimates: 4 OCPU / 24 GB for more comfortable shared
desktop/editor/media use; 8 OCPU / 32 GB for heavier builds. These are not
benchmarks or an executed paid resize. [Oracle's current allowance](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)
is equivalent to 2 OCPUs / 12 GB; do not describe 4 / 24 as free.

Remaining acceptance includes real iPhone Files navigation and background
photo uploads, phone/WAN reconnect/endurance, an off-host backup of originals,
the physical Intel/AMD/laptop device matrix, suspend and Bluetooth/device
pairing, and measured OOMD policy (the active daemon currently monitors no
cgroup). Current signature/build/boot checks do not close these tasks.
Next-Plasma canary and publisher EOL migration remain explicit plan work.
An app catalog or installed compatibility runtime does not prove all Windows
or Android apps work. These boundaries prevent a false “no problems anywhere”
claim while retaining the measured working release.
