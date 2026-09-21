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
| Station agent | The physical x86 NVIDIA workstation | `feat/w8-material-arrival-20260921`: finish W8's one-shot material arrival, then **W9 — one MoOS System Centre** (Updater, Recovery and Remote as Settings deep links, one authority, live 4K/265% review). The former off-station W9 reservation had no pushed branch or open PR on 2026-09-21; the owner reassigned the work to this station. | `artwork/generate_moos_design_core.py` and the generated `org/moos/ui`; `system_files/usr/bin/moos-update`, `moos-rollback`, `mo-pc-remote`, `moos-settings`; `system_files/usr/share/moos/apps/settings/**`; W9 desktop entries/routes/tests; the MoOS plasmoids' glass surfaces; `system_files/etc/xdg/kwinrc`, `system_files/usr/share/kwin/**`, `scripts/station/**` |
| Remote agent | Off-station: Windows 11 + WSL2, no live KWin | No pushed product branch. Release tooling and off-station review remain reserved; coordinate before editing them. | `scripts/review/**`, `scripts/release-candidate.sh`; release rows in `PROJECT_STATE.md` |
| Oracle agent | The Oracle A1 (aarch64) | ARM boot proofs and the A1's own findings. The A1 live review's first batch is merged (PR #130: icon caps, one glyph per session action, one store in Search, the Store-test isolation, `THEME_REV` 68); **now:** `fix/a1-arm-honesty-20260918` — no x86-only work offered or attempted on ARM | `Containerfile.arm`, ARM tests and ARM rows; `moai-do`'s `pc_games_supported` and the two setups it guards, `moai-control`'s `arch`, Mo AI's `shownSkillChips`, the skills `graphics-and-nvidia` and `gaming-and-windows-apps`, `tests/test_openclaw_arch_install.py`, `tests/test_moai_app_launch.py`, the stderr flag in `tests/test_moai_rail_layout.py` / `tests/test_moai_agent_loop.py` |

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
