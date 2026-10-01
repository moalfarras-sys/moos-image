import 'package:flutter/material.dart';

import 'palette.dart';

/// **MoPlayer Horizon** — the app's colour tokens.
///
/// Surfaces and the accent come from the active [Palette], which follows the
/// MoOS desktop (see `palette.dart` for why). Everything else — text, states,
/// the on-air red, the brand's own ember — is fixed here. Nothing in the app
/// writes a `Color(0x…)` literal of its own for a role this file names.
///
/// The surfaces are a four-step ladder from a near-black ink. Near, not pure:
/// a `#000000` canvas leaves no shading below it, every panel has to be
/// lighter, and the interface flattens. Each panel sits one step above its
/// parent, so depth reads without drawing a single shadow.
class AppColors {
  const AppColors._();

  /// The palette every token below reads. Set once before the first frame and
  /// again when the desktop's palette changes; the app rebuilds around it.
  static Palette palette = Palette.moos;

  // ── Surfaces ───────────────────────────────────────────────────────────────

  /// The canvas, and the player's void.
  static Color get surface0 => palette.canvas;

  /// Panels, the navigation rail, the caption.
  static Color get surface1 => palette.surface1;

  /// Cards in a scrolling grid.
  static Color get surface2 => palette.surface2;

  /// Hover and selection.
  static Color get surface3 => palette.surface3;

  /// A surface lit by the accent: the hero base, a focused card's floor.
  static Color get surfaceWarm => palette.surfaceWarm;

  static Color get black => surface0;
  static Color get background => surface0;
  static Color get backgroundAlt => surface1;
  static Color get surface => surface1;
  static Color get surfaceHigh => surface2;

  // ── Borders ────────────────────────────────────────────────────────────────
  // White at very low alpha: a grey line on a tinted surface reads as dirt,
  // a translucent one takes the surface's own hue and only the edge survives.
  static const Color borderSubtle = Color(0x14FFFFFF);
  static const Color borderStrong = Color(0x29FFFFFF);

  // ── Accent ─────────────────────────────────────────────────────────────────

  /// The accent: focus, selection, primary actions, progress.
  static Color get primary => palette.accent;
  static Color get primaryBright => palette.accentBright;
  static Color get accentDeep => palette.accentDeep;

  /// The focus ring. The accent's bright stop, so it reads over a moving
  /// picture as well as over a panel.
  static Color get focus => palette.accentBright;

  /// Foreground for anything painted on [emberGradient] (the accent gradient).
  /// Chosen by measuring every stop — see [Palette].
  static Color get onEmber => palette.onAccent;
  static Color get onAccent => palette.onAccent;

  /// The accent gradient. Named for the brand it replaced so that the widgets
  /// written against it keep their meaning: the one gradient that says
  /// "primary".
  static LinearGradient get emberGradient => LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [palette.accentBright, palette.accent, palette.accentDeep],
  );
  static LinearGradient get accentGradient => emberGradient;
  static LinearGradient get orangeGradient => emberGradient;

  // ── Brand ──────────────────────────────────────────────────────────────────
  //
  // Measured off the mark (`assets/branding/logo.png`), not chosen: the logo is
  // a painted flame with its own ramp, and a palette that merely looks
  // orange-ish next to it fights it. These are artwork colours — the logo, the
  // splash, the ember palette — never chrome.

  /// The flame's core, its single most common pixel.
  static const Color ember = Color(0xFFFF4400);

  /// The flame's lit crown.
  static const Color brandPrimary = Color(0xFFFF8A1F);
  static const Color brandBright = Color(0xFFFFB347);

  /// Ratings and the things that are *earned* rather than selected.
  static const Color gold = Color(0xFFE8B84A);
  static const Color goldBright = Color(0xFFFFD27A);

  /// The mark's green pip: *connected*.
  static const Color online = Color(0xFF6BD48F);

  // ── Text ───────────────────────────────────────────────────────────────────
  static const Color textPrimary = Color(0xFFF3F5F9);
  static const Color textSecondary = Color(0xFFB4BBC8);
  static const Color textMuted = Color(0xFF8A93A3);

  // ── State ──────────────────────────────────────────────────────────────────
  static const Color success = Color(0xFF4ADE80);
  static const Color warning = Color(0xFFF4C56A);
  static const Color danger = Color(0xFFFF6B7A);
  static const Color info = Color(0xFF78AFFF);

  /// On air. Deliberately neither the danger colour nor the accent: on a wall
  /// of channel tiles, "live", "error" and "selected" must stay distinguishable
  /// at a glance.
  static const Color live = Color(0xFFFF3B4E);

  // ── Glass ──────────────────────────────────────────────────────────────────
  // The fill is a real colour at real opacity; blur, where it is used at all,
  // is decoration on top of it. Turn the blur off and every panel still reads.

  static Color get glassFill => palette.surface1.withValues(alpha: 0.86);
  static Color get glassFillStrong => palette.canvas.withValues(alpha: 0.92);
  static Color get glassFillSoft => palette.surface2.withValues(alpha: 0.62);
  static Color get glassFillWeak => glassFillSoft;
  static const Color glassStroke = Color(0x1FFFFFFF);
  static const Color glassHighlight = Color(0x24FFFFFF);

  // ── Gradients ──────────────────────────────────────────────────────────────

  static LinearGradient get goldGradient => const LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [goldBright, gold],
  );

  /// MoOS's identity gradient — only where the surface speaks for the system.
  static const LinearGradient novaGradient = LinearGradient(
    begin: Alignment.centerLeft,
    end: Alignment.centerRight,
    colors: [Color(0xFF22D3EE), Color(0xFF2E7BFF), Color(0xFF8B5CF6)],
  );

  /// The scene behind every screen.
  static LinearGradient get sceneGradient => LinearGradient(
    begin: Alignment.topCenter,
    end: Alignment.bottomCenter,
    colors: [
      Color.lerp(palette.canvas, palette.accent, 0.05)!,
      palette.canvas,
      Color.lerp(palette.canvas, Colors.black, 0.35)!,
    ],
    stops: const [0.0, 0.55, 1.0],
  );

  /// The scrim under text laid over artwork.
  static LinearGradient get posterScrim => LinearGradient(
    begin: Alignment.topCenter,
    end: Alignment.bottomCenter,
    colors: [
      const Color(0x00000000),
      const Color(0x5C000000),
      palette.canvas.withValues(alpha: 0.92),
    ],
    stops: const [0.35, 0.68, 1.0],
  );

  /// Horizontal scrim for a hero: the copy on the leading edge stays readable
  /// while the artwork survives on the trailing one. Flipped for RTL by the
  /// widget that draws it.
  static LinearGradient get heroScrim => LinearGradient(
    begin: Alignment.centerLeft,
    end: Alignment.centerRight,
    colors: [
      palette.canvas.withValues(alpha: 0.96),
      palette.canvas.withValues(alpha: 0.80),
      palette.canvas.withValues(alpha: 0.20),
      palette.canvas.withValues(alpha: 0.0),
    ],
    stops: const [0.0, 0.36, 0.74, 1.0],
  );

  /// The floor under a hero image.
  static LinearGradient get heroFloor => LinearGradient(
    begin: Alignment.topCenter,
    end: Alignment.bottomCenter,
    colors: [
      palette.canvas.withValues(alpha: 0.0),
      palette.canvas.withValues(alpha: 0.62),
      palette.canvas,
    ],
    stops: const [0.0, 0.62, 1.0],
  );

  /// The plate of a hero with no artwork — a live channel, whose only picture
  /// is a transparent logo that must never be stretched to fill.
  static LinearGradient get heroPlate => LinearGradient(
    begin: Alignment.topRight,
    end: Alignment.bottomLeft,
    colors: [palette.surfaceWarm, palette.surface1, palette.canvas],
    stops: const [0.0, 0.55, 1.0],
  );

  static RadialGradient glow(Color color, {double opacity = 0.35}) {
    return RadialGradient(
      colors: [
        color.withValues(alpha: opacity),
        color.withValues(alpha: 0.0),
      ],
    );
  }

  /// The accent wash high on the trailing side of the window — the reason the
  /// interface reads as lit rather than merely dark. Nearly invisible when you
  /// look for it, which is correct.
  static RadialGradient get ambientAmber => RadialGradient(
    center: const Alignment(0.72, -0.9),
    radius: 1.15,
    colors: [
      palette.accent.withValues(alpha: 0.10),
      palette.accentDeep.withValues(alpha: 0.04),
      palette.canvas.withValues(alpha: 0.0),
    ],
    stops: const [0.0, 0.42, 1.0],
  );
}
