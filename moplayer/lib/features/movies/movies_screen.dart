import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/routes.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_typography.dart';
import '../../core/theme/nova.dart';
import '../../models/library_items.dart';
import '../../models/media_kind.dart';
import '../../models/vod_movie.dart';
import '../../providers/content_providers.dart';
import '../../providers/core_providers.dart';
import '../../providers/library_providers.dart';
import '../../providers/playback_providers.dart';
import '../../providers/system_providers.dart';
import '../../widgets/browse_panes.dart';
import '../../widgets/buttons.dart';
import '../../widgets/media_card.dart';
import '../../widgets/media_rail.dart';
import '../../widgets/state_views.dart';

/// A cell is a 2:3 poster *plus* a title line and a subtitle line — some 41 px
/// of text that does not scale with the artwork. At the 180 px cap the
/// arithmetic wants 180 / (180 × 1.5 + 41) ≈ 0.58, but `maxCrossAxisExtent`
/// hands out tiles *narrower* than the cap to make the columns fit, and the text
/// block stays the height it was while the poster shrinks. So the ratio runs
/// short of the arithmetic on purpose: that slack is what stops a narrow window
/// from clipping the title off the bottom of every cell in the grid.
const double _tileWidth = 180;
const double _tileWidthCompact = 150;
const double _tileRatio = 0.54;
const double _tileRatioCompact = 0.53;
const double _filterWidth = 280;
const int _skeletonCount = 18;

/// The movie catalogue: a category strip over a wall of posters.
class MoviesScreen extends ConsumerStatefulWidget {
  const MoviesScreen({super.key});

  @override
  ConsumerState<MoviesScreen> createState() => _MoviesScreenState();
}

class _MoviesScreenState extends ConsumerState<MoviesScreen> {
  final TextEditingController _filter = TextEditingController();
  String _query = '';

  /// The film the preview pane is showing: whatever the cursor or the keyboard
  /// last landed on. Local state, not a provider — it is worth nothing to any
  /// other screen and it changes on every hover.
  VodMovie? _previewed;

  /// The film whose *plot* we have gone and asked the panel for.
  ///
  /// Not the same thing as [_previewed], and the gap between them is the point: a
  /// list response carries a film's poster, year and rating but not a word of its
  /// story, so the plot is a second request — and a cursor crossing a row of ten
  /// posters would fire ten of them. It is only asked for once the pointer has
  /// *settled*, and the answer is cached for a day, so sweeping back across the
  /// same row costs nothing at all.
  VodMovie? _detailed;
  Timer? _settle;

  static const _settleDelay = Duration(milliseconds: 320);

  void _preview(VodMovie movie) {
    if (identical(movie, _previewed)) return;
    setState(() => _previewed = movie);

    _settle?.cancel();
    _settle = Timer(_settleDelay, () {
      if (mounted && identical(_previewed, movie)) {
        setState(() => _detailed = movie);
      }
    });
  }

  @override
  void dispose() {
    _settle?.cancel();
    _filter.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final s = ref.watch(stringsProvider);
    final categoryId = ref.watch(selectedMovieCategoryProvider);
    final categories = ref.watch(movieCategoriesProvider);
    final movies = ref.watch(moviesProvider(categoryId));
    final compact = ref.watch(settingsProvider).compactGrids;
    final loaded = movies.valueOrNull;

    ref.watch(libraryRefreshProvider);
    final library = ref.read(libraryActionsProvider);
    final playlistId = ref.watch(activePlaylistProvider)?.id;
    final movie = _previewed;

    return BrowseLayout(
      groups: GroupPane(
        categories: categories.valueOrNull ?? const [],
        selectedId: categoryId,
        strings: s,
        onSelect: (id) {
          // The preview belongs to the wall it was picked from. Leaving it up
          // while a different group loads behind it shows a film that is no
          // longer on screen.
          _settle?.cancel();
          setState(() {
            _previewed = null;
            _detailed = null;
          });
          ref.read(selectedMovieCategoryProvider.notifier).state = id;
        },
      ),
      preview: PreviewPane(
        strings: s,
        title: movie?.name,
        imageUrl: movie?.poster,
        meta: movie == null ? null : _movieMeta(movie),
        // The plot is shown only when it belongs to the film currently under the
        // cursor. A plot arriving late for a poster the user has already moved
        // past is worse than no plot: it is the *wrong* plot, on screen, next to
        // the right picture.
        plot: (movie != null && identical(movie, _detailed))
            ? ref.watch(movieDetailProvider(movie)).valueOrNull?.plot
            : null,
        rating: movie?.rating,
        isFavorite:
            movie != null && library.isFavorite(MediaKind.movie, movie.streamId),
        onPlay: movie == null
            ? null
            : () => ref.read(playbackProvider.notifier).playMovie(movie),
        onOpen: movie == null
            ? null
            : () => context.push(Routes.movieDetail, extra: movie),
        onToggleFavorite: (movie == null || playlistId == null)
            ? null
            : () => library.toggleFavorite(
                FavoriteItem(
                  playlistId: playlistId,
                  kind: MediaKind.movie,
                  refId: movie.streamId,
                  title: movie.name,
                  imageUrl: movie.poster,
                  payload: movie.toPayload(),
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
              title: s.movies,
              subtitle: loaded == null ? null : s.moviesCount(loaded.length),
              trailing: _FilterField(
                controller: _filter,
                hint: s.searchMovies,
                clearTooltip: s.clearSearch,
                onChanged: (value) => setState(() => _query = value.trim()),
              ),
            ),
            const SizedBox(height: Nova.space5),
            Expanded(
              child: movies.when(
                // Not a spinner: the grid has to hold its final geometry while
                // it loads, or the first real poster lands under a cursor that
                // was already aimed somewhere else.
                loading: () => _PosterSkeletonGrid(compact: compact),
                error: (error, _) => ErrorView(
                  strings: s,
                  error: error,
                  onRetry: () => ref.invalidate(moviesProvider(categoryId)),
                  onOpenSettings: () => context.go(Routes.settings),
                ),
                data: (all) => _MovieGrid(
                  movies: all,
                  query: _query,
                  compact: compact,
                  onPreview: _preview,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

String _movieMeta(VodMovie movie) => [
  if (movie.year != null && movie.year!.isNotEmpty) movie.year!,
].join('  ·  ');

class _MovieGrid extends ConsumerWidget {
  const _MovieGrid({
    required this.movies,
    required this.query,
    required this.compact,
    required this.onPreview,
  });

  final List<VodMovie> movies;
  final String query;
  final bool compact;
  final ValueChanged<VodMovie> onPreview;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(stringsProvider);

    // Favourites live in a repository, not in provider state. Without watching
    // the refresh counter the heart would stay hollow until something else
    // happened to rebuild the grid.
    ref.watch(libraryRefreshProvider);
    final library = ref.read(libraryActionsProvider);
    final playlistId = ref.watch(activePlaylistProvider)?.id;

    final progress = <String, double>{
      for (final item in ref.watch(continueWatchingProvider))
        if (item.kind == MediaKind.movie) item.refId: item.progress,
    };

    if (movies.isEmpty) {
      return EmptyView(message: s.empty, icon: Icons.movie_rounded);
    }

    final needle = query.toLowerCase();
    final visible = needle.isEmpty
        ? movies
        : movies.where((m) => m.name.toLowerCase().contains(needle)).toList();

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
        final movie = visible[index];
        final rating = movie.rating ?? 0;

        return PosterCard(
          title: movie.name,
          subtitle: movie.year,
          imageUrl: movie.poster,
          progress: progress[movie.streamId],
          badge: rating > 0 ? RatingBadge(rating: rating) : null,
          isFavorite: library.isFavorite(MediaKind.movie, movie.streamId),
          onToggleFavorite: playlistId == null
              ? null
              : () => library.toggleFavorite(
                  FavoriteItem(
                    playlistId: playlistId,
                    kind: MediaKind.movie,
                    refId: movie.streamId,
                    title: movie.name,
                    imageUrl: movie.poster,
                    payload: movie.toPayload(),
                  ),
                ),
          onTap: () => context.push(Routes.movieDetail, extra: movie),
          onPlay: () => ref.read(playbackProvider.notifier).playMovie(movie),
          onPreview: () => onPreview(movie),
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
/// return three hundred genres, and a chip cloud that deep pushes the grid off
/// the bottom of the window.
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

/// One geometry, shared by the wall and the skeleton under it. They have to
/// agree exactly, or the grid jumps at the moment the data lands.
SliverGridDelegateWithMaxCrossAxisExtent _gridDelegate(bool compact) {
  return SliverGridDelegateWithMaxCrossAxisExtent(
    maxCrossAxisExtent: compact ? _tileWidthCompact : _tileWidth,
    childAspectRatio: compact ? _tileRatioCompact : _tileRatio,
    crossAxisSpacing: Nova.space4,
    mainAxisSpacing: Nova.space5,
  );
}
