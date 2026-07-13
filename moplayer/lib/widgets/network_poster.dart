import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';

import '../core/theme/app_colors.dart';
import '../core/theme/app_typography.dart';
import '../core/theme/motion.dart';
import '../core/theme/nova.dart';
import '../core/utils/formatters.dart';

/// Artwork from an IPTV panel, which is to say: artwork that may be a 404, an
/// HTML error page with an image content-type, a 4000×6000 poster, or nothing at
/// all. Every one of those has to end in a rectangle of the right size.
///
/// Two things here are load-bearing on a laptop GPU:
///
///  * **The decode is sized to the layout.** A panel's poster is routinely
///    1000×1500; decoding sixty of those into 180 px cards is ~350 MB of image
///    cache and a stutter on every scroll. [memCacheWidth] is derived from the
///    box the image will actually occupy, quantised so that a grid of slightly
///    different widths still shares cache entries.
///  * **The fallback is art, not an error.** A broken-image glyph is the single
///    loudest way to tell a user their library is junk. A missing poster gets
///    the title's initials on a warm plate, which reads as *designed*.
class NetworkPoster extends StatelessWidget {
  const NetworkPoster({
    super.key,
    required this.url,
    required this.title,
    this.radius = Nova.radiusCard,
    this.fit = BoxFit.cover,
    this.logoMode = false,
    this.width,
    this.background,
    this.alignment = Alignment.center,
    this.fadeIn = true,
  });

  final String? url;
  final String title;
  final double radius;
  final BoxFit fit;

  /// Channel logos are transparent PNGs of wildly varying aspect. They are
  /// letterboxed with padding instead of cropped, or half the logo is gone.
  final bool logoMode;

  /// The width this poster will occupy, in logical pixels. Given, the decode is
  /// sized to it; omitted, it is measured — which costs a [LayoutBuilder], so
  /// pass it when you already know (a rail's `itemWidth`, a fixed-size logo).
  final double? width;

  final Color? background;
  final Alignment alignment;

  /// Off inside a hero, where the [Backdrop]'s own crossfade already owns the
  /// transition and a second fade just makes the image arrive twice.
  final bool fadeIn;

  @override
  Widget build(BuildContext context) {
    if (width != null) return _build(context, width!);
    return LayoutBuilder(
      builder: (context, constraints) => _build(
        context,
        constraints.hasBoundedWidth ? constraints.maxWidth : 480,
      ),
    );
  }

  Widget _build(BuildContext context, double layoutWidth) {
    final borderRadius = BorderRadius.circular(radius);
    final link = url?.trim();
    final plate = background ?? AppColors.surface2;

    final Widget content;
    if (link == null || link.isEmpty) {
      content = _Fallback(title: title, logoMode: logoMode);
    } else {
      final ratio = MediaQuery.devicePixelRatioOf(context);
      // Quantised to 64 px steps: a grid whose columns land on 178.4 px and one
      // that lands on 181.2 px must not decode the same poster twice.
      final target = (layoutWidth * ratio / 64).ceil() * 64;
      final cacheWidth = target.clamp(64, 1536);

      content = CachedNetworkImage(
        imageUrl: link,
        fit: logoMode ? BoxFit.contain : fit,
        alignment: alignment,
        width: double.infinity,
        height: double.infinity,
        memCacheWidth: cacheWidth,
        filterQuality: FilterQuality.medium,
        fadeInDuration: fadeIn
            ? Motion.duration(context, Nova.panel)
            : Duration.zero,
        fadeInCurve: Ease.fade,
        fadeOutDuration: Duration.zero,
        placeholder: (_, _) => ColoredBox(color: plate),
        errorWidget: (_, _, _) => _Fallback(title: title, logoMode: logoMode),
      );
    }

    return ClipRRect(
      borderRadius: borderRadius,
      child: ColoredBox(
        color: plate,
        child: logoMode && (link != null && link.isNotEmpty)
            // A logo is letterboxed, and it needs air around it or it reads as
            // a sticker slapped onto the tile.
            ? Padding(
                padding: const EdgeInsets.all(Nova.space2),
                child: content,
              )
            : content,
      ),
    );
  }
}

/// What a missing poster looks like. Not a broken-image glyph — the initials, on
/// a warm plate, which reads as deliberate rather than failed.
class _Fallback extends StatelessWidget {
  const _Fallback({required this.title, required this.logoMode});

  final String title;
  final bool logoMode;

  @override
  Widget build(BuildContext context) {
    final initials = Fmt.initials(title);

    return DecoratedBox(
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [AppColors.surface2, AppColors.surfaceWarm],
        ),
      ),
      child: LayoutBuilder(
        builder: (context, constraints) {
          // The monogram is sized off the box, so the same widget works at 42 px
          // in a channel row and at 220 px in a poster grid.
          final side = constraints.biggest.shortestSide;
          final size = (side * (logoMode ? 0.34 : 0.26)).clamp(11.0, 46.0);

          return Stack(
            fit: StackFit.expand,
            children: [
              // A single ember sheen across the corner. It is what stops forty
              // fallbacks in a grid from reading as forty holes.
              const DecoratedBox(
                decoration: BoxDecoration(
                  gradient: RadialGradient(
                    center: Alignment(-0.7, -0.8),
                    radius: 1.3,
                    colors: [Color(0x14FF8A1F), Color(0x00000000)],
                  ),
                ),
              ),
              Center(
                child: Text(
                  initials,
                  maxLines: 1,
                  textDirection: TextDirection.ltr,
                  style: AppText.headline.copyWith(
                    fontSize: size,
                    height: 1,
                    fontWeight: FontWeight.w700,
                    letterSpacing: 1,
                    color: AppColors.textMuted.withValues(alpha: 0.72),
                  ),
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}
