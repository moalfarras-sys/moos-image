# MoOS current state — updated 2026-10-12

Oracle A1 and the physical NVIDIA workstation develop one MoOS product.
Source, promoted artifacts, staged/booted systems are separate evidence; backlog: [DEVELOPMENT_PLAN.md](docs/DEVELOPMENT_PLAN.md).

## Current owner development (delivery pending)

Reliability PR224 at `3abe787a` is promoted: x86 38136731168, ARM 38128647066. Local image `90fae1cabecd` and 246 source gates pass; NVIDIA .1026 and ARM .752 are booted/accepted.
Canary 38099434894 passes reviewed 6.7.91/12 seams, native RPM/greeter and
final image gates; stable 6.8.0 stays unreviewed/refused.
Native active-workload 30 s: 6.4–6.7 GiB available, PSI=0, GPU 0–21%/1.62–1.81 GiB VRAM;
Code/browser dominate active work; idle Baloo restart reduced PSS 2.23 GiB→104 MiB,
anonymous 970→13 MiB; all 303,766 indexed files/probe/config preserved. Generated `~/moos-wt/` excluded; durable weak-tier policy unproven.
ARM boot guard/256 MiB pressure controls pass both hosts (22.25/31.42 s,
sentinel survives, kernel OOM=0); both hosts prove native monitoring after signed boot.
Remote PR225 merged at `d44cecfd`; ARM .756 is booted/accepted; x86 .1029 proofs are running.
Private .1022/r10 guest passes repeated cold PAM login, account handoff/logout,
real decoded frames and scoped trust; AR/EN renders/seven .NET projects pass.
Native masked-PIN validation/close clearing and GTK ink correction pass;
managed opt-in/units and real listener/trust revocation pass native VM controls;
disabled cold boot stays off. Full local image `5ce19e082374` passes/31 files match;
Oracle's separate public Community/private Remote and PC certificate-verified HTTPS pass. Greeter enrollment is fixture-only; hardware/phone acceptance remains P2.17. X86 signed build 38169917085 passed; .1029 disk proofs 38178926184/38178929064/38178932277 and ISO 38178935305 are running; main frozen.
PR227 scopes three desktop maintenance units away from system accounts: 247 gates, 17 native theme tests, owner/greeter old/fixed conditions and full image `e0fbe27e2932`/three hashes pass for the first revision. The final batch also restores Community's native KDE picker with QApplication: native filename input/preview/draft/zero API calls, actual source AR/EN Wayland main/shutdown and all 247 source gates pass. Old fallback has Breeze errors; final image/ARM/x86 CI and signed delivery remain. These corrections are not in .756/.1029; privacy/theme/authentication gates remain.

## Source and promoted delivery

Owner PR222 (`1a73a4e0`) preserves candidate ancestry; 244 checks, catalogue,
full image `926579dbe394` and 12 runtime hashes pass. THEME_REV=102.
Identity, authentication, signature, installer mount and rollback guards remain.

| Edition | Version | Proven signed digest |
| --- | --- | --- |
| Desktop | 44.20261011.1026 | a1ac3c6b0eec756f2d20f238abb1896ba8f7e25228cc2e8458952201ffe7524a |
| NVIDIA | 44.20261011.1026 | 782032d1739b775d7f673bc8e91c858e5246a5cd2d631b3944c470a99b98046e |
| Cloud x86 | 44.20261011.1026 | aa2d4fefa1c45d3cb2f6bc08d5c0ad73b7b890cef3f5aad52e86221425b2143a |
| ARM | 44.20261011.756 | 0a02cbd72e25656fea4c3d814f04ceb67b2ec82f2256fcea7368058960d9180b |

Latest exact proofs pass on attempt 1: signed x86 build 38128732396;
generic/NVIDIA/cloud disks 38133971240, 38133974055, 38133976682;
final offline ISO install/installed boot/shutdown 38133979283;
x86 promotion 38136731168; latest ARM build/disk/two boots/promotion 38169587234.
Both ARM boots prove actual system/native-user memory monitoring, failed units=0.
The qualified .1026 ISO is now public; it predates pre-login Remote.

## Physical NVIDIA workstation

Official update and restart booted signed NVIDIA .1026 (`782032d1…`),
boot ID `b8bcee30-0e8c-4ea0-8f66-489fe57510f2`. Native post-login acceptance
at 19:44:24 UTC passed 54 selfchecks, 55 post-update checks, fourteen exact
runtime hashes, actual system/native-user memory monitoring, signed origin and
no failed production units. Signed .1022 (`4abf5afd…`) remains for rollback.
Ordinary PLM login and the self-retiring autostart proof passed; boot=32.989 s.

Installed stack: kernel 7.2.9, Plasma 6.7.5, Qt 6.11.2 and NVIDIA 615.78.08;
Arabic session, 4K/250%, UI2 Arena. Actual RTX 2080 SUPER driver/display readback
passes, Wi-Fi is connected, Bluetooth is powered and two camera device nodes
exist. Those are enumeration/current-state checks, not suspend/hotplug/camera
quality or a universal hardware matrix. Earlier failures remain in private evidence.
ESP offline proof repaired only dirty byte 65; clone/live bytes match, all 16
boot-file hashes and both vfat peers are preserved; 1 GiB owned scratch retired.
The preceding independent-unmount mistake aborted before fsck and was restored;
private old/fixed shared-mount controls pass. Next cold boot is still owed.
Old local .989 ISO/signature/checksum retired after full old hash/ancestry/no-holder checks; 5,786,763,443 logical bytes removed. Native /var delayed readback=177,792,430,080 bytes free; source/VM controls/.1022 rollback preserved.

Official Mo Store `update-apps` reports apps up to date. Settings, Store,
Mira and MoPlayer were previously opened/reopened on installed .1018 without
QML errors; actual Settings loader and Arabic Mira/MoPlayer pixels passed.
A free synthetic cloud reply returned HTTP 200 in 10.13 s. This does not
prove spoken voice, every action, media playback or hardware endurance.

## Oracle A1

Oracle rebooted into signed ARM .756 (`0a02cbd7…`), boot ID
`0ac1f5dc-082e-4948-abcd-ccad1169ce9c`; signed .752 is retained for rollback.
Native graphical-context acceptance at 22:12:40 UTC October 11 passed 51 selfchecks,
55 post-update checks, all 31 Remote runtime hashes and no failed units. Actual system
and native-user oomd monitoring pass; boot=14.064 s, network=connected/full.
At 22:14:39 UTC four containers are healthy and certificate-verified Remote/Community return 200; pre-login remains explicitly off. Existing autologin is not ordinary password acceptance. The .752/.756 CI greeter maintenance timeout is tracked by PR227; native owner reconcile passes.
Kernel retains audit throttling/accountsd/bootupd metadata warnings; bootloader update succeeds/latest. Earlier failures remain recorded.
Existing private account HTTPS passes certificate-verified readback. An SSH shell
omits Plasma's XDG cascade and is not an authoritative desktop-theme probe.
Arabic session/UI2 Nova is distinct from system fallback `C.UTF-8`.

Files, photos, database/cache, SMB, IDE and Remote are existing owner services;
no data directories or ingress routes were removed. The completed R2 upload
scratch was retired after matching its full hash to the qualified public proof,
reclaiming 5,827,068,083 bytes; new .1026 archive is preserved; pre-.756 native /var=33,144,696,832 bytes free. Temporary artifact ZIP retired after successful extraction.
System-wide pressure/frame/audio recovery and weak-device endurance remain P5.7 gaps.

Owner-authorized persistent native SSH now uses a dedicated workstation-only
Ed25519 key, verified server host key, password-disabled existing sshd and
`restrict,pty` on the added public key. A managed user service maintains one
strictly authenticated master and reconnects on failure. It uses an owned
`-F` config because namespace mapping made the vendor root-owned SSH include
fail its ownership check; global SSH permissions/checks were not relaxed.
Actual native key login, sudo and master/control socket pass. The workstation
master automatically reconnected across Oracle's real .756 reboot without reauthentication.
Actual Oracle commands reach the accepted ARM boot. No private
key is in Git. Oracle's current dirty docs remain unchanged on their original
branch; verified bundle/ref `archive/owner-pre-reboot-20261011` (`b3b886b6…`)
preserves them on both stations without altering the owner's index. Pre-.756 checks reuse the matching tree ref; six current dirty files and the original branch remain intact, with no duplicate snapshot.

## Public website incident and isolation

Authenticated Vercel Hobby billing is active, but team metadata reports
`FAIR_USE_LIMITS_EXCEEDED`, specifically `fluidCpuDuration`, at
2026-10-10 01:50 Berlin. Dashboard totals: CPU 11h40/4h, ISR writes
839K/200K, Blob 6.22GB/1GB, origin transfer 12.12GB/10GB. Paid observability
would be required for project CPU attribution; none was enabled.

Documented project unpause restored all 14 primary sites. Latest anonymous
readback (21:47 UTC): 24/25 addresses return actual application pages;
the old A&D vercel.app alias remains disabled while its custom domain works.
28 isolated browser views rendered all 14 sites on phone/desktop, with no JS
errors or visibly broken images. This did not submit business forms/accounts.
New Vercel deploys remain account-blocked.

MoOS's independent AR/EN frontend is deployed at
https://moos-site.moalfarras-moos.workers.dev/ar/ . HTML/images/fonts/JS
are static Cloudflare assets; only download routing executes its small Worker.
Eight .1026 public AR/EN width/input/motion views pass without Vercel calls. Five
scoped live Vercel CDN 307 rules preserve existing MoOS entrypoints/queries;
MoPlayer, admin and business APIs retain their existing ownership.

Only the obsolete September Blob ISO (5,884,149,760 bytes) was deleted with
size/ETag preconditions after validating current R2 routing. All five MoPlayer
assets remain, exactly 333,653,409 bytes total. Monthly usage is not reset.
Website source/handoff: Mohammad-alfarras PR56 merged at `11cb5052`; source CI passes all three
jobs, while Vercel preview checks correctly retain the account-block error.

## ISO and visual evidence

The current public .1026 ISO from final run 38133979283 is preserved on
Oracle and published to R2 (5,827,133,440 bytes):
SHA-256 `288fcb001aabc990103653cd622d11734a5472cf7942715429eb1934dd3cb57b`.
Local signature/hash and full anonymous public verification passed at
21:24:17 UTC; resumed ranges and both exact sidecars match.
Frontend `7fc92c0a-3f66-4114-8a74-dda39cf1681f` passes eight local/eight public
views; download Worker `72141578-1b4c-4a48-8e2c-e3e70295bb05` carries .1026.
Five existing CDN rules remain; fourteen fresh .1026 routing/metadata/script/range checks pass at 21:56:52 UTC. Six owned website test caches retired after CI/public acceptance: 1,263,339,069 logical bytes; original dependencies/source/lockfiles remain. Concurrent image writes and CoW preclude claiming equal physical free-space gain.
.1011's exact three objects were deleted (5,796,462,771 bytes). .1018's original
bytes survived the full grace period; guarded retirement at 15:05:09 UTC
deleted only its three public objects (5,808,128,179 bytes). .1022 retains original bytes through Oct12 12:00 UTC; persistent guarded retirement at 12:05 passes five read-only negatives, not yet executed.
Public receipt: `docs/releases/2026-10-11-public-download-proof.json`.
Worker source/native tests pass 21 cases, including
immutable-path retirement, grace period, sidecars and >4 GiB resumes.

Earlier actual .1018 source-overlay Arabic GUI journey passed install DONE,
two ordinary password logins across clean shutdown/cold boot (51/0 twice),
and wrong/correct lock-password refusal/unlock. It is distinct from the exact
.1022 signed ISO CI proof. Strict offline manifest mismatch remains 54/1;
all 261 uncompressed layers/runtime config match. No origin rewrite hides it.
Desktop `~/سطح المكتب/صور MoOS` contains 3,744 image assets, images only,
including 12 new qualified .1026 CI captures and an actual installed .1022 Arabic
community frame; images only. Native community frame/shutdown returns 0 with
no null-context teardown error. Its deprecation/portal-registration warnings
remain in evidence; capture alone does not test picker/network. A separate private native bootstrap control proves KDE selection/preview/draft with no API calls; final source delivery remains. Private owner frames stay
local. CI English/small-screen fixtures are not owner Arabic hardware evidence.

## Integrated owner features and remaining boundaries

- Mira capture pauses on mute, missing/unknown source, discards late recognition
  and loads wake recognition lazily. Eleven boundary, seven wake and 45 controller
  tests pass. Eight real/private-helper stages include muted physical USB with
  zero capture/overruns and three private unmute/mute cycles. Physical unmuted
  USB speech/long capture remains open; owner mic preference is unchanged.
- Recovery distinguishes unreadable state from no rollback; read-only retry and
  native AR/EN GTK proof pass. Actual failed-update/rollback/forward is still owed.
- Community beta passes 34 API/11 native tests, real Wayland/Oracle TLS image
  flow, title-fetch guard, account isolation and narrow AR/EN/light/dark frames.
  Root-managed unprivileged API preserves host UID namespace and forged headers
  fail 403. Current public TLS service uses the existing Tailscale Funnel on
  HTTPS port 10000; it is distinct from the four private owner routes. After
  Oracle reboot the dedicated unprivileged UID 968 service is active in the
  host UID namespace; `/v1/health` returns ready with registration open. Basic
  hide/ban/delete API routes exist. Branded DNS, recovery, full moderation UI/
  retention, notification preferences and endurance remain beta work. Native
  shutdown and ARM tmpfiles old/fixed controls pass.
- Arabic installer search uses CLDR for all 312 zones, actual AR/EN Qt row clicks
  and mismatch refusal; old raw-ID search fails its negative control. Wider
  keyboard/screen-reader/scale tests and global greeter locale remain open.
- All committed refs were audited before retirement; unique work is archived.
  Fourteen uncommitted Oracle files are protected by two Git tree refs plus a
  verified cross-station snapshot. Three isolated suites pass 82 engine tests;
  those APK/PE changes are not merged or installed from that evidence alone.

## Evidence still owed

P6.7 reviewed next-Plasma canary 38099434894 passes 6.7.91/12 seams;
stable 6.8.0 and Qt 6.12 are not integrated/qualified for signed delivery.
Upstream kernel.org lists stable 7.2.10 (October 11); installed/vendor-qualified 7.2.9 is not "latest everywhere". A signed base/driver transition is still required, never a host kernel layer.
Do not layer either over the signed image or widen a seam gate to pass it.
Hardware boot visuals, suspend/hotplug/multi-monitor/laptops/touch, deliberately
bad update recovery, full AR/EN accessibility/contrast/scale/motion matrix,
clean-account free-provider setup/cancel/quota/failover and owner-spoken Mira,
ten real Windows/Android app journeys, phone/WAN Remote and physical lamps,
measured pressure policy, immutable inputs/SBOM/staged rollout/support/licences
remain acceptance work. One shared architecture does not imply universal
compatibility, complete Arabic coverage or parity with established global OSes.
