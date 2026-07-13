import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../core/l10n/strings.dart';
import '../core/theme/app_colors.dart';
import '../core/theme/app_typography.dart';
import '../core/theme/motion.dart';
import '../core/theme/nova.dart';
import '../services/weather/weather_service.dart';

/// The weather, next to the football.
///
/// It is here for the same reason the match strip is: this app opens on a
/// television screen in a living room, and the two things a person glances at
/// before choosing what to watch are *what is on* and *what it is like outside*.
/// It asks for nothing — no key, no account, no permission dialog — and if it
/// cannot answer it does not appear.
class WeatherTile extends StatelessWidget {
  const WeatherTile({
    super.key,
    required this.weather,
    required this.strings,
    this.width = 260,
  });

  final WeatherNow weather;
  final S strings;
  final double width;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: width,
      padding: const EdgeInsets.all(Nova.space4),
      decoration: BoxDecoration(
        color: AppColors.surface2,
        borderRadius: BorderRadius.circular(Nova.radiusCard),
        border: Border.all(color: AppColors.borderSubtle),
      ),
      child: Row(
        children: [
          SizedBox(
            width: 62,
            height: 62,
            child: WeatherGlyph(kind: weather.kind, isDay: weather.isDay),
          ),
          const SizedBox(width: Nova.space4),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text(
                  '${weather.temperature.round()}°',
                  style: AppText.headline.copyWith(height: 1),
                ),
                const SizedBox(height: Nova.space1),
                Text(
                  strings.weatherPhrase(weather.kind),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppText.caption.copyWith(
                    color: AppColors.textSecondary,
                  ),
                ),
                if (weather.city.isNotEmpty ||
                    (weather.high != null && weather.low != null)) ...[
                  const SizedBox(height: Nova.space1),
                  Text(
                    [
                      if (weather.city.isNotEmpty) weather.city,
                      if (weather.high != null && weather.low != null)
                        '↑${weather.high!.round()}° ↓${weather.low!.round()}°',
                    ].join('  ·  '),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: AppText.caption.copyWith(color: AppColors.textMuted),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// A drawn weather mark — not an icon-font glyph.
///
/// Vector, because the icon theme is the *desktop's* and a MoPlayer window that
/// loses its weather symbol when the user changes their Plasma icon set is a
/// window with a hole in it. Animated, because a still sun and a still cloud are
/// the same picture: the movement is what says this is now.
class WeatherGlyph extends StatefulWidget {
  const WeatherGlyph({super.key, required this.kind, required this.isDay});

  final WeatherKind kind;
  final bool isDay;

  @override
  State<WeatherGlyph> createState() => _WeatherGlyphState();
}

class _WeatherGlyphState extends State<WeatherGlyph>
    with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(
    vsync: this,
    duration: const Duration(seconds: 12),
  )..repeat();

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (Motion.isReduced(context)) {
      return CustomPaint(
        painter: _WeatherPainter(kind: widget.kind, isDay: widget.isDay, t: 0),
      );
    }
    return AnimatedBuilder(
      animation: _c,
      builder: (_, _) => CustomPaint(
        painter: _WeatherPainter(
          kind: widget.kind,
          isDay: widget.isDay,
          t: _c.value,
        ),
      ),
    );
  }
}

class _WeatherPainter extends CustomPainter {
  _WeatherPainter({required this.kind, required this.isDay, required this.t});

  final WeatherKind kind;
  final bool isDay;

  /// 0..1, one full loop.
  final double t;

  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width;
    final h = size.height;
    final centre = Offset(w * 0.5, h * 0.5);

    switch (kind) {
      case WeatherKind.clear:
        _sun(canvas, centre, w * 0.24);
      case WeatherKind.partlyCloudy:
        _sun(canvas, Offset(w * 0.36, h * 0.36), w * 0.18);
        _cloud(canvas, size, dy: h * 0.10, scale: 0.92);
      case WeatherKind.cloudy:
        _cloud(canvas, size, dy: h * 0.04, scale: 1);
      case WeatherKind.fog:
        _cloud(canvas, size, dy: -h * 0.06, scale: 0.92);
        _fog(canvas, size);
      case WeatherKind.rain:
        _cloud(canvas, size, dy: -h * 0.10, scale: 0.92);
        _rain(canvas, size);
      case WeatherKind.snow:
        _cloud(canvas, size, dy: -h * 0.10, scale: 0.92);
        _snow(canvas, size);
      case WeatherKind.storm:
        _cloud(canvas, size, dy: -h * 0.10, scale: 0.92);
        _bolt(canvas, size);
    }
  }

  /// The disc breathes and the crown turns. Both are slow enough to be felt
  /// rather than watched.
  void _sun(Canvas canvas, Offset c, double r) {
    final breathe = 1 + 0.045 * _wave(t * 2);
    final disc = Paint()
      ..shader = const LinearGradient(
        colors: [AppColors.primaryBright, AppColors.primary],
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
      ).createShader(Rect.fromCircle(center: c, radius: r * breathe));

    final ray = Paint()
      ..color = AppColors.primary.withValues(alpha: 0.85)
      ..strokeWidth = 2.2
      ..strokeCap = StrokeCap.round;

    final spin = t * 2 * math.pi;
    for (var i = 0; i < 8; i++) {
      final a = spin + i * math.pi / 4;
      final from = Offset(c.dx + (r * 1.45) * _cos(a), c.dy + (r * 1.45) * _sin(a));
      final to = Offset(c.dx + (r * 1.9) * _cos(a), c.dy + (r * 1.9) * _sin(a));
      canvas.drawLine(from, to, ray);
    }
    canvas.drawCircle(c, r * breathe, disc);
  }

  void _cloud(Canvas canvas, Size size, {required double dy, double scale = 1}) {
    // The drift is ±3 px over the whole loop. A cloud that visibly slides is a
    // cloud the eye follows instead of reading the temperature next to it.
    final drift = 3 * _wave(t);
    final w = size.width;
    final h = size.height;
    final base = Offset(w * 0.5 + drift, h * 0.62 + dy);
    final r = w * 0.16 * scale;

    final paint = Paint()..color = const Color(0xFFC9D2DC);
    canvas.drawCircle(base.translate(-r * 1.15, 0), r * 0.86, paint);
    canvas.drawCircle(base.translate(0, -r * 0.42), r * 1.08, paint);
    canvas.drawCircle(base.translate(r * 1.2, 0), r * 0.9, paint);
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        Rect.fromLTWH(base.dx - r * 1.95, base.dy - r * 0.1, r * 3.9, r * 1.05),
        Radius.circular(r),
      ),
      paint,
    );
  }

  /// Drops fall on *different phases*. In lockstep they read as a barcode.
  void _rain(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = AppColors.info.withValues(alpha: 0.9)
      ..strokeWidth = 2
      ..strokeCap = StrokeCap.round;

    const drops = 3;
    for (var i = 0; i < drops; i++) {
      final phase = (t * 3 + i / drops) % 1;
      final x = size.width * (0.34 + 0.16 * i);
      final y = size.height * (0.68 + 0.24 * phase);
      canvas.drawLine(Offset(x, y), Offset(x - 1.5, y + size.height * 0.10), paint);
    }
  }

  void _snow(Canvas canvas, Size size) {
    final paint = Paint()..color = Colors.white.withValues(alpha: 0.92);
    const flakes = 3;
    for (var i = 0; i < flakes; i++) {
      final phase = (t * 2 + i / flakes) % 1;
      final sway = 3 * _wave(phase * 2 + i);
      final x = size.width * (0.34 + 0.16 * i) + sway;
      final y = size.height * (0.68 + 0.24 * phase);
      canvas.drawCircle(Offset(x, y), 2.4, paint);
    }
  }

  void _fog(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = const Color(0xFF9AA6B2).withValues(alpha: 0.75)
      ..strokeWidth = 2.6
      ..strokeCap = StrokeCap.round;
    for (var i = 0; i < 3; i++) {
      final slide = 4 * _wave(t + i * 0.2);
      final y = size.height * (0.70 + 0.09 * i);
      canvas.drawLine(
        Offset(size.width * 0.26 + slide, y),
        Offset(size.width * 0.74 + slide, y),
        paint,
      );
    }
  }

  /// Two strikes per loop, and nothing in between. A bolt that is always lit is
  /// a shape; a bolt that strikes is weather.
  void _bolt(Canvas canvas, Size size) {
    final beat = (t * 2) % 1;
    final lit = beat < 0.12 || (beat > 0.2 && beat < 0.28);
    final paint = Paint()
      ..color = AppColors.warning.withValues(alpha: lit ? 1 : 0.30);

    final w = size.width;
    final h = size.height;
    final path = Path()
      ..moveTo(w * 0.52, h * 0.64)
      ..lineTo(w * 0.40, h * 0.86)
      ..lineTo(w * 0.50, h * 0.86)
      ..lineTo(w * 0.44, h * 1.00)
      ..lineTo(w * 0.62, h * 0.80)
      ..lineTo(w * 0.51, h * 0.80)
      ..close();
    canvas.drawPath(path, paint);
  }

  /// −1..1, one cycle per unit of [x].
  static double _wave(double x) => math.sin(x * 2 * math.pi);
  static double _sin(double a) => math.sin(a);
  static double _cos(double a) => math.cos(a);

  @override
  bool shouldRepaint(_WeatherPainter old) =>
      old.t != t || old.kind != kind || old.isDay != isDay;
}
