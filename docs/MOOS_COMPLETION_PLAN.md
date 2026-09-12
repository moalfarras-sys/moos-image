# MoOS completion plan — from a working system to one world-class product

Adopted 2026-09-11. This is the master program. Release gates stay in
[`MOOS_ROADMAP.md`](../MOOS_ROADMAP.md), current terrain in
[`PROJECT_STATE.md`](../PROJECT_STATE.md), ownership architecture in
[`MOOS_UNIFIED_PLATFORM.md`](MOOS_UNIFIED_PLATFORM.md). Only completed evidence
closes an item; a plan line is not a claim.

## ملخص للمالك

- **وين نحن:** MoOS نظام حقيقي شغّال وموقّع على 4 إصدارات، والكمبيوتر الأساسي
  شغّال على الإصدار الموقّع `44.20260910.796` مع نسخة رجوع. التصميم الجديد
  (الإعدادات، المتجر، Mo AI، الثيمات) قوي، لكن النظام **مش موحّد بعد**: بنفس
  الجلسة ثلاث لغات واجهة، وجيلين تصميم، وجهتين بتثبّت برامج، والعقل الافتراضي
  أخد 36.7 ثانية لجواب سطر واحد.
- **القرار:** ما منعمل fork لـ KDE. منوحّد التجربة فوقه: لكل قدرة صاحب واحد،
  لغة واحدة، تصميم واحد، و Mo AI بيصير مشغّل للنظام (يثبّت ويحذف ويحدّث ويصلّح)
  عبر نفس الأدوات الموثوقة، بموافقة المستخدم، بعقل سحابي مجاني مقاس بالأرقام.
- **الترتيب:** P0 نفك قطار الإصدار ← P1 منتج واحد (لغة/تصميم/مداخل) ←
  P2 Mo AI مشغّل النظام ← P3 برامج Android و Windows من المتجر ←
  P4 لابتوب ولمس وسحابة ← P5 جودة عالمية (وصول، أداء، عتاد، تثبيت حقيقي).

## 1. Where MoOS is — measured 2026-09-11

### Release train

- Production `latest`: `44.20260910.796` (revision `c0cc94e7`) for `moos`,
  `moos-nvidia`, `moos-cloud`; `moos-arm` `44.20260909.333`. The daily-driver
  NVIDIA PC boots the signed NVIDIA digest and retains `44.20260908.782`.
- Candidate `a0e7ef96` was rejected by its own ISO and ARM proofs (the
  inherited Flatpak bootstrap raced the MoOS store owner). The corrected
  revision `153f056a` passed all 126 CI repo gates locally and was dispatched as
  x86 build run `34646188216` and ARM run `34646190268`. Three QCOW2 proofs, the
  ISO install proof and promotion are still owed.

### Live audit on the daily driver, as a user

Every first-party app was launched on the running 4K session and captured.
Captures stay local because they contain private session content.

| Surface | What a user actually sees | Verdict |
| --- | --- | --- |
| Settings | UI2 design, device glance, signed-image and rollback status | Strong. "All system settings" still hands off to a second settings app |
| Mo Store | UI2 design, 3345 apps, 27 installed, curated picks | Strong. Stat sub-labels sit on the card border; the first pick is a local-LLM app while Mo AI is cloud-only |
| Mo AI | Arabic UI, four quick actions, raw `openrouter/free` model id in the composer | Beautiful shell, weak brain defaults: slow answers, leaked reasoning, can install but not remove or update apps |
| Updater, Recovery, Mo PC Remote | Older teal/grey generation | Reads as a different product; Remote offers Start and Stop together while running |
| Themes | 16 polished families plus wallpaper motion | Good, but a second entry point beside Settings → Appearance |
| Welcome | Bilingual first-run with a clear call to action | Good |
| MoPlayer | Own orange identity, German UI | Follows the session locale, unlike the MoOS apps beside it |
| Language | Session `LANGUAGE=de`; `moos-lang` accepts only `ar`/`en` | One session shows German, English and Arabic at once |
| App authority | Store installs per user through `moos-storectl` (22 apps); `moai-do install` uses Flatpak's system installation (3 apps) | Two install authorities and scopes |
| Health | `moos-selfcheck`: 49 passed, 2 broken, 6 notes | Both broken items are stale user drop-ins identical to the image; four retired local-brain units still ship |
| Compatibility | Waydroid, Wine and Bottles present; `setup-waydroid`/`setup-windows` actions exist | Per-app, not yet a product; Waydroid on the proprietary NVIDIA stack needs software rendering |

### Mo AI brain benchmark

One sample per model through the real `moai-gateway` with the zero-price
policy active: an Arabic request that should produce an `uninstall` tool call,
and a two-sentence Arabic explanation.

| Model | Tool call | Arabic chat |
| --- | --- | --- |
| `openrouter/free` (current default → a 550B reasoning model) | not tested | 36.7 s |
| `dots-studio/dots-3-note-preview:free` | correct, 2.7 s | good, 5.1 s |
| `nex-agi/nex-n2.5-pro:free` | asked to confirm instead of calling, 3.2 s | good, 2.4 s |
| `nvidia/nemotron-3-super-120b-a12b:free` | correct, 3.0 s | 9.4 s, stray tool JSON in text |
| `nvidia/nemotron-3.5-lightning:free` | correct, 21.0 s | 32.0 s, English reasoning leaked |
| `google/gemma-4-31b-it:free` | upstream rate limit | — |
| `thinkingmachines/inkling:free` | refused outside agent harnesses | — |

`automatic_model()` ranks candidates by tool support, reasoning support and
parameter count, so it deliberately selects the slowest models. Free catalogues
change weekly; a single sample is evidence of a problem, not a final ranking.

## 2. Decisions

1. **Upstream stays.** KDE Plasma, KWin, systemd and bootc remain the base;
   MoOS owns the experience above them (unchanged architecture).
2. **One authority per capability.** Apps: `moos-storectl`. System image:
   `moos-image-update` through `moai-do`. Privilege: `moai-do` + Polkit.
   Language: one MoOS language authority. Theme: `moos-apply-theme`.
   AI inference: `moai-gateway` with the cloud policy.
3. **Mo AI is a system operator, not a chatbot.** The model proposes, the user
   confirms, the allowlisted executor acts, and Mo AI reports only what it read
   back. No path lets model text execute.
4. **The brain is measured, not guessed.** Free cloud by default, ranked by a
   recurring evaluation of latency, Arabic quality and tool-call accuracy, with
   OpenRouter fallbacks restricted to zero-price models and bounded reasoning
   for interactive chat.
5. **One design generation.** Every first-party surface uses UI2 components.
6. **Android and Windows apps arrive through Mo Store** as first-class sources
   with an honest per-app compatibility label, never a universal promise.
7. **Evidence before promotion** stays unchanged.

## 3. Program

### P0 — Release unblock and live hygiene (now)

| ID | Work | Exit evidence |
| --- | --- | --- |
| M0.1 | Carry `153f056a` through build, three QCOW2 proofs, ISO install and ARM boot; promote | Five x86 run IDs plus ARM proof manifest for one revision |
| M0.2 | Run `docs/NVIDIA_HARDWARE_ACCEPTANCE.md` on the daily driver after promotion | Filled checklist naming the digest |
| M0.3 | Deliberate broken-update rollback, disposable VM first, then hardware | Previous signed deployment boots with user data intact |
| M0.4 | C2b: stop shipping retired local-brain units and local-engine wording in the gateway unit and `moai-do` help | Units absent from the image; migration tests still pass |
| M0.5 | Remove the two stale user drop-ins on the daily driver (owner approval pending) | `moos-selfcheck` 0 broken |
| M0.6 | S03: sustained-session KWin memory trace under the existing bound | Same workload over hours with no unexplained growth |

### P1 — One product: language, design, front doors

| ID | Work | Exit evidence |
| --- | --- | --- |
| M1.1 | One language authority for `ar`, `en` and `de` that every first-party app reads, including MoPlayer and Mo AI; RTL stays first-class | Each app launched under each language shows no foreign-language chrome |
| M1.2 | Move Updater, Recovery and the Mo PC Remote control centre onto UI2 components | Live 4K captures beside Settings; measured contrast |
| M1.3 | Settings owns Themes, Updates and Recovery as sections; standalone launchers become deep links | One launcher entry per task; routes cross-checked |
| M1.4 | Store polish: stat labels, curation consistent with product policy, progress for Mo AI-started jobs | Captures and job readback |
| M1.5 | Remote control centre state: only the valid action is enabled | Start/stop fixture test and capture |
| M1.6 | Show a human brain label instead of raw model ids | Capture in Arabic and English |

### P2 — Mo AI, the system operator

| ID | Work | Exit evidence |
| --- | --- | --- |
| M2.1 | Install, remove and update apps through `moos-storectl` from `moai-do`, `moos-open` routes and Mo AI run buttons | Refusal and delegation tests with doubles; live remove/reinstall of a small app |
| M2.2 | Recurring brain evaluation writes a ranked zero-price candidate list; the gateway uses it with bounded reasoning | Policy tests keep zero `max_price`; eval report; ≤ 5 s p50 Arabic answer |
| M2.3 | Native tool calling generated from the `moai-do` allowlist; confirm cards instead of text scraping | Tool-call accuracy ≥ 95 % on a fixed Arabic/English eval set |
| M2.4 | Incremental streaming in the desktop chat | First visible token latency measured |
| M2.5 | Operator skills with readback: update status and staging, cleanup, diagnosis, theme and language through their owners | Each skill reports verified state, never an assumed result |
| M2.6 | Opt-in device context from `moos_hardware` and Settings state | Privacy review and fixture tests |

### P3 — Run everything: Android and Windows apps

| ID | Work | Exit evidence |
| --- | --- | --- |
| M3.1 | Windows: `.exe`/`.msi` open in MoOS App Runner → a per-app Bottles bottle with launcher entry and icon; a Store shelf of verified apps | install-launch-use-reopen-remove for ten popular apps |
| M3.2 | Android: on-demand Waydroid session, Store Android source (F-Droid first), per-app launcher entries, clipboard and files; honest GPU labels | Same lifecycle for ten apps on Intel/AMD and on NVIDIA software rendering |
| M3.3 | Publish the compatibility matrix (A01) in Store and docs | Matrix generated from recorded runs |

### P4 — Form factors: laptop, touch, cloud

| ID | Work | Exit evidence |
| --- | --- | --- |
| M4.1 | Laptop: power profiles, suspend/resume, lid, brightness shown by default on portable hardware | Tested model list |
| M4.2 | Touch and tablet: automatic tablet mode, larger targets, on-screen keyboard in all three languages, gestures | Captures and input readback on a touch device |
| M4.3 | Cloud desktop: capture efficiency (P02) and reliable multi-user screens; the phone Remote as a first-class client | Frame pacing and reconnect measurements |

### P5 — World-class trust

| ID | Work | Exit evidence |
| --- | --- | --- |
| M5.1 | Accessibility runtime (X01): screen reader, focus, contrast, disabled motion | Spoken-output and focus-traversal recordings |
| M5.2 | Performance budgets per release: boot to desktop, idle memory, app launch p95, Mo AI first token | Tracked table in `PROJECT_STATE.md` |
| M5.3 | Hardware qualification (H01) and installer on real hardware (I01) | Supported/experimental/unsupported list |
| M5.4 | Supply chain: pinned base digests (R02), scheduled ARM rebuilds (R03), SBOM outside the release job | One immutable input per release |
| M5.5 | Opt-in redacted support bundle (Q01) | Bundle reproduces a real report |

## 4. Scorecard

| Metric | Measured 2026-09-11 | Target |
| --- | --- | --- |
| Mo AI desktop chat answers at all | no: HTTP 503 for every message | yes, on every edition |
| Mo AI one-line Arabic answer | 36.7 s with the default brain | ≤ 5 s p50 |
| Mo AI tool-call accuracy | not yet measured systematically | ≥ 95 % |
| App lifecycle from Mo AI | install only, separate scope | install, remove, update via the Store backend |
| UI languages in one session | 3 | 1 |
| First-party design generations | 2 | 1 |
| `moos-selfcheck` on the daily driver | 2 broken | 0 |
| x86 proofs for the current candidate | 0 of 5 | 5 of 5 before promotion |
| NVIDIA hardware acceptance steps run | 0 | all |
| Deliberate rollback proof | never | VM and hardware |

## 5. Working agreement

- One branch per slice, a pull request, the full CI repo-gate list and
  `just check`; visual slices add live captures. Nothing lands on `main`
  without its gates.
- Agents working at the same time use separate git worktrees. Another
  session's uncommitted work is committed only after review and a green gate
  run, with its origin stated in the commit message.
- Every slice updates `PROJECT_STATE.md` and `MOOS_ROADMAP.md`; boot, kernel
  and update changes are documented there and in the commit message.

## 6. Progress log

- **2026-09-11:** live audit and brain benchmark recorded above; store-owner
  fix `153f056a` committed after 126/126 gates and dispatched to CI; M2.1
  implementation started on `feat/moos-completion-20260911`.
- **2026-09-11, M2.1 source + live proof:** `moai-do` install/uninstall/update-apps
  delegate to `moos-storectl`; Mo AI Remove and update chips and routes; truthful
  cloud-only prompt; OpenCode config fixed (old model reproduced HTTP 409). Live
  run on the daily driver installed, removed and updated apps with readback.
- **2026-09-11, M2.2 source + live proof:** measured free ranking, cooldown and
  pre-byte retry among verified free models; the branch gateway answered Arabic in
  2.0 s and 1.8 s and a tool call in 1.9 s, against 13–37 s on the installed route.
- **2026-09-11, M1.4 + M1.6 source + live captures:** Mo Store's hero stat cards kept
  their captions on the card border and centred each number at a different offset;
  fixed line heights and a filling column put all three inside their cards, aligned
  (before/after 4K captures of the running Store). Mo AI's composer chip showed the raw
  `openrouter/free` id; it now reads "Free · automatic" / "مجاني تلقائي" and names the
  model that answered from `X-MoAI-Model` (QML engine probe plus a live capture).
- **2026-09-11, P0 found by using the app:** Mo AI's desktop chat returned "agent
  unavailable" for every message on the daily driver (absent Hermes runtime → HTTP 503
  in 0.0 s). Source now answers through the direct free route with a `direct-fallback`
  label; the branch app replied in-app with a working Remove chip.
- **2026-09-12, M1.2 + drift root cause:** Updater, Recovery and Mo PC Remote now take
  the active theme's palette (KConfig cascade; live captures on Arena). The recurring
  wallpaper drift was the gate suite driving the live shell; the suite is isolated.
- **2026-09-12, M1.5 + polish:** Remote offers only the valid action; the Updater checks
  on open; Mo AI's chip names the model in full. All captured live from the branch.
- **2026-09-12, release unblock + user-visible polish:** the ISO install proof failed only
  at Plasma Login (PAM rejected the correct password three times); the proof now clears
  the field before typing, pinned by its gate, awaiting the next ISO run. Mo AI device,
  apps and compatibility panels and six Settings icons fixed after live use; a new gate
  stops Settings glyphs from silently falling back to the sparkle.
- **2026-09-12, released:** `6021840c` signed and promoted; the ISO login fix is proven
  (run 34676614084 logged in on attempt 1).
- **2026-09-12, M2.3 (control) + M2.4 (daily check) + P1 Plasma:** `moos-control`
  tap-to-run actions, `moos-health` read-only daily check with Mo AI card and brain
  context, and the `moai-krunner` search runner; each proven live and gated.
