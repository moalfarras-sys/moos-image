# MoOS current state

Current measured facts only; Git owns history.

## Source state

- Date measured: 2026-09-14.
- PR #93 is merged as `225e29f3`; Remote geometry source `64f0e76b` passed
  signed build 34810522899 and all three QCOW2 boot/reboot proofs. ISO run
  34811868497 installed offline, booted and opened/closed/reopened ten apps,
  but timed out waiting for the second boot ID. It was not promoted.
- GitHub authentication and branch publishing work from the host. Fourteen
  historical remote branches were deleted after fresh ancestry checks proved
  every tip was already contained in `main`; their commits remain in history.

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
| Storage during the Remote image build | 73 GiB used of 477 GiB; 403 GiB available on `/var` |

The machine now boots signed `moos-nvidia` version `44.20260913.824`, digest
`sha256:76861a3b7cc8b9d8fb61d9506ed26183b4035fae67d3e9d683bc7baadaa92d3a`,
with signed NVIDIA `44.20260913.819` retained for rollback. Boot measured
35.993 seconds, including 8.640 seconds userspace. Both failed-unit lists are empty.
A root-owned local administrator override at
`/etc/plasmalogin.conf.d/90-moos-development-autologin.conf` enables one-session
automatic login for user `moos` while this dedicated development cycle runs.
It is not in the repository/image and sets `Relogin=false`. Remove it with
`pkexec rm /etc/plasmalogin.conf.d/90-moos-development-autologin.conf` when the
owner ends development; normal MoOS releases continue to require login.

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

The P2.7 source slice has a full host `just check` pass (145 maintained gates)
and a local NVIDIA image proof: built-image QML motion passed with physical
settling/reversal/reduced-motion/hidden-state/key/pointer checks; the sound
gate resolved real core KDE event definitions to 32 original MoOS Ogg files;
the actual image carries the MoKernel identity fix and NVIDIA/OStree initramfs
content. A source Arabic/English QML frame was reviewed on the installed
Wayland/Qt stack. KDE login/logout/notification playback and custom mute need a
signed upgraded-session proof; decoding/mapping alone does not prove delivery.

Candidate run 34785063649 signed all three x86 editions at `1d92082f`.
Generic, NVIDIA and cloud QCOW2 boot/reboot proofs (34786215189, 34786216334,
34786218085) and the live/offline-install/installed-second-boot ISO proof
(34786220039) succeeded. Promotion 34807542252 moved only those proven digests.

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
7. Mo PC Remote's broken touch was reproduced on the physical Wayland desktop:
   its portal retained 1280×720 after the desktop changed to 1536×864, so a
   requested center landed at 639×359 rather than 768×432. The current branch
   observes native Wayland monitor geometry and renews the combined portal grant
   on scale, size, position, rotation or hotplug changes. A live 225%→250% test
   renewed twice and exact quarter/center/three-quarter injection then landed at
   384×216, 768×432 and 1151×647. Seven isolated regressions and the real
   Chromium mobile-input suite pass.
8. The offline installer now requires a non-empty password but does not impose
   an eight-character minimum. It visibly recommends a longer password while
   leaving length to the owner; hashing, confirmation and password-protected
   login remain mandatory.

The pre-update `moos-selfcheck` reports 50 passed, zero broken, seven notes:
cloud key setup,
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

Current Horizon work uses revision 57: larger time beside readable day/date,
a visible 40px search target in the existing launcher, and a smaller media island
with larger cover artwork. Real 4K/250% Arabic desktop captures prove rendering
and a portal-injected click opened the launcher. Source applets are temporarily
previewed with KPackage under the user's local Plasma directory; remove the
three preview packages (brand, clock, island) before release handoff.
KWin readback proves Arabic-first `ara,de`, with exactly two layouts. Source
defaults, installer and scoped stock-profile migration now agree. The VT uses
the German physical map because Arabic XKB has no matching console keymap.

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

- Mo AI free cloud now returned both `OK` and Arabic `جاهز` through the live
  gateway, including `moai.agent=true`, using `nex-agi/nex-n2.5-pro:free` with
  reported cost zero. This proves replies, not unrestricted agent tool execution.
- NVIDIA acceptance still needs photographed Plymouth/login evidence,
  suspend/resume twice, multi-monitor coverage and deliberate rollback then
  roll-forward on hardware.
- Rollback against a deliberately broken update has not been proven first in a
  disposable VM.
- Laptop power/lid/brightness, touch/tablet, camera, broad Bluetooth/audio and
  diverse Wi-Fi hardware are not qualified.
- ARM remains separately unqualified for this x86 release. The cloud x86 exact
  digest passed its QCOW2 boot/reboot proof; provider chat acceptance is still open.
- The local image is unsigned test evidence. It must not replace the signed
  installed deployment or be described as a release.
- The live `plasmawindowed` source-applet process stayed healthy but did not
  surface as a composited preview in this session's capture. Its QML/key path
  is covered by the isolated native review and direct process readback; a
  booted candidate desktop remains required visual evidence.

## Next task
Finish the visible Horizon slice through local image build and a new signed
candidate. Re-run ISO proof with independent SSH boot-ID observation and QGA
stream synchronisation; preserve both checks. Current post-update check reports
52 passes and three expected development differences: two old-image/new-layout
comparisons and the temporary launcher preview. Full release acceptance remains open.
