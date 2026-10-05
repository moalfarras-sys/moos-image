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
| Station agent | The physical x86 NVIDIA workstation | `feat/remote-unified-system-20261005`: P2.14 — v53 native EIS input independent of capture; one Desktop/Touchpad/Keyboard controller; narrow unattended screen consent. Local review active; phone/PAM unlock/WAN and signed artifact proofs remain open. | `moremote/agent-linux/**`, `moremote/agent/Web/StreamSession.cs`, `moremote/agent/Core/InputInjector.cs`, `moremote/controller/**`, `moremote/agent/wwwroot/**`, `moremote/tests/**`, `moremote/ONE_REMOTE.md`, `moremote/README.md`, `system_files/usr/bin/mo-pc-remote`, `tests/test_moos_gtk_runtime.py`, the Remote row of `system_files/usr/share/moos/whats-new.json`. Shared docs: only the Remote evidence/plan rows. |
| Station agent (Mira home + Lumen) | The physical x86 NVIDIA workstation | `feat/mira-home-lumen-20261002`: Mira's home centre (rooms, renaming through Home Assistant's registry, what each device can do, discovery) and **Lumen**, the MoOS lighting engine: every light as one system (Home Assistant, the Hue bridge directly, the PC's own RGB controller), groups, scenes, effects, and lights that follow the screen. | `mira/lumen/**`, `mira/homehub.py`, `mira/home_link.py`, `mira/pages/home.py`, `mira/pages/lumen.py`, `mira/qml/Mira/{HomePage,LumenPage,Lumen*}.qml`, the home/light tools and the home inventory in `mira/tools.py`, their lines in `mira/controller.py`, `mira/i18n.py`, `mira/review_fakes.py`, `mira/qml/Main.qml`, `mira/qml/Mira/NavRail.qml`, `mira/packaging/stage.sh` and their tests (`mira/test_lumen*.py`, `mira/test_homehub.py`, `mira/test_page_home.py`, `mira/test_page_lumen.py`, `mira/test_group_lights.py`); `system_files/usr/bin/mira-lumen`, the Home and Lighting rows of `moos-settings-kcm/modules/ai/ui/main.qml`, the `ai/home` and `ai/lumen` routes in `system_files/usr/bin/moos-open`, the Lights/Home actions in `org.moos.moai.desktop`, the Mira test list in `Containerfile.arm`, `system_files/usr/lib/systemd/user/mira-lumen.service`, the Lumen launcher entry and its `whats-new.json` lines; the Mira test list in the `Containerfile` mira-build stage and the Lumen lines of the Mira gate in `build_files/build.sh`; the Mira rows (W11/P3.x home) in `PROJECT_STATE.md` and `docs/DEVELOPMENT_PLAN.md`. |
| Remote agent | Off-station: Windows 11 + WSL2, no live KWin | No pushed product branch. Release tooling and off-station review remain reserved; coordinate before editing them. | `scripts/review/**`, `scripts/release-candidate.sh`; release rows in `PROJECT_STATE.md` |
| Oracle agent | The Oracle A1 (aarch64) | `fix/remote-hidden-decoder-20261005`: the phone's H.264 give-ups (P5.5). **It edits files the station row holds** — `moremote/controller/src/lib/decode.ts` (suspend/resume and the give-up reason only), the hide/show handlers in `RemoteScreen.tsx` (not the ladder) and the rebuilt bundle in `moremote/agent/wwwroot` (BUILD v50) — after the station's P2.14 work had merged and with no unmerged branch touching them (checked 2026-10-05). The owner asked for it to be fixed. Station: please review, and read the next `gave up on H.264` reasons from the iPhone. Nothing open. Merged and released on 2026-10-04: #198 (the Oracle cloud-station batch) and #201 (the Island job feed, the `desktop_size` verb, Mira's playbook words); production is `3b00e90b`. The A1 has `.694` staged and is waiting for its owner's reboot. Earlier and merged: `plan/unified-moos-20260924`: P6.7, MoOS reviewed for each new Plasma before the base delivers it (seam registry, 6.8 lock screen, real-greeter gate, Plasma-next canary), plus the MoOS One plan section and rows P2.12/P6.8. PRs #155/#156 are merged. | Released, so no longer held: the PipeWire remote's lifetime and the frame pacer in `mo-remote-portal.py`, `moos-privacy-monitor`, Mira's `MessageDelegate.qml` height, the Island's re-read timers, the `display` verb of `moos-cloud-desktop`, `desktop-size` in `moos-control`. Still the Oracle agent's to maintain: `scripts/station/compositor-rig/**` and the Oracle section of `skills/moos-engineering/references/live-development.md`. From earlier: `build_files/plasma_seams.py`, `build_files/plasma-seams/**`, `scripts/plasma-next/**`, `.github/workflows/plasma-next-canary.yml`, `tests/test_plasma_seams.py`, `tests/test_plasma_next_canary_workflow.py`; the one seam-gate block each in `build_files/build.sh` and `build_files/build-arm.sh`; their lines in the `Justfile` and `tests/repo-gates.sh`. **ARM Mira stage handed to the station by the owner (2026-09-29):** `Containerfile.arm`, `build_files/build-arm.sh` (all but the seam-gate block above) and `build_files/verify_arm_image.py` are the station's now. **The station's handoff is closed (2026-09-29):** the station was going to ask for (1) a guard in `tests/test_moos_arm.py` that the x86 and ARM mira-build stages run the same suites, that `stage.sh` ships `pages/`, and that both builds carry the same Mira log-fault pattern and still-face probe; (2) a fake-root test of `verify_arm_image.verify_mira` there; (3) a Mira start in `tests/verify_arm_runtime.sh` (offscreen, `MIRA_TEST_MODE=1`, as the provisioned user: exit 0, a PNG, a clean log). No Oracle session was reachable, and the owner had made the station responsible for every edition, so the station landed all three itself in its integration batch: the `MiraOnBothArchitectures` and `VerifyMiraOnAFakeRoot` classes and the Mira block of `verify_arm_runtime.sh` are the station's. The runtime start has not run yet; it needs a booted ARM disk (the CI boot proof). Still mine from earlier: the rest of the ARM tests and rows (`tests/test_moos_arm.py`, `tests/verify_arm_runtime.sh`, `tests/boot_arm_qcow2.sh`), `build_files/verify_mime_handlers.py`, `tests/test_mime_handlers.py`, the Store architecture files (`catalog.json`, `moos-store-index`, `moos-storectl`, `moos-store`, the Store's `main.qml`, `tests/test_store_arch_honesty.py`) and `system_files/usr/bin/moos-measure-speed`. |

Shared files (`docs/DEVELOPMENT_PLAN.md`, `PROJECT_STATE.md`, `AGENTS.md`) are
edited by everyone, so touch only your own rows and expect to rebase.

**`scripts/release-candidate.sh`** is the off-station agent's file. The station edited it on
2026-09-18 with that agent's part of the work untouched, because the defect it fixes stopped
the station's own release: `build.yml` cancels in-progress runs per ref, so the nightly
rebuild of the same commit killed the cycle's build and the cycle reported FAIL. It now
reuses a finished build of the exact revision and adopts a superseding one. Expect to rebase
rather than to conflict.

**Release cycles** normally belong to the off-station agent. On 2026-09-18 the owner
asked the station to run one for W8 so every edition updates; say so here when that
happens, because two agents dispatching a cycle at once would prove nothing twice.

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
