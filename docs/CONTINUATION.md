# Theme System Continuation

Date: 2026-08-07
Branch: `fix/remove-heroclock-seed`

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

Generators: `artwork/generate_moos_plasma_surfaces.py`, `artwork/generate_moos_ui2.py`, `artwork/generate_moos_themes.py`, `artwork/tools/gen-nova-plasma-svgs.py`.

Tests: `tests/test_theme_shadow_cleanup.py`, `tests/test_theme_wallpaper_steady_state.py`, `tests/test_theme_wallpaper_readback.py`, `tests/test_moos_ui2.py`, `tests/verify_user_experience.py`.

## Remaining

- Install the changed runtime tools into a disposable live image or build the image, then repeat the login/reboot test against `/usr/bin` rather than the repository copy.
- Run visual checks at 100%, 125%, 150%, and 200%, and test launcher, clock/calendar, tray, RTL/LTR, and window decoration after a real session restart.
- Run the complete CI-equivalent gate list and the appropriate image build.

## Handoff

The next agent should inspect `git status` and the existing parallel Horizon Bar changes before staging. Do not reset them. First run `python3 tests/verify_user_experience.py` after reconciling its expected revision and bar contracts, then run the complete theme-specific suite. Keep the backup branch/tag intact. The live user currently wears Nova Light; restore it with `moos-theme nova-light` or use `moos-theme undo` after testing.
