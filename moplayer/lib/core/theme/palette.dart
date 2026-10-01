import 'dart:io';
import 'dart:math' as math;

import 'package:flutter/painting.dart';

/// The colours MoPlayer is drawn in *on this desktop*.
///
/// MoPlayer is part of MoOS, and MoOS has one colour system with several
/// palettes — Graphite, Tidal, Amethyst, Aurora, Midnight and the rest — that
/// the owner switches between in Settings. An app that ignores the switch is an
/// app that looks installed rather than built in. So the accent (focus rings,
/// the selected destination, the primary button, progress) is read from the
/// session's own `kdeglobals`, and the ink the surfaces are mixed from leans a
/// little toward the palette's window colour.
///
/// Only a little. This is a video player, and chrome that carries a strong hue
/// casts it onto every frame beside it — so the surfaces stay near-neutral and
/// the tint is a quarter-strength wash, while the accent carries the identity.
/// The brand's ember survives as an explicit choice ([PaletteSource.ember]) and
/// on the logo, which is artwork, not chrome.
class Palette {
  Palette._({
    required this.source,
    required this.accent,
    required this.accentBright,
    required this.accentDeep,
    required this.onAccent,
    required this.canvas,
    required this.surface1,
    required this.surface2,
    required this.surface3,
    required this.surfaceWarm,
    this.schemeName,
  });

  /// Builds the whole palette from one accent and one tint.
  factory Palette.from({
    required Color accent,
    Color? tint,
    PaletteSource source = PaletteSource.system,
    String? schemeName,
  }) {
    final hsl = HSLColor.fromColor(accent);
    final saturation = math.max(hsl.saturation, 0.45);
    final tuned = hsl.withSaturation(saturation);
    // Every stop of the accent gradient carries dark ink at WCAG AA (4.5:1),
    // whatever hue the desktop hands us: blue at a given HSL lightness is far
    // darker than yellow, so the stops are lifted by *luminance*, not by a
    // fixed lightness.
    final base = _atLeast(tuned, 0.26, max: 0.80);
    final bright = _atLeast(
      tuned.withLightness(math.min(tuned.lightness + 0.12, 0.88)),
      0.40,
      max: 0.90,
    );
    final deep = _atLeast(
      tuned
          .withHue((tuned.hue + 12) % 360)
          .withSaturation(math.min(saturation + 0.08, 1))
          .withLightness(math.max(tuned.lightness - 0.10, 0.30)),
      0.20,
      max: 0.78,
    );

    const ink = Color(0xFF0A0C11);
    final wash = tint ?? const Color(0xFF14191C);
    Color mix(Color a, Color b, double t) => Color.lerp(a, b, t)!;
    final canvas = mix(ink, wash, 0.22);

    return Palette._(
      source: source,
      accent: base,
      accentBright: bright,
      accentDeep: deep,
      onAccent: _readableOn([bright, base, deep]),
      canvas: canvas,
      surface1: mix(canvas, const Color(0xFFFFFFFF), 0.035),
      surface2: mix(canvas, const Color(0xFFFFFFFF), 0.065),
      surface3: mix(canvas, const Color(0xFFFFFFFF), 0.11),
      surfaceWarm: mix(canvas, base, 0.10),
      schemeName: schemeName,
    );
  }

  /// MoOS's own default (Graphite): the Tidal teal.
  static final Palette moos = Palette.from(
    accent: const Color(0xFF4ED7C8),
    tint: const Color(0xFF14191C),
    source: PaletteSource.moos,
  );

  /// MoPlayer's brand, for the owner who asks for it.
  static final Palette ember = Palette.from(
    accent: const Color(0xFFFF8A1F),
    tint: const Color(0xFF1A1714),
    source: PaletteSource.ember,
  );

  final PaletteSource source;
  final Color accent;
  final Color accentBright;
  final Color accentDeep;

  /// The one foreground for anything painted on the accent gradient, chosen
  /// by measurement across all three stops (see [_readableOn]).
  final Color onAccent;

  final Color canvas;
  final Color surface1;
  final Color surface2;
  final Color surface3;
  final Color surfaceWarm;

  /// The desktop colour scheme this was read from, if any.
  final String? schemeName;

  /// [color], lightened until its relative luminance reaches [luminance] (or
  /// its lightness reaches [max]).
  static Color _atLeast(HSLColor color, double luminance, {double max = 0.9}) {
    var c = color;
    while (c.toColor().computeLuminance() < luminance && c.lightness < max) {
      c = c.withLightness(math.min(c.lightness + 0.02, max));
    }
    return c.toColor();
  }

  /// Dark ink or white — whichever clears the higher minimum contrast over
  /// every stop of the accent gradient.
  static Color _readableOn(List<Color> stops) {
    const dark = Color(0xFF0A0C11);
    const light = Color(0xFFFFFFFF);
    double worst(Color fg) =>
        stops.map((bg) => contrast(fg, bg)).reduce(math.min);
    return worst(dark) >= worst(light) ? dark : light;
  }

  static double contrast(Color a, Color b) {
    final la = a.computeLuminance();
    final lb = b.computeLuminance();
    final hi = math.max(la, lb);
    final lo = math.min(la, lb);
    return (hi + 0.05) / (lo + 0.05);
  }

  @override
  bool operator ==(Object other) =>
      other is Palette &&
      other.source == source &&
      other.accent == accent &&
      other.canvas == canvas;

  @override
  int get hashCode => Object.hash(source, accent, canvas);

  // ── Reading the desktop ────────────────────────────────────────────────────

  /// The `kdeglobals` the session reads, or null outside a KDE session.
  static File? kdeglobalsFile() {
    final env = Platform.environment;
    final config = (env['XDG_CONFIG_HOME']?.isNotEmpty ?? false)
        ? env['XDG_CONFIG_HOME']!
        : '${env['HOME'] ?? ''}/.config';
    final file = File('$config/kdeglobals');
    return file.existsSync() ? file : null;
  }

  /// The palette of the running desktop, or MoOS's default when it cannot be
  /// read. Never throws: a missing or odd `kdeglobals` is not worth a crash.
  static Palette fromDesktop() {
    try {
      final file = kdeglobalsFile();
      if (file == null) return moos;
      return fromKdeglobals(file.readAsStringSync()) ?? moos;
    } on Object {
      return moos;
    }
  }

  /// Parses `kdeglobals` text. The explicit `[General] AccentColor` wins (it is
  /// what the owner picked when they picked one); otherwise the scheme's own
  /// selection colour is the accent.
  static Palette? fromKdeglobals(String text) {
    final groups = <String, Map<String, String>>{};
    var current = '';
    for (final raw in text.split('\n')) {
      final line = raw.trim();
      if (line.isEmpty || line.startsWith('#')) continue;
      if (line.startsWith('[') && line.endsWith(']')) {
        current = line.substring(1, line.length - 1);
        continue;
      }
      final eq = line.indexOf('=');
      if (eq <= 0) continue;
      (groups[current] ??= {})[line.substring(0, eq).trim()] = line
          .substring(eq + 1)
          .trim();
    }
    final general = groups['General'] ?? const {};
    final accent =
        _rgb(general['AccentColor']) ??
        _rgb(groups['Colors:Selection']?['BackgroundNormal']);
    if (accent == null) return null;
    final window = _rgb(groups['Colors:Window']?['BackgroundNormal']);
    // A light scheme's window colour would wash the canvas out; only a dark
    // one is a useful tint for a player that is always dark.
    final tint = (window != null && window.computeLuminance() < 0.2)
        ? window
        : null;
    return Palette.from(
      accent: accent,
      tint: tint,
      schemeName: general['ColorScheme'],
    );
  }

  static Color? _rgb(String? value) {
    if (value == null) return null;
    final parts = value.split(',').map((p) => int.tryParse(p.trim())).toList();
    if (parts.length < 3 || parts.take(3).any((p) => p == null)) return null;
    return Color.fromARGB(
      255,
      parts[0]!.clamp(0, 255),
      parts[1]!.clamp(0, 255),
      parts[2]!.clamp(0, 255),
    );
  }
}

enum PaletteSource {
  /// Follows the desktop's MoOS palette.
  system,

  /// MoOS's default palette, when the desktop cannot be read.
  moos,

  /// MoPlayer's own ember, chosen in Settings.
  ember,
}
