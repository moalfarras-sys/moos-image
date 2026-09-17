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
| Station agent | The physical x86 NVIDIA workstation | **W7 — MoOS Workspace** and the live station review owed for W4–W6 | `system_files/usr/share/kwin/**`, `system_files/etc/xdg/kwinrc`, `system_files/etc/xdg/kcminputrc`, `system_files/usr/bin/moos-motion`, `tests/test_moos_switcher.py`, `tests/test_moos_arrange.py`, `tests/test_motion_authority.py`, `tests/test_touchpad_defaults.py` |
| Remote agent | Off-station (no live KWin) | **W9 — system surfaces on MoOS UI** (Updater, Recovery, Remote centre, Settings front door) | the app trees those surfaces live in, `PROJECT_STATE.md` release rows |
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

- **The task switcher is not MoOS.** Alt+Tab draws the stock `thumbnail_grid`
  in a pale near-white panel with a Breeze close button, in left-to-right order
  in an Arabic session, floating above a dark MoOS glass bar. Nothing about it
  shares the bar's material, type or corner radius.
- **Overview's chrome is not MoOS either, and cannot be replaced the same way.**
  Its search field, desktop tiles and window captions are stock. Unlike the
  switcher, Overview's QML is compiled into `libkwin.so.6` — there is no file to
  override and no supported extension point, so restyling it means patching KWin.
  That is a fork, which `AGENTS.md` forbids, so W7 does not attempt it. What W7
  can honestly give Overview is its configuration: trigger, layout and the
  durations it animates with.
