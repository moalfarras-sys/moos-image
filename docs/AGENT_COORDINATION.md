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
| Station agent | The physical x86 NVIDIA workstation | **W7 — MoOS Workspace** and the live station review owed for W4–W6 | `system_files/usr/share/kwin/**`, `system_files/etc/xdg/kwinrc`, `system_files/etc/xdg/kcminputrc`, `artwork/generate_moos_design_core.py` and the generated `org/moos/ui` tokens, `org/moos/ui/Button.qml` and `Card.qml`, `tests/qml/motion-review.qml`, `tests/test_moos_switcher.py`, `tests/test_moos_arrange.py` |
| Remote agent | Off-station: Windows 11 + WSL2, no live KWin | **W9 — system surfaces on MoOS UI** (Updater, Recovery, Remote centre, Settings front door); **the x86 release cycles** (cycle D carries W7 and W6.2); the off-station review tools | `system_files/usr/bin/moos-update`, `moos-rollback`, `mo-pc-remote`, `moos-settings` and `usr/share/moos/apps/settings/**`; `scripts/review/**`, `scripts/release-candidate.sh`; `PROJECT_STATE.md` release rows. W6.2 (PR #119) also touched the Hub clock card, `org.moos.island` and `org.moos.search`; those are free again once it is merged |
| Oracle agent | The Oracle A1 (aarch64) | ARM boot proofs and the A1's own findings | `Containerfile.arm`, ARM tests and ARM rows |

Shared files (`docs/DEVELOPMENT_PLAN.md`, `PROJECT_STATE.md`, `AGENTS.md`) are
edited by everyone, so touch only your own rows and expect to rebase.

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
