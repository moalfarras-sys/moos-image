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

## Current checkpoint

- Date: 2026-07-19, Europe/Berlin.
- Local repository: `/var/home/moos/moos-image`.
- Branch: `main`.
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
  `sha256:6bb673b6583d597048079610ab5b2a91e7bf5f1d2f3e2773a9265ba4b7bae134`.
- The booted image is version `44.20260719.259`; its digest exactly matches
  GHCR `latest` and its signature was verified locally with `cosign.pub`.
- NVIDIA, Wayland, Plasma login and CUDA/NVIDIA operation are live and healthy;
  `nvidia-smi` reports the RTX 2080 SUPER with driver `610.43.03`.
- The previous signed NVIDIA `.258` deployment remains available as rollback:
  `sha256:7bb194c28894aa07ad732a5eb302394f8e1f3587fd1795b9de4491c4460eeb88`.
- `moos-selfcheck`: 38 passed, 1 expected development warning for the local
  Quiet Horizon staging wallpaper; it must return to 39/39 after the signed
  image boots and local staging shadows are removed.
- Failed system units: 0.
- Failed user units: 0.
- `tests/post-update-check.sh`: 39 passed on `.256`; the booted digest exactly
  matches GHCR `latest` and signature enforcement is active.

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

1. Publish this visual-polish candidate once, wait for both CI editions and
   the signed GHCR image, then stage the NVIDIA image by exact digest.
2. Reboot, remove only the known local development shadows, reapply the signed
   dark theme, and verify autologin, dock/control, launcher, lock, logout,
   Plymouth and login from immutable `/usr`.
3. Require `moos-selfcheck` and `post-update-check.sh` to return 39/39, verify
   the exact booted digest/signature and rollback, and inspect system/user
   journals for new MoOS-owned QML or NVIDIA/Wayland failures.
4. ~~Replace deprecated `Qt.btoa(string)`~~ DONE — replaced with the Qt 6.11
   array-like overload `Qt.btoa(Array.from(svg))` (verified QML-host-safe; a
   sibling session's PR #10 added a gate forbidding browser-only `TextEncoder`).
5. Introduce testing/candidate/stable image channels before treating the
    maintainer's daily driver as a general release target.

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

Reboot into staged `.259`, then live-verify the doorway surfaces and exact
digest:

```bash
systemctl reboot
# After login:
rpm-ostree status --json
moos-selfcheck
bash tests/post-update-check.sh
# Recapture login, lock/password and logout. Confirm initial avatar + MoOS badge,
# bidi punctuation, and no new QML errors in both greeter and user journals.
```

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
