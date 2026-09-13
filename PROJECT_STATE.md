# MoOS current state

This file contains current measured facts only. Git history owns old sessions,
rejected approaches and completed incident narratives.

## Source state

- Date measured: 2026-09-13.
- Integration: [PR #92](https://github.com/moalfarras-sys/moos-image/pull/92),
  first-install repairs and repository cleanup; follow-up review also fixes
  legacy Baloo ownership and makes the engineering workflow reproducible.
- GitHub authentication and branch publishing work from the host. Thirteen
  historical remote branches were deleted after fresh ancestry checks proved
  every tip was already contained in `main`; their commits remain in history.
- `main` still represents the previous accepted release. The new source must
  complete the candidate/boot-proof contract before release integration.
- Latest retained local test image:
  `localhost/moos-nvidia:latest`, image ID `8d325f56369b`.

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
| Audio | PipeWire devices enumerated; Bluetooth powered; full playback/call matrix open |
| Firmware | Inventory completed; no update offered |
| Failed units | Zero system and user units |
| Storage after build/SDK setup | 62 GiB used of 477 GiB; 413 GiB available on `/var` |

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

`just build-nvidia` completed with exit 0 including the Baloo ownership fix:

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

PR checks at `55898f85` passed the repository gates, MoRemote checks and ARM
image build. ARM signing/disk/boot/promotion were skipped on the PR. The Claude
advisory action failed inside a green job; it provided no completed code review.
Direct independent source review found the Baloo edge fixed below.

Candidate run [34767888628](https://github.com/moalfarras-sys/moos-image/actions/runs/34767888628)
successfully built and signed all three x86 editions at the earlier `55898f85`
revision. Its outputs cannot prove later changes.
A new exact revision and artifact proofs are required for release acceptance.

## Fixed in the current branch

1. NVIDIA first-run switching and automatic updates now share one image lock.
   An automatic update cannot overwrite a staged signed edition switch.
2. Update comparison reads the resolved deployment digest for tag-tracked
   images and no longer reports a false downgrade.
3. The index policy controls `kde-baloo.service`; it no longer spawns a second
   unmanaged indexer. It checks D-Bus ownership after stopping that unit and
   preserves the index if a legacy daemon survives or ownership is unknown.
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

`moos-selfcheck` reports 50 passed, zero broken, six notes: cloud key setup,
two omitted tray controls and four retired local-brain units still present in
the installed release but masked. Source fixes are not yet installed fixes.

## Workstation and performance

- `scripts/setup-development-machine.sh --check` is read-only and delegates
  from VS Code Flatpak to the host. It distinguishes available tools from
  executed builds and reports SDK gaps without reading provider credentials.
- `.vscode/extensions.json` recommends eight component-specific extensions;
  personal editor settings remain ignored. Qt QML and ShellCheck support were
  installed locally; 24 unrelated/duplicate extensions were uninstalled.
- Native .NET SDK `10.0.401` was installed in user space from Microsoft's
  release artifact after checking its published SHA-512. The shared editor SDK
  path now exists; `just dotnet-check` built every MoRemote .NET project and
  passed all test executables with exit 0.
- Boot measured 36.783 s including firmware/loader, with 11.335 s userspace.
  `ldconfig` accounted for 5.325 s; a later boot must determine repeatability.
- A five-second sample with browser/editor active was 94–97% CPU idle. This
  is not a clean desktop-idle or memory-pressure qualification.
- Twenty-six `qwebengine_convert_dict` SIGTRAP dumps came from Hunspell RPM
  scriptlets inside the rootless image build. They were not desktop app crashes
  or `just check` fixtures. Explicit dictionary conversion passed; suppressing
  those earlier scriptlet dumps remains unimplemented.

## Visual review

The source Settings harness ran on the installed Wayland/Qt stack at 250%.
Arabic 1400×760 logical frames showed coherent RTL and active Aurora colours.
An English run exposed stale input status: navigation passed while real actions
were disabled. The harness now requires fresh status before normal captures and
fails if image saving fails. A stale-status negative run exited 1 as intended.
Fresh English 1100×700 and Arabic 1400×760 reruns passed search/Escape and all
four workspace keyboard routes, saving eleven section/error frames each.
Private captures remain
outside Git. This harness does not prove a new installed release or screen/file
portals. Full light/dark and scaled desktop review remain open.

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

Complete `P0.1` in [`docs/DEVELOPMENT_PLAN.md`](docs/DEVELOPMENT_PLAN.md):
publish the reviewed fixes as one revision, build signed candidates, then run
`P0.2` exact-digest disk and offline-ISO proofs. Merge/promotion and the physical
update must follow the evidence; free cloud chat still needs a provider key.
