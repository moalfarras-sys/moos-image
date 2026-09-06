# MoOS agent handoff contract

Read `AGENTS.md`, `skills/moos-engineering/SKILL.md`, `PROJECT_STATE.md`, then the
current system plan. Visual work also reads `MOOS_DESIGN_PLAN.md` and the relevant
mechanism in `AGENT_GUIDE.md`. Do not copy an older plan's scope into a new session.

## Before work

1. Inspect `git status --short`, current branch/SHA, `git worktree list`,
   `git stash list`, and fetched remote branches. Do not reset, clean or overwrite
   another worker's changes. Record the intended task ID from the system plan.
2. Establish where commands run. This workstation's coding shell is inside
   VS Code Flatpak; `flatpak-spawn --host` runs host commands. A missing binary
   inside the sandbox does not prove it is absent from the host.
3. Read active image origin, local overrides and build services. Never start a
   duplicate full build before checking the previous one. Measure `/var` or
   `/sysroot`, not immutable `/`.
4. Define success and the rollback path. Get consent only for actions outside
   existing user authorization; do not ask repeatedly for already-authorized work.
5. If parallel work is authorized, assign disjoint files/bounded tasks. Only one
   agent owns builds, deployments and git integration. Helpers report tests and
   exact files; they do not independently push or restart the desktop.

## During work

- Make a failing reproduction, then the smallest complete repair. Gate behavior,
  not strings that merely resemble the implementation. Prove a new gate bites.
- Use the existing authority for themes, updates, app install and privilege.
  Never introduce a second writer or let a model/web page execute arbitrary
  privileged commands. User-approved host maintenance is not permission to ship
  that privilege to the product's AI runtime.
- Real-time UI comes from the live process; file defaults are not readback.
  Screenshots must name source, viewport, theme, scale and whether transport is
  mocked. Preserve user settings and distinguish custom values from drift.
- Keep code and generated shipping bundles together. Force-add only the intended
  ignored generated assets, then run `test_shipped_bundle_is_tracked.py`.
- Run required source checks and an appropriate full native image build before
  push. Inspect finished image bytes. Record skipped hardware/runtime tests.
- No release promotion based only on a parser, successful build, or screenshot
  from a different digest. Never erase a safety gate or swap sibling editions to
  make verification pass.

## Checkpoint template

Keep a concise current checkpoint in `PROJECT_STATE.md` or the referenced release
report, not credentials and not a second history log:

```text
Task ID / objective:
Branch / source SHA / working-tree state:
Remote PR / merge SHA:
Built edition / architecture / local image ID:
Registry digest / signature status:
Installed booted digest / staged digest:
Active build service / log / result:
Files changed / why:
Executed checks / failures / explicit skips:
Visual/runtime evidence paths and conditions:
Local overrides (path, purpose, retirement condition):
Preserved rollback / backup:
Next bounded task and exact acceptance:
Not done / do not claim:
```

## Current maintenance checkpoint (2026-09-06)

Read this, then `PROJECT_STATE.md`, then `docs/MOOS_SYSTEM_DEVELOPMENT_PLAN.md`.
Pick ONE execution-order ID; do not re-derive what is already recorded.

- **Branch `fix/system-audit-20260905` → PR #74**, stacked on **PR #73**
  (`fix/oracle-storage-health-20260905`). #74 holds five commits: S01/S02 system
  audit, Launcher keyboard navigation (THEME_REV 53), the visual-tier resource
  budget, the CommandCard RTL clip fix, and the ARM initramfs/`/boot` fix (B01).
  Merge #73 first, then rebase or merge #74. **Query GitHub for current state;
  do not assume either PR is still open.**
- **CI on #74 is green**: `Build MoOS ARM (aarch64)` succeeded — that is a full
  native ARM image build plus every repo gate and `bootc container lint`.
  Locally, 97 of 98 CI gates pass; `test_openclaw_modern_unit_retire.py` needs
  `systemctl`, which the VS Code Flatpak sandbox does not have. That gap is
  pre-existing and unrelated — verify before blaming your own change.
- **THEME_REV is 53.** Any further change to a shipped theme SVG or plasmoid QML
  in this branch rides that same rev; a NEW rev needs both pinned gates
  (`test_moos_ui2.py`, `verify_user_experience.py`) moved with it.
- **B01 is implemented but not yet observed on hardware.** The next ARM image
  should produce an initramfs well under 110 MiB and take `/boot` from 78% to
  roughly 51%. After the machine updates, confirm with `df -h /boot` and
  `du -sh /boot/ostree/*/` and record the real numbers — that is what closes B01.
- **Next bounded tasks, in order:** B02 (measure the x86 editions' initramfs the
  same way — `moos-nvidia` must keep its kmod, so expect a different answer),
  P03 (make baloo's `only basic indexing` follow `budget.file_indexing`, written
  by that config's existing owner, never by visual-tier), then R01/R04.
- **Do not use synthetic input (`ydotool`) against the live session.** The owner
  works in it. The Launcher's keyboard flow is proven to LOAD (`plasmawindowed`,
  `MOOS_LAUNCHER_FULL_READY 792x576`) but its focus ring has not been driven by
  real key presses; that proof belongs to a session you own or the signed image.
- **`pgrep -f` / `pkill -f` kill this shell** (exit 144) because the pattern is in
  its own command line. Kill by PID; use `pidof` to check. Cost two shells here.
- Active Remote: `~/.local/lib/mo-remote-v39-20260905`, selected by
  `~/.config/systemd/user/mo-remote-personal.service.d/99-remote-control-v39.conf`.
  Earlier 90-oracle-live override also exists. Retire both only when signed
  image Remote is proven. Prior binary and moved overrides are retained.
- Temporary AppStream override: `/etc/systemd/system/moos-appstream-refresh.service`;
  remove after verifying the signed image's own service and enablement.
- Owner's zone is Europe/Berlin. Live host is `moos-arm-oracle`, booted digest
  `sha256:049a620d…` / `44.20260905.263`, theme `MoOSUI2Arena`
  (`org.moos.ui2.gaming`), tier `essential`. `AnimationDurationFactor=0` is the
  owner's own setting, recorded as such — do not "repair" it.
- Persistent SDK: `~/.local/share/dotnet` (10.0.400); verified in host and sandbox.
  Do not reload the editor while the user is working.
- No user files/apps were deleted. Oracle full pre-resize backup is retained.
  Disk/boot/scrub evidence is in `ORACLE_STORAGE_HEALTH_20260905.md`.
- Not closed by these sessions: real NVIDIA hardware, deliberate rollback (R04),
  the full device/network matrix, the 100–225% visual sweep, and global
  application compatibility.
