import 'package:flutter/material.dart';

import '../core/theme/app_colors.dart';
import '../core/theme/app_typography.dart';
import '../core/theme/nova.dart';
import '../models/category.dart';

/// The category filter above a grid.
///
/// An IPTV panel will happily return 300 categories, so this scrolls rather than
/// wraps: a wrapping chip cloud 300 items deep would push the actual content off
/// the screen.
class CategoryChips extends StatelessWidget {
  const CategoryChips({
    super.key,
    required this.categories,
    required this.selectedId,
    required this.onSelect,
  });

  final List<Category> categories;
  final String selectedId;
  final ValueChanged<String> onSelect;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 34,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        itemCount: categories.length,
        separatorBuilder: (_, _) => const SizedBox(width: Nova.space2),
        itemBuilder: (context, index) {
          final category = categories[index];
          return _Chip(
            label: category.name,
            count: category.count,
            selected: category.id == selectedId,
            onTap: () => onSelect(category.id),
          );
        },
      ),
    );
  }
}

class _Chip extends StatefulWidget {
  const _Chip({
    required this.label,
    required this.selected,
    required this.onTap,
    this.count,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;
  final int? count;

  @override
  State<_Chip> createState() => _ChipState();
}

class _ChipState extends State<_Chip> {
  bool _hovered = false;

  @override
  Widget build(BuildContext context) {
    return MouseRegion(
      cursor: SystemMouseCursors.click,
      onEnter: (_) => setState(() => _hovered = true),
      onExit: (_) => setState(() => _hovered = false),
      child: GestureDetector(
        onTap: widget.onTap,
        child: AnimatedContainer(
          duration: Nova.fast,
          padding: const EdgeInsets.symmetric(horizontal: Nova.space4),
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: widget.selected
                ? AppColors.primary.withValues(alpha: 0.14)
                : (_hovered ? AppColors.surface3 : AppColors.surface2),
            borderRadius: BorderRadius.circular(Nova.radiusControl),
            border: Border.all(
              color: widget.selected
                  ? AppColors.primary.withValues(alpha: 0.55)
                  : AppColors.borderSubtle,
            ),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                widget.label,
                style: AppText.control.copyWith(
                  fontSize: 13.5,
                  color: widget.selected
                      ? AppColors.primary
                      : AppColors.textSecondary,
                  fontWeight: widget.selected ? FontWeight.w600 : FontWeight.w500,
                ),
              ),
              if (widget.count != null) ...[
                const SizedBox(width: Nova.space2),
                Text('${widget.count}', style: AppText.caption),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
