import 'dart:ui';

import 'package:flutter/material.dart';

import 'app_colors.dart';
import 'baked_gradient.dart';
import 'nova.dart';

/// Glass — the material MoPlayer's chrome is made of.
///
/// The recipe has five layers and every one of them is doing a job:
///
///  1. **A soft dark shadow**, so the pane sits *above* the scene rather than
///     being painted onto it.
///  2. **A real blur** of whatever is behind it.
///  3. **A dark fill at real opacity.** This is the load-bearing one. Nova's
///     rule — *no text on a variable background without an opaque-enough surface
///     beneath it* — is stricter here than anywhere else in MoOS, because the
///     "variable background" is a moving video frame. Turn the blur off and the
///     panel must still be legible; the blur is decoration, never the thing that
///     makes the text readable.
///  4. **A warm hairline border**, tinted with the surface's own hue. A neutral
///     grey line on a warm black reads as dirt.
///  5. **An inner highlight on the top edge only.** Real glass catches light on
///     the edge that faces it and nowhere else, and that single asymmetry is
///     most of what separates "a material" from "a translucent rectangle".
///
/// ## Where glass is allowed — and why the blur is off by default
///
/// On **chrome** that floats over something moving: the player's controls, a
/// toast, a dialog. Never on a card in a scrolling grid.
///
/// The blur itself is opt-in (`blur` defaults to 0). Every [BackdropFilter] is
/// an offscreen layer, and on the Impeller renderer this app uses, each one the
/// size of the window was measured at roughly **400 MB of graphics memory** on
/// the maintainer's 4K RTX 2080 — held for the life of the process, because the
/// driver keeps what the renderer once asked for. MoPlayer idled at 4.9 GB of
/// an 8 GB card with its blurs and film grain in place. The fill (layer 3) is
/// what makes a panel legible, so a panel without the blur loses nothing a
/// viewer reads.
class GlassPanel extends StatelessWidget {
  const GlassPanel({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(Nova.space4),
    this.radius = Nova.radiusPanel,
    this.blur = 0,
    this.fill,
    this.stroke,
    this.glow = false,
    this.shadow = true,
    this.highlight = true,
  });

  final Widget child;
  final EdgeInsetsGeometry padding;
  final double radius;
  final double blur;
  final Color? fill;
  final Color? stroke;

  /// An ember bloom behind the panel. Reserved for the one primary surface on a
  /// screen; more than one, and neither reads as primary.
  final bool glow;
  final bool shadow;

  /// The lit top edge. Off for a panel that is flush against the top of the
  /// window, where there is no light above it to catch.
  final bool highlight;

  @override
  Widget build(BuildContext context) {
    final borderRadius = BorderRadius.circular(radius);
    final base = fill ?? AppColors.glassFill;

    return DecoratedBox(
      decoration: BoxDecoration(
        borderRadius: borderRadius,
        boxShadow: [
          if (shadow)
            const BoxShadow(
              color: Color(0x80000000),
              blurRadius: 32,
              offset: Offset(0, 12),
              spreadRadius: -10,
            ),
          if (glow)
            BoxShadow(
              color: AppColors.primary.withValues(alpha: 0.18),
              blurRadius: 48,
              spreadRadius: -12,
            ),
        ],
      ),
      child: ClipRRect(
        borderRadius: borderRadius,
        child: _blurred(
          blur,
          DecoratedBox(
            decoration: BoxDecoration(
              color: base,
              borderRadius: borderRadius,
              // One hairline all round. A brighter top edge used to be drawn
              // as a gradient — the one thing this renderer makes expensive
              // (see `baked_gradient.dart`) — and a rounded border must be one
              // colour, so a lit panel simply takes the brighter hairline.
              border: Border.all(
                color: highlight
                    ? AppColors.glassHighlight
                    : (stroke ?? AppColors.glassStroke),
              ),
            ),
            child: Padding(padding: padding, child: child),
          ),
        ),
      ),
    );
  }
}

/// A solid card — the default surface for anything that scrolls.
///
/// See the note on [GlassPanel]: this exists so that a grid of two hundred
/// posters costs two hundred `DecoratedBox`es instead of two hundred save-layers.
class SolidCard extends StatelessWidget {
  const SolidCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(Nova.space4),
    this.radius = Nova.radiusCard,
    this.color,
    this.border = true,
    this.onTap,
  });

  final Widget child;
  final EdgeInsetsGeometry padding;
  final double radius;
  final Color? color;
  final bool border;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final borderRadius = BorderRadius.circular(radius);
    final surface = Container(
      padding: padding,
      decoration: BoxDecoration(
        color: color ?? AppColors.surface2,
        borderRadius: borderRadius,
        border: border ? Border.all(color: AppColors.borderSubtle) : null,
      ),
      child: child,
    );

    if (onTap == null) return surface;
    return Material(
      color: Colors.transparent,
      borderRadius: borderRadius,
      child: InkWell(
        onTap: onTap,
        borderRadius: borderRadius,
        hoverColor: AppColors.surface3.withValues(alpha: 0.6),
        child: surface,
      ),
    );
  }
}

/// The old name, kept so the ported core still compiles.
typedef NovaCard = SolidCard;

/// The ambient scene: the ink wash, the accent's bloom high in the trailing
/// corner, and a controlled vignette.
///
/// Drawn once, behind the page, by the shell. Every layer is a static
/// gradient in a `DecoratedBox`, so it costs nothing per frame and no
/// offscreen layer at all.
///
/// There used to be a film grain here: a 64×64 noise tile repeated across the
/// window under an `Opacity`. The opacity made it a window-sized offscreen
/// layer, which on the Impeller renderer measured ~400 MB of graphics memory on
/// a 4K panel — for an effect at 3% opacity. The gradients below are gentle
/// enough not to band without it.
class AmbientScene extends StatelessWidget {
  const AmbientScene({super.key, required this.child, this.grain = false});

  final Widget child;

  /// Kept for source compatibility; the grain is gone (see above).
  final bool grain;

  @override
  Widget build(BuildContext context) {
    // Baked, not shaded: see `baked_gradient.dart` for why a gradient shader
    // this size is measured in gigabytes of graphics memory on this renderer.
    return Stack(
      fit: StackFit.expand,
      children: [
        GradientFill(gradient: AppColors.sceneGradient),
        GradientFill(gradient: AppColors.ambientAmber),
        // The vignette. Very slight — enough to keep the eye in the middle of
        // a 32-inch screen, not enough to be seen as a shape.
        const GradientFill(
          gradient: RadialGradient(
            center: Alignment.center,
            radius: 1.05,
            colors: [Color(0x00000000), Color(0x40000000)],
            stops: [0.6, 1.0],
          ),
        ),
        child,
      ],
    );
  }
}

/// A backdrop blur only when one was asked for.
Widget _blurred(double blur, Widget child) => blur <= 0
    ? child
    : BackdropFilter(
        filter: ImageFilter.blur(sigmaX: blur, sigmaY: blur),
        child: child,
      );
