# MoOS current state — measured 2026-10-09

This machine is the Oracle A1 ARM station. Historical NVIDIA workstation
measurements are separate hardware evidence; they are not current A1 readback.
The full audit and acceptance gaps are in [the Arabic audit](docs/AUDIT_20261008_AR.md).
The sole execution backlog is [DEVELOPMENT_PLAN.md](docs/DEVELOPMENT_PLAN.md).

## Installed Oracle system

- Signed MoOS ARM 44.20261006.724, source fa85b2daf3db0f1f823b3159bb46b25571a99740.
  Digest: sha256:f9441728f373cf19d59bdc4116c42833392a628e3ac01f33905cd76fce3c7305.
- Signed ARM 44.20261009.733, source
  46b46e87e282a3f817f1f8aaf099a25a59d083fc, digest
  sha256:8b7857b6e2b5ac95d93768ee6c0699f09bd00041b75a4c676ff55f6eb7c810de,
  is staged through moai-do update, not yet booted. Its update replaces the
  intermediate .728 stage; signed .710 rollback and booted .724 remain.
- Fresh installed selfcheck: 51 passed, 3 notes, no broken checks. Notes are
  the staged update and owner-masked mpris-proxy/obex, not missing MoOS code.
- No failed system/user units. Four rootless photos/database/cache/SMB
  containers are healthy. About 38 GiB writable storage remains after preserving the new ISO;
  removing two audit-owned superseded builds reclaimed about 4 GiB.
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
- FileBrowser 2.0 and Immich 3.3.1 passed authenticated/persistent-state
  upgrade checks. FileBrowser SQLite was added to encrypted local backup and
  restored with identical hash/integrity. code-server 4.141.0 is selected for
  the restart; the current 4.140.0 process remains.
- Photos/SMB/browser IDE have previous post-reboot acceptance. Phone background photo
  upload, off-host originals backup and long phone/WAN endurance remain unproven.
  Details: [Oracle profile](docs/ORACLE_CLOUD_WORKSTATION.md).

## Promoted releases and public delivery

Stable x86 editions are 44.20261009.1018 from candidate source
144b1a6ad04f0b7fa442183110ad6d969f636add. ARM .733 uses main merge
46b46e87; its tree exactly matches that candidate. Source-only merges and
image-only builds do not constitute promoted releases.

| Edition | Version | Signed digest |
| --- | --- | --- |
| Desktop | 44.20261009.1018 | 3055eb28ac032492a053da1efb9493c9780e7bfa20a01c7c3300961693bfee92 |
| NVIDIA | 44.20261009.1018 | c5977fc7d68bc6cd708b85931711f3ff8eb44be5a4468edc7e9c490b9dfc0dd0 |
| Cloud x86 | 44.20261009.1018 | 0160fddaab3deb4a8f3eef1d87d5343b3f0a1472e6f3f26f1bba4882dfccb977 |
| ARM | 44.20261009.733 | 8b7857b6e2b5ac95d93768ee6c0699f09bd00041b75a4c676ff55f6eb7c810de |

First-attempt proofs: signed build 37910223752; generic/NVIDIA/cloud disks
37916917245, 37916921267, 37916925157; offline ISO 37916929153; x86 promotion
37946594645; ARM main build/two UEFI boots/promotion 37946472626.
The independent main push run 37946472602 failed its cloud build on an
upstream HTTP 503; it did not supply this qualified release.

The new generic x86-64 Intel/AMD UEFI ISO is 5,808,128,000 bytes, SHA-256
612a175308a76436549590cfb3d0ff7771ffe075a89a3fd77ab7ca47e675055a.
The complete anonymous transfer, detached signature/hash and resume ranges
passed for its versioned private-R2 Worker URL; both public sidecars match CI.
Website PR54 is merged at 49a0dd9f, production READY. Canonical redirect,
first/resume ranges, signature/checksum and all required production routes
passed. Arabic/English 390/1440 renders loaded real Mira images with no
overflow or browser errors. [New delivery receipt](docs/releases/2026-10-09-public-download-proof.json).
The old [canonical receipt](docs/releases/2026-10-08-public-download-proof.json)
and .1011 download paths remain available for the older file. P0.12 is closed
for its original release; every new release repeats the delivery procedure.

Website PR52 is merged at 50db25d9: Mira's actual installed interface and both
original faces replace the retired Mo AI picture. Arabic/English desktop/phone
and full-size image checks passed; displayed demo data is disclosed.

## Audit correction batch — promoted, local reboot pending

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
passed all seven modules without changing that gate. Final capture privacy passed native .NET checks and the cached full-image build.
PR220 and PR221 are merged. The unchanged identity/signature/initramfs gates
passed in the exact signed candidate and all four promoted editions. Local
installed acceptance remains required after the authorized reboot.

## Offline installer follow-up — exact candidate qualified

The 8ebe0591 signed x86 build 37881477050 and its three QCOW2 proofs
37888183362/37888186631/37888189800 passed. ISO 37888192868 refused an
empty EFI mount directory; x86 promotion correctly stopped. Diagnostic ISO
37900328567 installed offline successfully, then failed while collecting its
large trace. That is not an installed-system login/reboot proof.

The actual process which detached EFI remains unidentified. A private native
virtual-disk negative control reproduced the exact bootc error after external
ESP detachment. The same real invocation in a private mount namespace retained
the ESP and reached the deliberately nonexistent image source. The helper now
checks the root/staging/ESP mounts and staging alias before invoking bootc,
then isolates the install process's mounts. Eligibility, source, SELinux,
signed-origin rearming, empty-root verification and finalization stay enforced.

Additional source fixes make the install lock mandatory before shared state
is touched, and move diagnostics from a linkable shared /tmp name to a private
0700 directory/0600 file. Busy admission preserves the backend's existing
progress/log; links and foreign/hard-linked state are refused. This does not
prove every front-end concurrency path. ISO evidence collection now caps each
file to 128 KiB plus a separator, fails on unreadable files and reports the
actual command deadline. Fresh full native image and first-attempt signed build, three QCOW2 proofs,
offline installed-system login/reboot proof and promotion passed for this
follow-up. Public delivery verification is still required before the website
replaces its old ISO.

User/system application updates ran again on October 9; Chromium updated to
154.0.8037.97; GNOME 51 runtime and locale updates also completed. Website's eleven apparently unique historical tips match the
exact heads of merged squash PRs; their product work is already integrated.

## Engine audit follow-up — not part of the promoted .733/.1018 image

Native A1 readback reports only the Linux engine. Wine/Waydroid/LXC/Bottles
are absent; the ARM kernel contains Binder support and QEMU translates Linux
ELF, which does not establish Windows or Android application support.
The x86 source ships those engines, but ten per-app lifecycle journeys remain
owed; universal application compatibility is not an accepted support claim.

Private negative controls found downloaded-APK false-success on zero-exit
ERROR diagnostics, unsupported PE architecture admission, and Android setup
misclassifying failed status as initialized. Team corrections and independent
review run on isolated fix/app-engine-admission-20261009; they are source work,
not installed fixes. Upstream Waydroid's CLI discards the install result:
an existing package after reinstall cannot prove the requested version.
Do not mark a replacement successful without an authoritative outcome.

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
