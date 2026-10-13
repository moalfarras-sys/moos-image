# MoOS current state — updated 2026-10-13

Oracle A1 and the physical NVIDIA workstation develop one MoOS product.
Source, promoted artifacts and staged/booted systems are separate evidence.
The only backlog is [DEVELOPMENT_PLAN.md](docs/DEVELOPMENT_PLAN.md).
Native audit: [AUDIT_20261012_AR.md](docs/AUDIT_20261012_AR.md).

## Current engineering batch

PR232's runtime fixes merged at `b11f5aa2`; all repo/x86/ARM PR gates pass.
PR233's padded-SRPM extraction correction merged at `1c321a53`: full native
`just check`, four extraction controls and ARM/x86 image CI pass. Final local
ARM image `f8a036d610a5` passes every image gate and fifteen source payload
hashes; compiled MoPlayer matches the tested .763 bundle. Old extraction fails
three controls. Both early candidate runs were cancelled before promotion.
No new signed delivery is claimed. The owned automatic push builds on
`1c321a53` were cancelled while finishing this combined batch.

The native audit recovered Community's QApplication correction from the one
unmerged NVIDIA merge commit `407c1eed`; the original branch stays preserved.
Actual client bootstrap now opens KDE's native picker; private Arabic/English
cancel controls preserve attachment/draft state with zero API requests. The
old QGuiApplication has zero native picker widgets and fails that control.
34 API and 12 native Qt tests pass; actual NVIDIA Wayland Arabic/English pickers pass.
This is source/native-dialog evidence; installed delivery and full picture
selection/upload acceptance remain separate.

Existing-account free cloud replies and SSE succeed on both stations. Oracle
JSON/SSE first content takes 1.01/1.28 s; NVIDIA 1.47/.91 s, with reported
cost=0. Isolated Hermes replies take 9.24/4.41 s; missing Hermes usage is not
measured zero cost. No secret read, private context submitted, action requested
or provider change. Seven socket-backed relay controls pass and old source
fails all seven. Selfcheck labels connections honestly and preserves the
Oracle monitor. Wider cancellation/stall/voice/clean-account acceptance remains.

PR228 merged at `4ee7f158`, retaining PR226/227 ancestry. Its signed cycle is
complete: x86 build 38311291809, disks 38318191729/38318194809/38318198405,
offline ISO 38318201656, promotion 38322153729; ARM 38311239191. Every run
passed on attempt 1. x86 .1032 and ARM .761 include the following corrections:

- The native KDE menu had zero Settings entries despite 51/55 green checks.
  An exact legacy hidden account launcher outranked the image. Six controls
  and a bounded, owner-checked digest migration restore one real menu entry,
  preserve its private backup and retain unknown customization. The account
  repair is applied; the source selfcheck passes 52/0.
- The three theme maintenance units exclude system accounts. Native owner and
  greeter conditions/old controls pass. Authentication remains upstream.
- Material state is one atomic generation filename, with bounded 100/750 ms
  event readback, opaque ambiguity and no heartbeat. Real publisher/Qt tests
  pass 480 transitions and a broken-reader negative. THEME_REV=103.

PR229 merged at `45ffc8fc`, retaining `9d1717fe` with an identical source tree.
Native installed ARM MoPlayer played a private MPEG4 but labelled it Live.
The correction accepts encoded Arabic file URIs, uses finite controls for
local/explicit movie URLs and leaves HLS/unknown streaming policy intact.
Direct playback produces no unusable catalogue history or resume records.
258 Flutter tests, analysis, native release build and all maintained repo
checks pass. A private Wayland source bundle proves actual moving frames,
20 s MPRIS length/CanSeek and paused +5 s seek; the restored old factory fails.
Final local ARM image `6537d0fba7c9` passes every image gate/9 payload hashes;
its 9,700,232-byte libapp.so SHA-256 is
`65b5a7fe283aae20c42b5985e6aed687f356b94ba9830cb7a77976d916503205`,
exactly matching the native tested bundle. No host bundle was replaced.
The x86 PR workflow now watches its real `moplayer/**` COPY input; the old
workflow fails the input negative control. Final repo/x86/ARM PR CI passes.

The final signed cycle on `45ffc8fc` is complete, all on attempt 1: x86 build
38349913971, disks 38355997007/38356002795/38356005878, offline ISO
38356009395, x86 promotion 38360661403 and full ARM pipeline 38349794036.
All final artifact references, signed origins, distinct QCOW2 boot IDs, zero
failed units and clean shutdown hashes match. Ten ISO-installed apps open,
close and reopen. All four live latest tags resolve to these exact digests.
Receipt: [station-readiness proof](docs/releases/2026-10-13-station-readiness-proof.json).
Oracle now proves the exact installed signed ARM image and local-video journey;
physical NVIDIA and the wider acceptance matrix remain separate.

## Promoted release and public delivery

| Edition | Version | Proven signed digest (sha256) |
| --- | --- | --- |
| Desktop | 44.20261013.1034 | 3504d19d826a74ecc6e4c5d4f40d417139af4e1c90917691aaf5b5a5079fba12 |
| NVIDIA | 44.20261013.1034 | 029961958ae2c243d018cad949da8a0f8d80e85be401fa8ff00b3a9e3a0dbf48 |
| Cloud x86 | 44.20261013.1034 | 28fcaf9e4670cf9a7982a791f56f8f56145dc3afc80487a6f5f8e340d50fa8d2 |
| ARM | 44.20261013.763 | a2ee6a1c5d10b16cae027f98797dd01ca3d5a5dfafd6e78470ab4f287f71d3b4 |

All three x86 QCOW2 proofs cover exact signed origins across boot/reboot and
clean shutdown. The final ISO installs offline and boots its installed target.
NVIDIA KVM proof is not a physical GPU test. ARM proves native first-party
linkage, Mira launch and actual system/native-user oomd monitoring.
CI greeter pixels show MoOS identity; English login buttons remain a locale gap.

The public ISO remains qualified .1026, from final run 38133979283,
5,827,133,440 bytes, SHA-256
`288fcb001aabc990103653cd622d11734a5472cf7942715429eb1934dd3cb57b`.
Full anonymous transfer/hash, local signature, ranges and sidecars pass.
Receipt: [2026-10-11-public-download-proof.json](docs/releases/2026-10-11-public-download-proof.json).
A newer CI ISO is not a newer public download. The existing archive is preserved.
Public .1018/.1022 retirement completed after grace periods; .1022's three
objects reclaimed 5,827,068,083 bytes at October 12 12:05:06 UTC.
Cloudflare Static Assets/R2 remain the public hosts with five scoped Vercel
redirects. Website PR56 merged at `11cb5052`, CI green, no open PR at audit.
Vercel restrictions/other sites remain in [owner handoff](docs/OWNER_EXECUTION_20261009_AR.md).
No provider billing choice or paid plan was changed.

## Oracle A1 development station

Native aarch64, 2 vCPU/11.6 GiB, no GPU; Wayland Arabic UI2 Nova,
virtual 1280×720 at 100%. Kernel 7.2.9, Plasma 6.7.5, Qt 6.11.2.
Booted signed ARM .763 (`a2ee6a1c…`), boot ID
`e569e39e-3dc0-4e8f-85be-32d360dae4d3`; signed .756 is the actual rollback.
Owner-timed native restart applied the official staged update. Native owner
UID 1000 acceptance at October 13 09:58:44 Berlin passes 51 selfchecks/4 notes,
55 post-update checks/0 failures, THEME_REV=103, all 9 payload hashes and the
exact compiled MoPlayer bytes. Notes count Remote connections and owner
mpris/obex masks; TCP counts alone do not prove viewers or capture cost.
No failed system/user units; boot=15.055 s. The private one-attempt graphical
probe retired its own launcher. Existing autologin is not ordinary PAM proof.
Installed /usr/lib/moplayer (no source override) opens encoded Arabic file URI,
plays actual MPEG4 frames, reports 20 s/CanSeek and paused +5 s seek. Rendered
finite controls/timecodes pass; owned unit closed. RSS=578.4 MiB with Remote
active; one small silent sample is not a codec/server/GPU/endurance matrix.
Native graphical acceptance of .756 passed 51 selfchecks/55 post-update checks,
31 Remote hashes, actual oomd monitoring, no failed units; boot=14.064 s.
Seven KCMs load in isolated Arabic homes without QML errors; seven Remote
.NET projects and test executables pass. Current theme/GTK/decorations agree.
Four owner service containers are healthy. Files/photos/DB/SMB/IDE/Remote and
ingress remain intact; pre-login stays explicitly off. Existing autologin is
not ordinary PAM acceptance. Private Remote/public Community TLS pass.
Gateway is live with an owner-selected paid policy; no paid inference or key
read was performed. A prior free synthetic reply on NVIDIA was a separate proof.

Five exact unused audit images retired only after container/ancestry/replacement
checks: total physical free-space gain 26,505,392,128 bytes (~24.7 GiB).
After this build, writable /var has about 41 GiB free/80% used. Composefs /
100% is not writable disk exhaustion. SDK/owner containers/data/rollback stay.
Obsolete completed retirement units are archived. Mo Store updated available
user apps. Core/journal bounds and weekly cleanup are active.
A 30 s editor/services sample has 7.17–7.28 GiB available; KWin uses 5.59%
of one core, plasmashell .14%, idle Remote .04%, Baloo <.001%. This is not
idle/phone/load-pressure qualification. Development toolchains execute in
native SDK containers; host KVM/Flutter and optional buildah remain absent.
Original dirty checkout/index and old APK/PE worktrees are untouched;
`archive/owner-pre-reboot-20261011` preserves the owner snapshot. Isolated
worktrees hold tested changes; the local main ref follows integrated ancestry.

## Physical NVIDIA workstation

Current native boot is signed .1032 (`4bbb7e5b…`) with signed .1029 rollback
(`eeeef743…`), boot ID `227076f6-dd24-4e17-914e-d93e5317b6b1`.
Owner and root Tailscale SSH are authenticated; the browser check is complete.
No SSH host-key field in status is not proof that SSH is disabled. No password
policy/ACL change is needed. Native owner Wayland readback passes 55 selfchecks,
one Settings entry, theme rev 103, GTK Breeze and one desktop portal front door.
Post-update baseline is 54/1: our `plasmashell --version` diagnostic outside a
graphical context aborted, not the real desktop. Its exact PID/core is attributed
and only its own 1.2 MiB core retired; journal evidence/gates remain unchanged.
Real KWin/plasmashell PIDs continue. Fresh-boot acceptance is still required.
Kernel 7.2.9, Plasma 6.7.5, Qt 6.11.2, NVIDIA 615.78.08; RTX 2080 SUPER,
Arabic 3840×2160@60, logical 1536×864 at 250%, UI2 Arena. Writable disk has
179 GiB free/61% used; about 10 GiB RAM available in the recorded baseline.
Thirty-second active-workload cgroup sampling has zero RAM PSI. Large Code's
4.77 GiB includes 3.85 GiB file cache and .86 GiB anonymous memory. KWin and
plasmashell use 9.06/9.65% of one of 16 logical CPUs; this is not an idle proof.
Lumen uses 5.23% of one core while four PC lights animate; screen sync is off.
Whole GPU table reads 1.74–2.05 GiB, 0–12% utilization under owner workload.
The clean native checkout and main worktree are fast-forwarded to integrated
source after ancestry proof; archive preserves the old tip. One unique merge's
Community change is recovered, without deleting its branch or other worktrees.
Cold boot/suspend/hotplug, physical video/GPU endurance and broader hardware
acceptance remain. Earlier .1026's 54/55 native acceptance is historical evidence.

## Integrated features and evidence still owed

Mira mute/disconnect/late-recognition and recovery unreadable-state controls
pass. Community beta has real native/Oracle TLS flow, isolation and bounded
AR/EN renders, but branded DNS/recovery/moderation/retention/endurance remain.
CLDR installer search covers 312 zones with actual AR/EN row controls.
Remote PR225 is promoted in .1029/.756: private guest repeated cold PAM/PIN,
account handoff/logout, decoded frames and managed trust controls pass;
real hardware/private-TLS enrollment/phone/WAN endurance remain P2.17.
Old unmerged APK/PE work has 82 isolated tests; not ten real application journeys.
Oracle's installed Linux engine does not imply Windows/Android engines exist.

Canary 38099434894 passes reviewed Plasma 6.7.91/12 seams; stable 6.8.0/Qt
6.12 are unreviewed and refused. Do not widen pins or layer them on the host.
Hardware boot visuals/suspend/hotplug/multi-monitor/laptop/touch, deliberate
failed-update/rollback, full AR/EN accessibility/contrast/scale/motion, clean
free-provider setup/cancel/quota/failover/owner voice, ten Windows/Android apps,
physical lamps, pressure policy, immutable inputs/SBOM/security delivery cadence,
staged rollout/support/licences/off-host data restore remain in the plan.
One architecture does not prove universal compatibility or complete Arabic UI.
