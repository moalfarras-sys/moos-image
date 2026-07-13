import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../core/theme/app_colors.dart';
import '../core/theme/motion.dart';
import '../core/theme/nova.dart';

/// Every interactive surface in MoPlayer is one of these.
///
/// It exists because the app has to be driven four ways — mouse, keyboard,
/// D-pad/remote and touch — and the *only* reliable way to get that right is to
/// make it impossible to build a control that handles one of them and forgets
/// the others. So this widget owns all four, and a screen that wants a focusable
/// thing wraps it rather than reimplementing it:
///
///  * **Hover and focus are the same visual state.** A remote user pointing at a
///    card and a mouse user pointing at it are asking the same question, and the
///    app should answer it the same way.
///  * **Focus is never signalled by colour alone.** The ring, the lift and the
///    bloom all move together — a user who cannot separate orange from grey
///    still sees the card grow.
///  * **Enter and Space activate.** So does the remote's OK button, which is what
///    a D-pad sends. Handled here, once.
///  * **A focused card scrolls itself into view.** Without this, arrowing down a
///    grid moves the focus off the bottom of the screen and the app looks frozen.
///
/// The lift is suppressed under reduced motion; the ring is not. That asymmetry
/// is the whole reason the ring may never be the only affordance.
class FocusSurface extends StatefulWidget {
  const FocusSurface({
    super.key,
    required this.child,
    this.onTap,
    this.onFocusChange,
    this.focusNode,
    this.autofocus = false,
    this.radius = Nova.radiusCard,
    this.scale = 1.04,
    this.bloom = true,
    this.selected = false,
    this.semanticLabel,
    this.canRequestFocus = true,
  });

  final Widget child;
  final VoidCallback? onTap;
  final ValueChanged<bool>? onFocusChange;
  final FocusNode? focusNode;
  final bool autofocus;
  final double radius;

  /// How much the surface grows when it takes focus. The brief's range is
  /// 1.06–1.10 for the dock and a *modest* lift for a card — a poster that grows
  /// by 10% overlaps its neighbours and the wall stops being a wall.
  final double scale;

  /// The warm bloom under the surface. Off for controls that sit inside an
  /// already-glowing parent, where a second bloom just muddies the first.
  final bool bloom;

  /// Persistent selection, drawn even when focus has moved elsewhere — a nav
  /// item stays lit while the user is three cards deep into the page it opened.
  final bool selected;

  final String? semanticLabel;
  final bool canRequestFocus;

  @override
  State<FocusSurface> createState() => _FocusSurfaceState();
}

class _FocusSurfaceState extends State<FocusSurface> {
  late FocusNode _node = widget.focusNode ?? FocusNode();
  bool _ownsNode = false;
  bool _hovered = false;
  bool _focused = false;
  bool _pressed = false;

  @override
  void initState() {
    super.initState();
    _ownsNode = widget.focusNode == null;
  }

  @override
  void didUpdateWidget(FocusSurface old) {
    super.didUpdateWidget(old);
    if (widget.focusNode != old.focusNode) {
      if (_ownsNode) _node.dispose();
      _node = widget.focusNode ?? FocusNode();
      _ownsNode = widget.focusNode == null;
    }
  }

  @override
  void dispose() {
    if (_ownsNode) _node.dispose();
    super.dispose();
  }

  void _setFocus(bool value) {
    if (_focused == value) return;
    setState(() => _focused = value);
    widget.onFocusChange?.call(value);

    // Arrowing off the bottom of a grid must not walk the focus off the screen.
    // `alignmentPolicy` keeps the scroll to the minimum that reveals the card —
    // centring it instead would make every keypress jump the whole viewport.
    if (value && mounted) {
      Scrollable.ensureVisible(
        context,
        alignment: 0.1,
        alignmentPolicy: ScrollPositionAlignmentPolicy.explicit,
        duration: Motion.duration(context, Nova.hover),
        curve: Ease.enter,
      );
    }
  }

  void _activate() {
    if (widget.onTap == null) return;
    HapticFeedback.selectionClick();
    widget.onTap!.call();
  }

  @override
  Widget build(BuildContext context) {
    final active = _focused || _hovered;
    final lit = active || widget.selected;
    final scale = _pressed
        ? 0.98
        : (active ? Motion.lift(context, widget.scale) : 1.0);

    final borderRadius = BorderRadius.circular(widget.radius);

    return Semantics(
      label: widget.semanticLabel,
      button: widget.onTap != null,
      selected: widget.selected,
      focusable: widget.canRequestFocus,
      focused: _focused,
      child: FocusableActionDetector(
        focusNode: _node,
        autofocus: widget.autofocus,
        enabled: widget.canRequestFocus,
        onShowFocusHighlight: _setFocus,
        onShowHoverHighlight: (v) => setState(() => _hovered = v),
        mouseCursor: widget.onTap == null
            ? MouseCursor.defer
            : SystemMouseCursors.click,
        shortcuts: const {
          SingleActivator(LogicalKeyboardKey.enter): ActivateIntent(),
          SingleActivator(LogicalKeyboardKey.space): ActivateIntent(),
          // What a TV remote's OK button and a game controller's A button send.
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
            scale: scale,
            duration: Motion.duration(
              context,
              _pressed ? Nova.press : Nova.hover,
            ),
            curve: Ease.enter,
            child: AnimatedContainer(
              duration: Motion.duration(context, Nova.hover),
              curve: Ease.enter,
              decoration: BoxDecoration(
                borderRadius: borderRadius,
                border: Border.all(
                  color: _focused
                      ? AppColors.focus
                      : (lit ? AppColors.borderStrong : Colors.transparent),
                  width: _focused ? 2 : 1,
                ),
                boxShadow: [
                  if (lit && widget.bloom)
                    BoxShadow(
                      color: AppColors.primary.withValues(
                        alpha: _focused ? 0.30 : 0.16,
                      ),
                      blurRadius: _focused ? 30 : 20,
                      spreadRadius: -6,
                      offset: const Offset(0, 6),
                    ),
                ],
              ),
              child: ClipRRect(
                // The child is clipped to the same radius as the ring, so a
                // poster's corner never pokes through the border it is inside.
                borderRadius: borderRadius,
                child: widget.child,
              ),
            ),
          ),
        ),
      ),
    );
  }
}
