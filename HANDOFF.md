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
   missing state directories. (No NFS/rpcbind unit present in repo as of this
   session — likely already handled or lives outside system_files; recheck.)
7. Identify the tmpfiles rules that mishandle `/home`, `/srv`, and `/root` on
   the bootc/composefs layout.
8. ~~Replace deprecated `Qt.btoa(string)`~~ DONE — replaced with the Qt 6.11
   array-like overload `Qt.btoa(Array.from(svg))` (verified QML-host-safe; a
   sibling session's PR #10 added a gate forbidding browser-only `TextEncoder`).
9. Add all maintained tests to `just check` and CI.
10. Introduce testing/candidate/stable image channels before treating the
    maintainer's daily driver as a general release target.

## Open issues / blockers (this session)

1. **Cannot push OR deploy from the agent** — the session had no GitHub token
   until late, and `sudo` needs the maintainer's password (not scriptable).
   The fix commit `b7a2175` was pushed (now merged via `dfe1b37` + `11cb3e9`).
   The **deployment + reboot step requires the maintainer** to run the commands
   in "Exact next action" below.
2. **This NVIDIA machine is currently BOOTED on the GENERIC `moos` image with
   no NVIDIA driver.** This is the top live priority and is NOT yet fixed
   (needs the reboot below).
3. `No QSGTexture provided from updateSampledImage()` — benign Qt/plasmashell
   internal warning; left as-is (non-blocking, not our QML).

## Exact next action (maintainer, needs sudo password)

This RTX 2080 SUPER box is on the driverless generic image. Deploy the freshly
built + signed NVIDIA image (rev `11cb3e9`, version `44.20260719.247`) and
reboot, then verify the driver, login, Wayland and rollback:

```bash
# 1. Deploy the exact signed NVIDIA digest (keeps the current generic deploy as rollback)
sudo rpm-ostree rebase \
  ostree-image-signed:docker://ghcr.io/moalfarras-sys/moos-nvidia@sha256:eacf979c3f1e36fd787f76446a143b47d90332f76a5c7d6fb5326c4b4bd50097

# 2. Reboot into it
sudo systemctl reboot

# 3. After boot, verify (as the desktop user):
lsmod | grep -E '^nvidia '            # must show the nvidia driver
nvidia-smi                              # must report the RTX 2080 SUPER
rpm-ostree status                       # booted edition must now be moos-nvidia
moos-selfcheck                          # expect 39/39
journalctl -b 0 | grep -iE 'orbPulse|Address already in use|Qt.btoa'   # expect nothing
# 4. Prove rollback safety:
sudo rpm-ostree rollback               # returns to the previous (generic) deploy
sudo systemctl reboot                  # confirm it still boots, then re-deploy nvidia
```

Do NOT trust the old staged NVIDIA digest `115141c5…` — it is an orphan that no
longer exists in GHCR. The generic image is now `sha256:81e10d12…` (same rev);

## Mo PC Remote (remote control) — status 2026-07-19

- **Verified live and WORKING**, both on LAN and from anywhere on the tailnet:
  - agent listening on `*:8765` (`MoRemotePersona`).
  - `mo-remote-personal.service` active + enabled.
  - `tailscale serve` active: `https://moos-3.tailab78a5.ts.net (tailnet only)
    -- / proxy http://127.0.0.1:8765` — real HTTPS MagicDNS name, so the phone
    reaches this machine on mobile data. Nothing published to the public internet.
- The whole chain is wired: Mo AI Remote panel buttons (Start/Stop/Reconnect/
  Open panel/Remote anywhere) -> `moos://remote/*` + `moos://do/remote-anywhere`
  -> `moos-open` (`remote_ctl`, confirm on start) -> `moai-do do_remote_anywhere`
  (Tailscale operator + `tailscale serve`).
- **Pinned in repo**: `tests/verify_user_experience.py` now gates the entire
  remote-control chain (commit `7c58fb0`) so a future edit cannot silently break
  remote access. Gate verified to bite when a route is removed.

## New-conversation prompt

Use:

> Continue MoOS from the last verified checkpoint. The repository is
> `/var/home/moos/moos-image`. Read `AGENTS.md` and `HANDOFF.md` completely,
> then verify the live system, GitHub CI, GHCR image, and OSTree deployment
> before acting. Trust observed live state over old documentation. Follow:
> fix, test, commit/push, CI, signed update, reboot when required, live
> verification. Update `HANDOFF.md` before stopping.
