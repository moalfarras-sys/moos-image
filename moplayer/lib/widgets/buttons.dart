import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../core/theme/app_colors.dart';
import '../core/theme/app_typography.dart';
import '../core/theme/motion.dart';
import '../core/theme/nova.dart';

/// The focus ring, drawn as an **outer shadow** rather than a border.
///
/// A border is part of a box's layout: growing one from 1 px to 2 px on focus
/// moves the content inside it and nudges every sibling in the row. A control
/// that jiggles when you tab to it is worse than one with no ring at all, so the
/// ring is painted outside the box where it costs nothing.
List<BoxShadow> focusRing(bool focused, {Color color = AppColors.focus}) {
  if (!focused) return const [];
  return [
    // The bloom is painted first, and therefore under the hard ring: the ring is
    // the affordance, the bloom is only what makes it sit *over* the artwork.
    BoxShadow(
      color: color.withValues(alpha: 0.34),
      blurRadius: 18,
      spreadRadius: 2,
    ),
    BoxShadow(color: color, blurRadius: 0, spreadRadius: 2),
  ];
}

/// Hover / focus / press / keyboard, once, for every control in this file.
///
/// Cards use [FocusSurface]; controls use this. The difference is the ring: a
/// card can afford a border that insets its artwork by a pixel, and a 44 px
/// button sitting in a row of other 44 px buttons cannot.
class _Pressable extends StatefulWidget {
  const _Pressable({
    required this.builder,
    required this.onPressed,
    this.focusNode,
    this.autofocus = false,
    this.semanticLabel,
    this.tooltip,
    this.pressScale = 0.97,
  });

  final Widget Function(BuildContext context, bool hovered, bool focused)
  builder;
  final VoidCallback? onPressed;
  final FocusNode? focusNode;
  final bool autofocus;
  final String? semanticLabel;
  final String? tooltip;
  final double pressScale;

  @override
  State<_Pressable> createState() => _PressableState();
}

class _PressableState extends State<_Pressable> {
  bool _hovered = false;
  bool _focused = false;
  bool _pressed = false;

  bool get _enabled => widget.onPressed != null;

  void _activate() {
    if (!_enabled) return;
    HapticFeedback.selectionClick();
    widget.onPressed!();
  }

  @override
  Widget build(BuildContext context) {
    Widget child = FocusableActionDetector(
      focusNode: widget.focusNode,
      autofocus: widget.autofocus,
      enabled: _enabled,
      onShowFocusHighlight: (v) => setState(() => _focused = v),
      onShowHoverHighlight: (v) => setState(() => _hovered = v),
      mouseCursor: _enabled
          ? SystemMouseCursors.click
          : SystemMouseCursors.basic,
      shortcuts: const {
        SingleActivator(LogicalKeyboardKey.enter): ActivateIntent(),
        SingleActivator(LogicalKeyboardKey.space): ActivateIntent(),
        SingleActivator(LogicalKeyboardKey.select): ActivateIntent(),
        SingleActivator(LogicalKeyboardKey.gameButtonA): ActivateIntent(),
      },
      actions: {
        ActivateIntent: CallbackAction<ActivateIntent>(
          onInvoke: (_) {
            _activate();
            return null;
          },
        ),
      },
      child: GestureDetector(
        onTap: _activate,
        onTapDown: (_) => setState(() => _pressed = true),
        onTapUp: (_) => setState(() => _pressed = false),
        onTapCancel: () => setState(() => _pressed = false),
        child: AnimatedScale(
          scale: _pressed && _enabled
              ? Motion.lift(context, widget.pressScale)
              : 1.0,
          duration: Motion.duration(context, Nova.press),
          curve: Ease.enter,
          child: widget.builder(context, _hovered && _enabled, _focused),
        ),
      ),
    );

    if (widget.tooltip != null) {
      child = Tooltip(message: widget.tooltip!, child: child);
    }

    return Semantics(
      label: widget.semanticLabel,
      button: true,
      enabled: _enabled,
      focusable: _enabled,
      focused: _focused,
      child: child,
    );
  }
}

/// The primary action. There is exactly one on a screen — it is the ember, and
/// the ember is what the eye goes to first.
class EmberButton extends StatelessWidget {
  const EmberButton({
    super.key,
    required this.label,
    this.icon,
    this.onPressed,
    this.busy = false,
    this.expand = false,
    this.compact = false,
    this.focusNode,
    this.autofocus = false,
    this.tooltip,
  });

  final String label;
  final IconData? icon;
  final VoidCallback? onPressed;

  /// The action is in flight. The button keeps its width — a spinner that
  /// replaces the label and shrinks the button relayouts the whole row.
  final bool busy;
  final bool expand;

  /// A shorter button, for a toolbar rather than a hero.
  final bool compact;

  final FocusNode? focusNode;
  final bool autofocus;
  final String? tooltip;

  @override
  Widget build(BuildContext context) {
    final enabled = onPressed != null && !busy;
    final height = compact ? 38.0 : 44.0;

    return Opacity(
      opacity: onPressed == null ? Nova.disabledOpacity : 1,
      child: _Pressable(
        onPressed: enabled ? onPressed : null,
        focusNode: focusNode,
        autofocus: autofocus,
        tooltip: tooltip,
        semanticLabel: label,
        builder: (context, hovered, focused) => AnimatedContainer(
          duration: Motion.duration(context, Nova.hover),
          curve: Ease.enter,
          height: height,
          width: expand ? double.infinity : null,
          padding: EdgeInsets.symmetric(
            horizontal: compact ? Nova.space4 : Nova.space5,
          ),
          decoration: BoxDecoration(
            gradient: AppColors.emberGradient,
            borderRadius: BorderRadius.circular(Nova.radiusControl),
            boxShadow: [
              if (hovered && !focused)
                BoxShadow(
                  color: AppColors.primary.withValues(alpha: 0.40),
                  blurRadius: 24,
                  spreadRadius: -4,
                  offset: const Offset(0, 5),
                ),
              ...focusRing(focused),
            ],
          ),
          child: Row(
            mainAxisSize: expand ? MainAxisSize.max : MainAxisSize.min,
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              if (busy)
                const SizedBox(
                  width: 16,
                  height: 16,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    color: Colors.white,
                  ),
                )
              else if (icon != null)
                Icon(icon, size: compact ? 17 : 19, color: Colors.white),
              if (busy || icon != null) const SizedBox(width: Nova.space2),
              Flexible(
                child: Text(
                  label,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppText.button.copyWith(color: Colors.white),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// The secondary action: a control surface, no gradient, no shout.
class GhostButton extends StatelessWidget {
  const GhostButton({
    super.key,
    required this.label,
    this.icon,
    this.onPressed,
    this.danger = false,
    this.expand = false,
    this.compact = false,
    this.selected = false,
    this.busy = false,
    this.focusNode,
    this.autofocus = false,
    this.tooltip,
  });

  final String label;
  final IconData? icon;
  final VoidCallback? onPressed;

  /// Destructive. The tint only appears on hover — a red button at rest reads as
  /// an error that has already happened.
  final bool danger;

  final bool expand;
  final bool compact;

  /// A persistent on-state: a segmented control, a toggled filter.
  final bool selected;

  final bool busy;
  final FocusNode? focusNode;
  final bool autofocus;
  final String? tooltip;

  @override
  Widget build(BuildContext context) {
    final enabled = onPressed != null && !busy;
    final height = compact ? 38.0 : 44.0;

    return Opacity(
      opacity: onPressed == null ? Nova.disabledOpacity : 1,
      child: _Pressable(
        onPressed: enabled ? onPressed : null,
        focusNode: focusNode,
        autofocus: autofocus,
        tooltip: tooltip,
        semanticLabel: label,
        builder: (context, hovered, focused) {
          final tint = danger
              ? AppColors.danger
              : (selected ? AppColors.primary : AppColors.textPrimary);

          return AnimatedContainer(
            duration: Motion.duration(context, Nova.hover),
            curve: Ease.enter,
            height: height,
            width: expand ? double.infinity : null,
            padding: EdgeInsets.symmetric(
              horizontal: compact ? Nova.space3 : Nova.space4,
            ),
            decoration: BoxDecoration(
              color: selected
                  ? AppColors.primary.withValues(alpha: 0.12)
                  : (hovered ? AppColors.surface3 : AppColors.surface2),
              borderRadius: BorderRadius.circular(Nova.radiusControl),
              border: Border.all(
                color: selected
                    ? AppColors.primary.withValues(alpha: 0.55)
                    : (danger && hovered
                          ? AppColors.danger.withValues(alpha: 0.6)
                          : (hovered
                                ? AppColors.borderStrong
                                : AppColors.borderSubtle)),
              ),
              boxShadow: focusRing(focused),
            ),
            child: Row(
              mainAxisSize: expand ? MainAxisSize.max : MainAxisSize.min,
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                if (busy)
                  SizedBox(
                    width: 15,
                    height: 15,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: tint,
                    ),
                  )
                else if (icon != null)
                  Icon(icon, size: compact ? 17 : 18, color: tint),
                if (busy || icon != null) const SizedBox(width: Nova.space2),
                Flexible(
                  child: Text(
                    label,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: AppText.button.copyWith(color: tint),
                  ),
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}

/// A round icon button for chrome that floats over video or artwork.
class IconPill extends StatelessWidget {
  const IconPill({
    super.key,
    required this.icon,
    required this.onPressed,
    this.tooltip,
    this.size = 40,
    this.active = false,
    this.filled = false,
    this.scrim = false,
    this.focusNode,
    this.autofocus = false,
    this.semanticLabel,
  });

  final IconData icon;
  final VoidCallback? onPressed;
  final String? tooltip;
  final double size;

  /// Ember-tinted: the control is *on* (subtitles enabled, muted, favourited).
  final bool active;

  /// Solid ember: this is the primary control of the surface it sits on.
  final bool filled;

  /// A dark plate behind the glyph, for a pill sitting directly on artwork where
  /// a white icon on a white poster would otherwise vanish.
  final bool scrim;

  final FocusNode? focusNode;
  final bool autofocus;
  final String? semanticLabel;

  @override
  Widget build(BuildContext context) {
    final enabled = onPressed != null;

    return _Pressable(
      onPressed: onPressed,
      focusNode: focusNode,
      autofocus: autofocus,
      tooltip: tooltip,
      semanticLabel: semanticLabel ?? tooltip,
      pressScale: 0.92,
      builder: (context, hovered, focused) {
        final color = !enabled
            ? AppColors.textMuted
            : filled
            ? Colors.white
            : active
            ? AppColors.primary
            : (hovered ? AppColors.textPrimary : AppColors.textSecondary);

        return AnimatedContainer(
          duration: Motion.duration(context, Nova.hover),
          curve: Ease.enter,
          width: size,
          height: size,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            gradient: filled ? AppColors.emberGradient : null,
            color: filled
                ? null
                : hovered
                ? AppColors.surface3.withValues(alpha: 0.92)
                : (scrim ? const Color(0x8C05070C) : Colors.transparent),
            boxShadow: [
              if (filled)
                BoxShadow(
                  color: AppColors.primary.withValues(
                    alpha: hovered ? 0.48 : 0.32,
                  ),
                  blurRadius: hovered ? 26 : 18,
                  spreadRadius: -2,
                ),
              ...focusRing(focused),
            ],
          ),
          child: Icon(icon, size: size * 0.5, color: color),
        );
      },
    );
  }
}
