# MoOS — current project state

This file is current state, not session history. Git history owns the history.
When documentation disagrees with a running machine, a freshly booted artifact,
or current source, those stronger forms of evidence win.

Last reconciled: **2026-08-28** — live user audit: Waydroid SELinux/data-path fix, Android UI proven, Speaches container permission fix staged.

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
  greeter) not proven E2E on physical hardware.
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
