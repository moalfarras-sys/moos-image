import 'package:flutter/material.dart';

import '../core/theme/app_colors.dart';
import '../core/theme/app_typography.dart';
import '../core/theme/glass.dart';
import '../core/theme/motion.dart';
import '../core/theme/nova.dart';
import '../core/utils/formatters.dart';
import 'buttons.dart';
import 'focus_surface.dart';
import 'media_card.dart';
import 'network_poster.dart';

/// One channel in the Live list.
///
/// The EPG is optional on purpose. Most IPTV channels carry no guide, and the
/// row has to look *designed* when there is nothing to show rather than leaving
/// a hole where the programme name would be — so when there is no `now`, the
/// name simply centres itself in the row and nothing else appears.
class ChannelTile extends StatefulWidget {
  const ChannelTile({
    super.key,
    required this.name,
    required this.onTap,
    required this.selected,
    this.logoUrl,
    this.nowTitle,
    this.nowProgress,
    this.nextTitle,
    this.isFavorite = false,
    this.onToggleFavorite,
    this.number,
    this.focusNode,
    this.autofocus = false,
    this.onPreview,
  });

  final String name;
  final String? logoUrl;
  final VoidCallback onTap;

  /// This row became the one under the eye — hovered, or reached by keyboard.
  /// The live screen's right-hand pane follows it, which is what makes the list
  /// behave like a receiver: you *look* through the channels, and you tune one
  /// only when you mean to.
  final VoidCallback? onPreview;

  /// The channel currently loaded in the player — not merely the highlighted row.
  final bool selected;

  final String? nowTitle;

  /// How far through the current programme we are, 0–1.
  final double? nowProgress;

  final String? nextTitle;
  final bool isFavorite;
  final VoidCallback? onToggleFavorite;

  /// The channel's own number, when the panel gives one.
  final int? number;

  final FocusNode? focusNode;
  final bool autofocus;

  @override
  State<ChannelTile> createState() => _ChannelTileState();
}

class _ChannelTileState extends State<ChannelTile> {
  bool _hovered = false;
  bool _focused = false;

  @override
  Widget build(BuildContext context) {
    final active = _hovered || _focused;
    final hasNow = widget.nowTitle != null && widget.nowTitle!.trim().isNotEmpty;

    return Padding(
      padding: const EdgeInsets.only(bottom: Nova.space1),
      child: MouseRegion(
        onEnter: (_) {
          setState(() => _hovered = true);
          widget.onPreview?.call();
        },
        onExit: (_) => setState(() => _hovered = false),
        child: FocusSurface(
          onTap: widget.onTap,
          focusNode: widget.focusNode,
          autofocus: widget.autofocus,
          onFocusChange: (v) {
            setState(() => _focused = v);
            if (v) widget.onPreview?.call();
          },
          radius: Nova.radiusControl,
          // A full-width row cannot take a poster's lift: 4% of 380 px is 15 px
          // of travel, and the list would appear to breathe.
          scale: 1.01,
          bloom: false,
          selected: widget.selected,
          semanticLabel: hasNow ? '${widget.name}, ${widget.nowTitle}' : widget.name,
          child: AnimatedContainer(
            duration: Motion.duration(context, Nova.hover),
            curve: Ease.enter,
            padding: const EdgeInsets.symmetric(
              horizontal: Nova.space3,
              vertical: Nova.space2 + 2,
            ),
            decoration: BoxDecoration(
              color: widget.selected
                  ? AppColors.surfaceWarm
                  : (active ? AppColors.surface2 : Colors.transparent),
              borderRadius: BorderRadius.circular(Nova.radiusControl),
            ),
            child: Row(
              children: [
                // The playing channel gets an ember bar at its leading edge —
                // the one mark that survives when the row is scrolled past at
                // speed.
                AnimatedContainer(
                  duration: Motion.duration(context, Nova.hover),
                  width: widget.selected ? 3 : 0,
                  height: 34,
                  margin: EdgeInsetsDirectional.only(
                    end: widget.selected ? Nova.space2 + 2 : 0,
                  ),
                  decoration: BoxDecoration(
                    gradient: AppColors.emberGradient,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),

                if (widget.number != null) ...[
                  SizedBox(
                    width: 26,
                    child: Text(
                      '${widget.number}',
                      textAlign: TextAlign.center,
                      textDirection: TextDirection.ltr,
                      style: AppText.timecode.copyWith(
                        fontSize: 12,
                        color: AppColors.textMuted,
                      ),
                    ),
                  ),
                  const SizedBox(width: Nova.space2),
                ],

                SizedBox(
                  width: 42,
                  height: 42,
                  child: NetworkPoster(
                    url: widget.logoUrl,
                    title: widget.name,
                    logoMode: true,
                    width: 42,
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
                              ? AppColors.primaryBright
                              : AppColors.textPrimary,
                        ),
                      ),
                      if (hasNow) ...[
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
                      ] else if (widget.nextTitle != null &&
                          widget.nextTitle!.trim().isNotEmpty) ...[
                        const SizedBox(height: 3),
                        Text(
                          widget.nextTitle!,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: AppText.caption,
                        ),
                      ],
                    ],
                  ),
                ),

                if (widget.onToggleFavorite != null &&
                    (active || widget.isFavorite || widget.selected))
                  IconPill(
                    icon: widget.isFavorite
                        ? Icons.favorite_rounded
                        : Icons.favorite_border_rounded,
                    size: 32,
                    active: widget.isFavorite,
                    onPressed: widget.onToggleFavorite,
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// A 16:9 card for something already started.
///
/// A thin arrangement of [LandscapeCard]: the resume copy and the bar are the
/// same overlay every other 16:9 card in the app draws, and two implementations
/// of it would drift apart within a week.
class ContinueCard extends StatelessWidget {
  const ContinueCard({
    super.key,
    required this.title,
    required this.progress,
    required this.remaining,
    required this.onTap,
    this.subtitle,
    this.imageUrl,
    this.onDismiss,
    this.width,
    this.focusNode,
    this.autofocus = false,
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
  final double? width;
  final FocusNode? focusNode;
  final bool autofocus;

  @override
  Widget build(BuildContext context) {
    return LandscapeCard(
      title: title,
      subtitle: subtitle,
      imageUrl: imageUrl,
      progress: progress,
      caption: remaining,
      onTap: onTap,
      onDismiss: onDismiss,
      width: width,
      focusNode: focusNode,
      autofocus: autofocus,
      semanticLabel: '$title, $remaining',
    );
  }
}

/// One episode in a season — the row form: thumbnail, number, title, runtime,
/// and as much of the plot as fits on two lines.
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
    this.watched = false,
    this.focusNode,
    this.autofocus = false,
  });

  final int number;
  final String title;
  final String? plot;
  final String? imageUrl;
  final int? durationSecs;

  /// 0–1, or null if never started.
  final double? progress;

  /// This episode is the one currently in the player.
  final bool playing;

  /// Finished.
  final bool watched;

  final VoidCallback onTap;
  final FocusNode? focusNode;
  final bool autofocus;

  @override
  State<EpisodeTile> createState() => _EpisodeTileState();
}

class _EpisodeTileState extends State<EpisodeTile> {
  bool _hovered = false;
  bool _focused = false;

  @override
  Widget build(BuildContext context) {
    final active = _hovered || _focused;
    final hasProgress = widget.progress != null && widget.progress! > 0.01;
    final runtime = (widget.durationSecs ?? 0) > 0
        ? Fmt.duration(Duration(seconds: widget.durationSecs!))
        : null;

    return Padding(
      padding: const EdgeInsets.only(bottom: Nova.space2),
      child: MouseRegion(
        onEnter: (_) => setState(() => _hovered = true),
        onExit: (_) => setState(() => _hovered = false),
        child: FocusSurface(
          onTap: widget.onTap,
          focusNode: widget.focusNode,
          autofocus: widget.autofocus,
          onFocusChange: (v) => setState(() => _focused = v),
          radius: Nova.radiusCard,
          scale: 1.01,
          bloom: false,
          selected: widget.playing,
          semanticLabel: '${widget.number}. ${widget.title}',
          child: AnimatedContainer(
            duration: Motion.duration(context, Nova.hover),
            curve: Ease.enter,
            padding: const EdgeInsets.all(Nova.space2 + 2),
            decoration: BoxDecoration(
              color: widget.playing
                  ? AppColors.surfaceWarm
                  : (active ? AppColors.surface2 : Colors.transparent),
              borderRadius: BorderRadius.circular(Nova.radiusCard),
            ),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                SizedBox(
                  width: 140,
                  child: AspectRatio(
                    aspectRatio: 16 / 9,
                    child: ClipRRect(
                      borderRadius: BorderRadius.circular(Nova.radiusControl),
                      child: Stack(
                        fit: StackFit.expand,
                        children: [
                          NetworkPoster(
                            url: widget.imageUrl,
                            title: widget.title,
                            width: 140,
                            radius: 0,
                          ),
                          AnimatedOpacity(
                            opacity: active || widget.playing ? 1 : 0,
                            duration: Motion.duration(context, Nova.hover),
                            child: ColoredBox(
                              color: Colors.black.withValues(alpha: 0.46),
                              child: Icon(
                                widget.playing
                                    ? Icons.graphic_eq_rounded
                                    : Icons.play_arrow_rounded,
                                color: Colors.white,
                                size: 26,
                              ),
                            ),
                          ),
                          if (hasProgress)
                            PositionedDirectional(
                              start: 0,
                              end: 0,
                              bottom: 0,
                              child: ProgressBar(
                                value: widget.progress!,
                                height: 2,
                              ),
                            ),
                        ],
                      ),
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
                          SizedBox(
                            width: 22,
                            child: Text(
                              '${widget.number}',
                              textDirection: TextDirection.ltr,
                              style: AppText.control.copyWith(
                                color: widget.playing
                                    ? AppColors.primary
                                    : AppColors.textMuted,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                          ),
                          const SizedBox(width: Nova.space2),
                          Expanded(
                            child: Text(
                              widget.title,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: AppText.control,
                            ),
                          ),
                          if (widget.watched && !widget.playing) ...[
                            const SizedBox(width: Nova.space2),
                            const Icon(
                              Icons.check_rounded,
                              size: 15,
                              color: AppColors.goldBright,
                            ),
                          ],
                          if (runtime != null) ...[
                            const SizedBox(width: Nova.space3),
                            Text(
                              runtime,
                              textDirection: TextDirection.ltr,
                              style: AppText.timecode.copyWith(
                                color: AppColors.textMuted,
                              ),
                            ),
                          ],
                        ],
                      ),
                      if (widget.plot != null &&
                          widget.plot!.trim().isNotEmpty) ...[
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
      ),
    );
  }
}

/// A category / filter pill. The selected one is ember; the rest are quiet.
///
/// Its natural height is **36 px** — 18 px of type, 8 px of padding either side,
/// and the hairline. A horizontal `ListView` hands its children a *tight* cross
/// axis, so a strip shorter than that does not shrink the pill, it overflows the
/// label out of the bottom of it. Give the strip 36 or more.
class CategoryPill extends StatefulWidget {
  const CategoryPill({
    super.key,
    required this.label,
    required this.selected,
    required this.onTap,
    this.count,
    this.focusNode,
    this.autofocus = false,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;
  final int? count;
  final FocusNode? focusNode;
  final bool autofocus;

  @override
  State<CategoryPill> createState() => _CategoryPillState();
}

class _CategoryPillState extends State<CategoryPill> {
  bool _hovered = false;
  bool _focused = false;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      selected: widget.selected,
      label: widget.label,
      child: FocusableActionDetector(
        focusNode: widget.focusNode,
        autofocus: widget.autofocus,
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
          child: AnimatedContainer(
            duration: Motion.duration(context, Nova.hover),
            curve: Ease.enter,
            padding: const EdgeInsets.symmetric(
              horizontal: Nova.space4,
              vertical: Nova.space2,
            ),
            decoration: BoxDecoration(
              gradient: widget.selected ? AppColors.emberGradient : null,
              color: widget.selected
                  ? null
                  : (_hovered ? AppColors.surface3 : AppColors.surface2),
              borderRadius: BorderRadius.circular(999),
              border: Border.all(
                color: widget.selected
                    ? Colors.transparent
                    : AppColors.borderSubtle,
              ),
              boxShadow: focusRing(_focused),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  widget.label,
                  style: AppText.control.copyWith(
                    color: widget.selected
                        ? Colors.white
                        : AppColors.textSecondary,
                    fontWeight: widget.selected
                        ? FontWeight.w600
                        : FontWeight.w500,
                  ),
                ),
                if (widget.count != null && widget.count! > 0) ...[
                  const SizedBox(width: Nova.space2),
                  Text(
                    Fmt.compact(widget.count!),
                    textDirection: TextDirection.ltr,
                    style: AppText.caption.copyWith(
                      color: widget.selected
                          ? Colors.white.withValues(alpha: 0.82)
                          : AppColors.textMuted,
                    ),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// A row in a settings list or a popover menu: leading glyph, two lines of type,
/// a control at the end.
class ListRow extends StatefulWidget {
  const ListRow({
    super.key,
    required this.title,
    this.subtitle,
    this.leading,
    this.trailing,
    this.onTap,
    this.selected = false,
    this.danger = false,
    this.focusNode,
    this.autofocus = false,
  });

  final String title;
  final String? subtitle;
  final Widget? leading;
  final Widget? trailing;
  final VoidCallback? onTap;
  final bool selected;
  final bool danger;
  final FocusNode? focusNode;
  final bool autofocus;

  @override
  State<ListRow> createState() => _ListRowState();
}

class _ListRowState extends State<ListRow> {
  bool _hovered = false;
  bool _focused = false;

  @override
  Widget build(BuildContext context) {
    final active = _hovered || _focused;
    final tint = widget.danger
        ? AppColors.danger
        : (widget.selected ? AppColors.primaryBright : AppColors.textPrimary);

    final body = AnimatedContainer(
      duration: Motion.duration(context, Nova.hover),
      curve: Ease.enter,
      padding: const EdgeInsets.symmetric(
        horizontal: Nova.space4,
        vertical: Nova.space3,
      ),
      decoration: BoxDecoration(
        color: widget.selected
            ? AppColors.surfaceWarm
            : (active && widget.onTap != null
                  ? AppColors.surface2
                  : Colors.transparent),
        borderRadius: BorderRadius.circular(Nova.radiusControl),
      ),
      child: Row(
        children: [
          if (widget.leading != null) ...[
            widget.leading!,
            const SizedBox(width: Nova.space3),
          ],
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  widget.title,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppText.control.copyWith(color: tint),
                ),
                if (widget.subtitle != null && widget.subtitle!.isNotEmpty) ...[
                  const SizedBox(height: 3),
                  Text(widget.subtitle!, style: AppText.caption),
                ],
              ],
            ),
          ),
          if (widget.trailing != null) ...[
            const SizedBox(width: Nova.space3),
            widget.trailing!,
          ],
        ],
      ),
    );

    if (widget.onTap == null) return body;

    return MouseRegion(
      onEnter: (_) => setState(() => _hovered = true),
      onExit: (_) => setState(() => _hovered = false),
      child: FocusSurface(
        onTap: widget.onTap,
        focusNode: widget.focusNode,
        autofocus: widget.autofocus,
        onFocusChange: (v) => setState(() => _focused = v),
        radius: Nova.radiusControl,
        scale: 1.0,
        bloom: false,
        selected: widget.selected,
        semanticLabel: widget.title,
        child: body,
      ),
    );
  }
}

/// One number, on a plate. The dashboard's unit: a count of channels, a cache
/// size, days left on a subscription.
///
/// The value is the only thing here with any weight to it, because the value is
/// the only thing anyone reads.
class StatTile extends StatelessWidget {
  const StatTile({
    super.key,
    required this.value,
    required this.label,
    this.icon,
    this.accent = false,
    this.trailing,
  });

  /// Pre-formatted, and never invented. If there is no number, there is no tile.
  final String value;

  final String label;
  final IconData? icon;

  /// Ember, for the one stat on the strip that matters most.
  final bool accent;

  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    return SolidCard(
      padding: const EdgeInsets.all(Nova.space4),
      child: Row(
        children: [
          if (icon != null) ...[
            Container(
              width: 38,
              height: 38,
              decoration: BoxDecoration(
                gradient: accent ? AppColors.emberGradient : null,
                color: accent ? null : AppColors.surface3,
                borderRadius: BorderRadius.circular(Nova.radiusControl - 2),
              ),
              child: Icon(
                icon,
                size: 19,
                color: accent ? Colors.white : AppColors.textSecondary,
              ),
            ),
            const SizedBox(width: Nova.space3),
          ],
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  value,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppText.title.copyWith(
                    color: accent ? AppColors.primaryBright : AppColors.textPrimary,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  label,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppText.caption,
                ),
              ],
            ),
          ),
          if (trailing != null) ...[
            const SizedBox(width: Nova.space2),
            trailing!,
          ],
        ],
      ),
    );
  }
}

/// A widget in the dashboard strip — glass, because it floats over the scene
/// rather than scrolling with a wall of cards.
class WidgetTile extends StatelessWidget {
  const WidgetTile({
    super.key,
    required this.title,
    required this.child,
    this.icon,
    this.trailing,
    this.glow = false,
  });

  final String title;
  final Widget child;
  final IconData? icon;
  final Widget? trailing;

  /// The one primary surface on a screen. More than one, and neither is primary.
  final bool glow;

  @override
  Widget build(BuildContext context) {
    return GlassPanel(
      radius: Nova.radiusPanel,
      glow: glow,
      padding: const EdgeInsets.all(Nova.space4 + 2),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            children: [
              if (icon != null) ...[
                Icon(icon, size: 15, color: AppColors.textMuted),
                const SizedBox(width: Nova.space2),
              ],
              Expanded(
                child: Text(
                  title,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppText.label,
                ),
              ),
              if (trailing != null) trailing!,
            ],
          ),
          const SizedBox(height: Nova.space3),
          child,
        ],
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
              boxShadow: on
                  ? const [
                      BoxShadow(
                        color: Color(0x552E7BFF),
                        blurRadius: 8,
                        spreadRadius: -1,
                      ),
                    ]
                  : null,
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

/// The one progress bar in the app.
///
/// A themed [LinearProgressIndicator] draws its track in the surface colour,
/// which is invisible on top of artwork — so the track here is always dark and
/// the fill is always the ember gradient, wherever it lands.
class ProgressBar extends StatelessWidget {
  const ProgressBar({
    super.key,
    required this.value,
    this.height = 4,
    this.track = const Color(0x73000000),
  });

  final double value;
  final double height;
  final Color track;

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(height),
      child: SizedBox(
        height: height,
        child: Stack(
          fit: StackFit.expand,
          children: [
            ColoredBox(color: track),
            FractionallySizedBox(
              alignment: AlignmentDirectional.centerStart,
              widthFactor: value.clamp(0.0, 1.0),
              child: const DecoratedBox(
                decoration: BoxDecoration(gradient: AppColors.emberGradient),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
