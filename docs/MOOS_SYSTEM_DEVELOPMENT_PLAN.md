# MoOS system development plan

Status: active, 2026-09-05. This supersedes the product-scope statement in
`MOOS_X86_SYSTEM_PLAN.md`; that file retains historical x86 measurements.
Evidence and open gates, not ambition, determine release status. Read alongside
`PROJECT_STATE.md`, `MOOS_ROADMAP.md`, the engineering skill and `AGENT_HANDOFF.md`.

## Product boundary and architecture

MoOS owns the complete user experience: installation and identity, session,
settings, application discovery, hardware policy, Remote, signed updates and
recovery. It builds on Linux, bootc/OSTree and KDE instead of replacing mature
components. Being a complete OS product does not require inventing a new kernel
or claiming binary compatibility with every other operating system.

One source tree and common MoOS overlay serve four editions:

| Edition | Target | Hardware foundation | Experience policy |
| --- | --- | --- | --- |
| moos | General x86 PC/laptop | Shared x86 base, upstream kernel/drivers | Adaptive local desktop; touch, keyboard and pointer |
| moos-nvidia | x86 NVIDIA workstation/gaming | Same x86 base, exact-kernel signed driver | Rich effects only on proven hardware; safe rollback |
| moos-cloud | x86 VPS/private desktop | Same x86 base, cloud role | Remote first, private transport, quiet background services |
| moos-arm | Native aarch64, including Oracle A1 | Native ARM bootc base, common MoOS overlay | Capability-detected local or virtual desktop |

Do not create a separate OS fork for every user category. Offer reversible
profiles (everyday, development, media/gaming, remote) through the existing
settings authority. A profile selects apps and workload policy; it does not
change architecture, silently install drivers, or switch a signed origin.
UTM remains a separately validated packaging target of ARM, not an additional
unconditionally supported edition. ARM currently does not use the x86-only
upstream image. The shared `:44` tags are mutable build inputs; locking release
inputs is still an explicit task below.

## Principles borrowed from mature systems

- Apple's [signed system volume](https://support.apple.com/guide/security/signed-system-volume-security-secd698747c9/1/web/1)
  illustrates treating system integrity as a product property. MoOS already
  enforces signed image origins; the next proof is update and rollback behavior,
  not a claim that its implementation equals Apple's secure boot chain.
- Android's [A/B update model](https://source.android.google.cn/docs/core/ota/ab?hl=en)
  preserves a bootable system during updates. For MoOS, test the existing
  bootc/OSTree deployment and rollback path rather than inventing another updater.
- Microsoft's [driver qualification](https://learn.microsoft.com/en-us/windows-hardware/drivers/dashboard/driver-signing-offerings)
  combines signing with reliability and hardware testing. MoOS needs its own
  published compatibility matrix; a package installed or a VM boot is insufficient.

These references inform engineering priorities. No comparative speed, security
superiority or universal hardware support has been demonstrated.

## Current measured baseline

Oracle A1: two CPU cores, about 11.6 GiB RAM, 200 GiB boot volume, 1920×1080
virtual desktop. KWin reports VirtualBackend/llvmpipe. At this audit snapshot,
RAM usage was 3.9 GiB and available RAM 7.7 GiB after builds stopped; swap held
2.7 GiB of older pages. Cache/free counters are not a memory leak. Do not run
swapoff or drop caches as cosmetic optimization.

Largest individual resident processes were VS Code (~463 MiB top process),
Plasma (~325 MiB), KWin (~278 MiB), plus browser and editor subprocesses. RSS
is not additive physical memory because processes share pages. A 10-second
sample during a live Remote session and launcher inspection measured KWin at
96% of one core and the portal helper at 21.6%; this is an active workload,
not an idle baseline. With only two cores, software composition/encoding is
an important target. No speculative service removal or claimed speedup follows
from that sample.

Live fixes in this pass:

- Clock synchronized but zone was UTC. Set this owner's machine to Europe/Berlin;
  verified NTP and summer offset +02:00. Keep cloud default UTC unless the owner
  chooses a zone; server location alone must not dictate every user's clock.
- Arena theme selected, but the live desktop still used Graphite wallpaper.
  `moos-theme wallpaper-reset` restored the active profile's Arena canvas through
  the existing transactional owner; the old state remains in theme recovery.
- Remote v39 improves phone glass controls, Arabic and clipboard/keyboard geometry;
  the owner confirmed keyboard-bar visibility in both orientations. See its report.
- DRM `virtio-pci` was misclassified as integrated graphics. The fix keeps virtual
  2/4/8-core Oracle hosts essential while preserving real GPU classifications.
  The actual host already had blur and animations off; this prevents a regression
  after CPU expansion and does not claim a present frame-rate improvement.
- A legacy local Remote override disabled restart limits. Restored the shipped
  bounded policy, retaining the old override for diagnosis.
- VS Code could not find a project .NET SDK. Existing verified ARM SDK 10.0.400
  moved into persistent user data and paths were configured. Host and sandbox
  both list it. Current VS Code was not reloaded mid-session; extension activation
  remains a next-window check.
- Flatpak updater reports no remaining updates. Native apps change through the
  signed image; do not mutate the installed immutable base with package hacks.

## Execution order

Each item is a bounded change with its own acceptance evidence. A later agent
must pick one item, record scope and preserve unrelated work.

| ID | Priority / state | Concrete work | Closure evidence |
| --- | --- | --- | --- |
| S01 | P0 implemented | Finish v39/keyboard/AppStream integration | Source tests, native ARM build/lint, exact image byte comparison, PR/release digest and post-boot result separately recorded |
| S02 | P0 implemented, integration pending | Correct virtual GPU classification and post-update edition/digest diagnosis | Regression must fail before fix; live probe; same-architecture image build; expected digest check after boot |
| R01 | P0 open | Revalidate NVIDIA modules after the final dracut rewrite | Required modules and exact kernel in final initramfs; deliberately omit module and prove gate fails; real NVIDIA boot kept separate from virtio VM proof |
| R02 | P0 open | Resolve approved upstream base digest once per release | One immutable x86 input shared by three jobs and driver preparation; separate explicit ARM digest; preserve repository allowlist; source-tag movement test |
| R03 | P0 open | Align ARM security rebuild cadence and promotion contract | Scheduled ARM rebuild, all source gates, signed exact artifact, boot proof before release tag promotion; failed boot cannot publish |
| R04 | P0 open | Prove interrupted update and deliberate rollback | Disposable VM first, then authorized hardware with recovery access; previous signed deployment boots; app/user data preserved |
| U01 | P1 open | First-run locale, timezone and keyboard | User selects language/zone independent of server geography; live clock/input readback, DST and offline setup fixtures; custom settings persist across updates |
| P01 | P1 authority landed, consumers + measurement open | Capability-based workload budget. `moos-visual-tier` now derives `budget` (file_indexing, update_concurrency, ai_default, remote_encode) from the same probe and exposes it in `--json`/state — advisory, no second writer. Remaining: wire baloo / `moai-do` / Remote encoder to read it, each under its own owner. | Measure idle, typing, scroll/video, build and AI separately; compare frame/input p50/p95, CPU, memory and network before/after on identical workload |
| P02 | P1 open | Cloud capture/compositor efficiency | Bound software-rendered quality via measured capability, not only network RTT; test frame pacing, cursor, degraded link, reconnect and local GPU path; explicit quality override retained |
| D01 | P1 existing visuals, remaining proof | Bar/launcher hierarchy and keyboard flow | One panel; reachable 44px equivalent targets; no clipped RTL/long labels; complete keyboard navigation; 1080p through 4K at 100–225%; light/dark screenshots and measured contrast |
| A01 | P1 open | Application/runtime compatibility matrix | Native Linux/Flatpak apps install-launch-use-reopen-remove; ARM availability explicit; development SDK inside its actual sandbox; Windows compatibility tested per app, never promised globally |
| H01 | P1 open | Hardware qualification | Per-model GPU/audio/Wi-Fi/Bluetooth/camera/suspend/dock/multi-monitor and firmware tests; exact image/kernel/driver versions; publish supported/experimental/unsupported status |
| I01 | P1 open | Installer and recovery qualification | Exact signed ISO offline installation to a blank disk, detach ISO, first login, reboot and poweroff; physical firmware separate from VM proof |
| Q01 | P2 open | Release observability and support bundle | Explicit opt-in, redact secrets/identifiers, bounded logs, enough digest/device/health facts to reproduce; diagnostics never execute model-generated privileged commands |

R01 is a proof gap found in `build_files/build.sh`: NVIDIA checks around lines
573–585 precede the final dracut rewrite around 3487. It is not evidence the
current driver is absent. Treat the repair as a boot-sensitive change with its
own build and negative gate test. Do not weaken existing tests to implement it.
R03 is a cadence mismatch: x86 has a daily schedule, ARM does not. A safe release
scheduler must preserve the current signature and artifact ordering contracts.

## Performance policy to implement and validate

For Oracle/virtual rendering, retain a still wallpaper, no costly blur, on-demand
AI models, bounded background update/build work, and adaptive Remote encoding.
Keep PipeWire/portal/desktop services needed by the primary screen alive. Do not
remove a service merely because it has a desktop-oriented name. Index only
intended user locations; exclude build/container caches through the indexer's
existing policy after proving they are actually indexed.

For a local GPU machine, retain the same visual language with hardware-scaled
blur (never above the existing strength limit), measured animations, HiDPI and
battery-aware behavior. CPU core count alone cannot justify effects; honor user
choices and fall back gracefully. Do not copy Oracle's no-animation override
onto every laptop or workstation.

Proposed regression budgets are targets, not achieved benchmarks: no unexplained
idle CPU regression above one core-percent or idle PSS growth above 10% on the
same machine; no loss of input, stuck held keys or stale clipboard paste; no
quality promotion triggered solely by low loopback RTT. Define and capture the
actual workload before choosing absolute frame/latency targets.

## What is preserved, retired or not merged

- Preserve the previous signed boot deployment, current Oracle pre-resize backup,
  and the last working Remote executable until the replacement is boot-verified.
- Stop disposable browser/Vite/test services after evidence capture. Do not delete
  user apps, personal files or all container caches as a shortcut to lower usage.
- `fix/remote-control-audit-20260904` is contained in main via PR 72.
- `archive/arm-utm-20260827` has 18 commits outside main, affecting boot/UTM/build
  code, not Remote. Some useful behavior was recovered independently; maintain
  semantic disposition before any cherry-pick. Preserve the archive.
- Retire local `/etc`/home overrides only after verifying the signed image contains
  their behavior. Active app overrides can hide future signed fixes indefinitely.

## Release definition

A release record binds source SHA, upstream base digest, built digest, signature,
edition/architecture, source tests, exact-image checks, boot/login/app evidence,
update/rollback results and known exclusions. “Built”, “locally deployed”,
“published”, “staged” and “booted” are separate states. A complete build is not a
claim that every application and hardware combination is free of defects.
