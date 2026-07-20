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

The previous next-action ("reboot into staged `.259`") was already **superseded**
before this session began: the machine went on to `.260` and is booted on it.
Nothing is pending on the release path — commit, signed image and booted digest
all agree, and CI is green on all five recent pushes.

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
