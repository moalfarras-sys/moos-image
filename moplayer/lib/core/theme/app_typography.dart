import 'package:flutter/material.dart';

import 'app_colors.dart';
import 'nova.dart';

/// The type ramp, on Nova's scale and in Nova's face.
///
/// The iOS app asked for `.SF Pro Display`, which does not exist here. It is
/// replaced by IBM Plex Sans — the MoOS interface face — with IBM Plex Sans
/// Arabic first in the fallback chain, so an Arabic title and its English
/// subtitle sit on the same metric instead of one silently dropping to DejaVu.
class AppText {
  const AppText._();

  static const TextStyle _base = TextStyle(
    fontFamily: Nova.fontFamily,
    fontFamilyFallback: Nova.fontFallback,
    color: AppColors.textPrimary,
  );

  /// Hero titles only. Never a control label — Nova forbids it.
  static TextStyle get display => _base.copyWith(
    fontSize: Nova.typeDisplay,
    height: 1.08,
    fontWeight: FontWeight.w700,
    letterSpacing: -0.4,
  );

  static TextStyle get headline => _base.copyWith(
    fontSize: 24,
    height: 1.15,
    fontWeight: FontWeight.w600,
    letterSpacing: -0.2,
  );

  static TextStyle get title => _base.copyWith(
    fontSize: Nova.typeTitle,
    height: 1.2,
    fontWeight: FontWeight.w600,
  );

  static TextStyle get section => _base.copyWith(
    fontSize: 17,
    height: 1.25,
    fontWeight: FontWeight.w600,
  );

  static TextStyle get subtitle => _base.copyWith(
    fontSize: Nova.typeControl,
    height: 1.3,
    fontWeight: FontWeight.w500,
    color: AppColors.textSecondary,
  );

  static TextStyle get body => _base.copyWith(
    fontSize: Nova.typeBody,
    height: 1.45,
    fontWeight: FontWeight.w400,
    color: AppColors.textSecondary,
  );

  static TextStyle get control => _base.copyWith(
    fontSize: Nova.typeControl,
    height: 1.2,
    fontWeight: FontWeight.w500,
  );

  static TextStyle get button => _base.copyWith(
    fontSize: Nova.typeControl,
    height: 1.2,
    fontWeight: FontWeight.w600,
    letterSpacing: 0.1,
  );

  /// Metadata and dates. Nova asks for 66–72% opacity at this size, which is
  /// what [AppColors.textMuted] already is against `surface-1`.
  static TextStyle get caption => _base.copyWith(
    fontSize: Nova.typeCaption,
    height: 1.3,
    fontWeight: FontWeight.w500,
    color: AppColors.textMuted,
  );

  static TextStyle get label => _base.copyWith(
    fontSize: 12.5,
    height: 1.2,
    fontWeight: FontWeight.w600,
    color: AppColors.textMuted,
  );

  /// Timecodes. Proportional digits make a running clock jitter; the mono face
  /// is the only correct answer for a seek bar.
  static TextStyle get timecode => const TextStyle(
    fontFamily: Nova.monoFamily,
    fontFamilyFallback: ['JetBrains Mono', 'DejaVu Sans Mono', 'monospace'],
    fontSize: 13,
    fontWeight: FontWeight.w500,
    color: AppColors.textPrimary,
    fontFeatures: [FontFeature.tabularFigures()],
  );
}
