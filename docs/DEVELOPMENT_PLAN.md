# MoOS development plan — current execution backlog

Updated 2026-10-20. This is the single execution backlog, not an incident diary.
Current measurements live in PROJECT_STATE.md; detailed audit evidence and
remaining boundaries are in [AUDIT_20261012_AR.md](AUDIT_20261012_AR.md). Git preserves prior waves.

The owner's ordered implementation and cross-device handoff are recorded in
[OWNER_EXECUTION_20261009_AR.md](OWNER_EXECUTION_20261009_AR.md). Its active slice
is reliability/release acceptance, before the remaining four milestones. The
new private feedback/optional public suggestions product is P6.9 below.

## Active delivery and acceptance batch

Oct20 checkpoint3708 passes full native source gate0/843.494s (2765 reported/14 conditional skips) and actual repository/Remote CI. Actual ARM image fails1/496.032s on post-transaction vendor tmpfiles authority drift, preserving unknown root-home state. x86 CI refuses unreviewed Plasma6.8.1 inputs. Active P0/P6.7 work: prove the changed authority before scoped cleanup, review exact signed6.8.1 sources/seams/authentication and native runtime controls, then repeat full image/final-head CI before a signed cycle. [Checkpoint](reviews/2026-10-20-final-3708-qualification.json).

Exact systemd259.10 `/root` authority variant is now reproduced old1/fixed0 with actual native tmpfiles and unchanged alias/authority;22 helper controls pass. Corrected full ARM image is next. Independent seam/login reviews match V3 held99269cc4; preserve its qualification freeze and wait for its merge before overlapping source integration. Installed prior signed ARM.816 passes56/0 postchecks in the actual graphical manager; it does not contain this batch.

Oct20 P0 compose unblock: merge8687010a without losing PR256 fixes, qualify the proven exact x86 SELinux alias correction (actual old1/fixed0,1357 policy hashes unchanged,18 controls), and qualify ARM/recovery private-HOME helper (18 process/source controls; actual vendor empty-state recreation/retirement passes). Preserve nonempty root-home refusal and original producer exits. Require full source/local image/final-head CI before one signed cycle; no claim about the actual unknown writer until image diagnostics. [Evidence](reviews/2026-10-20-integration-followup.json).

Oct19 P2/P5.1 integration PR256 combines PR253/current main without retiring owner refs.11 bounded groups repair Arrange/diagnostic truth, complete update units, ARM enumerator dependencies, Remote bind lifecycle and context hygiene; daily timer recurrence and vendor/confidence follow-ups have real native/process negative controls. Clean e3572bcd passes native full check865.835s (2706 reported/14 conditional skips), full local ARM imagec26fd056/986.234s and actual payload/service/updater/device-plan/Remote readback.9f PR ARM/x86 images and source/.NET/controller pass; ddbdfc1f final-head CI passes; merged-source requalification/signed delivery remain pending. Preserve prior full7eda wheel failure and no-compiler pill failure: later full check and six bounded sequential ar20/250% positives do not establish cause. New failure-only diagnostics retain180ms/all assertions; actual failed-invocation causality remains acceptance. After external Oct20 reboot Oracle boots.816 with.804 rollback; exact /etc compatibility retirement requires signed /usr replacement after boot. [Measured scope and explicit boundaries](AUDIT_20261019_AR.md).

Oct18 Oracle audit P4.1/P5.4/P5.6 on `codex/system-audit-20261018` / PR253: both missing ARM app-update pairs now run through the existing authority with delayed idle schedules and exact local compatibility files. Shared source and both builders supply/enable/verify the pairs;20 controls,16 real native network-condition cases and two private timer firings pass. Native full ARM image at2b12ad2f exits0 in11196.421s; actual unit hashes/modes/wants match, and the tightened gate passes inside that immutable image. Final native full source at05649cd0 passes875.904s with a clean stable fingerprint; native .804 postcheck passes56/0. PR ARM/generic-x86 images at2b12ad2f pass; exact-head CI/review for the merged verifier hardening is tracked in [PR253](https://github.com/moalfarras-sys/moos-image/pull/253). Official signed .807 is staged but .804 still runs; the patch is not signed/delivered. Keep exact /etc copies until matching signed /usr replacement and retirement proof, then installed postboot/app acceptance. The727e7b6c owner cycle completed without another dispatch. [Current evidence and remaining platform boundaries](AUDIT_20261018_AR.md).

V3 phase1 now has an actual signed1078 boot with1072 pinned rollback, direct fingerprint match, measured multi-touch, owner-accepted front/rear moving camera images, stereo speakers and speech. Retained microphone30% has0% clipping/−11.50dBFS peak in warmed speech. BIOS80% cap is owner-confirmed; observe the actual plateau. Native keyboard diagnostics need the topic absent-key correction, not an owner-config rewrite. External/hotplug acceptance belongs to the preceding boot; current external, pen and suspend remain acceptance. The separate greeter screenRemoved SIGSEGV and unboundSMOCF05 are unresolved. Appearance follows compatibility, using supported Plasma/KWin and shared MoOS Qt/Kirigami tokens. [Native phase1 evidence](releases/2026-10-19-v3-1078-native-phase1-proof.json).

Active login slice: retain either valid password or fingerprint, start the enrolled account's reader without an arrow, and prove fallback/cold login. The greeter-only generated PAM derivative moves sufficient unix before fprint without changing global stacks or vendor account/password/session rules. Earlier physical password-only and manually started fingerprint-only passed; the first automatic /run review timed out and owner reported a repeated reader after password. Audit attributes return to fingerprint, so fallback is not accepted. Actual QQuickView revealed a screen-lookup TypeError missed by the mock load; native old/fixed screen and request tests pass after correction. Exact signed SRPM source, unchanged auth/helper/daemon hashes, bounded root enrollment metadata and native RPM delivery are in the topic. Corrected physical no-arrow match now passes with owner confirmation and audit pam_fprintd; a distinct no-touch timeout/password-only attempt passes with audit pam_unix and no second reader. Complete full native check, full local image and exact-head PR gates before one signed release cycle and cold-login acceptance. A /run profile is not signed delivery. [Contract and retirement](../build_files/plasma_login/README.md).

P4.1/previous P5 delivery: PR255 merges finalf1fd1cf9 as18ba1a83 after full native/local-image/PR gates. Signed x86 build39265167668, all3disks/offline ISO/full ARM pipeline and x86 promotion39283856876 pass; independent production/cosign readback gives x861078/ARM816. V3 now actually boots1078, with1072 pinned. Four official WD19 updates persist after replug. Source/local/signed proofs belong to that delivered batch, not the new login correction. [Qualified cycle](releases/2026-10-19-v3-qualified-1078-cycle-proof.json). [Hardware scope](hardware/V3_20261019_AR.md).

The independent native development profile executes SDK/Flutter/QML/MCP and editor-container CMake/QML/C# journeys. Wallet/provider login remains owner-deferred. Antigravity's old live-subscription exit double-free reproduces; official watcher2.6.0 passes3native cycles/60events and installed-addon close0 with original bundle backup. Authenticated/editor/endurance acceptance remains open. [Measured profile](workstations/V3_NATIVE_DEVELOPMENT_20261019_AR.md).

Previous delivery: PR248–251 integrate at727e7b6c/tree22086a7e. Complete local image87e84381/native source checks pass; signed build39120488031, all3 exact-digest QCOW2 proofs, ISO39126568330 ordinary offline install/login/10 apps/second boot, ARM39120345470 and actual x86 promotion39129933686 succeed. Independent cosign/registry reads match all4 candidate digests: x861072/ARM807. Old Cloud and1069 ISO refusals remain evidence; new success keeps all original gates. Physical NVIDIA now boots1072 with signed1062 rollback:35 payloads,54 selfchecks,55/0 postchecks and natural cold search lifecycle pass. Broader coredump review retains greeter screenRemoved teardown and first-owner Remote bind collision; full native acceptance remains open. [Qualified cycle](releases/2026-10-18-qualified-1072-cycle-proof.json).

Current live repair/acceptance: new1062 boot7b01c656 retains18 display-start aborts despite no failed units (candidate postcheck54/1). Baloo had stale filesystem identity for the same HOME inode; automatic atomic-save/delete reproduced stale results. Preserve old derived index offline, rebuild only it, and retain cold-boot durability as acceptance. New186300-file index is idle/0 failed; automatic create/save/delete passes1.042/1.054/.525s. A bounded read-only identity check adds real old/broken CLI controls; native2672-case full check succeeds at68708f89. Owner cleanup removes42.67GB known obsolete/duplicate payloads plus a separately measured3.68GB local-image delta and two optional apps with data preserved. [Audit](AUDIT_20261017_AR.md), [evidence](releases/2026-10-18-search-cleanup-source-proof.json).

Historical Oct16 P0/P2.17 correction: native NVIDIA login was restored with a scoped copied Remote bundle after actual decoded camera output exposed incorrect v6 serial targeting and permitted video fallback. Source now chooses the correct ID/serial property, forbids fallback and bounds greeter crash recovery while preserving upstream authentication. Five native old/fixed/stop/success/exhaustion dependency controls and eight target/contract controls pass. Fresh local image/signed cycle, exact override retirement and phone/hotplug endurance remain required; no local override counts as delivery. [Evidence](releases/2026-10-16-remote-screen-target-source-proof.json). Store real-app additions/touch/lifecycle/task management continue independently on `feat/store-real-apps-touch-20261016`.

Current qualified source `e1ffacfa` (PR243–246) ships the 200-app Store, all
13 Craft apps, reviewed lifecycle/data/index/UI fixes, stable x86 Plasma6.8.0
and THEME_REV=106. Native repository gates and the complete local image with
63 immutable payload hashes pass. The complete first-attempt signed cycle
passes: build38816837919, disks38824574093/38824577430/38824580671,
ISO38824584100, ARM38824591685 and x86 promotion38829865381. Independent
registry/cosign readback matches x86 `.1062` / ARM `.792`.
[Qualified cycle and boundaries](releases/2026-10-16-store-qualified-cycle-proof.json).
Native NVIDIA now boots exact signed `.1062` with `.1046` rollback: ordinary owner login,63 hashes,54 selfchecks/2 notes,55 post-update/0 failures, Plasma6.8/GPU/app acceptance pass. Its later temporary Remote correction still needs signed delivery and phone acceptance. Oracle
has rebooted to exact signed `.792` with `.791` rollback and changed boot ID;
native graphical acceptance passes63 hashes,51 selfchecks/4 notes,55 post-update
checks/0 failures, no failed units, user-app update and a real Store window. The
owned postboot ordering-cycle failure and repair remain preserved. ARM keeps
qualified native Plasma6.7.5; native6.8 and Qt6.12 remain open. All audited refs,
original worktrees/dirty drafts and a verified full Git bundle are preserved.

M1/P2.4/P2.8 Island keys now avoid hidden tabs, synchronize selection/content,
activate Return/keypad Enter once and resolve disappearing domains. Forty-eight
native Qt component samples pass across AR/EN, light/dark, two/five contexts,
100/150/250% and normal/reduced; completed original-source 250% controls fail.
New M1 source recovers a lost first Mira task delivery with one coalesced delayed
real directory event, without idle polling or token resurrection. Old/fixed
native Qt controls and [62 control tests pass](releases/2026-10-14-mira-job-presence-proof.json); this does not establish the prior
intermittent Qt startup failure's cause. Full local ARM image and actual 20-file
readback now pass after an ENOSPC final-commit failure and exact obsolete-cache
retirement. Signed .1053/.778 promotion completed at `5745edd1`; independent
the historical Store review is now integrated in the qualified `.1062`/`.792` batch.
Next acceptance is native installed shell input/focus and screen-reader behavior.

P2.17 greeter desktop facts/actual matching EIS groups are signed in .1044/.773
and retained in the current images. Its full cycle completed. An HTTP 500 while
reading an already-dispatched proof was recovered by adopting exact existing
runs, never duplicate dispatch or rerun. Follow-up source now bounds metadata
GET recovery (three attempts, 30 s plus 5 s kill deadlines, 2/4 s backoff),
records created run IDs and refuses duplicate dispatch on unreadable build lists.
Fourteen executable controls, including restored-old failures, pass; mutations,
source/digest/attempt checks and promotion requirements remain unchanged.
Historical `.1046` NVIDIA readback: signed .1046 with .1044 rollback, boot ID
`d8a6ce1d-ca57-4680-9e5f-ef8118623b61`. Native graphical-owner checks pass
54 selfchecks/2 notes and 55 post-update/0 failures, all 19 hashes/player,
THEME_REV=104 and no failed units. Boot=32.381 s. The prior ordinary password
login and exact unused copied-bundle retirement remain scoped evidence.
[Native receipt](releases/2026-10-14-nvidia-1046-native-proof.json).
Preserve opt-in/PIN/private TLS/upstream PAM/default-off and the owner's flow.
Historical `.775` Oracle readback: signed .775 with .763 rollback. Native graphical checks pass
51 selfchecks/4 notes and 55 post-update/0 failures, all 19 payload hashes,
exact player and THEME_REV=104; one KDE Wayland compositor, boot=14.301 s.
The initial transient-container selfcheck failure and the subsequent owned
probe flag failure remain preserved; only the owned failed flag was retired.
Current failed units are empty and all four owner containers are healthy;
the initial failure's precise cause is unproven. Existing autologin is not PAM
acceptance. [Native receipt](releases/2026-10-14-oracle-775-native-proof.json).
New .775 direct/SSE and isolated Hermes synthetic replies pass; direct reported
cost=0, Hermes usage absent. Preserve signed rollback and the owner’s monitor.

Existing-account cloud JSON/SSE/free replies and isolated Hermes journeys pass
on both stations. Reported direct cost=0; missing Hermes usage is not zero cost.
Response-lifetime, Community API/native Qt pickers, finite MoPlayer controls and
URI/source gates remain delivered within their recorded scope. Broader
cancellation/stall/quota/voice/clean-account and hardware/application journeys
remain open in their rows. See [runtime evidence](AUDIT_20261013_RUNTIME_AR.md).

P0.12 public .1046 now passes complete anonymous download/signature/hash,
resumed ranges, exact sidecars, paired public metadata and eight local/eight
public AR/EN native browser views. Publication uses the existing independent
Static Assets/R2 host. [Delivery](releases/2026-10-14-public-download-proof.json)
and [site receipt](releases/2026-10-14-public-site-1046-proof.json) record the
exact source, successful boot/install/promotion runs and deployed versions.
Previous .1026 retains original bytes through Oct16 12:00 UTC; only a qualified
replacement permits expiry. Current .1046/local archive and signed rollback stay.
The site deployment's enclosing exec ended 143 after printing success; actual
public paired bytes/redirects/views independently pass. Cause remains unproven.
Website PR57's inert unsafe conversion scripts remain inert. Web/admin checks,
99 tests, dashboard build and 21 download boundaries pass; Android command
returns 127 because the repository invokes Windows gradlew.bat on Linux.
NVIDIA/Cloud first migration still needs its separately qualified journey.

The cadence of release cycles is the security cadence: nightly image-only
builds cannot deliver a base fix. P6.3 stays open until bounded, boot-proven
cycles keep every supported edition current. Oct15's separate native source
review qualifies exact x86 Plasma 6.8.0 packages/seams and retains the full
positive/negative greeter/logout controls. Native ARM 6.8 source rebuilding and
installed hardware acceptance remain P6.7 work; unknown inputs stay refused.

## Product acceptance

MoOS is Arabic-first, with English supported. KDE Plasma/KWin remain its engine;
MoOS owns identity, shared surfaces/defaults and fixed native control paths.
A complete product means a qualified support scope and real connected journeys:
boot/login, files/apps, sound/network, Settings/Store/Mira, update/rollback and
privacy. It does not mean universal compatibility or an absence of all defects.

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
   Bottles and first-run Flatpak install paths. Shared job lifecycle is still open. Desktop applications
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

The qualified `.1062`/`.792` catalogue contains 200 curated entries and all13
Craft apps, with architecture-pinned publisher downloads and reviewed lifecycle
authority. Catalogue/gate coverage is separate from connected per-app and
hardware acceptance; see
`docs/MO_STORE.md`.


**The owner's requirement, in their words:** MoOS should run apps from Android,
Windows and any Linux distribution; the person presses install or drops a file, it
installs and runs, and they never see Wayland, KWin or Bottles. One store for every
kind of app. Everything else happens behind it.

**What MoOS already had, measured on the station 2026-09-19.** More than the source
suggested. The engines are shipped, not missing: `wine` and `waydroid` are installed by
`build.sh` on every desktop edition (`_core_power`), `waydroid-container.service` is
enabled, Flatpak comes from the base, and `mimeapps.list` already routes `.exe`, `.msi`
and `.apk` to `org.moos.runforeign.desktop`. What was missing was not capability. It was
the product: one decision, one vocabulary, and silence about the machinery.

**What landed.** `/usr/share/moos/app-engines.json` is the one registry — engines, the
runtimes that carry them, where each runtime comes from (`build` / `base` / `overlay`),
whether it is sandboxed, what files it claims, and the bilingual name a person actually
sees. `/usr/libexec/moos-app-engine` resolves a file against it and answers three
questions — which engine, is it ready, what do we call it — read-only, so the single
privileged executor stays `moai-do`. `moos-run-foreign` asks instead of deciding, which
closed a defect neither half could show alone: the image installs a Windows runtime "so
any .exe the user downloads actually runs" and the runner knew only about the optional
Flatpak one, so a first `.exe` offered a large download on a machine that could already
run it. `tests/test_app_engines.py` holds the contract and every half of it is proven to
fail on purpose.

**The rule that makes it feel like one system:** the engine never says its name. Not in a
dialog, not in a terminal line, not in a notification. "Windows programs", "Android apps",
"Linux apps" — which runtime MoOS used is MoOS's business. The gate fails the build on any
user-facing string that names wine, bottles, waydroid, proton, lutris, flatpak, wayland,
kwin, plasma, qemu or bubblewrap.

One word carried an exemption, and on 2026-09-20 the exemption was found paying for
things it was never written for. "Flatpak" is also a FILE a person can hold — App Drop
saying "This Flatpak file is not valid" names the thing in their hand, and refusing the
word there would leave them holding a file MoOS will not name. That is why the gate's
`RUNTIME_BRANDS` subset lets it through. But the same subset was also letting the
STOREFRONT say it: Mo Store's install sheet read "Flatpaks install for your user only",
its review line appended "· AppImage", the sources panel was headed "AppImage · External
sources", and Mo AI described installing an app as "in sandboxed Flatpak container".
None of those is a file; each is the mechanism, which is the one thing the owner asked
never to see. The copy is rewritten in MoOS's voice ("Apps install for your account
only", "· Verified file · SHA-256", "Publisher downloads · External sources"), and the
line is now drawn where it belongs: on the surfaces where MoOS SELLS and INSTALLS apps —
Mo Store, Welcome, Mo AI — the packaging may appear only inside a file name. App Drop,
whose entire job is the file you just dropped, keeps the word on purpose. Both halves are
held by `test_the_storefront_names_a_file_but_never_the_mechanism`, proven to fail on the old sentence.

**And the rule is not only about strings MoOS writes.** The same day, with every string
gate green, the application menu on the station showed a folder called "Waydroid"
containing a launcher called "Waydroid". Neither came from a MoOS file: the package ships
`Waydroid.desktop` (a visible launcher whose `Exec` is the bare CLI) and
`/etc/xdg/menus/applications-merged/waydroid.menu`, which collects every `X-WayDroid-App`
into a folder labelled by `waydroid.directory` — so that folder is where EVERY Android app
the owner installs lands. It had been true since Android first worked, and no gate could
see it, because every gate read MoOS's files and this was a third party's. `build.sh` now
hides the launcher and relabels the folder to **"Android apps" / "تطبيقات أندرويد"** with
MoOS's own icon, and FAILS THE BUILD if either file moves or either edit does not take.
The folder itself stays: the apps need a home, and naming the platform an app came FROM is
what Mo Store's own category already does — the rule forbids naming the machinery, not the
origin. The wine half of this was fixed long ago (ten Wine tools masked, with a build gate);
the Android half had simply never been written.

**And the same audit, run properly, found the bigger one.** With every string gate green,
the application menu in the owner's Arabic session offered **two settings applications**:
"إعدادات MoOS" and "إعدادات النّظام". `build.sh` had hidden `kdesystemsettings.desktop`,
Fedora's *duplicate* launcher, and left `systemsettings.desktop`, the real one, visible —
and the gate beneath that section only ever checked the duplicate. Beside it stood
"Dolphin / دولفين", "KDE Connect / جسر كِيدِي", "KDE Partition Manager / مدير أقسام كِيدِي"
and "Info Center". Hiding all five would be the wrong fix: a person needs a file manager
and a disk tool. MoOS Settings now uses `systemsettings` itself as the window and keeps
Plasma's real hardware modules beside its own MoOS module; `kinfocenter` retains specialist
hardware pages. So each entry now carries MoOS's name and MoOS's icon — Files / الملفات,
Phone / الهاتف, Disks / الأقراص — and the two reached only through MoOS Settings also leave
the menu. Only the `[Desktop Entry]` group is rewritten, because `systemsettings.desktop`
ships five Desktop Actions whose own `Name=` lines a blind `sed` would overwrite; the
rewrite was proven against the real files before it shipped. `build.sh` fails the build if
either half stops taking, and `test_the_app_menu_carries_no_other_desktop_name` holds it.

**What is still honestly a seam, on NVIDIA machines only.** Android apps render in
software. `waydroid`'s own `tools/helpers/gpu.py` carries `unsupported = ["nvidia"]` and
falls back to `ro.hardware.egl=swiftshader` whenever the only DRI node belongs to the
proprietary driver — measured on the station, an RTX 2080 SUPER. Forcing `drm_device` in
`waydroid.cfg` does not defeat it; the same list is consulted. On AMD and Intel machines
MoOS gets `gbm` + `mesa` automatically. A private override would be an unqualified fork of
a core runtime and could trade slow rendering for corruption; qualify an upstream-supported
path or a separately tested patch on NVIDIA before changing the image. It remains written
down rather than being hidden behind a misleading “accelerated” label.

**The 4K sizing review added two separate facts.** A legacy fixed Win32 dialog cannot be
made useful by forcing KWin to resize it: PuTTY became a huge white frame while its controls
stayed in one corner. The MoOS runner now derives a capped 96–192 DPI from the active desktop
and writes `LogPixels` before launch. On the 265% station the same real PuTTY binary grew from
178×331 to 348×591 logical pixels with its content scaled. Android VLC also launched as a real,
resizable desktop window through the catalogue adapter. On fractional-scale KDE its client-side
surface still does not fill the geometry KWin reports when maximized; this matches upstream
Waydroid's open fractional-scaling defect and is a remaining P4.4 qualification seam, not a
reason to add a second compositor or expose Android settings to the owner.

**macOS** is unsupported. The answer lives in ONE place — the `unsupported` entry in
`app-engines.json`, in both languages — and this paragraph deliberately does not repeat
it, because two copies of an answer is how a repository comes to give two answers. What
belongs here is the engineering position behind it: experimental compatibility projects
exist, MoOS has not qualified a reliable path for graphical macOS applications, and until
it does there is no Store button and no promise.

**What the 2026-09-19 review found.** The Store drop
path was reviewed across security, contract, correctness and product by four independent
readers and every finding was put to an adversarial verifier. The security design held:
outside-home paths, directory-symlink escapes, FIFOs, device nodes, dangling symlinks and
non-owned files are all refused, argv is never a shell even with `$(...)` in a filename, a
declined dialog spawns nothing, and the only privileged thing reachable is `moai-do`
behind its own confirmation. What did not hold, and is fixed: the catalogue edit reddened
the gate CI runs before signing; the Store told the drag source a rejected drop had been
accepted; an install started from the Store was invisible in the Store; the what's-new
entry promised installation for `.exe` and `.apk`, which that path does not do; the UI
test ran under an app id that has no bridge, so it never reached the code it is named
after; and today's eight gates existed only in `just check`, which `test_gate_coverage.py`
permits and which protects nothing at the moment a candidate is signed.

The five concrete defects from that review are closed in corrective source. APK mutation
now occurs only inside `moos-storectl`'s job and lock; the authority gate recognizes the
actual Android install argv. The bridge's six Qt/consent cases ran in a disposable SDK.
Mo Store's ordinary copy says apps, not its packaging mechanism. `.xapk`/`.apks` are
refused with a bilingual reason before a dialog because no qualified runner exists.
KDialog 26 was exercised on a private X server: Enter and Escape reject; only an explicit
Tab+Enter accepts. All 204 source gates and the full local generic image build are green;
the latter passed the bootc, initramfs, QML-runtime, motion, clean-state and identity
firewall gates. What remains open is product evidence, not hidden completion: a real
pointer drop and double-click on the installed signed image, Windows/Android launcher and
remove lifecycle, and the full P4.1 cancel/retry/readback contract across every adapter.

**Next, in order. Each row is a wave; source progress does not replace its installed acceptance proof.**

| Order | What the owner gets | The work | Acceptance |
| --- | --- | --- | --- |
| A1 | **DONE — all three engines, on the installed image, 2026-09-20** | **Windows:** two PE32+ GUI programs launched through `moos-run-foreign`, the double-click path, and appeared on the 4K Arabic desktop — Notepad (`غير معنون - المفكرة`) and Minesweeper (`الألغام`) — both wearing **MoOS's own Aurorae decoration** and both listed in the **MoOS Bar** beside native apps. Resolver: `برامج ويندوز, ready=true, chosen=wine, needs_setup=false`, no download. **Linux:** `moos-storectl install com.github.tchx84.Flatseal` → real job `state=success`, launcher entry `فلاتسيل`, ran in Arabic RTL, then `moos-storectl remove` → gone cleanly. Install, launch and remove all through Mo Store, never `flatpak` directly, which is what P4.1 claimed on paper. **Android — and it had NEVER worked.** `moai-do setup-waydroid` called `waydroid init -s VANILLA` with no OTA channels. waydroid composes its URL as `<channel>/<rom>/waydroid_<arch>/<type>.json` and falls back to a channels config that neither MoOS nor Fedora's package ships, so it stopped every time with "You must provide 'System OTA' and 'Vendor OTA' URLs" — before downloading a byte. Every existing gate read the source, where each half was correct. Passing the channels explicitly fixed it: **2.3 GB downloaded** (system.img 1.7 G, vendor.img 536 M), container `RUNNING` on 192.168.240.112, a real 11.9 MB APK installed through `moos-storectl install-file` (`state=success`), and **F-Droid opened on the MoOS desktop** with its own icon in the MoOS Bar. `tests/test_android_setup_channels.py` holds it and is proven to fail when the channels are removed. Frames in `test-results/a1-live/`. | Met. What remains is not A1: a second machine; PE32 (32-bit Windows), which SELinux blocks with an `execmod` denial mapping the i386 DLL from composefs; and **the Android caption**, re-measured on the station 2026-09-20 (`test-results/android-caption-seam.png`). A Windows program wears MoOS's Aurorae frame, but an Android app does not: in `multi_windows` mode the LineageOS freeform caption — back chevron, minimize, maximize, close — is drawn by SystemUI INSIDE the Android surface, so it arrives as client-side decoration and KWin never gets to frame it. No host-side property turns it off; `persist.waydroid.multi_windows` is the only `persist.waydroid.*` key the shipped tooling knows. Forcing a server-side frame would give the window two title bars, which is worse than one honest seam, so nothing was forced. The real fix is a patched Android image with the caption suppressed, which is a ROM build and belongs in its own cycle — written down here rather than quietly carried. |
| A2 | Installed foreign apps appear in the launcher like any other app | Android exports named launchers; the managed Windows adapter now has an individual prefix, stable ID, launcher/icon, receipt and symmetric removal in the integrated .1062 source. The Oct16 batch adds strict ownership of unlisted APK receipts and isolates Android runtime lifetime from short Store jobs. | Signed installed-image install → ordinary logout/login → menu launch → remove/reinstall, for every adapter; names/icons stay application-specific. Private Wine windows and mock lifecycle tests do not fulfill this row. |
| A3 | Mo Store carries Android and Windows apps beside Linux ones | Production .1072 now has264:150 Flathub,46 pinned Android APKs,20 managed portable Windows apps,17 App Drop recipes,27 preserved webapps,3 CLI tools and1 vendor package. Two real Linux/Android ID collisions now prefer confirmed native Linux builds while retaining existing Android receipts as namespaced unlisted apps. All64 additions are real apps; seven featured cards are packaged apps. Fresh publisher/architecture metadata and exact APK/PE provenance are recorded.14 new Windows apps render under private native Wine;5 rejected candidates are excluded. Oracle's real Curtail journey passes. Native Markor installs exact APK bytes and reaches KWin after cold Android recovery; initial display/HWUI crash remains unresolved. Real Notepad4 exposed and proves the shared launch-lifetime fix. | Combined signed milestone cycle now passes at727e7b6c; complete native installed-image Store UI install/open/update/cancel/remove/reinstall.10 Android and10 Windows full app journeys, durable Android startup, actual touch hardware and physical GPU qualification remain open. |
| A4 | Drop anything into MoOS and it installs | App Drop resolves through the same registry instead of its own list, so a dropped `.exe`, `.apk`, AppImage or archive takes the identical path as a catalogue install — consent, one job, a menu entry at the end | Drop one of each. Refused types still say why. A cancelled consent leaves nothing behind |
| A5 | A MoOS API third parties can build against | The resolver is the first piece and it is a private CLI. Promote the app surface to a documented, versioned D-Bus interface — `org.moos.Apps1` over the registry and `moos-storectl`'s existing job model — so "what can this machine run, and install this for me" is answerable without shelling out to private commands. See the stack-depth audit: this is the single largest thing standing between MoOS and being an operating system rather than a very good desktop | An interface XML in `/usr/share/dbus-1/interfaces/`, introspectable, with a version; one first-party caller migrated onto it; the CLI kept as a thin client of the same interface |

**Do not** fork Plasma, KWin or Wine to do any of this, and do not let a second copy of the
"which engine" decision appear anywhere — that duplication is the defect this contract was
created to end.

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

PR243–246 integrate the complete reviewed Store/Plasma batch at `e1ffacfa`.
All231 audited refs and the original57 station worktree heads are ancestors;
82 missing/behind remote heads were published without force. Original dirty
station/Oracle drafts are backed up, cross-verified and untouched.
The previous `.1060` ISO failed a real final visual gate on a session-handoff
frame mislabeled pre-login. Its failure and old-source negative controls remain;
PR246 captures the actual pre-authentication frame without changing thresholds.
The fresh exact-source `.1062`/`.792` cycle passes all three disks, offline ISO,
ARM build/two-boots and promotion. Native NVIDIA has the exact signed stage;
Oracle `.792` passes native63 hashes/51 selfchecks/55 post-update checks. Source,
promoted artifacts and native application/GPU
acceptance remain distinct in the [current receipt](releases/2026-10-16-store-qualified-cycle-proof.json).
The historical [Oct14](reviews/STORE_20261014_AR.md) and
[Oct15](reviews/STORE_20261015_AR.md) review fixes are integrated; do not report
them as missing source. M3/A3/P4.1 artifact delivery is complete within its
recorded scope; connected user journeys, accessibility and physical/endurance
acceptance remain in the existing rows below.

### Milestone map

| Milestone | Coherent outcome | Work-stream rows | Boundary proof |
| --- | --- | --- | --- |
| M0 | One honest source/release/workstation state | P0.1–P0.2, P0.6, release harness defects | signed build + 3×QCOW2 + ISO + ARM; exact installed readback |
| M1 acceptance | Daily shell feels like one MoOS product: Bar, Search, Island, clock, sound, keyboard and desktop hub | P2.3–P2.5, P2.7–P2.8, P5.4 baseline | native keyboard/render review, matrix samples, then the M0 artifact set |
| M2 | Workspace, Intro, login/lock/boot and first-run form one journey | P1.6, P2.1–P2.2, P2.5, P5.8 | clean and upgraded profiles; offline/online; Wayland restart and scale/hotplug |
| **M3 active: owner Store priority** | Settings, Store and Mo AI complete real jobs with one authority | P1.7, P3.1–P3.7, P4.1–P4.2 | schema/failure fixtures plus install/update/remove and confirmed AI-action readback |
| M4 | Hardware and compatibility breadth | P0.3–P0.5, P4.3–P4.5, P5.1–P5.8 | device records, suspend/rollback and published compatibility evidence |
| M5 | Sustainable releases and support | P6.1–P6.6 | reproducible inputs, attestations, staged rollout and support policy |

Rows can contribute to more than one milestone. A row closes only when its own
exit evidence exists; the map controls batching, not truth.

**Time-boxed outside the milestone order:** P6.7 must be green on the canary before Fedora 44
ships Plasma 6.8 (released upstream 2026-10-14). On that day the mutable base tag moves by
itself and an unreviewed MoOS would ship kscreenlocker's emergency locker.

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
| P4.1 | Unify every install/update/remove request behind Mo Store | Shared native backend/bridge/UI and200-app catalogue are signed/promoted in `.1062`/`.792`; actual Linux/web/Windows installs/runs and13 Craft artifact lifecycles pass within their recorded scope. Native full-account/error/cancel/update/remove journeys remain. Newly discovered Oracle draftPR253 restores missing ARM base app-update units and gates both edition trees; it is independent, not part of727/.1072, and still needs final image qualification, integration and signed delivery. Native NVIDIA1062 already has both loaded/enabled/active timers | Store authority for every engine; shared job IDs, cancel/retry/remove and final readback. |
| P4.2 | Audit desktop-app permissions and prefer portals | Open / acceptance not complete | Permission inventory and actual file/camera/screen/print portals without broad grants. |
| P4.3 | Turn Windows compatibility into a per-app runner product | Combined source retains 20 reviewed publisher-pinned Windows recipes and their existing private render evidence. The six unqualified local additions are preserved in Git history, not offered as proven apps. Ten full native lifecycle journeys remain open. | Ten Windows apps with isolated prefixes and install/launch/reopen/update/remove evidence. |
| P4.4 | Turn Android compatibility into a per-app product | Signed .1062 catalogue has 21 Android apps; combined source has 46, actual boot/property readback and independent session lifetime. Native Markor launch/document display passes within its recorded scope; editing/saving, cold-start endurance and ten complete journeys remain | Ten Android apps, on-demand container, files/clipboard/audio and NVIDIA fallback. |
| P4.5 | Publish a generated compatibility matrix | Source generator uses the Store sanitization, architecture, engine and installability rules for all 264 entries. JSON and AR/EN text distinguish recipe availability from unassessed application testing, include pinned recipe versions and NVIDIA-only software graphics. Eleven controls pass; old generator fails all eleven. Signed delivery and published per-app lifecycle evidence remain separate. | Generated version/edition/architecture/GPU compatibility matrix, including unsupported cases. |
| P4.6 | Consent-based App Drop for files | Implemented/delivered within recorded scope; wider acceptance remains | Real magic, sandbox extraction, default-No consent, safe launchers and all entry paths. |
| P4.7 | Native Store picker/drop through App Drop | Implemented/delivered within recorded scope; wider acceptance remains | Actual QML picker/drop delegates to App Drop, valid local files, refusal/cancel and Store job. |

## P5 — Hardware and performance

| ID | Outcome | Current boundary | Required acceptance |
| --- | --- | --- | --- |
| P5.1 | Hardware qualification lab | Open: station USB capture overruns reproduced; Home Assistant Bluetooth/DHCP/duplicate entities and first-start protocol failure remain | GPU/audio/network/Bluetooth/camera/storage/firmware records across actual hardware; distinguish host hardware from rootless home-hub integration faults. |
| P5.2 | Laptop policy | Open / acceptance not complete | Three laptop classes, lid/battery/brightness/power and two suspend cycles each. |
| P5.3 | Touch/tablet policy | Open / acceptance not complete | Actual touch/tablet targets, keyboard/rotation/gestures/stylus and ≥44px controls. |
| P5.4 | Performance budgets | Open: native active-workload 30 s has 6.4–6.7 GiB available/PSI=0/GPU 0–21%. Idle Baloo restart reduces PSS 2.23 GiB→104 MiB and anonymous memory 970→13 MiB; all 303,766 indexed files, actual indexed probe and config preserved. This is one local intervention, not durable policy or weak-tier acceptance | Measured boot/idle PSS/CPU/wakeups, app launch p95, frame pacing, build load and AI latency per tier. |
| P5.5 | Cloud desktop efficiency | Implemented/delivered within recorded scope; wider acceptance remains | Efficient cloud desktop plus actual private files/photos/IDE access, phone background and off-host restore. |
| P5.6 | Storage lifecycle | Earlier42GiB local OCI commit exhausted disk and crashed Chrome/ChatGPT; real failure/unsaved-state boundary preserved. Scoped build cleanup recovered owner app units without profile deletion. Oct18 owner-delegated retirement removes44,583,870,472 file/cache bytes after cold-success retirement of the1,913,401,344-byte old derived index; superseded generic image+2 exclusive parents yields separately observed3,677,118,464 writable bytes; Bazaar/Chess/temporaryNotepad4 removed with data/prefixes retained. Sources/dirty trees/full bundle/SDKs/databases/17 containers/current signed ISO/rollback survive. About83.5GiB free after new boot/readback. New guarded full image passes60GiB/5GiB preflight and8GiB/1GiB continuous floors. Private helper is not shipped low-space protection; durable build/cache retention/recovery and3 lint warnings remain open | Headroom, cache/log bounds, low-space recovery and cleanup that never removes owner data. |
| P5.7 | Qualify kernel policy and driver transitions | Source adds ARM's missing vendor oomd-defaults, final-image guard and actual native-monitor readback in both disk boot proofs. Eight compose controls, native ARM package install, and bounded native negative/positive pressure controls pass on both stations (256 MiB cap; no kernel OOM; protected sentinel survives). Signed ARM .756 and NVIDIA .1026 are booted and prove actual system/native-user monitoring. System-wide recovery/weak-hardware frame latency remains open | Kernel/driver readback and measured frame/audio/CPU/RAM policy; actual daemon monitoring after signed boot; sustained frame/audio latency under bounded pressure on qualified weak tiers, never an uncontrolled OOM on the owner's workstation. |
| P5.8 | Qualify Wayland and compositor lifetime | Open / acceptance not complete; Oracle .752 retains bootupd metadata/accountsd SELinux warnings, while bootloader update returns success/latest and no unit fails | Portal consent/revocation/restart, output/scale/hotplug, clipboard/input and long session-return soak; review native SELinux warnings without disabling enforcement or guessing labels. |

## P6 — Long-term release trust

| ID | Outcome | Current boundary | Required acceptance |
| --- | --- | --- | --- |
| P6.1 | Resolve immutable base inputs once per release | Open / acceptance not complete | Immutable base inputs recorded once and consumed consistently by all same-architecture editions. |
| P6.2 | Produce SBOM and provenance for each image | Open / acceptance not complete | Exact digest-linked SBOM/provenance on a separately budgeted workflow, not release-critical disk exhaustion. |
| P6.3 | Security-release cadence for all editions | Open / acceptance not complete | Proven release cycles deliver security updates; schedules only build candidates. |
| P6.4 | Add staged rollout and release health | Open / acceptance not complete | Staged rings, halt/rollback criteria and actual field release health. |
| P6.5 | URL, Remote, AI and diagnostic security boundaries | Implemented/delivered within recorded scope; wider acceptance remains; the integrated audit cycle is signed/promoted. Oct17 open Dependabot/secret alerts are0; Code Scanning returns no analysis (404), so static-analysis acceptance is unproven | Auth/UID/URL/PIN/upload/secret boundaries and failure controls; native dependency advisories refuse release. |
| P6.6 | Establish support lifecycle and migration policy | Open / acceptance not complete | Published support/upgrade/rollback/EOL policy plus clear licences, attribution and official identity. |
| P6.7 | Reviewed Plasma seams before upstream transitions | [Oct15 stable qualification](releases/2026-10-15-plasma-stable-source-proof.json): native x86 Plasma 6.8.0, exact signed inputs,12 seams, real greeter positive/broken/restored and rebuilt vendor logout old/fixed/rejected/cancelled controls pass. PR246's corrected `.1062`/`.792` signed cycle passes all exact QCOW2/offline ISO/two-boot proofs and promotion with unchanged gates. Physical x86 now boots exact signed .1062 on Plasma6.8.0; its prior acceptance is recorded separately. Oct18 current1072 native boot passes unchanged55/0 checks without display-start aborts; expanded coredump review retains greeter Qt screenRemoved teardown and Remote handoff bind collision; broader hardware/phone/accessibility acceptance remains open. ARM retains qualified native6.7.5. The specific publisher/chroot aarch64 metadata endpoint returns404 at the Oct17 readback; the x86 metadata GET was unreadable, not absent. Complete native6.8 package/seam/source closure remains open. [Provider snapshot](releases/2026-10-17-plasma-provider-readback.json). Qt 6.12 stays unqualified. Prior beta canary evidence remains historical. | Actual matching stack, registered seams and native controls, final signed boot and installed acceptance for each architecture; never widen pins or substitute cross-architecture packages. |
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

Mo Store Oct15 follow-up: 200 curated apps, including 16 additional native games
and everyday tools. Existing supported theme/motion configuration is reachable
from Store Settings. Full game/hardware acceptance, Steam-managed game inventory
and general third-party theme installation remain separate work; no blanket
compatibility claim. Release and workstation acceptance remain governed by RELEASE.md.

Oct15 coherent integration follow-up: recovered the still-relevant engine admission
checks from the preserved Oracle worktree. Windows processor combinations are
checked before runtime selection; Android setup, admission and Store share strict
read-only status parsing and bounded session readiness. Original APK metadata and
update verification remain with the newer reviewed implementation. See
releases/2026-10-15-engine-admission-recovery.json for source/fixture evidence.

Stable Plasma Oct15 qualification: the x86 image composes the signed KDE SIG
6.8.0 stack with a pinned publisher key and exact core NVR checks, preserving
the base kernel. Stable seams retain upstream authentication and use the
reviewed virtual-keyboard Panel correction. Native greeter positive/broken/
restored and rebuilt logout old/fixed/rejected/cancelled controls pass. Cache
fingerprinting now includes version-specific seam QML (THEME_REV106). The ARM
image retains its separately qualified native provider: the final upstream
repository has no ARM binaries, and a full native stable source rebuild remains
P6.7 acceptance work. No cross-architecture packages or beta relabeling.
Source/image/boot/promoted/installed evidence remain separate; one replacement
release cycle only after the combined source passes.

Oct16 unified application batch (source; delivery pending): one on-demand user
Android session survives Store task completion and stops with graphical logout;
no idle autostart, unsigned image download or ambiguous readiness is accepted.
Dropped APK updates install an owned disk snapshot, verify the actual package,
and retain the old receipt on silent refusal. Unlisted APKs stay manageable
without colliding with identically named Linux apps. Native Task Manager is
reachable from the Library through its existing launcher; no duplicate manager
or polling daemon is added. Basic-style QML apps select KDE's platform plugin
so Plasma's disabled motion applies. Native Qt touch/wheel/keyboard and old-source
negative controls pass. See [source/runtime receipt](releases/2026-10-16-store-native-source-proof.json).
The real Oracle Curtail journey found a Mesa Vulkan crash; ARM's existing
software-rendering environment now selects GL, with positive native Wayland
readback on the same app/runtime. The local user-manager setting is a temporary
runtime correction, not a signed release. Freeze the coherent Store + Remote
source and complete one local native ARM image/required CI/signed four-edition
cycle before official Oracle update/reboot. NVIDIA became available Oct17;
its bounded native evidence below does not qualify every application.

Primary sources reviewed2026-10-16: [Waydroid desktop-window properties](https://docs.waydro.id/usage/waydroid-prop-options),
[Waydroid unsupported-GPU software path](https://docs.waydro.id/faq/get-waydroid-to-work-through-a-vm),
[actual session-manager lifetime](https://github.com/waydroid/waydroid/blob/main/tools/actions/session_manager.py),
[GTK renderer selection](https://docs.gtk.org/gtk4/running.html),
[KDE platform-plugin selection](https://github.com/KDE/kirigami/blob/master/src/platform/platformpluginfactory.cpp).
Native x86 desktop images ship Wine/Waydroid; ARM and cloud engine availability
is separately advertised by measured admission. This batch does not claim
x86 Windows execution on the current ARM machine or universal Android hardware support.

Oct16 gate follow-up: the journal-isolation run caught a lost Mira job-presence
notification. Stopping the owned diagnostic scan and running quietly passed,
so that rerun did not qualify the original behavior. A new deterministic real
Qt control delayed the first consumer delivery1.1s and reproduced the same
old one-shot failure. The producer now emits a finite three-event coalesced
burst from one worker; it leaves no idle polling, token or timer, preserves
end timestamps and does not recreate a retired runtime directory.64 native
controls pass; old scheduler controls must remain red. This is part of the
same not-yet-delivered Store/Remote milestone, not a second candidate cycle.

Oct16 APK follow-up keeps one bounded update confirmation before publishing a
new receipt, preserving the existing `android_update_refused` and unreadable
legacy-data policy.29 update controls,36 Store controller controls and47 backend
kind controls pass. The dropped-file fixture now contains a real compiled
manifest and checks the private snapshot/source-file lifecycle. The generated
cache fingerprint records107; its refusal of same-revision changes is unchanged.
The109-command adaptive remainder diagnostic retains its three failures and
their subsequent targeted corrections; it is not the official full-check proof.
Exact `c16a7a70` subsequently passed the official284-command native `just check`
in652.471s. Its PR x86/ARM/canary image gates then exposed a fixture-input
error: the corrected host inherited the shipped factor0.5 (measured100ms),
while the full motion test assumed200ms. Oct17's private explicit factor1
passes real native interaction/Hub tests; broken reduced-motion scaling still
fails. Shipped defaults and assertions are unchanged. The separate local image
stopped at its3GiB disk reserve and remains a failed build, not qualification.
The rebuilt image, final source check, signed cycle and installed readback stay
open. [Follow-up evidence](releases/2026-10-17-store-qualification-followup.json).

Primary source refresh2026-10-17: [Flatpak architecture/remote/app lifecycle](https://docs.flatpak.org/en/latest/using-flatpak.html),
[F-Droid signed indexes rather than display APIs](https://f-droid.org/docs/All_our_APIs/),
[F-Droid index/APK signing](https://f-droid.org/en/docs/Signing_Process/),
[Waydroid desktop windows and idle suspend](https://docs.waydro.id/usage/waydroid-prop-options),
and [unsupported-GPU software rendering](https://docs.waydro.id/faq/get-waydroid-to-work-through-a-vm).
These support the existing verified-source adapters; they do not replace real
per-application installed-image or physical GPU acceptance.

Oct17 first-use Android integration: source review against the current upstream
property command and desktop instructions confirms that a stopped session can
refuse both property writes with exit0. Confirmed setup now waits for the real
boot property, verifies both desktop values, restarts once only when changed,
and verifies them again. Correct sessions keep running; existing-app restart
notice is before consent. No separate phone desktop opens. Nine native isolated
setup controls pass, including silent refusal, failed readback/restart and an
unbooted platform; two restored-old controls fail. Five shared-runtime and four
channel controls pass. These controls do not qualify actual Android windows or
apps on hardware; that acceptance and the final combined signed cycle remain
open. [Evidence](releases/2026-10-17-android-desktop-setup-source-proof.json).

Oct17 native follow-up: exact `7c37862e` passes the full native repository check,
complete ARM image/19-file immutable readback and every PR image/repository/Remote
check. Preserve earlier failures; this checkpoint does not qualify later edits.
Real Notepad4 installed but closed with the Store caller. Shared launches now
use the canonical user-manager boundary with cgroup lifetime and desktop stop
ownership, refusing manager errors. Two actual private old/broken lifetime
controls fail; fixed child survives its caller and stops with its private target.
Seven portable controls and real NVIDIA Notepad4 window/pixels pass. Existing
five Android runtime controls now join the maintained `just check` recipe.
Native Markor exact APK/version installs and a KWin window appears after cold
Android recovery; WCG/SurfaceFlinger failure is not permanently repaired. Both
default HWUI and Vulkan cold controls pass, so renderer selection was restored
and is not claimed as a cure. Scoped document permission returns to default;
document-intent success is not editing/saving proof. Final combined qualification,
one signed cycle and installed-image acceptance remain open. Oracle API tenancy
read/instance-principal auth and the recovered backup succeed; compute detail
access and billing standing are not established. [Evidence](releases/2026-10-17-managed-app-native-proof.json).

Primary lifetime source reviewed2026-10-17: [systemd service lifetime](https://github.com/systemd/systemd/blob/main/man/systemd.service.xml)
and [transient services](https://github.com/systemd/systemd/blob/main/man/systemd-run.xml).
