# MoOS — current project state

This file is current state, not session history. Git history owns the history.
When documentation disagrees with a running machine, a freshly booted artifact,
or current source, those stronger forms of evidence win.

Last reconciled: **2026-08-26** — ARM/iPhone UTM release gates hardened and
the live-ISO evidence record corrected. A workflow marked green while both
runtime proof scripts had actually failed; the current gates correctly reject
that result.

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

The source and image gates verify the hidden-menu and Plymouth configuration.
The latest live-ISO runtime attempt did not reach a stable themed desktop, so
this remains pending an actual non-blank visual proof rather than being inferred
from the files in the image.

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

## ISO build pipeline — ARTIFACT PRESERVATION FIXED; RUNTIME PROOF OPEN

The ISO built fine but the `Upload ISO as workflow artifact` step ran **last**,
so when the QEMU boot/install proof steps failed in the GitHub runner (a runner
environment limitation, not an ISO defect) the whole job aborted and the
already-built ISO was dropped.

Fix (merged to `main`, commit `5279e2b8`): the ISO upload now runs **before**
the proof steps, so the artifact is captured even if a later proof step fails.
The proof gates themselves stay hard-fail (no `continue-on-error` was added — we
do not weaken a guard to make a build pass).

Run `32851648759` was previously recorded here as an end-to-end success. That
was false-green evidence: its log contains `ISO BOOT FATAL` (missing live theme
marker and an unstable graphical session), followed by `ISO INSTALL FATAL`
(45-minute install timeout). Those steps were marked successful only because
that historical revision used `continue-on-error`.

Current `main` removed that bypass. Run `32878499815` therefore failed at the
live boot proof and correctly skipped installation. The finished ISO is still
uploaded for diagnosis, but it is **not release-proven** and cannot satisfy the
promotion gate until boot and offline installation both pass without an error
bypass.

The latest diagnostic artifact is a generic ~4.8 GB bootable ISO 9660 labelled
`MoOS-Live`. It is not a final deliverable while the runtime proof above is red.

---

## Where we are (one paragraph)

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

- **Live-ISO runtime** — the exact final ISO must still pass the hard-fail CI
  live boot and offline install/reboot proof. A real-firmware/real-disk pass is
  then a separate hardware exercise.
- **ARM / iPhone UTM net installer** — full path (download → install → boot →
  greeter) not proven E2E on physical hardware. Current source requires the
  1.5 GiB/2 CPU iPhone 13+ profile, portable emulated networking, a non-blank TCG
  installer frame, two boots of the exact ARM disk, and login/app/non-blank
  proof of the exact full iPhone bundle before GitHub can publish it. Those new
  gates are awaiting their first CI artifact run.
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
