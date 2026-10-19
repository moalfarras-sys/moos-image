# MoOS current state — updated 2026-10-20
Oracle A1 and the physical NVIDIA workstation develop one MoOS product. Source, promoted artifacts and installed systems are separate evidence; the only backlog is [DEVELOPMENT_PLAN.md](docs/DEVELOPMENT_PLAN.md).
Native audit: [AUDIT_20261012_AR.md](docs/AUDIT_20261012_AR.md). [Oct15 live delivery readback](docs/releases/2026-10-15-unified-delivery-readback.json). [Oct15 branch integration](docs/releases/2026-10-15-owner-integration.json). [Historical Store defects and their integrated corrections](docs/reviews/STORE_20261015_AR.md).

## Current engineering batch

Native V3 actually boots signed1078/c0aa with1072 pinned rollback. Current Plasma-context selfcheck54/54; the model-only keyboard override inherits LayoutList correctly. Topic diagnostic56/0 preserves owner config and rejects real conflicts, with a native old-source negative. Goodix direct verification and1828 touch events/max3 contacts pass. Owner accepts both camera previews, stereo speakers and recorded speech at retained microphone30%; a warmed six-second sample has0% clipping and−11.50dBFS peak. BIOS80% cap is owner-confirmed, plateau unobserved; battery42cycles/~91.5% gauge health and AC charging. External4K60/hotplug both ways were accepted before this boot; current external/suspend/pen remain open. [Native phase1 proof](docs/releases/2026-10-19-v3-1078-native-phase1-proof.json).
The active topic corrects greeter-only PAM order and adds an exact vendor-source native frontend startup patch. Password-only and arrow-started fingerprint-only each passed earlier physical attempts. Automatic startup's first one-boot profile did start PAM, then timed out; owner saw no automatic reader and reported the reader again after password. Actual audit attributes the eventual return to fingerprint. A QQuickView screen-lookup TypeError prevented the intended reveal; the attached Screen correction now passes an actual native QQuickView old/fixed probe. Corrected no-arrow login now passes: owner confirmation, empty-response request, actual verify-match and audit pam_fprintd. A separate no-touch timeout then password-only passes with a logged password request and audit pam_unix, no second reader. Cold login and signed feature delivery remain unqualified. Global PAM and installed1078 RPM bytes stay unchanged; the /run frontend review expires on reboot. [Correction contract](build_files/plasma_login/README.md).
Native greeter6.8.0/Qt6.11.2 also has a separate screenRemoved SIGSEGV. Exact Qt debuginfo identifies a corrupt listener list during QQuickItemView destruction; root cause is not repaired. SMOCF05 remains unbound, IIO0 is light-only, and rotation is unavailable. Historical DrKonqi failures remain visible; a green selfcheck does not erase them. Camera/audio private media and the protected core stay local. [Measured hardware and remaining acceptance](docs/hardware/V3_20261019_AR.md).
PR255 finalf1fd1cf9 passed native2682-case checks, local image44eb43c1 and final-head PR gates, merging as18ba1a83. Its signed x86 build39265167668, disks39274409976/39274417585/39274424589, offline ISO39274432535, ARM39265084041 and x86 promotion39283856876 all pass; independent latest/cosign readback gives x861078/ARM816. Four WD19 firmware updates persist after replug. These qualify that delivered source, not the new authentication topic. [Qualified1078 cycle](docs/releases/2026-10-19-v3-qualified-1078-cycle-proof.json).
The separate V3 development profile installs official native Code/OpenCode/Claude/Antigravity/Hermes and executes SDK/Flutter/QML/MCP/editor checks. Wallet/provider signins are owner-deferred; original disabled wallet state is restored. Official watcher2.6.0 passes the reproduced2.5.1 live-subscription exit control,3private native cycles/60events and installed-addon close0. Scoped bundle backport retains its verified original backup; authenticated/editor/endurance acceptance remains open. Conmon cleanup crash, Node22 syntax failure and missing-helper/relative-file fixture refusals remain recorded. [Developer profile](docs/workstations/V3_NATIVE_DEVELOPMENT_20261019_AR.md).

PR248–251 are integrated at `727e7b6cf6df2ba2c47ca4a5264e911c48e81d48`, tree `22086a7e312991b77f61bfa794efbfca0ceba00d`. Native full2668-case check, complete local image87e84381,28 overlay payloads/seven compiled modules, and first-attempt PR image/repository gates pass. The one frozen signed cycle succeeds: build39120488031, disks39126559377/39126562830/39126565706, ISO39126568330 (ordinary offline install/login, all10 app close/reopen journeys, second boot), full ARM39120345470 and actual x86 promotion39129933686. Independent native public-key verification matches all4 production digests/source labels. [Qualified cycle](docs/releases/2026-10-18-qualified-1072-cycle-proof.json). Earlier Cloud composition and .1069 ISO close failures remain preserved; no gate/deadline/signature/rollback policy was weakened.

Oct17 owner completion is merged through PR249/248 at `8add4ac2`, tree `84f74523`, identical to qualified topic `c3608bd2`. It combines PR248, the preserved native-inventory/Store-experience branch and local compatibility work. The initial242-ref/62-worktree inventory, five dirty-tree archives and reverified609244906-byte Git bundle preserve originals; all244 refs audited immediately before merge are ancestors. Source retains264 reviewed recipes (150 repository Linux,46 Android), native application ownership/inventory, one product with explicit variants, deferred card creation and both exact-target/raw-geometry Remote corrections. The native launch path uses the canonical detached launcher. Android waits for the actual application service without losing the later APK parser/property/receipt guards. Catalogue availability reuses Store policy and explicitly leaves application testing unassessed; eleven original-generator negatives fail. Six unqualified local recipes stay in Git history. Actual catalogue/index reconciliation also found Finamp and Shattered Pixel Dungeon sharing Linux/Android IDs: prefer their confirmed native Linux builds on x86/ARM, preserve existing Android receipts as namespaced unlisted apps, and require the backend action to stay on the selected platform.

Native NVIDIA now boots signed1072/0c76f1ec with signed1062/708223c7 rollback; new boot35500d14 replaces7b01c656. All35 payloads match, signatures pass,54 selfchecks and55/0 postchecks pass, zero failed units and zero display-start aborts. Android session now resolves to immutable/usr; kernel7.2.11/NVIDIA615.78.08/GPU pass. Natural cold create/atomic-save/delete passes1.072/1.091/.024s, so only the preserved old invalid derived index retires. Notepad4 removal now passes via installed Store with prefix/other receipts retained. Total old file payload retirement44,583,870,472bytes; old-image net gain is separate. [Native proof](docs/releases/2026-10-18-nvidia-1072-native-proof.json). Broader crash audit retains two real handoff failures: greeter QtQuick ListView teardown on screenRemoved; owner Remote localhost8765 bind before greeter stops, one managed retry then active. These are not zero-crash acceptance; exact Qt root cause and bounded port handoff repair remain open. Original five dirty trees/242 refs remain preserved; independent draftPR253 stays outside this release.

Owner-authorized cleanup retires44,583,870,472 logical bytes including the old derived index after cold acceptance of proven old inspection downloads/extracted files/pip cache, one exact duplicate installer, an unused old private VM disk and superseded local1022 ISO. Signed1062 ISO, original installer, owner sources/data/dirty worktrees/Git bundle/SDKs/databases/17 containers/rollback remain. One superseded generic image plus2 exclusive parents is removed without force/global prune (observed net3,677,118,464 writable bytes). Bazaar, GNOME Chess and temporary Notepad4 are removed through Store with data/prefixes preserved; old1062 ID refusal remains historical. Available apps update successfully; Code1.139.1 equals Flathub while Microsoft stable1.142.0 exposes channel lag. About83.5GiB writable free after new boot and cleanup; no universal latest-version claim. Earlier ENOSPC incident and app crashes remain in the owner audit; new guarded local image passes with71.5GB disk/8.45GB memory minimum headroom.

Oct17 Android setup follow-up fixes a source-verified first-use defect: desktop-window properties were written before the platform started, and the upstream command could log refusal with exit0. Confirmed setup now waits for actual Android boot, applies/reads the two properties, restarts once only if changed and verifies the new session; it no longer opens a separate phone desktop. Existing configured sessions need no writes/restart; the existing-session notice precedes consent. Nine native isolated setup controls, five runtime controls and four OTA-channel controls pass; two restored-old controls fail. Real APK/windows/GPU acceptance remains separate. [Source evidence](docs/releases/2026-10-17-android-desktop-setup-source-proof.json).

Oct17 qualification: after preserved fixture-input/reserve failures, exact `7c37862e` passes native full check (764.570s), the complete ARM image (1035.036s, immutable ID `3d66eafa`) and all19 changed payload hashes; PR x86/ARM/Plasma-next/repository/Remote checks succeed. This qualifies that checkpoint, not the later lifetime fix. Exact cache/old-artifact retirement preserves current images, SDKs, containers and signed rollback; Oracle now has26.6GiB free, NVIDIA42.2GiB. Backup saves snapshot39ea83ab. OCI instance-principal authentication and tenancy read succeed; compute detail access is denied and billing is unverified. No new signed image was promoted or installed. [Earlier failures](docs/releases/2026-10-17-store-qualification-followup.json). [New checkpoint/native evidence](docs/releases/2026-10-17-managed-app-native-proof.json).

Native NVIDIA exposed a Store lifetime defect: Notepad4 closed when its short caller exited. The shared canonical launcher now gives each app cgroup lifetime and graphical-session stop ownership, refusing manager failures. Seven portable controls pass; actual private native old-Popen/no-cgroup negatives die, fixed child survives then stops with only its private target. Exact staged source opens real Notepad4 in a separate unit and its actual MoOS-framed pixels are reviewed. This is source/runtime evidence, not signed installed payload. The qualified727e7b6c four-edition cycle now delivers this fix; new physical boot acceptance remains separate.

Oct16 Store source batch adds64 real app recipes (23 Linux/27 Android/14 Windows):264 curated entries, with all200 baseline app objects and27 existing webapps preserved. Platform browsing, touch/wheel and management actions have native Qt positive/old-source negative controls. Actual Basic-style QML hosts now use KDE motion policy; THEME_REV107 invalidates changed QML. [Measured source evidence](docs/releases/2026-10-16-store-native-source-proof.json).
Oracle real Curtail install/function/permissions/update/keep-data/remove-data/reinstall and forced-Wayland launch pass. First launch crashed in sandbox Mesa Vulkan; ARM's GL policy works on the same artifact, with a temporary owner-manager setting until delivery. Android updates confirm kept APK bytes before publishing a receipt. Native NVIDIA is reachable through existing authorized root/owner SSH: Markor installs with exact publisher bytes/version and gets a real KWin window after cold Android recovery. Initial WCG/display abort and a later launch failure remain preserved; renderer choice was measured irrelevant and restored. Owned document-intent/permission controls restore their baseline; editing/saving pixels and durable startup/endurance remain unproven. Fourteen added Windows apps have private Wine renders; five rejected candidates stay excluded. Mira's delayed-delivery old negative and64 bounded-burst controls pass with no idle poll. Coherent signed727e7b6c delivery now passes; installed-image and wider application acceptance remain separate.

Urgent Oct16 source correction: the physical greeter's v6 PipeWire serial was passed as a node ID; decoded output was a real camera image. The corrected exact target disables default-video fallback. That historical audit used a scoped copied bundle; its log reported NVENC from the 3840×2160 desktop. Native1072 now carries the reviewed helper in/usr and the run override is gone. Ordinary owner login and the existing signed .1062 acceptance pass63 hashes/54 selfchecks (2 notes)/55 post-update checks, with no failed system/owner units at acceptance. The owner subsequently confirmed the real desktop picture; signed727e7b6c delivery now passes; installed payload readback and phone endurance remain separate. The Qt screen-removal crash has bounded recovery, not a claimed upstream/hardware cure. [Source/runtime evidence](docs/releases/2026-10-16-remote-screen-target-source-proof.json).
Repository security now enables vulnerability alerts, automated security fixes and private reporting; existing secret scanning/push protection and strict main checks remain. Source pins64 top-level action uses/18 nonpersisting checkouts and restricts credential-bearing AI jobs to the owner; transitive action pinning and public-source copying are separate boundaries. [Readback](docs/releases/2026-10-16-repository-security-readback.json).
PR243–246 at `e1ffacfa` integrate the 200-app Store, all 13 Craft apps, reviewed engine/data/index/UI fixes and the actual pre-authentication ISO capture. All 231 audited refs and 57 original station worktree heads are ancestors; 82 remote heads were published without force. Five station/four Oracle dirty trees and 24 cross-verified dirty files remain preserved with a verified full Git bundle; originals are untouched.
Stable x86 Plasma 6.8.0, 12 reviewed seams, greeter/logout old/fixed controls and THEME_REV=106 pass. Native ARM `just check` and the complete local image pass; 63 immutable payload files and 200 curated apps match. First-attempt build 38816837919, disks 38824574093/38824577430/38824580671, ISO 38824584100, ARM 38824591685 and x86 promotion 38829865381 all succeed at this exact source. Independently verified production is x86 `.1062` / ARM `.792`. [Qualified receipt](docs/releases/2026-10-16-store-qualified-cycle-proof.json).
The previous `.1060` ISO failed on a post-authentication handoff mislabeled pre-login; the failed verdict and old-source negatives remain preserved. The corrected cycle passes the unchanged visual threshold and ordinary offline install/login/ten-app/second-boot proofs. These are CI artifact proofs; physical NVIDIA acceptance remains separate. ARM retains qualified native Plasma 6.7.5.

Previous full batch `5745edd1` (PR241), THEME_REV=104, passed the native local image/20-file readback, signed four-edition cycle and unchanged gates after a preserved ENOSPC failure. Its eight CI boots and offline installed ISO/ten-app journey remain historical evidence, with physical GPU qualification separate. [Qualified cycle](docs/releases/2026-10-14-m1-qualified-cycle-proof.json).

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
| Desktop | 44.20261018.1072 | 05232afbdb5df5be2f71d9e8cb62f7ea73f54f5970b6eb90a251366ef58b60a3 |
| NVIDIA | 44.20261018.1072 | 0c76f1eccb43a20c9b1fe5c23f615f7b6621d9c25c6f630a3d334be4857b9111 |
| Cloud x86 | 44.20261018.1072 | d103f05edb66d4b77e4d317630b1c0e8a993072399981ca764f92c15ffa1feed |
| ARM | 44.20261018.807 | 870b59875b0f401348dab7a9c457cb6632529083cfd6bc5ab9069a588a9994ce |

All four production digests independently match signed727e7b6c candidates and completed first-attempt boot/promotion proofs. Final ISO SHA256 is `9ed8da699b704e0450d88cb8487f0fed1f6c8e7696e3b032efc2e28633dc9eca`; CI retention is not public download qualification. The complete older signed1062 ISO remains privately retained (6,020,923,392 bytes, SHA256 `62a16ebb1d3f8dc4107c44fdc588b5c2dccd906b42a86b1aa5ee559deb4255db`). NVIDIA now boots exact1072 with1062 rollback; Oracle792 acceptance below is historical, not proof of807 installed.
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

Native aarch64, 2 vCPU/11.6 GiB, no GPU; Wayland Arabic UI2 Nova, virtual 1280×800 at 100%. Kernel 7.2.10, Plasma 6.7.5, Qt 6.11.2.
Booted signed `.792` (`05d9bbac…`), boot ID `17e46ccf-f6d3-4416-b2c5-550be96077ca`, changed from `.791`'s `ab975b93-f72b-47ce-a327-b84f3f68a371`; signed `.791` is the actual rollback. The full coordinated cycle completed before the official native update/restart. Its postboot unit encountered an ordering cycle; the owned unit ordering is repaired and originals/logs retained. Actual native graphical acceptance now passes: 63/63 payload hashes, 51 selfchecks/4 notes, 55 post-update checks/0 failures, no failed units, user-app updates and a real Mo Store window; boot=14.625 s. Existing autologin is not ordinary PAM or broad hardware/endurance proof.
Earlier `.775` measurements and its preserved transient-unit/probe failures belong
to [their receipt](docs/releases/2026-10-14-oracle-775-native-proof.json), not `.792` acceptance.
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

Current boot is signed1072/rollback1062, ID35500d14-a564-46de-9636-5ea133ba44cf. Basic native acceptance and cold search pass above; two real greeter/Remote handoff crashes remain visible. The old1062 boot7b01c656 retains its18 historical display-start aborts. Earlier ordinary-login63-hash/54-selfcheck/55-postcheck acceptance at bootb0fa1b9c is historical and does not qualify the later integrated source. The two-hour staging timeout and greeter failure remain preserved. Earlier1046 evidence follows,
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
55 GiB free after 124 exact anonymous pre-Oct15 cache images retired (measured +20.5 GiB); all 280 protected images and 17 containers remain. Earlier RAM figures below are scoped baseline samples.
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

Mira uses the bounded three-event burst above. The [earlier presence proof](docs/releases/2026-10-14-mira-job-presence-proof.json) predates the measured1.1s delay and does not qualify current behavior. Token-age/end-state and retired-directory protections remain, without idle polling; retired ARM-image evidence is historical only.

Mira mute/disconnect/late-recognition and recovery unreadable-state controls
pass. Community beta has real native/Oracle TLS flow, isolation and bounded
AR/EN renders, but branded DNS/recovery/moderation/retention/endurance remain.
CLDR installer search covers 312 zones with actual AR/EN row controls.
Remote PR225 is promoted in .1029/.756: private guest repeated cold PAM/PIN,
account handoff/logout, decoded frames and managed trust controls pass;
real hardware/private-TLS enrollment/phone/WAN endurance remain P2.17.
Original APK/PE branches are integrated with ancestry retained; 82 isolated tests are not ten real application journeys.
Oracle's installed Linux engine does not imply Windows/Android engines exist.

[Oct15 stable source qualification](docs/releases/2026-10-15-plasma-stable-source-proof.json) accepts exact native x86 Plasma 6.8.0 inputs and 12 seams, with real positive/negative greeter/logout controls. Native ARM 6.8 and Qt 6.12 remain unqualified; ARM keeps its reviewed 6.7.5 provider. Do not widen pins or layer desktop packages on a host.
Hardware boot visuals/suspend/hotplug/multi-monitor/laptop/touch, deliberate
failed-update/rollback, full AR/EN accessibility/contrast/scale/motion, clean
free-provider setup/cancel/quota/failover/owner voice, ten Windows/Android apps,
physical lamps, pressure policy, immutable inputs/SBOM/security delivery cadence,
staged rollout/support/licences/off-host data restore remain in the plan.
One architecture does not prove universal compatibility or complete Arabic UI.
