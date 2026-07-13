import 'package:flutter/material.dart';

import '../core/theme/app_colors.dart';
import '../core/theme/app_typography.dart';
import '../core/theme/nova.dart';

/// A horizontal shelf of cards, with the arrows a mouse expects.
///
/// A touch app can let you flick a rail. A desktop cannot: a trackpad can
/// scroll it, but a mouse with a vertical wheel cannot, and a rail you can see
/// but not move is broken. So the arrows are real controls, they appear on
/// hover, and they hide at the ends.
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
  });

  final String title;
  final String? subtitle;
  final int itemCount;
  final Widget Function(BuildContext context, int index) itemBuilder;
  final double itemWidth;
  final double height;
  final VoidCallback? onSeeAll;
  final String? seeAllLabel;

  @override
  State<MediaRail> createState() => _MediaRailState();
}

class _MediaRailState extends State<MediaRail> {
  final ScrollController _controller = ScrollController();
  bool _hovered = false;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _scrollBy(double pages) {
    if (!_controller.hasClients) return;
    final delta = (widget.itemWidth + Nova.space4) * pages;
    final target = (_controller.offset + delta).clamp(
      0.0,
      _controller.position.maxScrollExtent,
    );
    _controller.animateTo(target, duration: Nova.slow, curve: Curves.easeOutCubic);
  }

  @override
  Widget build(BuildContext context) {
    if (widget.itemCount == 0) return const SizedBox.shrink();

    // In Arabic the rail runs right-to-left, so "scroll forward" is a different
    // arrow *and* a different sign. The ListView already flips; the arrows have
    // to be told.
    final rtl = Directionality.of(context) == TextDirection.rtl;

    return MouseRegion(
      onEnter: (_) => setState(() => _hovered = true),
      onExit: (_) => setState(() => _hovered = false),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.only(bottom: Nova.space3),
            child: Row(
              children: [
                Text(widget.title, style: AppText.section),
                if (widget.subtitle != null) ...[
                  const SizedBox(width: Nova.space3),
                  Text(widget.subtitle!, style: AppText.caption),
                ],
                const Spacer(),
                if (widget.onSeeAll != null)
                  _TextAction(
                    label: widget.seeAllLabel ?? '',
                    onTap: widget.onSeeAll!,
                  ),
                AnimatedOpacity(
                  opacity: _hovered ? 1 : 0,
                  duration: Nova.fast,
                  child: Row(
                    children: [
                      _RailArrow(
                        icon: rtl
                            ? Icons.chevron_right_rounded
                            : Icons.chevron_left_rounded,
                        onTap: () => _scrollBy(-3),
                      ),
                      const SizedBox(width: Nova.space1),
                      _RailArrow(
                        icon: rtl
                            ? Icons.chevron_left_rounded
                            : Icons.chevron_right_rounded,
                        onTap: () => _scrollBy(3),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          SizedBox(
            height: widget.height,
            child: ListView.separated(
              controller: _controller,
              scrollDirection: Axis.horizontal,
              padding: EdgeInsets.zero,
              itemCount: widget.itemCount,
              separatorBuilder: (_, _) => const SizedBox(width: Nova.space4),
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

class _RailArrow extends StatelessWidget {
  const _RailArrow({required this.icon, required this.onTap});

  final IconData icon;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return MouseRegion(
      cursor: SystemMouseCursors.click,
      child: GestureDetector(
        onTap: onTap,
        child: Container(
          width: 30,
          height: 30,
          decoration: BoxDecoration(
            color: AppColors.surface2,
            shape: BoxShape.circle,
            border: Border.all(color: AppColors.borderSubtle),
          ),
          child: Icon(icon, size: 18, color: AppColors.textSecondary),
        ),
      ),
    );
  }
}

class _TextAction extends StatefulWidget {
  const _TextAction({required this.label, required this.onTap});

  final String label;
  final VoidCallback onTap;

  @override
  State<_TextAction> createState() => _TextActionState();
}

class _TextActionState extends State<_TextAction> {
  bool _hovered = false;

  @override
  Widget build(BuildContext context) {
    return MouseRegion(
      cursor: SystemMouseCursors.click,
      onEnter: (_) => setState(() => _hovered = true),
      onExit: (_) => setState(() => _hovered = false),
      child: GestureDetector(
        onTap: widget.onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: Nova.space3),
          child: Text(
            widget.label,
            style: AppText.label.copyWith(
              color: _hovered ? AppColors.primary : AppColors.textMuted,
            ),
          ),
        ),
      ),
    );
  }
}

/// A section title with an optional trailing control. Used by the grids, which
/// have no rail to hang a title off.
class SectionHeader extends StatelessWidget {
  const SectionHeader({
    super.key,
    required this.title,
    this.subtitle,
    this.trailing,
  });

  final String title;
  final String? subtitle;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(title, style: AppText.headline),
            if (subtitle != null) ...[
              const SizedBox(height: 2),
              Text(subtitle!, style: AppText.caption),
            ],
          ],
        ),
        const Spacer(),
        if (trailing != null) trailing!,
      ],
    );
  }
}
