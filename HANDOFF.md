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
- `main` and `origin/main`: `8ccfeff08d25b80e60ced7fe4ebee24e95047a08`.
- The NFS-root initramfs fix from `9fe30a9` is now verified on the live system:
  this boot contains no `rpcbind`, `rpc.statd`, or `nfs-start-rpc` errors.
- The live `.252` image verified the previous `moai-control` class-scope fix,
  but exposed a second recovery-path bug: an occupied port called
  `sys.stderr.write()` without importing `sys`, causing three startup crashes.
- Commit `8ccfeff` imports `sys`, gates the import, and fixes
  `moos-device-plan` falling back to “NVIDIA image required” because current
  `bootc status` needs root. It now uses unprivileged `rpm-ostree status --json`.
- GitHub image run `29694295811` passed for both editions, pushed and verified
  signed image `.253`. Exact signed NVIDIA digest:
  `sha256:8ac01ccbba3f14c374d9534062290a12119498ab84ecbf88f0c49745b60b3a85`.
- `.253` is now booted and live-verified. `moai-control` survived the observed
  occupied-port startup path without a traceback, then a controlled restart
  bound `8079` immediately and served valid JSON.
- The next fix removes only the three generic tmpfiles creation rules that
  conflict with OSTree's `/home`, `/srv`, and `/root` symlinks. It is locally
  built and tested; commit/push and signed-image CI remain.

## Installed system

- MoOS 44 on KDE Plasma 6.7.3, Wayland, kernel 7.1.3.
- Booted origin: exact signed `ghcr.io/moalfarras-sys/moos-nvidia` image.
- Booted signed NVIDIA digest:
  `sha256:8ac01ccbba3f14c374d9534062290a12119498ab84ecbf88f0c49745b60b3a85`.
- The booted image is revision `8ccfeff`, version `44.20260719.253`, and its
  signature was verified locally with `cosign.pub`.
- NVIDIA, Wayland, Plasma login and CUDA/NVIDIA operation are live and healthy;
  `nvidia-smi` reports the RTX 2080 SUPER with driver `610.43.03`.
- The previous signed NVIDIA `.252` deployment remains available as rollback.
- `moos-selfcheck`: 39 passed.
- Failed system units: 0.
- Failed user units: 0.
- `tests/post-update-check.sh`: 39 passed on `.253`; the booted digest exactly
  matches GHCR `latest` and signature enforcement is active.

## Repository checks

Passed from the live tree with the two new fixes:

- `just check`
- `python3 tests/test_moos_theme_safety.py` (3 tests)
- `python3 tests/test_moos_ui2.py` (7 tests)
- `bash -n build_files/build.sh`
- `python3 tests/verify_user_experience.py`
- `just build` (full local bootc image, including `bootc container lint`)
- forced occupied-port test: repository `moai-control` retried for five seconds
  with no traceback or `NameError`.
- real local Mo AI chat through gateway → RamaLama → CUDA answered exactly
  `MoOS AI OK`; generation was ~8 ms/token and `llama-server` used 3386 MiB VRAM.
- live device plan from the fixed helper reports `nvidia_image=true` and
  `NVIDIA proprietary driver active`.
- temporary 4K hardware test: 3840x2160@60, scale 2; screenshot is 3840x2160
  and fonts, icons, panel, dashboard and windows remained coherent. The display
  was restored to its original 1920x1080@60, scale 1 afterward.
- `just build` full local image succeeded, including identity/experience
  firewalls, QML smoke tests and `bootc container lint`.
- tmpfiles root simulation: after scrubbing only the three conflicting
  top-level rules, `/home`, `/srv`, and `/root` remained symlinks and emitted no
  “already exists and is not a directory” messages.
- inspection of the built `moos:latest` image confirms `home.conf` no longer
  creates `/home` or `/srv`, and `provision.conf` still provisions
  `/root/.ssh` while no longer trying to recreate `/root`.

The two unittest files are reached by the recursive experience verifier invoked
by `just check`; the older handoff statement that they were outside the gate was
stale.

## Highest-priority observed issues

1. Commit/push the locally built tmpfiles fix, wait for signed-image CI, stage
   the exact NVIDIA digest, reboot, and confirm the three errors are absent.
2. Investigate repeated `No QSGTexture provided from updateSampledImage()`.
3. Investigate MoPlayer's display-change/UI-close crash path.
4. ~~Replace deprecated `Qt.btoa(string)`~~ DONE — replaced with the Qt 6.11
   array-like overload `Qt.btoa(Array.from(svg))` (verified QML-host-safe; a
   sibling session's PR #10 added a gate forbidding browser-only `TextEncoder`).
5. Introduce testing/candidate/stable image channels before treating the
    maintainer's daily driver as a general release target.

## Open issues / blockers (this session)

1. Suspend/resume was not triggered during this session: Mo Remote intentionally
   holds a sleep inhibitor, and no prior successful suspend cycle was present in
   the retained journal. NVIDIA's suspend unit/drop-in is installed.
2. Boot logs in `.253` contain tmpfiles errors for the composefs symlinks
   `/home`, `/srv`, and `/root`. The exact owning rules are now identified and
   the fix is locally built, but it is not live until a new image boots.
3. MoPlayer produced one real core dump after 25 seconds:
   `eglMakeCurrent failed` → libepoxy assertion during
   `fl_compositor_opengl_cleanup`. A controlled 15-second launch followed by
   SIGTERM exited without a crash, so startup/playback rendering is not enough
   to reproduce it; test the UI close path and display-change path separately.
4. `No QSGTexture provided from updateSampledImage()` — likely Qt/plasmashell
   internal warning; left as-is (non-blocking, not our QML).
5. CI warns that several upstream actions still target deprecated Node.js 20.

## Exact next action

Commit and push the tmpfiles fix. After image CI passes, resolve and verify the
exact signed NVIDIA digest, stage it, reboot, then verify:

```bash
rpm-ostree status
moos-selfcheck
systemctl --failed
systemctl --user --failed
journalctl -b 0 -p err..alert --no-pager
# Expect the new signed NVIDIA image, 39/39, zero failed units, and no tmpfiles
# errors for /home, /srv, or /root. Keep the previous deployment for rollback.
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
