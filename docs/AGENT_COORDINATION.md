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
| Owner-milestone agent | Physical NVIDIA station | `feat/owner-milestones-20261009`: ordered owner request, muted/disconnected local-wake capture policy, honest unreadable-recovery state, journey evidence and independently prepared private-participation service; do not edit the running installer candidate `144b1a6a` | `docs/OWNER_EXECUTION_20261009_AR.md`, `docs/reviews/system-journey/**`, `mira/capture_policy.py`, `mira/local_wake.py`, `mira/test_local_wake.py`, `tests/test_mira_capture_policy.py`, own test registrations in `tests/repo-gates.sh` and `Justfile`, local-wake health lines in `mira/controller.py` and relevant tests, `system_files/usr/bin/moos-rollback`, `tests/test_recovery_rollback_target.py`, `community/**`, `tests/test_community*.py`; own truth/plan rows only. Image integration will be claimed after the service/client acceptance batch. |
| Station agent | The physical x86 NVIDIA workstation | `feat/remote-unified-system-20261005`: P2.14 — v55 visible typing and healthy relay detail; native EIS input independent of capture; narrow unattended consent. Disposable signed-base VM typing/video and repeated ordinary password unlock proven; owner phone/WAN still open. Final integration #206, phone/WAN and signed delivery remain open. | `moremote/agent-linux/**`, `moremote/agent/Web/StreamSession.cs`, `moremote/agent/Core/InputInjector.cs`, `moremote/controller/**`, `moremote/agent/wwwroot/**`, `moremote/tests/**`, `moremote/ONE_REMOTE.md`, `moremote/README.md`, `system_files/usr/bin/mo-pc-remote`, `tests/test_moos_gtk_runtime.py`, the Remote row of `system_files/usr/share/moos/whats-new.json`. Shared docs: only the Remote evidence/plan rows. |
| Station agent (Mira home + Lumen) | The physical x86 NVIDIA workstation | `feat/mira-home-lumen-20261002`: Mira's home centre (rooms, renaming through Home Assistant's registry, what each device can do, discovery) and **Lumen**, the MoOS lighting engine: every light as one system (Home Assistant, the Hue bridge directly, the PC's own RGB controller), groups, scenes, effects, and lights that follow the screen. | `mira/lumen/**`, `mira/homehub.py`, `mira/home_link.py`, `mira/pages/home.py`, `mira/pages/lumen.py`, `mira/qml/Mira/{HomePage,LumenPage,Lumen*}.qml`, the home/light tools and the home inventory in `mira/tools.py`, their lines in `mira/controller.py`, `mira/i18n.py`, `mira/review_fakes.py`, `mira/qml/Main.qml`, `mira/qml/Mira/NavRail.qml`, `mira/packaging/stage.sh` and their tests (`mira/test_lumen*.py`, `mira/test_homehub.py`, `mira/test_page_home.py`, `mira/test_page_lumen.py`, `mira/test_group_lights.py`); `system_files/usr/bin/mira-lumen`, the Home and Lighting rows of `moos-settings-kcm/modules/ai/ui/main.qml`, the `ai/home` and `ai/lumen` routes in `system_files/usr/bin/moos-open`, the Lights/Home actions in `org.moos.moai.desktop`, the Mira test list in `Containerfile.arm`, `system_files/usr/lib/systemd/user/mira-lumen.service`, the Lumen launcher entry and its `whats-new.json` lines; the Mira test list in the `Containerfile` mira-build stage and the Lumen lines of the Mira gate in `build_files/build.sh`; the Mira rows (W11/P3.x home) in `PROJECT_STATE.md` and `docs/DEVELOPMENT_PLAN.md`. |
| Remote agent | Off-station: Windows 11 + WSL2, no live KWin | No pushed product branch. Release tooling and off-station review remain reserved; coordinate before editing them. | `scripts/review/**`, `scripts/release-candidate.sh`; release rows in `PROJECT_STATE.md` |
| Oracle agent | The Oracle A1 (aarch64) | `audit/public-readiness-20261007`: installed `.724` acceptance, final qualified ISO preservation, honest public-delivery and hardware report. Previous Oracle product branches are integrated at `fa85b2da`; no product edits in this slice. | Oracle acceptance paragraphs in shared truth files; `docs/INTEGRATION_AUDIT_20261006.md`, `docs/RELEASE_READINESS_20261007.md`, P0.12/P5.5 evidence. Existing maintenance ownership remains: `scripts/station/compositor-rig/**`, Oracle live-development reference, Plasma seams/canary and corresponding tests. ARM image/Mira assembly remains with the station. |

Shared files (`docs/DEVELOPMENT_PLAN.md`, `PROJECT_STATE.md`, `AGENTS.md`) are
edited by everyone, so touch only your own rows and expect to rebase.

**`scripts/release-candidate.sh`** is the off-station agent's file. The station edited it on
2026-09-18 with that agent's part of the work untouched, because the defect it fixes stopped
the station's own release: `build.yml` cancels in-progress runs per ref, so the nightly
rebuild of the same commit killed the cycle's build and the cycle reported FAIL. It now
reuses a finished build of the exact revision and adopts a superseding one. Expect to rebase
rather than to conflict.

**2026-10-07: the station completed the owner-authorized final cycle at `fa85b2da`.** #215 includes exact #214/v56, shared PIN protection and reviewed Oracle #216 history/recorder updates. X86 build `37552824167`, three QCOW2 proofs, offline ISO and promotion `37562359722` all succeed; ARM `37539003204` succeeds at the same source. Production is x86 `.1011` and ARM `.724`. Main's candidate freeze is released. The station holds only its delivery/readback paragraphs in `PROJECT_STATE.md`, `docs/DEVELOPMENT_PLAN.md` and this file on `docs/session-delivery-20261007`; it requested the official NVIDIA host update, while native authentication/staging/reboot and physical full logout remain pending. Oracle follows the proven ARM release for its own installed acceptance without a duplicate cycle.

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
