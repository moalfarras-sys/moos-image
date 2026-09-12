#!/usr/bin/env bash
# The repository gates: every check that needs nothing but a checkout, python3 and bash.
#
# WHY THIS IS A SCRIPT AND NOT A WORKFLOW STEP
#
# This list used to live inside build.yml's `build-push-sign` job — the job that builds, pushes
# and signs three images. That job runs only on `push: branches: [main]`, on the schedule, and on
# workflow_dispatch. So on a BRANCH or a PULL REQUEST none of these gates ran at all, and the only
# pre-merge signal was the ARM image build, which takes twelve minutes on a good day and up to
# three hours on a bad one.
#
# What that cost, on 2026-09-12 alone:
#
#   * a shared C# file missing from one of seven .csproj lists — twenty-five minutes of ARM image
#     build to report one line of missing XML;
#   * `tests/test_device_plan.py` reading the HOST's CPU while simulating an x86 NVIDIA desktop,
#     so it passed on every CI runner and failed on the maintainer's own aarch64 machine;
#   * `tests/test_moai_free_policy.py` reading the owner's LIVE Mo AI provider selection, so the
#     free-only boundary was asserted against whatever that person had chosen.
#
# The last two are worse than a slow signal: `just check` is what AGENTS.md tells every
# contributor to run before pushing, and two of its gates could not pass on the machine this
# project is built for. A gate that only passes on a runner teaches people that red means nothing.
#
# One list, two callers: build.yml still runs it before it signs anything, and repo-gates.yml runs
# it on every pull request in about half a minute. tests/test_gate_coverage.py reads this file as
# well as the workflows, so `just check` still has to be a superset of all of it.
set -euo pipefail
cd "$(dirname "$0")/.."

bash -n build_files/build.sh
python3 tests/test_shell_line_continuations.py
python3 tests/test_usr_local_layout.py
python3 tests/test_image_state.py
python3 tests/test_settings_hardware_identity.py
python3 tests/test_theme_drift_repair.py
python3 tests/test_moai_severity_banner.py
python3 tests/verify_user_experience.py
python3 tests/test_device_plan.py
python3 tests/test_moai_do.py
python3 tests/test_moos_control.py
python3 tests/test_moos_health.py
python3 tests/test_moai_krunner.py
python3 tests/test_foreign_app_menus.py
python3 tests/test_remote_cuda_scaler.py
python3 tests/test_app_qml_identity.py
python3 tests/test_moos_auto_update.py
python3 tests/test_updater_trust_badge.py
python3 tests/test_cloud_console_order.py
python3 tests/test_oracle_deploy.py
python3 tests/test_theme_wallpaper_readback.py
python3 tests/test_theme_wallpaper_steady_state.py
python3 tests/test_mokernel.py
python3 tests/test_moai_control.py
python3 tests/test_moai_config.py
# Mo AI's brain is a cloud API and nothing is ever downloaded to the
# machine. Free, no-card providers must exist and come first.
python3 tests/test_moai_cloud_only.py
# No externally reachable moai-do action may START a local engine.
# install-openclaw still called setup_brain_impl after do_setup_brain
# was guarded — and Mo AI can name install-openclaw.
python3 tests/test_moai_no_local_start_path.py
python3 tests/test_moai_free_policy.py
python3 tests/test_moai_hermes.py
python3 tests/test_moai_workspace.py
python3 tests/test_moai_hybrid.py
# moos-open's session/logout and session/power hardcoded `qdbus6`, absent on Plasma 6
# (which ships qdbus-qt6), so they confirmed then silently did nothing. This asserts the
# qdbus_run resolver finds qdbus-qt6 and the session routes use it.
python3 tests/test_moos_open_qdbus.py
python3 tests/test_moai_http_security.py
# The gateway must not leave a chat reply hanging: a mid-stream upstream drop has to close
# the connection (not swallow the error and keep-alive), and Anthropic error/truncation
# events must be surfaced with [DONE] rather than read as a blank finished reply.
python3 tests/test_moai_gateway_streaming.py
python3 tests/test_exec_bits.py
# This one guards THIS job specifically: nothing here runs `npm run build`, so the web UI
# in the image is whatever is committed under moremote/agent/wwwroot — and .gitignore hides
# that directory, so a rebuilt bundle silently fails to land. Serving index.html for a
# missing script is a 200, not a 404, so the symptom is a blank page and a green build.
python3 tests/test_shipped_bundle_is_tracked.py
# Syft killed all three disk-constrained image jobs twice after their images had
# already built. Keep heavyweight SBOM generation off the release-critical workflow;
# it may return only in a separate workflow with its own runner budget.
python3 tests/test_release_workflow_safety.py
python3 tests/test_firewall_migration.py
python3 tests/test_hardware_adapt_lifecycle.py
python3 tests/test_moos_verify_origin.py
python3 tests/test_theme_shadow_cleanup.py
python3 tests/test_docs_privacy.py
# THE REST OF `just check`, because a gate CI does not run is a gate that
# stops the maintainer and nobody else.
#
# These fourteen ran in the Justfile only. `just build` and `just build-cloud`
# both depend on `check`, so any one of them failing halts an image build on
# the maintainer's machine while every CI run stays green — the exact shape of
# trap this repo keeps finding. It is not hypothetical: on 2026-08-15
# test_moos_fast_remote asserted a "deliberately absent" kwinrc key while
# setting only XDG_CONFIG_HOME, so KConfig's cascade answered from the HOST's
# /etc/xdg/kwinrc (which ships contrastEnabled=false) and the build stopped.
# CI could not have caught it, because CI was not running the file.
python3 tests/test_moos_fast_remote.py
python3 tests/test_remote_h264_single_slice.py
# The second, independent reason iOS refused the H.264 stream: the pipeline had no
# format caps, so the encoder took pipewiresrc's BGRx as 4:4:4 and shipped High 4:4:4
# Predictive (profile_idc 244) — a profile no phone implements in hardware. Its static
# half needs nothing installed; the runtime half skips where GStreamer is absent, which
# is the case on this runner.
python3 tests/test_remote_h264_chroma.py
python3 tests/test_remote_toolbar_edge.py
python3 tests/test_remote_input_mode.py
python3 tests/test_remote_scroll_direction.py
python3 tests/test_dotnet_project_coverage.py
python3 tests/test_remote_us_keymap.py
python3 tests/test_remote_group_resolution.py
python3 tests/test_remote_keycode_flush.py
python3 tests/test_remote_portal_keysyms_sync.py
python3 tests/test_arabic_terminal_font.py
# Arabic spell-check must exist in EVERY edition from ONE shared script.
# ARM shipped 24 English and ZERO Arabic dictionaries because the x86
# block was copied instead of shared.
python3 tests/test_webengine_dictionaries.py
python3 tests/test_boot_branding_tool.py
python3 tests/test_boot_splash_polish.py
python3 tests/test_moai_app_launch.py
python3 tests/test_moai_credential_store.py
python3 tests/test_moai_waydroid.py
python3 tests/test_moos_sound_theme.py
python3 tests/test_remote_background_alerts.py
python3 tests/test_remote_clipboard_runtime.py
python3 tests/test_remote_linux_network_boundary.py
python3 tests/test_remote_start_lifecycle.py
python3 tests/test_remote_trusted_devices.py
python3 tests/test_wayland_display_resolver.py
# These three were in the Justfile only, so they could not fail a build. The cloud edition
# is one of the three images this matrix publishes; its two gates belong here.
python3 tests/test_moos_cloud_audio.py
python3 tests/test_cloud_private_desktop.py
# A cloud account with no PIN answers /api/setup to whoever reaches it first, and one with
# a forgotten PIN has no way back in at all. Both are silent on a healthy-looking server.
python3 tests/test_cloud_set_pin.py
# moos-cloud-dev wrote an inverted subuid range (100000-65535) that usermod rejects,
# aborting a tenant half-created; a fixed range would instead make two tenants share host
# UIDs. This asserts the allocation is valid and uid-derived (unique).
python3 tests/test_cloud_subid_range.py
# Recovery must name the PRIOR deployment as the rollback target, never a staged (pending)
# update — rpm-ostree lists a staged update at index 0, so "first non-booted" pointed the
# rescue screen at the newer version, the opposite of what rollback does.
python3 tests/test_recovery_rollback_target.py
# The Mo AI per-user port generator must fail CLOSED: no account but uid 1000 may resolve to
# the base ports 8080/8079/8077, or the 11th cloud tenant reaches uid 1000's key-holding
# gateway. The old guard exited without printing for uid>=1010, which fell back to the base.
python3 tests/test_moai_ports_fail_closed.py
python3 tests/test_moai_service_lifecycle.py
# moai-openclaw-bootstrap (moai-agent-api's ExecStartPre) rewrote+revalidated an unchanged
# config on EVERY login — a ~1.7s / ~428 MB Node cold start for no net change. This asserts
# a no-op config skips the save while a drifted config still self-heals.
python3 tests/test_openclaw_bootstrap_noop.py
# OpenClaw's SQLite state DB needs 3.51.3+; Fedora 44's system Node 22.23.1 embeds
# the broken 3.51.2, which silently dropped WhatsApp replies. The shipped systemd
# override must keep pinning a SQLite-safe Node on the gateway's PATH.
python3 tests/test_openclaw_nodejs_sqlite.py
# `openclaw service install` drops a unit in ~/.config/systemd/user, which outranks the
# image's forever — so ExecStartPre=moai-openclaw-preflight (the whole Mo AI link: speech
# engine, Ollama/brain start, OLLAMA_API_KEY, ConditionUser=!@system) never runs while the
# gateway still answers. retire_legacy_gateway_unit() only knew the EARLY installer's three
# strings, so the current unit (OPENCLAW_SERVICE_VERSION=2026.7.1-2) survived every boot on
# the maintainer's own machine. This asserts both generations retire and that hand-written
# or symlinked units are still never touched.
python3 tests/test_openclaw_modern_unit_retire.py
python3 tests/test_openclaw_idle_mask_migration.py
# moai-wake is the ONLY thing that can wake a sleeping gateway, so if it cannot reach
# Telegram the phone agent is silently dead while every surface reports healthy. On a
# host with no IPv6 route it died instantly on the AAAA record ([Errno 101]) and the
# default A record timed out, though .167.220/.99 answered in 0.10s. An enabled
# WhatsApp channel pins the gateway awake, which masked this for months.
python3 tests/test_moai_wake_telegram_reachability.py
python3 tests/test_mo_remote_codec_resend.py
# The H.264->JPEG fallback latch was dead code: `if not pick_h264()` tests a 2-tuple that is
# always truthy, and the mid-stream blacklist keyed the instance name 'enc' and called
# dict.add(). Without it, a host that cannot start H.264 froze ~4s on every rebuild.
python3 tests/test_remote_h264_fallback.py
# Only encoder failure may negotiate down. A dead PipeWire source needs a fresh portal
# session, and both helper and agent must detect silence after frames have started.
python3 tests/test_remote_video_health.py
# Mo PC Remote's feel over cellular is decided by three lines of kernel tuning, and both
# ways they can fail are silent: a congestion control selected but never registered
# (machine stays on cubic, nobody is told), and a mistyped key (skipped with a warning
# nobody reads). Cheap to check, invisible when it breaks.
python3 tests/test_kernel_network_tuning.py
# One connecting phone used to rebuild the encode pipeline four times in two seconds:
# the picture appears, blanks, appears, blanks, appears. Reads as a bad link; is not one.
python3 tests/test_remote_rebuild_debounce.py
python3 tests/test_remote_connection_lifecycle.py
python3 tests/test_remote_async_lifecycle.py
python3 tests/test_remote_logout_revocation.py
python3 tests/test_remote_dotnet_dependencies.py
python3 tests/test_remote_data_dir.py
python3 tests/test_remote_power_policy.py
python3 tests/test_remote_transfer_security.py
# Injecting input used to run on the socket-reading thread, so every ping queued behind
# every click — and the auto-quality ladder reads those pongs, so USING the remote made
# it lower its own picture quality. Measured on loopback: 0.7ms idle, 133ms after 5 clicks.
python3 tests/test_input_off_socket_thread.py
# The picture ceiling (1920@30 was a constant, not a hardware limit) and the rule that
# makes raising it safe: a cached client that only speaks `scale` must keep the old one.
python3 tests/test_remote_resolution_ceiling.py
# The desktop's sound was enabled only on the cloud edition (so the Sound button 404'd
# on a desktop) and the service has no auth, so it must bind loopback — both together.
python3 tests/test_desktop_sound_reachable.py
python3 tests/test_remote_audio_is_authenticated.py
python3 tests/test_moos_store_index.py
python3 tests/test_moos_storectl.py
python3 tests/test_store_job_language.py
# One globally importable MoUI module must own identity metrics and shared
# controls; an app-local copy cannot silently grow back.
python3 tests/test_moos_design_core.py
# One answer to "is this session Arabic". Four surfaces read
# Qt.application.layoutDirection, which follows a translator and not the
# locale — the Command Center, installer and welcome screen rendered in
# English on Arabic installs.
python3 tests/test_moos_one_locale_authority.py
python3 tests/test_moos_ui2.py
# The full Launcher must be operable with the keyboard alone: the
# sidebar pages take focus and activation keys, Down/Up cross between
# the search field and the active page's grid/list, Shift+Tab returns
# to the owning page. Source gate (the runner has no Qt).
python3 tests/test_moos_launcher_keyboard.py
# The bar is ONE capsule: this runs the real merge surgery out of
# moos-bar-apply against appletsrc fixtures, so a change that can leave
# a second bottom panel fails here instead of on the owner's desktop.
python3 tests/test_moos_bar_single_panel.py
# Motion is sized to the machine: this runs the real hardware probe
# against fake /sys+/proc+/dev trees, so a classification change that
# would hand a software renderer a full blur pass fails here.
python3 tests/test_moos_visual_tier.py
# Hold the Tidal Cut geometry and byte-identical doorway component
# across every generated theme before any image layer is built.
python3 tests/test_tidal_horizon.py
python3 tests/test_tidal_portals.py
python3 tests/test_moos_theme_safety.py
python3 tests/test_moos_visual_system.py
# The MoOS settings front door must ship with its owned icon and
# private live-state helper, and every command must remain a fixed
# router destination rather than user-controlled argv.
python3 tests/test_moos_settings.py
python3 tests/test_desktop_customize.py
# `just check` must be able to run every gate CI runs; it could not,
# and an ARM regression reached main because of it.
python3 tests/test_no_privileged_user_writable_units.py
python3 tests/test_index_policy_consumer.py
python3 tests/test_diagnostic_redirection.py
python3 tests/test_selfcheck_unit_shadowing.py
python3 tests/test_mo_remote_watchdog.py
python3 tests/test_edition_unit_parity.py
python3 tests/test_selfcheck_url_handler.py
python3 tests/test_gate_coverage.py
python3 tests/test_moos_app_icons.py
# KDE and GTK windows must put their buttons on the SAME side. KWin said
# left, GSettings and the portal said right, and half the desktop
# disagreed with the other half.
python3 tests/test_window_button_consistency.py
# MoOS's own windows must never take the title bar from KWin: buttons on
# the left are only safe while the compositor reserves that strip.
python3 tests/test_first_party_window_frame.py
# Every name in an Inherits= chain must be a theme the image installs.
# MoOSUI2 named Papirus-Dark, which Fedora does not ship: 69 failed
# lookups per boot while the gate on the RPM stayed green.
python3 tests/test_icon_theme_inheritance.py
# Parse all 16 KDE palettes into first-party GTK roles and hold the
# remote status poll behind a coalescing background worker.
python3 tests/test_moos_gtk_runtime.py
# First-party interface chrome is one owned, palette-aware symbolic
# layer; this also catches unresolved icon names before a QML window ships.
python3 tests/test_moos_symbolic_icons.py
# A person who cannot see the screen must be able to use MoOS. The
# AT-SPI bus was running with NO screen reader and no speech engine
# behind it, and QT_ACCESSIBILITY was unset.
python3 tests/test_moos_accessibility.py
# Runtime rendering is skipped only when the runner lacks the desktop
# libraries; on MoOS it resolves through GTK, KDE and librsvg at 16–128px.
python3 tests/test_moos_symbolic_runtime.py
# Mo AI's custom controls and modal sheets must remain keyboard/AT
# reachable; its ambient scene must follow palette and reduced motion.
python3 tests/test_moos_app_visual_polish.py
# Skips on the runner (no Qt); its string half lives in
# verify_user_experience.py and does run here. Kept in the list so the
# gate is never forgotten when the runner image gains Qt.
python3 tests/test_moos_motion_gate.py
python3 tests/test_fwupd_refresh_policy.py
python3 tests/test_flatpak_user_update.py
python3 artwork/verify_visuals.py
# .mcp.json and .claude/settings.json are the agent contract, and they are
# COMMITTED. A pasted API key in either one is public the moment it is pushed;
# a server added to one file but not the other reaches the next agent as a tool
# that appears broken; and the deny list is the only thing standing between an
# automated session and a force-push over main. Pure stdlib, reads two files.
python3 tests/test_mcp_config.py
# The UTM bundle must carry a NoCloud seed (the ARM image has no other
# user-provisioning path) and generate a per-bundle one-time password —
# never a shared static one inside the image.
python3 tests/test_utm_bundle.py
# The store-chain gate also runs inside the image build (build.sh), where
# it reads the finished /usr. It supports MOOS_TEST_ROOT, so run it here
# too: a catalogue/recipe/route drift should cost 3 seconds, not a
# 20-minute image build that fails at its last stage.
MOOS_TEST_ROOT=system_files python3 build_files/verify_store_catalog.py

