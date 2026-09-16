# MoOS current state

Current measured facts only; Git owns history.

## Source state

- Date measured: 2026-09-16.
- Promotion `35060599655` moved the x86 tags to revision `5fce15df`
  (version 44.20260915.836): generic
  `sha256:fa5cbfe3fa3e2d04555233e2906bbf02dec4bd04bcdd7ca5a7fced75052260d4`,
  NVIDIA `sha256:086f70863c5bb37f05a35c01761bd7c246ab0487e323b5e7c99db9db46cc91ff`
  and cloud `sha256:42a95f1d578c49e2833863e33fe3882749553556f353f9d9877f077013fd497f`,
  each verified by reading the revision label back from the production tag.
  Its proofs were build `35020040690`, QCOW2 `35041130671`/`35022568669`/
  `35022223373`, ISO `35022230306` and ARM `35024967781` — all attempt 1 on the
  exact candidate.
- The promoted revision carries the Mo PC Remote live-keymap repair (English,
  German and phone keyboards) and the signature-verified local RPM install.
- The ARM disk job was repaired (its UTM packaging step copied a deleted README)
  and run `35024967781` then passed end to end on the promoted revision.
- GitHub authentication and branch publishing work from the host; historical
  branches are deleted only after ancestry proof.

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

The machine boots signed `moos-nvidia` version `44.20260913.824`, digest
`sha256:76861a3b7cc8b9d8fb61d9506ed26183b4035fae67d3e9d683bc7baadaa92d3a`,
with signed NVIDIA `44.20260913.819` retained for rollback. The newly promoted
NVIDIA digest is not staged here yet (automatic staging timer inactive). Boot
measured 35.993 seconds, 8.640 seconds userspace. Both failed-unit lists are
empty (2026-09-15).
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

The P2.7 image proof passed built-image QML motion (settling, reversal,
reduced motion, hidden state, key/pointer) and resolved core KDE events to 32
original MoOS Ogg files. KDE login/logout/notification playback and custom mute
still need a signed upgraded-session proof; decoding alone is not delivery.

## Fixed in this branch (not yet released)

1. Mo PC Remote typing follows the running keymap. Reproduced live on `ara,de`
   with Arabic active: the shipped Latin keysym batch typed nothing. The helper
   compiles KWin's kxkbrc names with libxkbcommon (refusing a list that differs
   from KWin's live one) and reports positions, levels and dead keys; the agent
   plans text with the fewest group switches, shortcut letters by Qt's rule and
   a desktop viewer's physical keys by the character they produced. Typed text
   releases a desk Caps Lock and restores it; a viewer's letter aligns the desk
   lock with theirs, only where a Caps Lock LED makes it observable. Fifteen
   live cases through the real portal into Konsole typed exactly with Caps Lock
   on: English, German umlauts/ß/€/AltGr symbols, dead-key accents, decomposed
   input, Arabic with harakat, mixed text and viewer physical keys. Emoji and
   unconfigured scripts keep the exact paste path.
2. Mo AI offers Apps → Install RPM and recognises a dropped `.rpm`. A root-owned
   helper re-checks the confirmed digest, path, owner, architecture and an OK
   signature line (NOKEY/BAD/NOTTRUSTED rejected; digest lines alone never
   pass), then stages the package with `rpm-ostree`. The OpenAI ChatGPT
   publisher key is pinned; ChatGPT itself stays optional.
3. The ARM UTM packaging step no longer copies the retired README; the bundle
   writes its own `README-FIRST.txt`.
4. This file is back under the 200-line limit `just check` enforces; at
   `bdee8c49` it had 225 lines and `main` failed that gate.

Already released (Git history has the evidence): NVIDIA switch/update lock,
digest-based update comparison, Baloo ownership, Mo AI key migration, retired
local-brain units, repository cleanup, Remote geometry renewal, password policy.

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
- Remote typing still needs installed acceptance from the owner's iPhone and
  German keyboard; Caps Lock handling is inactive where no LED reports it.
- ARM remains separately unqualified for this x86 release. The cloud x86 exact
  digest passed its QCOW2 boot/reboot proof; provider chat acceptance is still open.
- The local image is unsigned test evidence. It must not replace the signed
  installed deployment or be described as a release.
- The live `plasmawindowed` source-applet process stayed healthy but did not
  surface as a composited preview in this session's capture. Its QML/key path
  is covered by the isolated native review and direct process readback; a
  booted candidate desktop remains required visual evidence.

## Next task
Run the signed image build, three QCOW2 proofs, the offline ISO proof and a
dispatched ARM proof on this branch's exact revision. Promote only all-green
digests, update the physical PC, reboot, then verify Remote typing from the
owner's iPhone and German keyboard, the Horizon desktop and the local-RPM flow
on the installed signed release. Release acceptance remains open.
