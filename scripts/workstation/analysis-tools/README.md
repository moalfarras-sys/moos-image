# Optional MoOS analysis workstation profile

REA6.7.0 and Ghidra12.1.4 are user applications. This profile reuses the existing
Node26.12.0 runtime and `moos-dev` Toolbx JDK25; it installs no host RPM or kernel
and changes no provider account or MCP client configuration. It supports this
x86_64 workstation profile, not every architecture.

`manifest.json` pins the official archive URLs, Ghidra size/SHA256, REA SHA512
integrity and the complete npm lock. Download the two named official archives,
then run from the repository:

```sh
python3 scripts/setup-analysis-tools.py --install \
  --ghidra-archive /path/to/ghidra_12.1.4_PUBLIC_20260921.zip \
  --rea-tarball /path/to/rea-agents-6.7.0.tgz
python3 scripts/setup-analysis-tools.py --check
```

An existing different launcher is a refusal. `--replace-launchers` explicitly
preserves its exact bytes in a private hash-named backup before replacement.
Links, unknown archive paths, digest/payload drift and changed dependency locks
remain refusals. npm lifecycle scripts are disabled. Optional native providers
such as Frida are not qualified by installing their package metadata.

Dependency updates at the same REA version use a separate directory named
`rea-6.7.0-sha256-<full reviewed lock SHA256>`. The installer renders the
`moos-rea` template to that exact generation and records both its identity and
lock in the profile receipt. An existing generation needs its own matching
receipt and must still pass the package/lock/archive checks; unknown directories
are refused. The original `rea-6.7.0` directory and earlier generations stay in
place so active consumers retain their files. Node, JDK and Ghidra stay shared.

To select a reviewed update, use the same install command with the two original
verified archives and `--replace-launchers`. This preserves the prior launcher
bytes before switching future launches; running REA processes continue with
their old generation. There is no automatic retirement or cache pruning. A
previous-launcher recovery remains tied to its retained prefix and original
receipt, rather than being accepted as the current profile.

Installation and checking hold an owned, nofollow profile lease. A concurrent
operation waits at most ten seconds, then reports busy without claiming a
completed check or publishing another generation. The lease covers package
verification, all launcher replacements, receipt publication and final readback.
`--check` opens an existing lease read-only and never creates a missing profile
or lock. A partially completed installation is a refusal until its exact
generation, launchers and receipt agree; it is never reported as installed.

`moos-rea` is the canonical CLI/MCP entry point. It supplies the native user bus
for a minimal MCP environment, crosses Flatpak/Toolbx as needed, uses the shared
Node/JDK and defaults headless Ghidra to2GiB. `moos-ghidra` opens the actual Java
GUI in the normal application cgroup, reading the primary display scale before
entering the SDK. Java rounded the tested2.5 scale to2.0: fractional GUI scaling
is not claimed exact. Its basic installed GUI journey now opens an owned project/program, displays decompiled `main` and closes normally. The original main frame was blank on Wayland; a scoped OpenJDK non-reparenting environment setting renders it, and restoring the original launcher reproduces the blank frame. The canonical launcher carries the host Wayland decision across Toolbx and preserves explicit caller values. Six native shell-boundary controls cover X11 absence, Wayland defaults, bridge state and argument/heap/scale preservation. This is a GUI-process setting, not a desktop-wide Java change; include the actual SDK Java process when measuring memory. Broader keyboard/server journeys and acceptance on the next OS boot remain open.

On the earlier V3 profile, adoption of both existing archive payloads, launcher installation and
read-only checks pass. All managed file bytes/mtimes remain unchanged during
`--check`. Actual canonical CLI and external MCP calls discover207 tools, check
the exact live package/catalog, open an owned ELF, decompile `moos_blend` and
close it. CLI/MCP pseudocode and input digest agree. This qualifies those calls,
not all207 tool journeys or paid/provider/account features. A running Codex
extension still needs its normal restart to discover the earlier local MCP
registration; this installer deliberately leaves that configuration alone.

The earlier fresh-helper test extracts Ghidra, installs174 locked npm packages,
and analyzes the same owned ELF through the canonical source launcher. Its
pseudocode matches the installed profile. Running both installer helpers again
preserves every file size/mtime; the temporary test payloads are then removed.
[Native qualification](native-qualification.json) records the precise scope.

The earlier direct SDK invocation refused process ownership cleanup with EACCES
under concurrent image builds. Its raw refusal is retained, no guard was
weakened, and none of its candidate PIDs remained after exit. The canonical
launcher passed under the same concurrent workload; this does not establish a
general cause or cure for arbitrary direct SDK/process-inspection calls.

The Oct27 security refresh overrides Zod to4.6.6 while retaining REA6.7.0.
This addresses GHSA-mrhx-c7xc-m3w5 for oversized constrained collections;
unbounded schemas still require application-level bounds. Remove the override
when the pinned REA dependency itself selects a qualified patched Zod.
The lock and its manifest digest advance together. Fresh locked installation,
npm audit with zero findings, CLI help/capabilities, normal Unicode object
validation and rejection before visiting an oversized constrained array pass.
This qualifies the updated source profile, not replacement of an already
running workstation REA process or the earlier Ghidra/MCP native journeys.

The Nov3 source refresh pins Glob14.0.2 and Minimatch11.0.1 for the published
cancellation and pattern-amplification advisories. On the existing private
121-directory control, old Glob13.0.6 rejects then performs117 more reads;
fixed14.0.2 performs none after rejection. Unicode FileList/Minimatch and
Electron ASAR roundtrip controls, fresh locked installation, actual CLI help
and registry audit0 pass; the manifest lock digest advances with the lock.
The running workstation profile is preserved. This source refresh is not an
installed profile replacement, a new SDK, or broader native-provider acceptance.

The generation installer has private old/fixed controls for lock upgrades, a
running old reader, unknown generations, exact recovery, unchanged read-only
checks and concurrent install/check publication. On Nov3 the original archives
match the existing installed Ghidra and spare REA payloads; the spare dependency
tree passes the exact reviewed lock. A rendered private launcher reaches actual
REA CLI help through the shared Node/SDK, with the live launcher, receipt and
legacy lock bytes/mtimes unchanged. This reuses dependencies through private
links and does not qualify a full native installation or another Ghidra/MCP
journey. No running workstation launcher or profile was replaced.

The original versioned archives under
`~/.cache/moos-dev-platform/analysis-archives/` remain inputs for the next
verified installation and retained-profile recovery. Keep them while those
consumers need them; retirement requires a separate recovery/retention review.
This installer does not download or remove either archive.
