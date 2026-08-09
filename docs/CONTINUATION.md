# Unified Experience Continuation

Date: 2026-08-09
Branch: `main`

## 2026-08-09 — rev-49 adversarial hardening pass (second session, same branch)

The signed `.574` deployment rebooted at 12:44 and reproduced the exact defect
class rev 49 targets on a machine that did not yet carry rev 49: the new
plasmashell logged `Invalid empty URL` for `org.moos.brand` and
`org.moos.island`, the installed (rev-48) `moos-bar-apply check` had no
current-shell health boundary, and the user saw two Plasma error tiles instead
of the launcher. Running THIS branch's `moos-bar-apply apply 49` performed the
one bounded recovery restart and healed the live bar; the same plasmashell PID
then survived a second apply (fast path, no restart), `check` printed
`bar: ok`, and pointer click/click, Meta and Escape all toggled the production
launcher on the real panel (driven by a closed-loop ydotool+KWin-cursorPos
harness, since one large relative move rides pointer acceleration into the
screen-corner clamp and misses every target).

A 26-agent adversarial review of the rev-49 diff (4 reviewers, every finding
independently re-verified against the running system) confirmed seven real
defects, all fixed here and all covered by executable or pinned gates:

- the payload fingerprint and the journal health gate omitted
  `org.moos.nova.clock`, the third first-party bar package — the masked
  error-icon state rev 49 exists to close stayed open for the clock. Both now
  cover all three zones, the fingerprint root is overridable
  (`MOOS_PLASMOID_ROOT`) and `tests/test_moos_bar_single_panel.py` now RUNS
  `bar_payload_generation`, asserting a 64-hex digest that moves when any of
  the three packages changes;
- after its one recovery restart, a persistent health failure idled ~20 s in
  the readback loop and was mislabelled a readback failure; it now fails fast
  with the truthful message;
- `Plasmoid.activationTogglesExpanded = true` was assigned on the Plasma::Applet
  attached object, which has no such property — a silent no-op. The property
  is now declared on the root PlasmoidItem, where it actually owns the
  keyboard/Meta/AT-SPI expansion route;
- the island's Flatpak artwork translation unconditionally rewrote every
  matching `/tmp` URL, permanently suppressing artwork for host-installed
  Chromium-family browsers whose raw URL was already readable. The bridge is
  now probe-driven: translation first, raw-URL fallback armed by Image.Error,
  re-armed per artwork change;
- the island's compact click toggled `expanded` from post-dismiss state (the
  exact press-capture race rev 49 fixed in the launcher); it now captures on
  press like the launcher;
- AT-SPI volume increase could walk the player to 150% while the slider read
  100%; both accessible actions now clamp to the slider's 0..1 range;
- the desktop-file Exec gate skipped everything wrapped in `konsole -e`, so a
  wrapped MoOS launcher could rot silently; the gate now unwraps and validates
  the hosted command.

Separately, the live orbit grid showed the same application twice: the shipped
`preferred://browser` alias resolves to the concrete browser the user had also
pinned (`com.google.Chrome.desktop`). `org.moos.brand` now snapshots the
Kicker `url` role per favourite and retires a `preferred://` alias exactly when
a concrete pin shares its resolved target — user pins are never touched,
distinct targets always coexist, and the prune converges through the existing
snapshot sync. Proven live (grid shows one Chrome; the alias row left the
kactivities DB) and pinned by
`test_launcher_orbit_never_shows_one_application_twice`.

Live second-session evidence (3840×2160, 225%, Arabic RTL, `.574` host with
branch overrides):
`~/.cache/moos-claude-bar-healed.png`, `~/.cache/moos-claude-v50-meta.png`,
`~/.cache/moos-claude-v50-click-open.png`,
`~/.cache/moos-claude-v50-click-closed.png`,
`~/.cache/moos-claude-dedup-test.png`. Focused gates after the fixes:
37/37 UI2, 13/13 one-panel (two new fingerprint tests), user-experience gate
passed.

## 2026-08-09 — live update recovery + real browser/Haruna island proof (THEME_REV 49)

This is a correction and verification layer on the rev-48 shell finish, not a
new launcher, bar, wallpaper or media architecture.

The signed update initially left `org.moos.brand` and `org.moos.island` present
in the panel configuration but rendered as Plasma error icons. The old marker
proved only that the ids existed and therefore suppressed the restart that
healed both QML packages. `moos-bar-apply` now fingerprints its real launcher,
island, configuration and apply payload; accepts that marker only when the
current plasmashell PID has no first-party load failure and the live one-panel
readback agrees; and performs one bounded recovery restart if the new shell
still reports a load failure. Its `check` command uses the same current-process
health boundary. The migration also deletes the retired nested island applet
from both Plasma tray storage shapes while preserving every unrelated tray
child. A second apply kept the same plasmashell PID, proving the healthy fast
path does not restart the shell gratuitously.

Launcher activation now matches Plasma 6.7's installed compact-representation
ownership: the custom MouseArea owns pointer expansion once, while Meta,
Return/Space and AT-SPI emit `Plasmoid.activated()` and let Plasma own that
route. The live Meta and AT-SPI press paths both opened and closed the production
launcher. Search used the existing KRunner query (`firefox`); the first Escape
cleared the query and the second closed the launcher.

The existing Plasma `Mpris2Model` island was tested against two real players:

- Chrome Flatpak exposed `org.mpris.MediaPlayer2.chromium.instance2` through a
  real Media Session. Its art URL was `file:///tmp/.com.google.Chrome.*`, while
  the same-user file lived below
  `$XDG_RUNTIME_DIR/.flatpak/com.google.Chrome/tmp`. The island now derives that
  safe reverse-DNS namespace generically and renders the artwork in compact and
  expanded modes without a browser registry. Play, pause and an AT-SPI
  five-second seek changed the real MPRIS state. Chrome ignored volume writes
  even through direct D-Bus, so browser volume remains capability-dependent and
  is not claimed.
- Haruna then became active automatically. AT-SPI volume changed 0.75 → 0.70,
  mute/unmute restored 0.70, and previous moved 6.83 s → 0.96 s. Closing Haruna
  handed the island back to paused Chrome; stopping all media collapsed it to
  its one-transparent-pixel idle representation with no second bar surface.

The same run caught and fixed a real QML `compactHover is not defined` error,
and added explicit AT-SPI increase/decrease actions for seek and volume sliders.
The one-second position timer still runs only while media is playing and the
timeline is visible. No decorative permanent animation was added.

Native live evidence (3840×2160 Wayland, HDR/WCG) is retained locally:

- `~/.cache/moos-launcher-v49-meta-toggle-open.png`
- `~/.cache/moos-launcher-v49-forge-light-new-process.png`
- `~/.cache/moos-launcher-v49-live-rtl-scale{100,125,150,200}.png`
- `~/.cache/moos-island-v49-chrome-expanded-artwork.png`
- `~/.cache/moos-island-v49-active-player-haruna.png`
- `~/.cache/moos-island-v49-switch-back-to-chrome.png`
- `~/.cache/moos-island-v49-all-media-stopped-idle-v2.png`

The real output was restored to Forge dark, Arabic RTL and 225%. `moos-bar-apply
check` reports `bar: ok`; no MPRIS test service remains; and all temporary media
fixtures were moved to Trash. A 30-second desktop-only sample at Alive measured
plasmashell 0.866% CPU / 494 MiB RSS. Switching the same scene temporarily to
Still measured 0.300%; Alive and all user services were restored. KWin stayed
13.3–18.3% across Still, Alive, stopped Mo Remote and stopped KRDP, so that
session's separate NVIDIA 4K/HDR compositor baseline is reported rather than
misattributed to a MoOS repaint loop. The earlier clean rev-48 samples remain
the comparable island idle/playing pair.

`just check` passes in full, including the user-experience, QML/UI2, one-panel,
theme, identity, motion, symbolic-icon, device and remote gates. The focused
rev-49 results are 36/36 UI2 and 11/11 one-panel tests. The local image build and
its final digest are the remaining handoff step for this section; do not infer a
new image from the live source preview alone.

## 2026-08-09 — signed `.573` closes offline install, boot and login

The official `.573` pipeline built and signed generic, NVIDIA and cloud images.
Its generic offline ISO installed completely with `-nic none`; the disk picker
showed only the 69 GB target, the embedded image completed, and the installer
reported “MoOS is installed”. After power-off, the same target disk—with no ISO
attached—automatically passed GRUB and displayed the MoOS Plymouth animation.
No manual GRUB command or display-manager restart was used.

The firstboot journal proves the bounded AccountsService `CacheUser` call
returned `/org/freedesktop/Accounts/User1000` before the real display manager
started. On the first greeter, normal input exposed the `moos` account; the
seeded password authenticated and the installed system reached Welcome, the
cardless Horizon desktop and the launcher. This is the complete signed release
proof the `.570` and `.571` failures required.

The earlier `.572` “AccountsService race” attribution is disproved. Plasma Login
Manager 6.7.4 intentionally fades its interface after ten idle seconds:
`GreeterState.qml` sets `greeterTimeoutTimer.interval` to 10000 and `Main.qml`
binds the stack opacity to that state. The wallpaper-only captures were made at
12 and 24 seconds. Returning to VT1 and pressing a normal key restored the user
card immediately without restarting anything. Keep the explicit `CacheUser`
verification as defence in depth, but wake this intentional timeout before
classifying a future greeter screenshot as an account-publication failure.

Release identifiers:

- source revision: `f0739d9036f178ff2a3db904100b1c1d31356358`
- generic signed digest: `sha256:775bfc01c0ae7282fd43907b2949cbe8656757b288a7bb736d7636dbad7252d4`
- NVIDIA signed digest: `sha256:d8c4b13b535472856a8096c03d787791d8af9d2969359d6e7f5c5db3ab37f1de`
- cloud signed digest: `sha256:945d9390b9a612db8f305e8775285f5e053a050f7266b20e53e6324e6676ebfb`
- downloaded ISO SHA-256: `50ac438aad17d9867e8901f2ad764e36f6944f7a9f98093a5986856fd240f138`

## 2026-08-09 — installer success was not boot success; EFI redirect fixed

Signed ISO `44.20260809.571` completed the real no-NIC install and displayed
“MoOS is installed”, proving the deferred Btrfs finalizer fixed `.570`'s 86%
EROFS failure. The mandatory next step — booting that exact target with the ISO
removed — exposed a second fault: GRUB reached its prompt but had no MoOS menu.

The installer deliberately deploys into a Btrfs `root` subvolume so its large
offline image proxy can use and then delete a sibling `bootc-stage`. GRUB starts
from tree ID 5 and the stock EFI redirect therefore looked for `/boot/grub2` in
the wrong tree. Manual diagnosis on the installed disk proved the complete
contract: `blscfg` needs `/root/boot/loader/entries`, while config, kernel and
initrd resolution need `btrfs_relative_path=y` + `btrfs_subvol=/root`. With all
parts set, the real `MoOS (ostree:0)` entry loaded and the disk reached the MoOS
login greeter.

`moos-install-to-disk` now installs that Btrfs-aware redirect atomically after
bootc and refuses to report success if the ESP cannot be patched, synced and
unmounted. `verify_user_experience.py` pins every required GRUB variable and the
fail-closed call. The release gate is intentionally unchanged: build a newly
signed ISO, install with no NIC, remove the ISO, and prove the generated target
boots without manual GRUB input.

## 2026-08-09 — shell finish pass + adaptive MPRIS island (THEME_REV 48)

This pass continues the shipped unified architecture; it does not introduce a
second shell, wallpaper, launcher or media stack.

- The Horizon Hub no longer owns an outer GlassCard. Clock, weather and
  telemetry float directly over `org.moos.ui2.wallpaper`, centred horizontally
  around the upper/middle composition and still below desktop icons. Only the
  internal content separators remain.
- The existing `org.moos.brand` launcher keeps its model, KRunner routes and
  transitions, but retires the split cyan/green wireframe and clipped corner
  strokes. All sixteen generated Plasma themes now use one continuous neutral
  dialog rim from the shared SVG master.
- The single-capsule bar now orders `brand;island;tasks;separator;tray;clock`.
  `org.moos.island` is a direct adaptive panel zone, not a duplicate tray item.
  `moos-bar-apply` migrates existing profiles, removes the retired tray copy,
  and proves the direct island immediately follows the launcher by reading the
  real `AppletOrder`.
- The existing Plasma `Mpris2Model` island is now a complete capability-aware
  media controller: active-player selection, art/application fallback, title +
  source, play/pause, previous/next, progress/seek and volume/mute, with compact
  and hover-expanded representations. It is one transparent pixel when idle.
  Its position timer sleeps unless playing progress is actually visible; the
  old decorative 15-second pulse is gone.

Live proof used the running Wayland desktop at native 3840x2160, HDR/WCG and
225% owner scale. Dark + Light, Arabic RTL + English LTR and isolated QML loads
at 100/125/150/200% all passed (8/8 for launcher, island and Hub). Chrome's real
MPRIS service successfully toggled browser play/pause; controls follow exposed
capabilities, while Chrome's current session advertised seek/volume but ignored
their D-Bus property writes, so those two browser operations are not claimed.
Evidence is committed under `docs/evidence/`:

- `horizon-hub-cardless-dark-4k.png`
- `horizon-hub-cardless-light-4k.png`
- `launcher-neutral-rim-dark-4k.png`
- `media-island-expanded-browser-4k.png`

Twelve-second live samples (background workload was noisy, so they are raw
observations rather than a claimed ratio) measured paused/idle at 1.832%
plasmashell + 1.915% KWin and playing/compact at 0.915% + 0.998%. The NVIDIA
sample reported 0% GPU, 17.62 W and 1656 MiB. No infinite or permanent
decorative island animation remains.

`just check` passed, followed by a complete local `just build`. The resulting
`localhost/moos:latest` is
`3c881239d49a90adffd1a56b81333387072241d36a88007e353f94e4a4a1d91f`
(manifest digest
`sha256:c50b9b8cd1f2e1268d6ae189849c2ba37b9d0600950081868c3a4cd001a8d1e7`,
10,774,099,532 bytes). Its 122 MiB initramfs, real launcher/island/scene hosts,
image-experience, store, identity firewall and bootc lint all passed.

## 2026-08-09 — offline installer finalization fault found, source fix gated

Signed ISO `44.20260808.570` was booted in UEFI QEMU with no NIC and driven
through the real installer. It copied all 261 layers / 10.8 GiB from the local
containers-storage source, deployed the image in 85 seconds and installed GRUB,
then failed at 86% during bootc filesystem finalization with
`Read-only file system (os error 30)`. This is important negative proof: the
offline source and large target-backed staging fixes work, but success must not
be claimed for `.570`.

The cause is the built-in bootc finalizer remounting the shared Btrfs
superblock read-only while the image proxy still owns the sibling
`bootc-stage`. `moos-install-to-disk` now requests `--skip-finalize`, removes
the staging sibling, seeds the target, then performs trim, sync, writable
freeze/thaw, read-only writeback flush and clean unmount itself. Any failure is
reported as disk I/O and partial success is refused. A source gate pins both
the operations and their order. This correction passed `bash -n`, the complete
test suite and the complete local image build; it still requires a fresh signed
ISO, a second no-network install and boot of that exact installed disk before
the installer item can be closed.

## 2026-08-08 — post-boot live QA follow-up (THEME_REV 47)

The first unified release was merged as `b514372b`, published for all three
editions as signed `44.20260808.567` images, used to build the signed-image-pinned
offline ISO, booted in UEFI from both the installed disk artifact and the live
ISO, then staged and booted on the owner's NVIDIA machine. The exact booted
digest was `sha256:261c21f30ceb03a90c7c4927cc175584a2f012e377cc381e763ee7c04060ab01`;
`tests/post-update-check.sh` reported **49 passed, 0 failed**.

That real post-boot review caught one issue the image gate did not: while an
application delegate is detached, `DelegateModel` temporarily exposes
`index=-1`. The launcher's capped stagger used the index directly and therefore
fed `-24ms` to `PauseAnimation`, repeating a warning whenever its model changed.
The delay now clamps both bounds, the source gate holds the exact expression,
and `THEME_REV=47` guarantees existing immutable-image users discard the old QML
cache. Four live open/close cycles on the real 4K RTL shell produced zero
negative-duration or launcher warnings. The same review removed two
user-installed, erroring desktop applets which duplicated the native Horizon
controls; their packages are recoverable from Trash and the previous layout is
backed up under `~/.local/state/moos-ui-audit/`.

The complete `just check` and a second local `just build` pass. The corrected
bootable image is
`e1ef941cce6048cebde68cadff11383438683a20e5d676bebca516e3c980defe`;
its final 122 MiB initramfs, real launcher/scene QML hosts, image-experience,
store, identity-firewall and bootc gates all passed. Signed follow-up
publication, an ISO pinned to that follow-up, and the second post-reboot check
remain release gates at this commit.

## 2026-08-08 — one design core, one transactional theme owner

The complete ownership map and before/after findings are in
`docs/UNIFIED_DESIGN_AUDIT.md`. The short handoff is:

- `artwork/moos-design/tokens.json` and `theme-profiles.json` are the two source
  files; generators produce the installed `org.moos.ui` module and the
  sixteen-profile runtime database.
- `moos-theme` is the sole appearance transaction and exact rollback owner.
  Picker, Control Center, login migration and Fast Remote no longer compete
  with it or replace the MoOS wallpaper scene.
- Launcher, Horizon Hub, bar, first-party apps, session surfaces and all profile
  outputs consume the same component/token language. Dead UI1 art, orphan
  generators, tracked backup copies and the test image are removed and
  absence-gated.
- Live proof covered dark/light Qt and GTK, Arabic RTL, English LTR, output
  scales 100/125/150/200% with the owner setting restored to 225%, the real
  notification protocol, lock/logout/splash/login sources, exact Fast Remote
  round-trip and the redesigned desktop/launcher/settings surfaces.
- Wallpaper animation was changed from endless repaint loops to sparse finite
  pulses. On the real 4K desktop, Gentle/Still measured 0.70% plasmashell CPU
  and Alive 2.85% over a 40-second sample including a pulse.

`just check` and the complete local `just build` both passed for this original
slice. Its subsequent signed release and post-boot result are recorded in the
follow-up section above; the older local image ID is intentionally superseded.

---

## 2026-08-07 — Hero Clock auto-seed rejected (THEME_REV 44)

The owner rejected the auto-placed `org.moos.heroclock` on sight. Removed from
the live desk immediately. THEME_REV 44 clears any remaining instance via
`apply_desktop_scene` (same retire path as deskclock/dashboard) and deletes
`seed_heroclock_once` — no `addWidget` on the desktop again. The plasmoid
package remains installable from the widget browser.

---

## 2026-08-07 — launcher hero cards + heroclock seed (THEME_REV 43)

**CommandCard was invisible at rest.** Resting fill sat at textColour 0.025 /
featured highlight 0.105 — the same 0.05–0.12 band `docs/MOOS_DESIGN_PLAN.md`
§0 measured as 5–11 luminance steps. Raised to the AppTile contract: textColour
0.11 at rest, highlight 0.24 / 0.34 on hover / press, rim ≤0.22 at rest, hover
lift −2 px. SettingCard 0.045 → 0.11. Live plasmawindowed full representation
(`moos-ci-full-representation`) on 4K@225%: card/page edge Δ luminance **25–31**
(gate ≥15). Evidence: `docs/evidence/launcher-hero-cards-rev43.png`.

**§3.1 createApplet — solved, and the first hypothesis was incomplete.**

- `plasma-plasmashell.service` had been **inactive**; plasmashell was an orphan
  under `systemd --user`. Restored the unit (MainPID = plasmashell).
- Session shell alone was **not** enough: createApplet still failed while
  `desktop.locked === true` even with appletsrc `immutability=0`. Clearing
  `d.locked = false` made systemmonitor, minimizeall, brand and heroclock all
  create. `apply_desktop_scene` and `seed_heroclock_once` now unlock first.

**heroclock on the desk, once.** `seed_heroclock_once` adds
`org.moos.heroclock` on the first desktop if absent, writes
`~/.local/state/moos-heroclock-seeded.v1`, and never re-adds after that marker
exists (user removal survives self-heal). Live-proven: `hero-added` then
`hero-already`. Gates updated: exactly one `addWidget` site, and it must name
heroclock — the retired bento/deskclock stay forbidden.

**Not done this round:** lock / login / logout Liquid Glass; panel clock popup;
100–200% scale sweep; dock (still at ceiling).

---

## 2026-08-07 — the bar is ONE capsule again (THEME_REV 33)

**What went wrong.** 44.20260806.546 shipped `moos-bar-apply`, which had never
run on the owner's machine before (the booted image predated it and logged
`moos-bar-apply missing — dock left as found`). On first login after that update
it did what rev 30 designed it to do: it SPLIT the dock into two panels — a
centred capsule holding the launcher and tasks, and a corner capsule holding the
tray and clock. The owner had removed that layout before and rejected it on
sight. The split was flagged as a likely visible change before shipping and was
shipped anyway instead of being held back; that was the mistake.

**The real cause, measured not guessed.** Two `org.kde.panel` containments at
`location=4`: `[Containments][398]` with `icontasks` + `org.moos.brand`, and
`[Containments][430]` with `marginsseparator` + `systemtray` +
`org.moos.nova.clock`, each with its own `[PlasmaViews][Panel N]` geometry in
`plasmashellrc`. Nothing to do with `tasks.svg` — the rev-32 drawing fixes were
correct and are untouched.

**The fix, at the source.**

- `moos-bar.conf` defines ONE `[bar]`: `floating=true`, `lengthMode=fit`,
  `alignment=center`, `applets=brand;tasks;separator;tray;clock`. `[dock]` and
  `[system]` are gone. Plasma mirrors that single order for RTL, so Arabic gets
  the MoOS button on the right and the clock on the left with no second
  definition.
- `moos-bar-apply` no longer splits. `merge_appletsrc()` folds EVERY bottom
  panel into the one holding the launcher, re-homes the applets, re-orders them
  by role from the conf, deletes the emptied containments, and strips their dead
  `[PlasmaViews][Panel N]` groups so Plasma cannot flush the geometry back. It
  runs on every apply, so one panel stays one and two become one. Idempotent: a
  merged bar reports `no-change` and rewrites nothing.
- The live readback now emits `bar=ok` only when exactly ONE bottom panel
  answered; more than one reports `bar=split` and fails, so the revision marker
  is never written while the user is still looking at two slabs.
- `THEME_REV 32 -> 33`. The merge is file surgery on the appletsrc and only runs
  inside the once-per-revision migration, so without the bump an already-split
  desktop would never converge.
- The task area now sits slightly off geometric centre because the system zone is
  heavier. **That asymmetry is accepted.** Perfect centring is what motivated the
  split; it is not worth breaking the object in half. If it is ever addressed it
  must be inside ONE surface.

**The gate that stops it coming back.** `tests/test_moos_bar_single_panel.py`
extracts the real merge program out of the shipped script and runs it against
appletsrc fixtures — including the exact two-panel profile 546 produced. It
proves one bottom panel out, applets in conf order, nothing dropped, idempotent
on a second run, a user's own top/side panel never absorbed, and that
`moos-bar-apply` can no longer write a panel containment at all. Registered in
`.github/workflows/build.yml` and the `Justfile`.

**Also carried (rim scale, THEME_REV 32's rule, applied to the last QML).** The
launcher's brand plate (0.54 -> 0.24), the clock chip's hover edge (0.42 ->
0.25) and the hero clock's emblem plate (0.44 -> 0.22) were the last always-on
accent outlines. Keyboard-focus rings keep their higher ceiling on purpose.

**Live proof (4K@225%, RTL).** After the merge: `PANELS=1`, `bottom`,
`align=center`, `len=fit`, `float=true`, `h=54`; `AppletOrder=424;400;401;402;421`
on containment 398 and no containment 430. Verified as ONE capsule on
`MoOSUI2` (dark), `MoOSUI2Amethyst` and `MoOSUI2Aurora` — `BOTTOM=1` on every
one — then restored to `org.moos.ui2.nova.light`. 60/60 CI repo gates green.

## 2026-08-07 — motion sized to the machine (THEME_REV 34)

`/etc/xdg/kwinrc` shipped ONE motion profile for every MoOS install —
`BlurStrength=15`, magic-lamp minimize, scale open/close, the full set. It was
tuned on the maintainer's RTX 2080 SUPER and it is right there. It was also what
a `moos-cloud` VPS got, and a 4-core laptop on integrated graphics, and any VM
with no render node — where each blur pass behind every panel and menu is CPU
work, every frame. KWin's `supported()` check asks what the BACKEND can do, not
what this machine should do.

**`moos-visual-tier`** (new) reads the hardware and picks the profile.

Probe — read-only, `/sys` + `/proc` + `/dev` only, no external command required:
render nodes (`/dev/dri/renderD*`), the kernel driver bound to each DRM card,
AMD VRAM from `mem_info_vram_total`, cores from `/proc/cpuinfo`, `MemTotal`,
battery presence, and the panel size. Two real bugs the live probe caught and
that are now encoded in the gate:

- sysfs `modes` **lies under the proprietary NVIDIA driver** — this machine's
  3840×2160 panel reports `1920x1080` in `/sys/class/drm/card1-HDMI-A-1/modes`,
  because NVIDIA does its own modesetting. `kscreen-doctor --json` is asked
  first; sysfs is the fallback for a session-less probe.
- NVIDIA publishes **no VRAM figure** anywhere (checked: the
  `/proc/driver/nvidia/gpus/*/information` file has Model, IRQ, UUID, Video
  BIOS, Bus Type, DMA Size — no memory). The driver name proves the card is
  discrete; a size threshold there would never be satisfied on NVIDIA.
- A "16 GB" machine reports **15.4 GiB** once firmware has taken its share, so
  the flagship floor is 15 — the convention `moos-device-plan` already uses. A
  literal 16 classified the maintainer's own desktop as `balanced`.

| tier | when | profile |
|---|---|---|
| `flagship` | discrete GPU with driver bound, ≥8 cores, ≥15 GiB | blur 15/noise 3, magic lamp, scale, slide, dim+dialogparent, animation factor 1.0 |
| `balanced` | any real GPU with a driver, ≥4 cores, ≥6 GiB | blur 9/noise 2, squash instead of magic lamp, no dialogparent, factor 0.85 |
| `essential` | software rendering, no render node, virtual adapter, <4 cores or <6 GiB | blur OFF, window animations off, factor 0.4 |

`AnimationDurationFactor` is the unifying knob: KWin reads it, and so does
Kirigami — so one tier decision scales the compositor's effects AND every
MoOS plasmoid and app animation together. At `essential` it is 0.4, never 0:
Kirigami's `longDuration` floors at 1, so 0 does not read as "off" to QML that
gates on `> 0`, it reads as an animation with a nonsense duration. "Off" stays
the user's own setting.

**It is a default, not a policy.** It writes only the keys it owns, records
exactly what it wrote, and if a key later differs from both what it wrote and
what it would write, that key is yours and it stops touching it. `moos-theme
perf <auto|flagship|balanced|essential>` pins a tier and turns detection off.

**Gate:** `tests/test_moos_visual_tier.py` (21 cases) builds fake `/sys`,
`/proc` and `/dev` trees and runs the REAL probe against them — the maintainer's
desktop, a VPS with no render node, a virtio adapter with and without a render
node, an AMD APU vs a discrete Radeon, a connector directory that must never be
read as a device — plus the blur ceiling, the never-zero animation factor, the
exclusive minimize slot, idempotency, and "a setting the user changed is left
alone". Registered in CI and the `Justfile`.

**Live:** this desktop classifies `flagship` (discrete nvidia, 16 cores,
15.4 GiB, 4K); applying changed 1 setting and a second run changed 0.

---

## Completed

- Added marker-independent, idempotent quarantine for MoOS-owned user data shadows. New shadows are discovered from the package namespace and moved to a dated backup before the marker fast path.
- The live `~/.local/share/plasma/desktoptheme/MoOSUI2Arena` preview was quarantined to `~/.local/share/MoOS/theme-shadow-backups/20260806T202217Z/`.
- Refined the shared task surface generation so hover does not claim pinned applications are running. `normal`, `minimized`, and `focus` retain palette-owned running indicators.
- Regenerated the 16 UI2 family packages and updated the legacy Nova generator contract.
- Added wallpaper steady-state regression coverage. Reconciliation now checks every desktop containment and retries only while the live scene is not ready.
- Created the missing plan and continuation documents.

## Live Validation

- Active session: Wayland; `plasma-plasmashell.service` and `plasma-kwin_wayland.service` active.
- `systemctl --user --failed` returned zero failed units.
- Switched live desktop to `org.moos.ui2.nova.light` and read back `MoOSUI2NovaLight` for the color scheme and Plasma style.
- Read back `/usr/share/wallpapers/MoOSUI2NovaLight` from `plasma-org.kde.plasma.desktop-appletsrc`.
- Ran the repository `moos-apply-theme` script successfully and captured a live screenshot with `moai-screenshot`.
- No new crash or plasmashell restart was observed during the final switch. Existing upstream QML/system-tray warnings remain documented in `PROJECT_STATE.md`.

## Tests

Passed:

- `python3 tests/test_theme_shadow_cleanup.py`
- `python3 tests/test_theme_wallpaper_steady_state.py`
- `python3 tests/test_theme_wallpaper_readback.py`
- `python3 tests/test_moos_theme_safety.py`
- `python3 tests/test_moos_ui2.py`
- `bash -n system_files/usr/bin/moos-apply-theme system_files/usr/bin/moos-selfcheck system_files/usr/bin/moos-theme`
- `python3 artwork/generate_moos_ui2.py`
- `python3 artwork/generate_moos_themes.py`

The full `tests/verify_user_experience.py` gate passed after the final generator and shadow changes.

## Files

Theme runtime: `system_files/usr/bin/moos-apply-theme`, `system_files/usr/bin/moos-selfcheck`.

Current generators: `artwork/generate_moos_plasma_surfaces.py`, `artwork/generate_moos_ui2.py`, `artwork/generate_moos_themes.py`, and `artwork/generate_moos_design_core.py`. The UI1 Nova generator named in older handoff text was retired.

Tests: `tests/test_theme_shadow_cleanup.py`, `tests/test_theme_wallpaper_steady_state.py`, `tests/test_theme_wallpaper_readback.py`, `tests/test_moos_ui2.py`, `tests/verify_user_experience.py`.

## Remaining

- Install the changed runtime tools into a disposable live image or build the image, then repeat the login/reboot test against `/usr/bin` rather than the repository copy.
- Run visual checks at 100%, 125%, 150%, and 200%, and test launcher, clock/calendar, tray, RTL/LTR, and window decoration after a real session restart.
- Run the complete CI-equivalent gate list and the appropriate image build.

## Handoff

The next agent should inspect `git status` and the existing parallel Horizon Bar changes before staging. Do not reset them. First run `python3 tests/verify_user_experience.py` after reconciling its expected revision and bar contracts, then run the complete theme-specific suite. Keep the backup branch/tag intact. The live user currently wears Nova Light; restore it with `moos-theme nova-light` or use `moos-theme undo` after testing.
