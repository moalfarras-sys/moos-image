# MoOS current state — measured 2026-10-09

Oracle A1 and the physical NVIDIA workstation develop the same MoOS product.
Evidence below names its device: Oracle measurements are not NVIDIA readback,
and registry promotion is not proof that either machine has rebooted into it.
The full audit and acceptance gaps are in [the Arabic audit](docs/AUDIT_20261008_AR.md).
The sole execution backlog is [DEVELOPMENT_PLAN.md](docs/DEVELOPMENT_PLAN.md).

## Installed Oracle system — last recorded readback 2026-10-07

- Signed MoOS ARM 44.20261006.724, source fa85b2daf3db0f1f823b3159bb46b25571a99740.
  Digest: sha256:f9441728f373cf19d59bdc4116c42833392a628e3ac01f33905cd76fce3c7305.
- Signed .710 rollback remains. The owner-authorized reboot was verified on
  2026-10-07; this audit has not replaced the installed origin with a local image.
- Recorded installed selfcheck: 51 passed, 2 notes, no broken checks. Notes are
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

The three x86 stable editions remain at source fa85b2da. ARM .728 completed
build, disk and promotion at source 8ebe0591 (run 37881437511); its exact
registry digest and cosign signature were read back on 2026-10-09.
Source-only merges and image-only scheduled builds do not constitute promotion.

| Edition | Version | Signed digest |
| --- | --- | --- |
| Desktop | 44.20261007.1011 | c3689b0e64c48cdf7d5de7d83b3dc156bf264f6381cce98d36376681b07ebf99 |
| NVIDIA | 44.20261007.1011 | 9b77fc3eaed85d2b3e9b38809c9ab91c1de22854f31706f79d6b4d2f76bd4e8e |
| Cloud x86 | 44.20261007.1011 | 4e187edbcced76e0c134ee68ab45c83bf3f9bf4ebae259235ed1306a289162cb |
| ARM | 44.20261009.728 | abc5aff9496d57917d94254c67da5af4caa94c412067d62a72a537a8e907f673 |

First-attempt stable proofs: signed build 37552824167; generic/NVIDIA/cloud disks
37558743993, 37558747906, 37558751431; offline ISO 37558755639; x86 promotion
37562359722; ARM build/two UEFI boots/promotion 37539003204.
Ten actual apps opened, closed and reopened in the final offline-installed ISO.

## Physical NVIDIA workstation — live 2026-10-09

- Official `moai-do update` and Mo Store app updates completed. The owner-
  authorized reboot now runs signed .1011 (`9b77fc3e…`), with signed .1009
  (`608f702a…`) retained for rollback. Boot ID changed to
  `2dc8a81a-c467-4a60-8595-1b381de1aad1`; the post-reboot receipt at
  `~/.local/state/moos-audit/20261009/post-reboot-receipt.json` records the
  exact expected/booted digest and both successful check exits.
- Post-reboot selfcheck: 54 passed; installed acceptance: 55 passed, 0 failed.
  No failed system/user units. Arabic session, 3840×2160@60, scale 250%, UI2
  Arena. Plasma 6.7.5, Qt 6.11.2, kernel 7.2.8, NVIDIA 615.71.09. Boot accounting
  was 33.071 s including firmware/loader; not a repeated cold-boot benchmark.
- Unlike the recorded Oracle state, station `oomctl dump` shows system/user
  pressure-monitored cgroups. Pressure is currently zero; this does not prove
  recovery under imposed memory pressure. Fresh reboot readback had about
  6.3 GiB RAM used/9.2 GiB available and no swap; opening four apps with the
  editor/browser workload later measured 7.9/7.5 GiB and 27 MiB swap. Neither
  sample is an idle baseline. The running default font reads IBM Plex Sans;
  Arabic fallback resolves to Noto Sans Arabic.
- Installed Mira, Store, native Settings and MoPlayer opened; Settings and
  MoPlayer reopened. Settings logged `MOOS_KCM_READY kcm_moos`. A synthetic
  free cloud reply returned HTTP 200 in 10.13 s. This is not owner-spoken
  voice or complete action acceptance. All four installed apps launched again
  after reboot; Settings again logged native readiness, and actual Mira and
  MoPlayer Arabic frames were inspected at 4K/250%. Their review processes
  stayed alive; this does not prove media playback or every app action.
  Remote, gateway, control and Lumen had zero service restarts after reboot.
- Remaining live faults: the initially quiet USB sample was conditional.
  With Mira's local wake listener capturing the muted `Webcam gadget` USB
  source, 18,761 xHCI buffer-overrun warnings occurred in five minutes. Its
  ALSA stream reads 16 kHz mono at USB port `1-6.2`; after stopping only the
  owned Mira review unit, the stream disappeared and a later 15-second sample
  had zero overruns. This isolates capture as the trigger, not the firmware
  root cause or the device's identity as the paired Echo. No NVIDIA Xid was
  present in that five-minute sample. Home Assistant Bluetooth scanning still
  errors with no system D-Bus socket in its container; Tuya duplicate IDs skip
  entities and rootless DHCP discovery lacks packet-capture permission. Its
  first start failed with `protocol`, then restarted successfully once; no
  notification-race fix is inferred. Three Lumen lights remain unavailable.
  Inspection did not flash firmware, rewrite integrations or alter lighting.
- Owner-authorized cleanup removed seven old VM disks, eight retired runtime
  copies, 13 stopped test containers and 147 inactive build containers, plus
  obsolete images, private review homes and crash dumps. Writable headroom
  rose from about 45 to 275 GiB (91% to 40% used). Git checkpoints are preserved
  in local `refs/archive/moos-audit-20261009/` before duplicate bundles were
  removed. Firmware recovery images, databases and source branches remain.
- Product base of the opened checkout and local main match origin/main 8ebe0591. All 49 local
  tips inspected before the documentation branch were ancestors of main;
  all 25 inspected worktrees were clean. The remote ISO trace branch has one
  unmerged diagnostic commit, not an accepted installer fix.
  Archived snapshots are preserved too: the old indexing-section and icon-cap
  corrections already exist in current source. The retired translucent-dialog
  prototype is not integrated or qualified against today's themes; review its
  blur-off fallback instead of restoring its obsolete theme revision/assets.
- Maintained `just check` passed: 239 test scripts with environment skips
  recorded. All Remote .NET builds/executables, controller typecheck/tests
  and production dependency audit passed. MoPlayer: 255 Flutter tests passed.
  Mira's 28 native modules ran 1,098 cases, with seven explicit skips; one
  private-HOME setup error was corrected and the affected module reran green.
  Python AST (419), JSON (92) and shell-file (60) parsing found no errors.
  Component logs and private captures remain outside Git in the station audit
  directory; these do not prove every app interaction or hardware device.

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

## Audit correction batch — edition delivery boundaries

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
The batch is delivered to promoted ARM .728; current installed Oracle
acceptance remains unverified from this station. The discovered tailnet peer
is online, but the existing SSH trust store has no key for its DNS name or IP;
strict verification refused connection. No remote deployment was changed.
X86 build
37881477050 and disk proofs 37888183362/37888186631/37888189800 passed at
8ebe0591; offline ISO 37888192868 failed on an empty `efi` directory. Diagnostic
retry 37900328567 records `install=done` before its later diagnostic file read
times out. The harness incorrectly labels every exec timeout as a 45-minute
installer failure, including its 30-second diagnostic reads; the exact cause
of that read stall remains unproven. X86 promotion and
installed acceptance remain blocked by that actual installer proof. Follow
[RELEASE.md](RELEASE.md); all unchanged identity/signature/initramfs gates remain.

## Evidence still owed

- Next-Plasma acceptance: latest canary 37378905167 (2026-10-05, 1e4a46e8)
  failed the image-build job. No later successful canary is recorded; current
  6.7.5 installed acceptance is not readiness for the next desktop version.
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
