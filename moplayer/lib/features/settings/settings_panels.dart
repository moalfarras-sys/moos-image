import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/routes.dart';
import '../../core/config/app_config.dart';
import '../../core/l10n/strings.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_typography.dart';
import '../../core/theme/glass.dart';
import '../../core/theme/motion.dart';
import '../../core/theme/nova.dart';
import '../../models/playlist_config.dart';
import '../../providers/content_providers.dart';
import '../../providers/core_providers.dart';
import '../../providers/library_providers.dart';
import '../../providers/playback_providers.dart';
import '../../providers/system_providers.dart';
import '../../widgets/app_logo.dart';
import '../../widgets/buttons.dart';
import '../../widgets/state_views.dart';
import '../../widgets/tiles.dart';

/// The sections of the settings panel, in the order they are listed down its
/// leading edge.
///
/// The order is not alphabetical and it is not arbitrary: it runs from *what the
/// app is pointed at* (the sources), through *how it behaves*, to *what it is*.
/// A user who opens Settings for the first time reads the list top to bottom and
/// should arrive at About last, having been told everything else first.
enum SettingsSection {
  sources(Icons.dns_rounded),
  playback(Icons.play_circle_outline_rounded),
  appearance(Icons.palette_outlined),
  language(Icons.translate_rounded),
  integration(Icons.hub_outlined),
  storage(Icons.sd_storage_outlined),
  updates(Icons.system_update_alt_rounded),
  about(Icons.info_outline_rounded);

  const SettingsSection(this.icon);

  final IconData icon;

  String title(S s) => switch (this) {
    SettingsSection.sources => s.sources,
    SettingsSection.playback => s.playback,
    SettingsSection.appearance => s.appearance,
    SettingsSection.language => s.language,
    SettingsSection.integration => s.systemIntegration,
    SettingsSection.storage => s.storage,
    SettingsSection.updates => s.updates,
    SettingsSection.about => s.about,
  };
}

/// The body of one section. The header above it is the pane's, not the panel's —
/// so a section is only ever the rows themselves.
class SettingsPanel extends StatelessWidget {
  const SettingsPanel({super.key, required this.section});

  final SettingsSection section;

  @override
  Widget build(BuildContext context) => switch (section) {
    SettingsSection.sources => const _SourcesPanel(),
    SettingsSection.playback => const _PlaybackPanel(),
    SettingsSection.appearance => const _AppearancePanel(),
    SettingsSection.language => const _LanguagePanel(),
    SettingsSection.integration => const _IntegrationPanel(),
    SettingsSection.storage => const _StoragePanel(),
    SettingsSection.updates => const _UpdatesPanel(),
    SettingsSection.about => const _AboutPanel(),
  };
}

// ── Sources ──────────────────────────────────────────────────────────────────

/// What the user would recognise: the host they typed, not the whole URL with
/// their password in the query string.
String _host(PlaylistConfig config) {
  final raw = config.isXtream ? config.normalizedServer : config.m3uUrl;
  final uri = Uri.tryParse(raw);
  if (uri == null || uri.host.isEmpty) return raw;
  return uri.hasPort ? '${uri.host}:${uri.port}' : uri.host;
}

/// A protocol name, not copy: it stays Latin in the Arabic UI, the way the
/// user's provider wrote it on the sign-up page.
String _type(PlaylistConfig config) => config.isXtream ? 'Xtream' : 'M3U';

class _SourcesPanel extends ConsumerWidget {
  const _SourcesPanel();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(stringsProvider);
    final active = ref.watch(activePlaylistProvider);
    final saved = ref.watch(savedPlaylistsProvider);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _Group(
          title: s.activeSource,
          children: [
            if (active == null)
              _Row(title: s.empty)
            else
              _Row(
                leading: _Plate(
                  icon: active.isXtream
                      ? Icons.dns_rounded
                      : Icons.link_rounded,
                  accent: true,
                ),
                title: active.name,
                // The protocol and the host, in Latin whatever the interface
                // language is — it is a machine address, not a sentence.
                description: '${_type(active)} · ${_host(active)}',
                descriptionLtr: true,
              ),
          ],
        ),
        const SizedBox(height: Nova.space5),

        _Group(
          title: s.sources,
          children: [
            saved.when(
              loading: () => const Padding(
                padding: EdgeInsets.symmetric(vertical: Nova.space5),
                child: LoadingView(),
              ),
              error: (error, _) => Padding(
                padding: const EdgeInsets.all(Nova.space4),
                child: InlineError(
                  strings: s,
                  error: error,
                  onRetry: () => ref.invalidate(savedPlaylistsProvider),
                ),
              ),
              data: (playlists) {
                if (playlists.isEmpty) return _Row(title: s.empty);
                return Column(
                  children: [
                    for (final playlist in playlists)
                      _SourceRow(
                        playlist: playlist,
                        isActive: playlist.id == active?.id,
                        last: playlist.id == playlists.last.id,
                      ),
                  ],
                );
              },
            ),
            const _Hairline(),
            // A row, not a row *with a button in it*: the whole strip is the
            // affordance, the way an "Add account…" line is in a settings list —
            // and a button labelled the same thing as the row it sits in is the
            // shape of an interface that was assembled rather than designed.
            ListRow(
              title: s.addSource,
              leading: const Icon(
                Icons.add_rounded,
                size: 19,
                color: AppColors.primary,
              ),
              // Pushed, not gone to: the login screen pops straight back here
              // when it has a source, and `go` would leave it nothing to pop.
              onTap: () => context.push('${Routes.login}?add=1'),
            ),
          ],
        ),
        const SizedBox(height: Nova.space5),

        _Group(
          children: [
            ListRow(
              title: s.signOut,
              danger: true,
              leading: const Icon(
                Icons.logout_rounded,
                size: 19,
                color: AppColors.danger,
              ),
              onTap: () async {
                await ref.read(activePlaylistProvider.notifier).logout();
                // The router's redirect reads the login state but nothing tells
                // it to re-run: without this the user is left on a Settings
                // screen for a source that no longer exists.
                if (context.mounted) context.go(Routes.login);
              },
            ),
          ],
        ),
      ],
    );
  }
}

class _SourceRow extends ConsumerWidget {
  const _SourceRow({
    required this.playlist,
    required this.isActive,
    required this.last,
  });

  final PlaylistConfig playlist;
  final bool isActive;

  /// The hairline goes *between* rows, so the last one does not draw it.
  final bool last;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(stringsProvider);

    return Column(
      children: [
        _Row(
          leading: _Dot(on: isActive),
          title: playlist.name,
          description: '${_type(playlist)} · ${_host(playlist)}',
          descriptionLtr: true,
          muted: !isActive,
          control: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (!isActive) ...[
                GhostButton(
                  label: s.switchSource,
                  icon: Icons.swap_horiz_rounded,
                  compact: true,
                  onPressed: () => ref
                      .read(activePlaylistProvider.notifier)
                      .selectSource(playlist),
                ),
                const SizedBox(width: Nova.space2),
              ],
              IconPill(
                icon: Icons.delete_outline_rounded,
                size: 36,
                tooltip: s.remove,
                onPressed: () => ref
                    .read(activePlaylistProvider.notifier)
                    .removeSource(playlist.id),
              ),
            ],
          ),
        ),
        if (!last) const _Hairline(),
      ],
    );
  }
}

// ── Playback ─────────────────────────────────────────────────────────────────

class _PlaybackPanel extends ConsumerWidget {
  const _PlaybackPanel();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(stringsProvider);
    final settings = ref.watch(settingsProvider);
    final controller = ref.read(settingsProvider.notifier);

    return _Group(
      children: [
        _SwitchRow(
          title: s.preferHls,
          description: s.preferHlsHint,
          value: settings.preferHls,
          onChanged: controller.setPreferHls,
        ),
        const _Hairline(),
        _SwitchRow(
          title: s.autoplayNext,
          value: settings.autoplayNext,
          onChanged: controller.setAutoplayNext,
        ),
        const _Hairline(),
        _SwitchRow(
          title: s.rememberLastChannel,
          value: settings.rememberLastChannel,
          onChanged: controller.setRememberLastChannel,
        ),
        // Only show "Sync on launch" when cloud sync can actually run — a switch
        // for a feature the shipped build has no backend for is a dead control.
        if (AppConfig.hasSupabase) ...[
          const _Hairline(),
          _SwitchRow(
            title: s.syncOnLaunch,
            value: settings.syncOnLaunch,
            onChanged: controller.setSyncOnLaunch,
          ),
        ],
      ],
    );
  }
}

// ── Appearance ───────────────────────────────────────────────────────────────

class _AppearancePanel extends ConsumerWidget {
  const _AppearancePanel();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(stringsProvider);
    final settings = ref.watch(settingsProvider);
    final controller = ref.read(settingsProvider.notifier);

    return _Group(
      children: [
        _SwitchRow(
          title: s.cinematicMotion,
          description: s.cinematicMotionHint,
          value: settings.cinematicMotion,
          onChanged: controller.setCinematicMotion,
        ),
        const _Hairline(),
        _SwitchRow(
          title: s.compactGrids,
          description: s.compactGridsHint,
          value: settings.compactGrids,
          onChanged: controller.setCompactGrids,
        ),
      ],
    );
  }
}

// ── Language ─────────────────────────────────────────────────────────────────

class _LanguagePanel extends ConsumerWidget {
  const _LanguagePanel();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(stringsProvider);
    final language = ref.watch(languageProvider);

    return _Group(
      children: [
        // The control sits *under* its label rather than beside it: three
        // languages is 320 px of segmented control, and a pane narrow enough to
        // squeeze it would squeeze the label instead.
        _StackedRow(
          title: s.language,
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 360),
            child: _Segmented<Lang>(
              values: Lang.values,
              selected: language,
              // The name of a language is written in that language. "Arabic" in
              // an English list is a translation of a thing that has its own
              // name, and a user looking for their own tongue looks for its own
              // letters.
              labelOf: (lang) => lang.label,
              onChanged: (lang) =>
                  ref.read(languageProvider.notifier).set(lang),
            ),
          ),
        ),
      ],
    );
  }
}

// ── MoOS integration ─────────────────────────────────────────────────────────

/// The app's signature section.
///
/// The chips are read from the running session rather than from a constant, so
/// "integrated with MoOS" is a claim the app can back up: on plain Fedora, in a
/// TTY, or in a session with no D-Bus, they go grey and say so. A green light
/// that is never checked is exactly the kind of claim MoOS's own build gates
/// exist to forbid.
class _IntegrationPanel extends ConsumerWidget {
  const _IntegrationPanel();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(stringsProvider);
    final settings = ref.watch(settingsProvider);
    final controller = ref.read(settingsProvider.notifier);

    final status = ref
        .read(desktopServiceProvider)
        .integrationStatus(mprisActive: ref.read(mprisProvider).isActive);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _Group(
          children: [
            _SwitchRow(
              title: s.mprisTitle,
              description: s.mprisHint,
              value: settings.mediaKeys,
              onChanged: controller.setMediaKeys,
            ),
            const _Hairline(),
            _SwitchRow(
              title: s.inhibitTitle,
              description: s.inhibitHint,
              value: settings.keepAwake,
              onChanged: controller.setKeepAwake,
            ),
          ],
        ),
        const SizedBox(height: Nova.space5),

        _Group(
          title: s.detected,
          children: [
            Padding(
              padding: const EdgeInsets.all(Nova.space4),
              // MoOS, Plasma, Wayland and MPRIS are what they are called in
              // Arabic too.
              child: Wrap(
                spacing: Nova.space2,
                runSpacing: Nova.space2,
                children: [
                  MoOSBadge(label: 'MoOS', on: status['moos'] ?? false),
                  MoOSBadge(label: 'Plasma', on: status['plasma'] ?? false),
                  MoOSBadge(label: 'Wayland', on: status['wayland'] ?? false),
                  MoOSBadge(label: 'MPRIS', on: status['mpris'] ?? false),
                ],
              ),
            ),
          ],
        ),
        const SizedBox(height: Nova.space5),

        _Group(
          title: s.shortcuts,
          children: [
            Padding(
              padding: const EdgeInsets.all(Nova.space4),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  for (final shortcut in ShortcutHelp.all)
                    Padding(
                      padding: const EdgeInsets.only(bottom: Nova.space2),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          SizedBox(
                            width: 132,
                            child: Text(
                              shortcut.keys,
                              style: AppText.timecode.copyWith(
                                color: AppColors.textSecondary,
                              ),
                              // Mirroring "Shift + ←" would tell an Arabic user
                              // to press the other arrow.
                              textDirection: TextDirection.ltr,
                            ),
                          ),
                          const SizedBox(width: Nova.space4),
                          Expanded(
                            child: Text(shortcut.text(s), style: AppText.body),
                          ),
                        ],
                      ),
                    ),
                ],
              ),
            ),
          ],
        ),
      ],
    );
  }
}

// ── Storage ──────────────────────────────────────────────────────────────────

class _StoragePanel extends ConsumerWidget {
  const _StoragePanel();

  Future<void> _confirmWipe(BuildContext context, WidgetRef ref, S s) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(s.wipeData, style: AppText.title),
        content: Text(s.wipeDataHint, style: AppText.body),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            child: Text(s.cancel, style: AppText.button),
          ),
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(true),
            child: Text(
              s.delete,
              style: AppText.button.copyWith(color: AppColors.danger),
            ),
          ),
        ],
      ),
    );
    if (confirmed != true) return;

    await ref.read(settingsRepositoryProvider).wipeAll();

    // The copy promises the sources go too, so they go. Their credentials live
    // in MoPlayer's private application store, alongside the active source.
    final playlists = await ref.read(authRepositoryProvider).playlists();
    for (final playlist in playlists) {
      await ref.read(activePlaylistProvider.notifier).removeSource(playlist.id);
    }
    await ref.read(activePlaylistProvider.notifier).logout();

    ref.read(catalogRefreshProvider.notifier).state++;
    ref.read(favoritesRefreshProvider.notifier).state++;
    ref.read(historyRefreshProvider.notifier).state++;
    ref.read(continueRefreshProvider.notifier).state++;

    if (context.mounted) context.go(Routes.login);
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(stringsProvider);
    final privateStorage = ref.watch(secureStorageProvider);

    return _Group(
      children: [
        _Row(
          leading: const _Plate(icon: Icons.shield_outlined, accent: true),
          title: s.privateStorage,
          description: s.privateStorageHint,
          control: MoOSBadge(
            label: privateStorage.degraded
                ? s.storageSessionOnly
                : s.storageReady,
            on: !privateStorage.degraded,
          ),
        ),
        const _Hairline(),
        _Row(
          title: s.clearCache,
          description: s.clearCacheHint,
          control: GhostButton(
            label: s.clearCache,
            icon: Icons.cleaning_services_rounded,
            compact: true,
            onPressed: () async {
              await ref.read(settingsRepositoryProvider).clearCache();
              // The catalogue providers still hold what the cache just lost;
              // without the bump the screen behind this one goes on showing it.
              ref.read(catalogRefreshProvider.notifier).state++;
            },
          ),
        ),
        const _Hairline(),
        _Row(
          title: s.wipeData,
          description: s.wipeDataHint,
          control: GhostButton(
            label: s.wipeData,
            icon: Icons.delete_forever_rounded,
            compact: true,
            danger: true,
            onPressed: () => _confirmWipe(context, ref, s),
          ),
        ),
      ],
    );
  }
}

// ── Updates ──────────────────────────────────────────────────────────────────

/// The update centre, and the one thing it must not do is lie.
///
/// MoPlayer does not self-update. It ships *inside* the MoOS image, and `bootc`
/// replaces the whole operating system — MoPlayer with it — atomically. So there
/// is no download to offer and no server to poll: the version on this machine is
/// the version the image installed, and the way to get a newer one is to update
/// the system.
///
/// The "check for updates" affordance is therefore present and **disabled**, with
/// the reason beside it. A button that pretended to check, or a progress bar that
/// always ended in "up to date", would be a green light nobody ever wired up —
/// exactly the failure MoOS's own build gates exist to forbid.
class _UpdatesPanel extends ConsumerWidget {
  const _UpdatesPanel();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(stringsProvider);
    final device = ref.read(deviceServiceProvider);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        SolidCard(
          color: AppColors.surface1,
          radius: Nova.radiusPanel,
          padding: const EdgeInsets.all(Nova.space5),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const _Plate(
                icon: Icons.verified_rounded,
                accent: true,
                size: 44,
              ),
              const SizedBox(width: Nova.space4),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(s.upToDate, style: AppText.section),
                    const SizedBox(height: Nova.space2),
                    Text(s.updatesViaSystem, style: AppText.body),
                  ],
                ),
              ),
              const SizedBox(width: Nova.space4),
              GhostButton(
                label: s.checkForUpdates,
                icon: Icons.system_update_alt_rounded,
                compact: true,
                tooltip: s.updatesViaSystem,
              ),
            ],
          ),
        ),
        const SizedBox(height: Nova.space5),

        _Group(
          children: [
            _InfoRow(
              label: s.version,
              value: '${device.appVersion} (${device.buildNumber})',
            ),
            const _Hairline(),
            _Row(
              title: s.systemIntegration,
              // Grey when this is not a MoOS system: the sentence above claims
              // the system does the updating, and this is the app checking that
              // the system it is on is the one it means.
              control: MoOSBadge(label: 'MoOS', on: AppConfig.isMoOS),
            ),
          ],
        ),
      ],
    );
  }
}

// ── About ────────────────────────────────────────────────────────────────────

class _AboutPanel extends ConsumerWidget {
  const _AboutPanel();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(stringsProvider);
    final device = ref.read(deviceServiceProvider);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        SolidCard(
          color: AppColors.surface1,
          radius: Nova.radiusPanel,
          padding: const EdgeInsets.symmetric(
            horizontal: Nova.space5,
            vertical: Nova.space6,
          ),
          child: Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const AppLogo(size: 76, showWordmark: true, showTagline: true),
                const SizedBox(height: Nova.space4),
                Text(s.forMoOS, style: AppText.body),
              ],
            ),
          ),
        ),
        const SizedBox(height: Nova.space5),

        _Group(
          children: [
            _InfoRow(
              label: s.version,
              value: '${device.appVersion} (${device.buildNumber})',
            ),
            const _Hairline(),
            // Not "media_kit": the thing decoding the picture is the system's
            // own libmpv — the same engine MoOS already ships for every other
            // player on the machine, and the reason this app adds no runtime
            // dependency to the image.
            _InfoRow(label: s.playbackEngine, value: 'libmpv via media_kit'),
            const _Hairline(),
            _InfoRow(label: s.device, value: device.deviceId),
            const _Hairline(),
            _InfoRow(label: s.appName, value: AppConfig.appId, muted: true),
          ],
        ),
      ],
    );
  }
}

// ── Building blocks ──────────────────────────────────────────────────────────

/// A plate of rows — the shape of a macOS System Settings group: one surface,
/// hairlines between the rows, an optional quiet label above it.
class _Group extends StatelessWidget {
  const _Group({required this.children, this.title});

  final String? title;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (title != null) ...[
          Padding(
            padding: const EdgeInsetsDirectional.only(
              start: Nova.space3,
              bottom: Nova.space2 + 2,
            ),
            child: Text(title!, style: AppText.label),
          ),
        ],
        SolidCard(
          color: AppColors.surface1,
          radius: Nova.radiusPanel,
          padding: EdgeInsets.zero,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: children,
          ),
        ),
      ],
    );
  }
}

/// The line between two rows. Inset from the plate's edge, the way a settings
/// list separates its rows without cutting the card in half.
class _Hairline extends StatelessWidget {
  const _Hairline();

  @override
  Widget build(BuildContext context) {
    return const Divider(
      height: 1,
      thickness: 1,
      // Directional: `indent` is the *leading* inset, so this flips with Arabic.
      indent: Nova.space4,
      endIndent: Nova.space4,
      color: AppColors.borderSubtle,
    );
  }
}

/// One row: a title and its explanation on one side, the control on the other.
class _Row extends StatelessWidget {
  const _Row({
    required this.title,
    this.description,
    this.control,
    this.leading,
    this.descriptionLtr = false,
    this.muted = false,
  });

  final String title;
  final String? description;
  final Widget? control;
  final Widget? leading;

  /// The description is a host, a version or a bus name — Latin in every
  /// language the app speaks.
  final bool descriptionLtr;

  /// A row that is present but not the active one.
  final bool muted;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(
        horizontal: Nova.space4,
        vertical: Nova.space3 + 2,
      ),
      child: Row(
        children: [
          if (leading != null) ...[
            leading!,
            const SizedBox(width: Nova.space3),
          ],
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  title,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppText.control.copyWith(
                    color: muted
                        ? AppColors.textSecondary
                        : AppColors.textPrimary,
                  ),
                ),
                if (description != null && description!.isNotEmpty) ...[
                  const SizedBox(height: 3),
                  Text(
                    description!,
                    style: AppText.caption,
                    textDirection: descriptionLtr ? TextDirection.ltr : null,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ],
            ),
          ),
          if (control != null) ...[
            const SizedBox(width: Nova.space4),
            control!,
          ],
        ],
      ),
    );
  }
}

/// A row whose control is too wide to sit beside its label — a segmented
/// control, a field. The label goes above it instead of being squeezed.
class _StackedRow extends StatelessWidget {
  const _StackedRow({required this.title, required this.child});

  final String title;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(Nova.space4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(title, style: AppText.control),
          const SizedBox(height: Nova.space3),
          Align(alignment: AlignmentDirectional.centerStart, child: child),
        ],
      ),
    );
  }
}

class _SwitchRow extends StatelessWidget {
  const _SwitchRow({
    required this.title,
    required this.value,
    required this.onChanged,
    this.description,
  });

  final String title;
  final String? description;
  final bool value;
  final ValueChanged<bool> onChanged;

  @override
  Widget build(BuildContext context) {
    return _Row(
      title: title,
      description: description,
      control: Switch(value: value, onChanged: onChanged),
    );
  }
}

/// A label and a value the user can select and paste into a support thread.
class _InfoRow extends StatelessWidget {
  const _InfoRow({
    required this.label,
    required this.value,
    this.muted = false,
  });

  final String label;
  final String value;
  final bool muted;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(
        horizontal: Nova.space4,
        vertical: Nova.space3 + 2,
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(width: 132, child: Text(label, style: AppText.label)),
          const SizedBox(width: Nova.space4),
          Expanded(
            child: SelectableText(
              value,
              style: AppText.body.copyWith(
                color: muted ? AppColors.textMuted : AppColors.textPrimary,
              ),
              // Versions, device ids and bus names are Latin strings whatever
              // the interface language is.
              textDirection: TextDirection.ltr,
            ),
          ),
        ],
      ),
    );
  }
}

/// The glyph plate a row can carry at its leading edge.
class _Plate extends StatelessWidget {
  const _Plate({required this.icon, this.accent = false, this.size = 36});

  final IconData icon;
  final bool accent;
  final double size;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        gradient: accent ? AppColors.emberGradient : null,
        color: accent ? null : AppColors.surface3,
        borderRadius: BorderRadius.circular(Nova.radiusControl - 2),
      ),
      child: Icon(
        icon,
        size: size * 0.5,
        color: accent ? Colors.white : AppColors.textSecondary,
      ),
    );
  }
}

/// The active-source mark. Ember when it is the one the app is pointed at.
class _Dot extends StatelessWidget {
  const _Dot({required this.on});

  final bool on;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 8,
      height: 8,
      margin: const EdgeInsets.symmetric(horizontal: Nova.space2),
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        gradient: on ? AppColors.emberGradient : null,
        color: on ? null : AppColors.borderStrong,
      ),
    );
  }
}

/// A segmented control: one track, one ember pill, no dropdown. Three languages
/// are worth showing at once — a menu would hide all three.
class _Segmented<T> extends StatelessWidget {
  const _Segmented({
    required this.values,
    required this.selected,
    required this.labelOf,
    required this.onChanged,
  });

  final List<T> values;
  final T selected;
  final String Function(T) labelOf;
  final ValueChanged<T> onChanged;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(Nova.space1),
      decoration: BoxDecoration(
        color: AppColors.surface2,
        borderRadius: BorderRadius.circular(Nova.radiusControl + 2),
        border: Border.all(color: AppColors.borderSubtle),
      ),
      child: Row(
        children: [
          for (final value in values)
            Expanded(
              child: _Segment(
                label: labelOf(value),
                selected: value == selected,
                onTap: () => onChanged(value),
              ),
            ),
        ],
      ),
    );
  }
}

class _Segment extends StatefulWidget {
  const _Segment({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  State<_Segment> createState() => _SegmentState();
}

class _SegmentState extends State<_Segment> {
  bool _hovered = false;
  bool _focused = false;

  @override
  Widget build(BuildContext context) {
    final selected = widget.selected;
    final color = selected
        ? Colors.white
        : (_hovered ? AppColors.textPrimary : AppColors.textSecondary);

    return Semantics(
      button: true,
      selected: selected,
      label: widget.label,
      child: FocusableActionDetector(
        mouseCursor: SystemMouseCursors.click,
        onShowHoverHighlight: (v) => setState(() => _hovered = v),
        onShowFocusHighlight: (v) => setState(() => _focused = v),
        actions: {
          ActivateIntent: CallbackAction<ActivateIntent>(
            onInvoke: (_) {
              widget.onTap();
              return null;
            },
          ),
        },
        child: GestureDetector(
          onTap: widget.onTap,
          behavior: HitTestBehavior.opaque,
          child: AnimatedContainer(
            duration: Motion.duration(context, Nova.hover),
            curve: Ease.enter,
            height: 38,
            decoration: BoxDecoration(
              gradient: selected ? AppColors.emberGradient : null,
              color: selected
                  ? null
                  : (_hovered ? AppColors.surface3 : Colors.transparent),
              borderRadius: BorderRadius.circular(Nova.radiusControl),
              boxShadow: focusRing(_focused),
            ),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Flexible(
                  child: Text(
                    widget.label,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: AppText.button.copyWith(color: color),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
