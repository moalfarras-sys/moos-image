# MoOS

MoOS is an atomic desktop operating system with its own identity, signed image
updates, a KDE Plasma 6 Wayland session, first-party system applications, Mo AI,
Mo Store, MoPlayer and Mo PC Remote. This repository is the single source used
to build the installable images; a local override is never a release.

## Start here

Read these files in order before changing the system:

1. [`skills/moos-engineering/SKILL.md`](skills/moos-engineering/SKILL.md) — the
   mandatory product and safety contract.
2. [`AGENTS.md`](AGENTS.md) — build, identity, privilege and hardware rules.
3. [`PROJECT_STATE.md`](PROJECT_STATE.md) — short, measured state of the current
   source and the physical development machine.
4. [`docs/DEVELOPMENT_PLAN.md`](docs/DEVELOPMENT_PLAN.md) — the only product
   development plan and ordered task queue.
5. [`RELEASE.md`](RELEASE.md) — the signed candidate, boot-proof and promotion
   contract.

Historical session logs, rejected mockups and screenshots do not live on
`main`. Git history is the archive. A fact enters `PROJECT_STATE.md` only when a
command, test, built artifact or physical-device check proves it.

## Editions

| Image | Target | Contract |
| --- | --- | --- |
| `moos` | General x86 desktop/laptop | Shared x86 base and adaptive hardware policy |
| `moos-nvidia` | NVIDIA x86 workstation | Same x86 base plus the exact-kernel NVIDIA layer |
| `moos-cloud` | Remote x86 machine | Remote-first profile with reduced local desktop work |
| `moos-arm` | Native aarch64/UTM/cloud | Native ARM base plus the same MoOS overlay |

The x86 editions must always share one base. The NVIDIA driver is layered; it
must match the image kernel and its required modules must be inside the final
initramfs. All published images are signed and installed systems enforce the
signature policy.

## Repository map

```text
Containerfile                 x86 image and NVIDIA/cloud variants
Containerfile.arm             native ARM image
build_files/                  image assembly and build-time gates
system_files/                 immutable MoOS filesystem overlay
artwork/                      canonical design sources and deterministic generators
moplayer/                     vendored MoPlayer source and tests
moremote/                     Mo PC Remote source and component documentation
iso/                          offline ISO inputs
tests/                        repository, image, VM and hardware verification
docs/DEVELOPMENT_PLAN.md      ordered product plan
PROJECT_STATE.md              current measured state only
RELEASE.md                    release/promotion contract
```

## Development workflow

Work on a branch for a coherent experience batch from the active milestone in
`docs/DEVELOPMENT_PLAN.md`. Establish source, live-machine and release state
first; preserve unrelated local edits. Implement related tasks together, run
focused checks while iterating, then `just check` before publishing. Review
visual changes on the running surface. Tier 1 boot/image changes require a
complete local image build; other UI changes share one build at milestone end.

```bash
just workstation-check     # read-only host/SDK capability inventory
just check
just build                 # generic x86
just build-nvidia          # NVIDIA x86
just build-cloud           # cloud x86
```

For the physical development machine, inspect the host from the VS Code
sandbox with `flatpak-spawn --host`. GUI programs must be launched through
`moai-open` so they survive the command session.

Record each finished task with:

- the exact behavior changed;
- tests and physical/artifact evidence;
- remaining risks or untested surfaces;
- `PROJECT_STATE.md` and the task status in
  `docs/DEVELOPMENT_PLAN.md` updated;
- source, live-review and release status separately. Continue the next
  unblocked task in the batch without waiting for another instruction.

The plan selects the batch, `AGENTS.md` defines engineering invariants,
`artwork/MOOS_UI2_DESIGN.md` defines MoOS UI, and `RELEASE.md` specifies
candidate proof and promotion. At batch end, merge reviewed source and freeze
one revision for `scripts/release-candidate.sh`. Do not start another candidate
while an existing release runner still owns that freeze.

## Release boundary

A successful local build is evidence, not a published release. The release path
is:

```text
source commit
  -> repository gates
  -> signed candidate digest
  -> exact-digest image checks
  -> QCOW2 boot/login/app proof
  -> offline ISO install and installed-disk proof
  -> edition-specific hardware proof
  -> promotion to the release tag
```

Never move a release tag because a build alone passed. Never weaken an identity,
initramfs, signature, route or runtime-loading gate to get a green result.

## Current status

See [`PROJECT_STATE.md`](PROJECT_STATE.md) for the measured installed version,
promoted revision, newer source, live Mo AI evidence and open hardware checks.
This entry point carries no duplicate release or readiness status.
