# =============================================================================
# MoOS Justfile — local inner-loop recipes (run inside WSL2 with podman 5.x)
# =============================================================================
# IMAGE builds are the ONLY thing supported locally/WSL2.
# ISO/disk-image recipes are deliberately ABSENT: ISO builds are CI-only
# (.github/workflows/build-iso.yml) because the osbuild/ISO tooling does not
# work on the WSL2 kernel. Offline fallback: a real Fedora VM in Hyper-V.
# CI owns ISO and disk-image production; these recipes are the local OCI loop.
# =============================================================================

image_name := "moos"
base_main := "ghcr.io/ublue-os/kinoite-main:44"

# List available recipes
default:
    @just --list

# The repo gates — the ones that read what is ABOUT to be shipped.
#
# These existed and nothing ran them. build.sh runs verify_image_experience.py inside the
# container, but the three tests under tests/ were honour-system: not in `just build`, not in
# the CI workflow. Every gate a session added ("a gate now guards this") could go red for
# weeks and no build would notice — which is the same failure AGENTS.md documents for the
# identity gate that ran before `set -e`. A gate that cannot fail a build is a comment.
#
# They run in seconds and need no container, so they go FIRST: a typo in a Konsole group name
# or a Mo AI button pointing at a command that does not exist should cost you 3 seconds, not a
# 20-minute image build.
check:
    bash -n build_files/build.sh
    python3 tests/verify_user_experience.py
    python3 tests/test_device_plan.py
    python3 tests/test_moai_do.py
    python3 tests/test_moai_control.py
    python3 tests/test_moai_workspace.py
    python3 tests/test_moai_hybrid.py
    python3 tests/test_moos_open_qdbus.py
    python3 tests/test_moai_http_security.py
    python3 tests/test_moai_gateway_streaming.py
    python3 tests/test_moai_credential_store.py
    python3 tests/test_moos_cloud_audio.py
    python3 tests/test_fwupd_refresh_policy.py
    python3 tests/test_exec_bits.py
    # CI never runs `npm run build`; the image ships the COMMITTED controller bundle, and
    # moremote/.gitignore hides the very directory it lives in. This catches an index.html
    # pointing at an asset that never made it into git — which serves a blank page with a 200.
    python3 tests/test_shipped_bundle_is_tracked.py
    python3 tests/test_release_workflow_safety.py
    # Troubleshooting reports must not commit an owner's phone number or an
    # allow-all phone-channel policy as though it were a safe product default.
    python3 tests/test_docs_privacy.py
    # The kernel half of "the remote feels slow": BBR must be both asked for and loadable, and
    # every key must exist on the kernel that will read it. Both failures are silent otherwise.
    python3 tests/test_kernel_network_tuning.py
    # Claim and recovery for a headless cloud account's PIN — both failures look like a healthy server.
    python3 tests/test_cloud_set_pin.py
    python3 tests/test_cloud_subid_range.py
    python3 tests/test_moai_ports_fail_closed.py
    python3 tests/test_openclaw_bootstrap_noop.py
    # A connect burst must coalesce into ONE pipeline build, and idle teardown must stay immediate.
    python3 tests/test_remote_rebuild_debounce.py
    python3 tests/test_remote_connection_lifecycle.py
    # Input must not block the socket that carries the pings the quality ladder measures.
    python3 tests/test_input_off_socket_thread.py
    # Raising the resolution ceiling must not change what an old cached client's `scale` means.
    python3 tests/test_remote_resolution_ceiling.py
    python3 tests/test_remote_h264_fallback.py
    # Desktop sound must be enabled everywhere AND bind loopback (the service has no auth).
    python3 tests/test_desktop_sound_reachable.py
    python3 tests/test_remote_audio_is_authenticated.py
    python3 tests/test_moos_store_index.py
    python3 tests/test_moos_storectl.py
    python3 tests/test_moos_ui2.py
    # Tidal Horizon is one generated silhouette and one portal contract across
    # the wallpaper family, Splash, Login, Lock, Logout and first-party apps.
    python3 tests/test_tidal_horizon.py
    python3 tests/test_tidal_portals.py
    python3 tests/test_moos_theme_safety.py
    python3 tests/test_moos_visual_system.py
    # MoOS Command Center is the owned settings front door: every visual command
    # must resolve through a fixed route, and its live status boundary stays
    # read-only, private and atomic.
    python3 tests/test_moos_settings.py
    # Protected app identities and the small-size icon ladder are separate from
    # the monochrome symbolic family and need their own proof.
    python3 tests/test_moos_app_icons.py
    # First-party GTK apps must follow all 16 live KDE schemes, and the remote
    # panel's three-second poll must never run subprocesses on GTK's main loop.
    python3 tests/test_moos_gtk_runtime.py
    # Recovery is where a broken update sends the user: its target, queued-state
    # copy, and non-blocking Polkit/bootc path belong in the local gate too.
    python3 tests/test_recovery_rollback_target.py
    python3 tests/test_moai_ports_fail_closed.py
    python3 tests/test_openclaw_bootstrap_noop.py
    # Owned first-party chrome must resolve to deterministic palette-aware SVGs,
    # never the retired fixed-colour action artwork or a missing icon name.
    python3 tests/test_moos_symbolic_icons.py
    # Exercise the real GTK/KDE resolver and librsvg raster path at the five
    # supported review sizes; static XML alone cannot catch a blank or clipped glyph.
    python3 tests/test_moos_symbolic_runtime.py
    # Mo AI's hand-drawn controls, modal exits, palette-driven ambient light and
    # every fixed-duration transition must remain keyboard/motion complete.
    python3 tests/test_moos_app_visual_polish.py
    # An Arabic user's terminal must stay legible: the fontconfig rule has to be
    # installed, Kawkab Mono must sit in JetBrains Mono's fallback chain, and
    # every Konsole profile must keep asking for JetBrains Mono by name so the
    # weak accept alias engages instead of detaching the cursive joins.
    python3 tests/test_arabic_terminal_font.py
    # OpenClaw's state DB needs SQLite 3.51.3+, and Fedora 44's system Node
    # (22.23.1) embeds the broken 3.51.2. The shipped systemd override must keep
    # pinning a SQLite-safe Node on the gateway's PATH, or replies silently drop.
    python3 tests/test_openclaw_nodejs_sqlite.py
    # Runs the motion gate in a REAL QML engine instead of grepping for it. Skips
    # cleanly where there is no Qt (the CI runner); the string half of the same
    # contract is in verify_user_experience.py and runs everywhere.
    python3 tests/test_moos_motion_gate.py
    python3 tests/test_cloud_private_desktop.py
    python3 tests/test_mo_remote_codec_resend.py
    python3 tests/test_remote_h264_fallback.py
    python3 artwork/verify_visuals.py
    # Same gate build.sh runs against the finished image, pointed at the tree that
    # is about to become it. Keeping it here means a drifted catalogue recipe or a
    # dead store route fails in seconds instead of at the end of an image build.
    MOOS_TEST_ROOT=system_files python3 build_files/verify_store_catalog.py

# Build the main MoOS image. The base is pinned in the Containerfile on purpose — both
# editions must share it (see the comment there); it is not a build-arg any more.
build: check
    # The base is rebuilt daily. Never validate a stale local tag, and never pull
    # the large NVIDIA stage for the generic image that cannot consume it.
    podman build \
        --pull=always \
        --build-arg IMAGE_NAME={{ image_name }} \
        --build-arg AKMODS_IMAGE=scratch \
        -t {{ image_name }}:latest \
        .

# Build the NVIDIA edition: the SAME base, with the driver layered on from ublue's akmods
# container. (It used to build FROM ghcr.io/ublue-os/kinoite-nvidia:44 — a tag upstream
# abandoned in May, which silently made the "NVIDIA image" ~589 packages older than the
# generic one.) The akmods tag is pinned to the base image's exact kernel: a kmod built for
# a different kernel does not load, and the machine boots to a black screen.
build-nvidia: check
    #!/usr/bin/env bash
    set -euo pipefail
    kernel="$(skopeo inspect docker://{{ base_main }} | jq -er '.Labels["ostree.linux"]')"
    echo "base kernel: ${kernel}"
    # `--pull=always` makes the Containerfile's base match the remote label used
    # above; otherwise a stale local base can pair kernel N with akmods N+1.
    podman build \
        --pull=always \
        --build-arg IMAGE_NAME={{ image_name }}-nvidia \
        --build-arg "AKMODS_IMAGE=ghcr.io/ublue-os/akmods-nvidia-open:main-44-${kernel}" \
        -t {{ image_name }}-nvidia:latest \
        .

# Build the CLOUD edition: the same tree, shaped for a VPS.
#
# No NVIDIA (a cloud VM has no card to layer a driver onto), no gaming stack, no
# Android layer; SSH enabled with keys only, a serial console so the provider's
# rescue shows the boot, and KWin effects off because llvmpipe renders on the CPU.
# Deployed with `system-reinstall-bootc` onto any VPS that offers Fedora — see
# MOOS_CLOUD_PLAN.md. It shares the base with the desktop editions on purpose: one
# identity, one gate suite, one signed update train.
build-cloud: check
    podman build \
        --pull=always \
        --build-arg IMAGE_NAME={{ image_name }}-cloud \
        --build-arg AKMODS_IMAGE=scratch \
        -t {{ image_name }}-cloud:latest \
        .

# Re-run the bootc lint against the built image (the Containerfile already
# runs it as the final build stage; this is for ad-hoc re-checks)
lint:
    podman run --rm {{ image_name }}:latest bootc container lint

# Remove locally built MoOS images
clean:
    -podman rmi -f {{ image_name }}:latest {{ image_name }}-nvidia:latest

# Re-vendor MoPlayer's source from its own repository.
#
# The image builds MoPlayer from source in a Containerfile stage (see
# `moplayer/VENDORED.md`), so this directory has to be a faithful copy of the app's
# tree. It copies exactly what MoPlayer's git tracks — never the 40 MB build
# output, never .dart_tool, never linux/flutter/ephemeral.
#
# And "what git tracks" is exactly why the working tree has to be clean first.
# `git ls-files` lists tracked files, so a NEW file that has not been committed is
# copied by nobody: the vendored tree gets the imports and not the file they point
# at, and the failure surfaces twenty minutes later, inside a container, as a Dart
# compile error about a URI that does not exist. That happened. A modified-but-
# uncommitted file is worse in a quieter way — the image would ship a build of
# source that exists on no branch, and nothing could ever reproduce it.
sync-moplayer:
    #!/usr/bin/env bash
    set -euo pipefail
    SRC="${MOPLAYER_SRC:-$(pwd)/../MoPlayerMoOS}"
    [ -f "$SRC/pubspec.yaml" ] || { echo "sync-moplayer: no MoPlayer tree at $SRC" >&2; exit 1; }

    DIRT="$(cd "$SRC" && git status --porcelain)"
    if [ -n "$DIRT" ]; then
        echo "sync-moplayer: MoPlayer's tree is not clean — refusing to vendor it." >&2
        echo "" >&2
        echo "$DIRT" >&2
        echo "" >&2
        echo "  A vendored copy is built from 'git ls-files'. An untracked file is" >&2
        echo "  copied by NOBODY, and the image then compiles source with a missing" >&2
        echo "  import; a modified one would ship a build of code that exists on no" >&2
        echo "  branch. Commit (or stash) in $SRC first." >&2
        exit 1
    fi

    REV="$(cd "$SRC" && git rev-parse --short HEAD)"
    echo "==> syncing from $SRC @ $REV"
    rm -rf moplayer.tmp && mkdir -p moplayer.tmp
    (cd "$SRC" && git ls-files) | while read -r f; do
        mkdir -p "moplayer.tmp/$(dirname "$f")"
        cp "$SRC/$f" "moplayer.tmp/$f"
    done
    cp moplayer/VENDORED.md moplayer.tmp/VENDORED.md
    rm -rf moplayer && mv moplayer.tmp moplayer

    # The launcher, the desktop entry and the icons are the app's, not the image's
    # — they live in MoPlayer's packaging/ and the image only carries a copy. Copy
    # it here rather than printing a reminder: a reminder is a step someone skips,
    # and the step that gets skipped is the one that drops the GPU-headroom guard
    # out of the launcher and lets the player abort on a full graphics card.
    install -D -m0755 moplayer/packaging/moos/moplayer system_files/usr/bin/moplayer
    install -D -m0644 moplayer/packaging/moos/org.moos.moplayer.desktop \
        system_files/usr/share/applications/org.moos.moplayer.desktop
    install -D -m0644 moplayer/packaging/moos/org.moos.moplayer.metainfo.xml \
        system_files/usr/share/metainfo/org.moos.moplayer.metainfo.xml
    # The ICONS are deliberately NOT copied any more.
    #
    # They used to be, on the same reasoning as the launcher: the app's art is
    # the app's. That stopped being true when MoOS grew one owned icon family —
    # `artwork/generate_moos_app_icons.py` renders moos-moplayer along with the
    # other eight first-party plates, so the shipped icon is MoOS's, not
    # MoPlayer's. Copying packaging/ over it silently reverted part of the
    # unified visual system to older art, and nothing said so: a re-vendor for a
    # one-line code fix would quietly change the dock icon. Caught exactly that
    # way on 2026-07-25, when syncing a keyring fix rewrote twelve PNGs.
    #
    # If MoPlayer's own icon changes and MoOS should follow, change it in the
    # generator and re-run it — that is the single source now.

    echo "==> vendored $(find moplayer -type f | wc -l) files ($(du -sh moplayer | cut -f1)) and installed its packaging"
    echo "    (icons NOT touched — MoOS generates moos-moplayer itself; see artwork/generate_moos_app_icons.py)"
