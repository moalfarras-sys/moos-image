# MoOS current state — measured 2026-10-08

This machine is the Oracle A1 ARM station. Historical NVIDIA workstation
measurements are separate hardware evidence; they are not current A1 readback.
The full audit and acceptance gaps are in [the Arabic audit](docs/AUDIT_20261008_AR.md).
The sole execution backlog is [DEVELOPMENT_PLAN.md](docs/DEVELOPMENT_PLAN.md).

## Installed Oracle system

- Signed MoOS ARM 44.20261006.724, source fa85b2daf3db0f1f823b3159bb46b25571a99740.
  Digest: sha256:f9441728f373cf19d59bdc4116c42833392a628e3ac01f33905cd76fce3c7305.
- Signed .710 rollback remains. The owner-authorized reboot was verified on
  2026-10-07; this audit has not replaced the installed origin with a local image.
- Fresh installed selfcheck: 51 passed, 2 notes, no broken checks. Notes are
  owner-masked mpris-proxy and obex, not missing MoOS code.
- No failed system/user units. Four rootless photos/database/cache/SMB
  containers are healthy. About 98 GiB writable storage remains.
- Session LANG/LANGUAGE and region formats are Arabic. KDE translation is ar.
  System fallback locale C.UTF-8 is distinct from the actual Arabic session.
  Look-and-feel readback: org.moos.ui2.nova.
- Kernel 7.2.8; Plasma 6.7.5 and Qt 6.11.2 are the installed stack recorded by
  release acceptance. Do not separately layer a new desktop or kernel.
- systemd-oomd is running but monitors no cgroup. KWin's shipped MemoryHigh
  guard is separate protection, not evidence of an applied oomd policy.
- SSH readback: root login, passwords and keyboard-interactive authentication
  are disabled; public-key authentication is enabled. Public firewall exposes
  SSH; the listening passimd service is not opened by that zone.
- Photos/SMB/browser IDE have post-reboot acceptance. Phone background photo
  upload, off-host originals backup and long phone/WAN endurance remain unproven.
  Details: [Oracle profile](docs/ORACLE_CLOUD_WORKSTATION.md).

## Promoted releases and public delivery

All four stable editions share source fa85b2da; source-only documentation
merges and image-only scheduled builds do not constitute newer promoted releases.

| Edition | Version | Signed digest |
| --- | --- | --- |
| Desktop | 44.20261007.1011 | c3689b0e64c48cdf7d5de7d83b3dc156bf264f6381cce98d36376681b07ebf99 |
| NVIDIA | 44.20261007.1011 | 9b77fc3eaed85d2b3e9b38809c9ab91c1de22854f31706f79d6b4d2f76bd4e8e |
| Cloud x86 | 44.20261007.1011 | 4e187edbcced76e0c134ee68ab45c83bf3f9bf4ebae259235ed1306a289162cb |
| ARM | 44.20261006.724 | f9441728f373cf19d59bdc4116c42833392a628e3ac01f33905cd76fce3c7305 |

First-attempt stable proofs: signed build 37552824167; generic/NVIDIA/cloud disks
37558743993, 37558747906, 37558751431; offline ISO 37558755639; x86 promotion
37562359722; ARM build/two UEFI boots/promotion 37539003204.
Ten actual apps opened, closed and reopened in the final offline-installed ISO.

The generic x86-64 Intel/AMD UEFI ISO is 5,796,462,592 bytes, SHA-256
cbe92573e620101f274081c884671e4b63ffbcdb765521713d21ada1dbe9cb1c.
[Public download](https://moalfarras.space/api/os/download?type=iso) passed the
complete anonymous transfer, signature/hash and >4 GiB ranges at
2026-10-08T15:14:41Z. [Canonical receipt](docs/releases/2026-10-08-public-download-proof.json).
Private R2 through the named Worker preserves site/mail DNS. The old blocked
Blob store is bypassed without deleting unrelated data. P0.12 is closed.

Website PR52 is merged at 50db25d9: Mira's actual installed interface and both
original faces replace the retired Mo AI picture. Arabic/English desktop/phone
and full-size image checks passed; displayed demo data is disclosed.

## Audit correction batch — source, not installed delivery

The audit baseline covered 4,383 tracked files, including 3,806 text files and
411 Python AST parses with zero syntax errors. Full maintained repository gates
and every Remote .NET executable passed. This inventory is not a claim that
every behavior, third-party package or hardware combination is qualified.

- Support privacy: reproduced leaks from quoted JSON/OAuth, PEM contents,
  fine-grained GitHub keys and compressed IPv6. Redaction now precedes trimming;
  output uses private unpredictable atomic files. New regressions fail old code.
- Remote: NuGet reported five ImageSharp 3.1.11 advisories despite successful
  compilation. The single fallback conversion now uses pinned MIT SkiaSharp
  4.153.1, bounds input/pixels and rejects incomplete PNG/JPEG data. Native ARM
  pixel/scale/quality/invalid-input tests pass. Fresh production audit has no
  findings. All Remote projects inherit fail-closed NuGet audit policy; restoring
  the old package fails on the real advisories.
  Each fallback screenshot uses its own 0700 temporary directory and is removed
  after conversion, rather than a predictable shared-/tmp filename.
- Language: a refused flock previously continued into KDE/Flatpak/session writes.
  It now stops before changing anything. Fresh Mira profiles follow supported
  session language, with Arabic fallback and explicit saved choices preserved.
- ARM net-install: both stale target manifests now name the independently
  signature/label-verified .724 fallback snapshot. Recovery resolves the official
  promoted registry tag once, with a 30-second bound, then verifies its immutable
  digest. Static metadata is only an explicitly older fallback on retrieval failure. Reinstall
  clearing follows successful signature verification, invalid explicit targets
  cannot select another disk, and unimplemented repair never reports success.
  All filesystems/partitions need explicit erase consent, unreadable layouts
  stop, and auto-selection refuses more than the bundle's two disks.
  Menu cancellation stops, failed installs cannot announce completion or reboot,
  and firmware boot selection requires one named MoOS entry with intact hex ID.
- ARM verifier: the built image exposed the old cosign 2.4.1 static fallback.
  Desktop and recovery now use one reviewed 3.1.3 upstream asset with its
  SHA-256 pin verified before execution/install; wrong bytes/version/architecture
  and failed downloads stop. Native image and exact-release verification follow.
- [OWNERSHIP.md](OWNERSHIP.md) records existing licences, attribution and official
  identity without relicensing upstream works. CODEOWNERS names the maintainer.
  It does not prevent copying/forking or claim a registered trademark.

Native ARM desktop and recovery full builds passed. A concurrent desktop build
failed the unchanged 10-second KCM readiness gate; the isolated full rebuild
passed all seven modules without changing that gate. Final capture privacy
receives native .NET checks and the cached full-image build before push.
Exact candidate, boot/promotion and installed acceptance for this
new batch remain required before calling these changes delivered. Follow
[RELEASE.md](RELEASE.md); all unchanged identity/signature/initramfs gates remain.

## Evidence still owed

- Hardware boot visuals, suspend, hotplug/multi-monitor, laptop/touch and a
  deliberately broken-update rollback/forward cycle.
- Arabic/English accessibility, keyboard/screen-reader and full scale/light/dark
  matrix across the actual native shells and all first-party apps.
- One qualified locale/update/job authority across every adapter; provider
  onboarding/cancellation/failure flows on a clean account and second model.
- Real Windows/Android per-app qualification and a generated supported-device
  matrix. Package presence or VM startup is insufficient.
- Phone/WAN Remote endurance, physical audio/lamps and owner-spoken Mira turns.
- Applied, measured memory-pressure policy; sustainable security-release cadence,
  SBOM/provenance, support window and staged rollout.
- Complete rights/attribution inventory. KDE/Linux rights permit independent
  modification; official naming/signatures distinguish the maintainer's release.

Past incidents, rejected prototypes and dated station diaries remain in Git.
Keep safety lessons in AGENTS.md and operational contracts in component docs;
do not append superseded current-state snapshots here.
