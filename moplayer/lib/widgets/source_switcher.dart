import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../app/routes.dart';
import '../core/l10n/strings.dart';
import '../core/theme/app_colors.dart';
import '../core/theme/app_typography.dart';
import '../core/theme/motion.dart';
import '../core/theme/nova.dart';
import '../models/playlist_config.dart';
import '../providers/core_providers.dart';
import '../providers/shell_providers.dart';
import '../providers/system_providers.dart';

/// The active server, at the foot of the navigation rail, and the way to
/// switch to another one.
///
/// A subscription is the thing an IPTV viewer actually has more than one of —
/// a main line, a backup, a trial from a friend — and switching between them
/// used to be three screens deep in Settings. Here it is one click from
/// anywhere, with the kind of each source (panel, playlist, portal) written on
/// it so two sources with similar names can still be told apart.
class SourceSwitcher extends ConsumerStatefulWidget {
  const SourceSwitcher({super.key});

  @override
  ConsumerState<SourceSwitcher> createState() => _SourceSwitcherState();
}

class _SourceSwitcherState extends ConsumerState<SourceSwitcher> {
  bool _hovered = false;
  final _anchor = GlobalKey();

  Future<void> _open() async {
    final s = ref.read(stringsProvider);
    final saved = await ref.read(savedPlaylistsProvider.future);
    final active = ref.read(activePlaylistProvider);
    if (!mounted) return;
    final box = _anchor.currentContext?.findRenderObject() as RenderBox?;
    if (box == null) return;
    final origin = box.localToGlobal(Offset.zero);
    final rtl = Directionality.of(context) == TextDirection.rtl;
    final screen = MediaQuery.sizeOf(context);
    final left = rtl ? origin.dx - 300 : origin.dx + box.size.width + 8;

    final picked = await showMenu<Object>(
      context: context,
      position: RelativeRect.fromLTRB(
        left,
        origin.dy - 40,
        screen.width - left - 300,
        screen.height - origin.dy - box.size.height,
      ),
      constraints: const BoxConstraints(minWidth: 300, maxWidth: 340),
      items: [
        PopupMenuItem<Object>(
          enabled: false,
          height: 36,
          child: Text(s.switchSource, style: AppText.label),
        ),
        for (final source in saved)
          PopupMenuItem<Object>(
            value: source,
            height: 56,
            child: _SourceRow(
              source: source,
              active: source.id == active?.id,
              kindLabel: _kindLabel(s, source),
            ),
          ),
        const PopupMenuDivider(height: 8),
        PopupMenuItem<Object>(
          value: _Action.add,
          height: 44,
          child: _ActionRow(icon: Icons.add_rounded, label: s.addSource),
        ),
        PopupMenuItem<Object>(
          value: _Action.manage,
          height: 44,
          child: _ActionRow(icon: Icons.tune_rounded, label: s.manageSources),
        ),
      ],
    );
    if (!mounted || picked == null) return;
    if (picked is PlaylistConfig) {
      if (picked.id != active?.id) {
        await ref.read(activePlaylistProvider.notifier).selectSource(picked);
        if (mounted) context.go(Routes.home);
      }
    } else if (picked == _Action.add) {
      context.push('${Routes.login}?add=1');
    } else if (picked == _Action.manage) {
      context.go(Routes.settings);
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = ref.watch(stringsProvider);
    final active = ref.watch(activePlaylistProvider);
    final online = ref.watch(connectivityProvider).value ?? true;
    if (active == null) return const SizedBox.shrink();
    final initial = active.name.trim().isEmpty
        ? '?'
        : active.name.trim().characters.first.toUpperCase();

    return Tooltip(
      message: '${active.name} · ${s.switchSource}',
      child: Semantics(
        button: true,
        label: '${s.switchSource}: ${active.name}',
        excludeSemantics: true,
        child: MouseRegion(
          cursor: SystemMouseCursors.click,
          onEnter: (_) => setState(() => _hovered = true),
          onExit: (_) => setState(() => _hovered = false),
          child: GestureDetector(
            onTap: _open,
            child: AnimatedContainer(
              key: _anchor,
              duration: Motion.duration(context, Nova.hover),
              width: 48,
              height: 48,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: AppColors.primary,
                border: Border.all(
                  color: _hovered ? AppColors.textPrimary : AppColors.surface1,
                  width: 2,
                ),
              ),
              child: Stack(
                clipBehavior: Clip.none,
                children: [
                  Center(
                    child: Text(
                      initial,
                      style: AppText.section.copyWith(
                        color: AppColors.onAccent,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
                  PositionedDirectional(
                    end: -1,
                    bottom: -1,
                    child: Container(
                      width: 13,
                      height: 13,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: online ? AppColors.success : AppColors.warning,
                        border: Border.all(color: AppColors.surface1, width: 2),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

String _kindLabel(S s, PlaylistConfig source) {
  if (source.isStalker) return s.sourceKindPortal;
  if (source.isXtream || source.xtreamEquivalent != null) {
    return s.sourceKindPanel;
  }
  return s.sourceKindPlaylist;
}

enum _Action { add, manage }

class _SourceRow extends StatelessWidget {
  const _SourceRow({
    required this.source,
    required this.active,
    required this.kindLabel,
  });

  final PlaylistConfig source;
  final bool active;
  final String kindLabel;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 34,
          height: 34,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: active ? AppColors.primary : AppColors.surface3,
          ),
          child: Text(
            source.name.trim().isEmpty
                ? '?'
                : source.name.trim().characters.first.toUpperCase(),
            style: AppText.control.copyWith(
              fontWeight: FontWeight.w700,
              color: active ? AppColors.onAccent : AppColors.textPrimary,
            ),
          ),
        ),
        const SizedBox(width: Nova.space3),
        Expanded(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                source.name,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: AppText.control.copyWith(
                  fontWeight: active ? FontWeight.w600 : FontWeight.w500,
                ),
              ),
              Text(kindLabel, style: AppText.caption),
            ],
          ),
        ),
        if (active)
          Icon(Icons.check_rounded, size: 18, color: AppColors.primary),
      ],
    );
  }
}

class _ActionRow extends StatelessWidget {
  const _ActionRow({required this.icon, required this.label});

  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        SizedBox(
          width: 34,
          child: Icon(icon, size: 20, color: AppColors.textSecondary),
        ),
        const SizedBox(width: Nova.space3),
        Text(label, style: AppText.control),
      ],
    );
  }
}
