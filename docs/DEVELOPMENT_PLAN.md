# MoOS development plan

This is the only product development plan. It replaces the former completion,
system, x86, unified-platform, visual and remote-v40 plans. Current evidence is
in [`PROJECT_STATE.md`](../PROJECT_STATE.md); release mechanics are in
[`RELEASE.md`](../RELEASE.md).

**How this plan is worked:** P0–P6 are product work streams, not a command to
stop all visible work behind hardware that is unavailable today. Active boot,
security and data-loss defects pre-empt everything; otherwise follow the
milestone map below and finish a coherent user journey across its owners. Run
targeted tests and `just check` as the batch develops, then one full image build,
QCOW2/ISO/ARM proof set and promotion at the milestone boundary. The scheduling
rules are in `AGENTS.md`
("How MoOS work is scheduled"); the release cycle itself is one command,
`scripts/release-candidate.sh`.

## Product outcome

MoOS must be a coherent operating-system product rather than a collection of
packages and themes. The target is competitive quality in the areas users feel:
reliable boot and recovery, safe updates, hardware adaptation, one visual and
language system, a trustworthy application model, accessible input and output,
fast interaction, and an AI operator whose actions are explicit and bounded.

Competition with macOS, Windows and Android is a quality benchmark, not a claim
of API compatibility or feature parity. MoOS should reuse mature upstream
components and own the integration, defaults, verification and recovery paths.

## MoOS Experience Program

**The goal is a desktop computer that feels like one product called MoOS** —
fast, calm, beautiful and obviously its own — with the reliability of an
image-based system. macOS, Windows, Android and iOS are the quality bar for
feel and polish; they are not API targets, and no claim of being "better" is
made without measured evidence. Plasma, KWin and Wayland stay the engine: MoOS
owns every surface the user sees and every default, never a fork.

### One vocabulary

User-facing names are MoOS names. Technical IDs (`org.moos.nova.clock`,
`MoOSUI2*`, `org.moos.ui2.*`, KDE package and D-Bus names, licence notices) stay
stable and are never renamed for branding. Every agent uses these words in plans,
commits and UI text:

| Name | What the user experiences | Owners in the tree |
| --- | --- | --- |
| **MoOS UI** | one palette, type, icon, corner and motion system everywhere | `artwork/` generators, `org/moos/ui`, Plasma Style, Aurorae |
| **MoOS Bar** | the one floating glass bar | `moos-bar.conf`, `moos-bar-apply`, layout template, stock task manager |
| **MoOS Search** | one anchored search surface with an Ask Mo AI hand-off | `org.moos.search`, Milou/KRunner runners, `moos-open` |
| **MoOS Island** | the living context zone: Remote, media, later jobs and privacy | `org.moos.island`, MPRIS, Remote presence, job owners |
| **MoOS Hub** | time, weather and device health on the desktop, user-controlled | `org.moos.ui2.wallpaper` (desktop scene) |
| **MoOS Workspace** | windows, overview, tiling, desktops and window frames | KWin effects/config, generated Aurorae, `moos-visual-tier` |
| **MoOS Intro** | boot → login → first desktop as one continuous scene | Plymouth generator, login theme, splash, `apps/welcome` |
| **MoOS Motion** | finite spring feedback, same rhythm in shell and apps | `SpringFeedback.qml`, `Tokens.qml`, KWin durations, reduced motion |
| **MoOS Sound** | original event sounds that mark outcomes, not hovers | `usr/share/sounds/moos`, KDE notification events |
| **MoOS Shield** | identity lock, signed updates, boot fallback, rollback, privacy | identity firewalls, cosign policy, `moos-boot-assess`, Recovery |
| **MoOS Speed** | hardware-tiered visuals and measured idle/boot/launch budgets | `moos-visual-tier`, `moos-hardware-adapt`, P5.4 harness |
| **Mo Store / Mo AI / MoPlayer / Mo PC Remote** | first-party apps | their own directories and `moai-do` |

**Identity lock.** No user-visible surface may show Fedora, Red Hat or another
OS's name or logo (three build firewalls enforce it). Plasma/KDE names that users
see in MoOS-owned surfaces are replaced by MoOS names; upstream application names,
licence text and diagnostics are left intact. **Disk encryption** is a deliberate
later item (MoOS Shield, M4): offer it only when the offline installer can enrol a
TPM2 key and that key is proven to survive an image update — a passphrase prompt
without that enrolment would lock owners out of headless and docked machines.

### Waves — what "big batch" means here

A wave is one coherent, user-visible release. It is implemented on one branch,
reviewed live, gated once, merged once and proven once.

| Wave | Milestone | User-visible content | State |
| --- | --- | --- | --- |
| W1 | M1 | MoOS Search surface, settling Remote chip, clock rail, localized Hub, keyboard-safe Search/Island, in-tree MoPlayer, hardened ISO proof | **installed** on the station as `44.20260916.848` |
| W2 | M1 | MoOS Hub controls (desktop right-click show/hide and per-card toggles, wallpaper page), review-shadow retirement, unified instructions and this program | merged (`8b272b87`); ARM production; its x86 cycle stopped on the ISO proof (run `35158666486`: second boot healthy on QGA, SSH banner timeout), so x86 ships it with W3–W5 |
| W3 | M1 | The owner controls the desk: every widget removable again (THEME_REV 60), a wallpaper chosen anywhere stays after login and drift checks, release watcher reads real run results | merged (`2e6f7686`, PR #109), reviewed live on the station; ARM production; x86 built green, never proven |
| W4 | M3 | **Mo AI as the system harness:** the cloud brain (free or paid, OpenRouter or OpenCode Zen) receives native tool schemas generated from the fixed `moai-do` and `moos-control` grammar; read-only tools run directly, every change shows a confirmation card, the fixed executor acts, and the result is read back into the conversation (P3.3, P3.4, P3.7) | merged (`009b4b58`, PR #110); ARM production; x86 unreleased; the ≥95% action-selection measurement and a station review are still owed, so P3.3/P3.4/P3.7 stay open |
| W5 | M1 | MoOS Island jobs (Store installs, updates, downloads) and privacy chips (camera, microphone, screen share); Search inline answers (calculator, units, file actions) | merged (`7f182689`, PR #111); ARM production (`44.20260917.431`); it turned x86 `main` red and shipped without its `THEME_REV` bump — both repaired by the 2026-09-17 integration (rev 61); no station review recorded |
| W6 | M1+M3 | **What W4 and W5 promised, working, plus App Drop.** Mo AI's tool loop runs on every machine, in steps, with ten read-only inspection tools and truthful results (P3.3, P3.4, P3.7, P3.8); the Island really shows Store jobs and names the app behind a privacy chip; a downloaded AppImage or portable archive dropped into Applications becomes an app (P4.6); secondary text is readable on every scheme; MoOS-owned text no longer names another desktop | in review on `feat/w6-operator-appdrop-workspace-20260917`; gates green, rendered from source, **not seen on a MoOS desktop** |
| W7 | M2 | MoOS Workspace: MoOS-styled overview, one-click tiling layouts, window open/close/minimise durations taken from MoOS Motion, gesture and touchpad defaults | planned — needs a live KWin session; see "Workspace facts" below |
| W8 | M2 | MoOS Intro: one horizon scene from Plymouth through login to the Hub; first-run tour; offline first run (P1.6) | planned |
| W9 | M2 | System surfaces on MoOS UI: Updater, Recovery, Remote centre, Settings front door (P2.1–P2.2), a MoOS-owned About page (P2.9) | planned |
| W10 | M3 | Mo Store as one job system for install/update/remove across the UI, Mo AI and URL routes, with a drop target in its own window (P1.7, P4.1–P4.2, P4.7) | planned |
| W11+ | M4–M5 | hardware breadth, compatibility products, MoOS Shield encryption, release trust | planned |

### Ideas worth building (each needs its owner and a proof before it ships)

- **Living Island:** one foreground state with a deterministic priority
  (Remote > call/screen share > recording > install/update job > media), a
  spring expansion that settles, and a history popover of finished work.
- **Hub stacks:** each Hub card becomes a small stack (time → calendar → world
  clock; weather → hourly; device → network/battery) that the user scrolls
  through with the wheel, never auto-rotating.
- **Search that answers:** inline calculator/unit/currency rows, file rows with
  open-folder/copy-path actions, and a Mo AI row that streams a short answer
  before the user commits to the chat.
- **Arrange in one click:** a Bar or overview popover with KWin tiling presets
  (halves, thirds, 2+1) and a live preview of the user's own windows.
- **Motion with meaning:** window open/close/minimise and popup durations derive
  from the same MoOS Motion tokens as QML springs; one "calm / lively" switch
  drives both, and Reduced Motion stops both at once.
- **Quiet privacy:** camera, microphone and screen-share indicators appear in the
  Island with the owning app's name and a one-tap stop.

Anything that would replace KWin, fork Plasma, add an always-running animation
or weaken a gate is out of scope, however attractive it looks.

### How an agent executes a wave

```bash
# 0. Orient: never start a duplicate release; never touch another agent's worktree.
git fetch --prune origin && git worktree list
systemctl --user list-units 'moos-release-*' ; gh run list --limit 10
# 1. One branch for the wave, from the newest main (or from an unmerged wave it builds on).
git worktree add -b feat/<wave> ~/.cache/<wave> origin/main
# 2. Implement the whole wave. Review it on the live desktop with TEMPORARY package
#    shadows (copy the package to ~/.local/share/plasma/{plasmoids,wallpapers}/,
#    `systemctl --user restart plasma-plasmashell.service`, capture with
#    `spectacle -b -n -f -o …`), driving it with a temporary applet shortcut and
#    `YDOTOOL_SOCKET=$XDG_RUNTIME_DIR/.ydotool_socket ydotool`. Restore layouts,
#    shortcuts and config you changed. THEME_REV sweeps first-party shadows on update.
# 3. Fast gates once, not per edit.
python3 tests/<affected>.py ; flatpak-spawn --host just check
just build-nvidia            # only when a Tier 1 file changed
# 4. One PR, merge after Repo gates (never while a release runner freezes main).
gh pr create … ; gh pr merge <n> --merge
# 5. One release for the wave, supervised outside the chat session.
systemd-run --user --unit=moos-release-<wave> --collect \
  --property=StandardOutput=file:$HOME/.cache/moos-release-<wave>.log \
  bash scripts/release-candidate.sh --promote
# 6. A red proof: read the failed step AND its proof artifact, fix on a new branch,
#    dispatch fresh (never "Re-run jobs"). Green: the owner stages the update
#    (Updater or `moai-do update`) and reboots; the agent reads the result back
#    from /usr and records it in PROJECT_STATE.md.
```

### Working off the station (Windows, macOS, a cloud VM)

An agent that is not on the MoOS workstation cannot restart plasmashell, but it is not blind.
Use a disposable Fedora development distro (WSL2, Toolbx, a container) — never a MoOS host:

```bash
sudo scripts/review/setup-review-distro.sh            # once: Qt 6 / KF6 QML stack, fonts, MoOS assets
scripts/review/mirror-gates.sh                        # all repo gates, on a native-filesystem mirror
scripts/review/mirror-gates.sh tests/test_app_drop.py # or just the ones a change touches
scripts/review/render-app.sh moai /tmp/moai-ar.png --lang=ar
scripts/review/render-app.sh store /tmp/store.png --scheme=MoOSUI2AuroraLight
```

`mirror-gates.sh` exists because a Windows drive seen from WSL reports every file as executable;
it mirrors the working tree and applies the modes git records. `render-app.sh` draws a first-party
app FROM SOURCE with a real MoOS colour scheme and prints the QML runtime's binding errors — it
is how an undefined colour in Mo AI's privileged-action card, a dead file read in the Island and
1.6:1 secondary text were found while every gate was green. It is source-harness evidence: it
cannot show plasmoids, KWin, the greeter or an installed image, and a frame from it is never a
desktop review. Say which evidence you have.

Two traps cost an hour each on 2026-09-17. A here-document passed through some agent shells has
its backslashes halved, so `\\n` written into a patch becomes a real newline inside a QML or
Python string: write patch scripts to a file, or edit directly. And `qmlformat` rejects Mo AI's
8000-line `main.qml` on `main` too — it is not a syntax check for this file; the QML engine is.

## Current engineering brief

The owner's requests converge on one product, not a new desktop rewrite:
keep the working offline-installed MoOS workstation, improve its existing
Horizon dock/UI, complete native sound and physical feedback, integrate stable
KDE/Wayland, make cloud AI truthful, and deliver the same result in signed ISOs.
Repository cleanup and engineering instructions support that work; screenshots,
old plans and extra packages are not product progress.

**Active milestone: M1, the daily MoOS desktop journey.** x86 production is W1
(`92248b5d`, `44.20260916.848`): Horizon 2 with one anchored MoOS Search, the
compact Remote island, the localized Hub, the clock rail and keyboard-safe
Search/Island. Waves W2–W5 are merged and are ARM production, but no x86 cycle
has completed for them; the wave table above says why for each. **The next
action for any agent is the x86 release cycle**, not another wave on top of five
unreleased ones: every extra unreleased wave widens what one red proof blocks.

Release cycle A (2026-09-17, candidate `51cc2ac3`, the integration that made
`main` green again) proved the signed build of all three editions (run
`35250170484`) and all three QCOW2 boots (`35252506869`, `35252511348`,
`35252516097`), and then lost the ISO proof (`35252520329`) to row P0.8 — the
third candidate that harness defect has cost. Its fix changes a proof script, so
it is a new revision and every proof must be run again: cycle B therefore
carries the integration, the P0.8 fix and wave W6 as ONE candidate. If cycle B's
signed build fails an image-only gate, fix it on the wave branch and dispatch a
fresh cycle (never "Re-run jobs"); if only the ISO proof fails, read
`reboot-channel.txt` and `reboot-channel-error.txt` in its artifact FIRST.

| Requested outcome | Work stream | What must actually be proven |
| --- | --- | --- |
| One clean project any agent can continue | Documentation policy + workstation profile | One state/plan; fresh branch ancestry; reproducible component checks |
| Reliable offline install/update/recovery | P0–P1 | Exact signed artifact boots twice; target-only disk writes; rollback works |
| Distinctive existing MoOS UI/dock/sounds | P2, active P2.7 | Real input/render/audio, Arabic/English, reduced motion and mute |
| Kernel/CPU/GPU/RAM work together | P5 | Actual policy/driver readback, pressure/frame/audio and thermal measurements |
| Unified core and APIs | P1.7 + P3/P4 | Schema, lifecycle, authorization and UI/backend agreement under failure |
| Free cloud intelligence actually replies | P0.5 + P3 | Approved key, free-policy reply, error recovery, no invented task completion |
| Same product on physical, cloud and ARM | P0 + P6 | Separate exact-edition/architecture proofs; no extrapolation from this PC |

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
6. Mo Store is the target application-lifecycle authority; convergence is not
   complete (`moai-do setup-windows` still installs Bottles directly). Desktop applications
   use sandboxing and portals by default; system drivers and services stay in
   the signed OS image.
7. Mo AI is cloud-only. Free service is the default, paid providers require an
   explicit choice, and credentials remain private user state.
8. A build, a local image, a published candidate, a booted artifact and a
   promoted release are different states and must never be conflated.
9. MoPlayer is a first-party in-tree application. `moplayer/` is its only source;
   x86 and ARM build and test it directly and install only the resulting bundle.
   No external MoPlayer branch, release archive or nested workflow participates.

## Baseline on 2026-09-13

The physical development machine runs Plasma/KWin 6.7.5, kernel 7.2.4,
systemd 259.8, bootc 1.16.10 and NVIDIA 615.71.09. Plasma 6.7.5 is the current
stable bug-fix release. Plasma 6.8 is in beta and its public release is scheduled
for 2026-10-14; MoOS must not replace a proven stable desktop with the beta.
Upgrade when the stable stack reaches the shared image base and passes the full
visual, QML, boot and hardware matrix.^1 ^2

The first physical offline installation and NVIDIA boot succeeded. The current
branch's complete NVIDIA image build also passed. The unresolved product gaps
are cloud-AI setup, hardware qualification breadth, deliberate rollback,
cross-edition exact-commit proofs, remaining older first-party UI surfaces,
language coherence and compatibility-product acceptance.

## Release scorecard

Every release records these values for the exact promoted digest:

| Dimension | Required evidence | Release target |
| --- | --- | --- |
| Boot | firmware-to-login and login-to-desktop timings | no regression >10%; no failed unit |
| Update | check, stage, reboot, readback | signed digest booted; previous deployment retained |
| Recovery | deliberate bad candidate and rollback | user data intact; old deployment boots |
| NVIDIA | kernel/kmod match, initramfs, journal, Wayland | no fallback driver or fatal NVRM event |
| Desktop | 1080p/1440p/4K, 100–250%, RTL/LTR | no clipping, dead action or foreign identity |
| Accessibility | keyboard traversal, screen reader, contrast, reduced motion | every primary flow usable without pointer |
| Applications | install, launch, reopen, update, remove | one authority and truthful progress/readback |
| Mo AI | setup, latency, tool accuracy, provider failure | ≥95% action selection; p50 first token ≤2 s |
| Idle | CPU, PSS, wakeups, disk/network | measured budget per hardware tier |
| Suspend | two cycles plus audio/network/display recovery | zero failed unit or lost device |
| Offline install | blank disk through second installed boot | no network dependency; only target disk changed |

Targets are gates only after the measurement harness is committed. A missing
measurement is `not proven`, never a pass.

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

### P0 — Establish one proven release

P0 is complete only when the cleaned source is published as one exact signed
revision and all required editions/artifacts prove that revision.

| ID | Status | Task | Exit evidence |
| --- | --- | --- | --- |
| P0.1 | Complete | Integrate the reviewed first-install repairs and create one candidate revision | PR #92 merged as `b6a72ad2`; signed candidate revision `1d92082f`, build run 34785063649 |
| P0.2 | Complete | Run generic, NVIDIA and cloud QCOW2 proofs plus offline ISO install/second boot | QCOW2 runs 34786215189/34786216334/34786218085 and offline ISO run 34786220039 succeeded on the exact candidate |
| P0.3 | Open | Finish physical NVIDIA qualification | Plymouth/login photos; two suspend cycles; audio/network recovery; second monitor; clean journal |
| P0.4 | Open | Prove failed-update recovery | disposable VM bad-candidate rollback, then hardware rollback/roll-forward with user data intact |
| P0.5 | Open | Configure and accept free Mo AI on a clean account | valid OpenRouter key entered through Settings; Arabic/English reply; reboot persistence; provider failure UI |
| P0.6 | **In progress** | Promote only the proven digests and update the physical PC | W1 (`92248b5d`, `44.20260916.848`) is promoted for x86; the station still boots `44.20260915.836` until the staged update is rebooted and read back |
| P0.7 | Open | Remove the intermittent ARM second-boot `plymouthd` crash | SEGV in `on_new_frame` failed ARM runs on 2026-09-15 and `35150466421`; reproduce with ARM-only branch dispatches, fix without weakening the zero-failed-unit gate, then two consecutive green ARM proofs **after a fix** (the W3 and W5 runs were green with none, which proves intermittency only) |
| P0.8 | Open — fix written, unproven | Make the ISO installed-reboot proof deterministic | lost THREE candidates out of four at the same point (`57874d6c`, `8b272b87`, and `51cc2ac3` in run `35252520329` on 2026-09-17): after the guest reboot SSH timed out "during banner exchange" for 1000 s while QGA reported the second boot, `:22` listened and `systemctl --failed` was empty. `tests/boot_x86_qcow2.sh` had documented the cause on 2026-09-03 — slirp can keep pre-reboot flow state on a forward and then accept TCP without delivering a banner — and reserves one forward per boot; the ISO proof was given its reboot half on 2026-09-16 with ONE forward. `install_live_iso.sh` now reserves two and switches at the reboot request (`ebd694fb`). **Read `reboot-channel.txt` in the next ISO proof artifact:** a green run now measures the first-boot forward afterwards. `dead` confirms the explanation; `alive` means the fresh forward is not what made the run pass and this row is still a hunt. Close after three consecutive green ISO proofs. Also hardened while reading (never known to have lost): the proof-channel helper read the default route once although wait-online is disabled, and said nothing on the console — `tests/test_ci_proof_channel.py` |
| P0.9 | Open | Run image-only gates before the merge | `build.yml` does not run on pull requests and `build-arm.sh` does not call `verify_image_experience.py`, so W5 was green on every check and red on `main`. The router parser is now covered by `tests/test_image_gate_source_parser.py`; remaining: give each source-readable section of the image gates a `MOOS_TEST_ROOT=system_files` mode (as `verify_store_catalog.py` has) and call it from `tests/repo-gates.sh`, or build one x86 edition on pull requests that touch `system_files/`, `build_files/` or a Containerfile |

Repository cleanup is complete: retired plans/evidence/assets were removed,
and all 14 historical remote branches were proven ancestors of `main` before
deleting their refs. PR #92 is merged. Its earlier green Claude job did not
complete review; never count that job as review evidence.

The engineering-instructions slice now distinguishes source, live workstation,
container and signed-artifact evidence; it includes a host/Flatpak preflight and
a live-review reference. Realistic independent skill scenarios exposed and
removed an unsigned-local deployment recipe and false-success shell checks.
The Settings visual harness also rejects stale normal-state status, after a
real English review exposed disabled actions hidden by passing keyboard tests.

bootc stages updates without changing the running deployment and exposes an
explicit rollback verb.^3 MoOS already builds on this behavior; P0.4 tests it
instead of inventing another updater. The current update lock and edition-switch
preservation must be exercised during P0.2.

### P1 — Reliability and first-run platform

| ID | Task | Exit evidence |
| --- | --- | --- |
| P1.1 | **Complete:** Make every first-boot migration versioned, idempotent and transaction-safe | every migration records id/revision/outcome in one append-only ledger; the two-key wallet write is staged and renamed so an interruption leaves the original file; interrupted, repeated and clean-vs-upgraded fixtures in `tests/test_migration_ledger.py` |
| P1.2 | **Complete:** Add boot-success health and automatic fallback design compatible with the actual boot loader | `moos-boot-assess` counts unblessed boots in `/var/lib/moos` because `/boot` is read-only and greenboot is absent; three unblessed boots return to the previous deployment through `bootc rollback`, and it refuses when a rollback is already queued, when there is no previous deployment, or when it already rolled away from this one; enabled on x86 and ARM; `tests/test_boot_assessment.py` |
| P1.3 | **Complete:** Make offline installer storage policy hardware-safe | `moos-list-disks` now reads TRAN, so soldered eMMC is no longer called removable (which could make a tablet only disk refusable) and eMMC boot/RPMB areas are not offered; `tests/test_installer_storage_policy.py` drives SATA/NVMe/USB/eMMC/SD fixtures, target-only mutation and the live-medium rules; the installer pins LC_ALL=C so the actionable low-space and disk-io messages survive a non-English session; no-encryption is recorded as a deliberate decision with the condition for revisiting |
| P1.4 | **Complete:** Build a redacted support bundle | `/usr/libexec/moos-support-bundle` with per-section and whole-bundle caps; redaction proven in `tests/test_support_bundle_redaction.py` and on this machine (51.6 KB, 13 sections, no live address, MAC, home path or credential shape); PR #102 |
| P1.5 | **Complete:** Establish update observability | `moos-image-update` publishes one atomic record that the Updater window and the journal both read; `tests/test_update_state_machine.py`; PR #102 |
| P1.6 | Qualify first-run without internet | Store metadata, dictionaries, locale, drivers and Help remain useful; cloud-only features explain connectivity clearly |
| P1.7 | Version and qualify core/API boundaries | gateway, control, agent API, Settings snapshot and Store job schemas; stale/dead/partial response, timeout, restart and same-host cross-user negative tests |

Core ownership is not one monolithic daemon. `moai-gateway` owns provider
requests; `moai-control` owns hardware/service control status; `moai-agent-api`
owns developer tasks; `moos-settings-status` owns the read-only Settings
snapshot; Store owns transaction jobs. Preserve those boundaries while giving
the UI typed/versioned contracts. A localhost bind and custom header alone do
not authenticate another local user. Check each service's actual identity and
permission boundary before adding a new caller.

Automatic boot assessment is a useful reference: a boot is marked good only
after explicit health units succeed, and repeated failures can select the prior
entry.^4 The implementation must fit MoOS's real GRUB/bootc layout; do not copy a
systemd-boot recipe without proving compatibility.

### P2 — One desktop experience

Implement through the existing owners below. KDE provides documented theme,
widget and window-decoration extension points; MoOS should use those supported
boundaries.^8 The actual display-manager unit takes precedence over generic
upstream examples that still describe SDDM.

| Surface | Existing owner | Integration rule |
| --- | --- | --- |
| Session, windows, display, input | Plasma/KWin Wayland, KScreen, input-method services | Read actual session capabilities; verify scale, screen capture and input through their real services |
| Palette, controls, app material | UI2 palette generators + `org/moos/ui` QML module | One geometry/type/icon system; dark/light and device tiers are tokens |
| Dock, launcher, desktop scene | `moos-bar.conf`, `moos-bar-apply`, MoOS plasmoids | One panel writer; existing and clean profiles converge after migration |
| Login, lock, splash | resolved display manager, MoOS shell theme, Plymouth | Same identity; exercise the real greeter and boot frames |
| Settings and service pages | MoOS Settings + owning backend | Read back actual state; existing standalone surfaces become tested links |
| Privileged operations and apps | `moai-do`, Mo Store transaction backend | Fixed action/confirmation; truthful progress and errors |

Within wave W9, the Updater leads P2.1: baseline its light/dark Arabic/English
frames and routes, move its controls onto shared UI2 and prove check/stage/error/
reboot-needed states. Recovery and Remote follow in the same wave once the
Updater passes its review, so no surface is left half-migrated and the wave still
ships as one release.

Observed polish gaps to include in P2.3/P2.5: the shared hardware summary still
renders the technical `nvidia (discrete)` label in Arabic; narrower English
trust text can elide. Translate presentation separately from hardware
classification, and retain the full accessible/error meaning at small widths.

**P2.5, measured 2026-09-17 on the Oracle A1 — Liquid Glass has no blur-less
fallback, and the material contract already requires one.** `MOOS_UI2_DESIGN.md`
says a Liquid Glass surface has "a palette-tinted fallback fill that works
without blur" and that "software rendering uses opaque or near-opaque
fallbacks ... through capability detection".
`org/moos/ui/GlassSurface.qml` implements no fallback: it sets `fillOpacity`
from a fixed token (`floatingGlassOpacity` 0.82, `glassRestingOpacity` 0.22)
whatever the machine can do. Those values are tuned for a machine whose
compositor smears what shows through.

This host is `llvmpipe` with no accelerated render node, so `moos-visual-tier`
correctly resolves the essential tier and writes `Plugins/blurEnabled=false` —
blur there would be paid on the CPU every frame. `qdbus6 …Effects.isEffectLoaded
blur` and `contrast` both answer `false`. The remaining ~18% is then not a
blurred wash but sharp content: in a capture of MoOS Search over a maximised
editor, the window's own body text reads straight through the results surface.
Every Liquid Glass surface inherits this, so it is one shared defect, not a
Search defect.

Not fixed here, deliberately. The installed QML stack exposes no blur-availability
API (`org/kde/kwindowsystem` and `plasma/core` qmltypes carry no `blurBehind` or
`isEffectAvailable`), so capability detection needs a mechanism MoOS does not yet
have; `moos-visual-tier` is the authority that should publish it, the way it
already publishes `file_indexing` to `moos-index-policy`. And this machine has no
GPU, so the blur-present path cannot be reviewed from it — changing the shared
glass material for every surface on evidence from one tier is exactly the
unverified change the engineering skill forbids. Implement it against both tiers,
with the flagship frames captured on the station.

| ID | Task | Exit evidence |
| --- | --- | --- |
| P2.1 | Move Updater, Recovery and Remote control center onto the shared UI2 component/token layer | live dark/light 4K captures; no private palette implementation |
| P2.2 | Make Settings the front door for themes, updates, recovery, devices, Remote and AI providers | standalone launchers become tested deep links; no duplicate authority |
| P2.3 | Create one locale authority for Arabic, English and German | every first-party app, date/number format and keyboard follows one selection after login/reboot |
| P2.4 | Complete keyboard and screen-reader operation | primary flows traversed with real keys; Orca reads Arabic and English; focus never disappears |
| P2.5 | Run the visual matrix | 1080p–4K, 100–250%, RTL/LTR, light/dark, reduced motion; measured contrast and no clipping |
| P2.6 | Remove remaining retired UI names/assets and enforce reachability | generated asset manifest; every shipped asset has a runtime/generator/test consumer |
| P2.7 | **Active:** complete existing Horizon feedback, clock input and original system sound | Shared finite spring with stable hit targets; reversal/hidden/reduced-motion tests; real clock keys; KDE event playback and mute/custom overrides; image and upgraded-session proof |
| P2.9 | Finish the identity lock on text MoOS displays | **In source (W6):** Mo AI's Apps panel, its system prompt, Mo Store's Sources page, a Settings error dialog, MoPlayer's store page and two unit descriptions no longer name another desktop; `tests/test_user_visible_identity.py` reads QML prose, bilingual messages, dialogs, unit descriptions, AppStream and desktop entries. **In source (after W6, `feat/about-this-device-20260917`):** Settings → About this device is MoOS's own page inside MoOS Settings — edition in words, version, build date, signed image, rollback, the kernel as its number (the release string carries the packager's build tag), processor, graphics, memory, storage, architecture, Copy details; `moos://settings/about` lands on it in a running window; every row says Unknown in words without the feed (`tests/test_settings_about_page.py`). Rendered from source in Arabic and English, light and dark, 1180–1400 px; **not seen on a MoOS desktop**. **Open:** the cloud edition's firewalld `DefaultZone` is still the base's server zone name (`build.sh`, Tier 1): ship `moos-server.xml` beside `moos-desktop.xml` |
| P2.10 | Readable text on every scheme | **In source (W6):** secondary text was the DISABLED role — 1.6:1 on light schemes; all five apps now use text at 72% (≥4.66:1 on all 16 schemes), held by `tests/test_secondary_text_contrast.py`. **Open:** the same arithmetic for plasmoids, the launcher and the greeter, and for state colours on tinted fills |
| P2.8 | **In progress:** compose MoOS Bar, Search and Island (experience goals 1–2 in `artwork/MOOS_UI2_DESIGN.md`) | one anchored Milou surface with recent apps/destinations/Mo AI, stale-result protection and complete keyboard escape/traversal; Remote keeps privacy priority while its popup can switch to media; native ≥40 px controls; localized clock/hub; typed queries reviewed live on the station (Arabic and German layouts: grouped app, settings and folder rows); MoOS Hub has desktop right-click controls; remaining: English/German session matrix and booted-candidate readback |

P2.7 retains the stock Plasma task manager and one existing panel writer. It
does not install an unrelated dock/effects pack. Qt's native spring provides
retargetable scale feedback; layout, text legibility and hit targets stay
stable.^9 Native KNotification event defaults must match the installed KDE
event IDs and yield to personal choices.^10 Asset presence or successful audio
decoding is not evidence of login/logout playback. Test both event delivery and
session volume, including notification quiet mode and per-event/global mute.
The local source and NVIDIA-image gates are complete at `0bdb289e`; candidate
boot and upgraded-session evidence remain required before this row can close.

**Workspace facts (W7), read from KWin 6.7.5's own `kwin.kcfg` on 2026-09-17, not remembered.**
What MoOS leaves unset is already a sensible default, so W7 is not a config dump:
`ElectricBorderMaximize=true`, `ElectricBorderTiling=true`, `ElectricBorderCornerRatio=0.25`
(drag to an edge or corner tiles), `BorderSnapZone=10`, `WindowSnapZone=10`,
`Placement=Centered`, `FocusStealingPreventionLevel=1`, `TitlebarDoubleClickCommand=Maximize`,
`[TabBox] LayoutName=thumbnail_grid`, `[NightColor] Active=false Mode=DarkLight
NightTemperature=4500`, `[Compositing] AllowTearing=true`, `[Xwayland]
XwaylandEavesdrops=Combinations`. `[Compositing] AnimationDurationFactor` does not exist; the
factor lives in `kdeglobals [KDE]` (already correct). Real W7 work is what cannot be set from a
file and judged from a gate: the look of Overview and the task switcher in MoOS UI, a tiling
popover, per-effect durations taken from MoOS Motion, gestures, and touchpad defaults (P5.2).
Every one needs a live session and a before/after capture.

Plasma 6 has no LTS branch and follows feature plus patch-release cycles.^1
MoOS therefore tracks stable releases through the shared base, keeps local
patches minimal, and runs its integration matrix on every Plasma transition.

### P3 — Mo AI as a trustworthy system operator

| ID | Task | Exit evidence |
| --- | --- | --- |
| P3.1 | Make provider setup self-diagnosing | distinguish missing key, invalid key, quota/billing, rate limit, outage and network failure without exposing secrets |
| P3.2 | Stream chat responses and show the answering model/provider in human language | measured first-token latency; cancellation and retry work |
| P3.3 | Generate native tool schemas from the `moai-do` allowlist | **In source (W6):** the schemas now reach the model on every machine (W4 attached them only when `!agentMode`, which defaults to true, so without Hermes they were never sent); every advertised value is run through the executor's own validator and every inspector combination through its own parser. **Open:** ≥95% correct action selection on fixed Arabic/English cases with a real free model — nothing here has been driven by one |
| P3.4 | Use explicit confirmation cards and execution readback | **In source (W6):** several calls per answer, up to eight steps per message, the executor decides what needs a card (`needs_confirmation`, including Wi-Fi/Bluetooth OFF), confirmed actions are jobs that end when the process ends, and a non-zero exit reaches the model as "did NOT succeed". `tests/test_moai_agent_loop.py` drives the real window against a scripted provider and the real `moai-control`. **Open:** "re-read from the owning subsystem" is still the executor's own output; a station review |
| P3.5 | Add free-provider health and bounded failover | zero-price policy enforced; unhealthy route cooldown; no silent paid fallback |
| P3.6 | Add optional, redacted device context | clear consent; inspectable payload; secret and personal-path rejection tests |
| P3.7 | Make task completion evidence-based | failed/missing tool results prevent a task-wide success; process exit 0 cannot mark unexecuted steps complete; cancellation/restart fixtures |
| P3.8 | **In source (W6):** let the operator LOOK before it acts | `moos-inspect`, a third executor beside `moai-do` and `moos-control`: ten read-only tools (failed units, one unit, the journal, top processes, memory, storage, network, installed apps, booted/staged/rollback versions, MoOS's own logs), closed grammar, fixed argv, never escalates, output redacted by the support bundle's `redact()`; `tests/test_moos_inspect.py`, `tests/test_moai_tool_schemas.py`. Open: measure which of them a free model actually chooses correctly (feeds P3.3) |
| P3.9 | **Owner decision:** an owner-enabled host shell for Mo AI | The owner asked on 2026-09-17 for an agent that "executes everything, with every permission", like a coding CLI. W6 deliberately stops short of that: the loop can inspect anything listed in P3.8 and run every fixed repair, but there is still no tool that runs a command the MODEL wrote, because that turns every web page and log line the model reads into a command source, and architecture rule 5 forbids it. If the owner confirms, the shape that keeps a person in the loop is: a `run_command` tool available only at the existing Settings → Permissions tier `system` or `full`; the exact command shown on the confirmation card; runs as the user, never root (polkit still asks the person for anything privileged); output redacted and bounded; one journal line per command; OFF by default; rule 5 and `AGENTS.md` rewritten in the same change. Not started |

Privileged OS operations remain fixed `moai-do` actions. The existing developer
runtime also exposes approved isolated project commands; that is a separate
capability, not permission to run generated commands as host administrator.
Audit approval, sandbox containment and task-result propagation explicitly.
No provider key crosses to another provider. A free route requiring billing is
unavailable, not successful configuration.

### P4 — Applications and compatibility

| ID | Task | Exit evidence |
| --- | --- | --- |
| P4.1 | Unify every install/update/remove request behind Mo Store | UI, Mo AI and URL routes share job IDs, progress, cancellation and readback |
| P4.2 | Audit desktop-app permissions and prefer portals | permission inventory; file/camera/screen/print flows work without broad filesystem or bus access |
| P4.3 | Turn Windows compatibility into a per-app runner product | isolated prefix per app; install/launch/reopen/update/remove for ten published test apps |
| P4.4 | Turn Android compatibility into a per-app product | on-demand container; launcher/files/clipboard/audio; ten test apps on Intel/AMD and NVIDIA fallback |
| P4.5 | Publish a generated compatibility matrix | supported/experimental/unsupported status names edition, architecture, GPU and tested version |
| P4.6 | **In source (W6):** App Drop — an application that arrives as a file | AppImage (extracted once inside bubblewrap into `~/Applications/<name>/`), portable archives (extracted by `moos_appdrop.py`, hostile members refused by name), Flathub `.flatpakref` (the ordinary verified path); `.rpm`/`.exe`/`.apk` handed to their existing routes; `.deb` and `.flatpak` bundles refused with the reason. Consent dialog with default No on every path; one Mo Store job (`moos-storectl install-file`). `tests/test_app_drop.py` builds the hostile files and runs the real sandbox. **Open:** a real AppImage on a MoOS machine; the dialog, the file-manager action and the `~/Applications` watch reviewed on a desktop; what a double-click on an AppImage did before (read from source, never observed); `.flatpak` bundles through libflatpak |
| P4.7 | A drop target in Mo Store's own window | needs a `Q_INVOKABLE installFile(path)` with a path validator in `build_files/moos-qml-shell.cpp` (the bridge's `validId` rejects paths) and a full image build; the Store must not use the public `moos:` scheme for it |

Flatpak sandboxes deny host access by default and portals provide controlled
access to files and services.^5 MoOS should keep per-user app development and
testing isolated; drivers and privileged services do not belong in a Flatpak.^6

### P5 — Hardware, performance and form factors

| ID | Task | Exit evidence |
| --- | --- | --- |
| P5.1 | Hardware qualification lab | repeatable GPU/audio/Wi-Fi/Bluetooth/camera/storage/firmware suite and published device records |
| P5.2 | Laptop policy | lid, brightness, battery health, power profiles and two suspend cycles on at least three platforms; **tap-to-click and natural scrolling by default** — KWin 6.7.5 stores libinput settings per device (`kcminputrc [Libinput][vendor][product][name]`, keys `TapToClick`, `NaturalScroll`, … confirmed in `libkwin.so`) and no system-wide defaults group was found, so a file in `/etc/xdg` would be dead config; the supported route is a one-time, ledger-recorded first-login step that sets the properties KWin exposes per device on D-Bus for touchpads the person has not configured. Needs a real laptop |
| P5.3 | Touch/tablet policy | automatic mode, ≥44 px targets, keyboard, rotation, gestures and stylus on real hardware |
| P5.4 | Performance budgets | boot, idle CPU/PSS/wakeups, app launch p95, scroll/frame pacing, build load and AI latency per tier. **Owed by W5:** `moos-privacy-monitor` polls PipeWire every 1.5 s for the whole session on every machine and was never measured; W6 cut it from three `pw-dump` spawns per round to one (12 ms → 4 ms on an idle pipewire 1.6.8), but its idle cost on the station and on the two-core A1 is unknown — measure it, and prefer `pw-dump --monitor` or a PipeWire registry listener if it shows |
| P5.5 | Cloud desktop efficiency | encode CPU/GPU, frame pacing, bandwidth degradation, reconnect, multiple accounts and audio sync |
| P5.6 | Storage lifecycle | update headroom, Flatpak/container cleanup, log bounds and low-space recovery without deleting user data |
| P5.7 | Qualify kernel policy and driver transitions | MoKernel sysctl/module/karg readback; exact kernel/NVIDIA match; boot/initramfs, frame pacing, audio underruns, CPU/RAM pressure and thermal/power regression measurements |
| P5.8 | Qualify Wayland and compositor lifetime | portal consent/revocation/restart; multi-output scale/hotplug; clipboard/input-layout continuity; separate users; long-session KWin PSS/pressure and recovery |

`mokernel` is MoOS's policy/readback wrapper around the signed Linux kernel,
not a forked kernel. `moos-visual-tier` selects visual budgets;
`moos-hardware-adapt` owns safe hardware initialization; device identity comes
from `moos_hardware.py`. Do not create rival tuners or infer performance from
configured values. The installed KWin memory guard is containment, not proof
that the historical growth cause is fixed. P5.8 must reproduce or rule out
growth with an explicit workload and duration.

### P6 — Release engineering and long-term trust

| ID | Task | Exit evidence |
| --- | --- | --- |
| P6.1 | Resolve immutable base inputs once per release | recorded x86 and ARM base digests; all edition jobs consume them |
| P6.2 | Produce SBOM and provenance for each image | signed attestations linked to exact digest and source SHA |
| P6.3 | Align ARM rebuild and promotion cadence | scheduled security rebuild; exact-image boot proof before tag movement |
| P6.4 | Add staged rollout and release health | candidate ring, development machine ring, broader ring; halt and rollback criteria |
| P6.5 | Security review the MoOS URL scheme, Remote and AI boundaries | threat model, negative tests, dependency audit and externally reviewable report |
| P6.6 | Establish support lifecycle and migration policy | published support window, upgrade path, rollback window and end-of-support behavior |

Android's modern update design retains boot-critical fallback state and marks a
new system successful only after boot.^7 MoOS uses different technology, but the
product expectation is the same: an interrupted or bad update must leave a
known-good boot path. This remains an acceptance requirement, not marketing.

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

Performance work starts with repeated measurements, not removing dependencies
based on RPM size metadata. The current boot is 36.783 s with 5.325 s in
`ldconfig`; P5.4 must check another boot and a real idle interval. P5.6 must
measure final image/ISO bytes and package reverse dependencies before removing
unused payload. Compiler SDKs stay in user/development environments; optional
office, Android and compatibility stacks remain on demand.

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
