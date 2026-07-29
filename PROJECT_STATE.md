# MoOS — where the project actually is

**Read this before touching anything.** It is the map an agent needs on day one:
what exists, what is load-bearing, and which of the "obvious" things to do next
are traps that have already cost this project a day.

Last updated: 2026-07-29 (session N round 3 — shipped to main and BOOTED on
44.20260729.452; `tests/post-update-check.sh` 48 passed / 0 failed. The design
system is **MoOS UI — Liquid Glass**; the mandatory agent skill is in place).

> **Read [`skills/moos-engineering/SKILL.md`](skills/moos-engineering/SKILL.md) first —
> it is mandatory for every agent working here.**

> **Session N — the practical full-system audit (2026-07-29), branch
> `fix/full-system-audit-and-completion`.** A live-first audit (bootc/rpm-ostree
> status, failed units, journal, coredumps, boot chain, sysctl-vs-live, ports)
> found the boot/update/rollback/kernel/signature foundation HEALTHY: all MoOS
> sysctls apply live (BBR, fq, swappiness 150, backlog, inotify), zram active,
> two deployments (rollback intact), signature policy enforced. No Critical/High.
> A read-only defect sweep across all subsystems then produced ten reproduced
> defects, each fixed with a regression proven to bite:
> - **boot** — `net.core.default_qdisc=fq` was rejected on the primary
>   systemd-sysctl pass because sch_fq (a module) was never preloaded; only
>   tcp_bbr was. Added sch_fq to modules-load.d and generalised
>   test_kernel_network_tuning to pair any module-backed sysctl value (95b0161).
> - **ui/motion** — the MoOS apps were the motion-gate blind spot: Mo AI ran 12
>   unguarded Animation.Infinite loops, Welcome/Installer/Store two each. Gated
>   all 18 on `Kirigami.Units.longDuration > 1` and added
>   `system_files/usr/share/moos/apps` to _MOTION_ROOTS (302a410).
> - **cloud** — moos-cloud-dev wrote an inverted subuid range (100000-65535);
>   fixed to a unique per-uid block + new gate test_cloud_subid_range (0c77163).
> - **remote** — the orphaned MoRemote.Tests crashed on a stale assertion
>   (removed wall-clock check); fixed and wired into the Containerfile build
>   stage so it runs every build (ba5bc81).
> - **moai** — test_moai_do now validates the UI's real extractRuns alternation
>   whitelist, not just literals (9569c6e).
> - **ci** — build-disk/iso now cosign-verify the image before building an
>   installer; all jobs got timeout-minutes; build-disk got concurrency
>   (8a13cff). Image build also gained an SPDX SBOM attestation (592e55f) —
>   **which was removed again on 2026-07-29 after it broke the build twice; see
>   the round-3 entry below. Do not re-add it to this workflow.**
> - **moplayer** — the bundled demo playlist could never load (undeclared in
>   pubspec, wrong asset path); shipped it correctly + regression (b25b158).
> - **store** — curated npm/AppImage tools could be installed but never removed;
>   added the symmetric removal path in storectl + the UI Remove button (cb4f981).
> All 30 repo gates pass locally verbatim; controller TS, MoRemote.Tests (.NET,
> 21), and MoPlayer flutter (164) all green. Live-verified where possible:
> Welcome rendered from edited source; `moos-storectl remove claude-code`
> returns success (was "Invalid Flatpak app ID"), the test install restored
> afterward. NOT yet verified (needs a boot / a main build): the sch_fq
> ordering on a clean single-pass boot, and the SBOM attestation step.
> **Update:** the SBOM step was never verifiable — it killed the runner on both
> attempts and was removed (round 3).
>
> **Session N, round 3 — shipped to main, booted, and verified on the machine
> (2026-07-29).** Everything below is running on `44.20260729.452` (rev d567c8b,
> digest ff45fe58), signature-verified against `/etc/pki/containers/moos.pub`.
> `tests/post-update-check.sh`: **48 passed, 0 failed** (was 45/3 before this
> boot), 0 failed system or user units, user `default.target` **1.444s**.
> - **ci (High)** — the SPDX SBOM step killed the GitHub runner twice; the second
>   time it took ALL THREE matrix jobs. syft spends ~8 min unpacking a multi-GB
>   image on a runner already squeezed by `Free disk space`, and the runner does
>   not come back. `continue-on-error: true` does NOT save it — that forgives a
>   step which EXITS non-zero, and nothing forgives a runner that is gone, so the
>   step showed "success" inside a red job. Removed (04b57bd). If it ever returns
>   it needs its own workflow, off the path that produces the image people boot.
> - **recovery (High)** — `deployments()` documents a 3-tuple and the call site
>   unpacks three names, but two failure paths still returned pairs, so Recovery
>   died with `ValueError: not enough values to unpack (expected 3, got 2)`.
>   Both paths mean "rpm-ostree is unwell" — the only reason anyone opens
>   Recovery. It worked on every healthy machine and crashed on the broken one
>   (db7fd10). Verified on this boot: with rpm-ostree PATH-shadowed by a stub
>   that exits 1, `/usr/bin/moos-rollback` still draws (timeout 6s -> exit 124,
>   no traceback); the installed file has 3 three-tuple returns and 0 pairs.
> - **remote/ui (High)** — the shared `<S>` icon set only a viewBox, so any use
>   site without a matching CSS rule fell back to the browser default object
>   size. Measured in Firefox: **290x270px vs 20x19px**, 14.5x too wide, at three
>   sites (idle-timeout overlay, PC-locked overlay, sign-in lockout hint) — the
>   same defect as the ~600px settings gear. Fixed on the component so no future
>   site can repeat it, then sized deliberately: `.center-msg svg` 44px,
>   `.hint svg` 1.05em (f6118e4, e391f79).
> - **remote/ui (Medium)** — `.seg button { min-width: 132px }` was tuned for a
>   FOUR-segment row; Pointer became three and Quality five, so phones wrapped
>   2+1 and 2+2+1. Re-measured inside the real `.card > .card-pad` nesting (a
>   first attempt measured the un-nested case, picked 108px and changed nothing):
>   320px fits three at no value tested, 360px needs <=84px, 390px+ fits all.
>   84px (d567c8b).
> - **theme (Medium)** — the UI2 cursor gate required the two halves to name
>   DIFFERENT themes, which the INVERTED assignment satisfies just as well, and
>   no file said which theme is the light-coloured one. Now two layers, neither
>   trusting the name: the repo gate covers all 16 look-and-feels, and
>   `verify_image_experience.py` decodes the shipped XCursor files and compares
>   mean opaque-pixel luminance (MoOS 155/255 light, MoOSDark 98/255 dark).
>   Both passed inside real CI image builds (5403739).
> - **moai (High)** — every privileged action now leaves a journal record with
>   four distinct verdicts. Verified on this boot against the INSTALLED binary:
>   `verdict=ok` (gpu-report), `verdict=declined` (a rollback declined via closed
>   stdin, deployments unchanged), `verdict=failed status=N`, and `verdict=refused`
>   for `rm -rf /`, `update; rm -rf /`, `$(reboot)`, `../../bin/sh`, `--exec`
>   (a5c2536).
> - **remote/ci (Medium)** — the image ships the vite OUTPUT, and that output is
>   committed at `moremote/agent/wwwroot`. Editing src/ without `npm run build`
>   left every test green and the shipped bundle unchanged. Two guards now:
>   `tests/bundle-freshness.test.ts` (BUILD marker must appear in the bundle, and
>   sw.js may only precache assets that exist) and a CI step running
>   `npm ci && npm run build` that fails on ANY diff. The CI step passed
>   byte-identical on GitHub's runner, so the build is reproducible from the
>   lockfile (8fe3695).
> Sweeps that found nothing, recorded so nobody repeats them: return-arity
> mismatches across 51 Python files and unbounded `subprocess` calls in 6 GTK
> apps produced 5 candidates, 4 false positives cleared by reading (the 5th was
> the Recovery bug above). Mo Store: 33/33 Flathub entries resolve against the
> Flathub API, and every curated `install.kind` (npm, web) has a handler.
>
> **Session N, round 2 — a deeper adversarial pass** on the same branch found
> and fixed eight more, each reproduced with a regression proven to bite:
> - **recovery (High)** — `moos-rollback` named a STAGED update as the rollback
>   target (rpm-ostree lists staged at index 0), telling the user "roll back to
>   <the newer version>". Skip staged deployments (7f9eefa).
> - **cloud/security (High)** — `60-moai-ports` failed OPEN for uid≥1010 (the
>   11th account), reverting to the base ports and reaching uid 1000's key-holding
>   gateway. Now folds into a unique non-base high band (f47f8f6).
> - **moai (High)** — the gateway left a chat reply hanging for ever on a
>   mid-stream drop (swallowed the error, never closed the socket) and dropped
>   Anthropic error/truncation events as blank "successful" replies (6266d7b).
> - **remote (High)** — the H.264→JPEG fallback latch was dead code (`if not
>   pick_h264()` on an always-truthy tuple) and the mid-stream blacklist keyed
>   the instance name 'enc' + called dict.add(); froze ~4s per rebuild (c0b9368).
> - **session (Med)** — `moos-open` session/logout|power hardcoded `qdbus6`
>   (absent on Plasma 6), so they confirmed then did nothing. Added a qdbus
>   resolver (5c58075).
> - **ui (Visual)** — the first-run theme picker previewed Nova/Aurora/Tidal in
>   the wrong accent and drew Midnight black-on-black (Qt.lighter on #000000).
>   Corrected accents to the palettes, elevate with Qt.tint (48dcd0b).
> - **perf** — `moai-openclaw-bootstrap` re-validated an unchanged config every
>   login (~1.7s / ~428 MB Node); short-circuit when nothing changed (fca4757).
> - **REJECTED** — a per-session gateway token (deep-pass proposal) was NOT
>   implemented: `moai-do:942` points codex/claude/opencode at the gateway as a
>   shared OpenAI endpoint, so requiring a token would break them. The gateway
>   being a shared local endpoint is by design.
>
> And the explicitly-requested Mo AI capability growth (60df793): three new
> `moai-do` actions — `rollback` (rescue), `net-doctor` and `gpu-report`
> (read-only diagnostics) — each a fixed case with confirm+pkexec, wired in
> moai-do + moos-open + the QML whitelist/prompt/menu, live-verified. Deferred
> by design: power lock/sleep/restart (overlaps moos://session/*), service-
> restart (validated-arg surface), backup-home (needs a destination story).

> **Session M — the audit-and-truth session (2026-07-28).** The live machine, the
> repo and GHCR were audited against each other before anything was edited.
> Verified live: the machine boots `moos-nvidia` **44.20260728.419** from the
> signed GHCR digest, zero failed system units, all Mo AI/Mo Remote/cloud-audio
> user services active, and `tests/post-update-check.sh` returned **44 passed /
> 0 MoOS failures** (the only failed units were third-party app scopes —
> Chrome/Chromium/Cursor/xwaylandvideobridge — cleared with `reset-failed`).
> All 26 gate commands of `build.yml`'s Repo-gates step pass locally, run verbatim. All
> three images (`moos`, `moos-nvidia`, `moos-cloud`) were published and
> cosign-signed the same day; `main` == `origin/main`; nothing local was
> unpushed (two stale merged branch pointers were deleted). The Mo PC Remote
> engineering of 2026-07-27/28 is on `main` and gated: input injection moved off
> the socket thread, the 1920×1080@30 resolution ceiling replaced by hardware
> probing, encoder rebuild debounce, kernel network tuning (BBR), codec resend,
> the desktop Sound button fix, and the phone UI layout fixes.
> Identity work this session: the design system is now consistently named
> **MoOS UI — Liquid Glass Design System** across README/AGENTS/ROADMAP/artwork
> docs ("Nova" survives only as the `MoOS UI · Nova` palette member and in
> historical logs; every load-bearing identifier — `MoOSUI2Nova*`,
> `org.moos.ui2.nova*`, `org.moos.nova.clock`, SVG `nova-*` ids, Dart
> `class Nova`, QML `nova*` properties — was deliberately left untouched).
> `skills/moos-engineering/SKILL.md` is the new mandatory agent skill, linked
> from README/AGENTS/this file and symlinked into `.claude/skills/` for
> auto-discovery. README.md was rewritten to describe the three-image reality.

> **Session L — MoPlayer 1.2 desktop playback overhaul (2026-07-26).** The
> canonical `~/MoPlayerMoOS` release is `e856461`, pushed on `main`, and the
> vendored source in this image is an exact sync of that commit. The KDE Wallet
> prompt is gone: MoPlayer no longer loads `flutter_secure_storage`/libsecret
> and stores IPTV credentials in its private XDG data file instead (directory
> `0700`, file `0600`, atomic replacement, and a non-fatal memory fallback).
> Existing wallet secrets cannot be migrated without reopening the wallet, so
> users enter the source once after this update. The NVIDIA-safe software
> presentation texture remains the default because the GL texture path has
> killed this app on the maintainer's RTX 2080 SUPER; hardware decoding remains
> enabled. Full-player presentation is bounded to 1280x720 and mini-player to
> 640x360, with a `videoParams` guard that reasserts the bound after media_kit
> silently resets it to the source size. Eight consecutive Wayland captures of
> the public 1080p Mux HLS stream were clean after the earlier 1920x1080 tearing
> was reproduced.
>
> Home, settings, player and catalogue browsing were modernised for mouse and
> keyboard use; direct URL launch on a clean profile works; live channel
> previous/next wraps through the queue from buttons, PageUp/PageDown, N/P and
> MPRIS; buffering/cache/reconnect settings are tuned for IPTV; catalogue caches
> are memoised and invalidated; and storage state is explained in all shipped
> languages. `flutter analyze` is clean, **114 tests** pass, release build and
> `~/.local` installation pass, desktop/AppStream validation pass, and the
> installed binary was exercised against the public HLS stream with MPRIS
> reporting `Playing`, system `libmpv.so.2`, NVDEC active, the safe texture
> resize visible in logs, and no KWallet/Secret Service call. Both local images
> then built successfully from the same source: generic `moos:latest`
> (`0328de17…`) and NVIDIA `moos-nvidia:latest` (`8929faea…`), including the
> app/identity/initramfs/bootc gates and NVIDIA 610.43.03 modules matched to
> kernel 7.1.4-204. Image commit `7308e57` was then published by CI run
> `30182998521`: generic, NVIDIA and cloud all built, pushed, cosign-signed, and
> verified against the OS-enforced public key. The machine has staged the exact
> signed NVIDIA digest `sha256:9608f65a…` as version `44.20260726.358`; the
> booted deployment remains `44.20260725.357` until the user reboots, after which
> `tests/post-update-check.sh` is still required before calling the boot proven.

> **Session K — MoPlayer 1.1 (2026-07-25).** The canonical
> `~/MoPlayerMoOS` repository, not only its image snapshot, now owns the rebuilt
> home and playback experience. The player has complete transport, seek,
> previous/next, volume, fullscreen, fit/fill/original sizing, speed and
> audio/subtitle controls; buffering is visible and recovery is bounded,
> generation-safe and manually retryable instead of silently wedging. The home
> hero is catalogue-driven and the always-running weather/live animations that
> kept an idle 4K window near one full core were removed (measured at ~1.6% CPU
> after the change). Linux single-instance activation now forwards a second
> file/URL to the existing window and was proven live while playback continued.
> Flutter is 3.44.8 / Dart 3.12.2 and the media stack is current.
>
> The “server disappears after restart” report exposed a system/app relationship
> bug: a shipped three-line `~/.config/kwalletrc` shadow disabled the encrypted
> wallet, while the compatibility provider was not active under
> `org.freedesktop.secrets`. `moos-secret-service.service` now provides that
> session service, and `moos-ui-migrate` repairs **only** the exact legacy
> disabled file; custom or later user choices are preserved. MoPlayer itself now
> treats the two encrypted writes as a transaction result and visibly refuses to
> claim success if either one fails — there is deliberately no plaintext
> credential fallback. The canonical app passed analyze + **102 tests**, built
> in release mode and was installed under `~/.local`; two full local image
> builds passed every image/identity/initramfs gate, with the second containing
> the final persistence service and exact existing-user migration.

> **Session J — the release pass (2026-07-25).** Session I's work is now ON
> `main`: `moos-ui-unify` merged as `1e7991b`, build-resilience as `5823f93`, and
> CI run `30152979451` published + cosign-signed `moos:latest` and
> `moos-nvidia:latest` (17m37s, green). Two defects the audit's evidence pointed
> at were fixed rather than noted: the wallpaper scene's `motionEnabled` now
> honours Plasma's "animations off" (it consulted only its own `AmbientMotion`
> key, so the largest surface on screen kept animating against the user's
> setting), and `uupd` — the most expensive unit of this machine's boot at
> 1min 16.195s, firing inside the first fifteen minutes of any desktop that was
> off at 04:00 — got the same idle CPU/IO drop-in `flatpak-system-update` already
> had. Both are gated (`test_moos_ui2.py`, `verify_user_experience.py`).
> **The release gate is now closed:** the machine staged
> `ostree-image-signed:docker://ghcr.io/moalfarras-sys/moos-nvidia:latest`
> (`sha256:12b44aba…`, `44.20260725.347`), rebooted, and
> `tests/post-update-check.sh` returned **48 passed / 0 failed** — the first boot
> on this machine from the signed published image rather than a local
> containers-storage deployment. `moos-selfcheck`: 46 passed.
> The live audit that followed found one real defect, now fixed: **Mo Store's rail
> status dot animated forever with no `running:` guard**, holding the QML render
> loop at full frame rate and repainting a 4K window for one 8 px dot — ~11% of a
> CPU core, paid by any session that merely had the Store window restored behind
> other windows. It was the ONLY unguarded infinite animation among the 30 MoOS
> ships, and the contract that would have caught it existed but covered the
> dashboard only; `verify_user_experience.py` now enforces it across `apps/`,
> `plasmoids/` and `wallpapers/`, broken-once to prove it bites. Everything else
> sampled was clean: no failed units, no MoOS QML errors in the journal,
> notifications deliver, the Mo AI stack answers, the Arabic locale resolves,
> firmware and Flatpaks have nothing pending.

> **Session I — unified visual-system work (2026-07-25, full audit in
> `artwork/MOOS_VISUAL_AUDIT_2026-07-25.md`).** The repository and live 4K/225%
> Plasma session were inventoried rather than judging metadata alone. The 16-theme
> family now shares one generated MoOS design system: complete high-visibility
> Plasma controls and blur masks, rebuilt Aurorae frames and functional button
> states, one safe KWin frost profile, crop-safe Graphite/Tidal wallpaper masters,
> low-duty ambient motion, RTL clock/picker corrections, exact Qt/GTK/GSettings
> readback, and an owned nine-application icon family. Existing-user revisions are
> `THEME_REV=22` and `MOOS_THEME_REV=10`. Both local images then built from the
> fresh `7.1.4-204.fc44.x86_64` base: generic and NVIDIA passed the identity,
> experience, initramfs/OSTree, Plymouth and bootc gates; NVIDIA carried the
> matching 610.43.03 open driver, and both produced 50 Qt WebEngine spell-check
> dictionaries including Arabic and English. The booted audit image was still
> `44.20260724.1` from a **local unverified containers-storage origin**, so it is
> diagnostic evidence only: signed CI publication, signed staging and
> post-reboot proof remain mandatory and must not be claimed until recorded.

> **Session H — the first-boot session (2026-07-17, full writeup in `FIXES_2026-07-17b.md`).**
> ISO `44.20260717.190` was walked end-to-end in QEMU (all green: splash+ring, DE live
> keyboard, 9-page installer, moving progress bar, offline install, target first boot on
> Vienna time) and the walkthrough caught two shipped bugs no gate had seen: (1) the zram
> storm — moos-hardware-adapt's first-boot re-tier restarted systemd-zram-setup@zram0
> bare, tripping dev-zram0.swap into start-limit-hit and leaving a fresh install's first
> boot with two failed units and NO swap (fix: config-equality skip + stop → daemon-reload
> → reset-failed → one start); (2) the live session kept KDE's 5-minute autolock and
> LOCKED the screen over its own running installer (fix: moos-live-polish, gated on
> rd.live.image, writes liveuser's kscreenlockerrc/powerdevilrc — never /etc/xdg). Both
> gates broken-once and watched go red. Forensics trick that cracked it: power the VM off,
> guestfish the journal out of the target disk, read it with `journalctl --directory`.

> **Session G — the polish session (2026-07-17, full writeup in `FIXES_2026-07-17.md`).**
> Wallpapers v2: the four family themes now carry LIT-SILK art (crest-lit bands, aurora
> veil, screen-blended neon edges — make_wallpaper rewritten; Canva retried, account AI
> quota still hard-blocked). A new pre-baked `ring.png` comet-ring sprite orbits the emblem
> on every doorway (login gained a scale-settle entrance, a hairline spark and drifting
> motes; lock and logout carry mirrored rings; the logout watermark breathes). The bar
> brand widened to 1.5× panel height with the ring orbiting continuously. NEW widget:
> `org.moos.heroclock` — the glass desktop Hero Clock (bilingual, live seconds, the mark in
> the corner; every size derives from min(width,height) — height-only sizing shoved the
> seconds strip out of the card on a square window, found live). Lock clock's tick
> breathes; panel clock glints on hover. Gates extended (heroclock completeness + the
> always-on shader ban loop), both watched go red.

> **Session F — the brand session (2026-07-16, full writeup in `FIXES_2026-07-16c.md`).**
> The owner's vector logo landed (`artwork/logo/`) and the animated MoOS brand now lives on
> every doorway surface: the login scene is `org.moos.ui2.greeter` (a Plasma/Wallpaper package
> the greeter's wallpaper process loads — the greeter QML itself is compiled into the binary),
> the lock screen brand breathes and its clock has a floor below it (4K collision fixed), the
> logout greeter carries the animated mark + a draining countdown hairline and its NINE action
> icons are -symbolic now (they all drew as solid teal blobs — isMask over full-colour disc
> icons), and the bar opens with `org.moos.brand` (animated emblem + MoOS-glance popup;
> Kickoff stays the launcher, wearing view-app-grid-symbolic; THEME_REV is 18). Every family
> theme got real designed wallpaper art (glass waves per palette — make_wallpaper rewrite;
> Canva was quota-blocked, the deterministic generator ships the art). All motion is
> Animators-only over pre-baked sprites (`artwork/generate_login_scene.py`); the Lottie file
> in the logo delivery has zero keyframes and is provenance only.

> **State on 2026-07-16 (session E).** The machine is green: `moos-selfcheck` all-pass,
> `post-update-check.sh` 39/0, **zero failed units**, boot to graphical in 4.8 s of userspace
> (GRUB timeout already 1 s; firmware is the remaining 10 s and is out of OS control). The
> NVIDIA fix is proven on hardware (~9 ms/token on CUDA). `fwupd-refresh` — the last open bug —
> now **completes successfully** (Result=success; keep the `10-moos-log-the-error.conf` drop-in
> so any recurrence names its own cause).
>
> **Session E found and fixed the two-stores regression:** Bazaar installed at SYSTEM scope
> (moos-setup's checklist) showed a second visible store, because the old hide only edited the
> per-user flatpak export. The fix is `/usr/bin/moos-one-store` — a NoDisplay override in
> `~/.local/share/applications`, the one dir that outranks BOTH export scopes — called by
> `moos-store-browse` AND `moos-setup`. Three new gates hold it: a static relationship gate in
> `tests/verify_user_experience.py` (both installers must route through the helper; the helper
> must not touch flatpak exports), and a live `moos-selfcheck` check that resolves Bazaar's menu
> entry the way the menu does. All were broken on purpose and watched go red.
>
> **Session E then drove the installer wizard end-to-end for the FIRST time** (ISO 176 in QEMU,
> QMP mouse/keys — synthetic input works in a VM even though it does not on the real machine)
> and the walkthrough caught two shipped bugs no gate had ever seen:
>
> 1. **The wizard called a SUCCEEDING install "stalled."** The backend finished the whole
>    install (target disk bootable, `Installation complete!`, 92 PROGRESS lines written) while
>    the front-end reported FAIL: the launcher's `--cache` already IS `~/.cache/moos-installer`,
>    and the QML appended another `/moos-installer` to it, polling a file nobody writes.
>    One-line QML fix; a three-party relationship gate (moos-open ↔ launcher ↔ QML) now pins
>    the status path.
> 2. **The live session typed English (US) on the owner's German keyboard** while the panel
>    indicator claimed "DE". KWin (Wayland) compiles the keymap locale1 answers — NOT the
>    shipped kxkbrc — and the image shipped neither of localed's sources, so the live ISO ran
>    with localectl fully unset. Proven live: `sudo localectl set-x11-keymap de,ara pc105`
>    flipped the running session to German instantly. The image now ships
>    `/etc/vconsole.conf` (KEYMAP=de) and `/etc/X11/xorg.conf.d/00-keyboard.conf` (de,ara,
>    alt_shift_toggle), both gated against kxkbrc's LayoutList as a relationship;
>    moos-firstboot still rewrites both per the install answers (its no-recipe fallback now
>    matches the image instead of reverting to `us`), and `moos-selfcheck` says explicitly
>    when KWin refused to answer and only config was checked.
>
> The installed target from that walkthrough also proved: timezone page 5 works (searched
> "vienna", selected Europe→Vienna), disk/account/confirm/hold-to-commit all behave, and the
> ISO's offline install path (embedded image, no network) completes.
>
> **ISO `44.20260716.179` (commit `0149736`) is built, WALKED AGAIN end-to-end in QEMU and
> verified fixed:** the live session types German (physical z,z,y,y → "yyzz"; localectl answers
> de/de,ara), the wizard's progress bar moves (34% → 80% → success page), and the whole journey
> is photographed. It lives in `~/Desktop/MoOS-ISO/` with BUILD-INFO.txt, sha256 and proof/.
> The older ISOs (175 broken splash, 176 stalled-wizard) are deleted. The QMP driver scripts
> used for walkthroughs are kept in `~/iso-test/` (drive.py, detype.py).
>
> **Two traps this session cost real time on, both worth knowing before you start:**
> - **Root is `pkexec`, not `sudo`.** `50-moos-devmode.rules` authorises the local active wheel
>   user for `org.freedesktop.policykit.exec`, so `pkexec` runs as root with no prompt while
>   `sudo` still asks for a password. A previous session hit `sudo`, concluded root was out of
>   reach, and left the decisive `fwupd` test unrun for a day. But the rule's allowlist is
>   narrow (`systemctl`, `journalctl`, `bootc`, `rpm-ostree`, `moai-do`, `moos-*`) — `pkexec`
>   on anything else (`localectl`, `cp`) **raises a password dialog on the owner's screen**, and
>   polkit's cache expires every few minutes so it keeps coming back. Do not make the owner
>   authenticate for your own diagnostics.
> - **Mo AI's units are USER units.** `systemctl is-active moai.service` in the system scope
>   answers `inactive` — for a unit that does not exist there. Use `systemctl --user`.

## Active visual work: the MoOS theme FAMILY (UI2 engine)

> **Update 2026-07-16 (session C) — read this before touching themes, the keyboard, or Mo Remote.**
> Full writeup in `FIXES_2026-07-16.md`. Four things landed and are on `main`:
>
> 1. **Theme FAMILY.** MoOS is no longer "ONE look" — it is a **family** on the single UI2
>    engine. Graphite (dark) + Tidal (light) stay the base; four palette-driven members were
>    added — **MoOS Nova, Amethyst, Midnight, Aurora** — each a full package set under
>    `org.moos.ui2.*`, generated by `artwork/generate_moos_themes.py` from
>    `artwork/moos-themes/palettes.json` (it recolours the working UI2 SVGs/decoration + reuses
>    `generate_moos_ui2.py`'s colour math; it does NOT revive the retired Nova/UI1 lineages).
>    `moos-theme <dark|light|nova|amethyst|midnight|aurora|list>` switches instantly;
>    `moos-apply-theme` is family-aware so a pick persists. `verify_identity.py` +
>    `tests/verify_user_experience.py` + `tests/test_moos_theme_safety.py` now enforce the
>    *family* (all MoOS-branded, no foreign, no old generation). The old top-level
>    `org.moos.nova`/`org.moos.ui` are still forbidden. `build.sh` hides the stock Breeze
>    Global Themes from the picker (Hidden=true, non-destructive) — Breeze stays the fallback
>    engine. Every theme was verified applying live. Passages below saying "ONE MoOS look"
>    describe the pre-family state.
> 2. **Keyboard = de,ara.** The owner's hardware is a GERMAN keyboard, so the default xkb layout
>    is now `de,ara` (`system_files/etc/xdg/kxkbrc`, installer `xkbForLang`), Alt+Shift toggle.
>    This is a LAYOUT only — the UI language stays bilingual ar/en (no German catalogues). The
>    old comment saying "de,ara was wrong" assumed US hardware; it does not, here.
> 3. **Mo Remote + terminal fixes** (session B→C): Arabic typed from the phone now works
>    (`agent-linux/InputInjector.cs` routes non-ASCII through clipboard, not portal keysyms);
>    the terminal's bold text is legible again (the Konsole scheme's Intense fg was inverted);
>    generic `monospace` no longer resolves to Kawkab (fontconfig binding).
> 4. **Build robustness.** `build.sh` writes the Tailscale repo file inline instead of
>    curl-ing it — a `pkgs.tailscale.com` 504 took a whole build down on 2026-07-16.

The owner rejected MoOS UI revision 15 as visually insufficient after reviewing
it on the installed machine. It remains installed and untouched as the explicit
fallback. The isolated **MoOS UI2** Graphite Dark / Tidal Light family is now
implemented, selected as the working-tree default, and proven in both variants
on the installed Plasma session. Its palette, package IDs, generated-image
prompts, independent dashboard, real screenshots, measured proof and rollback
rules are documented in [`artwork/MOOS_UI2_DESIGN.md`](artwork/MOOS_UI2_DESIGN.md).
**Correction (2026-07-27): `moos-theme ui1-dark|ui1-light` does not exist.** It was
planned, documented here as supported, and never implemented — `grep -c ui1
system_files/usr/bin/moos-theme` returns 0 — and UI1 itself was removed from the
shipped image in July 2026, so the command could not work even if it were added.
An agent trusting this line would run a nonexistent rollback on the owner's daily
driver. The real fallbacks, in increasing order of blast radius:
`moos-theme undo` (previous MoOS theme) → `plasma-apply-lookandfeel
org.kde.breezedark.desktop` (leave the MoOS family entirely) → `sudo rpm-ostree
rollback` + reboot (previous image). Do not leave user-local UI2 staging shadows
after testing.

### Revision 16.1 — the surfaces UI2 had missed

A full sweep of every visual surface found four places where the desktop was UI2
and the thing sitting on it was not. All four are fixed, and each one is now held
by a gate that was broken on purpose and watched go red:

- **A QML binding loop, live in the shipped image.** `WeatherScene.qml` bound
  `sourceSize.height` to `sourceSize.width` — both halves of one `QSize`, so the
  property depended on itself. Qt resolves that by *dropping* the binding, so the
  weather art decoded at a stale size and plasmashell logged the loop 21 times.
  The build already ran the dashboard and already grepped its log for
  `binding loop`, and **could never have caught it**: under
  `QT_QPA_PLATFORM=offscreen` the card is never laid out to a real width, the
  binding never re-enters, and Qt has no loop to detect. Reproduced deliberately.
  The gate that bites is therefore **static**, in `verify_user_experience.py`.
- **The login screen was still the retired Nova generation.** Everything moved to UI2 except the greeter,
  so the machine booted to a NovaHorizonII login screen and a Graphite desktop a
  second later. The gate could not catch it because it asserted the literal string
  `"NovaHorizon"` — it was pinning the bug in place. It now requires the login and
  lock screens to name the **same** wallpaper.
- **The boot splash was Nova navy** (`#050A14`, `#2E7BFF` bar) on a graphite OS. It
  is now gated against `artwork/moos-ui2/palette.json` rather than a hard-coded hex.
- **The kde-settings profile still named `org.moos.nova`** — a third family, which
  the theme switcher cannot even reach. This is the exact cascade layer AGENTS.md
  blames for Plasma resolving a stale name and persisting Breeze.

The pattern in three of those four: **the gate named a constant, and the constant
went stale.** The replacements gate a *relationship* (login screen == lock screen;
splash == palette; kde-profile == the image's own default), so the next theme
family inherits them for free.

`artwork/MOOS_UI2_DESIGN.md` ends with a coverage-gap list that is now largely
**closed**: teal MoOSUI2/MoOSUI2Light icon themes are built in build.sh,
libadwaita/Flatpak apps get the UI2 palette (moos-ui2.css + the gtk-4.0 read
hole), the lock screen is the MoOS shell-package override, and the desktop
dashboard lives INSIDE the wallpaper (org.moos.ui2.wallpaper — below the icons,
so it can never cover them). The Welcome (apps/welcome) is a real onboarding
wizard again; Mo Store (apps/store, /usr/bin/moos-store, org.moos.store.desktop)
is the standalone storefront. Verify against the gates, not this paragraph.

## Previous visual work: MoOS UI

The working tree contains the new **MoOS UI** dark/light visual pair, first-party
Mo AI and Mo PC Remote icon masters, a warm matched wallpaper, and the glass
desktop-widget evolution. The implementation contract, palette, generated-image
prompts, rollout rules and one-command regeneration path are in
[`artwork/MOOS_UI_DESIGN.md`](artwork/MOOS_UI_DESIGN.md). The retired Nova
generation (UI1-era) is NO LONGER installed — it was removed from the shipped
image in July 2026; see the removal note at the end of this section and use the
real fallbacks listed under "Active visual work" above. Do not hand-edit
generated MoOS UI package output;
change its masters and regenerate it. (Removed 2026-07-27: `artwork/generate_moos_ui.py` was the UI1 generator. It copied `plasma/desktoptheme/Nova` -> `MoOSUI`, and neither directory has existed in `system_files/` since UI1 was removed from the shipped image in July 2026 — running it produced nothing. UI2 is generated by `generate_moos_ui2.py` and `generate_moos_themes.py`.)

Visual revision 15 incorporates direct hardware review: the desktop widget is now
a wide animated live dashboard, and the Light dock owns a warm-mauve FrameSvg with
the exact Dark geometry. Both variants pin adaptive transparency off so Plasma
cannot turn only the Light dock into an opaque white slab. Current hardware proof
is under `artwork/moos-ui/live-tests/*-v2.png`.

---

## The shape of the thing

| Repository | What it is | How it reaches the user |
|---|---|---|
| `~/moos-image` | The OS. A bootc image built from `Containerfile` + `build_files/build.sh` + a literal filesystem tree in `system_files/`. | Push to `main` → GitHub Actions builds **two editions** (`moos`, `moos-nvidia`), signs them with sigstore, pushes to `ghcr.io/moalfarras-sys/`. The user's machine stages the resolved signed digest through `moai-do update`. |
| `~/MoPlayerMoOS` | The IPTV player. Flutter. Its own repository: **github.com/moalfarras-sys/MoPlayerMoOS**. | **Vendored** into `moos-image/moplayer/` by `just sync-moplayer`, then compiled *inside* the image by a Containerfile stage. The image ships the binary, never the toolchain. |
| `~/MoPlayerios` | An iOS build of MoPlayer. Not part of the OS. | — |

The machine this is developed on **boots the thing being developed**:
`ghcr.io/moalfarras-sys/moos-nvidia:latest`, signature-enforced. That is the whole
reason the gates below exist.

### Changing MoPlayer, end to end

MoPlayer has two homes and they are not equal. Its **repository** is where the work
happens; `moos-image/moplayer/` is a **snapshot** of it, and the snapshot is what
the image compiles. A change that lives only in one of them ships as half a change.

```
1. work + commit in ~/MoPlayerMoOS   (`just check` there: analyze + 114 tests)
2. push it                            → github.com/moalfarras-sys/MoPlayerMoOS
3. cd ~/moos-image && just sync-moplayer
      ↳ refuses a dirty MoPlayer tree — vendoring copies `git ls-files`, so an
        UNCOMMITTED file is copied by nobody and the image fails on a missing import
      ↳ also installs the launcher/.desktop/icons into system_files/ itself
4. commit the re-vendor, push          → CI builds and signs both editions
5. on the machine: `moai-do update`, then reboot from the MoOS power UI after the signed digest is staged
6. `./tests/post-update-check.sh`      → confirms the booted digest IS the published one
```

Never edit `moos-image/moplayer/` by hand. It is generated, and the next
`sync-moplayer` will silently erase you.

---

## The five traps that have actually bitten

These are not style notes. Each one shipped, or nearly shipped, and each one cost
hours to find because **the gate was green while the thing was broken**.

### 1. The shadowed-config trap
The image is right, the user still does not get it. `/etc/xdg/…` and
`/usr/share/…` are *defaults*; a file in `~/.config` or `~/.local/share`
**shadows them forever**. Staging a fix into the home directory to "prove" it on
the running desktop leaves that shadow behind. `moos-apply-theme` exists to remove
those shadows once the system copy is correct — extend it rather than writing a
new one.

**Corollary that cost two hours today:** `moos-selfcheck` verified the *system's*
keyboard layout (`localectl`, which said `de,ara`) while the *session* was running
`us`, because fcitx5 had rewritten `~/.config/kxkbrc`. A check that reads the
image instead of the running desktop cannot fail. It asks KWin now.

### 2. A gate that matches its own comment
Every file here documents the bug it prevents — so a gate written as
`"Kawkab Mono" in text` passes forever, because the *comment* names Kawkab Mono.
`tests/verify_user_experience.py` has a `code()` helper that strips comments.
**Use it.** And after writing a gate, **break the thing on purpose and watch the
gate go red.** A gate that has never failed has never been tested.

### 3. The build context is not the git tree
`COPY system_files/ /` copies from the *working tree*, and `.gitignore` has no say
in it. The image shipped `/usr/bin/__pycache__/moai-control.cpython-313.pyc` — the
bytecode cache of the build machine — while CI, building from a fresh clone,
shipped nothing of the sort. **Two different images from one commit.**
`.containerignore` now excludes it, and a gate in `build.sh` fails the build if any
`__pycache__` reaches `/usr/bin`.

And note the pattern syntax: `__pycache__/` matches only the **context root**. It
must be `**/__pycache__/`. The first version of that file looked right, read right,
and excluded nothing. The gate caught it.

### 4. Vendoring drops what git does not track
`just sync-moplayer` copies `git ls-files` from `~/MoPlayerMoOS`. An **untracked**
file is copied by nobody: the vendored tree keeps the import and loses the file,
and the image fails twenty minutes later, inside a container, on a missing URI. It
**refuses a dirty tree** now, and a gate walks every relative import in the
vendored source and fails if the target was not vendored.

### 5. The local LLM owns the graphics card
MoOS ships a local model that holds **~6 GB of an 8 GB card** while loaded. With
that little left, EGL cannot make a context: `eglMakeCurrent failed` → libepoxy
asserts → **the process aborts**. The user's own OS killed its own video player,
silently. `/usr/bin/moplayer` calls `moos-gpu-headroom` first, which unloads *only*
the brain and only when the card is nearly full. A gate requires the launcher in
`system_files/` to be **byte-identical** to MoPlayer's own
`packaging/moos/moplayer` — the guard lived in only one of them for two hours, one
`install -D` away from being lost.

**Practical rule:** check `nvidia-smi` free memory before launching anything
GPU-heavy for a screenshot. Do not open a browser to "set up a scene" — that
exhausted VRAM and took KWin down with a SIGSEGV.

---

## Verification: how to actually see things

- **Synthetic input does not work on this machine.** `ydotoold` runs, the uinput
  device exists, and KWin receives nothing — in logical *or* physical coordinates.
  Proven by clicking a window's close button in both spaces and watching the
  process live. **Never plan a loop that needs to drive a GUI.** Reach the state
  from outside instead: `moplayer --section live`, `moplayer <subscription-link>`,
  a route the app opens on. If a state can only be reached by clicking, add an
  honest CLI seam (it is usually a feature someone wanted) or ask the user.
- **Screenshot:** `spectacle -b -n -f -o out.png` (not `grim` — wlroots only), then
  crop and zoom with ImageMagick and *read the image*.
- **A new window opens behind a fullscreen app.** Make a temp virtual desktop,
  switch, launch, capture, switch back, remove.
- `konsole --geometry` **is not a valid option** — the process exits instantly and
  no window appears. This silently blinded a whole session.

---

## MoPlayer: the IPTV facts that decide the design

Measured against the maintainer's real subscription, not assumed:

- A subscription is sold as **one link**:
  `…/get.php?username=U&password=P&type=m3u_plus`. Pasted into an M3U field it
  *works* — and yields channels and nothing else. Read as what it is (a panel plus
  an account), the same string opens the whole Xtream API: **12,653 channels,
  20,187 films, 10,550 series.** That is `lib/services/source/source_link.dart`,
  and it is used by both the login screen and the command line.
- **`max_connections = 1`.** One stream at a time. Never design a flow that tunes a
  channel to show a preview — the user knocks their own stream off the air. This is
  why the live screen's third pane follows the channel you are *looking at*.
- Panels lie about their own API: this one answers `get_short_epg` and
  `get_simple_data_table` with `[]` for **every** channel, while `xmltv.php`
  returns 2,587 programmes. An "empty" guide is usually an unimplemented endpoint.
- The panel publishes **duplicate** `<programme>` elements, and serves its
  catalogue with 32 identical-artwork recorded matches first. Sort by `added` or
  the film wall reads as a failed image load.
- The home page's football comes from that guide, joined against the user's own
  channels, so every card is one press from playing. A fixture on a channel the
  account does not carry is **not drawn** — a card that cannot be pressed is a
  disappointment dressed as a feature.

---

## Owner's UX rules (do not "improve" these away)

- The dock has **seven** slots: search · home · live · movies · series · favorites ·
  settings. Home *is* in the dock — the corner logo was not enough.
- Every browse page: **groups (vertical) · wall · preview**. The preview follows
  hover **and keyboard focus**.
- **The mouse wheel scrolls the page.** A rail must never turn a vertical wheel
  into sideways movement — the home page is a column of rails, so that makes
  everything below the fold unreachable. Shift+wheel and the hover arrows move a
  rail. There is a widget test that fails if this regresses.
- Settings is an Apple-style panel. Its Updates section is honest: MoPlayer ships
  *inside* the image and `bootc` replaces the whole OS atomically, so there is no
  self-update button, because there is no self-update.
- The brand palette is **measured off `assets/branding/logo.png`**, not chosen
  beside it. A test opens the PNG and fails if the tokens drift.

---

## Gates — what runs, and where

| Gate | Runs in |
|---|---|
| `tests/verify_user_experience.py` | CI (before the build) **and** `just build` |
| `tests/test_device_plan.py` | same |
| `tests/test_moai_do.py` | same — covers all 17 `moai-do` actions and rejects anything off the list |
| `build_files/verify_image_experience.py` | *inside* the image, after every package and rebrand |
| `__pycache__` / bytecode-cache gate | inside the image, at the end of `build.sh` |
| MoPlayer bundle completeness | inside the `moplayer-build` stage |
| MoPlayer: `flutter analyze` + 114 tests | `just check` in `~/MoPlayerMoOS` |

They were honour-system until today: **not in CI, not in `just build`**. If you add
a gate, wire it into both, and break it once to prove it fires.

---

## Working rules

- `git status --short` before every batch. Another agent may be in the same tree —
  it has happened, and a commit landed on the wrong branch because of it.
- Do not commit, push, or change the installed image without the owner asking.
- Every visible fix adds a gate or a test that would have caught it.
- Do not invent a new file under `system_files/` before searching for the surface
  that already does that job.
