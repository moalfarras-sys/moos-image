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
- Starting `main` and `origin/main`: `a623cb29e0b29b865313422b53978df1749edbb3`.
- Current source change: omit dracut's NFS-root module from both generated
  initramfs passes; this stops its initrd-only `rpcbind`/`rpc.statd` startup on
  local OSTree boots without removing post-switch-root NFS client support.
- The change passed the full local image build and is awaiting commit, push,
  CI, signed-image deployment, reboot, and live-journal verification.

## Installed system

- MoOS 44 on KDE Plasma 6.7.3, Wayland, kernel 7.1.3.
- Booted origin: `ghcr.io/moalfarras-sys/moos:latest`.
- Booted digest:
  `sha256:43f0c86fd739312bd91ecaea37f70ec42532a6a5e403669095741c9df2786584`.
- An exact signed switch to `ghcr.io/moalfarras-sys/moos-nvidia` is staged.
- Staged NVIDIA digest:
  `sha256:96f9e0e64c5d4027233ed50c2344436f2217e1dd8b69e3831be67039a56dcdc9`.
- The staged image is revision `a623cb29`, version `44.20260719.250`, and its
  signature was verified locally with `cosign.pub`.
- Do not assume the staged deployment is healthy until it has booted and the
  NVIDIA, Wayland, login, CUDA, and rollback checks have passed.
- `moos-selfcheck`: 39 passed, with one informational staged-update note.
- Failed system units: 0.
- Failed user units: 0.
- `tests/post-update-check.sh` reports that the booted digest is older than the
  registry image. This is expected until a tested update is booted, but must not
  be silently ignored.

## Repository checks

Passed from the live tree based on `a623cb29`, including the NFS-initramfs fix:

- `just check`
- `python3 tests/test_moos_theme_safety.py` (3 tests)
- `python3 tests/test_moos_ui2.py` (7 tests)
- `bash -n build_files/build.sh`
- `python3 tests/verify_user_experience.py`
- `just build` (full local bootc image, including `bootc container lint`)
- Direct inspection of the built initramfs confirmed that the `nfs` dracut
  module, `nfs-start-rpc`, and `rpc.statd` are absent.

The two unittest files are reached by the recursive experience verifier invoked
by `just check`; the older handoff statement that they were outside the gate was
stale.

## Highest-priority observed issues

1. Commit and push the tested initramfs fix, then do not update/reboot into its
   image until the GitHub image workflow completes successfully.
2. After CI succeeds, replace the currently staged NVIDIA image with the exact
   newly signed digest, reboot deliberately,
   then run the complete live verification and prove rollback.
3. The live journal recorded
   `ReferenceError: orbPulse is not defined` from Mo AI's `launch()` function.
   Confirm whether current source still reproduces it and add a regression gate.
4. Investigate repeated `No QSGTexture provided from updateSampledImage()`.
5. Investigate previous `moai-gateway.service` and `moai-control.service`
   restart failures even though both recovered.
6. Verify on the newly booted live image that the initrd NFS/RPC errors are gone.
7. Identify the tmpfiles rules that mishandle `/home`, `/srv`, and `/root` on
   the bootc/composefs layout.
8. ~~Replace deprecated `Qt.btoa(string)`~~ DONE — replaced with the Qt 6.11
   array-like overload `Qt.btoa(Array.from(svg))` (verified QML-host-safe; a
   sibling session's PR #10 added a gate forbidding browser-only `TextEncoder`).
9. Introduce testing/candidate/stable image channels before treating the
    maintainer's daily driver as a general release target.

## Open issues / blockers (this session)

1. **This NVIDIA machine is currently BOOTED on the GENERIC `moos` image with
   no NVIDIA driver.** This is the top live priority and is NOT yet fixed
   (the exact NVIDIA image is staged, but reboot is intentionally deferred until
   the new fix passes CI so only one reboot is needed).
2. `No QSGTexture provided from updateSampledImage()` — benign Qt/plasmashell
   internal warning; left as-is (non-blocking, not our QML).

## Exact next action

Commit and push the initramfs fix, wait for the image workflow, resolve and
verify the new exact NVIDIA digest, then replace the staged deployment with it.
Only then reboot and verify driver, login, Wayland, journal, and rollback safety:

```bash
# 1. After CI, deploy the new exact signed NVIDIA digest (keep generic rollback)
sudo rpm-ostree rebase ostree-image-signed:docker://ghcr.io/moalfarras-sys/moos-nvidia@sha256:NEW_CI_DIGEST

# 2. Reboot into it
sudo systemctl reboot

# 3. After boot, verify (as the desktop user):
lsmod | grep -E '^nvidia '            # must show the nvidia driver
nvidia-smi                              # must report the RTX 2080 SUPER
rpm-ostree status                       # booted edition must now be moos-nvidia
moos-selfcheck                          # expect 39/39
journalctl -b 0 | grep -iE 'rpc\.statd|rpcbind|orbPulse|Address already in use|Qt.btoa'
# Expect no initrd rpc.statd/rpcbind hard errors. Confirm the previous generic
# deployment remains listed and usable as the rollback entry.
```

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
