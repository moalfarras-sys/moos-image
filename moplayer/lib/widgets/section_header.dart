import 'package:flutter/material.dart';

import '../core/theme/app_colors.dart';
import '../core/theme/app_typography.dart';
import '../core/theme/nova.dart';
import 'mo_icons.dart';

/// A section title, with an optional count beside it and an optional control at
/// the end of the row.
///
/// The ember rule at the top of a page: the title is type, not a banner. The one
/// coloured thing in this row is the [accent] hairline — four pixels of ember at
/// the leading edge, which is enough to mark a section and not enough to compete
/// with the artwork under it.
class SectionHeader extends StatelessWidget {
  const SectionHeader({
    super.key,
    required this.title,
    this.subtitle,
    this.trailing,
    this.icon,
    this.accent = false,
    this.dense = false,
  });

  final String title;

  /// The count, the category, the "3 of 12" — never a sentence.
  final String? subtitle;

  /// A filter field, a sort control, a "see all".
  final Widget? trailing;

  final MoIcon? icon;

  /// The ember hairline. For a page's own title, not for every shelf on it.
  final bool accent;

  /// A shelf's header rather than a page's: one type step down.
  final bool dense;

  @override
  Widget build(BuildContext context) {
    final titleStyle = dense ? AppText.section : AppText.headline;

    return Row(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        if (accent) ...[
          Container(
            width: 3,
            height: dense ? 18 : 26,
            decoration: BoxDecoration(
              gradient: AppColors.emberGradient,
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          const SizedBox(width: Nova.space3),
        ],
        if (icon != null) ...[
          MoIconWidget(icon!, size: dense ? 18 : 20, color: AppColors.primary),
          const SizedBox(width: Nova.space2 + 2),
        ],
        Flexible(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                title,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: titleStyle,
              ),
              if (subtitle != null && subtitle!.isNotEmpty) ...[
                const SizedBox(height: 2),
                Text(
                  subtitle!,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppText.caption,
                ),
              ],
            ],
          ),
        ),
        const Spacer(),
        ?trailing,
      ],
    );
  }
}
