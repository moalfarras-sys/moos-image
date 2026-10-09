# MoOS current state — measured 2026-10-09

Oracle A1 and the physical NVIDIA workstation develop the same MoOS product.
Evidence below names its device: Oracle measurements are not NVIDIA readback,
and registry promotion is not proof that either machine has rebooted into it.
The full audit and acceptance gaps are in [the Arabic audit](docs/AUDIT_20261008_AR.md).
The sole execution backlog is [DEVELOPMENT_PLAN.md](docs/DEVELOPMENT_PLAN.md).

## Installed Oracle system — last recorded readback 2026-10-07

- Signed MoOS ARM 44.20261006.724, source fa85b2daf3db0f1f823b3159bb46b25571a99740.
  Digest: sha256:f9441728f373cf19d59bdc4116c42833392a628e3ac01f33905cd76fce3c7305.
- Signed ARM 44.20261009.728 (source 8ebe0591, digest
  sha256:abc5aff9496d57917d94254c67da5af4caa94c412067d62a72a537a8e907f673)
  is staged through moai-do update, not yet booted. Signed .710 rollback remains. The owner-authorized reboot was verified on
  2026-10-07; this audit has not replaced the installed origin with a local image.
- Recorded installed selfcheck: 51 passed, 2 notes, no broken checks. Notes are
  owner-masked mpris-proxy and obex, not missing MoOS code.
- No failed system/user units. Four rootless photos/database/cache/SMB
  containers are healthy. About 52 GiB writable storage remains during artifact qualification;
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
- Photos/SMB/browser IDE have post-reboot acceptance. Phone background photo
  upload, off-host originals backup and long phone/WAN endurance remain unproven.
  Details: [Oracle profile](docs/ORACLE_CLOUD_WORKSTATION.md).

## Promoted releases and public delivery

The x86 editions are promoted from candidate 144b1a6a by run 37946594645.
All five exact-artifact proofs succeeded on attempt 1; main 46b46e87 preserves
candidate ancestry and its identical tree. ARM .728 remains source 8ebe0591.
Image-only scheduled builds and later owner source do not imply delivery.

| Edition | Version | Signed digest |
| --- | --- | --- |
| Desktop | 44.20261009.1018 | 3055eb28ac032492a053da1efb9493c9780e7bfa20a01c7c3300961693bfee92 |
| NVIDIA | 44.20261009.1018 | c5977fc7d68bc6cd708b85931711f3ff8eb44be5a4468edc7e9c490b9dfc0dd0 |
| Cloud x86 | 44.20261009.1018 | 0160fddaab3deb4a8f3eef1d87d5343b3f0a1472e6f3f26f1bba4882dfccb977 |
| ARM | 44.20261009.728 | abc5aff9496d57917d94254c67da5af4caa94c412067d62a72a537a8e907f673 |

First-attempt stable proofs: signed build 37552824167; generic/NVIDIA/cloud disks
37558743993, 37558747906, 37558751431; offline ISO 37558755639; x86 promotion
37562359722; ARM build/two UEFI boots/promotion 37539003204.
Ten actual apps opened, closed and reopened in the final offline-installed ISO.

## Physical NVIDIA workstation — live 2026-10-09

- Official update/reboot now runs signed .1018 (`c5977fc7…`), with signed .1011
  (`9b77fc3e…`) retained for rollback. Boot ID changed to
  `51a8ca7f-9feb-427b-837b-0e5c033d7077`; the private
  `~/.local/state/moos-audit/20261009/post-proven-1018-receipt.json` records
  exact expected/booted digest, signed origin/rollback and both successful checks.
- Post-reboot selfcheck: 54 passed; installed acceptance: 55 passed, 0 failed.
  No failed system/user units. Arabic session, 3840×2160@60, scale 250%, UI2
  Arena. Plasma 6.7.5, Qt 6.11.2, kernel 7.2.9, NVIDIA 615.78.08. Boot accounting
  was 34.886 s including firmware/loader; not a repeated cold-boot benchmark.
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
  stayed alive; this does not prove media playback or every app action. On .1018,
  all four apps opened without QML errors; native Settings readiness and Arabic
  Mira/MoPlayer pixels passed. Remote/gateway/control/Lumen have zero restarts.
- Remaining live faults: the initially quiet USB sample was conditional.
  With Mira's local wake listener capturing the muted `Webcam gadget` USB
  source, 18,761 xHCI buffer-overrun warnings occurred in five minutes. Its
  ALSA stream reads 16 kHz mono at USB port `1-6.2`; after stopping only the
  owned Mira review unit, the stream disappeared and a later 15-second sample
  had zero overruns. .1018 still produced 5,744 in a three-minute Mira sample;
  only its owned review unit was stopped. This isolates capture, not the firmware
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
- Initial product audit matched main 8ebe0591: all 49 inspected local tips were
  ancestors and all 25 worktrees clean. Main is now 46b46e87, preserving the
  accepted installer repair; PR222 contains the later owner batch. Earlier
  diagnostic-only trace history remains preserved, not counted as a repair.
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

Privacy redaction/private output, Remote's SkiaSharp replacement and fail-closed
dependency audits, language locking/startup, ARM disk-consent/install metadata
and pinned cosign 3.1.3 passed their recorded native/source checks. Detailed
negative controls and rights inventory are in the linked Arabic audit and
[OWNERSHIP.md](OWNERSHIP.md); no universal compatibility/security claim follows.
The batch is delivered to ARM .728. Oracle SSH is now verified through one Tailscale session; `.724` remains booted,
`.728` staged. New installed acceptance remains unverified; no remote origin changed.

X86 build 37881477050 and three disk proofs passed at 8ebe0591; ISO 37888192868
failed on an empty `efi`. Retry 37900328567 installed before diagnostics timed
out. The independent installer repair at 144b1a6a now holds mount namespaces,
private privileged state and bounded diagnostics; candidate build 37910223752
passed; ISO 37916929153, disks 37916917245/37916921267/37916925157 and ARM
37916934408 all succeeded. PR221 merged at 46b46e87 with the exact candidate
tree; x86 promotion 37946594645 succeeded. NVIDIA .1018 (`c5977fc7…`) is published;
official reboot/readback passed 54/0 and 55/0, with signed .1011 rollback. Its installer proof excludes this later owner batch.

## Owner milestone — source work, not promoted delivery

[Execution/handoff](docs/OWNER_EXECUTION_20261009_AR.md) records five ordered
milestones, private support conversations/optional public suggestions, and the
image gallery. The active slice is reliability. Source microphone policy now
pauses on mute/missing/unknown source, invalidates pending recognition and lazily
loads the wake model. Eleven dependency-free regressions, seven wake tests and
45 native controller cases pass. Live source-helper proof passed eight stages:
already-muted real USB without capture/overruns, three virtual-source unmute/mute
cycles and removal, with helper/socket/module cleanup and unchanged defaults.
This does not fix unmuted USB firmware or prove physical speech. Full maintained
`just check` passed all 240 gates; this source is not installed or signed/promoted yet.
Recovery's unreadable state now differs from a proven absent rollback, with a
read-only retry. Its regression gate and actual native AR/EN GTK source review
pass; no rollback mechanism or boot choice changed. The gallery holds 31 unique
real frames with explicit source/CI/private-host boundaries and missing stages.
Participation beta: 34 API/privacy/retry/proxy/release, 10 native Qt HTTP/launcher cases
pass. Oracle API runs under a dedicated unprivileged account; public TLS, six
API cases and physical Wayland Arabic/image flow passed. Synthetic data removed.
Four packaging cases, all 243 repo gates and the full generic image pass at 2cb1e863;
five shipped runtime hashes match. Old/fixed QML teardown controls fail/pass.
Image 9a2d355605ff has kernel 7.2.9; signed owner-batch delivery remains open.

## Installer mechanism preserved in the integrated batch

The repair retains private mount namespaces, checked target/subvolume/ESP
readback, mandatory lock before state reset, private 0700/0600 diagnostics and
bounded QGA reads. The old detacher is unidentified; native negative controls
prove the failure class, while the final offline ISO now proves install/reboot.
The detailed incident remains in AGENTS.md and the dated Arabic audit.

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

Past incidents remain in Git; rules belong in AGENTS.md and component docs.
