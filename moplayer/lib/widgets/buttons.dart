import 'package:flutter/material.dart';

import '../core/theme/app_colors.dart';
import '../core/theme/app_typography.dart';
import '../core/theme/nova.dart';

/// The primary action. There is exactly one on a screen — it is the ember, and
/// the ember is what the eye goes to first.
class EmberButton extends StatefulWidget {
  const EmberButton({
    super.key,
    required this.label,
    this.icon,
    this.onPressed,
    this.busy = false,
    this.expand = false,
  });

  final String label;
  final IconData? icon;
  final VoidCallback? onPressed;
  final bool busy;
  final bool expand;

  @override
  State<EmberButton> createState() => _EmberButtonState();
}

class _EmberButtonState extends State<EmberButton> {
  bool _hovered = false;

  @override
  Widget build(BuildContext context) {
    final enabled = widget.onPressed != null && !widget.busy;

    return Opacity(
      opacity: enabled ? 1 : Nova.disabledOpacity,
      child: MouseRegion(
        cursor: enabled ? SystemMouseCursors.click : SystemMouseCursors.basic,
        onEnter: (_) => setState(() => _hovered = true),
        onExit: (_) => setState(() => _hovered = false),
        child: GestureDetector(
          onTap: enabled ? widget.onPressed : null,
          child: AnimatedContainer(
            duration: Nova.fast,
            height: 44,
            width: widget.expand ? double.infinity : null,
            padding: const EdgeInsets.symmetric(horizontal: Nova.space5),
            decoration: BoxDecoration(
              gradient: AppColors.emberGradient,
              borderRadius: BorderRadius.circular(Nova.radiusControl),
              boxShadow: [
                if (_hovered && enabled)
                  BoxShadow(
                    color: AppColors.primary.withValues(alpha: 0.38),
                    blurRadius: 22,
                    spreadRadius: -4,
                    offset: const Offset(0, 4),
                  ),
              ],
            ),
            child: Row(
              mainAxisSize: widget.expand ? MainAxisSize.max : MainAxisSize.min,
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                if (widget.busy)
                  const SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: Colors.white,
                    ),
                  )
                else if (widget.icon != null)
                  Icon(widget.icon, size: 19, color: Colors.white),
                if (widget.busy || widget.icon != null)
                  const SizedBox(width: Nova.space2),
                Text(
                  widget.label,
                  style: AppText.button.copyWith(color: Colors.white),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// The secondary action: a Nova control surface, no gradient, no shout.
class GhostButton extends StatefulWidget {
  const GhostButton({
    super.key,
    required this.label,
    this.icon,
    this.onPressed,
    this.danger = false,
  });

  final String label;
  final IconData? icon;
  final VoidCallback? onPressed;
  final bool danger;

  @override
  State<GhostButton> createState() => _GhostButtonState();
}

class _GhostButtonState extends State<GhostButton> {
  bool _hovered = false;

  @override
  Widget build(BuildContext context) {
    final enabled = widget.onPressed != null;
    final tint = widget.danger ? AppColors.danger : AppColors.textPrimary;

    return Opacity(
      opacity: enabled ? 1 : Nova.disabledOpacity,
      child: MouseRegion(
        cursor: enabled ? SystemMouseCursors.click : SystemMouseCursors.basic,
        onEnter: (_) => setState(() => _hovered = true),
        onExit: (_) => setState(() => _hovered = false),
        child: GestureDetector(
          onTap: widget.onPressed,
          child: AnimatedContainer(
            duration: Nova.fast,
            height: 44,
            padding: const EdgeInsets.symmetric(horizontal: Nova.space4),
            decoration: BoxDecoration(
              color: _hovered ? AppColors.surface3 : AppColors.surface2,
              borderRadius: BorderRadius.circular(Nova.radiusControl),
              border: Border.all(
                color: widget.danger && _hovered
                    ? AppColors.danger.withValues(alpha: 0.6)
                    : AppColors.borderSubtle,
              ),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                if (widget.icon != null) ...[
                  Icon(widget.icon, size: 18, color: tint),
                  const SizedBox(width: Nova.space2),
                ],
                Text(widget.label, style: AppText.button.copyWith(color: tint)),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// A round icon button for chrome that floats over video or artwork.
class IconPill extends StatefulWidget {
  const IconPill({
    super.key,
    required this.icon,
    required this.onPressed,
    this.tooltip,
    this.size = 40,
    this.active = false,
    this.filled = false,
  });

  final IconData icon;
  final VoidCallback? onPressed;
  final String? tooltip;
  final double size;

  /// Ember-tinted: the control is *on* (subtitles enabled, muted, favourited).
  final bool active;

  /// Solid ember: this is the primary control of the surface it sits on.
  final bool filled;

  @override
  State<IconPill> createState() => _IconPillState();
}

class _IconPillState extends State<IconPill> {
  bool _hovered = false;

  @override
  Widget build(BuildContext context) {
    final enabled = widget.onPressed != null;

    final color = widget.filled
        ? Colors.white
        : widget.active
        ? AppColors.primary
        : (_hovered ? AppColors.textPrimary : AppColors.textSecondary);

    final button = MouseRegion(
      cursor: enabled ? SystemMouseCursors.click : SystemMouseCursors.basic,
      onEnter: (_) => setState(() => _hovered = true),
      onExit: (_) => setState(() => _hovered = false),
      child: GestureDetector(
        onTap: widget.onPressed,
        child: AnimatedContainer(
          duration: Nova.fast,
          width: widget.size,
          height: widget.size,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            gradient: widget.filled ? AppColors.emberGradient : null,
            color: widget.filled
                ? null
                : (_hovered
                      ? AppColors.surface3.withValues(alpha: 0.9)
                      : Colors.transparent),
          ),
          child: Icon(
            widget.icon,
            size: widget.size * 0.5,
            color: enabled ? color : AppColors.textMuted,
          ),
        ),
      ),
    );

    if (widget.tooltip == null) return button;
    return Tooltip(message: widget.tooltip!, child: button);
  }
}
