# MoOS current state

This file contains current measured facts only. Git history owns old sessions,
rejected approaches and completed incident narratives.

## Source state

- Date measured: 2026-09-13.
- Active branch: `fix/first-install-hardware-update-race-20260913`.
- Source head contains the first physical-install repairs, physical NVIDIA
  proof and the repository cleanup described below. Use `git log` for hashes;
  this file records product state rather than duplicating history.
- GitHub authentication is not configured on this installation. The branch is
  local and has not been pushed or released.
- Latest retained local test image:
  `localhost/moos-nvidia:latest`, image ID `6161803c8dee`, 15.7 GB.

## Physical development machine

| Area | Measured state |
| --- | --- |
| Install | Offline USB installation completed successfully |
| Target disk | `/dev/sdb`: 512 MiB ESP + 476.4 GiB Btrfs |
| Other disks | Existing NTFS/NVMe disks were not modified |
| CPU / RAM | Intel Core i5-14400F / 15.4 GiB |
| GPU | NVIDIA RTX 2080 SUPER |
| Network | Intel AX210 Wi-Fi/Bluetooth + RTL8125 Ethernet |
| Display | Wayland, HDMI, 3840×2160@60, scale 250% |
| Audio | PipeWire and Bluetooth audio operational |
| Firmware | Inventory completed; no update offered |
| Failed units | Zero system and user units |
| Storage after cleanup | 48 GB used of 477 GB on `/var` |

The machine boots signed `moos-nvidia` version `44.20260913.819`, resolved
digest `sha256:c7c58ab993345b1ce2eba7e08e903bb715f4957902fec9d4a93b1e959e4beb15`.
A signed generic deployment is retained for rollback.

Current host versions:

| Component | Version |
| --- | --- |
| Kernel | `7.2.4-200.fc44.x86_64` |
| Plasma Desktop / Workspace / KWin | `6.7.5` |
| systemd | `259.8` |
| bootc | `1.16.10` |
| rpm-ostree | `2026.2` |
| NVIDIA driver | `615.71.09` |

The NVIDIA modules `nvidia`, `nvidia_drm`, `nvidia_modeset` and `nvidia_uvm`
are loaded. `nvidia_peermem` is intentionally absent from early loading. The
kernel journal contains no fatal NVRM event.

## Verified source and image

`just build-nvidia` completed with exit code 0 from the current source:

- complete repository gate passed;
- MoRemote tests and publish passed;
- MoPlayer analysis passed and all 179 tests passed;
- every first-party QML application remained alive in its runtime smoke test;
- identity, image-experience and no-foreign-identity gates passed;
- Store catalog and clean image-state gates passed;
- all 12 `bootc container lint` checks passed;
- final initramfs size is 194 MiB;
- `lsinitrd` proved `ostree-prepare-root`, MoOS Plymouth assets and six NVIDIA
  kernel modules are present.

The lint warning for non-empty `/boot` is intentional: EFI/GRUB inputs are
required by the offline ISO path.

After repository cleanup, `just check` completed again with exit code 0. The
cleanup changes documentation, test fixtures and unused generator outputs; a
new image build is therefore still required for the eventual P0 candidate.

## Fixed in the current branch

1. NVIDIA first-run switching and automatic updates now share one image lock.
   An automatic update cannot overwrite a staged signed edition switch.
2. Update comparison reads the resolved deployment digest for tag-tracked
   images and no longer reports a false downgrade.
3. The index policy controls `kde-baloo.service`; it no longer spawns a second
   unmanaged indexer.
4. Mo AI migration preserves policy-approved providers, models and keys and can
   recover the exact previously observed key-loss shape from the private
   pre-migration file.
5. Fresh images no longer ship four retired local-brain units or advertise a
   local-brain launcher action. Upgrade migration still masks old installed
   copies.
6. Six competing product plans, old session evidence, retired remote/UI1
   artwork and unused static wrappers were removed. `README.md`, this file and
   `docs/DEVELOPMENT_PLAN.md` now form one entry point, one measured state and
   one task queue. `tests/test_repository_hygiene.py` rejects retired paths,
   broken Markdown links and a new state-file diary. Current deterministic
   sources, runtime assets and test-consumed review sheets remain.

`moos-selfcheck` reports 49 passed, zero broken. Baloo runs under its user unit
and indexed 25,676 files using 136.61 MiB at the last measurement.

## Known open gaps

- Mo AI free cloud: the current OpenRouter route has no OpenRouter API key and
  therefore returns HTTP 503. The previously entered Zen key reached Zen, but
  Zen returned HTTP 401 because that provider requires billing. No secret is
  stored in the repository.
- NVIDIA acceptance still needs photographed Plymouth/login evidence,
  suspend/resume twice, multi-monitor coverage and deliberate rollback then
  roll-forward on hardware.
- Rollback against a deliberately broken update has not been proven first in a
  disposable VM.
- Laptop power/lid/brightness, touch/tablet, camera, broad Bluetooth/audio and
  diverse Wi-Fi hardware are not qualified.
- ARM and cloud editions require fresh exact-commit boot proofs after this
  branch lands.
- The local image is unsigned test evidence. It must not replace the signed
  installed deployment or be described as a release.

## Next task

Execute `P0.1` in [`docs/DEVELOPMENT_PLAN.md`](docs/DEVELOPMENT_PLAN.md): push
the cleaned branch after GitHub authentication, obtain review, then build and
boot-prove the exact candidate digest before any promotion.
