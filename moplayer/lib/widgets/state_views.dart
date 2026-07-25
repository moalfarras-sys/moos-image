import 'package:flutter/material.dart';

import '../core/error/failures.dart';
import '../core/l10n/strings.dart';
import '../core/theme/app_colors.dart';
import '../core/theme/app_typography.dart';
import '../core/theme/motion.dart';
import '../core/theme/nova.dart';
import 'buttons.dart';
import 'mo_icons.dart';
import 'skeletons.dart';

// The skeletons used to live here, and half the app imports this file for them.
export 'skeletons.dart';

/// Turn a [Failure] into something a person can act on.
///
/// The panel's own error text is never shown: an Xtream server's idea of an
/// error message is `{"user_info":{"auth":0}}`, and pasting that at the user
/// tells them nothing about what to do next. Neither is a stack trace, ever —
/// it is not the user's bug and it is not their job to read it.
String failureMessage(S s, Object error) {
  if (error is! Failure) return s.errUnknown;
  return switch (error.kind) {
    FailureKind.network => s.errNetwork,
    FailureKind.timeout => s.errTimeout,
    FailureKind.auth => s.errAuth,
    FailureKind.server => s.errServer,
    FailureKind.parse => s.errParse,
    FailureKind.notConfigured => s.errNotConfigured,
    FailureKind.unknown => s.errUnknown,
  };
}

/// True when the failure is one the user can fix in Settings rather than by
/// pressing Retry. Retrying a wrong password is just a slower way to be wrong.
bool failureNeedsSettings(Object error) =>
    error is Failure &&
    (error.kind == FailureKind.auth || error.kind == FailureKind.notConfigured);

/// The last resort. Prefer a skeleton — [PosterGridSkeleton], [RailSkeleton],
/// [ListSkeleton], [DetailSkeleton] — anywhere the shape of the content is
/// already known, which is very nearly everywhere. A spinner tells the user only
/// that the app has not crashed.
///
/// Pass [child] to use this as a centred frame around a skeleton of your own.
class LoadingView extends StatelessWidget {
  const LoadingView({super.key, this.label, this.child});

  final String? label;
  final Widget? child;

  @override
  Widget build(BuildContext context) {
    if (child != null) return child!;

    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const SizedBox(
            width: 26,
            height: 26,
            child: CircularProgressIndicator(strokeWidth: 2.4),
          ),
          if (label != null) ...[
            const SizedBox(height: Nova.space4),
            Text(label!, style: AppText.body),
          ],
        ],
      ),
    );
  }
}

/// Nothing here — and here is what to do about it.
///
/// Small on purpose. A full-bleed illustration of an empty box is a way of
/// making the user feel the emptiness is an event; it is not, it is Tuesday, and
/// the useful part of this view is the button.
class EmptyView extends StatelessWidget {
  const EmptyView({
    super.key,
    required this.message,
    this.icon = Icons.inbox_rounded,
    this.moIcon,
    this.title,
    this.action,
    this.compact = false,
  });

  final String message;

  /// The Material glyph. Ignored when [moIcon] is given.
  final IconData icon;

  /// One of the app's own icons, for the six places that have one.
  final MoIcon? moIcon;

  final String? title;

  /// The way out. An empty state without one is a dead end with better type.
  final Widget? action;

  final bool compact;

  @override
  Widget build(BuildContext context) {
    final glyphSize = compact ? 24.0 : 30.0;

    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 360),
        child: Padding(
          padding: const EdgeInsets.all(Nova.space5),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              // A plate, not a giant outline glyph: it gives the icon a surface
              // to sit on, which is the difference between "designed" and
              // "an icon floating in the void".
              Container(
                width: compact ? 48 : 60,
                height: compact ? 48 : 60,
                decoration: BoxDecoration(
                  color: AppColors.surface2,
                  shape: BoxShape.circle,
                  border: Border.all(color: AppColors.borderSubtle),
                ),
                child: Center(
                  child: moIcon != null
                      ? MoIconWidget(
                          moIcon!,
                          size: glyphSize,
                          color: AppColors.textMuted,
                        )
                      : Icon(icon, size: glyphSize, color: AppColors.textMuted),
                ),
              ),
              const SizedBox(height: Nova.space4),
              if (title != null) ...[
                Text(
                  title!,
                  style: AppText.section,
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: Nova.space2),
              ],
              Text(message, style: AppText.body, textAlign: TextAlign.center),
              if (action != null) ...[
                const SizedBox(height: Nova.space5),
                action!,
              ],
            ],
          ),
        ),
      ),
    );
  }
}

/// Something failed — said in a sentence, with a way forward.
///
/// Three rules, and they are not negotiable:
///
///  * **Never a stack trace.** See [failureMessage].
///  * **Never blame the user.** "Wrong credentials, or the account has expired"
///    is a fact about the state of the world. "You entered the wrong password"
///    is an accusation, and it is wrong half the time.
///  * **Always an action.** Retry when retrying could work; Settings when it
///    could not, because a password does not get better by being sent twice.
class ErrorView extends StatelessWidget {
  const ErrorView({
    super.key,
    required this.strings,
    required this.error,
    this.onRetry,
    this.onOpenSettings,
    this.compact = false,
  });

  final S strings;
  final Object error;
  final VoidCallback? onRetry;

  /// Offered automatically for the failures Settings can actually fix.
  final VoidCallback? onOpenSettings;

  final bool compact;

  @override
  Widget build(BuildContext context) {
    final settingsFirst = failureNeedsSettings(error);
    final showSettings = onOpenSettings != null && settingsFirst;

    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 420),
        child: Padding(
          padding: const EdgeInsets.all(Nova.space5),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: compact ? 48 : 60,
                height: compact ? 48 : 60,
                decoration: BoxDecoration(
                  color: AppColors.danger.withValues(alpha: 0.10),
                  shape: BoxShape.circle,
                  border: Border.all(
                    color: AppColors.danger.withValues(alpha: 0.28),
                  ),
                ),
                child: Icon(
                  Icons.error_outline_rounded,
                  size: compact ? 24 : 30,
                  color: AppColors.danger,
                ),
              ),
              const SizedBox(height: Nova.space4),
              Text(
                strings.errorTitle,
                style: AppText.section,
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: Nova.space2),
              Text(
                failureMessage(strings, error),
                style: AppText.body,
                textAlign: TextAlign.center,
              ),
              if (onRetry != null || showSettings) ...[
                const SizedBox(height: Nova.space5),
                Wrap(
                  spacing: Nova.space3,
                  runSpacing: Nova.space3,
                  alignment: WrapAlignment.center,
                  children: [
                    // The action that can actually work leads. On a bad password
                    // that is Settings, and Retry drops to a ghost beside it.
                    if (showSettings)
                      EmberButton(
                        label: strings.settings,
                        icon: Icons.tune_rounded,
                        onPressed: onOpenSettings,
                      ),
                    if (onRetry != null)
                      showSettings
                          ? GhostButton(
                              label: strings.retry,
                              icon: Icons.refresh_rounded,
                              onPressed: onRetry,
                            )
                          : EmberButton(
                              label: strings.retry,
                              icon: Icons.refresh_rounded,
                              onPressed: onRetry,
                            ),
                    if (!showSettings && onOpenSettings != null)
                      GhostButton(
                        label: strings.settings,
                        icon: Icons.tune_rounded,
                        onPressed: onOpenSettings,
                      ),
                  ],
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

/// A thin inline strip for a failure that is *not* the whole screen — one shelf
/// on the home page that would not load, while the rest of it did.
class InlineError extends StatelessWidget {
  const InlineError({
    super.key,
    required this.strings,
    required this.error,
    this.onRetry,
  });

  final S strings;
  final Object error;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    return AnimatedContainer(
      duration: Motion.duration(context, Nova.hover),
      padding: const EdgeInsets.symmetric(
        horizontal: Nova.space4,
        vertical: Nova.space3,
      ),
      decoration: BoxDecoration(
        color: AppColors.surface2,
        borderRadius: BorderRadius.circular(Nova.radiusControl),
        border: Border.all(color: AppColors.danger.withValues(alpha: 0.24)),
      ),
      child: Row(
        children: [
          const Icon(
            Icons.error_outline_rounded,
            size: 18,
            color: AppColors.danger,
          ),
          const SizedBox(width: Nova.space3),
          Expanded(
            child: Text(
              failureMessage(strings, error),
              style: AppText.body,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
          ),
          if (onRetry != null) ...[
            const SizedBox(width: Nova.space3),
            GhostButton(
              label: strings.retry,
              icon: Icons.refresh_rounded,
              compact: true,
              onPressed: onRetry,
            ),
          ],
        ],
      ),
    );
  }
}
