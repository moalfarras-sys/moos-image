import 'package:flutter/material.dart';

import 'nova.dart';

/// The app's one motion system, and its off switch.
///
/// Two things can ask MoPlayer to stop moving, and both of them must be obeyed:
///
///  * **The system.** `MediaQuery.disableAnimations` is what a MoOS user's
///    "Reduce animations" toggle in System Settings actually sets. An app that
///    ignores it is an app that ignores an accessibility setting.
///  * **The app.** MoPlayer's own *cinematic motion* switch, because the hover
///    zoom on a wall of forty posters is the first thing to cost frames on the
///    integrated GPU a MoOS laptop is likely to have — and a user who wants a
///    smooth scroll more than a lifting card should be able to say so without
///    turning off the whole desktop's animations.
///
/// When motion is reduced, transitions do not become *janky* — they become
/// **instant**, and opacity crossfades survive at a shortened duration. Removing
/// a fade entirely makes content appear to teleport, which is a worse experience
/// than the one being avoided.
class Motion extends InheritedWidget {
  const Motion({super.key, required this.reduced, required super.child});

  /// True when either the system or the app has asked for less movement.
  final bool reduced;

  static Motion of(BuildContext context) {
    final motion = context.dependOnInheritedWidgetOfExactType<Motion>();
    return motion ?? const Motion(reduced: false, child: SizedBox.shrink());
  }

  /// True if motion should be suppressed — checks the app's setting *and* the
  /// platform's, so a caller only has to ask once.
  static bool isReduced(BuildContext context) =>
      of(context).reduced ||
      MediaQuery.maybeDisableAnimationsOf(context) == true;

  /// A duration, scaled for the current motion preference.
  ///
  /// Reduced motion collapses transforms to nothing but keeps a 60 ms fade, which
  /// is below the threshold where the eye reads it as *movement* and above the
  /// one where content appears to pop into being.
  static Duration duration(BuildContext context, Duration full) =>
      isReduced(context) ? const Duration(milliseconds: 60) : full;

  /// The scale a card should take when focused or hovered. 1.0 — no scale at
  /// all — when motion is reduced; the focus ring still marks the card, which is
  /// why the ring may never be the *only* focus affordance.
  static double lift(BuildContext context, double full) =>
      isReduced(context) ? 1.0 : full;

  @override
  bool updateShouldNotify(Motion oldWidget) => reduced != oldWidget.reduced;
}

/// The curves. Named for what they are *for*, not for their shape — a call site
/// that says `Curves.easeOutCubic` has to be re-derived every time it is read.
class Ease {
  const Ease._();

  /// Everything that enters, grows, or settles. Fast out of the gate, slow into
  /// place: the shape of a thing arriving under its own weight.
  static const Curve enter = Curves.easeOutCubic;

  /// Everything that leaves. Quicker than [enter] — waiting for a thing you have
  /// already dismissed is the most reliably irritating moment in any interface.
  static const Curve exit = Curves.easeInCubic;

  /// A dock item taking focus. A spring with the bounce filed off: it overshoots
  /// by a hair and settles, and it never oscillates.
  static const Curve dock = Curves.easeOutBack;

  /// A crossfade between two images.
  static const Curve fade = Curves.easeInOut;
}

/// Standard entrance for a dialog or a details panel: a fade with a small scale
/// from 0.96, which reads as the surface coming *forward* rather than growing.
class ScaleFadeIn extends StatelessWidget {
  const ScaleFadeIn({
    super.key,
    required this.child,
    this.duration = Nova.panel,
    this.from = 0.96,
  });

  final Widget child;
  final Duration duration;
  final double from;

  @override
  Widget build(BuildContext context) {
    final reduced = Motion.isReduced(context);
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0, end: 1),
      duration: Motion.duration(context, duration),
      curve: Ease.enter,
      builder: (context, t, child) => Opacity(
        opacity: t.clamp(0.0, 1.0),
        child: reduced
            ? child
            : Transform.scale(scale: from + (1 - from) * t, child: child),
      ),
      child: child,
    );
  }
}
