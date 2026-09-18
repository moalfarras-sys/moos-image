# MoOS development plan

This is the only product development plan. Current evidence is in
[`PROJECT_STATE.md`](../PROJECT_STATE.md); release mechanics are in
[`RELEASE.md`](../RELEASE.md); who holds which files right now is in
[`AGENT_COORDINATION.md`](AGENT_COORDINATION.md).

## Read this first

**MoOS is a complete operating system, not a theme on top of one.** It is built
from Fedora Kinoite and it ships as a signed, image-based OS that installs on a
real machine, updates atomically and rolls back. The people it has to satisfy
are people who could have used Windows, macOS, Android or iOS instead — so those
four are the quality bar for how MoOS looks, how fast it feels, how little it
asks of its owner and how rarely it surprises them. They are not API targets and
MoOS never forks Plasma, KWin or Wayland: MoOS owns the identity, every surface
the owner looks at, every default and every recovery path.

**Where MoOS is today (2026-09-18).** The versions in production, on the station and in
flight are in ONE place — the "Source and release truth" block at the top of
`PROJECT_STATE.md`. Read it there; nothing here repeats a number.

Everything through **W8.5** is merged: the MoOS Bar, Search, Island, Hub, Switcher,
Arrange, App Drop, What's new, Aurora Glass, the hub's second faces, Mo AI's tool loop,
its readback, the free-brain measurement and the picker that shows it. Three things are
worth knowing before choosing work. **Five merges are newer than the image on the
station** — #134 (hub faces), #135 (recorded permissions), #132 (ARM honesty), #133
(SIGPIPE proof) and #136 (W8.5) — so none of them is on a desk yet, and
`moos-image-update` correctly says "current" because the installed digest *is* the newest
promoted one; only another cycle changes that. The ARM edition has had **one** live
review (2026-09-18, fixes merged as #130 and #132, recorded in `PROJECT_STATE.md`), but
only on the seatless Oracle A1 under `kwin --virtual` on llvmpipe — never on ARM hardware
with a real seat and a GPU. And nothing has been measured on a **second machine, a
laptop, a touchscreen or two monitors**.

**What is missing before MoOS competes.** In the order that decides it:

1. **Speed the owner can feel and the repo can prove** — now it is written down.
   `moos-measure-speed` measures boot, login, app launch and MoOS's own idle CPU against
   budgets per hardware tier (`speed-budgets.json`, keyed on `moos-visual-tier`). The
   station measures 6.03 s of MoOS-owned boot, 1.11 s to a ready desktop, 0.46 s to an
   app's window and 2.6% idle — all inside budget. What is still owed is the same four
   rows on a **balanced** and an **essential** machine, whose budgets are still derived
   rather than measured (P5.4).
2. **Applications that just work** — the one install/update/remove authority is now
   enforced by a gate, not a comment: `moai-do`'s Windows setup and `moos-setup`'s
   first-run selection both called `flatpak install` directly, putting apps in the SYSTEM
   scope that Mo Store could never remove (W9.3). What remains is truthful progress
   everywhere and the Store's own job surface (W10, P4).
3. **Mo AI as the system's hands, proven** — the brain is configured, the tool loop runs
   live, and action selection is now MEASURED: 80 fixed Arabic/English cases through the
   real gateway, 100% and 98.8% across two runs after the measurement itself found two
   ambiguous tool pairs, with no wrong tool chosen in either run (P3.3).
   What is still owed is a confirmation card walked on a desk, and the same 80 cases on a
   second model and a second machine (P3.4, P3.7).
4. **Hardware breadth** — laptop, touch, a second monitor, suspend/resume, deliberate
   rollback on real machines, and an ARM review on a physical seat with a real GPU —
   the one ARM review so far was a seatless A1 under `kwin --virtual` (P5, P0.7).
5. **The rest of the look** — the desk itself is settled: nothing is laid over the
   wallpaper, nothing on that layer moves, and its contrast is lifted on the image and
   measured (W9.8). The bridge a clarity control needs exists too (W9.6: a QML singleton
   reads `kwinrc` synchronously and the surfaces answer to it). What remains is the
   control itself from clear to solid, the MoOS mark at exactly three sizes, and the
   specular sweeping once as a surface arrives (the open half of W8).

   **The rule those two waves established, and the one to keep:** a MoOS surface earns
   its effect by measurement, not by taste. Two ideas that looked good — an ambient wash
   and an hour-placed light — were built, measured against contrast and shadow loss on
   the real screen, and deleted. Motion on a desktop has to mean something to a person or
   it is a cost; a translucent layer over artwork always spends clarity to buy it.
6. **Trust at scale** — reproducible release trust, recovery UX, and a support bundle
   an owner can send (P6).

The look itself is no longer the first gap: Aurora Glass gave the system one material
at four depths, the bar tells the truth, and every hub card answers the question that
comes after it.

**How you work here — the law of the wave.** MoOS is developed in waves, never in
small edits followed by a build. One wave is one coherent, user-visible release:
one branch, the whole wave implemented, reviewed on a live desktop (or on a real
Qt runtime when there is no desktop), gated ONCE with `just check`, one pull
request, and one release cycle for the batch. A wave that produces no visible
difference is not a wave. Fixing a defect you find on the way belongs in the same
wave. What is never traded for speed: a safety gate, a signing or rollback rule,
the identity contract, or a meaningful test.

## Product outcome

MoOS must be a coherent operating-system product rather than a collection of
packages and themes. The target is competitive quality in the areas users feel:
reliable boot and recovery, safe updates, hardware adaptation, one visual and
language system, a trustworthy application model, accessible input and output,
fast interaction, and an AI operator whose actions are explicit and bounded.

Competition with macOS, Windows and Android is a quality benchmark, not a claim
of API compatibility or feature parity. MoOS should reuse mature upstream
components and own the integration, defaults, verification and recovery paths.

## MoOS Experience Program

**The goal is a desktop computer that feels like one product called MoOS** —
fast, calm, beautiful and obviously its own — with the reliability of an
image-based system. macOS, Windows, Android and iOS are the quality bar for
feel and polish; they are not API targets, and no claim of being "better" is
made without measured evidence. Plasma, KWin and Wayland stay the engine: MoOS
owns every surface the user sees and every default, never a fork.

### One vocabulary

User-facing names are MoOS names. Technical IDs (`org.moos.nova.clock`,
`MoOSUI2*`, `org.moos.ui2.*`, KDE package and D-Bus names, licence notices) stay
stable and are never renamed for branding. Every agent uses these words in plans,
commits and UI text:

| Name | What the user experiences | Owners in the tree |
| --- | --- | --- |
| **MoOS UI** | one palette, type, icon, corner and motion system everywhere | `artwork/` generators, `org/moos/ui`, Plasma Style, Aurorae |
| **MoOS Bar** | the one floating glass bar | `moos-bar.conf`, `moos-bar-apply`, layout template, stock task manager |
| **MoOS Search** | one anchored search surface with an Ask Mo AI hand-off | `org.moos.search`, Milou/KRunner runners, `moos-open` |
| **MoOS Island** | the living context zone: Remote, media, later jobs and privacy | `org.moos.island`, MPRIS, Remote presence, job owners |
| **MoOS Hub** | time, weather and device health on the desktop, user-controlled | `org.moos.ui2.wallpaper` (desktop scene) |
| **MoOS Workspace** | windows, overview, tiling, desktops and window frames | KWin effects/config, generated Aurorae, `moos-visual-tier` |
| **MoOS Intro** | boot → login → first desktop as one continuous scene | Plymouth generator, login theme, splash, `apps/welcome` |
| **MoOS Motion** | finite spring feedback, same rhythm in shell and apps | `SpringFeedback.qml`, `Tokens.qml`, KWin durations, reduced motion |
| **MoOS Sound** | original event sounds that mark outcomes, not hovers | `usr/share/sounds/moos`, KDE notification events |
| **MoOS Shield** | identity lock, signed updates, boot fallback, rollback, privacy | identity firewalls, cosign policy, `moos-boot-assess`, Recovery |
| **MoOS Speed** | hardware-tiered visuals and measured idle/boot/launch budgets | `moos-visual-tier`, `moos-hardware-adapt`, P5.4 harness |
| **Mo Store / Mo AI / MoPlayer / Mo PC Remote** | first-party apps | their own directories and `moai-do` |

**Identity lock.** No user-visible surface may show Fedora, Red Hat or another
OS's name or logo (three build firewalls enforce it). Plasma/KDE names that users
see in MoOS-owned surfaces are replaced by MoOS names; upstream application names,
licence text and diagnostics are left intact. **Disk encryption** is a deliberate
later item (MoOS Shield, M4): offer it only when the offline installer can enrol a
TPM2 key and that key is proven to survive an image update — a passphrase prompt
without that enrolment would lock owners out of headless and docked machines.

### Waves — what "big batch" means here

A wave is one coherent, user-visible release. It is implemented on one branch,
reviewed live, gated once, merged once and proven once.

| Wave | Milestone | User-visible content | State |
| --- | --- | --- | --- |
| W1 | M1 | MoOS Search surface, settling Remote chip, clock rail, localized Hub, keyboard-safe Search/Island, in-tree MoPlayer, hardened ISO proof | **installed** on the station as `44.20260916.848` |
| W2 | M1 | MoOS Hub controls (desktop right-click show/hide and per-card toggles, wallpaper page), review-shadow retirement, unified instructions and this program | merged (`8b272b87`); **x86 production since 2026-09-17** (cycle B, `44.20260917.858`); ARM production |
| W3 | M1 | The owner controls the desk: every widget removable again (THEME_REV 60), a wallpaper chosen anywhere stays after login and drift checks, release watcher reads real run results | merged (`2e6f7686`, PR #109), reviewed live on the station; **x86 production since 2026-09-17** (cycle B, `44.20260917.858`); ARM production |
| W4 | M3 | **Mo AI as the system harness:** the cloud brain (free or paid, OpenRouter or OpenCode Zen) receives native tool schemas generated from the fixed `moai-do` and `moos-control` grammar; read-only tools run directly, every change shows a confirmation card, the fixed executor acts, and the result is read back into the conversation (P3.3, P3.4, P3.7) | merged (`009b4b58`, PR #110); **x86 production since 2026-09-17** (cycle B, `44.20260917.858`) in the form W6 repaired; ARM production; the ≥95% action-selection measurement and a station review are still owed, so P3.3/P3.4/P3.7 stay open |
| W5 | M1 | MoOS Island jobs (Store installs, updates, downloads) and privacy chips (camera, microphone, screen share); Search inline answers (calculator, units, file actions) | merged (`7f182689`, PR #111); it turned x86 `main` red and shipped without its `THEME_REV` bump — both repaired by the 2026-09-17 integration (#114, rev 61); **x86 production since 2026-09-17** (cycle B, `44.20260917.858`) in the form W6 repaired; ARM production; no station review recorded |
| W6 | M1+M3 | **What W4 and W5 promised, working, plus App Drop.** Mo AI's tool loop runs on every machine, in steps, with ten read-only inspection tools and truthful results (P3.3, P3.4, P3.7, P3.8); the Island really shows Store jobs and names the app behind a privacy chip; a downloaded AppImage or portable archive dropped into Applications becomes an app (P4.6); secondary text is readable on every scheme; MoOS-owned text no longer names another desktop | merged (`a8622f95`, PR #115); **x86 production since 2026-09-17** (cycle B, `44.20260917.858`); ARM promotion follows `main`'s own boot proof; gated and rendered from source, **not seen on a MoOS desktop** |
| W6.1 | M1+M3 | a MoOS-owned "About this device" page (P2.9); Mo AI skills — twelve repair playbooks, `list_skills`/`read_skill`, one-tap chips (P3.10); Mo AI's rail at the window's DEFAULT size; the Device panel no longer prints the raw kernel release; P0.8's cause recorded as measured | merged (`291361ad`, PR #117); **production on all four editions since 2026-09-17** (x86 `44.20260917.862`, ARM `44.20260917.441`, cycle C); **not seen on a MoOS desktop** |
| W6.2 | M1 | **What the desktop renderer saw first:** the Hub's date lines on one edge, the Island's privacy chip no longer cut in Arabic, MoOS Search's two start-up warnings (`THEME_REV` 64; W7 is 63); `scripts/review/render-desktop.sh` and `render-lockscreen.sh` | merged (`012eac13`, PR #119); **production on all four editions since 2026-09-18** (cycle D `44.20260917.865`, then cycle E `44.20260918.868`); rendered from source, **not seen on a MoOS desktop** |
| W6.3 | M1 | **What's new:** after an update MoOS says once what it brought and where to try it; Settings → System → What's new keeps the list (P2.11) | merged (`a0dd4b33`, PR #120); **production on all four editions since 2026-09-18** (cycle D `44.20260917.865`, then cycle E `44.20260918.868`); rendered from source, **not seen on a MoOS desktop** |
| W7 | M2 | MoOS Workspace: the switcher and Overview in MoOS UI, one-click tiling layouts, window durations taken from MoOS Motion, gesture and touchpad defaults | merged (`411a470c`, PR #118); **production on all four editions since 2026-09-18** (cycle D `44.20260917.865`, then cycle E `44.20260918.868`); ARM production. Landed and reviewed live on the station: **MoOS Switcher** (Alt+Tab and Alt+` are a MoOS surface, mirrored by the LOCALE, with a working close control), **`Tokens.scaled()`** (MoOS motion answers to the same AnimationDurationFactor Plasma does) and **MoOS Arrange** (halves, thirds, quarters, main-and-two and centre, from the window menu and Meta+Alt+1..4/C). `Tokens.scaled()` now reaches every surface: the motion ROLES carry the owner's animation speed, so the 288 places that read `design.motionFast` follow the one control (proven on a real Qt runtime in `tests/qml/motion-review.qml`). Open: touchpad/gesture defaults (P5.2, needs hardware this station does not have) and a live preview in the Arrange surface. Overview is **configuration only** — see "Workspace facts". **Closed on 2026-09-18** (`a2cfd72a`, PR #123): `scripts/station/pointer.py` made pointer review real (KWin confirms every position before a click), the four owed review rows passed on the station, the administrator prompt and a dismissed one became MoOS's own words, and the motion ROLES now carry the owner's animation speed so all 288 surfaces follow one control (`THEME_REV` 65). Open: touchpad and gesture defaults (P5.2, needs hardware this station does not have) and a live preview in Arrange |
| W8 | M2 | **MoOS Aurora Glass, and a bar that tells the truth.** One material with four depths (a darker rim and a specular hairline, both derived from the palette); the Island capsule fits its real height and names the app that is playing; MoOS Search is a button the size of its neighbours instead of a 196 px empty pill; the status cluster is four glyphs and an arrow instead of nine; MoOS Search shows what is playing, with its control, while nothing is typed; MoPlayer publishes its MPRIS object before its name and its metadata with one variant, so a video that starts now appears on the desk now | merged (PR #126), every visible item reviewed on the running station |
| W8.1 | M3 | **The strongest free brain is measured, not guessed, and the workshop works.** `moai-measure-free` asks every zero-price tool-capable model two fixed questions through the real gateway and writes the order that answered on THIS machine; the policy prefers it for 30 days and ranks anything unmeasured by the context window an OS agent actually needs. The release cycle reuses a signed build of the same revision instead of racing the nightly rebuild that cancels it. The three npx MCP servers run again inside the VS Code Flatpak. The RDP/VNC port MoOS's health scan finds now has an action that closes it | merged (PR #127) |
| W8.2 | M2 | **The desk answers the next question.** The clock card has two faces — the hour, and the week the owner is standing in, with today marked and the day of the year — turned from the desktop's own menu and remembered; the Hub cards wear Aurora Glass's specular hairline, so the desktop and the bar are one material | merged (PR #129), reviewed on the running station |
| W8.3 | M3 | **Mo AI reports instead of paging a log.** A tool row shows its first six lines and says how many are left; `hw_report` — which opened a panel, printed nothing and made the loop show a red "failed" row — is replaced by `device_report`, which returns the machine's state in words | merged (PR #131), reviewed live with the owner's own brain |
| W8.4 | M2 | **Every hub card answers the question that comes after it.** The weather card's second face is the next six hours (from the same forecast request); the device card's is the network and the space that is actually left, each figure gated on its own sensor | PR #134, reviewed on the station |
| W8.5 | M3 | **The owner picks a free brain by what it did here, not by what shipped.** The picker's first group is what THIS machine measured — each row carrying its own seconds, the order the run produced, and a model it caught failing saying which half it failed; the automatic row names the model it resolves to right now; one button re-measures without leaving the picker. The action ranking counts the answer the same turn gives, so a 550B model that calls a tool in 1.4 s and then takes 16.6 s to say what it did no longer outranks one that does both in 2.9 s | PR #136, measured and clicked on the running station |
| W9.1 | M3 | **Mo AI's tool choice is measured, and the measurement fixed MoOS.** Forty fixed cases in Arabic and English — 80 measurements — go through the real gateway with the whole shipped schema, `tool_choice` never forced, scored on the first call. The first run read 93.8%, and four of the five misses were two MoOS tool pairs the model could only guess between: `diagnose_services` ran exactly what `list_failed_units` runs, and `net_doctor`/`network_status` never said which one tests and which one reads. The duplicate is gone from the model-facing schema and the pair now points at itself; the same cases then read 100% and 98.8% across two runs, with no wrong tool in either | PR #138, measured three times on the running station |
| W9.2 | M1 | **MoOS has speed numbers, and a budget it can fail.** `moos-measure-speed` asks systemd for boot and session, asks KWin when an app's window really exists, and measures MoOS's OWN processes' idle CPU — not the whole machine, which on this station read 9.03% with Chrome, VS Code and Steam open while MoOS cost 2.6%. Budgets live per tier in `speed-budgets.json`, each carrying the measurement that justifies it; a probe that cannot run reports why and is excluded from the verdict instead of counting as a zero | PR #138, all four rows measured on the running station |
| W9.3 | M3 | **One authority for every app transaction, held by a gate instead of a comment.** `moai-do` has said since W6 that Mo Store's backend is the only thing that installs, removes or updates an app — because `flatpak install` lands in the SYSTEM scope while Mo Store installs per user, so Mo AI's apps could never be removed from the Store. Two callers were outside that rule, and they were the two a person meets first: the Windows-programs setup, and the first-run app selection. Both go through `moos-storectl` now, and `tests/test_one_app_transaction_authority.py` fails on any new one — with a single narrow exception for `flatpak uninstall --unused`, which collects orphaned runtimes and cannot touch an app | PR #138 |
| W9.5 | M1 | **How a security update reaches a machine, said truthfully.** `build.yml`'s nightly claimed it picked up Fedora/uBlue base security updates "promptly"; it pushes only a candidate tag, and promotion refuses any run that is not a dispatch, so it ships nothing and never could. ARM had no scheduled rebuild at all. Both corrected, and `tests/test_security_update_reachability.py` keeps the claim and the mechanism from drifting apart again | PR #139 |
| W9.6 | M2 | **Glass stops being a window where there is no blur (P2.5).** Every Aurora Glass density assumed a blur pass behind the surface; without one — the essential tier, llvmpipe, or an owner who turned blur off — 0.22 alpha over a wallpaper is a window, and the A1's review said exactly that. The surfaces now read `kwinrc/Plugins/blurEnabled`, the same key `moos-visual-tier` already writes, and paint the same colour with enough body to hold text when it is off. Proved on a real Qt engine against a real config both ways: 0.22/0.22/0.82 with blur, 0.86/0.97/0.97 without, and the depths still separate | `THEME_REV` 70, PR #139 |
| W9.8 | M2 | **The desk stops moving, and the wallpaper gets stronger — one defect.** Two full-screen washes traded emphasis every 90 s: long enough that the eye caught a drift and found nothing, and to do it they veiled every pixel of the artwork. A replacement was built (one light whose place in the sky is the hour), measured, and DELETED — every translucent layer over a dark image lifts its blacks, which is what "washed out" means, so both complaints had one answer: take things off. Nothing is over the artwork now and its own contrast is lifted instead, gated on GPU compositing via `Tokens.blurActive`. Measured on the station: **+14.2% contrast**; the strength was chosen against shadow loss (0.24 bought +4.5% more contrast for 3.5× the crushing) | `THEME_REV` 71, PR #140 |
| W9 | M2 | System surfaces on MoOS UI: Updater, Recovery, Remote centre, Settings front door (P2.1–P2.2), a MoOS-owned About page (P2.9) | planned |
| W10 | M3 | Mo Store as one job system for install/update/remove across the UI, Mo AI and URL routes, with a drop target in its own window (P1.7, P4.1–P4.2, P4.7) | planned |
| W11 | M2 | MoOS Intro: one horizon scene from Plymouth through login to the Hub; first-run tour; offline first run (P1.6) | planned |
| W12+ | M4–M5 | hardware breadth, compatibility products, MoOS Shield encryption, release trust | planned |

### W8 — MoOS Aurora Glass: what shipped, and what is left

Shipped, each one measured on the running station on 2026-09-18 (frames in
`~/.cache/moos-w8/`):

1. **One glass, four depths.** `Tokens.glassDensityAt/glassEdge/glassSpecular` derive
   body, rim and highlight from the palette and from how far forward a surface sits
   (scene, panel, popover, dialog). The Island capsule, the Search button and every
   `MoUI.GlassSurface` (Settings sheets, the clock popup, the widget explorer, the lock
   screen) wear it. A surface keeps an edge over a bright wallpaper instead of
   dissolving into it.
2. **The capsule fits.** The two pinned text lines assumed `panelHeight` (54); the bar
   gives its applets 40, so the source line was drawn through the pill's bottom curve
   and sat outside the capsule — the owner reported it and a frame proved it. The block
   now measures the real height and drops to one line when two do not fit.
3. **The capsule names the app.** A player publishes a desktop-entry NAME, which is not
   an icon name: MoPlayer's entry is `org.moos.moplayer` and its icon is
   `moos-moplayer`, so the bar showed the theme's "unknown file" sheet next to a working
   player. MoOS entries map to MoOS icons and any unknown name falls back to a media
   glyph.
4. **Search is a button.** The 140–196 px pill carried the words "ابحث في MoOS" and a
   field that can never be typed into (a panel cannot take keyboard focus), and it made
   the bar as much wider as four application icons. It is one icon now; the hint lives
   in the popup, where the caret is.
5. **The status cluster is four glyphs and an arrow.** Nine icons reported themselves
   active on a desktop that has a screen, a radio and a USB port. Bluetooth, brightness,
   removable devices, the camera indicator, printers, KDE Connect, vaults and Caps Lock
   moved behind the arrow; network, sound, notifications and keyboard language stayed.
6. **Search and the Island are one answer.** Opening Search while something plays used
   to hide the Island behind the popup. Search now shows that same player at the top —
   title, source and one control — and only while nothing is typed.
7. **MoPlayer is visible to the desktop.** Two defects, both root-caused on the bus:
   it took its MPRIS bus name before exporting the object (a desktop asks the new owner
   for its properties 2 ms later and drops a player that answers `UnknownObject`), and
   it wrapped every metadata value in a second variant, so no reader could read the
   title. Starting a video now changes the desk.

Still open in W8, for whoever picks it up next:

- **One clarity control.** «وضوح الزجاج | Glass clarity» from clear to solid, one value
  driving both MoOS token density and KWin's blur strength, pinned to solid by the
  reduced-transparency setting. It needs a config bridge a QML singleton can read (the
  design core deliberately imports nothing), so it is a piece of plumbing, not a slider.
- **The MoOS mark at exactly three sizes** (boot, login, bar) with a glyph everywhere
  else.
- **Glass that settles**: the specular sweeping once as a surface springs in.

### Ideas worth building (each needs its owner and a proof before it ships)

- **Living Island:** one foreground state with a deterministic priority
  (Remote > call/screen share > recording > install/update job > media), a
  spring expansion that settles, and a history popover of finished work.
- **Hub stacks:** each Hub card becomes a small stack (time → calendar → world
  clock; weather → hourly; device → network/battery) that the user scrolls
  through with the wheel, never auto-rotating.
- **Search that answers:** inline calculator/unit/currency rows, file rows with
  open-folder/copy-path actions, and a Mo AI row that streams a short answer
  before the user commits to the chat.
- **Arrange in one click:** a Bar or overview popover with KWin tiling presets
  (halves, thirds, 2+1) and a live preview of the user's own windows.
- **Motion with meaning:** window open/close/minimise and popup durations derive
  from the same MoOS Motion tokens as QML springs; one "calm / lively" switch
  drives both, and Reduced Motion stops both at once.
- **Quiet privacy:** camera, microphone and screen-share indicators appear in the
  Island with the owning app's name and a one-tap stop.

Anything that would replace KWin, fork Plasma, add an always-running animation
or weaken a gate is out of scope, however attractive it looks.

### How an agent executes a wave

```bash
# 0. Orient: never start a duplicate release; never touch another agent's worktree.
git fetch --prune origin && git worktree list
systemctl --user list-units 'moos-release-*' ; gh run list --limit 10
# 1. One branch for the wave, from the newest main (or from an unmerged wave it builds on).
git worktree add -b feat/<wave> ~/.cache/<wave> origin/main
# 2. Implement the whole wave. Review it on the live desktop with TEMPORARY package
#    shadows (copy the package to ~/.local/share/plasma/{plasmoids,wallpapers}/,
#    `systemctl --user restart plasma-plasmashell.service`, capture with
#    `spectacle -b -n -f -o …`), driving it with a temporary applet shortcut and
#    `YDOTOOL_SOCKET=$XDG_RUNTIME_DIR/.ydotool_socket ydotool`. Restore layouts,
#    shortcuts and config you changed. THEME_REV sweeps first-party shadows on update.
# 3. Fast gates once, not per edit.
python3 tests/<affected>.py ; flatpak-spawn --host just check
just build-nvidia            # only when a Tier 1 file changed
# 4. One PR, merge after Repo gates (never while a release runner freezes main).
gh pr create … ; gh pr merge <n> --merge
# 5. One release for the wave, supervised outside the chat session.
systemd-run --user --unit=moos-release-<wave> --collect \
  --property=StandardOutput=file:$HOME/.cache/moos-release-<wave>.log \
  bash scripts/release-candidate.sh --promote
# 6. A red proof: read the failed step AND its proof artifact, fix on a new branch,
#    dispatch fresh (never "Re-run jobs"). Green: the owner stages the update
#    (Updater or `moai-do update`) and reboots; the agent reads the result back
#    from /usr and records it in PROJECT_STATE.md.
```

### Working off the station (Windows, macOS, a cloud VM)

An agent that is not on the MoOS workstation cannot restart plasmashell, but it is not blind.
Use a disposable Fedora development distro (WSL2, Toolbx, a container) — never a MoOS host:

```bash
sudo scripts/review/setup-review-distro.sh            # once: Qt 6 / KF6 QML stack, fonts, MoOS assets
scripts/review/mirror-gates.sh                        # all repo gates, on a native-filesystem mirror
scripts/review/mirror-gates.sh tests/test_app_drop.py # or just the ones a change touches
scripts/review/render-app.sh moai /tmp/moai-ar.png --lang=ar
scripts/review/render-app.sh store /tmp/store.png --scheme=MoOSUI2AuroraLight
```

`mirror-gates.sh` exists because a Windows drive seen from WSL reports every file as executable;
it mirrors the working tree and applies the modes git records. `render-app.sh` draws a first-party
app FROM SOURCE with a real MoOS colour scheme and prints the QML runtime's binding errors — it
is how an undefined colour in Mo AI's privileged-action card, a dead file read in the Island and
1.6:1 secondary text were found while every gate was green. It is source-harness evidence: it
cannot show plasmoids, KWin, the greeter or an installed image, and a frame from it is never a
desktop review. Say which evidence you have.

`render-desktop.sh` goes one layer further (2026-09-17): the REAL `plasmashell` with MoOS's shipped
layout, `/etc/xdg` configuration, scene wallpaper (Hub) and plasmoids, with `kwin_x11` under Xvfb,
captured at the station's logical size (1536×864) in Arabic or English. It needs the stock shell
package COPIED and MoOS's partial overrides laid over it (in the image they share one directory;
from a checkout KPackage otherwise finds a package with no metadata and draws nothing), the
activity manager started by its real path, and Qt/Frameworks/Plasma on one version. What it
cannot show is everything KWin's compositor adds — blur, translucency, the bar's rounded corners,
window animations — and it is X11 where MoOS is Wayland. Its first run printed two binding
warnings in `org.moos.search` that every desktop start had been logging.

Two traps cost an hour each on 2026-09-17. A here-document passed through some agent shells has
its backslashes halved, so `\\n` written into a patch becomes a real newline inside a QML or
Python string: write patch scripts to a file, or edit directly. And `qmlformat` rejects Mo AI's
8000-line `main.qml` on `main` too — it is not a syntax check for this file; the QML engine is.

## Current engineering brief

The owner's requests converge on one product, not a new desktop rewrite:
keep the working offline-installed MoOS workstation, improve its existing
Horizon dock/UI, complete native sound and physical feedback, integrate stable
KDE/Wayland, make cloud AI truthful, and deliver the same result in signed ISOs.
Repository cleanup and engineering instructions support that work; screenshots,
old plans and extra packages are not product progress.

**Active milestone: M1, the daily MoOS desktop journey.** Which image is in production, and
which revision built it, is stated in exactly ONE place: the "Source and release truth" block
at the top of `PROJECT_STATE.md`. This file does not repeat it. Four documents each carrying
their own copy of "production is X" is how three of them came to be a release behind at once,
while the fourth said something different two hundred lines away — and an agent picking work
could not tell which was live.

W6.1–W6.3 HAVE now been seen on a MoOS desktop: the station review that closed them is
recorded in `PROJECT_STATE.md`, and W8, W8.1, W8.2 and W8.3 were reviewed there too.

How that release happened is the procedure to repeat. Cycle A (candidate
`51cc2ac3`) passed the signed build and all three QCOW2 boots and lost its ISO
proof to row P0.8. The fix changed a proof script and an image fixture, so it was
a new revision and every proof ran again: cycle B carried the integration, the
fix and W6 as ONE candidate (`scripts/release-candidate.sh --ref <branch>`; build
`35261411076`, disks `35265314956`/`35265319663`/`35265323922`, ISO
`35265328509`), the pull request was merged with a merge commit so `main`'s tree
equalled the candidate's, and `promote-x86.yml` was dispatched with those run
ids. Never "Re-run jobs": promotion accepts attempt 1 only. Pull requests that
touch the image now build it first (`pr-image-gates.yml`, row P0.9), so a red
`main` like W5's should not recur.

| Requested outcome | Work stream | What must actually be proven |
| --- | --- | --- |
| One clean project any agent can continue | Documentation policy + workstation profile | One state/plan; fresh branch ancestry; reproducible component checks |
| Reliable offline install/update/recovery | P0–P1 | Exact signed artifact boots twice; target-only disk writes; rollback works |
| Distinctive existing MoOS UI/dock/sounds | P2, active P2.7 | Real input/render/audio, Arabic/English, reduced motion and mute |
| Kernel/CPU/GPU/RAM work together | P5 | Actual policy/driver readback, pressure/frame/audio and thermal measurements |
| Unified core and APIs | P1.7 + P3/P4 | Schema, lifecycle, authorization and UI/backend agreement under failure |
| Free cloud intelligence actually replies | P0.5 + P3 | Approved key, free-policy reply, error recovery, no invented task completion |
| Same product on physical, cloud and ARM | P0 + P6 | Separate exact-edition/architecture proofs; no extrapolation from this PC |

### Station review owed for W4–W6.1

Everything below shipped after being gated, rendered from source and boot-proven in CI. Rows
with a verdict were walked on the station; the rest are still owed. Pointer-driven rows need
`scripts/station/pointer.py` (it verifies each position with KWin before clicking) — a blind
`ydotool` click does not land on a 4K screen at 265% and is not evidence. After the station (and the A1) take the update
with the MoOS Updater and restart, walk this list ONCE, in order, and record PASS/FAIL with
what was seen in `PROJECT_STATE.md`. A FAIL is a finding for a fix branch, not a reason to
roll back unless the desktop itself is unusable (Settings → Recovery keeps the old version).

| # | Do this | Expect | Wave |
| --- | --- | --- | --- |
| 1 | `bootc status`; Settings → System → About this device | booted version ≥ `44.20260917.858`; the page is MoOS's own (edition in words, kernel as `Linux x.y.z`), not the desktop's module | W6, W6.1 |
| 2 | First login after the update: `ls ~/.local/share/plasma/plasmoids/` | the four review shadows (`org.moos.search`, `island`, `nova.clock`, `ui2.wallpaper`) are gone (`THEME_REV` 62) | W2–W6 |
| 3 | Right-click the desktop → MoOS Hub controls; turn one card off and on | the Hub redraws without that card; the choice survives a re-login | W2  — **PASS** 2026-09-18 (pointer) |
| 4 | Edit mode → remove a desktop widget; choose a wallpaper in the desktop's own dialog; log out and in | the widget is removable; the wallpaper stays | W3  — **PASS** for the widget 2026-09-18 (pointer); the wallpaper half was proven in W3 |
| 5 | MoOS Search: type `12*7`, `5 km in miles`, a file name | inline answer / conversion / file actions | W5 |
| 6 | Start a Mo Store install, then look at the Island; join a call or open the camera | the Island shows the Store job with progress; a privacy chip NAMES the app, one tap stops it | W5 as repaired by W6  — privacy chip **PASS** 2026-09-18; the Store-job half still owed (the Remote chip outranks it) |
| 7 | Open Mo AI at its default size | the compact rail has each label centred under its icon; eight chips under the four cards | W6.1 |
| 8 | Mo AI, cloud brain configured: "الصوت لا يعمل، افحص وأصلح" | it reads a skill or inspects first (tool rows with no card), THEN shows ONE card for the repair; "Don't run" really runs nothing; the final answer matches the tool's real result | W4 as repaired by W6, W6.1 |
| 9 | In that same chat, ask it to turn Wi-Fi off | a card appears (the executor asks for that value); turning it ON needs none | W6 |
| 10 | Download a real AppImage from its maker; double-click it; then drop another into `~/Applications`; then right-click a portable `.tar.gz` → Install in MoOS | a default-No dialog each time; after Yes the app is in the launcher with an icon and starts; no administrator password; `moos-app-drop --list` shows them; Remove works | W6  — **PASS** 2026-09-18 with a real 8.4 MB AppImage, install and remove |
| 11 | Dismiss the administrator prompt during Mo AI's "Update firmware" or "Install RPM" | the result says it was NOT done (it used to print success) | W6  — **PASS** 2026-09-18: nothing was staged and MoOS said so; the prompt's own English wording was the finding, fixed in the same wave |
| 12 | Light theme: read the secondary text in Mo Store's hero, Welcome and Mo AI's rail | clearly readable (was 1.6:1) | W6 |
| 13 | Ask Mo AI "what system is this?" and "which desktop do I use?" | it answers MoOS / the MoOS desktop and names no other system | W6 |

## Non-negotiable architecture

1. One source tree produces four editions: general x86, NVIDIA x86, cloud x86
   and ARM. The three x86 editions share one base and one kernel.
2. The immutable image owns `/usr`; persistent system and user state lives in
   `/etc` and `/var`. Updates preserve a previous bootable deployment.
3. Every published digest is signed. Installation and later updates enforce the
   signature policy.
4. KDE Plasma and KWin remain the desktop engine. MoOS owns identity, defaults,
   first-party surfaces and integration; it does not fork the desktop without a
   measured upstream limitation and a maintenance budget.
5. `moai-do` is the only privileged product executor. Models and web content can
   select fixed actions but can never execute generated commands.
6. Mo Store is the target application-lifecycle authority; convergence is not
   complete (`moai-do setup-windows` still installs Bottles directly). Desktop applications
   use sandboxing and portals by default; system drivers and services stay in
   the signed OS image.
7. Mo AI is cloud-only. Free service is the default, paid providers require an
   explicit choice, and credentials remain private user state.
8. A build, a local image, a published candidate, a booted artifact and a
   promoted release are different states and must never be conflated.
9. MoPlayer is a first-party in-tree application. `moplayer/` is its only source;
   x86 and ARM build and test it directly and install only the resulting bundle.
   No external MoPlayer branch, release archive or nested workflow participates.

## Baseline on 2026-09-13

The physical development machine runs Plasma/KWin 6.7.5, kernel 7.2.4,
systemd 259.8, bootc 1.16.10 and NVIDIA 615.71.09. Plasma 6.7.5 is the current
stable bug-fix release. Plasma 6.8 is in beta and its public release is scheduled
for 2026-10-14; MoOS must not replace a proven stable desktop with the beta.
Upgrade when the stable stack reaches the shared image base and passes the full
visual, QML, boot and hardware matrix.^1 ^2

The first physical offline installation and NVIDIA boot succeeded. The current
branch's complete NVIDIA image build also passed. The unresolved product gaps
are cloud-AI setup, hardware qualification breadth, deliberate rollback,
cross-edition exact-commit proofs, remaining older first-party UI surfaces,
language coherence and compatibility-product acceptance.

## Release scorecard

Every release records these values for the exact promoted digest:

| Dimension | Required evidence | Release target |
| --- | --- | --- |
| Boot | firmware-to-login and login-to-desktop timings | no regression >10%; no failed unit |
| Update | check, stage, reboot, readback | signed digest booted; previous deployment retained |
| Recovery | deliberate bad candidate and rollback | user data intact; old deployment boots |
| NVIDIA | kernel/kmod match, initramfs, journal, Wayland | no fallback driver or fatal NVRM event |
| Desktop | 1080p/1440p/4K, 100–250%, RTL/LTR | no clipping, dead action or foreign identity |
| Accessibility | keyboard traversal, screen reader, contrast, reduced motion | every primary flow usable without pointer |
| Applications | install, launch, reopen, update, remove | one authority and truthful progress/readback |
| Mo AI | setup, latency, tool accuracy, provider failure | ≥95% action selection; p50 first token ≤2 s |
| Idle | CPU, PSS, wakeups, disk/network | measured budget per hardware tier |
| Suspend | two cycles plus audio/network/display recovery | zero failed unit or lost device |
| Offline install | blank disk through second installed boot | no network dependency; only target disk changed |

Targets are gates only after the measurement harness is committed. A missing
measurement is `not proven`, never a pass.

## Task protocol

Work in release batches. Related slices may use reviewable commits, but integrate
the coherent batch in one pull request after its fast gates pass: targeted tests,
`just check`, PR CI, and a local image build when a Tier 1 boot/image file changed
(see `docs/AGENT_GUIDE.md`). A push to `main` starts candidate work, so do not
spend one image build on every small file. Merging does not deploy:
`build.yml` pushes only `candidate-*` tags, and production tags move only
through `promote-x86.yml` after exact-revision proofs. Do not stop and wait for
a release cycle between slices; keep implementing while CI runs.

A batch ends with one release cycle, started by `scripts/release-candidate.sh`.
Before dispatch, inspect active workflow SHA/run IDs and reuse them; never start
a duplicate build merely to learn status. At dispatch, merges freeze, the signed
candidate is built from `main`, the three QCOW2
proofs, the offline ISO proof and the ARM proof run in parallel on the exact
digests, and promotion happens only when every x86 proof passes. Merges reopen
after promotion, or after the failure is fixed and a new cycle starts. The
candidate SHA stays fixed for its cycle; neither a second branch nor a running
build is a second release authority. Independent implementation may run in
parallel with explicit non-overlapping file ownership.

For every task:

1. Read this plan, `PROJECT_STATE.md`, the engineering skill and the affected
   component documentation.
2. Record the current runtime or artifact behavior before editing.
3. For runtime defects, add a regression that fails for the reproduced defect;
   for new behavior, define measurable acceptance. Documentation/editor-only
   changes need direct validation, not tests that merely mirror their wording.
4. Implement the largest safe, coherent batch of related tasks, each as a
   complete vertical slice. Do not leave a second owner, compatibility alias or
   dead service unless an upgrade path requires it, and do not split one
   coherent change into several release cycles.
5. Run targeted tests, `just check` and, for Tier 1 boot/image changes, a local
   image build. VM, ISO and hardware proofs run once per release batch unless
   the slice is itself a boot fix that must be proven before anything else.
6. Update `PROJECT_STATE.md` with current evidence and update the task status
   here. Remove superseded prose instead of appending a diary.
7. Commit reviewable results and integrate the coherent batch once. Report
   changed behavior, evidence and open exclusions.
8. **Move straight to the next task in the batch.** Do not announce readiness and
   wait: a finished task is recorded, not celebrated. Stop only for a real
   blocker — something that needs the owner (hardware, a credential, a reboot),
   a failing safety gate, or a decision that changes the plan — and then state
   the exact blocker and carry on with the next unblocked task. Source
   completion and release evidence are separate: a merged slice is complete in
   source, and its row closes when the batch promotion proves it. Report the
   whole cycle at the end: what landed, what each proof showed, what is open.

## Ordered execution

### Milestone map

| Milestone | Coherent outcome | Work-stream rows | Boundary proof |
| --- | --- | --- | --- |
| M0 | One honest source/release/workstation state | P0.1–P0.2, P0.6, release harness defects | signed build + 3×QCOW2 + ISO + ARM; exact installed readback |
| **M1 active** | Daily shell feels like one MoOS product: Bar, Search, Island, clock, sound, keyboard and desktop hub | P2.3–P2.5, P2.7–P2.8, P5.4 baseline | native keyboard/render review, matrix samples, then the M0 artifact set |
| M2 | Workspace, Intro, login/lock/boot and first-run form one journey | P1.6, P2.1–P2.2, P2.5, P5.8 | clean and upgraded profiles; offline/online; Wayland restart and scale/hotplug |
| M3 | Settings, Store and Mo AI complete real jobs with one authority | P1.7, P3.1–P3.7, P4.1–P4.2 | schema/failure fixtures plus install/update/remove and confirmed AI-action readback |
| M4 | Hardware and compatibility breadth | P0.3–P0.5, P4.3–P4.5, P5.1–P5.8 | device records, suspend/rollback and published compatibility evidence |
| M5 | Sustainable releases and support | P6.1–P6.6 | reproducible inputs, attestations, staged rollout and support policy |

Rows can contribute to more than one milestone. A row closes only when its own
exit evidence exists; the map controls batching, not truth.

### P0 — Establish one proven release

P0 is complete only when the cleaned source is published as one exact signed
revision and all required editions/artifacts prove that revision.

| ID | Status | Task | Exit evidence |
| --- | --- | --- | --- |
| P0.1 | Complete | Integrate the reviewed first-install repairs and create one candidate revision | PR #92 merged as `b6a72ad2`; signed candidate revision `1d92082f`, build run 34785063649 |
| P0.2 | Complete | Run generic, NVIDIA and cloud QCOW2 proofs plus offline ISO install/second boot | QCOW2 runs 34786215189/34786216334/34786218085 and offline ISO run 34786220039 succeeded on the exact candidate |
| P0.3 | Open | Finish physical NVIDIA qualification | Plymouth/login photos; two suspend cycles; audio/network recovery; second monitor; clean journal |
| P0.4 | Open | Prove failed-update recovery | disposable VM bad-candidate rollback, then hardware rollback/roll-forward with user data intact |
| P0.5 | Open | Configure and accept free Mo AI on a clean account | valid OpenRouter key entered through Settings; Arabic/English reply; reboot persistence; provider failure UI |
| P0.6 | **In progress** | Promote only the proven digests and update the physical PC | Eight cycles have promoted only proven digests, and the owner has updated and rebooted the station each time (the current pair is in `PROJECT_STATE.md`). The ARM half was the reason this stayed open — `build-arm.yml`'s promote job required a `push` event while a release cycle dispatches it, so no cycle had ever promoted `moos-arm`. **Fixed in W9.4** and gated by `tests/test_release_candidate_script.py`. What is left is to SEE it happen: cycle H reached one revision on both architectures, but ARM got there by its own push, so the dispatched path has still never been observed promoting. The next cycle whose ARM run finishes is the proof |
| P0.7 | Open — **x86 too since 2026-09-18** | Remove the intermittent `plymouthd` crash (ARM second boot; x86 first boot) | SEGV in `on_new_frame` failed ARM runs on 2026-09-15 and `35150466421`; on 2026-09-18 it core-dumped `plymouth-start.service` on the FIRST boot of cycle D's generic x86 QCOW2 (`35289168012`) while the same candidate's NVIDIA, cloud and ISO boots were clean — one x86 proof in about twelve so far. A lone proof lost to it is dispatched again (`RELEASE.md`), which costs a release cycle an hour each time. The theme is a Plymouth SCRIPT theme kept on screen through the KWin hand-off (`plymouth-quit.service.d/10-moos-retain-splash.conf`); the next step that costs nothing is diagnostics: the boot proofs' failed-unit report must include `coredumpctl info` for the crashed process, so the next failure yields a stack and not a service name; reproduce with ARM-only branch dispatches, fix without weakening the zero-failed-unit gate, then two consecutive green ARM proofs **after a fix** (the W3 and W5 runs were green with none, which proves intermittency only) |
| P0.8 | **Closed 2026-09-18:** cause measured; three green in a row (`35265328509`, `35276847573`, `35289177072`) | Make the ISO installed-reboot proof deterministic | lost THREE candidates out of four (`57874d6c`, `8b272b87`, `51cc2ac3`): after the installed reboot SSH timed out "during banner exchange" for 1000 s while QGA reported the second boot. **Cause, measured in run `35265328509` (2026-09-17, the first green ISO proof since):** the image's proof-channel helper read the IPv4 default route ONCE, and MoOS disables NetworkManager-wait-online, so nothing orders that read after DHCP. The helper now waits and speaks on the console, and the serial log shows it: first boot, route 16 ms after the daemons were active; SECOND boot, 1.02 s — the first read was empty and one retry found it. The old helper died on that read, so its SSH rule was never added. `systemctl --failed` had looked empty in the failed runs only because SELinux confines the harness's QGA context. The harness change written on the other theory (one slirp forward per boot) was measured by the same run as irrelevant (`reboot-channel.txt`: `first-boot-forward=alive`); it stays because it is free. `tests/test_ci_proof_channel.py` runs the shipped helper end to end under bubblewrap. Cycle D's proof made three; closed |
| P0.9 | Done 2026-09-17 (PR #116) | Run image-only gates before the merge | `build.yml` did not run on pull requests and `build-arm.sh` does not call `verify_image_experience.py`, so W5 was green on every check and red on `main`. `.github/workflows/pr-image-gates.yml` now builds the generic x86 edition on every pull request that touches `Containerfile`, `build_files/` or `system_files/` — same Containerfile, same build arguments as `build.yml`'s generic row, every in-image gate — and pushes, signs and tags nothing (`contents: read` only; `tests/test_pr_image_gates_workflow.py` keeps both halves true). It does NOT build the NVIDIA or cloud editions: those still first build on `main` or through `scripts/release-candidate.sh --ref`. Individual image gates can still be pulled forward into the repo gates the way `tests/test_image_gate_source_parser.py` and the lifted check in `tests/test_moai_skills.py` do. **First run (2026-09-17, PR #116):** green in 16 minutes end to end, 12 min 20 s of it the image build; the log shows `MoOS image-experience gate passed`, the motion gate on the real Qt runtime and the image-state gate, then the local commit — and no push. That is shorter than a release build because nothing is pushed or signed |

Repository cleanup is complete: retired plans/evidence/assets were removed,
and all 14 historical remote branches were proven ancestors of `main` before
deleting their refs. PR #92 is merged. Its earlier green Claude job did not
complete review; never count that job as review evidence.

The engineering-instructions slice now distinguishes source, live workstation,
container and signed-artifact evidence; it includes a host/Flatpak preflight and
a live-review reference. Realistic independent skill scenarios exposed and
removed an unsigned-local deployment recipe and false-success shell checks.
The Settings visual harness also rejects stale normal-state status, after a
real English review exposed disabled actions hidden by passing keyboard tests.

bootc stages updates without changing the running deployment and exposes an
explicit rollback verb.^3 MoOS already builds on this behavior; P0.4 tests it
instead of inventing another updater. The current update lock and edition-switch
preservation must be exercised during P0.2.

### P1 — Reliability and first-run platform

| ID | Task | Exit evidence |
| --- | --- | --- |
| P1.1 | **Complete:** Make every first-boot migration versioned, idempotent and transaction-safe | every migration records id/revision/outcome in one append-only ledger; the two-key wallet write is staged and renamed so an interruption leaves the original file; interrupted, repeated and clean-vs-upgraded fixtures in `tests/test_migration_ledger.py` |
| P1.2 | **Complete:** Add boot-success health and automatic fallback design compatible with the actual boot loader | `moos-boot-assess` counts unblessed boots in `/var/lib/moos` because `/boot` is read-only and greenboot is absent; three unblessed boots return to the previous deployment through `bootc rollback`, and it refuses when a rollback is already queued, when there is no previous deployment, or when it already rolled away from this one; enabled on x86 and ARM; `tests/test_boot_assessment.py` |
| P1.3 | **Complete:** Make offline installer storage policy hardware-safe | `moos-list-disks` now reads TRAN, so soldered eMMC is no longer called removable (which could make a tablet only disk refusable) and eMMC boot/RPMB areas are not offered; `tests/test_installer_storage_policy.py` drives SATA/NVMe/USB/eMMC/SD fixtures, target-only mutation and the live-medium rules; the installer pins LC_ALL=C so the actionable low-space and disk-io messages survive a non-English session; no-encryption is recorded as a deliberate decision with the condition for revisiting |
| P1.4 | **Complete:** Build a redacted support bundle | `/usr/libexec/moos-support-bundle` with per-section and whole-bundle caps; redaction proven in `tests/test_support_bundle_redaction.py` and on this machine (51.6 KB, 13 sections, no live address, MAC, home path or credential shape); PR #102 |
| P1.5 | **Complete:** Establish update observability | `moos-image-update` publishes one atomic record that the Updater window and the journal both read; `tests/test_update_state_machine.py`; PR #102 |
| P1.6 | Qualify first-run without internet | Store metadata, dictionaries, locale, drivers and Help remain useful; cloud-only features explain connectivity clearly |
| P1.7 | Version and qualify core/API boundaries | gateway, control, agent API, Settings snapshot and Store job schemas; stale/dead/partial response, timeout, restart and same-host cross-user negative tests |

Core ownership is not one monolithic daemon. `moai-gateway` owns provider
requests; `moai-control` owns hardware/service control status; `moai-agent-api`
owns developer tasks; `moos-settings-status` owns the read-only Settings
snapshot; Store owns transaction jobs. Preserve those boundaries while giving
the UI typed/versioned contracts. A localhost bind and custom header alone do
not authenticate another local user. Check each service's actual identity and
permission boundary before adding a new caller.

Automatic boot assessment is a useful reference: a boot is marked good only
after explicit health units succeed, and repeated failures can select the prior
entry.^4 The implementation must fit MoOS's real GRUB/bootc layout; do not copy a
systemd-boot recipe without proving compatibility.

### P2 — One desktop experience

Implement through the existing owners below. KDE provides documented theme,
widget and window-decoration extension points; MoOS should use those supported
boundaries.^8 The actual display-manager unit takes precedence over generic
upstream examples that still describe SDDM.

| Surface | Existing owner | Integration rule |
| --- | --- | --- |
| Session, windows, display, input | Plasma/KWin Wayland, KScreen, input-method services | Read actual session capabilities; verify scale, screen capture and input through their real services |
| Palette, controls, app material | UI2 palette generators + `org/moos/ui` QML module | One geometry/type/icon system; dark/light and device tiers are tokens |
| Dock, launcher, desktop scene | `moos-bar.conf`, `moos-bar-apply`, MoOS plasmoids | One panel writer; existing and clean profiles converge after migration |
| Login, lock, splash | resolved display manager, MoOS shell theme, Plymouth | Same identity; exercise the real greeter and boot frames |
| Settings and service pages | MoOS Settings + owning backend | Read back actual state; existing standalone surfaces become tested links |
| Privileged operations and apps | `moai-do`, Mo Store transaction backend | Fixed action/confirmation; truthful progress and errors |

Within wave W9, the Updater leads P2.1: baseline its light/dark Arabic/English
frames and routes, move its controls onto shared UI2 and prove check/stage/error/
reboot-needed states. Recovery and Remote follow in the same wave once the
Updater passes its review, so no surface is left half-migrated and the wave still
ships as one release.

Observed polish gaps to include in P2.3/P2.5: the shared hardware summary still
renders the technical `nvidia (discrete)` label in Arabic; narrower English
trust text can elide. Translate presentation separately from hardware
classification, and retain the full accessible/error meaning at small widths.

**P2.5, measured 2026-09-17 on the Oracle A1 — Liquid Glass has no blur-less
fallback, and the material contract already requires one.** `MOOS_UI2_DESIGN.md`
says a Liquid Glass surface has "a palette-tinted fallback fill that works
without blur" and that "software rendering uses opaque or near-opaque
fallbacks ... through capability detection".
`org/moos/ui/GlassSurface.qml` implements no fallback: it sets `fillOpacity`
from a fixed token (`floatingGlassOpacity` 0.82, `glassRestingOpacity` 0.22)
whatever the machine can do. Those values are tuned for a machine whose
compositor smears what shows through.

This host is `llvmpipe` with no accelerated render node, so `moos-visual-tier`
correctly resolves the essential tier and writes `Plugins/blurEnabled=false` —
blur there would be paid on the CPU every frame. `qdbus6 …Effects.isEffectLoaded
blur` and `contrast` both answer `false`. The remaining ~18% is then not a
blurred wash but sharp content: in a capture of MoOS Search over a maximised
editor, the window's own body text reads straight through the results surface.
Every Liquid Glass surface inherits this, so it is one shared defect, not a
Search defect.

Not fixed here, deliberately. The installed QML stack exposes no blur-availability
API (`org/kde/kwindowsystem` and `plasma/core` qmltypes carry no `blurBehind` or
`isEffectAvailable`), so capability detection needs a mechanism MoOS does not yet
have; `moos-visual-tier` is the authority that should publish it, the way it
already publishes `file_indexing` to `moos-index-policy`. And this machine has no
GPU, so the blur-present path cannot be reviewed from it — changing the shared
glass material for every surface on evidence from one tier is exactly the
unverified change the engineering skill forbids. Implement it against both tiers,
with the flagship frames captured on the station.

| ID | Task | Exit evidence |
| --- | --- | --- |
| P2.1 | Move Updater, Recovery and Remote control center onto the shared UI2 component/token layer | live dark/light 4K captures; no private palette implementation |
| P2.2 | Make Settings the front door for themes, updates, recovery, devices, Remote and AI providers | standalone launchers become tested deep links; no duplicate authority |
| P2.3 | Create one locale authority for Arabic, English and German | every first-party app, date/number format and keyboard follows one selection after login/reboot |
| P2.4 | Complete keyboard and screen-reader operation | primary flows traversed with real keys; Orca reads Arabic and English; focus never disappears |
| P2.5 | Run the visual matrix | 1080p–4K, 100–250%, RTL/LTR, light/dark, reduced motion; measured contrast and no clipping |
| P2.6 | Remove remaining retired UI names/assets and enforce reachability | generated asset manifest; every shipped asset has a runtime/generator/test consumer |
| P2.7 | **Active:** complete existing Horizon feedback, clock input and original system sound | Shared finite spring with stable hit targets; reversal/hidden/reduced-motion tests; real clock keys; KDE event playback and mute/custom overrides; image and upgraded-session proof |
| P2.9 | Finish the identity lock on text MoOS displays | **In source (W6):** Mo AI's Apps panel, its system prompt, Mo Store's Sources page, a Settings error dialog, MoPlayer's store page and two unit descriptions no longer name another desktop; `tests/test_user_visible_identity.py` reads QML prose, bilingual messages, dialogs, unit descriptions, AppStream and desktop entries. **In source (after W6, `feat/about-this-device-20260917`):** Settings → About this device is MoOS's own page inside MoOS Settings — edition in words, version, build date, signed image, rollback, the kernel as its number (the release string carries the packager's build tag), processor, graphics, memory, storage, architecture, Copy details; `moos://settings/about` lands on it in a running window; every row says Unknown in words without the feed (`tests/test_settings_about_page.py`). Rendered from source in Arabic and English, light and dark, 1180–1400 px; **not seen on a MoOS desktop**. **Open:** the cloud edition's firewalld `DefaultZone` is still the base's server zone name (`build.sh`, Tier 1): ship `moos-server.xml` beside `moos-desktop.xml` |
| P2.10 | Readable text on every scheme | **In source (W6):** secondary text was the DISABLED role — 1.6:1 on light schemes; all five apps now use text at 72% (≥4.66:1 on all 16 schemes), held by `tests/test_secondary_text_contrast.py`. **Open:** the same arithmetic for plasmoids, the launcher and the greeter, and for state colours on tinted fills |
| P2.11 | **In source (W6.3):** tell a person what an update brought | The owner updated across six waves and "felt no change". `/usr/share/moos/whats-new.json` lists what a person can see or do, newest first; MoOS Settings → System → What's new shows it with "Try it" routes and marks what this machine did not have before its last update (`fresh` = merged after the rollback deployment's build); `moos-whats-new-notify` says it ONCE at the first login on a new version (never to a brand-new user, never for an update with nothing visible, retried when the message did not go out). One reader (`usr/lib/moos/moos_whats_new.py`) for both; `tests/test_whats_new.py` runs the notifier end to end under bubblewrap and refuses an entry the reader would drop, a glyph the catalogue lacks or a route Settings may not open. **Rule:** a user-visible change ships with its entry. **Open:** a station review of the notification on a real update |
| P2.8 | **In progress:** compose MoOS Bar, Search and Island (experience goals 1–2 in `artwork/MOOS_UI2_DESIGN.md`) | one anchored Milou surface with recent apps/destinations/Mo AI, stale-result protection and complete keyboard escape/traversal; Remote keeps privacy priority while its popup can switch to media; native ≥40 px controls; localized clock/hub; typed queries reviewed live on the station (Arabic and German layouts: grouped app, settings and folder rows); MoOS Hub has desktop right-click controls; remaining: English/German session matrix and booted-candidate readback |

P2.7 retains the stock Plasma task manager and one existing panel writer. It
does not install an unrelated dock/effects pack. Qt's native spring provides
retargetable scale feedback; layout, text legibility and hit targets stay
stable.^9 Native KNotification event defaults must match the installed KDE
event IDs and yield to personal choices.^10 Asset presence or successful audio
decoding is not evidence of login/logout playback. Test both event delivery and
session volume, including notification quiet mode and per-event/global mute.
The local source and NVIDIA-image gates are complete at `0bdb289e`; candidate
boot and upgraded-session evidence remain required before this row can close.

**Workspace facts (W7), read from KWin 6.7.5's own `kwin.kcfg` on 2026-09-17, not remembered.**
What MoOS leaves unset is already a sensible default, so W7 is not a config dump:
`ElectricBorderMaximize=true`, `ElectricBorderTiling=true`, `ElectricBorderCornerRatio=0.25`
(drag to an edge or corner tiles), `BorderSnapZone=10`, `WindowSnapZone=10`,
`Placement=Centered`, `FocusStealingPreventionLevel=1`, `TitlebarDoubleClickCommand=Maximize`,
`[TabBox] LayoutName=thumbnail_grid`, `[NightColor] Active=false Mode=DarkLight
NightTemperature=4500`, `[Compositing] AllowTearing=true`, `[Xwayland]
XwaylandEavesdrops=Combinations`. `[Compositing] AnimationDurationFactor` does not exist; the
factor lives in `kdeglobals [KDE]` (already correct). Real W7 work is what cannot be set from a
file and judged from a gate: the look of Overview and the task switcher in MoOS UI, a tiling
popover, per-effect durations taken from MoOS Motion, gestures, and touchpad defaults (P5.2).
Every one needs a live session and a before/after capture.

**What the station then measured, 2026-09-17, on the running session** (`44.20260917.858`,
KWin 6.7.5, 3840x2160 at 265%, Arabic, scheme `MoOSUI2AuroraLight`):

- **The switcher was MoOS's colour and nobody else's shape, and it read the wrong way.**
  The MoOS Plasma style reaches a stock switcher's palette but not its layout, so
  `thumbnail_grid` was correctly pale-mint and entirely Breeze in geometry, type, radii
  and its close button. Worse, it ran LEFT-TO-RIGHT in an Arabic session, because the
  stock layouts take direction from `Application.layoutDirection` and MoOS ships
  bilingual QML strings rather than Qt catalogues - so no translator is installed and
  that property is LeftToRight on every MoOS session. `org/moos/ui/Locale.qml` already
  warns about exactly this. **Fixed:** MoOS ships
  `usr/share/kwin/tabbox/org.moos.ui2.switcher` and selects it in `etc/xdg/kwinrc` for
  both `[TabBox]` and `[TabBoxAlternative]`; the five stock layouts stay installed and
  selectable. `tests/test_moos_switcher.py` holds the direction, the guarded motion and
  the close handler.
- **Overview cannot be re-shaped without forking KWin, so W7 does not try.**
  `/usr/share/kwin/effects/` contains only a third-party `cube`, the effects plugin
  directory contains only `kwin_overview_config.so`, and no `kwin/effects/overview` path
  exists anywhere on disk: the effect's QML is compiled into `libkwin.so.6`. There is no
  file to override and no supported extension point. Overview therefore gets
  configuration only - trigger, layout, and the durations it animates with - and its
  chrome stays stock until upstream offers a seam. Recorded so the next agent does not
  spend the hour re-discovering it.
- **KWin has exactly ONE duration control, and MoOS's own surfaces ignored it.**
  No per-effect `Duration` key exists in the installed schemas; `kwin.kcfg` declares
  `AnimationDurationFactor` (group `KDE`, so it lives in kdeglobals) and nothing else,
  and `moos-visual-tier` already writes it per tier (flagship 1, balanced 0.85,
  essential 0.4). It reaches QML only through `Kirigami.Units.longDuration` - the three
  Kirigami platform plugins all read that key and call `Units::setLongDuration`. But
  `Tokens.duration()` read it as yes-or-no, so on a tier asking for 40% the shell ran at
  40% while every MoOS surface ran at 100%. **Fixed:** `Tokens.scaled(longDuration, role)`
  converts a role by the same control and still returns 0 when animations are off;
  `tests/qml/motion-review.qml` proves the arithmetic on a real Qt runtime, including
  that the runtime's unscaled `longDuration` really is 200.
- **A KWin script's missing property is silent, and cost the first MoOS Arrange run.**
  `window.onCurrentDesktop` DOES NOT EXIST on KWin 6.7.5. It reads as `undefined`, and
  `undefined` inside an `&&` chain makes the chain falsy, so the candidate filter rejected
  every window and the script logged "nothing to arrange on this screen" rather than
  failing. Virtual-desktop membership is `window.desktops`, where an EMPTY array means
  "on all desktops". The window-movability properties are `moveable` and `resizeable`,
  both with the e — `movable`/`resizable` read as undefined, and BOTH spellings appear in
  `libkwin.so.6.7.5`, so only the live object settles it. Measured by printing the live
  window object into the journal with `console.info`, which is the one print that reaches
  it from a KWin script. `tests/test_moos_arrange.py` pins all of this.
- **MoOS Arrange ships as a KWin script, and its surface is the window menu.**
  `registerUserActionsMenu()` adds a submenu to the menu a person already has on a title
  bar, so the one-click arrangement needed no new window, no Bar slot and nothing running
  while it is unused. Arrangements go into `KWin.MaximizeArea`, so they clear the MoOS
  Bar. Proven live on the station on a scratch virtual desktop (so the owner's own windows
  were never moved): three windows into even thirds, then into a 60% main pane with two
  stacked beside it. **Open:** the live preview the plan's idea asks for, and a Bar entry.
- **A KWin script can be loaded and unloaded live**, through
  `org.kde.kwin.Scripting.loadScript`/`start`/`unloadScript` on the session bus. That is
  how each revision above was reviewed without restarting KWin, which on Wayland would
  have ended the session.
- **A pointer-driven live review needs calibration first.** `ydotool`'s absolute axis
  does not map 1:1 to this 3840x2160 screen; two hypotheses (screen pixels, and a
  0-65535 range) both landed the click elsewhere. Keyboard and CLI review worked.
  Anything in W7 that needs a real click is blocked on calibrating that axis.

**System-surface facts (W9), read from the source on 2026-09-18, not remembered.**
The Updater (`usr/bin/moos-update`) and Recovery (`usr/bin/moos-rollback`) are GTK4 windows on
`usr/lib/moos/moos_ui2.py`, which maps the live KDE colour scheme to GTK; Mo PC Remote builds
its own GTK window on the same palette. Everything else first-party is QML on `org/moos/ui`
under `moos-qml-shell`. Rendered from source for the first time that day, both GTK windows
opened shorter than their content (the primary button below the fold) and one button was
painted by the GTK theme's image rather than MoOS's colour — repaired in `MoOSApp`, which now
measures its page inside the window. Moving them onto MoOS UI (P2.1) means a QML page in
Settings fed by the status document: the update backend already publishes ONE record
(`/run/moos/update-state.json`, P1.5) that a status helper can carry, and `moos-image-update
resolve`/`stage --expected-digest` are the only verbs. Two constraints are fixed before any
design: `moos-open` is reachable by any web page, so an update route may never carry a digest
or a version — it reads the published record and the backend revalidates after Polkit; and
"Restart now" stays a button in a window, never an action on a notification
(`moos-update-ready`). What's new (W6.3) is the first page of that front door: an in-app page
of Settings, a `settings/…` route in `moos-open`, and a status-document field, with the GTK
launcher untouched.

Plasma 6 has no LTS branch and follows feature plus patch-release cycles.^1
MoOS therefore tracks stable releases through the shared base, keeps local
patches minimal, and runs its integration matrix on every Plasma transition.

### P3 — Mo AI as a trustworthy system operator

| ID | Task | Exit evidence |
| --- | --- | --- |
| P3.1 | Make provider setup self-diagnosing | distinguish missing key, invalid key, quota/billing, rate limit, outage and network failure without exposing secrets |
| P3.2 | Stream chat responses and show the answering model/provider in human language | measured first-token latency; cancellation and retry work |
| P3.3 | Generate native tool schemas from the `moai-do` allowlist | **In source (W6):** the schemas now reach the model on every machine (W4 attached them only when `!agentMode`, which defaults to true, so without Hermes they were never sent); every advertised value is run through the executor's own validator and every inspector combination through its own parser. **Measured 2026-09-18 (W9):** `moai-measure-actions` sends 40 fixed cases in Arabic AND English — 80 measurements — through the real gateway with the COMPLETE 42-tool schema, never forcing `tool_choice`, and scores the first call. First run with `nex-agi/nex-n2.5-pro:free`: **75/80 = 93.8%**, and four of the five misses were MoOS's fault, not the model's — `diagnose_services` ran the same two `systemctl --failed` commands as `list_failed_units` under an indistinguishable description, and `net_doctor`/`network_status` did not say which one reads and which one tests. The duplicate was retired from the model-facing schema and the network pair rewritten to point at each other. The same 80 cases were then measured twice: **80/80 = 100%** and **79/80 = 98.8%**. Neither run chose a WRONG tool; the single miss in the second was the model answering an Arabic request in words instead of calling — which is what varies between runs, and what the threshold has to survive. The case set is `system_files/usr/share/moos/moai-action-cases.json` and the gate is `tests/test_moai_action_selection.py`. **Still open:** a second model and a second machine — one machine, one brain is not a claim about MoOS |
| P3.4 | Use explicit confirmation cards and execution readback | **In source (W6):** several calls per answer, up to eight steps per message, the executor decides what needs a card (`needs_confirmation`, including Wi-Fi/Bluetooth OFF), confirmed actions are jobs that end when the process ends, and a non-zero exit reaches the model as "did NOT succeed". `tests/test_moai_agent_loop.py` drives the real window against a scripted provider and the real `moai-control`. **Open:** "re-read from the owning subsystem" is still the executor's own output; a station review |
| P3.5 | Add free-provider health and bounded failover | zero-price policy enforced; unhealthy route cooldown; no silent paid fallback |
| P3.6 | Add optional, redacted device context | clear consent; inspectable payload; secret and personal-path rejection tests |
| P3.7 | Make task completion evidence-based | failed/missing tool results prevent a task-wide success; process exit 0 cannot mark unexecuted steps complete; cancellation/restart fixtures |
| P3.8 | **In source (W6):** let the operator LOOK before it acts | `moos-inspect`, a third executor beside `moai-do` and `moos-control`: ten read-only tools (failed units, one unit, the journal, top processes, memory, storage, network, installed apps, booted/staged/rollback versions, MoOS's own logs), closed grammar, fixed argv, never escalates, output redacted by the support bundle's `redact()`; `tests/test_moos_inspect.py`, `tests/test_moai_tool_schemas.py`. Open: measure which of them a free model actually chooses correctly (feeds P3.3) |
| P3.9 | **Owner decision:** an owner-enabled host shell for Mo AI | The owner asked on 2026-09-17 for an agent that "executes everything, with every permission", like a coding CLI. W6 deliberately stops short of that: the loop can inspect anything listed in P3.8 and run every fixed repair, but there is still no tool that runs a command the MODEL wrote, because that turns every web page and log line the model reads into a command source, and architecture rule 5 forbids it. If the owner confirms, the shape that keeps a person in the loop is: a `run_command` tool available only at the existing Settings → Permissions tier `system` or `full`; the exact command shown on the confirmation card; runs as the user, never root (polkit still asks the person for anything privileged); output redacted and bounded; one journal line per command; OFF by default; rule 5 and `AGENTS.md` rewritten in the same change. Not started |
| P3.10 | **In source (after W6, `feat/moai-skills-20260917`):** Mo AI skills — what a free model does not know about THIS system | twelve repair playbooks shipped read-only under `usr/share/moos/moai/skills/` (no sound, no internet, slow, disk full, update and rollback, failed service, app will not start, Bluetooth, graphics and NVIDIA, startup, installing software incl. App Drop, games/Windows/Android). The model finds them with `list_skills` and reads one with `read_skill` — two more read-only `moos-inspect` tools, an enum of shipped ids, no card. A skill grants nothing: every step is an existing tool under that tool's own confirmation rule. `tests/test_moai_skills.py` reads each skill the way the model will: every tool, argument and enum value exists in the schema, every unit name has the reader's shape, no command lines, no other system's name, "asks first" where a repair asks; the real reader returns each one whole and refuses a planted link. Eight one-tap chips under the home screen's four cards open the other playbooks in the person's words. The same branch repairs the navigation rail at the window's DEFAULT size (940 px opens the compact rail, which laid icon and label out in opposite corners of the pill and cut "Workbench" off — every earlier review had been rendered at 1400 px); `tests/test_moai_rail_layout.py` measures the real window in both modes and both directions. **Open:** measure with a real free model whether it reaches for a skill and follows it (goes with the P3.3 measurement); a Skills panel in the window (quick-start chips); MCP: Mo AI's agent runtime has ONE reviewed, read-only MCP client (Context7 library documentation, `usr/lib/moai/moai_web.py`); a general MCP client — owner-chosen servers, each tool behind a card — is not started and needs the same closed-grammar treatment a native tool gets (the repo's own `.mcp.json` is for development agents, not for Mo AI) |

Privileged OS operations remain fixed `moai-do` actions. The existing developer
runtime also exposes approved isolated project commands; that is a separate
capability, not permission to run generated commands as host administrator.
Audit approval, sandbox containment and task-result propagation explicitly.
No provider key crosses to another provider. A free route requiring billing is
unavailable, not successful configuration.

### P4 — Applications and compatibility

| ID | Task | Exit evidence |
| --- | --- | --- |
| P4.1 | Unify every install/update/remove request behind Mo Store | UI, Mo AI and URL routes share job IDs, progress, cancellation and readback |
| P4.2 | Audit desktop-app permissions and prefer portals | permission inventory; file/camera/screen/print flows work without broad filesystem or bus access |
| P4.3 | Turn Windows compatibility into a per-app runner product | isolated prefix per app; install/launch/reopen/update/remove for ten published test apps |
| P4.4 | Turn Android compatibility into a per-app product | on-demand container; launcher/files/clipboard/audio; ten test apps on Intel/AMD and NVIDIA fallback |
| P4.5 | Publish a generated compatibility matrix | supported/experimental/unsupported status names edition, architecture, GPU and tested version |
| P4.6 | **In source (W6):** App Drop — an application that arrives as a file | AppImage (extracted once inside bubblewrap into `~/Applications/<name>/`), portable archives (extracted by `moos_appdrop.py`, hostile members refused by name), Flathub `.flatpakref` (the ordinary verified path); `.rpm`/`.exe`/`.apk` handed to their existing routes; `.deb` and `.flatpak` bundles refused with the reason. Consent dialog with default No on every path; one Mo Store job (`moos-storectl install-file`). `tests/test_app_drop.py` builds the hostile files and runs the real sandbox. **Open:** a real AppImage on a MoOS machine; the dialog, the file-manager action and the `~/Applications` watch reviewed on a desktop; what a double-click on an AppImage did before (read from source, never observed); `.flatpak` bundles through libflatpak; **discoverability** — nothing points a person at `~/Applications` yet: a Places entry in the file manager (check on a desktop how the places model treats a seeded `user-places.xbel` before shipping one) or a launcher entry, which needs its own designed icon |
| P4.7 | A drop target in Mo Store's own window | needs a `Q_INVOKABLE installFile(path)` with a path validator in `build_files/moos-qml-shell.cpp` (the bridge's `validId` rejects paths) and a full image build; the Store must not use the public `moos:` scheme for it |

Flatpak sandboxes deny host access by default and portals provide controlled
access to files and services.^5 MoOS should keep per-user app development and
testing isolated; drivers and privileged services do not belong in a Flatpak.^6

### P5 — Hardware, performance and form factors

| ID | Task | Exit evidence |
| --- | --- | --- |
| P5.1 | Hardware qualification lab | repeatable GPU/audio/Wi-Fi/Bluetooth/camera/storage/firmware suite and published device records |
| P5.2 | Laptop policy | lid, brightness, battery health, power profiles and two suspend cycles on at least three platforms; **tap-to-click and natural scrolling by default** — KWin 6.7.5 stores libinput settings per device (`kcminputrc [Libinput][vendor][product][name]`, keys `TapToClick`, `NaturalScroll`, … confirmed in `libkwin.so`) and no system-wide defaults group was found, so a file in `/etc/xdg` would be dead config; the supported route is a one-time, ledger-recorded first-login step that sets the properties KWin exposes per device on D-Bus for touchpads the person has not configured. Needs a real laptop |
| P5.3 | Touch/tablet policy | automatic mode, ≥44 px targets, keyboard, rotation, gestures and stylus on real hardware |
| P5.4 | Performance budgets | boot, idle CPU/PSS/wakeups, app launch p95, scroll/frame pacing, build load and AI latency per tier. **Owed by W5:** `moos-privacy-monitor` polls PipeWire every 1.5 s for the whole session on every machine and was never measured; W6 cut it from three `pw-dump` spawns per round to one (12 ms → 4 ms on an idle pipewire 1.6.8), **Measured 2026-09-17** off the station (Fedora 44 under WSL2, x86, idle PipeWire with 37 objects): 60 s of the loop cost 0.39 s of CPU including its `pw-dump` children — 0.66% of one core, 40 process spawns a minute. Small enough to leave the simple poll alone on a desktop; its cost on the station and on the A1's slower cores, and its wakeups on a battery, are still unmeasured — prefer `pw-dump --monitor` with a slow safety poll only if one of those shows **Closed for the flagship tier, 2026-09-18 (W9.2):** `moos-measure-speed` measures boot userspace, session ready, an app's window appearing (asked of KWin) and MoOS's OWN idle CPU against `speed-budgets.json`, keyed on `moos-visual-tier`. Station: 6.034 s / 1.108 s / 0.46 s / 2.6%, all inside budget. **Still open:** the same four rows on a balanced and an essential machine — those tiers' budgets are derived, not measured — plus app-launch p95 and frame pacing, which this tool does not attempt. |
| P5.5 | Cloud desktop efficiency | encode CPU/GPU, frame pacing, bandwidth degradation, reconnect, multiple accounts and audio sync |
| P5.6 | Storage lifecycle | update headroom, Flatpak/container cleanup, log bounds and low-space recovery without deleting user data |
| P5.7 | Qualify kernel policy and driver transitions | MoKernel sysctl/module/karg readback; exact kernel/NVIDIA match; boot/initramfs, frame pacing, audio underruns, CPU/RAM pressure and thermal/power regression measurements |
| P5.8 | Qualify Wayland and compositor lifetime | portal consent/revocation/restart; multi-output scale/hotplug; clipboard/input-layout continuity; separate users; long-session KWin PSS/pressure and recovery |

`mokernel` is MoOS's policy/readback wrapper around the signed Linux kernel,
not a forked kernel. `moos-visual-tier` selects visual budgets;
`moos-hardware-adapt` owns safe hardware initialization; device identity comes
from `moos_hardware.py`. Do not create rival tuners or infer performance from
configured values. The installed KWin memory guard is containment, not proof
that the historical growth cause is fixed. P5.8 must reproduce or rule out
growth with an explicit workload and duration.

### P6 — Release engineering and long-term trust

| ID | Task | Exit evidence |
| --- | --- | --- |
| P6.1 | Resolve immutable base inputs once per release | recorded x86 and ARM base digests; all edition jobs consume them |
| P6.2 | Produce SBOM and provenance for each image | signed attestations linked to exact digest and source SHA |
| P6.3 | Align ARM rebuild and promotion cadence, and say how a security update actually arrives | **Half closed 2026-09-18 (W9.5).** ARM had NO scheduled rebuild at all, so a base change that broke the aarch64 tree stayed invisible until someone touched one of its paths; it now rebuilds nightly at 07:00 UTC, an hour after x86. And `build-arm.yml`'s promote job required a `push` event while a release cycle dispatches it, so **no cycle had ever promoted ARM** — fixed in W9.4's release work, and gated. **Still open, and it is the important half:** a scheduled rebuild can never reach a machine. `build.yml` pushes only a candidate tag and `promote-x86.yml` refuses any run that is not a `workflow_dispatch`, so **the cadence of release cycles IS the security cadence of MoOS** — an owner who does not run one gets no base security updates, however many nights are green. That is the safety model working (nothing ships unproven) and a real gap at the same time. The decision it needs is the owner's: either a scheduled cycle that runs the full proof set unattended and promotes, or an explicit statement of the supported cadence. `tests/test_security_update_reachability.py` holds the claim and the mechanism together meanwhile |
| P6.4 | Add staged rollout and release health | candidate ring, development machine ring, broader ring; halt and rollback criteria |
| P6.5 | Security review the MoOS URL scheme, Remote and AI boundaries | threat model, negative tests, dependency audit and externally reviewable report |
| P6.6 | Establish support lifecycle and migration policy | published support window, upgrade path, rollback window and end-of-support behavior |

Android's modern update design retains boot-critical fallback state and marks a
new system successful only after boot.^7 MoOS uses different technology, but the
product expectation is the same: an interrupted or bad update must leave a
known-good boot path. This remains an acceptance requirement, not marketing.

## Development-machine profile

The physical PC is a MoOS engineering station. Its setup must be reproducible,
not an undocumented pile of host changes.

The first slice is implemented: `just workstation-check` runs
`scripts/setup-development-machine.sh --check` on the host, including when
invoked from VS Code Flatpak. It reads signed-origin state, real `/var` space,
tool paths, native SDK availability, KVM access and redacted GitHub readiness.
It installs nothing and does not launch apps. A successful inventory is not a
successful SDK build. `.vscode/extensions.json` carries the shared editor
recommendations; machine-specific paths remain local.

The remaining provisioning slice must:

- install editor/SDK/debug tools in user sandboxes or Toolbx/Distrobox-style
  development containers where possible;
- configure Git and GitHub authentication interactively without storing tokens
  in the repository;
- install QEMU/KVM, image, accessibility, performance and network-debug tools
  through an auditable profile;
- verify Podman, `just`, Flutter/MoPlayer, .NET/MoRemote, QML and Python gates;
- keep the report free of credentials and private configuration;
- be idempotent and support `--check` without mutation.

Do not layer compilers onto the immutable host merely for convenience. Do not
put API keys in `.env`, committed config, shell history or test fixtures.

Performance work starts with repeated measurements, not removing dependencies
based on RPM size metadata. The current boot is 36.783 s with 5.325 s in
`ldconfig`; P5.4 must check another boot and a real idle interval. P5.6 must
measure final image/ISO bytes and package reverse dependencies before removing
unused payload. Compiler SDKs stay in user/development environments; optional
office, Android and compatibility stacks remain on demand.

## Documentation policy

- `README.md`: stable entry point and repository workflow.
- `PROJECT_STATE.md`: current measured state, normally under 200 lines.
- `docs/DEVELOPMENT_PLAN.md`: this plan and task status.
- `RELEASE.md`: release contract.
- `docs/AGENT_GUIDE.md`: operational traps that remain true.
- Component-local documents: only live architecture or operating instructions.
- Git history: incident diaries, old plans, rejected visuals and screenshots.

No completed task is appended as a narrative. Replace the old state with the
new measured state. Evidence generated by CI belongs in the workflow artifact;
only a small canonical fixture belongs in Git when a test consumes it.

## Sources

1. KDE Community, [Plasma 6 release schedule](https://community.kde.org/Schedules/Plasma_6), accessed 2026-09-13.
2. KDE, [Plasma 6.7.5 release information](https://kde.org/info/plasma-6.7.5/), 2026-09-08.
3. bootc project, [Managing upgrades and rollback](https://bootc.dev/bootc/upgrades.html), accessed 2026-09-13.
4. systemd project, [Automatic Boot Assessment](https://systemd.io/AUTOMATIC_BOOT_ASSESSMENT/), accessed 2026-09-13.
5. Flatpak project, [Basic concepts: sandboxes and portals](https://docs.flatpak.org/en/latest/basic-concepts.html), accessed 2026-09-13.
6. Flatpak project, [Introduction and packaging boundaries](https://docs.flatpak.org/en/latest/introduction.html), accessed 2026-09-13.
7. Android Open Source Project, [Virtual A/B overview](https://source.android.com/docs/core/ota/virtual_ab), accessed 2026-09-13.
8. KDE Developer, [Plasma themes and plugins](https://develop.kde.org/docs/plasma/), accessed 2026-09-13.
9. Qt, [SpringAnimation](https://doc.qt.io/qt-6/qml-qtquick-springanimation.html) and [Behavior](https://doc.qt.io/qt-6/qml-qtquick-behavior.html), accessed 2026-09-13.
10. KDE, [KNotification configuration implementation](https://github.com/KDE/knotifications/blob/master/src/knotifyconfig.cpp), accessed 2026-09-13.
