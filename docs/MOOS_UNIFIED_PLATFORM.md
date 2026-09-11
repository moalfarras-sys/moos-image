# MoOS unified platform: architecture and implementation audit

2026-09-11. Source audit with native Settings captures, local container
experiments, and read-only inspection of the daily-driver deployment and
GitHub release runs. No claim of completeness, performance parity or hardware certification.

## Decision: own the experience above KDE

Keep upstream Plasma, KWin, KDE Frameworks, Linux, systemd and bootc/OSTree.
Develop MoOS's own shell surfaces, navigation, shared controls, service contracts
and policies above them. Do not undertake a permanent full Plasma/KWin fork.
The existing engineering contract already chooses this architecture.

This repository contains substantial product code: installer, signed updater,
recovery, launcher, Settings, Store, AI, Remote and a shared design system.
The missing step is consistent behavior and qualification across their boundaries.
A compositor fork would add ownership of input, rendering, accessibility and
upstream fixes without itself repairing those boundaries. This is an engineering
judgment grounded in the current maintenance and validation gaps, not a measured
comparison of alternative compositors.

KDE documents [Plasma extension points](https://develop.kde.org/docs/plasma/)
and [KWin scripting](https://develop.kde.org/docs/plasma/kwin/). Prefer supported
extension points; track each unavoidable private API/overlay against the exact
upstream version and test upgrades. For application access to desktop resources,
retain [XDG Desktop Portal](https://flatpak.github.io/xdg-desktop-portal/docs/api-reference)
and its [desktop integration](https://flatpak.github.io/xdg-desktop-portal/docs/system-integration.html).
Do not duplicate the permission broker or expose a generic command-execution API.

## Product target

Prioritize a complete desktop/laptop and private remote-desktop experience across
x86 and ARM: one setup flow, one Settings front door, one application storefront,
consistent search/permissions, and one signed update/recovery path. Touch and
phone Remote access must use the same capabilities. A standalone phone OS would
add modem, telephony, power-management and device qualification work; native ARM
support or Waydroid alone does not establish that product.

The differentiating experience should be visible in everyday tasks: connect a
network, find/install an app, open a file, change a setting, recover a failure,
and resume the same workspace remotely. Score these complete flows before adding
more decorative surfaces or another backend abstraction.

## Existing core and API ownership

Paths below are relative to the repository.

| Capability | Current authority | Integration boundary / finding |
| --- | --- | --- |
| Boot, deployments, updates | `Containerfile*`, `build_files/build*.sh`, `system_files/usr/libexec/moos-image-update` | Signed immutable deployments exist. Base `FROM` tags remain mutable; final release proof is separate from source correctness. |
| Privileged operations | `system_files/usr/bin/moai-do` | Fixed actions, confirmation and Polkit remain the authority. Do not add another privileged service to unify presentation. |
| Desktop command routing | `system_files/usr/bin/moos-open` | Fixed `settings/*` routes. Many open an external System Settings/KInfoCenter page, so the main Settings window is a front door, not yet one continuous editor. |
| Settings state | `system_files/usr/libexec/moos-settings-status` | Private atomic JSON, schema 1, bounded probes, periodic refresh. Destination capability detection mirrors router targets. |
| AI/device state | `system_files/usr/bin/moai-control` | Loopback HTTP `/quick`, `/scan`, `/models`, `/diagnose`; browser-origin/header guards. Existing transport remains internal, not a general SDK or per-app authorization boundary. |
| Hardware identity | `system_files/usr/lib/moos/moos_hardware.py` | Shared in this pass. Previously Settings supported ARM names while `/scan` only read x86 `model name`. |
| Graphics and workload policy | `system_files/usr/bin/moos-visual-tier`, `moos-index-policy` | Visual-tier owns classification; Baloo consumes its indexing policy. Update/Remote hints are advisory, not proof of applied resource limits. |
| Design system | `system_files/usr/lib64/qt6/qml/org/moos/ui/`, `artwork/` generators | Shared QML components exist. A shared palette is not proof of keyboard, RTL, screen-reader or visual consistency in every application/toolkit. |
| Desktop permissions | `system_files/etc/xdg-desktop-portal/kde-portals.conf`, Settings permissions route | Keep the portal/KDE owners. Per-application workflows and revocation need real application tests. |
| AI product policy | `system_files/usr/lib/moai/moai_cloud_policy.py` | Cloud-only, free default, explicit paid selection. Old local-engine documentation was misleading and has been corrected. |

## Implemented in this pass

Settings and Mo AI now import one read-only hardware library using paths that
resolve both in the source tree and installed `/usr`. Existing response keys,
Settings schema and URL routes are preserved. CPU naming uses `/proc/cpuinfo`,
then util-linux `lscpu`, then a known ARM implementer/part fallback. Unknown
hardware remains an empty value for the UI's Unknown state.

Graphics descriptions in both consumers now use the existing visual-tier facts.
Mo AI previously used a shell/lspci pipeline; it now reports the same driver and
class as Settings. This is a classification/driver description, not a commercial
GPU model inventory. A future richer model field should be added at the shared
inventory boundary and tested on PCI and non-PCI hardware.

Malformed visual-tier JSON, unexpected field types, unavailable commands,
timeouts and decoding failures no longer crash the shared probe. No additional
background daemon, remote listener or privileged path was introduced.

`tests/test_settings_hardware_identity.py` retains hardware/identity assertions
and now executes both real state producers with ARM fixtures, plus x86,
missing-command and malformed-payload tests. The gate already runs in `just check`
and x86 CI. A disposable copy restoring the old Mo AI CPU probe demonstrably
fails the cross-consumer test. No identity, boot or security gate was relaxed.

### Settings workspace

Overview now places Appearance, Connectivity, Apps and System in four distinct
cards above detailed status. They use the existing section model, shared symbols
and theme roles; actions navigate inside Settings. Every section remains in the
sidebar. The sidebar scrolls on short windows, including when keyboard focus
moves out of view. Wide-window hero height is reduced; compact layouts preserve
the room needed for their controls. Arabic order, arrows and alignment follow
RTL. Enter and keypad Enter activate each new card; the native harness exposed
and verified the missing keyboard handler during development.

[Native before/after, light and Arabic evidence](evidence/settings-workspace-20260911/README.md)
includes measured resting luminance differences of 30.071 and 22.103. These are
source-window renders with native Qt, not a full desktop or installed-image proof.
Existing settings editors/backend owners remain; this pass does not claim that
every external configuration page has been embedded.

### Image state and first-boot store

`finalize_image_state.py` removes known derived DNF and empty Flatpak installation
state after all package transactions. Before recursive deletion it rejects a
cleanup root that became a file or mount and rejects links and special nodes
inside it. Its final sweep rejects unknown files, empty directories, links and
non-allowlisted mounts across both `/var` and `/run`. Explicit package-created
directories are converted leaf-first into generated tmpfiles declarations with
their measured modes and named owners, then removed from the image.
The X server package's `README.compiled` is preserved under immutable
`/usr/share/doc/moos-xkb`, and its empty keymap cache receives a tmpfiles
declaration. This was caught by the full NVIDIA build after the generic
experiment passed. Boot files are outside the cleanup scope. Buildah's exact
cache/runtime mounts and the base's zero-byte resolver mountpoint are validated
through a narrow allowlist. The last identity firewall remains last and now also
requires the inherited store bootstrap to be masked and absent from boot targets.

`moos-flatpak-init.service` initializes fresh installations from the immutable
Flathub remote declaration, with `extra-languages=ar;en;de`, before the display
manager. It uses a pending/completion transaction so a partial fresh store is
retried, while existing repo configuration and user choices are preserved. An
early preset keeps it enabled through bootc installer finalization. The base
bootstrap is masked because it raced MoOS and added two disabled foreign remotes;
the helper migrates only those exact automatic entries when no installed ref
depends on them. This is a one-shot boot reconciliation, not a second update
service. x86 and ARM share it. `moos-hardware.conf` declares `plugdev` via sysusers.

Ten image-state tests exercise preservation, rejection, `preset-all` and mask
survival, offline completion, safe legacy migration, tmpfiles directory
recreation with its original mode, and the real x86/ARM/ISO store-check snippets
against healthy and broken fixtures.
The artifact checks read the repo and trusted key **before** invoking Flatpak,
so Flatpak cannot silently initialize them and create a false-green boot test.

The native ARM candidate exposed another lifecycle issue: its package setup
writes `/var/lib/authselect/checksum`. The ARM compose path preserves those exact
bytes under `/usr/lib/moos` and uses a tmpfiles copy-if-absent rule to initialize
fresh systems without overwriting existing machine checksums. Upstream's
`authselect-apply-changes.service` keeps ownership of profile upgrades.
The actual compose block, checksum restoration and `authselect check` passed
in a disposable local image. Compose now rejects a missing/empty checksum and
the signed ARM disk gate runs `authselect check` on both boots; native ARM CI
must repeat the complete proof.

The NVIDIA build also exposed expired shared DNF metadata requesting a retired
Mesa i686 RPM (HTTP 404). A fresh query resolved an available newer version.
The first package transaction now uses `--refresh`; the kernel exclusion still
precedes every transaction, and all NVIDIA/kernel/initramfs guards are intact.

## Ordered implementation and acceptance

| Priority | Work | Evidence required before closure |
| --- | --- | --- |
| P0 | Resolve built-image lifecycle warnings | Known mutable files, sysusers and empty-directory/runtime ownership are fixed in source and a disposable image; the EFI/GRUB boot-asset warning remains. Prove first-run Store initialization in the new disk/ISO artifacts before promotion. |
| P0 | Complete the x86 candidate → disk/ISO → installed session → promotion chain | One source SHA and signed digest across proofs; failed system/user units diagnosed; desktop and apps open/close/reopen. Prior revision `c0cc94e7` completed formal promotion in run `34432578942`; repeat the proof for this changed candidate. |
| P0 | Freeze approved upstream inputs once for each release | Shared exact x86 base/kernel across generic/NVIDIA/cloud; explicit ARM digest; deliberate upstream tag movement cannot change the candidate mid-build. |
| P0 | Align ARM rebuild cadence and source coverage with x86 | Scheduled rebuilds and the complete source suite; signed exact artifact and boot proof still precede tag promotion. The current ARM workflow has no schedule trigger. |
| P0 | Prove interrupted update, staging headroom and rollback | Disposable VM fault injection first; previous signed deployment and user data survive. Physical NVIDIA acceptance remains a separate exercise. |
| P0 | Resolve sustained-session/OOM uncertainty | Same-workload memory and compositor traces over time; no unexplained growth or lost Remote session. A healthy short sample is insufficient. |
| P1 | Establish shared read-only state contracts incrementally | Inventory current callers; define field types, unknown/error/freshness semantics and compatibility fixtures. Move one domain at a time behind existing adapters; hardware identity is the first implemented domain. |
| P1 | Unify Settings navigation | Start with one domain, retain its existing backend, implement loading/error/apply/revert/readback and keyboard/back navigation in the MoOS window. Keep working external pages until replacements are proven. |
| P1 | Complete permissions, first run and app lifecycle | Fresh offline/online setup, locale/timezone/input persistence; install-launch-use-reopen-remove per app; portal allow/deny/revoke readback. Android/Windows compatibility is per-app, not universal. |
| P1 | Prove the common visual and accessibility system | Real captures of login/lock/logout/apps across scale, light/dark and Arabic/English; focus traversal, screen-reader output, contrast and disabled-motion acceptance. |
| P1 | Qualify hardware and performance | Publish tested/experimental/unsupported per device. Measure idle, input, video, AI and Remote separately, including p50/p95 latency, PSS, power and thermal behavior. |
| P2 | Developer contract and diagnostics | Document versioned public capabilities only after internal consumer tests stabilize; opt-in redacted support bundle; bounded jobs, progress/cancellation and stable error codes under existing owners. |

The API objective is one definition and owner of each capability, with consistent
state and errors across native/remote clients. It does not require routing every
OS operation through one giant daemon. Start with shared libraries for in-process
facts; use existing D-Bus/portal services for desktop operations and existing
allowlisted command adapters for privileged actions. Add a new bus service only
when measured cross-process lifecycle or subscription requirements justify it.

## Validation and release limits

Six focused executable tests passed, including real Settings/scan agreement on
ARM fixtures. Restoring the previous CPU probe in a temporary tree made that
same test fail. `just check` completed successfully (exit 0); its coverage gate
reported 130 listed gates before the image-state gate was added; the current suite has 131. The first suite skipped three Qt motion tests because they only recognized
the retired generic QML launcher. The harness now uses the installed
`moos-qml-shell`; all three runtime tests subsequently passed, including the
intentional broken-gate control.
Log: `/var/tmp/moos-unified-check-20260910.log`. A read-only host probe also
confirmed both consumers return `Intel(R) Core(TM) i5-14400F` through the shared
module. ARM proof here is fixture-based, not a new ARM hardware run.

The generic image build completed with exit 0:
`localhost/moos:unified-platform-20260910`, image ID
`b844a8c3b4cb3d58ea9ba45eafc0892158e13e10328cdd1f30faaa5a94f2ac27`.
Log: `/var/tmp/moos-unified-build-20260910.log`. The final initramfs measured
107 MiB; image-experience and identity-firewall gates passed. Independent
`podman run --rm --entrypoint python3` inspection verified SHA-256 equality for
the shared module and both consumers against this working tree, imported both
installed consumers and proved they use the same installed module and CPU name.

**Image completion is not release acceptance.** That earlier generic build
returned 0 despite four lint warnings and real DNF/Flatpak files under `/var`.
The final cleanup experiment built `localhost/moos:state-proof`, ID
`cc5146c15742…`, successfully: no regular mutable files remained; 12 lint checks
passed, one skipped, and only the `nonempty-boot` warning for EFI/GRUB assets
remained. No lint rule was suppressed. Runtime-only `ask-password` is removed
at compose and recreated by the existing `systemd.conf` policy. For the known
empty package directories (`livesys`, `lxc`, `lxcfs`, `rpm-state`,
`samba/winbindd_privileged`), compose emits tmpfiles declarations only when the
package has supplied the directory, preserving its actual mode and named owner.
The test recreates a removed directory with the real `systemd-tmpfiles` command
and verifies its mode. EFI/GRUB assets remain intact for final boot/install proof.

A disposable `podman run --network none` after finalization recreated the store
using the unit's exact Flatpak command, read back `ar;en;de`, found the `flathub`
remote and trusted key, and proved the unit condition skips an initialized repo.
This is offline command-level evidence, not a systemd boot or install proof.
The full NVIDIA image built successfully: `14b21c399430…`,
`localhost/moos-nvidia:unified-platform-20260911`. Final identity/application
and boot gates passed. Offline inspection matched six source hashes, verified
the enabled store unit and generated tmpfiles policy, proved shared installed
hardware imports and zero regular files in `/var`, and checked the four NVIDIA
modules inside the 203,733,446-byte initramfs for `7.2.4-200.fc44.x86_64`.
It also repeated offline store recreation on this final image. The only lint
warning is the retained EFI/GRUB boot content (12 passed, one skipped). No new release was staged or
rebooted at the time of this source record. No comparative performance benchmark
or new physical-device qualification was performed.
