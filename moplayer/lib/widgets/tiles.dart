import 'package:flutter/material.dart';

import '../core/theme/app_colors.dart';
import '../core/theme/app_typography.dart';
import '../core/theme/nova.dart';
import '../core/utils/formatters.dart';
import 'buttons.dart';
import 'network_poster.dart';

/// One channel in the Live list.
///
/// The EPG is optional on purpose. Most IPTV channels carry no guide, and the
/// tile has to look *designed* when there is nothing to show rather than leaving
/// a hole where the programme name would be.
class ChannelTile extends StatefulWidget {
  const ChannelTile({
    super.key,
    required this.name,
    required this.onTap,
    required this.selected,
    this.logoUrl,
    this.nowTitle,
    this.nowProgress,
    this.isFavorite = false,
    this.onToggleFavorite,
  });

  final String name;
  final String? logoUrl;
  final VoidCallback onTap;

  /// The channel currently loaded in the player — not merely the highlighted row.
  final bool selected;

  final String? nowTitle;
  final double? nowProgress;
  final bool isFavorite;
  final VoidCallback? onToggleFavorite;

  @override
  State<ChannelTile> createState() => _ChannelTileState();
}

class _ChannelTileState extends State<ChannelTile> {
  bool _hovered = false;

  @override
  Widget build(BuildContext context) {
    final background = widget.selected
        ? AppColors.surface3
        : (_hovered ? AppColors.surface2 : Colors.transparent);

    return MouseRegion(
      cursor: SystemMouseCursors.click,
      onEnter: (_) => setState(() => _hovered = true),
      onExit: (_) => setState(() => _hovered = false),
      child: GestureDetector(
        onTap: widget.onTap,
        child: AnimatedContainer(
          duration: Nova.fast,
          margin: const EdgeInsets.only(bottom: Nova.space1),
          padding: const EdgeInsets.symmetric(
            horizontal: Nova.space3,
            vertical: Nova.space2 + 2,
          ),
          decoration: BoxDecoration(
            color: background,
            borderRadius: BorderRadius.circular(Nova.radiusControl),
            border: Border.all(
              color: widget.selected ? AppColors.primary : Colors.transparent,
            ),
          ),
          child: Row(
            children: [
              SizedBox(
                width: 42,
                height: 42,
                child: NetworkPoster(
                  url: widget.logoUrl,
                  title: widget.name,
                  logoMode: true,
                  radius: Nova.radiusControl - 2,
                ),
              ),
              const SizedBox(width: Nova.space3),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      widget.name,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: AppText.control.copyWith(
                        color: widget.selected
                            ? AppColors.primary
                            : AppColors.textPrimary,
                      ),
                    ),
                    if (widget.nowTitle != null && widget.nowTitle!.isNotEmpty) ...[
                      const SizedBox(height: 3),
                      Text(
                        widget.nowTitle!,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: AppText.caption,
                      ),
                      if (widget.nowProgress != null) ...[
                        const SizedBox(height: 5),
                        ProgressBar(value: widget.nowProgress!, height: 2),
                      ],
                    ],
                  ],
                ),
              ),
              if (widget.onToggleFavorite != null &&
                  (_hovered || widget.isFavorite || widget.selected))
                IconPill(
                  icon: widget.isFavorite ? Icons.favorite : Icons.favorite_border,
                  size: 32,
                  active: widget.isFavorite,
                  onPressed: widget.onToggleFavorite,
                ),
            ],
          ),
        ),
      ),
    );
  }
}

/// A 16:9 card for something already started. Wider than a poster because what
/// the user is looking for is *where they left off*, not the artwork.
class ContinueCard extends StatefulWidget {
  const ContinueCard({
    super.key,
    required this.title,
    required this.progress,
    required this.remaining,
    required this.onTap,
    this.subtitle,
    this.imageUrl,
    this.onDismiss,
  });

  final String title;
  final String? subtitle;
  final String? imageUrl;

  /// 0–1.
  final double progress;

  /// Pre-formatted: "23 min left".
  final String remaining;
  final VoidCallback onTap;
  final VoidCallback? onDismiss;

  @override
  State<ContinueCard> createState() => _ContinueCardState();
}

class _ContinueCardState extends State<ContinueCard> {
  bool _hovered = false;

  @override
  Widget build(BuildContext context) {
    return MouseRegion(
      cursor: SystemMouseCursors.click,
      onEnter: (_) => setState(() => _hovered = true),
      onExit: (_) => setState(() => _hovered = false),
      child: GestureDetector(
        onTap: widget.onTap,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            AnimatedContainer(
              duration: Nova.normal,
              curve: Curves.easeOutCubic,
              transform: Matrix4.translationValues(0, _hovered ? -4 : 0, 0),
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(Nova.radiusCard),
                border: Border.all(
                  color: _hovered ? AppColors.primary : AppColors.borderSubtle,
                ),
                boxShadow: _hovered
                    ? [
                        BoxShadow(
                          color: AppColors.primary.withValues(alpha: 0.16),
                          blurRadius: 26,
                          spreadRadius: -8,
                          offset: const Offset(0, 8),
                        ),
                      ]
                    : null,
              ),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(Nova.radiusCard - 1),
                child: AspectRatio(
                  aspectRatio: 16 / 9,
                  child: Stack(
                    fit: StackFit.expand,
                    children: [
                      NetworkPoster(
                        url: widget.imageUrl,
                        title: widget.title,
                        radius: 0,
                      ),
                      const DecoratedBox(
                        decoration: BoxDecoration(gradient: AppColors.posterScrim),
                      ),
                      Center(
                        child: AnimatedScale(
                          scale: _hovered ? 1.0 : 0.86,
                          duration: Nova.normal,
                          curve: Curves.easeOutCubic,
                          child: IconPill(
                            icon: Icons.play_arrow_rounded,
                            filled: true,
                            size: 46,
                            onPressed: widget.onTap,
                          ),
                        ),
                      ),
                      if (widget.onDismiss != null && _hovered)
                        PositionedDirectional(
                          top: Nova.space1,
                          end: Nova.space1,
                          child: IconPill(
                            icon: Icons.close_rounded,
                            size: 30,
                            onPressed: widget.onDismiss,
                          ),
                        ),
                      PositionedDirectional(
                        start: Nova.space3,
                        end: Nova.space3,
                        bottom: Nova.space3,
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Text(
                              widget.remaining,
                              style: AppText.caption.copyWith(
                                color: Colors.white.withValues(alpha: 0.9),
                              ),
                            ),
                            const SizedBox(height: Nova.space1 + 2),
                            ProgressBar(value: widget.progress, height: 3),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
            const SizedBox(height: Nova.space2 + 2),
            Text(
              widget.title,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: AppText.control,
            ),
            if (widget.subtitle != null) ...[
              const SizedBox(height: 2),
              Text(
                widget.subtitle!,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: AppText.caption,
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// One episode in a season.
class EpisodeTile extends StatefulWidget {
  const EpisodeTile({
    super.key,
    required this.number,
    required this.title,
    required this.onTap,
    this.plot,
    this.imageUrl,
    this.durationSecs,
    this.progress,
    this.playing = false,
  });

  final int number;
  final String title;
  final String? plot;
  final String? imageUrl;
  final int? durationSecs;
  final double? progress;

  /// This episode is the one currently in the player.
  final bool playing;
  final VoidCallback onTap;

  @override
  State<EpisodeTile> createState() => _EpisodeTileState();
}

class _EpisodeTileState extends State<EpisodeTile> {
  bool _hovered = false;

  @override
  Widget build(BuildContext context) {
    return MouseRegion(
      cursor: SystemMouseCursors.click,
      onEnter: (_) => setState(() => _hovered = true),
      onExit: (_) => setState(() => _hovered = false),
      child: GestureDetector(
        onTap: widget.onTap,
        child: AnimatedContainer(
          duration: Nova.fast,
          margin: const EdgeInsets.only(bottom: Nova.space2),
          padding: const EdgeInsets.all(Nova.space2 + 2),
          decoration: BoxDecoration(
            color: _hovered || widget.playing
                ? AppColors.surface2
                : Colors.transparent,
            borderRadius: BorderRadius.circular(Nova.radiusCard),
            border: Border.all(
              color: widget.playing ? AppColors.primary : AppColors.borderSubtle,
            ),
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              SizedBox(
                width: 140,
                child: AspectRatio(
                  aspectRatio: 16 / 9,
                  child: Stack(
                    fit: StackFit.expand,
                    children: [
                      NetworkPoster(
                        url: widget.imageUrl,
                        title: '${widget.number}',
                        radius: Nova.radiusControl,
                      ),
                      if (_hovered || widget.playing)
                        ClipRRect(
                          borderRadius: BorderRadius.circular(Nova.radiusControl),
                          child: ColoredBox(
                            color: Colors.black.withValues(alpha: 0.5),
                            child: Icon(
                              widget.playing
                                  ? Icons.graphic_eq_rounded
                                  : Icons.play_arrow_rounded,
                              color: Colors.white,
                              size: 26,
                            ),
                          ),
                        ),
                      if (widget.progress != null)
                        PositionedDirectional(
                          start: 0,
                          end: 0,
                          bottom: 0,
                          child: ProgressBar(value: widget.progress!, height: 2),
                        ),
                    ],
                  ),
                ),
              ),
              const SizedBox(width: Nova.space3),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Text(
                          '${widget.number}',
                          style: AppText.control.copyWith(
                            color: AppColors.textMuted,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                        const SizedBox(width: Nova.space3),
                        Expanded(
                          child: Text(
                            widget.title,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: AppText.control,
                          ),
                        ),
                        if (widget.durationSecs != null && widget.durationSecs! > 0)
                          Text(
                            Fmt.duration(Duration(seconds: widget.durationSecs!)),
                            style: AppText.timecode.copyWith(
                              color: AppColors.textMuted,
                            ),
                          ),
                      ],
                    ),
                    if (widget.plot != null && widget.plot!.trim().isNotEmpty) ...[
                      const SizedBox(height: Nova.space2),
                      Text(
                        widget.plot!,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: AppText.caption,
                      ),
                    ],
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// A category / filter pill. The selected one is ember; the rest are quiet.
class CategoryPill extends StatefulWidget {
  const CategoryPill({
    super.key,
    required this.label,
    required this.selected,
    required this.onTap,
    this.count,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;
  final int? count;

  @override
  State<CategoryPill> createState() => _CategoryPillState();
}

class _CategoryPillState extends State<CategoryPill> {
  bool _hovered = false;

  @override
  Widget build(BuildContext context) {
    return MouseRegion(
      cursor: SystemMouseCursors.click,
      onEnter: (_) => setState(() => _hovered = true),
      onExit: (_) => setState(() => _hovered = false),
      child: GestureDetector(
        onTap: widget.onTap,
        child: AnimatedContainer(
          duration: Nova.fast,
          padding: const EdgeInsets.symmetric(
            horizontal: Nova.space4,
            vertical: Nova.space2 + 2,
          ),
          decoration: BoxDecoration(
            gradient: widget.selected ? AppColors.emberGradient : null,
            color: widget.selected
                ? null
                : (_hovered ? AppColors.surface3 : AppColors.surface2),
            borderRadius: BorderRadius.circular(999),
            border: Border.all(
              color: widget.selected ? Colors.transparent : AppColors.borderSubtle,
            ),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                widget.label,
                style: AppText.control.copyWith(
                  color: widget.selected ? Colors.white : AppColors.textSecondary,
                  fontWeight: widget.selected ? FontWeight.w600 : FontWeight.w500,
                ),
              ),
              if (widget.count != null && widget.count! > 0) ...[
                const SizedBox(width: Nova.space2),
                Text(
                  '${widget.count}',
                  style: AppText.caption.copyWith(
                    color: widget.selected
                        ? Colors.white.withValues(alpha: 0.82)
                        : AppColors.textMuted,
                  ),
                  textDirection: TextDirection.ltr,
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

/// The MoOS mark — the only place Nova's own gradient appears in this app. It
/// speaks for the system, not for MoPlayer; a second gradient accent anywhere
/// else would leave the interface with two identities and no hierarchy.
class MoOSBadge extends StatelessWidget {
  const MoOSBadge({super.key, required this.label, this.on = true});

  final String label;

  /// A dead integration is drawn grey rather than hidden: a user who turned
  /// media keys on deserves to see that the session had no D-Bus to attach to.
  final bool on;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: Nova.space3,
        vertical: Nova.space1 + 2,
      ),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: AppColors.borderSubtle),
        color: AppColors.surface2,
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 8,
            height: 8,
            decoration: BoxDecoration(
              gradient: on ? AppColors.novaGradient : null,
              color: on ? null : AppColors.textMuted,
              shape: BoxShape.circle,
            ),
          ),
          const SizedBox(width: Nova.space2),
          Text(
            label,
            style: AppText.caption.copyWith(
              color: on ? AppColors.textSecondary : AppColors.textMuted,
            ),
          ),
        ],
      ),
    );
  }
}

/// The one progress bar in the app. A `LinearProgressIndicator` with the theme's
/// track colour would be invisible on artwork, so the track is always dark.
class ProgressBar extends StatelessWidget {
  const ProgressBar({super.key, required this.value, this.height = 4});

  final double value;
  final double height;

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(height),
      child: SizedBox(
        height: height,
        child: LinearProgressIndicator(
          value: value.clamp(0.0, 1.0),
          backgroundColor: Colors.black.withValues(alpha: 0.5),
          valueColor: const AlwaysStoppedAnimation(AppColors.primary),
        ),
      ),
    );
  }
}
