import 'dart:ui' as ui;

import 'package:flutter/material.dart';

/// Gradients, drawn as small pre-rendered images instead of as shaders.
///
/// **Why this exists — measured, not guessed.** MoPlayer renders with Impeller
/// on OpenGL ES, and on the maintainer's RTX 2080 at 4K that backend reserves
/// graphics memory for gradient shaders out of all proportion to what they
/// draw: one window-sized `LinearGradient` in a `BoxDecoration` took the
/// process from 360 MB to 1.2 GB; the ambient scene's three stacked gradients
/// cost 2.2 GB; forty poster-sized gradients cost 0.9 GB. The driver keeps that
/// reservation for the life of the process, so an idle MoPlayer sat on nearly
/// 5 GB of an 8 GB card and the whole desktop slowed down around it.
///
/// The same gradient rendered once into a 96×96 image and drawn stretched —
/// a plain textured quad — measured at the 360 MB baseline. Soft gradients do
/// not need more texels than that: bilinear filtering interpolates between
/// them, so the stretched image is as smooth as the shader was.
///
/// Rule for the whole app: **never put a [Gradient] in a `BoxDecoration`, a
/// `Paint.shader` or a `ShaderMask`** on a surface that reaches the screen.
/// Use [GradientFill] (or [BakedGradients.paint] inside a painter).
class BakedGradients {
  const BakedGradients._();

  static final Map<(Gradient, int, int), ui.Image> _cache = {};

  /// Texels along each axis. Enough for any soft ramp; a gradient with a hard
  /// stop would need more, and this app has none.
  static const int _texels = 96;

  /// The baked image of [gradient] for a box of [size]'s aspect ratio.
  ///
  /// Linear gradients defined by alignments scale with their box, so one
  /// square image serves every size. Radial and sweep gradients do not (their
  /// radius follows the shorter side), so they are baked at the box's aspect,
  /// quantised to limit how many variants the cache keeps.
  static ui.Image imageFor(Gradient gradient, Size size) {
    var w = _texels;
    var h = _texels;
    if (gradient is! LinearGradient && size.width > 0 && size.height > 0) {
      final aspect = size.width / size.height;
      if (aspect >= 1) {
        h = (w / aspect).round().clamp(8, _texels);
      } else {
        w = (h * aspect).round().clamp(8, _texels);
      }
      // Quantise to multiples of 8 texels.
      w = (w / 8).ceil() * 8;
      h = (h / 8).ceil() * 8;
    }
    final key = (gradient, w, h);
    final cached = _cache[key];
    if (cached != null) return cached;
    if (_cache.length > 160) {
      for (final image in _cache.values) {
        image.dispose();
      }
      _cache.clear();
    }
    final rect = Rect.fromLTWH(0, 0, w.toDouble(), h.toDouble());
    final recorder = ui.PictureRecorder();
    Canvas(
      recorder,
    ).drawRect(rect, Paint()..shader = gradient.createShader(rect));
    final picture = recorder.endRecording();
    final image = picture.toImageSync(w, h);
    picture.dispose();
    return _cache[key] = image;
  }

  /// Paints [gradient] over [rect], clipped to [radius] when given.
  static void paint(
    Canvas canvas,
    Rect rect,
    Gradient gradient, {
    BorderRadius? radius,
  }) {
    if (rect.isEmpty) return;
    final image = imageFor(gradient, rect.size);
    if (radius != null && radius != BorderRadius.zero) {
      canvas.save();
      canvas.clipRRect(radius.toRRect(rect));
    }
    canvas.drawImageRect(
      image,
      Rect.fromLTWH(0, 0, image.width.toDouble(), image.height.toDouble()),
      rect,
      Paint()..filterQuality = FilterQuality.medium,
    );
    if (radius != null && radius != BorderRadius.zero) canvas.restore();
  }
}

/// A box filled with a gradient, the cheap way (see [BakedGradients]).
///
/// Directional gradients are resolved against the ambient text direction first,
/// so a `LinearGradient` that starts on the leading edge flips in Arabic.
class GradientFill extends StatelessWidget {
  const GradientFill({
    super.key,
    required this.gradient,
    this.borderRadius,
    this.child,
  });

  final Gradient gradient;
  final BorderRadiusGeometry? borderRadius;
  final Widget? child;

  @override
  Widget build(BuildContext context) {
    final direction = Directionality.maybeOf(context) ?? TextDirection.ltr;
    return CustomPaint(
      painter: _GradientPainter(
        gradient: _resolve(gradient, direction),
        radius: borderRadius?.resolve(direction),
      ),
      child: child,
    );
  }

  static Gradient _resolve(Gradient gradient, TextDirection direction) {
    if (gradient is LinearGradient &&
        (gradient.begin is AlignmentDirectional ||
            gradient.end is AlignmentDirectional)) {
      return LinearGradient(
        begin: gradient.begin.resolve(direction),
        end: gradient.end.resolve(direction),
        colors: gradient.colors,
        stops: gradient.stops,
        tileMode: gradient.tileMode,
      );
    }
    return gradient;
  }
}

class _GradientPainter extends CustomPainter {
  _GradientPainter({required this.gradient, this.radius});

  final Gradient gradient;
  final BorderRadius? radius;

  @override
  void paint(Canvas canvas, Size size) {
    BakedGradients.paint(canvas, Offset.zero & size, gradient, radius: radius);
  }

  @override
  bool shouldRepaint(_GradientPainter old) =>
      old.gradient != gradient || old.radius != radius;
}
