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

## Current maintenance checkpoint (2026-09-05)

- Remote v39 source checkpoint: `5b0d79ca`; build proof documentation `4079bb73`.
  PR 73 holds keyboard/AppStream/storage/Remote integration. Query GitHub for
  current merge state; do not assume an open PR was merged.
- Native ARM exact-image proof passed on local image `c39840054b30`.
  Services `moos-glass-image-build` and `moos-glass-image-final` completed.
  Their journal records bootc lint and controller/helper byte checks.
- Follow-on system audit branch: `fix/system-audit-20260905`.
  Check `moos-system-audit-build.service` before starting another image build.
- Active Remote: `~/.local/lib/mo-remote-v39-20260905`, selected by
  `~/.config/systemd/user/mo-remote-personal.service.d/99-remote-control-v39.conf`.
  Earlier 90-oracle-live override also exists. Retire both only when signed
  image Remote is proven. Prior binary and moved overrides are retained.
- Temporary AppStream override: `/etc/systemd/system/moos-appstream-refresh.service`;
  remove after verifying the signed image's own service and enablement.
- Owner's zone is Europe/Berlin with synchronized clock. Theme owner restored
  Arena's wallpaper to match the selected Arena profile.
- Persistent SDK: `~/.local/share/dotnet` (10.0.400); verified in host and sandbox.
  VS Code paths configured; do not reload the editor while the user is working.
- No user files/apps were deleted. Oracle full pre-resize backup is retained.
  Disk/boot/scrub evidence is in `ORACLE_STORAGE_HEALTH_20260905.md`.
- Physical phone owner confirmed typing/bar visibility in both orientations.
  Full device/network matrix, deliberate rollback, real NVIDIA hardware and
  global application compatibility are not closed by this session.
