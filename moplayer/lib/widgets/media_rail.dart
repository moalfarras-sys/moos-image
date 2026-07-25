import 'package:flutter/material.dart';

import '../core/theme/app_colors.dart';
import '../core/theme/app_typography.dart';
import '../core/theme/motion.dart';
import '../core/theme/nova.dart';
import 'section_header.dart';

// `SectionHeader` used to live in this file. It still resolves for anything that
// imports the rail — the screens are being rewritten in parallel and none of
// them should have to chase an import to compile.
export 'section_header.dart';

/// A horizontal shelf of cards.
///
/// **The wheel belongs to the page.** This rail used to turn a vertical wheel
/// into sideways movement and only hand the event back at the end of the shelf —
/// which is a clever idea and a bad one. The home page is a *column* of shelves:
/// wherever the cursor happens to rest, it is resting on a rail, so every attempt
/// to scroll the page dragged a shelf sideways instead and the page below the
/// fold could not be reached at all. The owner reported it as "I cannot scroll
/// down", which is exactly what it was.
///
/// So the four ways a desktop drives a shelf, and the one it does not:
///
///  * **The arrows.** A mouse with a vertical wheel has no other way to move a
///    horizontal list. They appear on hover, they dim at the ends, and they do
///    not appear at all if the whole shelf already fits.
///  * **Shift + wheel.** The desktop convention for "scroll the other axis", and
///    the one gesture that says *sideways* explicitly. Flutter flips the axis for
///    this itself; the rail only has to not get in the way.
///  * **A trackpad's horizontal pan** arrives already on the right axis, and the
///    list handles it natively.
///  * **The keyboard and the D-pad.** Nothing to do here — the cards are
///    [FocusSurface]s, and a focused one pulls itself into view through every
///    scrollable it sits inside, this one included.
///  * **A plain wheel does nothing to the shelf.** It scrolls the page, like it
///    does everywhere else in every application the user has ever used.
///
/// A rail with nothing in it does not render. Not an empty state, not a header
/// with a gap under it: nothing. An empty shelf is the single clearest way to
/// tell a user their library is broken when it is merely partial.
class MediaRail extends StatefulWidget {
  const MediaRail({
    super.key,
    required this.title,
    required this.itemCount,
    required this.itemBuilder,
    required this.itemWidth,
    required this.height,
    this.subtitle,
    this.onSeeAll,
    this.seeAllLabel,
    this.spacing = Nova.space4,
    this.padding = EdgeInsets.zero,
    this.header = true,
  });

  final String title;
  final String? subtitle;
  final int itemCount;
  final Widget Function(BuildContext context, int index) itemBuilder;
  final double itemWidth;

  /// The shelf's height. It has to hold the artwork *and* the two lines of type
  /// under it — a card is a `Column`, and a rail is a fixed-height box.
  final double height;

  final VoidCallback? onSeeAll;
  final String? seeAllLabel;
  final double spacing;

  /// Leading/trailing inset on the scrolling list, for a rail that runs to the
  /// edge of a full-bleed page.
  final EdgeInsetsGeometry padding;

  /// Off for a shelf that already sits under a [SectionHeader] of its own.
  final bool header;

  @override
  State<MediaRail> createState() => _MediaRailState();
}

class _MediaRailState extends State<MediaRail> {
  final ScrollController _controller = ScrollController();

  bool _hovered = false;
  bool _atStart = true;
  bool _atEnd = true;
  bool _scrollable = false;

  @override
  void initState() {
    super.initState();
    _controller.addListener(_sync);
    WidgetsBinding.instance.addPostFrameCallback((_) => _sync());
  }

  @override
  void didUpdateWidget(MediaRail old) {
    super.didUpdateWidget(old);
    // The list changed under us — a category switch, a favourite removed.
    if (old.itemCount != widget.itemCount) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _sync());
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _sync() {
    if (!mounted || !_controller.hasClients) return;
    final position = _controller.position;
    final max = position.maxScrollExtent;
    final scrollable = max > 1;
    final atStart = position.pixels <= 1;
    final atEnd = position.pixels >= max - 1;

    if (scrollable != _scrollable || atStart != _atStart || atEnd != _atEnd) {
      setState(() {
        _scrollable = scrollable;
        _atStart = atStart;
        _atEnd = atEnd;
      });
    }
  }

  /// One press of an arrow moves a viewport-worth of shelf, less one card, so
  /// that the card at the edge stays on screen and the eye keeps its place.
  void _page(int direction) {
    if (!_controller.hasClients) return;
    final position = _controller.position;
    final step =
        (position.viewportDimension - widget.itemWidth - widget.spacing).clamp(
          widget.itemWidth,
          double.infinity,
        );
    final target = (position.pixels + step * direction).clamp(
      0.0,
      position.maxScrollExtent,
    );
    _controller.animateTo(
      target,
      duration: Motion.duration(context, Nova.panel),
      curve: Ease.enter,
    );
  }

  @override
  Widget build(BuildContext context) {
    if (widget.itemCount == 0) return const SizedBox.shrink();

    // In Arabic the shelf runs right-to-left, so "forward" is a different arrow
    // *and* a different sign. The ListView flips itself; the arrows are told.
    final rtl = Directionality.of(context) == TextDirection.rtl;
    final showArrows = _scrollable && _hovered;

    return MouseRegion(
      onEnter: (_) => setState(() => _hovered = true),
      onExit: (_) => setState(() => _hovered = false),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          if (widget.header)
            Padding(
              padding: const EdgeInsets.only(bottom: Nova.space3),
              child: SectionHeader(
                title: widget.title,
                subtitle: widget.subtitle,
                dense: true,
                trailing: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    if (widget.onSeeAll != null && widget.seeAllLabel != null)
                      _SeeAll(
                        label: widget.seeAllLabel!,
                        onTap: widget.onSeeAll!,
                      ),
                    AnimatedOpacity(
                      opacity: showArrows ? 1 : 0,
                      duration: Motion.duration(context, Nova.hover),
                      curve: Ease.fade,
                      child: IgnorePointer(
                        ignoring: !showArrows,
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            _RailArrow(
                              icon: rtl
                                  ? Icons.chevron_right_rounded
                                  : Icons.chevron_left_rounded,
                              enabled: !_atStart,
                              onTap: () => _page(-1),
                            ),
                            const SizedBox(width: Nova.space1 + 2),
                            _RailArrow(
                              icon: rtl
                                  ? Icons.chevron_left_rounded
                                  : Icons.chevron_right_rounded,
                              enabled: !_atEnd,
                              onTap: () => _page(1),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          SizedBox(
            height: widget.height,
            // No Listener, and no custom pointer-signal handling. A horizontal
            // Scrollable in Flutter already ignores a plain vertical wheel — it
            // reads `scrollDelta.dx`, which a wheel does not produce — and it
            // already flips its own axis for shift+wheel. Everything the shelf
            // needs is what Flutter does when nothing interferes; the bug was the
            // interference.
            child: ListView.separated(
              controller: _controller,
              scrollDirection: Axis.horizontal,
              padding: widget.padding,
              clipBehavior: Clip.none,
              itemCount: widget.itemCount,
              separatorBuilder: (_, _) => SizedBox(width: widget.spacing),
              itemBuilder: (context, index) => SizedBox(
                width: widget.itemWidth,
                child: widget.itemBuilder(context, index),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// An arrow. Disabled at the end it points at rather than removed — a control
/// that vanishes mid-hover moves the one next to it under the cursor.
class _RailArrow extends StatefulWidget {
  const _RailArrow({
    required this.icon,
    required this.onTap,
    required this.enabled,
  });

  final IconData icon;
  final VoidCallback onTap;
  final bool enabled;

  @override
  State<_RailArrow> createState() => _RailArrowState();
}

class _RailArrowState extends State<_RailArrow> {
  bool _hovered = false;

  @override
  Widget build(BuildContext context) {
    final on = widget.enabled;

    return MouseRegion(
      cursor: on ? SystemMouseCursors.click : SystemMouseCursors.basic,
      onEnter: (_) => setState(() => _hovered = true),
      onExit: (_) => setState(() => _hovered = false),
      child: GestureDetector(
        onTap: on ? widget.onTap : null,
        child: AnimatedOpacity(
          opacity: on ? 1 : 0.32,
          duration: Motion.duration(context, Nova.hover),
          child: AnimatedContainer(
            duration: Motion.duration(context, Nova.hover),
            curve: Ease.enter,
            width: 30,
            height: 30,
            decoration: BoxDecoration(
              color: _hovered && on ? AppColors.surface3 : AppColors.surface2,
              shape: BoxShape.circle,
              border: Border.all(
                color: _hovered && on
                    ? AppColors.borderStrong
                    : AppColors.borderSubtle,
              ),
            ),
            child: Icon(
              widget.icon,
              size: 18,
              color: _hovered && on
                  ? AppColors.textPrimary
                  : AppColors.textSecondary,
            ),
          ),
        ),
      ),
    );
  }
}

/// "More". A text action, not a button: it is the least important thing in the
/// header and it should look it.
class _SeeAll extends StatefulWidget {
  const _SeeAll({required this.label, required this.onTap});

  final String label;
  final VoidCallback onTap;

  @override
  State<_SeeAll> createState() => _SeeAllState();
}

class _SeeAllState extends State<_SeeAll> {
  bool _hovered = false;
  bool _focused = false;

  @override
  Widget build(BuildContext context) {
    final lit = _hovered || _focused;
    final rtl = Directionality.of(context) == TextDirection.rtl;

    return Semantics(
      button: true,
      label: widget.label,
      child: FocusableActionDetector(
        onShowHoverHighlight: (v) => setState(() => _hovered = v),
        onShowFocusHighlight: (v) => setState(() => _focused = v),
        mouseCursor: SystemMouseCursors.click,
        actions: {
          ActivateIntent: CallbackAction<ActivateIntent>(
            onInvoke: (_) {
              widget.onTap();
              return null;
            },
          ),
        },
        child: GestureDetector(
          onTap: widget.onTap,
          child: AnimatedContainer(
            duration: Motion.duration(context, Nova.hover),
            curve: Ease.enter,
            padding: const EdgeInsets.symmetric(
              horizontal: Nova.space3,
              vertical: Nova.space1 + 2,
            ),
            margin: const EdgeInsetsDirectional.only(end: Nova.space2),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(999),
              color: lit
                  ? AppColors.primary.withValues(alpha: 0.10)
                  : Colors.transparent,
              border: Border.all(
                color: _focused ? AppColors.focus : Colors.transparent,
              ),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  widget.label,
                  style: AppText.label.copyWith(
                    color: lit ? AppColors.primaryBright : AppColors.textMuted,
                  ),
                ),
                const SizedBox(width: 2),
                Icon(
                  rtl
                      ? Icons.chevron_left_rounded
                      : Icons.chevron_right_rounded,
                  size: 15,
                  color: lit ? AppColors.primaryBright : AppColors.textMuted,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
