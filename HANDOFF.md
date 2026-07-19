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
- `main` and `origin/main`: `9fe30a96fd310ac95454df9fe5c6dd196395611c`.
- The NFS-root initramfs fix from `9fe30a9` is now verified on the live system:
  this boot contains no `rpcbind`, `rpc.statd`, or `nfs-start-rpc` errors.
- Current source change fixes `moai-control` crashing at class definition with
  `NameError: self is not defined`; the gateway/response block is restored to
  `H.do_POST`, with an AST regression gate that catches class-scope request code.

## Installed system

- MoOS 44 on KDE Plasma 6.7.3, Wayland, kernel 7.1.3.
- Booted origin: exact signed `ghcr.io/moalfarras-sys/moos-nvidia` image.
- Booted signed NVIDIA digest:
  `sha256:284a8f229046c77199ff7c0a6bc576b967a02e9279042a37826f5cf49c758ea7`.
- The booted image is revision `9fe30a96`, version `44.20260719.251`, and its
  signature was verified locally with `cosign.pub`.
- NVIDIA, Wayland, Plasma login and CUDA/NVIDIA operation are live and healthy;
  `nvidia-smi` reports the RTX 2080 SUPER with driver `610.43.03`.
- The previous generic `.241` deployment remains available as rollback.
- `moos-selfcheck`: 38 passed, one note because the broken installed
  `moai-control` is intentionally stopped until the fixed image is deployed.
- Failed system units: 0.
- Failed user units: 0.
- `tests/post-update-check.sh`: 39 passed; the booted digest is exactly the
  published `moos-nvidia:latest` digest and signature enforcement is active.

## Repository checks

Passed from the live tree with the `moai-control` fix:

- `just check`
- `python3 tests/test_moos_theme_safety.py` (3 tests)
- `python3 tests/test_moos_ui2.py` (7 tests)
- `bash -n build_files/build.sh`
- `python3 tests/verify_user_experience.py`
- `just build` (full local bootc image, including `bootc container lint`)
- isolated live HTTP test: service startup, `GET /config`, `POST /config`, and
  follow-up `/status` all succeeded; the process remained alive.
- the new AST gate was proven to bite by deliberately moving the block back to
  class scope, observing both expected failures, then restoring the fix.

The two unittest files are reached by the recursive experience verifier invoked
by `just check`; the older handoff statement that they were outside the gate was
stale.

## Highest-priority observed issues

1. Commit/push the tested `moai-control` fix, wait for signed-image CI, deploy
   its exact NVIDIA digest, reboot, and verify the installed service/API live.
2. Investigate repeated `No QSGTexture provided from updateSampledImage()`.
3. Identify the tmpfiles rules that mishandle `/home`, `/srv`, and `/root` on
   the bootc/composefs layout.
4. ~~Replace deprecated `Qt.btoa(string)`~~ DONE — replaced with the Qt 6.11
   array-like overload `Qt.btoa(Array.from(svg))` (verified QML-host-safe; a
   sibling session's PR #10 added a gate forbidding browser-only `TextEncoder`).
5. Introduce testing/candidate/stable image channels before treating the
    maintainer's daily driver as a general release target.

## Open issues / blockers (this session)

1. The installed `.251` image has a broken `moai-control`; its user service was
   stopped to end the restart loop. The repository fix is locally verified but
   is not live until a new signed image is built, staged, and booted.
2. `No QSGTexture provided from updateSampledImage()` — likely Qt/plasmashell
   internal warning; left as-is (non-blocking, not our QML).

## Exact next action

Commit and push the tested `moai-control` fix. After image CI succeeds, resolve
and verify the exact signed NVIDIA digest, deploy it, reboot, then verify:

```bash
# 1. Deploy only the exact digest emitted by the successful image workflow
sudo rpm-ostree rebase ostree-image-signed:docker://ghcr.io/moalfarras-sys/moos-nvidia@sha256:NEW_DIGEST
sudo systemctl reboot

# 2. After boot, verify (as the desktop user):
lsmod | grep -E '^nvidia '            # must show the nvidia driver
nvidia-smi                              # must report the RTX 2080 SUPER
rpm-ostree status                       # booted edition must now be moos-nvidia
moos-selfcheck                          # expect 39/39
systemctl --user status moai-control.service
curl -H 'X-Moai-Control: 1' http://127.0.0.1:8079/config
journalctl --user -b 0 -u moai-control.service
# Expect an active service, a JSON response, and no NameError/restart loop.
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
