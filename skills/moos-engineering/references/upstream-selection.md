# Upstream selection for MoOS

Read for a new dependency, compatibility engine, visual/performance proposal or
whole-product plan. This is a decision reference; tasks and acceptance targets
stay in [the product plan](../../../docs/DEVELOPMENT_PLAN.md). Primary sources
were reviewed on2026-10-28. Links describe upstream capability, not MoOS support
or a version pin. Recheck the exact installed and proposed versions when acting.

## Extend established owners first

| Component / primary source | MoOS decision and integration boundary | Evidence before extending its use |
| --- | --- | --- |
| [KWin](https://github.com/KDE/kwin), [Kirigami](https://github.com/KDE/kirigami), [adaptive components](https://api.kde.org/kirigami-index.html) | Keep Plasma/KWin/Qt as compositor, shell and native control owners. Adapt existing MoOS components through shared tokens, not a second shell or toolkit rewrite | Actual parent build, loaded module path, native input/window journey and compositor/frame evidence |
| [KDE HIG](https://develop.kde.org/hig/) and [accessibility](https://develop.kde.org/hig/accessibility/) | Apply native navigation, focus and accessibility alongside the MoOS Liquid Glass contract; preserve recognizable MoOS identity | Keyboard-only, pointer/virtual-keyboard, screen-reader, large-text, contrast and real tablet journeys |
| [Flatpak permissions/portals](https://docs.flatpak.org/en/latest/sandbox-permissions.html), [xdg-desktop-portal](https://github.com/flatpak/xdg-desktop-portal) | Reuse the Store lifecycle and installed KDE portal backend. Prefer scoped access through file/URI/camera/screen/print portals to blanket filesystem/session-bus grants | Actual allow/deny/cancel and persistence on the canonical app/URI route; runtime update must preserve running applications |
| [Wine](https://www.winehq.org/about), [Bottles](https://github.com/bottlesdevs/Bottles) | Keep the registry-selected Windows route and per-app state. Wine implements Windows compatibility; a prefix alone provides no sandbox. Do not install another runner merely because it is available | Exact app/runtime/32-or64-bit/GPU/isolation, real window and data lifecycle, upgrade/prefix recovery; architecture failures remain visible |
| [Waydroid](https://github.com/waydroid/waydroid), [APK/ABI constraints](https://docs.waydro.id/usage/install-and-run-android-applications), [GPU fallback](https://docs.waydro.id/faq/get-waydroid-to-work-through-a-vm) | Extend the existing on-demand Android service and Store adapter. Keep system/vendor provenance and APK ABI explicit; software rendering on unsupported GPUs is a separately measured path | Render/input/files/audio/clipboard/window lifecycle, cold start and suspend; RUNNING or boot-completed is insufficient. No unreviewed translation blobs or licence/DRM bypass |
| [HarfBuzz](https://github.com/harfbuzz/harfbuzz), [fontTools](https://github.com/fonttools/fonttools) | Continue the checked-in Meyar derivative and build tools. Preserve upstream licences/native shaping and extended-script fallback | Reproducible font bytes plus native editor/terminal joining, marks, cursor/cells, fallback and actual generic default; a glyph sheet is insufficient |
| [fwupd](https://github.com/fwupd/fwupd), [LVFS delivery](https://lvfs.readthedocs.io/en/latest/download.html) | Use existing firmware/device owners and vendor-supported updates. Keep power profiles and administrator masks; do not add a competing daemon | Exact device/firmware support and policy, safe staging/recovery and post-update operation; a missing probe is unknown, not healthy |
| [bootc](https://github.com/bootc-dev/bootc), [cosign](https://github.com/sigstore/cosign) | Retain immutable delivery and installed signature enforcement under RELEASE.md. Do not substitute a new updater/key policy | Exact signed source/digest/artifact/boot/promotion linkage and working rollback; SBOM work uses separately budgeted P6.2 workflow |

KDE's canonical development repositories are on Invent; its GitHub mirrors were
accessible during this review when the Kirigami Invent page returned403. Resolve
the upstream commit/provider from the actual source manifest before patching.
Use the project's existing source/licence manifests for Meyar's upstream inputs;
do not replace them with a different font downloaded from this reference.

## Conditional additions, through the same product path

- [Valve Proton](https://github.com/ValveSoftware/Proton) is the candidate for
  Steam-managed Windows games, not a blanket default for all Windows software.
  Qualify the actual game and selected runtime under P4.3/P4.5. Steam's client,
  game licences, DRM and anti-cheat support remain separate requirements.
- [DXVK](https://github.com/doitsujin/dxvk) and
  [vkd3d-proton](https://github.com/HansKristian-Work/vkd3d-proton) provide
  Direct3D-to-Vulkan paths. Prefer components managed by the selected runner;
  record exact Vulkan/driver requirements and GPU readback. Do not globally
  inject DLLs, fetch moving builds or make a software fallback invisible.
- [FEX](https://github.com/FEX-Emu/FEX) is a research option for x86/x86-64
  user-mode execution on ARM64, only if a named missing application justifies
  P4/P5 investigation. It adds a separate compatibility/rootfs/graphics cost;
  it does not qualify Android ARM-only APKs on x86 or all Windows apps on ARM.
  Keep it optional until provenance, isolation, update/removal and native-device
  performance pass. No default enablement follows from this plan.

For unsupported professional apps, drivers or games, preserve the unsupported
result and offer a qualified alternative where useful. Full guest virtualization
is a separate resource/licensing/product decision, not a hidden fallback or a
reason to build local VM images instead of testing the installed workstation.

## Use diagnostic tools to answer one measured question

- [Qt Quick performance guidance](https://doc.qt.io/qt-6.11/qtquick-performance.html)
  and [QML Profiler](https://doc.qt.io/qt-6.11/qtquick-profiling.html): find costly
  bindings, GUI-thread work and rendering before changing effects. Match docs
  to the installed Qt branch, retain tracing overhead in the receipt, and scope
  debugging to a private development process. Never ship an open debug endpoint.
- Use existing `systemd-analyze`, bounded journal/cgroup/PSS sampling and native
  compositor/scenegraph traces to separate boot, launch, CPU and GPU delays.
  A graph or timer average is not a successful session or presentation trace.
- [Kernel PSI](https://docs.kernel.org/accounting/psi.html) supplies CPU/memory/IO
  pressure evidence. Correlate it with the named workload and thermal/power
  state; do not infer a scheduler or memory-policy change from one busy sample.
- Reuse the existing SDK/Toolbx, native font tools and review harnesses. Check
  `docs/MCP.md` before proposing another connector. Install a missing development
  tool only for a named task/consumer; avoid duplicate SDKs, host layering,
  background telemetry and unbounded traces.

## Admission and maintenance record

Attach a small decision to the existing P-row/PR: user-visible benefit and
reproduced gap; options including the current implementation; chosen native
owner; upstream URL and immutable version/hash/signature; licences/redistribution
and notices; dependencies and image/download/RAM costs; supported ABI/GPU;
privilege/data boundaries; failure/update/uninstall/recovery; responsible owner
and upstream maintenance path. Check the exact dependency's licence files,
including submodules and binary redistributions, rather than a repository badge.
Stage optional components on demand. Update the registry/matrix and both
architecture build paths only after the corresponding admission evidence exists.

Prefer a small upstreamable fix at a measured seam. A local fork needs a bounded
patch set, upstream tracking, security-update owner and retirement condition.
Keep previous failure evidence and reject unknown input drift; never expand a
version/digest allowlist or remove a gate just to accept an upstream update.
