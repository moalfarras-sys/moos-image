# MoOS current state — updated 2026-10-11

Oracle A1 and the physical NVIDIA workstation develop one MoOS product.
Source, promoted artifacts, staged deployments and actual booted systems are
separate evidence. The only backlog is [DEVELOPMENT_PLAN.md](docs/DEVELOPMENT_PLAN.md).
The owner handoff is [OWNER_EXECUTION_20261009_AR.md](docs/OWNER_EXECUTION_20261009_AR.md).

## Source and promoted delivery

Owner PR222 is merged at `1a73a4e08b33d5a49f0eda42947acaca037d0d9a`,
with candidate ancestry preserved. Final owner source passes 244 maintained
checks plus catalogue and the full local image `926579dbe394` (12 runtime
hashes). THEME_REV/fingerprint is 102. No identity, authentication, signature,
installer mount or rollback guard was weakened.

| Edition | Version | Proven signed digest |
| --- | --- | --- |
| Desktop | 44.20261010.1022 | 8134f32a09ab4ff2301554a7bac16858e7d48d907ec7bd48631b5fd35e97fef1 |
| NVIDIA | 44.20261010.1022 | 4abf5afd9bedc52aba992c81e93b9ae3b7fbed8274643be5e88e75d81eafaa4c |
| Cloud x86 | 44.20261010.1022 | 691a6bd9da96a18fc0acce11fd037ff21b95d9b75207fed6c2913f334cb6ede5 |
| ARM | 44.20261010.749 | 3b6e9edf7a9d852c84fbaef6b6606b49b1e039fb4bf241c3fd0699197fd25ed6 |

All exact proofs passed on attempt 1: signed x86 build 38042999495;
generic/NVIDIA/cloud disks 38051449009, 38051451818, 38051454259;
final offline ISO install/installed boot/shutdown 38051456847;
x86 promotion 38053736733; ARM build/disk/two boots/promotion 38042996902.
Later scheduled ARM run 38055271505 built an image but skipped disk/promotion;
it is not a new release. This documentation branch is not new OS runtime code.

## Physical NVIDIA workstation

Official update and restart booted signed NVIDIA .1022 (`4abf5afd…`),
boot ID `83a69153-a981-42cb-9652-5baf8f025f45`. Native post-login acceptance
at 22:40:06 UTC passed 53 selfchecks, 55 post-update checks, twelve exact
runtime hashes, signed origin/rollback and no failed system/user units. Signed
.1018 (`c5977fc7…`) remains for rollback. The owned autostart proof retired
itself after acceptance; stage-only evidence is no longer the current state.

Installed stack: kernel 7.2.9, Plasma 6.7.5, Qt 6.11.2 and NVIDIA 615.78.08;
Arabic session, 4K/250%, UI2 Arena. Actual RTX 2080 SUPER driver/display readback
passes, Wi-Fi is connected, Bluetooth is powered and two camera device nodes
exist. Those are enumeration/current-state checks, not suspend/hotplug/camera
quality or a universal hardware matrix. Earlier user-unit failures remain in
private evidence; current post-reboot failed lists are empty. Writable /var has
about 212 GiB free. Current RAM is active tooling, not an idle benchmark.

Official Mo Store `update-apps` reports apps up to date. Settings, Store,
Mira and MoPlayer were previously opened/reopened on installed .1018 without
QML errors; actual Settings loader and Arabic Mira/MoPlayer pixels passed.
A free synthetic cloud reply returned HTTP 200 in 10.13 s. This does not
prove spoken voice, every action, media playback or hardware endurance.

## Oracle A1

Oracle rebooted into signed ARM .749 (`3b6e9edf…`), boot ID
`9bc626eb-1aae-404d-a343-1522984b36af`; signed .733 is retained for rollback.
Native graphical-context acceptance at 22:18:34 UTC passed 51 selfchecks,
55 post-update checks, all 12 runtime hashes and no failed units. Initial
autostart evidence retains early transient container-health failures and a
launcher inspection race; the later unchanged checks pass after actual service
convergence. Four containers are healthy and all four private HTTPS routes
return their application/login/ping responses. An SSH shell
omits Plasma's XDG cascade and is not an authoritative desktop-theme probe.
Arabic session/UI2 Nova is distinct from system fallback `C.UTF-8`.

Files, photos, database/cache, SMB, IDE and Remote are existing owner services;
no data directories or ingress routes were removed. The completed R2 upload
scratch was retired after matching its full hash to the qualified public proof,
reclaiming 5,827,068,083 bytes; writable /var now has about 35 GiB free.
The station's systemd-oomd still monitors no cgroup, an explicit P5.7 gap.

Owner-authorized persistent native SSH now uses a dedicated workstation-only
Ed25519 key, verified server host key, password-disabled existing sshd and
`restrict,pty` on the added public key. A managed user service maintains one
strictly authenticated master and reconnects on failure. It uses an owned
`-F` config because namespace mapping made the vendor root-owned SSH include
fail its ownership check; global SSH permissions/checks were not relaxed.
Actual native key login, sudo and master/control socket pass. The workstation
master automatically reconnected across Oracle's real reboot (new PID 139935).
After the workstation reboot its native SSH master is active (PID 2626), and
actual Oracle commands reach the same accepted ARM boot without reauthentication. No private
key is in Git. Oracle's current dirty docs remain unchanged on their original
branch; verified bundle/ref `archive/owner-pre-reboot-20261011` (`b3b886b6…`)
preserves them on both stations without altering the owner's index.

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
Pünktlich's newer deployment remains separately blocked by Git-author access;
its older READY production works. New Vercel deploys remain account-blocked.

MoOS's independent AR/EN frontend is deployed at
https://moos-site.moalfarras-moos.workers.dev/ar/ . HTML/images/fonts/JS
are static Cloudflare assets; only download routing executes its small Worker.
Eight refreshed .1022 public AR/EN width/input/motion views pass without Vercel calls. Five
scoped live Vercel CDN 307 rules preserve existing MoOS entrypoints/queries;
MoPlayer, admin and business APIs retain their existing ownership.

Only the obsolete September Blob ISO (5,884,149,760 bytes) was deleted with
size/ETag preconditions after validating current R2 routing. All five MoPlayer
assets remain, exactly 333,653,409 bytes total. Monthly usage is not reset.
Four Alhasaka photos fail at Supabase origin with `exceed_egress_quota`; one
cached real photo was recovered privately. Account access, quota reset date
and complete data workflows are unqualified. Main website's bounded last-hour
logs contain 27 image-proxy upstream failures (15×502, 12×504); other projects
had no 5xx entries in that query, not proof of all authenticated workflows.
Website source/handoff: Mohammad-alfarras PR55; source CI passes all three
jobs, while Vercel preview checks correctly retain the account-block error.

## ISO and visual evidence

The current public .1022 ISO from final run 38051456847 is preserved on
the workstation and published to R2 (5,827,067,904 bytes):
SHA-256 `0927826e1d28cbbd8c9054ba19b49c9904184c9f0ea304bf60050dfc76d926f3`.
Full local signature/hash checks passed on both stations. Full anonymous public
hash/signature/range verification passed at 22:10:02 UTC; both sidecars match.
The paired frontend is deployed as `fc9c2a50-0ae4-422b-b855-7d63c22fbd36`;
download Worker `49a3c101-15ef-4dc0-91d5-5d9c4807b6c9` carries the .1022
publication marker. All five CDN rules are live; 14 final routing checks pass.
.1011's exact three objects were deleted (5,796,462,771 bytes). .1018 retains
its original bytes until 2026-10-11 15:00 UTC; Oracle's guarded persistent
retirement timer is due at 15:05 UTC. Scheduled deletion is not completed proof.
Public receipt: `docs/releases/2026-10-10-public-download-proof.json`.
Worker source/native tests pass 21 cases, including
immutable-path retirement, grace period, sidecars and >4 GiB resumes.

Earlier actual .1018 source-overlay Arabic GUI journey passed install DONE,
two ordinary password logins across clean shutdown/cold boot (51/0 twice),
and wrong/correct lock-password refusal/unlock. It is distinct from the exact
.1022 signed ISO CI proof. Strict offline manifest mismatch remains 54/1;
all 261 uncompressed layers/runtime config match. No origin rewrite hides it.
Desktop `~/سطح المكتب/صور MoOS` contains 3,724 unique actual image assets,
including 12 unique .1022 CI captures and one actual installed .1022 Arabic
community frame; images only. Native community frame/shutdown returns 0 with
no null-context teardown error. Its deprecation/portal-registration warnings
remain in evidence; this capture mode does not test the image picker or network. Private owner frames stay
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

P6.7 next-Plasma canary remains failed at run 37378905167; Plasma 6.8 is
scheduled 14 October. Qt 6.12 LTS is released but not integrated/qualified.
Do not layer either over the signed image or widen a seam gate to pass it.
Hardware boot visuals, suspend/hotplug/multi-monitor/laptops/touch, deliberately
bad update recovery, full AR/EN accessibility/contrast/scale/motion matrix,
clean-account free-provider setup/cancel/quota/failover and owner-spoken Mira,
ten real Windows/Android app journeys, phone/WAN Remote and physical lamps,
measured pressure policy, immutable inputs/SBOM/staged rollout/support/licences
remain acceptance work. One shared architecture does not imply universal
compatibility, complete Arabic coverage or parity with established global OSes.
