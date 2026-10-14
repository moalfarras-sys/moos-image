# MoOS current state — updated 2026-10-14

Oracle A1 and the physical NVIDIA workstation develop one MoOS product.
Source, promoted artifacts and staged/booted systems are separate evidence.
The only backlog is [DEVELOPMENT_PLAN.md](docs/DEVELOPMENT_PLAN.md).
Native audit: [AUDIT_20261012_AR.md](docs/AUDIT_20261012_AR.md).

## Current engineering batch

PR232/233/234 are integrated at `c5f2451b`. The combined first-attempt cycle
passed signed build 38446133446, three disk proofs
38454884448/38454887386/38454893061, offline ISO 38454900845, x86 promotion
38461170910 and full ARM 38445991140. All four latest tags match the exact
candidate. Final local ARM `0693eb6f4c68` passes every image gate/16 source
hashes; 34 Community API/12 native Qt tests and actual AR/EN Wayland pickers pass.
Padded-SRPM extraction and seven cloud-response lifetime negative controls hold.
Receipt: [native runtime release proof](docs/releases/2026-10-13-native-runtime-release-proof.json).

NVIDIA's real pre-login Remote exposed two further defects: KDE's backend
started without KDE/Wayland desktop facts, and its actual de/us/ara EIS map was
refused by a single-group parser. Greeter-only backend renewal restores both
interfaces; the actual 43,505-byte device map fails old source and yields
178/98/144 entries with the correction. Fresh authenticated hello changes
secureText false→true without audit input; the owner then reports successful
password login and native logind confirms ordinary plasmalogin/Wayland handoff.
Source publishes desktop facts even when Remote stays disabled, checks actual
interfaces on warm enable, retires failed enrollment and accepts exact matching
EIS group counts. Administrator opt-in/PIN/private TLS/PAM remain unchanged.
The live correction is an explicitly documented temporary greeter-only copied
bundle via the existing MO_REMOTE_AGENT override in /run. It is not a signed
release; native owner .1042 acceptance below still checks immutable image bytes.
PR235 is integrated at `bfb158dd`; final local ARM/18 hashes and PR gates pass.
Signed build 38481320383/full ARM 38481265631 are running; main stays fixed.
Deliver the correction through the full release path, then retire the exact
owned override/bundle after signature/source and no-holder checks.

Existing-account free cloud replies and SSE succeed on both stations. Oracle
JSON/SSE first content takes 1.01/1.28 s; NVIDIA 1.47/.91 s, with reported
cost=0. Isolated Hermes replies take 9.24/4.41 s; missing Hermes usage is not
measured zero cost. No secret read, private context submitted, action requested
or provider change. Seven socket-backed relay controls pass and old source
fails all seven. Selfcheck labels connections honestly and preserves the
Oracle monitor. Wider cancellation/stall/voice/clean-account acceptance remains.

Earlier PR228/229 delivered the single native Settings entry, theme maintenance
scoping and atomic material generations (THEME_REV=103), plus finite MoPlayer
controls and encoded Arabic file URIs. 480 native material transitions and old
controls, 258 Flutter tests, native ARM build/frames/seek and signed .1034/.763
acceptance pass in their recorded scope. Current .1042/.771 retain those fixes.

Independent M1 source follow-up repairs Island arrows into hidden tabs, stale
selected content, Return/keypad Enter and a blank page after a context finishes.
THEME_REV=104 is topic source only. Native ARM Qt/Plasma component review passes
48 AR/EN, two/five-context, light/dark, 100/150/250% normal/reduced samples;
completed original-source 250% controls fail, including 28 measured arrow
mismatches. This is isolated offscreen/software evidence, not installed shell,
Orca or signed delivery. Full source gates and integration remain separate.

## Promoted release and public delivery

| Edition | Version | Proven signed digest (sha256) |
| --- | --- | --- |
| Desktop | 44.20261013.1042 | e136bc339543995b15ad9d129453ca31df77a7fa2fe9eaa4fba469f35ae13384 |
| NVIDIA | 44.20261013.1042 | 88953ed40528ddca8ed16f1888b57c6420699f72897909819433f4a455559562 |
| Cloud x86 | 44.20261013.1042 | 8a65514db492da10afba7833b61fea4d7d3329a173b315c6dd902ab23a3a583a |
| ARM | 44.20261013.771 | e4f94b5d735dbf1e3ecad94e60a5d86c37568133eddeac6303906b1dcbcec8c5 |

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
Exact .1042 ISO is preserved: 5,827,985,408 bytes, SHA-256
`57f3d61ad8000595cc3266f1a48309d0ffe885ef7511ca05d61bd53f8aa9a2c0`,
local detached signature/hash verified. Public transfer/site qualification remains.
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

Seven exact unused audit images retired only after container/ancestry/replacement
checks: total physical free-space gain 33,544,560,640 bytes (~31.2 GiB).
With the qualified ISO archive, writable /var has about 38 GiB free. Composefs /
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

Native signed .1042 (`88953ed4…`) is booted, with signed .1032 rollback,
boot ID `4b5cb64e-a7ee-46f9-bcfa-49ed17771926`. Owner/root Tailscale SSH work.
Owner Wayland checks pass 55 selfchecks/55 post-update/0 failures, 16 payload
hashes and compiled player equality with the exact signed NVIDIA candidate.
Theme rev 103, one Settings entry and no failed system/owner units; boot=36.174 s.
One ordinary plasmalogin session/compositor is active. Remote hands off from
restricted greeter to account scope; its temporary correction is described above.
Installed Arabic-file-URI MPEG4 passes 20 s/CanSeek, time advance and paused
+5 s seek. RSS=765.9 MiB; full GPU table shows player=593 MiB, absent after Quit.
This is transport/resource evidence, not native moving-pixel/HDR/endurance proof.
New direct/SSE cloud calls pass 1.02/1.11 s first content with reported cost=0;
isolated Hermes passes 4.30 s, usage absent. No provider or private-context change.
Old .1032's 54/1 diagnostic abort remains historical; fresh .1042 passes 55/0.
New 30 s sample: KWin/plasmashell 1.43/1.31% of one core, 263/483 MiB;
gateway .01%/21 MiB. Baloo's 1.75 GiB is file cache, anonymous=25 MiB;
Lumen 6.08% with owner lights. CPU/RAM PSI avg10=0, sampled swap=0. Not endurance.
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
USB-C UCSI -110 remains at boot; cold boot/suspend/hotplug, video/GPU endurance and broader hardware
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
