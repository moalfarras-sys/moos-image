# MoOS development plan — current execution backlog

Updated 2026-11-24. This is the single execution backlog. `PROJECT_STATE.md`
records measured state; `AGENTS.md` defines invariants; the engineering skill
selects the workflow. Dated handoffs and Git history preserve earlier work,
not competing instructions about what to do next.

## Product direction and success criteria

**هدف MoOS:** نظام عربي متكامل وجميل وسريع للحاسوب والجهاز اللوحي، يشغّل
تطبيقات Linux وWindows وAndroid من تجربة واحدة، بخط مِعيار وواجهة متناسقة
ومتجر غني وتحديث موثوق. الطموح هو المنافسة عالميًا؛ إثبات التفوق يحتاج
مقارنة منشورة بعتاد وأحمال متكافئة، وليس عدد الميزات أو وصفًا تسويقيًا.

Build on the existing signed OS, KDE/Qt/KWin/Wayland, app engines and native
services. Prioritize daily usefulness, correct Arabic, coherent interaction,
responsiveness, application compatibility and recovery together. An installed
runtime, a larger catalogue or a new wallpaper does not close a product journey.

| Product outcome | Acceptance that changes its status |
| --- | --- |
| Arabic identity and text | Distinctive OFL-derived Meyar with retained licences; native joining/stacked marks, mixed RTL/LTR, IPA/extended characters, editing and terminal cells; meaningful fallback for other scripts, without promising every Unicode sequence in one font |
| Beautiful daily desktop | Connected login → launcher → app → files → Settings/Store → lock/power journey, coherent light/dark materials and icons, legible small text, keyboard/accessibility and reduced motion; before/after installed pixels plus owner feedback |
| Three application ecosystems | One Store/App Drop lifecycle with honest per-app/version/architecture/GPU evidence for Linux, Windows and Android; runtime availability is separate from successful use |
| Fast and durable operation | Workload-stated boot, launch, frame pacing, PSS/CPU/wakeups, thermal/battery and pressure measurements, repeatable baseline and regression budget per hardware tier |
| One integrated system | Existing native owners and versioned API contracts; visible pending/failure/cancellation, actual state readback, preserved user data and no competing executors |
| Trustworthy delivery | Matching source/artifact evidence, all edition-specific boot gates, signed promotion, installed readback and working recovery |

## Active delivery and acceptance batch

Nov24. PR328 (a6577cd8) reached signed production on x86 and ARM. V3 booted
1187 with the expected signed digest, a working file search and 56/56 post-update
checks. The open PR tips for the Arabic theme names, glass, quarter layout and
Meyar variants (#327, #324, #326, #323 and #322) are ancestors of this release.
PR329 changes the optional engineering profile and is outside this revision.
The next physical M1 checks are two/four real windows on the V3, keyboard
detach/reattach with a focused field, and the internal-panel login handoff.
Record the attached display, scaling and orientation for each journey.
[Signed x86 promotion](https://github.com/moalfarras-sys/moos-image/actions/runs/45314040906).
[ARM build, packaged recovery boot and promotion](https://github.com/moalfarras-sys/moos-image/actions/runs/45259218792).

Nov23 owner steering (second message): one polished, modern system across all
eighteen looks. The MoOS corner (square top-trailing, three round) and Liquid Glass
apply to every card and frame. The interface scales to each screen's size,
resolution and scale. Plasma, KWin and Wayland stay the owners. Windows arrange
themselves: two programs take halves, four take quarters, and frames and programs
adapt to their cells. The tablet behaves as a tablet when the keyboard is detached,
showing the on-screen keyboard then and hiding it when a keyboard is attached.
Delivered in source so far: Meyar Arabic on Tajawal (PR325), real Hub frost
(PR325) and automatic arrangement (feat/v3-auto-arrange-20261123, P2.18). The
remaining slices are P2.18 frames and P5.3 tablet keyboard. Research inputs (to be
re-checked at implementation):
- Plasma 6.6 Plasma Keyboard can be limited to tablet mode, Plasma 6.7 made its
  triggers configurable, and KWin !8592 limits the virtual keyboard to tablet mode.
- KDE bug 467583 still lacks native auto-tiling.
- Polonium, Krohnkite and Fluid Tile are the KWin 6 auto-tilers.
- Windows 11 Snap Layouts adapt to screen orientation and guide the remaining zones.

Nov23. PR320 (the MoOS corner on cards and commands, the Meyar Glass on-screen
keyboard and the PR319 station repairs) merged as aa779022; its signed cycle is
pinned to that revision. The follow-up batch advances the reviewed x86 base to
44.20261123.1 (ced7919b). Only fzf and pipewire-libs-extra changed, and the
vmlinuz differs only by the Universal Blue re-sign that refused the nightlies
([kernel input review](reviews/2026-11-23-v3-kernel-input.json)). It also carries
Codex's Meyar alef/lam caps with redrawn Plymouth captions and the Mova Home
caption fit. Tier 1: the complete local image build and both PR image builds
qualify it before the next signed cycle.

PR318 contains the Arabic session keys from PR317, the selected-look handoff,
and the light-theme contrast fixes. On V3, check the native fingerprint prompt,
keyboard input, refusal and accessible action names after signed installation.
1178 supplied the earlier visual baseline; V3 now runs 1187.

V3 session qualification follows the signed 1178 baseline. Check the twelve
session symbols, password entry, lock/unlock and power confirmation on the
signed successor in the selected light and dark themes. The signed 1178 baseline was 21.173s. Plymouth exited at
10.505s, KWin selected DRM at 11.787s, and the greeter signalled readiness at
13.209s. On eDP-1 at 1.45 scale the owner requested larger glyphs and text.
The revision enlarges the drawn symbols by 12% and increases caption size by
one reference point. Compare the successor's cold boot and visible handoff
with the owner's observation on the same internal panel.

Nov21 login handoff (owner: "black for a second or two, then a heavy, badly
designed login"). On 1178 KWin takes 11.53→12.59 s before its clients start;
the scene then painted the login config's stale BloomLight fallback while the
island used the greeter account's Graphite seed, and both repainted when the
dark Bloom appearance arrived (13.55 s). The successor waits for the selected
appearance (≤900 ms, latched), paints the splash ground meanwhile, and draws
one password capsule with a time-of-day greeting. A warm QML disk cache made no
measurable difference in the private harness (cold/warm first paint 0.41/0.42 s),
so the boot-time greeter cache purge is unchanged. Acceptance: a cold boot of the
signed successor on eDP-1 with the owner's observation; KWin's own first black
frame is not removed by this change. whats-new.json reached 65,476/65,536 bytes;
Nov23 retired the five entries merged before 2026-09-25 (62,502 bytes after two
new entries). Keep retiring the oldest history rather than raising the cap.

Nov20 P0.1. The owner assigned V3 the merge and signed rollout for PR316.
Its full source checks passed at c157f126. The local x86 image refused the
new complete kernel digest from base 44.20261119.1. Its executable bytes,
original vendor signature, sensor core and transport match the reviewed inputs.
The successor admits the verified complete kernel from that upstream image.
Qualify it through the four edition pipelines, packaged recovery disk and V3
boot. [Kernel input review](reviews/2026-11-20-v3-kernel-input.json).

Nov20 follow-up. The local and PR images passed on 7753b182. The full local
check refused a 206-line state summary. The packaged ARM recovery proof timed
out reading an early boot screen before it saw the menu. Preserve that run and
exercise the bounded observer on the next packaged disk. The x86 release now
shares the verified 44.20261120.1 digest across its three editions while the
nightly still discovers the upstream base. At dacd5245 the complete local checks
and both PR image builds passed. Run 44696732832 reached a real tty1 login on
the packaged recovery disk and timed out waiting for the installer menu. Its
target stayed intact. Give the recovery menu exclusive tty1 ownership while
preserving serial login. At f239ef8f the local suite and both PR builds passed.
The packaged guest instead displayed cloud-init host-key generation on the
graphical console. Route system output to the serial port and explicitly hand
the display from Plymouth to the menu. The pinned disk builder also injects tty0 and ttyS0. Omit those defaults for recovery, verify the actual packaged boot entry, then repeat the interaction. Run 44742631108 booted with the single reviewed console and displayed the menu. The OCR reader saw only the backtitle. Verify the captured Linux-console glyphs and focus coordinates, then exercise navigation, Cancel and clean poweroff on the next packaged disk. Run 44799995260 passed menu, navigation and Cancel focus. After Cancel the original controls stayed visible above the exit message. Both recovery menus now request newt’s native clear-on-exit; the next packaged disk must visibly close and power off.

Run 44821608069 passed the packaged recovery menu, visible exit, clean guest
poweroff and target preservation. The separate full ARM desktop reached SSH
and captured Mira, then returned 124 at the 120-second first-open limit.
Its import trace charged 17.21 seconds to ESPHome and 4.34 seconds to the HTTP
server on a computer without a paired Echo. Load these only for a paired device.
Repeat both boots of the desktop disk with the same time limit before promotion.

Nov21 P2.17. The owner uses Mawj (موج) as the daily phone/browser connection.
Keep the existing account, pre-login boundary, routes and pairing through the
rename. At the five-second retry cap the old controller waited out the timer
after a network return, and could miss a socket left closing. The revised
controller starts one attempt on the foreground network event, preserves a
handshake already in flight and retires stale events. Native private-agent
setup, sign-in, reload and an authenticated WebSocket reply passed on V3.
The Chromium mobile fixture covers Arabic typing, frame continuity, switching
workspaces and return from the background. Physical phone timing and the signed
installed update require their own readback. [Mawj evidence](reviews/2026-11-21-mawj.json).

The x86 editions reached production as 1173. ARM 994 from main a0261263 passed the desktop QCOW2 UEFI boot and production promotion in run 44573209173. V3 follow-up PR315 passed the full Oracle suite and ARM/x86 image CI. Keep the separate recovery disk and physical tablet checks open. [Release and installed application checks](reviews/2026-11-19-app-runtime-compatibility.json).

Nov19 P0.1/P6.8: the upstream ARM base moved to 44.20261119.0 and renumbered service accounts. Register the exact new account bodies, refuse the old ones (PR CI rebuilt ARM/recovery on the new base), then follow the signed ARM pipeline and read back passim ownership after the Oracle update. [Review](reviews/2026-11-19-arm-base-accounts.json).

Nov19: qualify the integrated ARM tray providers, Store runtime and archive icons on the same source as the native frame and V3 changes. Verify all 16 tray components and the offline npm journey on the built images. Oracle boots signed 966 with 964 retained. [Maintenance record](reviews/2026-11-19-oracle-maintenance.json).

Nov18 owner authorizes preserving/pushing all remaining source, correct integration
and a signed system update, and has explicitly approved the requested automated source/image/CI/boot-fixture
checks. Physical host reboot/suspend remains coordinated with open editor work.

Oracle merged PR313 at 3f114cb0 and started the signed x86 cycle (44511467942).
V3 coordinates the packaged ARM recovery follow-up. On signed 1173 its normal firmware
order contains only MoOS entry 0001, and GRUB hides the normal menu for one second.
The 966 recovery guest recorded a coldplug probe before udev readiness in one
boot and a cloud-final/menu ordering cycle. Its native dialog also refused an
occupied target and misreported the second empty-target row. Require a real
menu, confirmed cancellation, clean shutdown and unchanged target on the
packaged successor. [V3 evidence](reviews/2026-11-19-v3-integration-and-recovery.json).
A late native KConfig failure control reproduces the Night Light opposite-pulse persistence defect.
The successor sends only the requested value and the existing fixed KConfig notification;
native watcher and unchanged already-off KWin readback pass. Final combined qualification
remains required; malformed-notification recovery and physical on/auto remain unqualified
(see `docs/reviews/2026-11-18-night-light-notification.json`).
The final private launcher fixture retains the86a full-check Qt-touch refusal,
requires the same actual AppletPopup after reopen and current native delegate
identities/rendered touch delivery. All9 tests/8 native viewport cases and original
broken controls pass; production launcher/image runtime inputs are unchanged.
The b677 local image was stopped by the coordinator freezing its cgroup; Buildah
refused paused status at44%. Keep that operator-induced failure and the earlier
3GiB OOM distinct. V3 subsequently built the 6315e997 image in 900 seconds
and verified eleven shipped files against source. This build reused the cached
Plasma transaction. The fresh x86 dependency failure is recorded below.
V3 also reproduced a delayed Store wheel event in Arabic at 250% scale. Its
probe now waits for the page and shelf to settle before measuring either axis.
[Input fixture proof](reviews/2026-11-18-launcher-input-fixture.json).
`fix/moos-complete-integration-20261118` is based on Oracle PR311
`d5d4897a`, which already contains PR308/309/310 and layout525e5600. It pins the
actual composed-base7.3.4 vmlinuz bytes while retaining original vendor lineage
and exact gates, and supplies native44px Tidal Cut frames/GTK transactions.
Earlier1df ARM44323788733/x8644323788622 results remain historical. Repo44323788769
refused stale32px/20px geometry assertions; the successor keeps exact44px
height/width/spacing/margins plus every SVG/state/identity control. First aggregate
aab fullcheck separately refused the stale native appearance fixture;d5 extracts
the real native_selected dependency and retains the old-order negative. Its
atomic GTK publication now preserves late personal writes with native race controls.
[Window proof](reviews/2026-11-18-window-integration.json).

The aggregate adds App Drop98fed279/qualified source913f016b and local Night
Light016e518d with ancestry retained. Their earlier checks do not qualify the
new combined tree. Preserve all news entries within the bounded reader and
original64KiB limit. [App Drop](reviews/2026-11-18-appdrop-active-removal.json),
[aggregate record](reviews/2026-11-18-complete-integration.json).

All formerly detached source tips have named GitHub archive refs. Old Qt review
and equivalent Center/Plasma changes retain provenance without restoring obsolete
production bytes. Private captures/build trees, credentials and inaccessible
native evidence directories are not publication candidates. No blanket add,
prune or worktree removal is authorized by an inventory.

On Nov19 V3 booted signed 1173 in 22.202 s. The only other deployment is 1162 for rollback.
The owner authorized retiring 1152 and 1078 after their local settings and origin metadata
were archived privately and checked against the originals. The locally retained 1139 offline ISO
previously passed full-byte checksum and detached-signature checks. The successor 1.8 s Liquid Glass scene passed native render, early handoff, and Arabic passphrase checks. Qualify the scene
in the signed successor and verify its appearance on the physical screen. The historical user qualification
159 failure has a preserved log and was cleared after the d8 source pass.
The V3 service reproduced exit 1 while ddcutil could not locate its dynamic
sleep cache. A private systemd runtime cache restored a completed, inactive
oneshot and a new stamp with the same mixed display topology. After reboot, the signed 1173 unit completed on the internal backlight.
Repeat on the mixed-display topology to verify that separate path. The existing PowerDevil policy and
zram size were preserved.

The V3 audit at 6315e997 includes all 70 local branch tips, 216 live GitHub
branch tips and 36 worktree heads. Seven untracked historical Qt files in the
older review tree match the named GitHub archive byte for byte. Exact-head
repository and ARM image checks passed. The x86 job 44347819021 and a fresh
transaction on its exact base both refused libavcodec 8.1.3-3 because no enabled
repository provided liboapv.so.11. Qualify the original transaction when the
provider is published to the stable repositories. Preserve the first attempt.
[V3 qualification](reviews/2026-11-18-complete-integration.json).
The a6a4eff3 image gate 44388295850 retained the same refusal. Bodhi
FEDORA-2026-a03cf645f0 (ffmpeg 8.1.3-3, openapv 1.1.3.0) reached Fedora 44
stable at 2026-11-19 01:29 UTC. Mirror propagation was uneven: at 05:40 UTC,
7 of 8 US and 5 of 16 European HTTPS mirrors served it. One V3 transaction on
an older mirror still refused. The original unchanged transaction is
requalified through fresh first-attempt PR gates. No exclusion, pin or testing
repository was added. Gate 44466840542 (7c2ce73a) then refused against
an older mirror: the rebuilt base 44.20261119 already contained openapv-libs
1.1.3.0 and libavcodec 8.1.3-3, and the runner's Updates mirror lacked
openapv-libs 1.1.3.0. The unchanged distro-sync then resolved on V3 against
the same base (config ce9eadd2) through both metalink and the primary mirror.
Both refusals are retained.

After approved qualification, push one final reviewed tree, let exact-head PR
image gates complete, integrate once, then freeze the actual merge SHA through
`--expected-revision` for one signed cycle. Preserve3×QCOW2/offline ISO/ARM,
separate recovery boot, signatures/tree/attempt and physical installed acceptance.
Never claim universal stability or move an unproven digest to production.

## Product acceptance

A supported release has a declared edition/hardware/application scope. It must
complete boot/login, files/apps, sound/network, Settings/Store/Mira and
update/recovery journeys within that scope. Unknown, failed and untested cases
remain visible. A finite matrix cannot establish universal compatibility or
absence of all defects. Compare other operating systems only with legal access,
the same hardware/workload and reported versions; do not infer private source
access or architectural superiority from screenshots.

## Non-negotiable architecture

1. One source tree produces four editions: general x86, NVIDIA x86, cloud x86
   and ARM. The three x86 editions share one base and one kernel.
2. The immutable image owns `/usr`; persistent system and user state lives in
   `/etc` and `/var`. Updates preserve a previous bootable deployment.
3. Every published digest is signed. Installation and later updates enforce the
   signature policy.
4. KDE Plasma and KWin remain the desktop engine. MoOS owns identity, defaults,
   first-party surfaces and integration; it does not fork the desktop without a
   measured upstream limitation and a maintenance budget.
5. `moai-do` is the only privileged product executor. Models and web content can
   select fixed actions but can never execute generated commands.
6. Mo Store is the application-lifecycle authority; W9.3 removed the direct
   Bottles and first-run Flatpak install paths. Shared end-to-end job/API acceptance remains open. Desktop applications
   use sandboxing and portals by default; system drivers and services stay in
   the signed OS image.
7. Mo AI is cloud-only. Free service is the default, paid providers require an
   explicit choice, and credentials remain private user state.
8. A build, a local image, a published candidate, a booted artifact and a
   promoted release are different states and must never be conflated.
9. MoPlayer is a first-party in-tree application. `moplayer/` is its only source;
   x86 and ARM build and test it directly and install only the resulting bundle.
   No external MoPlayer branch, release archive or nested workflow participates.

## Every app, one verb — the app-engine contract (P4.x)

The owner wants install/open/update/remove to feel like one MoOS product.
The existing authority chain is:

`Store / file picker / drop / launcher → registry and resolver → Store job and
engine adapter → native runtime → result and installed-state readback`.

- `system_files/usr/share/moos/app-engines.json` declares supported engines and
  truthful capabilities; `moos-app-engine` resolves readiness read-only.
- `moos-storectl` owns application mutation/jobs; `moos-run-foreign` and
  `moos-app-drop` delegate through the existing routes. `moai-do` remains the
  privileged product executor. Never add a second installer or privileged API.
- Linux uses the existing native/Flatpak/App Drop paths. Qualify the exact package
  and ABI; “Linux apps” does not promise arbitrary distribution packages install
  into the immutable host. Keep development containers separate from OS delivery.
- Windows uses the registry-selected Wine/Bottles path and managed per-app state.
  A Wine prefix is not a security sandbox. Preserve isolation disclosures,
  file/data ownership, runtime/version and32/64-bit qualification. Additional
  gaming/runtime paths require reviewed integration through the same authority.
- Android uses the existing Waydroid path and reviewed system/vendor images.
  Record APK ABI, image provenance, graphics path and actual app behavior.
  NVIDIA software rendering, fractional scaling and Android's internal caption
  remain separately measured limitations until a supported repair passes.
- ARM capability is measured independently. Do not equate x86 emulation with
  native support, quietly enable translation, or copy an x86 compatibility label.
  Cloud editions qualify their actual service/remote contract; desktop tests
  may be inapplicable with an explicit reason.

Ordinary product surfaces say Windows programs, Android apps and Linux apps.
Keep runtime details in appropriate engineering/support evidence. Existing
branding gates and file-name exceptions remain; legal attribution survives.
Unsupported formats and unmet DRM/anti-cheat, driver, service or proprietary API
requirements need a clear capability result, not an enabled button that cannot
complete. Do not bypass security, licensing or isolation to obtain a pass.

The catalogue has264 source entries, including46 Android and20 Windows recipes,
within the recorded qualified inventory. Recalculate it from current source
rather than editing counts as a growth target. `moos-compat-matrix` already
separates recipe availability from unassessed application testing. Extend that
existing product path with actual evidence; do not create a parallel catalogue
or use catalogue count as a compatibility score. See [Mo Store](MO_STORE.md).

For each engine, first complete one representative daily app through discover
or file-open → consent/install → visible app → Arabic-named file save/reopen →
launcher after login → update/cancel/failure → remove with data retained by
default. Then expand P4 coverage: at least ten Windows, ten Android and ten Linux
applications across documents, media, communication, development and graphics;
include supported gaming workloads without extrapolating to all games. Choose
named, licensed, version-pinned apps from the existing catalogue and record the
selection in P4 evidence before running. Keep a cross-app clipboard/file/URI
journey and a concurrent mixed-engine workload in the acceptance set.

Historical A1–A5 labels remain aliases, not another ordered backlog:
A1 engine baseline → P4.3/P4.4; A2 launchers → P4.1/P4.3/P4.4;
A3 catalogue → P4.1/P4.5; A4 dropped files → P4.6/P4.7;
A5 third-party app API → P4.1/P4.2. A public Apps API needs a documented schema,
authorization, cancellation and backward-compatibility tests over the existing
backend before its interface is called supported.

## Task protocol

Work in release batches. Related slices may use reviewable commits, but integrate
the coherent batch in one pull request after its fast gates pass: targeted tests,
`just check`, PR CI, and a local image build when a Tier 1 boot/image file changed
(see `docs/AGENT_GUIDE.md`). A push to `main` starts candidate work, so do not
spend one image build on every small file. Merging does not deploy:
`build.yml` pushes only `candidate-*` tags, and production tags move only
through `promote-x86.yml` after exact-revision proofs. Do not stop and wait for
a release cycle between slices; keep implementing while CI runs.

A batch ends with one release cycle, started by `scripts/release-candidate.sh`.
Before dispatch, inspect active workflow SHA/run IDs and reuse them; never start
a duplicate build merely to learn status. At dispatch, merges freeze, the signed
candidate is built from `main`, the three QCOW2
proofs, the offline ISO proof and the ARM proof run in parallel on the exact
digests, and promotion happens only when every x86 proof passes. Merges reopen
after promotion, or after the failure is fixed and a new cycle starts. The
candidate SHA stays fixed for its cycle; neither a second branch nor a running
build is a second release authority. Independent implementation may run in
parallel with explicit non-overlapping file ownership.

For every task:

1. Read this plan, `PROJECT_STATE.md`, the engineering skill and the affected
   component documentation.
2. Record the current runtime or artifact behavior before editing.
3. For runtime defects, add a regression that fails for the reproduced defect;
   for new behavior, define measurable acceptance. Documentation/editor-only
   changes need direct validation, not tests that merely mirror their wording.
4. Implement the largest safe, coherent batch of related tasks, each as a
   complete vertical slice. Do not leave a second owner, compatibility alias or
   dead service unless an upgrade path requires it, and do not split one
   coherent change into several release cycles.
5. Run targeted tests, `just check` and, for Tier 1 boot/image changes, a local
   image build. VM, ISO and hardware proofs run once per release batch unless
   the slice is itself a boot fix that must be proven before anything else.
6. Update `PROJECT_STATE.md` with current evidence and update the task status
   here. Remove superseded prose instead of appending a diary.
7. Commit reviewable results and integrate the coherent batch once. Report
   changed behavior, evidence and open exclusions.
8. **Move straight to the next task in the batch.** Do not announce readiness and
   wait: a finished task is recorded, not celebrated. Stop only for a real
   blocker — something that needs the owner (hardware, a credential, a reboot),
   a failing safety gate, or a decision that changes the plan — and then state
   the exact blocker and carry on with the next unblocked task. Source
   completion and release evidence are separate: a merged slice is complete in
   source, and its row closes when the batch promotion proves it. Report the
   whole cycle at the end: what landed, what each proof showed, what is open.

## Ordered execution

The owner-authorized complete integration above is the current entry point.
Boot/security/data-loss fixes still preempt the same M0→M1→M2/M3→M4→M5 queue.
Oracle coordinated PR313. V3 completed the later PR328 delivery and booted 1187. PR313 includes d5d4897a and the preserved Oracle
maintenance ancestry; all269 known refs are covered. Keep constituent component
and V3 proofs with their actual sources; freeze one final combined candidate,
then preserve its source/tree/attempt/signature and release admission.
[PR313 branch audit](reviews/2026-11-18-unified-oracle-integration.json).

Owner permission for automated qualification is now granted. Freeze the complete
source for its tests and image/CI. Preserve original refused runs and use a fresh
first-attempt candidate after any source repair; host reboot remains separate.

| Order / milestone | Outcome and implementation focus | Rows | Exit evidence |
| --- | --- | --- | --- |
| 1 · M0 current delivery | Qualify the stock-input repair and coherent native UI batch | P0.1–P0.2, P0.6–P0.7, P2.5, P2.8, P6.7 | Full exact-source/image/CI, signed3×QCOW2+offline ISO+ARM proofs, separate recovery qualification, promotion and physical readback; live copies retire by recorded bytes |
| 2 · M1 daily Arabic workspace | One coherent desktop/typography journey and one daily app per engine through Store/native launchers | P2.3–P2.5, P2.7–P2.10, P4.1, P4.3–P4.4, P5.4 | Installed Arabic/English whole-workspace review, files/clipboard/input, reduced motion/accessibility and baseline performance; owner feedback |
| 3 · M2 first run and M3 integration | Onboarding, login/lock/power, Settings/Store/Mira and shared jobs/API | P1.6–P1.7, P2.1–P2.2, P2.12, P2.16, P3.1–P3.7, P4.1–P4.2 | Clean/upgraded/offline profiles; real auth, cancel/retry/failure/readback, preferences and data survive update |
| 4 · M4 compatibility and hardware | Expand three app suites and qualify device/tablet/GPU/performance tiers | P0.3–P0.5, P4.3–P4.5, P5.1–P5.8 | Version/architecture/GPU matrix, ten Windows+ten Android+ten Linux journeys, physical tablet input/rotation/suspend, measured performance/recovery |
| 5 · M5 sustainable product | Reproducible inputs, security cadence, staged rollout, support/migration | P6.1–P6.6, P6.9 | Proven rollout/halt/recovery, digest-linked provenance, support scope and maintainer/user docs |

Run security/Plasma-transition work when its input changes; P6.7 is recurring
qualification. Blocked physical tests do not block disjoint native/app source
work. While a candidate runs, keep its SHA fixed, use disjoint files and one
integration owner, and preserve signing, identity and recovery throughout.

## Product design and implementation decisions

The visual brief is a recognizable Arabic workspace: Meyar's geometric rhythm
and soft curves, clear hierarchy, restrained glass, consistent icons and useful
motion. Implement it through the existing
[Liquid Glass contract](../artwork/MOOS_UI2_DESIGN.md), shared token module and
generators. Do not introduce another palette, token system or shell. Review a
connected daily journey, not a gallery: wake/login → launcher → Arabic document
and browser → Windows/Android app → files/clipboard → Settings → lock/power.
Include empty/loading/error/offline states and preserve personal choices.

Desktop and tablet share the same application/service owners. Adapt navigation,
density and content flow to actual available space and input. Use the existing
40px control/44px touch targets, visible keyboard focus and native virtual
keyboard; verify the focused field stays visible, portrait/landscape rotation,
external keyboard/dock transitions and pen input on physical hardware. A
resized desktop screenshot is not tablet acceptance. Screen-reader navigation,
large text, contrast and reduced motion belong to each slice, not final polish.

Motion explains focus, hierarchy or state. Use existing KWin/Qt animations and
shared timing tokens, allow interruption/reversal, stop invisible work and never
delay an action for its transition. Profile the real compositor/client pair;
reduce expensive effects through the existing visual-tier owner. Do not change
security, driver selection or power policy to make an animation benchmark pass.

Reuse decisions and primary sources are in the engineering skill's
[upstream selection reference](../skills/moos-engineering/references/upstream-selection.md).
It distinguishes established owners, conditional additions and research-only
options. It is a dependency decision reference, not another task queue. Every
addition must name the P-row/user problem, existing integration owner, exact
reviewed release/commit and licence, maintenance/security cost, architecture and
GPU limits, upgrade/removal behavior and acceptance evidence before adoption.

## Hardware scope and performance targets (P5.1/P5.4)

These are **qualification targets, not measured minimum requirements or current
performance claims**. Publish a supported minimum only after the named device
and workload pass. Keep `system_files/usr/bin/moos-visual-tier` as the single
classifier: essential for limited/software graphics; balanced with a bound GPU,
at least4 cores/6GiB; flagship with a bound discrete GPU, at least8 cores/15GiB.
Preserve its user overrides and consumer-owned budgets; do not create a second
tier detector or treat RAM alone as proof of graphics capability.

| Qualification profile | Workload and scope | Acceptance focus |
| --- | --- | --- |
| Entry: 2–4 cores,4GiB,SSD,1080p | Arabic files/editor/browser and one native Linux app; essential effects | Useful core workspace under bounded memory pressure; no forced Android/Windows background startup; heavier apps qualified individually |
| Everyday: 4+ cores,8GiB,accelerated integrated GPU,SSD | Arabic desktop/tablet at1080p/1440p; one daily app from each engine, individually then together | Input/launch/frame targets below; portal/data journeys, suspend and measured power; mixed-engine limits stay explicit |
| Expanded: 8+ cores,16GiB,qualified discrete GPU,SSD | 4K/fractional scaling, multiple apps, video and selected gaming | Same responsiveness at the actual refresh rate, GPU/VRAM and thermal stability; NVIDIA Android fallback measured separately |
| ARM/cloud | Actual native ARM or cloud hardware and its declared display/remote workload | Independent ABI/driver/encoder and boot evidence; neither x86 emulation nor a software-rendered A1 proves tablet/GPU performance |

For the everyday/expanded profiles, start M1 measurement with these product
targets: visible input feedback p95≤100ms, warm launcher p95≤150ms, and the
existing Settings landing page interactive in≤1s warm/≤2.5s cold. Measure third-
party launch times separately; do not apply a launcher target to Android boot
or downloads. For a60Hz active desktop transition, the presentation budget is
16.67ms (8.33ms at120Hz); target≤1% missed presentation deadlines over the trace.
Report p50/p95/p99 frame intervals and stalls too. An unavailable presentation
probe leaves this result untested; average FPS is insufficient. These MoOS
targets are design decisions, not performance guarantees from upstream.

Use at least30 warm launches,5 independent cold launches/boots (report each,
not a confident tail percentile from five samples),3×60s interaction traces,
and10min settled idle. Record versions, resolution/scale/refresh, cache state,
power profile, temperature, storage and concurrent work; do not drop global
caches or reboot the owner's active work to manufacture a cold sample. Bound
pressure tests and preserve recovery. Record whole-workload PSS, CPU/wakeups,
GPU/VRAM, PSI, battery/energy and thermal throttling, including a30min mixed-
engine session and repeated open/close. New first-party idle services must be
event-driven; prove no unintended recurring process/animation work.

Before optimizing, freeze comparable before/after traces and the metric budget.
A repeatable regression above5% in launch/frame/idle resource or energy cost
requires investigation; a smaller change within measured noise is inconclusive.
Existing missed product targets remain open rather than becoming the new target.
Do not trade data safety, legibility, battery or another critical journey for a
headline speedup. Report any justified tradeoff explicitly in the same P-row.
These are M1/M4 acceptance work; they do not retroactively label historical
M0 evidence as measured performance or require another local VM image.

## التسليم للإيجنت المنفّذ التالي

هذه النقاط سجلّ تسليم سابق. للتنفيذ الحالي ابدأ بفقرة 24 نوفمبر وأدلة الإصدار 1187 أعلاه.

1. اقرأ الحالة والفروع والـPRs والعمليات الحقيقية. root علىV3 يملك الدمج الكامل
   منPR311/1df01483 معApp Drop98fed279 وNight Light016e518d. لا تعِد دمج
   PR308/309/310 منفردة، ولا تغيّر مصدر إثباتاتOracle الجارية.
2. المالك وافق صراحة على الفحوص الآلية؛ شغّل بوابات المصدر والصورة وCI
   علىSHA ثابت، ونسّق حفظ المحررات قبلإعادة تشغيل الجهاز الفعلي.
3. فرّق نتيجة913f الكاملة السابقة عن الشجرة المجمعة الجديدة. أصلح توقع32/20
   القديم إلى عقد44 الأصلي المقاس دون إسقاط تغطية الرسوم/الحالات/الهوية.
4. احفظ كلcommit أصلي والأرشيف والعمل الخاص. لا تدفع أسرارًا أو صورًا خاصة
   أوbuild trees. تحقق من الأسلاف والمالك والملفات المفتوحة قبل تقاعد شجرة عمل.
5. أقلع V3 إلى 1173 الموقّع وبقي 1162 للرجوع. أُزيلت 1152 و1078 بعد التحقق من
   أرشيفَي الإعدادات المحليين. يلزم فحص الحركة الجديدة على الجهاز بعد إصدارها.
6. بعد البوابات المعتمدة، ادمج مرة واحدة وجمّدSHA الفعلي عبر`--expected-revision`.
   كلتوقيع/digest/tree/attempt وإثباتx86/ISO/ARM وrecovery المنفصل لازم. التحديث
   والإقلاع الفعلي وقراءة الجهاز مرحلة أخرى؛ نسّق حفظ المحررات قبل إعادة التشغيل.
7. تابع صفوفP القائمة والرحلات غير المحجوبة؛ لا تسمّ الاختبار أوالكتالوج أوفرع
   المصدر نظامًا منشورًا، ولا تصف الاستقرار بأنه خال من كل العيوب دون دليل.

## P0 — Release qualification

| ID | Outcome | Current boundary | Required acceptance |
| --- | --- | --- | --- |
| P0.1 | Integrate the reviewed first-install repairs and create one candidate revision | PR313 preserves the reviewed window, sensor, Store/App Drop and Night Light work. All 70 local and 216 GitHub branch tips were ancestors of 6315e997 on V3. PR313 merged at 3f114cb0. The subsequent PR328 release qualified the combined inputs at a6577cd8. | Exact candidate source, all integrated fixes and no local override counted as release. |
| P0.2 | Run generic, NVIDIA and cloud QCOW2 proofs plus offline ISO install/second boot | Signed x86 1162 and ARM 966 have independent promotion receipts. PR313 at 6315e997 passed ARM image CI. Its x86 package solver refused the missing stable liboapv.so.11 provider before image construction. The subsequent PR328 workflow booted and accepted its separately packaged three-drive recovery installer and promoted the ARM image. | Three exact-digest x86 QCOW2 journeys, offline installed ISO and separate ARM two-boot proof. |
| P0.3 | Finish physical NVIDIA qualification | Open: signed .1042 native 55/0 + 55/0, 16 hashes and exact signed player bytes pass; one URI/finite seek/resource journey passes. Kernel -201 NVIDIA vermagic matches. USB-C UCSI -110 remains; broader physical acceptance is open. Offline ESP dirty-bit-only clone/live proof passes, 16 boot-file hashes preserved and both shared vfat mounts restored; the prior unmount mistake failed before fsck and has a private old/fixed topology control. New1072 boot preserves UCSI-110 and a QtQuick ListView/QQuickView teardown SIGSEGV through screenRemoved; exact root cause is unproven. Basic GPU/35 payload/54 selfcheck/55 postcheck/cold-search acceptance passes; isolate real screen-removal before changing greeter/graphics policy. Suspend/hotplug and recovery remain | Actual NVIDIA GPU, initramfs module, displays, suspend and clean recovery on qualified hardware. |
| P0.4 | Prove failed-update recovery | Nov15 disposable-VM run 43769002291 (rollback-proof.yml, signed moos@03c211a6): a second deployment booted, `bootc rollback` returned to the same signed commit with user data intact, signed origin and no failed units, and kept the newer deployment. Open: a deliberately failing boot reaching automatic fallback (P1.2) and an actual forward return; no physical-station rollback | Deliberate bad update, automatic/manual rollback and forward return without owner data loss. |
| P0.5 | Configure and accept free Mo AI on a clean account | Open / acceptance not complete | Clean-account provider setup, free route, reboot, cancellation and network/quota/key failures. |
| P0.6 | Promote only proven digests and update the physical PC | Nov19 V3 booted signed 1173/d3ce53eb, retaining 1162. The native hardware unit and all 54 settled self-checks passed. Post-update returned 55/1 after the early check service logged a display error. All three x86 editions and ARM 994 reached production. The separate recovery disk and a signed physical boot of the new animation remain open. | Promote only exact proven signed digests; separately verify installed stage/reboot/rollback. |
| P0.7 | Remove the intermittent `plymouthd` crash (ARM second boot; x86 first boot) | Reviewed Plymouth producer/native library and exact final initramfs gates are integrated for desktop and separate ARM recovery. Main ARM44289879261 passes recovery image/archive construction and desktop disk boot/promotion. The packaged recovery disk has no separate UEFI boot proof; keep that acceptance open and preserve old stock-package/source-log refusals | Pinned vendor Plymouth fix, old/fixed negative, exact final initramfs and actual boot visuals. |
| P0.8 | Make the ISO installed-reboot proof deterministic | Integrated at 1a73a4e0; .1022 exact offline ISO 38051456847 passes. CLDR/native AR/EN row clicks and mismatch negatives pass. Earlier .1018 private two password logins/cold boot pass 51/0 twice; offline serialization strict mismatch remains visible. Host batch reboot is separate | Repeated installed-ISO reboot with DHCP/SSH-channel evidence and console failures visible. |
| P0.9 | Run image-only gates before the merge | PR311 Repo44323788769 refuses old TitleHeight32/ButtonWidth20 assertions against reviewed native44px geometry; exact remaining SVG/state/identity controls stay intact. Its ARM44323788733/x8644323788622 jobs retain their original1df inputs. New combined-head Repo/image CI is approved and remains mandatory before normal main merge | PR generic image gates block real image failures; no signing/publishing from PR. |
| P0.10 | Gate NVIDIA persistence on a bound GPU | Stable mechanism/artifact evidence recorded; preserve required gates | Bound NVIDIA hardware and exact-kernel persistence/initramfs proof. |
| P0.11 | Give first-boot Flatpak setup a realistic finite timeout | Stable mechanism/artifact evidence recorded; preserve required gates | Finite realistic first-boot app setup timeout and actual ARM reboot. |
| P0.12 | Deliver the exact signed, installed-system-proven ISO through a stable anonymous download | Public1046 remains last anonymous qualification. Qualified1127 ISO is locally archived:5817565184bytes, SHA2566303b2147a9ed271180a6b63d86d8e6d48bee23b90a1cadec5b02617b112075f, detached signature verified. New hosting/account access and anonymous full/range acceptance remain open | Repeat stable anonymous full signed ISO, exact size/hash and resumed ranges, sidecars and site readback for each release. |

## P1 — Reliability and first run

| ID | Outcome | Current boundary | Required acceptance |
| --- | --- | --- | --- |
| P1.1 | every migration records id/revision/outcome in one append-only ledger; the two-key wallet write is staged and renamed so an interruption leaves the original file; interrupted, repeated and clean-vs-upgraded fixtures in `tests/test_migration_ledger.py` | Native explicit wallet opt-in/out, provider lifecycle and migration-preservation controls pass; owner Off is live, exact compiled Settings is locally reviewed. New-source full/image/signed acceptance pending | Versioned idempotent transactional migrations; private durable outcomes and failure recovery. |
| P1.2 | `moos-boot-assess` counts unblessed boots in `/var/lib/moos` because `/boot` is read-only and greenboot is absent; three unblessed boots return to the previous deployment through `bootc rollback`, and it refuses when a rollback is already queued, when there is no previous deployment, or when it already rolled away from this one; enabled on x86 and ARM; `tests/test_boot_assessment.py` | Stable mechanism/artifact evidence recorded; preserve required gates | Correct installed boot assessment and fallback; physical bad-update journey remains separate. |
| P1.3 | `moos-list-disks` now reads TRAN, so soldered eMMC is no longer called removable (which could make a tablet only disk refusable) and eMMC boot/RPMB areas are not offered; `tests/test_installer_storage_policy.py` drives SATA/NVMe/USB/eMMC/SD fixtures, target-only mutation and the live-medium rules; the installer pins LC_ALL=C so the actionable low-space and disk-io messages survive a non-English session; no-encryption is recorded as a deliberate decision with the condition for revisiting | Stable mechanism/artifact evidence recorded; preserve required gates | Target-only installer storage, removable/live-disk refusal and safe partition/boot ownership. |
| P1.4 | `/usr/libexec/moos-support-bundle` with per-section and whole-bundle caps; redaction proven in `tests/test_support_bundle_redaction.py` and on this machine (51.6 KB, 13 sections, no live address, MAC, home path or credential shape); PR #102 | Implemented/delivered within recorded scope; wider acceptance remains; the integrated audit cycle is signed/promoted | Every collected output redacted before truncation; no credential-file reads; private bounded atomic export. |
| P1.5 | `moos-image-update` publishes one atomic record that the Updater window and the journal both read; `tests/test_update_state_machine.py`; PR #102 | Stable mechanism/artifact evidence recorded; preserve required gates | Atomic truthful update state, stale/dead PID handling and meaningful failure UI. |
| P1.6 | Store metadata, dictionaries, locale, drivers and Help remain useful; cloud-only features explain connectivity clearly | Open / acceptance not complete | Fresh offline files/media/Help/store/locale/dictionaries; cloud functions state connectivity needs. |
| P1.7 | gateway, control, agent API, Settings snapshot and Store job schemas; stale/dead/partial response, timeout, restart and same-host cross-user negative tests. **2026-10-04 source:** shared kernel socket-UID guard on all three HTTP APIs; positive live-loopback and negative identity/unknown-record tests. Installed upgrade/reboot and server impersonation remain open. | Open / acceptance not complete | Versioned native/API schemas, partial/stale/dead responses, timeout/restart and adapter failure tests. |

## P2 — Unified desktop

| ID | Outcome | Current boundary | Required acceptance |
| --- | --- | --- | --- |
| P2.1 | Native MoOS modules inside KDE System Settings | Implemented/delivered within recorded scope; wider acceptance remains | Installed native loader, every MoOS module and backend; readback and keyboard/locale/scale frames. |
| P2.2 | One Settings entry and stable application identity | Native audit repaired the zero-entry account shadow. One real KDE entry, 52/0 source selfcheck, six launcher controls/seven isolated KCMs pass. Integrated PR228 at 4ee7f158 passes final local ARM/9 hashes and ARM/generic PR CI; signed .1034/.763 delivery passes. Oracle native boot/one entry pass; wider keyboard/scale entry acceptance remains | One actual System Settings identity/window and correct native destinations from all entry points. |
| P2.3 | One qualified Arabic/English locale authority | Signed1162 includes the qualified Meyar defaults and existing native/Flatpak discovery controls. Nov18 source repairs native Chromium family-less Arabic fallback; after reboot the owner editor still paints Noto Sans Arabic through system-ui, whose proposed alias is withdrawn/unproven. Flatpak-browser policy and actual rendered Arabic pairing remain open. Owner steering Nov23: Meyar Arabic takes Tajawal's design. It is built from Tajawal's seven weights (google/fonts 20776328, OFL, no Reserved Font Name) with outlines, spacing, kerning, marks and line metrics unchanged, plus only the Arabic-script code points Tajawal lacks. Those come from the reviewed Noto derivative at the weight whose stroke colour matches each face. `build_arabic_ui.py --verify` passes 16/16 shaping-identical strings per weight, loses no character and keeps پ ژ گ چ. The native editor journey keeps every stacked-mark line inside its box. Codex's alef/lam caps and Meyar Form drafts are superseded for the default and remain on their branches. Signed delivery and installed-app rendering remain open. Preserve named/personal/generic requests and the original discovery/painting refusals | KDE/QML/GTK/Mira/MoPlayer/Flatpak selection after relogin/reboot; Arabic first, English supported. |
| P2.4 | Keyboard and screen-reader operation | Source Island correction passes 48 native Qt configurations and original-source controls; full shell/Orca acceptance remains | Real keyboard traversal/focus and Orca Arabic/English on all primary flows. |
| P2.5 | Visual, contrast, scale and reduced-motion matrix | Nov23 source batch: the MoOS corner (square top-trailing, mirrored) owns Design Core, shared surfaces, 46 app/plasmoid cards, shared and hand-drawn command buttons (17 in installer/Welcome), session surfaces and all 18 popup/desktop-card FrameSvgs with matching blur masks; plasma-keyboard 6.8.3 wears Meyar Glass with layout-following languages (private-compositor evidence, `tests/test_moos_corner.py`; signed delivery and physical touch remain open). Codex's unmerged wide-screen account-beside-prompt session card (same preserved branch) fails the maker's-mark gate and replaces the accent glyph tile with a bare glyph; it awaits an owner design decision, and its keyboard-rotation stale-key report is not yet reproduced here. Merged source includes Quiet Glass, native Control Center/Mova and PR307 frame centring; user-local copies and signed1162 remain distinct. Historical480 atomic material transitions and signed1034/763 proofs remain in receipts. Current full AR/EN/scale/contrast/reduced-motion and installed connected workspace acceptance remain open; window PR309/310 stay with their owner | 1080p–4K, 100–250%, Arabic RTL/English LTR, light/dark, reduced motion and measured readable contrast. |
| P2.6 | Asset reachability and removal of retired UI | Open: archived translucent-dialog prototype retained, but current-theme blur-off qualification/integration remains | Generator/runtime/test consumers proven; retain negative fixtures and required upstream notices; never restore obsolete generated assets over today's theme. |
| P2.7 | Horizon feedback, clock input and system sound | Nov11 shared-role Quiet Lift KWin effect passes native open/close/reversal/reduced/broken controls and is session-loaded on V3; complete source/signed/default/frame-time qualification pending. Existing shell and sound acceptance remain open. See docs/reviews/2026-11-11-native-motion-qt-workloads.json | Finite stable-hit feedback, reversal/hidden/reduced-motion proof, clock keys and actual event sound. |
| P2.8 | MoOS Bar, Search and Island as one shell | Merged source unifies native Control Center and Mova through existing tray/Kicker/Milou/KWin owners, retaining old/fixed/input controls. Recorded user-local packages on signed1162 are not immutable delivery. Nov23 source: Mova Home commands take their native caption height; the real native driver refuses the old 66px card (Arabic label 37+32px) and passes the fixed view in its four AR/EN viewports, with scrolled before/after captures. Original Island keyboard/token proofs and installed inventories remain historical evidence; owner portrait/touch/Orca and full connected launcher/panel acceptance remain open | Native accessible Search/Island/Bar, keyboard escape, multi-context tabs and truthful lifecycle tokens. |
| P2.9 | User-visible MoOS identity on every surface | Implemented/delivered within recorded scope; wider acceptance remains. Nov19 Liquid Glass boot scene passes source/native-pixel review; owner acceptance, image initramfs and signed boot pending | Unchanged identity gates plus actual login/boot/desktop/app surfaces; legal attribution preserved. |
| P2.10 | Readable text and glyph contrast on every palette | Nov23 native review: the common keyboard outline uses the scheme’s DecorationFocus colour. Measured on Window in all 18 looks, Daylight improves from 1.88:1 to 3.13:1. The Arabic desktop scene rendered on the V3 in 18 private Plasma sessions. Physical tablet and signed-session acceptance remain open. Nov22 source: every KDE text role, focus mark, selected ink, Konsole ANSI 1-6 and libadwaita accent pair in all 18 looks meets WCAG (test_theme_role_contrast); retired light-family links/visited/terminal/GTK accent values fail the same predicate. Existing desktops receive only exact retired values via moos-color-roles. Daylight selection vs view stays 2.98:1 (the accent itself). Installed frames and owner review pending | All schemes meet role-specific contrast; actual glyph/card/pointer frames instead of token names. |
| P2.11 | Visible, bilingual update changes | Implemented/delivered within recorded scope; wider acceptance remains | Readable current entries and working routes, delivered update/notification readback. |
| P2.12 | One update surface for OS, apps and firmware | Open / acceptance not complete | OS image, Flatpak apps and firmware share truthful pending/failure/unsupported/finished states. |
| P2.13 | MoPlayer performance and server/stream compatibility | Native ARM installed MPEG4 plays and advances 2.93→8.07 s (~447 MiB RSS), but exposed direct-file live controls. Independent fix accepts encoded Arabic file URIs, finite local/explicit movie URLs and no catalogue records; 258 Flutter tests/native ARM build pass. Native source bundle proves 20 s MPRIS length/CanSeek, paused +5 s seek and rendered frames/controls; restored all-live factory fails the new test. Final local image/9 hashes, all PR CI and signed .1034/.763 delivery pass. Oracle signed .763 native boot/installed small MPEG4/seek/frame journey pass; wider server/hardware/codec/endurance acceptance remains | Installed playback/reopen/stop and memory on real server kinds, MAC portal, HEVC/interlaced samples. |
| P2.14 | Remote input, recovery and mobile/WAN video | Nov9 main NVIDIA gate preserves a missing restarted-frame refusal. Packet-bound actual codec fixes the native withheld/stale-metadata class; old negative,51 portal/394 total assertions and six real encoded/transported/decoded frames pass. Full source/image/new signed and installed acceptance pending; earlier delivered input remains scoped | Held-input ownership, decoded pictures, browser recovery and owner iPhone/cellular endurance. |
| P2.15 | Mira face, speech/rest and original portrait identity | Capture policy integrated/promoted in .1022/.749; both hosts booted with matching delivered hashes. Source/private-helper boundary and muted real USB pass; physical unmuted speech and long capture remain open | Both portraits retained; single mouth, real voice/pause/idle/hidden/reduced-motion readback; 11 private-process boundary tests, 45 controller tests, real muted USB with zero captures/overruns and three synthetic unmute/mute cycles. Signed installed delivery passes on both hosts; physical unmuted voice/device acceptance remains open. |
| P2.16 | Shared login, lock and power experience | Nov21 source: login appears once in the selected look (bounded settled appearance, splash ground meanwhile), one password capsule, time-of-day greeting; real greeter/lock frames on a private KWin. Cold boot pending. Delivered within earlier recorded scope; private Arabic lock/power/wrong/correct-password controls pass, login buttons remain English. PR227 maintenance scoping is integrated through PR228 with both native PR image CIs, owner/greeter conditions, 17 theme tests and final local ARM/three unit hashes passing. Signed .1034/.763 delivery passes; Oracle native boot/bytes pass; ordinary-login/hardware acceptance remains; authentication stays upstream. Nov13 Arabic unlock21 native frames/18 tests remove measured prompt/bullet overlap, keeping normal artwork bytes; final initramfs/encrypted input/cold boot remain pending | Native greeters 640×480–4K@2.5, password refusal, multi-user, save/logout and accessibility. |
| P2.17 | Mo PC Remote before account login after reboot | Greeter KDE environment and actual three-group EIS keymap correction is signed in .1044/.773 and retained in .1046/.775. Source/29 controls and actual device old/fixed proof pass; owner ordinary password login/account handoff passed on .1044, and .1046 now boots with 54 selfchecks/2 notes, 55 post-update/0 failures and 19 hashes/player. Temporary bundle retired after replacement/no-holder proof. Oracle pre-login remains off; repeated native wrong/correct PIN/password/cold-boot, phone/WAN/multi-account/endurance acceptance remains  Native1072 additionally measures first-owner localhost8765 binding before old greeter Remote stops, one SIGABRT/managed restart then active; bounded account-owned startup/handoff controls and qualified repair remain, not a reason to change PIN/PAM or steal another account listener. | Explicit opt-in, authenticated PIN/trusted-device/private TLS; native greeter capture/input with upstream PAM and no saved account password; real wrong/correct PIN/password, bounded handoff/logout/account isolation; default-disabled/native NVIDIA and ARM reboot evidence. |
| P2.18 | Windows that arrange themselves, with frames that fit | Nov23 source: MoOS Arrange splits the screen by itself on KWin's own signals: halves (portrait: rows), main and two, quarters, a floating fifth window, a lone survivor taking the area. Order follows position, so no reading direction is assumed. A window whose minSize cannot fit its cell refuses the layout, and dialogs never move. Meta+Alt+A, a checkable window-menu item and System Settings → KWin Scripts toggle it. Node contract plus a private KWin 6.8.3 native proof (exact halves/quarters; forced-off negative). Open: KWin native tile objects so neighbours resize together, a Snap-Layouts-style picker on the maximise button, frames (Aurorae corner, title-bar density) tuned to cells and scale, tablet rules (two cells at most, follow rotation), and physical multi-monitor/touch acceptance | Two/three/four real programs arrange on the installed V3 in landscape and portrait, with neighbours resizing together, keyboard and touch, and Arabic and English; no window is squeezed below its minimum. |

## P3 — Trustworthy assistant

| ID | Outcome | Current boundary | Required acceptance |
| --- | --- | --- | --- |
| P3.1 | Make provider setup self-diagnosing | Nov14 recorded PC-voice key/config/model binding and offline-Echo input fixes retain original REST401/Live refusals; a later credential REST200/both Live setups and synthetic-text audio pass in the private receipt. Owner speech/recognition/audible reply is deferred, and clean-account quota/network/cancel plus signed installed acceptance remain open. Existing Brain diagnosis separates configured/answering state without exposing credentials; no new provider/key or auth policy is selected by this audit | Separate missing/invalid key, billing/quota, rate limit, outage and network failure without secrets. |
| P3.2 | Stream chat responses and show the answering model/provider in human language | Open / acceptance not complete | Streaming first-token/answer-model UI, cancellation/retry and real provider failure. |
| P3.3 | Native fixed tool schemas and measured action choice | Implemented/delivered within recorded scope; wider acceptance remains | Valid executor schemas, free action cases in Arabic/English on second model and machine. |
| P3.4 | Approval cards, cancellation and execution readback | Implemented/delivered within recorded scope; wider acceptance remains | Real owner approve/cancel, job end and subsystem readback; failed steps never become success. |
| P3.5 | Add free-provider health and bounded failover | Open / acceptance not complete | Zero-price policy, bounded cooldown/failover and no implicit billed route. |
| P3.6 | Add optional, redacted device context | Open / acceptance not complete | Opt-in redacted context with inspectable payload and no private paths/keys. |
| P3.7 | Make task completion evidence-based | Source93ea210d removes false completion: actual private bwrap exit0/Git then exit7 and pending requirements formerly became completed.13 runtime controls and3 executed old failures pass; finished turns now pause for review, concurrent cancel/failure authoritative. Full semantic step-evidence contract, native review/continue and signed delivery remain open | Task outcome tied to every required step; cancellation/failure cannot claim unexecuted work. |
| P3.8 | Read-only redacted inspection before actions | Implemented/delivered within recorded scope; wider acceptance remains | Closed read grammar, redaction/caps/timeouts and shared production inspector rules. |
| P3.9 | Owner decision on model-written host commands | Open / acceptance not complete | No product model-generated shell is added without a separate explicit product decision. |
| P3.10 | MoOS playbooks using existing tools | Implemented/delivered within recorded scope; wider acceptance remains | Every playbook names supported schema tools/arguments; no free command capability. |

## P4 — Application lifecycle

| ID | Outcome | Current boundary | Required acceptance |
| --- | --- | --- | --- |
| P4.1 | Unify every install/update/remove request behind Mo Store | Existing Store remains the single lifecycle owner. Nov18 independent App Drop removal reuses its bounded active-tree guard before any deletion; native old5 failures/fixed66 tests and six localized catalogue/indexed/file job controls pass. [Current proof](reviews/2026-11-18-appdrop-active-removal.json). Prior packet-order/updater/signal and Windows portable-data corrections remain in their receipts; the historical Remote block is resolved. Full App Drop lifetime lease, GUI/PR/image/signed acceptance, Code canonical identity durability, native Arabic Windows save and public API lifecycle acceptance remain open | One lifecycle authority, stable job IDs, data-preserving remove, cancelled/failed state and measured readback for every adapter; versioned API authorization/backward-compatibility controls. |
| P4.2 | Audit desktop-app permissions and prefer portals | Oct29 source correction: actual resolver selected Flatpak/sandboxed for AppImage; format-scoped adapters and App Drop sandboxed=false now agree with existing truthful Store labels/consent. Old failure,32 resolver tests and private native launcher/synthetic file-access proof pass. Complete source qualification, signed delivery and broader portal journeys remain open | Distinguish extraction isolation from running-app permissions; truthful capability readback and actual file/camera/screen/print allow/deny/cancel without broad grants. |
| P4.3 | Turn Windows compatibility into a per-app runner product | Combined source retains 20 reviewed publisher-pinned Windows recipes and their existing private render evidence. The six unqualified local additions are preserved in Git history, not offered as proven apps. Ten full native lifecycle journeys remain open. Nov4 V3 Notepad4 26.08r6282/Wine11.20 opens and edits Arabic/Latin; Arabic Save/close labels remain clipped while temporary English labels render. Save target/focus changed unexpectedly; keep the actual saved file and unknown cause, no further global input. Native full save/reopen/update/remove acceptance remains failed or untested. [Data and runtime scope](reviews/2026-11-04-windows-portable-data.json). | Ten Windows apps with isolated prefixes and install/launch/reopen/update/remove evidence. |
| P4.4 | Turn Android compatibility into a per-app product | Source has46 recipes, native boot/property and scoped Markor/calculator rendering evidence. Oct28 V3 calculator arithmetic/maximize passes. Oct29 normal Alt+F4 removes its actual window and the canonical desktop entry reopens a new one; full-desktop composition confirms its global1536x810 root is transparent around the portrait app. Native sizing, persistence, switching, cold-start endurance and ten complete journeys remain open. Nov3 installed1119 canonical cold launch, native keyboard7×8=56, Alt+Tab away/back and normal close/new-window reopen pass; pointer arithmetic remains unaccepted and APK version/history/resize/endurance remain open. The review restored its originally stopped session. | Ten version-pinned Android apps; visible content/input/switch/resize/reopen, files/clipboard/audio, on-demand lifecycle and separately measured GPU fallback. |
| P4.5 | Publish a generated compatibility matrix | Source generator uses the Store sanitization, architecture, engine and installability rules for all 264 entries. JSON and AR/EN text distinguish recipe availability from unassessed application testing, include pinned recipe versions and NVIDIA-only software graphics. Eleven controls pass; old generator fails all eleven. Signed delivery and published per-app lifecycle evidence remain separate. | Generated version/edition/architecture/GPU compatibility matrix, including unsupported, unavailable and untested cases; evidence for the ten-app Linux reference suite as well as Windows/Android, with tested versions and invalidation on relevant input changes. |
| P4.6 | Consent-based App Drop for files | Existing consent/extraction/launcher and active-update guard remain authoritative. Nov18 removal now refuses observed cwd/exe/argv/maps users or unavailable inventory before tree/launcher/receipt/menu mutation; exact old5 failures, fixed66 App Drop tests and six translated Store-route failures pass. [Current proof](reviews/2026-11-18-appdrop-active-removal.json). No owner app removed. Concurrent launch/open-only references, full lifetime lease, GUI/PR/image/signed/ARM acceptance and arbitrary in-tree personal-data retention remain separate | Real magic, sandbox extraction, default-No consent, safe launchers and all entry paths. |
| P4.7 | Native Store picker/drop through App Drop | Implemented/delivered within recorded scope; wider acceptance remains | Actual QML picker/drop delegates to App Drop, valid local files, refusal/cancel and Store job. |

## P5 — Hardware and performance

| ID | Outcome | Current boundary | Required acceptance |
| --- | --- | --- | --- |
| P5.1 | Hardware qualification lab | Nov16 V3 installed1162 has actual bound SMOCF05 and SensorProxy accelerometer. Source successor avoids DDC on a validated connector-owned internal eDP backlight;22 controls retain external, malformed and missing-bus failures. V3’s native adapter now completes with a private runtime cache on mixed displays. SMBus/EFI warnings and earlier USB4/fingerprint faults remain explicit. Native luminance/hotplug/suspend and Home Assistant acceptance remain open; no reset or speculative firmware change | GPU/audio/network/Bluetooth/camera/storage/firmware records across actual hardware; distinguish host hardware from rootless home-hub integration faults. |
| P5.2 | Laptop policy | Nov18 V3 remains signed1162/stock7.3.3 with preserved rollback. Historical Nov11 balanced-battery/MoKernel and BIOS1.06 evidence is scoped to that workload, not fresh battery or suspend acceptance. Three-class policy, two suspend cycles each, endurance and repeated boots remain open; no profile or firmware changes in this audit | Three laptop classes, lid/battery/brightness/power and two suspend cycles each. |
| P5.3 | Touch/tablet policy | Nov23 plan: with the keyboard detached (KWin TabletModeManager), show Plasma Keyboard only in tablet mode (KWin's virtual-keyboard visibility option, Plasma 6.7+). Resize the focused window rather than cover it, and hide the keyboard and return to the desktop when a keyboard is attached. Qualify each step on the V3's actual detach event before shipping a default. Nov16 recorded installed7.3.3 SMOCF05/accelerometer and owner-confirmed four-direction rotation at1.45 after exact temporary normalized-key alias/cache. User retains tablet-only; detached transition lacks native capture. Nov18 still boots signed1162 with eDP disabled and availability metadata unresolved. The source alias is merged; its old x86 cycle later refused picomatch, and current x86 refuses stock7.3.4 sensor input. Signed successor/live-copy retirement, module-key enrollment and physical touch/suspend/pen acceptance remain open. [Live proof](reviews/2026-11-16-v3-live-rotation.json) | Actual touch/tablet targets, keyboard/rotation/gestures/stylus and ≥44px controls. |
| P5.4 | Performance budgets per hardware tier | Historical active-workload samples and local index repairs are retained in PROJECT_STATE/evidence; they are not controlled current idle or comparative OS benchmarks. Establish comparable baselines before choosing optimization work | Record workload, power/thermal state, background work, sample count/duration and refresh rate; compare cold/warm launch p50/p95, frame misses, boot, PSS/CPU/wakeups, battery and mixed-engine load. Declare tolerances before the change, repeat against the same baseline and reject material regressions in another critical metric. |
| P5.5 | Cloud desktop efficiency | Implemented/delivered within recorded scope; wider acceptance remains | Efficient cloud desktop plus actual private files/photos/IDE access, phone background and off-host restore. |
| P5.6 | Storage lifecycle | Earlier42GiB local OCI commit exhausted disk and crashed Chrome/ChatGPT; real failure/unsaved-state boundary preserved. Scoped build cleanup recovered owner app units without profile deletion. Oct18 owner-delegated retirement removes44,583,870,472 file/cache bytes after cold-success retirement of the1,913,401,344-byte old derived index; superseded generic image+2 exclusive parents yields separately observed3,677,118,464 writable bytes; Bazaar/Chess/temporaryNotepad4 removed with data/prefixes retained. Sources/dirty trees/full bundle/SDKs/databases/17 containers/current signed ISO/rollback survive. About83.5GiB free after new boot/readback. New guarded full image passes60GiB/5GiB preflight and8GiB/1GiB continuous floors. Private helper is not shipped low-space protection; durable build/cache retention/recovery and3 lint warnings remain open | Headroom, cache/log bounds, low-space recovery and cleanup that never removes owner data. |
| P5.7 | Qualify kernel policy and driver transitions | PR311 pins the exact composed-base7.3.4 vmlinuz66473624 while retaining original signed RPM95b80a8c and complete OCI layer/manifest evidence. Executable/vendor/core/transport invariants remain in its proof; production admission keeps exact complete bytes. V3 boots signed1162/stock7.3.3. Final aggregate native/image/signed/installed transition remains pending; no policy/performance claim | Kernel/driver readback and measured frame/audio/CPU/RAM policy; actual daemon monitoring after signed boot; sustained frame/audio latency under bounded pressure on qualified weak tiers, never an uncontrolled OOM on the owner's workstation. |
| P5.8 | Qualify Wayland and compositor lifetime | Nov11 native control-launch old-dead/fixed-alive and actual immutable Arabic Settings journey pass through canonical app ownership; finite early0/7/refusal controls retained. Same30 display failures remain fatal with unavailable-journal refusal. Full source passes0/1058.893s with frozen inputs; signed acceptance pending. See docs/reviews/2026-11-11-control-launch-display-proof.json. Open / acceptance not complete; Oracle .752 retains bootupd metadata/accountsd SELinux warnings, while bootloader update returns success/latest and no unit fails | Portal consent/revocation/restart, output/scale/hotplug, clipboard/input and long session-return soak; review native SELinux warnings without disabling enforcement or guessing labels. |

## P6 — Long-term release trust

| ID | Outcome | Current boundary | Required acceptance |
| --- | --- | --- | --- |
| P6.1 | Resolve immutable base inputs once per release | x86 source pins the reviewed manifest for all three editions and records it in each candidate receipt. Signed matrix readback and ARM remain open. | Immutable base inputs recorded once and consumed consistently by all same-architecture editions. |
| P6.2 | Produce SBOM and provenance for each image | Open / acceptance not complete | Exact digest-linked SBOM/provenance on a separately budgeted workflow, not release-critical disk exhaustion. |
| P6.3 | Security-release cadence for all editions | Open / acceptance not complete | The cadence of release cycles is the security cadence of MoOS: schedules only build candidates. Triage upstream advisories daily; target a qualified cycle weekly and start urgent affected-input qualification within24h. Publish affected editions, mitigation and delivery status; an unproven candidate never bypasses gates to meet a deadline. |
| P6.4 | Add staged rollout and release health | Open / acceptance not complete | Staged rings, halt/rollback criteria and actual field release health. |
| P6.5 | URL, Remote, AI and diagnostic security boundaries | Implemented/delivered within recorded scope; wider acceptance remains; the integrated audit cycle is signed/promoted. Oct17 open Dependabot/secret alerts are0; Code Scanning returns no analysis (404), so static-analysis acceptance is unproven | Auth/UID/URL/PIN/upload/secret boundaries and failure controls; native dependency advisories refuse release. |
| P6.6 | Establish support lifecycle and migration policy | Open / acceptance not complete | Published support/upgrade/rollback/EOL policy plus clear licences, attribution and official identity. |
| P6.7 | Reviewed Plasma seams before upstream transitions | Nov18 V3 boots signed1162 with Plasma/KWin6.8.3 and fixed native QtQuick6.11.2-3.1; earlier Qt/KWin old/fixed/seam/kernel controls remain in their receipts. Current build transition is stock7.3.4 plus composed-base EFI signature: PR308 must qualify exact bytes without widening gates. Canary libkgapi/kio-gdrive ABI refusal, physical hotplug/screen-removal and new-architecture/input acceptance remain separate | Actual matching stack, registered seams and native controls, complete native SDK/image, signed boot and installed acceptance on each architecture; unknown inputs refuse, never widen pins to bypass a failure. |
| P6.8 | Separate reviewed next-base transition lane | Open / acceptance not complete | Reviewed next-base packages, all native seams/boot/apps/identity gates and migration/support qualification. |
| P6.9 | Native user/developer participation | Beta integrated/promoted in .1022/.749; native launch/shutdown and ARM D-Bus controls pass, plus 34 API/11 native and actual Wayland/Oracle TLS flow. Both hosts boot delivered client bytes; actual .1022 native capture/shutdown passes and Oracle public health is ready. Capture retains Qt/portal-registration warnings; the recovered QApplication picker correction passes source native Arabic/English cancellation and physical Wayland readback; its signed installed selection/upload flow still needs acceptance. Branded DNS/onboarding/recovery/full moderation UI/preferences/endurance remain open | Real authenticated service/client, private image attachments, account isolation and bounded uploads, admin moderation, retry/offline and promoted-release notifications; no secrets or automatic screenshots. |

## Development-machine profile

The physical PC is a MoOS engineering station. Its setup must be reproducible,
not an undocumented pile of host changes.

The first slice is implemented: `just workstation-check` runs
`scripts/setup-development-machine.sh --check` on the host, including when
invoked from VS Code Flatpak. It reads signed-origin state, real `/var` space,
tool paths, native SDK availability, KVM access and redacted GitHub readiness.
It installs nothing and does not launch apps. A successful inventory is not a
successful SDK build. `.vscode/extensions.json` carries the shared editor
recommendations; machine-specific paths remain local.

The [October 14 workstation audit](WORKSTATION_20261014_AR.md) adds actual
QML old/fixed/live-startup evidence, .NET host/Flatpak Arabic execution,
C++/Go/Rust/Java builds, and native Flutter analyze/test/Linux-build evidence.
The same four MCP servers pass protocol/call checks; Codex and VS Code local
registration is recorded separately from active-session discovery. Preserve
the original failures, private backups and the compatible GitHub extension.
All optional extension flows, subscriptions/quotas and the complete auditable
cross-machine provisioning profile remain acceptance work, not green by inventory.
One existing live Island first-token probe timed out during a repeated native
gate; 15 private diagnostic trials passed. Component completion precedes model
readiness, but the failure's cause is unproven. Preserve the failed log and
investigate without weakening the gate or claiming a product correction.

The optional [analysis-tools profile](../scripts/workstation/analysis-tools/README.md) now preserves REA6.7/Ghidra12.1.4 with complete npm pins, official archive checks, existing SDK reuse and exact private launcher backups. Native canonical CLI/MCP fixture open/analyze/close and read-only installed checks pass. Fresh extraction/npm-ci, canonical function analysis and unchanged-file installer rerun pass, with temporary test payloads retired. Its earlier direct SDK protected-process cleanup refusal is retained as unqualified. Final maintained source gates remain required before integration. This adds no OS payload or client credentials.

The remaining provisioning slice must:

- install editor/SDK/debug tools in user sandboxes or Toolbx/Distrobox-style
  development containers where possible;
- configure Git and GitHub authentication interactively without storing tokens
  in the repository;
- install QEMU/KVM, image, accessibility, performance and network-debug tools
  through an auditable profile;
- verify Podman, `just`, Flutter/MoPlayer, .NET/MoRemote, QML and Python gates;
- keep the report free of credentials and private configuration;
- be idempotent and support `--check` without mutation.

Do not layer compilers onto the immutable host merely for convenience. Do not
put API keys in `.env`, committed config, shell history or test fixtures.

Performance work starts with repeated measurements, not RPM size guesses.
Oracle A1 and the NVIDIA workstation share the development source; boot totals
and autostart choices belong to the measured device. Read PROJECT_STATE.md and
the current audit for baseline, workload and exact evidence. P5.4 requires repeated cold
boots and an actual idle interval; P5.6 requires bytes/headroom and reverse
dependencies before payload removal. SDKs remain in development environments.

## Documentation policy

- `README.md`: stable entry point and repository workflow.
- `PROJECT_STATE.md`: current measured state, normally under 200 lines.
- `docs/DEVELOPMENT_PLAN.md`: this plan and task status.
- `RELEASE.md`: release contract.
- `docs/AGENT_GUIDE.md`: operational traps that remain true.
- Component-local documents: only live architecture or operating instructions.
- Git history: incident diaries, old plans, rejected visuals and screenshots.

No completed task is appended as a narrative. Replace the old state with the
new measured state. Evidence generated by CI belongs in the workflow artifact;
only a small canonical fixture belongs in Git when a test consumes it.

## Sources

1. KDE Community, [Plasma 6 release schedule](https://community.kde.org/Schedules/Plasma_6), accessed 2026-09-13.
2. KDE, [Plasma 6.7.5 release information](https://kde.org/info/plasma-6.7.5/), 2026-09-08.
3. bootc project, [Managing upgrades and rollback](https://bootc.dev/bootc/upgrades.html), accessed 2026-09-13.
4. systemd project, [Automatic Boot Assessment](https://systemd.io/AUTOMATIC_BOOT_ASSESSMENT/), accessed 2026-09-13.
5. Flatpak project, [Basic concepts: sandboxes and portals](https://docs.flatpak.org/en/latest/basic-concepts.html), accessed 2026-09-13.
6. Flatpak project, [Introduction and packaging boundaries](https://docs.flatpak.org/en/latest/introduction.html), accessed 2026-09-13.
7. Android Open Source Project, [Virtual A/B overview](https://source.android.com/docs/core/ota/virtual_ab), accessed 2026-09-13.
8. KDE Developer, [Plasma themes and plugins](https://develop.kde.org/docs/plasma/), accessed 2026-09-13.
9. Qt, [SpringAnimation](https://doc.qt.io/qt-6/qml-qtquick-springanimation.html) and [Behavior](https://doc.qt.io/qt-6/qml-qtquick-behavior.html), accessed 2026-09-13.
10. KDE, [KNotification configuration implementation](https://github.com/KDE/knotifications/blob/master/src/knotifyconfig.cpp), accessed 2026-09-13.
11. KDE Community, [Plasma 6 release schedule](https://community.kde.org/Schedules/Plasma_6) (6.8: beta 2 2026-09-24, release 2026-10-14; 6.9 release 2027-02-23), accessed 2026-09-24.
12. David Edmundson, [EX-11: Prepping for Plasma's last X11-supported release](https://blog.davidedmundson.co.uk/blog/596/), and Phoronix, [KDE Plasma 6.8 will go Wayland-exclusive](https://www.phoronix.com/news/KDE-Plasma-68-Wayland-Exclusive), accessed 2026-09-24.
13. Fedora Magazine, [Announcing Fedora Linux 45 Beta](https://fedoramagazine.org/announcing-fedora-linux-45-beta/) (final target 2026-10-20, Plasma 6.7), accessed 2026-09-24.
14. Plymouth, [`ply-boot-splash.c` on `main`](https://gitlab.freedesktop.org/plymouth/plymouth/-/blob/main/src/libply-splash-core/ply-boot-splash.c) (`ply_boot_splash_free()` still leaves `on_new_frame` armed), read 2026-09-24.


Primary-source decisions refreshed2026-10-28 are linked beside each recommendation
in [Upstream selection](../skills/moos-engineering/references/upstream-selection.md).
Older dated references above explain historical transitions, not current version
selection. Earlier Oct15–17 narratives remain in Git and their evidence receipts;
current status belongs only to the active batch and P-rows above.

Additional adapter sources retained from the Oct17 review:
[Flatpak lifecycle](https://docs.flatpak.org/en/latest/using-flatpak.html),
[F-Droid signed indexes](https://f-droid.org/docs/All_our_APIs/),
[F-Droid APK signing](https://f-droid.org/en/docs/Signing_Process/),
[Waydroid properties](https://docs.waydro.id/usage/waydroid-prop-options),
[systemd service lifetime](https://github.com/systemd/systemd/blob/main/man/systemd.service.xml)
and [transient services](https://github.com/systemd/systemd/blob/main/man/systemd-run.xml).

Nov8 primary-source comparison: [Plasma6.8.2 changes](https://kde.org/announcements/changelogs/plasma/6/6.8.1-6.8.2/),
[GNOME51](https://release.gnome.org/51/) and
[COSMIC epoch1.11.0](https://github.com/pop-os/cosmic-epoch/releases/tag/epoch-1.11.0).
Prioritize actual keyboard/modal focus, finite reduced motion, touch and
per-device GPU proof in MoOS's existing native owners. Release notes inform
selection; delivered MoOS behavior still requires its own installed evidence.
