# MoOS development plan — current execution backlog

Updated 2026-10-09. This is the single execution backlog, not an incident diary.
Current measurements live in PROJECT_STATE.md; detailed audit evidence and
remaining boundaries are in AUDIT_20261008_AR.md. Git preserves prior waves.

The owner's ordered implementation and cross-device handoff are recorded in
[OWNER_EXECUTION_20261009_AR.md](OWNER_EXECUTION_20261009_AR.md). Its active slice
is reliability/release acceptance, before the remaining four milestones. The
new private feedback/optional public suggestions product is P6.9 below.

## Active audit correction batch

Priority before the M1 visual work: support-report privacy/atomic output,
Remote's vulnerable fallback dependency and fail-closed NuGet audits,
language transaction/startup consistency, and current signed ARM install
metadata. Source regressions and native tests pass. ARM .728 completed
exact-source build, disk proof and promotion at 8ebe0591; installed Oracle
readback remains owed. X86's build and three disks passed, but offline ISO
installation first failed on an empty `efi`. The diagnostic retry records
`install=done` before a later file-read timeout; the harness misleadingly calls
its 30-second diagnostic timeout a 45-minute installer failure. Diagnose and
bound diagnostic transfer, preserve accurate timeouts, then repeat the whole
installed-ISO proof before x86 promotion; retain every existing gate.

Current stable delivery is x86 .1011 at fa85b2da and ARM .728 at 8ebe0591.
Public .1011 ISO hosting is qualified and P0.12 is closed. Both stations develop
the same product; each hardware result must name its device and deployment.
The NVIDIA station completed app updates and rebooted into exact signed .1011
from .1009, retaining .1009 rollback; installed checks passed 55/0 and
selfcheck passed 54. Its real app launches and Mira/MoPlayer frames were read
back, while physical voice, suspend and deliberate rollback remain unproven.
Running scheduled/image-only builds
never imply promotion. No new model-written shell or hardware acceptance is inferred.

The cadence of release cycles is the security cadence: a nightly image-only
build cannot deliver a base fix. P6.3 remains an explicit gap until bounded,
boot-proven release cycles keep every supported edition current.

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
| A2 | Installed foreign apps appear in the launcher like any other app | **Android half works:** the container exports a launcher with the app's real name/icon, and removal takes it away; VLC and Organic Maps are present on the station. **Windows half remains:** App Drop runs the selected file but does not yet create a per-app environment, launcher/icon or uninstall record. Build that product instead of exporting the runtime's generic tools. | Install, log out, log in, launch from the menu. Remove takes the entry with it. No entry names a runtime |
| A3 | Mo Store carries Android and Windows apps beside Linux ones | **Android catalogue adapter is source-complete and live-proven:** pinned publisher URL + SHA-256, one Store job/lock, session readiness, install/run/remove/reinstall, and ordinary Store buttons. Seven Android apps are catalogued. The Windows row currently contains five verified publisher destinations; it is discovery, not a managed install adapter. Next: per-app Windows environments with stable IDs and symmetric remove/retry; keep downloads explicit until that exists. | Android: cancel mid-download plus installed-image remove/reinstall proof. Windows: managed install/run/remove for a published test app. The Island shows one job and names the app, never the engine |
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

### Milestone map

| Milestone | Coherent outcome | Work-stream rows | Boundary proof |
| --- | --- | --- | --- |
| M0 | One honest source/release/workstation state | P0.1–P0.2, P0.6, release harness defects | signed build + 3×QCOW2 + ISO + ARM; exact installed readback |
| **M1 active** | Daily shell feels like one MoOS product: Bar, Search, Island, clock, sound, keyboard and desktop hub | P2.3–P2.5, P2.7–P2.8, P5.4 baseline | native keyboard/render review, matrix samples, then the M0 artifact set |
| M2 | Workspace, Intro, login/lock/boot and first-run form one journey | P1.6, P2.1–P2.2, P2.5, P5.8 | clean and upgraded profiles; offline/online; Wayland restart and scale/hotplug |
| M3 | Settings, Store and Mo AI complete real jobs with one authority | P1.7, P3.1–P3.7, P4.1–P4.2 | schema/failure fixtures plus install/update/remove and confirmed AI-action readback |
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
| P0.2 | Run generic, NVIDIA and cloud QCOW2 proofs plus offline ISO install/second boot | .1011 stable proof retained; 8ebe0591 disks pass but final offline ISO installation fails | Three exact-digest x86 QCOW2 journeys, offline installed ISO and separate ARM two-boot proof. |
| P0.3 | Finish physical NVIDIA qualification | Open / acceptance not complete | Actual NVIDIA GPU, initramfs module, displays, suspend and clean recovery on qualified hardware. |
| P0.4 | Prove failed-update recovery | Open / acceptance not complete | Deliberate bad update, automatic/manual rollback and forward return without owner data loss. |
| P0.5 | Configure and accept free Mo AI on a clean account | Open / acceptance not complete | Clean-account provider setup, free route, reboot, cancellation and network/quota/key failures. |
| P0.6 | Promote only proven digests and update the physical PC | Stable mechanism/artifact evidence recorded; preserve required gates | Promote only exact proven signed digests; separately verify installed stage/reboot/rollback. |
| P0.7 | Remove the intermittent `plymouthd` crash (ARM second boot; x86 first boot) | Implemented/delivered within recorded scope; wider acceptance remains | Pinned vendor Plymouth fix, old/fixed negative, exact final initramfs and actual boot visuals. |
| P0.8 | Make the ISO installed-reboot proof deterministic | Stable mechanism/artifact evidence recorded; preserve required gates | Repeated installed-ISO reboot with DHCP/SSH-channel evidence and console failures visible. |
| P0.9 | Run image-only gates before the merge | Stable mechanism/artifact evidence recorded; preserve required gates | PR generic image gates block real image failures; no signing/publishing from PR. |
| P0.10 | Gate NVIDIA persistence on a bound GPU | Stable mechanism/artifact evidence recorded; preserve required gates | Bound NVIDIA hardware and exact-kernel persistence/initramfs proof. |
| P0.11 | Give first-boot Flatpak setup a realistic finite timeout | Stable mechanism/artifact evidence recorded; preserve required gates | Finite realistic first-boot app setup timeout and actual ARM reboot. |
| P0.12 | Deliver the exact signed, installed-system-proven ISO through a stable anonymous download | Closed: full public transfer/signature/hash/ranges and website proved | Stable anonymous full signed ISO, exact size/hash and resumed ranges; sidecars and site readback. |

## P1 — Reliability and first run

| ID | Outcome | Current boundary | Required acceptance |
| --- | --- | --- | --- |
| P1.1 | every migration records id/revision/outcome in one append-only ledger; the two-key wallet write is staged and renamed so an interruption leaves the original file; interrupted, repeated and clean-vs-upgraded fixtures in `tests/test_migration_ledger.py` | Stable mechanism/artifact evidence recorded; preserve required gates | Versioned idempotent transactional migrations; private durable outcomes and failure recovery. |
| P1.2 | `moos-boot-assess` counts unblessed boots in `/var/lib/moos` because `/boot` is read-only and greenboot is absent; three unblessed boots return to the previous deployment through `bootc rollback`, and it refuses when a rollback is already queued, when there is no previous deployment, or when it already rolled away from this one; enabled on x86 and ARM; `tests/test_boot_assessment.py` | Stable mechanism/artifact evidence recorded; preserve required gates | Correct installed boot assessment and fallback; physical bad-update journey remains separate. |
| P1.3 | `moos-list-disks` now reads TRAN, so soldered eMMC is no longer called removable (which could make a tablet only disk refusable) and eMMC boot/RPMB areas are not offered; `tests/test_installer_storage_policy.py` drives SATA/NVMe/USB/eMMC/SD fixtures, target-only mutation and the live-medium rules; the installer pins LC_ALL=C so the actionable low-space and disk-io messages survive a non-English session; no-encryption is recorded as a deliberate decision with the condition for revisiting | Stable mechanism/artifact evidence recorded; preserve required gates | Target-only installer storage, removable/live-disk refusal and safe partition/boot ownership. |
| P1.4 | `/usr/libexec/moos-support-bundle` with per-section and whole-bundle caps; redaction proven in `tests/test_support_bundle_redaction.py` and on this machine (51.6 KB, 13 sections, no live address, MAC, home path or credential shape); PR #102 | Implemented/delivered within recorded scope; wider acceptance remains; new audit corrections await signed delivery | Every collected output redacted before truncation; no credential-file reads; private bounded atomic export. |
| P1.5 | `moos-image-update` publishes one atomic record that the Updater window and the journal both read; `tests/test_update_state_machine.py`; PR #102 | Stable mechanism/artifact evidence recorded; preserve required gates | Atomic truthful update state, stale/dead PID handling and meaningful failure UI. |
| P1.6 | Store metadata, dictionaries, locale, drivers and Help remain useful; cloud-only features explain connectivity clearly | Open / acceptance not complete | Fresh offline files/media/Help/store/locale/dictionaries; cloud functions state connectivity needs. |
| P1.7 | gateway, control, agent API, Settings snapshot and Store job schemas; stale/dead/partial response, timeout, restart and same-host cross-user negative tests. **2026-10-04 source:** shared kernel socket-UID guard on all three HTTP APIs; positive live-loopback and negative identity/unknown-record tests. Installed upgrade/reboot and server impersonation remain open. | Open / acceptance not complete | Versioned native/API schemas, partial/stale/dead responses, timeout/restart and adapter failure tests. |

## P2 — Unified desktop

| ID | Outcome | Current boundary | Required acceptance |
| --- | --- | --- | --- |
| P2.1 | Native MoOS modules inside KDE System Settings | Implemented/delivered within recorded scope; wider acceptance remains | Installed native loader, every MoOS module and backend; readback and keyboard/locale/scale frames. |
| P2.2 | One Settings entry and stable application identity | Implemented/delivered within recorded scope; wider acceptance remains | One actual System Settings identity/window and correct native destinations from all entry points. |
| P2.3 | One qualified Arabic/English locale authority | Arabic session works; new lock/Mira startup correction in source; cross-app unity remains | KDE/QML/GTK/Mira/MoPlayer/Flatpak selection after relogin/reboot; Arabic first, English supported. |
| P2.4 | Keyboard and screen-reader operation | Open / acceptance not complete | Real keyboard traversal/focus and Orca Arabic/English on all primary flows. |
| P2.5 | Visual, contrast, scale and reduced-motion matrix | Open / acceptance not complete | 1080p–4K, 100–250%, Arabic RTL/English LTR, light/dark, reduced motion and measured readable contrast. |
| P2.6 | Asset reachability and removal of retired UI | Open: archived translucent-dialog prototype retained, but current-theme blur-off qualification/integration remains | Generator/runtime/test consumers proven; retain negative fixtures and required upstream notices; never restore obsolete generated assets over today's theme. |
| P2.7 | Horizon feedback, clock input and system sound | Open / acceptance not complete | Finite stable-hit feedback, reversal/hidden/reduced-motion proof, clock keys and actual event sound. |
| P2.8 | MoOS Bar, Search and Island as one shell | Open / acceptance not complete | Native accessible Search/Island/Bar, keyboard escape, multi-context tabs and truthful lifecycle tokens. |
| P2.9 | User-visible MoOS identity on every surface | Implemented/delivered within recorded scope; wider acceptance remains | Unchanged identity gates plus actual login/boot/desktop/app surfaces; legal attribution preserved. |
| P2.10 | Readable text and glyph contrast on every palette | Open / acceptance not complete | All schemes meet role-specific contrast; actual glyph/card/pointer frames instead of token names. |
| P2.11 | Visible, bilingual update changes | Implemented/delivered within recorded scope; wider acceptance remains | Readable current entries and working routes, delivered update/notification readback. |
| P2.12 | One update surface for OS, apps and firmware | Open / acceptance not complete | OS image, Flatpak apps and firmware share truthful pending/failure/unsupported/finished states. |
| P2.13 | MoPlayer performance and server/stream compatibility | Implemented/delivered within recorded scope; wider acceptance remains | Installed playback/reopen/stop and memory on real server kinds, MAC portal, HEVC/interlaced samples. |
| P2.14 | Remote input, recovery and mobile/WAN video | Implemented/delivered within recorded scope; wider acceptance remains | Held-input ownership, decoded pictures, browser recovery and owner iPhone/cellular endurance. |
| P2.15 | Mira face, speech/rest and original portrait identity | Implemented/delivered within recorded scope; live local-wake capture triggers USB overruns even on a muted source; wider acceptance remains | Both portraits retained; single mouth, real voice/pause/idle/hidden/reduced-motion readback; capture-device/mute policy and USB audio qualification. |
| P2.16 | Shared login, lock and power experience | Implemented/delivered within recorded scope; wider acceptance remains | Native greeters 640×480–4K@2.5, password refusal, multi-user, save/logout and accessibility. |

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
| P4.1 | Unify every install/update/remove request behind Mo Store | Open / acceptance not complete | Store authority for every engine; shared job IDs, cancel/retry/remove and final readback. |
| P4.2 | Audit desktop-app permissions and prefer portals | Open / acceptance not complete | Permission inventory and actual file/camera/screen/print portals without broad grants. |
| P4.3 | Turn Windows compatibility into a per-app runner product | Open / acceptance not complete | Ten Windows apps with isolated prefixes and install/launch/reopen/update/remove evidence. |
| P4.4 | Turn Android compatibility into a per-app product | Open / acceptance not complete | Ten Android apps, on-demand container, files/clipboard/audio and NVIDIA fallback. |
| P4.5 | Publish a generated compatibility matrix | Open / acceptance not complete | Generated version/edition/architecture/GPU compatibility matrix, including unsupported cases. |
| P4.6 | Consent-based App Drop for files | Implemented/delivered within recorded scope; wider acceptance remains | Real magic, sandbox extraction, default-No consent, safe launchers and all entry paths. |
| P4.7 | Native Store picker/drop through App Drop | Implemented/delivered within recorded scope; wider acceptance remains | Actual QML picker/drop delegates to App Drop, valid local files, refusal/cancel and Store job. |

## P5 — Hardware and performance

| ID | Outcome | Current boundary | Required acceptance |
| --- | --- | --- | --- |
| P5.1 | Hardware qualification lab | Open: station USB capture overruns reproduced; Home Assistant Bluetooth/DHCP/duplicate entities and first-start protocol failure remain | GPU/audio/network/Bluetooth/camera/storage/firmware records across actual hardware; distinguish host hardware from rootless home-hub integration faults. |
| P5.2 | Laptop policy | Open / acceptance not complete | Three laptop classes, lid/battery/brightness/power and two suspend cycles each. |
| P5.3 | Touch/tablet policy | Open / acceptance not complete | Actual touch/tablet targets, keyboard/rotation/gestures/stylus and ≥44px controls. |
| P5.4 | Performance budgets | Open / acceptance not complete | Measured boot/idle PSS/CPU/wakeups, app launch p95, frame pacing, build load and AI latency per tier. |
| P5.5 | Cloud desktop efficiency | Implemented/delivered within recorded scope; wider acceptance remains | Efficient cloud desktop plus actual private files/photos/IDE access, phone background and off-host restore. |
| P5.6 | Storage lifecycle | Open: NVIDIA cleanup restores headroom and preserves source/checkpoints/rollback; sustainable limits still owed | Headroom, cache/log bounds, low-space recovery and cleanup that never removes owner data. |
| P5.7 | Qualify kernel policy and driver transitions | Open: recorded Oracle oomd has no monitored cgroup; NVIDIA station monitors system/user groups, but pressure-recovery qualification is owed | Kernel/driver readback and measured frame/audio/CPU/RAM policy; oomd running is not applied monitoring. |
| P5.8 | Qualify Wayland and compositor lifetime | Open / acceptance not complete | Portal consent/revocation/restart, output/scale/hotplug, clipboard/input and long session-return soak. |

## P6 — Long-term release trust

| ID | Outcome | Current boundary | Required acceptance |
| --- | --- | --- | --- |
| P6.1 | Resolve immutable base inputs once per release | Open / acceptance not complete | Immutable base inputs recorded once and consumed consistently by all same-architecture editions. |
| P6.2 | Produce SBOM and provenance for each image | Open / acceptance not complete | Exact digest-linked SBOM/provenance on a separately budgeted workflow, not release-critical disk exhaustion. |
| P6.3 | Security-release cadence for all editions | Open / acceptance not complete | Proven release cycles deliver security updates; schedules only build candidates. |
| P6.4 | Add staged rollout and release health | Open / acceptance not complete | Staged rings, halt/rollback criteria and actual field release health. |
| P6.5 | URL, Remote, AI and diagnostic security boundaries | Implemented/delivered within recorded scope; wider acceptance remains; new audit corrections await signed delivery | Auth/UID/URL/PIN/upload/secret boundaries and failure controls; native dependency advisories refuse release. |
| P6.6 | Establish support lifecycle and migration policy | Open / acceptance not complete | Published support/upgrade/rollback/EOL policy plus clear licences, attribution and official identity. |
| P6.7 | Reviewed Plasma seams before upstream transitions | Implemented/delivered within recorded scope; wider acceptance remains | Actual next-Plasma canary, registered reviewed seams and old/broken/native controls. |
| P6.8 | Separate reviewed next-base transition lane | Open / acceptance not complete | Reviewed next-base packages, all native seams/boot/apps/identity gates and migration/support qualification. |
| P6.9 | Native user/developer participation | Owner-requested: private support conversations and optional public suggestions; implementation open | Real authenticated service/client, private image attachments, account isolation and bounded uploads, admin moderation, retry/offline and promoted-release notifications; no secrets or automatic screenshots. |

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
