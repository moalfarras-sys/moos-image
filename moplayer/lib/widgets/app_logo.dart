import 'package:flutter/material.dart';

import '../core/theme/app_colors.dart';
import '../core/theme/app_typography.dart';
import '../core/theme/nova.dart';

/// The MoPlayer mark, with its ember bloom.
///
/// It draws `assets/branding/mark.png` — the mark cut out of the original lockup
/// by `artwork/generate_icons.py`. The lockup's own wordmark is *black* and would
/// be invisible here, so the wordmark is set in type and filled with the brand
/// gradient instead ([showWordmark]).
///
/// If the asset is ever missing from a bundle the mark is *drawn* rather than
/// left as a broken image. A logo is the first thing on the login screen and the
/// last thing that should be allowed to fail visibly.
class AppLogo extends StatelessWidget {
  const AppLogo({
    super.key,
    this.size = 96,
    this.showWordmark = false,
    this.showTagline = false,
    this.tagline,
    this.bloom = true,
  }) : assert(
         !showTagline || tagline != null,
         'A visible tagline must come from the current locale.',
       );

  final double size;
  final bool showWordmark;
  final bool showTagline;
  final String? tagline;

  /// The ember glow behind the mark. Off in the caption bar, where a 22 px mark
  /// with a halo just looks smudged.
  final bool bloom;

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        SizedBox(
          width: size,
          height: size,
          child: DecoratedBox(
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              boxShadow: bloom
                  ? [
                      BoxShadow(
                        color: AppColors.primary.withValues(alpha: 0.35),
                        blurRadius: size * 0.5,
                        spreadRadius: -size * 0.10,
                      ),
                    ]
                  : null,
            ),
            child: Image.asset(
              'assets/branding/mark.png',
              fit: BoxFit.contain,
              filterQuality: FilterQuality.high,
              errorBuilder: (context, _, _) => _DrawnMark(size: size),
            ),
          ),
        ),
        if (showWordmark) ...[
          const SizedBox(height: Nova.space3),
          ShaderMask(
            shaderCallback: (bounds) =>
                AppColors.goldGradient.createShader(bounds),
            child: Text(
              'MoPlayer',
              style: AppText.display.copyWith(color: Colors.white),
              // The wordmark is a mark, not copy: it is Latin in every language
              // the app speaks, exactly as it is in the logo file.
              textDirection: TextDirection.ltr,
            ),
          ),
        ],
        if (showTagline) ...[
          const SizedBox(height: Nova.space1),
          Text(
            tagline!,
            // Tracking breaks Arabic joining; the Latin lockup can carry the
            // wide cinematic spacing, while Arabic keeps its natural shaping.
            style: AppText.label.copyWith(
              letterSpacing: Directionality.of(context) == TextDirection.rtl
                  ? 0
                  : 3,
            ),
          ),
        ],
      ],
    );
  }
}

/// The mark, drawn: an ember disc with the play gate cut out of it. Only ever
/// seen if the asset did not ship.
class _DrawnMark extends StatelessWidget {
  const _DrawnMark({required this.size});

  final double size;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: const BoxDecoration(
        shape: BoxShape.circle,
        gradient: AppColors.emberGradient,
      ),
      child: Center(
        child: Icon(
          Icons.play_arrow_rounded,
          size: size * 0.56,
          color: Colors.white,
        ),
      ),
    );
  }
}
