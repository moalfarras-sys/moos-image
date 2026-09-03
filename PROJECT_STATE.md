# MoOS — current project state

This file is current state, not session history. Git history owns the history.
When documentation disagrees with a running machine, a freshly booted artifact,
or current source, those stronger forms of evidence win.

Last reconciled: **2026-09-03 (exact-frame release proof)** — latest source
branch, signed CI artifacts, exact mapped-window evidence, and live host checks
on `moos-arm-oracle`.

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
helper's heredoc with a source-order regression test.

The same candidate's final ISO booted visually, but install run `33766199203`
ended when hosted QEMU itself asserted in epoxy after repeated EGL context loss
during the long offline copy. The installer did not report a product error. Current
source uses stable virtio 2D only for that nonvisual copy phase; the independent
LiveOS proof and the installed-system login/application proof remain VirGL mapped
captures. These ARM and ISO corrections require a new same-SHA full matrix before
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
