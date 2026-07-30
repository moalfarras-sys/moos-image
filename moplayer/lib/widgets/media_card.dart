import 'package:flutter/material.dart';

import '../core/theme/app_colors.dart';
import '../core/theme/app_typography.dart';
import '../core/theme/motion.dart';
import '../core/theme/nova.dart';
import '../core/utils/formatters.dart';
import 'buttons.dart';
import 'focus_surface.dart';
import 'network_poster.dart';

/// The shell every card in the app is built on: artwork that lifts, and a label
/// under it that does not.
///
/// Two decisions here are the whole reason the wall reads as a wall:
///
///  * **Only the artwork is inside the [FocusSurface].** The ring hugs the
///    picture, not a loose paragraph of type under it — and because the label
///    sits outside the lift, a hovered card's title stays exactly where it was.
///    The card's *slot* never changes size, so no neighbour ever moves.
///  * **Hover and focus are one state, shared by both halves.** Pointing at the
///    title lights the artwork, and clicking the title opens the card, because a
///    user does not know or care that they are two widgets.
class _CardShell extends StatefulWidget {
  const _CardShell({
    required this.artwork,
    this.label,
    this.onTap,
    this.onPreview,
    this.focusNode,
    this.autofocus = false,
    this.semanticLabel,
    this.gap = Nova.space2,
  });

  /// The card became the one the user is looking at — hovered with a mouse, or
  /// reached with the keyboard. Both, deliberately: a preview pane that only
  /// answers the mouse is a preview pane a keyboard user never sees.
  final VoidCallback? onPreview;

  /// Built with the card's active (hovered *or* focused) state, so the quick
  /// actions can appear without the artwork owning a second hover listener.
  final Widget Function(BuildContext context, bool active) artwork;
  final Widget Function(BuildContext context, bool active)? label;

  final VoidCallback? onTap;
  final FocusNode? focusNode;
  final bool autofocus;
  final String? semanticLabel;

  /// The gap between the artwork and its label.
  final double gap;

  @override
  State<_CardShell> createState() => _CardShellState();
}

class _CardShellState extends State<_CardShell> {
  bool _hovered = false;
  bool _focused = false;

  bool get _active => _hovered || _focused;

  @override
  Widget build(BuildContext context) {
    return MouseRegion(
      onEnter: (_) {
        setState(() => _hovered = true);
        widget.onPreview?.call();
      },
      onExit: (_) => setState(() => _hovered = false),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          FocusSurface(
            onTap: widget.onTap,
            focusNode: widget.focusNode,
            autofocus: widget.autofocus,
            radius: Nova.radiusCard,
            // A modest lift. A poster that grows by ten per cent overlaps its
            // neighbours, and the wall stops being a wall.
            scale: 1.04,
            semanticLabel: widget.semanticLabel,
            onFocusChange: (v) {
              setState(() => _focused = v);
              if (v) widget.onPreview?.call();
            },
            child: widget.artwork(context, _active),
          ),
          if (widget.label != null) ...[
            SizedBox(height: widget.gap),
            // The label repeats what the [FocusSurface] already announces, so it
            // is excluded rather than read out twice.
            ExcludeSemantics(
              child: MouseRegion(
                cursor: widget.onTap == null
                    ? MouseCursor.defer
                    : SystemMouseCursors.click,
                child: GestureDetector(
                  onTap: widget.onTap,
                  behavior: HitTestBehavior.opaque,
                  child: widget.label!(context, _active),
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

/// What a screen reader is told about a card: the title, and the one line of
/// metadata under it if there is one.
String _describe(String title, String? subtitle) =>
    (subtitle == null || subtitle.isEmpty) ? title : '$title, $subtitle';

/// The two lines under every card. Fixed height by construction — one line each,
/// always — because a grid delegate has to be able to reserve room for it.
class _CardLabel extends StatelessWidget {
  const _CardLabel({required this.title, required this.active, this.subtitle});

  final String title;
  final String? subtitle;
  final bool active;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        AnimatedDefaultTextStyle(
          duration: Motion.duration(context, Nova.hover),
          curve: Ease.enter,
          style: AppText.control.copyWith(
            color: active ? AppColors.primaryBright : AppColors.textPrimary,
          ),
          child: Text(title, maxLines: 1, overflow: TextOverflow.ellipsis),
        ),
        if (subtitle != null && subtitle!.isNotEmpty)
          Text(
            subtitle!,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: AppText.caption,
          ),
      ],
    );
  }
}

/// A poster in a grid or a rail. The unit the whole catalogue is built from.
///
/// Everything interactive appears on hover or focus and nowhere else: at rest a
/// card is artwork and a title, and that is what makes a wall of forty of them
/// readable. The quick actions live *on the artwork* and the title lives *under*
/// it, so revealing them never covers the one thing the user is reading.
class PosterCard extends StatelessWidget {
  const PosterCard({
    super.key,
    required this.title,
    this.subtitle,
    this.imageUrl,
    this.onTap,
    this.onPlay,
    this.onPreview,
    this.isFavorite = false,
    this.onToggleFavorite,
    this.progress,
    this.badge,
    this.aspectRatio = 2 / 3,
    this.rating,
    this.watched = false,
    this.width,
    this.focusNode,
    this.autofocus = false,
    this.semanticLabel,
  });

  final String title;
  final String? subtitle;
  final String? imageUrl;

  /// Opening the detail page.
  final VoidCallback? onTap;

  /// Playing it directly, skipping the detail page. Bound to the hover button.
  final VoidCallback? onPlay;

  /// This card became the one under the eye — hovered, or reached by keyboard.
  /// The browse pages hang their preview pane off it.
  final VoidCallback? onPreview;

  final bool isFavorite;
  final VoidCallback? onToggleFavorite;

  /// 0–1. Draws the resume bar along the bottom of the artwork. Null — not
  /// zero — when the item has never been started.
  final double? progress;

  /// A short overlay label on the leading corner: a rating, a year, `LIVE`.
  final Widget? badge;

  final double aspectRatio;

  /// A real rating, or null. Draws a [RatingBadge] when [badge] is not given —
  /// and draws **nothing** at 0, because an IPTV panel returns 0 for "we do not
  /// know", and a wall of zero-star films is a lie about the library.
  final double? rating;

  /// Finished. A quiet tick, not a banner.
  final bool watched;

  /// The card's laid-out width, passed through to size the image decode.
  final double? width;

  final FocusNode? focusNode;
  final bool autofocus;
  final String? semanticLabel;

  @override
  Widget build(BuildContext context) {
    final hasProgress = progress != null && progress! > 0.01;
    final corner =
        badge ?? ((rating ?? 0) > 0 ? RatingBadge(rating: rating!) : null);

    return _CardShell(
      onTap: onTap,
      onPreview: onPreview,
      focusNode: focusNode,
      autofocus: autofocus,
      semanticLabel: semanticLabel ?? _describe(title, subtitle),
      artwork: (context, active) => AspectRatio(
        aspectRatio: aspectRatio,
        child: Stack(
          fit: StackFit.expand,
          children: [
            NetworkPoster(url: imageUrl, title: title, width: width, radius: 0),

            // The scrim only exists under something. Painting it on a card with
            // no badge, no bar and no hover would only dull the art.
            if (active || corner != null || hasProgress || watched)
              const DecoratedBox(
                decoration: BoxDecoration(gradient: AppColors.posterScrim),
              ),

            if (corner != null)
              PositionedDirectional(
                top: Nova.space2,
                start: Nova.space2,
                child: corner,
              ),

            // The pointer affordances. They are deliberately outside the focus
            // tree: on a remote, a favourite button inside every poster turns a
            // left-right walk across the wall into a walk *through* each card.
            _Reveals(
              children: [
                if (onToggleFavorite != null && (active || isFavorite))
                  PositionedDirectional(
                    top: Nova.space2,
                    end: Nova.space2,
                    child: IconPill(
                      size: 30,
                      scrim: true,
                      icon: isFavorite
                          ? Icons.favorite_rounded
                          : Icons.favorite_border_rounded,
                      active: isFavorite,
                      onPressed: onToggleFavorite,
                    ),
                  ),

                if (onPlay != null)
                  Center(
                    child: _PlayReveal(active: active, onTap: onPlay!),
                  ),
              ],
            ),

            if (watched)
              const PositionedDirectional(
                bottom: Nova.space2,
                end: Nova.space2,
                child: _WatchedTick(),
              ),

            if (hasProgress)
              PositionedDirectional(
                start: 0,
                end: 0,
                bottom: 0,
                child: _EmberBar(value: progress!),
              ),
          ],
        ),
      ),
      label: (context, active) =>
          _CardLabel(title: title, subtitle: subtitle, active: active),
    );
  }
}

/// 16:9 — channels, episodes in a rail, and anything already started.
///
/// Wider than a poster because what the user is looking for on this card is
/// *where they left off*, not the artwork.
class LandscapeCard extends StatelessWidget {
  const LandscapeCard({
    super.key,
    required this.title,
    this.subtitle,
    this.imageUrl,
    this.onTap,
    this.onPlay,
    this.onDismiss,
    this.progress,
    this.caption,
    this.badge,
    this.isFavorite = false,
    this.onToggleFavorite,
    this.logoMode = false,
    this.showLabel = true,
    this.width,
    this.focusNode,
    this.autofocus = false,
    this.semanticLabel,
  });

  final String title;
  final String? subtitle;
  final String? imageUrl;
  final VoidCallback? onTap;

  /// The centre play button. When null, tapping the card plays it and the button
  /// still appears — a 16:9 card is almost always a thing you play.
  final VoidCallback? onPlay;

  /// Removing it from Continue Watching.
  final VoidCallback? onDismiss;

  /// 0–1.
  final double? progress;

  /// Pre-formatted copy laid over the foot of the artwork: "23 min left".
  final String? caption;

  final Widget? badge;
  final bool isFavorite;
  final VoidCallback? onToggleFavorite;

  /// The artwork is a transparent channel logo, not a still: letterbox it.
  final bool logoMode;

  /// The title under the card. Off when the card is the whole story (a channel
  /// wall where the logo *is* the name).
  final bool showLabel;

  final double? width;
  final FocusNode? focusNode;
  final bool autofocus;
  final String? semanticLabel;

  @override
  Widget build(BuildContext context) {
    final hasProgress = progress != null && progress! > 0.01;
    final play = onPlay ?? onTap;

    return _CardShell(
      onTap: onTap,
      focusNode: focusNode,
      autofocus: autofocus,
      semanticLabel: semanticLabel ?? _describe(title, subtitle),
      gap: Nova.space3,
      artwork: (context, active) => AspectRatio(
        aspectRatio: 16 / 9,
        child: Stack(
          fit: StackFit.expand,
          children: [
            NetworkPoster(
              url: imageUrl,
              title: title,
              width: width,
              radius: 0,
              logoMode: logoMode,
            ),

            if (active || badge != null || hasProgress || caption != null)
              const DecoratedBox(
                decoration: BoxDecoration(gradient: AppColors.posterScrim),
              ),

            if (badge != null)
              PositionedDirectional(
                top: Nova.space2,
                start: Nova.space2,
                child: badge!,
              ),

            _Reveals(
              children: [
                if (onDismiss != null && active)
                  PositionedDirectional(
                    top: Nova.space2,
                    end: Nova.space2,
                    child: IconPill(
                      icon: Icons.close_rounded,
                      size: 30,
                      scrim: true,
                      onPressed: onDismiss,
                    ),
                  )
                else if (onToggleFavorite != null && (active || isFavorite))
                  PositionedDirectional(
                    top: Nova.space2,
                    end: Nova.space2,
                    child: IconPill(
                      size: 30,
                      scrim: true,
                      icon: isFavorite
                          ? Icons.favorite_rounded
                          : Icons.favorite_border_rounded,
                      active: isFavorite,
                      onPressed: onToggleFavorite,
                    ),
                  ),

                if (play != null)
                  Center(
                    child: _PlayReveal(active: active, onTap: play, size: 46),
                  ),
              ],
            ),

            if (caption != null || hasProgress)
              PositionedDirectional(
                start: Nova.space3,
                end: Nova.space3,
                bottom: Nova.space3,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    if (caption != null)
                      Text(
                        caption!,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: AppText.caption.copyWith(
                          color: Colors.white.withValues(alpha: 0.92),
                        ),
                      ),
                    if (hasProgress) ...[
                      const SizedBox(height: Nova.space1 + 2),
                      _EmberBar(value: progress!, height: 3, rounded: true),
                    ],
                  ],
                ),
              ),
          ],
        ),
      ),
      label: showLabel
          ? (context, active) =>
                _CardLabel(title: title, subtitle: subtitle, active: active)
          : null,
    );
  }
}

/// One episode, as a card in a rail or a grid. (The row form — a thumbnail beside
/// a plot — is [EpisodeTile] in `tiles.dart`; this is the one that goes in a
/// shelf.)
class EpisodeCard extends StatelessWidget {
  const EpisodeCard({
    super.key,
    required this.number,
    required this.title,
    required this.onTap,
    this.imageUrl,
    this.durationSecs,
    this.progress,
    this.watched = false,
    this.playing = false,
    this.subtitle,
    this.width,
    this.focusNode,
    this.autofocus = false,
    this.semanticLabel,
  });

  /// The episode number. Drawn as a numeral, never translated — `S02E07` is the
  /// same string in every language this app speaks.
  final int number;

  final String title;
  final String? subtitle;
  final String? imageUrl;
  final int? durationSecs;

  /// 0–1, or null if never started.
  final double? progress;

  /// Finished.
  final bool watched;

  /// This episode is the one currently in the player.
  final bool playing;

  final VoidCallback onTap;
  final double? width;
  final FocusNode? focusNode;
  final bool autofocus;
  final String? semanticLabel;

  @override
  Widget build(BuildContext context) {
    final hasProgress = progress != null && progress! > 0.01;
    final runtime = (durationSecs ?? 0) > 0
        ? Fmt.duration(Duration(seconds: durationSecs!))
        : null;

    return _CardShell(
      onTap: onTap,
      focusNode: focusNode,
      autofocus: autofocus,
      semanticLabel: semanticLabel ?? '$number. $title',
      gap: Nova.space3,
      artwork: (context, active) => AspectRatio(
        aspectRatio: 16 / 9,
        child: Stack(
          fit: StackFit.expand,
          children: [
            NetworkPoster(url: imageUrl, title: title, width: width, radius: 0),
            const DecoratedBox(
              decoration: BoxDecoration(gradient: AppColors.posterScrim),
            ),

            // The number is the card's identity — it stays at rest, where the
            // eye can run down a shelf of them.
            PositionedDirectional(
              top: Nova.space2,
              start: Nova.space2,
              child: _NumberChip(number: number, playing: playing),
            ),

            if (watched && !playing)
              const PositionedDirectional(
                top: Nova.space2,
                end: Nova.space2,
                child: _WatchedTick(),
              ),

            _Reveals(
              children: [
                Center(
                  child: _PlayReveal(
                    active: active,
                    onTap: onTap,
                    size: 44,
                    icon: playing
                        ? Icons.graphic_eq_rounded
                        : Icons.play_arrow_rounded,
                  ),
                ),
              ],
            ),

            if (runtime != null)
              PositionedDirectional(
                bottom: hasProgress ? Nova.space2 + 2 : Nova.space2,
                end: Nova.space2,
                child: Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 6,
                    vertical: 2,
                  ),
                  decoration: BoxDecoration(
                    color: const Color(0xA605070C),
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Text(
                    runtime,
                    style: AppText.timecode.copyWith(fontSize: 11),
                    textDirection: TextDirection.ltr,
                  ),
                ),
              ),

            if (hasProgress)
              PositionedDirectional(
                start: 0,
                end: 0,
                bottom: 0,
                child: _EmberBar(value: progress!),
              ),
          ],
        ),
      ),
      label: (context, active) =>
          _CardLabel(title: title, subtitle: subtitle, active: active),
    );
  }
}

/// The resume bar. Ember, on a dark track — a themed [LinearProgressIndicator]
/// would be invisible against a bright poster.
class _EmberBar extends StatelessWidget {
  const _EmberBar({required this.value, this.height = 3, this.rounded = false});

  final double value;
  final double height;
  final bool rounded;

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(rounded ? height : 0),
      child: SizedBox(
        height: height,
        child: Stack(
          fit: StackFit.expand,
          children: [
            const ColoredBox(color: Color(0x73000000)),
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

/// The controls that appear on a card under the cursor.
///
/// They are lifted out of the focus tree wholesale. A poster wall is walked with
/// the arrow keys, and a favourite button *inside* every card turns a five-press
/// walk across a shelf into a fifteen-press one — so on a keyboard or a remote
/// you activate the card, and these belong to the mouse. They keep their
/// semantics, so a screen reader still finds them.
class _Reveals extends StatelessWidget {
  const _Reveals({required this.children});

  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    if (children.isEmpty) return const SizedBox.shrink();
    return ExcludeFocus(
      child: Stack(fit: StackFit.expand, children: children),
    );
  }
}

/// The play button that grows out of the artwork on hover. It scales and fades
/// rather than appearing, because a control that pops into existence under a
/// moving cursor is a control the user clicks by accident.
class _PlayReveal extends StatelessWidget {
  const _PlayReveal({
    required this.active,
    required this.onTap,
    this.size = 48,
    this.icon = Icons.play_arrow_rounded,
  });

  final bool active;
  final VoidCallback onTap;
  final double size;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    final reduced = Motion.isReduced(context);

    return IgnorePointer(
      ignoring: !active,
      child: AnimatedOpacity(
        opacity: active ? 1 : 0,
        duration: Motion.duration(context, Nova.hover),
        curve: Ease.enter,
        child: AnimatedScale(
          scale: reduced ? 1.0 : (active ? 1.0 : 0.82),
          duration: Motion.duration(context, Nova.hover),
          curve: Ease.enter,
          child: IconPill(
            icon: icon,
            size: size,
            filled: true,
            onPressed: onTap,
          ),
        ),
      ),
    );
  }
}

class _NumberChip extends StatelessWidget {
  const _NumberChip({required this.number, required this.playing});

  final int number;
  final bool playing;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
      decoration: BoxDecoration(
        gradient: playing ? AppColors.emberGradient : null,
        color: playing ? null : const Color(0xA605070C),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(
        '$number',
        textDirection: TextDirection.ltr,
        style: AppText.caption.copyWith(
          color: playing ? AppColors.onEmber : Colors.white,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}

/// Finished. Gold, because a watched title is *earned* rather than selected —
/// and small, because it is a fact about the item, not a call to act on it.
class _WatchedTick extends StatelessWidget {
  const _WatchedTick();

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 20,
      height: 20,
      decoration: BoxDecoration(
        color: const Color(0xCC05070C),
        shape: BoxShape.circle,
        border: Border.all(color: AppColors.gold.withValues(alpha: 0.35)),
      ),
      child: const Icon(
        Icons.check_rounded,
        size: 12,
        color: AppColors.goldBright,
      ),
    );
  }
}

/// The `LIVE` dot. Not the danger colour — an on-air badge is not an error.
class LiveBadge extends StatelessWidget {
  const LiveBadge({super.key, required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
      decoration: BoxDecoration(
        color: AppColors.live,
        borderRadius: BorderRadius.circular(6),
        boxShadow: [
          BoxShadow(
            color: AppColors.live.withValues(alpha: 0.35),
            blurRadius: 12,
            spreadRadius: -3,
          ),
        ],
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          const SizedBox(
            width: 5,
            height: 5,
            child: DecoratedBox(
              decoration: BoxDecoration(
                color: Colors.white,
                shape: BoxShape.circle,
              ),
            ),
          ),
          const SizedBox(width: 5),
          Text(
            label,
            style: AppText.caption.copyWith(
              color: Colors.white,
              fontWeight: FontWeight.w700,
              fontSize: 9.5,
              letterSpacing: 0.6,
            ),
          ),
        ],
      ),
    );
  }
}

/// A rating chip. Only ever built for a rating a panel actually returned —
/// see [PosterCard.rating].
class RatingBadge extends StatelessWidget {
  const RatingBadge({super.key, required this.rating});

  final double rating;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
      decoration: BoxDecoration(
        color: const Color(0xA605070C),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: AppColors.gold.withValues(alpha: 0.28)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.star_rounded, size: 12, color: AppColors.goldBright),
          const SizedBox(width: 3),
          Text(
            rating.toStringAsFixed(1),
            style: AppText.caption.copyWith(
              color: Colors.white,
              fontWeight: FontWeight.w700,
            ),
            textDirection: TextDirection.ltr,
          ),
        ],
      ),
    );
  }
}
