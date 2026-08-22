# MoOS — current project state

This file is current state, not session history. Git history owns the history.
When documentation disagrees with a running machine, a freshly booted artifact,
or current source, those stronger forms of evidence win.

Last reconciled: 2026-08-22 on `fix/release-trust-boot-20260820` (PR #60).
The last fully remote checkpoint before this document cleanup is `059f62c9`.

## Running development host

- The real host is on signed `moos-nvidia` release `44.20260820.617`, digest
  `sha256:1d9dd510f92fa906aa3a48eba0f83584417cbfb39c540db3352611cba722d1a5`.
- Signed `.612` is retained as the rollback deployment.
- Baseline boot: 37.293 s total = 10.327 s firmware + 5.994 s loader +
  6.081 s kernel + 4.274 s initrd + 10.616 s userspace.
- Hardware baseline: x86_64, kernel 7.1.8, NVIDIA RTX 2080 Super, one 4K
  display at 225%. At capture time system and user failed-unit sets were empty;
  `moos-selfcheck` was 50/50 and the post-update check 49/49.
- Do not update or reboot this machine until the exact signed candidate and its
  artifact boots are proven and the rollback deployment is rechecked.

## Current candidate

The recovery branch preserves the release-trust, x86 boot-proof, ARM, native
MoPlayer/Mo PC Remote, cloud first-boot, UTM and visual-login work. It must not
be recreated from `main` or force-pushed.

What is proven from current source:

- fast source, syntax, identity, route, ARM, release-safety and UTM gates pass;
- native ARM64 MoPlayer and Mo PC Remote are built and their architecture is
  gated—ARM does not intentionally omit either app;
- ARM owns one update writer (`moos-image-update`), one hardware policy layer,
  the shared Mo AI loopback authorities and on-demand KRDP;
- the ARM disk emergency-mode cause was reproduced under AArch64 TCG: mutable
  `/etc/udev/hwdb.bin` delayed real-root udev until `/boot` and `/boot/efi`
  timed out. The image now compiles the database under immutable `/usr/lib`;
- workflow run `32558263735` booted its exact final ARM QCOW2 twice through
  AArch64 UEFI, completed cloud-init, reached graphical login, had zero failed
  critical units and powered off cleanly. That run predates the latest UI and
  UTM fixes and is evidence of the root-cause repair, not the final release;
- Plasma Login Manager 6.7 always hides the authentication form after its idle
  timeout. `ShowClock=false` therefore produced an apparently dead wallpaper.
  The MoOS clock is enabled and is responsive at the VM's 640×480 firmware
  mode; real captured frames proved both the idle clock and wake-to-password
  form. The final candidate still needs the same visual proof after rebuilding;
- the UTM generator emits current QEMU schema v4, binds the bundle to the exact
  boot-proven QCOW2, carries a MoOS icon, and creates no shared build-time
  password. cloud-init generates a unique console credential inside each VM;
- the final-ISO workflow now contains an end-to-end offline install gate:
  LiveOS → real installer backend → blank disk → ISO detached → installed PLM
  login → desktop/app smoke → reboot → second boot → poweroff. It is source-
  gated but has not yet run on a newly built final ISO.

In progress at reconciliation time:

- ARM workflow dispatch `32563571676` builds the first candidate containing
  the responsive login and secure UTM bundle work. A final run must be repeated
  from the eventual release SHA because subsequent ISO/document commits do not
  change image bytes but do change revision provenance.

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

- The current branch is not merged or released; the real host still runs `.617`.
- The newest ARM QCOW2 has not yet been downloaded, opened visibly, logged into,
  and driven through every first-party app.
- `MoOS-ARM.utm.zip` has not been imported on an owner iPhone/iPad. Local
  AArch64/UEFI/virtio proof cannot be reported as physical iPhone proof.
- No OCI Ampere instance has been created from the final disk in this mission.
  Until credentials and host capacity allow it, status is ready-but-not-deployed.
- The new final-ISO offline install gate has not yet completed on the exact
  release ISO.
- The final generic/NVIDIA/cloud images, signed digests, real-host update,
  suspend/resume, second real reboot and rollback exercise remain open.
- The full clean-VM visual matrix (1080p/1440p/4K, 100–225%, English/German/
  Arabic, dark/light) is incomplete. Existing evidence must not be stretched
  into combinations that were not captured.

## Next safe order

1. Finish and inspect the current ARM candidate; visibly boot its exact QCOW2,
   log in, use the first-party applications, reboot and power off.
2. Fix any runtime/visual failure, add a regression gate, checkpoint and repeat.
3. Build the exact x86 candidates and final ISO; run QCOW2 and offline-install
   artifact gates.
4. Reconcile the visual matrix on clean VMs and the upgraded real host.
5. Merge the proven tree, verify signatures/digests, stage the matching NVIDIA
   deployment with rollback intact, then reboot and perform full live proof.
