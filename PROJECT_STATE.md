# MoOS — current project state

**Unified platform integration (2026-09-11, candidate source):** keep KDE/KWin
upstream and own the MoOS experience above them. Settings and Mo AI now share
`usr/lib/moos/moos_hardware.py`, with executable ARM/x86 and malformed-tool
fixtures. Settings Overview has four prominent task cards, working Enter/RTL
navigation and a scrollable sidebar on short windows. Native source captures
show resting card luminance deltas of 30.071 (dark) and 22.103 (light), with no
installed desktop overrides. [Visual evidence](docs/evidence/settings-workspace-20260911/README.md).

Compose now preflights every recursively cleaned tree, rejects files, empty
directories, links, special nodes and non-allowlisted mounts under `/var` and
`/run`, then converts the explicit cross-edition package directory set to
tmpfiles ownership before removing it. A first-boot unit initializes the system
store and ar/en/de locale policy offline while preserving existing config.
It has an early system preset and is the sole store bootstrap; the inherited
competing unit is masked. Its safe migration removes only the two exact disabled
legacy remotes when no installed ref depends on them. `plugdev` is owned by
sysusers. Offline fresh/migration/preservation probes passed in disposable
containers; signed fresh-install artifact proof remains pending.
The 131-gate source suite passed. Motion tests now use `moos-qml-shell` and
all three execute successfully instead of skipping on the installed runtime.
Empty package-owned `/var` and `/run` directories now have generated tmpfiles declarations
with their original modes and named owners. The disposable image passes 12 lint
checks with one skip; only the existing EFI/GRUB boot-asset warning remains.
[Architecture, implementation and validation](docs/MOOS_UNIFIED_PLATFORM.md).

**Superseded local NVIDIA image evidence (2026-09-11):**
`localhost/moos-nvidia:unified-platform-20260911`, ID `14b21c399430…`, built with
exit 0. Final identity, application-load and NVIDIA initramfs gates passed;
lint reports 12 passed, one skipped, and only the retained EFI/GRUB warning.
Independent offline inspection matched six shipped source files byte-for-byte,
proved zero regular files under `/var`, read the enabled store unit and generated
tmpfiles policy, imported the shared hardware module through both consumers,
and found all four required NVIDIA modules in the 203,733,446-byte initramfs
for kernel `7.2.4-200.fc44.x86_64`. Offline store recreation read back Flathub,
its trusted key and `ar;en;de`. Later artifact boots exposed a competing inherited
store service and lost enablement after installer presets, so this image is not
a releasable candidate.
Logs: `/var/tmp/moos-integrated-nvidia-final-build.log` and
`/var/tmp/moos-integrated-image-verification.log`.

**Rejected integration candidate and corrections (2026-09-11):** native CI run `34580503351`
reached finalization but correctly rejected `/var/lib/authselect/checksum`.
ARM compose now preserves the exact applied-profile checksum in immutable
storage and emits a tmpfiles copy-if-absent rule. Existing machine checksums
are never overwritten; upstream authselect remains the profile-upgrade owner.
The real compose block passed in a disposable image with `authselect check`
valid after recreation; the build and both runtime boots now require that check.
The following `a0e7ef96` image build (`34581665411`) succeeded, but ISO run
`34583782652` correctly failed because installer finalization removed the MoOS
store unit's enable link and ran the inherited bootstrap instead. ARM run
`34581668929` also exposed the two bootstraps racing and a one-sample graphical
readiness error. Neither candidate was promoted. Source now adds a preset that
survives `preset-all`, masks the inherited bootstrap, requires fresh artifacts
to expose only signed Flathub, and waits a bounded six minutes for the actual ARM
desktop/store transaction. Ten image-state tests and the full 131-gate source
suite pass; a new candidate must repeat every artifact proof.
Native ARM compose for `153f056a` (run `34646190268`) then stopped in the new
cleanup preflight, which required `run/systemd/systemd-units-load` to be a
directory. systemd 259 (Fedora 44, the ARM base) keeps it as an empty regular
file, which the cleanup already unlinks; x86 compose does not create it. The
preflight now accepts a regular file for that single entry only; symlinks,
mounts and cleanup roots that must be directories still fail (eleven
image-state tests).

**Release train and live origin re-verified (2026-09-11):** the prior claim that
promotion never ran is superseded. [Promotion run 34432578942](https://github.com/moalfarras-sys/moos-image/actions/runs/34432578942)
completed successfully on 2026-09-10 for `c0cc94e7213cafde8ddbc58d292084ae52af70f0`.
Read-only host status shows signed NVIDIA `44.20260910.796`, digest `7f1df5b03d97…`,
booted; signed `44.20260908.782`, digest `81a9061cbe2e…`, remains the rollback.
This does not constitute deliberate rollback testing or full hardware acceptance.
The new integration changes below have not yet reached the signed image.

**Local phone gateway repair (2026-09-11):** the installed OpenClaw gateway
was failed because workspace setup state had not been migrated to its new store.
After a private state/config backup, the installed `openclaw doctor --fix
--non-interactive --no-workspace-suggestions` migrated and archived legacy state.
Restarting the packaged user unit reached `ready`, `Result=success`, `NRestarts=0`.
This was local account maintenance, not part of the image overlay. Existing
DrKonqi coredump-processing timeout failures remain recorded; they were not
reset merely to produce an empty failed-unit list. Remote message delivery was
not tested by sending a message.

**Branch hygiene (2026-09-09):** remote `archive/arm-utm-20260827` deleted — it
held 18 superseded UTM/ARM commits and owed nothing to main. Local worktree
`fix/iso-session-user-20260908` was folded into main (ISO `runuser` session
identity) and removed. GitHub now has only `main`.

**Update channel unstuck (2026-09-09, emergency repair on the daily driver):**
Production `moos` / `moos-nvidia` / `moos-cloud` `:latest` had been frozen on
`44.20260823.650` since 2026-08-23. The NVIDIA PC was already on signed
candidate `44.20260908.782` (digest `81a9061c…` from build run `34213809427`).
`moos-image-update resolve` correctly returned `blocked-downgrade`; the Updater
UI then painted that protective state as a red "invalid state" error — so the
owner saw "system update is broken". The three `:latest` tags (and dated
`20260908`) were moved to the cosign-verified digests of that candidate after
snapshot/rollback-ready copies. Live resolve now returns `state=current` /
`latest_version=44.20260908.782`. This was **not** a full `promote-x86.yml` run
(ISO install proof is still red); it restored the update channel to digests
already signed and running on hardware. Source also teaches the Updater to
treat `blocked-downgrade` as healthy, and bumps `sharp` 0.35.3→0.35.4 so the
scheduled `npm audit --audit-level=high` gate stops failing the image build.

**ISO session UID fix (source, 2026-09-08):** run `34201023152` showed an
additional ISO blocker after KSplash: `kwin-active` / `plasmashell-active` then
`Failed to connect to user scope bus ... Operation not permitted`. Root SSH is
required to read `/sysroot`, but setting `XDG_RUNTIME_DIR` alone does not change
the process UID. `tests/install_live_iso.sh` now uses `runuser -u moosci` for
desktop, app open/close/reopen and user-health checks; system/origin checks stay
root. `tests/test_iso_install_gate.py` executes the SSH/gate functions and checks
every session call's identity. Exact-ISO runtime acceptance is still pending.

**The x86/NVIDIA release train, and why it was stuck (2026-09-08, Oracle A1):**
`moos:latest`, `moos-nvidia:latest` and `moos-cloud:latest` had not moved since
**2026-08-23** (`44.20260823.650`) while ARM's `latest` was current. That is not
a broken build: `build.yml` deliberately pushes only a run/SHA-bound
`candidate-*` tag, and `promote-x86.yml` moves production tags only after five
proofs of one revision — the signed build, three QCOW2 disk boots and the
offline ISO install. **At the time of this 2026-09-08 diagnosis, `promote-x86.yml` had never run.** The ISO proof kept
failing, so nothing could ever be promoted through the formal path, and until
the 2026-09-09 channel repair above the maintainer's daily driver could not
advance via `:latest`.

The ISO gate failed the same way every run: *"PLM login did not reach the
desktop: kwin_wayland not running under moosci"*, printed above four EMPTY
evidence sections. Two independent defects made it unreadable, both now fixed:

- All 14 failure dumps across `install_live_iso.sh`, `boot_live_iso.sh` and
  `boot_x86_qcow2.sh` were written `tail … 2>/dev/null >&2`. Redirections apply
  left to right, so `>&2` pointed stdout at the `/dev/null` fd 2 had just been
  set to and **every dump was discarded**. Gated by
  `tests/test_diagnostic_redirection.py`, which proves the behaviour by running
  both orders.
- `gate_until()`'s failure diagnosis runs only `if label.startswith("installed")`.
  The desktop gate's label is `"PLM login did not reach the desktop"`, so
  **nothing was collected for the one gate that fails** — while SSH was plainly
  alive. It now takes a diagnosis script, run over that same channel, printed to
  stderr as well as archived.

The MECHANISM was finally identified after the restored diagnostics ran. The password WAS typed correctly, and the `moosci` user did log in (creating a session and launching Wayland). However, Plasma 6 dropped KSplash by default, but MoOS themes still requested the `KSplashQML` engine. Under Wayland, the `ksplashqml` binary failed and exited, causing `plasma_waitforname` to time out waiting for the `org.kde.KSplash` D-Bus name. Since the desktop gate explicitly asserts no user units fail (`[ -z "$user_failed" ]`), this single `KSplash@1.service` timeout caused the script to exit with failure repeatedly for 900 seconds.

**This is now fixed**: `Engine=None` is set across all MoOS themes and `ksplashrc`, and `install_live_iso.sh` now correctly preserves the gate output when the `PLM login` label fails.

**Historical limit (superseded 2026-09-10):** ISO/promotion was still missing
after the emergency repair; the successful formal run is recorded at the top.

**Stale $HOME overrides were shadowing MoOS code on the A1 (2026-09-08):**
Mo AI's `moai-agent-api`, `moai-control` and `moai-gateway`, plus Mo PC Remote,
were all executing binaries under `~/.local/lib` (`moai-cloud-20260906`,
`mo-remote-v39-20260905`) via drop-ins from a migration two days earlier;
`moai-hermes.service` had a whole replacement unit in `$HOME`; four MoOS units
were masked to `/dev/null`. The image's copies had never run on this machine.
`moos-selfcheck` reported *"no user-level copy is shadowing a MoOS asset"*
throughout — it looked only at `~/.local/share`. It now also reports units,
drop-ins that repoint ExecStart/Environment into `$HOME`, drop-ins shadowing an
image drop-in by filename, and masks over shipped units
(`tests/test_selfcheck_unit_shadowing.py`).

**DONE (2026-09-08).** The A1 now has `44.20260908.322`
(`sha256:f8447708…`) **staged and awaiting a reboot**, and the overrides are
retired. Order mattered: the booted image (`44.20260907.319`) predates PR #77,
so retiring them first would have downgraded Mo PC Remote to a build without the
input fix.

What was verified before staging, not after: `cosign verify` against
`cosign.pub` for that exact digest; the ARM boot proof for the same digest
(`workflow_run_id` 34187655686, `first_boot: healthy`, `second_boot: healthy`,
`poweroff: clean`, `graphical=active`, `display_manager=active`,
`failed_units=0` on both boots); and after `bootc switch
--enforce-container-sigpolicy --retain`, that the staged origin string is
character-for-character the signed digest asked for. The booted deployment and
one older one are retained, and `/boot` is unchanged at 48% with three
deployments.

Retired (backed up to `~/.moos-override-backup-20260908/`): the three Mo AI
drop-ins, `moai-hermes.service`, both Mo PC Remote agent redirects, the `$HOME`
`mo-remote-watchdog` pair, the now-shipped kwin memory guard, a
`.conf.before-xwayland` leftover, and `moos-oracle-verify.service`. Kept on
purpose: `20-stability.conf`, the ARM virtual-output drop-in and
`moos-web-studio.service` — owner tuning that shadows no image code.

One self-inflicted fault, found and cleared: removing the `$HOME` watchdog files
while its timer was running left `mo-remote-watchdog.timer` failed with
"Unit to trigger vanished" (`Result: resources`). Stop the unit before deleting
its files. Cleared with `reset-failed`; no failed system or user units remain.

The machine went from **51 passed / 3 failed** to **54 passed / 1 failed** on
`tests/post-update-check.sh`. The single remaining failure is the wallpaper
drift documented below, which is not claimed fixed.

**NOT DONE: the reboot.** The owner reboots. Nothing here has booted the new
deployment, so nothing in this file may be read as post-reboot verification.

**NVIDIA boot-path gates (2026-09-08):**
`test_x86_nvidia_is_deliberately_untouched` searched `build.sh` for heredocs
delimited `DRACUT`; the only x86 dracut config is delimited `DRC`, so it
inspected **zero blocks and could not fail**. Its stated contract was also false
— x86 deliberately omits nouveau/amdgpu/radeon/i915/xe/nvidiafb, which is what
took the NVIDIA initramfs from ~368 MB (GRUB could not allocate it) to ~242 MB.
It now asserts the contract that matters: `nvidia` and `nvidia_drm` must never
be omitted. The x86 initramfs also had **no size ceiling** despite that
documented GRUB failure; `build.sh` now measures the artifact dracut wrote and
fails above 300 MiB, as ARM has since 2026-09-06.

**Mo PC Remote had no recovery path in any image (2026-09-08):** after five
failures in 300 s it stays dead for the session. On moos-cloud and the ARM host
Remote IS the screen. A watchdog had lived only in one machine's `$HOME` since
2026-08-30 — and it restarted Remote unconditionally, overriding the
`systemctl --user stop` that `moos-selfcheck` documents as the off switch. The
shipped version acts only on the `failed` state and is enabled on all four
editions.

**Every `moos://` link on the A1 was dead, under a green check (2026-09-08).**
`~/.local/share/applications/org.moos.urlhandler.desktop` carried
`Exec=/var/home/moos/moos-desktop-edit/system_files/usr/bin/moos-open` — a path
inside a working copy that had since been deleted. `~/.local/share` outranks
`/usr/share`, so that entry was the one the desktop ran, and Mo Store install
links, Settings routes and Mo AI's app links all went nowhere.

`moos-selfcheck` printed *"moos:// links route to MoOS"* throughout, because it
compared the NAME `xdg-mime` returned and never resolved which FILE that name
won, nor whether that file's `Exec` program existed. The check now resolves the
entry by XDG precedence, takes argv[0] of `Exec=` with the field codes dropped,
and requires it to be executable — and separately reports a handler that wins
from the user's data home even when it works, because it freezes the image's
copy. Gated by `tests/test_selfcheck_url_handler.py`.

**FIXED ON THE MACHINE.** The stale entry was removed (backed up to
`~/.moos-override-backup-20260908/`); `xdg-mime` now resolves to
`/usr/share/applications/org.moos.urlhandler.desktop` → `/usr/bin/moos-open`,
which exists and is executable. This was the one live repair made before the
image update, because it needed no new image.

**Signature chain verified from the A1 (2026-09-08).** The problem was never
signing. `/etc/pki/containers/moos.pub` is byte-identical to the repo's
`cosign.pub` (sha256 3ed7f81e…), `/etc/containers/policy.json` rejects by
default and requires `sigstoreSigned` for `ghcr.io/moalfarras-sys`, and
`cosign verify --key cosign.pub` passes for `moos`, `moos-nvidia`, `moos-cloud`
and `moos-arm` at `:latest`, and for BOTH deployment digests on this machine
(booted `32283e41`, rollback `bf247bdc`). Both origins are
`ostree-image-signed:`, and `moos-verify-origin` reports the origin already
enforces the policy. What is broken is promotion, not trust.

**Observed, cause NOT established: the desktop wallpaper drifted mid-session
(2026-09-08, A1).** At the start of the session `moos-selfcheck` reported
*"all 1 desktop wallpaper(s) match: MoOSUI2Arena"*. Roughly an hour later the
same check reported *"only 0/1 desktop wallpaper(s) match MoOSUI2Arena"*, with
`[Containments][24][Wallpaper][org.moos.ui2.wallpaper][General] Image=` reading
`MoOSUI2Graphite` while the family stayed `org.moos.ui2.gaming` / Arena. The
`[Containments][24][General]` key still read Arena; it is the plugin-specific
section, the one that wins, that had moved.

Timeline: `moos-theme-drift.timer` fires `moos-theme-sync.service`
(`moos-theme reconcile-service`) every 30 minutes — it ran 00:55:38–00:55:51 —
and `plasma-org.kde.plasma.desktop-appletsrc` was rewritten at 00:58:54, three
minutes AFTER that reconcile. Running `moos-theme reconcile` by hand restored
Arena in both the file and the live plasmashell (read back over
`org.kde.PlasmaShell.evaluateScript`, not from the file), and selfcheck went
green again.

It RECURS. Watched from 01:31: Arena at 01:31, Graphite again by 01:43:52, and
Graphite again by ~02:00 — three independent observations, each repaired by
`moos-theme reconcile`. So this is a live loop, not a one-off, and the 30-minute
drift timer is currently the only thing holding the desktop to its own theme.

RULED OUT BY TEST, not by reading: `moos-visual-tier`. It was the only caller of
`kscreen-doctor`, which appeared in the journal at 01:43:56, seconds from the
flip, and it drives `moos-theme motion`, which writes `MotionMode`/
`AmbientMotion` into the SAME config group as `Image=` — and whose
`restore_desktop_scene()` does write `Image` back from a snapshot. That made it
the obvious suspect. Running `moos-visual-tier --apply` directly, immediately
after a reconcile had restored Arena, reported "0 setting(s) changed" and left
the wallpaper on Arena. It is not the writer, at least not when its profile is
already satisfied.

Also excluded by inspection: the wallpaper plugin's own config default.
`/usr/share/plasma/wallpapers/org.moos.ui2.wallpaper/contents/config/main.xml`
declares `<entry name="Image"><default></default>`, i.e. empty — so a config
reload writing the declared default back cannot be the source of a Graphite
value.

And MoOS's own intent is correct throughout:
`~/.local/state/moos/theme/theme-state.json` reads `"active":
"org.moos.ui2.gaming"`, `"wallpaperMode": "profile"`, `"wallpaperEncoded":
"%2Fusr%2Fshare%2Fwallpapers%2FMoOSUI2Arena"`. Whatever writes Graphite is not
reading MoOS's recorded intent. (Noted in passing: a stale
`~/.local/state/moos/theme/transaction.1Ced2U/` directory has been sitting there
since 2026-09-06 04:13 — an abandoned theme transaction, not yet shown to be
related.)

What this does NOT establish is the cause. Nothing in this session wrote Plasma
configuration, and the installed `moos-theme` and `moos-apply-theme` are
byte-identical to the repo copies, so it is not a stale image. The shape — a
reconcile writing the correct value and the file carrying the wrong one minutes
later — is consistent with plasmashell flushing its own in-memory copy over a
config written behind its back, but that has NOT been proven and must not be
recorded as fixed. The 30-minute reconcile timer is the existing mitigation and
it did repair it. `moos-theme wallpaper-*` and the two wallpaper gates
(`test_theme_wallpaper_readback.py`, `test_theme_wallpaper_steady_state.py`)
are where a real fix would go once the writer is identified.

**Open, not explained: `efi.automount` fails on every installed x86 system.**
The ISO proof's serial console from run 34164335024 shows
`[FAILED] Failed to set up automount efi.automount - EFI System Partition
Automount` on the freshly installed disk, while `installed-first-boot.txt` from
the same run reports `failed-units=0`. Those two cannot both be right, so one of
them is wrong and it is not yet known which. The A1 has no such unit and no ESP
line in `/etc/fstab` (only `/boot` and the swapfile), and `moos-install-to-disk`
mounts the ESP at `/boot/efi` — a unit named `efi.automount` is `/efi`, so a
generator, most likely systemd's GPT auto-generator, is creating it. This is NOT
fixed: nothing here should touch x86 EFI mounting from an aarch64 machine with
no x86 host to test on. The ISO gate's restored diagnostics now collect failed
system units, so the next ISO run should say which of the two readings is true.

**NVIDIA hardware remains unverified.** No session may claim otherwise from
Oracle or from a green build; see
[`docs/NVIDIA_HARDWARE_ACCEPTANCE.md`](docs/NVIDIA_HARDWARE_ACCEPTANCE.md),
which is unrun.
**Boot visual continuity source pass (2026-09-08):** the physical NVIDIA host's
last boot measured 44.377 s end to end: 10.329 s firmware + 5.932 s loader +
6.073 s kernel + 4.151 s initrd + 17.890 s userspace. Plymouth started at
kernel-monotonic 8.815 s and quit at 21.171 s; the login compositor selected its
DRM backend at 24.855 s. The existing `plymouth quit --retain-splash` therefore
covers a measured ~3.7 s handoff that would otherwise be black. The remaining
visual defect was the surface itself: the rendered logo sting played on a flat,
almost-black canvas, then the login manager replaced the whole frame with its
Graphite glass landscape.

Source now plays the existing 32-frame energy/mark animation over
`boot-backdrop.png`, a deterministic 1920x1080 downsample of the **exact**
Graphite-dark wallpaper already configured for Plasma Login Manager. The
backdrop is 864 KiB encoded, is scaled once outside Plymouth's refresh loop,
contains zero pure-black pixels, and stays visible in the retained handoff; the
login frame therefore replaces the mark/authentication layer without replacing
the ground. The preview now renders the complete slow-boot cue after 2.4 s and
the explicit quit frame, not only the 1.28 s intro. The reviewed 16:9 and 4:3
storyboards are `artwork/generated/boot-animation-filmstrip.png` and the
temporary scale preview; horizontal scans on the 1080p settled frame measured
127–231 luminance steps across the glass/brand rows (design floor: 15).

Repo gates cover exact backdrop provenance, 4 MiB encoded ceiling, cover
geometry, one-time scaling, missing assets, BOM/parser safety, and final-initrd
presence in x86, ARM and recovery build paths. `just check` passed all 123
workflow gates, and a clean local `just build` produced
`localhost/moos:latest` with `bootc container lint` passing. Independent
built-image inspection found the exact source SHA-256
`bdb3b79845eac51265bd850ca2cb0762c1c253a5ed6a8a7885d6a4dc888d9931`
in the image and its 107 MiB final initramfs, with `Theme=moos` and the
`--retain-splash` override active. This is **built-image proof**, not a visible
boot proof: a UEFI VM/hardware capture remains required before merge or release,
and firmware-controlled pixels before Plymouth remain outside the OS renderer.

**Current bounded x86 repair (2026-09-07):** run 769 fails all three editions
because `55737753` applies ARM's real-directory `/usr/local/sbin` repair to
Atomic's dangling `/usr/local -> ../var/usrlocal` link. Candidate work on
`gpt/fix-x86-build-20260907` preserves that writable layout and gates the two
existing boot-time tmpfiles rules. ARM's NFS and sbin fixes remain unchanged.
Validation and exact build evidence: [Opus handoff](docs/MOOS_X86_SYSTEM_PLAN.md).
This branch is not merged or deployed; candidate builds do not promote releases.

**Live NVIDIA update-path audit (2026-09-07):** the physical PC is booted from
local `containers-storage` image `44.20260829.1`, with one local 44.20260828
rollback. `moos-image-update` correctly refuses that unverified origin, so
`moai-do update` cannot advance it. The boot-time `moos-verify-origin` audit,
however, falsely logged that this same local origin enforced signatures because
its default case treated every reference other than `ostree-unverified-registry`
as signed. The parser now positively recognizes only the exact official signed
repositories, repairs only an exact official unverified-registry reference, and
reports local/foreign origins without replacing them. Rejoining the release
train remains an explicit signed NVIDIA edition switch after a newer candidate
passes artifact boot gates and is promoted. The one update backend now compares
validated MoOS release labels as well as digests and refuses an older or equal
production `latest`, both during resolution and again after privilege escalation.
The installed and repository public keys match, and the current signed candidate
verifies with that key.

**Current Mo AI integration:** read `PROJECT_STATE.md` and
`docs/MOAI_CLOUD_ONLY_PLAN.md`. Latest owner policy is cloud-only, free default
and explicitly selected paid models allowed. Hermes has a real isolated adapter
and live free-cloud response proof; current changes are not yet a signed release.
Older local/hybrid descriptions below are historical and must not re-enable engines.


This file is current state, not session history. Git history owns the history.
When documentation disagrees with a running machine, a freshly booted artifact,
or current source, those stronger forms of evidence win.

Last reconciled: **2026-09-06 (resumed audit)**. Current source and live
findings: [`PROJECT_STATE.md`](PROJECT_STATE.md).
Signed release and post-reboot verification are tracked there separately.

### Customize Desktop — MoOS owns the widget explorer (2026-09-07)

MoOS now ships its own Plasma shell surface for desktop widgets, reachable from
Settings → Appearance → "Customize Desktop" (`moos://settings/desktop`) and from
Plasma's own "Add or Manage Widgets". Two files overlay plasma-workspace's shell
package via `COPY system_files/ /`:

| Overlay | What it replaces |
| --- | --- |
| `.../contents/explorer/WidgetExplorer.qml` | the stock widget explorer, restyled on UI2 (`MoUI.Card`/`Surface`/`Button`), bilingual, RTL-mirrored |
| `.../contents/views/DesktopEditMode.qml` | Arrange, made to render without a GPU |

**Plasma stays the owner.** The catalog, the applet list, add/remove/configure
and all persistence are the native `Shell.WidgetExplorer` and each applet's own
`internalAction()`. The overlay writes no config of its own — it must never
become a second source of truth for `plasma-org.kde.plasma.desktop-appletsrc`,
which is what decides whether the user's desktop survives a reboot.

**Arrange was black on this machine, and that is now fixed.** Upstream's edit
mode blurs the containment through two `MultiEffect` blocks. `MultiEffect` is a
shader effect: on the Qt Quick **software** backend it draws nothing at all. That
backend is exactly what `moos-arm` (the Oracle A1) and `moos-cloud` run — no GPU
— so Arrange painted an opaque black rectangle over the desktop and the widgets
being arranged were invisible. It read as a crashed shell. The overlay hides both
effects on the software backend and lifts the real, interactive containment above
the backdrop instead, so the user arranges the actual desktop. GPU sessions are
untouched and keep the blur (`restoreMode: Binding.RestoreBindingOrValue`).

**Removal is confirmed and scoped.** "Remove" and "Reset desktop widgets…" act
only on applets in the *current* containment — never Plasma's global
`removeAllInstances()` — behind a confirmation popup, and the count is snapshotted
so cancelling removes nothing. Undo is Plasma's own desktop notification.

**Live previews never touch the desktop.** "Live preview in a window" routes
through `moos://desktop/preview/<id>` to `moos-desktop-edit --preview`, which
validates the id against `^[A-Za-z0-9_-]+(\.[A-Za-z0-9_-]+)+$`, confirms the
package is installed with `kpackagetool6`, and `exec`s `plasmawindowed`. URL text
never becomes argv, and the preview is not added to any containment.

Verified live on the A1 in an Arabic session by driving the real shell overlay
(`tests/qml/desktop-live-driver.qml`): a real `systemmonitor.memory` widget was
added, moved, rendered with live data, and survived a `plasmashell` restart at
the same geometry; a deliberately broken applet showed its error state instead of
a blank tile; removal took the confirmation path. Screenshots and the applet
geometry before/after the restart are in
[`docs/evidence/desktop-edit-20260907/`](docs/evidence/desktop-edit-20260907/) —
compare `manage-ar.png` (black containment, pre-fix) with
`software-edit-fixed.png` (the desktop drawn under Arrange).

**Gates.** `tests/test_desktop_customize.py` covers the containment scoping, the
confirmation/undo contract, the preview argv boundary, the fixed router routes,
and the software-rendering guard. Because both QML files are verbatim overlays of
upstream shell files, **both** build scripts — `build.sh` (x86) and
`build-arm.sh` (aarch64) — additionally assert on the **finished image** that
each one is present *and still carries its MoOS marker*; a later rpm transaction
reinstalling plasma-workspace would otherwise restore stock Plasma at those exact
paths with every repo gate still green. ARM is a separate ~1200-line script, so a
repo gate also proves neither script lost the check — and ARM is the edition that
needs it most, since it forces Qt Quick's software renderer. If an upstream
re-sync makes that gate fire, re-apply the guard; do not weaken the gate.

### A live test rig was shadowing the whole Plasma shell (2026-09-07, removed)

Found on the A1 while verifying the Customize Desktop work, by the new
post-update check — not by looking for it. `~/.local/share/plasma/shells/
org.kde.plasma.desktop` held a **complete copy of the Plasma shell package**,
left behind by the session that developed the overlay. A user-level shell
package outranks `/usr` entirely, so:

- every shell QML the image ships was being ignored on this machine;
- the copy's `WidgetExplorer.qml` had a `Timer` appended that loaded
  `file:///var/home/moos/moos-desktop-edit/tests/qml/desktop-live-driver.qml`
  — an absolute path into a scratch worktree — and that driver polls a command
  file every 700 ms for as long as the explorer is open;
- it was the reason the live tests passed. They exercised `$HOME`, not the image.

Left in place it would have been the worst kind of green check: the update
would land, `/usr` would hold the right bytes, and the desktop would keep
running the old scaffolding — including a dangling path once the worktree was
cleaned. This is the shadowed-config trap `tests/post-update-check.sh` was
written for, in its purest form.

Removed, after backing it up to `/var/home/moos/astra-live-testrig-backup-20260907.tar.gz`
(80 files) in case any of it is wanted again. `~/.local/state/moos-desktop-review/`
(the driver's command file and an appletsrc snapshot) went with it.

`tests/post-update-check.sh` now fails if any shell package exists in `$HOME`,
and separately checks that the two overlay files on disk are the MoOS copies
rather than stock Plasma. **Never develop a shell overlay by copying the package
into `$HOME` and leaving it there** — bind-mount it, or build and deploy the
image, so what you verify is what ships.

### moos-nvidia could not build: a multilib mesa file conflict (2026-09-07, fixed)

The first `main` build after the desktop merge failed for two x86 editions, and
neither cause was in the merged tree:

- **`moos`** — `reading blob ...: connection reset by peer` while buildah pulled
  the base image, after three retries. A GHCR transport flake; re-running fixed
  it. Recorded so the next reader does not hunt for a code cause.
- **`moos-nvidia`** — real and reproducible. `MULTILIB=1` makes ublue's
  `nvidia-install.sh` add the 32-bit NVIDIA/GL stack, which pulls **i686 mesa**
  as a dependency. mesa ships **arch-independent** files from *both* arches
  (`/usr/share/drirc.d/00-mesa-defaults.conf`, `00-radv-defaults.conf`, licence
  texts), so the two arches must be the same version or rpm aborts the whole
  transaction on a file conflict. The pinned `kinoite-main:44` base lagged
  Fedora's repository: i686 `26.1.8-1.fc44` against x86_64 `26.1.4-4.fc44`.

Only `moos-nvidia` is affected — the generic and cloud editions never enable
multilib, which is exactly why the failure looked edition-specific rather than
environmental.

Fix: `dnf5 -y upgrade 'mesa*'` immediately **before** `nvidia-install.sh`, so
both arches agree before the 32-bit packages arrive.

**The first attempt at this fix did nothing, and that is the lesson.** It named
`mesa-dri-drivers` and `mesa-vulkan-drivers` in the later `wine` install list, on
the assumption that wine pulled the i686 stack and that naming an installed
package upgrades it. Both were wrong: wine was never the source (`moos` installs
wine and pulls no i686 mesa at all), and **`dnf5 install` on an already-installed
package answers "already installed" and changes nothing** — it does not upgrade.
The build failed again, identically. The gate therefore asserts the `upgrade`
verb *and the ordering* relative to `nvidia-install.sh`, not merely that the
package names appear somewhere in the file.

Not verified locally: this session's host is aarch64, so only CI can run the x86
multilib transaction.

### `just check` did not run every gate CI runs (2026-09-07, fixed)

The repository has two build workflows with two independent gate lists, and
`just check` — the command `AGENTS.md` and the engineering skill tell every
contributor and agent to run before pushing — covered only part of the union.

Missing from it: `test_moos_arm.py` and `test_arm_initramfs_size.py` (ARM
workflow only), `test_moai_free_policy.py` and `test_moai_hermes.py` (both build
workflows), `test_release_partition_roles.py` (disk workflow) and
`test_iso_install_gate.py` (ISO workflow). **All six passed and always had** —
nothing was broken. They were simply unrunnable from the one command people are
told to use, so no local run could ever exercise them.

The cost was immediate and concrete. A change to the ARM update-authority wiring
passed `just check`, passed the x86 repo gates, was pushed to main, and failed
the ARM build on `test_moos_arm.py` — a gate that could not have been run locally
without reading workflow YAML by hand. The real damage is not a red build: it is
that "I ran the gates" stops meaning anything, and this repo already documents
several defects that shipped while every gate anyone actually ran was green.

Fixed by wiring all six into the `check` recipe, and by adding
[`tests/test_gate_coverage.py`](tests/test_gate_coverage.py), which asserts that
the union of every workflow's gate list is a subset of what `just check` runs.
`just check` may run more — it deliberately does — but never less. It also fails
on a gate path that does not exist on disk, since a typo'd path is a gate that
silently never runs. Both failure modes are proven. The gate itself runs in both
build workflows, so the two lists cannot drift apart again.

### Branch and worktree state, audited and tidied (2026-09-07)

`feat/desktop-customize-20260907` merged as PR 76 and was deleted on both sides;
its second worktree at `/var/home/moos/moos-desktop-edit` was removed. The
repository now has exactly one working tree and two branches: `main`, and
`archive/arm-utm-20260827`.

**The archive was audited rather than assumed.** It carries 18 commits that never
merged, and three documents described it as unmerged work pending disposition —
which reads like a debt. It is not. Every file it touches exists in main; it
contains no test function main lacks; and its three `build-arm.sh` gates are all
present in main under clearer names. main is strictly *ahead* of it: the archive's
`moos-arm-greeter-kwin` `exec`s KWin even when no usable DRM node was found, and
main fixed exactly that by requiring the node be readable and writable first.

It is kept for provenance, and the docs now say it is superseded instead of
implying something is owed from it. Cherry-picking from it would be a regression.

### Post-update boot journal: two real errors, both fixed (2026-09-07)

The 305 -> 315 update landed and the desktop work is live and verified on the
running A1 (see below). The boot journal was not clean, though, and the same
errors were present on the three previous boots — pre-existing, not caused by
the update.

**NFS client machinery was starting inside the initramfs.** With `hostonly="no"`,
dracut pulls in its `74nfs` module merely because `nfs-utils` is installed, and
that module's pre-udev hook (`99-nfs-start-rpc.sh`) starts `rpcbind` and
`rpc.statd` in the initrd on every boot. Neither can work there: `/run/rpcbind`
does not exist yet and `/var/lib/nfs/statd/sm` is absent because bootc images may
not ship content under `/var`. Six hard errors per boot, on a machine with no NFS
mount at all — and `rpcbind` plus its hook riding in an initramfs this edition
treats as a size contract.

`build.sh` has omitted this module for the x86 editions since the same symptom
was found there; its comment describes this exact failure. **ARM was simply never
given the same treatment.** Now omitted in `build-arm.sh` too, and gated. Omitting
the *initrd* module does not remove NFS client support from the running system —
mounting a NAS after boot is unaffected.

**`/usr/local/sbin` did not exist.** `rpm-ostree-0-integration.conf` asks for the
eight classic `/usr/local` subdirectories; the base ships seven. On bootc `/usr`
is read-only at runtime, so `systemd-tmpfiles` failed to create it and logged an
error every boot. Created at build time in both scripts, and gated.

**Not defects:** the repeated `sshd: kex_exchange_identification: Connection reset
by peer` lines are internet background scanning against a public Oracle IP. sshd
is correctly hardened — `permitrootlogin no`, `passwordauthentication no`,
pubkey only — so these are refused connections, not failures to fix.

**Also cleaned:** `moos-post-reboot-verify.service`, the one-shot unit used to
capture proof across the reboot, failed its `ExecStartPost` because it ran as
`User=moos` and could not disable a system unit. Its verification had already run
and passed; the unit was removed. And the deliberately broken QA plasmoid left on
the desktop by the earlier session (`org.moos.test.broken`, applet 43) was
removed through Plasma's own applet action, then its package deleted — its error
popup was the visible defect on the owner's screen.

### Oracle stability/performance pass — the budget had no consumer (2026-09-07)

Branch `oracle/stability-performance-20260907`, ARM only. The PC agent's
`gpt/fix-x86-build-20260907` was left untouched and unmerged.

**The measured win: Baloo was ignoring the machine's own budget.**
`moos-visual-tier` has published `budget.file_indexing` since the adaptive work
landed, and its docstring delegates application to each consumer's own owner.
No such owner existed. So a 2-core, GPU-less A1 ran full content extraction
against its own advice. Measured on the live machine, signed image
44.20260907.315, tier `essential`:

| | before | after |
| --- | --- | --- |
| `baloo_file` RSS | 439.3 MiB | **36.1 MiB** |
| index database | 2.8 GB | **108 MB** |
| indexer state | indexing file content | idle |
| files indexed | 12,460 | 12,468 |

403 MiB of RAM and 2.7 GB of disk, on the largest MoOS-owned process on the box.
Nothing was disabled: the FILENAME index the Launcher's file results and the
Places page's search promise depend on is intact. Content EXTRACTION is the
sustained cost, and it is all that stopped.

`moos-index-policy` is that consumer, under Baloo's own owner. It owns no
thresholds — a gate asserts it references no core count, memory figure or GPU
class — and does nothing at all if the authority cannot be asked. Live testing
found a real flaw in the first version: `balooctl6 purge` blocked past 300 s,
unacceptable in a unit bound to the graphical session. It now stops the indexer,
deletes the derived database and restarts, letting the filename index rebuild in
the background at idle IO priority.

**`budget.ai_default` was advertising a route the OS removed.** It returned
"local" on a flagship machine, from sound reasoning about RAM and GPU — but
stage C2b retired the local engine, `moai-config` has no local mode, and
`test_moai_cloud_only.py` asserts "the one door to a local engine is closed".
Nothing consumed the key, which is the only reason it never surfaced. Now
constant, and gated against the hardware branch returning.

**Not wired, and deliberately.** `remote_encode` would cap what the host offers,
but `test_remote_resolution_ceiling.py` records that 1920 was removed as a
measured, reasoned decision with a client compatibility rule; Remote costs
106.8 MiB here and is not a measured problem, so it was left alone.
`update_concurrency` has no consumer to wire — `moos-image-update` exposes no
concurrency knob. Both keys stay published and unconsumed rather than being
forced.

**S03 remains open, honestly.** KWin is healthy: 272 MiB RSS after five hours,
cgroup 302 MiB against the 3 GiB guard, zero OOM kills across three boots. The
6.53 GiB balloon does not reproduce, and reproducing it deliberately means
OOM-ing the owner's only screen. No cause is claimed.

**The journal's 727 errors are not defects.** 93 are SSH scans against a public
Oracle IP, refused by a correctly hardened sshd. The rest are 26
`qwebengine_convert_dict` coredumps from a local `podman build`, which that
converter's own comment predicts. Filtering both leaves zero runtime errors.

### Live /etc had drifted from its signed image (2026-09-07, repaired)

Four stale overrides on the A1, each one a file `/etc` had taken ownership of, so
image updates could no longer reach it. All backed up to
`/var/home/moos/etc-drift-backup-20260907/` before removal.

- `containers/policy.json` — missing the `containers-storage` block the image
  ships. OS update signing was never affected: the origin is
  `ostree-image-signed:` and `ghcr.io/moalfarras-sys` requires `sigstoreSigned`
  against `/etc/pki/containers/moos.pub`.
- `udev/rules.d/61-moos-arm-vgem.rules` — **one line where the image ships
  eight**, missing the greeter's DRM ownership rules entirely.
- `xdg/kdeglobals` — a comment-only delta, but enough to freeze the file.
- `modules-load.d/moos-cloud-vgem.conf` + `61-moos-cloud-vgem.rules` — hand-placed
  2026-08-30, duplicating what the ARM edition now ships properly.

**And a privileged one.** `moos-post-reboot-check.service` was enabled and active,
a SYSTEM unit — root, no `User=` — whose `ExecStart` was
`/var/home/moos/.local/state/moos/post-reboot-check.sh`, owned by and writable by
the unprivileged desktop user. Anything running as `moos` could rewrite it and be
root at the next boot. It was one-off scaffolding for an Arabic-font fix in image
44.20260830.203, referenced a repo path that no longer exists, and had run at
every boot for eight days. Removed, and
[`tests/test_no_privileged_user_writable_units.py`](tests/test_no_privileged_user_writable_units.py)
now fails any shipped root unit that executes from a user-writable path — proven
against this exact unit.

### Settings product pass — integration branch (2026-09-07)

`fix/settings-real-state-20260907` fixes Settings status truth, missing-backend
handling, live row summaries, search and double-mirrored Arabic alignment. It
retains the shared UI2 components and graphical KDE backends. Native English/
Arabic source frames and failure fixtures are reviewed; no OS build or deployment.
See [the bounded handoff](docs/MOOS_SYSTEM_DEVELOPMENT_PLAN.md) for tests and limits.

### x86 was blocked behind the retired local-brain unit (2026-09-07, FIXED)

Fixing the truncated `sed` let the x86 build run far enough to expose the next
defect, which had been hidden behind it:

    + systemd-analyze verify ... /usr/lib/systemd/user/moai.service ...
    moai.service: Command /usr/bin/ramalama is not executable
    Error: buildah exited with code 1

`moai.service` is the RamaLama local-brain unit. Mo AI is cloud-only and
`/usr/bin/ramalama` was removed with the engine, so the unit ships naming a
binary that does not exist. It is masked at runtime and never `--global`
enabled, so nothing starts it -- but `systemd-analyze verify` is right, and it
fails the whole build.

**Three things were tried and rejected, deliberately:**

* Removing the unit. Three gates model its port and lifecycle contracts
  (`test_moai_ports_fail_closed`, `test_moai_service_lifecycle`,
  `verify_user_experience`), and one of them is a fail-closed *security*
  contract. Deleting the unit breaks all three at once.
* Excluding it from the verify list, the way `openclaw-gateway.service` is
  excluded for the same reason. `verify_user_experience` explicitly requires
  "the image build must systemd-verify Mo AI runtime unit moai.service", so the
  repo already forbids exactly that shortcut. The gate is correct.
* Pointing ExecStart at a shim. That invents a binary to satisfy a verifier for
  a feature that no longer exists.

**Fixed by doing the C2b cleanup properly**: the unit and the four gates that
modelled it were retired together, because removing the unit alone breaks all
four at once. None was weakened. The fail-closed ports gate checked six units
carry `ConditionUser=!@system`; "moai" is simply no longer one of them, and a
unit that does not exist cannot start for a system user at all. The lifecycle
gate's restart-limit checks went with the brain. The 8081 port-collision
assertion went with the second port that no longer exists, while the gateway's
own port-derivation check stayed. `verify_identity` now requires the three
services Mo AI actually has, and both it and `verify_user_experience` assert the
unit does NOT come back -- stronger than before, and bite-tested by restoring it.

The gateway's `RAMALAMA_UNIT` default was left alone deliberately:
`ensure_local()` refuses unconditionally before anything reads it, so it can
never resolve to the absent unit, and rewriting that allowlist is a separate
change with its own risk.

Result: all three x86 editions build, push and sign again, each signature
verified against `/etc/pki/containers/moos.pub`.

### main could not build any x86 edition (2026-09-07, fixed)

`moos`, `moos-nvidia` and `moos-cloud` all died identically on `sed: no input
files`, exit 4. The icon-theme `sed` carried its explanatory comment BETWEEN its
`-e` arguments; bash joins a backslash continuation into one logical line, so
the `#` commented out the remainder -- three expressions and the target file.
The same truncation meant the `Inherits=` fix that comment describes never
applied, so one defect hid a second.

`bash -n` PASSES on the broken form, which is why the CI syntax check never
caught it. `tests/test_shell_line_continuations.py` checks the structure and
distinguishes a documentation comment block whose lines end in `\` (harmless)
from a comment inside a continuation opened by code (fatal).

### The Device page described hardware that does not exist (2026-09-07, fixed)

It told the owner of this Oracle A1 that their processor was a "MoOS device",
and showed no GPU at all. aarch64 publishes no `model name` and no `Hardware`
line in `/proc/cpuinfo` -- only numeric implementer/part registers -- so the
x86-only scan fell through to a branded placeholder on EVERY ARM machine.

    before   cpu: "MoOS device"
    after    cpu: "Neoverse-N1"          (lscpu ground truth: Neoverse-N1)
             gpu: "virtio-pci (virtual)"

GPU comes from `moos-visual-tier`, the prober that already drives compositor
policy, rather than a second one that could disagree with it. An unidentified
part now renders "Unknown"; a placeholder shaped like a product name is worse
than an empty field.

### Bubblewrap reached the image only by inheritance (2026-09-07, fixed)

Mo AI runs model-proposed commands only inside bubblewrap and REFUSES when
`/usr/bin/bwrap` is absent. That refusal is correct, which is exactly what made
the gap dangerous: nothing in MoOS asked for the package, so an upstream change
could have removed a security boundary with no gate firing and no crash --
`run_command` would simply have stopped working. Both build paths now install it
by name and `verify_arm_image.py` asserts the binary is in the finished image.

### Wallpaper drift now repairs itself (2026-09-07, closed)

`moos-selfcheck` reported the desktop wallpaper as broken and it was right, but
not for the reason it looked like. Every other theme surface was Arena --
LookAndFeelPackage, decoration, colour scheme, icons, Plasma style -- while the
desktop alone still showed MoOSUI2Graphite, and `theme-state.json` recorded
`status: committed`, `wallpaperMode: profile`, `wallpaperEncoded: …/MoOSUI2Arena`.
Recorded intent and real state disagreed.

The timeline rules out a failed transaction: the machine booted 13:57:11,
plasmashell started 13:57:37 and never restarted, the theme committed 13:57:50,
and `plasma-org.kde.plasma.desktop-appletsrc` was last modified at **21:31:34**
-- almost eight hours later, during an agent session. So the wallpaper drifted
away from a committed profile after the fact.

**Two mechanisms should have caught it and neither can.** `moos-apply-theme` is
marker-gated on THEME_REV, which is 53 in both the running image and the current
tree, so it will not re-run on the next login or even after the update.
`moos-theme-sync.path` watches `%h/.config/kdeglobals`, so a wallpaper-only
drift -- which touches the containment config, not kdeglobals -- fires nothing.
The result is a state selfcheck correctly calls broken and nothing repairs.

**Closed.** It recurred across a reboot, which settled that it was not a
one-off. `moos-theme reconcile` already repairs the state correctly (verified
Graphite -> Arena, selfcheck 1 broken -> 0 broken); only the trigger was
missing, so `moos-theme-drift.timer` now runs that same idempotent service on a
30-minute schedule. There is still exactly one repair path.

Watching the containment file directly stays rejected -- plasmashell rewrites it
on every applet move -- and `tests/test_theme_drift_repair.py` refuses that
regression along with an aggressive period and a missing `[Install]` section.

A guard that would have preserved a live custom wallpaper the recorded state
never learned about was written and then REVERTED: a round-trip on the real
desktop showed `plasma-apply-wallpaperimage` switches the wallpaper plugin away
from `org.moos.ui2.wallpaper`, so the classifier returns empty and the guard
never fires. MoOS owns that plugin by design and a genuine custom image goes
through `moos-theme`, which records `mode=custom` and is already honoured.

### The live A1 is running an unverified origin (2026-09-07)

Measured, not inferred, with `ostree admin status` and the deployments' own
`.origin` files:

      23beed6e…1 (staged)    ostree-image-signed:…/moos-arm@sha256:d2045552…
    * 23beed6e…0 (booted)    ostree-unverified-registry:…/moos-arm@sha256:d2045552…
      1cba09f5…0 (rollback)  ostree-image-signed:…/moos-arm@sha256:049a620d…

The booted deployment and the staged one are the **same digest**; they differ
only in whether the origin records signature verification. So the pending update
is a signed re-pin of the content already running, and rebooting moves this
machine from an unverified origin onto a verified one. That is also why the
Updater showed 44.20260906.284 as both current and pending -- it was not a
display bug.

How it got there is not established. `bootc install to-disk` writing an
unverified origin, or a local image import during bring-up, both fit; neither is
proven, so do not repeat either explanation as fact. What is proven is the state
above and that the rollback deployment is signed.

**While it stays unverified, this machine cannot update at all.**
`/usr/libexec/moos-image-update resolve` reads the *booted* origin, requires it
to match the signed-official pattern, and otherwise raises a security error:

    moos-image-update: the booted deployment is not a signed official MoOS origin

That backend is the single authority behind `moai-do update`, the Updater's
check/install buttons and the nightly train, so all three refuse. The refusal is
correct -- MoOS should not pull an update onto a base it cannot vouch for -- but
it inverts the usual release order for this host:

    reboot into the staged signed deployment  ->  update  ->  reboot again

Updating before that first reboot is not merely inadvisable, it is impossible.

**The badge was hiding it.** The Updater's "SIGNED IMAGE · ATOMIC" was a
hardcoded string, so the one surface that tells the owner whether they are
running the system MoOS signed said yes without looking. It now reads the booted
deployment's origin from the kernel command line -- unprivileged, no
bootc/rpm-ostree call -- and reports signed, unverified or unknown, with unknown
deliberately a warning rather than a pass. Gate:
`tests/test_updater_trust_badge.py`.

### Mo Store spoke the backend's language, and branched on its prose (2026-09-07)

An entirely Arabic Mo Store showed the English toast "Rebuilding the unified app
index" above its own Arabic cancel button. The cause was structural: every job
message `moos-storectl` emitted was English prose, and `main.qml` compared that
prose to decide install state, so translating the backend would have silently
broken scope detection and offered a Remove action that cannot work.

The backend now emits a stable `message_key` beside the human `message` and the
UI owns the words. Failures and dynamic Flatpak status deliberately carry no
key so their real text reaches the user verbatim, which means every failure path
must *clear* the key -- a job document keeps fields it was given, and the first
run showed `message: "App index refreshed"` still carrying
`message_key: "refreshing_index"`. Gate: `tests/test_store_job_language.py`,
21 keys checked against 21 phrases in both directions.

### First-party visual pass on the live session (2026-09-07)

Captured and read, not assumed. Mo Store renders its real catalogue (2938 apps,
1936 verified publishers) with correct RTL. Recovery is correct and calm, and
its state matches the deployments exactly. Mo AI is healthy and genuinely
cloud-only -- Online, `Cloud · openrouter/free` -- but its **installed** UI is
English in an Arabic session. That is not a new defect: the tree's Mo AI is
already RTL-aware through `MoUI.Locale.rtl`, and `Locale.qml` simply does not
exist in the running image yet. It ships with the next build; do not "fix" it
again in source.

### S03 — the OOM had one cause, and it was KWin (2026-09-06)

The review left this open as an unexplained cascade with five victims. Summing
the kernel's own OOM process table across all 151 processes settles it:

    total anonymous RSS at the kill   10.66 GiB   (machine has 11.6 GiB)
    kwin_wayland  pid 1792             6.53 GiB   — 63% of the machine, alone
    plasmashell                        724 MiB
    plasma-keyboard                    703 MiB
    kded6                              591 MiB
    xdg-desktop-portal-kde             555 MiB
    kactivitymanagerd                  441 MiB
    claude (this agent, two procs)     216 MiB

It was a `global_oom`. **KWin was not a victim of a cascade, it caused one** —
the later kills of plasmashell, the portal, kded6 and kactivitymanagerd happened
over the following three minutes as they ballooned on a broken Wayland
connection. The earlier reading of "~10.6 GB at kactivitymanagerd's kill" was
its total-vm at a later moment, not its share of the original exhaustion.

**The leak is not continuous.** The replacement compositor has run 6.5 hours at
**168 MiB** and its RSS falls rather than climbs. So there is a trigger, and it
has NOT been identified. Reproducing it means risking another session-wide OOM
on the owner's only screen, so it has not been reproduced and no cause is
claimed.

**Bounded instead of guessed:** `plasma-kwin_wayland.service.d/50-moos-memory-guard.conf`
sets `MemoryHigh=3G` (~18x the healthy 170 MiB) and `ManagedOOMPreference=avoid`.
`MemoryHigh` applies reclaim pressure and does **not** kill — `MemoryMax` would
kill the compositor, which on this machine is turning the monitor off, i.e.
automating the exact disaster. A leak now becomes a slow desktop with a journal
entry instead of a dead session. Live: accepted by systemd, KWin reads
`MemoryCurrent` 142.8 MiB against the 3 GiB limit, and neither KWin nor Remote
was restarted. S03 stays open: this bounds damage, it does not explain the cause.

### Mo AI goes cloud-only, free by default (2026-09-06)

The latest owner decision permits **free or explicitly selected paid cloud
models**, with free as the default on every edition. Mo AI must never download
or run a local model, and a free quota failure must never trigger paid inference.
The current contract is
[`docs/MOAI_CLOUD_ONLY_PLAN.md`](docs/MOAI_CLOUD_ONLY_PLAN.md); read
[`PROJECT_STATE.md`](PROJECT_STATE.md)
for release and deployment evidence.

**Current source:** OpenRouter is the supported provider, with separate Free
and Paid by choice selections. Free requests use `openrouter/free` or an explicit
`:free` model and enforce a zero price ceiling; caller-supplied model/provider
routing and paid plugins cannot override that boundary. Settings owns the cost
choice and the gateway reads it. The earlier four-provider catalogue and planned
cross-provider fallback ladder are superseded. Quotas can stop a free reply;
there is no unlimited-free guarantee. Paid selection is fixture-tested, but no
paid inference was made in this session.

**Local inference is retired at public entry points.** Chat, model pull, setup,
preflight and voice routes cannot start local engines or speech models. Migration
preserves a private config backup, removes local fallback selection and stops/
masks fixed legacy units without deleting existing model weights or unrelated
user files. Both architecture builds omit the local engine packages. Unreachable
legacy helper bodies remain for C2b cleanup; they are not an available local mode.
Finished-image inspection and historic-layout migration acceptance remain open.

**Hermes is integrated with a real installed runtime.** The isolated
`moai-hermes` adapter starts on demand, processes text/history with Hermes 0.21.0,
and sends inference through the same Mo AI cloud policy. A real request through
the production gateway and adapter returned Arabic from free cloud in about
3 seconds; an earlier source-gateway proof took about 5.8 seconds. The separate
direct free-model probe reported cost 0. The adapter uses its own private home
and authenticated loopback endpoint; it does not start the owner's Hermes
messaging gateway or use the owner's `~/.hermes` state. Model tools are empty
and verified empty, outbound connections are restricted to the Mo AI gateway,
and subprocess execution is blocked. System actions stay with `moai-do`.

**Still open:** Hermes is not packaged for fresh installations across all four
editions; a missing runtime is reported and direct cloud remains available.
The adapter supports text/history and a final-answer SSE frame, not incremental
streaming, persistent memory, plugins or model-executed tools. First-login and
upgrade migration, native QML/phone acceptance and bounded-memory checks remain.
The current native build is in progress: neither local runtime proof nor source
tests make these changes a signed OS release.

### Why the desktop looked unchanged — four measured causes (2026-09-06)

The owner reported seeing no difference from several sessions of work. They were
right, and none of it was visible for reasons no file-level gate could see. Full
plan and the ordered remainder: [`docs/MOOS_VISUAL_ROADMAP.md`](docs/MOOS_VISUAL_ROADMAP.md).

- **The desktop had no motion at all.** `AnimationDurationFactor=0` in the
  user's kdeglobals, and `blur/magiclamp/squash/scale/slide/dimscreen/
  dialogparent` all `false`. There was nothing to see.
- **`moos-visual-tier` never told the running session anything.** It called
  `kwriteconfig6` without `--notify`, so KConfig emitted no change signal and the
  whole hardware-matched profile only ever landed at the NEXT login — on every
  machine, since the tool was written. Same trap as the keyboard migration, which
  KWin 6 watches through `KConfigWatcher`. Fixed.
- **The `essential` tier disabled the requested window motion.** The profile
  now retains scale/squash/slide/dimscreen and refuses blur. This is a design
  choice with runtime cost still unmeasured: the ~1% idle sample had the
  effects configured on but not loaded. Slide and dimscreen are not all
  single-window transforms; do not call them free.
- **KDE and GTK windows disagreed about which side the buttons go on.** kwinrc
  `ButtonsOnLeft=XIA` (left) versus GSettings and the xdg portal both answering
  `appmenu:minimize,maximize,close` (right). `moos-theme` already owned both
  halves and simply never wrote the GTK one. Fixed and gated in both directions.

**The reported bug that started it:** VS Code drew *its own* window controls at
the left, on top of its own menu bar, hiding `File` entirely and `Ed` of `Edit`
— measured from a 4× crop of the title strip. Its `window.titleBarStyle` is now
`native`, so KWin's MoOS frame is the title bar and the menu moves below it.

**Honest limits.** KWin decides at session start whether animations load at all;
a session that began with factor 0 loads none, and `loadedEffects` still holds no
animation effect on this machine. The configuration is correct and takes effect
at the next login. KWin was NOT restarted: on this machine the screen *is* Mo PC
Remote, so restarting the compositor is turning the monitor off. A CPU sample of
58% taken during active screen output is not comparable to the 1% idle sample
taken after; no CPU reduction is claimed from these changes.

### Earlier Oracle A1 resource snapshot — /boot pressure (2026-09-06)

Measured on the running `moos-arm-oracle`, not inferred. Healthy: boot 14.3 s
(kernel 0.9 + initrd 3.0 + userspace 10.4, graphical at 8.4 s), **zero failed
units**, 11 GiB RAM with 6.9 GiB available and **0 B swap in use**, journal
capped at 500 M (310 M used), `/var` 35% of 199 G.

**One measured fault: `/boot` was 78% full (974 MiB, 205 MiB free) with only two
deployments at 351 MiB each.** A third needs 351 MiB, so the next signed update
had nowhere to stage — a silent update failure, not a cosmetic one.

Cause, read out of the built archive: the ARM initramfs was **237 MiB**, of which
**137.8 MiB was firmware and 131 MiB of that belonged to discrete desktop GPUs
that cannot exist on an Ampere A1** — `nouveau` declares 559 firmware entries
(`firmware/nvidia`, 101.2 MiB), `amdgpu` 694 (23.4 MiB), `xe` 41
(`firmware/xe`+`i915`, 5.0 MiB), `radeon` 232 (1.4 MiB). GPU firmware is not
needed to reach the root filesystem, which is an initramfs's only job.

Fixed in `build_files/build-arm.sh`'s dracut drop-in with
`omit_drivers+=" nouveau amdgpu radeon xe "`. Safe by construction: dracut
anchors every omit entry as `^name$` (`/usr/bin/dracut:1493`), so a bare `xe`
cannot reach `sdhci-xenon-driver` or the 15 other modules whose names merely
contain "xe" — that anchoring was verified in dracut-108-7.fc44 before relying on
it. `hostonly="no"` and the force-added virtio drivers are untouched; **x86 is
deliberately untouched** because `moos-nvidia` requires its kmod in-initramfs.

**Measured, by building three real initramfs images on the live A1**
(dracut-108-7.fc44, kernel 7.1.13-200.fc44.aarch64):

| build | size | nvidia firmware files |
| --- | --- | --- |
| no omission | 248,496,743 B (237 MiB) | 597 |
| `omit_drivers` via conf drop-in | **104,554,992 B (99.7 MiB)** | 11 |
| `omit_drivers` via `--omit-drivers` | 104,554,530 B | 11 |

Both forms work; the conf drop-in is the one this edition uses. **58% smaller.**

The first CI run of this fix FAILED, and its own gate is what stopped it — a
good outcome that also exposed a bad gate. The gate demanded the
`lib/firmware/nvidia/` namespace be EMPTY, but the eleven remaining files are
correct: `tegra-drm` (8) and `xhci-tegra` (4) are NVIDIA **Tegra** drivers, real
aarch64 SoC hardware MoOS keeps on purpose, sharing that namespace. The gate now
asserts the four *modules* are absent, plus the size ceiling. **A gate that
cannot pass on a correct image is worse than no gate** — the same lesson this
file already records about `verify_user_experience`'s `startswith("")` default arm.

Gated in three places: the finished-image gate in `build-arm.sh` proves the four
modules left the archive *after* the existing OSTree/virtio/Plymouth gates prove
nothing needed went with them (that ordering held in the failing run: the
OSTree/virtio/splash line printed first), plus a 150 MiB ceiling; and
`tests/test_arm_initramfs_size.py` — bite-tested four ways: omission removed,
storage driver sneaked into the list, `hostonly=yes` as a wrong shrink, and the
too-strict firmware-namespace check being reintroduced — runs in the ARM workflow
via `test_moos_arm.py`. **CONFIRMED ON THE CI ARTIFACT** (run `34002105601`,
the gate's own line): `ARM initramfs: 99 MiB`, down from 237. **Still not
observed on the deployed machine:** `/boot` near 51% once that image is
published and the machine updates — `df -h /boot` then is what closes B01.

Earlier `AnimationDurationFactor=0` was a preserved user override. The owner
subsequently requested motion; the current live value is 0.4. Actual effect
loading still needs the fresh-session check above. Preserve future user edits.

**The loudest warning on the machine was a real bug: `Icon theme "Papirus-Dark"
not found.` × 69 in one boot.** Fedora's `papirus-icon-theme` ships exactly one
directory, `/usr/share/icons/Papirus`; upstream splits Dark/Light variants and
Fedora does not. `MoOSUI2` (the dark base every dark family inherits) named
`Papirus-Dark`, while `MoOSUI2Light` named `Papirus` and was right the whole
time — the same asymmetry in `build.sh`, `finalize_moos_desktop.sh` and the
shipped `kdeglobals` comment. Nothing looked broken because the icon still
resolves through a later link in the chain; only the log knew. All three now say
`Papirus`.

The gate that existed asserted the RPM was installed. The gate that replaces it
resolves the WHOLE chain against the icon directories the finished image really
has (`verify_arm_image.py`), so the class of bug cannot return under a different
name. `tests/test_icon_theme_inheritance.py` rejects the live machine's exact
configuration, holds the dark/light chains to one spelling, and is bite-tested;
it runs in `build.yml`, `build-arm.yml` and the Justfile.

**Arabic spell-check was entirely absent from `moos-arm`, and the contract that
was supposed to prevent that existed only on x86.** Read off the live A1:
`/usr/share/qt6/qtwebengine_dictionaries/` held 24 `en_*.bdic` and **zero**
`ar_*.bdic`, with six `qwebengine_convert_dict` SIGTRAP coredumps in
`coredumpctl` — every one an Arabic locale
(`.../ar_SD.dic -> .../ar_SD.bdic`). `AGENTS.md` calls this build-enforced; it
was, on x86 only. `build-arm.sh` had zero references to `bdic`/`convert_dict`.

Root cause of the crash (already documented by the x86 block): Chromium's
converter aborts on the hunspell `IGNORE` command, and every Arabic `.aff` uses
it to ignore tashkeel — `IGNORE ًٌٍَُِّْـٰ` in `ar_SD.aff` on this machine.
x86 strips that line into a temp copy and converts from there.

Root cause of the DIVERGENCE: the block was copied, not shared. So it is now
`build_files/convert_webengine_dictionaries.sh`, called by both builds, with the
both-languages assertion inside it. **Proven live before shipping:** run on this
A1 it built **50 dictionaries, 26 of them Arabic**, and exited 0 through its own
gate — against a system that currently has none.
`tests/test_webengine_dictionaries.py` holds the shape that matters (both
editions call it; neither keeps an inline copy) and is bite-tested three ways.

**Local override, FIXED with the owner's authorisation (2026-09-06).**
`~/.config/systemd/user/mo-remote-watchdog.service` had
`ConditionPathExists=%t/bus` in `[Service]`, where systemd ignores it
(`Condition*` is a `[Unit]` directive), so the guard its author intended never
applied. That was not cosmetic. Traced in the journal:

    12.65s  mo-remote-watchdog.service starts (pre-graphical-session)
              -> systemctl --user start mo-remote-personal.service
                 -> its Wants= pulls up xdg-desktop-portal
                    -> xdg-desktop-portal-kde is a QApplication; with no
                       platform plugin it hit qFatal -> SIGABRT (core 1381)
    13.18s  systemd: "Dependency failed for xdg-desktop-portal.service"

at every boot, on the machine whose screen IS Mo PC Remote. `%t/bus` was never
the right marker either — the bus exists at 12.5 s. `%t/wayland-0` is what "the
graphical session is up" actually means, and it is what `mo-remote-personal`
needs, so the condition now guards on that and sits in `[Unit]`.

**Kept, not disabled, deliberately:** `mo-remote-personal.service` has
`StartLimitBurst=5`, so after five failures in 300 s systemd gives up
permanently; on this machine that timer is the only thing that recovers from
that. Its `ExecStart` is a plain `start`, a no-op on a running unit, so it can
never interrupt a live session. The shipped unit itself was already correctly
ordered (`After=plasma-workspace.target`, `PartOf=`, `Restart=on-failure`) —
this was never a product bug, only a local unit starting Remote out of band.

Verified live without touching the session: originals backed up to
`~/.config/systemd/user/.moos-backup-20260906/`, `daemon-reload` only, and
across two observed firings the unit ran `Starting -> Finished` with no
`Unknown key` warning while `mo-remote-personal` held **the same MainPID 2262
and NRestarts=1** throughout.

### Launcher keyboard navigation + system-audit integration (2026-09-05)

Branch `fix/system-audit-20260905`.

- **System audit (S01/S02) committed** (`89e4d2a7`): `moos-visual-tier` adds
  `virtio-pci` to `VIRTUAL_DRIVERS` so an Oracle A1 core expansion can't flip the
  host into software-rendered blur (regression proven); `post-update-check.sh`
  reads the booted deployment as one snapshot and gains
  `MOOS_EXPECTED_DIGEST=sha256:<64 hex>`, exercised by the new
  `tests/test_post_update_deployment.py`. `PROJECT_STATE.md` and
  `docs/MOOS_SYSTEM_DEVELOPMENT_PLAN.md` are the current handoff + four-edition
  plan; `MOOS_X86_SYSTEM_PLAN.md` is historical.

- **Launcher is keyboard-operable (THEME_REV 53).** `LauncherView.qml`
  (`org.moos.brand`) had a keyboard dead zone: the sidebar pages carried an
  `activeFocus` edge but no key handlers and no tab-chain slot, and nothing
  moved focus from the search field into Home/Applications/Places/Customize
  content — only the search-results list was wired. Now: the four sidebar
  `NavButton`s take Tab focus, Enter/Space activate, Up/Down cycle the ring,
  Left/Right step into content; `focusActivePageContent()` is the one owner of
  "enter the surface the user sees"; Down from the search field enters it, the
  grids/lists return to the field from their top row, and `Shift+Tab` from a
  grid/list/results goes to the owning page (not the last one). Keyboard
  selection is now visible on `PlaceRow`/`RecentTile` via `ListView.isCurrentItem`.
  Verified: modified QML loads with zero errors in `plasmawindowed`
  (`MOOS_LAUNCHER_FULL_READY 792x576`); new source gate
  `tests/test_moos_launcher_keyboard.py` (bite-tested) and the full CI repo-gate
  list pass (only the documented `systemctl`-missing sandbox gap fails).
  **Not yet done:** driving the focus ring with real key presses on a logged-in
  Plasma session (synthetic input into the live shared session was deliberately
  not used) and the signed-image frame.
  A follow-up in the same rev fixes a real RTL clip found by rendering the
  launcher at 150% in `plasmawindowed`: the Home `CommandCard` eyebrow ran into
  the card's rounded corner and lost its leading letter ("اكتشف" → "كتشف");
  the card now insets its content (`leftPadding`/`rightPadding`), matching
  `AppTile`. Before/after 150% + 100% frames inspected; gated in `test_moos_ui2.py`.

- **`moos-visual-tier` now publishes a resource `budget`** (P01 / ROADMAP-4
  foundation). The same probe that picks the motion tier now also derives, as a
  pure function of `facts` + `tier`: `file_indexing` (content / filenames),
  `update_concurrency` (1 / 2 / 4), `ai_default` (local / cloud) and
  `remote_encode` (720p30 / 1080p30 / 1080p60). It is in `--json`, the human
  summary and the recorded state file. It is **advisory** — visual-tier does not
  write baloofilerc, moai or Remote config; each consumer reads it under its own
  owner. Live on `moos-arm-oracle` (virtual, 2 cores): essential → filename
  indexing, 1 update stream, Mo AI cloud, Remote ≤ 720p30. Gated by
  `tests/test_moos_visual_tier.py` (35 tests). The 2026-09-06 audit corrected
  `file_indexing`: an earlier revision answered `off` for a small streamed box,
  which would have deleted launcher file search from the machines used remotely.
  Measured instead: baloo idle at 0.0% CPU, 12,323 files, 70 MB index — the
  filename index is cheap; content EXTRACTION is the cost. The two values now
  map 1:1 onto `only basic indexing` in `/etc/xdg/baloofilerc`. **Not yet done:**
  wiring the consumers (baloo / `moai-do` / Remote encoder) and the P01
  before/after workload measurement — those stay open on the plan.

### Mo PC Remote v39 — phone workspace (2026-09-05)

The local Remote deployment now serves the Liquid Glass controller with clearer
button plates, constrained sheets, Arabic editing shortcuts and explicit clipboard
directions. Phone clipboard reads produce an editable draft, with manual paste on
permission failure. Sheets follow the visual viewport above the phone keyboard;
the typing bar follows without a second delayed animation. RTL side rails fade in
place so rotation cannot translate them into the desktop. Closed keyboard controls
are inert while opening still focuses synchronously from the phone tap.

Source/bundle tests and rendered evidence, local rollback paths, official product
references and branch-preservation findings are recorded in
[`docs/MO_PC_REMOTE_ARCHITECTURE.md`](docs/MO_PC_REMOTE_ARCHITECTURE.md).
The owner confirmed typing-bar visibility above their phone keyboard in both
orientations. The wider iOS/Android keyboard matrix and cellular performance remain
physical-device gates.
The local deployment keeps the previous app and signed OS deployment recoverable.

### Oracle expansion and Remote Arabic repair (2026-09-05)

The live Frankfurt A1 boot disk is now 200 GiB, with about 155–156 GiB available.
Reboot verification and a read-only full Btrfs scrub passed. The full pre-resize
Oracle backup is retained in the separate backup allowance. App updates and
live keyboard/AppStream repairs completed; selfcheck is 48/48 and post-update
checks are 49/49. Detailed scope and recovery notes:
[`docs/MOOS_ARM_ORACLE.md`](docs/MOOS_ARM_ORACLE.md).

Adding US to the keyboard ring exposed a second Remote bug: its portal cached
Arabic's old group index and typed Arabic positions on English. The active v38
helper now refreshes live groups before selection and remaps the saved home
language by code. Five regression tests and real GTK readback across repeated
layout-list changes pass. Physical-phone confirmation and mixed Latin/emoji
stress paths remain open; this is a local deployment, not a new signed release.

### Keyboard-layout migration reload, and ARM's own AppStream refresh (2026-09-05)

Two independent, small fixes, finished and gated in this pass:

- **`migrate_legacy_keyboard()` in `moos-ui-migrate`** rewrites an existing user's exact
  legacy `LayoutList=de,ara` kxkbrc shadow to `de,us,ara` — the `us` group Mo PC Remote's
  Linux agent needs as a landing spot for its physical-position typing fallback
  (`UsKeymap`/`InputInjector`, see [`moremote/agent-linux/UsKeymap.cs`](moremote/agent-linux/UsKeymap.cs)).
  Without a `us` group in the live layout ring, that fallback has nowhere to select, and
  a run of Latin text typed through the remote lands on whichever layout IS active —
  German or Arabic — which is exactly what scrambles it into wrong letters. The migration
  wrote the file correctly already; what it did NOT do was take effect in the already-running
  session. It called KWin's generic `org.kde.KWin.reconfigure`, which does not reload the
  keyboard on KWin 6.5+ (KWin now watches `kxkbrc` through `KConfigWatcher`). Fixed by
  emitting the watcher's own `org.kde.kconfig.notify.ConfigChanged` signal on the `Layout`
  group after the atomic rename, so the first upgraded session gains the `us` route
  immediately rather than at the next login. The file-rewrite half is covered by
  `tests/test_moos_theme_safety.py::test_keyboard_migration_is_exact_and_preserves_custom_profiles`
  (skipped in this sandbox — no `kwriteconfig6` on `PATH` here — so the live-notify half is
  verified by reading, not by a green run; re-run that test on a real KDE session before
  trusting the reload path fully).
- **ARM's build gained its own AppStream refresh.** ARM does not inherit Kinoite's shipped
  AppStream unit the way the x86 build renames-and-retimes it (see
  `system_files/usr/lib/systemd/system/moos-appstream-refresh.timer`), so enabling that
  timer alone did nothing on ARM — no service backed it. `build-arm.sh` now installs
  `build_files/moos-appstream-refresh.service` (oneshot `appstreamcli refresh-cache --force`,
  `Nice=19`/idle I/O so it doesn't compete with the desktop) and layers the `appstream`
  package; `verify_arm_image.py` gates that the timer/service pair, the executable and the
  enable symlink actually exist in the built image. `tests/test_arm_appstream_refresh.py`
  and the full `tests/test_moos_arm.py` suite pass.

Both changes were sitting uncommitted in the tree from a prior session; this pass ran
`bash -n` on every touched shell script and the full CI "Repo gates" python list (all pass
except the pre-existing `systemctl`-not-installed sandbox gap in
`tests/test_boot_path_authorities.py` and `tests/test_openclaw_modern_unit_retire.py`,
unrelated to these files) before committing and pushing.

### Mo PC Remote v38 — local ARM deployment (2026-09-05)

The current branch fixes cancelled gestures/held inputs, letterbox hit testing,
relative trackpad control with the real embedded cursor, Unicode/IME reconnect
state, local modal keyboard isolation and hidden-viewer video queues. Phone controls
now prioritize typing, clipboard, mode, display and settings; Arabic sheet headers
and rotation help fit without overlap. Detailed per-input disk logging is opt-in.

The self-contained ARM agent and generated v38 controller were built and activated
on `moos-arm-oracle` at 11:15 UTC through a user-service override. Fresh portal
readiness, the served production index and preserved first-run/authentication state
were checked; the previous binary remains available for rollback. This is a local
Remote deployment, **not a new signed OS release**.

Before activation, a separate loopback instance produced 111 real frame messages in
seven seconds, negotiated H.264/OpenH264 and reported ready portal input. A dedicated
focused GTK field read back `MoOS العربية 😀` exactly; a remote click activated its
button, relative movement moved the real pointer, and Backspace removed the emoji.
Browser UI tests use intercepted transport, separately from this live proof.
See [the v38 verification report](docs/MO_PC_REMOTE_ARCHITECTURE.md) for scope and limits.
Physical iOS/Android keyboards, Internet loss/latency matrices and Windows runtime
input remain unverified for this revision; Windows compilation passes.

A full audit pass on 2026-09-05 ran every gate this branch touches: the controller's 66
unit tests, its typecheck and `npm audit`, the Linux agent build, and the two new .NET
executables `MoRemote.Stream.Tests`/`MoRemote.Linux.Input.Tests` (session recovery and
input-injection assertions) — all green. That pass caught and fixed one real gap: the
rebuilt controller bundle's new hashed assets were untracked while the old ones stayed
staged (`test_shipped_bundle_is_tracked.py` would have shipped a blank Remote page). Fixed
by tracking the new assets and removing the stale ones. Separately, `Containerfile` and
`Containerfile.arm` already gate both new .NET test executables during the image build, so a
regression there fails the build; `.github/workflows/build.yml` now also runs both in a fast
`remote-dotnet-tests` job so that signal lands in about a minute instead of waiting on the
full (up to 180-minute) image build. See the verification report for the full gate list.

### Mo PC Remote — real-browser visual audit and full Arabic i18n (2026-09-05)

The controller's own dev server was run under a real headless Chromium (Playwright), with
`window.WebSocket` and `/api/*` faked to drive the actual compiled app through its real states —
PIN setup/login, the connected desktop view, every bottom-sheet, the power-confirm dialog — at
phone (iPhone 14 Pro, iPhone SE) and desktop viewports, in both themes and both languages, and
the resulting screenshots were inspected, not assumed. Evidence lives only in this session's
scratch directory (not committed); the findings below are what changed.

The audit found the Arabic experience was fake past its own surface: the connection-status pill,
the reconnect overlay, and — almost entirely — the Files sheet, Clipboard sheet, Power section and
Security/trusted-devices list rendered in English even with the UI language set to Arabic, despite
the top-level toolbar and Settings toggles being genuinely translated in an earlier pass. Roughly
70 strings across `RemoteScreen.tsx`, `AuthScreens.tsx` and `App.tsx` — including the "cannot reach
the PC" and "connection dropped" error screens, the five power actions and their confirmation
dialog, every clipboard/file transfer toast, and the default trusted-device names — were moved into
`i18n.ts` and now resolve through `tr()`. A second, independent defect surfaced in the same pass:
a toast fired while any bottom sheet was open rendered at its normal fixed position and landed
mid-card over sheet content (first seen overlapping the scroll-speed slider); `.toast.in-sheet`
now pins it to the clear top strip every sheet leaves above itself. Both were verified fixed by
re-rendering the same real-browser screenshots, then confirmed structurally by updating the
literal-source-text assertions in `accessibility.test.ts`, `auth-lifecycle.test.ts`,
`test_remote_power_policy.py` and `test_remote_trusted_devices.py` to check for the `tr()` binding
rather than the now-relocated English string — the same pattern an earlier translation pass had
already established for one string, extended here to the rest. Full gate suite (controller
typecheck/tests/audit, rebuilt-bundle tracking, and the ~86 Python repo gates) passes.

The visual language itself — dark glass surfaces with `backdrop-filter` blur, the turquoise/blue
MoOS accent gradient, restrained opacity over blur per the system's own Liquid Glass doctrine —
was judged already consistent with the rest of MoOS and was not redesigned. Mouse+keyboard control
on the desktop viewport and touch/typing on the phone viewport were exercised through this same
real-render harness and read correctly; no code path was assumed to work without seeing it render.

### Branch reconciliation (2026-09-02)

All remote refs were fetched and compared by patch and by release contract. The old
`fix/build-*`, `fix/ci-kde-gate`, `fix/phone-typing`,
`fix/portal-group-resolution`, `fix/cloud-remote-perf-clarity-20260815` and
`feat/boot-animation-and-arm` refs are already represented by merged PRs; their names simply
remain on the server. Re-merging them would replay older code.

Five genuinely absent commits from `fix/oracle-uefi-capacity-20260829` were integrated on the
current tree: multi-AD/fault-domain capacity retries, UEFI_64 image capability enforcement,
native ARM Tailscale transport, signed-origin repair, portal readiness and single-owner cloud
desktop startup. The merge preserved the newer ARM application, search, storefront, Arabic font
and Remote lifecycle work. `tests/test_oracle_deploy.py`, `tests/test_moos_arm.py`,
`tests/test_cloud_private_desktop.py`, Remote lifecycle tests and shell syntax pass together.
The imported repository block was then reconciled with Tailscale's current official Fedora
definition: both x86 and ARM now require `repo_gpgcheck=1` and `gpgcheck=1`, and the Remote network
boundary test rejects either metadata or package-signature verification being disabled.

`archive/arm-utm-20260827` and the closed PR #61 branch
`fix/utm-release-gates-20260826` were deliberately not merged wholesale. They package the recovery
disk before the candidate is proven and carried a visual-gate bypass. The display-aware greeter
launcher was later recovered selectively from that work onto the current release ordering: UTM's
virtio connector selects its real DRM scanout, while a connector-less Oracle VPS selects KWin's
virtual output. The unsafe publication order and bypass remain rejected.

The candidate at `a931e09c` completed the full matrix. x86 run `33735887419` built and signed
generic, NVIDIA and Cloud images plus the Windows Remote agent. ARM run `33735890038` built and
signed the native image, composed Oracle/UTM and recovery disks, completed two UEFI boots, captured
the graphical session, grew the disk and reported zero failed units.

The exact Cloud disk proof (`33740041923`) passed KVM + VirGL boot, signed-origin, network,
MoOS greeter, zero-failed-unit, reboot, second-boot and clean poweroff checks. Both exact mapped
window frames were visually inspected and show the authored MoOS experience. Generic run
`33740036698` passed the first runtime/frame but its reused QEMU user-network SSH forward accepted
TCP without delivering a banner after reboot. The proof now allocates an independent second host
forward for the second boot, so stale slirp state cannot produce a false product failure.

NVIDIA run `33740038888` passed the runtime contract twice with zero failed units, but its exact
frames were black apart from the white pointer. The old standard-deviation check accepted those
frames because the pointer supplied enough variance. The NVIDIA greeter helper had forced llvmpipe
whenever `/dev/nvidia*` was absent, even though the proof VM exposed a working VirGL render node;
KWin remained active but its mapped scanout was black. The helper now preserves NVIDIA, Intel,
AMD and virtio DRM render nodes and uses Mesa software EGL only when no GPU node exists. A shared
PPM gate also requires at least 3% visible pixels, and a synthetic black-plus-cursor regression
test proves that it fails.

ISO run `33740044447` passed the exact LiveOS visual proof and completed the offline install to
100%, including Btrfs finalization and MoOS UEFI registration. QGA then accepted guest shutdown
but did not terminate the live environment within the deadline. The installer proof now sends one
ACPI power-button event if that clean request stalls, then continues waiting for systemd shutdown;
it does not force-kill the guest. The installed-system boot and app evidence still require one
fresh same-SHA rerun.

The next build at `b7424340` passed all three x86 image builds in run `33758817997`; its Cloud
disk proof `33761593137` also passed both boots. ARM image composition succeeded in
`33758820668`, but the second disk boot correctly failed because `plymouth-start.service` was in
systemd's failed set. The same serial evidence exposed that ARM firmware had registered a legacy
product label even though GRUB itself displayed MoOS. The ARM proof had also still set
`MOOS_ARM_SKIP_VISUAL_GATE=1`, so its tiny framebuffer capture was not release evidence. Current
source removes that bypass, runs the final ARM disk in a mapped GTK window under Xvfb, applies the
shared visible-pixel gate, and preserves full Plymouth status/journal evidence on failure. The ARM
greeter now attaches software rendering to UTM's actual virtio DRM node and uses a virtual output
only on a truly display-less VPS.

Shim's UTF-16 fallback CSV owns the firmware's visible boot-entry label. One shared build helper now
decodes every shipped `BOOT*.CSV` for both x86 and ARM, rewrites the presentation label to MoOS and
fails if the legacy label survives; signed loader paths and required vendor directories remain
untouched.

Candidate `4549641c` then built and signed all x86 editions in run `33764283217`.
Its exact generic, Cloud and NVIDIA disks passed two boots, zero failed units and
clean poweroff in runs `33766163439`, `33766166166` and `33766715929`; their mapped
frames were inspected and show the MoOS greeter. ARM run `33764287001` passed its
runtime and packaging gates, but human inspection rejected its captured frame: the
guest area was black with only a cursor while QEMU's bright 25-pixel menu bar made
the whole-window visible-pixel score read 5%. The shared frame gate now measures an
inset canvas, ARM preserves both the guest framebuffer and mapped window, and its
proof always records DRM, process, environment and greeter-journal diagnostics.
The selectively recovered DRM launcher had also outlived a temporary
`virtio-ramfb` experiment that removed the login user's video/render access; the
standard-QEMU proof uses `virtio-gpu`, so current source restores bounded group
access during image composition and refuses to launch KWin until that exact scanout
is readable and writable. Run `33773955960` proved the first correction was placed
inside the generated remote helper instead of the image build; its finished-image
gate failed before publication, and the rule plus group assignment now precede that
helper's heredoc with a source-order regression test. Run `33775414235` then exposed
bootc's split account database: the package groups live in `/usr/lib/group`, so
`usermod` can succeed without updating them. The next attempt used a
`systemd-sysusers` membership declaration with same-GID `/etc` overlays. Run
`33776822139` proved that sysusers also declines to shadow an already-resolvable
altfiles group during composition. Current source therefore avoids account-database mutation:
udev gives the dedicated greeter ownership of physical DRM nodes while preserving
the standard groups and logind ACLs, and the root pre-greeter helper applies a
user-specific ACL as a bounded fallback. vgem's display-less nodes remain available
to the explicitly started cloud Remote session.

Candidate `70b7d438` later proved the corrected ARM disk in run `33779520543`:
both internal guest scanout and the mapped QEMU window show the authored MoOS
greeter, two boot IDs differ, and both boots report zero failed units. Exact
generic and Cloud x86 disks passed the same two-boot contract in `33782226458`
and `33782228825`; NVIDIA's first proof hit a host Xvfb startup race before QEMU
opened and its unchanged-digest retry is `33785511871`.

Inspection of the maintainer's running ARM session also found that its generated
MoOSUI2 icon theme declared Papirus as a fallback while the ARM package set did
not install it. ARM now installs that fallback explicitly.
**That fix was half of one, and the gate written for it was a green-check trap:**
it asserted the RPM was installed — true — and said nothing about whether the
name in the chain resolved. See the 2026-09-06 entry: the package ships only
`/usr/share/icons/Papirus`, the chain named `Papirus-Dark`, and the misses
continued for months at 69 per boot.

The earlier candidate's final ISO booted visually, but install run `33766199203`
ended when hosted QEMU itself asserted in epoxy after repeated EGL context loss
during the long offline copy. The installer did not report a product error. Current
source uses stable virtio 2D only for that nonvisual copy phase; the independent
LiveOS proof and the installed-system login/application proof remain VirGL mapped
captures. Run `33782234413` then completed that offline installation through 100%,
including EFI registration, signed-origin repair, target trim, sync and unmount,
but the LiveOS desktop session ignored both QGA's generic shutdown and an ACPI
button for 180 seconds. The gate now proves every target filesystem is detached,
flushes guest writes, and asks systemd directly through QGA before retaining the
same ACPI fallback. This correction requires one new same-SHA full matrix before
promotion.

The ARM compose failure from run `33689074450` is closed: local `containers-storage` is allowed
only for composition while the registry path remains exact `sigstoreSigned`; both policy halves
are asserted at runtime by ARM run `33735890038`.

The x86 workflow also caught a newly published high-severity npm advisory before image build.
The affected indirect `fast-uri` lock moved from `3.1.5` to fixed `3.1.7` without changing any
direct dependency or shipped web bundle. A clean Node 22 install, all Remote controller behavioural
tests, TypeScript checking, production build and `npm audit --audit-level=high` now pass with zero
reported vulnerabilities.

### Remote-ready context and responsive control center (2026-09-02)

The native Mo PC Remote control center was rendered on the live Arabic 1920x1080 session. Its
unbounded technical log pushed the window behind the Horizon Bar even though the configured
default height was smaller; source-only tests had not exposed the natural-size minimum. The page
now scrolls vertically and Recent errors is a collapsed, bounded diagnostic expander, matching
Updater and Recovery. The QR, secure URL and five health rows fit in the first viewport. Evidence:
`docs/evidence/mo-pc-remote-control-center-ar-1080p.png`.

The context island now gives authenticated Remote control priority over media. `SessionState`
atomically publishes `presence-active-N` or `presence-paused-N` in the private
`$XDG_RUNTIME_DIR/mo-remote` directory only after WebSocket authentication, updates the real viewer
count, and removes the marker on the last disconnect or clean shutdown. The applet watches those
regular files with `FolderListModel`; it never polls a service and never tries to inspect the
invisible frame socket. Active and paused states were switched live inside `plasmawindowed` with no
QML error and no Plasma/Remote restart. Evidence:
`docs/evidence/moos-island-remote-active-ar.png` and
`docs/evidence/moos-island-remote-paused-ar.png`. `THEME_REV=52` makes the media-only cached island
expire for existing users.

Remote's shared Web API had also drifted beyond the Windows clipboard implementation:
`SetTextConfirmed` and `SetImagePngConfirmed` existed only on Linux, so the Windows agent no longer
compiled. Windows now confirms exact text and canonical decoded image pixels on its STA clipboard
before acknowledging the phone. Verified with a clean `net10.0-windows/win-x64` build (zero warnings
and errors), Linux x64 and ARM64 publish, and 124 Linux behavioural tests. The running Remote,
ydotool and Plasma services were not stopped or restarted.

### Inspection environment, boot overlay and responsive clock (2026-09-01)

The local tree was fast-forwarded to `origin/main` at `f9be33f9`, then a work branch
`work/system-inspection-boot-polish-20260901` merged the remaining live branch
`origin/fix/controller-browserslist-audit-20260901`. That branch only updates the
Mo PC Remote controller lockfile's Browserslist family.

The Codex shell is a Flatpak/VS Code environment, so host tools are intentionally outside its
normal PATH. A user-local helper was installed at `~/.local/bin/moos-host-run` to run commands
on the real host through `flatpak-spawn --host --directory="$PWD"` without mixing host libraries
into the Flatpak runtime. With that helper:

- `mo-remote-personal.service` and `ydotoold-moremote.service` were confirmed active; Remote was
  not restarted or stopped.
- A fresh live screenshot was captured with host `spectacle` to
  `.tmp-live-audit-20260901.png`. The visible desktop retained the MoOS dock, UI2 glass rim,
  first-party icons and Arabic clock with no visible foreign identity on the captured surface.
- The previously failing host-dependent checks were rerun correctly:
  `tests/test_boot_path_authorities.py`, `tests/test_openclaw_modern_unit_retire.py`, and
  `tests/test_moos_fast_remote.py` passed.

Controller verification on the host passed: `npm test`, `npm ci`, `npm run typecheck`,
`npm audit --audit-level=high`, and `npm run build`. The committed
`moremote/agent/wwwroot` bundle remained byte-identical.

Plymouth now bounds all event-driven text overlays to 78% of the screen width: boot status
messages, encrypted-volume prompts and password bullets. This prevents long fsck/device/recovery
messages from clipping off small VM or laptop screens while keeping the refresh loop unchanged.
`tests/test_boot_splash_polish.py` now gates that contract. Verified:
`python3 tests/test_boot_splash_polish.py`, `python3 tests/verify_user_experience.py`, and
`bash -n build_files/build.sh build_files/build-arm.sh build_files/build-arm-recovery.sh`.

The panel clock now lets Plasma choose its representation from the available space: the dock
keeps the fixed compact chip, while a popup or standalone window receives the full clock and
calendar. The full surface adds a theme-driven day header, minute-updated day-progress line,
scale-aware week numbers, a working return-to-today action and the existing guarded
`moos://settings/time` route. No new timer or permanent animation was added. Revision 51 introduced
the popup; current `THEME_REV=52` also delivers Remote presence and purges both old QML surfaces.

The modified source package was loaded through an isolated temporary `XDG_DATA_HOME` and
rendered on the live Arabic session at 100%, 125% and 150%; it produced no QML load errors,
kept all controls/text inside the window, and its accent edge measured 90+ luminance steps
against the adjacent surface (the design gate is 15). Evidence:
`docs/evidence/clock-popup-arabic-100.png`,
`docs/evidence/clock-popup-arabic-125.png`, and
`docs/evidence/clock-popup-arabic-150.png`. The temporary package and process were removed;
no user-local plasmoid override remains. 200%/225% on a real 4K frame and the signed-image
popup remain release evidence, not source-complete claims.

Older state retained below:

### Oracle ARM live desktop audit — fixes in source (2026-08-30)

A normal-user audit on the native Oracle A1 deployment `44.20260830.203` found ARM parity and
Remote lifecycle defects that source-only gates had missed:

- ARM shipped `balooctl6` without `kf6-baloo-file`, so configuration and self-check inputs said
  indexing was enabled while no indexer service existed. ARM now includes the real service.
- ARM omitted Gwenview and Haruna, leaving images assigned to Chromium and MP4 with no handler.
  Both viewers now join the curated ARM desktop package set.
- ARM skipped the x86 Discover rewrite and showed a second storefront beside Mo Store. The image
  now applies the same hidden, MoOS-branded engine entry; `moos-one-store` also writes an effective
  per-user override so existing deployments repair without modifying immutable `/usr`.
- The English keyboard display name was empty (`DE,,ع`), making the active English layout look like
  no layout at all. New and migrated configurations show `DE,EN,ع`; the live session was explicitly
  returned to Arabic without restarting Plasma.
- The live account had never recorded a MoOS language choice and still ran `C.UTF-8`, so the panel
  clock showed an English date despite an Arabic-speaking owner. `moos-lang ar` now records Arabic,
  sets Plasma translations and `LC_TIME=ar_SA.UTF-8`, and updates activation environments; the
  existing shell will adopt the Arabic clock/date at the next login without disrupting Remote.
- Every GStreamer rebuild added a bus signal watch but never removed it. On the live server one
  helper process accumulated dozens of PipeWire clients, and service stops timed out. Pipeline
  retirement now disconnects the handler, removes the watch, clears the bus references, stops the
  health generation, and then transitions to NULL through one teardown path.

The live wallpaper was repaired to MoOSUI2Aurora and visually inspected at 1920x1080; text and the
desktop stream were sharp. Applying the Remote helper change still requires the next signed ARM
deployment and a service restart, deliberately deferred so the active remote session was not cut.

### Mo Store first user install — fixed and live-proven (2026-08-30)

Mo Store rejected every first per-user Flatpak install with `Parsed Flathub remote failed URL/GPG
validation`. `Flatpak.Remote.new_from_file()` does not expose the effective `gpg-verify` bit until
the parsed remote is installed, although the `.flatpakrepo` already carries the verified key. The
backend now validates the pinned URL and embedded GPG key before adding the remote, then verifies
libflatpak's effective URL/GPG/disabled/nodeps state after installation. The production path was
proven on Oracle ARM by installing `org.gnome.Calculator`; the job completed at 100%, the user
Flathub remote is GPG-enabled, and subsequent installs use the repaired effective remote.

### Mo PC Remote gesture scrolling — fixed in source (2026-08-30)

The touch controller's default `Natural scroll` setting was wired backwards. The gesture engine
reports finger travel, while the Remote input contract reports wheel travel (`dy > 0` means scroll
down). Passing an upward finger delta through unchanged therefore scrolled the remote page up; an
upward swipe moved the content down, exactly opposite the label and normal phone behaviour.

- Natural touch scrolling now inverts both gesture axes before sending wheel input; traditional
  scrolling preserves the gesture sign. The desktop mouse-wheel path is unchanged because browser
  wheel events already carry wheel, rather than finger, direction.
- The controller test suite now gates the sign translation. All controller tests, TypeScript, the
  production Vite build, shipped-bundle tracking gate, and all runnable `test_remote_*` repo gates
  passed in the development environment.
- Live Plasma/portal input and audio were not re-proven in this session: the available shell is an
  ARM development container without systemd, PipeWire or KDE Frameworks. The next signed-image
  acceptance still needs a real MoOS session and the release-acceptance loop documented in
  `moremote/docs/MOOS_REMOTE_ARCHITECTURE.md`.

### MoOS Cloud developer container isolation — fixed in source (2026-08-30)

`moos-cloud-dev` contained a policy-aware subordinate-ID allocator but `ensure_subids` did not use
it. New developer accounts missing a preallocated range were instead placed on a hard-coded grid
starting at 100000, even when the host's `login.defs` required a different floor. The old gate
looked for uid arithmetic and therefore held the wrong implementation in place while reporting OK.

`ensure_subids` now allocates `subuid` and `subgid` independently from each file's existing
high-water mark and the host's configured `SUB_UID_MIN`/`SUB_UID_COUNT`. The gate now executes the
allocator against a temporary host policy and proves the production path calls it for both maps.
- **New deployment confirmed booted** (`49d73f3965a1` is the `●` current deployment; old
  `2747ad403c8d` and `355327e314f8` retained as rollback).
- **Aurora theme confirmed live**: `LookAndFeelPackage=org.moos.ui2.aurora`,
  `ColorScheme=MoOSUI2Aurora`, plasma style `MoOSUI2Aurora`, accent `78,215,200`. A captured
  Mo Settings window measured mean luminance 90.7 with teal `(24,120,120)` dominant — the
  Liquid-Glass teal is actually rendering, not just configured.
- **Speaches confirmed fixed on the shipped image**: `systemctl --user start speaches` →
  `active (running)`, `Uvicorn running on http://0.0.0.0:8000`, `NRestarts=0`. (The earlier
  root/user podman-store split is resolved in source: the Containerfile chmods `/home/ubuntu`
  and the build runs rootless into the store the service reads.)
- **Waydroid confirmed**: `Container: RUNNING`, `Session: RUNNING`, IP 192.168.240.112,
  user moos(1000), started on demand (does not autostart — by design, to spare GPU/RAM).
- **Wine / Okular / PDF→Okular / visual-tier** all present and enabled.
- **Boot path**: `flatpak-system-update.timer` was found adding **~24.5s** to every cold boot
  (synchronous `flatpak update`+`repair` on `network-online.target`). Disabled + masked on the
  live machine AND in `build.sh` so it does not return on rebuild. Flatpak stays fully usable
  (`moai-do update` / `flatpak update` on demand).
- **Dock visual identity (post-reboot refinement):** the MoOS dock is already frosted Liquid Glass
  (Aurora `panel-background.svg`, KWin blur BlurStrength 15). Added a **thin teal bottom edge**
  (`#4EC8C8`, opacity ~0.42–0.52) to the dock/panel SVG so the bar carries MoOS's accent identity
  without breaking the owner's "frosted, no white glow, no top lines" rule. Verified visually on a
  real 4K capture: teal-edge pixel density went from 0% to ~0.9% across the bottom strip, ~1.6% on
  the MoOS Island pill. The edit is FILL-only (no outline paths) so the build's glass-mask gate still
  passes. Committed in source so it survives the next deployment.

### Theme system is FAMILY-WIDE, not a single theme (phase 4d, 2026-08-29)

MoOS ships **16 themes** — 8 families (Graphite, Aurora, Nova, Amethyst, Midnight, Arena, Forge,
Scholar) × dark/light. Each is generated from `artwork/moos-ui2/` source by `generate_moos_ui2.py`
(Graphite/Tidal) and `generate_moos_themes.py` (the other 14), driven by `theme-profiles.json`
+ `moos-ui2/palette.json` + `moos-themes/palettes.json`.

The dock bottom rim previously used a **neutral grey** (`@OUTLINE@`) on every theme — it broke the
family identity. Fixed at the **source**: `panel-background.svg.in` now fills the bottom rim with
`@RIM_ACCENT@` (the family primary), and `render_panel` passes `@RIM_ACCENT@ = tokens["primary"]`.
Verified across all families in the built image:

| Family (dark) | Dock rim |
|---|---|
| Graphite | teal `#4ED7C8` |
| Aurora | blue `#3B82F6` |
| Nova | indigo `#6366F1` |
| Amethyst | violet `#C084FC` |
| Midnight | cyan `#22D3EE` |
| Arena | magenta `#FF2D95` |
| Forge | green `#3FB950` |
| Scholar | amber `#E0A458` |

Visual proof (4K captures): switching to Amethyst live flipped the dock rim from teal/blue to
**violet** (63/82 rim pixels), and the theme picker renders **125 distinct saturated accent
buckets** — the full family set is visible and switchable. The rim is FILL-only (no outline), so
`verify_user_experience` still passes; `test_moos_ui2.py` (40 tests) still OK.

### Motion is ADAPTIVE to hardware (moos-visual-tier) — verified live

`moos-visual-tier` reads the render node / GPU driver / core count / RAM and picks one of three
tiers, then writes `kwinrc`/`kdeglobals`/`kscreenlockerrc` via `kwriteconfig6`:

- **flagship** — discrete GPU with driver bound, ≥8 cores, ≥15 GiB → full motion, blur 15
- **balanced** — real (integrated counts) GPU + driver, ≥4 cores, ≥6 GiB → blur 9, squash not magic-lamp
- **essential** — software rendering / weak → no blur, short cheap motion only

It **never raises BlurStrength above 15** (the readability ceiling) and stops touching blur once you
set it yourself. Wired to boot via `moos-visual-tier.service` (enabled, `graphical.target.wants`)
and called from `moos-apply-theme`. On this machine (nvidia, 16 cores, 15.4 GiB, 4K) it reported
**Tier: flagship**. This satisfies the "1 GiB RAM → strongest, weakest GPU → flagship" goal: a 1 GiB
no-GPU box lands on `essential` automatically.

The same probe now also emits an advisory **`budget`** (`--json` + state file): `file_indexing`
(content/filenames), `update_concurrency` (1/2/4), `ai_default` (cloud only), `remote_encode`
(720p30/1080p30/1080p60), a pure function of the probed facts + tier. It is not a second writer —
Baloo now reads it through `moos-index-policy` (2026-09-07); update and Remote hints remain advisory.

KWin effects confirmed enabled: `blur`, `magiclamp` (genie minimize), `scale` (open/close), plus
`slidingpopups`/`fadingpopups`/`slide`/`dimscreen`/`dialogparent`/`fullscreen`/`overview`/
`windowview`. MoOS keeps exactly one effect per exclusive slot (magiclamp/scale/slide) and excludes
expensive/conflicting ones (translucency, glide/fade-vs-scale, wobbly/cube/fall-apart).

### Oracle ARM deployment — LIVE ON ALWAYS FREE A1 (2026-08-30)

- Exact release disk `44.20260829.197` / revision `da7fff6e` is present locally;
  its raw SHA-256 matches the CI manifest and it passed two AArch64 UEFI boots,
  cloud-init, graphical target, zero failed units and clean poweroff.
- OCI authentication, full tenancy administration, the SSH-key fingerprint,
  VCN, internet gateway, public subnet and TCP/22 security rule were verified.
- Root cause of the first `Running` but unresponsive instance was proven in OCI:
  the custom image and instance had `firmware=BIOS`, while the release disk is
  UEFI. Its console history was empty and SSH timed out. The image now has an
  ACTIVE `Compute.Firmware=UEFI_64` capability schema, and every later launch
  reports `firmware=UEFI_64`.
- Instance `moos-arm-oracle` is running in Frankfurt AD-1 / fault domain 3 on
  `VM.Standard.A1.Flex`, 1 OCPU, 4 GB RAM and a 50 GB boot volume. A real guest
  reboot returned with a different boot ID, `systemd` running, graphical and
  display-manager targets active, zero failed units, and 43 GB free on the
  grown physical root filesystem.
- The booted deployment is the signed exact origin
  `ghcr.io/moalfarras-sys/moos-arm@sha256:7a6f1191e691b6f5ee35a70caad77b066cf13aa4b24c72e631a532fd90cb1825`,
  version `44.20260829.197`, architecture `arm64`, with `containerPolicy`
  signature enforcement. cloud-init completed from `DataSourceOracle` with no
  errors and the provisioned SSH key works for user `moos`.
- The private browser desktop is live at
  `https://moos-oracle.tailab78a5.ts.net` (tailnet only). A real Firefox session
  rendered the MoOS welcome desktop; the RemoteDesktop portal restore token,
  authenticated audio route, H.264/clipboard HTTPS publication and autologin
  survived reboot. No desktop or agent port is exposed on the public Internet.
- The first Oracle runtime exposed one ARM packaging gap: Mo PC Remote shipped
  but Tailscale did not. The live server uses the verified upstream aarch64
  static release; `build-arm.sh` now installs the native RPM, enables
  `tailscaled.service`, and the finished-image gate asserts both contracts.
- Temporary capacity-proof/custom-image instances and their boot volumes were
  terminated after the reboot proof. The uploaded QCOW2 object and all expired
  pre-authenticated import URLs were removed. The capacity watcher is disabled;
  only the proven 1/4/50 instance and its 50 GB boot volume remain. An ACTIVE
  tenancy-wide budget (`MoOS-Always-Free-guard`) alerts the owner at actual
  spend above 0.01, with a budget amount of 1 in the tenancy currency.
- `scripts/oracle_deploy.sh` fixes the former silent valid-config exit, uses
  the real limits API, treats the tenancy as root compartment, enforces UEFI on
  import, and provides a duplicate-safe capacity watcher with encrypted
  management credentials. Its watcher found a valid UEFI placement and stopped
  itself; the service is now disabled to prevent duplicate instances.

---

## Boot splash: root cause of "black screen, no MoOS logo" — FIXED (2026-08-24)

**Symptom on the owner's NVIDIA daily driver:** from power button to desktop,
a black screen; the MoOS splash never appeared; boot felt slow (~36 s measured:
13.9 s firmware + 6.6 s GRUB/loader + 10.5 s kernel+initrd + 4.9 s userspace).

**Root cause (proven, not guessed):** `moos.script` shipped with a **UTF-8 BOM**
(EF BB BF at byte 0). Plymouth's scanner turns those bytes into three SYMBOL
tokens before the first comment, so the parser rejects the whole script
(`Unparsed characters at end of file`, L:1 C:0) and `script_parse_file()`
returns NULL. `plugin.c` does NOT check that result — it calls
`start_script_animation()` anyway and reports success, so plymouthd runs a
theme that draws nothing (not even its background colour, which the script
sets). Result: a pure BLACK splash window (8.7 s → 14.5 s of the boot) while
every file-presence gate stayed green.

Fixes landed:

- BOM stripped from
  `system_files/usr/share/plymouth/themes/moos/moos.script`.
- New gates that FAIL on any BOM in the theme dir:
  `tests/test_boot_splash_polish.py` (repo) + inline gates in `build.sh`,
  `build-arm.sh`, `build-arm-recovery.sh` (image). Both layers bite-tested.

Initramfs diet (same session): the generic `--no-hostonly` initramfs was
sweeping in the full initrd network stack (`network`, `network-manager`,
`kernel-network-modules`) plus all of `kernel-modules-extra` although MoOS
always roots from a LOCAL device. Both are now omitted in `99-moos-boot.conf`
and both dracut runs.

---

## Boot speed / GRUB / Plymouth polish — 2026-08-25

- **GRUB hidden** — no GRUB menu flash on boot (commit `3011182a`).
- **Faster Plymouth** — `use-fb`, `fbcon=nodefer`, `CUE_DELAY 2.4s` in the
  kargs so the splash paints immediately and quits as soon as userspace is
  ready instead of holding the screen.
- **`plymouth-use-simpledrm`** is absent on the NVIDIA image (correct — the
  nvidia driver owns the framebuffer) and present on generic.

Verified on the live ISO: UEFI → GRUB "MoOS Live" → Plymouth splash with the
MoOS teal accent on a dark MoOS background (NOT black, NOT Fedora).

---

## moai-wake reachability — FIXED (merged 2026-08-25, commit d4a0bdf1)

`moai-wake` was the ONLY process that could wake a sleeping OpenClaw gateway.
On a network with no IPv6 default route it died instantly on the AAAA record
(`[Errno 101]`) and the default A record timed out, while `.167.220`/`.99`
answered in ~0.10 s. An enabled WhatsApp channel pinned the gateway awake and
**masked this for months** — the phone agent was silently dead while every
surface reported healthy.

Fix: restrict resolution to IPv4 and, on a *connection* failure only, retry
known `api.telegram.org` addresses with the socket pinned (TLS SNI + Host still
carry the real name, so cert validation is unchanged). The winner is cached and
tried first; `149.154.175.50` is excluded (answers `SSL: WRONG_VERSION_NUMBER`).

- `system_files/usr/bin/moai-wake` — hardened.
- `tests/test_moai_wake_telegram_reachability.py` — offline gate, confirmed to
  fail against the pre-fix script.
- Wired into `Justfile check` and `build.yml` CI gate.
- The previous live state (gateway pinned awake via masked `openclaw-idle`) is
  now superseded by the signed image carrying this fix.

---

## Theme system hardening — MERGED (2026-08-25, commit d4a0bdf1)

From `backup/theme-system-2026-08-06`:

- `system_files/usr/bin/moos-apply-theme` — tray toggles one click away, not
  two icons; cleaner state write.
- `system_files/usr/bin/moos-selfcheck` — stricter self-check.
- `tests/verify_user_experience.py` — stronger UX gate.

---

## ISO build pipeline — proof-gated

The workflow preserves a built ISO for diagnosis as an explicitly **unproven,
unsigned** debug artifact when a gate fails. The release ISO is signed and
uploaded only after both the exact LiveOS boot and offline install/installed-
system proof pass. Neither gate has `continue-on-error`.

Run `32851648759` previously completed both paths. Candidate run `33740044447`
completed LiveOS boot and the exact offline install through Btrfs finalization
and UEFI registration; its clean-shutdown fallback and installed-system SSH/app
inspection must pass on the final same-SHA rerun before the ISO can be called
publishable. Generic ISO media installs the generic x86_64 edition; NVIDIA
remains a separately built and proven image/update path.

---

## Recent work — 2026-08-27 (x86 boot experience continuation)

Two defects found and fixed while continuing the x86 system plan from
`docs/MOOS_X86_SYSTEM_PLAN.md` (Phase 1 shipped; Phase 2 in progress).

### `moos-visual-tier` was shipped but never ran at boot — FIXED

The phase-2a commit (`4bf615a6`) added `moos-visual-tier.service` and a
`systemctl enable moos-visual-tier.service` line in `build.sh`, but the unit
file had **no `[Install]` section**. `systemctl enable` then printed a warning,
returned 0, and created **no wants symlink** — so the unit stayed `static` and
never ran. On the real machine the journal showed `-- No entries --`; the
hardware-matched motion profile was therefore never applied automatically (a
software-rendered box or a small laptop paid for a full GPU blur pass it could
not afford, and the cloud edition streamed an animated wallpaper via llvmpipe).

- Added `[Install] / WantedBy=graphical.target` to
  `system_files/usr/lib/systemd/system/moos-visual-tier.service`.
- `tests/test_boot_path_authorities.py` now PROVES the enable actually creates
  the `graphical.target.wants` symlink (it enables the unit against a throw-away
  root and asserts the symlink exists). Bite-tested: a unit without `[Install]`
  is correctly rejected. The old check only looked for the `enable` string in
  `build.sh` — a green-check trap, exactly the kind the repo's rules forbid.
- The running machine was on image `moos-nvidia:phase2boot` (pre-fix). It was
  left as-is by owner decision; the fix lands on the next built/updated image.

Verified: `moos-visual-tier --apply` runs clean and classifies the owner's
machine as `flagship` (nvidia, 16 cores, 15.4 GiB, 4K).

### First-party app dedupe — `moos-store-browse` removed

Phase 2 goal: one owner per capability, no duplicate front doors. Audit of the
`moos-*` / `moai-*` surface found the redundancy was smaller than it looked:

- `moos-store-browse` was a 18-line shim that did only
  `exec moos-storectl open-engine bazaar`. `org.moos.store` calls
  `moos-storectl` directly; **no caller** referenced the shim. Removed it,
  dropped it from `build.sh`, and inverted the gate in
  `tests/verify_user_experience.py` to **require its absence** (bites if it
  returns). Bite-tested green→red→green.
- `moos-store` (launcher: QML cache stamping, background index rebuild,
  `moos-qml-shell` app_id) vs `moos-storectl` (backend) vs `moos-store-index`
  (indexer) are **three distinct roles**, not duplicates — kept.
- `moai-open` (detached `systemd-run --user` launch for the Telegram agent) and
  `moos-one-store` (hide Bazaar launcher, the "one storefront" guard) are
  **purposeful**, not duplicates — kept.
- `moos-compat` / `moos-hardware` are intentional `moai --panel` wrappers so
  old shortcuts/dock entries keep working — the allowed "shim routes to owner"
  shape. Kept.
- All five first-party QML apps already import `org.moos.ui` (the shared Liquid
  Glass component library) from a single `main.qml` — the "shared component
  library" Phase-2 item is already met.

### Live user audit — 2026-08-28

A real post-reboot audit found two defects that static presence gates had missed:

- Waydroid was installed/enabled but failed with SELinux AVCs while appending
  `/var/lib/waydroid/waydroid.log`: the earlier `/var/waydroid` symlink design
  gave the `waydroid_t` domain a generic `var_lib_t` label. The live machine was
  migrated back to canonical `/var/lib/waydroid`, relabelled to
  `waydroid_data_t`, and the container plus Android UI were then proven running
  (Android home screen, Chrome, search, clock and navigation visible in a
  3840x2160 screenshot). Source now uses `tmpfiles.d` to preserve that canonical
  SELinux-labelled path. Android remains on-demand at the user-session level so
  fresh boots do not consume GPU/RAM for users who do not use it.
- The optional Speaches Arabic voice container was in a restart storm: its
  non-root `ubuntu` user could not traverse upstream image `/home/ubuntu`
  (`0750 root:root`), so Podman reported `uvicorn: Permission denied`. The
  pinned bootstrap Containerfile now makes only `/home/ubuntu` traversable and
  owns `/home/ubuntu/speaches`, retaining non-root execution. A local derived
  image test runs `uvicorn --version` successfully as uid 1000.

The live machine's Speaches/OpenClaw restart loop was stopped while the corrected
image is built; it must not be advertised as healthy until the rebuilt image is
prepared and the speech endpoint answers.


MoOS is a **real operating system**: an immutable, signed bootc/OSTree image
built FROM Fedora Kinoite + KDE Plasma 6, with its own MoOS UI (Liquid Glass),
its own apps (Mo AI, Mo Store, Mo Settings, Mo Updater, Mo Recovery, Mo PC
Remote, MoPlayer), its own identity on every user-visible surface (Plymouth,
GRUB, login, desktop, installer — no Fedora/Red Hat branding reaches the user),
and a signed-update + rollback path. The maintainer's daily driver runs the
`moos-nvidia` image. The release blockers below are about *proving* every edge
(ARM, visual matrix, real-hardware ISO install) — not about whether the OS
exists.

---

## Still unproven / open

- **Live-ISO on real hardware** — QEMU is the release gate; the ISO is proven
  in CI QEMU boot+install, but a real-firmware/real-disk pass remains a
  separate hardware exercise. (The owner's machine runs the container image,
  not the ISO.)
- **ARM / iPhone UTM net installer** — full path (download → install → boot →
  greeter) not proven E2E on physical hardware. *Partial:* the owner's Oracle
  A1 (real aarch64 hardware) has run `moos-arm` natively since 2026-08-30 —
  native boot, package layering, font config, and reboot cycles verified on
  the metal. Still open: the iPhone/UTM net-installer flow specifically.
- **Visual matrix** — 1080p/1440p/4K × 100/125/150/200/225% × en/de/ar ×
  dark/light not all captured. Per `MOOS_DESIGN_PLAN.md` §2, the largest
  untouched opaque surfaces are the lock/login/logout screens.
- **Rollback on the real NVIDIA host** — not exercised against a deliberately
  broken update.

---

## Load-bearing release contracts

- Never weaken identity gates; repair the image scrub.
- Published tags move only after boot-proven artifacts.
- `/var` empty in image; `bootc container lint` is a gate.
- Recovery coldplug + device timeout gates cannot be removed (iPhone boot fix).
- An unproven ISO may be retained only as an unsigned debug artifact. The signed
  release ISO must remain after both hard-fail boot and install proofs.
