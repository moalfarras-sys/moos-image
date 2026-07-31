import 'dart:math' as math;

import 'package:flutter/widgets.dart';

/// MoPlayer's own icon set.
///
/// The six dock destinations do not use Material's glyphs. Not out of pride —
/// Material's icons are better drawn than anything hand-rolled here would be —
/// but because they are the six shapes a user will see every time they open the
/// app, and a stock `Icons.live_tv_rounded` next to a stock `Icons.settings` is
/// the single clearest tell that an interface was assembled rather than
/// designed. These are one family: a 24-unit grid, a 1.9-unit stroke, round caps
/// and joins, and no fills except where a fill *means* something (the play
/// triangle, the favourite's heart when it is set).
///
/// They are painted, not shipped as a font: a font is one more asset that can go
/// missing from a bundle, and six paths do not justify one.
enum MoIcon { search, live, movies, series, favorites, settings, home }

class MoIconWidget extends StatelessWidget {
  const MoIconWidget(
    this.icon, {
    super.key,
    this.size = 24,
    required this.color,
    this.filled = false,
    this.strokeWidth = 1.9,
  });

  final MoIcon icon;
  final double size;
  final Color color;

  /// Only the favourite heart takes a fill, and only when it is set.
  final bool filled;
  final double strokeWidth;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: size,
      height: size,
      child: CustomPaint(
        painter: _MoIconPainter(
          icon: icon,
          color: color,
          filled: filled,
          strokeWidth: strokeWidth,
        ),
      ),
    );
  }
}

class _MoIconPainter extends CustomPainter {
  _MoIconPainter({
    required this.icon,
    required this.color,
    required this.filled,
    required this.strokeWidth,
  });

  final MoIcon icon;
  final Color color;
  final bool filled;
  final double strokeWidth;

  @override
  void paint(Canvas canvas, Size size) {
    // Everything below is drawn on a 24×24 grid and scaled to whatever the call
    // site asked for, so the stroke stays optically even at 20 px in the dock and
    // at 56 px on an empty state.
    final s = size.width / 24.0;
    canvas.save();
    canvas.scale(s);

    final stroke = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = strokeWidth
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round
      ..color = color
      ..isAntiAlias = true;

    final fill = Paint()
      ..style = PaintingStyle.fill
      ..color = color
      ..isAntiAlias = true;

    switch (icon) {
      case MoIcon.search:
        canvas.drawCircle(const Offset(10, 10), 7, stroke);
        canvas.drawLine(const Offset(15.5, 15.5), const Offset(21, 21), stroke);

      case MoIcon.live:
        canvas.drawRRect(
          RRect.fromRectAndRadius(
            const Rect.fromLTWH(2.5, 7, 19, 13.5),
            const Radius.circular(3),
          ),
          stroke,
        );
        canvas.drawArc(
          Rect.fromCircle(center: const Offset(12, 7), radius: 4.4),
          math.pi * 1.18,
          math.pi * 0.64,
          false,
          stroke,
        );
        canvas.drawArc(
          Rect.fromCircle(center: const Offset(12, 7), radius: 7.6),
          math.pi * 1.22,
          math.pi * 0.56,
          false,
          stroke,
        );
        canvas.drawCircle(const Offset(12, 13.7), 1.9, fill);

      case MoIcon.movies:
        final frame = RRect.fromRectAndRadius(
          const Rect.fromLTWH(2.5, 4, 19, 16),
          const Radius.circular(3),
        );
        canvas.drawRRect(frame, stroke);
        canvas.drawLine(const Offset(7, 4), const Offset(7, 20), stroke);
        canvas.drawLine(const Offset(17, 4), const Offset(17, 20), stroke);
        for (final y in const [7.2, 12.0, 16.8]) {
          canvas.drawCircle(Offset(4.75, y), 0.85, fill);
          canvas.drawCircle(Offset(19.25, y), 0.85, fill);
        }
        canvas.drawPath(
          Path()
            ..moveTo(10.6, 8.8)
            ..lineTo(15, 12)
            ..lineTo(10.6, 15.2)
            ..close(),
          fill,
        );

      case MoIcon.series:
        canvas.drawRRect(
          RRect.fromRectAndRadius(
            const Rect.fromLTWH(2.5, 8.5, 19, 12),
            const Radius.circular(3),
          ),
          stroke,
        );
        canvas.drawLine(
          const Offset(5.4, 5.6),
          const Offset(18.6, 5.6),
          stroke,
        );
        canvas.drawLine(const Offset(7.8, 3), const Offset(16.2, 3), stroke);

      case MoIcon.favorites:
        final heart = Path()
          ..moveTo(12, 20.2)
          ..cubicTo(5.5, 14.5, 2.8, 10.2, 3.8, 7)
          ..cubicTo(4.8, 3.5, 8.8, 3, 12, 6)
          ..cubicTo(15.2, 3, 19.2, 3.5, 20.2, 7)
          ..cubicTo(21.2, 10.2, 18.5, 14.5, 12, 20.2)
          ..close();
        canvas.drawPath(heart, filled ? fill : stroke);

      case MoIcon.settings:
        for (final y in const [6.0, 12.0, 18.0]) {
          canvas.drawLine(Offset(3, y), Offset(21, y), stroke);
        }
        canvas.drawCircle(const Offset(8, 6), 2.5, fill);
        canvas.drawCircle(const Offset(16, 12), 2.5, fill);
        canvas.drawCircle(const Offset(6, 18), 2.5, fill);

      case MoIcon.home:
        canvas.drawPath(
          Path()
            ..moveTo(3, 10.4)
            ..lineTo(12, 3)
            ..lineTo(21, 10.4)
            ..lineTo(21, 20)
            ..lineTo(3, 20)
            ..close(),
          stroke,
        );
        canvas.drawPath(
          Path()
            ..moveTo(10.4, 15.6)
            ..lineTo(14.2, 13.1)
            ..lineTo(10.4, 10.6)
            ..close(),
          fill,
        );
    }

    canvas.restore();
  }

  @override
  bool shouldRepaint(_MoIconPainter old) =>
      old.icon != icon ||
      old.color != color ||
      old.filled != filled ||
      old.strokeWidth != strokeWidth;
}
