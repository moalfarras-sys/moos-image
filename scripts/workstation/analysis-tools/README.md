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

`moos-rea` is the canonical CLI/MCP entry point. It supplies the native user bus
for a minimal MCP environment, crosses Flatpak/Toolbx as needed, uses the shared
Node/JDK and defaults headless Ghidra to2GiB. `moos-ghidra` opens the actual Java
GUI in the normal application cgroup, reading the primary display scale before
entering the SDK. Java rounded the tested2.5 scale to2.0: fractional GUI scaling
is not claimed exact. Its first-run agreement remains owner onboarding.

On the V3, adoption of both existing archive payloads, launcher installation and
read-only checks pass. All managed file bytes/mtimes remain unchanged during
`--check`. Actual canonical CLI and external MCP calls discover207 tools, check
the exact live package/catalog, open an owned ELF, decompile `moos_blend` and
close it. CLI/MCP pseudocode and input digest agree. This qualifies those calls,
not all207 tool journeys or paid/provider/account features. A running Codex
extension still needs its normal restart to discover the earlier local MCP
registration; this installer deliberately leaves that configuration alone.

The actual fresh-helper test extracts Ghidra, installs174 locked npm packages,
and analyzes the same owned ELF through the canonical source launcher. Its
pseudocode matches the installed profile. Running both installer helpers again
preserves every file size/mtime; the temporary test payloads are then removed.
[Native qualification](native-qualification.json) records the precise scope.

The earlier direct SDK invocation refused process ownership cleanup with EACCES
under concurrent image builds. Its raw refusal is retained, no guard was
weakened, and none of its candidate PIDs remained after exit. The canonical
launcher passed under the same concurrent workload; this does not establish a
general cause or cure for arbitrary direct SDK/process-inspection calls.
