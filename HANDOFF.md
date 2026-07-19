# MoOS development handoff

This is the durable continuation point for work performed from inside the
installed MoOS system. Update it at the end of every development session.

## Operating contract

The installed system, its journal, running services, active OSTree deployment,
and real hardware behaviour are the primary evidence. Repository documentation
explains intent but must not override observed behaviour.

At the start of every session:

1. Read `AGENTS.md` and this file completely.
2. Inspect `git status`, `git log`, and `origin/main`.
3. Fetch first; only fast-forward a clean tree. Never discard local work.
4. Inspect `rpm-ostree status`, failed system/user units, and both journals.
5. Compare the booted digest with the signed image currently published in GHCR.
6. Run `moos-selfcheck`, `tests/post-update-check.sh`, `just check`,
   `tests/test_moos_theme_safety.py`, and `tests/test_moos_ui2.py`.
7. Treat a feature as working only after observing it on the live system or in
   a booted VM.
8. Use the release path: fix -> tests -> commit/push -> CI -> signed image ->
   update -> reboot when required -> live verification.
9. Never weaken identity, signature, SELinux, Polkit, or boot safety gates to
   make a build pass.

Evidence priority:

`live system > live journal > observed test > current source > CI/GHCR > old documentation`

## Current checkpoint

- Date: 2026-07-19, Europe/Berlin.
- Local repository: `/var/home/moos/moos-image`.
- Branch: `main`.
- Local and `origin/main`: `d63fa01733d32bd4032a496c61dfa89a61e07192`.
- Current commit: `fix(login): wait for DRM before starting greeter`.
- Working tree was clean immediately before this handoff was created.
- The GitHub image build for `d63fa01` was still running at the checkpoint.
- The ISO and qcow2 jobs for `8c9f34a` were cancelled by the newer work.
- The previous image build for `8c9f34a` completed successfully.

## Installed system

- MoOS 44 on KDE Plasma 6.7.3, Wayland, kernel 7.1.3.
- Booted origin: `ghcr.io/moalfarras-sys/moos:latest`.
- Booted digest:
  `sha256:43f0c86fd739312bd91ecaea37f70ec42532a6a5e403669095741c9df2786584`.
- A switch/update to `ghcr.io/moalfarras-sys/moos-nvidia:latest` is staged.
- Staged NVIDIA digest:
  `sha256:115141c550c166e645fab4de2febade8df66d19ae854b5e047b377458a976a7e`.
- Do not assume the staged deployment is healthy until it has booted and the
  NVIDIA, Wayland, login, CUDA, and rollback checks have passed.
- `moos-selfcheck`: 39/39 passed.
- Failed system units: 0.
- Failed user units: 0.
- `tests/post-update-check.sh` reports that the booted digest is older than the
  registry image. This is expected until a tested update is booted, but must not
  be silently ignored.

## Repository checks

Passed at `d63fa01`:

- `just check`
- `python3 tests/test_moos_theme_safety.py` (3 tests)
- `python3 tests/test_moos_ui2.py` (7 tests)

Local `pytest` is not installed. The two unittest files above are not currently
part of `just check`; wiring every maintained test into the mandatory gate is
still required.

## Highest-priority observed issues

1. Do not update/reboot into a newly published image until its GitHub image
   workflow completes successfully.
2. After CI succeeds, stage the exact signed NVIDIA image, reboot deliberately,
   then run the complete live verification and prove rollback.
3. The live journal recorded
   `ReferenceError: orbPulse is not defined` from Mo AI's `launch()` function.
   Confirm whether current source still reproduces it and add a regression gate.
4. Investigate repeated `No QSGTexture provided from updateSampledImage()`.
5. Investigate previous `moai-gateway.service` and `moai-control.service`
   restart failures even though both recovered.
6. Fix or intentionally disable unused NFS/rpcbind startup paths and their
   missing state directories.
7. Identify the tmpfiles rules that mishandle `/home`, `/srv`, and `/root` on
   the bootc/composefs layout.
8. Replace deprecated `Qt.btoa(string)` calls in Welcome, Store, and Installer.
9. Add all maintained tests to `just check` and CI.
10. Introduce testing/candidate/stable image channels before treating the
    maintainer's daily driver as a general release target.

## Exact next action

Check the GitHub Actions result for commit `d63fa01`. If both MoOS image variants
are green, fetch the newly published digests and compare them with the staged
deployment. Do not reboot until the staged NVIDIA digest is confirmed to be the
successful build intended for this commit. Then perform the controlled reboot
and run the full post-update hardware verification.

## New-conversation prompt

Use:

> Continue MoOS from the last verified checkpoint. The repository is
> `/var/home/moos/moos-image`. Read `AGENTS.md` and `HANDOFF.md` completely,
> then verify the live system, GitHub CI, GHCR image, and OSTree deployment
> before acting. Trust observed live state over old documentation. Follow:
> fix, test, commit/push, CI, signed update, reboot when required, live
> verification. Update `HANDOFF.md` before stopping.
