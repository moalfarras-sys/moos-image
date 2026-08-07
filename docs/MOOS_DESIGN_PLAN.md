# MoOS design plan — start here

**If you are an agent picking up MoOS visual work, read this file first, then
`docs/AGENT_GUIDE.md` (mechanisms + traps), then `AGENTS.md` (the rules).**

This file exists because a full session was spent shipping changes that were all
correct and all invisible, and the owner had to say so five times before the
cause was found. Everything below is measured, with the evidence in
`docs/evidence/`. Do not re-derive it.

---

## 0. The rule that would have saved that session

> **A visual change does not ship until a horizontal luminance scan across the
> changed element and its unchanged neighbour shows ≥ 15 steps.**

Measured on the real 4K session, same row, same wallpaper:

| change | alpha | rendered Δ luminance | visible? |
|---|---|---|---|
| home button resting pill | 0.10 | **11** | no |
| home button resting pill | 0.24 | **21.5** | yes |
| dock glass ramp (alpha only) | 0.15 → 0.30 span | **4 → 9** | barely |

Every value in revs 32–38 was chosen in the 0.05–0.12 band. That band renders as
5–11 steps over pale glass. The eye needs ~15. **Reading the diff is not
verification — measure the screen.**

```python
# the measurement, verbatim
from PIL import Image
im = Image.open(shot).convert("RGB"); w, h = im.size
y = h - 72                       # a row through the element
lum = lambda p: (p[0]*299 + p[1]*587 + p[2]*114)//1000
changed = lum(im.getpixel((x_in_element, y)))
neighbour = lum(im.getpixel((x_in_bare_surface, y)))
assert abs(changed - neighbour) >= 15
```

---

## 1. What is cheap, and why — with evidence

### 1.1 The dock cannot carry depth, and that is physics

`docs/evidence/bar-one-capsule-three-families.png`

The dock is translucent glass over a **blurred wallpaper**, so what you see is
dominated by what is behind it. The SVG ramp travels 34 luminance steps;
**9 reach the screen**. Widening alpha further starts destroying the frost the
owner explicitly asked for ("زجاج ضبابي بدون ضلال ابيض و خطوط بالاعلى").

**Do not keep tuning the dock gradient.** It is at its ceiling. Visible work
belongs on surfaces that own their pixels — see §2.

One real bug was found and fixed here: each light family mixed the panel roles
55% toward a near-white tint, which did not tint the ramp but **collapsed** it
(34 steps → 13). The wash now moves *where* the dock sits without changing *how
far* it travels (`_offset_hex` in `generate_moos_themes.py`).

### 1.2 Things that were "transparent" until hovered

This defect appeared **three times** in the same codebase, and it is the single
most common cheapness in MoOS:

| surface | was | now |
|---|---|---|
| home button pill | `"transparent"` | highlight 0.24 |
| launcher app tiles | `"transparent"` | text 0.11, +2px hover lift |
| launcher list rows | `"transparent"` | **correctly** left alone — rows are not cards |

`docs/evidence/dock-home-button-before-after.png`
`docs/evidence/launcher-before-flat.png` → `docs/evidence/launcher-tiles-as-cards.png`

**When you add a surface, ask what it looks like at REST**, not on hover. A
control that is invisible until touched is not a control.

**The one value that works for all 16 themes:** `Kirigami.Theme.textColor` at low
alpha. Text is dark on light themes and light on dark ones, so the same alpha
lifts a card off its surface in both directions without tinting everything with
the accent. Reserve the accent for states that *mean* something (hover, press,
selection).

### 1.3 The rim scale (THEME_REV 32), still the law

An interaction state is told by its **fill**; the rim only hints an edge.

```
resting ≤ 0.22 · hover ≤ 0.25 · selected/pressed ≤ 0.40
keyboard focus 0.40–0.60   ← the one exception, it must be unmistakable
```

Floating glass (tooltip, popup, dock capsule) is exempt: there the rim is the
only thing separating the surface from live wallpaper. Gated by
`test_native_controls_hint_an_edge_instead_of_drawing_a_box`.

---

## 2. Where the visible work actually is

Ranked by pixels-owned, i.e. by how much a change can possibly show:

1. **The launcher popup** (792×576, opaque) — owns every pixel. Tiles are cards
   now; the sidebar, search field and the two hero cards are still flat and are
   the next obvious win.
2. **The desktop** — currently **bare wallpaper**, no widgets at all. Biggest
   untapped surface on the whole system. Blocked, see §3.1.
3. **Lock / login / logout screens** — full-screen, opaque, and untouched this
   session.
4. **Mo AI / Mo Store / MoPlayer** app windows — own their pixels.
5. **The dock** — at its ceiling (§1.1). Stop here.

---

## 3. Open bugs, with everything known

### 3.1 The desktop refuses every widget — UNSOLVED, highest value

```
org.kde.plasma.systemmonitor  →  Error: Could not create the widget!
org.kde.plasma.minimizeall    →  Error: Could not create the widget!
org.moos.heroclock            →  Error: Could not create the widget!
```

This is why the owner said "I don't know where to manage the widgets". It is
**not** MoOS-specific — stock KDE applets fail identically on the same
containment, while the **panel accepts widgets fine**.

Ruled out already, do not re-check:
- `immutability` — both containments confirmed `0` in the file, shell restarted
- kiosk lockdown — `/etc/kderc` is Fedora stock, no `[KDE Action Restrictions]`
  anywhere
- `containmentlayoutmanager` — installed
- MoOS package validity — all four render fine under `plasmawindowed`
- (`org.kde.plasma.analogclock` is **not installed** on Fedora; an early test
  used it and produced a false conclusion. Use systemmonitor/minimizeall.)

**Untested and most likely:** every test ran against a plasmashell launched by
hand (`setsid plasmashell`) rather than by the session. **Test this first after
a clean reboot** — if it works there, the bug is in the manual-launch
environment, not MoOS.

If it reproduces on a clean session: instrument `plasmashell` with
`QT_LOGGING_RULES='kde.*=true;org.kde.plasma.*=true'` and trace
`Containment::createApplet`.

### 3.2 The context island is invisible in practice

It only appears while a media player is **playing**. Correct for an island that
must not be clutter — but it means it can never be the thing that makes the
desktop feel different. Mo AI "thinking" and Mo PC Remote states are still
missing, and both need a **regular marker file**: `FolderListModel` cannot see
unix sockets (measured — 3 matching names, 2 sockets + 1 regular file, model
reported `count=1`).

### 3.3 Never developed

- **The clock widget** — 4 changed lines all session, all border alpha.
- **Dock icon hover motion** — unreachable; `icontasks`' `Task.qml` is compiled
  into `org.kde.plasma.taskmanager.so`. Needs a MoOS task manager (large).
- **100–200% scale sweep** — everything is verified at 4K@225% only.

---

## 4. My own process errors — do not repeat them

Four in one session, all of the same family: **claiming verification that did
not happen.**

1. **Two concurrent `just build` runs.** I read the image the *first* tagged and
   reported it as the second. Verified "rev 41" against a rev-40 image. → One
   build at a time; confirm with `grep -c 'Successfully tagged' <log>`.
2. **Six pushes in one afternoon.** GHCR answered `403 permission_denied —
   secondary rate limit`, which reads like a broken token. It hit one edition
   and left `moos` a commit behind. → **Batch commits, push once.**
3. **A gate that globbed only `*.svg`** and reported `moos-logo` missing — it
   ships as png in `hicolor/*/apps/`.
4. **A gate that globbed `/usr/share/icons`** and so tested the *runner*, not the
   repo: `preferences-system-time` exists on a desktop and not in CI. It passed
   locally and turned CI red on all three editions.

→ A gate must read only the repository, and must check what the real loader
checks.

---

## 5. The next session, in order

1. **Reboot first**, then retry §3.1 on a session-launched shell. That one
   answer unblocks the largest surface on the system.
2. If widgets can be placed: ship `org.moos.heroclock` on the default desktop
   via `layout.js` (new profiles) + a once-per-rev migration (existing users,
   add-once semantics so a removal is respected).
3. Launcher, second pass: sidebar, search field and the two hero cards still
   read flat. Same rule as §0 — measure before shipping.
4. Lock / login / logout — untouched, full-screen, opaque.
5. Only then revisit motion.

**Every step: change → apply live → screenshot → measure ≥15 → then commit.**
