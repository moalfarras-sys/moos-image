# System audit resumed — 2026-09-06

## Scope and source

The owner requested review of the intervening agent's changes, completion of
launcher/bar improvements, application updates, signed build/update and reboot.
PR #73 is merged at `9dda6dff`. PR #74 contains the continuation through
`164899a6`; branch `fix/system-audit-20260905` merged main at `2229eff6`.
No stash, separate worktree or uncommitted continuation was found. The ARM/UTM
archive branch retains its independent experiments; it was not bulk-merged.

## Findings and repairs

- Keyboard navigation and RTL CommandCard corrections, consistent GTK/KWin
  window controls, icon inheritance, ARM Arabic dictionaries and the smaller
  ARM initramfs are preserved. Local screenshot `resume-before.png` shows the
  native VS Code frame without the previous menu/button collision; the bar is
  one centered capsule over Arena. Remote v39 remains the owner's screen.
- Motion's essential profile is a requested design choice, **not a proven free
  optimization**. Live factor is 0.4, but the four configured effects are absent
  from KWin's loadedEffects. The idle sample cannot measure their cost. Slide
  affects desktop transitions and dimscreen can affect multiple windows. Source
  comments and the state/visual plan now reflect this limitation.
- Kernel logs record OOM kills at 04:12–04:15 during the previous session.
  Victims include KWin (~6.8 GB anonymous RSS), Plasma (~3 GB), the KDE portal
  (~4.2 GB), kded (~6.3 GB), and activities (~10.6 GB at its kill). These are
  different moments, not additive simultaneous usage. No causal trigger is
  established. Activities remained failed; starting that service restored it
  to ~25 MB. Remote and KWin were not restarted.
- The resumed selfcheck passed **47 checks**, with three advisory notes (live
  Remote viewing and optional tray entries). At 10:03, RAM was ~4.9 GiB used,
  ~6.7 GiB available; swap ~1.7 GiB. This is a snapshot, not leak clearance.
- Europe/Berlin remains selected with synchronized time. `/var` is ~199 GiB.
  The earlier pre-resize Oracle backup and signed rollback are retained.
- `/boot` initially had only 205 MiB available. The ~100 MiB new initramfs
  also needs a ~17 MiB kernel and ~98 MiB DTB tree. A dry run found 1,552
  identical DTBs in both deployments. Consolidated only those DTBs with
  `hardlink --ignore-time --respect-name --respect-xattrs`, temporarily
  remounting `/boot` writable and restoring read-only in a finally block.
  Every boot file's path, SHA-256, mode, owner and xattrs matched before/after.
  Actual free space rose **205 → 302 MiB**; both loader entries and complete
  deployments remain. Local proof: `boot-dtb-preservation.json`. An initial
  attempt on the read-only mount made no change; that was not counted as space
  recovery. Future updates must still measure their full boot footprint.
- Added executable focus-routing coverage: 11 tests pass; forcing every page to
  Home fails three page cases. Qt's rendered focus delivery remains separate.
- `python3 tests/observe_session_health.py --samples 60 --interval 30` records a
  finite 30-minute series of memory, cumulative OOM count and top process names.
  It reads no process arguments/environment. Logs are local; no claim of leak
  resolution follows from a single healthy sample.

## Verification and release checkpoint

Local native ARM build runs as **user** service
`moos-audit-resume-build.service`, image `localhost/moos-arm:audit-resume`.
Use `systemctl --user` and rootless `podman`; system units/rootful image storage
are different and do not report this build. **105 workflow/ARM source commands
passed on the host**, plus all 11 deployment diagnostic tests. The launcher
behavioral suite ran with Node (11 total tests, no skips). The finite memory
observer passed a live schema/bounds smoke check; it is not a stability gate.
A passing source build is not a deployed signed release.

Application updates use user service `moos-audit-flatpak-update.service`.
Both system/user final invocations report no remaining updates. OCI remotes
can still appear in `remote-ls --updates`: for Ptyxis the installed OSTree
commit differs from the remote OCI digest, but its `xa.alt-id` exactly matches
that digest. Comparing those different identifiers is not proof of a missed
update. Native OS app versions ship through the signed ARM image.

Local evidence directory: `~/.cache/moos-glass-review/` (not a release artifact).
Signed digest, final image proof and post-reboot result will be recorded below.

Prepared local `moos-audit-postboot.service`/timer: after an expected digest and
old boot ID are recorded, it runs the exact-digest desktop diagnostic, selfcheck,
Remote/activities status, effects/clock/storage readback and local screenshot.
It records five checks at three-minute intervals then disables its own timer.
Results: `~/.cache/moos-glass-review/postboot-audit-result.json`. It cannot count
a check on the old boot as success. Units passed `systemd-analyze --user verify`.
No screenshot or raw private journal is published in the repository.

An isolated native keyboard test could not run with installed tools: no Xvfb,
QML test runner, Python Qt bindings or standalone session-bus launcher. No live
synthetic input or competing compositor was started. The actual Qt focus/RTL
frame remains an explicit acceptance item.

## Overrides and next work

Remote runs from `~/.local/lib/mo-remote-v39-20260905`, selected by
`~/.config/systemd/user/mo-remote-personal.service.d/99-remote-control-v39.conf`.
Earlier 90-oracle-live remains outranked. Retire these only after signed Remote
is verified. The local watchdog is intentional recovery; its Wayland condition
belongs in `[Unit]`. The temporary AppStream service in `/etc/systemd/system`
can retire after the image's service and timer are proved present.

Persistent SDK 10.0.400 is `~/.local/share/dotnet`, verified in host and editor
sandbox. Do not force an editor reload during the owner's work.

Next priorities: S03 memory incident, D01 actual focus/scale sweep, P03 budget
consumer through the existing Baloo config owner, then release/device gates
R01–R04. Do not mark motion performance, universal compatibility, deliberate
rollback, or real NVIDIA hardware as validated by this ARM build.
