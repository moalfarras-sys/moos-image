# MoOS visual & experience roadmap

Written 2026-09-06 after a live audit of `moos-arm-oracle` that started from one
complaint — *"I asked you to fix and improve the system and I see no
difference"* — and found that the complaint was correct, for reasons no
file-level gate could see.

Read `MOOS_DESIGN_PLAN.md` first (the ≥15 luminance rule and which surfaces can
carry a change). This file is the ordered work that follows from the audit.

---

## 0. Why nothing looked different — the four findings

These are the measurements, not opinions. Each is now fixed and gated.

| # | What was wrong | Evidence |
|---|---|---|
| V1 | **The desktop had no motion at all.** Not "reduced" — none. | `AnimationDurationFactor=0` in the user's kdeglobals; `blur/magiclamp/squash/scale/slide/dimscreen/dialogparent` all `false` |
| V2 | **`moos-visual-tier` never told the running session anything.** | `kwriteconfig6` was called without `--notify`, so KConfig emitted no change signal and the whole profile landed only at the next login |
| V3 | **The `essential` tier disabled even the free effects.** | Idle `kwin_wayland` sits at ~1% of one core with `scale/squash/slide/dimscreen` ON; the real cost on this box is Remote's screen capture, not a 200 ms single-window transform |
| V4 | **KDE and GTK windows disagreed about which side the buttons go on.** | kwinrc `ButtonsOnLeft=XIA`; GSettings and the xdg portal both `appmenu:minimize,maximize,close` |

**The lesson to carry forward:** every one of these passed every existing gate,
because the gates read files and these bugs live in *what the running session
did with those files*. When adding a visual gate, ask what the compositor
actually loaded, not what the config says.

---

## 1. The rule this roadmap adds

> **A motion or theme change is not shipped until the RUNNING session has been
> asked what it loaded.**
>
> ```bash
> gdbus introspect --session -d org.kde.KWin -o /Effects --only-properties | grep loadedEffects
> gsettings get org.gnome.desktop.wm.preferences button-layout
> gdbus call --session -d org.freedesktop.portal.Desktop \
>   -o /org/freedesktop/portal/desktop \
>   -m org.freedesktop.portal.Settings.Read <schema> <key>
> ```
>
> `loadedEffects` is the one that matters. A `[Plugins]` key set to `true` for an
> effect that is not in that list is a setting nobody is reading.

KWin decides at session start whether animations are enabled at all. A session
that starts with `AnimationDurationFactor=0` will not load a single animation
effect, and **no amount of live reconfiguring changes that** — the profile
applies at the next login. Say so plainly rather than claiming a live fix.

---

## 2. Ordered work

| ID | State | Work | Closure evidence |
|---|---|---|---|
| V1 | done, needs a session | Restore the motion profile; remove the stale `AnimationDurationFactor=0` | `loadedEffects` contains scale/squash/slide/dimscreen after the next login |
| V2 | done | `moos-visual-tier` writes with `--notify` | `test_moos_visual_tier.py::test_every_config_write_notifies_the_running_session`, bite-tested |
| V3 | done | `essential` = balanced minus blur | Same file, `test_essential_keeps_the_cheap_motion_and_still_refuses_blur` |
| V4 | done | `moos-theme` writes the GTK mirror of `ButtonsOnLeft` | `test_window_button_consistency.py`, bite-tested both directions |
| V5 | done, needs a reload | VS Code drew its own window controls at the LEFT, over its own menu, hiding `File` and `Ed` of `Edit`. Set `window.titleBarStyle: native` so KWin's MoOS frame is the title bar | Re-crop the top-left strip after a VS Code restart; `File` and `Edit` legible, MoOS circular controls present |
| V6 | **closed, no defect + gated** | All five first-party QML windows (moai, installer, settings, store, welcome) root in `ApplicationWindow` with no frameless hint, so KWin owns their title bar and the VS Code collision cannot occur. `test_first_party_window_frame.py` keeps it that way | Source audit + bite-tested gate |
| V7 | **closed, no defect** | The dock was suspected of a weight mismatch between tray glyphs and app icons. Measured instead — see below. Nothing to fix | Every element clears ≥15 against its own plate |
| V8 | **open** | The desktop is bare wallpaper. `MOOS_DESIGN_PLAN.md` §3.1 unlocked `createApplet`, and §5 forbids auto-seeding a widget again (rev 43's heroclock was rejected on sight). Offer widgets through a *chooser* the user opts into, never a seed | A first-run affordance that places nothing until clicked |
| V9 | **open** | Complete the 100/125/150/200/225 % sweep for the launcher, dock and popups | A frame per step; no clipped label, no control off-plate |
| V10 | **open** | Lock / login / logout final artifact frames across locale and scale | Frames from the signed image, not a live session |

---

## 2b. V7, measured and closed — the dock is fine

A first pass eyeballed the dock and called the tray glyphs "lighter than the app
icons". A first *measurement* with guessed band coordinates then reported the
clock chip at delta 11, below the ≥15 rule. Both were wrong: the bands mixed the
chip's own plate with the wallpaper behind the capsule.

Locating each element by scanning for contiguous bright columns in the dock band
(y 1032–1068), then sampling the plate from the clear gaps beside each element:

| element | x | plate | ink | delta |
|---|---|---|---|---|
| MoOS wordmark | 579–653 | 29 | 239 | **210** |
| app icons | 686–1026 | 28 | 254 | **226** |
| tray glyphs | 1055–1181 | 28 | 255 | **227** |
| DE + volume | 1293–1346 | 36 | 179 | **143** |
| clock divider | 1369–1390 | 82 | 108 | **26** |
| clock text | 1392–1502 | 82 | 159 | **77** |

Every element clears the rule. The clock reads lowest only because its chip has
its own lighter plate (82 against the capsule's 28) — that is the chip design,
not a contrast fault.

**The process lesson, which is the reusable part:** a luminance measurement is
only as good as the coordinates it samples. Locate the element first — scan for
its actual columns — then sample its plate from a gap *beside* it. A band chosen
by eye will happily report a defect that is not there, and this one nearly
bought a "fix" for a dock that never needed one.

## 2c. V6, closed — why MoOS's own windows cannot hit the VS Code bug

The collision the owner reported is not "buttons on the left is wrong". It is
narrower and worth stating precisely, because the fix follows from it:

> Buttons on the left are safe **only while the compositor owns the title bar**.
> KWin reserves that strip, so nothing in the client area can be underneath it.
> An application that draws its OWN title bar has to reserve the space itself,
> and an application written for right-hand buttons does not.

All five first-party QML windows — `moai`, `installer`, `settings`, `store`,
`welcome` — root in `ApplicationWindow` (Kirigami or QQC2) with no
`FramelessWindowHint` and no custom title bar, so they take the MoOS Aurorae
frame and the collision is structurally impossible. Nothing needed changing.

`tests/test_first_party_window_frame.py` now holds that: no first-party window
may go frameless, and each must root in a real `ApplicationWindow`. Bite-tested
by adding `Qt.FramelessWindowHint` to Mo Settings and watching it go red. A new
app under `system_files/usr/share/moos/apps/` is covered automatically.

Third-party apps stay a per-app matter: VS Code was fixed by handing the title
bar back (`window.titleBarStyle: native`), not by moving MoOS's buttons.

## 3. What must not be done

- **Do not enable blur on a software renderer.** It is the one per-frame
  full-screen pass, and on this class of machine it is also being encoded and
  streamed. The `BlurStrength` ceiling of 15 is a readability limit; "off" on
  `essential` is a cost limit. Both stay.
- **Do not restart KWin or `mo-remote-personal` on a machine whose screen is Mo
  PC Remote.** Restarting the compositor there is not a refresh, it is turning
  the monitor off.
- **Do not auto-place desktop widgets.** Rev 43 did; it was rejected on sight
  and removed in rev 44.
- **Do not "fix" a user's own setting silently.** `AnimationDurationFactor=0`
  was treated as a deliberate choice by `moos-visual-tier` for exactly the right
  reason. It was cleared here because the owner said they wanted motion back.
