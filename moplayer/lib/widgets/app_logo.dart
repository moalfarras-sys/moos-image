import 'package:flutter/material.dart';

import '../core/theme/app_colors.dart';
import '../core/theme/app_typography.dart';
import '../core/theme/nova.dart';

/// The MoPlayer mark, with its ember bloom.
///
/// It draws `assets/branding/mark.png` — the mark cut out of the original
/// lockup by `artwork/generate_icons.py`. The lockup's own wordmark is *black*
/// and would be invisible here, so the wordmark is set in type and filled with
/// the brand gradient instead ([showWordmark]).
class AppLogo extends StatelessWidget {
  const AppLogo({
    super.key,
    this.size = 96,
    this.showWordmark = false,
    this.showTagline = false,
  });

  final double size;
  final bool showWordmark;
  final bool showTagline;

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
              boxShadow: [
                BoxShadow(
                  color: AppColors.primary.withValues(alpha: 0.35),
                  blurRadius: size * 0.5,
                  spreadRadius: -size * 0.10,
                ),
              ],
            ),
            child: Image.asset(
              'assets/branding/mark.png',
              fit: BoxFit.contain,
              filterQuality: FilterQuality.high,
            ),
          ),
        ),
        if (showWordmark) ...[
          SizedBox(height: Nova.space3),
          ShaderMask(
            shaderCallback: (bounds) => AppColors.goldGradient.createShader(bounds),
            child: Text(
              'MoPlayer',
              style: AppText.display.copyWith(color: Colors.white),
            ),
          ),
        ],
        if (showTagline) ...[
          SizedBox(height: Nova.space1),
          Text(
            'by Moalfarras',
            style: AppText.label.copyWith(letterSpacing: 3),
            // The tagline is a signature, not copy: it stays in Latin even in
            // the Arabic UI, exactly as it does in the logo itself.
            textDirection: TextDirection.ltr,
          ),
        ],
      ],
    );
  }
}
