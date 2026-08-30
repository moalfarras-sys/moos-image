# MoOS — current project state

This file is current state, not session history. Git history owns the history.
When documentation disagrees with a running machine, a freshly booted artifact,
or current source, those stronger forms of evidence win.

Last reconciled: **2026-08-28 (post-reboot Phase 4 audit)** — verification on the new
deployment `49d73f3965a1` (44.20260828), booted live:

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

## ISO build pipeline — REPAIRED (2026-08-25)

The ISO built fine but the `Upload ISO as workflow artifact` step ran **last**,
so when the QEMU boot/install proof steps failed in the GitHub runner (a runner
environment limitation, not an ISO defect) the whole job aborted and the
already-built ISO was dropped.

Fix (merged to `main`, commit `5279e2b8`): the ISO upload now runs **before**
the proof steps, so the artifact is captured even if a later proof step fails.
The proof gates themselves stay hard-fail (no `continue-on-error` was added — we
do not weaken a guard to make a build pass).

**Resulting build (run #32851648759):** `conclusion: success` — all 17 steps
green, including `Boot and prove the exact final live ISO` (step 14) and
`Install the exact final ISO offline and boot the target disk` (step 16). The
ISO is therefore **proven to boot its LiveOS, perform the offline install to a
blank disk, detach, and boot the installed system** in CI.

Deliverable: `Desktop/moos-live.iso` (generic `moos:latest`, ~4.8 GB, bootable
ISO 9660, label `MoOS-Live`). Boots + installs on any x86_64 (Intel/AMD). Does
NOT carry nvidia in the initramfs — for nvidia hardware use the `moos-nvidia`
image/update path.

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
- The ISO upload-before-proof ordering must stay; the proof gates stay
  hard-fail.
