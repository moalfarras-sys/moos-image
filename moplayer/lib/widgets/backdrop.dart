import 'dart:ui' as ui;

import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';

import '../core/theme/app_colors.dart';
import '../core/theme/motion.dart';
import '../core/theme/nova.dart';

/// The artwork behind a hero, and the reason text on top of it is always legible.
///
/// Poster art is arbitrary. A film's backdrop can be a black frame or a snow
/// field, and a title laid over it has to survive both — so the image is never
/// the bottom layer of the hero, the scrim is:
///
///  1. the artwork, optionally softened, so it reads as *ambience* and not as a
///     picture competing with the copy in front of it;
///  2. [AppColors.heroScrim] — dark on the leading edge, transparent on the
///     trailing one, **and it flips in Arabic**, because in Arabic the copy sits
///     on the right and a scrim that did not flip would darken the empty side;
///  3. [AppColors.heroFloor], so the hero does not end at a hard horizontal line
///     with the content below it starting abruptly underneath.
///
/// When [imageUrl] changes the two images cross-fade over [Nova.hero] — the one
/// slow transition in the app, because the backdrop changing is the one thing on
/// screen that is *supposed* to be noticed.
class Backdrop extends StatelessWidget {
  const Backdrop({
    super.key,
    required this.imageUrl,
    this.child,
    this.scrim = true,
    this.floor = true,
    this.blur = 0,
    this.darken = 0,
    this.fit = BoxFit.cover,
    this.alignment = Alignment.topCenter,
    this.duration = Nova.hero,
  });

  final String? imageUrl;

  /// The copy that sits on the artwork. It is a child rather than a sibling so
  /// that it is impossible to draw one without the other's scrim underneath.
  final Widget? child;

  final bool scrim;
  final bool floor;

  /// Softens the artwork. A hero page wants 0 (the picture *is* the point); an
  /// ambient wash behind a dialog or a now-playing panel wants 20–40.
  final double blur;

  /// An extra flat dim on top of the artwork, 0–1, for copy-heavy heroes.
  final double darken;

  final BoxFit fit;
  final Alignment alignment;
  final Duration duration;

  @override
  Widget build(BuildContext context) {
    final rtl = Directionality.of(context) == TextDirection.rtl;
    final link = imageUrl?.trim();

    Widget art = link == null || link.isEmpty
        ? const ColoredBox(
            key: ValueKey('backdrop-empty'),
            color: AppColors.surface1,
          )
        : CachedNetworkImage(
            key: ValueKey(link),
            imageUrl: link,
            fit: fit,
            alignment: alignment,
            width: double.infinity,
            height: double.infinity,
            // A backdrop is the one image in the app that is allowed to be big:
            // it fills the window, and undersizing it is visible as mush.
            memCacheWidth: 1920,
            filterQuality: FilterQuality.medium,
            // The crossfade below owns the transition; a second fade inside the
            // image would make it arrive twice.
            fadeInDuration: Duration.zero,
            fadeOutDuration: Duration.zero,
            placeholder: (_, _) => const ColoredBox(color: AppColors.surface1),
            errorWidget: (_, _, _) =>
                const ColoredBox(color: AppColors.surface1),
          );

    if (blur > 0) {
      art = ImageFiltered(
        imageFilter: ui.ImageFilter.blur(
          sigmaX: blur,
          sigmaY: blur,
          tileMode: TileMode.decal,
        ),
        child: art,
      );
    }

    return Stack(
      fit: StackFit.expand,
      children: [
        // The plate under the crossfade. Without it, the outgoing image shows
        // through the incoming one's transparent half for half a second.
        const ColoredBox(color: AppColors.surface0),

        AnimatedSwitcher(
          duration: Motion.duration(context, duration),
          switchInCurve: Ease.fade,
          switchOutCurve: Ease.fade,
          // Both frames stay put and simply dissolve. A scale here would make
          // the whole window appear to breathe every time the selection moves.
          layoutBuilder: (current, previous) =>
              Stack(fit: StackFit.expand, children: [...previous, ?current]),
          child: art,
        ),

        if (darken > 0)
          ColoredBox(
            color: Colors.black.withValues(alpha: darken.clamp(0.0, 1.0)),
          ),

        if (scrim)
          DecoratedBox(decoration: BoxDecoration(gradient: _heroScrim(rtl))),

        if (floor)
          const DecoratedBox(
            decoration: BoxDecoration(gradient: AppColors.heroFloor),
          ),

        ?child,
      ],
    );
  }

  /// [AppColors.heroScrim], flipped for Arabic. The colours and stops are the
  /// palette's; only the direction is this widget's business.
  static LinearGradient _heroScrim(bool rtl) {
    const source = AppColors.heroScrim;
    return LinearGradient(
      begin: rtl ? Alignment.centerRight : Alignment.centerLeft,
      end: rtl ? Alignment.centerLeft : Alignment.centerRight,
      colors: source.colors,
      stops: source.stops,
    );
  }
}

/// The app's canvas: the scene gradient, with two ember blooms bleeding in from
/// opposite corners.
///
/// The blooms are painted with a radial gradient rather than a blurred layer — a
/// [BackdropFilter] this large would cost a full-screen save-layer on every
/// frame, and this thing is behind *everything*.
class SceneBackdrop extends StatelessWidget {
  const SceneBackdrop({super.key, required this.child, this.showGlow = true});

  final Widget child;
  final bool showGlow;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: const BoxDecoration(gradient: AppColors.sceneGradient),
      child: Stack(
        children: [
          if (showGlow) ...[
            const Positioned(
              top: -140,
              left: -100,
              child: _Bloom(color: AppColors.primary, size: 420, opacity: 0.13),
            ),
            const Positioned(
              bottom: -160,
              right: -120,
              child: _Bloom(color: AppColors.ember, size: 480, opacity: 0.10),
            ),
          ],
          Positioned.fill(child: child),
        ],
      ),
    );
  }
}

class _Bloom extends StatelessWidget {
  const _Bloom({
    required this.color,
    required this.size,
    required this.opacity,
  });

  final Color color;
  final double size;
  final double opacity;

  @override
  Widget build(BuildContext context) {
    return IgnorePointer(
      child: Container(
        width: size,
        height: size,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          gradient: AppColors.glow(color, opacity: opacity),
        ),
      ),
    );
  }
}
