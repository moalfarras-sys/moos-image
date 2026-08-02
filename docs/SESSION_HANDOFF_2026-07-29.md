# Session handoff — 2026-07-29 → 2026-07-30 (ship-readiness milestone)

**Read this if you are a new agent picking the project up.** It records what was
found, what was measured, what shipped, what was rejected and why, and what
remains — with no claims that were not verified by a command that ran.

| Fact | Value at handoff |
|---|---|
| Repo HEAD | `24a2126` (`docs(truth): the 2026-07-30 ship-readiness milestone…`) + this doc's commit |
| Booted image (dev machine) | `moos-nvidia` **44.20260729.452**, digest `sha256:ff45fe58dd34…` |
| Staged before this session | 44.20260729.461 (pre-dates every fix below — superseded) |
| Session commits | 13 fix/docs commits, `0124a6d..24a2126`, all pushed to `origin/main` |
| CI for the full milestone | run **30497407799** (commit `24a2126`) — result recorded in PROJECT_STATE when it lands |
| THEME_REV | 23 → **24** (existing sessions migrate tray list, purge qmlcache, one shell restart) |
| Origin of the work | 16-agent adversarial audit (workflow `moos-desktop-audit`): 8 findings confirmed by independent refuters, 2 refuted, cap-dropped findings recovered from the journal, dead motion inspector re-run as a solo agent |

---

## 1. Changelog — the 13 commits in order

| # | SHA | What | Verified how | Needs reboot? |
|---|---|---|---|---|
| 1 | `0124a6d` | Mo Store failed to COMPILE at HEAD: the a11y commit set `Accessible.name` twice on four controls (`main.qml:1106` "Property value set multiple times"). Kept the truer line each time; the category tiles' name was a bare COUNT ("7") — now the category label. | Engine probe before/after; CI run 30484023329 failed at exactly this line (both editions), proving the smoke gate works | yes |
| 2 | `459e936` | 110 literal corner radii → `fs(N)` in the four apps. | Pixel-neutral at default: 0 differing px whole-window after masking the hero-ring animation (animation proven by two same-code frames 6s apart = 10,302 px in same bbox). Scaling proven in-engine: fs identity at 10pt, fs(24)=53 at 22pt, live-Rectangle histograms shift | yes |
| 3 | `c046c81` | `onAccent` → `accentText`. A property named `on<Capitalized>` beside sibling `accent` is SIGNAL-HANDLER syntax: script bindings are silently swallowed as handler bodies (colour stays `#000000`); literal values are a compile error ("Cannot assign a value to a signal"). Mo AI alone was correct — no sibling `accent`. Gate now bans the name in all four apps. | Minimal repro both ways; root values #000000→#E1F0EC in-engine ×4 apps; Welcome CTA pixels (0,0,0)×394 → (225,240,236)×398 on an otherwise identical frame; gate negative-tested | yes |
| 4 | `a151e61` | Updater showed the STAGED deployment as "Current system" (`deployments[0]`); now selects `booted==true`. | Live: old expr → .461 (staged), new → .452 (booted); patched app launched, read .452 off the window | yes |
| 5 | `2290dbb` | Aurorae ×16: maximized bar flat terminal-colour (see §2.1 for the two REJECTED gradient repairs), buttons centred (`ButtonMarginTop=6` **and** `ButtonMarginTopMaximized=6` — the maximized key does NOT inherit), minimize glyph centred (y=9.15), blur mask REMOVED (material decision §3.1). | Live Aurorae override + kwrite: maximized bar uniform #E1F0EC, glyph centres 35.7/36.0/36.0 vs bar centre 35.5; restored glyphs 74.0×3 vs caption ink 77.2 (descender bias); WCAG sweep ×16 themes: worst 10.28:1, flash delta 1.06–1.16:1. Gates negative-tested. Override removed after | yes |
| 6 | `97f2b89` | Lock/login: 6 × `font.family: "Inter"` (no Arabic — falls back to Noto) → "IBM Plex Sans Arabic". `font.families` is NOT usable (Qt 6.11.1 fails the whole component — documented in Logout.qml). Deliberately kept: Inter on the clock DIGITS (always Latin, `latinNumerals()` design) and the "MoOS" wordmark (documented brand choice). | Full lock screen rendered FROM THE REPO TREE (merged package overlay + `QML2_IMPORT_PATH`, `kscreenlocker_greet --testing`, UI woken with ydotool): 0 load failures, captions share letterforms with the Plex date | yes |
| 7 | `c9a9c25` | Comet ring head cap: `fade *= min(1, ang/6)` — the head was full brightness one degree after full transparency (a razor chop orbiting every boot). 21 copies regenerated; plymouth's `ring.png` is a DIFFERENT full-circle asset, untouched. | Alpha at ring radius: 0→18→70→150→220 across 0.5..6°, no step; splash rendered from repo tree — both arc ends rounded | yes |
| 8 | `17ecd65` | Lock halo: fixed cyan/violet rasters → RadialGradients from the lock's own `accentA`/`accentB` (mirrors the logout's documented change; drift on 14/16 palettes). Dead PNGs unshipped. **History note:** this commit's `git add -A` also swept the then-in-flight Batch-D store/welcome/installer edits in — its stat is wider than its story (see §5). | Lock rendered from repo tree, 0 load failures, halo drawn from session accent | yes |
| 9 | `3cf2e4b` | Shell (THEME_REV 24): remote-control SNI **unhidden** (§3.2); launcher RTL fixed by DELETING 16 explicit `layoutDirection` lines (double-mirroring under plasmashell's LayoutMirroring rendered them backwards); dock pill date digits fold Latin via `latinNumerals()`; themes button wears `moos-themes` (its own app's icon); Arabic bridge Id added to hide list. Gate contract FLIPPED for the portal + variant list enforced; both negative-tested. | Live plasmoid overrides + shell restart: nav rail right, grid right→left, footer caption right, pill "الخميس 30 يوليو", footer = 6 circles + 2 app tiles. Overrides removed after | yes (live session already migrated by test, image lands on reboot) |
| 10 | `181217e` | Apps batch: store RTL chips snap to reading start; chips keyboard; PageUp/Down + window-level `revealFocus()` ensure-visible across 6 Flickables; details-sheet dedup/close-glyph/chip alignment; tab order (bulk-add demoted); localized window titles; installer headline differentiated; installer timezone `Accessible.name` TypeError fixed (`parent.modelData` from delegate ROOT = contentItem); theme picker full keyboard treatment; Recovery height 760×700 + log min-height + LRI/PDI isolates on bilingual strings. | Headless load probes ×4 apps; `py_compile`; UX gate; live Mo Store render (RTL + light-on-teal CTA). RTL snap position, tab traversal and reader output need the post-reboot hardware pass (§6) | yes |
| 11 | `ea8c591` | Mo AI icon seated on the family plate: new deterministic `artwork/generate_moai_icon.py`; wrapper embeds the commissioned 1024 master BYTE-EXACT (gate unchanged) over the verbatim sibling plate; ladder ×11 sizes rendered from the same composition. Gate now also requires the plate rect (negative-tested). | Rerun = byte-identical no-op; solid box at 256px = 85.9% — equal to moos-store to the pixel; QtSvg render (Plasma's real loader) matches the ladder beside siblings | yes |
| 12 | `aebceb0` | Motion: store index pulse bounded by `indexPoll.running` + failed-state label (was ~12% of a core FOREVER when the catalogue build fails; production path 0.0%); Mo AI's 6 ambient loops `paused: !root.active` (scene measured 12.95% for the window's whole life); logout countdown 950ms Behavior gated on `longDuration > 1` ×16 variants; Mo AI remote live-ring gains its missing `root.visible` term. | Inspector measurements (65s CPU buckets, per-thread splits); both apps probe-load clean; regeneration ×16 verified | yes |
| 13 | `24a2126` | Truth files: PROJECT_STATE dated milestone block + motion verdict; ROADMAP THEME_REV=24 section. | — | no |

---

## 2. Rejected approaches (do not retry without new evidence)

**2.1 Maximized-titlebar gradient repairs — both measured and rejected.**
The canonical `title` gradient is userSpaceOnUse y=12..52 (the RESTORED bar);
`decoration-maximized-center` is a 24×24 rect at y=0..24 → renders the clamp
(flat start stop). Two repairs were built and measured live:
- re-spanned userSpaceOnUse (y=0..24): rendered a barely-moving ramp
  (82,127,121)→(86,131,125) across 64 device rows;
- objectBoundingBox (0..1): **identical** barely-moving ramp — the effective
  box is the whole window rect, not the visible strip.
A garish red→blue probe proved the right element was painting. Conclusion
(now encoded in `generate_moos_aurorae.py` + both gates): **FrameSvg stretches
the center cell and no SVG gradient basis survives the stretch; the maximized
bar can only be painted flat.** The flat colour chosen is the title ramp's
terminal stop — grounded, per-palette, WCAG-clean.

**2.2 `font.families` for per-script font fallback.** Qt 6.11.1 on this stack
rejects the property and the whole component fails to load (documented in
Logout.qml, re-confirmed this session). Use the one family that carries both
scripts (IBM Plex Sans Arabic).

**2.3 Hiding the remote-control SNI as "one click away".** The old comment
claimed hidden items surface when Active. Measured false on Plasma 6 during a
LIVE remote session: nothing anywhere on screen. Never re-hide
`xdg-desktop-portal-kde`; the gate now fails if it returns to the list.

**2.4 Explicit `layoutDirection: rtl ? RightToLeft : LeftToRight` inside
plasmashell popups.** LayoutMirroring inverts it back to LTR. The mirroring is
the one system; un-annotated rows were correct all along.

---

## 3. Design decisions on record

1. **Material hierarchy:** persistent surfaces (window frames) are SOLID for
   predictable caption contrast; Liquid Glass belongs to TRANSIENT shell
   surfaces (dock, popups, notifications). The Aurorae blur mask is gone
   (KWin computed blur behind opaque pixels every frame); gates enforce its
   absence. Revisiting = reintroduce mask + re-verify contrast ×16 themes.
2. **The remote-control indicator is sacred.** Visible whenever a session is
   Active. This outranks tray minimalism on an OS that ships Mo PC Remote.
3. **One Arabic typeface per surface** (IBM Plex Sans Arabic); Inter only for
   always-Latin digits and the wordmark (documented at each site).
4. **One numeral system in shell chrome:** Latin digits, locale's own
   day/month names (`latinNumerals()` in lock clock, dock pill; hero card was
   already Latin). The bilingual calendar popup deliberately shows both.
5. **Maximized bar = title ramp's terminal colour, flat** (see 2.1).
6. **Ambient motion pauses when the window loses focus** (`paused:
   !root.active`, resumes in place) — decorative loops must not cost an
   eighth of a core in an unfocused window.
7. **The commissioned Mo AI master and the MoOS logo are owner assets** —
   byte-exact master enforced by gate; only seating/integration may change.
8. **Family plate geometry is the icon contract** — 85.9% solid box; the gate
   now requires the plate under the Mo AI master.

---

## 4. Audit outcomes that must not be re-reported

- **REFUTED — wallpaper `images_dark` duplication:** composefs dedupes to ONE
  object on disk (filefrag: 48/48 same physical extents; one object in a
  254k-object store), and `images_dark` is the live dark-variant runtime path.
- **REFUTED — login-clock "ungated animation":** the image ships
  `ShowClock=false` (`/usr/lib/plasmalogin/defaults.conf`); the clock renders
  on this dev machine only via a machine-local `/etc/plasmalogin.conf`
  preference, and the greeter autologin-skips here anyway.
- **REFUTED — `plasmalogin.conf` "silent override":** documented deliberate
  scope in `moos-wait-drm` (ShowClock is a preference, not a mask) + build
  gates assert what a build can reach.

---

## 5. Honest notes / drift observed live

- **`17ecd65` mixed-commit:** a `git add -A` swept a background agent's
  in-flight app edits into the lock-halo commit. History is pushed; the
  lesson is a standing rule (memory + here): stage explicit paths while any
  agent may be writing.
- **Locale drift on the dev machine:** `~/.config/plasma-localerc` had
  silently become `en_US` ([Translations]+[Formats]) and the systemd-user env
  matched — the running Arabic shell was living on its ORIGINAL session env,
  and the next login (or any plasmashell restart, which is how it surfaced)
  would flip the shell English. Restored: `LANGUAGE=ar`, `LANG=ar_SA.UTF-8`
  (file + `systemctl --user set-environment`). Root cause of the drift is
  UNKNOWN (suspect: a KCM touch during audits). Watch for recurrence.
- **Orphan processes:** the dead motion inspector left `qml-qt6 …moai/main.qml`
  (PID 458817) burning 12–13% of a core for 2h07m — killed. A leftover
  `bento.qml` window from the dead session had earlier voided a screenshot
  diff — also killed. Post-session check confirmed zero leftover test
  processes.
- **plasmashell ~9% CPU at "idle": UNATTRIBUTED.** Measured under an actively
  busy dev desktop (Cursor 29%, kwin 15–21%, the orphan above). Every
  deployed MoOS widget was individually exonerated. Re-measure on a quiet
  session before calling it a defect (§6).
- **Booted vs repo:** the booted .452 predates everything above; the running
  session carries only the THEME_REV-24 tray migration side-effects of live
  testing. Everything else lands at reboot.

---

## 6. Deferred work — actionable plan

| Task | Why | Priority | Where | Acceptance | Test | Risks | Needs |
|---|---|---|---|---|---|---|---|
| Post-reboot verification | 13 commits land at once; the gates were green but five shipped traps in history were green-while-broken | **Critical** | `tests/post-update-check.sh` + manual: maximized titlebar, lock captions, launcher RTL, store CTA colour, Mo AI idle CPU | post-update-check all green; maximized bar #E1F0EC/palette terminal; `top` shows moai < 2% unfocused | run script + spectacle crops + 30s CPU buckets | a regression ships to the daily driver | reboot, real HW |
| plasmashell idle re-measure | ~9% reading unattributed (§5) | High | live session, no dev apps running | < ~2% sustained over 60s on quiet desktop, or an attributed culprit | `/proc/<pid>/stat` deltas 6×10s, per-thread | chasing a phantom from a busy session | reboot + quiet session |
| ~~Welcome/Installer full keyboard page-scrolling~~ **Code/gate closed 2026-08-02; installed walk remains** | the shared Store contract now covers both wizards | Medium | `apps/ui/KeyboardViewport.js` + Welcome/Installer pane bindings | PageUp/Down move every scrollable page; Tab pulls off-screen items into view | focused structural gate passed; live Tab-walk remains in the installed visual pass | low — shared bounded helper | built Qt/KDE image for live proof |
| Mo Store AppStream long descriptions | details sheet suppresses the duplicated summary but has no real long description | Medium | store `main.qml` details sheet + catalogue index builder (`build_files/verify_store_catalog.py` ecosystem) | details shows AppStream `<description>` when present; sheet sizes to content | render details for 3 apps with/without descriptions | index size growth; RTL text quality of upstream descriptions | no |
| VPS `moos-cloud` update verification | user asked for the VPS updated; it self-updates from ghcr, and interactive SSH is blocked by a Tailscale re-auth (see memory `moos-cloud-server-access`) | Medium | VPS peer via tailscale | VPS reports the new image version after its self-update window | `ssh` once re-authed, or its status endpoint | none — signed-image pull only | Tailscale re-auth by owner |
| Store tab-chain edge cases | agent's own caveats: bulk-add reached only after instantiated cards (virtualized grid); Shift+Tab from bulk-add follows default chain | Low | store `main.qml` All-apps | deterministic forward+backward chain | live Tab/Shift+Tab walk | over-engineering a rare path | no |
| Hero logo (Welcome) integration polish | audit called the glossy 3D orb on mint "the biggest visual break"; the ORB itself is the owner's brand asset | Low (owner decision) | `apps/welcome` hero area — seating/halo only, never the asset | owner signs off a mock before any change | side-by-side renders | brand sensitivity | owner input |
| `qsTr` vs bilingual audit | titles were `qsTr()` with no catalogs; other strings are inline-bilingual — one mechanism should win | Low | all four apps | zero `qsTr` or a real translation catalog | grep + render ar/en | churn | no |

**Closed by design (not debt):** opaque titlebars (§3.1); `images_dark` (§4);
Inter on digits/wordmark (§3.3); the calendar popup's dual locale (§3.4).

---

## 7. Update & reboot procedure (what happens after CI)

```bash
# 1. wait for CI run 30497407799 (or successor) == success on all 3 editions
# 2. on the dev machine:
rpm-ostree upgrade          # pulls the new SIGNED moos-nvidia:latest
rpm-ostree status           # staged version/digest MUST match the CI-published one
# 3. reboot is the switch:
systemctl reboot
# 4. after login:
bash tests/post-update-check.sh
```

The dev machine keeps `bootc rollback` / the GRUB previous entry — the .452
deployment stays bootable.
