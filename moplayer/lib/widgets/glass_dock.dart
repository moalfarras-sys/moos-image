import 'dart:ui';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../core/theme/app_colors.dart';
import '../core/theme/app_typography.dart';
import '../core/theme/motion.dart';
import '../core/theme/nova.dart';
import 'mo_icons.dart';

/// One destination in the dock.
class DockDestination {
  const DockDestination({
    required this.icon,
    required this.label,
    required this.route,
    required this.shortcut,
  });

  final MoIcon icon;
  final String label;
  final String route;

  /// Shown in the tooltip, not in the dock. A shortcut hint printed next to
  /// every label is six pieces of chrome the user reads once and then never
  /// again — and in the compact dock there is no room for it at all.
  final String shortcut;
}

/// The floating glass dock — MoPlayer's signature.
///
/// It floats: it is `Positioned` at the bottom centre of the shell's `Stack`,
/// over the content, with the content padded so that nothing ever ends *under*
/// it. That last part is the whole reason a floating bar is normally a bad idea,
/// and it is the reason the shell — not the dock — owns the padding.
///
/// ## What it has to survive
///
///  * **Seven labels in three languages.** "Einstellungen" is 13 characters;
///    "الإعدادات" is 9 but sets wider; "Settings" is 8. The dock is laid out
///    intrinsically and sizes itself to whatever the longest one turns out to
///    be — nothing here is a hard-coded width.
///  * **RTL.** The `Row` flips with the `Directionality`, so in Arabic the dock
///    reads Search-first from the *right*. The order of the list does not change;
///    only the axis it is laid out on does.
///  * **A window at 1366 px.** Below [compactWidth] the labels go and the dock
///    becomes seven icons with tooltips — it does *not* become a stretched-out
///    mobile tab bar pinned to the window edges.
///  * **A remote control.** Focus moves along the dock with left/right, leaves it
///    upward into the page, and can be summoned from anywhere with F6 — because
///    a user three hundred posters deep must not have to arrow through all of
///    them to reach Settings.
class GlassDock extends StatelessWidget {
  const GlassDock({
    super.key,
    required this.destinations,
    required this.currentRoute,
    required this.onSelect,
    required this.focusNodes,
    this.onEscape,
  });

  final List<DockDestination> destinations;
  final String currentRoute;
  final ValueChanged<String> onSelect;

  /// Owned by the shell, so that F6 can move focus onto the *selected* item
  /// rather than always onto the first one.
  final List<FocusNode> focusNodes;

  /// Up-arrow or Escape from inside the dock: hand focus back to the page.
  final VoidCallback? onEscape;

  /// Seven translated labels are too dense on the 1397-logical-pixel desktop
  /// used by a scaled 4K display. Tooltips retain every label in compact mode.
  static const double compactWidth = 1500;

  @override
  Widget build(BuildContext context) {
    final compact = MediaQuery.sizeOf(context).width < compactWidth;

    return FocusTraversalGroup(
      // The dock is one region. Arrowing inside it must not fall through into
      // the poster grid behind it.
      policy: OrderedTraversalPolicy(),
      child: Shortcuts(
        shortcuts: const {
          SingleActivator(LogicalKeyboardKey.arrowUp): _LeaveDockIntent(),
          SingleActivator(LogicalKeyboardKey.escape): _LeaveDockIntent(),
        },
        child: Actions(
          actions: {
            _LeaveDockIntent: CallbackAction<_LeaveDockIntent>(
              onInvoke: (_) {
                onEscape?.call();
                return null;
              },
            ),
          },
          child: _DockSurface(
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                for (var i = 0; i < destinations.length; i++)
                  FocusTraversalOrder(
                    order: NumericFocusOrder(i.toDouble()),
                    child: _DockItem(
                      destination: destinations[i],
                      selected: currentRoute == destinations[i].route,
                      compact: compact,
                      focusNode: focusNodes[i],
                      onTap: () => onSelect(destinations[i].route),
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

class _LeaveDockIntent extends Intent {
  const _LeaveDockIntent();
}

/// The pane the items sit on. Split out so the blur is one save-layer for the
/// whole dock rather than one per item.
class _DockSurface extends StatelessWidget {
  const _DockSurface({required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    const radius = BorderRadius.all(Radius.circular(Nova.radiusDock));

    return DecoratedBox(
      decoration: const BoxDecoration(
        borderRadius: radius,
        boxShadow: [
          // Two shadows. The tight one seats the dock on the surface below it;
          // the wide, warm one is the light it is standing in. One shadow alone
          // gives you a sticker; two give you an object.
          BoxShadow(
            color: Color(0x99000000),
            blurRadius: 30,
            offset: Offset(0, 14),
            spreadRadius: -12,
          ),
          BoxShadow(
            color: Color(0x1AFF8A1F),
            blurRadius: 54,
            offset: Offset(0, 10),
            spreadRadius: -18,
          ),
        ],
      ),
      child: ClipRRect(
        borderRadius: radius,
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: 26, sigmaY: 26),
          child: DecoratedBox(
            decoration: BoxDecoration(
              color: AppColors.glassFillStrong,
              borderRadius: radius,
              border: Border.all(color: AppColors.glassStroke),
              gradient: const LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [Color(0x1FFFF3E0), Color(0x00FFF3E0)],
                stops: [0.0, 0.35],
              ),
            ),
            child: Padding(
              padding: const EdgeInsets.symmetric(
                horizontal: Nova.space3,
                vertical: Nova.space3,
              ),
              child: child,
            ),
          ),
        ),
      ),
    );
  }
}

class _DockItem extends StatefulWidget {
  const _DockItem({
    required this.destination,
    required this.selected,
    required this.compact,
    required this.focusNode,
    required this.onTap,
  });

  final DockDestination destination;
  final bool selected;
  final bool compact;
  final FocusNode focusNode;
  final VoidCallback onTap;

  @override
  State<_DockItem> createState() => _DockItemState();
}

class _DockItemState extends State<_DockItem> {
  bool _hovered = false;
  bool _focused = false;

  @override
  Widget build(BuildContext context) {
    final active = _hovered || _focused;
    final lit = active || widget.selected;
    final reduced = Motion.isReduced(context);

    // The brief's range is 1.06–1.10. The lift is a translation *and* a scale:
    // scale alone reads as a zoom, and the thing a dock item should look like it
    // is doing is rising toward the pointer.
    final scale = reduced ? 1.0 : (active ? 1.08 : 1.0);
    final rise = reduced ? 0.0 : (active ? -3.0 : 0.0);

    final iconColor = lit
        ? (widget.selected ? AppColors.primaryBright : AppColors.textPrimary)
        : AppColors.textSecondary;

    final item = AnimatedContainer(
      duration: Motion.duration(context, Nova.hover),
      curve: Ease.dock,
      transform: Matrix4.identity()
        ..translateByDouble(0.0, rise, 0.0, 1.0)
        ..scaleByDouble(scale, scale, 1.0, 1.0),
      transformAlignment: Alignment.center,
      padding: EdgeInsets.symmetric(
        horizontal: widget.compact ? Nova.space3 : Nova.space4,
        vertical: Nova.space2,
      ),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(Nova.radiusPanel),
        // The selected item's capsule. Warm, low, and *behind* the icon — it
        // marks the destination without competing with it.
        color: widget.selected
            ? AppColors.primary.withValues(alpha: 0.14)
            : (active ? AppColors.glassHighlight : Colors.transparent),
        border: Border.all(
          color: _focused
              ? AppColors.focus
              : (widget.selected
                    ? AppColors.primary.withValues(alpha: 0.34)
                    : Colors.transparent),
          width: _focused ? 2 : 1,
        ),
        boxShadow: [
          if (lit)
            BoxShadow(
              color: AppColors.primary.withValues(
                alpha: _focused ? 0.34 : (widget.selected ? 0.22 : 0.16),
              ),
              blurRadius: 26,
              spreadRadius: -8,
              offset: const Offset(0, 6),
            ),
        ],
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          MoIconWidget(
            widget.destination.icon,
            size: 24,
            color: iconColor,
            filled:
                widget.destination.icon == MoIcon.favorites && widget.selected,
          ),
          if (!widget.compact) ...[
            const SizedBox(height: Nova.space1 + 2),
            // The label is always laid out — only its opacity changes. If it were
            // added and removed, the dock would resize every time the pointer
            // crossed it, and a dock that moves under the cursor is a dock you
            // cannot click.
            AnimatedDefaultTextStyle(
              duration: Motion.duration(context, Nova.hover),
              style: AppText.caption.copyWith(
                color: lit ? AppColors.textPrimary : AppColors.textMuted,
                fontWeight: widget.selected ? FontWeight.w600 : FontWeight.w500,
              ),
              child: Text(widget.destination.label, maxLines: 1),
            ),
          ],
          const SizedBox(height: Nova.space1 + 2),
          // The persistent indicator: a short glowing bar. It survives focus
          // moving away into the page, which is the point — a nav item that goes
          // dark the moment you start using the page it opened has stopped
          // telling you where you are.
          AnimatedContainer(
            duration: Motion.duration(context, Nova.hover),
            curve: Ease.enter,
            height: 3,
            width: widget.selected ? 18 : 0,
            decoration: BoxDecoration(
              gradient: AppColors.emberGradient,
              borderRadius: BorderRadius.circular(2),
              boxShadow: [
                if (widget.selected)
                  BoxShadow(
                    color: AppColors.primary.withValues(alpha: 0.7),
                    blurRadius: 10,
                  ),
              ],
            ),
          ),
        ],
      ),
    );

    final focusable = FocusableActionDetector(
      focusNode: widget.focusNode,
      onShowFocusHighlight: (v) => setState(() => _focused = v),
      onShowHoverHighlight: (v) => setState(() => _hovered = v),
      mouseCursor: SystemMouseCursors.click,
      shortcuts: const {
        SingleActivator(LogicalKeyboardKey.enter): ActivateIntent(),
        SingleActivator(LogicalKeyboardKey.space): ActivateIntent(),
        SingleActivator(LogicalKeyboardKey.select): ActivateIntent(),
        SingleActivator(LogicalKeyboardKey.gameButtonA): ActivateIntent(),
      },
      actions: {
        ActivateIntent: CallbackAction<ActivateIntent>(
          onInvoke: (_) {
            widget.onTap();
            return null;
          },
        ),
      },
      child: Semantics(
        button: true,
        selected: widget.selected,
        label: widget.destination.label,
        child: GestureDetector(onTap: widget.onTap, child: item),
      ),
    );

    if (!widget.compact) return focusable;
    return Tooltip(
      message: '${widget.destination.label}  ·  ${widget.destination.shortcut}',
      child: focusable,
    );
  }
}
