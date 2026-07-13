/// The structural tokens: spacing, radius, type scale, motion.
///
/// The *rhythm* is MoOS's — the 4/8/12/16/24/32 spacing ladder and the IBM Plex
/// type ramp are the ones the MoOS shell, Mo AI and the Welcome app move in, and
/// matching them is most of what "native" actually means. The *colour* is not;
/// see [AppColors] and DESIGN.md for why a cinema surface cannot take the
/// system's navy.
///
/// The radius and motion scales below are MoPlayer's own, because they carry the
/// Glass Orange Cinema shape language: a bigger, softer corner than a settings
/// dialog wants, and a motion curve tuned for a surface you sit back from.
class Nova {
  const Nova._();

  // ── Spacing ────────────────────────────────────────────────────────────────
  // Dense controls use 4/8, cards 12/16, sections 24/32.
  static const double space1 = 4;
  static const double space2 = 8;
  static const double space3 = 12;
  static const double space4 = 16;
  static const double space5 = 24;
  static const double space6 = 32;
  static const double space7 = 48;

  // ── Radius ─────────────────────────────────────────────────────────────────
  // One ladder, used everywhere. A nested surface always takes a smaller radius
  // than its parent — a 20 px card inside a 20 px panel reads as a mistake, and
  // the eye catches it long before it can name it.
  static const double radiusControl = 12; // buttons, chips, fields
  static const double radiusCard = 18; // posters, channel tiles
  static const double radiusPanel = 24; // dialogs, side panels, widgets
  static const double radiusDock = 30; // the floating dock — its own step
  static const double radiusHero = 32; // hero surfaces, the player's chrome

  /// Kept so the ported core still compiles; the overlay *is* the panel step.
  static const double radiusOverlay = radiusPanel;

  // ── Type scale (logical px) ────────────────────────────────────────────────
  static const double typeCaption = 12;
  static const double typeBody = 14;
  static const double typeControl = 15;
  static const double typeTitle = 21;
  static const double typeDisplay = 32;

  /// The interface face of MoOS. Shipped by the image (`ibm-plex-sans-fonts`),
  /// with `IBM Plex Sans Arabic` alongside it, so Arabic and Latin share one
  /// family and one metric instead of Arabic silently dropping to DejaVu.
  ///
  /// Nothing is bundled and nothing is fetched at runtime — the brief forbids
  /// the second and the image makes the first unnecessary.
  static const String fontFamily = 'IBM Plex Sans';
  static const List<String> fontFallback = <String>[
    'IBM Plex Sans Arabic',
    'Noto Sans Arabic',
    'Noto Sans',
    'DejaVu Sans',
  ];
  static const String monoFamily = 'JetBrains Mono';

  // ── Motion ─────────────────────────────────────────────────────────────────
  // Calm, short, eased. The one thing this app must never do is make the user
  // wait for an animation to finish before it will accept the next keypress —
  // a remote control sends them faster than any of these durations.

  /// Hover and focus. The cheapest transition in the app and by far the most
  /// frequent; anything longer than this feels like lag rather than motion.
  static const Duration hover = Duration(milliseconds: 150);

  /// A button taking a press.
  static const Duration press = Duration(milliseconds: 100);

  /// A panel, a popover, a dialog.
  static const Duration panel = Duration(milliseconds: 280);

  /// A page.
  static const Duration page = Duration(milliseconds: 320);

  /// The hero's backdrop crossfade. Long, because it is the one thing on screen
  /// that is *supposed* to be noticed changing.
  static const Duration hero = Duration(milliseconds: 550);

  /// Legacy names, mapped onto the scale above.
  static const Duration fast = hover;
  static const Duration normal = panel;
  static const Duration slow = hero;

  /// Opacity of disabled content.
  static const double disabledOpacity = 0.42;

  // ── Television ─────────────────────────────────────────────────────────────
  /// The margin a TV's overscan can eat. Nothing interactive may live inside it.
  static const double tvSafeArea = 48;
}
