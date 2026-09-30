import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:isolate';

import 'package:flutter/foundation.dart' show visibleForTesting;
import 'package:flutter/services.dart' show rootBundle;

import '../core/constants/app_constants.dart';
import '../core/error/failures.dart';
import '../core/utils/app_logger.dart';
import '../models/category.dart';
import '../models/epg_entry.dart';
import '../models/live_channel.dart';
import '../models/playlist_config.dart';
import '../models/series.dart';
import '../models/vod_movie.dart';
import '../services/catalog/catalog_files.dart';
import '../services/catalog/shelf.dart';
import '../services/epg/guide_job.dart';
import '../services/epg/xmltv_guide.dart';
import '../services/m3u/m3u_catalog.dart';
import '../services/m3u/m3u_parser.dart';
import '../services/stalker/stalker_api.dart';
import '../services/xtream/xtream_api.dart';
import '../services/xtream/xtream_catalog.dart';
import '../services/xtream/xtream_url_builder.dart';

export '../services/xtream/xtream_catalog.dart' show CatalogSection, newestFirst;

/// How a source is actually being read.
enum SourceMode {
  /// The panel's `player_api.php`: typed JSON per section, with categories,
  /// artwork, film and series details and a guide.
  xtream,

  /// A playlist file, sorted into channels, films and series on a background
  /// isolate.
  m3u,

  /// A MAG-style middleware portal.
  stalker,
}

/// What to open, and what to open instead if that fails.
///
/// A panel serves each live channel as HLS (`.m3u8`) and as MPEG-TS (`.ts`),
/// but an account can be limited to one of them, and some panels answer one
/// format with a 404 while the other plays. Trying the second format before
/// reporting a dead channel is the difference between "this server works" and
/// "half the channels are broken".
class PlaybackTarget {
  const PlaybackTarget(this.url, {this.alternatives = const []});

  final String url;
  final List<String> alternatives;
}

typedef CatalogSearch = ({
  List<LiveChannel> live,
  List<VodMovie> movies,
  List<SeriesItem> series,
});

/// Unified content access for the active source.
///
/// **Nothing heavy runs on the UI isolate.** Every catalogue section is fetched,
/// cached and indexed on a background isolate (see [Shelf]), and what comes back
/// is a finished index. The first read of a section after launch comes from the
/// on-disk cache, instantly, even when that copy is old; a stale copy is then
/// refreshed in the background and the screens are told through [changes]. The
/// network is only waited on when there is no copy at all.
///
/// Three kinds of source share this one interface — an Xtream panel, a playlist
/// file and a Stalker portal — and a playlist link that turns out to *be* an
/// Xtream account is read through the account's API (see
/// [PlaylistConfig.xtreamEquivalent]).
class ContentRepository {
  ContentRepository({
    required this.config,
    CatalogFiles? files,
    XtreamApi? api,
    @visibleForTesting Duration? staleAfter,
  }) : _files = files ?? CatalogFiles.forUser(),
       _xtreamConfig = config.isXtream ? config : config.xtreamEquivalent,
       _injectedApi = api,
       _staleAfter = staleAfter ?? CacheTtl.streams {
    _mode = _initialMode();
  }

  final PlaylistConfig config;
  final CatalogFiles _files;
  final PlaylistConfig? _xtreamConfig;
  final XtreamApi? _injectedApi;
  final Duration _staleAfter;

  late SourceMode _mode;

  /// How this source is being read right now. A playlist link can move from
  /// [SourceMode.xtream] to [SourceMode.m3u] once, if the panel's API refuses
  /// the account the link carries.
  SourceMode get mode => _mode;

  String get _ns => config.id;

  final StreamController<CatalogSection> _changes =
      StreamController<CatalogSection>.broadcast();

  /// A section whose content changed after it was first served — a background
  /// refresh landed, or the source switched how it is read.
  Stream<CatalogSection> get changes => _changes.stream;

  bool _disposed = false;

  // Film and series pages exist for every kind of source. A playlist that
  // carries none simply shows them empty, which says something true.
  bool get supportsVod => true;
  bool get supportsSeries => true;

  static const _modeFile = 'mode';

  SourceMode _initialMode() {
    if (config.isStalker) return SourceMode.stalker;
    if (config.isXtream) return SourceMode.xtream;
    if (_xtreamConfig == null) return SourceMode.m3u;
    // A playlist link that carries an account. Read it through the account's
    // API unless a previous run learned that the API refuses it.
    final marker = _files.read(_ns, _modeFile);
    if (marker != null && utf8.decode(marker, allowMalformed: true) == 'm3u') {
      return SourceMode.m3u;
    }
    return SourceMode.xtream;
  }

  XtreamApi? _apiInstance;
  XtreamApi get _api =>
      _injectedApi ?? (_apiInstance ??= XtreamApi(_xtreamConfig!));

  XtreamUrlBuilder get _urls => XtreamUrlBuilder(_xtreamConfig!);

  // ── Sections ───────────────────────────────────────────────────────────────

  final Map<CatalogSection, Shelf<Object>> _shelves = {};
  final Map<CatalogSection, Future<Shelf<Object>>> _inflight = {};
  final Set<CatalogSection> _refreshing = {};

  Future<Shelf<LiveChannel>> liveShelf({bool forceRefresh = false}) async =>
      (await _shelf(CatalogSection.live, forceRefresh)) as Shelf<LiveChannel>;

  Future<Shelf<VodMovie>> movieShelf({bool forceRefresh = false}) async =>
      (await _shelf(CatalogSection.movies, forceRefresh)) as Shelf<VodMovie>;

  Future<Shelf<SeriesItem>> seriesShelf({bool forceRefresh = false}) async =>
      (await _shelf(CatalogSection.series, forceRefresh))
          as Shelf<SeriesItem>;

  /// The section if it is already in memory, without waiting. Screens use this
  /// to draw a first frame with content instead of a spinner.
  Shelf<T>? peek<T>(CatalogSection section) => _shelves[section] as Shelf<T>?;

  Future<Shelf<Object>> _shelf(CatalogSection section, bool forceRefresh) {
    if (!forceRefresh) {
      final ready = _shelves[section];
      if (ready != null) return Future.value(ready);
    }
    final running = _inflight[section];
    if (running != null) return running;
    final future = _load(section, forceRefresh).whenComplete(() {
      _inflight.remove(section);
    });
    _inflight[section] = future;
    return future;
  }

  Future<Shelf<Object>> _load(CatalogSection section, bool forceRefresh) {
    return switch (_mode) {
      SourceMode.xtream => _loadXtream(section, forceRefresh),
      SourceMode.m3u => _loadM3u(section, forceRefresh),
      SourceMode.stalker => _loadStalker(section),
    };
  }

  XtreamShelfJob _xtreamJob(CatalogSection section) {
    final x = _xtreamConfig!;
    return XtreamShelfJob(
      server: x.normalizedServer,
      username: x.username,
      password: x.password,
      cacheRoot: _files.root,
      namespace: _ns,
      section: section,
    );
  }

  Future<Shelf<Object>> _loadXtream(
    CatalogSection section,
    bool forceRefresh,
  ) async {
    final job = _xtreamJob(section);
    if (!forceRefresh) {
      final cached = await _runCachedXtream(job);
      if (cached != null) {
        _shelves[section] = cached;
        if (DateTime.now().difference(cached.fetchedAt) > _staleAfter) {
          _refreshInBackground(section);
        }
        return cached;
      }
    }
    try {
      final fresh = await _runFetchXtream(job);
      _shelves[section] = fresh;
      return fresh;
    } on Failure catch (failure) {
      final stale = _shelves[section];
      if (stale != null) return stale;
      if (_canFallBackToPlaylist(failure)) {
        _switchToPlaylist();
        return _loadM3u(section, forceRefresh);
      }
      rethrow;
    }
  }

  /// A playlist link read as an account falls back to the playlist when the
  /// panel says the account is not one it will serve through its API. A
  /// network failure proves nothing about the API, so it does not count.
  bool _canFallBackToPlaylist(Failure failure) =>
      config.isM3u &&
      (failure.kind == FailureKind.auth ||
          failure.kind == FailureKind.parse ||
          failure.kind == FailureKind.server);

  void _switchToPlaylist() {
    if (_mode == SourceMode.m3u) return;
    log.w('source: the panel API refused this link — reading it as a playlist');
    _mode = SourceMode.m3u;
    _shelves.clear();
    _files.write(_ns, _modeFile, utf8.encode('m3u'));
  }

  void _refreshInBackground(CatalogSection section) {
    if (_refreshing.contains(section) || _disposed) return;
    _refreshing.add(section);
    final Future<void> work = switch (_mode) {
      SourceMode.xtream => _runFetchXtream(_xtreamJob(section)).then((fresh) {
        _shelves[section] = fresh;
        _announce(section);
      }),
      SourceMode.m3u => _fetchM3uLibrary().then((library) {
        _adoptLibrary(library);
        for (final s in CatalogSection.values) {
          _announce(s);
        }
      }),
      SourceMode.stalker => Future<void>.value(),
    };
    unawaited(
      work
          .catchError((Object error) {
            log.w('catalogue refresh failed: ${safeLogMessage(error)}');
          })
          .whenComplete(() => _refreshing.remove(section)),
    );
  }

  void _announce(CatalogSection section) {
    if (!_disposed) _changes.add(section);
  }

  // The isolate entry points are static so that their closures capture the
  // job and nothing else. A closure created inside an instance method can
  // capture `this`, and a repository holding an HTTP client cannot be copied
  // into another isolate.
  static Future<Shelf<Object>?> _runCachedXtream(XtreamShelfJob job) =>
      _isolate(() => loadCachedXtreamShelf(job));

  static Future<Shelf<Object>> _runFetchXtream(XtreamShelfJob job) =>
      _isolate(() => fetchXtreamShelf(job));

  static Future<R> _isolate<R>(FutureOr<R> Function() job) async {
    try {
      return await Isolate.run(job);
    } on RemoteError catch (error) {
      log.w('catalogue job failed: ${safeLogMessage(error)}');
      throw Failure.server('Could not read the catalogue.');
    }
  }

  // ── Playlists ──────────────────────────────────────────────────────────────

  M3uLibrary? _library;
  Future<M3uLibrary>? _libraryLoad;

  String get _playlistUrl => config.m3uUrl.trim();

  M3uLibraryJob get _m3uJob => M3uLibraryJob(
    url: _playlistUrl,
    cacheRoot: _files.root,
    namespace: _ns,
  );

  Future<Shelf<Object>> _loadM3u(
    CatalogSection section,
    bool forceRefresh,
  ) async {
    final library = await _m3uLibrary(forceRefresh: forceRefresh);
    return _shelves[section] ?? _sectionOf(library, section);
  }

  static Shelf<Object> _sectionOf(M3uLibrary library, CatalogSection section) =>
      switch (section) {
        CatalogSection.live => library.live,
        CatalogSection.movies => library.movies,
        CatalogSection.series => library.series,
      };

  void _adoptLibrary(M3uLibrary library) {
    _library = library;
    for (final section in CatalogSection.values) {
      _shelves[section] = _sectionOf(library, section);
    }
  }

  Future<M3uLibrary> _m3uLibrary({bool forceRefresh = false}) {
    if (!forceRefresh && _library != null) return Future.value(_library);
    return _libraryLoad ??= _loadLibrary(forceRefresh).whenComplete(() {
      _libraryLoad = null;
    });
  }

  Future<M3uLibrary> _loadLibrary(bool forceRefresh) async {
    final job = _m3uJob;
    if (!forceRefresh && job.isRemote) {
      final cached = await _runCachedLibrary(job);
      if (cached != null) {
        _adoptLibrary(cached.library);
        if (DateTime.now().difference(cached.written) > _staleAfter) {
          _refreshInBackground(CatalogSection.live);
        }
        return cached.library;
      }
    }
    try {
      final library = await _fetchM3uLibrary();
      _adoptLibrary(library);
      return library;
    } on Failure {
      final stale = _library;
      if (stale != null) return stale;
      rethrow;
    }
  }

  static Future<({M3uLibrary library, DateTime written})?> _runCachedLibrary(
    M3uLibraryJob job,
  ) => _isolate(() => loadCachedM3uLibrary(job));

  static Future<M3uLibrary> _runFetchLibrary(M3uLibraryJob job) =>
      _isolate(() => fetchM3uLibrary(job));

  static Future<M3uLibrary> _runParseText(String text) =>
      _isolate(() => parseM3uText(text));

  Future<M3uLibrary> _fetchM3uLibrary() async {
    final url = _playlistUrl;
    if (url.startsWith('asset://')) {
      final text = await rootBundle.loadString(
        'assets/${url.substring('asset://'.length)}',
      );
      return _runParseText(text);
    }
    return _runFetchLibrary(_m3uJob);
  }

  // ── Portals ────────────────────────────────────────────────────────────────
  //
  // A Stalker portal pages its films and series fourteen at a time and has no
  // "everything" answer to cache, so it is read the way a set-top box reads
  // it: the channel list whole, and films and series a category at a time, as
  // the user opens them. Nothing of it is written to disk; a portal hands out
  // one-time stream links, and its catalogue is only as good as the session
  // that fetched it.

  StalkerApi? _stalkerInstance;
  StalkerApi get _stalker => _stalkerInstance ??= StalkerApi(
    portalUrl: config.serverUrl,
    macAddress: config.macAddress,
  );

  List<Category>? _stalkerMovieCategories;
  List<Category>? _stalkerSeriesCategories;
  final Map<String, Future<List<VodMovie>>> _stalkerMovies = {};
  final Map<String, Future<List<SeriesItem>>> _stalkerSeries = {};

  /// How many pages of one category are read up front. A portal page is
  /// usually fourteen items, so this is the first hundred or so — what a
  /// screen shows before anybody scrolls, without a hundred requests behind it.
  static const _stalkerPages = 8;

  Future<Shelf<Object>> _loadStalker(CatalogSection section) async {
    switch (section) {
      case CatalogSection.live:
        final results = await Future.wait<Object>([
          _stalker.liveGenres(),
          _stalker.liveChannels(),
        ]);
        final shelf = Shelf<LiveChannel>.build(
          items: results[1] as List<LiveChannel>,
          categoryOf: (c) => c.categoryId,
          nameOf: (c) => c.name,
          declared: results[0] as List<Category>,
        );
        _shelves[section] = shelf;
        return shelf;
      case CatalogSection.movies:
        _stalkerMovieCategories ??= await _stalker.vodCategories();
        final items = await _stalkerMoviesIn(Category.allId);
        final shelf = Shelf<VodMovie>.build(
          items: items,
          categoryOf: (m) => m.categoryId,
          nameOf: (m) => m.name,
        );
        _shelves[section] = shelf;
        return shelf;
      case CatalogSection.series:
        _stalkerSeriesCategories ??= await _stalker.seriesCategories();
        final items = await _stalkerSeriesIn(Category.allId);
        final shelf = Shelf<SeriesItem>.build(
          items: items,
          categoryOf: (s) => s.categoryId,
          nameOf: (s) => s.name,
        );
        _shelves[section] = shelf;
        return shelf;
    }
  }

  static String _portalCategory(String? id) =>
      (id == null || id.isEmpty || id == Category.allId) ? '*' : id;

  Future<List<VodMovie>> _stalkerMoviesIn(String? categoryId) {
    final key = _portalCategory(categoryId);
    return _stalkerMovies[key] ??= _pages<VodMovie>(
      (page) => _stalker.vodPage(key, page: page),
    ).catchError((Object error) {
      _stalkerMovies.remove(key);
      throw error;
    });
  }

  Future<List<SeriesItem>> _stalkerSeriesIn(String? categoryId) {
    final key = _portalCategory(categoryId);
    return _stalkerSeries[key] ??= _pages<SeriesItem>(
      (page) => _stalker.seriesPage(key, page: page),
    ).catchError((Object error) {
      _stalkerSeries.remove(key);
      throw error;
    });
  }

  static Future<List<T>> _pages<T>(
    Future<StalkerPage<T>> Function(int page) fetch,
  ) async {
    final first = await fetch(1);
    if (!first.hasMore || first.perPage <= 0) return first.items;
    final total = (first.totalItems / first.perPage).ceil();
    final last = total < _stalkerPages ? total : _stalkerPages;
    final rest = await Future.wait([
      for (var page = 2; page <= last; page++)
        fetch(page).then(
          (p) => p.items,
          onError: (Object _) => <T>[],
        ),
    ]);
    return [...first.items, for (final items in rest) ...items];
  }

  // ── Compatibility surface used by the providers ────────────────────────────

  Future<List<Category>> liveCategories({bool forceRefresh = false}) async =>
      (await liveShelf(forceRefresh: forceRefresh)).categories;

  Future<List<LiveChannel>> liveStreams({
    String? categoryId,
    bool forceRefresh = false,
  }) async =>
      (await liveShelf(forceRefresh: forceRefresh)).inCategory(categoryId);

  Future<List<Category>> movieCategories({bool forceRefresh = false}) async {
    final shelf = await movieShelf(forceRefresh: forceRefresh);
    return _mode == SourceMode.stalker
        ? (_stalkerMovieCategories ?? const [])
        : shelf.categories;
  }

  Future<List<VodMovie>> movies({
    String? categoryId,
    bool forceRefresh = false,
  }) async {
    if (_mode == SourceMode.stalker) return _stalkerMoviesIn(categoryId);
    return (await movieShelf(forceRefresh: forceRefresh)).inCategory(
      categoryId,
    );
  }

  Future<List<Category>> seriesCategories({bool forceRefresh = false}) async {
    final shelf = await seriesShelf(forceRefresh: forceRefresh);
    return _mode == SourceMode.stalker
        ? (_stalkerSeriesCategories ?? const [])
        : shelf.categories;
  }

  Future<List<SeriesItem>> series({
    String? categoryId,
    bool forceRefresh = false,
  }) async {
    if (_mode == SourceMode.stalker) return _stalkerSeriesIn(categoryId);
    return (await seriesShelf(forceRefresh: forceRefresh)).inCategory(
      categoryId,
    );
  }

  /// Every section this session has loaded, fetched again from the source.
  Future<void> refreshAll() async {
    _guideMemo = null;
    if (_mode == SourceMode.stalker) {
      _stalkerMovies.clear();
      _stalkerSeries.clear();
    }
    if (_mode == SourceMode.m3u) {
      final library = await _m3uLibrary(forceRefresh: true);
      _adoptLibrary(library);
      for (final section in CatalogSection.values) {
        _announce(section);
      }
      return;
    }
    final loaded = _shelves.keys.toList();
    for (final section in loaded.isEmpty ? [CatalogSection.live] : loaded) {
      await _shelf(section, true);
      _announce(section);
    }
  }

  // ── Details ────────────────────────────────────────────────────────────────

  /// A film's plot, cast and backdrop — cached for a day.
  ///
  /// The film wall's preview pane asks for it whenever the cursor settles on a
  /// poster, so a user sweeping back and forth across a row of ten films would
  /// otherwise refetch ten plots, then refetch them again on the way back. A
  /// detail is the same detail tomorrow.
  Future<MovieDetail> movieInfo(VodMovie base) async {
    if (_mode == SourceMode.stalker) return _stalker.movieDetail(base);
    if (_mode != SourceMode.xtream || base.directUrl != null) {
      // A playlist carries no details beyond the entry itself.
      return MovieDetail(movie: base);
    }
    final name = 'vodinfo_${base.streamId}.json';
    final cached = await _readSmall(name, CacheTtl.info);
    if (cached != null) {
      try {
        return MovieDetail.fromXtream(
          jsonDecode(cached) as Map<String, dynamic>,
          base,
        );
      } on Object {
        // A corrupt entry is a cache miss, not a broken film.
      }
    }
    final raw = await _api.getVodInfoRaw(base.streamId);
    _writeSmall(name, jsonEncode(raw));
    return MovieDetail.fromXtream(raw, base);
  }

  Future<SeriesDetail> seriesInfo(SeriesItem base) async {
    if (_mode == SourceMode.stalker) {
      final portal = await _stalker.seriesDetail(base);
      final urls = portal.episodeUrls;
      return SeriesDetail(
        series: portal.detail.series,
        seasons: [
          for (final season in portal.detail.seasons)
            Season(
              number: season.number,
              name: season.name,
              cover: season.cover,
              episodes: [
                for (final e in season.episodes)
                  Episode(
                    id: e.id,
                    title: e.title,
                    episodeNum: e.episodeNum,
                    seasonNumber: e.seasonNumber,
                    containerExtension: e.containerExtension,
                    durationSecs: e.durationSecs,
                    plot: e.plot,
                    image: e.image,
                    rating: e.rating,
                    added: e.added,
                    directUrl: urls[e.id] ?? e.directUrl,
                  ),
              ],
            ),
        ],
      );
    }
    if (_mode == SourceMode.m3u || base.seriesId.startsWith('m3us_')) {
      final library = await _m3uLibrary();
      final episodes = library.episodes[base.seriesId] ?? const <Episode>[];
      final bySeason = <int, List<Episode>>{};
      for (final episode in episodes) {
        bySeason.putIfAbsent(episode.seasonNumber, () => []).add(episode);
      }
      final numbers = bySeason.keys.toList()..sort();
      return SeriesDetail(
        series: base,
        seasons: [
          for (final n in numbers) Season(number: n, episodes: bySeason[n]!),
        ],
      );
    }
    final name = 'seriesinfo_${base.seriesId}.json';
    final cached = await _readSmall(name, CacheTtl.info);
    if (cached != null) {
      try {
        return SeriesDetail.fromXtream(
          jsonDecode(cached) as Map<String, dynamic>,
          base,
        );
      } on Object {
        // Fall through to the panel.
      }
    }
    final raw = await _api.getSeriesInfoRaw(base.seriesId);
    _writeSmall(name, jsonEncode(raw));
    return SeriesDetail.fromXtream(raw, base);
  }

  Future<String?> _readSmall(String name, Duration ttl) async {
    final age = _files.age(_ns, name);
    if (age == null || age > ttl) return null;
    try {
      return await File(_files.path(_ns, name)).readAsString();
    } on Object {
      return null;
    }
  }

  void _writeSmall(String name, String text) {
    _files.write(_ns, name, utf8.encode(text));
  }

  // ── Account ────────────────────────────────────────────────────────────────

  XtreamAccountInfo? _account;

  /// The subscription behind an Xtream source — status, expiry, connections —
  /// or null for a source that has no account to describe.
  Future<XtreamAccountInfo?> accountInfo({bool forceRefresh = false}) async {
    if (_mode != SourceMode.xtream) return null;
    if (!forceRefresh && _account != null) return _account;
    try {
      _account = await _api.authenticate();
    } on Failure {
      return _account;
    }
    return _account;
  }

  // ── Guide ──────────────────────────────────────────────────────────────────

  /// The guide for one channel.
  ///
  /// The panel's own `get_short_epg` is asked first — a panel that implements it
  /// answers per-channel and answers fast. When it comes back empty (and there
  /// are panels where it *always* does, while `xmltv.php` returns thousands of
  /// programmes), the channel is looked up in the XMLTV guide instead.
  Future<List<EpgEntry>> epg(String streamId, {String? epgChannelId}) async {
    if (_mode == SourceMode.xtream && !streamId.startsWith('m3u_')) {
      final short = await _api.getShortEpg(streamId);
      if (short.isNotEmpty) return short;
    }
    if (epgChannelId == null || epgChannelId.trim().isEmpty) return const [];
    final guide = await this.guide();
    return guide.forChannel(epgChannelId);
  }

  EpgGuide? _guideMemo;
  Future<EpgGuide>? _guideLoad;

  /// The whole XMLTV guide, cached on disk and parsed off the UI isolate.
  Future<EpgGuide> guide({bool forceRefresh = false}) {
    if (!forceRefresh && _guideMemo != null) return Future.value(_guideMemo);
    return _guideLoad ??= _loadGuide(forceRefresh).whenComplete(() {
      _guideLoad = null;
    });
  }

  Future<String?> _guideUrl() async {
    switch (_mode) {
      case SourceMode.xtream:
        return _urls.xmltv().toString();
      case SourceMode.m3u:
        return (await _m3uLibrary()).guideUrl;
      case SourceMode.stalker:
        return null;
    }
  }

  Future<EpgGuide> _loadGuide(bool forceRefresh) async {
    final url = await _guideUrl();
    if (url == null) return _guideMemo = EpgGuide.empty;
    final job = GuideJob(url: url, cacheRoot: _files.root, namespace: _ns);
    if (!forceRefresh) {
      final cached = await _runCachedGuide(job);
      if (cached != null) {
        _guideMemo = cached.guide;
        if (DateTime.now().difference(cached.written) > CacheTtl.categories) {
          unawaited(
            _runFetchGuide(job)
                .then((fresh) => _guideMemo = fresh)
                .catchError((Object _) => cached.guide),
          );
        }
        return cached.guide;
      }
    }
    try {
      return _guideMemo = await _runFetchGuide(job);
    } on Failure catch (failure) {
      log.d('guide unavailable: ${failure.kind}');
      return _guideMemo = EpgGuide.empty;
    }
  }

  static Future<({EpgGuide guide, DateTime written})?> _runCachedGuide(
    GuideJob job,
  ) => _isolate(() => loadCachedGuide(job));

  static Future<EpgGuide> _runFetchGuide(GuideJob job) =>
      _isolate(() => fetchGuide(job));

  // ── Search ─────────────────────────────────────────────────────────────────

  /// Every section searched at once, on titles already folded for comparison
  /// when the sections were built — no decode, no rebuild, per keystroke.
  Future<CatalogSearch> search(String query) async {
    if (query.trim().isEmpty) {
      return (
        live: <LiveChannel>[],
        movies: <VodMovie>[],
        series: <SeriesItem>[],
      );
    }
    final live = await _safe(liveShelf);
    final movies = await _safe(movieShelf);
    final series = await _safe(seriesShelf);
    return (
      live: live?.search(query) ?? <LiveChannel>[],
      movies: movies?.search(query) ?? <VodMovie>[],
      series: series?.search(query) ?? <SeriesItem>[],
    );
  }

  Future<T?> _safe<T>(Future<T> Function({bool forceRefresh}) load) async {
    try {
      return await load();
    } on Object {
      return null;
    }
  }

  // ── Playback addresses ─────────────────────────────────────────────────────

  PlaybackTarget liveTarget(LiveChannel channel, {bool preferHls = true}) {
    final direct = channel.directUrl;
    if (direct != null && direct.isNotEmpty) return PlaybackTarget(direct);
    final hls = _urls.liveStream(channel.streamId, hls: true);
    final ts = _urls.liveStream(channel.streamId, hls: false);
    return preferHls
        ? PlaybackTarget(hls, alternatives: [ts])
        : PlaybackTarget(ts, alternatives: [hls]);
  }

  PlaybackTarget movieTarget(VodMovie movie) {
    final direct = movie.directUrl;
    if (direct != null && direct.isNotEmpty) return PlaybackTarget(direct);
    return PlaybackTarget(
      _urls.movieStream(movie.streamId, ext: movie.containerExtension ?? 'mp4'),
    );
  }

  PlaybackTarget episodeTarget(Episode episode) {
    final direct = episode.directUrl;
    if (direct != null && direct.isNotEmpty) return PlaybackTarget(direct);
    return PlaybackTarget(
      _urls.episodeStream(
        episode.id,
        ext: episode.containerExtension ?? 'mp4',
      ),
    );
  }

  /// The address to hand the player *now*. A portal's items carry an opaque
  /// `stalker://` command that becomes a real, one-time stream link only when
  /// it is asked for — so it is asked for on every open and every retry.
  Future<String> resolve(String url) async {
    if (!StalkerApi.isStalkerUrl(url)) return url;
    return _stalker.resolve(url);
  }

  String liveUrl(LiveChannel channel, {bool hls = true}) =>
      liveTarget(channel, preferHls: hls).url;

  String movieUrl(VodMovie movie) => movieTarget(movie).url;

  String episodeUrl(Episode episode) => episodeTarget(episode).url;

  void dispose() {
    _disposed = true;
    unawaited(_changes.close());
    _apiInstance?.close();
    _stalkerInstance?.close();
  }
}
