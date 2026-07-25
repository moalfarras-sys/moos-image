# This directory is a vendored copy of MoPlayer

The canonical source of MoPlayer lives in its own repository. What is here is a
**snapshot of it**, checked in the same way `moremote/` is, and for the same
reason: the image builds its first-party applications from source, in a
Containerfile stage, so that the shipped image contains the binary and nothing
that produced it — no SDK, no toolchain, no build cache.

```
moplayer/            ← this directory: the source, ~5 MB, no build artefacts
   ↓  Containerfile stage `moplayer-build` (Fedora 44 + Flutter + mpv-libs-devel)
/usr/lib/moplayer/   ← the ~40 MB Flutter bundle, and only that
/usr/bin/moplayer    ← the launcher, from system_files/
```

## Keeping it in sync

A vendored copy is a copy, and a copy drifts. Re-sync it from the MoPlayer
working tree with:

```bash
just sync-moplayer                       # from ../MoPlayerMoOS by default
MOPLAYER_SRC=/path/to/repo just sync-moplayer
```

That target copies exactly the files MoPlayer's own git tracks — so build output,
`.dart_tool/`, and the 20 MB `linux/flutter/ephemeral/` never land here.

## Why not a submodule

The canonical repository is public, but the OS image deliberately carries a
plain snapshot rather than making its build depend on a nested checkout. CI
receives one complete, auditable build context, and `just sync-moplayer` refuses
dirty source so untracked or half-committed code cannot produce a partial
snapshot. The OS commit then pins the exact copied tree without a submodule fetch
during the image build.

## What must NOT be edited here

Everything. Edit MoPlayer in the MoPlayer repository, run its own gate
(`just check` — analyze + test), then sync. A fix made only in this copy is a fix
that vanishes the next time anyone runs the sync.
