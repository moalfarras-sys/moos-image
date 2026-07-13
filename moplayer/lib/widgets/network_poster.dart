import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';

import '../core/theme/app_colors.dart';
import '../core/theme/app_typography.dart';
import '../core/theme/nova.dart';

/// Artwork from an IPTV panel, which is to say: artwork that may be a 404, an
/// HTML error page with an image content-type, a 4000×6000 poster, or nothing at
/// all. Every one of those has to end in a rectangle of the right size.
class NetworkPoster extends StatelessWidget {
  const NetworkPoster({
    super.key,
    required this.url,
    required this.title,
    this.radius = Nova.radiusCard,
    this.fit = BoxFit.cover,
    this.logoMode = false,
  });

  final String? url;
  final String title;
  final double radius;
  final BoxFit fit;

  /// Channel logos are transparent PNGs of wildly varying aspect. They are
  /// letterboxed with padding instead of cropped, or half the logo is gone.
  final bool logoMode;

  @override
  Widget build(BuildContext context) {
    final borderRadius = BorderRadius.circular(radius);
    final link = url;

    return ClipRRect(
      borderRadius: borderRadius,
      child: ColoredBox(
        color: AppColors.surface2,
        child: (link == null || link.isEmpty)
            ? _Fallback(title: title, logoMode: logoMode)
            : CachedNetworkImage(
                imageUrl: link,
                fit: logoMode ? BoxFit.contain : fit,
                width: double.infinity,
                height: double.infinity,
                // A poster wall of 60 items must not decode 60 full-size images.
                memCacheWidth: logoMode ? 240 : 480,
                fadeInDuration: Nova.fast,
                placeholder: (_, _) => const ColoredBox(color: AppColors.surface2),
                errorWidget: (_, _, _) => _Fallback(title: title, logoMode: logoMode),
              ),
      ),
    );
  }
}

/// What a missing poster looks like. Not a broken-image glyph — the initials, on
/// the surface colour, which reads as deliberate rather than failed.
class _Fallback extends StatelessWidget {
  const _Fallback({required this.title, required this.logoMode});

  final String title;
  final bool logoMode;

  @override
  Widget build(BuildContext context) {
    final initials = title.trim().isEmpty
        ? '?'
        : title
              .trim()
              .split(RegExp(r'\s+'))
              .take(2)
              .map((w) => w.characters.first)
              .join()
              .toUpperCase();

    return DecoratedBox(
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            AppColors.surface2,
            AppColors.surface3.withValues(alpha: 0.8),
          ],
        ),
      ),
      child: Center(
        child: Text(
          initials,
          style: (logoMode ? AppText.body : AppText.headline).copyWith(
            color: AppColors.textMuted,
            fontWeight: FontWeight.w700,
          ),
        ),
      ),
    );
  }
}
