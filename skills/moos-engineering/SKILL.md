---
name: moos-engineering
description: Engineer and verify MoOS images, KDE/Wayland integration, first-party apps and release workflows. Required before repository changes; distinguishes source, live-machine and signed-artifact evidence.
---

# MoOS engineering — the mandatory skill

**Every agent working in this repository must read and obey this file, plus
[`AGENTS.md`](../../AGENTS.md) (the rules) and [`PROJECT_STATE.md`](../../PROJECT_STATE.md)
(the terrain), before changing anything.**

## What MoOS is

- MoOS is a **real operating system**, built on **Fedora Atomic (bootc/OSTree)** and
  **KDE Plasma 6 (Wayland)**, from `ghcr.io/ublue-os/kinoite-main:44`.
- It is **not** "Fedora with a different name", and it is **not** just a theme.
  The identity is *built* by `build_files/build.sh` and enforced by gates; no user-visible
  surface may ever show Fedora/Red Hat branding (see THE IDENTITY CONTRACT in `AGENTS.md`).
- MoOS **develops on top of Plasma and KDE — it never deletes or arbitrarily replaces
  them**. It stays compatible with upstream and adds the MoOS layer above the original
  components. Deleting Plasma, KDE, systemd, or bootc to make a small change easier is
  forbidden.
- Four editions share one source tree and MoOS filesystem overlay: **`moos`**
  (x86 desktop), **`moos-nvidia`** (same x86 base + NVIDIA driver), **`moos-cloud`**
  (x86 VPS), and **`moos-arm`** (native aarch64, including Oracle A1).
  The three x86 editions use the same upstream repository; ARM uses the native
  bootc base in `Containerfile.arm`. Current upstream `:44` inputs are mutable
  tags, not locked release digests. Published MoOS images are cosign-signed and
  installed origins enforce signatures. See `docs/DEVELOPMENT_PLAN.md`.
- Targets: **speed, stability, beauty, and security** on real hardware and VMs.
  This physical computer is now the dedicated MoOS development station. Its
  boot and rollback remain load-bearing for continuing development.
- **Arabic and RTL are first-class**. Layouts use logical dimensions; read the
  actual resolution and scale from the session, not a remembered reference PC.

## Select the work and its evidence

Read the plan in [`docs/DEVELOPMENT_PLAN.md`](../../docs/DEVELOPMENT_PLAN.md). Its
unfinished tasks are ONE execution backlog. P0–P6 are work-stream IDs; follow
the active milestone order in that plan, with boot/security/data-loss defects
first and the owner's visual priority next. Work in **milestone batches**:
implement the largest safe, coherent group of related tasks in a
cycle, move to the next task automatically, and fix what you find on the way. Each task
still needs a bounded result with an observable exit condition before you change code.

Fast signals belong in the cycle — targeted tests, `just check`, live/rendered review,
and reviewable commits integrated as a coherent batch. The expensive signals belong at the end of
the milestone: the full local image build, the signed candidate, three QCOW2 boots, the
offline ISO install, the ARM proof and promotion, all started by one command,
`scripts/release-candidate.sh`. A Tier 1 change (Containerfiles, `build.sh`, packages,
initramfs, kernel arguments, boot, signing, installer) is the exception that still builds
and proves before it ships. Batching removes iterations, never gates: signing, rollback,
identity and every firing gate hold exactly as written below.
Independent review, host diagnostics and tooling may run beside a candidate build;
keep that candidate's branch/SHA fixed. Any later source change needs a new candidate.
Check active release runners and workflow SHAs before dispatching. A running
candidate freezes `main`, not independent development on a topic branch. Reuse
its run IDs for monitoring; never duplicate the build or cancel somebody else's
proof casually. Each push to `main` starts image CI, so batch related reviewed
commits into one integration and use `RELEASE.md` for delivery.

| Work | Read before acting | Required distinction |
| --- | --- | --- |
| Boot, units, image assembly | [Boot wiring and image verification](references/boot-wiring-and-image-verification.md) | source declaration vs installed unit wiring and actual initramfs |
| KDE, Wayland, apps or artwork | [Agent guide](../../docs/AGENT_GUIDE.md), [visual contract](../../artwork/MOOS_UI2_DESIGN.md) | generated assets vs live readback, input and rendered pixels |
| Branch integration or release | [Release contract](../../RELEASE.md) | merged source vs signed candidate vs boot-proven promotion |
| Live diagnostics, visual review or workstation setup | [Live development](references/live-development.md), development-machine section of the plan | host vs sandbox tools; source vs installed UI; available SDK vs executed tests |

Before retiring a branch, fetch current refs and prove its tip is an ancestor
of the target (`git merge-base --is-ancestor`). Review unique commits when it
is not; timestamps, names and an old merged PR are insufficient. Preserve the
candidate commit ancestry and final tree required by the promotion workflow.
Inspect individual CI steps and artifacts: a skipped boot job or an advisory
review with `continue-on-error` is not acceptance evidence.

For a broad "complete the OS" request, reconcile it with the existing plan,
name the active vertical slice and keep the rest as explicit acceptance work.
An engineering team may parallelize independent files/reviews; one agent owns
integration and the candidate SHA. Kernel policy is not a custom kernel, a
healthy API process is not a successful user flow, and available assets are
not evidence that Plasma actually consumes them.

## The design language: MoOS UI

- The official design system of MoOS is **MoOS UI — Liquid Glass Design System**.
  It covers *everything the user sees*: the desktop, the panel/dock, the launcher,
  notifications, windows (Plasma Style + Aurorae), the login screen, the lock screen,
  the power/restart screen, the update screen, the installer, and the MoOS apps —
  Mo AI, Mo Store, MoPlayer, Mo PC Remote.
- Implementation lives on the **UI2 engine** (`org.moos.ui2.*`, generated by
  `artwork/generate_moos_ui2.py` + `artwork/generate_moos_themes.py`). "Nova" is now
  ONLY the name of one palette member of the family (`MoOS UI · Nova`) and of retired
  first-generation artifacts; never present "Nova" as the name of the design system.
- **Liquid Glass is deliberate, not maximal blur.** Never set `BlurStrength` above 15 —
  higher values have produced unreadable surfaces on the real machine. Motion respects
  Plasma's "animations off"; no unguarded always-running animation may ship (a single
  unguarded 8 px dot has cost ~11% of a CPU core).
- Technical identifiers are load-bearing: `MoOSUI2Nova*` asset names, `org.moos.ui2.nova*`,
  `org.moos.nova.clock`, SVG gradient ids `nova-*`, Dart `class Nova`, QML `nova*` colour
  properties, `"nova"` palette keys. **Do not rename them** outside a complete, gated
  migration.

## The rules (violating any of these is a broken session)

1. **Never claim success for anything you did not actually run and verify.** A claim
   without a command that ran and returned output is a lie in this repo's terms.
2. **Review the change and run the applicable checks.** `just check` is the
   maintained repository gate used by CI; do not extract a second test list
   from workflow YAML. Visual changes also require live interaction/rendered
   review; documentation and tooling changes do not imply a desktop redesign.
3. **Work on a topic branch.** Preserve unrelated edits, fetch current refs,
   review unique commits and integrate only tested work. Main contains candidate
   source; only proven signed promotion can reach the installed workstation.
4. **Never disable, weaken, or delete a build gate because it fails.** A firing gate is
   telling the truth. Fix the cause (usually in `build.sh`), never the gate.
5. **No undocumented temporary hacks.** If a workaround must exist, it is documented
   (what, why, how to remove) in the relevant doc or commit message.
6. **No fake apps and no dead buttons.** Anything shipped must work; QML apps are
   launch-tested by the build, and a button that does nothing is a defect.
7. **Keep rollback safe.** The previous deployment must remain bootable
   (`bootc rollback` / GRUB entry). Never break the ostree origin, the signature policy
   (`/etc/pki/containers/moos.pub`), or pin removal without an explicit, reviewed reason.
8. **Document every change that affects boot, kernel, or updates** (initramfs, dracut,
   GRUB, Plymouth, uupd/`moai-do update`, signing) — in the commit message AND in
   `PROJECT_STATE.md`.
9. **Update the truth files.** `PROJECT_STATE.md` (measured state),
   `docs/DEVELOPMENT_PLAN.md` (task status and gates), and `AGENTS.md` (rules)
   must reflect reality after your session; what is NOT done stays listed as
   not done.
10. **Respect upstream compatibility.** Prefer configuration/overlay over forking;
    changes ride on top of stock Kinoite packages so base updates keep flowing.

## How to verify (the honest loop)

```bash
# the exact repo gates CI runs (fast, no container needed):
just check
# a full local image build runs every image gate (identity, initramfs, NVIDIA, QML apps).
# Run it for Tier 1 changes and at the end of a milestone — not after every edit:
just build            # or: just build-nvidia / just build-cloud
# on the installed machine, after an update reboot:
bash tests/post-update-check.sh
```

For tests that execute desktop tools, isolate the session bus, display and
HOME/XDG state in the test process; a fake root alone does not isolate Plasma.
Check the real desktop before/after suspected test side effects. Never source
private API configuration to diagnose readiness: use redacted status endpoints.

If a gate is green but you have not seen or exercised the surface it guards,
record the missing runtime evidence. `AGENTS.md` preserves the false-green traps.

### Boot / systemd wiring traps (verified 2026-08-27)

- **A `systemctl enable` in `build.sh` is NOT proof the unit runs.** If the unit file
  has no `[Install]` section, `systemctl enable` prints a warning, returns 0, and
  creates NO wants symlink — the unit stays `static` and never starts at boot. A gate
  that only greps `build.sh` for the string `systemctl enable <unit>` is a green-check
  trap. This shipped broken in commit `4bf615a6`: `moos-visual-tier.service` had the
  enable line but no `[Install]`, so the hardware-matched motion profile was never
  applied automatically. **Fix:** add `[Install] / WantedBy=graphical.target` to the
  unit, and gate it by *proving the enable wires* (see references/boot-wiring-and-image-verification.md).
- **Inspect the BUILT image, not the source, to confirm a fix landed.** `podman build`
  serves cached layers and a green build log proves nothing about the bytes. After a
  build, `podman run --rm --entrypoint bash <img>:latest -c '...'` and assert the actual
  file/section/symlink is present (service has `[Install]`, the shim is gone, the
  initramfs exists). This caught the `4bf615a6` regression every source-level gate missed.
- **`kwriteconfig6 --file <name>` ignores `MOOS_TIER_ROOT`.** Tools like `moos-visual-tier`
  honor the env var for their own probe/read functions but shell out to `kwriteconfig6`
  for writes, which always targets the real `/etc/xdg`. A fake-root `moos-visual-tier
  --apply` therefore CANNOT validate `kscreenlockerrc` writes — prove those against the
  built image instead (run the real binary inside `podman run`, or rely on the source gate).
- **A local image is container/VM evidence only.** Do not replace this station's
  signed origin with `localhost` or an unverified transport. Follow `RELEASE.md`
  to create a signed candidate, boot the exact artifact and promote the proven
  digest. A host update is a separate action through the MoOS update authority.
