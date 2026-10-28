# MoOS development plan — current execution backlog

Updated 2026-10-28. This is the single execution backlog. `PROJECT_STATE.md`
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

The current release batch is Meyar/UI142 plus the native appearance library.
Exact15a source checks, full local image and32-file/generic-font readback pass.
The publisher's mixed Plasma6.8.1/6.8.2 inputs correctly refused x86/canary.
Sourcea054 reviews exact6.8.2 sources and13 seams, retains native backend changes
and14 unchanged prepared frontend files, and passes lock positive/broken/restored
controls. Its frozen full source check passes0/954.016s and complete local image
passes0/2787.051s, with32 exact files, generic Meyar matches and6.8.2 package
readback. Repository, x86, ARM and canary CI all pass on a054. The current
engineering-documentation revision requires its own source checks; signed
four-edition delivery, physical acceptance and local-copy retirement remain open. Reuse active run IDs
and actual current results before dispatching; these sentences are not a ready
release flag. [Source/native scope](reviews/2026-10-27-meyar-family-native-proof.json),
[6.8.2 checkpoint](reviews/2026-10-28-plasma-682-source-checkpoint.json).

Physical V3 remains signed1107 with1100 rollback and pinned1078 recovery.
Earlier138 signed release and its exact native acceptance are recorded in
[delivery](releases/2026-10-26-ui138-signed-stage-proof.json) and
[installed proof](releases/2026-10-26-ui138-v3-native-proof.json). Current personal
settings and development overrides need current readback; do not force an older
Bloom snapshot over a later user choice.

Keep these real gaps visible: ordinary new-digest authentication/account switching,
earlier greeter screenRemoved crashes, Android native sizing/window lifecycle,
USB4 controller timeouts, tablet rotation/pen/suspend, charge-limit uncertainty,
accessibility/phone/endurance and broader app compatibility. Oct28 calculator
pointer arithmetic and internal maximize rendered correctly on the V3; that does
not close independent native resizing, close/reopen or ten Android journeys.
The owner rejected earlier component-only polish as a whole-desktop redesign;
retain that feedback when evaluating the next native visual batch.
[Appearance library](reviews/2026-10-26-kde-library-native-proof.json),
[earlier native failures](reviews/2026-10-21-native-acceptance-followup.json),
[hardware scope](hardware/V3_20261019_AR.md).

Earlier qualified/failed checkpoints live in their evidence documents and Git.
Do not execute an old dated “active slice” as a second queue. Existing P0–P6
rows below retain their own acceptance boundaries; a historical success must be
rechecked when its relevant installed bytes, hardware or engine inputs change.

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

Boot, security and data-loss regressions preempt the queue. Otherwise use the
owner's current priority below. Milestones group deliverable outcomes; P0–P6
remain the only detailed task IDs. Already delivered source is tested and
improved through its owner, not rewritten as missing functionality.

| Order / milestone | Outcome and implementation focus | Rows | Exit evidence |
| --- | --- | --- | --- |
| 1 · M0 current delivery | Finish Meyar/appearance/Plasma qualification and deliver the coherent batch | P0.1–P0.2, P0.6, P2.5, P2.8, P6.7 | Full current image/CI, signed3×QCOW2+offline ISO+ARM proofs, promotion and physical font/UI/readback; local overrides retire by recorded bytes |
| 2 · M1 daily Arabic workspace | Refine one coherent desktop and typography journey; in parallel qualify one daily app per engine through Store and native launcher | P2.3–P2.5, P2.7–P2.10, P4.1, P4.3–P4.4, P5.4 | Installed Arabic/English whole-workspace review, file/clipboard/input journeys, reduced-motion/accessibility and baseline performance; owner feedback recorded |
| 3 · M2 first run and M3 integration | Complete onboarding, login/lock/power, Settings/Store/Mira and shared jobs/API | P1.6–P1.7, P2.1–P2.2, P2.12, P2.16, P3.1–P3.7, P4.1–P4.2 | Clean/upgraded/offline profiles; actual authentication, job cancel/retry/failure/readback, preferences and data survive update |
| 4 · M4 compatibility and hardware | Expand the three app suites and qualify device/tablet/GPU/performance tiers | P0.3–P0.5, P4.3–P4.5, P5.1–P5.8 | Per-version/architecture/GPU matrix, ten Windows+ten Android+ten Linux journeys, real tablet input/rotation/suspend, measured performance and recovery |
| 5 · M5 sustainable product | Reproducible inputs, security cadence, staged rollout, support and migration | P6.1–P6.6, P6.9 | Proven rollout/halt/recovery, digest-linked provenance, support scope and maintainer/user documentation |

Run security/Plasma-transition work whenever its input changes; P6.7 is a
recurring qualification lane, not a deadline for an already released version.
The detailed scope of a blocked device test does not block independent native
UI/app work. While a frozen candidate runs, work on disjoint source with one
integration owner; never mutate its inputs or count later changes as qualified.
Each completed milestone uses the existing M0 release contract; signing,
identity and recovery are present throughout, not postponed to M5.

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

ابدأ من هذه الخطة ومن الحالة الفعلية، ولا تنشئ خطة موازية أو تعِد كتابة المكوّنات
الموجودة. اقرأ `AGENTS.md` و`PROJECT_STATE.md` ومهارة الهندسة، ثم اتبع الآتي:

1. حدّث قراءة Git والـPR والعمليات الجارية قبل أي تغيير. الدفعة الحالية في
   [PR275](https://github.com/moalfarras-sys/moos-image/pull/275)؛ أدلةa054 تخص
   ذلك المصدر فقط. اقرأ SHA الحالي والبوابات الفعلية، واحفظ تغييرات أي جلسة أخرى.
2. تحقّق من الجهاز الجاري والـdigest والـrollback وWayland والمقياس والمسارات
   المحمّلة. جهازV3 كان على1107 عند إعداد التسليم؛ هذا مرجع لإعادة القراءة وليس
   أمرًا لاسترجاع إصدار أو إعداد شخصي قديم.
3. أغلقM0 أولًا: بوابات المصدر الحالي، دمج الدفعة بعدCI، ثم دورة الإصدار الحالية
   وفق `RELEASE.md` دون تكرارrun قائم. سجّل الـdigests وإثباتات الإقلاع والترقية
   منفصلة. تحديث المصدر أو نسخ خط محلي لا يعني تحديث الأجهزة أو النسخ الأربع.
4. أثناء انتظار المرشح الثابت، قِسM1 في فرع مستقل: رحلة سطح المكتب العربي
   المتصلة ورحلة تطبيق واحد لكل محرك. ابدأ من عيوب Android المسجّلة في تغيير
   الحجم والإغلاق/إعادة الفتح، ومن قبول الخط في المحرر والترمنال. لا تستبدل تطبيقًا
   فاشلًا بتطبيق أسهل ثم تحذف الفشل. لا تغيّر مصدر المرشح الجاري.
5. عيّن لكل شريحة: رقمP، تفاعل المستخدم، المالك البرمجي الأصلي، العطل/القياس قبل
   التعديل، الملفات المسموح تعديلها، الاختبار السلبي، دليل النجاح وخطة الاسترجاع.
   يمكن توزيع فحص التطبيقات والواجهة والعتاد على مهام مستقلة؛ شخص واحد يدمج
   ويراجع النتائج. عدم توفر إيجنت أو أداة يُسجّل، ولا يُحسب مراجعة مكتملة.
6. أكمل ترتيبM1→M2/M3→M4→M5، مع تقديم عيوب الإقلاع/الأمان/فقد البيانات فورًا.
   ثبّت التطبيق والإصدار والمعمارية وGPU في مصفوفة التوافق، وأبقِ الحالات غير
   المجربة واضحة. لا تعلن دعم كل برامجWindows أوAndroid أو كل الأجهزة.
7. سلّم تغييرات قابلة للمراجعة مع نتائج الأوامر، sourceSHA، المكتبة/الخط المحمّل،
   runIDs وحالتها، الدليل المحلي الخاص، وشرط إزالة كل override. حدّث صفP والحالة
   الحالية فقط. تابع العمل غير المحجوب؛ لا تعيد البناء أو التنظيف لتجاوز فشل مجهول.

The next agent's first result is the exact current M0 qualification/merge state
and the next unblocked native journey, not a new design proposal. Reconcile this
handoff when the branch merges; keep milestone/task ownership in this file.

## P0 — Release qualification

| ID | Outcome | Current boundary | Required acceptance |
| --- | --- | --- | --- |
| P0.1 | Integrate the reviewed first-install repairs and create one candidate revision | Stable mechanism/artifact evidence recorded; preserve required gates | Exact candidate source, all integrated fixes and no local override counted as release. |
| P0.2 | Run generic, NVIDIA and cloud QCOW2 proofs plus offline ISO install/second boot | Complete at727e7b6c: signed build39120488031; disks39126559377/39126562830/39126565706; ISO39126568330 with all10 app close/reopen journeys; ARM39120345470. All first-attempt proofs and actual promotion pass. Previous Cloud/1069/diagnostic refusals remain preserved; no weakened ownership/75s close gate. New physical acceptance is separate | Three exact-digest x86 QCOW2 journeys, offline installed ISO and separate ARM two-boot proof. |
| P0.3 | Finish physical NVIDIA qualification | Open: signed .1042 native 55/0 + 55/0, 16 hashes and exact signed player bytes pass; one URI/finite seek/resource journey passes. Kernel -201 NVIDIA vermagic matches. USB-C UCSI -110 remains; broader physical acceptance is open. Offline ESP dirty-bit-only clone/live proof passes, 16 boot-file hashes preserved and both shared vfat mounts restored; the prior unmount mistake failed before fsck and has a private old/fixed topology control. New1072 boot preserves UCSI-110 and a QtQuick ListView/QQuickView teardown SIGSEGV through screenRemoved; exact root cause is unproven. Basic GPU/35 payload/54 selfcheck/55 postcheck/cold-search acceptance passes; isolate real screen-removal before changing greeter/graphics policy. Suspend/hotplug and recovery remain | Actual NVIDIA GPU, initramfs module, displays, suspend and clean recovery on qualified hardware. |
| P0.4 | Prove failed-update recovery | Open / acceptance not complete | Deliberate bad update, automatic/manual rollback and forward return without owner data loss. |
| P0.5 | Configure and accept free Mo AI on a clean account | Open / acceptance not complete | Clean-account provider setup, free route, reboot, cancellation and network/quota/key failures. |
| P0.6 | Promote only proven digests and update the physical PC | Four exact727e7b6c digests are signed/promoted (x861072/ARM807); native NVIDIA now boots1072 with signed1062 rollback,35 payload matches,54 selfchecks,55/0 postchecks and cold natural search pass. No failed units/display-start aborts. Two actual greeter/Remote handoff crashes remain explicit in P0.3/P2.17; this is not complete physical acceptance. No fresh Oracle807 installed claim | Promote only exact proven signed digests; separately verify installed stage/reboot/rollback. |
| P0.7 | Remove the intermittent `plymouthd` crash (ARM second boot; x86 first boot) | Implemented/delivered within recorded scope; wider acceptance remains | Pinned vendor Plymouth fix, old/fixed negative, exact final initramfs and actual boot visuals. |
| P0.8 | Make the ISO installed-reboot proof deterministic | Integrated at 1a73a4e0; .1022 exact offline ISO 38051456847 passes. CLDR/native AR/EN row clicks and mismatch negatives pass. Earlier .1018 private two password logins/cold boot pass 51/0 twice; offline serialization strict mismatch remains visible. Host batch reboot is separate | Repeated installed-ISO reboot with DHCP/SSH-channel evidence and console failures visible. |
| P0.9 | Run image-only gates before the merge | Stable mechanism/artifact evidence recorded. Native audit adds the omitted moplayer/** x86 PR trigger; the new input gate fails against the old workflow and passes fixed. ARM already watches the in-tree player. No publishing permission added; final x86/ARM image CI and signed cycle pass | PR generic image gates block real image failures; no signing/publishing from PR. |
| P0.10 | Gate NVIDIA persistence on a bound GPU | Stable mechanism/artifact evidence recorded; preserve required gates | Bound NVIDIA hardware and exact-kernel persistence/initramfs proof. |
| P0.11 | Give first-boot Flatpak setup a realistic finite timeout | Stable mechanism/artifact evidence recorded; preserve required gates | Finite realistic first-boot app setup timeout and actual ARM reboot. |
| P0.12 | Deliver the exact signed, installed-system-proven ISO through a stable anonymous download | Delivered .1046: full anonymous transfer/signature/hash/resumed ranges/exact sidecars at Oct14 17:58:53 UTC; paired public metadata, eight local/eight public native views and actual three redirects pass. .1026 retains immutable bytes through Oct16 12:00 UTC; .1018/.1022 retirement complete. Exact current local archive and signed rollback remain separate. Enclosing site-deploy exec 143 is preserved with independent exact active-byte acceptance | Repeat stable anonymous full signed ISO, exact size/hash and resumed ranges, sidecars and site readback for each release. |

## P1 — Reliability and first run

| ID | Outcome | Current boundary | Required acceptance |
| --- | --- | --- | --- |
| P1.1 | every migration records id/revision/outcome in one append-only ledger; the two-key wallet write is staged and renamed so an interruption leaves the original file; interrupted, repeated and clean-vs-upgraded fixtures in `tests/test_migration_ledger.py` | Stable mechanism/artifact evidence recorded; preserve required gates | Versioned idempotent transactional migrations; private durable outcomes and failure recovery. |
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
| P2.3 | One qualified Arabic/English locale authority | Arabic session works; new lock/Mira startup correction in source; cross-app unity remains | KDE/QML/GTK/Mira/MoPlayer/Flatpak selection after relogin/reboot; Arabic first, English supported. |
| P2.4 | Keyboard and screen-reader operation | Source Island correction passes 48 native Qt configurations and original-source controls; full shell/Orca acceptance remains | Real keyboard traversal/focus and Orca Arabic/English on all primary flows. |
| P2.5 | Visual, contrast, scale and reduced-motion matrix | Native audit reproduces a lost blur/clarity file update with the real producer. Atomic generation publication and unchanged finite event readback pass 480 native transitions, invalid/ambiguous/absent and broken-reader controls; THEME_REV/fingerprint=103 in source. Signed .1034/.763 delivery passes; Oracle native boot/bytes pass; full visual/scale/motion matrix remains open | 1080p–4K, 100–250%, Arabic RTL/English LTR, light/dark, reduced motion and measured readable contrast. |
| P2.6 | Asset reachability and removal of retired UI | Open: archived translucent-dialog prototype retained, but current-theme blur-off qualification/integration remains | Generator/runtime/test consumers proven; retain negative fixtures and required upstream notices; never restore obsolete generated assets over today's theme. |
| P2.7 | Horizon feedback, clock input and system sound | Open / acceptance not complete | Finite stable-hit feedback, reversal/hidden/reduced-motion proof, clock keys and actual event sound. |
| P2.8 | MoOS Bar, Search and Island as one shell | Island visible-context arrows, Return/Enter and retired-domain correction pass native isolated Qt and signed .1046/.775 qualification; [Actual installed inventories](releases/2026-10-14-running-shell-components.json) show one active Bar per station with one Brand/Island/clock and native KDE task/tray integration; keyboard/render/Orca acceptance remains | Native accessible Search/Island/Bar, keyboard escape, multi-context tabs and truthful lifecycle tokens. |
| P2.9 | User-visible MoOS identity on every surface | Implemented/delivered within recorded scope; wider acceptance remains | Unchanged identity gates plus actual login/boot/desktop/app surfaces; legal attribution preserved. |
| P2.10 | Readable text and glyph contrast on every palette | Open / acceptance not complete | All schemes meet role-specific contrast; actual glyph/card/pointer frames instead of token names. |
| P2.11 | Visible, bilingual update changes | Implemented/delivered within recorded scope; wider acceptance remains | Readable current entries and working routes, delivered update/notification readback. |
| P2.12 | One update surface for OS, apps and firmware | Open / acceptance not complete | OS image, Flatpak apps and firmware share truthful pending/failure/unsupported/finished states. |
| P2.13 | MoPlayer performance and server/stream compatibility | Native ARM installed MPEG4 plays and advances 2.93→8.07 s (~447 MiB RSS), but exposed direct-file live controls. Independent fix accepts encoded Arabic file URIs, finite local/explicit movie URLs and no catalogue records; 258 Flutter tests/native ARM build pass. Native source bundle proves 20 s MPRIS length/CanSeek, paused +5 s seek and rendered frames/controls; restored all-live factory fails the new test. Final local image/9 hashes, all PR CI and signed .1034/.763 delivery pass. Oracle signed .763 native boot/installed small MPEG4/seek/frame journey pass; wider server/hardware/codec/endurance acceptance remains | Installed playback/reopen/stop and memory on real server kinds, MAC portal, HEVC/interlaced samples. |
| P2.14 | Remote input, recovery and mobile/WAN video | Implemented/delivered within recorded scope; wider acceptance remains | Held-input ownership, decoded pictures, browser recovery and owner iPhone/cellular endurance. |
| P2.15 | Mira face, speech/rest and original portrait identity | Capture policy integrated/promoted in .1022/.749; both hosts booted with matching delivered hashes. Source/private-helper boundary and muted real USB pass; physical unmuted speech and long capture remain open | Both portraits retained; single mouth, real voice/pause/idle/hidden/reduced-motion readback; 11 private-process boundary tests, 45 controller tests, real muted USB with zero captures/overruns and three synthetic unmute/mute cycles. Signed installed delivery passes on both hosts; physical unmuted voice/device acceptance remains open. |
| P2.16 | Shared login, lock and power experience | Delivered within earlier recorded scope; private Arabic lock/power/wrong/correct-password controls pass, login buttons remain English. PR227 maintenance scoping is integrated through PR228 with both native PR image CIs, owner/greeter conditions, 17 theme tests and final local ARM/three unit hashes passing. Signed .1034/.763 delivery passes; Oracle native boot/bytes pass; ordinary-login/hardware acceptance remains; authentication stays upstream | Native greeters 640×480–4K@2.5, password refusal, multi-user, save/logout and accessibility. |
| P2.17 | Mo PC Remote before account login after reboot | Greeter KDE environment and actual three-group EIS keymap correction is signed in .1044/.773 and retained in .1046/.775. Source/29 controls and actual device old/fixed proof pass; owner ordinary password login/account handoff passed on .1044, and .1046 now boots with 54 selfchecks/2 notes, 55 post-update/0 failures and 19 hashes/player. Temporary bundle retired after replacement/no-holder proof. Oracle pre-login remains off; repeated native wrong/correct PIN/password/cold-boot, phone/WAN/multi-account/endurance acceptance remains  Native1072 additionally measures first-owner localhost8765 binding before old greeter Remote stops, one SIGABRT/managed restart then active; bounded account-owned startup/handoff controls and qualified repair remain, not a reason to change PIN/PAM or steal another account listener. | Explicit opt-in, authenticated PIN/trusted-device/private TLS; native greeter capture/input with upstream PAM and no saved account password; real wrong/correct PIN/password, bounded handoff/logout/account isolation; default-disabled/native NVIDIA and ARM reboot evidence. |

## P3 — Trustworthy assistant

| ID | Outcome | Current boundary | Required acceptance |
| --- | --- | --- | --- |
| P3.1 | Make provider setup self-diagnosing | Open / acceptance not complete | Separate missing/invalid key, billing/quota, rate limit, outage and network failure without secrets. |
| P3.2 | Stream chat responses and show the answering model/provider in human language | Open / acceptance not complete | Streaming first-token/answer-model UI, cancellation/retry and real provider failure. |
| P3.3 | Native fixed tool schemas and measured action choice | Implemented/delivered within recorded scope; wider acceptance remains | Valid executor schemas, free action cases in Arabic/English on second model and machine. |
| P3.4 | Approval cards, cancellation and execution readback | Implemented/delivered within recorded scope; wider acceptance remains | Real owner approve/cancel, job end and subsystem readback; failed steps never become success. |
| P3.5 | Add free-provider health and bounded failover | Open / acceptance not complete | Zero-price policy, bounded cooldown/failover and no implicit billed route. |
| P3.6 | Add optional, redacted device context | Open / acceptance not complete | Opt-in redacted context with inspectable payload and no private paths/keys. |
| P3.7 | Make task completion evidence-based | Open / acceptance not complete | Task outcome tied to every required step; cancellation/failure cannot claim unexecuted work. |
| P3.8 | Read-only redacted inspection before actions | Implemented/delivered within recorded scope; wider acceptance remains | Closed read grammar, redaction/caps/timeouts and shared production inspector rules. |
| P3.9 | Owner decision on model-written host commands | Open / acceptance not complete | No product model-generated shell is added without a separate explicit product decision. |
| P3.10 | MoOS playbooks using existing tools | Implemented/delivered within recorded scope; wider acceptance remains | Every playbook names supported schema tools/arguments; no free command capability. |

## P4 — Application lifecycle

| ID | Outcome | Current boundary | Required acceptance |
| --- | --- | --- | --- |
| P4.1 | Unify every install/update/remove request behind Mo Store | Shared backend/bridge/UI and264-entry catalogue are integrated; previous signed Linux/web/Windows/Craft journeys remain scoped evidence. The earlier ARM app-update unit draft was integrated in the later reliability batch; it is not a new missing installer. Full current-adapter cancel/retry/update/remove and public API acceptance remain | One lifecycle authority, stable job IDs, data-preserving remove, cancelled/failed state and measured readback for every adapter; versioned API authorization/backward-compatibility controls. |
| P4.2 | Audit desktop-app permissions and prefer portals | Open: App Drop registry says sandboxed while MO_STORE describes unsandboxed execution; trace the actual displayed/admitted capability before changing it | Distinguish extraction isolation from running-app permissions; truthful capability readback and actual file/camera/screen/print allow/deny/cancel without broad grants. |
| P4.3 | Turn Windows compatibility into a per-app runner product | Combined source retains 20 reviewed publisher-pinned Windows recipes and their existing private render evidence. The six unqualified local additions are preserved in Git history, not offered as proven apps. Ten full native lifecycle journeys remain open. | Ten Windows apps with isolated prefixes and install/launch/reopen/update/remove evidence. |
| P4.4 | Turn Android compatibility into a per-app product | Source has46 recipes, native boot/property and scoped Markor/calculator rendering evidence. Oct28 V3 calculator arithmetic/maximize passes; native sizing, independent close/reopen, cold-start endurance and ten complete journeys remain open | Ten version-pinned Android apps; visible content/input/switch/resize/reopen, files/clipboard/audio, on-demand lifecycle and separately measured GPU fallback. |
| P4.5 | Publish a generated compatibility matrix | Source generator uses the Store sanitization, architecture, engine and installability rules for all 264 entries. JSON and AR/EN text distinguish recipe availability from unassessed application testing, include pinned recipe versions and NVIDIA-only software graphics. Eleven controls pass; old generator fails all eleven. Signed delivery and published per-app lifecycle evidence remain separate. | Generated version/edition/architecture/GPU compatibility matrix, including unsupported, unavailable and untested cases; evidence for the ten-app Linux reference suite as well as Windows/Android, with tested versions and invalidation on relevant input changes. |
| P4.6 | Consent-based App Drop for files | Implemented/delivered within recorded scope; wider acceptance remains | Real magic, sandbox extraction, default-No consent, safe launchers and all entry paths. |
| P4.7 | Native Store picker/drop through App Drop | Implemented/delivered within recorded scope; wider acceptance remains | Actual QML picker/drop delegates to App Drop, valid local files, refusal/cancel and Store job. |

## P5 — Hardware and performance

| ID | Outcome | Current boundary | Required acceptance |
| --- | --- | --- | --- |
| P5.1 | Hardware qualification lab | Open: station USB capture overruns reproduced; Home Assistant Bluetooth/DHCP/duplicate entities and first-start protocol failure remain | GPU/audio/network/Bluetooth/camera/storage/firmware records across actual hardware; distinguish host hardware from rootless home-hub integration faults. |
| P5.2 | Laptop policy | Open / acceptance not complete | Three laptop classes, lid/battery/brightness/power and two suspend cycles each. |
| P5.3 | Touch/tablet policy | Open / acceptance not complete | Actual touch/tablet targets, keyboard/rotation/gestures/stylus and ≥44px controls. |
| P5.4 | Performance budgets per hardware tier | Historical active-workload samples and local index repairs are retained in PROJECT_STATE/evidence; they are not controlled current idle or comparative OS benchmarks. Establish comparable baselines before choosing optimization work | Record workload, power/thermal state, background work, sample count/duration and refresh rate; compare cold/warm launch p50/p95, frame misses, boot, PSS/CPU/wakeups, battery and mixed-engine load. Declare tolerances before the change, repeat against the same baseline and reject material regressions in another critical metric. |
| P5.5 | Cloud desktop efficiency | Implemented/delivered within recorded scope; wider acceptance remains | Efficient cloud desktop plus actual private files/photos/IDE access, phone background and off-host restore. |
| P5.6 | Storage lifecycle | Earlier42GiB local OCI commit exhausted disk and crashed Chrome/ChatGPT; real failure/unsaved-state boundary preserved. Scoped build cleanup recovered owner app units without profile deletion. Oct18 owner-delegated retirement removes44,583,870,472 file/cache bytes after cold-success retirement of the1,913,401,344-byte old derived index; superseded generic image+2 exclusive parents yields separately observed3,677,118,464 writable bytes; Bazaar/Chess/temporaryNotepad4 removed with data/prefixes retained. Sources/dirty trees/full bundle/SDKs/databases/17 containers/current signed ISO/rollback survive. About83.5GiB free after new boot/readback. New guarded full image passes60GiB/5GiB preflight and8GiB/1GiB continuous floors. Private helper is not shipped low-space protection; durable build/cache retention/recovery and3 lint warnings remain open | Headroom, cache/log bounds, low-space recovery and cleanup that never removes owner data. |
| P5.7 | Qualify kernel policy and driver transitions | Source adds ARM's missing vendor oomd-defaults, final-image guard and actual native-monitor readback in both disk boot proofs. Eight compose controls, native ARM package install, and bounded native negative/positive pressure controls pass on both stations (256 MiB cap; no kernel OOM; protected sentinel survives). Signed ARM .756 and NVIDIA .1026 are booted and prove actual system/native-user monitoring. System-wide recovery/weak-hardware frame latency remains open | Kernel/driver readback and measured frame/audio/CPU/RAM policy; actual daemon monitoring after signed boot; sustained frame/audio latency under bounded pressure on qualified weak tiers, never an uncontrolled OOM on the owner's workstation. |
| P5.8 | Qualify Wayland and compositor lifetime | Open / acceptance not complete; Oracle .752 retains bootupd metadata/accountsd SELinux warnings, while bootloader update returns success/latest and no unit fails | Portal consent/revocation/restart, output/scale/hotplug, clipboard/input and long session-return soak; review native SELinux warnings without disabling enforcement or guessing labels. |

## P6 — Long-term release trust

| ID | Outcome | Current boundary | Required acceptance |
| --- | --- | --- | --- |
| P6.1 | Resolve immutable base inputs once per release | Open / acceptance not complete | Immutable base inputs recorded once and consumed consistently by all same-architecture editions. |
| P6.2 | Produce SBOM and provenance for each image | Open / acceptance not complete | Exact digest-linked SBOM/provenance on a separately budgeted workflow, not release-critical disk exhaustion. |
| P6.3 | Security-release cadence for all editions | Open / acceptance not complete | The cadence of release cycles is the security cadence of MoOS: schedules only build candidates. Triage upstream advisories daily; target a qualified cycle weekly and start urgent affected-input qualification within24h. Publish affected editions, mitigation and delivery status; an unproven candidate never bypasses gates to meet a deadline. |
| P6.4 | Add staged rollout and release health | Open / acceptance not complete | Staged rings, halt/rollback criteria and actual field release health. |
| P6.5 | URL, Remote, AI and diagnostic security boundaries | Implemented/delivered within recorded scope; wider acceptance remains; the integrated audit cycle is signed/promoted. Oct17 open Dependabot/secret alerts are0; Code Scanning returns no analysis (404), so static-analysis acceptance is unproven | Auth/UID/URL/PIN/upload/secret boundaries and failure controls; native dependency advisories refuse release. |
| P6.6 | Establish support lifecycle and migration policy | Open / acceptance not complete | Published support/upgrade/rollback/EOL policy plus clear licences, attribution and official identity. |
| P6.7 | Reviewed Plasma seams before upstream transitions | Earlier6.8.1 signed delivery remains historical. Current exact6.8.2 source review passes13 seam digests,14 prepared frontend matches and native lock positive/broken/restored; complete a054 image and x86/ARM/canary CI pass. Signed boot/promotion and installed acceptance remain open. ARM keeps its separately qualified native provider; Qt6.12 is unqualified. | Actual matching stack, registered seams and native controls, complete native SDK/image, signed boot and installed acceptance on each architecture; unknown inputs refuse, never widen pins to bypass a failure. |
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
