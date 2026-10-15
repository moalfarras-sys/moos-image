# MoOS current state — updated 2026-10-15

Oracle A1 and the physical NVIDIA workstation develop one MoOS product. Source, promoted artifacts and installed systems are separate evidence; the only backlog is [DEVELOPMENT_PLAN.md](docs/DEVELOPMENT_PLAN.md).
Native audit: [AUDIT_20261012_AR.md](docs/AUDIT_20261012_AR.md). [Oct15 branch integration: source, gates and delivery boundaries](docs/releases/2026-10-15-owner-integration.json).

## Current engineering batch
Mo Store PR243 is merged; follow-up source offers all 13 Craft apps and 200 curated entries, plus supported theme/motion settings. Git bundles preserve original branches. Local image/Craft extraction proofs are separate from pending signed delivery and physical reboot acceptance.

Current payload source is `5745edd1` (PR241): THEME_REV=104, full local ARM
image and exact 20-file readback pass after the preserved ENOSPC failure.
Build 38621311347, disks 38631573998/38631579047/38631585290,
ISO 38631591001, ARM 38621121074 and promotion 38638466690 all succeeded
on attempt 1 at the same source. Independent registry/signature readback matches.
Eight distinct CI boots have exact signed origins and graphical active; the
final ISO installs offline and opens/closes/reopens ten apps. NVIDIA VM proof
does not qualify the physical GPU. [Qualified cycle](docs/releases/2026-10-14-m1-qualified-cycle-proof.json).

The Island correction resolves hidden-tab arrow selection, selection/content
agreement, Return/keypad Enter, held Enter and retired-context blank pages.
Forty-eight native ARM Qt component samples pass: AR/EN, light/dark,
two/five contexts, 100/150/250%, normal/reduced. Completed old-source 250%
controls fail, including 28 arrow mismatches. This is isolated native software
rendering, not installed whole-shell, Orca or Wayland input acceptance.

PR235's greeter desktop facts and exact three-group EIS typing correction are
signed in .1044/.773 and retained in the current candidates. Its signed cycle
also completed: build 38481320383, disks
38488652939/38488984542/38488987448, ISO 38488990935,
ARM 38481265631, promotion 38493025295. One coordinator metadata read failed
with GitHub HTTP 500 after generic dispatch; existing exact runs were adopted,
not rerun or duplicated. The follow-up bounds metadata GET retries, records
created run IDs and refuses dispatch when a build listing cannot be read;
14 executable controls include restored-old failures. No workflow POST retry.
Native NVIDIA booted .1044 with both corrected /usr
helper hashes. The /run override disappeared on reboot. Its exact temporary
copied bundle retired after replacement/no-holder proof. Administrator
opt-in, PIN, private TLS, upstream PAM and default-disabled access are preserved.
Native .1044 post-login receipt passes 55/55 with 18 payload hashes. Exact
unused copied bundle retirement completed. Native .1046 now passes 54
selfchecks/2 notes and 55 post-update checks; all 19 hashes/player match.

Existing-account free cloud JSON/SSE and isolated Hermes replies pass on both
stations in the earlier runtime audit. Direct reported cost=0; absent Hermes
usage is not measured zero cost. Seven real socket-backed response-lifetime
controls fail old source and pass fixed. Provider choice and owner monitoring
are preserved. Community 34 API/12 native Qt controls and native AR/EN Wayland
pickers pass; wider user journeys remain in the single development plan.

## Promoted release and public delivery

| Edition | Version | Proven signed digest (sha256) |
| --- | --- | --- |
| Desktop | 44.20261014.1053 | 7fe46304f3fba63aa37bc7cdf78368f2c2d184142bfd03b79c6a39ca639bc667 |
| NVIDIA | 44.20261014.1053 | 0f43d2f950d88d01ba20a53a7272e588ffeb1dce9d7eb0b6541506278fd705f1 |
| Cloud x86 | 44.20261014.1053 | 5ea45415c6a4b1c0496aca7e9789cdfb8e5d115a9cf7d66310e86b458ec59593 |
| ARM | 44.20261014.778 | 70f6dfe38c185a7b33c7231130f56705c6cf4b591f5126490e916aff67f6f7f3 |

ARM proves native first-party linkage, two healthy boots and clean poweroff.
CI greeter pixels show MoOS identity; English login buttons remain a locale gap.
New final ISO is CI-only; installed NVIDIA .1046/Oracle .775 and public .1046 remain separate evidence.
Public .1046 is independently qualified and published: 5,830,410,240 bytes,
SHA-256 `37053a88ae313f994875794055035d53134206a88eb44fb160b39fef3bb04821`.
Full anonymous HTTP 200, resumed 206 ranges, signature and exact sidecars pass
at Oct14 17:58:53 UTC. [Delivery proof](docs/releases/2026-10-14-public-download-proof.json).
Eight local/eight public native Chromium AR/EN views, exact paired metadata,
three actual redirects and inert installer bytes pass. [Site proof](docs/releases/2026-10-14-public-site-1046-proof.json).
Site version `1bbe00dc-c579-4015-ae82-af7a58c9fc93`; download version
`b322760e-4302-44d1-940d-3eb2f49913d1`. The site deployment printed success,
then its enclosing exec ended 143 before an exit receipt; exact active bytes
and public views independently qualify it. Its termination cause is unproven.
The .1046 marker is published only after that acceptance. Previous .1026 stays
resumable through Oct16 12:00 UTC; no old immutable URL redirects to new bytes.
.1018/.1022 retirement is complete. Current local .1046 and signed rollback stay;
exact .1044 retirement has [its proof](docs/releases/2026-10-14-current-archive-proof.json).
Web/admin checks and 99 tests pass; dashboard's missing declared dependency is
installed only in the private test worktree and its build passes. The broader
Android check returns 127 on Linux's unavailable Windows `gradlew.bat`.
No other product, API, DNS, WAF, authentication or billing setting changed.

## Oracle A1 development station

Native aarch64, 2 vCPU/11.6 GiB, no GPU; Wayland Arabic UI2 Nova,
virtual 1280×720 at 100%. Kernel 7.2.9, Plasma 6.7.5, Qt 6.11.2.
Booted signed .775 (`fb0ba637…`), boot ID
`c5df8872-c80a-4265-8b30-5db89f7aca5f`; signed .763 is the actual rollback.
Native UID 1000 graphical checks pass 51 selfchecks/4 notes and 55 post-update
checks/0 failures. All 19 payload files, exact compiled player and THEME_REV=104
match reviewed source. One KWin/one plasmashell own the KDE Wayland session;
boot=14.301 s. [Native receipt](docs/releases/2026-10-14-oracle-775-native-proof.json).
Initial selfcheck failed on three transient container-prefixed units; its
subsequent post-update check passed. The exact cause is unproven. A second
probe found the first probe's own failed autostart unit. Both failures remain
preserved; only that owned failed flag was retired before the passing readback.
No current failed units; four owner containers are healthy. Existing autologin
is not ordinary PAM proof, and this is not whole-shell keyboard/endurance proof.
The following installed small-video journey belongs to the earlier .763 boot.
Installed /usr/lib/moplayer (no source override) opens encoded Arabic file URI,
plays actual MPEG4 frames, reports 20 s/CanSeek and paused +5 s seek. Rendered
finite controls/timecodes pass; owned unit closed. RSS=578.4 MiB with Remote
active; one small silent sample is not a codec/server/GPU/endurance matrix.
Earlier signed boots also proved native KCM/Remote .NET components and
GTK/decorations agreement within their recorded scope. Private Remote/public
Community TLS pass; pre-login stays explicitly off.
Gateway is live with an owner-selected paid policy; no paid inference or key
read was performed. A prior free synthetic reply on NVIDIA was a separate proof.

Seven exact unused audit images retired only after container/ancestry/replacement
checks: total physical free-space gain 33,544,560,640 bytes (~31.2 GiB).
Earlier exact local .1042/.1044 archive retirement preserves proofs, public
.1026, current .1046 and signed rollback; writable /var measures 23 GiB free after the local build. One exact unused
local greeter audit image was untagged with no parent prune; its shared layers
produced no measured free-space gain. Current image/SDK/owner containers stay. Composefs /
100% is not writable disk exhaustion. One unused Oct8 generated audit ISO
retired after signatures/ancestry/no-holder checks: 5,808,128,179 logical bytes;
concurrent immediate free-space delta=0. [Receipt](docs/releases/2026-10-14-old-audit-iso-retirement.json).
Obsolete completed retirement units are archived. Mo Store updated available
user apps. Core/journal bounds and weekly cleanup are active.
A 30 s editor/services sample has 7.17–7.28 GiB available; KWin uses 5.59%
of one core, plasmashell .14%, idle Remote .04%, Baloo <.001%. This is not
idle/phone/load-pressure qualification. A later native 20 s sample after owned
build/browser fixtures finished has 6.09 GiB available, RAM PSI avg10=0,
KWin/plasmashell 2.40/.21% of one core and gateway .007%/15 MiB. The configured
Remote service name was inactive/unmeasured; this is not its capture-cost proof.
3.93 GiB swap usage alone does not measure swap activity. After the .775 reboot,
a native 20 s sample has 6.04 GiB available, zero swap/RAM PSI avg10,
KWin/plasmashell 4.14/.26% of one core. Gateway direct/SSE replies pass
.90/2.08 s first content with reported cost=0; isolated Hermes passes 8.72 s
with usage absent. Remote capture and input are separate helpers; the input
helper shares the personal service cgroup and must not be counted twice.
These are bounded active-workload samples, not idle/phone/endurance acceptance.
Both stations pass native QML/.NET/C++/Go/Rust/Java/Flutter/MCP component checks
within [the workstation audit](docs/WORKSTATION_20261014_AR.md). Flutter
3.47.4 is now available in user space; host KVM and optional buildah remain absent.
Original dirty checkout/index and old APK/PE worktrees are untouched;
`archive/owner-pre-reboot-20261011` preserves the owner snapshot. Isolated
worktrees hold tested changes; the local main ref follows integrated ancestry.

## Physical NVIDIA workstation

Booted signed .1046 (`0235cad7…`) with signed .1044 rollback,
boot ID `d8a6ce1d-ca57-4680-9e5f-ef8118623b61`. Native ordinary plasmalogin
owns one KDE Wayland session. Graphical-owner checks pass 54 selfchecks/2 notes
and 55 post-update checks/0 failures; all 19 payload hashes, exact player and
THEME_REV=104 agree. No system/user failed units. Boot=32.381 s;
graphical.target=6.892 s userspace. [Native receipt](docs/releases/2026-10-14-nvidia-1046-native-proof.json).
The two notes concern active Remote and retaining its only-display path; they
are not decoded-frame, idle-cost, phone or hardware endurance acceptance.
Earlier .1044 ordinary password-login evidence and exact unused greeter bundle
retirement remain valid within their scope; opt-in/PIN/private TLS/PAM stay.
Prior .1042's 55/55 checks, 16 hashes and following video/resource measurements
remain historical evidence; they do not qualify new .1046 workloads.
Installed Arabic-file-URI MPEG4 passes 20 s/CanSeek, time advance and paused
+5 s seek. RSS=765.9 MiB; full GPU table shows player=593 MiB, absent after Quit.
This is transport/resource evidence, not native moving-pixel/HDR/endurance proof.
New direct/SSE cloud calls pass 1.02/1.11 s first content with reported cost=0;
isolated Hermes passes 4.30 s, usage absent. No provider or private-context change.
Old .1032's 54/1 diagnostic abort remains historical; fresh .1042 passes 55/0.
Kernel 7.2.9, Plasma 6.7.5, Qt 6.11.2, NVIDIA 615.78.08; RTX 2080 SUPER,
Arabic 3840×2160@60, logical 1536×864 at 250%, UI2 Arena. Writable disk has
136 GiB free/71% used at the Store review; earlier RAM figures below are scoped baseline samples.
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

Current M1 source adds one coalesced delayed directory notification for Mira's
confirmed task presence. A real Qt consumer with its first delivery discarded
fails old source and recovers fixed; [62 control tests pass](docs/releases/2026-10-14-mira-job-presence-proof.json). Token end state/age
and a retired session directory remain intact, with no idle poll. This measures
missed-delivery recovery, not the unproven cause of the prior intermittent Qt
startup timeout. Full local ARM image `c49ccd53` and actual 20-file readback
pass; the first final-commit ENOSPC failure is preserved. Signed .1053/.778
are promoted; installed presence acceptance and [active Store work](docs/reviews/STORE_20261014_AR.md) stay separate.

Mira mute/disconnect/late-recognition and recovery unreadable-state controls
pass. Community beta has real native/Oracle TLS flow, isolation and bounded
AR/EN renders, but branded DNS/recovery/moderation/retention/endurance remain.
CLDR installer search covers 312 zones with actual AR/EN row controls.
Remote PR225 is promoted in .1029/.756: private guest repeated cold PAM/PIN,
account handoff/logout, decoded frames and managed trust controls pass;
real hardware/private-TLS enrollment/phone/WAN endurance remain P2.17.
Old unmerged APK/PE work has 82 isolated tests; not ten real application journeys.
Oracle's installed Linux engine does not imply Windows/Android engines exist.

[Latest canary 38248425611](docs/releases/2026-10-14-plasma-canary-readback.json) passes Plasma 6.7.91/12 seams and real greeter; stable 6.8.0/Qt
6.12 are unreviewed and refused. Do not widen pins or layer them on the host.
Hardware boot visuals/suspend/hotplug/multi-monitor/laptop/touch, deliberate
failed-update/rollback, full AR/EN accessibility/contrast/scale/motion, clean
free-provider setup/cancel/quota/failover/owner voice, ten Windows/Android apps,
physical lamps, pressure policy, immutable inputs/SBOM/security delivery cadence,
staged rollout/support/licences/off-host data restore remain in the plan.
One architecture does not prove universal compatibility or complete Arabic UI.
