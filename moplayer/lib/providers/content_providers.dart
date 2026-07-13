import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/error/failures.dart';
import '../models/category.dart';
import '../models/epg_entry.dart';
import '../models/live_channel.dart';
import '../models/series.dart';
import '../models/vod_movie.dart';
import '../repositories/content_repository.dart';
import 'core_providers.dart';

/// The content repository bound to the active playlist (null when logged out).
final contentRepositoryProvider = Provider<ContentRepository?>((ref) {
  final cfg = ref.watch(activePlaylistProvider);
  if (cfg == null) return null;
  final repo = ContentRepository(
    config: cfg,
    cache: ref.watch(cacheServiceProvider),
  );
  ref.onDispose(repo.dispose);
  return repo;
});

ContentRepository _repo(Ref ref) {
  final r = ref.watch(contentRepositoryProvider);
  if (r == null) throw Failure.notConfigured('No active playlist selected.');
  return r;
}

/// Bumped to force a refresh of catalog providers.
final catalogRefreshProvider = StateProvider<int>((ref) => 0);

// --- Live ----------------------------------------------------------------

final selectedLiveCategoryProvider = StateProvider<String>(
  (ref) => Category.allId,
);

final liveCategoriesProvider = FutureProvider<List<Category>>((ref) async {
  ref.watch(catalogRefreshProvider);
  final cats = await _repo(ref).liveCategories();
  return [Category(id: Category.allId, name: 'All Channels'), ...cats];
});

final liveStreamsProvider = FutureProvider.family<List<LiveChannel>, String>((
  ref,
  categoryId,
) async {
  ref.watch(catalogRefreshProvider);
  return _repo(ref).liveStreams(categoryId: categoryId);
});

final epgProvider = FutureProvider.family<List<EpgEntry>, String>((
  ref,
  streamId,
) async {
  return _repo(ref).epg(streamId);
});

// --- Movies --------------------------------------------------------------

final selectedMovieCategoryProvider = StateProvider<String>(
  (ref) => Category.allId,
);

final movieCategoriesProvider = FutureProvider<List<Category>>((ref) async {
  ref.watch(catalogRefreshProvider);
  final cats = await _repo(ref).movieCategories();
  return [Category(id: Category.allId, name: 'All Movies'), ...cats];
});

final moviesProvider = FutureProvider.family<List<VodMovie>, String>((
  ref,
  categoryId,
) async {
  ref.watch(catalogRefreshProvider);
  return _repo(ref).movies(categoryId: categoryId);
});

final movieDetailProvider = FutureProvider.family<MovieDetail, VodMovie>((
  ref,
  movie,
) async {
  return _repo(ref).movieInfo(movie);
});

// --- Series --------------------------------------------------------------

final selectedSeriesCategoryProvider = StateProvider<String>(
  (ref) => Category.allId,
);

final seriesCategoriesProvider = FutureProvider<List<Category>>((ref) async {
  ref.watch(catalogRefreshProvider);
  final cats = await _repo(ref).seriesCategories();
  return [Category(id: Category.allId, name: 'All Series'), ...cats];
});

final seriesListProvider = FutureProvider.family<List<SeriesItem>, String>((
  ref,
  categoryId,
) async {
  ref.watch(catalogRefreshProvider);
  return _repo(ref).series(categoryId: categoryId);
});

final seriesDetailProvider = FutureProvider.family<SeriesDetail, SeriesItem>((
  ref,
  series,
) async {
  return _repo(ref).seriesInfo(series);
});

// --- Search --------------------------------------------------------------

typedef SearchResults = ({
  List<LiveChannel> live,
  List<VodMovie> movies,
  List<SeriesItem> series,
});

final searchQueryProvider = StateProvider<String>((ref) => '');

final searchResultsProvider = FutureProvider<SearchResults>((ref) async {
  final query = ref.watch(searchQueryProvider).trim();
  if (query.length < 2) {
    return (
      live: <LiveChannel>[],
      movies: <VodMovie>[],
      series: <SeriesItem>[],
    );
  }
  return _repo(ref).search(query);
});
