import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/error/failures.dart';
import '../models/category.dart';
import '../models/epg_entry.dart';
import '../models/live_channel.dart';
import '../models/live_match.dart';
import '../models/series.dart';
import '../models/vod_movie.dart';
import '../repositories/content_repository.dart';
import '../services/epg/xmltv_guide.dart';
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

/// A record, not a bare stream id: XMLTV keys the guide on the channel's
/// `epg_channel_id`, and the panel's own endpoint keys it on the stream id. Both
/// are needed to ask for one channel's programmes, and a record has the value
/// equality a `family` key requires.
typedef EpgKey = ({String streamId, String? epgChannelId});

final epgProvider = FutureProvider.family<List<EpgEntry>, EpgKey>((
  ref,
  key,
) async {
  return _repo(ref).epg(key.streamId, epgChannelId: key.epgChannelId);
});

/// The whole guide. Watched by the live screen's now/next and by the match strip.
final epgGuideProvider = FutureProvider<EpgGuide>((ref) async {
  ref.watch(catalogRefreshProvider);
  final repo = ref.watch(contentRepositoryProvider);
  if (repo == null) return EpgGuide.empty;
  return repo.guide();
});

/// Today's fixtures, joined to the channels the user actually has.
///
/// The join is the point. A fixture the guide knows about but the subscription
/// does not carry cannot be tuned, and a match card that cannot be pressed is a
/// disappointment dressed as a feature — so it is dropped. What survives is a
/// list of matches that are each one click from playing.
///
/// Finished matches are dropped too, but only after they have finished: a match
/// that kicked off ninety minutes ago is the *most* likely thing the user wants,
/// and it stays at the head of the list while it is on air.
final matchesTodayProvider = FutureProvider<List<LiveMatch>>((ref) async {
  final guide = await ref.watch(epgGuideProvider.future);
  if (guide.matches.isEmpty) return const [];

  final channels = await ref.watch(liveStreamsProvider(Category.allId).future);
  if (channels.isEmpty) return const [];

  // One channel per EPG id — a panel carries the same channel five times (SD,
  // HD, FHD, 4K, "Event"), and five identical cards for one match is a wall.
  // The first one wins, which is the order the panel itself put them in.
  final byEpgId = <String, LiveChannel>{};
  for (final channel in channels) {
    final id = channel.epgChannelId?.trim().toLowerCase();
    if (id == null || id.isEmpty) continue;
    byEpgId.putIfAbsent(id, () => channel);
  }

  final now = DateTime.now();
  final horizon = now.add(const Duration(hours: 30));

  // And one card per *fixture*. The guide already deduped identical programmes
  // on one channel; this is the other half — the same game listed on beIN 1 and
  // on beIN 1 4K is two guide entries and one match, and the viewer wants to see
  // it once. The first channel wins, which is the order the panel listed them in.
  final seenFixtures = <String>{};

  final resolved = <LiveMatch>[];
  for (final match in guide.matches) {
    if (match.isFinished) continue;
    if (match.start.isAfter(horizon)) continue;

    final channel = byEpgId[match.epgChannelId.trim().toLowerCase()];
    if (channel == null) continue;

    final fixture =
        '${match.home}|${match.away}|${match.start.millisecondsSinceEpoch}';
    if (!seenFixtures.add(fixture)) continue;

    resolved.add(
      match.withChannel(
        streamId: channel.streamId,
        channelName: channel.name,
        channelLogo: channel.logo,
      ),
    );
  }

  // On air first, then by kick-off. Two fixtures on air at once are both worth
  // showing; the one that started earlier is the one closer to a result.
  resolved.sort((a, b) {
    if (a.isLiveNow != b.isLiveNow) return a.isLiveNow ? -1 : 1;
    return a.start.compareTo(b.start);
  });

  return resolved;
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

/// The twenty newest films, and the twenty newest series — the rails a returning
/// viewer opens the app to see.
///
/// Only a `take`: the repository already serves every catalogue newest-first
/// (see [newestFirst], and the FIFA wall it exists to prevent), so this does not
/// sort a second time.
const _homeRailLength = 20;

final newestMoviesProvider = FutureProvider<List<VodMovie>>((ref) async {
  final movies = await ref.watch(moviesProvider(Category.allId).future);
  return movies.take(_homeRailLength).toList();
});

final newestSeriesProvider = FutureProvider<List<SeriesItem>>((ref) async {
  final series = await ref.watch(seriesListProvider(Category.allId).future);
  return series.take(_homeRailLength).toList();
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
