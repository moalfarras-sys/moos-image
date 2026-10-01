import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../core/theme/app_colors.dart';
import '../core/theme/app_typography.dart';
import '../core/theme/motion.dart';
import '../core/theme/nova.dart';
import 'app_logo.dart';
import 'mo_icons.dart';

/// One place the rail can take the user.
class NavDestination {
  const NavDestination({
    required this.icon,
    required this.label,
    required this.route,
    required this.shortcut,
  });

  final MoIcon icon;
  final String label;
  final String route;

  /// Shown in the tooltip — the keyboard is a first-class way to move here.
  final String shortcut;
}

/// The navigation rail: a slim column on the start edge of the window.
///
/// **Why a rail, and not the floating dock this app used to have.** MoOS
/// already has a floating capsule at the foot of the screen — the MoOS Bar —
/// and a maximised MoPlayer stacked a second capsule right on top of it: two
/// docks, one above the other, both claiming to be where you go next. A rail
/// on the start edge is where desktop media apps keep their destinations, it
/// costs no height (the scarce dimension on a 16:9 panel), and nothing scrolls
/// under it, so no screen has to reserve room for it.
///
/// It is solid, not glass. A blur behind a surface that never has anything
/// moving behind it is a save-layer for an effect with no source, and on the
/// Impeller renderer every full-height save-layer is measured in hundreds of
/// megabytes of graphics memory (see `DESIGN.md`).
class NavRail extends StatelessWidget {
  const NavRail({
    super.key,
    required this.destinations,
    required this.currentRoute,
    required this.onSelect,
    required this.focusNodes,
    this.onEscape,
    this.footer,
  });

  final List<NavDestination> destinations;
  final String currentRoute;
  final ValueChanged<String> onSelect;
  final List<FocusNode> focusNodes;
  final VoidCallback? onEscape;

  /// The source switcher, pinned to the foot of the rail.
  final Widget? footer;

  static const double width = 88;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: width,
      child: FocusTraversalGroup(
        policy: OrderedTraversalPolicy(),
        child: Shortcuts(
          shortcuts: const {
            SingleActivator(LogicalKeyboardKey.escape): _LeaveRailIntent(),
          },
          child: Actions(
            actions: {
              _LeaveRailIntent: CallbackAction<_LeaveRailIntent>(
                onInvoke: (_) {
                  onEscape?.call();
                  return null;
                },
              ),
            },
            child: Column(
              children: [
                const SizedBox(height: Nova.space3),
                const ExcludeSemantics(child: AppLogo(size: 38, bloom: false)),
                const SizedBox(height: Nova.space4),
                Expanded(
                  child: SingleChildScrollView(
                    child: Column(
                      children: [
                        for (var i = 0; i < destinations.length; i++)
                          FocusTraversalOrder(
                            order: NumericFocusOrder(i.toDouble()),
                            child: _RailItem(
                              destination: destinations[i],
                              selected: currentRoute == destinations[i].route,
                              focusNode: focusNodes[i],
                              onTap: () => onSelect(destinations[i].route),
                            ),
                          ),
                      ],
                    ),
                  ),
                ),
                if (footer != null) ...[
                  footer!,
                  const SizedBox(height: Nova.space4),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _LeaveRailIntent extends Intent {
  const _LeaveRailIntent();
}

class _RailItem extends StatefulWidget {
  const _RailItem({
    required this.destination,
    required this.selected,
    required this.focusNode,
    required this.onTap,
  });

  final NavDestination destination;
  final bool selected;
  final FocusNode focusNode;
  final VoidCallback onTap;

  @override
  State<_RailItem> createState() => _RailItemState();
}

class _RailItemState extends State<_RailItem> {
  bool _hovered = false;
  bool _focused = false;
  bool _pressed = false;

  @override
  Widget build(BuildContext context) {
    final selected = widget.selected;
    final lit = selected || _hovered || _focused;
    final duration = Motion.duration(context, Nova.hover);
    final accent = AppColors.primary;
    final iconColor = selected
        ? accent
        : (lit ? AppColors.textPrimary : AppColors.textSecondary);

    return Semantics(
      button: true,
      selected: selected,
      label: widget.destination.label,
      excludeSemantics: true,
      child: Tooltip(
        message:
            '${widget.destination.label}  ·  ${widget.destination.shortcut}',
        preferBelow: false,
        verticalOffset: 0,
        margin: const EdgeInsetsDirectional.only(start: NavRail.width),
        child: FocusableActionDetector(
          focusNode: widget.focusNode,
          mouseCursor: SystemMouseCursors.click,
          onShowHoverHighlight: (v) => setState(() => _hovered = v),
          onShowFocusHighlight: (v) => setState(() => _focused = v),
          actions: {
            ActivateIntent: CallbackAction<ActivateIntent>(
              onInvoke: (_) {
                widget.onTap();
                return null;
              },
            ),
          },
          child: GestureDetector(
            behavior: HitTestBehavior.opaque,
            onTapDown: (_) => setState(() => _pressed = true),
            onTapCancel: () => setState(() => _pressed = false),
            onTapUp: (_) => setState(() => _pressed = false),
            onTap: widget.onTap,
            child: SizedBox(
              width: NavRail.width,
              height: 68,
              child: Stack(
                alignment: Alignment.center,
                children: [
                  // The selection bar on the start edge: the one mark that says
                  // "you are here" without reading the label.
                  PositionedDirectional(
                    start: 0,
                    child: AnimatedContainer(
                      duration: duration,
                      curve: Ease.enter,
                      width: 3,
                      height: selected ? 28 : 0,
                      decoration: BoxDecoration(
                        color: accent,
                        borderRadius: const BorderRadiusDirectional.horizontal(
                          end: Radius.circular(3),
                        ).resolve(Directionality.of(context)),
                      ),
                    ),
                  ),
                  AnimatedScale(
                    duration: Motion.duration(context, Nova.press),
                    scale: _pressed && !Motion.isReduced(context) ? 0.94 : 1,
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        AnimatedContainer(
                          duration: duration,
                          curve: Ease.enter,
                          width: 52,
                          height: 34,
                          decoration: BoxDecoration(
                            borderRadius: BorderRadius.circular(17),
                            color: selected
                                ? accent.withValues(alpha: 0.16)
                                : (lit
                                      ? AppColors.surface3
                                      : Colors.transparent),
                            border: _focused
                                ? Border.all(color: AppColors.focus, width: 2)
                                : null,
                          ),
                          alignment: Alignment.center,
                          child: MoIconWidget(
                            widget.destination.icon,
                            size: 22,
                            color: iconColor,
                            strokeWidth: selected ? 2.1 : 1.9,
                          ),
                        ),
                        const SizedBox(height: 5),
                        Text(
                          widget.destination.label,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          textAlign: TextAlign.center,
                          style: AppText.caption.copyWith(
                            fontSize: 11.5,
                            fontWeight: selected
                                ? FontWeight.w600
                                : FontWeight.w500,
                            color: selected
                                ? AppColors.textPrimary
                                : AppColors.textSecondary,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
