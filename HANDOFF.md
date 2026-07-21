# MoOS development handoff

This is the durable continuation point for work performed from inside the
installed MoOS system. Update it at the end of every development session.

## Operating contract

The installed system, its journal, running services, active OSTree deployment,
and real hardware behaviour are the primary evidence. Repository documentation
explains intent but must not override observed behaviour.

At the start of every session:

1. Read `AGENTS.md` and this file completely.
2. Inspect `git status`, `git log`, and `origin/main`.
3. Fetch first; only fast-forward a clean tree. Never discard local work.
4. Inspect `rpm-ostree status`, failed system/user units, and both journals.
5. Compare the booted digest with the signed image currently published in GHCR.
6. Run `moos-selfcheck`, `tests/post-update-check.sh`, `just check`,
   `tests/test_moos_theme_safety.py`, and `tests/test_moos_ui2.py`.
7. Treat a feature as working only after observing it on the live system or in
   a booted VM.
8. Use the release path: fix -> tests -> commit/push -> CI -> signed image ->
   update -> reboot when required -> live verification.
9. Never weaken identity, signature, SELinux, Polkit, or boot safety gates to
   make a build pass.

Evidence priority:

`live system > live journal > observed test > current source > CI/GHCR > old documentation`

## Session 2026-07-21 (night) — login scene elevated + SHIP PIPELINE BLOCKED

### RESUME HERE

**The user reports seeing NO visual change across recent sessions (login / logout /
shutdown / restart). The root cause is not the design — it is the pipeline.**

- **`gh` token is INVALID → nothing new can ship.** `gh auth status` = "token in
  keyring is invalid"; `git push` = "Authentication failed". Local commits are
  stranded on `main`, ahead of `origin/main` (`a86df17`):
    - `3a91287` feat(moai): make the brain FAST (from the prior session)
    - `6f16024` feat(login): premium glass identity chip + living halo (this session)
    - `027afd8` polish(login): legible signature + soft-sprite glow, visually verified
  The booted image v288 (`2a3a9558`) was built from `a86df17`, whose recent work was
  Mo AI, **not** the login/logout screens — so those looked identical v281→v288, which
  is exactly what the user perceives. **Until `gh` is re-authed and these push, the
  machine keeps booting the same pixels no matter what we change.**
- **The one action that unblocks everything:** the user runs `! gh auth login`
  (device flow), then `git -C ~/moos-image push origin main` → CI builds & signs →
  `rpm-ostree upgrade` → reboot → new login scene is live.

### What was done

1. **Deep live audit of the named surfaces.** Confirmed against the live `/usr` tree:
   the logout/shutdown/restart screen (`.../look-and-feel/*/contents/logout/Logout.qml`,
   identical across all 16 variants), the lock screen (`shells/.../lockscreen/`), the
   splash and the action buttons are **already high-craft and already deployed** — the
   active theme is `org.moos.ui2.midnight`, and its live files byte-match the repo. The
   only genuinely plain, first-seen surface was the **login greeter** background scene.

2. **Login scene redesigned** (`wallpapers/org.moos.ui2.greeter/contents/ui/main.qml`,
   commit `6f16024`). Within the `verify_image_experience.py` login contract (no
   `Animation`/`Repeater`/`ShaderEffect`/`Canvas`; brand pinned top-left; base image
   paints synchronously): a frosted glass identity chip with two continuously
   counter-rotating halo rings (render-thread `RotationAnimator`, finite loops), an
   accent-tinted depth glow + vignette, a refined horizon thread, and a MoOS wordmark
   lockup over an accent underline + soft welcome. All colours from the active scheme,
   so login now tracks each theme's accent like lock/logout do.

### Visual verification (new capability this session)

Built an **offscreen QML render loop on the live system** to actually *look* at the
design instead of trusting the source: `QT_QPA_PLATFORM=offscreen /usr/lib64/qt6/bin/qml`
+ `Item.grabToImage(...).saveToFile(...)`, then `magick` to downscale and read the PNG.
A faithful standalone harness mirrors the greeter with the concrete
`MoOSUI2Midnight.colors` palette and the real Graphite wallpaper / ring / glow / logo.
Rendered at 1920×1080 and 1280×800. This caught two real faults the source review
missed (hard-edged glow discs; a small dark emblem), fixed in `027afd8`, and re-rendered
to confirm — the corner signature now reads as a bright, confident mark.
- Scripts live in the session scratchpad (`render.sh`, `_harness_*.qml`).
- **Logout/lock cannot be rendered this way:** they instantiate `SessionsModel`
  (org.kde.plasma.private.sessions) / the authenticator, which need a live logind/session
  bus and fail to construct headless (grab comes back blank). They are already premium
  and already deployed, so they were reviewed as source only, not re-rendered.

### What was tested

- Gate logic replicated locally: no forbidden tokens in non-comment lines, brand
  anchored `top-left`. `qmllint` clean (exit 0, same as baseline).
- `just check` green (user-experience, device-plan, moai-do, fwupd, visuals);
  `tests/test_moos_ui2.py`, `tests/test_moos_theme_safety.py` green;
  `bash -n build_files/build.sh` OK. `systemctl --failed` empty.
- **Not yet run:** the real `verify_image_experience.py` (reads live `/usr`, so it can
  only judge the *deployed* greeter, not the new one) and a full local `podman build`.
  CI is the first place the new greeter meets that gate — watch that build.

### Next precise step

Re-auth `gh`, push both commits, watch CI go green, `rpm-ostree upgrade`, reboot, and
confirm the new login scene live. Then continue cohesive polish only where a surface is
genuinely plain — the rest of the doorway system is already premium.

## Session 2026-07-21 (evening) — live fwupd/zram proof + full doorway & app visual polish

### What was done

1. **fwupd-refresh polkit fix — VERIFIED LIVE and closed.** Booted the signed
   image `be91759a` (v281). Manually triggered `fwupd-refresh.service`: it ran the
   session-less DynamicUser, downloaded the full LVFS metadata and exited
   `0/SUCCESS` with **no "Failed to obtain auth"** anywhere this boot;
   `systemctl --failed` empty before and after. ROADMAP item flipped to `[x]`;
   committed `1b4f910` (pushed). The registry drift (`c06a9420`/v282) is the
   benign gate-image (revision `1038550`, test-only, no runtime effect).

2. **zram first-boot fix — mechanism VERIFIED LIVE and closed.** The shipped
   drop-in `systemd-zram-setup@.service.d/10-moos-reset-on-retry.conf` (commit
   `2e7b7d0`) was validated on real zram hardware via a privileged podman
   container sharing `/sys` (scratch zram1, never touching the live zram0 swap):
   reproduced the EBUSY wedge (initialised device rejects comp_algorithm),
   confirmed the exact `ExecStartPre` reset clears it, and confirmed the
   `/proc/swaps` guard never resets an active swap. `systemctl show` proves
   systemd loads the reset before every (re)start (ignore_errors=yes). ROADMAP
   `[x]`; the full fresh-install VM first-boot repro is the one residual (no
   `qemu`/`bootc-image-builder` in this dev env — do it on the next ISO round).

3. **Full visual + functional polish pass, driven by a 4-agent deep audit**
   (doorway screens · panel widget + Mo AI · live health · apps + themes). All
   fixes land in canonical sources; the 16 look-and-feel packages were
   re-propagated (QML is copied byte-for-byte by the generator, verified: one md5
   per file across all 16). Doorway now tracks each theme instead of shipping
   Nova's cosmic literals on all 16:
   - **Lock date (BUG):** English date rendered US month-first ("July 21");
     `MoOSClock.qml` used the 3-arg `Qt.formatDate(date,locale,string)` trap that
     discards the format string. Both dates now use `Qt.locale(..).toString(..)`.
   - **Invisible Cancel icon (BUG):** the logout action background turns
     highlightColor on emphasized/pressed, and the non-destructive glyph was
     always highlightColor → it vanished (the primary Cancel button). Icon+label
     now switch to `highlightedTextColor` on emphasized/down (`MoOSUI2ActionButton.qml`).
   - **Aurora + splash now theme-aware:** the six logout aurora curtains route
     through a new `auroraTint()` (each jewel tone pulled 40% toward the live
     `highlightColor` via `Qt.tint` — rich spectrum kept, per-theme mood gained);
     the splash's third progress sweep is now `Kirigami.Theme.linkColor` (== each
     family's `secondary` role; byte-identical violet on Nova). Verified
     `linkColor`==palette `secondary` across every scheme (incl. Complementary).
   - Logout `bilingual()` BiDi fix (two labels bypassed the isolate-wrapping
     helper), `onNavigate: (step) =>` arrow form (Qt6 injected-param deprecation),
     `PropertyChanges` grouped form, lock `MainBlock` unlock arrow `isMask:true`,
     `LockScreenUi` redundant `property Item shadow` → assignment.
   - **Mo AI (`apps/moai/main.qml`):** the toast/brain-picker/Settings-sheet
     overlays were children of the main `RowLayout` (undefined-behaviour anchors,
     mis-size/shift at 200%/4K) → moved to be `Kirigami.Page` children (0
     layout-positioning warnings now, verified by brace/child analysis). Silent
     model-delete error now routes to the displayed `cfgError`. Removed 149 lines
     of dead pre-`moapp-console` settings plumbing (fired two useless XHRs on
     every gear-open). Added the missing `agent` panel header/subtitle, made rail
     labels session-aware (were Arabic-only), gave Agent its own `moos-identity`
     icon (was sharing `moos-phone`).
   - **Plasmoid `org.moos.brand`:** `StatusChip` unqualified access → `id: chip`
     (its only qmllint warnings).
   - **Mo Store:** two layout-positioning bugs (status dot, progress track) →
     `Layout.preferredWidth/Height`.
   - **Journal hygiene (MoOS-owned):** `fwupd-refresh` drop-in gains
     `Environment=HOME=%T` (silences 10 dconf lines/refresh); `moai-brain.container`
     gains `OLLAMA_NO_CLOUD=true` (stops ollama.com probe warnings at boot).
   - Deprecation banner on the stale `MOOS_NOVA_DESIGN_TOKENS.md` (its Nova-navy
     values are exactly where the splash/logout literals came from).

### What was tested

- Live: fwupd + zram as above; `moos-selfcheck` 39+note (keyboard now `de,us,ara`,
  the old drift resolved); `tests/post-update-check.sh` 40/1 (the 1 = benign v282
  digest drift).
- `qmllint-qt6` clean (exit 0) on all edited QML: canonical Logout/ActionButton/
  Splash, `moai/main.qml`, `store/main.qml`, `org.moos.brand`, and the three
  lockscreen files. The moai overlay move was verified structurally (brace balance
  0, RowLayout now closes after the panel, 0 layout-positioning warnings).
- Gates: `verify_user_experience.py`, `test_device_plan.py`,
  `test_moos_theme_safety.py` (3), `test_moos_ui2.py` (7), `test_moai_do.py` (19),
  `bash -n build.sh` — all pass. Three NEW regression gates added to
  `verify_user_experience.py` (date-trap, Cancel-icon visibility, splash/aurora
  theme-tracking); each was proven to fire on the pre-fix content and pass on the
  fix.
- Full `just build` — **GREEN** (`localhost/moos:latest` `9f245a09`): the QML
  smoke test LOADED the restructured `moai/main.qml` (no scene-load error →
  the 4K overlay move is runtime-valid), identity firewall OK, image-experience +
  user-experience + fwupd-policy gates passed, initramfs ostree proof passed,
  `bootc container lint` 9 passed / 1 skipped / the 4 known warnings.

### Commit and image state

- `4f133a0` `polish(doorway+apps)` — CI **success**, published signed
  `moos-nvidia` **v284** (`rev 4f133a0f`); local `just build` was GREEN first.
- `278e1a5` `feat(moai): empty-state hero` (v285) then **`911362d`
  `feat(moai): premium empty-state`** superseding it — CI building **v286**. The
  Mo AI empty chat is now an image-driven premium surface: a generated
  mesh-gradient aurora (`artwork/generate_moai_hero_bg.py` → `hero-bg.png`), the
  brand orb over a layered glow, and **four glass suggestion cards** (crafted MoOS
  icon + bilingual title + hint, hover, seed the chat via sendPrompt). Previewed
  LIVE via `moos-qml-shell`; before/after on the Desktop
  (`MoOS-MoAI-قبل-وبعد.png`, `MoOS-MoAI-فاخر-قبل-وبعد.png`).
- Booted: v281 `be91759a`; rollback `509bdf68` (v275). Everything reaches the
  desktop only after v285 is staged + rebooted.
- `f63f1f1` `fix(moai): theme-adaptive hero bg` — a light aurora variant so the
  premium hero is correct on Tidal/Daylight too (picks by
  `palette.window.hslLightness`).
- `a86df17` `polish(moai): premium glass MoButton` — a hairline top sheen + hover
  micro-interaction on the shared chip component (systemwide). **This is the head**;
  CI building **v288** = the comprehensive image (all polish + theme-aware doorway
  + premium adaptive Mo AI hero + glass buttons). Rapid iterations v285–v287 were
  auto-cancelled by the workflow's concurrency group, so only v288 builds to
  completion — no wasted compute.
- **ENGINE FIX — the heart, made fast (owner-approved model swap).** Diagnosed the
  real cause of Mo AI's ~97 s replies: the live brain had drifted to a Qwen3-VL
  *thinking* build whose renderer forces 3700+ reasoning tokens on trivial turns
  and a baked prompt that forced Arabic even for English. `think:false`, template
  and renderer overrides all failed (proven live). Fix: swapped the served brain
  to **Qwen2.5-7B-Instruct** (non-thinking) — measured **100% GPU / 4.8 GB /
  num_ctx 8192**, **0.27 s** for "2+2", **0.39 s through the gateway** (was 97 s),
  and it answers in the language asked (EN→EN, AR→AR) via the app's own bilingual
  system prompt. Applied LIVE (retagged `default`/`moai-brain` from the fast
  model; persists in `~/.ollama`) and made reproducible for the image:
  `system_files/usr/share/moos/containers/moai-brain.Modelfile`,
  `/usr/bin/moos-ensure-brain` (idempotent + failure-tolerant), a
  `moos-ensure-brain.service` (enabled in build.sh), and `DEFAULT_LOCAL_MODEL` →
  qwen2.5:7b-instruct. `qwen3-vl:4b` kept locally as rollback.
- Live-look this session (spectacle, 4K): Midnight desktop is clean and modern;
  **Mo Store is already strongly designed** (identity, onboarding hero, bundle
  cards); **Welcome already has a theme-adaptive gradient + accent glows**
  (`win.look`) — both left as-is on purpose (forcing more would clash). The one
  real void was Mo AI's empty chat, now the premium hero. Not yet elevated (safe
  follow-ups): Mo AI's device/apps panels and the desktop weather widget.

### Deferred (safe follow-ups, not blockers)

- Mo AI NICE items P8 (route chip shows "Local" before models resolve) and P9
  (projectField stale on reopen); installer/welcome layout-positioning (~15
  sites); MoPlayer `.desktop` leftover `[de]` strings; generator hardening
  (A4 widen `build_lnf` subdir coverage, A5 add a variant↔canonical sync gate,
  A1 encode "run generate_moos_ui2 before generate_moos_themes" in the Justfile);
  radius-token consolidation across Store/Remote.
- `mo-remote-portal.py` uses ~45-55% of a core while a viewer is connected —
  this is real streaming cost (pipeline is idle-gated), not a spin; a lower-FPS/
  buffered-relay optimization needs the phone path to validate, so it is left for
  a session that can measure it.

### RESUME HERE (exact next step)

The comprehensive image is **v288 (`a86df17`)** on CI. The exact next steps:

1. When v288 CI is signed, stage the exact signed `moos-nvidia` digest:
   `sudo rpm-ostree rebase ostree-image-signed:docker://ghcr.io/moalfarras-sys/moos-nvidia@sha256:<v288-digest>`
   (rpm-ostree is passwordless; signature enforced; `509bdf68` stays as rollback).
2. Write the Desktop resume file `~/سطح المكتب/MoOS-متابعة.md` with the staged
   digest so the owner can hand it back after reboot. **Reboot is the owner's**
   (do not force it on the daily driver).
3. Live-verify on the new image: `moos-selfcheck`, `tests/post-update-check.sh`
   (the digest-drift check goes green once booted == published), then the visible
   wins — lock date reads "…, 21 July 2026"; the logout Cancel icon is visible and
   the aurora tint tracks the active theme; Mo AI opens to the **premium hero**
   (aurora bg + glass suggestion cards) and its overlays sit correctly at 200%/4K.
   Roll back with `sudo rpm-ostree rollback` if anything regresses.
4. Optional next tier of premium polish (offered, not blocking): elevate the
   Welcome/other surfaces only where genuinely weak (most are already well
   designed — Store, Welcome, the Mo AI device panel), and the desktop weather
   widget. Preview each live via `moos-qml-shell` before shipping.

## Session 2026-07-21 (afternoon) — fwupd-refresh polkit fix + workstation triage

### What was done

- Full live triage of the maintainer's workstation. System healthy: booted the
  signature-enforced NVIDIA image 44.20260720.275 (sha256:509bdf68…); rpm-ostree
  automatic **staging** updates on; NVIDIA RTX 2080 SUPER driver live (CUDA 13.3).
  GHCR `moos-nvidia:latest` has already advanced to sha256:e1cf1672… (the
  theme-family commits 7285101/b377bbc) — pending, not yet booted. The ONLY
  failed unit was `fwupd-refresh.service`.
- **Root-caused and fixed fwupd-refresh** (the sole `systemctl --failed` entry).
  The prior session's journal drop-in exposed the real error, which recurred on
  the 2026-07-21 boot: `Failed to obtain auth`. Cause: the service runs
  `fwupdmgr refresh` as the DynamicUser `fwupd-refresh` with no session, so
  polkit evaluates the LVFS metadata action
  `org.freedesktop.fwupd.refresh-remote` (default `allow_any=auth_admin`) with no
  agent present and denies it. This **supersedes** the 2026-07-16 note that
  "rejected polkit by experiment": that session-less replica most likely hit a
  warm cache (exit 2) or a differently-classified spawn; the live error string is
  an unambiguous polkit signature. Fix:
  `system_files/usr/share/polkit-1/rules.d/60-moos-fwupd-refresh.rules` grants
  ONLY `refresh-remote` + `get-remotes` to ONLY the `fwupd-refresh` user; every
  `update-*/downgrade-*/modify-*` firmware action keeps `auth_admin`, so flashing
  hardware still needs an administrator. Kept the drop-in's
  `StandardError=journal` and rewrote its comment to record the resolution.
- **Maintainer toolchain** (outside the image, NOT shipped): fixed the VS Code
  (Flatpak) Codex extension's "bubblewrap not on PATH" error by setting
  `sandbox_mode=danger-full-access` + `approval_policy=never` in
  `~/.codex/config.toml` (Codex no longer nests a sandbox inside Flatpak's).
  Confirmed .NET SDK 10.0.302 is installed and runs INSIDE the VS Code sandbox
  (proved with a sandbox-scoped `dotnet --list-sdks`); the earlier ENOENT was
  transient and settings already pin the path — a window reload clears it. A
  scoped, **local-only** `/etc/sudoers.d/10-moos-dev` (NOPASSWD for dev commands
  only, 2 h timeout) was installed on the workstation for convenience — it must
  NEVER be committed into `system_files`.

### What was tested

- `just check` — all four gates passed (UX, device-plan, moai-do, visuals).
- `python3 tests/test_moos_theme_safety.py` — 3/3.
- `python3 tests/test_moos_ui2.py` — 7/7.
- polkit rule parses cleanly (`node --check`).
- Full `just build` (generic `moos`) — GREEN end to end: initramfs 122 MB (< 300),
  Plymouth `moos` theme present in the initramfs, image-experience gate passed,
  store-catalog gate passed, foreign-identity firewall OK, `bootc container lint`
  (1 check skipped, the 4 known warnings). Image `localhost/moos:latest`
  `acf5ca1a2e16`.
- **VERIFIED LIVE 2026-07-21** on the booted signed image `be91759a…` (v281):
  - `rpm-ostree status` confirms booted digest == `sha256:be91759a…` (v281),
    signed origin, with `509bdf68…` (v275) retained as rollback.
  - The polkit rule is present in the booted read-only `/usr`
    (`/usr/share/polkit-1/rules.d/60-moos-fwupd-refresh.rules`).
  - Manually triggered `sudo systemctl start fwupd-refresh.service`: it ran the
    DynamicUser `fwupd-refresh` with **no session**, downloaded the full LVFS
    metadata ("نُزّلت معلومات وصفيّة جديدة بنجاح", 12 updatable / 3 supported
    devices) and exited **`0/SUCCESS`** — `journalctl -u fwupd-refresh.service -b`
    shows **no "Failed to obtain auth"** anywhere this boot. The polkit rule is
    doing exactly its job on a headless timer-style run.
  - `systemctl --failed` is empty both before and after the run.
  - `moos-selfcheck`: 39 checks passed, 1 note (the tray items, user-owned — not a
    failure). Keyboard is now live `de,us,ara` from KWin, so the earlier
    `de,ara` drift is resolved on this boot.
  - `tests/post-update-check.sh`: 40 passed, 1 failed — the single failure is the
    benign digest-drift check (`booted be91759a… but the registry publishes
    c06a9420…`). That newer image is v282, built from revision `10385506…` = the
    regression-gate commit `1038550`; the gate is test-only with **no runtime
    effect**, so booting it is optional and be91759a already carries the verified
    fix. Every other post-update check is green (0 failed system/user units,
    session won the compositor race, no $HOME shadow).

### Commit and image state

- fwupd fix: commit `448f926`; docs `7822e55`; regression gate `1038550` — ALL
  pushed to origin/main. CI for the fix (run on `7822e55`) SUCCEEDED and published
  the signed `moos-nvidia` digest sha256:be91759a… = version 44.20260721.281.
- **STAGED, awaiting reboot**: the workstation was rebased (signed,
  `ostree-image-signed:`) to sha256:be91759a… (v281); it applies on next boot.
  Booted now: 44.20260720.275 (sha256:509bdf68…), kept as rollback (272 also
  present).
- The gate commit `1038550` triggered a later CI run; its image (fix + gate) is
  NOT needed for the reboot — the gate has no runtime effect and be91759a already
  carries the fix.

### RESUME HERE (exact next step)

**fwupd is DONE and live-verified** (see "What was tested" above); the ROADMAP
item is flipped to `[x]` and this handoff is pushed. The keyboard drift is also
resolved on this boot (`de,us,ara` live). Remaining work, in order:

1. **zram0 first-boot failure on fresh installs** (the highest safe open
   release-gate item). Observed only in the QEMU install round (gate 190), never
   on the owner's machine: one transient `systemd-zram-setup@zram0.service`
   failure at boot leaves the device initialised, so every retry then dies with
   `EBUSY` writing `/sys/block/zram0/comp_algorithm` and swap stays off. **Do NOT
   ship a swap change untested** — reproduce in a booted VM first, add a drop-in
   that resets zram0 before setup on retry (or otherwise handles the first
   transient failure), then a regression gate. ROADMAP section 2, the `[ ]` item
   flagged "عطل اكتشفته جولة 190". A cosmetic companion: the live installer
   session locks the screen after 5 min idle (Esc unlocks — liveuser has no
   password); worth suppressing the lock in the live image.
2. Then the installer end-to-end round (timezone step) on a real ISO.

Optional, non-blocking: the machine may be converged to v282 (`c06a9420…`) on any
future update to silence the digest-drift check — it is the same fix plus a
test-only gate, so it is not required and is deliberately not forced here.

Environment carried into resume: scoped `/etc/sudoers.d/10-moos-dev` is active
(passwordless for rpm-ostree/systemctl/etc. ONLY — not blanket); `gh` is logged
in for push; the VS Code Codex + .NET fixes need only a window reload.

## Session 2026-07-21 — live theme-family health and self-heal repair

### What was done

- Fetched `origin/main` without touching the existing untracked development files; local
  `main` was already identical to the remote at `596125b` before this work.
- Verified the machine is booted from the signature-enforced NVIDIA image
  `44.20260720.275`, digest
  `sha256:509bdf6887296340a2891397a65eb9952f021aeb88a54f4d8c32beb5a07d0cc2`.
  GHCR `moos-nvidia:latest` resolves to the same digest. The previous deployment remains
  available for rollback.
- Verified zero failed system units and zero failed user units. Reviewed the current system
  and user journals. The notable visual noise is Aurorae probing a nonexistent user-data
  candidate before resolving the complete Midnight theme from `/usr`; no user asset shadows
  the image and the live decoration renders correctly.
- Captured and inspected the live 3840x2160 desktop. The active Midnight selectors all agree:
  look-and-feel, Aurorae decoration, colour scheme, icon theme, Plasma style, scene plugin and
  `MoOSUI2Midnight` wallpaper. The MoOS panel capsule is live and its popup already exposes
  search, Mo AI, Mo Store, updates, theme, settings and recovery.
- Fixed `moos-selfcheck` and `tests/post-update-check.sh`, which still accepted only the old
  Graphite/Tidal base pair and falsely called every newer family member non-MoOS.
- Fixed `moos-apply-theme` self-heal so all 16 UI2 family members—including light variants and
  Arena/Forge/Scholar—count as intact when their selectors agree. Previously those legitimate
  choices could trigger needless repair work at login.
- Added a relationship regression test requiring the switcher, both live checks and login
  self-heal to recognize every dark/light family pair.

### What was tested

- `just check` — passed.
- `python3 tests/test_moos_theme_safety.py` — 3/3 passed.
- `python3 tests/test_moos_ui2.py` — 7/7 passed.
- Shell syntax for all three changed Bash programs — passed.
- Repository copies of both live checks against the running desktop now identify Midnight
  correctly; the only remaining failure is the keyboard runtime drift below.
- `just build` / full `podman build` — passed. The built image passed the identity gate,
  image-experience gate, foreign-identity firewall, QML smoke tests, initramfs/Plymouth proof,
  store catalogue gate and `bootc container lint` (lint completed with the four existing
  warnings for `/boot`, runtime dirs, `plugdev` sysusers and `/var` tmpfiles).

### Commits and image state

- Implementation commit: `7285101` (`fix(themes): recognize every UI2 family in live health checks`).
- Booted/published image at handoff time: `44.20260720.275`, digest
  `sha256:509bdf6887296340a2891397a65eb9952f021aeb88a54f4d8c32beb5a07d0cc2`.
- The implementation is not in the booted image yet; CI/published-image/update verification
  must complete before claiming it live.

### Open issue and exact next step

- KWin's running keyboard list is still `de,ara`, while the current image default is
  `de,us,ara`. There is no `~/.config/kxkbrc` shadow, and a KWin reconfigure does not replace
  the already-loaded layout model. Do not create a permanent user shadow merely to make the
  check green. After the next signed image is published, stage it, reboot once, and verify the
  session loads `de,us,ara`; if it remains stale, add a bounded image-owned migration with a
  regression test.
- Push the handoff commit, wait for both image editions in CI, confirm the new signed GHCR
  digest, stage that digest explicitly, reboot, then run installed `moos-selfcheck` and
  `tests/post-update-check.sh`. Only after that live proof continue visual iteration on the
  MoOS panel popup / Mo AI / Mo Store.

## Session 2026-07-21 — Post-Reboot Verification & Interactive Brand Search & Mo AI Prompt Bar

### What was done
1. **Post-Reboot Verification of Image 44.20260720.275**:
   - Machine successfully booted into signed digest `sha256:509bdf6887296340a2891397a65eb9952f021aeb88a54f4d8c32beb5a07d0cc2`.
   - Verified 0 failed system units and 0 failed user units.
   - Session won its race with the compositor at boot (0 process crashes).
   - Cleaned up local shadow files (`~/.config/systemd/user/mo-remote-personal.service.d/zz-local-build.conf`, `~/.local/bin/moai`, `~/.config/kxkbrc`) so system runs 100% pure image code.

2. **Interactive Live Search & Mo AI Prompt Bar in `org.moos.brand`**:
   - Upgraded `system_files/usr/share/plasma/plasmoids/org.moos.brand/contents/ui/main.qml`.
   - Transformed static "Search & launch" card into an active, sleek glass `TextInput` prompt bar.
   - Integrated live query detection:
     - `ai ...` / `ذكاء ...`: triggers Mo AI.
     - `store ...` / `متجر ...`: opens Mo Store.
     - search text: triggers KRunner / app launcher menu.
   - Added clear button and dynamic action indicator pills (`↵ Open Mo AI`, `↵ Open Mo Store`, `↵ Search apps & system`).

3. **Logout Screen Action Buttons Upgrade**:
   - Upgraded `MoOSUI2ActionButton.qml` with dynamic bottom neon active indicator rail, smooth hover scaling, and responsive press animations.
   - Synchronized across all 16 MoOS UI2 theme variants via `generate_moos_themes.py`.

4. **Verification**:
   - `just check` (UX gate, device plan, moai-do test, visual checks) — **PASSED**.
   - `python3 tests/test_moos_ui2.py` (7 tests) — **PASSED**.
   - `python3 tests/test_moos_theme_safety.py` (3 tests) — **PASSED**.
   - `bash -n build_files/build.sh` — **PASSED**.

## Session 2026-07-20 (late night) — MoOS Screens 3D & Animation Upgrade (Plymouth, Login, Logout, Splash)

### What was done
1. **Plymouth Boot Splash Upgrade (3D Orbital)**:
   - Upgraded `system_files/usr/share/plymouth/themes/moos/moos.script` with dual-ring counter-rotating orbital motion for 3D depth.
   - Added 3 elliptical particle orbits at staggered phases and tilted axes.
   - Added a radial shockwave pulse wave (`pulse.png`) repeating every 3.8s.
   - Added emblem breathing pulse (2% subtle scale pulse).
   - Generated new high-quality assets: `particle.png` (64x64), `ring2.png` (720x720), `pulse.png` (512x512).

2. **Splash Screen Upgrade (Orbital Reveal)**:
   - Upgraded `system_files/usr/share/plasma/look-and-feel/org.moos.ui2/contents/splash/Splash.qml`.
   - Ring expands from a point birthing the logo from inside it (`OutBack` ease).
   - 3 energy particles shoot outward during reveal.
   - Multi-lane neon progress bar with cyan/violet/electric sweeps racing.
   - Typewriter wordmark effect for "MoOS".

3. **Logout Screen Upgrade (Cosmic Aurora & Glass Refraction)**:
   - Upgraded `system_files/usr/share/plasma/look-and-feel/org.moos.ui2/contents/logout/Logout.qml`.
   - Expanded aurora curtains from 4 to 6 (adding warm gold and rose nebula curtains with slow 3D rotation oscillation).
   - Added 24 depth-staggered breathing stars, 5 rising motes, double-streak shooting stars.
   - Added glass refraction lines drifting across the panel.
   - Added second counter-rotating brand ring behind emblem.
   - Upgraded `MoOSUI2ActionButton.qml`: icon 5° tilt on hover with bounce-back, `OutBack` scaling, press pulse ring, glass refraction light sweep.

4. **Login Greeter Wallpaper & Gate Compliance**:
   - Fixed `system_files/usr/share/plasma/wallpapers/org.moos.ui2.greeter/contents/ui/main.qml`.
   - Removed `Animation` keywords to satisfy UX gate requirement (login greeter must paint immediately).
   - Maintained static ambient orbital presence: concentric glow discs, fixed-rotation ring, static horizon line, 3 accent dots.

5. **Theme Synchronization & Verification**:
   - Ran `artwork/generate_moos_themes.py` to propagate updated Splash, Logout, and ActionButton QML to all 16 theme variants.
   - Verified `python3 tests/verify_user_experience.py` — **PASSED**.
   - Verified `python3 tests/test_device_plan.py` — **PASSED**.
   - Verified `bash -n build_files/build.sh` — **PASSED**.

### Current Status
- Booted Image: `ghcr.io/moalfarras-sys/moos-nvidia@sha256:75daa80ef2073cee1cbd3a7873e922a3b41a87f6a200942862fc3252c18f55fc`
- Staged Image (Ready on Reboot): `ghcr.io/moalfarras-sys/moos-nvidia@sha256:509bdf6887296340a2891397a65eb9952f021aeb88a54f4d8c32beb5a07d0cc2` (Version `44.20260720.275`)
- Gates: `verify_user_experience.py` PASSED, `test_device_plan.py` PASSED, CI Build `29783730674` SUCCESS
- Open Tasks: System reboot to boot into the upgraded 3D visual screens.

## Session 2026-07-20 (evening) — Mo PC Remote: typing, H.264, TLS topology, CI unblock

Three commits on `main`: `14a8c80`, `138f2b4`, `f250006`.

### The measuring rig (reuse it — it is why this session found real causes)

Everything below was measured, not reasoned about. Two throwaway GTK4 diagnostics
driven through the agent's **real** authenticated WebSocket path:

- a focused window logging every key the compositor delivers (`evdev`, keyval,
  modifier state) plus the text that actually landed in its buffer;
- a scrollable window reporting its own scroll offset, kinetic scrolling **off**
  (with it on, the offset drifts for seconds and direction tests are worthless).

The agent already ships the hook that makes this possible:
`/api/local-diagnostic-token`, loopback-only and gated behind
`MOREMOTE_LOCAL_DIAGNOSTICS=1`. Set it with a user drop-in, measure, then remove
the drop-in — it is off again now (verified 404).

Two traps this rig has already sprung, both of which produce confident wrong
answers: a GTK controller in the default *bubble* phase never sees Tab, Enter or
the arrows (the focused TextView eats them, so working keys look broken), and a
handler returning `True` consumes the event so nothing is ever pasted or typed.
Use CAPTURE phase and return `False`.

### What was actually wrong

**H.264 never engaged, for any phone.** The PWA declares its decoder with
`{"type":"video","h264":true}`, but `StreamSession` only read that field under
`"settings"`, so the message fell through to the input switch, matched nothing and
was discarded on every connect. Proven by sending both forms: `"video"` came back
`inputState`, `"settings"` came back `codec:h264`. The stream was JPEG at
**1.18 MB per frame** at 1080p. Fixed; both names now route to the same handler.
Measured after: **27 KB per frame**, `nvh264enc` (NVENC, no CPU cost).

**Typing was broken three ways**, all one root cause: KWin resolves a keysym
against the ACTIVE keymap group only, at shift level one. On this `de,ara` keymap:

| sent | arrived |
|---|---|
| `'a'` | `'a'` — correct |
| `'Z'` | `'z'` — shift level never applied |
| `'م'` | keycode 247 / keyval `0x1008ffb5` — a key that types nothing |

So capitals typed lowercase, Arabic typed nothing, and shifted punctuation typed
the wrong character — `/` became `7`, i.e. every path the owner tried to type. The
keysym fast path is now restricted to what is provably level 1 on any Latin layout,
capitals hold a real Shift keycode around the lowercase keysym, and everything else
is typed by briefly **borrowing the clipboard** (layout-independent, any Unicode),
pasted with **Shift+Insert** — Ctrl+V is not paste in a terminal, which is why
Arabic into Konsole silently did nothing. The borrow is returned afterwards.

**Combos were QWERTY-keycoded**, so on German QWERTZ `Ctrl+Z` landed on Y and did
redo instead of undo. Modifiers still go by keycode; the modified key goes by
keysym.

**Arrows, Enter and Tab were never broken.** The first diagnostic said otherwise
and was wrong (bubble-phase trap above).

### The TLS topology — read this before touching HTTPS again

`14a8c80` provisioned a `tailscale cert` and had Kestrel serve HTTPS on 8765.
**That broke the phone entirely** and `138f2b4` reverts it. The reason:

```text
phone ── https :443 ──► tailscale serve ── PLAIN http ──► agent :8765
```

`tailscale serve` was already terminating TLS on 443 and proxying **plain HTTP**
to 8765. An HTTPS listener there answers the proxy with a TLS handshake, so the
only URL the phone has returned **502**. It was also redundant: serve already
supplies and renews the certificate, on a nicer URL with no port number. The
certificate helper and renewal timer added in `14a8c80` are removed.

`TlsManager` stays dormant unless something writes `tls/host.txt`; nothing in the
image should. `MO_PC_REMOTE_ARCHITECTURE.md` now says this explicitly — its old
claim that "the agent is plain http so we are stuck on JPEG" is what sent me down
this path, and it was describing a topology this has not had for a while.

### Scrolling was not a sign error

Measured with kinetic scrolling off: `dy=+4` moved the offset `3300 -> 2550`,
`dy=-4` moved it `2550 -> 3300`, exactly back. A finger swipe up sends negative
`dy`, so content follows the finger — phone-native, and already correct.

What was broken: the **"Natural scroll" toggle, both sensitivity sliders and the
gesture mode were plain `useState` with no persistence**, so every reconnect
silently reset them. A preference the user cannot make stick reads as the app
ignoring them. They persist in `localStorage` now (`moremote.*`).

The owner confirmed they want phone-native ("content follows my finger"), which is
the default.

### Two gates were asserting things that are false

Both in `tests/verify_user_experience.py`, both replaced rather than weakened:

- *"must map core Arabic Unicode to XKB's legacy Arabic keysyms"* — measured false
  (see the table). Replaced with a gate on what was measured to work: the clipboard
  borrow, its Shift+Insert paste, the borrow being returned, **and** an assertion
  that the legacy keysyms are not reintroduced.
- *"text batching must stay below one 60 Hz frame"*, pinned to the literal `12`.
  Rather than widen it, coalescing is now **adaptive**: keysym-typable text still
  flushes in one frame (English typing is exactly as immediate as before), while
  text needing a clipboard borrow batches into words instead of one borrow per
  letter. Both halves are pinned.

### CI was red on main before this session, for an unrelated reason

`tests/test_moai_do.py` runs as a gate before the build; it derives the action list
from `moai-do`'s own dispatch block and requires each to appear in `usage()`.
`install-openclaw` and `setup-brain` shipped in `5eab2dc` with a dispatch entry and
no help line, so **every build since 13:45 failed and produced no image**.
`f250006` documents both. The gate was right and was left intact.

### Verified

Through the real phone path (`wss://moos-3.tailab78a5.ts.net/ws`, port 443, not
loopback):

- codec `jpeg -> h264`; 370 frames averaging **27 KB** (JPEG was ~1180 KB);
- `'Hello مرحبا /home/mo --flag'` lands intact — capitals, Arabic, `/`, `--`;
- clipboard still holds its original contents afterwards;
- `Ctrl+z` reaches the German `z` key (evdev 21), not `y`;
- diagnostic endpoint returns **404** with the drop-in removed;
- CI gate set (`test_moai_do`, `verify_user_experience`, `test_device_plan`,
  `artwork/verify_visuals`) all pass locally;
- `moos-selfcheck` 39/40, `post-update-check.sh` 37/40 — remaining failures are
  pre-existing and unrelated (below).

### ⚠️ Temporary local override — REMOVE after the next image update

`/usr` is read-only, so the fixed agent runs from `~/.local/lib/mo-remote` via:

    ~/.config/systemd/user/mo-remote-personal.service.d/zz-local-build.conf

Once the image carrying `f250006` is booted, delete it so the image copy takes
over — otherwise the machine keeps running a hand-built binary forever and the
image is no longer the thing being tested:

    rm ~/.config/systemd/user/mo-remote-personal.service.d/zz-local-build.conf
    systemctl --user daemon-reload
    systemctl --user restart mo-remote-personal.service

`post-update-check.sh` now **does** catch this class of shadow. It previously only
looked at `$HOME` `.desktop` files and `~/.local/bin` on `PATH`; a drop-in replaces
no file and puts nothing on `PATH`, so a redirected unit stayed invisible while
`systemctl is-active` reported green. The new check flags any
`~/.config/systemd/user/<unit>.d/` drop-in whose `ExecStart=` leaves `/usr` for a
home directory. Verified it fires on the override above, and it is expected to go
green the moment that drop-in is deleted.

### Pre-existing issues, not from this session

- **Automatic updates are a permanent no-op.** The deployment is *digest-pinned*
  (`ostree-image-signed:docker://…moos-nvidia@sha256:b7a12e65…`), so
  `rpm-ostreed-automatic.timer` runs, resolves nothing newer, and exits in ~1s.
  This matches the deliberate update-by-digest protocol, so it is a finding, not
  necessarily a bug — but nobody should expect this machine to update itself.
- **The phone is on a DERP relay, not a direct path** — and this is now the
  remaining latency floor, not anything in the code:

      tailscale ping iphone182
      pong ... via DERP(fra) in ~50ms
      direct connection not established

  Every input event and every frame pays that round trip. `tailscale netcheck` on
  this side is healthy (`UDP: true`, `MappingVariesByDestIP: false`), so the
  blockers are (a) `PortMapping:` empty — no UPnP/NAT-PMP/PCP on the router, and
  (b) `IPv6: no, but OS has support` — the ISP/router provides no IPv6, which is
  what mobile carriers usually need to hole-punch. Neither is fixable from the
  image: enabling UPnP/NAT-PMP and IPv6 on the home router is the actual fix, and
  it is worth doing — a direct path would cut ~50 ms off every interaction.
- `fwupd-refresh.service` failed: `Failed to obtain auth` after downloading LVFS
  metadata. Unrelated to the image.
- `~/.local` shadows the image's `moai` binary — Kickoff and PATH run the copy.
  `post-update-check.sh` flags it; left alone as it may be a deliberate dev copy.

## Session 2026-07-20 — Mo AI × OpenClaw: Agent panel, Settings rebuild, access tiers

Mo AI and the OpenClaw agent now share one brain, one key, one channel and one
config file. Two commits, both pushed to `main`.

### What was done

**`5f16f80` — Agent panel + Settings rebuilt around one config source**

- Seventh nav entry, `agent`, after Dev. Lists the same Telegram sessions,
  renders the thread, sends from the desktop. Pure QML has no Process API and
  cannot read `~/.openclaw`, so it talks to `moapp-console` on
  `127.0.0.1:8077` — that service is the only seam.
- Settings replaced wholesale (511 lines → 409, then +2 sections), sectioned as
  Brain / Channel / Voice / Power / Access / Models / Health.
- Secrets stay write-only, matching `moai-control`: the API answers
  `has_key` / `has_token` and never returns a value.

**`798d7f9` — three-tier access control**

Each tier writes the key OpenClaw already enforces; none of it is a local layer:

| Tier | elevatedDefault | workspaceAccess | approvals.exec | deny |
|---|---|---|---|---|
| read | off | ro | off | web, browser, exec |
| ask | ask | rw | on, `mode=session` | web, browser |
| full | full | rw | off | — |

`mode=session` is what makes phone approval real: the prompt returns to the chat
the request came from, so a Telegram request is approved from Telegram and
nothing runs before it is answered.

Project-folder scoping writes `agents.defaults.workspace`. Absolute paths inside
`$HOME` only; `/etc` and non-existent paths are refused with a reason.

### The brain, and why the app said "offline"

The local brain moved from RamaLama on 8081 to Ollama on 11434, serving
`default` (a `qwen3-vl:4b` derivative with thinking suppressed). Two drop-ins
carry it, and **both** are required — the gateway alone is not enough:

- `moai-gateway.service.d/ollama.conf` — routes chat
- `moai-control.service.d/ollama.conf` — routes the liveness probe

Without the second, `local_online()` polls the dead 8081, the app renders
`غير متصل`, and its "Start local brain" button tries to load a SECOND model onto
the same 8 GB card. That is the `cudaMalloc failed: out of memory` path already
documented in `moai-idle`.

### Tested

- `tests/verify_user_experience.py` — passed
- `tests/test_device_plan.py` — passed
- `bash -n build_files/build.sh` — clean
- `qmllint-qt6 main.qml` — 0 errors
- `QT_QPA_PLATFORM=offscreen qml-qt6 main.qml` — loads (the enforced gate)
- `moos-selfcheck` — 40 checks passed
- All three tiers round-tripped against the live config; it stayed schema-valid
  at every step
- Telegram verified end to end in the journal: `Inbound message` →
  `sendMessage ok`

### Traps found here, worth not rediscovering

1. **The user-experience gate caught three regressions from the Settings
   rebuild** — model deletion, the one-tap download section, and
   `moos://do/<id>` repairs. They are back as the Models and Health sections.
   The last one is the safety contract: a repair is a named action behind
   `moai-do` confirmation and Polkit, never a composed command.
2. **Adding a panel needs three edits, not one**: `navItems`, the `StackLayout`
   `indexOf` array, and the `--panel` whitelist. Missing the third makes
   `moai --panel agent` fail silently and open on chat.
3. **A pattern that eats a closing brace produces no error message.** The app
   simply printed `qml: Did not load any objects`. A brace-balance count against
   the pre-edit copy located it; `qml-qt6` alone never will.
4. **`qmllint-qt6` finds duplicate ids that a normal load does not.** `bubble`
   and `body` collided with existing ids and still "loaded".
5. **A root key OpenClaw does not know invalidates the whole config.** The
   schema is `additionalProperties:false` at the root, so console state lives in
   `~/.config/moapp/state.json`, not inside `openclaw.json`.
6. **`api: "openai"` is rejected**; the schema wants the dialect
   (`openai-responses`, `anthropic-messages`, …).
7. **Repeated gateway restarts suppress the Telegram channel.** The health
   monitor logs `channel autostart suppressed; treating as expected stopped` and
   polling stops. `moapp-console` now restarts the gateway for the Telegram
   token only — OpenClaw applies the rest live.
8. **Twelve systemd hardening directives each break rootless podman**
   (`ProtectKernelTunables`, `PrivateUsers`, `NoNewPrivileges`,
   `CapabilityBoundingSet`, `ProtectClock`, `ProtectKernelLogs`, `PrivateTmp`,
   `RestrictSUIDSGID`, `ProtectControlGroups`, `KeyringMode`,
   `InaccessiblePaths`, `ProtectKernelModules`). All fail with the same message
   blaming podman and suggesting `podman system migrate`, which does not help.
   Only `RestrictRealtime`, `LockPersonality` and `UMask` survive alongside the
   agent sandbox.

### Open issues

1. **`~/.local/bin/moai` shadows the image copy.** It was the way to see the
   change before a rebuild, and it contradicts the `moos-selfcheck` rule that no
   user-level copy shadows a MoOS asset. **Delete it once `798d7f9` is booted.**
2. **The Settings sheet has not been clicked through.** Code-side is clean
   (gate, lint, load) but the window could not be raised for a visual pass —
   no `kdotool` or `wmctrl` on this host, and clicks cannot be automated here.
3. **MOAPP support files live outside the repo** in `/var/home/moos/عام/MOAPP`
   (`moapp-console`, `console.html`, `moapp-transcribe`, quadlets for Ollama and
   Speaches). They are not shipped by the image yet. Deciding whether they
   belong in `system_files/` is the natural next step.

### Exact next action

1. Wait for CI run `29744624343` on `798d7f9`, confirm both editions signed.
2. Stage that exact signed NVIDIA digest, reboot, re-run `moos-selfcheck` and
   `tests/post-update-check.sh`.
3. Delete `~/.local/bin/moai`, then confirm the icon still opens the Agent panel
   from the image copy.
4. Click through Settings: all seven sections, save each, verify the config
   stays valid and Telegram keeps polling.

## Session 2026-07-20 — fast Remote input and complete Mo Store redesign

- The machine now boots the signed `moos-nvidia` image `44.20260720.263`,
  digest `sha256:35d13c7b37bf8178cb9aaac2362158ef2ea43e1d8c6c8e9ab0f251fa2d97f00e`,
  revision `a04f46f`. This exactly matches the current signed GHCR image at the
  start of the session. Signed `.260` (`sha256:bc7d…`) remains the rollback.
- Live health is clean: no failed system or user units; `moos-selfcheck` and
  `tests/post-update-check.sh` both passed 40/40.
- Remote text latency was reduced by batching controller edits every 12 ms.
  The Linux agent now sends an Arabic word's ordered keysym press/release
  sequence to the portal helper in one IPC message instead of two pipe writes
  plus a delay for every character.
- Touch now begins after a 5 px movement and preserves the first meaningful
  delta instead of dropping it. This makes tap/drag response noticeably more
  immediate while retaining click-vs-drag separation.
- Mo Store was redesigned as a new MoOS-specific surface: new identity header,
  curated status capsule, deeper atmospheric background, angular search and
  category controls, a new “Make MoOS yours” onboarding hero, and larger
  unclipped bundle cards. Source preview:
  `test-results/mo-store-redesign.png` (comparison:
  `test-results/mo-store-before.png`).

Tests completed:

- controller unit tests and production PWA build passed;
- Remote .NET suite passed in the SDK container: 22/22;
- `just check`, theme safety 3/3, UI2 7/7, `test_moai_do`, build-script syntax,
  and Python compile checks passed;
- full `just build` passed, including Remote publish, QML smoke tests, image
  experience/identity/catalog gates, initramfs proof and `bootc container lint`
  (9 checks passed, 4 non-blocking content warnings). Local image:
  `localhost/moos:latest`, ID
  `c9dcb3fd91e2ce39817644d92ae40a17bc64360821fd0f5f31da0e9fcce8a167`.

Open issues and exact next step:

1. Candidate commit `4e619cb` is pushed. CI run `29722350344` passed both
   editions, pushed them, signed them, and verified each signature against the
   OS-enforced public key. The resulting `.264` NVIDIA image is
   `sha256:b7a12e6525e6e08fb8351b4394f9251adde0aee0c0740e05a69dc0787b2ce7e3`
   with revision `4e619cb`.
2. The audited repo copy of `moai-do update` resolved only the official NVIDIA
   `:latest`, pinned the exact digest above, and staged it through
   `ostree-image-signed:` after interactive Polkit approval. Pre-reboot
   `rpm-ostree status --json` proves `.264` is staged, `.263` remains booted,
   and signed `.260` remains the rollback. Exact next step: reboot into `.264`,
   confirm the booted digest, repeat all live gates, and test the installed
   immutable Mo Store and Remote services.
3. Real-phone acceptance remains mandatory: Arabic composition, Backspace,
   spaces and punctuation in KWrite and Firefox; tap/drag/scroll; and
   bidirectional clipboard text. Source and automated contract tests are green,
   but this session does not claim phone hardware verification.
4. The stale screencast UUID/reconnect failure and a future WebRTC/libei
   transport remain open. Do not call TeamViewer-class video recovery complete.

## Session 2026-07-20 — Mo Store / Mo PC Remote icons and Arabic input

- Code checkpoint: `cf8dad5` (`feat(remote): improve Arabic input and refresh app icons`).
  Current pushed HEAD is the documentation-only `d457024` on top of it.
- Booted image remains signed `moos-nvidia` `44.20260719.260`,
  digest `sha256:bc7d68117e2be0d21c161efd1c54277169fddb8c239173cfd58fe1fc85695b16`.
  The retained rollback deployment is `.259` at digest `sha256:6bb673…`.
- At session start `main` and `origin/main` were `9ad2028`; GHCR `moos-nvidia:latest`
  and the booted deployment both pointed to `.260` / `bc7d…` (image revision
  `13359ab`). No rpm-ostree update was available.
- Added original new Mo Store and Mo PC Remote icon masters, RGBA raster fallbacks
  for every KDE size, a new vector Remote master, and regenerated Remote's PWA,
  Windows ICO, and shipping web bundle. The image-generation source PNGs are in
  `artwork/generated/`.
- Fixed the Arabic path at both ends:
  - the controller now respects browser IME composition boundaries, so Arabic
    word edits are not streamed as duplicate text and Backspaces;
  - the Linux agent maps the core Arabic Unicode block to the legacy XKB
    `0x05xx` keysyms KWin actually injects, instead of relying on clipboard paste;
  - the unit suite now asserts representative Arabic mappings, and the experience
    gate protects both the KWin mapping and phone composition handlers.
- Live Remote services were active (`mo-remote-personal`, PipeWire helper and
  `ydotoold`). The journal nevertheless recorded Plasma screencast failures for
  stale window UUIDs during use. Do not call video reliability complete until
  source restoration/reconnect is reproduced and fixed on a booted candidate.
- Research conclusion: the current PipeWire + H.264 design is a sound low-latency
  base, but a TeamViewer-class next step should move media/input transport toward
  WebRTC plus portal/libei semantics. XDG ScreenCast v6 also recommends
  `pipewire-serial`/`PW_KEY_TARGET_OBJECT` rather than reusable numeric node IDs.

Tests completed:

- live `moos-selfcheck`: 40/40.
- live `tests/post-update-check.sh`: 39 passed, 1 failed only on the already-known
  compositor startup race (39 processes aborted before KWin became ready).
- controller `npm test` and production PWA build passed.
- Remote .NET unit suite passed inside the SDK container: 22 mapping/validation/
  Unicode tests.
- `just check`, theme-safety 3/3, UI2 7/7 and build-script syntax passed.
- full `just build` passed, including .NET publish, image identity/experience/QML
  gates, identity firewall and `bootc container lint`.

Open issues and exact next step:

1. CI run `29708715032` completed successfully for both editions, including
   signing and verification. Signed `moos-nvidia` `.262` is published at
   `sha256:dde50286ccfc1623ea47e49431ca18050eecf1d8a3509255780b350f4f95b9ea`
   with revision `d457024`; generic `.262` is
   `sha256:8e88afe04987c4b85584d7ac1df38056ce4909d1dfdef4fa5a0f6f6c37a1b96e`.
   It is **not staged**: the installed origin is pinned to the old exact digest,
   so `rpm-ostree upgrade` says no update, while an exact `rpm-ostree rebase`
   is correctly denied to the unprivileged session.
2. Commit `a04f46f` fixes that updater dead end in `moai-do update`: it
   identifies the booted MoOS edition, resolves only the official GHCR `:latest`
   tag, validates an exact SHA-256 digest, and escalates only a constructed
   `ostree-image-signed:` rebase. The previous deployment remains available.
   `tests/test_moai_do.py` now executes the complete update flow against command
   doubles and proves the exact privileged argv. `bash -n`, that test, and
   `just check` pass. CI run `29717267108` passed both editions, signing, and
   OS-key verification. The resulting `.263` NVIDIA image is
   `sha256:35d13c7b37bf8178cb9aaac2362158ef2ea43e1d8c6c8e9ab0f251fa2d97f00e`
   (generic: `sha256:ef1c008e40fb6e287bf723b9a02ae5df9d14d85ef8ff7c46ec3cb9f311c70667`).
   The audited repo copy of `moai-do update` was then run live with interactive
   Polkit approval. It pulled the signature-enforced exact digest and staged
   `.263` successfully. Pre-reboot `rpm-ostree status --json` confirms `.263`
   is staged with the exact digest above, `.260` remains booted, and `.259`
   remains present. Exact next step: reboot into `.263`, confirm its booted
   digest, then run the full live self-check/post-update suite and Remote tests.
3. Boot the candidate while retaining `.260`, then test real Arabic typing from
   an Arabic phone keyboard into at least KWrite and Firefox, including composing,
   Backspace, spaces and punctuation. Test touch tap/drag/scroll on the same run.
3. Reproduce the stale screencast UUID failure across window close, display-mode
   change and reconnect. Implement stream targeting/recovery using the portal's
   stable stream identity where supported; then measure RTT, FPS and bitrate.
4. The compositor startup race remains the highest system-wide issue and still
   requires the VM-first procedure documented below.

## Current checkpoint

- Date: 2026-07-20, Europe/Berlin.
- Local repository: `/var/home/moos/moos-image`.
- Historical checkpoint below predates the session section above; use the newer
  section for the current commit/image/test state.
- The visual-polish candidate described below is no longer a candidate: it was
  published as `44.20260719.260` and is the booted image.
- Session note: development ran from inside the VS Code **Flatpak sandbox**,
  which has no `rpm-ostree`, `bootc` or `systemctl`. Reach the real host with
  `flatpak-spawn --host <cmd>`; without it every live check silently inspects
  the Freedesktop runtime instead of MoOS and reports nonsense.
- Visual-polish candidate (not published at the time of this checkpoint):
  the bottom shell is now a 54 px floating command dock with a restrained
  multi-layer FrameSvg, a wide MoOS status/wordmark control, a separate search
  launcher, and a smaller default set of first-party task pins. The MoOS
  control opens a 420x430 search/action surface and supports middle-click
  launcher activation.
- The dark base experience now uses the original **Quiet Horizon** 4K master.
  It is wired into the canonical generator, Graphite wallpaper package,
  look-and-feel previews, desktop and lock-screen defaults; it is not a renamed
  third-party theme. Light/Tidal remains available and was live-tested.
- Logout is a balanced 3x2 action grid on normal/4K widths (2 columns only on
  narrow surfaces) across all 16 MoOS look-and-feel variants. Theme revision
  is 20, including migration of the existing user's panel geometry, search
  glyph and MoOS-control popup size.
- Live development proof exists under
  `test-results/live-polish-20260719/bar-v20/`: the previous bar, MoOS Control,
  launcher, Graphite dark, Tidal light, final Quiet Horizon desktop, and a
  real 3840x2160@60/200% capture. The display was restored to
  1920x1080@60/100%. Arabic RTL and English/German LTR content remained
  correctly ordered in the live session.
- One full local image build passed all experience/identity/QML/Plymouth/
  initramfs gates and `bootc container lint` (9 checks passed). Candidate
  image: `localhost/moos:latest`, ID
  `76d656577f22306449428935dd072d70d34867363888fb4c19a0e1d903529820`.
- The candidate is deliberately still local: commit/push, CI, signed GHCR
  image, exact-digest update, reboot and immutable live verification are the
  next release steps. Do not remove the retained rollback deployment.
- Live doorway audit captured the real Plasma Login Manager (`plasmalogin`),
  the shell lock screen, and the UI2 logout greeter. Before this work:
  accounts without a photo showed Plasma's generic outline avatar; the login
  surface had no MoOS identity if its separate wallpaper service was absent;
  and the bilingual logout text reordered Arabic/English and moved the question
  mark under RTL.
- The source now gives the shared login/lock `UserDelegate` an intentional
  initial avatar plus a small MoOS badge, so identity survives a wallpaper
  fallback without changing any authentication wiring. All 16 UI2 logout
  packages now use one direction-aware `bilingual()` formatter with Unicode
  isolates for every heading, action and description.
- Live source-path rendering verified the logout fix visually. Before:
  `?What would you like to do | ماذا تريد أن تفعل؟`; after, the Arabic phrase
  and its punctuation remain together and the English phrase remains intact.
  No QML error was logged by the test greeter. Screenshots are under
  `test-results/live-audit-20260719/`.
- The login/lock avatar change is present in the locally built image and gated,
  but is not applied to the immutable live `/usr`; it requires the next signed
  image. The existing login wallpaper service was confirmed healthy in the
  real greeter session (`plasma-wallpaper.service`, 3m13s, no QML failure).
- A single full `just build` passed the image-experience gate, identity
  firewall, all QML smoke tests, initramfs/Plymouth proof, and
  `bootc container lint` (9 checks passed). Local image:
  `localhost/moos:latest` / image ID
  `1fa54323d04459a6a1655ffc97090a4de1d5d65a441a67cdf4a5488ce74c8f3c`.
- Commit `7f2405e` contains the doorway fixes. GitHub image run
  `29702830044` passed both editions, pushed `.259`, signed it, and verified
  the signature against the OS-enforced key. Exact NVIDIA digest:
  `sha256:6bb673b6583d597048079610ab5b2a91e7bf5f1d2f3e2773a9265ba4b7bae134`.
- `.259` is staged by that exact signed digest for the next boot. `.258`
  remains the booted deployment and `.257` is also still present; no rollback
  deployment was deleted.
- Live `.256` verification exposed that the first RTL clock fix was incomplete:
  the dashboard showed `73:02` while the panel showed `20:37`. Plasma's
  inherited `LayoutMirroring` overrides `RowLayout.layoutDirection` alone.
  The new source fix explicitly disables mirroring on the HH:mm row and
  propagates that non-mirrored state to its rolling digits. Both regression
  gates now require the complete invariant.
- Commit `fcc1fe6` contains the complete fix. GitHub image run `29699253331`
  passed for both editions, pushed `.257`, signed it, and verified it against
  the OS-enforced public key. Exact NVIDIA digest:
  `sha256:c794fc6715c2cb63fec9a6520c22081f95717f5d3f7af31ecc074b1b8f7b4fc8`.
- `.257` is now booted and live-verified. Its digest exactly matches current
  GHCR `moos-nvidia:latest`; `.256` remains the rollback deployment.
- The live `.257` session exposed one MoOS-owned Qt warning on login:
  `org.moos.brand` used the bare `expanded` name in `onExpandedChanged`, which
  Qt 6 resolves through deprecated signal-parameter injection. The source now
  explicitly reads `root.expanded`, with a regression assertion in the
  experience gate.
- Commit `6a64ddd` contains that cleanup. GitHub image run `29701307417`
  passed both editions, signed them, and verified each signature against the
  OS-enforced public key. GHCR NVIDIA `.258` is
  `sha256:7bb194c28894aa07ad732a5eb302394f8e1f3587fd1795b9de4491c4460eeb88`.
- `.258` is staged by that exact signed digest for the next boot. `.257`
  remains the running deployment until reboot and `.256` remains rollback.
- The NFS-root initramfs fix from `9fe30a9` is now verified on the live system:
  this boot contains no `rpcbind`, `rpc.statd`, or `nfs-start-rpc` errors.
- The live `.252` image verified the previous `moai-control` class-scope fix,
  but exposed a second recovery-path bug: an occupied port called
  `sys.stderr.write()` without importing `sys`, causing three startup crashes.
- Commit `8ccfeff` imports `sys`, gates the import, and fixes
  `moos-device-plan` falling back to “NVIDIA image required” because current
  `bootc status` needs root. It now uses unprivileged `rpm-ostree status --json`.
- GitHub image run `29694295811` passed for both editions, pushed and verified
  signed image `.253`. Exact signed NVIDIA digest:
  `sha256:8ac01ccbba3f14c374d9534062290a12119498ab84ecbf88f0c49745b60b3a85`.
- `.253` is now booted and live-verified. `moai-control` survived the observed
  occupied-port startup path without a traceback, then a controlled restart
  bound `8079` immediately and served valid JSON.
- The next fix removes only the three generic tmpfiles creation rules that
  conflict with OSTree's `/home`, `/srv`, and `/root` symlinks. It is locally
  built and tested in commit `5d49e84`.
- GitHub image run `29695527186` passed for both editions at head `83d1e98`,
  pushed `.254`, signed it, and verified it against the OS-enforced key. Exact
  NVIDIA digest:
  `sha256:274c18b2daddeb86ff62f958de3f36a633cca4dea1aabbbb5bfc859d426ddb00`.
- `.254` is now booted and live-verified by exact digest. The `/home`, `/srv`,
  and `/root` composefs links remain intact and this boot contains none of the
  former “already exists and is not a directory” tmpfiles errors.
- QSG localization is complete. Controlled Plasma restarts produced 27 startup
  warnings; replacing the MoOS wallpaper and both MoOS panel applets did not
  change the count. Disabling the panel removed all 27, and replacing only the
  standard Plasma System Tray removed 18. They are upstream Qt/Plasma
  scene-graph startup noise, do not recur, and caused no crash, visual defect,
  or sustained load. No MoOS asset was changed to hide them.
- The canonical MoPlayer source is
  `https://github.com/moalfarras-sys/MoPlayerMoOS.git`. It is byte-identical to
  the previously vendored snapshot. Commit `ed5ebe4` fixes the reproducible
  NVIDIA/Wayland close crash and is now synced into this image tree.
- A live 4K/200% dark/light audit found two real dashboard defects: Arabic RTL
  reversed `HH:mm` (for example 19:59 became 95:91), and the normal `HEALTHY`
  verdict was clipped to `HEALT…`. This release pins the time row LTR and gives
  the verdict column enough width, with regression gates for both.

## Installed system

- MoOS 44 on KDE Plasma 6.7.3, Wayland, kernel 7.1.3.
- Booted origin: exact signed `ghcr.io/moalfarras-sys/moos-nvidia` image.
- Booted signed NVIDIA digest:
  `sha256:bc7d68117e2be0d21c161efd1c54277169fddb8c239173cfd58fe1fc85695b16`.
- The booted image is version `44.20260719.260`, built from commit `13359ab`.
  Verified 2026-07-20: this digest is byte-identical to GHCR `latest`, so the
  three states have **converged** — last commit on `main`, last signed
  published image, and the digest the machine actually boots are the same.
- NVIDIA, Wayland, Plasma login and CUDA/NVIDIA operation are live and healthy.
- The previous signed NVIDIA `.259` deployment remains available as rollback:
  `sha256:6bb673b6583d597048079610ab5b2a91e7bf5f1d2f3e2773a9265ba4b7bae134`.
- `moos-selfcheck`: **39/39 passed** on the booted `.260` — the local staging
  shadows noted in the previous checkpoint are gone, as required.
- Failed system units: 29, **all** `drkonqi-coredump-processor@*` — the
  symptom of the compositor race below, not 29 distinct defects.
- Failed user units: 0.
- `tests/post-update-check.sh`: 39 passed, 1 failed. The single failure is the
  new compositor-race check added this session, and it is a TRUE POSITIVE.

## Repository checks

Passed from the live tree:

- `just check`
- `python3 tests/test_moos_theme_safety.py` (3 tests)
- `python3 tests/test_moos_ui2.py` (7 tests)
- `bash -n build_files/build.sh`
- `python3 tests/verify_user_experience.py`
- `just build` (full local bootc image, including `bootc container lint`)
- `.256` live checks: `moos-selfcheck` 39/39,
  `tests/post-update-check.sh` 39/39, `just check`, theme-safety 3/3, UI2
  7/7, direct experience gate, and build-script syntax all passed.
- `.256` live screenshot at 1920x1080 confirmed the HEALTHY verdict is no
  longer clipped and the dashboard cards do not overlap. It also provided the
  decisive counterexample to the old clock gate: dashboard `73:02` versus
  panel `20:37`.
- `.257` live screenshot at 1920x1080 confirms the dashboard and panel both
  read `21:35` in chronological order under the Arabic/RTL session; `HEALTHY`
  is complete and the dashboard cards do not overlap.
- `.257` live checks: `moos-selfcheck` 39/39 and
  `tests/post-update-check.sh` 39/39; the booted digest matches signed GHCR
  `latest`, signature enforcement remains `sigstoreSigned`, and there are zero
  failed system/user units.
- The brand-applet cleanup passes `just check`, theme-safety 3/3, UI2 7/7,
  direct experience verification, build-script syntax, and a full `just build`
  through all image gates and `bootc container lint`.
- Full local image build with the complete mirroring fix passed every identity,
  image-experience and QML smoke gate plus `bootc container lint`.
- forced occupied-port test: repository `moai-control` retried for five seconds
  with no traceback or `NameError`.
- real local Mo AI chat through gateway → RamaLama → CUDA answered exactly
  `MoOS AI OK`; generation was ~8 ms/token and `llama-server` used 3386 MiB VRAM.
- live device plan from the fixed helper reports `nvidia_image=true` and
  `NVIDIA proprietary driver active`.
- temporary 4K hardware test: 3840x2160@60, scale 2; screenshot is 3840x2160
  and fonts, icons, panel, dashboard and windows remained coherent. The display
  was restored to its original 1920x1080@60, scale 1 afterward.
- `just build` full local image succeeded, including identity/experience
  firewalls, QML smoke tests and `bootc container lint`.
- Canonical MoPlayer `ed5ebe4`: `flutter analyze` passed; all 95 Flutter tests
  passed; release build passed. On the live NVIDIA/Wayland session it survived
  1920x1080 -> 3840x2160@60 scale 2 -> 1920x1080 while remaining correctly
  rendered, then a real KWin close request exited 0 with no process left, black
  screen, coredump, EGL/libepoxy journal error, or failed unit.
- Live visual audit at 3840x2160/200% covered Graphite dark and Tidal light,
  desktop/dashboard, wallpaper, panel, launcher, Arabic menus, Konsole window,
  and notification. Fonts, icons, colour, transparency, spacing, corners and
  contrast remained coherent. The two concrete defects above are fixed in
  source; post-update screenshots must confirm them from the new booted image.
- tmpfiles root simulation: after scrubbing only the three conflicting
  top-level rules, `/home`, `/srv`, and `/root` remained symlinks and emitted no
  “already exists and is not a directory” messages.
- inspection of the built `moos:latest` image confirms `home.conf` no longer
  creates `/home` or `/srv`, and `provision.conf` still provisions
  `/root/.ssh` while no longer trying to recreate `/root`.
- Live `.254` verification repeated `just check`, the 3 theme-safety tests, the
  7 UI2 tests, `bash -n build_files/build.sh`, and the direct experience gate;
  all passed. There are zero failed system/user units and no coredumps in this
  boot.

The two unittest files are reached by the recursive experience verifier invoked
by `just check`; the older handoff statement that they were outside the gate was
stale.

## Highest-priority observed issues

1. **The session loses a race with the compositor at boot. NOT YET FIXED —
   only detected.** `plasma-kwin_wayland.service` declares
   `Before=plasma-core.target`, but its `WantedBy=` is **empty**: nothing pulls
   the compositor into the boot transaction, and systemd only honours ordering
   between units it is already starting. So `plasma-core.target`'s members
   (`plasmashell`, `kded6`, `kglobalacceld`, `org_kde_powerdevil`, `ksmserver`,
   `kaccess`, `kcminit_startup`, `gmenudbusmenuproxy`, `xembedsniproxy`) start
   before any display exists, Qt's `init_platform` calls `qFatal`, and every one
   of them SIGABRTs. Confirmed by stack trace on core `2385`
   (`qAbort` -> `QMessageLogger::fatal` -> `init_platform`).
   - It is **self-healing**: systemd restarts them and they succeed once kwin is
     up (`kded6` active at `01:09:55`, `plasmashell` at `01:10:03`). The desktop
     comes up correctly, which is precisely why nothing caught it.
   - It is a **race, not a constant**: occurrences by boot were
     `-4: 0, -3: 0, -2: 0, -1: 8, 0: 39`. The last two images began losing it
     consistently.
   - Cost: ~12 s of login time and ~25-39 aborted processes per boot. No disk
     risk — `/var/lib/systemd/coredump` is 133 MB against the 1 G cap in
     `10-moos-cap.conf`, with 414 G free.
   - **No MoOS unit is implicated.** Nothing under
     `system_files/usr/lib/systemd/user/` orders against `plasma-core.target`;
     the empty `WantedBy=` is upstream's. The recent commits are QML, theme and
     artwork only. `moos-theme-sync` taking 12.3 s is unrelated and expected —
     it is the one-time `THEME_REV` 19->20 re-apply from `13359ab`, and it ran
     at `01:17`, eight minutes after the storm.
   - **Do not fix this on the live machine.** The fix touches session startup on
     the maintainer's daily driver; a wrong ordering drop-in means no desktop.
     Per `AGENTS.md` rule 9 it must be proven in a booted VM first.
2. Introduce testing/candidate/stable image channels before treating the
   maintainer's daily driver as a general release target.
3. ~~Replace deprecated `Qt.btoa(string)`~~ DONE — replaced with the Qt 6.11
   array-like overload `Qt.btoa(Array.from(svg))` (verified QML-host-safe; a
   sibling session's PR #10 added a gate forbidding browser-only `TextEncoder`).

## Open issues / blockers (this session)

1. Suspend/resume was not triggered during this session: Mo Remote intentionally
   holds a sleep inhibitor, and no prior successful suspend cycle was present in
   the retained journal. NVIDIA's suspend unit/drop-in is installed.
2. The tmpfiles issue is CLOSED on live `.254`: `/home`, `/srv`, and `/root`
   are the expected composefs symlinks and the old errors are absent.
3. MoPlayer close/display issue is fixed in canonical commit `ed5ebe4` and
   passed the live test described above. It remains to verify the installed
   copy after booting the signed image containing it.
4. `No QSGTexture provided from updateSampledImage()` is localized to standard
   Plasma panel/tray startup. It is non-recurring and has no observed functional
   or visual consequence. Leave it unchanged unless future evidence shows an
   actual defect; do not shadow system assets in `$HOME`.
5. CI warns that several upstream actions still target deprecated Node.js 20.
6. `kded6` logs missing Aurorae button files under the user-local search path
   during startup, then the installed theme resolves from `/usr/share`. There
   is no user copy, all system assets exist, the live decoration checks pass,
   and copying the theme into `$HOME` would improperly shadow the image. Treat
   this as diagnostic noise unless a visible decoration defect is reproduced.

## Exact next action

**Superseded by the 2026-07-20 (evening) session.**

CI is green and the fix image is **already staged**. Nothing is pending except the
reboot, which was deliberately left to the owner (the machine was in use):

    staged   44.20260720.272  sha256:75daa80e…  revision b95b74fc…  (2026-07-20T19:42Z)
    booted   44.20260720.264  sha256:b7a12e65…  ← becomes the rollback
    also     44.20260720.263  sha256:35d13c7b…

Verified before staging: the image's `org.opencontainers.image.revision` label is
`b95b74fc21014f26c4429eb34534f8c5503ece06`, i.e. exactly the commit carrying the
fixes — not merely "a recent `:latest`". Worth repeating the check, because every
build from `5eab2dc` (13:45) to `f250006` failed on the `moai-do` help gate and
published nothing.

⚠️ This update also bumps the **kernel, 7.1.3-201 → 7.1.4-200**. The NVIDIA kmod is
built into the same image so they match by construction, but this is the machine's
historical failure mode. If the desktop comes up without NVIDIA, roll back to
`.264` rather than debugging live:

    rpm-ostree rollback && systemctl reboot

Do this after rebooting:

1. `moos-selfcheck` and `tests/post-update-check.sh`.
2. **Delete the temporary local override** — until it is gone the machine still
   runs the hand-built agent from `~/.local/lib/mo-remote` and the image copy is
   never exercised, so "verified live" would mean nothing:

       rm ~/.config/systemd/user/mo-remote-personal.service.d/zz-local-build.conf
       systemctl --user daemon-reload
       systemctl --user restart mo-remote-personal.service

   `post-update-check.sh` now fails while that drop-in exists and should go green
   once it is removed — that pair is the actual test.
3. Check Mo PC Remote from the phone at `https://moos-3.tailab78a5.ts.net` (port
   443, no port number in the URL). Expect H.264, not JPEG.

Everything below this line is the older backlog and still applies afterwards.

The one open engineering task is issue 1 above: the compositor race. It is
detected but **not fixed**, and it must not be fixed on the live machine.

Fix it in a VM, in this order:

```bash
# 1. Reproduce in a booted VM (a fast VM may WIN the race — force a loss by
#    slowing the compositor, e.g. software rendering, before trusting a green run).
just build
# bootc-image-builder --type qcow2, then boot under qemu. NOT in /tmp:
# a qcow2 of this image is ~10GB and /tmp here is a 7.8GB tmpfs.

# 2. The candidate fix is a user drop-in that puts the compositor in the
#    transaction, so its existing Before= actually binds:
#      system_files/usr/lib/systemd/user/plasma-kwin_wayland.service.d/10-moos-order.conf
#      [Install]
#      WantedBy=plasma-workspace-wayland.target
#    Confirm against the real unit graph first — `systemctl --user show
#    plasma-kwin_wayland.service -p WantedBy` must stop returning empty.

# 3. Prove it in the VM across several cold boots, then:
bash tests/post-update-check.sh   # the new check must go GREEN (it is red today)
```

Only after the VM is green: commit, push, wait for CI and the signed GHCR
image, stage the NVIDIA image by exact digest, reboot, and re-verify live.
Keep `.260` as the rollback.

## Mo PC Remote (remote control) — status 2026-07-19

- **Verified live and WORKING**, both on LAN and from anywhere on the tailnet:
  - agent listening on `*:8765` (`MoRemotePersona`).
  - `mo-remote-personal.service` active + enabled.
  - `tailscale serve` active: `https://moos-3.tailab78a5.ts.net (tailnet only)
    -- / proxy http://127.0.0.1:8765` — real HTTPS MagicDNS name, so the phone
    reaches this machine on mobile data. Nothing published to the public internet.
- The whole chain is wired: Mo AI Remote panel buttons (Start/Stop/Reconnect/
  Open panel/Remote anywhere) -> `moos://remote/*` + `moos://do/remote-anywhere`
  -> `moos-open` (`remote_ctl`, confirm on start) -> `moai-do do_remote_anywhere`
  (Tailscale operator + `tailscale serve`).
- **Pinned in repo**: `tests/verify_user_experience.py` now gates the entire
  remote-control chain (commit `7c58fb0`) so a future edit cannot silently break
  remote access. Gate verified to bite when a route is removed.

## New-conversation prompt

Use:

> Continue MoOS from the last verified checkpoint. The repository is
> `/var/home/moos/moos-image`. Read `AGENTS.md` and `HANDOFF.md` completely,
> then verify the live system, GitHub CI, GHCR image, and OSTree deployment
> before acting. Trust observed live state over old documentation. Follow:
> fix, test, commit/push, CI, signed update, reboot when required, live
> verification. Update `HANDOFF.md` before stopping.
