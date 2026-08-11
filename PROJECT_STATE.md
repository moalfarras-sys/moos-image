# MoOS — where the project actually is

**Read this before touching anything.** It is the map an agent needs on day one:
what exists, what is load-bearing, and which of the "obvious" things to do next
are traps that have already cost this project a day.

Last updated: 2026-08-11, signed **`44.20260811.583`** on all three editions
(main `f4cd224e`), deployed and verified on the live cloud host. This release
carries two fixes both root-caused ON that host: `moos-bar-apply`'s shell
probes were unscoped `pgrep`, so on a multi-user machine another session's
plasmashell made every headless login "fail" its stop and bail one line before
`start_shell` — every remote screen streamed black with zero failed units
(single-user desktops cannot reproduce it; that is how it shipped). Probes are
now user-scoped, the unit stop is unconditional (is-active calls an ACTIVATING
unit a failure), and a failed stop restores the shell before bailing. Second:
Mo PC Remote's controller bar moves to the TOP edge on hover+fine-pointer
devices — bottom-centre belongs to the remote's own dock, and the bottom
hover-summon strip meant reaching for that dock summoned the bar under the
click. Verified end-to-end on the deployed `:8444` screen: bar at top over the
live stream, dock clickable, phones unchanged at the bottom. After the `.583`
reboot all three cloud sessions started their shell exactly once, `bar=ok`,
v49 markers written; the temporary per-user shell-guard timers were removed.

Release `.583` signed digests:

- generic: `sha256:f757cb378931a52cd539506ed6dc80620f5c1c479a7e7acec85e499ecfcd1714`
- NVIDIA: `sha256:a0b22ac0a4087597c415e3c1c74aff10281f9e47df66aec09c57bea774cc6794`
- cloud: `sha256:ee9a189d47bd2f3455f300f507dc0528bcee99c7180e6b3dc02588d94f63c782`

Working tree, 2026-08-11 — **Unified motion + sound polish, THEME_REV 50**
(`polish/unified-motion-sound-2026-08-11`, not published or deployed yet): the
existing Horizon Bar media island now sizes its hover extension from
the active player's real Previous/Next/Volume capability count instead of a
fixed 68 px, and one reveal progress owns control width, travel and opacity.
The self-referential track-title `y` animation is replaced by a layout-neutral
Translate entrance, the capsule gains a finite Tidal crest response, and both
media and calendar popups receive short reduced-motion-aware entrances. There
is still one bar capsule and the island still collapses to one transparent pixel
at idle; no new shell owner, timer or media registry was introduced.

The existing session surfaces receive one coherent entrance pass without
touching authentication or power signals: the logout island settles from
0.965 scale, its existing action tiles reveal in a bounded visual sequence, the
shared Login/Lock action key widens its crest/horizon on hover/focus, the login
signature's former anchor animation is now a reduced-motion-aware Translate,
and ksplash's existing brand grows to a 4K-appropriate bounded size with a
single scale settle. Source-tree QML was loaded by the real
`ksmserver-logout-greeter`, `kscreenlocker_greet --testing`, and
`plasmawindowed` at 3840×2160; the lock/password/PAM composition loaded and
rendered without QML errors. Temporary XDG overlays were removed afterward.

Plymouth keeps the same MoOS mark/orbit composition but its hero sources are
now 1024 px (logo/glow/pulse) and 1440 px (rings), so a 4K frame downsamples
instead of doubling 720 px art. The logo, field and one entrance wave now settle
and stop resampling; only the energy head/particles remain as the loading
signal. The generated seven-sprite payload is still only ~913 KiB. This is
source/preview and composed-image evidence, not a boot proof: a real boot
remains required before claiming the new Plymouth motion shipped.

The four-file sound sample is now a 27-event original MoOS family: login/logout,
message, dialog severity, device/service arrival and removal, battery, power,
completion/outcome, volume/button micro-feedback and trash. Every file is
synthesized at 48 kHz stereo from the same glass-chime vocabulary, contains no
recorded/third-party sample, and was decoded by `ffprobe`; a new gate pins the
semantic inventory and Ogg headers. Cloud keeps the same pixels and sound
assets but all new QML motion collapses through `longDuration > 1`, matching its
existing `AnimationDurationFactor=0` policy.

`just check` passes with the new sound/Plymouth gates wired into the default
recipe. The runtime motion test skips on this host because the standalone Qt
`qml` executable is absent, but the edited island/logout/lock sources were
loaded by Plasma's real hosts and the comment-stripped reduced-motion contract
passes. A full local generic `just build` then completed from this exact tree:
MoPlayer and Mo Remote built, every shipped QML app, the launcher, island and
desktop scene loaded offscreen, the final 122 MiB initramfs contained the MoOS
Plymouth script and its new sprites, and the image-experience, store, identity
and foreign-identity firewall gates all passed. `bootc container lint` passed
its checks with warnings only, and Podman emitted `localhost/moos:latest` as
`eee86c4f62577c1cbfffb6d95fe2fa627deb443aa8997827ab19ee5ca8f65577`
(10,776,133,031 bytes). The MoPlayer SDK still keeps the normal signed mirror
path first and retries the official signed origin only when that build-only
transaction fails. A real boot remains open; do not call the motion shipped
until the signed image is published and viewed through boot.

Previous release `.577` (main `c6b71924`) shipped THEME_REV 49 live-shell
recovery, the media-island follow-up, the adversarial hardening pass, and the
live offline ISO `MoOS-Live-c6b71924.iso` delivered to the owner desktop.

The live ISO built from the signed generic image is
`MoOS-Live-c6b71924.iso`, 5,164,040,192 bytes, SHA-256
`671973a043c989e47aa21419d79549f055d392fc05fc7b92e8a2cea2c250380f`, delivered
to `~/سطح المكتب/MoOS-ISO/` with a `BUILD-INFO.txt` and a verified checksum
file. `file` reports `ISO 9660 … 'MoOS-Live' (bootable)` and `sha256sum -c`
passes. **It has NOT yet performed an install** — the release rule stands: a
newly signed ISO must complete a no-NIC install and the resulting disk must
boot with the ISO removed before this is called a closed release.

The NVIDIA edition failed its first CI attempt on this commit while generic and
cloud succeeded. A complete local `just build-nvidia` passed (exit 0), which is
what justified re-running that one job — it then succeeded. Treat a lone
NVIDIA-edition failure as runner resource pressure ONLY after a local build
proves the source; never re-run a silent buildah failure on faith.

The current working branch continues the Unified MoOS Experience without
replacing its architecture. THEME_REV 48 made the Horizon Hub cardless and
centred in the upper/middle wallpaper composition, replaced the launcher's
split neon/wireframe popup rim with a continuous neutral Liquid Glass rim, and
turned the existing `org.moos.island` + Plasma `Mpris2Model` implementation into
a direct adaptive zone immediately after the launcher in the one-capsule bar.
THEME_REV 49 closes defects found only after the signed update reached a
persistent user profile: launcher pointer activation and Plasma
keyboard/accessibility activation now have exactly one expanded-state owner
(`activationTogglesExpanded` declared on the root PlasmoidItem — assigning it
through the Plasmoid attached object is a silent no-op on Plasma::Applet); the
bar's revision marker is a fingerprint of the actual payload of ALL THREE
first-party bar packages (launcher, island and `org.moos.nova.clock`), with an
overridable root so the gates execute the function; the marker is trusted only
when the current plasmashell journal is clean for those three applets and the
live panel readback agrees; a health failure that survives the one bounded
recovery restart fails fast instead of idling in the readback loop; and both
historical system-tray nesting shapes are scrubbed of the retired second
island without touching unrelated tray children. The launcher's orbit grid
also retires a `preferred://` favourite alias exactly when the user pins the
same resolved application, so one app can never occupy two tiles while user
pins and distinct targets are never touched.

The island remains one transparent pixel at idle and exposes art/source/title,
capability-aware transport controls, timeline/seek and volume/mute in compact
and expanded modes. Rev 49 additionally resolves Flatpak Media Session artwork
from the app's private runtime `/tmp` — as a probe: if the translated path
errors (host-installed Chromium-family browsers publish the same dot-prefixed
basenames but their raw `/tmp` URL is the readable one), the image falls back
to the raw MPRIS URL and re-arms per artwork change — fixes a live
compact-hover reference error, commits seek/volume changes from AT-SPI slider
actions clamped to the slider's own 0..1 range, and captures expanded state on
press in the compact capsule so a dialog dismissed by the press is not
re-opened by its own release. It has no permanent decorative animation; its
only polling timer sleeps unless playing progress is visible.

Shell finish: the bar capsules no longer hardcode their own glass alpha.
`MoUI.Tokens.glassDensity()` derives it from the palette — 0.86 for the
true-black families, 0.80 for the light ones, 0.72 (the tuned reference) for
the rest including the default — so a family's finish follows its own colours
with no new channel to plumb. This replaced an attempt to vary KWin's
`NoiseStrength` per family, which was **measured inert**: 1 vs 5 and even 0 vs
30 moved 0.000 mean per-channel on the panel, because KWin blur governs what
shows THROUGH a translucent window and has no say over an alpha QML paints
itself. Do not reach for a KWin blur key to change how a MoOS surface feels.

Media island: one `MediaControl` component owns every transport control in both
representations (same geometry, resting transparency, glass fill, press-scale),
with the expanded play/pause a filled primary and prev/next ghosts. The compact
capsule is a ColumnLayout, not anchored siblings — the timeline lane and the
content row cannot overlap by construction, which three rounds of margin
tuning failed to achieve. The progress hairline is RTL-mirrored (it used to
appear to drain in Arabic) and inset from the pill's curve. Text lines carry
fixed line boxes because an Arabic-capable font's natural boxes overflow the
capsule.

Raster decode: `sourceSize` is a CAP and Qt scales it by devicePixelRatio only
for SCALABLE sources. Every MoOS mark now derives its decode from
`Screen.devicePixelRatio`; the installer and Welcome heroes were stretching 104
decoded pixels across 234 on the reference panel. The shipped
`/usr/share/moos/moos-logo.svg` is NOT a usable substitute — Qt prints
`Invalid path data; path truncated` for it and it is the posterised trace,
while the PNGs come from the 2756-path master.

First-run hardware: `moos-device-plan` already read the machine, but nothing
surfaced it on the one screen every new machine shows. `moos-firstrun` now
runs that probe in the background (atomic `.partial` + `mv`) and `moos-welcome`
passes `--device-plan=` on its own argument, so the Welcome can draw a device
card — but ONLY for an important action carrying a real URL (today: an NVIDIA
GPU running without the NVIDIA image, offering the one-command atomic switch).
A healthy machine sees no card at all, and the poll gives up after 15 tries so
the first-run screen never carries a permanent timer.

Identity gating: `verify_identity.py` used to pin the installer icon to the
literal `moos-logo`. It now asserts the CONTRACT — a MoOS-owned icon name that
actually resolves to a file in the image — which is strictly stricter, because
the old string compare never touched the filesystem and would pass a launcher
pointing at a missing icon. **CI's buildah step truncates its output, so an
image-build failure can show no error at all; build locally to see it.**

Boot hygiene: thermald exits 1 by design on non-mobile chassis, which the
stock unit turned into a red failed system unit on every desktop boot. The
image gates it with `ExecCondition=/usr/libexec/moos-thermald-supported`
(chassis + CPU-vendor judgment, inputs overridable for the gates), so
unsupported machines skip the unit cleanly and Intel laptops keep it.

This was inspected on the running 3840x2160 Wayland/HDR desktop in dark and
light, Arabic RTL and English LTR. The launcher was exercised on the actual
output at 100/125/150/200%, with 225% restored afterward. Meta, KRunner search,
Escape, and the accessibility press action toggle the production launcher.
Chrome Flatpak's real MPRIS Media Session displayed its private artwork and
accepted play/pause plus a five-second AT-SPI seek. Haruna proved active-player
handoff, previous, seek, volume, mute/unmute, and automatic return to Chrome;
after both players stopped the direct island disappeared and the bar remained
one capsule. Chrome advertises volume but ignores even direct MPRIS volume
writes, so browser volume is not falsely claimed. Stable rev-48 4K evidence is
in `docs/evidence/`; the rev-49 live captures are listed in
`docs/CONTINUATION.md`.

The complete local image is
`3c881239d49a90adffd1a56b81333387072241d36a88007e353f94e4a4a1d91f`
(`sha256:c50b9b8cd1f2e1268d6ae189849c2ba37b9d0600950081868c3a4cd001a8d1e7`,
10,774,099,532 bytes). `just check`, all real QML hosts, the 122 MiB final
initramfs proof, image-experience, store, identity firewall and bootc lint pass.

The no-network `.570` ISO run is negative but valuable evidence. Local image
copy (261 layers / 10.8 GiB), deployment and GRUB all completed, then bootc's
built-in finalizer remounted the Btrfs superblock read-only while its image proxy
still used the target-backed sibling `bootc-stage`; the installer correctly
failed at 86% with EROFS. The source now uses `--skip-finalize`, removes staging,
seeds the target, then performs trim, sync, freeze/thaw, read-only flush and
clean unmount. Gates and a full compose pass. Do not claim the fix complete
until a newly signed ISO performs a full offline install and the resulting disk
boots without the ISO.

That exact rule caught a second defect in signed ISO `.571`: the corrected
finalizer completed and the real installer displayed “MoOS is installed”, but
the same disk with the ISO removed stopped at `grub>`. The target-backed staging
layout deploys MoOS into the Btrfs `root` subvolume; the stock EFI redirect starts
at tree ID 5, so it could not find `/boot/grub2`, the BLS entry, kernel or initrd.
The installer now rewrites only that small external redirect after bootc has laid
down the signed shim/GRUB payload: it selects the `root` subvolume for runtime
paths while retaining the tree-ID-5 BLS path. This is mandatory and fail-closed.
The exact commands were proved against `.571`: the MoOS BLS entry appeared and
the installed disk reached the MoOS login greeter. Release closure still requires
the same proof from a newly signed ISO so the generated redirect, not a manual
GRUB command, is what performed the boot.

Signed `.573` closes the complete offline release gate. All three official
images built and were signed. The generic ISO installed with no NIC from its
embedded image, exposed only the target disk, reported success, and powered
off. With that ISO removed, the same target disk automatically booted MoOS with
no GRUB input and no service restart. Firstboot's AccountsService `CacheUser`
call returned `/org/freedesktop/Accounts/User1000`; the first greeter displayed
the `moos` account, its password authenticated, and the installed session reached
Welcome, the cardless Horizon desktop and the production launcher.

This final run also corrects the earlier `.572` diagnosis. Plasma Login Manager
6.7.4 intentionally fades the greeter stack to zero opacity after 10000 ms of
idle time (`GreeterState.qml` owns the timer and `Main.qml` binds stack opacity
to it). Screenshots taken after 12 seconds therefore contained only wallpaper;
ordinary input restored the account card immediately, without restarting the
display manager. The claimed AccountsService race was not demonstrated.
Firstboot's explicit, verified `CacheUser` remains harmless synchronization and
defence in depth, but must not be cited as the cause of the now-understood idle
screen. Wake the greeter before judging future visual evidence.

Official `.573` generic image digest is
`sha256:775bfc01c0ae7282fd43907b2949cbe8656757b288a7bb736d7636dbad7252d4`;
NVIDIA is
`sha256:d8c4b13b535472856a8096c03d787791d8af9d2969359d6e7f5c5db3ab37f1de`;
cloud is
`sha256:945d9390b9a612db8f305e8775285f5e053a050f7266b20e53e6324e6676ebfb`.
The downloaded ISO SHA-256 is
`50ac438aad17d9867e8901f2ad764e36f6944f7a9f98093a5986856fd240f138`.

The previous `.567` deployment facts below remain valid historical proof.

The first signed unified deployment (`44.20260808.567`) has now booted on the
owner machine and passed `tests/post-update-check.sh` 49/49. Its UEFI disk image
and signed-image-pinned offline ISO both booted in virtual hardware. The real
post-boot journal caught a launcher teardown edge the gates missed:
`DelegateModel` temporarily reports `index=-1`, which made the staggered
`PauseAnimation` negative. THEME_REV 47 clamps both ends and adds the missing
regression. Four live 4K RTL open/close cycles are warning-free, and the second
complete local image
`e1ef941cce6048cebde68cadff11383438683a20e5d676bebca516e3c980defe`
passes all image gates. Its signed follow-up publication and second boot proof
remain pending at this commit; do not confuse the first successful release with
proof of the corrective follow-up.

The interface now has the ownership chain the project previously described but
did not actually possess:

```
artwork/moos-design/tokens.json + theme-profiles.json
    -> generated org.moos.ui Design Core + generated 16-profile database
    -> moos-theme (one transactional appearance owner + exact readback/undo)
    -> shell, session surfaces, Qt/GTK, Konsole and first-party applications
```

The application-local QML component fork is gone. Launcher, Horizon Hub,
Control Center, Theme Picker, first-party apps, lock, login, splash and power
now consume the installed `org.moos.ui` module. `moos-apply-theme` is a revision
migrator/delegator, not a second theme engine. Theme state schema 2 records the
verified profile and exact encoded profile/custom wallpaper identity; all 16
profiles come from one generated manifest and explicitly own the internal Qt and
GTK engine selection as well as palette, icon, cursor, decoration, wallpaper,
Konsole and session state.

The visual change was exercised on the running 4K/HDR/NVIDIA desktop, not only
offscreen: Graphite and Tidal, Qt and GTK, Arabic RTL and English LTR, and real
output scales 100/125/150/200% (then restored to 225%). Source session previews
also loaded the real lock, logout, splash and plasmalogin component trees. The
notification service was found absent because the tray never instantiated the
notification applet; the tray inventory is now complete and a real D-Bus
notification was displayed.

Performance was fixed from measurement. The wallpaper's endless weather group
and 1.5-second telemetry interpolation kept `plasmashell` at 10.25% in Gentle
and 11.3% in Alive on the real 4K screen. The package now forbids every
`Animation.Infinite`, uses sparse finite pulses and five-second health samples:
Gentle/Still measured 0.70%; Alive measured 2.85% across a 40-second window that
included its pulse. A fresh shell settled around 513 MiB RSS versus 741 MiB
before reload. KWin's separate ~11.7% static-desktop baseline remained with
MoOS motion off and became worse, not better, when blur was temporarily
disabled; it is the OpenGL/EGL NVIDIA 4K/HDR compositor baseline, not a hidden
MoOS animation.

Fast Remote now participates in that architecture instead of installing a
second wallpaper owner. It holds the shared theme lock, asks `moos-theme` for a
temporary Still scene, snapshots the exact KWin and `kdeglobals` values
(including absence), and writes its recovery marker before mutation. A live
ON/OFF round-trip preserved `org.moos.ui2.wallpaper` and restored Alive, the
original effect values, the selected local engine and keyboard layout. The
round-trip caught an older D-Bus parser reading the `32` in `uint32` instead of
layout index `0`; the parser and acceptance readback are now gated. The
resident media island's only continuous animation was also replaced by a
finite 1.4-second pulse every 15 seconds while media is playing.

Dead top-level `desktoptheme/Nova`, orphan generators, tracked `.bak` files and
the test icon were removed and are absence-gated. Load-bearing historical ids
such as `org.moos.ui2.nova` and `org.moos.nova.clock` remain deliberately. The
branch has focused source gates, live proof, a complete green `just check`, and
two complete green local image builds. The current corrected
`localhost/moos:latest` is
`e1ef941cce6048cebde68cadff11383438683a20e5d676bebca516e3c980defe`:
the final dracut inspection found the OSTree root and MoOS Plymouth assets,
every shipped QML app and the launcher/scene loaded in their real image runtime,
and the image-experience, store, identity and bootc gates passed. The initial
signed release and its post-reboot proof are complete; the THEME_REV 47
follow-up still requires its own signed publication and boot proof.

Last updated: 2026-08-07, unified design audit slice — **the update button could never have
updated anything, on any machine.**

The background train was fixed two rounds ago and the *app* was left behind.
`moos-update` — the window Mo Store's "system update" card opens, and the one a
person opens to update MoOS — ran `pkexec bootc upgrade`. On the live Cloud host,
two builds behind at the time, that command reports:

```
No changes in: ostree-image-signed:docker://…/moos-cloud@sha256:34b5…
```

and it reports that **forever**. `bootc upgrade` cannot advance a digest-pinned
origin, and every MoOS install becomes digest-pinned the first time `moai-do
update` or the nightly `moos-auto-update` stages anything — which is by design,
because both escalate an immutable object across Polkit rather than a mutable
tag. So "Install update" was a dead button on every machine, while the machine
kept updating anyway at 04:30 and nobody could tell.

The app now carries the same contract as the other two paths: resolve `:latest`
unprivileged, accept only the three official editions (specific before generic,
or a `moos-nvidia` desktop gets rebased onto an image with no driver in it),
validate the digest SHAPE, and hand Polkit a reference the app CONSTRUCTED. It
also says, the moment it opens, when an update is **already staged** — which
nothing on the desktop did: the notifier and `bootc upgrade --check` both read
the pinned origin and see "no changes", so a finished update sat on the disk
with no way to learn it was there except rebooting.

Proven, not asserted: the new gate
(`test_updater_stages_an_exact_signed_digest_never_a_tag_upgrade`) **fails on the
old file** — `['pkexec','bootc','upgrade']` — and passes on the new one; the
updater's real functions were then run against the live registry on this machine
and correctly answered `moos-cloud` / `already on the latest signed image`, and
the app was launched on the live session without a traceback.

**The staged update is now announced.** `moos-update-ready` (user timer, 5 min
after the session settles, then every 6 h) sends ONE notification per staged
version and never repeats it — the first thing on this desktop that says an
update is waiting. It carries no restart button on purpose: a stray click on a
desktop notification must not be able to take down a session that was in the
middle of something. Proven against the machine's own staged 44.20260803.541,
and the gate catches a notifier that nags (verified by breaking it).

The updater also **no longer races another writer**: `deployment_state()` returns
the in-flight transaction from the same status call, so clicking Check while the
nightly train is staging says "an update is being staged right now" instead of
failing with "Update failed" at the rebase.

The same round removed a **health check that lied**. `moos-selfcheck` reported
"✗ plasma-ksystemstats is NOT running — every system monitor will draw an empty
box" on a machine whose monitors were fine: the unit is D-Bus activated and exits
when the desktop is covered, and one introspect call had it `active` in under a
second. It now distinguishes running / idle-but-activatable / genuinely
unavailable, and starts nothing itself (verified: still `inactive` after the
check). The host went from "1 broken, 49 passed" to **50 passed**.

What was audited and found intact, so nobody re-does it: OS image, system
Flatpaks, user Flatpaks, distrobox and firmware metadata all update on their own
timers (each one's last run confirmed in the journal); firmware APPLY stays
manual on purpose (`moai-do update-firmware`) per the anti-brick contract in
`moos-hardware-adapt`; and no driver is missing — `linux-firmware`, mesa
DRI+Vulkan, `cups`/`ipp-usb`/`sane-backends`, `bluez`, `fwupd`, `thermald`,
`rasdaemon` are all installed, the kernel log has zero firmware-load failures,
and `fwupdmgr` reports no updatable devices.

Last updated: 2026-08-03, round 7 — **the release was red, and the reason was
the trap this file warned about two rounds ago.**

`main` at `cb1807fa` did NOT build. CI is unambiguous: `moos` and `moos-cloud`
passed the identical commit and **`moos-nvidia` failed inside `build.sh`** —

```
ldconfig -p | grep -q libGLESv2.so.2   ->  GATE FAIL: … no package provides it
find /usr/lib64 -name libGLESv2.so.2   ->  (it IS on disk …)
```

The gate printed its own refutation and failed the build anyway. This is the
`producer | grep -q` / `set -o pipefail` trap round 5 documented and left
half-fixed: `grep -q` exits on its first match, the producer still has output to
write, it dies of SIGPIPE (141), and pipefail hands the PIPELINE that 141 — so a
MATCH is read as a MISS. Round 5 said "four more instances that work only by
luck"; the luck ran out on one edition of one commit, because whether the
producer has written enough to be killed is a race that depends on cache size
and machine speed.

**All ten instances in `build.sh` are now capture-first, match-second**, and the
class was proven before and after rather than asserted: with a producer still
writing, the old idiom returns `rc=141` and reports a present match as absent
3/3, the captured form is correct 3/3. Two of the ten were far worse than the
one that fired, because a match there means FAILURE, so a SIGPIPE turned the bad
condition into "all clear" — a gate that fails OPEN:

- `ldd /usr/lib/moplayer/moplayer | grep -q 'not found'` would have shipped a
  MoPlayer with unresolved libraries, i.e. a window that never appears.
- the login-defaults check for `wallpapers/Fedora` would have shipped a dangling
  login wallpaper — an identity-contract surface.

Neither had fired yet. Both were one output-size change away from firing.

The same round **retired the clipboard typing path outright** and shipped its
replacement. Arabic is typed the way a keyboard types it: select the keymap
group that carries the characters, then press the positions. Nothing is
borrowed, nothing is pasted, and every shift level is reachable — the Arabic
comma, the question mark and the diacritics included — where keysym injection
only ever reached level 1 of the active group. The user-facing clipboard feature
(copy from the PC, paste to the PC, send an image) is untouched: it was never
the problem, being used as a typing mechanism was.

**Proven on the shipped path**, driving the real helper with the real batch
shape: 12 of 12 realistic mixed sentences
(`السلام عليكم Ahmed كيف الحال ok 123`) arrived **byte-identical across 48 group
switches** — Arabic, Latin, a capital, digits and spaces. Harsher runs with a
switch on every line measured 38/38.

Three designs died to measurement first, and the sequence is the useful part:

- **The mechanism works.** With `org.kde.KeyboardLayouts.setLayout` pointing at
  the `ara` group, injected evdev POSITIONS produce Arabic byte-for-byte
  (`مرحبا` saved from a real editor), and every shift level is reachable —
  unlike keysym injection, which only ever reaches level 1 of the active group.
- **`AraKeymap.cs` is ground truth, not a transcription.** Every key of the
  alphanumeric block was pressed at level 1 and level 2 with the group active,
  one character per line into an editor; the saved file IS the table (48 level-1
  cells, covering letters, hamza forms, diacritics, `،` and `؟`).
- **Virtual-keyboard designs are impossible on this compositor.** KWin 6.7.3
  advertises no `zwp_virtual_keyboard_manager_v1` (full global list checked), so
  `wtype` and everything like it cannot work here. That closes a door earlier
  notes left ajar by recording only that `wtype` was "not installed".
- **There is no confirmation primitive for a layout switch.** `setLayout`'s own
  reply and the `layoutChanged` signal both arrive in ~0.15 ms and both mean
  ACCEPTED, not APPLIED: typing straight after either is still wrong (0/25 and
  1/30 correct). `getLayout` reports the requested value before injected keys
  see it.
- **Awaiting the portal call is not a barrier either** — it proves
  xdg-desktop-portal handled the call, not KWin, which the portal reaches over a
  second connection asynchronously. End-to-end against the real helper, 4 of 12
  words lost their tail to the German layout (`مكتوب` → `مكتوf`).
- **Every switch paints an OSD.** KWin calls
  `org.kde.osdService.kbdLayoutChanged` on plasmashell, which draws a layout pill
  across the middle of the screen — re-encoded into the video stream. Disabling
  it globally was refused: it is the same feedback the owner relies on for
  Alt+Shift at their desk. The answer is to switch rarely, not to silence it.

**What ships** stops crossing channels altogether. xkb's own
`grp:alt_shift_toggle` — which MoOS already ships and `moos-selfcheck` already
gates — cycles the group in response to ORDINARY KEY EVENTS, so injecting
Alt+Shift through the portal puts the group change in the SAME ordered stream as
the letters; neither can overtake the other. Toggling is relative, so a
swallowed chord would desync the tracked index and corrupt every later switch
(`كيف الحال` arrived `;dt hgphg`); each chord is therefore followed by a bounded
read of the group KWin actually has, which makes a lost toggle self-correcting
and re-syncs the index from the compositor instead of from our own count. That
read is safe where `setLayout` is not — it confirms state BEFORE any letter is
sent rather than racing letters in flight. Fail closed throughout: a run whose
group cannot be reached is dropped and reported, never typed on the other
layout.

Every clipboard-typing contract was MIGRATED at equal strictness, not deleted,
and each was broken once and watched go red. Two gates turned out to be
satisfiable by their own explanatory prose (they now strip comments), and two
more were passing on a substring — `TryStrokesX` contains `TryStrokes` — and now
pin exact declarations. That is the second and third time this round that a gate
was found agreeing with the wrong thing.

**RELEASED AND PROVEN ON BOTH MACHINES.** CI run `30845547536` built, pushed and
cosign-signed all three editions as **`44.20260803.537`**, verified the way this
file insists on — the registry digests all MOVED (`moos` 9f6ea0be→b6095d65,
`moos-nvidia` c5ff7b41→b8f42111, `moos-cloud` f0378d35→40ea1874) and all three
verify against the OS-enforced `/etc/pki/containers/moos.pub` — not by trusting
an exit code. The first attempt failed in the **cosign step only**, with Rekor
returning `404 getLogEntryByUuidNotFound` for `moos-cloud` and `moos-nvidia`: an
external Sigstore flake, cured by `gh run rerun --failed`. That attempt is also
what proved the build fix, because `moos-nvidia` reached the signing step at all
— its "Build image (buildah)" was green for the first time since `.535`.

The maintainer desktop has `.537` staged with `.535` retained for rollback.

**MoOS Cloud is updated, rebooted and verified**, and getting there removed a
blocker this project has carried for a week. `tailscale ping moos-cloud` reports
the direct path, and that path names the VPS's **public IP** — Tailscale SSH only
intercepts port 22 *on the tailnet*, so `ssh -i ~/.ssh/moos_cloud root@<public-ip>`
reaches the host's real sshd and needs no interactive re-auth at all. Every
previous session recorded Cloud as unreachable; it never was.

Measured on the rebooted Cloud host at `.537`: `systemctl is-system-running` =
**running**, **0 failed units**, PID 1 back in `ep_poll` (not `n_tty_write`, so
the round-4 serial-console wedge has not returned) and the last `console=` on
`/proc/cmdline` is still `console=tty0`, with `moos-cloud-console-order`
correctly skipping on its marker. Mo PC Remote runs for BOTH accounts —
`moalfarras` on 8765 and `momo` on 8766, reached through the two authenticated
`tailscale serve` mounts — each answering `/api/status` 200 with
`hostPowerAllowed:false` (the Cloud policy), and both now serve
`index-BiUZ-spc.js`, byte-identical to the bundle this repo ships, which is the
honest proof the new image is the one running. The legacy unauthenticated
`/audio` sibling mounts stay retired.

`moos-selfcheck` on that host went from **9 broken / 37 passed to 3 broken / 44
passed**. Two real defects were fixed with their own shipped tools rather than by
hand: `moos-one-store` retired a duplicate Bazaar launcher (two stores in the
menu), and `moos-apply-theme` reconciled a session wearing the generic
`MoOSUI2*` components under a `MoOSUI2Midnight` look-and-feel — the same drift
class round 4 recorded, and it needs the account's real session environment
(`WAYLAND_DISPLAY`, `XDG_SESSION_TYPE`) or every `plasma-apply-*` tool core-dumps.
The 3 that remain are artefacts of a headless virtual session (no Plasma shell to
inspect, Baloo suspended), not defects. One thing that looks broken and is not:
`momo`'s `ydotoold-moremote.service` is inactive because
`ExecCondition=/usr/libexec/moos-has-seat` exits 1 — that account has no seat, so
the uinput fallback is correctly declined.

Previous update: 2026-08-03, round 6 — **the remote's disconnect loop and the
typing that was still bad, diagnosed on the live host and fixed at both ends.**
The owner reported Mo PC Remote disconnecting repeatedly and typing still
arriving badly — and typed part of the report THROUGH the remote, garbled,
which was itself the evidence. Four parallel investigators over the live Cloud
host (the agent's own log under `~/.local/share/MoRemotePersonal/`, the
tailscaled journal, portal/PipeWire state) plus two source auditors converged
on one connected chain; every link was then confirmed by reading the code
before anything was changed:

- **The stall watchdog accepted only PONGS as proof of life** (`ws.ts`):
  under load the tiny JSON pong queues behind megabytes of frames, so the
  watchdog killed sessions that were visibly streaming — every few seconds,
  exactly under load. Any inbound message now counts, frames first of all.
- **A mid-stream resolution renegotiation fed the old decoder a new stream.**
  The width ladder's pipeline rebuild usually keeps the identical `avc1.…`
  codec string (same profile/level), so nothing reopened the VideoDecoder;
  phones that cannot follow an in-band dimension change errored, and the room
  fell to full-picture JPEG (~79 Mbit/s class) — manufacturing the congestion
  that fed the watchdog loop. The decoder now byte-compares the SPS on every
  keyframe and reopens cleanly on change: zero frames lost, no fallback.
- **The agent's 3-second frame-send bound CANCELLED `WebSocket.SendAsync`,
  which ABORTS the socket**, while its log claimed to drop one frame and
  carry on; the session then died of the next send with nothing connecting
  the two. It now aborts explicitly and says so — a saturated link becomes
  one clean reconnect instead of an unexplained death.
- **Token expiry destroyed the credential that exists to survive it.** The
  60-minute sliding TTL ends mid-session; "unauthorized" was routed through
  exitToLogin, whose logout() also revokes the trusted-device credential —
  so every hour: credential gone, PIN pad. Expiry now clears only the dead
  access token and re-decides, resuming silently through the device
  credential (`onAuthExpired`, distinct from Sign out by design).
- **iOS resume wrote into a zombie.** After backgrounding, the server has
  usually aborted the socket but the phone's object still reads OPEN; resume
  waited out the full watchdog staring at a frozen desktop. `probe()` now
  pings with a 2 s deadline on pageshow/visibilitychange and closes the
  zombie at machine speed; any inbound message (a frame) is proof of life.
- **Watching was idle.** The 20-minute idle timeout counted only injected
  input, so an owner actively WATCHING a long build was cut — as a
  deliberate exit the client does not reconnect from. Pings now count while
  the viewer reports watching=true; a pocketed phone reports watching=false
  (pagehide fires before iOS suspends) and still times out.
- **Typing was still letter-at-a-time, and the agent taxed every chunk.**
  The live agent log showed Arabic arriving overwhelmingly as length-1
  messages: the shipped 220 ms client window loses to the owner's real
  inter-letter cadence, and the agent then held EVERY chunk — even
  client-coalesced whole words — for its own fixed +140 ms gather.
  Multi-character chunks now flush instantly (the gather exists to merge
  single letters), and the agent gained the 700 ms age cap that had only
  ever existed client-side.
- **Reconnects duplicated and lost text.** onClose zeroed the typing diff
  base while the field kept its content, so the first keystroke after every
  reconnect re-sent the whole field; and flushText emptied its buffer into a
  dead socket, whose send() drops silently. The diff base now resyncs to the
  field, and unsent text queues (960-char bound, oldest kept) and delivers
  exactly once after the reconnect's hello.
- **An unconfirmed clipboard write PASTED ANYWAY** after its 300 ms budget —
  by then the selection is provably not ours, so Shift+Insert delivered the
  previous clipboard or a manager's rewrite into the middle of the user's
  sentence. It now skips the paste and logs why: a dropped word the user
  retypes beats a wrong word they never typed.

Every new contract was broken once and watched go red: three behavioural ws
contracts and a stubbed-VideoDecoder renegotiation harness in the controller
suite, the expiry-routing contract in auth-lifecycle, two new checks in
`tests/test_remote_clipboard_runtime.py`, three source contracts in the C#
suite. tsc, all 16 controller suites, npm audit (0 findings), a deterministic
`npm ci` rebuild of the shipped wwwroot (new hashed asset force-added), and
the complete 58-gate CI repo list pass locally. PWA BUILD v36. NOT verified
here: the C# suite compiles/runs in CI's image build (no local dotnet), and
the live phone experience on the new image is the owner's to confirm. Known
and deliberately not fixed this round: after a reboot, tailscale serve
proxies 8765 about a second before the agent listens — the client's existing
backoff absorbs it. Context the investigation also surfaced: 20 reboots in
2 days and two hard host crashes (journal truncated mid-write, Aug 2 22:05
and Aug 3 02:08) explain much of the past week's "it keeps disconnecting",
and the iPhone's tailnet path flapped between direct and DERP to-the-second
with the drops — network weather the fixes above are built to survive, not
erase.

Previous update: 2026-08-03, round 5 — **the deep hardware/kernel audit, and the
pipefail trap it uncovered.** Twenty agents measured the live desktop and Cloud
host across kernel tuning, hardware enablement, app→hardware paths, boot cost
and language choice; every candidate went through an independent refutation
pass and eight survived. Implemented this round:

- **Nothing watched the CPU's own speed.** This desktop once ran thirteen boots
  at 53% of its clock (turbo off, 2.5 GHz of a 4.7 GHz part, measured 1.9×
  slower single-thread); `moos-hardware-adapt` cures it with one
  `tuned-adm profile balanced` **once per image digest**, so a single tap of
  Plasma's Power Save tile re-enters it silently until the next update. Neither
  `moos-selfcheck` nor `post-update-check.sh` contained a single match for
  `cpufreq|no_turbo|scaling_max|tuned`. `moos-selfcheck` now reports the
  ceiling-vs-capability ratio and the turbo/boost switch, and distinguishes a
  laptop on battery (a correct choice, reported as a note) from a desktop
  pinned at half speed (a defect). It reports, it never enforces — overriding a
  user's Power Save is the bug this would be fixing. Live: `✓ CPU may use its
  full 4700 MHz`.
- **Every login paid 6.5 s to ask a TV about its brightness.**
  `plasma-powerdevil` was the slowest unit of the session by 2× (6.575 s vs
  3.266 s for the next), all of it libddcutil probing for DDC/CI; `ddcutil
  detect` on this desk answers `Invalid display`. `moos-hardware-adapt` (HW_REV
  3) now probes once per revision and writes
  `POWERDEVIL_NO_DDCUTIL=1` — powerdevil's own switch, not a fork — **only**
  when no display answers, and removes it again if one later does.
- **The RTX 2080 was rendering video on the CPU.** MoPlayer's crash-probe latch
  had been stuck at 2 since 2026-07-26 with nothing to re-arm it. Cleared on
  the live machine; the code-side fix (arm the probe around texture creation
  rather than process start) is written up but NOT done.
- **The one binary MoOS compiles had no hardening at all** — no PIE, no canary,
  no FORTIFY, lazy binding — alone in an image where every Fedora package
  carries the lot. Now `-fstack-protector-all -D_FORTIFY_SOURCE=3 -fPIE -pie
  -Wl,-z,relro,-z,now`, stripped (62 KB → 48 KB), with the properties read back
  off the ELF **before** the strip. Verified in the built image: `Type: DYN`,
  full RELRO.
- **MoOS Cloud respawned agetty 426 times in one boot** (2143 journal lines,
  ~5.7/min forever) on a UART the provider never wired. Neither obvious fix
  works — `systemd-getty-generator` re-creates the unit from our own
  `console=ttyS0` karg, and `Restart=on-failure` would silently kill serial
  login on hosts where the console works, because agetty exits 0 there too. The
  cloud edition now ships `ExecStartPre=/usr/bin/stty -F /dev/ttyS0` (measured:
  `Input/output error` on a dead UART, success on a live one) plus a 3-in-120 s
  start limit.
- **`lm_sensors` was not installed**, so an air-cooled tower had no way to read
  a fan speed. Added. The it87/`acpi_enforce_resources=lax` override that would
  bind the board's Super-I/O was deliberately NOT taken: it overlaps an I/O
  window the firmware's own ACPI OpRegion uses, and racing firmware for a fan
  controller violates this file's anti-overheat contract.

**The trap this round paid for** (now in `AGENTS.md`): `producer | grep -q p`
under `set -o pipefail` reports a MATCH as a failure — `grep -q` exits on the
first hit, the producer dies of SIGPIPE (141), and pipefail returns that 141.
The hardening gate insisted `__stack_chk_fail` was absent while
`readelf -sW … | grep -i stack` in the same shell printed
`UND __stack_chk_fail@GLIBC_2.4`. It cost three builds, and it was only found
because the gate was made to print its own evidence instead of being deleted.
Small producers hide it; `build.sh` has four more instances of the idiom that
work only by luck. Capture first, match second.

The **C/C++ toolchain (33 packages, 373 MiB) no longer ships** — implemented
2026-08-05 by moving the `moos-qml-shell` compile into its own Containerfile
stage (`qmlshell-build`, `FROM base` so the linked Qt6/KF6 sonames are exactly
the shipped ones — the same pattern moremote and moplayer use), so `gcc-c++` is
installed only inside a throwaway stage and never reaches the image. The old
in-`build.sh` install/remove (`dnf5 -y remove gcc-c++ …`) was why the toolchain
kept coming back; `build.sh` now only verifies the shipped binary (ldd for
`libKF6DBusAddons`, readelf PIE + `BIND_NOW`, `test -x`) and the (e0) sweep is a
firewall. Still open: rebuild all three editions and boot them to prove the
sweep reports zero removals and every app's QML still loads. Firefox also
decodes every video in software; the only measured cure needs
`MOZ_DISABLE_RDD_SANDBOX=1`, which removes the sandbox from the process that
parses untrusted media — not shipped by default, and not shipped quietly.

Previous update: 2026-08-03, round 4 — **the serial console froze a live MoOS
Cloud, and the karg order was ours.** The owner reported the VPS "went slow and
stopped opening apps after the update". It was not the update and it was not
load: load average was **0.02** while PID 1 sat blocked inside `write(2)` —
`/proc/1/stack` read `wait_woken → n_tty_write → iterate_tty_write →
redirected_tty_write → vfs_writev`. MoOS Cloud passed
`console=tty0 console=ttyS0,115200n8`, and the kernel gives `/dev/console` to
the LAST `console=`, so every console write went out the emulated UART. With
nothing draining that port on the provider side its ring filled and the write
blocked forever. A systemd stuck in `write()` answers no D-Bus and reaps no
children: `systemctl` hung, dbus-activated services hung, nothing could launch,
and a zombie `rpm-ostree` from the owner's own update sat unreaped — the exact
reported symptom, from a machine that was 99.98% idle.

The order is now `console=ttyS0,115200n8 console=tty0`. The kernel writes to
EVERY `console=` device, so the serial boot log — the reason the karg exists —
is untouched; only `/dev/console` moves, onto a virtual terminal, which writes
into a screen buffer and cannot block on a consumer that is not there.
`serial-getty@ttyS0` still serves an interactive serial login. Because bootc's
kargs.d diff sees an unchanged argument SET, installed machines would never get
the reorder, so `moos-cloud-console-order` (one-shot, marker-guarded,
transaction-aware) rewrites the live kargs through rpm-ostree exactly once and
never reboots by itself. `tests/test_cloud_console_order.py` holds both halves
and was broken-once to prove it bites; it runs the repair script against a fake
`/proc/cmdline` and a recording `rpm-ostree`.

The same round fixed three Mo PC Remote defects found by adversarial review of
the six commits the owner had just pushed, each confirmed by an independent
refutation pass: **(1)** pointer events never flushed the text coalescing
buffer while key events always did, so a tap inside the window — five times
wider since `CLIPBOARD_FLUSH_MS` went 45 → 220 ms — was delivered before the
queued word and pasted it into whatever the tap had just focused;
`down`/`click`/`dblclick` now flush on both the client and the agent
(`move`/`scroll` deliberately do not). **(2)** the coalescing debounce re-armed
on every keystroke with no size or age bound, so continuous input (dictation,
swipe typing) could hold a growing buffer indefinitely and lose it on a dropped
socket; it is now capped at the agent's own 240-char gather and 700 ms.
**(3)** the autocorrect middle-diff walked the caret with `ArrowLeft`/`Right`,
but Qt's default LogicalMoveStyle makes ArrowLeft move *forward* inside an RTL
run — on Arabic that deleted the shared suffix and dropped the replacement at
the end, re-scrambling the text this very series set out to fix; bidirectional
text now rewrites the whole tail, which needs no arrows. Two new contracts in
`coordinates.test.ts` hold the flush parity and the bidi guard, both
broken-once. The shipped `wwwroot` bundle was rebuilt and its new assets
force-added (the tracked-bundle gate caught the omission).

**RELEASED AND PROVEN ON THE SERVER.** CI signed all three editions as
`44.20260802.524` (verified by run conclusion and by moving digests — the first
attempt's `gh run watch` exit code lied, and the run had in fact failed; see
below). The Cloud host was power-cycled by the owner, upgraded to `.524`, and
its live kargs repaired. Measured on the recovered machine: the last `console=`
on `/proc/cmdline` is now **`console=tty0`**, `/proc/1/stack` is back in
`ep_poll` (systemd's normal event loop, not `n_tty_write`), `systemctl
is-system-running` returns **running**, zero failed units, `systemd-run`
starts transient units at both system and user level — the owner's actual
complaint — and the shipped `moos-cloud-console-order` ran on that boot and
logged `safe ordering already: /dev/console is tty0`, i.e. the repair unit
works and correctly no-ops. Memory 11 GiB available of 15, load 0.46. The
desktop has `.524` staged.

The post-update check on that recovered host then found the round's second real
defect: **root was running Mo AI on the desktop user's ports.** `60-moai-ports`
only prints an offset for uid >= 1000 and `exit 0`ed silently below it — the
identical fail-OPEN shape it was written to close for uid >= 1010, because a
service with no override falls back to its built-in 8080/8079/8077, which ARE
uid 1000's ports. On the Cloud host root has a real login session, so its user
manager started `moai-agent-api`, which sat in a restart loop on
`[Errno 98] Address already in use` (that is the *benign* outcome; the harmful
one is root winning the race and owning uid 1000's front door as root — a
loopback API that shells out to `openclaw` and `systemctl --user`, reachable by
every local account, since the `X-Moai-*` headers guard against web pages and
not against another user on the same machine). Fixed in two layers:
`ConditionUser=!@system` on all eight Mo AI/OpenClaw user units so they never
start for a system account, and the generator now hands uid < 1000 a private
`19077-19080` band instead of nothing. Verified by running the new generator as
uid 0 on the live server (`MOAI_AGENT_PORT=19077`) and by clearing root's
failed unit there. `tests/test_moai_ports_fail_closed.py` had encoded the
fail-open assumption (`uid 999 must emit no ports`); that contract is migrated
to the stronger one and broken-once against the old behaviour.

The third defect the same check surfaced was **a reconcile that could never
converge**. `moos-apply-theme`'s steady-state wallpaper readback parses `gdbus`
output with `grep -oE 'WPV:[^"]*'`, but gdbus quotes strings with SINGLE quotes
and wraps them in a tuple — `('WPV:/usr/share/wallpapers/MoOSUI2Arena',)` — so
the extracted value kept a trailing `',)` and could never equal the package it
had just written. Every login on the Cloud host logged
`steady-state: desktop wallpaper '…/MoOSUI2Arena',)' != '…/MoOSUI2Arena' —
healing` and re-applied a scene that had never drifted. The character class now
excludes `'` as well, and `tests/test_theme_wallpaper_readback.py` drives the
SHIPPED function against a stub gdbus (real reply, double-quoted reply, empty
reply) rather than asserting on the shape of a regex; broken-once against the
old extractor. The same Cloud session was also wearing the generic dark
components under an Arena look-and-feel (scheme `MoOSUI2Dark`, icons
`MoOSUI2`, decoration `__aurorae__svg__MoOSUI2`, and `moos-warning-symbolic`
resolving to *missing*) — the reconciler's Arena branch was correct, it had
simply not run in that virtual session. Running the fixed script there brought
all four onto `MoOSUI2Arena`, and `post-update-check.sh` went from **43/6 to
47/2** (the two remaining are a `kiconfinder6` display race and the tool-name
probe, both artefacts of a headless virtual session, not defects).

One process lesson from this round: **`gh run watch --exit-status` returned 0
for a run whose three jobs all failed.** The failure was real — the previous
commit shipped a `wwwroot` bundle built against stale `node_modules`, and the
reproducible-build check rejected it (`npm ci` produces different bytes from
the same source). Trust `gh run view --json conclusion`, and confirm a release
by watching the registry digests move — not by an exit code.

Previous update: 2026-08-03, round 3 — **the Arabic typing race, found by
testing it live instead of reasoning about it.** The owner rejected the
previous round's claim and demanded the fix be proven on the machine first.
Injecting three Arabic words on the live Cloud session through the real
compositor, exactly as the agent does it — `wl-copy` then Shift+Insert —
produced `" في مشكلة "`: **the first word was gone entirely**. The same three
words with a read-back between the copy and the paste produced
`"لسى في مشكلة "`, intact. Root cause: `wl-copy` returns as soon as it has
forked the process that will SERVE the selection, not when the compositor is
handing that content to readers, so the paste raced the copy and delivered
the previous clipboard (or nothing). `ClipboardBridge.SetTextConfirmed`
now reads the clipboard back until it serves what was set (12 × 25 ms, then
pastes anyway so a clipboard manager can never hang typing) and the typing
path uses it; the unconfirmed `SetText` remains only for RESTORING the user's
own clipboard after a borrow, where nothing races it.
The same live evidence exposed a second reorder that round 2 had introduced:
a space is ON the fast keysym path, so while Arabic letters waited in the new
140 ms paste buffer the space was injected immediately and landed a letter
early — `"لسى في"` arriving as `"لس ىف"`. Whatever is gathering now owns the
order: text arriving while a paste is pending joins the buffer even when it
could take the instant path. Both contracts are gated in
`tests/test_remote_clipboard_runtime.py` and in the C# suite.

The fix was then STRESS-PROVEN on the same live session: eight Arabic chunks
injected back-to-back at full speed with the confirmed write arrived
character-for-character identical to the source
(`لسى في مشكلة بالكتابة و الشاشة تعلق كثير`), where the unconfirmed path had
lost a whole word from three. Two other injection routes were tested and
rejected on evidence, so nobody re-chases them: `wtype` is not installed, and
`ydotool type` delivers only the spaces of an Arabic string — the clipboard
is the only path that carries Arabic on this compositor. Finally the client's
non-Latin coalescing rose 45 ms → 220 ms: 45 ms was SHORTER than the gap
between two letters of ordinary typing, so every letter still paid for its
own clipboard borrow; 220 ms is longer than that gap and shorter than a pause
between words, so a word becomes one borrow. BUILD v35.

Last updated: 2026-08-03 — **Mo PC Remote round 2, from the owner's own
evidence.** The owner tried to type this session's report THROUGH the remote
and the message arrived scrambled with letters missing — that garbled text is
the bug report. Root cause: Arabic (and anything with no level-1 Latin
keysym) types by borrowing the clipboard, and the phone sends text as it is
typed, so one Arabic word was one wl-copy + wl-paste + Shift+Insert cycle PER
LETTER. Those cycles overlap at real typing speed on a single shared
clipboard slot, so letter N+1 replaced the clipboard before letter N had been
pasted — scrambling and dropping characters while the subprocess load
stuttered the session. Fixed by coalescing: chunks gather for 140 ms (or 240
chars) and ONE paste delivers the run, with KeyTap/KeyDown/Combo flushing the
buffer first so Enter/Backspace/arrows can never overtake pending text (the
Shift+Insert combo is exempt — it IS the delivery). A word is now one
clipboard cycle instead of six.
Second: the two-finger recogniser is retired, not tuned. It picked ONE mode
per gesture from whichever accumulator was larger after 10 px and lived it
out, so a pinch that also drifted latched to "scroll" and never zoomed —
"hard to control with two fingers". Now spreading always zooms (past an 8 px
engage threshold that keeps scroll jitter from creeping the picture) and
translating always moves, panning overflowing axes and scrolling the remote
on fitted ones, both in the same frame. Third: the typing bar outlived the
keyboard that justified it — every control inside defends focus, so a real
blur means the phone dismissed its own keyboard; the bar now leaves with it
instead of covering the screen with something the user could not remove.
BUILD v33; bundle rebuilt and tracked; typecheck, controller tests and the
five affected gates pass.

Last updated: 2026-08-02, late night — **Mo PC Remote usability overhaul**
(owner report: typing freezes the picture, zoom/pan feel dead, always blurry,
worst on MoOS Cloud). Root causes found by tracing, each fixed at source:
(1) the portal helper injected EVERY key via synchronous D-Bus on the input
thread — a burst serialized at compositor pace while KWin was also being
hammered; injection is now fire-and-forget async (ordering preserved by GDBus)
with the failure threshold 5→20 so a transient compositor hiccup no longer
kills the helper into a JPEG rebuild. (2) The phone's autocorrect diff deleted
the WHOLE line and retyped it (up to 300 Backspaces); it now keeps the common
prefix AND suffix and rewrites only the middle (ArrowLeft/Backspace/text/
ArrowRight), with the resync cap 300→48 and Backspace/Delete hold 12→4 ms.
(3) The RTT auto-ladder read its own injection load as a bad network and
dropped quality exactly while typing — it now ignores samples within 1.5 s of
input bursts, and its floor is Balanced: auto can never park the session on
Data saver. (4) The pinch recogniser's one-shot latch (10 px) is upgradeable
mid-gesture (spread > 28 px and 1.4× travel), so a drifting pinch zooms
instead of latching to scroll forever; a one-tap Zoom toggle joined the
toolbar. (5) Zooming now lifts the preset width ceiling to the hard 2560 cap
(inspecting detail is an explicit request), the request floor rose 480→720,
quality/auto/view choices persist across sessions, and the two lowest presets
became readable (Data saver 960/q45→1024/q52, Balanced q62→68). x264enc and
openh264enc are confirmed present on the Cloud image, so H.264 (not JPEG) is
the software path. BUILD v32; bundle rebuilt, force-added and gate-verified;
controller typecheck+tests pass; the seven targeted remote gates pass. Agent
C# tests run in CI's image build (no local dotnet).

Last updated: 2026-08-02, night — **the Tidal arc is retired everywhere**

Previous update: 2026-08-02, night — **launcher polish round on branch
`product/launcher-polish-2026-08-02`** (this entry; rebased onto the Tidal-arc
retirement below, whose release `71d1b466` is already signed). The owner
could not name the launcher's icon-only session buttons by hovering: all nine
`PC3.ToolTip.text` declarations in `LauncherView.qml` lacked the
`ToolTip.visible` binding QQC2 requires, so no tooltip ever appeared — fixed
with `visible: hovered` + `Kirigami.Units.toolTipDelay` on all nine. Two glyphs
lied: logout wore the external-link box and switch-user the identity spark;
both now use the family's own `moos-logout-symbolic` / `moos-user-symbolic`.
Mo AI's appearance page asked for `moos-themes-symbolic`, an icon that never
existed (blank button) — now `moos-ui-symbolic`. Three new UX-gate contracts
hold all of this (tooltip text↔visible parity per QML file; every `moos-*`
icon name on an icon-bearing QML line must resolve in a shipped inventory —
this contract is what found the dead Mo AI icon; the session-strip glyph map
is pinned), each broken once and watched go red. The application marks gained
a restrained 9-layer liquid-glass plate (crisp top edge, liquid horizon band,
deeper bottom depth; sheen tamed so the palette colour saturates the whole
tile) — regenerated masters/ladder plus all 14 palette overlay bakes;
`tests/test_moos_app_icons.py` (contrast + pixel proofs) passes unchanged.
THEME_REV=29 delivers it to existing sessions and additionally purges home
shadows of the three first-party plasmoids (`org.moos.brand`,
`org.moos.heroclock`, `org.moos.nova.clock`) — a preview-litter class no
earlier revision cleaned. The same session's live audit found **background OS
updates silently dead on every digest-pinned install** (uupd's `bootc
upgrade` cannot advance the digest-pinned origin `moai-do update`
deliberately writes; the maintainer desktop was exactly this) — new
`/usr/libexec/moos-auto-update` + 04:30 Persistent timer, enabled for every
edition by build.sh, resolves the official `:latest` to an exact digest
nightly and stages it through the signature-enforcing transport, skipping
cleanly when rpm-ostreed is busy; `tests/test_moos_auto_update.py` proves the
argv boundary with command doubles and joins `just check` and the CI Repo
gates. On the maintainer desktop, the stray local `crd-test`/`moplayer-dev`
distrobox launcher entries were moved to
`~/.local/state/moos/launcher-cleanup-20260802` (machine-local, never image
content). `just check` passes end to end; the generic image built locally
with every gate green before the rebase. A live home preview (plasmoid +
NovaLight overlay) is installed on the maintainer session for owner
verification and is exactly what the v29 purge removes after the signed image
boots.

Previous update: 2026-08-02, night — **the Tidal arc is retired everywhere**
(owner verdict on the live system: the full-screen curve reads cheap and
appears in every surface — it is gone, not tuned). Removed from: Logout (16
packages), Splash (master + 16), Lock, the Login greeter scene, and the
first-party apps (Store, Mo AI ×2, Settings) — 36 TidalHorizon.qml files
deleted including the canonical master and the apps' MoOSUi variant;
`generate_login_scene.py` no longer syncs a portal. The splash was
re-composed around a centred brand + progress line (same finite reveal
contracts, 460/260 durations kept). The lock lost the arc's one gated fade —
its duration count contract is now 5 (was 6). Five gate files migrated to an
explicit anti-regression: no `TidalHorizon` may ship or be referenced from
any session surface or app (`test_tidal_portals` now bans instead of syncing;
`test_tidal_horizon` bans in apps; `verify_user_experience` splash/logout/
lock/login requires inverted; `test_moos_ui2` byte-sets and splash static
frame pruned; Mo AI ambient contract is the still gradient field). The
affected suites all pass; untouched suites are covered by the 70/70 run on
`b260174b` per the owner's no-redundant-verification rule (see
memory/owner-work-discipline). The session identity is now purely the dark
Glass Island: material, two-tone rim, crest tick.

The same session's live audit found that **background OS updates were silently
dead on every digest-pinned install**: `moai-do update` deliberately stages an
exact digest (the Polkit boundary escalates only an immutable object), but
uupd's nightly `bootc upgrade` cannot advance a digest-pinned origin — the
maintainer desktop's bootc spec tracks `moos-nvidia@sha256:…`, so the enabled,
green uupd timer updated Flatpaks and never the OS. The cloud host only
advanced because its origin still tracks `:latest`. New
`/usr/libexec/moos-auto-update` (+ service and 04:30 Persistent timer, enabled
by build.sh for every edition) is the missing train: nightly unprivileged-shape
resolve of the official `:latest`, official-editions allowlist (including
moos-cloud), digest-shape validation, then an exact-digest
`rpm-ostree rebase ostree-image-signed:docker://…@sha256:…` as root, skipping
cleanly when rpm-ostreed has a transaction in flight.
`tests/test_moos_auto_update.py` proves the argv boundary with command doubles
(exact digest, no foreign origins, no invalid digests, no racing) and is wired
into `just check` and the CI Repo-gates list. Live verification of the timer on
a booted image is pending the next release boot.

Previous update: 2026-08-02, evening — **the Complementary correction: the fix
that makes the session islands actually read.** After the design image
`44.20260802.512` booted, the live lock still rendered a pale ghost card on
Scholar Light and the owner rightly reported "nothing changed". Root cause:
MoOS light schemes declared `[Colors:Complementary]` as their OWN light
canvas, while KDE's semantic (and Breeze's practice) makes Complementary the
DARK session surface — lock, logout, OSD — on every palette. All the
Glass-Island work keyed off Complementary, so on light themes it dissolved.
`generate_moos_ui2.color_scheme()` now renders Complementary from the
family's dark sibling wholesale (backgrounds AND foregrounds, via
`session_sibling()`: `<fam>-light`→`<fam>`, `light`/`daylight`→`dark`), and
`generate_moos_themes.color_scheme_for()` registers the sibling palette
before rendering. Only the light members' schemes/desktoptheme colors
changed on regeneration. That flip exposed a latent conflation in
`moos_ui2.py::palette_from_color_scheme`: `on_negative` (the ink ON a
destructive fill in NORMAL windows) was read from Complementary's
background — historically identical to the light canvas, now dark — pairing
2.69:1 on AmethystLight; it now reads the scheme's own View canvas, which is
what the hand-written palettes always meant. A caveat for future previews:
`qml-qt6 + QT_QPA_PLATFORMTHEME=kde` does NOT apply KDE color schemes, so
every harness render wore the Fusion fallback (dark grey + stock blue) —
which is WHY the harness showed handsome dark islands while the real
session showed ghosts. Harness renders prove geometry/material only; colour
truth needs a real KDE process on a booted image. Prepending the repo share
to XDG_DATA_DIRS for `kscreenlocker_greet` does not work either (partial
shell package → fallback greeter). 70/70 gates pass with the corrected
schemes.

Previous update: 2026-08-02 — the complete `push-temp` line (86 commits: the
remote security/lifecycle/accessibility audits, the Tidal portal restoration
after the rejected glassmorphic pass, theme rev 28, bounded Mo AI service
lifecycles and the CI gate sync) is fast-forwarded onto `main` as
`563a9724552e6fb76371155e2828c4edadeb70fd` and pushed. The push was initially
rejected because the stored OAuth token lacked the `workflow` scope (the
commits change `build.yml`); the owner authorized a device-flow refresh —
codes were delivered over the linked WhatsApp channel because Telegram is
currently unconfigured (see below). The exact tree also composed locally on
the Cloud host as `localhost/moos-cloud:latest` (`5ebbababbfcc…`) with every
image gate green, before CI ran. GitHub Actions run `30748263893` is the
release run for this head: **completed success** — all three editions built,
pushed and cosign-signed, then verified again from the Cloud host against the
OS-enforced `/etc/pki/containers/moos.pub`:
`moos@sha256:968c8aa63f58…`, `moos-cloud@sha256:df0c922d71c5…`,
`moos-nvidia@sha256:72264234f54b…`. The full 70-command check recipe was
re-run on the merged head after the push: 70/70. The Cloud host staged
`44.20260802.508` (`df0c922d…`) via `bootc upgrade` with the previous
deployment retained for rollback.

The reboot into `44.20260802.508` completed and `post-update-check.sh` now
returns **49 passed / 0 failed** on the Cloud host. Getting there surfaced and
fixed three more real defects: (1) the check itself hardcoded
`moos-nvidia:latest` as the registry comparison, so every healthy Cloud or
generic machine reported a false "reboot did not take" — it now derives the
reference from the booted deployment; (2) the HOME shadows and the three
self-described TEMPORARY unit drop-ins were moved to
`~/.local/state/moos/post-update-backup-20260802-release` and the three
affected services restarted onto image binaries; (3) the desktop wallpaper
reverted to `MoOSUI2Graphite` across the reboot while the theme stayed
`Scholar Light` — root cause still open (the steady-state marker deliberately
does not reconcile a package-level wallpaper drift; a THEME_REV=29
reconciliation that heals MoOSUI2-package drift while preserving deliberate
custom image files is the planned fix). The live shell was reconciled through
the Plasma scripting API and disk state confirmed.

Live Cloud-host repairs on 2026-08-02, before the release landed:

- **Theme drift healed.** The session's chosen look was `MoOS Scholar Light`
  (`org.moos.ui2.study.light`) but the desktop wallpaper was
  `MoOSUI2Graphite`: the shipped THEME_REV=27 marker short-circuited before
  any wallpaper check, exactly the defect rev 28 fixes. Running the repo's
  rev-28 `moos-apply-theme` on the live session migrated both desktop and
  lock wallpapers to `MoOSUI2ScholarLight`; `post-update-check.sh` moved from
  45/4 to 46/3.
- **Unauthenticated `/audio` tailnet mounts retracted again.** The booted
  main-line image still re-creates the legacy `tailscale serve /audio`
  sibling mounts that `efaa3c98` (now on `main`) retires. Both mounts (443
  and 8443 listeners) were retracted live; sound flows only through the
  agent's authenticated one-use-ticket proxy. The next booted image stops
  recreating them.
- **Telegram channel is dead on the live gateway and the bot token is
  unrecoverable.** `openclaw doctor --fix` (run by a prior session on
  2026-08-01 01:11, per `~/.openclaw/logs/config-audit.jsonl`) reset
  `channels.telegram` to scaffold defaults: token gone, `allowFrom` emptied,
  `dmPolicy` back to `pairing`. No file on the host still contains the token.
  The owner-only restriction (`allowFrom:[1142563280]`, `dmPolicy:allowlist`)
  was restored on disk immediately; the owner was asked over WhatsApp to
  re-enter the BotFather token (Mo AI Settings → Telegram). WhatsApp remains
  linked and delivering (used for all owner notifications this session).
  `moai-wake` handles the missing token quietly (no restart loop).
- **moos-admind never existed in the tree.** The 2026-07-29 design was never
  committed on any branch (`git log --all -- '**/moos-admind'` is empty); the
  shipped answer to the same problem is OpenClaw's four permission levels,
  the Gateway exec-approval queue and the audit ledger. Do not look for
  `moosctl`.
- **HOME shadows and temporary drop-ins are scheduled for post-boot removal,
  not before.** `~/.local/bin/{moai-brain-mode,moai-code,moai-screenshot,`
  `moai-openclaw-preflight}`, the `org.moos.moai.desktop` override, and the
  self-described TEMPORARY drop-ins on `moai-gateway`, `moos-ensure-brain`
  and `openclaw-gateway` all point at repo copies whose fixes are baked into
  the new image. Removing them while the old image is still booted would
  revert live fixes (main's preflight lacks `is-active --wait`); they must be
  moved to a recoverable backup only after the new deployment boots.

Session-surface redesign, slice 1 — later on 2026-08-02, working tree: the
Logout/Restart/Shutdown doorway is rebuilt around a **Glass Island** — one
layered-material card (fill 0.58 + sheen + neutral border + two-tone accent
rim + three-step depth halo, all scheme roles, zero hex) that carries emblem,
clock, date, question, identity chip, a Shape-arc countdown ring (the naked
hairline is retired) and a dock of second-generation tiles whose captions live
INSIDE the key surface (8.6×6.2 grid units, max four columns, 3+3/4+3/4+4
balanced wraps). The Tidal Horizon keeps its exact reviewed geometry but now
frames from BEHIND the island at intensity 0.55 — never through the content.
Cancel is a full-width quiet text pill under a hairline. All contracts kept:
signals, armOrFire two-step, moveFocus grid arrows + RTL inversion, Escape,
exactly three `cancelRequested()` sites, Accessible role/name/description/
pressed/onPressAction, `longDuration > 1` motion gating. The three constraint
gates were MIGRATED to pin the new contract at equal strictness
(`test_tidal_portals` island/ring/tile tokens, `test_moos_ui2` four-column
wrap table, `verify_user_experience` island tokens + indentation-robust
fill/rim regexes). All 16 packages resynced via `generate_login_scene.py`;
the complete 70-command check recipe passes. Live 1080p evidence on the Cloud
session (llvmpipe, real qml-qt6 + spectacle, per-palette schemes via the new
`artwork/moos-ui2/preview-harness/make-preview.sh`):
`artwork/moos-ui2/live-tests/redesign-2026-08-02/` holds before/after pairs —
dark restart/halt/picker, Scholar-Light restart (Complementary island), and a
full Arabic RTL picker with correct mirror flow. Slices 2+3, same session: the LOCK island and the LOGIN components now wear
the identical language. The lock's authCard adopts the Complementary set (a
deliberate dark glass slab on light palettes too, exactly like the power
island), fill 0.58, unified 2-unit radius, sheen, and the same still
three-step depth halo; the redundant accent pool was retired and the Tidal
arc calms to 0.55 while the card is up so it frames from behind instead of
cutting through (its previous 0.88 visibly crossed the translucent card).
MainBlock inherits Complementary at its root — visual only, the auth path is
untouched and its 8 gated durations are unchanged (LockScreenUi stays at
exactly 6, breeze ActionButton at exactly 4). The shared breeze ActionButton
becomes a real tile (6.6×4.8 grid units) whose caption sits INSIDE the key
surface (elide, single line) — this reskins the lock's Sleep/Switch User row
AND the compiled login greeter's power row at once. The greeter scene's
package resolver finally honours the *Light families (an existing
ScholarLight lock previously faced a Graphite-dark login background from the
same package). The complete 70-command recipe passes after these slices.
Splash remains deliberately unchanged this round (one reveal + progress,
already on-language). Live lock/login captures on a booted image remain the
required visual evidence and are the next step after CI.

Previous update: 2026-08-01 — the Mo AI Workspace rebuild is merged on `main`,
published and booted. GitHub Actions run `30704582346` built, pushed, cosign-
signed and verified `moos`, `moos-cloud` and `moos-nvidia` from merge
`77707fd1461774b931518df14a418e9286251ba4`. The maintainer machine is booted
from signed NVIDIA digest
`sha256:c73d9002efb3db9ffc2c6c2d4a7141b17d8af5e283172adb3c2790dccc0731e7`
with kernel `7.1.5-201.fc44.x86_64`; the previous deployment remains available.

Working-tree correction, later on 2026-08-01 (`push-temp`): the unpublished
`0a6a05d3` glass pass replaced the reviewed Tidal Cut doorway with a full-frame
`Qt5Compat.GraphicalEffects` DropShadow (65 samples plus an offscreen layer) in
Splash, Login, Lock, Logout and first-party apps, then changed three regression
gates to require that implementation. This was an identity and GPU-cost
regression, not accepted polish. Commits `2811e138`, `b2ddb444` and `c0154aa0`
restore the code-native Qt Quick Shapes horizon and make the gates require its
cut/gradient geometry again across all 38 synchronised copies. The Cloud-hosted
repo gate suite passes by executing the complete `just check` recipe directly
(`just` itself is absent). Minimal Cloud Python also exposed two real portability
defects: DOCX/ODT MIME detection depended on a host MIME database (`a7dc930b`
now recognises the three supported document suffixes deterministically), and two
runtime gates crashed on a partial non-PyGObject `gi` namespace (`41c40bf4`,
`b2ddb444` now retain their pure contracts and skip only unavailable GTK/KDE
runtime checks).

Logout/Power responsive-layout follow-up: the command island is capped at 50
grid units, but its action dock was one unwrapped row that could contain eight
seven-unit cells when update, suspend and hibernate actions were all available.
That geometry overflowed before accounting for spacing and was especially bad
under fractional scaling. All 16 look-and-feel packages now share a responsive
`GridLayout`: at most five columns, with balanced 3+3, 4+3 or 4+4 rows for six
to eight actions and a width-derived lower cap. Arrow navigation now moves by
one column horizontally, by the actual column count vertically, and mirrors
only horizontal movement in RTL. Vertical movement leaves an incomplete edge
for the real Cancel control rather than wrapping to an unrelated top-row action;
Cancel returns to a deterministic dock edge. A regression test exercises every 1–8 action
shape and guards the directional accessibility contract. The 28 UI2 tests,
user-experience gate and complete repository check pass. This is source/gate
evidence only; live Qt rendering at fractional scales remains required.

Login/lock assistive-name follow-up: Plasma's real shared `ActionButton.qml`
received labels containing KDE mnemonic markers such as `Slee&p` and
`&Hibernate`, but its explicit `Accessible.name` exposed the raw string. The
visual caption already used Kirigami's parsed mnemonic data, so screen readers
and sighted users were given different labels. Accessibility now consumes
`MnemonicData.plainTextLabel`, the official plain-text property that removes
markup and `&` markers, while the visible underline and Alt shortcut remain
unchanged. The UI2 regression gate rejects returning to `root.text`; all 28 UI2
tests, the user-experience gate and the complete repository check pass. This is
source evidence only; a live screen-reader pass on the composed image remains
required.

Session assistive-activation follow-up: the custom Logout/Power portal key and
the lock screen's Unlock button declared accessible roles, names and pressed
state but no `Accessible.onPressAction`. An assistive client could discover the
control yet have no explicit activation route. Logout keys now call Qt 6.11's
`animateClick()`, emitting the normal `clicked` signal; therefore Restart and
Shutdown still enter the existing `armOrFire` two-step confirmation and cannot
be invoked through an accessibility bypass. Unlock calls the same `clicked`
signal as Enter/Return. All 16 generated logout copies are byte-identical, the
UI2 gate requires both handlers, and the 28 UI2 tests plus the complete repository
check pass. Live assistive-technology activation on the composed image remains
required evidence.

Mo PC Remote's available source gates pass for capture rebuild
coalescing, non-blocking input, resolution negotiation, H.264 fallback/restart,
authenticated sound, private Cloud desktop, PIN ownership, subids and per-user
ports. This Cloud environment has no Node/npm, .NET, systemd, Qt/KDE runtime or
display, so controller compilation, image compose, live phone control and new
Light/Dark × RTL/LTR × 4K captures remain explicitly unverified in this round.
The same round later gained a real isolated Node build environment verified
against Node's published SHA256 for the current LTS `v24.18.0`. Mo PC Remote's
controller now cancels generation-bound reconnect timers on logout/unmount
(`1ac17902`), closing a ghost-socket path that could restart streaming after the
screen had exited. Its committed PWA was rebuilt deterministically after moving
to React 19.2.8, Vite 8.2.0, TypeScript 7.0.2 and vite-plugin-pwa 1.3.0
(`d66a3ff6`); `npm ci`, controller tests, `tsc --noEmit`, two byte-identical
builds and `npm audit` (0 vulnerabilities) passed. CI now enforces typecheck and
audit before comparing the shipped bundle. `@vitejs/plugin-react` remains on
5.2.0, the newest cleanly resolving line that supports Vite 8; 6.0.5 currently
has an unsatisfied Babel 8 peer graph and was not forced with legacy resolution.
Cloud audio cleanup is bounded after both TERM and KILL, and Mo AI activity
stamps use unique atomic temporaries under concurrent requests (`9f120c27`).
Two duplicated troubleshooting reports that exposed an owner phone number and
an unsafe allow-all example were removed; `tests/test_docs_privacy.py` now gates
the repository and CI (`2877c228`). The complete repo `just check` recipe passes
after these changes. Image compose, installed-service proof and a real phone
session remain open.

Session/login/power accessibility correction, later in the same unpublished
Cloud audit (`4073365e`, `e5c18d9b`, `2c298613`, `d51a1252`): the shared logout action had a visible keyboard focus ring,
four-direction navigation, a name and a description, but relied on
`AbstractButton` to infer its assistive role while running in ksmserver's
out-of-process greeter. All 16 theme copies now explicitly expose
`Accessible.Button` and their transient pressed state. A repository gate holds
the role, name, description, pressed state, strong focus policy and arrow-key
contract. The complete `just check` recipe passes. This is source/gate evidence,
not a live screen-reader claim; Qt/KDE runtime and live Light/Dark × RTL/LTR ×
4K verification remain open on an installed image. The lock screen now follows
the same explicit contract: Password has a stable accessible name and Unlock
exposes Button role plus pressed state, while preserving its real PAM path. The
actual Plasma Login Manager components now expose the same complete contract.
Most importantly, UserDelegate's inert `function accessiblePressAction()` was
replaced by the Qt-supported `Accessible.onPressAction`, so assistive activation
selects a user through the same real click signal; Enter and Return now match
Space. The compiled greeter's shared action button also routes assistive presses
through its existing `animateClick()` path.
The greeter's four button transitions and three user-selection transitions now
also resolve to a literal zero duration when `AnimationDurationFactor=0`; both
components are registered in the real Qt motion-gate test. The Cloud source gate
passes, while the runtime branch remains explicitly pending an image environment
with Qt/KDE and `kwriteconfig6`.
The same audit then closed the lock surface (`ebcebc57`): all eight auth-card
transitions and six scene transitions are explicitly duration-zero when motion
is disabled, and a repeated authentication notice no longer starts its bounce.
PAM, grace timers, password bindings and unlock signals remain unchanged. Both
lock files are now held by the real Qt motion-gate test; the complete repository
check recipe passes on Cloud, with its Qt runtime branch honestly skipped.

Mo PC Remote server proof, later in the same Cloud audit: Microsoft’s temporary
.NET 10.0.302 SDK ran the exact Containerfile test (`21` mapping, validation and
Unicode checks) and published the Linux agent self-contained in Release with no
compiler warnings. The resulting 109 MB distribution was launched on isolated
loopback port `18765`; a real HTTP sequence proved fresh status, PIN setup,
token revoke/logout, rejection of a wrong PIN, successful login, and delivery
of the committed React PWA. Its config landed mode `0600`. `MOREMOTE_DATA_DIR`
is now an explicit absolute-only service/container boundary with a deterministic
per-directory mutex, so an isolated validation instance cannot read the owner's
live configuration or be suppressed by the live agent (`65ac6d71`). A relative
override was actually run and rejected nonzero. NuGet reports no known
vulnerabilities for the Linux project. ImageSharp 4.0 was tested but its build
requires a separate Six Labors commercial license; the project therefore stays
intentionally on the newest license-compatible 3.1.11 line, with a gate that
prevents an automated major bump from breaking the image build. The complete
repo gate recipe passes after this server proof. Screen capture through the real
KDE portal, phone input over a real tailnet, image compose and installed-service
behavior remain separate open proofs.

Mo PC Remote power/session audit, later on 2026-08-01: the Linux agent's five
buttons were not real. It sent `lock-session` and `terminate-user` to
`systemctl` (both belong to other session interfaces), and treated
`Process.Start` as success even when the command immediately failed. Commit
`59600e7d` now uses fixed-argument Plasma D-Bus calls for the exact user
session, non-blocking logind operations for suspend/reboot/poweroff, and checks
timeout plus exit status. The .NET suite now has 32 tests including accepted,
rejected and hung-process execution; Linux publish succeeded. The next audit
found a multi-user Cloud boundary: an authenticated developer PIN could expose
sleep/reboot/poweroff for the shared server. Commit `c489d10c` bakes an
authoritative edition marker and initially rejected the three host operations.
A follow-up lifecycle audit found that Cloud accounts are passwordless by design
(Lock is therefore unrecoverable) and that clean Sign out stops their private
desktop because its supervisor correctly uses `Restart=on-failure`. The Cloud
API and phone now withhold all five session/power operations and explain that
the server console owns them; desktop MoOS retains all five controls.
The committed PWA is v16; Linux and Windows agents build with zero warnings,
controller tests/typecheck/build pass, and the complete repo check recipe is
green. No destructive power command was run on the audit host. Image compose,
installed Cloud service behavior and a real tailnet/phone session remain open.
A later Windows audit found that Sign out, Restart and Shut down still returned
`true` immediately after `Process.Start`, including a null process or a command
that exited nonzero. They now invoke the absolute System32 `shutdown.exe` with a
fixed argument list, wait at most five seconds for acceptance, and return false
on start failure, timeout or nonzero exit. A cross-platform execution harness
proves accepted, rejected, hung and missing-command cases; the Windows agent
builds with zero warnings and the repository power-policy gate covers the new
boundary. No destructive action was invoked—the harness uses inert test commands.

Mo PC Remote transfer/authentication audit, later on 2026-08-01 (`67e58e6a`):
native downloads and the HTML audio element embedded the reusable session bearer
in their query strings, exposing it to browser/proxy history and copied URLs.
Both now exchange the Authorization header for a cryptographically random
256-bit, purpose-bound, single-use ticket that expires after 45 seconds. An
isolated real HTTP run proved download `200`, replay `401`, missing ticket `401`;
an audio ticket reached the absent upstream (`502`) and replay was still `401`.
Uploads no longer stream directly into the visible destination: each file is
limited to 1 GiB at Kestrel and application boundaries, written to an isolated
partial, removed on disconnect/error, moved atomically only after completion,
and stops before consuming the final 512 MiB of its actual longest-matching
filesystem. Space checks are paced at 64 MiB rather than per 128 KiB network
chunk. Ticket storage is capped at 1024 entries with amortised O(1) FIFO
eviction (`a5d9e954`); it no longer scans the entire dictionary on every issue,
which made an authenticated issuance burst quadratic. The .NET suite now passes
48 tests including pressure bounds, ticket replay/purpose
confusion and interrupted-upload cleanup; Linux publish, Windows build (zero
warnings), TypeScript typecheck, controller tests, committed PWA v17 and the
complete repo check recipe all pass. A real phone/tailnet transfer and full
image compose remain open release evidence.

Mo PC Remote asynchronous lifecycle audit (`44ab6880`): Refresh owned a raw
120 ms `setTimeout(connect)` that could reopen a socket after Disconnect/Sign
out, and an audio-ticket request could finish after Stop and begin playback
behind the user's back. Refresh/Reconnect/Disconnect now retire one owned timer;
audio start and retry results are generation-bound, Stop/unmount invalidate the
generation, remove the media source and close the upstream encoder. Toast and
first-use hint timers are also cleared on unmount. The new
`test_remote_async_lifecycle.py` gate runs in local checks and CI, the committed
controller is PWA v18, TypeScript/controller tests pass, and the complete repo
check recipe is green.

Phone sign-out audit (`dcdb9c0c`): the UI's Sign out path only cleared
`localStorage`; it never called the already-existing `/api/logout`, so a copied
bearer remained valid server-side for up to the 60-minute session TTL after the
user saw the login screen. `App.exitToLogin` now awaits server revocation before
returning to authentication while retaining offline-safe local clearing. The
new relationship gate is wired into local checks and CI, PWA v19 is committed,
and the complete repo check recipe passes. The server revocation endpoint itself
was already proven in the isolated HTTP login/logout sequence earlier in this
audit; this change connects the real phone action to it.

Mo PC Remote phone interaction/accessibility audit (`aad4a25c`): Display,
Settings, Files and Clipboard were visual bottom sheets only. Focus stayed on
the desktop behind them, Tab could escape into hidden controls, Escape did not
close them and no dialog semantics reached a screen reader. All four now share
one modal SheetPanel that moves focus in, traps Tab/Shift+Tab, closes on Escape,
restores the invoking control and exposes a labelled close target. The clickable
connection pill is a real disclosure button with an accurate expanded state;
connection changes and transient confirmations are polite live announcements.
The content-editable image paste target remains inside the focus loop. A source
regression test is part of `npm test`; TypeScript, production build, two
byte-identical builds, zero-vulnerability npm audits, shipped-asset tracking and
the complete repository check recipe pass. The committed controller is PWA v20.
Touch/VoiceOver/TalkBack proof on a real phone remains open release evidence.

Remote PIN interaction follow-up (`32de7625`): the connect/setup screen was
touch-only despite using native buttons—physical number keys, Backspace/Delete
and Enter did nothing. It now gives hardware keyboards the exact keypad path,
announces only the entered digit count (never the secret), and disables the
entire keypad atomically during a login/setup request or server lockout instead
of leaving controls that visibly press but are ignored. The regression test,
TypeScript, zero-vulnerability audit, deterministic production rebuild, shipped
asset gate and complete repository check pass. The committed controller is PWA
v21; real mobile keyboard and screen-reader proof remains open.

Remote Reduced Motion follow-up (`d78ac6cc`): the PWA previously honoured the
system preference for only the settings switch and disclosure chevron while 18
other animations/transitions—including the perpetual connecting spinner,
sheets, toast, toolbar and keypad feedback—continued. One global policy now
stops animations and transitions for every element and pseudo-element and keeps
scroll state changes immediate; it does not use a near-zero-duration workaround.
The source gate, TypeScript, npm audit, deterministic production rebuild,
shipped-asset gate and complete repository check pass. The committed controller
is PWA v22; a real phone setting toggle remains open visual evidence.

Remote sensitive-power confirmation audit (`34a1f8b0`): Sign out, Restart and
Shut down used the browser's `window.confirm()`, producing an unthemed platform
dialog outside the Liquid Glass interaction and an untestable focus path. They
now use a MoOS `alertdialog` built on the same modal/focus contract as the phone
sheets, with Cancel focused first, explicit unsaved-work consequences and a
single shared API execution path. An atomic in-flight guard prevents a fast
double tap from issuing the action twice. Once submitted, the dialog becomes a
non-dismissible Working state because closing it cannot cancel a command already
delivered to the host. Cloud still exposes none of these host actions. The source
gate bans `window.confirm` and holds confirmation-before-API plus single-flight;
TypeScript, npm audit, deterministic production build, shipped assets and the
complete repository check pass. The committed controller is PWA v23. A safe
non-destructive live confirmation run on desktop MoOS remains open evidence.

Remote authentication-handoff audit (`b8ff5480`): a network drop during
`login()` or first-time `setupPin()` threw past the screen and left `busy=true`,
permanently disabling the keypad. A second race happened after the server issued
a token: if the immediate status read failed, `enterRemote()` leaked a rejected
Promise with no recovery UI. Both auth screens now catch network failure and
release busy through `finally`; successful handoff deliberately avoids updating
an unmounted screen. App stores the issued token, enters an accessible Loading
state, and on status failure shows a Retry path that reuses the token rather than
asking for the PIN again. Non-2xx `/api/status` is rejected instead of parsed as
a valid status. A Node behavior test proves HTTP 503 rejection and gates both
handoffs. TypeScript, npm audit, deterministic production build, shipped assets
and the complete repository check pass. The committed controller is PWA v24;
an actual mid-handoff network interruption on a phone remains open live proof.

Remote control-plane timeout audit (`99c66235`): rejection handling still did
not cover a black-holed mobile network, where `fetch()` could remain pending for
minutes and pin Login, Setup or a power action in its busy state. Short JSON
control requests now share a 15-second `AbortController` boundary, relay a
caller's own abort signal, and always remove the relay listener and timer. File
uploads and media streams intentionally remain outside this boundary because
they are valid long-running transfers. A Node behavior test proves that a
never-resolving request is aborted; TypeScript, npm audit, deterministic
production build, shipped-assets gate and the complete repository check pass.
The committed controller is PWA v25. A real tailnet black-hole test from a phone
remains open live proof.

Remote Linux network-boundary audit (`efaa3c98`): the Linux agent still used
Kestrel `ListenAnyIP`, leaving a raw cleartext port beside the intended
Tailscale-Serve HTTPS door. Its CGNAT-range middleware was not an interface
boundary, and the Cloud account manager had escaped the earlier audio fix: it
still created an unauthenticated `/audio` sibling mount for both the seat owner
and private desktops. Linux Kestrel now listens on loopback only; Desktop and
Cloud publish that single door through Tailscale Serve. Both Cloud setup paths
actively retract legacy audio mounts, and Doctor now treats such a mount as an
exposure instead of a requirement. Sound remains available through the agent's
authenticated, one-use-ticket proxy. A new regression gate covers the listener,
both publishers, the truthful startup log and the Cloud audio path, and is part
of `just check`. Runtime proof against the built .NET agent returned HTTP 200 on
loopback and refused both the host network and tailnet interfaces; .NET built
with zero warnings, all 48 behavior tests passed, and the complete repository
check passed. A real phone connection through Tailscale Serve remains open live
proof.

Remote trusted-device lifecycle (`d4364fe7`): “trusted device” previously meant
only an access bearer in browser `localStorage`; the server kept it in memory,
had no device identity or inventory, and every agent restart forced a PIN while
leaving the UI to try a dead token. Trust is now explicit on Setup/Login and
separate from the short-lived access session. The phone receives a 256-bit
device secret once; Linux stores only its SHA-256 hash in the mode-0600 config
and Windows keeps the same hash inside its existing DPAPI-protected config.
Credentials expire after 30 days, are capped at 16, carry a sanitized device
name and last-used time, and changing/resetting the PIN removes all of them.
The PWA validates an access token before entering Remote, resumes through the
device credential after an agent restart, and exposes an owner-visible Settings
inventory with individual removal. Sign out removes both the access session and
the current trusted credential. The server also closes the first-run setup race
inside the same authentication lock, rather than relying on the earlier HTTP
check. A new gate covers Linux/Windows persistence, hashing, bounds, API, PWA
handoff, consent, inventory and revocation. Live HTTP proof showed the old bearer
return 401 after restart, device resume/list/revoke return 200, and replay after
revocation return 401. Linux and Windows .NET builds completed with zero
warnings; 61 core behavior tests, PWA tests/typecheck, npm audit (zero findings),
deterministic PWA v26 build, shipped-assets gate and the complete repository
check pass. Touch/visual confirmation on a physical phone remains open evidence.

Remote transfer resource-bound audit (`21008908`): authenticated clipboard-image
upload copied the complete HTTP body into a `MemoryStream` before checking the
25 MB limit. Kestrel permits the file-transfer ceiling of 1 GiB, so one trusted
client could make the agent retain close to a gigabyte and be killed by memory
pressure. It now rejects declared oversize bodies before reading and uses a
shared streaming reader that asks for only one byte beyond the remaining cap;
the rejected byte is never followed by buffering the rest. Directory browsing
also stopped materializing and sorting an unbounded folder: enumeration is
materialized inside its exception boundary, capped at 500 entries, and reports
`truncated` visibly in the phone UI instead of pretending the response is
complete. Exact-limit, one-byte-over, 520-entry truncation and partial-upload
cleanup are behavior tested. Linux and Windows .NET builds have zero warnings,
65 core tests pass, PWA tests/typecheck and npm audit pass with zero findings,
the PWA v27 production build is deterministic, and the shipped-assets and full
repository gates pass. A real large transfer interrupted over a phone tailnet
remains open live evidence; automatic background folder sync is not claimed.

Remote resumable-download audit (`a8689686`): the download URL previously held
a one-use capability, so enabling HTTP Range alone would have made the first
partial request consume the ticket and every retry fail. Downloads now receive
a five-minute, resource-bound lease limited to 32 uses; wrong-purpose use burns
it, its FIFO shares the existing 1,024-capability memory ceiling, and audio
remains strictly single-use. The file response enables Range and supplies stable
Last-Modified plus length/mtime ETag validators so a browser does not splice two
versions of a changing file. Live HTTP proof against the built Linux agent used
one lease for two ranges: both returned 206, `bytes 5-9/37` and `bytes 10-15/37`,
with the requested payload and identical ETag. Linux and Windows builds have
zero warnings, 72 core behavior tests and the complete repository check pass.
This proves resumable downloads; bidirectional background folder sync remains a
separate, unimplemented protocol and is not claimed.

Remote resumable-upload audit (`e484249e`): the PWA formerly sent every selected
file as one request, so losing the final response forced a full restart and made
it unsafe to guess whether the server had accepted the bytes. Uploads now use an
owner-bound, 30-minute session and authoritative offset, with 4 MiB chunks, a
64-session ceiling and a 1 GiB file ceiling. Chunks are written to a hidden file
in the destination filesystem; only a complete commit atomically moves it into
place, incomplete/cancelled/expired sessions clean their temporary file, and a
name collision still uses the existing unique-name policy. The PWA fingerprints
the selected file from metadata plus its first and last 64 KiB before resuming,
shows byte progress, and queries status after a lost response instead of sending
the same bytes twice. Live HTTP proof against the built Linux agent wrote two
chunks around a deliberate duplicate-offset conflict: the conflict returned 409
with authoritative offset 3, no target existed before commit, commit returned
200 with exactly `abcdef`, and commit replay returned 404. Linux and Windows
builds completed with zero warnings; 84 core tests, PWA tests/typecheck, npm audit
(zero findings), shipped-bundle freshness and the complete repository check pass.
A follow-up audit found that the original expiry cleanup was request-driven: a
phone that vanished caused no later request, so its `.part` file could survive
for the lifetime of the agent. A five-minute timer now sweeps the bounded
64-entry table even while idle, is disposed with the agent services, and has a
clock-controlled regression test proving both session and file disappear after
expiry.
A service restart intentionally invalidates in-memory upload sessions, and a real
interrupted large transfer on a physical phone remains open evidence; automatic
background folder sync is not claimed.

Remote private-background-alert audit (PWA v29): the controller can now opt in,
from its Settings sheet and a direct user gesture, to two generic phone alerts:
an interrupted desktop connection and a completed upload. The boundary requires
a secure installed/service-worker context, stays silent while the controller is
visible, and exposes an event union rather than arbitrary title/body text, so a
later caller cannot accidentally mirror desktop notifications, filenames,
clipboard data or credentials. Tapping the alert focuses the existing controller
window or opens it. The worker adds no polling and the feature remains disabled
by default. A follow-up lifecycle audit found that every failed reconnect would
have emitted the same alert and an intentional server stop could be labelled an
interruption. The socket now reports whether a close will actually recover, and
the UI emits once per outage only after a prior authenticated `hello`; another
successful `hello` re-arms it. Eight controller suites, TypeScript, the production PWA build, npm
audit (zero findings), Linux and Windows .NET builds (zero warnings), the shipped
bundle gate and the complete repository check pass. This is not Web Push: a fully
closed or OS-suspended phone app receives nothing, and live iOS/Android evidence
over Tailscale HTTPS remains open.

Remote Tidal Cut icon audit (PWA v30): the largest fallback/error state still
used a platform-dependent plug Emoji, orientation mixed text arrows with a lock
Emoji, and the file browser mixed coloured folder/document Emoji beside the
existing stroke system. Those surfaces now share four new 24×24 viewBox marks
(plug, rotate, file and up) plus the existing folder/lock marks, all driven by
`currentColor`; file rows pin them to a sharp 20 px optical size. The shared SVG
root now explicitly hides decorative marks from assistive technology so adjacent
button/status names are announced once. Nine controller suites, TypeScript, the
production bundle and npm audit (zero findings) pass. This is source/render-pipeline
evidence; phone screenshots at light/dark and multiple pixel densities remain open.

Remote control glyph completion (PWA v31): the sheet close control, paused-state
mark and keyboard Backspace/Enter controls no longer depend on font-specific
dingbats. They now use the same accessible, `currentColor` Tidal Cut SVG root as
the rest of the controller, with deterministic 19 px control sizing. The credit
accent is a CSS material lozenge rather than another font glyph. Conventional
keycap legends (arrows and modifier shortcuts) intentionally remain text because
they describe the exact key sent. The icon regression suite rejects a return of
these visible dingbats. Live phone screenshots remain required before claiming
pixel-level validation.

Remote clipboard runtime audit: the Linux bridge's apparent three-second timeout
was dead code for a hung `wl-paste`, because it synchronously drained stdout
before calling `WaitForExit`. A stuck compositor helper could therefore hold an
authenticated clipboard request forever, and output had no memory bound. Reads
and writes now run with cancellable async I/O, a 25 MB ceiling, fixed
`ArgumentList` argv, and process-tree termination at the deadline. Helper exit
status now reaches both platform bridges; the API returns 503 rather than fake
`ok:true`, and Unicode input does not inject Shift+Insert when `wl-copy` rejected
the payload. A real subprocess test proves a `sleep 20` helper is cut off, exact
limits succeed, oversized output is discarded, and failed/successful writes are
distinguished. Linux and Windows cross-builds complete with zero warnings. This
does not substitute for a live Wayland clipboard round-trip on the built image.

Wayland session resolution audit: the Remote unit used the first `wayland-*`
filename in the runtime directory without proving a compositor still listened
there, while `moai-open` and `moai-screenshot` independently guessed
`wayland-0`. That fails after a Plasma restart and on private Cloud desktops
whose display names are not fixed. The shared `moos-wayland-display` resolver
now honours the inherited display only if its current-user Unix socket accepts a
connection, otherwise probes newest-first and rejects stale/non-socket/foreign
entries. Remote fails into its bounded restart policy instead of advertising an
uncapturable session; Mo AI open/screenshot can use the actual compositor or
fall through without poisoning X11 with a fabricated Wayland name. A behavioural
test creates stale and live Unix listeners and proves preference, fallback and
no-session failure. A real post-restart/private-desktop capture remains live-image
evidence, not something this off-image test claims.

Boot identity repair audit: the installed-system helper contradicted the known
bootupd contract by invoking `grub2-mkconfig` against a static Atomic
`grub.cfg`, then could print Done after that forbidden step failed. The image
also carried an unreachable retired Nova GRUB theme and inert timeout/theme
defaults, making dead assets look like implemented polish. The helper is now a
read-only audit unless explicitly run as root with `--apply`; mutation is limited
to a verified create-before-delete firmware label replacement and a conditional
Plymouth repair. It never rewrites bootupd configuration, leaves the old entry
when replacement verification fails, and no longer exposes raw foreign labels in
its report. The dead Nova theme and inert knobs were removed from the shipped
image, retaining only `GRUB_DISTRIBUTOR=MoOS` as compatibility identity. A gate
holds those constraints. This deliberately does **not** close the real open work:
a first-party rollback-menu design needs a tested bootupd-supported integration
and boot photographs on an installed image.

Lock wallpaper migration audit: both theme paths already wrote the selected
wallpaper package to `kscreenlockerrc`, but existing v27 users never reached
that write: the per-user marker exited on `theme_intact()` before the stricter
`theme_complete()` lock check. Revision 28 now performs the one-time migration.
The completion checks also changed from substring to exact equality; previously
`MoOSUI2NovaLight` satisfied an expected `MoOSUI2Nova`, allowing a dark theme to
retain its light lock wallpaper while every marker stayed green. Regression
tests hold the revision, both exact readbacks, the image-plugin write, and the
full theme-to-lock relationship. This is migration/configuration evidence only;
an installed Plasma lock in Light and Dark still needs live screenshots before
the visual result is claimed.

Mo PC Remote audio recovery audit: the authenticated audio
path itself was complete, but one dead media response can emit a burst of
`stalled`, `error`, and `ended`. Each event previously scheduled a separate
one-use ticket request, so a single drop could start several Opus encoders; only
the last timer id was retained, allowing an older callback to cross Stop and
restore audio. Recovery is now single-flight, keeps its slot occupied while a
fresh ticket is in flight, reopens it only for the new source, and checks both
generation and `src` before and after the await.
The controller test and repository security gate hold that lifecycle.

Mo PC Remote startup-inhibitor audit: the user unit synchronously called
`systemd-inhibit` once as a probe and then again around the agent. Either D-Bus/
polkit acquisition could hang while Type=simple still presented an active unit;
the second call also reopened a probe/execute race, so the documented fallback
did not cover the call that actually mattered. `/usr/libexec/mo-remote-start`
now resolves a connectable Wayland socket with a five-second bound, launches one
real inhibit attempt in an isolated process group, and observes `/proc` for the
agent child. A granted lock is retained for the agent's lifetime. Refusal, early
exit or five seconds without a child terminates the complete attempt and `exec`s
the same agent directly. After a successful acquisition only a tiny shell waiter
remains to propagate the agent's real exit status to `Restart=on-failure`; no
Python launcher stays resident. Behavioural tests prove a deliberately hung
inhibitor falls back promptly, a granted inhibitor runs the agent exactly once,
and the selected private Wayland display reaches it; a failing acquired agent also
returns its exact status to systemd. The experience and Wayland gates
now follow the indirection through the launcher; live logind inhibition remains
built-session evidence.

MoOS Cloud dashboard lifecycle audit: `ShowDashboard=false` previously changed
only `bentoFrame.visible`; `DashboardBento` was still constructed, immediately
started geolocation, kept its clock/weather/retry timers, and retained every card
behind the hidden frame. The scene now owns the bento through a conditional
`Loader`: disabled or too-small surfaces instantiate no dashboard object at all.
Source, experience and image-build gates hold that lifecycle boundary. This
removes hidden dashboard work; it does not claim to explain the separate
plasmashell frame-request behavior documented in the roadmap.

Mo AI service lifecycle audit (`1cf194b3`, `017df8a6`): the ~386 MB OpenClaw
Node gateway used `Restart=always` with a heavy preflight but no start limit, so
a persistent binary/config failure could rebuild its stack every ten seconds
forever. It now permits eight attempts per five minutes—enough for intentional
clean reloads—then becomes visibly failed, and its stop is bounded at 30 seconds
instead of the systemd default 90-second logout/reboot stall. The on-demand
Ollama and ~1.5 GB Speaches Quadlets had the same unbounded five-second restart
shape; each now has a five-per-five-minute limit, and Ollama teardown is bounded
at 30 seconds. Explicit stop, wake-on-demand, clean OpenClaw reloads and
AutoUpdate behavior are unchanged. `test_moai_service_lifecycle.py` is in local
checks and CI; focused Mo AI tests and the complete repo check recipe pass.
This Cloud host has no systemd user runtime, so installed-unit restart-rate and
shutdown timing remain image/live evidence rather than claimed measurements.

Mo AI Waydroid control audit: `setup-waydroid` confirmed only while downloading
the first Android image. Once initialized, the public `moos:` route could start
the persistent container and UI without a user decision. It also swallowed a
failed `systemctl enable --now`, slept two seconds and printed “Android ready”
without proving either container or session. The action now asks exactly once on
every state-changing run, requires the container to be active, then waits up to
20 seconds for `Session: RUNNING` before opening the UI or reporting readiness.
A command-double behavior gate proves decline changes nothing, container failure
is nonzero and never launches the UI, and the healthy path reaches every stage.
No Android image or privileged service was started on this audit host; a real
Waydroid/Wayland launch on the composed image remains open live evidence.

Mo AI application-launch acceptance audit: `setup-windows` promised to open
Bottles, but the shared `launch_app` helper returned success immediately after a
background fork—even when `flatpak run` exited nonzero—and then printed usage
instructions for a window that did not exist. Detached launches now get a short
acceptance window: a process still alive or a D-Bus launcher exiting zero is
accepted; an immediate nonzero exit is surfaced. Both generic post-install launch
and Bottles report the honest partial state (“installed, could not open”) and fail
the audit instead of implying completion. A behavior test proves accepted and
rejected Flatpak launches; the complete repository check passes. A real Bottles
launch on the composed image remains the stronger live proof.

Mo AI small-service lifecycle follow-up: the original gate covered only the
heavy OpenClaw/AI containers. `moai-control` could still restart every five
seconds forever, `moai-wake` had the same crash-loop shape, and the gateway's
30 attempts at a four-second cadence sat on the exact edge of its 120-second
window, so the limiter was not a reliable stop. Control now permits 6/120s,
gateway 12/120s, and wake 5/300s; Mo PC Remote receives the same 5/300s bound.
Control, gateway, wake, agent API, Remote and Cloud audio now have explicit
10–15 second stop bounds instead of the default 90 seconds. The regression gate
was also repaired: its section parser previously matched `[Service]` written in
a comment before the real header, so it could inspect dead text. It now matches
only actual systemd headers and verifies directive placement. Focused Mo AI
tests and the complete repository check pass. This off-image Cloud host lacks
`systemd-analyze`, so unit loading and shutdown latency still require the image
build/live system and are not claimed here.

Mo AI RamaLama lifecycle follow-up: the primary on-demand `moai.service` still
had `Restart=on-failure` at a five-second cadence with no explicit rate limit.
That cadence can stay below systemd's distribution-default burst indefinitely,
recreating a multi-gigabyte model process after a persistent model, GPU or
runtime failure. The unit now allows five attempts per five minutes in `[Unit]`
and then remains visibly failed. The lifecycle gate now covers this unit and
directive placement as well as the Ollama/Speaches containers. No model was
loaded on this off-image audit host; installed restart timing remains live-image
evidence.

Theme-sync failure lifecycle audit: `moos-theme-sync.path` correctly disables
systemd's start-rate limiter because Plasma emits a burst of successful
`kdeglobals` rewrites at ordinary login; restoring a start limit would fail the
path for the session. But the paired service also used `Restart=on-failure`
every five seconds, so a persistent Plasma/config write error could reconcile
forever. Retry now lives in the service-only command and ends after three
attempts with 2/4-second backoff. The path remains active for the next genuine
theme change, while a persistent fault is visible and idle. Theme safety gates
hold the unlimited successful path activations and the bounded failure budget.

First-run keyboard viewport audit: Welcome's optional-app and install-queue
panes, plus the installer's disk, account and timezone panes, allowed Tab to
move focus below a clipped viewport without scrolling it; Page Up/Down had no
page action there. The previously proven Mo Store algorithm now lives once in
`apps/ui/KeyboardViewport.js`: every first-party wizard reveals the focused
control through all nested Flickable/ListView ancestors and moves page keys by
90% of the viewport with hard origin/end clamps. A focused visual regression
gate holds the shared algorithm and every pane binding. This host has no Qt/KDE
runtime, so source construction and the gate are evidence here; a live Tab walk
on the built image remains part of the next installed visual pass.

Mo Store long-description audit: the details sheet already named an AppStream
`description`, but curated catalogue overlay replaced that field with the short
card summary, so curated applications repeated one sentence and never exposed
their real details. The indexer now preserves distinct AppStream copy, handles
both container-localized and per-paragraph/list `xml:lang`, renders paragraphs
and lists as bounded plain text, and caps each chosen locale at 2048 characters.
The scrolling details sheet no longer truncates at eight lines and forces both
summary and description to `Text.PlainText`. The generator's own SHA-256 is part
of its metadata token, so existing caches rebuild once after this code change
rather than retaining the broken projection. Black-box tests prove curated
summary plus Arabic/English long descriptions, list structure, locale isolation,
the hard size cap and the no-description fallback; the QML gate holds scrolling,
plain-text rendering and absence of line elision.

Mo Store virtual-grid keyboard audit: catalogue cards were individually tabbable
delegates inside a `GridView`. Because the view creates only its visible cache
window, the apparent Tab chain could never cover the whole model; the last-model
link to the bulk action often did not exist, and reverse traversal depended on
whatever delegates happened to be alive. The catalogue is now one accessible
composite Tab stop. GridView's arrow navigation owns `currentIndex` and reveals
virtualized rows, Enter/Space and the accessible press action open the current
app, and the shared focus ring follows the current delegate. The shared page-key
handler now explicitly passes every non-Page key onward, so it cannot swallow
GridView's arrows before the view handles them. Tab moves to the
bulk action (or the rail where that action is absent), Backtab returns through
the final category chip, and the bulk action has explicit traversal in both
directions. Discover's small non-virtual card set retains ordinary independent
Tab stops. A focused source gate holds the composite boundary, both directions,
activation and visible current state; live assistive traversal remains installed
image evidence rather than a claim from this Qt-less host.

Telegram wake lifecycle audit: `moai-wake` is intentionally the only lightweight
resident receiver while the OpenClaw/AI stack sleeps, but every `systemctl --user`
call was unbounded. A wedged user bus or gateway preflight therefore left the
receiver process nominally active while it stopped polling Telegram forever;
systemd's restart policy could not help a process that never exited. Fast status
and reset calls now time out after five seconds, the gateway unit has an explicit
100-second start boundary, and the client waits at most 110 seconds. A timed-out
client performs one final active-state proof because killing `systemctl` does not
cancel a unit that completed concurrently. Only then does it report and consume
the failed wake update. Behavioural tests inject a hung systemctl client and prove
bounded recovery; lifecycle and experience gates hold both timeout budgets and
the existing no-fake-success ordering. No real Telegram message was sent during
this source-host test.

OpenClaw deep health now proves Telegram `OK` and the owner's newly paired
WhatsApp account `LINKED`, both on the same gateway/session store. That live
pairing exposed a status bug: OpenClaw 2026.7 reports WhatsApp through
`connected`/`linked` rather than Telegram's `probe.ok`, so Mo AI rendered a
false disconnected state. The source API now consumes both contracts; a real
isolated source run returned both channels `connected:true`, WhatsApp account
with the owner's account redacted, mode `linked`. The bootstrap also pins the exact seven trusted
runtime plugins once WhatsApp exists, removing unrestricted extension discovery
without overwriting an owner-managed allowlist. `just check` passes with
regression tests. This post-pairing correction still needs its own signed
matrix/update before the installed UI contains it.

The pairing audit also found two lifecycle traps that would have made a linked
channel unreliable. OpenClaw exits successfully when a channel config reload
needs a full restart, so `Restart=on-failure` left both channels offline; the
signed unit now uses `Restart=always` (an explicit systemd stop still suppresses
restart). A legacy installer-created user unit also outranked that signed unit
forever and hard-required Ollama. The bootstrap now recognizes only its exact
old fingerprint, moves it to a private recoverable migration backup and reloads
the user manager; customised units and symlinks are untouched. Finally,
`openclaw-idle` no longer stops the sole WhatsApp Web receiver while WhatsApp is
enabled. The local model still unloads itself and frees VRAM after its keepalive;
machines without a persistent WhatsApp channel retain the lightweight Telegram
wake/sleep path. These contracts have behavioral/static gates and were applied
to the live account; their signed image update remains pending.

The first booted-image `post-update-check.sh` proved the published digest,
signature policy, MoOS identity/UI, Mo AI runtime, boot and zero failed units;
it returned 46/3 only because `$HOME` shadowed the image with an old `de,ara`
keyboard file and two hand-installed MoPlayer launchers. The MoPlayer shadows
were moved to recoverable
`~/.local/state/moos/post-update-backup-20260801-1810`; `/usr/bin/moplayer` now
wins. The keyboard file agrees with the image at `de,us,ara`, but the already-
running KWin process retains `de,ara` until the next login/reboot. A clean rerun
therefore remains open and must not be claimed yet.

Mo AI Workspace rebuild, first implementation slice
on `product/moai-workspace-rebuild-2026-08-01`. `MO_AI_ARCHITECTURE.md` is now
the durable architecture and completion ledger. The existing Qt/Kirigami and
Python stack is retained; no second Mo AI and no risky language rewrite was
introduced. `moai-agent-api` now owns separate atomic workspace metadata for
OpenClaw conversations (search/pin/rename/archive), canonical home-contained
projects and persistent task state. It also provides bounded user-owned PTYs:
the source UI was run on the live 4K RTL session and showed real shell output
from `printf 'Mo-AI-terminal-live\n'`, with tabs and process stop. Image/text
attachments now enter through a private non-executable store via picker or
drag/drop. PDF (first 50 pages), DOCX and ODT text extraction is real and capped
at 512 KiB; PDF uses fixed `pdftotext` argv and Office/ODF reads only an exact
bounded XML member, while unsupported binaries remain honestly metadata-only.
Vision routing now reads explicit model input metadata: Ollama's real
`/api/show` capability or provider-advertised `input`/`modalities`; it no longer
guesses from a model name, and uncertain routes remain text-only. A live PNG
request through the source Mo AI gateway and unified OpenClaw runtime reached
`qwen3-vl:4b` and returned `blue` in 17.6 seconds. Push-to-talk uses `pw-record`
→ the existing `moai-transcribe` path. A synthesized English speech proof was
auto-detected as `en` with 0.93 probability and returned `Hello, I am the MOAI
assistant.`; transcription now defaults to bilingual auto detection rather
than forcing every clip through Arabic. A real human Arabic microphone sample
is still not verified. The Speaches Quadlet now treats its known exit 137 after
clean ASGI shutdown as a successful idle stop, avoiding a false failed service.
`moai-gateway` gains
an explainable Hybrid route: sensitive data and attachments remain local by
default, complex work may use configured/reachable cloud, and routing/fallback
reasons are returned to the UI. The gateway now reads the same OpenClaw cloud provider/key written
by Settings, with the old Mo AI config retained only as an upgrade fallback;
this fixes a live contradiction where Settings reported Cloud linked but the
gateway returned `cloud brain not configured`. Source runtime proofs returned
the exact Cloud and Local markers, then routed Hybrid private to `local/privacy`
and Hybrid complex to `cloud/complex-task`, all HTTP 200 with
`X-MoAI-Agent: openclaw`. OpenClaw permissions are split into the four
real levels (read/project/system-with-approval/full). Tracked tasks now launch
the fixed OpenClaw agent command, persist real outcomes, expose pause/resume/
cancel, and ingest tool-call names from the OpenClaw session JSONL. The project
Workbench provides canonical-root file browsing, bounded UTF-8 preview and
fixed-argv Git status/diff; traversal and symlink escapes are tested, and a
bounded persistent audit ledger records task actions, project reads/diffs and
permission-policy changes. Agent process completion now adds a separate bounded
`task/finish` event for completed, failed, cancelled, timed-out or internal-error
outcomes with only exit status and observed tool names; model prompts and process
output are deliberately excluded from the audit record. OpenClaw tool outcomes
are now audited individually too: success/error and explicit
`missing-result`, bounded to the newest 8 MiB and 200 events, with only tool name
and a short call-id hash. Arguments and tool output never enter the ledger.
Tracked task cards consume OpenClaw's real
Gateway exec-approval queue and expose only its allowed decisions; a live
source-API proof listed an exact pending command, denied it through
`exec.approval.resolve`, verified removal from the queue and recorded the
decision plus command hash in the audit ledger. The shared Gateway token stays
inside the backend, and `python3-websockets` is now an explicit image
dependency. Live 4K RTL evidence exists for Tasks and the real
Git Workbench. The primary Chat canvas now uses OpenClaw's authenticated
loopback Chat Completions endpoint, so desktop, Telegram and WhatsApp share the
same agent runtime, sessions, memory, tools and policy while the existing QML
keeps streaming and multimodal payloads. A real local two-turn test preserved
the token `MOAI-LOCAL-UNIFIED-READY` in one OpenClaw session; the live UI proof
shows `qwen3-vl:4b · وكيل موحّد`. The central Chat now includes a searchable
conversation drawer and can load/continue the exact OpenClaw thread shared with
phone channels. A 4K RTL source run rendered all four messages from the proof
session; a subsequent request using its guarded session key returned the same
token with `X-MoAI-Agent: openclaw`. Replies retain Markdown/fenced-code
rendering, are selectable and have a one-click Qt clipboard action. Real
OpenClaw tool calls/results now render as bounded semantic status cards; a live
4K RTL run displayed the actual `exec` call and `opened (setsid): code` result.
Streaming can be stopped through the real active XHR, and Regenerate now removes
the prior turn then replays its exact stored payload—including image/document
parts—without duplicating conversation history.
Settings are now twelve distinct functional pages (Models, Providers, OpenClaw,
Telegram, WhatsApp, Voice, Permissions, Memory, Projects, Terminal, Privacy and
Appearance) rather than seven mixed buckets. Hybrid is a first-class privacy
choice, secrets remain write-only, and the retired unreachable Health duplicate
was removed. The fixed narrow rail is now a responsive workspace sidebar: it
keeps the 76 px compact form at 720×540 and expands to 188 px with readable
horizontal labels at 1120 px and above. Both compact and 1440×900 RTL source-QML
states were captured and visually inspected without clipping. Live 4K RTL evidence covered the section grid and real configured
OpenClaw status. Settings also passed English/LTR at the enforced compact
`720×540` minimum and Permissions passed Dark/RTL on the live 4K session; the
machine was restored to its exact prior `MoOS Scholar Light` theme afterward.
The visual matrix is now complete for the four primary workspaces. Source QML
and the source Agent backend were run together on the live 4K Wayland session;
Conversations, Projects, Tasks and Terminal were captured in Light/Dark ×
LTR/RTL at `720×540`, `1120×760` and native 4K scale: 48 real screenshots,
reviewed as three 4×4 contact sheets. The captures show the real MoOS project,
real OpenClaw sessions and a completed task. No binding/type/load errors appeared.
The accessibility surface is now live-proven rather than only grepped: Qt's
AT-SPI tree exposed the source app, every interactive node had a name or named
`labelledBy` relation after fixing six anonymous secret/switch controls, and
real Tab traversal reached named chat, composer and Settings actions. Reduced
motion remains enforced by the existing real-QML runtime gate.
The bilingual speech proof now covers Arabic too: an 11.96-second synthesized
Arabic WAV traversed the shipped `moai-transcribe` and live Speaches service
with `MOAI_STT_LANG=ar`, returned recognisable Arabic text and exit 0, after
which Speaches was stopped and reset to clean inactive state.
Visual review direction can now be selected per source run with the validated
`--layout-direction ltr|rtl` argument, avoiding global locale changes. Live
captures added Light/LTR compact Providers, Dark/LTR 1440×900 Chat and Dark/RTL
compact Terminal, then restored `org.moos.ui2.study.light` and
`MoOSUI2ScholarLight` exactly. The full primary-workspace cross-product is now
closed; the evidence contact sheets remain under `/var/tmp/moai-review-source-*`.
OpenClaw also gains a `moai/hybrid` loopback
provider so phone turns use the same smart routing policy. The installed OpenClaw
advertises WhatsApp Web support and Mo AI now exposes its fixed login route.
Channel settings now call a bounded, secret-free `/api/channels` probe instead
of implying connectivity: a live source-backend probe verified Telegram polling
connected as `@Moalfarras_bot`. The owner has now completed the real WhatsApp
QR pairing and OpenClaw deep health reports the account `LINKED`; the repaired
source projection returns both channels connected. A real inbound WhatsApp turn
is the remaining channel proof. The
endpoint wakes OpenClaw only for this explicit status request and leaves idle
sleep policy intact. `just check` passed after this slice. All of this is
unreleased working-branch state
until merge, signed CI matrix and live update pass. The final release image proof
was repeated after the last code change from branch head `622926a2`: generic
image `localhost/moos:latest` (`e3f83010083e…`). Its final 122 MB initramfs contains the OSTree boot path and
MoOS Plymouth assets; all shipped QML apps, Launcher, desktop scene, Store,
image-experience, identity and foreign-identity firewall gates passed, followed
by `bootc container lint` (9 checks passed, four pre-existing warning classes).
The same exact head produced Cloud image
`localhost/moos-cloud:latest` (`11eb2b525ba1…`) and NVIDIA image
`localhost/moos-nvidia:latest` (`7de9463dc16d…`); both passed edition-specific
gates and bootc lint. NVIDIA used kernel `7.1.5-201.fc44.x86_64`, matched
`kmod-nvidia` and `nvidia-driver` at `610.43.03`, and proved seven NVIDIA modules
inside its final 217 MB initramfs. This proves all three local composes—not
signed publication, the booted deployment or post-update behavior.
Telegram is now end-to-end proven: the live config restricts DMs to owner
`1142563280`, the real shared session records owner inbound turns plus explicit
`telegram-final` delivery mirrors to that same chat, and a new cold-start source
probe returned `@Moalfarras_bot` connected via polling. That cold proof exposed
and fixed a status race: the API now waits up to 12 seconds for the configured
loopback Gateway port before invoking OpenClaw, instead of treating systemd's
early active state as socket readiness. WhatsApp is now paired and linked;
inbound-turn proof remains open.

Previous update: 2026-08-01 — release pipeline recovery. The public, NVIDIA and
cloud images built and pushed in CI, but all three jobs were killed afterward by
an accidentally reintroduced in-job Syft SBOM scan. This is the exact failure
already recorded on 2026-07-29. Heavy SBOM work is removed again from
`build.yml`, while digest signing and verification against the installed MoOS
public key remain mandatory. `tests/test_release_workflow_safety.py` now prevents
the release-critical workflow from regressing. The locally callable `just check`
suite is also brought back in sync with CI's qdbus, gateway-streaming, cloud UID,
fail-closed ports, OpenClaw no-op, H.264 fallback and authenticated-audio gates.
The cloud build's stale status line claiming the retired unauthenticated
`tailscale serve /audio` mount is corrected to name the authenticated agent
proxy, and the audio regression test now holds the build-log contract too.
Publication, staging, reboot and
post-update verification remain open until the repaired CI run completes.

Previous update: 2026-07-31, early session — **Premium Liquid Glass application
marks** on branch `product/liquid-glass-app-icons-2026-07-30`. The machine
still boots signed `moos-nvidia` **44.20260730.486**; this round restores the
theme-baked SVG architecture (after a mid-flight PNG/hardcoded-RGB diversion
broke palette baking and the app-icon gates) and upgrades the plate material
to multi-layer Liquid Glass. Design system remains **MoOS UI — Liquid Glass**.

> **Mo AI phone-agent repair — 2026-08-01.** The gateway unit now uses the
> same `~/.local/node` runtime that `moai-do install-openclaw` provisions;
> the contradictory nvm-only drop-in was removed and the SQLite gate checks
> the installer/service contract. Bootstrap now reapplies mode `0700` to the
> OpenClaw credentials directory even when configuration content is unchanged.
> The local `just check` list was also brought back in line with CI's omitted
> runtime, cloud, recovery, streaming and remote-security gates.

> **Read [`skills/moos-engineering/SKILL.md`](skills/moos-engineering/SKILL.md) first —
> it is mandatory for every agent working here.**

> **Premium Liquid Glass app marks — 2026-07-31, branch
> `product/liquid-glass-app-icons-2026-07-30`.** A same-day diversion replaced
> the nine themeable SVG marks with static RGB PNG squircles (and stole
> Firefox/Dolphin/Konsole/Gwenview identity). That broke
> `generate_moos_themes.build_icon_theme`'s `recoloured()` bake,
> `tests/test_moos_app_icons.py`, and the "icons follow the theme" claim.
> This round restores SVG masters with KDE colour roles, upgrades the plate to
> a multi-layer Liquid Glass stack (sheen / depth / refraction / caustic /
> floor / rim — white+black opacity only, theme-safe), and redesigns Mo Store
> as a four-tile modern storefront (not a shopping bag). Mo AI stays the
> commissioned floating orb. Third-party overrides are removed. Live evidence:
> Daylight bake → blue store, Amethyst bake → purple store
> (`artwork/moos-ui2/live-tests/daylight-store-256.png`,
> `amethyst-store-256.png`); family sheet
> `artwork/moos-ui2/previews/moos-app-icons.png` + palette matrix
> `moos-app-icons-palettes.png`. `artwork/generate_3d_squircle.py` is retired.
> Release still needs commit/push, signed image, and THEME_REV=27's home purge
> on reboot so `/usr` wins over any leftover preview.

> **THEME_REV=27 — home icon override purge, 2026-07-30 evening.** The
> redrawn marks and per-palette bakes were already on `main`, but existing
> sessions never saw them: `~/.local/share/icons` outranks `/usr`, and a
> live-preview tree left the retired geometry (often still Breeze
> `#3daee9`) in place forever. `moos-apply-theme` now deletes
> `~/.local/share/icons/MoOSUI2*` and every `moos-*` / `moplayer.*` under
> home `hicolor` once per this revision, then rebuilds ksycoca. The UX
> gate asserts the purge. Until the signed image that carries THEME_REV=27
> is booted, this machine may still wear a *fresh* home preview of the new
> marks (MoOS teal / palette-baked) so the dock is honest during the wait;
> that preview is exactly what THEME_REV=27 clears after reboot.
>
> **Application-mark round — 2026-07-30, on `main` (baked per palette).** The symbolic overlays gave the *interface* a palette;
> the nine first-party **application marks** still did not have one. They are
> redrawn from scratch in `artwork/generate_moos_app_icons.py` (one 880 px
> squircle on the 1024 canvas, glyph inside a 640 px safe area, every load-
> bearing stroke ≥ 76 units so it survives the 16 px dock cell) and **every
> ink is a KDE colour role, never a literal colour**. Because MoOS pins
> `FollowsColorScheme=false` for the reason below, following the palette is
> not a runtime property — it is **baked**: `generate_moos_themes.build_icon_theme`
> writes one re-inked copy of all nine into each of the 14 palette icon themes
> (`moos/apps/scalable`, now declared in every overlay's `Directories=`), and
> `build.sh`'s new `recolor_moos_app_dir` does the same for the two broad
> bases it assembles from Colloid. Role pairing is not free choice: only
> `HighlightedText`-on-`Highlight`, `Background`-on-`Positive/Neutral/Negative`
> and the inverted `Background`-on-`Text` plate are used, because those are
> the pairs KDE guarantees — measured minimum contrast across all 16 shipped
> palettes is **4.4:1**, and `tests/test_moos_app_icons.py` re-derives it and
> fails under 4:1. What actually proves the claim is
> `tests/test_moos_symbolic_runtime.py::MoOSAppMarkThemeResolverTests`: it runs
> **`kiconfinder6`** under an isolated XDG profile once per palette and asserts
> KDE resolves `moos-store` (and three siblings) to *that* theme's baked file
> whose accent equals that palette's own `Colors:Selection`. Rendered evidence:
> `artwork/moos-ui2/previews/moos-app-icons-palettes.png` (six palettes × ten
> marks, each row on its own window colour).
>
> Three things this round found already broken and fixed:
> **(1)** `hicolor/scalable/apps/moos-moai.svg` on `main` had **lost the
> embedded commissioned master entirely** — it was a bare plate carrying
> Breeze's `#3daee9`/`#eff0f1`, i.e. a foreign identity on the assistant's
> icon, while the UX gate that requires the byte-exact master sat in a
> working-tree state that no longer checked it. **(2)** The same working tree
> had moved every app master from `scalable/apps` to `scalable/places` and
> pointed `verify_user_experience.py` at the new path — Plasma looks up
> application icons in `apps`, so that was a silent break with a green gate.
> **(3)** It had deleted the four `moos-logo.png` rasters the brand plasmoid
> resolves. All three are restored. Mo AI is now the one **tile-less** mark:
> its tile would be re-inked per palette like its siblings' and would fight
> the commissioned orb's own light, so the orb floats — scaled so its visible
> footprint is the family's 880 px span (`generate_moai_icon.py`), which is
> measured on the rendered 512 px raster by a gate, not asserted from markup.
> The stale `72x72` MoPlayer raster (a size the ladder does not produce, left
> over from MoPlayer's own packaging tree) is dropped rather than left showing
> the retired ember tile at one size.

> **Icon-bridge round — 2026-07-30, working tree on top of the shipped
> `.478` (THEME_REV=26).** Continued from the previous session, which stopped
> mid-flight on an external usage limit; its in-progress step (settling the
> Theme/Icon-bridge test contracts) is now complete. The round gives every one
> of the 14 family palettes its own first-party symbolic icon overlay
> (`/usr/share/icons/MoOSUI2<Family>[Light]`, 69 Tidal Cut symbols each,
> identical geometry, palette-matched inks) inheriting the broad `MoOSUI2` /
> `MoOSUI2Light` bases built from Colloid. The load-bearing decision is
> **`FollowsColorScheme=false`** on every MoOS icon theme: with `true`,
> QIcon recolouring reads the application `QPalette` rather than the Plasma
> surface colour set, which painted near-invisible dark symbols on the dark
> Launcher (evidence pair in `artwork/moos-ui2/live-tests/`,
> `tidal-cut-arena-followscolorscheme-before.png` →
> `tidal-cut-arena-baked-inks-after.png`, both captured through the real
> KIconLoader on the live session). Each overlay instead bakes its
> WCAG-checked palette inks; `_symbol_accent_ink` picks the nearest 1% step
> from primary toward text clearing 3:1 on every semantic surface, and
> `tests/test_moos_symbolic_icons.py` holds that math. The bridge is wired
> end-to-end: look-and-feel `defaults` select the palette overlay,
> `moos-theme`/`moos-apply-theme`/`moos-selfcheck` expect `icons == style`
> for every member, `build_files/build.sh` gates all 14 overlays in the image
> (index validity, inherits direction, full inventory, semantic roles) and
> recolours the two broad bases' baked inks, and
> `tests/post-update-check.sh` now proves `kiconfinder6` resolves the
> overlay from `/usr` after an update. The same round calms the Command
> Canvas (four columns on the 11px+ type ramp, 20px outer rhythm, 56px
> command field, quieter tiles/nav, scrollbars) — live-verified at 4K RTL
> (`launcher-four-column-live-4k.jpg`) — and gives the shared app Button
> semantic 44px states plus `isMask` symbol foregrounds; the native Plasma
> widget states (button/lineedit/listitem/menubaritem/viewitem across all 16
> desktoptheme variants) render through the real KSvg/FrameSvg path
> (`native-controls-arena-kframe.png`). The four previously-failing gate
> files were moved to the new contracts without weakening intent (density,
> type-ramp, target and destructive-pairing protections all kept). Release
> steps still open: local `just build`, commit/push + CI signed image, host
> staging, reboot, and the stricter post-update check on the booted image.

> **Tidal Horizon product-design pass — 2026-07-30, working tree
> `product/tidal-horizon-2026-07-30`.** This pass starts from the already
> accepted commercial audit; it is implementation, not another audit. It gives
> MoOS one spatial signature across the desktop: two low mineral-glass
> membranes meet at a precise concave **Tidal Cut**, while content keeps a calm
> upper field. The normal contract is `left/right=0.11/0.89W`,
> `horizon=0.82H`, `crest=0.12H`, `shoulder=0.22W` and
> `cutHalf=max(11px,0.013W)`; compact surfaces use
> `0.04/0.96W`, `0.78H`, `0.19H` and `0.18W`. It is physical geometry and
> therefore does not mirror in RTL.
>
> The accepted light/dark wallpaper masters are 1672×941 lossless PNGs:
> `moos-ui-tidal-horizon-master-v1.png`
> (`b09a5a71e68d…`) and
> `moos-ui-graphite-horizon-master-v1.png`
> (`4402f755df0c…`). They keep one silhouette and change only material/light;
> the family generator maps that geometry to all 16 semantic palettes. The
> MoOS and Mo AI logos keep their existing geometry. The accepted 69-symbol
> Tidal Cut family also remains the icon language; this pass does not restart
> icon design or import another project's artwork.
>
> The shell is now the **Command Canvas**, `828×630` logical px with a `24px`
> outer rhythm, `68px` command bar, ≥`40px` targets and the shared
> `8/12/16/24px` radius scale. It exposes Mo AI, Store and Settings once,
> then quiet context/session actions; its finite entrance is `240ms` and
> interaction feedback `120ms`. Hero Clock updates by the minute and has no
> perpetual seconds animation. Splash, login, lock and logout share the same
> horizon geometry; the application component uses one finite `320ms` reveal.
> Every duration becomes zero when
> `Kirigami.Units.longDuration <= 1`.
>
> Portal motion is deliberately surface-specific: Splash reveal **460ms** +
> progress **260ms**; Logout background **480ms** + sheet **420ms**; Lock has
> only finite transitions and a minute-event pulse; the Login wallpaper is
> static. The canonical portal component hash is
> `11a0ddbd40ae617a2ff7ac25204ceb9cf63fd42795fa373d531b5fb6caa82705`;
> the generator synchronises those exact bytes across all 16 family doorways.
> Store and Mo AI now seat their unchanged identities on the shared horizon
> instead of unrelated decorative glow layers. The new native MoOS Control
> Center unifies Overview, Appearance, Connectivity, Hardware, Privacy,
> Updates and Recovery in one bilingual/RTL shell. It uses ≥`48px` controls,
> a read-only status helper and **34 fixed allowlisted routes**; storage is
> measured on `/var`, not composefs `/`. MoPlayer was deliberately not
> reworked again in this pass: the accepted MoOS chrome and canonical
> `23799ad` / 176-test state remain the source of truth.
>
> Working-tree previews and before/after pairs are indexed at
> [`artwork/moos-ui2/live-tests/README.md`](artwork/moos-ui2/live-tests/README.md).
> The final wallpaper and Command Canvas were also captured from the running
> 3840×2160 Plasma session after a temporary source-package install; that user
> override was then removed so it cannot shadow the signed image. These are
> **not signed-deployment evidence**. Measured idle samples from the previews:
> Launcher **0 ticks / 0.000% over 20s**, Hero Clock **0 / 0.000% over 20s**,
> Store **0 / 0.000% over 20s**; Control Center held **55.8 MiB current /
> 58.8 MiB peak** and accumulated **0.427s CPU after minutes**. The full gates
> and local generic image build have passed. Release remains open until the
> branch is committed/pushed, CI publishes a signed image, that exact digest is
> staged and booted, and post-update verification plus final booted-image
> captures pass.

> **Working-tree visual/UX audit — 2026-07-30, branch
> `audit/commercial-visual-polish-2026-07-30`.** The measured audit and release
> checklist are in
> [`artwork/MOOS_VISUAL_POLISH_AUDIT_2026-07-30.md`](artwork/MOOS_VISUAL_POLISH_AUDIT_2026-07-30.md).
> The rejected 67/68-symbol monoline checkpoint was replaced wholesale by the
> original **69-symbol Tidal Cut** family: compound filled paths, one generated
> manifest/catalogue, live semantic theme roles and executable KDE, GTK and
> librsvg proofs at 16–128 px. The worktree also closes session-control and
> Installer contrast gaps across all 16 schemes; makes custom actions keyboard-
> and AT-reachable; binds finite motion to animations-off; maps first-party GTK
> windows to the active family palette; removes blocking Recovery and Mo PC
> Remote work from GTK's main loop; and fixes shell double-mirroring in RTL.
>
> Source acceptance is now green: the four QML apps share tokens, focus, buttons
> and symbols; Launcher is a 720×590 three-column MoOS composition; dock type
> uses the system font/11 pt floor; Splash is one reveal plus progress; Mo AI
> ambient loops and bilingual duplication are removed; and active-locale copy
> is enforced. MoPlayer uses palette-native MoOS chrome, passes analyze plus
> **176/176**, is committed/pushed at canonical `23799ad`, and is vendored from
> that exact clean revision. Final image-repository `just check` exits 0. The
> full generic `just build` also exits 0 from this exact worktree and produces
> `localhost/moos:latest` (`5e64dbf3373a…`): all in-image QML, Launcher,
> desktop-scene, identity, Store, initramfs/Plymouth and bootc gates pass;
> initramfs is 122 MB and contains the MoOS Plymouth assets plus
> `ostree-prepare-root`.
> **This is still not shipped evidence:** signed publication (including the
> NVIDIA matrix image), update staging, reboot and post-update check are the
> remaining release steps.

> **Session N — the practical full-system audit (2026-07-29), branch
> `fix/full-system-audit-and-completion`.** A live-first audit (bootc/rpm-ostree
> status, failed units, journal, coredumps, boot chain, sysctl-vs-live, ports)
> found the boot/update/rollback/kernel/signature foundation HEALTHY: all MoOS
> sysctls apply live (BBR, fq, swappiness 150, backlog, inotify), zram active,
> two deployments (rollback intact), signature policy enforced. No Critical/High.
> A read-only defect sweep across all subsystems then produced ten reproduced
> defects, each fixed with a regression proven to bite:
> - **boot** — `net.core.default_qdisc=fq` was rejected on the primary
>   systemd-sysctl pass because sch_fq (a module) was never preloaded; only
>   tcp_bbr was. Added sch_fq to modules-load.d and generalised
>   test_kernel_network_tuning to pair any module-backed sysctl value (95b0161).
> - **ui/motion** — the MoOS apps were the motion-gate blind spot: Mo AI ran 12
>   unguarded Animation.Infinite loops, Welcome/Installer/Store two each. Gated
>   all 18 on `Kirigami.Units.longDuration > 1` and added
>   `system_files/usr/share/moos/apps` to _MOTION_ROOTS (302a410).
> - **cloud** — moos-cloud-dev wrote an inverted subuid range (100000-65535);
>   fixed to a unique per-uid block + new gate test_cloud_subid_range (0c77163).
> - **remote** — the orphaned MoRemote.Tests crashed on a stale assertion
>   (removed wall-clock check); fixed and wired into the Containerfile build
>   stage so it runs every build (ba5bc81).
> - **moai** — test_moai_do now validates the UI's real extractRuns alternation
>   whitelist, not just literals (9569c6e).
> - **ci** — build-disk/iso now cosign-verify the image before building an
>   installer; all jobs got timeout-minutes; build-disk got concurrency
>   (8a13cff). Image build also gained an SPDX SBOM attestation (592e55f) —
>   **which was removed again on 2026-07-29 after it broke the build twice; see
>   the round-3 entry below. Do not re-add it to this workflow.**
> - **moplayer** — the bundled demo playlist could never load (undeclared in
>   pubspec, wrong asset path); shipped it correctly + regression (b25b158).
> - **store** — curated npm/AppImage tools could be installed but never removed;
>   added the symmetric removal path in storectl + the UI Remove button (cb4f981).
> All 30 repo gates pass locally verbatim; controller TS, MoRemote.Tests (.NET,
> 21), and MoPlayer flutter (164) all green. Live-verified where possible:
> Welcome rendered from edited source; `moos-storectl remove claude-code`
> returns success (was "Invalid Flatpak app ID"), the test install restored
> afterward. NOT yet verified (needs a boot / a main build): the sch_fq
> ordering on a clean single-pass boot, and the SBOM attestation step.
> **Update:** the SBOM step was never verifiable — it killed the runner on both
> attempts and was removed (round 3).
>
> **Session N, round 3 — shipped to main, booted, and verified on the machine
> (2026-07-29).** Everything below is running on `44.20260729.452` (rev d567c8b,
> digest ff45fe58), signature-verified against `/etc/pki/containers/moos.pub`.
> `tests/post-update-check.sh`: **48 passed, 0 failed** (was 45/3 before this
> boot), 0 failed system or user units, user `default.target` **1.444s**.
> - **ci (High)** — the SPDX SBOM step killed the GitHub runner twice; the second
>   time it took ALL THREE matrix jobs. syft spends ~8 min unpacking a multi-GB
>   image on a runner already squeezed by `Free disk space`, and the runner does
>   not come back. `continue-on-error: true` does NOT save it — that forgives a
>   step which EXITS non-zero, and nothing forgives a runner that is gone, so the
>   step showed "success" inside a red job. Removed (04b57bd). If it ever returns
>   it needs its own workflow, off the path that produces the image people boot.
> - **recovery (High)** — `deployments()` documents a 3-tuple and the call site
>   unpacks three names, but two failure paths still returned pairs, so Recovery
>   died with `ValueError: not enough values to unpack (expected 3, got 2)`.
>   Both paths mean "rpm-ostree is unwell" — the only reason anyone opens
>   Recovery. It worked on every healthy machine and crashed on the broken one
>   (db7fd10). Verified on this boot: with rpm-ostree PATH-shadowed by a stub
>   that exits 1, `/usr/bin/moos-rollback` still draws (timeout 6s -> exit 124,
>   no traceback); the installed file has 3 three-tuple returns and 0 pairs.
> - **remote/ui (High)** — the shared `<S>` icon set only a viewBox, so any use
>   site without a matching CSS rule fell back to the browser default object
>   size. Measured in Firefox: **290x270px vs 20x19px**, 14.5x too wide, at three
>   sites (idle-timeout overlay, PC-locked overlay, sign-in lockout hint) — the
>   same defect as the ~600px settings gear. Fixed on the component so no future
>   site can repeat it, then sized deliberately: `.center-msg svg` 44px,
>   `.hint svg` 1.05em (f6118e4, e391f79).
> - **remote/ui (Medium)** — `.seg button { min-width: 132px }` was tuned for a
>   FOUR-segment row; Pointer became three and Quality five, so phones wrapped
>   2+1 and 2+2+1. Re-measured inside the real `.card > .card-pad` nesting (a
>   first attempt measured the un-nested case, picked 108px and changed nothing):
>   320px fits three at no value tested, 360px needs <=84px, 390px+ fits all.
>   84px (d567c8b).
> - **theme (Medium)** — the UI2 cursor gate required the two halves to name
>   DIFFERENT themes, which the INVERTED assignment satisfies just as well, and
>   no file said which theme is the light-coloured one. Now two layers, neither
>   trusting the name: the repo gate covers all 16 look-and-feels, and
>   `verify_image_experience.py` decodes the shipped XCursor files and compares
>   mean opaque-pixel luminance (MoOS 155/255 light, MoOSDark 98/255 dark).
>   Both passed inside real CI image builds (5403739).
> - **moai (High)** — every privileged action now leaves a journal record with
>   four distinct verdicts. Verified on this boot against the INSTALLED binary:
>   `verdict=ok` (gpu-report), `verdict=declined` (a rollback declined via closed
>   stdin, deployments unchanged), `verdict=failed status=N`, and `verdict=refused`
>   for `rm -rf /`, `update; rm -rf /`, `$(reboot)`, `../../bin/sh`, `--exec`
>   (a5c2536).
> - **remote/ci (Medium)** — the image ships the vite OUTPUT, and that output is
>   committed at `moremote/agent/wwwroot`. Editing src/ without `npm run build`
>   left every test green and the shipped bundle unchanged. Two guards now:
>   `tests/bundle-freshness.test.ts` (BUILD marker must appear in the bundle, and
>   sw.js may only precache assets that exist) and a CI step running
>   `npm ci && npm run build` that fails on ANY diff. The CI step passed
>   byte-identical on GitHub's runner, so the build is reproducible from the
>   lockfile (8fe3695).
> - **security (HIGH, live) — the machine's sound was on the tailnet with no PIN.**
>   `mo-pc-remote` published moos-cloud-audio with
>   `tailscale serve --set-path=/audio`, and that service has NO authentication —
>   its own header says so. `tailscale serve` re-publishes a loopback socket to
>   the WHOLE tailnet, so on one hostname, one port, one certificate:
>       POST /api/login (wrong PIN)       -> 401
>       GET  /audio/stream.webm (no auth) -> 200 audio/webm, a live Opus stream
>   Four devices were enrolled. Any of them could listen to every call and video,
>   silently, with nothing on the desktop to say so. Tailnet-only
>   (`AllowFunnel: None`), all peers one account — bounded, not harmless.
>   The flaw was architectural: the audio was a SIBLING of the authenticated app
>   instead of part of it. Two doors, one with no lock. The sound now goes through
>   the agent at `/api/audio/stream.webm`, behind `UseNetworkGuard` and the session
>   token, with the token in the query string for the same reason
>   `/api/files/download` takes it that way — an `<audio>` element cannot send an
>   Authorization header. `mount_audio()` is replaced by `unmount_audio()`, which
>   the panel calls on every open, so a machine exposed once closes itself.
>   Verified end to end against a real agent on a spare port: no token -> 401,
>   bogus token -> 401, valid token -> 200 audio/webm decoding as WebM. The live
>   mount was retracted on this machine during the work (200 -> 404).
>   NOTE FOR THE NEXT AGENT: `tests/test_desktop_sound_reachable.py` used to
>   REQUIRE the vulnerable mount, and kept passing after the fix only because
>   `mount_audio` is a substring of `unmount_audio`. It now uses word boundaries
>   and asserts the opposite. New gate: `tests/test_remote_audio_is_authenticated.py`.
> Also recorded: the blanket `/etc/sudoers.d/moos-nopasswd` and
> `49-moos-wheel-nopasswd.rules` on the maintainer's machine are LOCAL dev
> artifacts, NOT shipped by the image — checked against `system_files/`. A
> five-agent adversarial audit refuted 6 of 8 candidate findings, including the
> theory that the 217MB initramfs costs meaningful boot time; do not re-chase it.
> Sweeps that found nothing, recorded so nobody repeats them: return-arity
> mismatches across 51 Python files and unbounded `subprocess` calls in 6 GTK
> apps produced 5 candidates, 4 false positives cleared by reading (the 5th was
> the Recovery bug above). Mo Store: 33/33 Flathub entries resolve against the
> Flathub API, and every curated `install.kind` (npm, web) has a handler.
>
> **Session N, round 2 — a deeper adversarial pass** on the same branch found
> and fixed eight more, each reproduced with a regression proven to bite:
> - **recovery (High)** — `moos-rollback` named a STAGED update as the rollback
>   target (rpm-ostree lists staged at index 0), telling the user "roll back to
>   <the newer version>". Skip staged deployments (7f9eefa).
> - **cloud/security (High)** — `60-moai-ports` failed OPEN for uid≥1010 (the
>   11th account), reverting to the base ports and reaching uid 1000's key-holding
>   gateway. Now folds into a unique non-base high band (f47f8f6).
> - **moai (High)** — the gateway left a chat reply hanging for ever on a
>   mid-stream drop (swallowed the error, never closed the socket) and dropped
>   Anthropic error/truncation events as blank "successful" replies (6266d7b).
> - **remote (High)** — the H.264→JPEG fallback latch was dead code (`if not
>   pick_h264()` on an always-truthy tuple) and the mid-stream blacklist keyed
>   the instance name 'enc' + called dict.add(); froze ~4s per rebuild (c0b9368).
> - **session (Med)** — `moos-open` session/logout|power hardcoded `qdbus6`
>   (absent on Plasma 6), so they confirmed then did nothing. Added a qdbus
>   resolver (5c58075).
> - **ui (Visual)** — the first-run theme picker previewed Nova/Aurora/Tidal in
>   the wrong accent and drew Midnight black-on-black (Qt.lighter on #000000).
>   Corrected accents to the palettes, elevate with Qt.tint (48dcd0b).
> - **perf** — `moai-openclaw-bootstrap` re-validated an unchanged config every
>   login (~1.7s / ~428 MB Node); short-circuit when nothing changed (fca4757).
> - **REJECTED** — a per-session gateway token (deep-pass proposal) was NOT
>   implemented: `moai-do:942` points codex/claude/opencode at the gateway as a
>   shared OpenAI endpoint, so requiring a token would break them. The gateway
>   being a shared local endpoint is by design.
>
> And the explicitly-requested Mo AI capability growth (60df793): three new
> `moai-do` actions — `rollback` (rescue), `net-doctor` and `gpu-report`
> (read-only diagnostics) — each a fixed case with confirm+pkexec, wired in
> moai-do + moos-open + the QML whitelist/prompt/menu, live-verified. Deferred
> by design: power lock/sleep/restart (overlaps moos://session/*), service-
> restart (validated-arg surface), backup-home (needs a destination story).

> **Session M — the audit-and-truth session (2026-07-28).** The live machine, the
> repo and GHCR were audited against each other before anything was edited.
> Verified live: the machine boots `moos-nvidia` **44.20260728.419** from the
> signed GHCR digest, zero failed system units, all Mo AI/Mo Remote/cloud-audio
> user services active, and `tests/post-update-check.sh` returned **44 passed /
> 0 MoOS failures** (the only failed units were third-party app scopes —
> Chrome/Chromium/Cursor/xwaylandvideobridge — cleared with `reset-failed`).
> All 26 gate commands of `build.yml`'s Repo-gates step pass locally, run verbatim. All
> three images (`moos`, `moos-nvidia`, `moos-cloud`) were published and
> cosign-signed the same day; `main` == `origin/main`; nothing local was
> unpushed (two stale merged branch pointers were deleted). The Mo PC Remote
> engineering of 2026-07-27/28 is on `main` and gated: input injection moved off
> the socket thread, the 1920×1080@30 resolution ceiling replaced by hardware
> probing, encoder rebuild debounce, kernel network tuning (BBR), codec resend,
> the desktop Sound button fix, and the phone UI layout fixes.
> Identity work this session: the design system is now consistently named
> **MoOS UI — Liquid Glass Design System** across README/AGENTS/ROADMAP/artwork
> docs ("Nova" survives only as the `MoOS UI · Nova` palette member and in
> historical logs; every load-bearing identifier — `MoOSUI2Nova*`,
> `org.moos.ui2.nova*`, `org.moos.nova.clock`, SVG `nova-*` ids, Dart
> `class Nova`, QML `nova*` properties — was deliberately left untouched).
> `skills/moos-engineering/SKILL.md` is the new mandatory agent skill, linked
> from README/AGENTS/this file and symlinked into `.claude/skills/` for
> auto-discovery. README.md was rewritten to describe the three-image reality.

> **Session L — MoPlayer 1.2 desktop playback overhaul (2026-07-26).** The
> canonical `~/MoPlayerMoOS` release is `e856461`, pushed on `main`, and the
> vendored source in this image is an exact sync of that commit. The KDE Wallet
> prompt is gone: MoPlayer no longer loads `flutter_secure_storage`/libsecret
> and stores IPTV credentials in its private XDG data file instead (directory
> `0700`, file `0600`, atomic replacement, and a non-fatal memory fallback).
> Existing wallet secrets cannot be migrated without reopening the wallet, so
> users enter the source once after this update. The NVIDIA-safe software
> presentation texture remains the default because the GL texture path has
> killed this app on the maintainer's RTX 2080 SUPER; hardware decoding remains
> enabled. Full-player presentation is bounded to 1280x720 and mini-player to
> 640x360, with a `videoParams` guard that reasserts the bound after media_kit
> silently resets it to the source size. Eight consecutive Wayland captures of
> the public 1080p Mux HLS stream were clean after the earlier 1920x1080 tearing
> was reproduced.
>
> Home, settings, player and catalogue browsing were modernised for mouse and
> keyboard use; direct URL launch on a clean profile works; live channel
> previous/next wraps through the queue from buttons, PageUp/PageDown, N/P and
> MPRIS; buffering/cache/reconnect settings are tuned for IPTV; catalogue caches
> are memoised and invalidated; and storage state is explained in all shipped
> languages. `flutter analyze` is clean, **114 tests** pass, release build and
> `~/.local` installation pass, desktop/AppStream validation pass, and the
> installed binary was exercised against the public HLS stream with MPRIS
> reporting `Playing`, system `libmpv.so.2`, NVDEC active, the safe texture
> resize visible in logs, and no KWallet/Secret Service call. Both local images
> then built successfully from the same source: generic `moos:latest`
> (`0328de17…`) and NVIDIA `moos-nvidia:latest` (`8929faea…`), including the
> app/identity/initramfs/bootc gates and NVIDIA 610.43.03 modules matched to
> kernel 7.1.4-204. Image commit `7308e57` was then published by CI run
> `30182998521`: generic, NVIDIA and cloud all built, pushed, cosign-signed, and
> verified against the OS-enforced public key. The machine has staged the exact
> signed NVIDIA digest `sha256:9608f65a…` as version `44.20260726.358`; the
> booted deployment remains `44.20260725.357` until the user reboots, after which
> `tests/post-update-check.sh` is still required before calling the boot proven.

> **Session K — MoPlayer 1.1 (2026-07-25).** The canonical
> `~/MoPlayerMoOS` repository, not only its image snapshot, now owns the rebuilt
> home and playback experience. The player has complete transport, seek,
> previous/next, volume, fullscreen, fit/fill/original sizing, speed and
> audio/subtitle controls; buffering is visible and recovery is bounded,
> generation-safe and manually retryable instead of silently wedging. The home
> hero is catalogue-driven and the always-running weather/live animations that
> kept an idle 4K window near one full core were removed (measured at ~1.6% CPU
> after the change). Linux single-instance activation now forwards a second
> file/URL to the existing window and was proven live while playback continued.
> Flutter is 3.44.8 / Dart 3.12.2 and the media stack is current.
>
> The “server disappears after restart” report exposed a system/app relationship
> bug: a shipped three-line `~/.config/kwalletrc` shadow disabled the encrypted
> wallet, while the compatibility provider was not active under
> `org.freedesktop.secrets`. `moos-secret-service.service` now provides that
> session service, and `moos-ui-migrate` repairs **only** the exact legacy
> disabled file; custom or later user choices are preserved. MoPlayer itself now
> treats the two encrypted writes as a transaction result and visibly refuses to
> claim success if either one fails — there is deliberately no plaintext
> credential fallback. The canonical app passed analyze + **102 tests**, built
> in release mode and was installed under `~/.local`; two full local image
> builds passed every image/identity/initramfs gate, with the second containing
> the final persistence service and exact existing-user migration.

> **Session J — the release pass (2026-07-25).** Session I's work is now ON
> `main`: `moos-ui-unify` merged as `1e7991b`, build-resilience as `5823f93`, and
> CI run `30152979451` published + cosign-signed `moos:latest` and
> `moos-nvidia:latest` (17m37s, green). Two defects the audit's evidence pointed
> at were fixed rather than noted: the wallpaper scene's `motionEnabled` now
> honours Plasma's "animations off" (it consulted only its own `AmbientMotion`
> key, so the largest surface on screen kept animating against the user's
> setting), and `uupd` — the most expensive unit of this machine's boot at
> 1min 16.195s, firing inside the first fifteen minutes of any desktop that was
> off at 04:00 — got the same idle CPU/IO drop-in `flatpak-system-update` already
> had. Both are gated (`test_moos_ui2.py`, `verify_user_experience.py`).
> **The release gate is now closed:** the machine staged
> `ostree-image-signed:docker://ghcr.io/moalfarras-sys/moos-nvidia:latest`
> (`sha256:12b44aba…`, `44.20260725.347`), rebooted, and
> `tests/post-update-check.sh` returned **48 passed / 0 failed** — the first boot
> on this machine from the signed published image rather than a local
> containers-storage deployment. `moos-selfcheck`: 46 passed.
> The live audit that followed found one real defect, now fixed: **Mo Store's rail
> status dot animated forever with no `running:` guard**, holding the QML render
> loop at full frame rate and repainting a 4K window for one 8 px dot — ~11% of a
> CPU core, paid by any session that merely had the Store window restored behind
> other windows. It was the ONLY unguarded infinite animation among the 30 MoOS
> ships, and the contract that would have caught it existed but covered the
> dashboard only; `verify_user_experience.py` now enforces it across `apps/`,
> `plasmoids/` and `wallpapers/`, broken-once to prove it bites. Everything else
> sampled was clean: no failed units, no MoOS QML errors in the journal,
> notifications deliver, the Mo AI stack answers, the Arabic locale resolves,
> firmware and Flatpaks have nothing pending.

> **Session I — unified visual-system work (2026-07-25, full audit in
> `artwork/MOOS_VISUAL_AUDIT_2026-07-25.md`).** The repository and live 4K/225%
> Plasma session were inventoried rather than judging metadata alone. The 16-theme
> family now shares one generated MoOS design system: complete high-visibility
> Plasma controls and blur masks, rebuilt Aurorae frames and functional button
> states, one safe KWin frost profile, crop-safe Graphite/Tidal wallpaper masters,
> low-duty ambient motion, RTL clock/picker corrections, exact Qt/GTK/GSettings
> readback, and an owned nine-application icon family. Existing-user revisions are
> `THEME_REV=22` and `MOOS_THEME_REV=10`. Both local images then built from the
> fresh `7.1.4-204.fc44.x86_64` base: generic and NVIDIA passed the identity,
> experience, initramfs/OSTree, Plymouth and bootc gates; NVIDIA carried the
> matching 610.43.03 open driver, and both produced 50 Qt WebEngine spell-check
> dictionaries including Arabic and English. The booted audit image was still
> `44.20260724.1` from a **local unverified containers-storage origin**, so it is
> diagnostic evidence only: signed CI publication, signed staging and
> post-reboot proof remain mandatory and must not be claimed until recorded.

> **Session H — the first-boot session (2026-07-17, full writeup in `docs/FIXES_2026-07-17b.md`).**
> ISO `44.20260717.190` was walked end-to-end in QEMU (all green: splash+ring, DE live
> keyboard, 9-page installer, moving progress bar, offline install, target first boot on
> Vienna time) and the walkthrough caught two shipped bugs no gate had seen: (1) the zram
> storm — moos-hardware-adapt's first-boot re-tier restarted systemd-zram-setup@zram0
> bare, tripping dev-zram0.swap into start-limit-hit and leaving a fresh install's first
> boot with two failed units and NO swap (fix: config-equality skip + stop → daemon-reload
> → reset-failed → one start); (2) the live session kept KDE's 5-minute autolock and
> LOCKED the screen over its own running installer (fix: moos-live-polish, gated on
> rd.live.image, writes liveuser's kscreenlockerrc/powerdevilrc — never /etc/xdg). Both
> gates broken-once and watched go red. Forensics trick that cracked it: power the VM off,
> guestfish the journal out of the target disk, read it with `journalctl --directory`.

> **Session G — the polish session (2026-07-17, full writeup in `docs/FIXES_2026-07-17.md`).**
> Wallpapers v2: the four family themes now carry LIT-SILK art (crest-lit bands, aurora
> veil, screen-blended neon edges — make_wallpaper rewritten; Canva retried, account AI
> quota still hard-blocked). A new pre-baked `ring.png` comet-ring sprite orbits the emblem
> on every doorway (login gained a scale-settle entrance, a hairline spark and drifting
> motes; lock and logout carry mirrored rings; the logout watermark breathes). The bar
> brand widened to 1.5× panel height with the ring orbiting continuously. NEW widget:
> `org.moos.heroclock` — the glass desktop Hero Clock (bilingual, live seconds, the mark in
> the corner; every size derives from min(width,height) — height-only sizing shoved the
> seconds strip out of the card on a square window, found live). Lock clock's tick
> breathes; panel clock glints on hover. Gates extended (heroclock completeness + the
> always-on shader ban loop), both watched go red.

> **Session F — the brand session (2026-07-16, full writeup in `docs/FIXES_2026-07-16c.md`).**
> The owner's vector logo landed (`artwork/logo/`) and the animated MoOS brand now lives on
> every doorway surface: the login scene is `org.moos.ui2.greeter` (a Plasma/Wallpaper package
> the greeter's wallpaper process loads — the greeter QML itself is compiled into the binary),
> the lock screen brand breathes and its clock has a floor below it (4K collision fixed), the
> logout greeter carries the animated mark + a draining countdown hairline and its NINE action
> icons are -symbolic now (they all drew as solid teal blobs — isMask over full-colour disc
> icons), and the bar opens with `org.moos.brand` (animated emblem + MoOS-glance popup;
> Kickoff stays the launcher, wearing view-app-grid-symbolic; THEME_REV is 18). Every family
> theme got real designed wallpaper art (glass waves per palette — make_wallpaper rewrite;
> Canva was quota-blocked, the deterministic generator ships the art). All motion is
> Animators-only over pre-baked sprites (`artwork/generate_login_scene.py`); the Lottie file
> in the logo delivery has zero keyframes and is provenance only.

> **State on 2026-07-16 (session E).** The machine is green: `moos-selfcheck` all-pass,
> `post-update-check.sh` 39/0, **zero failed units**, boot to graphical in 4.8 s of userspace
> (GRUB timeout already 1 s; firmware is the remaining 10 s and is out of OS control). The
> NVIDIA fix is proven on hardware (~9 ms/token on CUDA). `fwupd-refresh` — the last open bug —
> now **completes successfully** (Result=success; keep the `10-moos-log-the-error.conf` drop-in
> so any recurrence names its own cause).
>
> **Session E found and fixed the two-stores regression:** Bazaar installed at SYSTEM scope
> (moos-setup's checklist) showed a second visible store, because the old hide only edited the
> per-user flatpak export. The fix is `/usr/bin/moos-one-store` — a NoDisplay override in
> `~/.local/share/applications`, the one dir that outranks BOTH export scopes — called by
> `moos-store-browse` AND `moos-setup`. Three new gates hold it: a static relationship gate in
> `tests/verify_user_experience.py` (both installers must route through the helper; the helper
> must not touch flatpak exports), and a live `moos-selfcheck` check that resolves Bazaar's menu
> entry the way the menu does. All were broken on purpose and watched go red.
>
> **Session E then drove the installer wizard end-to-end for the FIRST time** (ISO 176 in QEMU,
> QMP mouse/keys — synthetic input works in a VM even though it does not on the real machine)
> and the walkthrough caught two shipped bugs no gate had ever seen:
>
> 1. **The wizard called a SUCCEEDING install "stalled."** The backend finished the whole
>    install (target disk bootable, `Installation complete!`, 92 PROGRESS lines written) while
>    the front-end reported FAIL: the launcher's `--cache` already IS `~/.cache/moos-installer`,
>    and the QML appended another `/moos-installer` to it, polling a file nobody writes.
>    One-line QML fix; a three-party relationship gate (moos-open ↔ launcher ↔ QML) now pins
>    the status path.
> 2. **The live session typed English (US) on the owner's German keyboard** while the panel
>    indicator claimed "DE". KWin (Wayland) compiles the keymap locale1 answers — NOT the
>    shipped kxkbrc — and the image shipped neither of localed's sources, so the live ISO ran
>    with localectl fully unset. Proven live: `sudo localectl set-x11-keymap de,ara pc105`
>    flipped the running session to German instantly. The image now ships
>    `/etc/vconsole.conf` (KEYMAP=de) and `/etc/X11/xorg.conf.d/00-keyboard.conf` (de,ara,
>    alt_shift_toggle), both gated against kxkbrc's LayoutList as a relationship;
>    moos-firstboot still rewrites both per the install answers (its no-recipe fallback now
>    matches the image instead of reverting to `us`), and `moos-selfcheck` says explicitly
>    when KWin refused to answer and only config was checked.
>
> The installed target from that walkthrough also proved: timezone page 5 works (searched
> "vienna", selected Europe→Vienna), disk/account/confirm/hold-to-commit all behave, and the
> ISO's offline install path (embedded image, no network) completes.
>
> **ISO `44.20260716.179` (commit `0149736`) is built, WALKED AGAIN end-to-end in QEMU and
> verified fixed:** the live session types German (physical z,z,y,y → "yyzz"; localectl answers
> de/de,ara), the wizard's progress bar moves (34% → 80% → success page), and the whole journey
> is photographed. It lives in `~/Desktop/MoOS-ISO/` with BUILD-INFO.txt, sha256 and proof/.
> The older ISOs (175 broken splash, 176 stalled-wizard) are deleted. The QMP driver scripts
> used for walkthroughs are kept in `~/iso-test/` (drive.py, detype.py).
>
> **Two traps this session cost real time on, both worth knowing before you start:**
> - **Root is `pkexec`, not `sudo`.** `50-moos-devmode.rules` authorises the local active wheel
>   user for `org.freedesktop.policykit.exec`, so `pkexec` runs as root with no prompt while
>   `sudo` still asks for a password. A previous session hit `sudo`, concluded root was out of
>   reach, and left the decisive `fwupd` test unrun for a day. But the rule's allowlist is
>   narrow (`systemctl`, `journalctl`, `bootc`, `rpm-ostree`, `moai-do`, `moos-*`) — `pkexec`
>   on anything else (`localectl`, `cp`) **raises a password dialog on the owner's screen**, and
>   polkit's cache expires every few minutes so it keeps coming back. Do not make the owner
>   authenticate for your own diagnostics.
> - **Mo AI's units are USER units.** `systemctl is-active moai.service` in the system scope
>   answers `inactive` — for a unit that does not exist there. Use `systemctl --user`.

## Active visual work: the MoOS theme FAMILY (UI2 engine)

> **Update 2026-08-06 — the box in the bar, and the rim scale that let it exist.**
> The owner reported "المربع الي بالبار الي يطلع": opening the MoOS launcher wrapped the
> dock button in a hard bordered rectangle. It was NOT the launcher's own art. Plasma's
> shell (`/usr/share/plasma/shells/org.kde.plasma.desktop/contents/applet/CompactApplet.qml`,
> the `expandedItem` FrameSvgItem) paints `widgets/tabbar.svg` behind ANY panel applet for
> as long as its popup is open, choosing the prefix from the panel edge — a bottom dock asks
> for `south-active-tab`. MoOS shipped that prefix as `raised` @ 0.84 ringed by `primary` @
> 0.88 on all four edges at radius 9: a near-opaque slab with a bright accent border, drawn
> full applet height behind the button. Confirmed by reading the shell QML and by the
> owner's own screenshot, whose popup text (`جلسة محلية موثوقة`) exists only in
> `org.moos.brand/contents/ui/LauncherView.qml:1305` — so the launcher popup was open.
>
> - **The open-applet slot is now a lit slot, not a box** (`generate_moos_plasma_surfaces.py`):
>   all four `*-active-tab` prefixes are `primary` @ 0.12 with **no rim at all**, at radius
>   20 of a 56 px block so the frame reads as a capsule at any dock height. The same four
>   prefixes are a PlasmaComponents TabBar's active tab, which becomes a soft segmented-
>   control fill — one piece of art, both roles improved.
> - **No task tile paints a slab any more** (`MoOSUI2/widgets/tasks.svg`, the authored
>   master all 16 recolour from). Every state used to fill the TEXT colour at ~0.10 across
>   all nine cells plus a 1 px accent hairline along its top edge; on a light family member
>   the text colour is near-black, so the ACTIVE app sat in a grey rectangle with a lit
>   edge — visible in the live 4K light session before the change. Running state is now
>   carried by the bottom indicator alone: `focus` and `attention` rise from their own bar
>   through `nova-lift` / the new `nova-alert` gradient (0.30 / 0.34), `hover` is the one
>   state that still fills and it TINTS with `luminous` @ 0.09 instead of darkening.
> - **The rim scale is written down and gated.** An interaction state is told by its fill;
>   the rim only hints an edge. Resting ≤ 0.22, hover ≤ 0.25, selected/pressed ≤ 0.40,
>   keyboard focus 0.40–0.60 (it must stay unmistakable). The pager's active desktop was
>   `luminous` @ 0.94 and its hover 0.64; menubaritem pressed was 0.64 — all brought in.
>   Floating glass (tooltip, popup background, dock capsule) is deliberately EXEMPT: there
>   the rim is the only thing separating the surface from live wallpaper.
> - **Three new gates in `tests/test_moos_ui2.py`** hold it for all 16:
>   `test_open_applet_slot_is_never_a_bordered_box`,
>   `test_dock_task_states_never_paint_a_tile_box`,
>   `test_native_controls_hint_an_edge_instead_of_drawing_a_box`. They read the GENERATED
>   packages, not the generator, so a hand-edit cannot slip past either.
> - **Verified live** on the 4K@225% session (`MoOSUI2NovaLight`) via the home-override
>   preview: launcher opened over D-Bus, screenshot read — soft borderless capsule behind
>   the button, active app carries a bar with no grey rectangle, pinned launchers carry
>   nothing. The override was removed again before commit. 59/59 CI repo gates green.
> - **Not changed, on purpose:** `desktoptheme/Nova` is retired UI1 geometry with no
>   metadata.json (Plasma never lists it), so the new gates scope to `MoOSUI2*`. The clock
>   chip's 1 px border and its two-dash "Tidal Cut" signal are deliberate identity, not
>   drift. The live dock is still ONE panel containment while `moos-bar.conf` defines two
>   slabs — rewriting a locked, in-use panel layout mid-session was out of scope here.

> **Update 2026-07-30 (ship-readiness milestone) — the adversarially-verified desktop audit
> and its fixes.** Full handoff with root causes, measurements, rejected approaches, design
> decisions and the deferred-work plan: **`docs/SESSION_HANDOFF_2026-07-29.md`** (13 commits,
> `0124a6d..24a2126`+docs). At handoff the dev machine still BOOTS 44.20260729.452
> (digest ff45fe58…) — every fix below lands at the next update+reboot; the milestone CI is
> run 30497407799. A 16-agent audit swept every desktop surface (windows, session screens,
> icons, shell, apps; the motion inspector died and was re-run separately); 8 findings were
> confirmed by independent refuters, and the dropped-by-cap findings were recovered from the
> journal. Everything actionable landed on `main` today, each verified live before push:
>
> - **Windows (`2290dbb`, THEME_REV 24):** the maximized titlebar was the `title` gradient
>   sampled outside its span — flat #527F79 slab, 3.12:1 captions, identical across all 7
>   light palettes. No gradient basis survives FrameSvg's centre-cell stretch (measured:
>   userSpaceOnUse AND objectBoundingBox both render a barely-moving ramp), so the maximized
>   bar is now FLAT in the ramp's terminal colour — worst caption contrast across 16 themes
>   is 10.28:1, focus flash 1.06–1.16:1 (was 2.95). Buttons centred (ButtonMarginTop=6 +
>   ButtonMarginTopMaximized=6 — the maximized key does NOT inherit), minimize glyph
>   centred (y=9.15), and the Aurorae blur mask is GONE: the frame is opaque, and
>   hasElementPrefix("mask") made KWin blur behind it every frame. Material decision on
>   record: persistent surfaces solid, glass for transient shell surfaces only.
> - **Session (`97f2b89`, `c9a9c25`, `17ecd65`):** lock/login Arabic strings wore Noto via
>   `font.family: "Inter"` (no Arabic coverage) at six sites — all bind IBM Plex Sans Arabic
>   now (`font.families` still fails to load on Qt 6.11.1; see Logout.qml). The brand comet
>   ring's head was a razor chop (fade peaked at the same degree the sweep zeroed) — capped
>   over 6°, all 21 comet copies regenerated (plymouth's full-circle ring.png is a different
>   asset, untouched). The lock halo dropped the untintable glow-cyan/violet rasters for
>   accentA/accentB RadialGradients — the mirrored logout surface made this exact change
>   earlier and the two had drifted apart on 14 of 16 palettes.
> - **Shell (`3cf2e4b`):** the portal's remote-control SNI is UNHIDDEN — hidden SNIs do NOT
>   surface when Active on Plasma 6 (measured during a live remote session), so hiding it
>   blinded the user to being watched; the gate contract flipped with it. The launcher's 16
>   explicit `layoutDirection` lines double-mirrored under plasmashell's LayoutMirroring and
>   rendered BACKWARDS in RTL — deleted, verified live (nav right, grid right-to-left). The
>   dock pill folds date digits to Latin like the lock clock and hero card (one numeral
>   system per glance). Footer: MoOS Themes button wears its app's own icon; the Xwayland
>   bridge hide-list gained its Arabic Id. Existing sessions migrate via THEME_REV 24.
> - **Apps (`c046c81`, `a151e61`, `181217e`, `0124a6d`):** a palette token named `onAccent`
>   beside `accent` is SIGNAL-HANDLER syntax to QML — the binding was swallowed and every
>   primary label rendered #000000 on the accent in three apps; renamed `accentText`, the
>   name is now banned by gate. The updater reported the STAGED deployment as "Current
>   system" (deployments[0]); it selects booted==true now. The a11y sweep's duplicate
>   `Accessible.name` had made Mo Store fail to COMPILE (caught by the engine probe + the
>   build's smoke gate; CI run 30484023329 died exactly there). Store: RTL chips snap to
>   reading start, PageUp/Down + ensure-visible keyboard scrolling, details-sheet polish,
>   sane tab order. Theme picker got the full keyboard treatment. Recovery's rollback button
>   no longer clips at 4K/225%, bilingual strings carry LRI/PDI isolates. Installer timezone
>   rows no longer TypeError on Accessible.name.
> - **Icons (`ea8c591`):** the commissioned Mo AI orb (byte-exact master, still
>   gate-enforced) now sits on the family squircle via `artwork/generate_moai_icon.py` —
>   85.9% solid box at 256px, same as moos-store to the pixel.
> - **Dev-machine note:** `~/.config/plasma-localerc` had drifted to en_US (the next login
>   would have been an English shell); restored to `LANGUAGE=ar` + ar_SA formats. The "DE"
>   tray indicator is the de,ara keyboard layout — deliberate, see the 07-16 note below.
> - **Motion (re-run inspector, fixes in the final batch):** the gating ARCHITECTURE is
>   fully clean — 309 infinite loops swept, every one behind `longDuration > 1` plus a
>   visibility/state term. Four cost bugs found and fixed same-day: the Store's index
>   pulse was unbounded when the catalogue build FAILS (~12% of a core forever; now bounded
>   by `indexPoll.running` + a failed-state label), Mo AI's ambient scene cost ~13% for the
>   window's whole life (now `paused: !root.active`), the logout countdown bar ignored
>   animations-off (950ms Behavior now gated, 16 variants), and Mo AI's remote live-ring
>   lacked its visibility term. plasmashell's ~9% idle reading is UNATTRIBUTED — the desktop
>   was not quiet during measurement; re-measure via the post-update checklist.
> - **Deliberately NOT done:** window titlebars stay opaque (documented material decision,
>   not an oversight); the hero logo artwork itself is untouched (owner's brand asset — only
>   its seating/halo/comet integration changed); the wallpaper `images_dark` duplication was
>   REFUTED as a defect (composefs dedupes to one object on disk, and images_dark is the
>   live dark-variant path).
>
> **Update 2026-07-16 (session C) — read this before touching themes, the keyboard, or Mo Remote.**
> Full writeup in `docs/FIXES_2026-07-16.md`. Four things landed and are on `main`:
>
> 1. **Theme FAMILY.** MoOS is no longer "ONE look" — it is a **family** on the single UI2
>    engine. Graphite (dark) + Tidal (light) stay the base; four palette-driven members were
>    added — **MoOS Nova, Amethyst, Midnight, Aurora** — each a full package set under
>    `org.moos.ui2.*`, generated by `artwork/generate_moos_themes.py` from
>    `artwork/moos-themes/palettes.json` (it recolours the working UI2 SVGs/decoration + reuses
>    `generate_moos_ui2.py`'s colour math; it does NOT revive the retired Nova/UI1 lineages).
>    `moos-theme <dark|light|nova|amethyst|midnight|aurora|list>` switches instantly;
>    `moos-apply-theme` is family-aware so a pick persists. `verify_identity.py` +
>    `tests/verify_user_experience.py` + `tests/test_moos_theme_safety.py` now enforce the
>    *family* (all MoOS-branded, no foreign, no old generation). The old top-level
>    `org.moos.nova`/`org.moos.ui` are still forbidden. `build.sh` hides the stock Breeze
>    Global Themes from the picker (Hidden=true, non-destructive) — Breeze stays the fallback
>    engine. Every theme was verified applying live. Passages below saying "ONE MoOS look"
>    describe the pre-family state.
> 2. **Keyboard = de,ara.** The owner's hardware is a GERMAN keyboard, so the default xkb layout
>    is now `de,ara` (`system_files/etc/xdg/kxkbrc`, installer `xkbForLang`), Alt+Shift toggle.
>    This is a LAYOUT only — the UI language stays bilingual ar/en (no German catalogues). The
>    old comment saying "de,ara was wrong" assumed US hardware; it does not, here.
> 3. **Mo Remote + terminal fixes** (session B→C): Arabic typed from the phone now works
>    (`agent-linux/InputInjector.cs` routes non-ASCII through clipboard, not portal keysyms);
>    the terminal's bold text is legible again (the Konsole scheme's Intense fg was inverted);
>    generic `monospace` no longer resolves to Kawkab (fontconfig binding).
> 4. **Build robustness.** `build.sh` writes the Tailscale repo file inline instead of
>    curl-ing it — a `pkgs.tailscale.com` 504 took a whole build down on 2026-07-16.

The owner rejected MoOS UI revision 15 as visually insufficient after reviewing
it on the installed machine. It remains installed and untouched as the explicit
fallback. The isolated **MoOS UI2** Graphite Dark / Tidal Light family is now
implemented, selected as the working-tree default, and proven in both variants
on the installed Plasma session. Its palette, package IDs, generated-image
prompts, independent dashboard, real screenshots, measured proof and rollback
rules are documented in [`artwork/MOOS_UI2_DESIGN.md`](artwork/MOOS_UI2_DESIGN.md).
**Correction (2026-07-27): `moos-theme ui1-dark|ui1-light` does not exist.** It was
planned, documented here as supported, and never implemented — `grep -c ui1
system_files/usr/bin/moos-theme` returns 0 — and UI1 itself was removed from the
shipped image in July 2026, so the command could not work even if it were added.
An agent trusting this line would run a nonexistent rollback on the owner's daily
driver. The real fallbacks, in increasing order of blast radius:
`moos-theme undo` (previous MoOS theme) → `plasma-apply-lookandfeel
org.kde.breezedark.desktop` (leave the MoOS family entirely) → `sudo rpm-ostree
rollback` + reboot (previous image). Do not leave user-local UI2 staging shadows
after testing.

### Revision 16.1 — the surfaces UI2 had missed

A full sweep of every visual surface found four places where the desktop was UI2
and the thing sitting on it was not. All four are fixed, and each one is now held
by a gate that was broken on purpose and watched go red:

- **A QML binding loop, live in the shipped image.** `WeatherScene.qml` bound
  `sourceSize.height` to `sourceSize.width` — both halves of one `QSize`, so the
  property depended on itself. Qt resolves that by *dropping* the binding, so the
  weather art decoded at a stale size and plasmashell logged the loop 21 times.
  The build already ran the dashboard and already grepped its log for
  `binding loop`, and **could never have caught it**: under
  `QT_QPA_PLATFORM=offscreen` the card is never laid out to a real width, the
  binding never re-enters, and Qt has no loop to detect. Reproduced deliberately.
  The gate that bites is therefore **static**, in `verify_user_experience.py`.
- **The login screen was still the retired Nova generation.** Everything moved to UI2 except the greeter,
  so the machine booted to a NovaHorizonII login screen and a Graphite desktop a
  second later. The gate could not catch it because it asserted the literal string
  `"NovaHorizon"` — it was pinning the bug in place. It now requires the login and
  lock screens to name the **same** wallpaper.
- **The boot splash was Nova navy** (`#050A14`, `#2E7BFF` bar) on a graphite OS. It
  is now gated against `artwork/moos-ui2/palette.json` rather than a hard-coded hex.
- **The kde-settings profile still named `org.moos.nova`** — a third family, which
  the theme switcher cannot even reach. This is the exact cascade layer AGENTS.md
  blames for Plasma resolving a stale name and persisting Breeze.

The pattern in three of those four: **the gate named a constant, and the constant
went stale.** The replacements gate a *relationship* (login screen == lock screen;
splash == palette; kde-profile == the image's own default), so the next theme
family inherits them for free.

`artwork/MOOS_UI2_DESIGN.md` ends with a coverage-gap list that is now largely
**closed**: teal MoOSUI2/MoOSUI2Light icon themes are built in build.sh,
libadwaita/Flatpak apps get the UI2 palette (moos-ui2.css + the gtk-4.0 read
hole), the lock screen is the MoOS shell-package override, and the desktop
dashboard lives INSIDE the wallpaper (org.moos.ui2.wallpaper — below the icons,
so it can never cover them). The Welcome (apps/welcome) is a real onboarding
wizard again; Mo Store (apps/store, /usr/bin/moos-store, org.moos.store.desktop)
is the standalone storefront. Verify against the gates, not this paragraph.

## Previous visual work: MoOS UI

The working tree contains the new **MoOS UI** dark/light visual pair, first-party
Mo AI and Mo PC Remote icon masters, a warm matched wallpaper, and the glass
desktop-widget evolution. The implementation contract, palette, generated-image
prompts, rollout rules and one-command regeneration path are in
[`artwork/MOOS_UI_DESIGN.md`](artwork/MOOS_UI_DESIGN.md). The retired Nova
generation (UI1-era) is NO LONGER installed — it was removed from the shipped
image in July 2026; see the removal note at the end of this section and use the
real fallbacks listed under "Active visual work" above. Do not hand-edit
generated MoOS UI package output;
change its masters and regenerate it. (Removed 2026-07-27: `artwork/generate_moos_ui.py` was the UI1 generator. It copied `plasma/desktoptheme/Nova` -> `MoOSUI`, and neither directory has existed in `system_files/` since UI1 was removed from the shipped image in July 2026 — running it produced nothing. UI2 is generated by `generate_moos_ui2.py` and `generate_moos_themes.py`.)

Visual revision 15 incorporates direct hardware review: the desktop widget is now
a wide animated live dashboard, and the Light dock owns a warm-mauve FrameSvg with
the exact Dark geometry. Both variants pin adaptive transparency off so Plasma
cannot turn only the Light dock into an opaque white slab. Current hardware proof
is under `artwork/moos-ui/live-tests/*-v2.png`.

---

## The shape of the thing

| Repository | What it is | How it reaches the user |
|---|---|---|
| `~/moos-image` | The OS. A bootc image built from `Containerfile` + `build_files/build.sh` + a literal filesystem tree in `system_files/`. | Push to `main` → GitHub Actions builds **two editions** (`moos`, `moos-nvidia`), signs them with sigstore, pushes to `ghcr.io/moalfarras-sys/`. The user's machine stages the resolved signed digest through `moai-do update`. |
| `~/MoPlayerMoOS` | The IPTV player. Flutter. Its own repository: **github.com/moalfarras-sys/MoPlayerMoOS**. | **Vendored** into `moos-image/moplayer/` by `just sync-moplayer`, then compiled *inside* the image by a Containerfile stage. The image ships the binary, never the toolchain. |
| `~/MoPlayerios` | An iOS build of MoPlayer. Not part of the OS. | — |

The machine this is developed on **boots the thing being developed**:
`ghcr.io/moalfarras-sys/moos-nvidia:latest`, signature-enforced. That is the whole
reason the gates below exist.

### Changing MoPlayer, end to end

MoPlayer has two homes and they are not equal. Its **repository** is where the work
happens; `moos-image/moplayer/` is a **snapshot** of it, and the snapshot is what
the image compiles. A change that lives only in one of them ships as half a change.

```
1. work + commit in ~/MoPlayerMoOS   (`just check` there: analyze + 114 tests)
2. push it                            → github.com/moalfarras-sys/MoPlayerMoOS
3. cd ~/moos-image && just sync-moplayer
      ↳ refuses a dirty MoPlayer tree — vendoring copies `git ls-files`, so an
        UNCOMMITTED file is copied by nobody and the image fails on a missing import
      ↳ also installs the launcher/.desktop/icons into system_files/ itself
4. commit the re-vendor, push          → CI builds and signs both editions
5. on the machine: `moai-do update`, then reboot from the MoOS power UI after the signed digest is staged
6. `./tests/post-update-check.sh`      → confirms the booted digest IS the published one
```

Never edit `moos-image/moplayer/` by hand. It is generated, and the next
`sync-moplayer` will silently erase you.

---

## The five traps that have actually bitten

These are not style notes. Each one shipped, or nearly shipped, and each one cost
hours to find because **the gate was green while the thing was broken**.

### 1. The shadowed-config trap
The image is right, the user still does not get it. `/etc/xdg/…` and
`/usr/share/…` are *defaults*; a file in `~/.config` or `~/.local/share`
**shadows them forever**. Staging a fix into the home directory to "prove" it on
the running desktop leaves that shadow behind. `moos-apply-theme` exists to remove
those shadows once the system copy is correct — extend it rather than writing a
new one.

**Corollary that cost two hours today:** `moos-selfcheck` verified the *system's*
keyboard layout (`localectl`, which said `de,ara`) while the *session* was running
`us`, because fcitx5 had rewritten `~/.config/kxkbrc`. A check that reads the
image instead of the running desktop cannot fail. It asks KWin now.

### 2. A gate that matches its own comment
Every file here documents the bug it prevents — so a gate written as
`"Kawkab Mono" in text` passes forever, because the *comment* names Kawkab Mono.
`tests/verify_user_experience.py` has a `code()` helper that strips comments.
**Use it.** And after writing a gate, **break the thing on purpose and watch the
gate go red.** A gate that has never failed has never been tested.

### 3. The build context is not the git tree
`COPY system_files/ /` copies from the *working tree*, and `.gitignore` has no say
in it. The image shipped `/usr/bin/__pycache__/moai-control.cpython-313.pyc` — the
bytecode cache of the build machine — while CI, building from a fresh clone,
shipped nothing of the sort. **Two different images from one commit.**
`.containerignore` now excludes it, and a gate in `build.sh` fails the build if any
`__pycache__` reaches `/usr/bin`.

And note the pattern syntax: `__pycache__/` matches only the **context root**. It
must be `**/__pycache__/`. The first version of that file looked right, read right,
and excluded nothing. The gate caught it.

### 4. Vendoring drops what git does not track
`just sync-moplayer` copies `git ls-files` from `~/MoPlayerMoOS`. An **untracked**
file is copied by nobody: the vendored tree keeps the import and loses the file,
and the image fails twenty minutes later, inside a container, on a missing URI. It
**refuses a dirty tree** now, and a gate walks every relative import in the
vendored source and fails if the target was not vendored.

### 5. The local LLM owns the graphics card
MoOS ships a local model that holds **~6 GB of an 8 GB card** while loaded. With
that little left, EGL cannot make a context: `eglMakeCurrent failed` → libepoxy
asserts → **the process aborts**. The user's own OS killed its own video player,
silently. `/usr/bin/moplayer` calls `moos-gpu-headroom` first, which unloads *only*
the brain and only when the card is nearly full. A gate requires the launcher in
`system_files/` to be **byte-identical** to MoPlayer's own
`packaging/moos/moplayer` — the guard lived in only one of them for two hours, one
`install -D` away from being lost.

**Practical rule:** check `nvidia-smi` free memory before launching anything
GPU-heavy for a screenshot. Do not open a browser to "set up a scene" — that
exhausted VRAM and took KWin down with a SIGSEGV.

---

## Verification: how to actually see things

- **Synthetic input does not work on this machine.** `ydotoold` runs, the uinput
  device exists, and KWin receives nothing — in logical *or* physical coordinates.
  Proven by clicking a window's close button in both spaces and watching the
  process live. **Never plan a loop that needs to drive a GUI.** Reach the state
  from outside instead: `moplayer --section live`, `moplayer <subscription-link>`,
  a route the app opens on. If a state can only be reached by clicking, add an
  honest CLI seam (it is usually a feature someone wanted) or ask the user.
- **Screenshot:** `spectacle -b -n -f -o out.png` (not `grim` — wlroots only), then
  crop and zoom with ImageMagick and *read the image*.
- **A new window opens behind a fullscreen app.** Make a temp virtual desktop,
  switch, launch, capture, switch back, remove.
- `konsole --geometry` **is not a valid option** — the process exits instantly and
  no window appears. This silently blinded a whole session.

---

## MoPlayer: the IPTV facts that decide the design

Measured against the maintainer's real subscription, not assumed:

- A subscription is sold as **one link**:
  `…/get.php?username=U&password=P&type=m3u_plus`. Pasted into an M3U field it
  *works* — and yields channels and nothing else. Read as what it is (a panel plus
  an account), the same string opens the whole Xtream API: **12,653 channels,
  20,187 films, 10,550 series.** That is `lib/services/source/source_link.dart`,
  and it is used by both the login screen and the command line.
- **`max_connections = 1`.** One stream at a time. Never design a flow that tunes a
  channel to show a preview — the user knocks their own stream off the air. This is
  why the live screen's third pane follows the channel you are *looking at*.
- Panels lie about their own API: this one answers `get_short_epg` and
  `get_simple_data_table` with `[]` for **every** channel, while `xmltv.php`
  returns 2,587 programmes. An "empty" guide is usually an unimplemented endpoint.
- The panel publishes **duplicate** `<programme>` elements, and serves its
  catalogue with 32 identical-artwork recorded matches first. Sort by `added` or
  the film wall reads as a failed image load.
- The home page's football comes from that guide, joined against the user's own
  channels, so every card is one press from playing. A fixture on a channel the
  account does not carry is **not drawn** — a card that cannot be pressed is a
  disappointment dressed as a feature.

---

## Owner's UX rules (do not "improve" these away)

- The dock has **seven** slots: search · home · live · movies · series · favorites ·
  settings. Home *is* in the dock — the corner logo was not enough.
- Every browse page: **groups (vertical) · wall · preview**. The preview follows
  hover **and keyboard focus**.
- **The mouse wheel scrolls the page.** A rail must never turn a vertical wheel
  into sideways movement — the home page is a column of rails, so that makes
  everything below the fold unreachable. Shift+wheel and the hover arrows move a
  rail. There is a widget test that fails if this regresses.
- Settings is an Apple-style panel. Its Updates section is honest: MoPlayer ships
  *inside* the image and `bootc` replaces the whole OS atomically, so there is no
  self-update button, because there is no self-update.
- The brand palette is **measured off `assets/branding/logo.png`**, not chosen
  beside it. A test opens the PNG and fails if the tokens drift.

---

## Gates — what runs, and where

| Gate | Runs in |
|---|---|
| `tests/verify_user_experience.py` | CI (before the build) **and** `just build` |
| `tests/test_device_plan.py` | same |
| `tests/test_moai_do.py` | same — covers all 17 `moai-do` actions and rejects anything off the list |
| `build_files/verify_image_experience.py` | *inside* the image, after every package and rebrand |
| `__pycache__` / bytecode-cache gate | inside the image, at the end of `build.sh` |
| MoPlayer bundle completeness | inside the `moplayer-build` stage |
| MoPlayer: `flutter analyze` + 114 tests | `just check` in `~/MoPlayerMoOS` |

They were honour-system until today: **not in CI, not in `just build`**. If you add
a gate, wire it into both, and break it once to prove it fires.

---

## Working rules

- `git status --short` before every batch. Another agent may be in the same tree —
  it has happened, and a commit landed on the wrong branch because of it.
- Do not commit, push, or change the installed image without the owner asking.
- Every visible fix adds a gate or a test that would have caught it.
- Do not invent a new file under `system_files/` before searching for the surface
  that already does that job.
