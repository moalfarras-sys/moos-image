# Who is working on what

MoOS is developed by more than one agent at once, on different machines. The
plan (`docs/DEVELOPMENT_PLAN.md`) is the single backlog; this file says who is
holding which part of it right now, so two agents never edit the same file.
It is short on purpose. Update your own row when you start and when you finish;
delete a row that is merged.

**The rule:** claim files, not tasks. A claim is only real once it is pushed.
If you need a file another agent holds, say so in your row and wait for their
merge instead of editing it.

| Agent | Machine | Holds | Files it may change |
| --- | --- | --- | --- |
| Oracle integration audit (Oct19–20) | Oracle A1 | PR256 `codex/integration-audit-20261019`: hardware confidence/enumerators, daily adapter recurrence, Arrange eligibility and Remote bind lifecycle; exact source3708 passes full check and repository/Remote CI. Local ARM refuses changed post-systemd tmpfiles authority; strict private-HOME helper correction is active. Needs V3's overlapping compose/Plasma work after its merge; independent signed-source reviews agree, no competing edits to its held files. | Existing PR256 hardware/Arrange/Remote corrections, new `compose_arm_initramfs.py` and `test_arm_dracut_home.py`, their existing main/recovery calls, own registrations and audit/proof/state/plan paragraphs. Preserve V3's source freeze, host signed origin/rollback, all guards and owner refs. |
| Owner system audit (Oct18) | Oracle A1 | `codex/system-audit-20261018` / PR253: live missing app-update units restored; native full ARM image and payload/stricter-gate verification pass at2b12ad2f.20 controls and final native full source at05649cd0 pass; exact-head CI/review tracked in PR253. Signed .807 staged, .804 still booted; patch delivery/override retirement remain open. No dispatch or main change; the727e7b6c owner cycle completed separately. | The four `system_files/usr/lib/systemd/{system,user}/flatpak-{system,user}-update.{service,timer}` bases, new `build_files/verify_app_updates.py`, `tests/test_app_update_units.py` and unit documentation; only app-update presence/enablement/final verification in both builders, own gate registrations, bilingual what's-new entry and own audit/state/plan paragraphs. Existing Settings, Store, Remote and Baloo changes remain with their holders. |
| V3 owner compatibility (Oct20) | Physical Minisforum V3 | `fix/v3-plasma-681-20261020` at `99269cc4`: owner-authorized native device/login completion. Exact vendor-state and Plasma6.8.1 review, native lock positive/broken/restored and fresh compose base pass; full final source/image qualification is running. Source is backed up and pushed, not a signed delivery. No main merge/release dispatch yet; preserve independent PR253/256 and review any overlapping source before integration. | `build_files/plasma_stable/**`, exact `plasma_login/**` vendor-input/prepared hashes, `plasma_logout/sources.json`, the new narrow6.8.1 seam set and its input-review helper/tests; `finalize_canary_base.py`, new `finalize_{root_home,dbus_state}.py` and their controls; only their existing builder calls/root-home diagnostics, recovery ctx mount, build-only cache environment, own Justfile registrations and own truth/hardware/release-proof paragraphs. Generic image/identity gates, app-update/Remote/Settings owners and existing unmerged work stay intact. |
| Owner completion (Oct17–18) | Physical NVIDIA station | PR249/248 and corrective PR250 merged atdcd1985b; all initial242 refs are ancestors, original five dirty trees preserved. Full source/local Cloud/PR images pass. | Refused cycle2: signed1069 and three QCOW2 pass, ISO39082792111 fails Themes close; no x86 promotion/stage. ARM39078288996 promotes804. `fix/iso-app-close-diagnostics-20261018` owns `tests/install_live_iso.sh`, its existing executable gate suite and truth files. Diagnostic39089750710 now identifies an orphan bluetoothctl in the closed Settings app cgroup. This branch also claims `moos-settings-kcm/src/moosbackend.{cpp,h}`, a private status-query process helper/control, its CMake/build-stage execution and `tests/test_moos_settings.py`. Also owns only the sequential scheduling of the existing independent walks in `tests/test_mo_store_ui_pages.py` after the512MiB test cap fired; all variants/negative controls/assertions/deadlines stay intact. Repair read-only query ownership; independent change units and the launcher cgroup contract remain intact. Diagnostic-only ISO retains close assertions/deadlines and stays distinct from signed delivery. |
| Owner-milestone agent | Physical NVIDIA station | `feat/owner-milestones-20261009`: ordered owner request, muted/disconnected local-wake capture policy, honest unreadable-recovery state, journey evidence and independently prepared private-participation service; do not edit the running installer candidate `144b1a6a` | `docs/OWNER_EXECUTION_20261009_AR.md`, `docs/reviews/system-journey/**`, `mira/capture_policy.py`, `mira/local_wake.py`, `mira/test_local_wake.py`, `tests/test_mira_capture_policy.py`, own test registrations in `tests/repo-gates.sh` and `Justfile`, local-wake health lines in `mira/controller.py` and relevant tests, `system_files/usr/bin/moos-rollback`, `tests/test_recovery_rollback_target.py`, `community/**`, `tests/test_community*.py`, `.github/workflows/community-check.yml`; own truth/plan rows only. Live API/client acceptance passed. Image integration additions only: community stage/COPY lines in `Containerfile` and `Containerfile.arm`, independent community gate call in `build_files/build.sh` and `build_files/build-arm.sh`, `build_files/verify_community_client.py`, `system_files/usr/bin/moos-community`, `system_files/usr/share/applications/org.moos.community.desktop`, `system_files/usr/share/metainfo/org.moos.community.metainfo.xml`, `system_files/usr/share/moos/community-service.json`, and THEME_REV increment in `system_files/usr/bin/moos-apply-theme`. Existing Mira/Lumen/Remote/seam lines stay with their holders. |
| Station agent (Mo Store library) | The physical x86 NVIDIA workstation | `feat/mo-store-library-20261014`: the owner's 2026-10-14 request — Mo Store as the one rich, beautiful place to find, install, update, remove and permission Linux, Windows, Android and web apps (PhotoCraft, ChatGPT, Claude, Antigravity, office suites), with KDE integration and per-machine compatibility; on 2026-10-15 also every ArtCraft program, Adobe alternatives and management of every installed app. Pushed at `c05e73ed` (includes origin/main #241/#242); review-fix branches `store/fix-*` pushed as backups. Integrates the Oracle review's `docs/reviews/store-20261014/` corrections into the Store source before the batch ships. Live acceptance on the station before the PR; the merge and signed delivery stay with the owner. | `system_files/usr/share/moos/apps/store/**`, `system_files/usr/share/moos/store/**`, `system_files/usr/bin/moos-store`, `system_files/usr/bin/moos-storectl`, `system_files/usr/bin/moos-store-index`, `system_files/usr/bin/moos-app-drop`, `system_files/usr/lib/moos/moos_appdrop.py`, new `system_files/usr/bin/moos-webapp` and `system_files/usr/lib/moos/moos_webapp*.py`, new KRunner/notifier files named `*moos-store*`/`*moos.store*`, `system_files/usr/share/applications/org.moos.store.desktop`, the store/app routes of `system_files/usr/bin/moos-open`, the `x-scheme-handler/appstream` line of `system_files/etc/xdg/mimeapps.list`, `build_files/verify_store_catalog.py`, `tests/test_store_*.py`, `tests/test_moos_store*.py`, new `tests/test_mo_store_*.py`/`tests/test_moos_webapp*.py`, the Store rows of `whats-new.json`, the P4.1/P4.4/P4.6/P4.7 and A1–A5 rows of `docs/DEVELOPMENT_PLAN.md` and the Store paragraphs of `PROJECT_STATE.md`. `moos-run-foreign` and `app-engines.json` only for an additive per-app Windows mode, after reading the existing Windows/Android contract. Also, only for the Store's own checks and registrations: the StoreBridge class in `build_files/moos-qml-shell.cpp`; store-specific assertions in `tests/verify_user_experience.py`, `tests/test_app_engines.py`, `tests/test_moos_app_visual_polish.py`, `tests/test_moos_design_core.py`, `tests/test_qml_root_references.py`, `tests/test_secondary_text_contrast.py`, `tests/test_notification_identity.py`, `tests/test_moos_symbolic_icons.py`, `tests/test_first_party_window_frame.py`, `tests/test_moos_one_locale_authority.py`, `build_files/verify_image_experience.py` (Store section only, never weakened) and `build_files/curate_app_menu.sh` (Discover url-handler comment); new test registrations in `Justfile` and `tests/repo-gates.sh`; `system_files/usr/lib/systemd/user/flatpak-user-update.timer.d/moos-schedule.conf`; store routes in `mira/moos_routes.py`. |
| Station agent | The physical x86 NVIDIA workstation | `feat/remote-unified-system-20261005`: P2.14 — v55 visible typing and healthy relay detail; native EIS input independent of capture; narrow unattended consent. Disposable signed-base VM typing/video and repeated ordinary password unlock proven; owner phone/WAN still open. Final integration #206, phone/WAN and signed delivery remain open. | `moremote/agent-linux/**`, `moremote/agent/Web/StreamSession.cs`, `moremote/agent/Core/InputInjector.cs`, `moremote/controller/**`, `moremote/agent/wwwroot/**`, `moremote/tests/**`, `moremote/ONE_REMOTE.md`, `moremote/README.md`, `system_files/usr/bin/mo-pc-remote`, `tests/test_moos_gtk_runtime.py`, the Remote row of `system_files/usr/share/moos/whats-new.json`. Shared docs: only the Remote evidence/plan rows. |
| Station agent (Mira home + Lumen) | The physical x86 NVIDIA workstation | `feat/mira-home-lumen-20261002`: Mira's home centre (rooms, renaming through Home Assistant's registry, what each device can do, discovery) and **Lumen**, the MoOS lighting engine: every light as one system (Home Assistant, the Hue bridge directly, the PC's own RGB controller), groups, scenes, effects, and lights that follow the screen. | `mira/lumen/**`, `mira/homehub.py`, `mira/home_link.py`, `mira/pages/home.py`, `mira/pages/lumen.py`, `mira/qml/Mira/{HomePage,LumenPage,Lumen*}.qml`, the home/light tools and the home inventory in `mira/tools.py`, their lines in `mira/controller.py`, `mira/i18n.py`, `mira/review_fakes.py`, `mira/qml/Main.qml`, `mira/qml/Mira/NavRail.qml`, `mira/packaging/stage.sh` and their tests (`mira/test_lumen*.py`, `mira/test_homehub.py`, `mira/test_page_home.py`, `mira/test_page_lumen.py`, `mira/test_group_lights.py`); `system_files/usr/bin/mira-lumen`, the Home and Lighting rows of `moos-settings-kcm/modules/ai/ui/main.qml`, the `ai/home` and `ai/lumen` routes in `system_files/usr/bin/moos-open`, the Lights/Home actions in `org.moos.moai.desktop`, the Mira test list in `Containerfile.arm`, `system_files/usr/lib/systemd/user/mira-lumen.service`, the Lumen launcher entry and its `whats-new.json` lines; the Mira test list in the `Containerfile` mira-build stage and the Lumen lines of the Mira gate in `build_files/build.sh`; the Mira rows (W11/P3.x home) in `PROJECT_STATE.md` and `docs/DEVELOPMENT_PLAN.md`. |
| Remote agent | Off-station: Windows 11 + WSL2, no live KWin | No pushed product branch. Release tooling and off-station review remain reserved; coordinate before editing them. | `scripts/review/**`, `scripts/release-candidate.sh`; release rows in `PROJECT_STATE.md` |
| Oracle owner Store batch (Oct16) | Oracle A1; NVIDIA currently offline | `feat/store-real-apps-touch-20261016` includes frozen Remote31bb0b70. Earlier review agents have stopped; root owns integration.264 apps, native input/motion controls, Android lifecycle/ownership and actual Oracle Linux app journey. Final native image and one coherent signed four-edition cycle remain pending; no candidate is active. | Root owns the existing Store catalog/UI/index/controller and narrow helper/tests; the measured bounded job-presence correction in `moai-control` and its native consumer tests; Android session unit and its three callers; shared QML platform selection and both build-time binary probes; THEME_REV107, exact ARM software-rendering policy, own registrations/truth/proof paragraphs. Original dirty trees, owner SDKs and installed signed payloads remain preserved. |

Shared files (`docs/DEVELOPMENT_PLAN.md`, `PROJECT_STATE.md`, `AGENTS.md`) are
edited by everyone, so touch only your own rows and expect to rebase.

**`scripts/release-candidate.sh`** is the off-station agent's file. The station edited it on
2026-09-18 with that agent's part of the work untouched, because the defect it fixes stopped
the station's own release: `build.yml` cancels in-progress runs per ref, so the nightly
rebuild of the same commit killed the cycle's build and the cycle reported FAIL. It now
reuses a finished build of the exact revision and adopts a superseding one. Expect to rebase
rather than to conflict.

**2026-10-07: the station completed the owner-authorized final cycle at `fa85b2da`.** #215 includes exact #214/v56, shared PIN protection and reviewed Oracle #216 history/recorder updates. X86 build `37552824167`, three QCOW2 proofs, offline ISO and promotion `37562359722` all succeed; ARM `37539003204` succeeds at the same source. Production is x86 `.1011` and ARM `.724`. Main's candidate freeze is released. The station holds only its delivery/readback paragraphs in `PROJECT_STATE.md`, `docs/DEVELOPMENT_PLAN.md` and this file on `docs/session-delivery-20261007`; it requested the official NVIDIA host update, while native authentication/staging/reboot and physical full logout remain pending. Oracle follows the proven ARM release for its own installed acceptance without a duplicate cycle.

**2026-10-09: owner-authorized station delivery of PR #222.** The owner-milestone
agent will run one standard `scripts/release-candidate.sh --promote` after the
final local image and PR checks pass, then official NVIDIA/Oracle readback.
No owner-batch cycle has started yet. Its image additions also own the explicit
`dbus-daemon` dependency for the community gate in `build_files/build-arm.sh`.
Native client trigger additions in `.github/workflows/pr-image-gates.yml`,
`.github/workflows/build-arm.yml` and `tests/test_pr_image_gates_workflow.py`
belong to this packaging batch too; existing matrix/jobs/permissions stay intact.
The station also holds the narrow D-Bus empty-directory correction in
`build_files/finalize_image_state.py` and `tests/test_image_state.py`: native ARM
37987720523 passed the real community launcher, then correctly refused
`/var/lib/dbus`. Preserve its vendor tmpfiles authority and all state refusals;
this does not take over the broader next-Plasma canary cleanup lane.
Actual GUI ISO review then reproduced Arabic `برلين` returning no zone while
`Berlin` works. The station holds `system_files/usr/share/moos/apps/installer/main.qml`,
its new immutable localized-zone data/generator and native regression gate,
plus installer-copy Mira naming only. Installer mount/privilege/authentication
mechanisms remain unchanged. PR integration watcher is stopped before merge;
finish this measured user-path correction before the one signed batch.
The existing cache migration advances to THEME_REV 102; the station also owns
only its exact revision assertions in `tests/test_moos_ui2.py` and
`tests/verify_user_experience.py`, preserving all migration/cache guards.
Its generated `tests/theme-rev-fingerprint.json` accompanies that revision;
own installer incident/provenance paragraphs in `AGENTS.md` and `OWNERSHIP.md`
record the native negative control and original data notices.
Main freezes at that cycle's recorded SHA through promotion/failure; do not
dispatch a duplicate cycle. The accepted installer cycle at `144b1a6a` is complete.

**Release cycles** normally belong to the off-station agent. On 2026-09-18 the owner
asked the station to run one for W8 so every edition updates; say so here when that
happens, because two agents dispatching a cycle at once would prove nothing twice.

**2026-10-06: the station ran the release cycle for P2.16 (PR #207)** at the owner's request, from `main` `a803a075`; promotion run 37394260892 succeeded. The next-Plasma canary has been red on `main` since 2026-10-05 11:46Z at `finalize_image_state.py` ("unexpected mutable image entries"), a step after the seam gate, which passes there — Oracle agent, that one is yours to look at before 6.8 lands.

**2026-09-30: the station runs the release cycle for P2.13.** The owner asked the station
to merge the MoPlayer batch, build the full signed update and install it on this machine. The
station dispatches `scripts/release-candidate.sh --promote` from `main` once PR #183 is merged;
do not start a second cycle on that revision. Merges to `main` wait for its promotion or failure.

## Why the station holds W7

W7 is the one wave that cannot be done anywhere else. The plan's own Workspace
facts say it: what is left is "the look of Overview and the task switcher in
MoOS UI, a tiling popover, per-effect durations taken from MoOS Motion,
gestures, and touchpad defaults ... Every one needs a live session and a
before/after capture." An agent with no KWin cannot take that capture, and a
rendered frame from `scripts/review/render-app.sh` is explicitly not a desktop
review. Conversely W9's surfaces are ordinary first-party windows that render
from source off-station, so they do not need the station.

## What the station measured on 2026-09-17, before W7

Both findings are from the running session (`44.20260917.858`, KWin 6.7.5,
3840×2160 at 265%, Arabic), not from source:

- **The switcher had MoOS's colour and nobody else's shape.** The first note
  written here said Alt+Tab "is not MoOS". That was imprecise, and the precise
  version is the useful one: the active scheme is `MoOSUI2AuroraLight`, and the
  MoOS Plasma style does reach the switcher's *colour* — which is why it looked
  pale mint rather than Breeze blue. What the Plasma style cannot reach is the
  layout: geometry, type, corner radii, the Breeze close button, and the
  reading order. Alt+Tab ran left-to-right inside a right-to-left session.
  Colour was the only thing MoOS owned, and it was the only thing that was right.
- **The reading order had a specific, MoOS-specific cause.** The stock layouts
  take their direction from `Application.layoutDirection`. MoOS ships bilingual
  QML strings instead of Qt translation catalogues, so no translator is
  installed and that property is LeftToRight in every MoOS session, Arabic ones
  included — exactly what the comment at the top of `org/moos/ui/Locale.qml`
  warns about. Any surface MoOS adopts from upstream needs checking for this.
- **Overview cannot be re-shaped the same way.** Its search field, desktop tiles
  and window captions are stock too, but its QML is compiled into
  `libkwin.so.6` — `/usr/share/kwin/effects/` holds only a third-party `cube`,
  and the effect plugin directory has only `kwin_overview_config.so`. There is
  no file to override and no supported extension point, so re-shaping it means
  patching KWin. That is a fork, which `AGENTS.md` forbids, so W7 does not
  attempt it. What W7 can honestly give Overview is its configuration: trigger,
  layout, and the durations it animates with.
- **MoOS's own motion did not follow the owner's animation-speed setting.**
  Plasma has one control, `AnimationDurationFactor`, and `moos-visual-tier`
  already writes it per hardware tier. It reaches QML through
  `Kirigami.Units.longDuration`. MoOS's `Tokens.duration()` read that only as
  yes-or-no, so on a tier set to 40% the shell ran at 40% and every MoOS surface
  still ran at 100%.


## The pointer, and why review claims were thin without it (2026-09-18)

Four review rows had stood as "untested" since W4 because open-loop pointer input does not
work here: `ydotool mousemove --absolute` leaves the cursor in the corner on this 4K screen at
265%, so a script that clicks blind can report a pass for a click that never landed. The fix is
`scripts/station/pointer.py`: KWin is asked where the pointer is (`workspace.cursorPos`, loaded
as a script, answered on Klipper's D-Bus interface) and the pointer is walked there with
relative moves until the compositor agrees, then the click is sent. It costs about a second per
click and it is the difference between evidence and a guess. Coordinates are LOGICAL pixels.

It closed rows 3, 4, 10 and 11 the same morning, and row 11 found two things the owner reads
that were not MoOS's own words (an English pkexec prompt naming a helper path, and "This
incident has been reported." after pressing Cancel). Both are fixed in source in the same wave.

## What the station has already done (2026-09-17)

On branch `feat/w7-workspace-20260917`, reviewed live on the running session:

1. **MoOS Switcher** — Alt+Tab is a MoOS surface, mirrored by the locale, with a
   working close control, selected in `etc/xdg/kwinrc` for both switchers.
2. **`Tokens.scaled()`** — MoOS motion answers to the same one control Plasma
   does, proven on the real Qt runtime by `tests/qml/motion-review.qml`.
4. **The station review owed for W4–W6** — results are in `PROJECT_STATE.md`.

3. **MoOS Arrange** — halves, thirds, quarters, a main pane plus two, and centre,
   from the window menu and Meta+Alt+1..4/C, proven live on a scratch virtual
   desktop so the owner's own windows were never moved.

Still open in W7, for whoever picks it up next: the live preview the plan's idea
asks for in the Arrange surface, touchpad and gesture defaults (P5.2), and
carrying `Tokens.scaled()` to the per-surface motion aliases in the plasmoids and
apps.

**2026-10-06: the owner now asks the station to integrate every active branch, update the physical NVIDIA station and reboot.** The reserved logout/Sharp cycle stays fixed on `97f4f121` through its promotion/failure. The next station batch preserves #214's reviewed v56 ancestry and adds the shared PIN lockout correction; start one standard signed cycle only after that fixed cycle resolves. All final edition proofs, signatures and installed readback remain required.

**Oracle final-batch handoff, 2026-10-07:** #216 joined #215 at `fa85b2da`; signed ARM `.724` is now booted on the A1, rollback `.710`, installed checks 51/0 and 55/0. No duplicate release dispatch. `audit/public-readiness-20261007` holds only the Oracle acceptance paragraphs, `docs/INTEGRATION_AUDIT_20261006.md`, `docs/RELEASE_READINESS_20261007.md` and the P0.12 delivery evidence. The final signed ISO is preserved and locally verified; website 503 and existing Blob-store 403 prevent public qualification. Account/hosting access remains external; never enable availability before full transfer proof. No product source is held.

| Oracle urgent Remote/security correction (Oct16) | Oracle + physical NVIDIA | PR248 at31bb0b70 passed required PR/source/image checks; no signed candidate was dispatched. Its exact source is merged into the Store topic for one coherent milestone delivery. The owner confirmed the corrected desktop picture before NVIDIA went offline. Native .1062 acceptance remains baseline only. | Root retains ownership of the existing Remote/security correction; final PR title/body and source SHA will describe the coherent batch. All final-source local/CI/signing/boot/promotion gates remain required. |
