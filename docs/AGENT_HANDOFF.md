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

## Current maintenance checkpoint (2026-09-06, resumed)

Read [`SYSTEM_AUDIT_RESUME_20260906.md`](SYSTEM_AUDIT_RESUME_20260906.md)
for the current branch, builds, live incident and release state. PR #73 is merged;
PR #74 contains the reviewed continuation. Query GitHub for subsequent changes.

- Run source gates on the **host**, not inside VS Code Flatpak; host systemctl
  exists. Inspect user build services with `systemctl --user` and rootless
  images with the owner's `podman`, not `sudo podman`.
- Remote is the owner's screen. Keep its v39 override until the signed image
  service is verified. Never stop Remote or KWin during the owner's session.
  The explicitly requested OS reboot is a separate authorized action.
- THEME_REV 53 carries launcher keyboard/RTL improvements. Actual rendered focus
  and the multi-scale sweep are still acceptance tasks, not source-gate results.
- Live motion factor is now 0.4 following the owner's request, not the historical
  zero override. Configured effects were not loaded during the idle benchmark.
- The 04:12–04:15 OOM incident is unresolved; activities was recovered with
  `systemctl --user start plasma-kactivitymanagerd.service`. Do not attribute
  the incident to motion without evidence, or describe the earlier healthy
  snapshot as proof of long-term stability.
- `/boot` has only 205 MiB available. The new initramfs is ~100 MiB but DTBs and
  kernel add ~115 MiB. Verify actual staging and retained rollback; archive size
  alone does not prove the update fits.
- Keep the fixed local Remote watchdog (Wayland condition belongs in `[Unit]`),
  the pre-resize Oracle backup, previous signed deployment, and persistent SDK
  `~/.local/share/dotnet`. Temporary overrides are listed in the release report.
- Next acceptance: signed ARM artifact, boot/update/Remote checks, then S03
  memory incident monitoring and P03 indexing budget. R01/R04 and the device
  matrix stay open. No blanket compatibility or performance claim is justified.
