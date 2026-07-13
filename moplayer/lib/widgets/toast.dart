import 'package:flutter/material.dart';

import '../core/theme/app_colors.dart';
import '../core/theme/app_typography.dart';
import '../core/theme/glass.dart';
import '../core/theme/motion.dart';
import '../core/theme/nova.dart';

/// What a toast is for: confirming something the user did, when the thing they
/// did left no trace on screen. "Copied", "Removed from favorites".
enum ToastKind { neutral, success, danger }

/// A brief confirmation, floating above the dock.
///
/// Deliberately **not** a `SnackBar`. Material's snack bar is a rectangle glued
/// to the bottom edge of the window, which is exactly where MoPlayer's dock
/// floats — the two would overlap, and the one that lost would be the dock the
/// user is trying to reach. This one sits above the dock's reserved space, is
/// made of the same glass as the rest of the chrome, and never blocks a control.
///
/// It also never carries an action. A toast with a button is a dialog that has
/// decided to disappear on its own, and the user will lose that race.
class Toast {
  const Toast._();

  static OverlayEntry? _current;

  static void show(
    BuildContext context, {
    required String message,
    IconData? icon,
    ToastKind kind = ToastKind.neutral,
    Duration duration = const Duration(milliseconds: 2600),
  }) {
    final overlay = Overlay.maybeOf(context, rootOverlay: true);
    if (overlay == null) return;

    // One at a time. Two stacked toasts is how an interface tells the user it
    // has lost track of what it is saying.
    _current?.remove();
    _current = null;

    // The dock's height, which the shell has already injected here. Anything
    // that ignores it lands underneath the dock.
    final dock = MediaQuery.paddingOf(context).bottom;
    final direction = Directionality.of(context);
    final reduced = Motion.isReduced(context);

    late final OverlayEntry entry;
    entry = OverlayEntry(
      builder: (context) => Directionality(
        textDirection: direction,
        child: Positioned(
          left: 0,
          right: 0,
          bottom: dock + Nova.space5,
          child: IgnorePointer(
            child: Center(
              child: _ToastBody(
                message: message,
                icon: icon,
                kind: kind,
                reduced: reduced,
              ),
            ),
          ),
        ),
      ),
    );

    _current = entry;
    overlay.insert(entry);

    Future.delayed(duration, () {
      if (_current != entry) return;
      entry.remove();
      _current = null;
    });
  }
}

class _ToastBody extends StatefulWidget {
  const _ToastBody({
    required this.message,
    required this.icon,
    required this.kind,
    required this.reduced,
  });

  final String message;
  final IconData? icon;
  final ToastKind kind;
  final bool reduced;

  @override
  State<_ToastBody> createState() => _ToastBodyState();
}

class _ToastBodyState extends State<_ToastBody> {
  double _t = 0;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) setState(() => _t = 1);
    });
  }

  @override
  Widget build(BuildContext context) {
    final tint = switch (widget.kind) {
      ToastKind.neutral => AppColors.textSecondary,
      ToastKind.success => AppColors.success,
      ToastKind.danger => AppColors.danger,
    };

    return AnimatedSlide(
      offset: Offset(0, widget.reduced ? 0 : (1 - _t) * 0.4),
      duration: Motion.duration(context, Nova.panel),
      curve: Ease.enter,
      child: AnimatedOpacity(
        opacity: _t,
        duration: Motion.duration(context, Nova.panel),
        curve: Ease.fade,
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 460),
          child: GlassPanel(
            radius: 999,
            blur: 20,
            fill: AppColors.glassFillStrong,
            padding: const EdgeInsets.symmetric(
              horizontal: Nova.space5,
              vertical: Nova.space3,
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                if (widget.icon != null) ...[
                  Icon(widget.icon, size: 17, color: tint),
                  const SizedBox(width: Nova.space3),
                ],
                Flexible(
                  child: Text(
                    widget.message,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: AppText.control,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
