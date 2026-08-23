# MoOS — current project state

This file is current state, not session history. Git history owns the history.
When documentation disagrees with a running machine, a freshly booted artifact,
or current source, those stronger forms of evidence win.

Last reconciled: 2026-08-23 on `fix/release-trust-boot-20260820` (PR #60)
at exact revision `70aff7a9235f8e8e641b635dce45ed3f073c9653`.

## Running development host

- Booted signed `moos-nvidia` `44.20260821.632`, digest
  `sha256:ef3b4ea72568e76a47b2b617c11ba594b93908e68c92647c7e6e5a831bc7adab`.
- Staged (not yet rebooted) `44.20260822.633`, digest
  `sha256:525ba286c317c6c5d863bba0e5a5aa2c09d89df8f1b68880e2911b591beb3de9`.
  That staged digest is **not** the frozen PR #60 candidate; do not reboot onto
  it for this release mission.
- Rollback retained: `44.20260820.617`
  (`sha256:1d9dd510f92fa906aa3a48eba0f83584417cbfb39c540db3352611cba722d1a5`).
- Hardware baseline: x86_64, kernel 7.1.8, NVIDIA RTX 2080 SUPER (driver
  610.57.04), Wayland session active, Wi-Fi connected, system and user failed
  unit sets empty at reconciliation.
- Do not update or reboot this machine onto a release digest until that exact
  signed candidate's QCOW2/ISO boots are proven and rollback is rechecked.

## Frozen candidate (PR #60)

Branch tip and remote HEAD are identical; working tree clean.

| Edition | Digest | Image workflow |
|---|---|---|
| `moos` | `sha256:87dcf9e6d8666e3eac7aeed69ec31035248c90534f82132e2afabcd7537e1342` | `32615972889` |
| `moos-nvidia` | `sha256:ab0c35a81f7941993331cd84ac8a85921637607f50ed99b905e2365098c3be22` | `32615972889` |
| `moos-cloud` | `sha256:652981fe41d696d391b768e2948b55a60c593b54b348749eff6b16d3c334ed12` | `32615972889` |
| `moos-arm` | `sha256:1abe212f5eca6e3182ad47d5a254f541da63eec1c05cc96f69418f7d709aae87` | `32615974079` |

Candidate tags are run-scoped (`candidate-32615972889-70aff7a9…`). ARM
production promote remains main-push-only and has **not** run.

### Proven for this freeze

- Signed x86 generic/NVIDIA/cloud images built and cosign-verified from the
  freeze SHA.
- ARM image + QCOW2 + UTM package from workflow `32615974079`:
  two-boot runtime proof healthy, poweroff clean, zero failed units,
  signed origin matches, UTM `Data/moos-arm.qcow2` sha256 equals
  `boot_proven_raw_qcow2_sha256`
  (`fb5c465fc25282665d682657a862f059e9a40031665f6123451fd657e9a434bb`).
- Local `~/Desktop/MoOS-Release/` currently holds matching
  `MoOS-ARM64.qcow2.zst`, `MoOS-ARM.utm.zip`, and `MoOS-ARM-iPhone.utm.zip`
  (the iPhone zip is byte-identical to `MoOS-ARM.utm.zip` by design — one
  bundle for Apple silicon and UTM SE).

### Not proven / blockers

- **x86 QCOW2 boot proof** and **final ISO live+install proof** had never
  succeeded on this freeze. Earlier failures on `d29dd5cf` stopped at
  `greeter-user` (fixed in `9cca1e0b` by querying NSS for `plasmalogin`) and
  ISO `stable-desktop`. Fresh proofs were dispatched from the freeze SHA:
  disk runs `32622079477` / `32622080738` / `32622081785` and ISO
  `32622082711`.
- **ARM visual login frame** from the healthy runtime proof is a nearly black
  1280×800 capture with cursor only (~163 non-black pixels). Runtime says
  `graphical=active`, but that is **not** accepted as visible MoOS greeter /
  desktop proof. Owner-device UTM import and OCI Ampere deploy remain open.
- PR #60 is mergeable but marked UNSTABLE solely because `claude-review`
  failed (tooling/auth noise, not an image gate). Do not merge until disk+ISO
  proofs pass on this exact tree.
- Host is not on the frozen NVIDIA digest; staged `.633` must not be confused
  with the freeze candidate `ab0c35a8…`.

## One authority per responsibility

| Responsibility | Authority | Runtime / state | Proof |
|---|---|---|---|
| OS image update | `moos-image-update` | bootc/OSTree deployment + signed origin | release gates, post-update check |
| Rollback | bootc/rpm-ostree | previous signed deployment | live deployment inspection |
| Image identity | `build.sh` / `finalize_moos_desktop.sh` | final image filesystem | three identity firewalls |
| Theme selection | `moos-theme` → `moos-apply-theme` | user KConfig/GSettings | live readback + UI gates |
| Hardware policy | `moos-device-plan` + `moos-hardware-adapt` | `/etc/moos` state | fixtures + live journal/readback |
| Kernel policy | MoKernel config/kargs/sysctl layer | running kernel values | runtime checks; no custom kernel fork |
| Mo AI config | `moai-agent-api` / OpenClaw config | user OpenClaw state | loopback API and route tests |
| Mo AI chat | `moai-gateway` | selected local/cloud backend | real response + service status |
| Mo PC Remote | `mo-remote-personal.service` | bound runtime endpoint | UI/status/port/process proof |
| Store installs | `moos-storectl` behind private QML bridge | per-user job state | catalogue/bridge tests |
| Disk installation | `moos-install-to-disk` | target disk + first-boot recipe | final-ISO install gate |
| ARM remote desktop | `moos-arm-remote` | KRDP user unit/config | opt-in runtime proof |

## Load-bearing release contracts

- Never weaken `verify_identity.py`, `verify_image_experience.py`, or
  `verify_no_foreign_identity.py`; repair the final image.
- Generic and NVIDIA share one current base. NVIDIA is layered and its exact
  kernel module must be present in initramfs.
- `ostree` must be present in every deployed initramfs.
- Published tags move only after the exact candidate artifact boots and the
  immutable digest is cosign-verified.
- ARM release packaging consumes the same QCOW2 hash that passed two-boot proof.
- The ISO source is an official signed digest and the installed origin is
  rewritten to `ostree-image-signed:` before the installer reports success.
- `/` is composefs on an installed bootc system; disk capacity is measured from
  `/sysroot`/`/var`, never from `/`.
- `/var` must be empty in the image and `bootc container lint` is a release gate.

## Still unproven

- PR #60 is not merged; `main` is 68 commits behind this branch tip.
- x86 QCOW2 and ISO install proofs for the freeze digests are in flight /
  not yet green.
- ARM greeter/desktop has runtime health but not an accepted visual frame.
- `MoOS-ARM.utm.zip` has not been imported on the owner's iPhone/iPad
  (OWNER-DEVICE-TEST-REQUIRED).
- No OCI Ampere instance from this disk (READY-BUT-NOT-DEPLOYED until
  credentials/quota allow).
- Real-host update to frozen `moos-nvidia` digest, suspend/resume, second
  reboot and rollback exercise remain open.
- Full clean-VM visual matrix (1080p/1440p/4K × scale × EN/DE/AR × dark/light)
  remains incomplete.

## Next safe order

1. Wait for freeze disk+ISO workflow results; if red, fix the reproduced
   runtime failure, checkpoint, rebuild only what changed.
2. Accept ARM only after a non-blank greeter/desktop frame (wake/capture or
   real login path) on the same QCOW2 hash.
3. Assemble `~/Desktop/MoOS-Release/` with ISO, checksums, manifest and
   install README once artifacts exist.
4. Merge PR #60 only for this exact proven tree; promote signed tags; stage
   the matching NVIDIA digest with rollback intact; reboot and live-prove
   the physical host.
