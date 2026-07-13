import 'package:flutter/material.dart';

import '../core/l10n/strings.dart';
import '../core/theme/app_colors.dart';
import '../core/theme/app_typography.dart';
import '../core/theme/motion.dart';
import '../core/theme/nova.dart';
import '../models/category.dart';
import 'buttons.dart';
import 'network_poster.dart';

/// The three-pane browse layout: groups, a wall, and what you are looking at.
///
/// It is the shape a set-top box has had since the first one, and it is here
/// because of what the panel actually contains: 20,187 films in 71 groups. A
/// horizontal strip of 71 chips over a flat wall of 20,187 posters — which is
/// what this app had — asks the user to *scroll sideways through the index*
/// before they can begin, and it opens on whatever the panel happened to sort
/// first, which on this subscription is 32 recorded football matches with
/// identical FIFA artwork.
///
/// Groups down the side are readable at a glance and stay put while the wall
/// moves. And the preview is what turns a wall into a library: the artwork is
/// 180 px wide and the plot is nowhere, so without it choosing a film means
/// opening films.
class BrowseLayout extends StatelessWidget {
  const BrowseLayout({
    super.key,
    required this.groups,
    required this.wall,
    this.preview,
    this.groupWidth = 260,
    this.previewWidth = 340,
  });

  final Widget groups;
  final Widget wall;

  /// Null on a window too narrow to carry it — the wall wins the space, because
  /// a preview pane squeezed to 160 px shows a thumbnail and a truncated word.
  final Widget? preview;

  final double groupWidth;
  final double previewWidth;

  @override
  Widget build(BuildContext context) {
    final width = MediaQuery.sizeOf(context).width;
    final showGroups = width >= 760;
    final showPreview = preview != null && width >= 1180;

    return Row(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (showGroups) ...[
          SizedBox(width: groupWidth, child: groups),
          const _Divider(),
        ],
        Expanded(child: wall),
        if (showPreview) ...[
          const _Divider(),
          SizedBox(width: previewWidth, child: preview),
        ],
      ],
    );
  }
}

class _Divider extends StatelessWidget {
  const _Divider();

  @override
  Widget build(BuildContext context) {
    return const SizedBox(
      width: 1,
      child: ColoredBox(color: AppColors.borderSubtle),
    );
  }
}

/// A panel's own groups, down the side, with the count the panel reported.
class GroupPane extends StatelessWidget {
  const GroupPane({
    super.key,
    required this.categories,
    required this.selectedId,
    required this.strings,
    required this.onSelect,
  });

  final List<Category> categories;
  final String selectedId;
  final S strings;
  final ValueChanged<String> onSelect;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(
            Nova.space5,
            Nova.space5,
            Nova.space5,
            Nova.space3,
          ),
          child: Text(
            strings.groups.toUpperCase(),
            style: AppText.label.copyWith(
              color: AppColors.textMuted,
              letterSpacing: 1.4,
            ),
          ),
        ),
        Expanded(
          child: ListView.builder(
            padding: const EdgeInsetsDirectional.only(
              start: Nova.space3,
              end: Nova.space3,
              bottom: Nova.space6,
            ),
            itemCount: categories.length,
            itemBuilder: (context, i) {
              final category = categories[i];
              return _GroupRow(
                label: category.id == Category.allId
                    ? strings.all
                    : category.name,
                selected: category.id == selectedId,
                onTap: () => onSelect(category.id),
              );
            },
          ),
        ),
      ],
    );
  }
}

class _GroupRow extends StatefulWidget {
  const _GroupRow({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  State<_GroupRow> createState() => _GroupRowState();
}

class _GroupRowState extends State<_GroupRow> {
  bool _hovered = false;
  bool _focused = false;

  @override
  Widget build(BuildContext context) {
    final selected = widget.selected;
    final active = _hovered || _focused;

    return FocusableActionDetector(
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
      mouseCursor: SystemMouseCursors.click,
      child: GestureDetector(
        onTap: widget.onTap,
        behavior: HitTestBehavior.opaque,
        child: AnimatedContainer(
          duration: Motion.duration(context, Nova.hover),
          curve: Ease.enter,
          margin: const EdgeInsets.symmetric(vertical: 1),
          padding: const EdgeInsetsDirectional.fromSTEB(
            Nova.space3,
            Nova.space3,
            Nova.space3,
            Nova.space3,
          ),
          decoration: BoxDecoration(
            color: selected
                ? AppColors.surfaceWarm
                : active
                ? AppColors.surface2
                : Colors.transparent,
            borderRadius: BorderRadius.circular(Nova.radiusControl),
            border: Border.all(
              color: _focused ? AppColors.focus : Colors.transparent,
              width: 1.6,
            ),
          ),
          child: Row(
            children: [
              // The selected group is marked with a bar, not only with a fill:
              // on a dark panel a filled row and a hovered row are two greys
              // three per cent apart, and the user loses their place.
              AnimatedContainer(
                duration: Motion.duration(context, Nova.hover),
                width: 3,
                height: 18,
                decoration: BoxDecoration(
                  color: selected ? AppColors.primary : Colors.transparent,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
              const SizedBox(width: Nova.space3),
              Expanded(
                child: Text(
                  widget.label,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppText.control.copyWith(
                    color: selected
                        ? AppColors.textPrimary
                        : AppColors.textSecondary,
                    fontWeight: selected ? FontWeight.w600 : FontWeight.w400,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// What the card under the cursor actually is.
///
/// Everything on it comes from the list the wall was built from — no second
/// request. Hovering a poster must not cost a round trip to the panel: a user
/// sweeping across four rows of a grid would fire forty of them, and on a
/// connection-limited account that is how a player gets itself throttled.
class PreviewPane extends StatelessWidget {
  const PreviewPane({
    super.key,
    required this.strings,
    this.title,
    this.imageUrl,
    this.meta,
    this.plot,
    this.rating,
    this.isFavorite = false,
    this.onPlay,
    this.onOpen,
    this.onToggleFavorite,
    this.openLabel,
  });

  final S strings;
  final String? title;
  final String? imageUrl;

  /// Year · genre · whatever the list carried. One line.
  final String? meta;
  final String? plot;
  final double? rating;
  final bool isFavorite;

  final VoidCallback? onPlay;
  final VoidCallback? onOpen;
  final VoidCallback? onToggleFavorite;

  /// "Episodes" on the series wall, "More info" on the films.
  final String? openLabel;

  @override
  Widget build(BuildContext context) {
    if (title == null) {
      return _Resting(strings: strings);
    }

    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(
        Nova.space5,
        Nova.space5,
        Nova.space5,
        Nova.space7,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          ClipRRect(
            borderRadius: BorderRadius.circular(Nova.radiusCard),
            child: AspectRatio(
              aspectRatio: 2 / 3,
              child: NetworkPoster(
                url: imageUrl,
                title: title!,
                radius: 0,
                // The pane is the one place a poster is big enough to be worth
                // decoding at full width.
                width: 300,
              ),
            ),
          ),
          const SizedBox(height: Nova.space4),
          Text(title!, style: AppText.title),
          if (meta != null && meta!.isNotEmpty) ...[
            const SizedBox(height: Nova.space2),
            Row(
              children: [
                if ((rating ?? 0) > 0) ...[
                  const Icon(
                    Icons.star_rounded,
                    size: 15,
                    color: AppColors.gold,
                  ),
                  const SizedBox(width: 4),
                  Text(
                    rating!.toStringAsFixed(1),
                    style: AppText.caption.copyWith(color: AppColors.gold),
                  ),
                  const SizedBox(width: Nova.space3),
                ],
                Expanded(
                  child: Text(
                    meta!,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: AppText.caption.copyWith(
                      color: AppColors.textSecondary,
                    ),
                  ),
                ),
              ],
            ),
          ],
          if (plot != null && plot!.trim().isNotEmpty) ...[
            const SizedBox(height: Nova.space4),
            Text(
              plot!.trim(),
              maxLines: 8,
              overflow: TextOverflow.ellipsis,
              style: AppText.body.copyWith(color: AppColors.textSecondary),
            ),
          ],
          const SizedBox(height: Nova.space5),
          if (onPlay != null)
            SizedBox(
              width: double.infinity,
              child: EmberButton(
                label: strings.play,
                icon: Icons.play_arrow_rounded,
                onPressed: onPlay,
              ),
            ),
          if (onOpen != null) ...[
            const SizedBox(height: Nova.space3),
            SizedBox(
              width: double.infinity,
              child: GhostButton(
                label: openLabel ?? strings.moreInfo,
                icon: Icons.info_outline_rounded,
                onPressed: onOpen,
              ),
            ),
          ],
          if (onToggleFavorite != null) ...[
            const SizedBox(height: Nova.space3),
            SizedBox(
              width: double.infinity,
              child: GhostButton(
                label: isFavorite
                    ? strings.removeFromFavorites
                    : strings.addToFavorites,
                icon: isFavorite
                    ? Icons.favorite_rounded
                    : Icons.favorite_border_rounded,
                onPressed: onToggleFavorite,
              ),
            ),
          ],
        ],
      ),
    );
  }
}

/// Before the cursor has touched anything. It says what the pane is for rather
/// than sitting empty, which on a dark surface reads as a rendering failure.
class _Resting extends StatelessWidget {
  const _Resting({required this.strings});

  final S strings;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(Nova.space6),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.style_outlined,
              size: 34,
              color: AppColors.textMuted.withValues(alpha: 0.55),
            ),
            const SizedBox(height: Nova.space3),
            Text(
              strings.preview,
              textAlign: TextAlign.center,
              style: AppText.caption.copyWith(color: AppColors.textMuted),
            ),
          ],
        ),
      ),
    );
  }
}
