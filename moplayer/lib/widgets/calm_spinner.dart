import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../core/theme/app_colors.dart';
import '../core/theme/motion.dart';

/// A busy indicator that turns ten times a second instead of sixty.
///
/// **Why not `CircularProgressIndicator`.** On MoOS the Flutter view is drawn
/// through GTK3, and GTK uploads the whole window to the GPU on the main thread
/// for every frame Flutter produces (gdkgl.c, `gdk_cairo_draw_from_gl`) — at
/// this station's 4K that is a 4608×2427 upload per frame. A Material spinner
/// asks for a frame every vsync, so a screen that was merely *waiting* — for a
/// 121 MB playlist, measured on 2026-09-30 — held the main thread at ~65% of a
/// core for the whole half-minute download. This one asks for ten frames a
/// second, which is all a turning arc needs to read as "working".
///
/// Under reduced motion it is a still arc.
class CalmSpinner extends StatefulWidget {
  const CalmSpinner({
    super.key,
    this.size = 26,
    this.strokeWidth = 2.4,
    this.color,
  });

  final double size;
  final double strokeWidth;
  final Color? color;

  @override
  State<CalmSpinner> createState() => _CalmSpinnerState();
}

class _CalmSpinnerState extends State<CalmSpinner> {
  static const _steps = 12;
  static const _interval = Duration(milliseconds: 100);

  Timer? _timer;
  int _step = 0;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final still = Motion.isReduced(context);
    if (still) {
      _timer?.cancel();
      _timer = null;
    } else {
      _timer ??= Timer.periodic(_interval, (_) {
        if (mounted) setState(() => _step = (_step + 1) % _steps);
      });
    }
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Semantics(
      label: MaterialLocalizations.of(context).refreshIndicatorSemanticLabel,
      child: SizedBox.square(
        dimension: widget.size,
        child: CustomPaint(
          painter: _ArcPainter(
            angle: _step * 2 * math.pi / _steps,
            color: widget.color ?? AppColors.primary,
            strokeWidth: widget.strokeWidth,
          ),
        ),
      ),
    );
  }
}

class _ArcPainter extends CustomPainter {
  _ArcPainter({
    required this.angle,
    required this.color,
    required this.strokeWidth,
  });

  final double angle;
  final Color color;
  final double strokeWidth;

  @override
  void paint(Canvas canvas, Size size) {
    final rect = (Offset.zero & size).deflate(strokeWidth / 2);
    canvas.drawArc(
      rect,
      0,
      2 * math.pi,
      false,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = strokeWidth
        ..color = color.withValues(alpha: 0.18),
    );
    canvas.drawArc(
      rect,
      angle - math.pi / 2,
      math.pi * 0.6,
      false,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = strokeWidth
        ..strokeCap = StrokeCap.round
        ..color = color,
    );
  }

  @override
  bool shouldRepaint(_ArcPainter old) =>
      old.angle != angle || old.color != color;
}
