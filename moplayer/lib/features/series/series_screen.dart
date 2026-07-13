import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/routes.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_typography.dart';
import '../../core/theme/nova.dart';
import '../../models/library_items.dart';
import '../../models/media_kind.dart';
import '../../models/series.dart';
import '../../providers/content_providers.dart';
import '../../providers/core_providers.dart';
import '../../providers/library_providers.dart';
import '../../providers/system_providers.dart';
import '../../widgets/browse_panes.dart';
import '../../widgets/buttons.dart';
import '../../widgets/media_card.dart';
import '../../widgets/media_rail.dart';
import '../../widgets/state_views.dart';

/// See `movies_screen.dart` for why the ratio runs short of the arithmetic: the
/// two lines of text under a poster are a fixed height, and the tile the grid
/// hands out is narrower than the cap it is given.
const double _tileWidth = 180;
const double _tileWidthCompact = 150;
const double _tileRatio = 0.54;
const double _tileRatioCompact = 0.53;
const double _filterWidth = 280;
const int _skeletonCount = 18;

/// The series catalogue. The movie wall's shape, one action lighter: a series is
/// a folder, so there is nothing on its poster to press play on.
class SeriesScreen extends ConsumerStatefulWidget {
  const SeriesScreen({super.key});

  @override
  ConsumerState<SeriesScreen> createState() => _SeriesScreenState();
}

class _SeriesScreenState extends ConsumerState<SeriesScreen> {
  final TextEditingController _filter = TextEditingController();
  String _query = '';

  /// What the preview pane is showing. A series carries its plot, genre and
  /// rating in the *list* response, so the pane can be complete without a second
  /// request — which is the difference between a preview that appears instantly
  /// on hover and one that spins.
  SeriesItem? _previewed;

  @override
  void dispose() {
    _filter.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final s = ref.watch(stringsProvider);
    final categoryId = ref.watch(selectedSeriesCategoryProvider);
    final categories = ref.watch(seriesCategoriesProvider);
    final series = ref.watch(seriesListProvider(categoryId));
    final compact = ref.watch(settingsProvider).compactGrids;
    final loaded = series.valueOrNull;

    ref.watch(libraryRefreshProvider);
    final library = ref.read(libraryActionsProvider);
    final playlistId = ref.watch(activePlaylistProvider)?.id;
    final item = _previewed;

    return BrowseLayout(
      groups: GroupPane(
        categories: categories.valueOrNull ?? const [],
        selectedId: categoryId,
        strings: s,
        onSelect: (id) {
          setState(() => _previewed = null);
          ref.read(selectedSeriesCategoryProvider.notifier).state = id;
        },
      ),
      preview: PreviewPane(
        strings: s,
        title: item?.name,
        imageUrl: item?.cover,
        meta: item == null ? null : _seriesMeta(item),
        plot: item?.plot,
        rating: item?.rating,
        isFavorite:
            item != null && library.isFavorite(MediaKind.series, item.seriesId),
        // A series is not a thing you press play on — it is a thing you open,
        // and *then* press play on an episode. The pane's primary action says so.
        onOpen: item == null
            ? null
            : () => context.push(Routes.seriesDetail, extra: item),
        openLabel: s.episodes,
        onToggleFavorite: (item == null || playlistId == null)
            ? null
            : () => library.toggleFavorite(
                FavoriteItem(
                  playlistId: playlistId,
                  kind: MediaKind.series,
                  refId: item.seriesId,
                  title: item.name,
                  imageUrl: item.cover,
                  payload: item.toPayload(),
                ),
              ),
      ),
      wall: Padding(
        padding: const EdgeInsetsDirectional.fromSTEB(
          Nova.space5,
          Nova.space5,
          Nova.space5,
          0,
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            SectionHeader(
              title: s.series,
              subtitle: loaded == null ? null : s.seriesCount(loaded.length),
              trailing: _FilterField(
                controller: _filter,
                hint: s.searchSeries,
                clearTooltip: s.clearSearch,
                onChanged: (value) => setState(() => _query = value.trim()),
              ),
            ),
            const SizedBox(height: Nova.space5),
            Expanded(
              child: series.when(
                // A skeleton in the grid's own geometry, not a spinner: the wall
                // must not jump the moment the data lands.
                loading: () => _PosterSkeletonGrid(compact: compact),
                error: (error, _) => ErrorView(
                  strings: s,
                  error: error,
                  onRetry: () => ref.invalidate(seriesListProvider(categoryId)),
                ),
                data: (all) => _SeriesGrid(
                  series: all,
                  query: _query,
                  compact: compact,
                  onPreview: (item) => setState(() => _previewed = item),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

String _seriesMeta(SeriesItem item) => [
  if (item.releaseDate != null && item.releaseDate!.isNotEmpty)
    item.releaseDate!,
  if (item.genre != null && item.genre!.isNotEmpty) item.genre!,
].join('  ·  ');

class _SeriesGrid extends ConsumerWidget {
  const _SeriesGrid({
    required this.series,
    required this.query,
    required this.compact,
    required this.onPreview,
  });

  final List<SeriesItem> series;
  final String query;
  final bool compact;
  final ValueChanged<SeriesItem> onPreview;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(stringsProvider);

    // The favourite lives in a repository rather than in provider state; the
    // heart repaints only because the refresh counter is watched here.
    ref.watch(libraryRefreshProvider);
    final library = ref.read(libraryActionsProvider);
    final playlistId = ref.watch(activePlaylistProvider)?.id;

    if (series.isEmpty) {
      return EmptyView(message: s.empty, icon: Icons.subscriptions_rounded);
    }

    final needle = query.toLowerCase();
    final visible = needle.isEmpty
        ? series
        : series.where((i) => i.name.toLowerCase().contains(needle)).toList();

    if (visible.isEmpty) {
      return EmptyView(
        message: s.noResults(query),
        icon: Icons.search_off_rounded,
      );
    }

    return GridView.builder(
      padding: const EdgeInsets.only(bottom: Nova.space6),
      gridDelegate: _gridDelegate(compact),
      itemCount: visible.length,
      itemBuilder: (context, index) {
        final item = visible[index];
        final rating = item.rating ?? 0;

        // No play button and no progress bar: a resume position belongs to an
        // episode, and which episode that is, is not a decision a poster in a
        // grid can make.
        return PosterCard(
          title: item.name,
          subtitle: item.releaseDate,
          imageUrl: item.cover,
          badge: rating > 0 ? RatingBadge(rating: rating) : null,
          isFavorite: library.isFavorite(MediaKind.series, item.seriesId),
          onToggleFavorite: playlistId == null
              ? null
              : () => library.toggleFavorite(
                  FavoriteItem(
                    playlistId: playlistId,
                    kind: MediaKind.series,
                    refId: item.seriesId,
                    title: item.name,
                    imageUrl: item.cover,
                    payload: item.toPayload(),
                  ),
                ),
          onTap: () => context.push(Routes.seriesDetail, extra: item),
          onPreview: () => onPreview(item),
        );
      },
    );
  }
}

/// Filters what is already on screen. It deliberately does not hit the panel:
/// the category is in memory, and a round trip to narrow a list the user can
/// already see would only make typing feel broken.
class _FilterField extends StatelessWidget {
  const _FilterField({
    required this.controller,
    required this.hint,
    required this.clearTooltip,
    required this.onChanged,
  });

  final TextEditingController controller;
  final String hint;
  final String clearTooltip;
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: _filterWidth,
      child: TextField(
        controller: controller,
        onChanged: onChanged,
        style: AppText.control,
        cursorColor: AppColors.primary,
        decoration: InputDecoration(
          hintText: hint,
          isDense: true,
          prefixIcon: const Icon(Icons.search_rounded, size: 18),
          suffixIcon: ValueListenableBuilder<TextEditingValue>(
            valueListenable: controller,
            builder: (context, value, _) => value.text.isEmpty
                ? const SizedBox.shrink()
                : IconPill(
                    icon: Icons.close_rounded,
                    size: 30,
                    tooltip: clearTooltip,
                    onPressed: () {
                      controller.clear();
                      onChanged('');
                    },
                  ),
          ),
        ),
      ),
    );
  }
}

/// The category filter. It scrolls rather than wraps: a panel will happily
/// return three hundred genres, and a chip cloud that deep would push the grid
/// off the bottom of the window.
class _PosterSkeletonGrid extends StatelessWidget {
  const _PosterSkeletonGrid({required this.compact});

  final bool compact;

  @override
  Widget build(BuildContext context) {
    return GridView.builder(
      padding: const EdgeInsets.only(bottom: Nova.space6),
      physics: const NeverScrollableScrollPhysics(),
      gridDelegate: _gridDelegate(compact),
      itemCount: _skeletonCount,
      itemBuilder: (context, index) => const Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Expanded, not an AspectRatio: whatever slack the cell ratio leaves
          // belongs to the artwork, and a placeholder must never be the thing
          // that overflows.
          Expanded(child: SkeletonBox(radius: Nova.radiusCard)),
          SizedBox(height: Nova.space2),
          SkeletonBox(width: 108, height: 12),
          SizedBox(height: Nova.space1 + 2),
          SkeletonBox(width: 52, height: 9),
        ],
      ),
    );
  }
}

/// One geometry, shared by the wall and the skeleton under it — they have to
/// agree exactly, or the grid jumps at the moment the data lands.
SliverGridDelegateWithMaxCrossAxisExtent _gridDelegate(bool compact) {
  return SliverGridDelegateWithMaxCrossAxisExtent(
    maxCrossAxisExtent: compact ? _tileWidthCompact : _tileWidth,
    childAspectRatio: compact ? _tileRatioCompact : _tileRatio,
    crossAxisSpacing: Nova.space4,
    mainAxisSpacing: Nova.space5,
  );
}
