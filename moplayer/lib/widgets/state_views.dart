import 'package:flutter/material.dart';

import '../core/error/failures.dart';
import '../core/l10n/strings.dart';
import '../core/theme/app_colors.dart';
import '../core/theme/app_typography.dart';
import '../core/theme/nova.dart';
import 'buttons.dart';

/// Turn a [Failure] into something a person can act on.
///
/// The panel's own error text is never shown: an Xtream server's idea of an
/// error message is `{"user_info":{"auth":0}}`, and pasting that at the user
/// tells them nothing about what to do next.
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

class LoadingView extends StatelessWidget {
  const LoadingView({super.key, this.label});

  final String? label;

  @override
  Widget build(BuildContext context) {
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

class EmptyView extends StatelessWidget {
  const EmptyView({
    super.key,
    required this.message,
    this.icon = Icons.inbox_rounded,
    this.action,
  });

  final String message;
  final IconData icon;
  final Widget? action;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 44, color: AppColors.textMuted),
          const SizedBox(height: Nova.space4),
          Text(message, style: AppText.body, textAlign: TextAlign.center),
          if (action != null) ...[const SizedBox(height: Nova.space5), action!],
        ],
      ),
    );
  }
}

class ErrorView extends StatelessWidget {
  const ErrorView({
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
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 420),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(
              Icons.error_outline_rounded,
              size: 44,
              color: AppColors.danger,
            ),
            const SizedBox(height: Nova.space4),
            Text(strings.errorTitle, style: AppText.title),
            const SizedBox(height: Nova.space2),
            Text(
              failureMessage(strings, error),
              style: AppText.body,
              textAlign: TextAlign.center,
            ),
            if (onRetry != null) ...[
              const SizedBox(height: Nova.space5),
              GhostButton(
                label: strings.retry,
                icon: Icons.refresh_rounded,
                onPressed: onRetry,
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// A shimmering placeholder box. Used while a grid loads, so the page does not
/// jump when the real cards land.
class SkeletonBox extends StatefulWidget {
  const SkeletonBox({
    super.key,
    this.width = double.infinity,
    this.height = 16,
    this.radius = Nova.radiusControl,
  });

  final double width;
  final double height;
  final double radius;

  @override
  State<SkeletonBox> createState() => _SkeletonBoxState();
}

class _SkeletonBoxState extends State<SkeletonBox>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1200),
  )..repeat(reverse: true);

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, _) => Container(
        width: widget.width,
        height: widget.height,
        decoration: BoxDecoration(
          color: Color.lerp(
            AppColors.surface2,
            AppColors.surface3,
            _controller.value,
          ),
          borderRadius: BorderRadius.circular(widget.radius),
        ),
      ),
    );
  }
}
