import 'package:flutter/material.dart';

import '../core/theme/motion.dart';
import '../core/theme/nova.dart';
import '../models/category.dart';
import 'tiles.dart';

/// The category filter above a grid.
///
/// An IPTV panel will happily return three hundred categories, so this scrolls
/// rather than wraps: a chip cloud three hundred items deep would push the
/// actual content off the bottom of the window. It is also virtualised, for the
/// same reason.
///
/// The selected chip pulls itself into view when the selection changes from
/// elsewhere — a search that lands in a category, a deep link — because a filter
/// bar that is *lit* somewhere off screen is a filter bar that looks broken.
class CategoryChips extends StatefulWidget {
  const CategoryChips({
    super.key,
    required this.categories,
    required this.selectedId,
    required this.onSelect,
    this.height = 40,
    this.spacing = Nova.space2,
    this.padding = EdgeInsets.zero,
    this.showCounts = true,
  });

  final List<Category> categories;
  final String selectedId;
  final ValueChanged<String> onSelect;
  final double height;
  final double spacing;
  final EdgeInsetsGeometry padding;

  /// Counts are only ever drawn when the source actually reported one — an
  /// Xtream panel does not, and a made-up number is worse than none.
  final bool showCounts;

  @override
  State<CategoryChips> createState() => _CategoryChipsState();
}

class _CategoryChipsState extends State<CategoryChips> {
  final ScrollController _controller = ScrollController();
  final Map<String, GlobalKey> _keys = {};

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _revealSelected());
  }

  @override
  void didUpdateWidget(CategoryChips old) {
    super.didUpdateWidget(old);
    if (old.selectedId != widget.selectedId) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _revealSelected());
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _revealSelected() {
    if (!mounted) return;
    final key = _keys[widget.selectedId];
    final context = key?.currentContext;
    // Off-screen chips are not built at all — the list is virtualised — and a
    // chip that was never built cannot be scrolled to. That is fine: it can only
    // happen when the selection is far from the viewport, and the correct answer
    // there is to leave the scroll alone rather than to jump the user.
    if (context == null) return;
    Scrollable.ensureVisible(
      context,
      alignment: 0.5,
      duration: Motion.duration(this.context, Nova.panel),
      curve: Ease.enter,
    );
  }

  @override
  Widget build(BuildContext context) {
    if (widget.categories.isEmpty) return const SizedBox.shrink();

    return SizedBox(
      height: widget.height,
      child: ListView.separated(
        controller: _controller,
        scrollDirection: Axis.horizontal,
        padding: widget.padding,
        clipBehavior: Clip.none,
        itemCount: widget.categories.length,
        separatorBuilder: (_, _) => SizedBox(width: widget.spacing),
        itemBuilder: (context, index) {
          final category = widget.categories[index];
          final key = _keys.putIfAbsent(category.id, GlobalKey.new);

          return KeyedSubtree(
            key: key,
            child: CategoryPill(
              label: category.name,
              count: widget.showCounts ? category.count : null,
              selected: category.id == widget.selectedId,
              onTap: () => widget.onSelect(category.id),
            ),
          );
        },
      ),
    );
  }
}
