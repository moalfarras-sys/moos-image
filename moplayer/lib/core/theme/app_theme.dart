import 'package:flutter/material.dart';

import 'app_colors.dart';
import 'app_typography.dart';
import 'nova.dart';

/// The global theme. Dark only: a video player has no light mode worth having,
/// and MoOS's own Nova Light is for the shell, not for a cinema surface.
class AppTheme {
  const AppTheme._();

  static ThemeData get dark {
    final base = ThemeData.dark(useMaterial3: true);

    final scheme = ColorScheme.fromSeed(
      seedColor: AppColors.primary,
      brightness: Brightness.dark,
    ).copyWith(
      primary: AppColors.primary,
      onPrimary: Colors.white,
      secondary: AppColors.gold,
      tertiary: AppColors.goldBright,
      surface: AppColors.surface1,
      onSurface: AppColors.textPrimary,
      surfaceContainerHighest: AppColors.surface2,
      outline: AppColors.borderSubtle,
      error: AppColors.danger,
    );

    return base.copyWith(
      colorScheme: scheme,
      scaffoldBackgroundColor: AppColors.surface0,
      canvasColor: AppColors.surface0,

      // Desktop pointers get a hover state, not a splash. Ink splashes are a
      // touch idiom; on a mouse they lag behind the cursor and look broken.
      splashFactory: NoSplash.splashFactory,
      highlightColor: Colors.transparent,
      hoverColor: AppColors.surface3.withValues(alpha: 0.55),
      focusColor: AppColors.focus.withValues(alpha: 0.18),

      textTheme: base.textTheme
          .apply(
            fontFamily: Nova.fontFamily,
            fontFamilyFallback: Nova.fontFallback,
            bodyColor: AppColors.textPrimary,
            displayColor: AppColors.textPrimary,
          )
          .copyWith(
            titleLarge: AppText.title,
            titleMedium: AppText.section,
            bodyMedium: AppText.body,
            labelLarge: AppText.button,
          ),

      appBarTheme: AppBarTheme(
        backgroundColor: Colors.transparent,
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: false,
        titleTextStyle: AppText.title,
        iconTheme: const IconThemeData(color: AppColors.textPrimary, size: 20),
      ),

      dividerTheme: const DividerThemeData(
        color: AppColors.borderSubtle,
        thickness: 1,
        space: 1,
      ),
      iconTheme: const IconThemeData(color: AppColors.textSecondary, size: 20),

      progressIndicatorTheme: const ProgressIndicatorThemeData(
        color: AppColors.primary,
        linearTrackColor: AppColors.surface3,
        circularTrackColor: Colors.transparent,
      ),

      tooltipTheme: TooltipThemeData(
        waitDuration: const Duration(milliseconds: 500),
        padding: const EdgeInsets.symmetric(
          horizontal: Nova.space3,
          vertical: Nova.space2,
        ),
        decoration: BoxDecoration(
          color: AppColors.surface3,
          borderRadius: BorderRadius.circular(Nova.radiusControl),
          border: Border.all(color: AppColors.borderSubtle),
        ),
        textStyle: AppText.caption.copyWith(color: AppColors.textPrimary),
      ),

      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: AppColors.surface2,
        hintStyle: AppText.body.copyWith(color: AppColors.textMuted),
        labelStyle: AppText.label,
        prefixIconColor: AppColors.textMuted,
        contentPadding: const EdgeInsets.symmetric(
          horizontal: Nova.space4,
          vertical: Nova.space3 + 2,
        ),
        border: _fieldBorder(AppColors.borderSubtle),
        enabledBorder: _fieldBorder(AppColors.borderSubtle),
        // The focused field wears the ember-gold ring, like every other
        // focusable surface in this app. See AppColors.focus for why MoPlayer
        // diverges from the system's cyan here, and only here.
        focusedBorder: _fieldBorder(AppColors.focus, width: 1.8),
        errorBorder: _fieldBorder(AppColors.danger),
        focusedErrorBorder: _fieldBorder(AppColors.danger, width: 1.6),
      ),

      snackBarTheme: SnackBarThemeData(
        backgroundColor: AppColors.surface3,
        contentTextStyle: AppText.body.copyWith(color: AppColors.textPrimary),
        behavior: SnackBarBehavior.floating,
        width: 460,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(Nova.radiusControl),
          side: const BorderSide(color: AppColors.borderSubtle),
        ),
      ),

      dialogTheme: DialogThemeData(
        backgroundColor: AppColors.surface1,
        surfaceTintColor: Colors.transparent,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(Nova.radiusOverlay),
          side: const BorderSide(color: AppColors.borderSubtle),
        ),
        titleTextStyle: AppText.title,
        contentTextStyle: AppText.body,
      ),

      popupMenuTheme: PopupMenuThemeData(
        color: AppColors.surface2,
        surfaceTintColor: Colors.transparent,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(Nova.radiusPanel),
          side: const BorderSide(color: AppColors.borderSubtle),
        ),
        textStyle: AppText.control,
      ),

      sliderTheme: SliderThemeData(
        trackHeight: 4,
        activeTrackColor: AppColors.primary,
        inactiveTrackColor: AppColors.surface3,
        thumbColor: Colors.white,
        overlayColor: AppColors.primary.withValues(alpha: 0.16),
        thumbShape: const RoundSliderThumbShape(enabledThumbRadius: 7),
        overlayShape: const RoundSliderOverlayShape(overlayRadius: 14),
      ),

      switchTheme: SwitchThemeData(
        thumbColor: WidgetStateProperty.resolveWith(
          (s) => s.contains(WidgetState.selected) ? Colors.white : AppColors.textMuted,
        ),
        trackColor: WidgetStateProperty.resolveWith(
          (s) => s.contains(WidgetState.selected) ? AppColors.primary : AppColors.surface3,
        ),
        trackOutlineColor: WidgetStateProperty.resolveWith(
          (s) => s.contains(WidgetState.selected) ? Colors.transparent : AppColors.borderSubtle,
        ),
      ),

      scrollbarTheme: ScrollbarThemeData(
        thumbColor: WidgetStateProperty.resolveWith(
          (s) => s.contains(WidgetState.hovered)
              ? AppColors.borderStrong
              : AppColors.borderSubtle,
        ),
        thickness: const WidgetStatePropertyAll(8),
        radius: const Radius.circular(4),
      ),

      bottomSheetTheme: const BottomSheetThemeData(
        backgroundColor: AppColors.surface1,
        modalBackgroundColor: AppColors.surface1,
        surfaceTintColor: Colors.transparent,
      ),

      // The whole app is one dark scroll surface; Material's default overscroll
      // glow paints a light bloom on it.
      splashColor: Colors.transparent,
    );
  }

  static OutlineInputBorder _fieldBorder(Color color, {double width = 1}) {
    return OutlineInputBorder(
      borderRadius: BorderRadius.circular(Nova.radiusControl),
      borderSide: BorderSide(color: color, width: width),
    );
  }
}
