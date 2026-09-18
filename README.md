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
moplayer/                     first-party MoPlayer source and tests
moremote/                     Mo PC Remote source and component documentation
iso/                          offline ISO inputs
tests/                        repository, image, VM and hardware verification
scripts/release-candidate.sh  one command per release batch: signed build, every boot proof, promotion
scripts/review/               off-station tools: run the gates on a mirror, render a first-party app from source
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

Away from that machine (any Linux box, or Windows with a Fedora WSL2 distro):
`scripts/review/setup-review-distro.sh` installs the toolchain,
`scripts/review/mirror-gates.sh` runs the gates on a mirror with git's file
modes, and `scripts/review/render-app.sh <app> out.png` draws a first-party
app from source with a real MoOS colour scheme and prints its QML binding
errors, and `scripts/review/render-desktop.sh out.png --lang=ar` brings up the
real `plasmashell` with MoOS's shipped layout, scene and plasmoids under Xvfb.
Render at the size the window really opens at. Both are source-harness
evidence (no GPU compositing: no blur, no KWin effects, X11 not Wayland); neither
is a desktop review, and the plan says which is owed.

A pull request that touches `Containerfile`, `build_files/` or `system_files/`
builds the generic x86 image and runs every in-image gate before the merge
(`.github/workflows/pr-image-gates.yml`; nothing is pushed or signed). Wait for
it. `main` holds one long-lived branch: merge with a merge commit, delete the
topic branch, and keep nothing half-merged.

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

## Taking over from another agent or person

1. `git log --oneline -15` and `gh pr list` — what landed last and what is open.
2. [`PROJECT_STATE.md`](PROJECT_STATE.md) — what production really is (it quotes the
   registry read-back), what has never been seen on a MoOS desktop, and "Next
   execution".
3. [`docs/DEVELOPMENT_PLAN.md`](docs/DEVELOPMENT_PLAN.md) — the wave table says
   what each wave delivered and its release state; "Station review owed" is the
   ordered checklist for the first session after an update; rows marked **Owner
   decision** are not yours to take.
4. Read the registry, not a document, before you claim a version:
   `skopeo inspect docker://ghcr.io/moalfarras-sys/moos-nvidia:latest`.
5. An installed MoOS updates through the MoOS Updater (origins are digest-pinned,
   so `bootc upgrade` answers "no changes" forever).
6. More than one agent works here at once, on different machines:
   [`docs/AGENT_COORDINATION.md`](docs/AGENT_COORDINATION.md) says who holds which
   files. Claim files, not tasks; touch only your own rows of the shared documents;
   `git fetch` before every push and expect to rebase.
7. A change a person can see or do ships with its line in
   `system_files/usr/share/moos/whats-new.json` — that is how MoOS tells the owner
   what an update brought (Settings → System → What's new, and one notification at
   the first login on a new version).

## Current status

See [`PROJECT_STATE.md`](PROJECT_STATE.md) for the measured installed version,
promoted revision, newer source, live Mo AI evidence and open hardware checks.
This entry point carries no duplicate release or readiness status.
