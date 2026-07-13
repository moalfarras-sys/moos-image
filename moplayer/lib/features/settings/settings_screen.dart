import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/routes.dart';
import '../../core/config/app_config.dart';
import '../../core/l10n/strings.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_typography.dart';
import '../../core/theme/glass.dart';
import '../../core/theme/nova.dart';
import '../../models/playlist_config.dart';
import '../../providers/content_providers.dart';
import '../../providers/core_providers.dart';
import '../../providers/library_providers.dart';
import '../../providers/playback_providers.dart';
import '../../providers/system_providers.dart';
import '../../widgets/app_logo.dart';
import '../../widgets/buttons.dart';
import '../../widgets/media_rail.dart';
import '../../widgets/state_views.dart';
import '../../widgets/tiles.dart';

class SettingsScreen extends ConsumerWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(stringsProvider);

    return SingleChildScrollView(
      padding: const EdgeInsets.symmetric(
        horizontal: Nova.space6,
        vertical: Nova.space6,
      ),
      child: Center(
        // A settings form stretched across a 1440-pixel window puts its switches
        // a hand's width from the labels they belong to.
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 880),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              SectionHeader(title: s.settings),
              const SizedBox(height: Nova.space5),
              const _SourcesCard(),
              const SizedBox(height: Nova.space4),
              const _PlaybackCard(),
              const SizedBox(height: Nova.space4),
              const _IntegrationCard(),
              const SizedBox(height: Nova.space4),
              const _AppearanceCard(),
              const SizedBox(height: Nova.space4),
              const _StorageCard(),
              const SizedBox(height: Nova.space4),
              const _AboutCard(),
              const SizedBox(height: Nova.space6),
            ],
          ),
        ),
      ),
    );
  }
}

// ── Sources ──────────────────────────────────────────────────────────────────

class _SourcesCard extends ConsumerWidget {
  const _SourcesCard();

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

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(stringsProvider);
    final active = ref.watch(activePlaylistProvider);
    final saved = ref.watch(savedPlaylistsProvider);

    return _Card(
      title: s.sources,
      trailing: GhostButton(
        label: s.addSource,
        icon: Icons.add_rounded,
        // Pushed, not gone to: the login screen pops straight back here when it
        // has a source, and `go` would leave it with nothing to pop.
        onPressed: () => context.push('${Routes.login}?add=1'),
      ),
      children: [
        Text(s.activeSource, style: AppText.label),
        const SizedBox(height: Nova.space3),
        if (active == null)
          Text(s.empty, style: AppText.body)
        else
          Row(
            children: [
              Icon(
                active.isXtream ? Icons.dns_rounded : Icons.link_rounded,
                size: 20,
                color: AppColors.primary,
              ),
              const SizedBox(width: Nova.space3),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      active.name,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: AppText.control,
                    ),
                    const SizedBox(height: 2),
                    Text(
                      '${_type(active)} · ${_host(active)}',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: AppText.caption,
                      textDirection: TextDirection.ltr,
                    ),
                  ],
                ),
              ),
            ],
          ),

        const _Divider(),

        saved.when(
          loading: () => const Padding(
            padding: EdgeInsets.symmetric(vertical: Nova.space4),
            child: LoadingView(),
          ),
          error: (error, _) => ErrorView(
            strings: s,
            error: error,
            onRetry: () => ref.invalidate(savedPlaylistsProvider),
          ),
          data: (playlists) {
            if (playlists.isEmpty) return Text(s.empty, style: AppText.body);
            return Column(
              children: [
                for (final playlist in playlists)
                  _SourceRow(
                    playlist: playlist,
                    isActive: playlist.id == active?.id,
                    subtitle: '${_type(playlist)} · ${_host(playlist)}',
                  ),
              ],
            );
          },
        ),

        const _Divider(),

        Align(
          alignment: AlignmentDirectional.centerStart,
          child: GhostButton(
            label: s.signOut,
            icon: Icons.logout_rounded,
            onPressed: () async {
              await ref.read(activePlaylistProvider.notifier).logout();
              // The router's redirect reads the login state but nothing tells it
              // to re-run: without this the user is left on a Settings screen
              // for a source that no longer exists.
              if (context.mounted) context.go(Routes.login);
            },
          ),
        ),
      ],
    );
  }
}

class _SourceRow extends ConsumerWidget {
  const _SourceRow({
    required this.playlist,
    required this.isActive,
    required this.subtitle,
  });

  final PlaylistConfig playlist;
  final bool isActive;
  final String subtitle;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(stringsProvider);

    return Padding(
      padding: const EdgeInsets.only(bottom: Nova.space2),
      child: Row(
        children: [
          Container(
            width: 8,
            height: 8,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: isActive ? AppColors.emberGradient : null,
              color: isActive ? null : AppColors.borderStrong,
            ),
          ),
          const SizedBox(width: Nova.space3),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  playlist.name,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppText.control.copyWith(
                    color: isActive
                        ? AppColors.textPrimary
                        : AppColors.textSecondary,
                  ),
                ),
                Text(
                  subtitle,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppText.caption,
                  textDirection: TextDirection.ltr,
                ),
              ],
            ),
          ),
          if (!isActive) ...[
            GhostButton(
              label: s.switchSource,
              icon: Icons.swap_horiz_rounded,
              onPressed: () => ref
                  .read(activePlaylistProvider.notifier)
                  .selectSource(playlist),
            ),
            const SizedBox(width: Nova.space2),
          ],
          IconPill(
            icon: Icons.delete_outline_rounded,
            tooltip: s.remove,
            onPressed: () => ref
                .read(activePlaylistProvider.notifier)
                .removeSource(playlist.id),
          ),
        ],
      ),
    );
  }
}

// ── Playback ─────────────────────────────────────────────────────────────────

class _PlaybackCard extends ConsumerWidget {
  const _PlaybackCard();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(stringsProvider);
    final settings = ref.watch(settingsProvider);
    final controller = ref.read(settingsProvider.notifier);

    return _Card(
      title: s.playback,
      children: [
        _SwitchRow(
          title: s.preferHls,
          hint: s.preferHlsHint,
          value: settings.preferHls,
          onChanged: controller.setPreferHls,
        ),
        _SwitchRow(
          title: s.autoplayNext,
          value: settings.autoplayNext,
          onChanged: controller.setAutoplayNext,
        ),
        _SwitchRow(
          title: s.rememberLastChannel,
          value: settings.rememberLastChannel,
          onChanged: controller.setRememberLastChannel,
        ),
        _SwitchRow(
          title: s.syncOnLaunch,
          value: settings.syncOnLaunch,
          onChanged: controller.setSyncOnLaunch,
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
class _IntegrationCard extends ConsumerWidget {
  const _IntegrationCard();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(stringsProvider);
    final settings = ref.watch(settingsProvider);
    final controller = ref.read(settingsProvider.notifier);

    final status = ref
        .read(desktopServiceProvider)
        .integrationStatus(mprisActive: ref.read(mprisProvider).isActive);

    return _Card(
      title: s.systemIntegration,
      children: [
        _SwitchRow(
          title: s.mprisTitle,
          hint: s.mprisHint,
          value: settings.mediaKeys,
          onChanged: controller.setMediaKeys,
        ),
        _SwitchRow(
          title: s.inhibitTitle,
          hint: s.inhibitHint,
          value: settings.keepAwake,
          onChanged: controller.setKeepAwake,
        ),

        const _Divider(),

        // MoOS, Plasma, Wayland and MPRIS are what they are called in Arabic too.
        Wrap(
          spacing: Nova.space2,
          runSpacing: Nova.space2,
          children: [
            MoOSBadge(label: 'MoOS', on: status['moos'] ?? false),
            MoOSBadge(label: 'Plasma', on: status['plasma'] ?? false),
            MoOSBadge(label: 'Wayland', on: status['wayland'] ?? false),
            MoOSBadge(label: 'MPRIS', on: status['mpris'] ?? false),
          ],
        ),

        const _Divider(),

        Text(s.shortcuts, style: AppText.label),
        const SizedBox(height: Nova.space3),
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
                    // Mirroring "Shift + ←" would tell an Arabic user to press
                    // the other arrow.
                    textDirection: TextDirection.ltr,
                  ),
                ),
                const SizedBox(width: Nova.space4),
                Expanded(
                  child: Text(
                    s.isAr ? shortcut.ar : shortcut.en,
                    style: AppText.body,
                  ),
                ),
              ],
            ),
          ),
      ],
    );
  }
}

// ── Appearance ───────────────────────────────────────────────────────────────

class _AppearanceCard extends ConsumerWidget {
  const _AppearanceCard();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(stringsProvider);
    final settings = ref.watch(settingsProvider);
    final controller = ref.read(settingsProvider.notifier);
    final language = ref.watch(languageProvider);

    return _Card(
      title: s.appearance,
      children: [
        Text(s.language, style: AppText.label),
        const SizedBox(height: Nova.space3),
        Align(
          alignment: AlignmentDirectional.centerStart,
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 320),
            child: _Segmented<Lang>(
              values: Lang.values,
              selected: language,
              labelOf: (lang) => lang.label,
              onChanged: (lang) => ref.read(languageProvider.notifier).set(lang),
            ),
          ),
        ),

        const _Divider(),

        _SwitchRow(
          title: s.cinematicMotion,
          hint: s.cinematicMotionHint,
          value: settings.cinematicMotion,
          onChanged: controller.setCinematicMotion,
        ),
        _SwitchRow(
          title: s.compactGrids,
          hint: s.compactGridsHint,
          value: settings.compactGrids,
          onChanged: controller.setCompactGrids,
        ),
      ],
    );
  }
}

// ── Storage ──────────────────────────────────────────────────────────────────

class _StorageCard extends ConsumerWidget {
  const _StorageCard();

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

    // The copy promises the sources go too, so they go: a wipe that quietly left
    // the user's panel credentials in the keyring would be a lie.
    final playlists = await ref.read(authRepositoryProvider).playlists();
    for (final playlist in playlists) {
      await ref.read(activePlaylistProvider.notifier).removeSource(playlist.id);
    }
    await ref.read(activePlaylistProvider.notifier).logout();

    ref.read(catalogRefreshProvider.notifier).state++;
    ref.read(libraryRefreshProvider.notifier).state++;

    if (context.mounted) context.go(Routes.login);
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(stringsProvider);

    return _Card(
      title: s.storage,
      children: [
        _ActionRow(
          title: s.clearCache,
          hint: s.clearCacheHint,
          action: GhostButton(
            label: s.clearCache,
            icon: Icons.cleaning_services_rounded,
            onPressed: () async {
              await ref.read(settingsRepositoryProvider).clearCache();
              // The catalogue providers still hold what the cache just lost;
              // without the bump the screen behind this one goes on showing it.
              ref.read(catalogRefreshProvider.notifier).state++;
            },
          ),
        ),
        const _Divider(),
        _ActionRow(
          title: s.wipeData,
          hint: s.wipeDataHint,
          action: GhostButton(
            label: s.wipeData,
            icon: Icons.delete_forever_rounded,
            danger: true,
            onPressed: () => _confirmWipe(context, ref, s),
          ),
        ),
      ],
    );
  }
}

// ── About ────────────────────────────────────────────────────────────────────

class _AboutCard extends ConsumerWidget {
  const _AboutCard();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(stringsProvider);
    final device = ref.read(deviceServiceProvider);

    return _Card(
      title: s.about,
      children: [
        Center(
          child: Column(
            children: [
              const AppLogo(size: 56, showWordmark: true),
              const SizedBox(height: Nova.space2),
              Text(s.forMoOS, style: AppText.caption),
            ],
          ),
        ),
        const SizedBox(height: Nova.space5),
        _KeyValue(
          label: s.version,
          value: '${device.appVersion} (${device.buildNumber})',
        ),
        const SizedBox(height: Nova.space3),
        // Not "media_kit": the thing decoding the picture is the system's own
        // libmpv — the same engine MoOS already ships for every other player on
        // the machine.
        _KeyValue(label: s.playbackEngine, value: 'libmpv via media_kit'),
        const SizedBox(height: Nova.space3),
        _KeyValue(label: s.device, value: device.deviceId),
        const SizedBox(height: Nova.space3),
        _KeyValue(label: s.appName, value: AppConfig.appId, muted: true),
      ],
    );
  }
}

// ── Building blocks ──────────────────────────────────────────────────────────

class _Card extends StatelessWidget {
  const _Card({required this.title, required this.children, this.trailing});

  final String title;
  final List<Widget> children;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    return NovaCard(
      padding: const EdgeInsets.all(Nova.space5),
      radius: Nova.radiusPanel,
      color: AppColors.surface1,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Expanded(child: Text(title, style: AppText.section)),
              if (trailing != null) trailing!,
            ],
          ),
          const SizedBox(height: Nova.space4),
          ...children,
        ],
      ),
    );
  }
}

class _Divider extends StatelessWidget {
  const _Divider();

  @override
  Widget build(BuildContext context) {
    return const Padding(
      padding: EdgeInsets.symmetric(vertical: Nova.space4),
      child: Divider(height: 1, thickness: 1, color: AppColors.borderSubtle),
    );
  }
}

class _SwitchRow extends StatelessWidget {
  const _SwitchRow({
    required this.title,
    required this.value,
    required this.onChanged,
    this.hint,
  });

  final String title;
  final String? hint;
  final bool value;
  final ValueChanged<bool> onChanged;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: Nova.space2),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: AppText.control),
                if (hint != null) ...[
                  const SizedBox(height: 2),
                  Text(hint!, style: AppText.caption),
                ],
              ],
            ),
          ),
          const SizedBox(width: Nova.space4),
          Switch(value: value, onChanged: onChanged),
        ],
      ),
    );
  }
}

class _ActionRow extends StatelessWidget {
  const _ActionRow({
    required this.title,
    required this.hint,
    required this.action,
  });

  final String title;
  final String hint;
  final Widget action;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title, style: AppText.control),
              const SizedBox(height: 2),
              Text(hint, style: AppText.caption),
            ],
          ),
        ),
        const SizedBox(width: Nova.space4),
        action,
      ],
    );
  }
}

/// A label and a value the user can select and paste into a support thread.
class _KeyValue extends StatelessWidget {
  const _KeyValue({
    required this.label,
    required this.value,
    this.muted = false,
  });

  final String label;
  final String value;
  final bool muted;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(width: 120, child: Text(label, style: AppText.label)),
        const SizedBox(width: Nova.space4),
        Expanded(
          child: SelectableText(
            value,
            style: AppText.body.copyWith(
              color: muted ? AppColors.textMuted : AppColors.textPrimary,
            ),
            // Versions, device ids and bus names are Latin strings whatever the
            // interface language is.
            textDirection: TextDirection.ltr,
          ),
        ),
      ],
    );
  }
}

/// A Nova segmented control: one track, one ember pill, no dropdown. Two options
/// are worth showing at once — a menu would hide them both.
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

  @override
  Widget build(BuildContext context) {
    final selected = widget.selected;
    final color = selected
        ? Colors.white
        : (_hovered ? AppColors.textPrimary : AppColors.textSecondary);

    return MouseRegion(
      cursor: SystemMouseCursors.click,
      onEnter: (_) => setState(() => _hovered = true),
      onExit: (_) => setState(() => _hovered = false),
      child: GestureDetector(
        onTap: widget.onTap,
        behavior: HitTestBehavior.opaque,
        child: AnimatedContainer(
          duration: Nova.fast,
          height: 38,
          decoration: BoxDecoration(
            gradient: selected ? AppColors.emberGradient : null,
            color: selected
                ? null
                : (_hovered ? AppColors.surface3 : Colors.transparent),
            borderRadius: BorderRadius.circular(Nova.radiusControl),
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
    );
  }
}
