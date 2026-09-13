# MoOS development plan

This is the only product development plan. It replaces the former completion,
system, x86, unified-platform, visual and remote-v40 plans. Current evidence is
in [`PROJECT_STATE.md`](../PROJECT_STATE.md); release mechanics are in
[`RELEASE.md`](../RELEASE.md).

## Product outcome

MoOS must be a coherent operating-system product rather than a collection of
packages and themes. The target is competitive quality in the areas users feel:
reliable boot and recovery, safe updates, hardware adaptation, one visual and
language system, a trustworthy application model, accessible input and output,
fast interaction, and an AI operator whose actions are explicit and bounded.

Competition with macOS, Windows and Android is a quality benchmark, not a claim
of API compatibility or feature parity. MoOS should reuse mature upstream
components and own the integration, defaults, verification and recovery paths.

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
6. Mo Store is the only application-lifecycle authority. Desktop applications
   use sandboxing and portals by default; system drivers and services stay in
   the signed OS image.
7. Mo AI is cloud-only. Free service is the default, paid providers require an
   explicit choice, and credentials remain private user state.
8. A build, a local image, a published candidate, a booted artifact and a
   promoted release are different states and must never be conflated.

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

Only one task is active at a time unless the plan explicitly states that two
independent artifacts may run in parallel.

For every task:

1. Read this plan, `PROJECT_STATE.md`, the engineering skill and the affected
   component documentation.
2. Record the current runtime or artifact behavior before editing.
3. Add a regression that fails for the reproduced defect or a measurable
   acceptance check for new work.
4. Implement the smallest complete vertical slice. Do not leave a second owner,
   compatibility alias or dead service unless an upgrade path requires it.
5. Run targeted tests, `just check`, and the risk-appropriate image/VM/hardware
   proof.
6. Update `PROJECT_STATE.md` with current evidence and update the task status
   here. Remove superseded prose instead of appending a diary.
7. Commit one reviewable result. Report changed behavior, evidence and open
   exclusions.
8. Say **“Task complete; ready for the next task.”** only when the exit evidence
   is present. Otherwise state the exact blocker and keep the task open.

## Ordered execution

### P0 — Establish one proven release

P0 is complete only when the cleaned source is published as one exact signed
revision and all required editions/artifacts prove that revision.

| ID | Status | Task | Exit evidence |
| --- | --- | --- | --- |
| P0.1 | **NEXT** | Authenticate GitHub, push the current branch, review it, and create one candidate revision | PR URL; clean review; signed candidate digests bound to one SHA |
| P0.2 | Open | Run generic, NVIDIA and cloud QCOW2 proofs plus offline ISO install/second boot | manifests and runtime logs name the exact P0.1 digests |
| P0.3 | Open | Finish physical NVIDIA qualification | Plymouth/login photos; two suspend cycles; audio/network recovery; second monitor; clean journal |
| P0.4 | Open | Prove failed-update recovery | disposable VM bad-candidate rollback, then hardware rollback/roll-forward with user data intact |
| P0.5 | Open | Configure and accept free Mo AI on a clean account | valid OpenRouter key entered through Settings; Arabic/English reply; reboot persistence; provider failure UI |
| P0.6 | Open | Promote only the proven digests and update the physical PC | signed origin, exact version/digest, zero failed units, full post-update check |

bootc stages updates without changing the running deployment and exposes an
explicit rollback verb.^3 MoOS already builds on this behavior; P0.4 tests it
instead of inventing another updater. The current update lock and edition-switch
preservation must be exercised during P0.2.

### P1 — Reliability and first-run platform

| ID | Task | Exit evidence |
| --- | --- | --- |
| P1.1 | Make every first-boot migration versioned, idempotent and transaction-safe | interrupted/repeated migration fixtures; clean account and upgraded account reach identical owned state |
| P1.2 | Add boot-success health and automatic fallback design compatible with the actual boot loader | three failed-boot simulation; successful boot blessing; manual rollback remains available |
| P1.3 | Make offline installer storage policy hardware-safe | SATA/NVMe/USB/eMMC fixtures; target-only mutation; encryption decision; low-space and firmware errors are actionable |
| P1.4 | Build a redacted support bundle | digest, edition, hardware, failed units and bounded logs; automated secret/identifier rejection |
| P1.5 | Establish update observability | one state machine for current/checking/downloading/staged/rebooted/rolled-back/failed; UI and journal read the same source |
| P1.6 | Qualify first-run without internet | Store metadata, dictionaries, locale, drivers and Help remain useful; cloud-only features explain connectivity clearly |

Automatic boot assessment is a useful reference: a boot is marked good only
after explicit health units succeed, and repeated failures can select the prior
entry.^4 The implementation must fit MoOS's real GRUB/bootc layout; do not copy a
systemd-boot recipe without proving compatibility.

### P2 — One desktop experience

| ID | Task | Exit evidence |
| --- | --- | --- |
| P2.1 | Move Updater, Recovery and Remote control center onto the shared UI2 component/token layer | live dark/light 4K captures; no private palette implementation |
| P2.2 | Make Settings the front door for themes, updates, recovery, devices, Remote and AI providers | standalone launchers become tested deep links; no duplicate authority |
| P2.3 | Create one locale authority for Arabic, English and German | every first-party app, date/number format and keyboard follows one selection after login/reboot |
| P2.4 | Complete keyboard and screen-reader operation | primary flows traversed with real keys; Orca reads Arabic and English; focus never disappears |
| P2.5 | Run the visual matrix | 1080p–4K, 100–250%, RTL/LTR, light/dark, reduced motion; measured contrast and no clipping |
| P2.6 | Remove remaining retired UI names/assets and enforce reachability | generated asset manifest; every shipped asset has a runtime/generator/test consumer |

Plasma 6 has no LTS branch and follows feature plus patch-release cycles.^1
MoOS therefore tracks stable releases through the shared base, keeps local
patches minimal, and runs its integration matrix on every Plasma transition.

### P3 — Mo AI as a trustworthy system operator

| ID | Task | Exit evidence |
| --- | --- | --- |
| P3.1 | Make provider setup self-diagnosing | distinguish missing key, invalid key, quota/billing, rate limit, outage and network failure without exposing secrets |
| P3.2 | Stream chat responses and show the answering model/provider in human language | measured first-token latency; cancellation and retry work |
| P3.3 | Generate native tool schemas from the `moai-do` allowlist | no UI/router/executor drift; ≥95% correct action selection on fixed Arabic/English cases |
| P3.4 | Use explicit confirmation cards and execution readback | model proposes; user confirms; fixed executor acts; result is re-read from the owning subsystem |
| P3.5 | Add free-provider health and bounded failover | zero-price policy enforced; unhealthy route cooldown; no silent paid fallback |
| P3.6 | Add optional, redacted device context | clear consent; inspectable payload; secret and personal-path rejection tests |

No model text becomes a shell command. No provider key crosses to another
provider. A free route that requires billing is treated as unavailable, not as
a successful configuration.

### P4 — Applications and compatibility

| ID | Task | Exit evidence |
| --- | --- | --- |
| P4.1 | Unify every install/update/remove request behind Mo Store | UI, Mo AI and URL routes share job IDs, progress, cancellation and readback |
| P4.2 | Audit desktop-app permissions and prefer portals | permission inventory; file/camera/screen/print flows work without broad filesystem or bus access |
| P4.3 | Turn Windows compatibility into a per-app runner product | isolated prefix per app; install/launch/reopen/update/remove for ten published test apps |
| P4.4 | Turn Android compatibility into a per-app product | on-demand container; launcher/files/clipboard/audio; ten test apps on Intel/AMD and NVIDIA fallback |
| P4.5 | Publish a generated compatibility matrix | supported/experimental/unsupported status names edition, architecture, GPU and tested version |

Flatpak sandboxes deny host access by default and portals provide controlled
access to files and services.^5 MoOS should keep per-user app development and
testing isolated; drivers and privileged services do not belong in a Flatpak.^6

### P5 — Hardware, performance and form factors

| ID | Task | Exit evidence |
| --- | --- | --- |
| P5.1 | Hardware qualification lab | repeatable GPU/audio/Wi-Fi/Bluetooth/camera/storage/firmware suite and published device records |
| P5.2 | Laptop policy | lid, brightness, battery health, power profiles and two suspend cycles on at least three platforms |
| P5.3 | Touch/tablet policy | automatic mode, ≥44 px targets, keyboard, rotation, gestures and stylus on real hardware |
| P5.4 | Performance budgets | boot, idle CPU/PSS/wakeups, app launch p95, scroll/frame pacing, build load and AI latency per tier |
| P5.5 | Cloud desktop efficiency | encode CPU/GPU, frame pacing, bandwidth degradation, reconnect, multiple accounts and audio sync |
| P5.6 | Storage lifecycle | update headroom, Flatpak/container cleanup, log bounds and low-space recovery without deleting user data |

### P6 — Release engineering and long-term trust

| ID | Task | Exit evidence |
| --- | --- | --- |
| P6.1 | Resolve immutable base inputs once per release | recorded x86 and ARM base digests; all edition jobs consume them |
| P6.2 | Produce SBOM and provenance for each image | signed attestations linked to exact digest and source SHA |
| P6.3 | Align ARM rebuild and promotion cadence | scheduled security rebuild; exact-image boot proof before tag movement |
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

Create `scripts/setup-development-machine.sh` in a dedicated task. It should:

- verify the signed MoOS origin and available disk space;
- install editor/SDK/debug tools in user sandboxes or Toolbx/Distrobox-style
  development containers where possible;
- configure Git and GitHub authentication interactively without storing tokens
  in the repository;
- install QEMU/KVM, image, accessibility, performance and network-debug tools
  through an auditable profile;
- verify Podman, `just`, Flutter/MoPlayer, .NET/MoRemote, QML and Python gates;
- generate a machine capability report without identifiers or secrets;
- be idempotent and support `--check` without mutation.

Do not layer compilers onto the immutable host merely for convenience. Do not
put API keys in `.env`, committed config, shell history or test fixtures.

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
