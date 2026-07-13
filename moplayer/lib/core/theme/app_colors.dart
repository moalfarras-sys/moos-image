import 'package:flutter/material.dart';

/// **Glass Orange Cinema** — MoPlayer's palette on MoOS.
///
/// The canvas is a *warm* near-black, not a navy and not a flat #000. Two
/// reasons, and they are both about the video:
///
///  * A player's chrome surrounds the brightest surface on the screen. Any hue
///    in that chrome bleeds into the picture — a navy shell puts a blue cast on
///    every frame it renders. So the surfaces are pulled almost to black.
///  * Almost, not all the way. A pure `#000000` canvas has no shading left to
///    build depth with: every panel above it has to be *lighter*, and the whole
///    interface flattens. `#070809` keeps a step below the darkest panel.
///
/// The warmth (`R ≥ G ≥ B` from [surface2] up) is what makes the ember accent
/// read as *ember* rather than as *alert*. Orange on cool grey looks like a
/// warning; orange on warm graphite looks like light.
///
/// ## Where cool colour is still allowed
///
/// Exactly two places, and both of them are the *system* speaking rather than
/// the app: [novaGradient] on the MoOS badge, and [info] on a network state.
/// Nowhere else — and specifically **not** the focus ring. See DESIGN.md.
class AppColors {
  const AppColors._();

  // ── Surfaces ───────────────────────────────────────────────────────────────
  // A four-step ladder. Every panel sits exactly one step above its parent, so
  // depth is legible without a single shadow being drawn.

  /// The canvas, and the player's void.
  static const Color surface0 = Color(0xFF070809);

  /// Panels, the dock's opaque floor, the caption bar.
  static const Color surface1 = Color(0xFF0D0F12);

  /// Cards in a scrolling grid.
  static const Color surface2 = Color(0xFF14171B);

  /// Hover and selection.
  static const Color surface3 = Color(0xFF1F2329);

  /// The warm surface. Used where a surface should feel *lit* rather than
  /// merely raised: the fill under glass, the hero's base, a focused card.
  /// `R > G > B` — the only tone in the ladder that leans warm on purpose.
  static const Color surfaceWarm = Color(0xFF1A1714);

  /// Kept as aliases so the ported core (which speaks the iOS app's names) still
  /// compiles and still means the same thing.
  static const Color black = surface0;
  static const Color background = surface0;
  static const Color backgroundAlt = surface1;
  static const Color surface = surface1;
  static const Color surfaceHigh = surface2;

  // ── Borders ────────────────────────────────────────────────────────────────
  // Warm white at very low alpha, never a grey line. A neutral border on a warm
  // surface reads as dirt; the same border tinted with the surface's own hue
  // disappears into it and only the *edge* survives, which is the whole point.
  static const Color borderSubtle = Color(0x14FFF0DC);
  static const Color borderStrong = Color(0x2EFFD9A8);

  /// The focus ring. **Orange-gold, not cyan.**
  ///
  /// MoOS's own focus affordance is Nova cyan, and every other app in the image
  /// wears it. MoPlayer deliberately does not: this app is a full-screen cinema
  /// surface where the focus ring is frequently the only chrome on top of a
  /// moving picture, and a cyan ring over warm film grades reads as a defect in
  /// the video rather than as a control. The divergence is the point, and it is
  /// the one place MoPlayer overrides a system affordance on purpose.
  static const Color focus = Color(0xFFFFB347);

  // ── Brand: ember & gold ────────────────────────────────────────────────────
  //
  // These are not chosen colours. They are **measured off the mark** —
  // `assets/branding/logo.png`, sampled pixel by pixel — because the brand is a
  // painted flame with a gradient in it, and a palette that merely looks
  // orange-ish next to it is a palette that fights it. The mark's own ramp runs
  // from a red-orange core to an amber crown:
  //
  //   core       #FF4400   (the single most common pixel in the flame)
  //   crown      #FF8D00   (its lit edge)
  //   highlight  near-white, which is a specular, not a colour
  //
  // So [ember] is the core, [primary] is the crown — the one that carries text
  // and icons, because the core is too dark to read at 14 px on near-black — and
  // [emberGradient] runs the mark's own ramp. Sampled, not guessed: `ember` was
  // #FF6A0F, a full 38 points lighter and yellower than the flame it was meant
  // to be, which is exactly the mismatch that makes a brand look approximated.
  static const Color primary = Color(0xFFFF8A1F);
  static const Color primaryBright = Color(0xFFFFB347);
  static const Color gold = Color(0xFFD9A441);
  static const Color goldBright = Color(0xFFFFD27A);
  static const Color ember = Color(0xFFFF4400);

  /// The green pip on the mark, and the only non-warm colour in it. It means
  /// *connected* here, which is what it means on the logo: the source badge in
  /// the caption bar, the "on" side of a switch.
  static const Color online = Color(0xFF74C23A);

  // ── Text — a warm ramp ─────────────────────────────────────────────────────
  /// Warm white. Not `#FFFFFF`: pure white on a warm black is the one pairing
  /// that reliably looks like an unstyled web page.
  static const Color textPrimary = Color(0xFFFFF7ED);
  static const Color textSecondary = Color(0xFFB9B1A6);
  static const Color textMuted = Color(0xFF8A8377);

  // ── State ──────────────────────────────────────────────────────────────────
  static const Color success = Color(0xFF3DD68C);
  static const Color warning = Color(0xFFE9B949);
  static const Color danger = Color(0xFFFF5D5D);

  /// Cool, and allowed to be: an information or network state is the *system*
  /// reporting on itself, not the app expressing an identity.
  static const Color info = Color(0xFF4FC3FF);

  /// The "on air" red. Deliberately not [danger] and deliberately not the brand
  /// orange: a live badge is neither an error nor a selection, and on a wall of
  /// channel tiles all three must stay distinguishable at a glance.
  static const Color live = Color(0xFFFF3B30);

  // ── Glass ──────────────────────────────────────────────────────────────────
  // The fill is a real colour at real opacity and the blur is decoration on top
  // of it. Turn the blur off (a software renderer, a remote session) and the
  // panel is still legible. A white translucent card would wash the whole app
  // out; these are dark fills with a warm cast picked up from the surface.

  /// Chrome that floats over video: the player's controls, the dock.
  static const Color glassFill = Color(0xC70E0F12); // ≈78%
  static const Color glassFillStrong = Color(0xD60C0D10); // ≈84%

  /// Secondary chrome: a widget in the dashboard strip, a popover.
  static const Color glassFillSoft = Color(0x8F14161A); // ≈56%

  /// The hairline on a glass edge, and the inner highlight just inside it. Two
  /// strokes, not one: the top edge of a real pane of glass catches the light
  /// and the rest of it does not, and that single asymmetry is most of what
  /// makes a translucent rectangle read as a material.
  static const Color glassStroke = Color(0x1AFFE9CE);
  static const Color glassHighlight = Color(0x24FFF3E0);

  /// Backwards-compatible aliases.
  static const Color glassFillWeak = glassFillSoft;

  // ── Gradients ──────────────────────────────────────────────────────────────

  /// MoPlayer's signature. Primary buttons, the logo bloom, the dock's active
  /// indicator.
  static const LinearGradient emberGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [primaryBright, primary, ember],
  );

  /// Backwards-compatible alias for the ported core.
  static const LinearGradient orangeGradient = emberGradient;

  /// Gold, for the things that are *earned* rather than merely selected: a
  /// rating, a subscription that is healthy, the highlight on a hero.
  static const LinearGradient goldGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [goldBright, gold],
  );

  /// MoOS's identity gradient (`#22D3EE → #2E7BFF → #8B5CF6`), untouched.
  ///
  /// It appears **only** where the surface speaks for the system rather than
  /// for the app — the MoOS badge, and the integration panel in Settings. It is
  /// not a second accent; used as one it would leave the interface with two
  /// identities and no hierarchy. Ember leads; Nova signs.
  static const LinearGradient novaGradient = LinearGradient(
    begin: Alignment.centerLeft,
    end: Alignment.centerRight,
    colors: [Color(0xFF22D3EE), Color(0xFF2E7BFF), Color(0xFF8B5CF6)],
  );

  /// The scene behind every screen: a warm graphite top falling to true
  /// near-black at the foot of the window, where the dock floats.
  static const LinearGradient sceneGradient = LinearGradient(
    begin: Alignment.topCenter,
    end: Alignment.bottomCenter,
    colors: [Color(0xFF101114), surface0, Color(0xFF050506)],
    stops: [0.0, 0.55, 1.0],
  );

  /// The scrim under text laid over artwork. Poster art is arbitrary — without
  /// an opaque-enough surface beneath it a title can land white-on-white.
  static const LinearGradient posterScrim = LinearGradient(
    begin: Alignment.topCenter,
    end: Alignment.bottomCenter,
    colors: [Color(0x00000000), Color(0x5C000000), Color(0xE6070809)],
    stops: [0.35, 0.68, 1.0],
  );

  /// Horizontal scrim for the hero: keeps the copy on the leading edge readable
  /// while the artwork survives on the trailing one.
  ///
  /// Directional on purpose — it is flipped for RTL by the widget that draws it,
  /// because in Arabic the copy sits on the right.
  static const LinearGradient heroScrim = LinearGradient(
    begin: Alignment.centerLeft,
    end: Alignment.centerRight,
    colors: [
      Color(0xF5070809),
      Color(0xCC070809),
      Color(0x33070809),
      Color(0x00070809),
    ],
    stops: [0.0, 0.38, 0.78, 1.0],
  );

  /// The floor under a hero image, so the content below it does not begin at a
  /// hard horizontal edge.
  static const LinearGradient heroFloor = LinearGradient(
    begin: Alignment.topCenter,
    end: Alignment.bottomCenter,
    colors: [Color(0x00070809), Color(0x99070809), Color(0xFF070809)],
    stops: [0.0, 0.62, 1.0],
  );

  /// The backdrop of a hero that has no artwork to show — a live channel, whose
  /// only picture is a transparent logo that must never be stretched to fill.
  /// Warm graphite with an ember lean, so the plate reads as *the brand's*
  /// surface rather than as a poster that failed to load.
  static const LinearGradient heroPlate = LinearGradient(
    begin: Alignment.topRight,
    end: Alignment.bottomLeft,
    colors: [surfaceWarm, surface1, surface0],
    stops: [0.0, 0.55, 1.0],
  );

  /// A soft radial bloom. Behind the logo, under a focused dock item, around
  /// the hero's ambient light.
  static RadialGradient glow(Color color, {double opacity = 0.35}) {
    return RadialGradient(
      colors: [color.withValues(alpha: opacity), color.withValues(alpha: 0.0)],
    );
  }

  /// The ambient amber wash that sits behind the whole app, top-trailing. It is
  /// the single largest reason the interface reads as *lit* rather than merely
  /// dark — and it is very nearly invisible when you look for it directly,
  /// which is correct.
  static RadialGradient get ambientAmber => const RadialGradient(
    center: Alignment(0.72, -0.85),
    radius: 1.1,
    colors: [Color(0x1FFF8A1F), Color(0x0DD9A441), Color(0x00070809)],
    stops: [0.0, 0.42, 1.0],
  );
}
