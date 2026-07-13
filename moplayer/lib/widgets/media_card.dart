import 'package:flutter/material.dart';

import '../core/theme/app_colors.dart';
import '../core/theme/app_typography.dart';
import '../core/theme/nova.dart';
import 'network_poster.dart';

/// A poster in a grid or a rail. The unit the whole catalogue is built from.
///
/// Everything interactive appears on hover and nowhere else: a desktop has a
/// cursor, so a card does not need to wear its play button, its favourite
/// button and its rating at rest. At rest it is artwork and a title, which is
/// what makes a wall of forty of them readable.
class PosterCard extends StatefulWidget {
  const PosterCard({
    super.key,
    required this.title,
    this.subtitle,
    this.imageUrl,
    this.onTap,
    this.onPlay,
    this.isFavorite = false,
    this.onToggleFavorite,
    this.progress,
    this.badge,
    this.aspectRatio = 2 / 3,
  });

  final String title;
  final String? subtitle;
  final String? imageUrl;

  /// Opening the detail page.
  final VoidCallback? onTap;

  /// Playing it directly, skipping the detail page. Bound to the hover button.
  final VoidCallback? onPlay;

  final bool isFavorite;
  final VoidCallback? onToggleFavorite;

  /// 0–1. Draws the resume bar along the bottom of the artwork.
  final double? progress;

  /// A short overlay label: a rating, a year, `LIVE`.
  final Widget? badge;

  final double aspectRatio;

  @override
  State<PosterCard> createState() => _PosterCardState();
}

class _PosterCardState extends State<PosterCard> {
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
            AspectRatio(
              aspectRatio: widget.aspectRatio,
              child: AnimatedScale(
                scale: _hovered ? 1.035 : 1,
                duration: Nova.normal,
                curve: Curves.easeOutCubic,
                child: AnimatedContainer(
                  duration: Nova.normal,
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(Nova.radiusCard),
                    boxShadow: [
                      if (_hovered)
                        BoxShadow(
                          color: AppColors.primary.withValues(alpha: 0.22),
                          blurRadius: 28,
                          spreadRadius: -6,
                          offset: const Offset(0, 8),
                        ),
                    ],
                  ),
                  child: Stack(
                    fit: StackFit.expand,
                    children: [
                      NetworkPoster(url: widget.imageUrl, title: widget.title),

                      // The scrim only exists under something. Painting it on a
                      // card with no badge and no hover would only dull the art.
                      if (_hovered || widget.badge != null || widget.progress != null)
                        DecoratedBox(
                          decoration: const BoxDecoration(
                            gradient: AppColors.posterScrim,
                            borderRadius: BorderRadius.all(
                              Radius.circular(Nova.radiusCard),
                            ),
                          ),
                        ),

                      if (widget.badge != null)
                        Positioned(top: Nova.space2, left: Nova.space2, child: widget.badge!),

                      if (widget.onToggleFavorite != null && (_hovered || widget.isFavorite))
                        Positioned(
                          top: Nova.space1,
                          right: Nova.space1,
                          child: _CardIcon(
                            icon: widget.isFavorite
                                ? Icons.favorite_rounded
                                : Icons.favorite_border_rounded,
                            color: widget.isFavorite
                                ? AppColors.primary
                                : Colors.white,
                            onTap: widget.onToggleFavorite!,
                          ),
                        ),

                      if (_hovered && widget.onPlay != null)
                        Center(
                          child: _PlayBubble(onTap: widget.onPlay!),
                        ),

                      if (widget.progress != null)
                        Positioned(
                          left: 0,
                          right: 0,
                          bottom: 0,
                          child: ClipRRect(
                            borderRadius: const BorderRadius.vertical(
                              bottom: Radius.circular(Nova.radiusCard),
                            ),
                            child: LinearProgressIndicator(
                              value: widget.progress!.clamp(0, 1),
                              minHeight: 3,
                              backgroundColor: Colors.white24,
                              valueColor: const AlwaysStoppedAnimation(
                                AppColors.primary,
                              ),
                            ),
                          ),
                        ),
                    ],
                  ),
                ),
              ),
            ),
            const SizedBox(height: Nova.space2),
            Text(
              widget.title,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: AppText.control.copyWith(
                color: _hovered ? AppColors.primary : AppColors.textPrimary,
              ),
            ),
            if (widget.subtitle != null)
              Text(
                widget.subtitle!,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: AppText.caption,
              ),
          ],
        ),
      ),
    );
  }
}

class _PlayBubble extends StatelessWidget {
  const _PlayBubble({required this.onTap});

  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 48,
        height: 48,
        decoration: BoxDecoration(
          gradient: AppColors.emberGradient,
          shape: BoxShape.circle,
          boxShadow: [
            BoxShadow(
              color: AppColors.primary.withValues(alpha: 0.45),
              blurRadius: 22,
              spreadRadius: -2,
            ),
          ],
        ),
        // Play glyphs point at the content, not at the reading direction: this
        // one stays pointing right in Arabic too, which is why it is wrapped.
        child: const Directionality(
          textDirection: TextDirection.ltr,
          child: Icon(Icons.play_arrow_rounded, color: Colors.white, size: 28),
        ),
      ),
    );
  }
}

class _CardIcon extends StatelessWidget {
  const _CardIcon({required this.icon, required this.color, required this.onTap});

  final IconData icon;
  final Color color;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(Nova.space2),
        decoration: const BoxDecoration(
          color: Color(0x8C05070C),
          shape: BoxShape.circle,
        ),
        child: Icon(icon, size: 16, color: color),
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
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          const SizedBox(
            width: 5,
            height: 5,
            child: DecoratedBox(
              decoration: BoxDecoration(color: Colors.white, shape: BoxShape.circle),
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

/// A rating chip. Xtream ratings arrive as anything from `7.4` to `"N/A"`.
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
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.star_rounded, size: 12, color: AppColors.gold),
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
