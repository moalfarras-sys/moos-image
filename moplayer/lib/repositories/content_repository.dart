import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter/services.dart';

import '../core/config/app_config.dart';
import '../core/constants/app_constants.dart';
import '../core/error/failures.dart';
import '../core/utils/app_logger.dart';
import '../models/category.dart';
import '../models/epg_entry.dart';
import '../models/live_channel.dart';
import '../models/playlist_config.dart';
import '../models/series.dart';
import '../models/vod_movie.dart';
import '../services/cache/cache_service.dart';
import '../services/m3u/m3u_parser.dart';
import '../services/xtream/xtream_api.dart';
import '../services/xtream/xtream_url_builder.dart';

/// Unified content access for the active playlist. For Xtream it talks to the
/// panel; for M3U it parses the playlist once and serves everything from the
/// in-memory + on-disk cache. All methods throw a typed [Failure] on error
/// (after falling back to any stale cache when possible).
class ContentRepository {
  ContentRepository({
    required this.config,
    required CacheService cache,
    XtreamApi? api,
  }) : _cache = cache,
       _api = config.isXtream ? (api ?? XtreamApi(config)) : null,
       _urls = XtreamUrlBuilder(config);

  final PlaylistConfig config;
  final CacheService _cache;
  final XtreamApi? _api;
  final XtreamUrlBuilder _urls;

  M3uResult? _m3uMemo;

  String get _ns => config.id; // cache namespace per playlist

  bool get supportsVod => config.isXtream;
  bool get supportsSeries => config.isXtream;

  // --- Live ----------------------------------------------------------------

  Future<List<Category>> liveCategories({bool forceRefresh = false}) async {
    if (config.isXtream) {
      return _xtreamCategories(
        'live_cats',
        () => _api!.getLiveCategories(),
        forceRefresh: forceRefresh,
      );
    }
    final m3u = await _loadM3u(forceRefresh: forceRefresh);
    return m3u.categories;
  }

  Future<List<LiveChannel>> liveStreams({
    String? categoryId,
    bool forceRefresh = false,
  }) async {
    if (config.isXtream) {
      final all = await _xtreamLive(
        categoryId: categoryId,
        forceRefresh: forceRefresh,
      );
      return _filterByCategory(all, categoryId, (c) => c.categoryId);
    }
    final m3u = await _loadM3u(forceRefresh: forceRefresh);
    return _filterByCategory(m3u.channels, categoryId, (c) => c.categoryId);
  }

  Future<List<EpgEntry>> epg(String streamId) async {
    final api = _api;
    if (api == null) return const [];
    return api.getShortEpg(streamId);
  }

  // --- Movies --------------------------------------------------------------

  Future<List<Category>> movieCategories({bool forceRefresh = false}) async {
    if (!supportsVod) return const [];
    return _xtreamCategories(
      'vod_cats',
      () => _api!.getVodCategories(),
      forceRefresh: forceRefresh,
    );
  }

  Future<List<VodMovie>> movies({
    String? categoryId,
    bool forceRefresh = false,
  }) async {
    if (!supportsVod) return const [];
    final all = await _xtreamMovies(
      categoryId: categoryId,
      forceRefresh: forceRefresh,
    );
    return _filterByCategory(all, categoryId, (m) => m.categoryId);
  }

  Future<MovieDetail> movieInfo(VodMovie base) {
    final api = _api;
    if (api == null) throw Failure.notConfigured();
    return api.getVodInfo(base);
  }

  // --- Series --------------------------------------------------------------

  Future<List<Category>> seriesCategories({bool forceRefresh = false}) async {
    if (!supportsSeries) return const [];
    return _xtreamCategories(
      'series_cats',
      () => _api!.getSeriesCategories(),
      forceRefresh: forceRefresh,
    );
  }

  Future<List<SeriesItem>> series({
    String? categoryId,
    bool forceRefresh = false,
  }) async {
    if (!supportsSeries) return const [];
    final all = await _xtreamSeries(
      categoryId: categoryId,
      forceRefresh: forceRefresh,
    );
    return _filterByCategory(all, categoryId, (s) => s.categoryId);
  }

  Future<SeriesDetail> seriesInfo(SeriesItem base) {
    final api = _api;
    if (api == null) throw Failure.notConfigured();
    return api.getSeriesInfo(base);
  }

  // --- Search --------------------------------------------------------------

  Future<
    ({List<LiveChannel> live, List<VodMovie> movies, List<SeriesItem> series})
  >
  search(String query) async {
    final q = query.trim().toLowerCase();
    if (q.isEmpty) {
      return (
        live: <LiveChannel>[],
        movies: <VodMovie>[],
        series: <SeriesItem>[],
      );
    }
    final live = await _safeAll(() => liveStreams());
    final mv = supportsVod
        ? await _safeAll(() => _xtreamMovies())
        : <VodMovie>[];
    final sr = supportsSeries
        ? await _safeAll(() => _xtreamSeries())
        : <SeriesItem>[];

    bool match(String name) => name.toLowerCase().contains(q);
    return (
      live: live.where((c) => match(c.name)).take(120).toList(),
      movies: mv.where((m) => match(m.name)).take(120).toList(),
      series: sr.where((s) => match(s.name)).take(120).toList(),
    );
  }

  Future<List<T>> _safeAll<T>(Future<List<T>> Function() fn) async {
    try {
      return await fn();
    } catch (_) {
      return <T>[];
    }
  }

  // --- URL builders --------------------------------------------------------

  String liveUrl(LiveChannel channel, {bool hls = true}) {
    if (channel.directUrl != null && channel.directUrl!.isNotEmpty) {
      return channel.directUrl!;
    }
    return _urls.liveStream(channel.streamId, hls: hls);
  }

  String movieUrl(VodMovie movie) {
    if (movie.directUrl != null && movie.directUrl!.isNotEmpty) {
      return movie.directUrl!;
    }
    return _urls.movieStream(
      movie.streamId,
      ext: movie.containerExtension ?? 'mp4',
    );
  }

  String episodeUrl(Episode episode) =>
      _urls.episodeStream(episode.id, ext: episode.containerExtension ?? 'mp4');

  // --- Internals -----------------------------------------------------------

  Future<List<Category>> _xtreamCategories(
    String key,
    Future<List<Category>> Function() fetch, {
    required bool forceRefresh,
  }) async {
    final cacheKey = '${_ns}_$key';
    if (!forceRefresh) {
      final cached = _cache.getList(cacheKey, ttl: CacheTtl.categories);
      if (cached != null) {
        return cached.map((e) => Category.fromXtream(e)).toList();
      }
    }
    try {
      final fresh = await fetch();
      await _cache.putList(
        cacheKey,
        fresh
            .map((c) => {'category_id': c.id, 'category_name': c.name})
            .toList(),
      );
      return fresh;
    } on Failure {
      final stale = _cache.getList(cacheKey);
      if (stale != null) {
        return stale.map((e) => Category.fromXtream(e)).toList();
      }
      rethrow;
    }
  }

  Future<List<LiveChannel>> _xtreamLive({
    String? categoryId,
    required bool forceRefresh,
  }) async {
    final scopedCategory = _scopedCategoryId(categoryId);
    final cacheKey = '${_ns}_live_$scopedCategory';
    if (!forceRefresh) {
      final cached = _cache.getList(cacheKey, ttl: CacheTtl.streams);
      if (cached != null) {
        return cached.map((e) => LiveChannel.fromXtream(e)).toList();
      }
    }
    try {
      final fresh = await _api!.getLiveStreams(categoryId: categoryId);
      await _cache.putList(cacheKey, fresh.map(_liveToRow).toList());
      return fresh;
    } on Failure {
      final stale = _cache.getList(cacheKey);
      if (stale != null) {
        return stale.map((e) => LiveChannel.fromXtream(e)).toList();
      }
      rethrow;
    }
  }

  Future<List<VodMovie>> _xtreamMovies({
    String? categoryId,
    bool forceRefresh = false,
  }) async {
    final scopedCategory = _scopedCategoryId(categoryId);
    final cacheKey = '${_ns}_vod_$scopedCategory';
    if (!forceRefresh) {
      final cached = _cache.getList(cacheKey, ttl: CacheTtl.streams);
      if (cached != null) {
        return cached.map((e) => VodMovie.fromXtream(e)).toList();
      }
    }
    try {
      final fresh = await _api!.getVodStreams(categoryId: categoryId);
      await _cache.putList(cacheKey, fresh.map(_movieToRow).toList());
      return fresh;
    } on Failure {
      final stale = _cache.getList(cacheKey);
      if (stale != null) {
        return stale.map((e) => VodMovie.fromXtream(e)).toList();
      }
      rethrow;
    }
  }

  Future<List<SeriesItem>> _xtreamSeries({
    String? categoryId,
    bool forceRefresh = false,
  }) async {
    final scopedCategory = _scopedCategoryId(categoryId);
    final cacheKey = '${_ns}_series_$scopedCategory';
    if (!forceRefresh) {
      final cached = _cache.getList(cacheKey, ttl: CacheTtl.streams);
      if (cached != null) {
        return cached.map((e) => SeriesItem.fromXtream(e)).toList();
      }
    }
    try {
      final fresh = await _api!.getSeries(categoryId: categoryId);
      await _cache.putList(cacheKey, fresh.map(_seriesToRow).toList());
      return fresh;
    } on Failure {
      final stale = _cache.getList(cacheKey);
      if (stale != null) {
        return stale.map((e) => SeriesItem.fromXtream(e)).toList();
      }
      rethrow;
    }
  }

  Future<M3uResult> _loadM3u({bool forceRefresh = false}) async {
    if (_m3uMemo != null && !forceRefresh) return _m3uMemo!;
    final cacheKey = '${_ns}_m3u_channels';

    if (!forceRefresh) {
      final cached = _cache.getList(cacheKey, ttl: CacheTtl.streams);
      if (cached != null) {
        final channels = cached.map((e) => LiveChannel.fromPayload(e)).toList();
        _m3uMemo = M3uResult(
          channels: channels,
          categories: _deriveCategories(channels),
        );
        return _m3uMemo!;
      }
    }

    final dio = Dio(
      BaseOptions(
        connectTimeout: AppConfig.connectTimeout,
        receiveTimeout: AppConfig.receiveTimeout,
        responseType: ResponseType.plain,
        headers: const {'User-Agent': 'MoPlayerPro/1.0'},
      ),
    );
    try {
      final body = await _readM3uBody(config.m3uUrl.trim(), dio);
      final parsed = M3uParser.parse(body);
      _m3uMemo = parsed;
      await _cache.putList(
        cacheKey,
        parsed.channels.map((c) => c.toPayload()).toList(),
      );
      return parsed;
    } on DioException catch (e) {
      final stale = _cache.getList(cacheKey);
      if (stale != null) {
        final channels = stale.map((e) => LiveChannel.fromPayload(e)).toList();
        _m3uMemo = M3uResult(
          channels: channels,
          categories: _deriveCategories(channels),
        );
        return _m3uMemo!;
      }
      log.e('M3U load failed', error: e);
      if (e.type == DioExceptionType.connectionTimeout ||
          e.type == DioExceptionType.receiveTimeout) {
        throw Failure.timeout();
      }
      throw Failure.network('Could not download the playlist.');
    } finally {
      dio.close(force: true);
    }
  }

  Future<String> _readM3uBody(String url, Dio dio) async {
    if (url.startsWith('asset://')) {
      final asset = 'assets/${url.substring('asset://'.length)}';
      return rootBundle.loadString(asset);
    }
    // See AuthRepository._readM3uBody: a playlist can be a file on disk, opened
    // from the file manager.
    if (url.startsWith('file://') || url.startsWith('/')) {
      return File(Uri.parse(url).toFilePath()).readAsString();
    }
    final res = await dio.get<String>(url);
    return res.data ?? '';
  }

  List<Category> _deriveCategories(List<LiveChannel> channels) {
    final order = <String>[];
    final counts = <String, int>{};
    for (final c in channels) {
      final g = c.categoryId ?? 'Uncategorized';
      if (!counts.containsKey(g)) order.add(g);
      counts[g] = (counts[g] ?? 0) + 1;
    }
    return [for (final g in order) Category(id: g, name: g, count: counts[g])];
  }

  List<T> _filterByCategory<T>(
    List<T> all,
    String? categoryId,
    String? Function(T) selector,
  ) {
    if (categoryId == null ||
        categoryId.isEmpty ||
        categoryId == Category.allId) {
      return all;
    }
    return all.where((e) => selector(e) == categoryId).toList();
  }

  String _scopedCategoryId(String? categoryId) {
    if (categoryId == null ||
        categoryId.isEmpty ||
        categoryId == Category.allId) {
      return 'all';
    }
    return categoryId.replaceAll(RegExp(r'[^a-zA-Z0-9_-]'), '_');
  }

  Map<String, dynamic> _liveToRow(LiveChannel c) => {
    'stream_id': c.streamId,
    'name': c.name,
    'stream_icon': c.logo,
    'category_id': c.categoryId,
    'epg_channel_id': c.epgChannelId,
    'num': c.number,
    'container_extension': c.containerExtension,
  };

  Map<String, dynamic> _movieToRow(VodMovie m) => {
    'stream_id': m.streamId,
    'name': m.name,
    'stream_icon': m.poster,
    'category_id': m.categoryId,
    'rating': m.rating,
    'year': m.year,
    'added': m.added?.millisecondsSinceEpoch == null
        ? null
        : (m.added!.millisecondsSinceEpoch ~/ 1000).toString(),
    'container_extension': m.containerExtension,
  };

  Map<String, dynamic> _seriesToRow(SeriesItem s) => {
    'series_id': s.seriesId,
    'name': s.name,
    'cover': s.cover,
    'category_id': s.categoryId,
    'rating': s.rating,
    'plot': s.plot,
    'genre': s.genre,
    'releaseDate': s.releaseDate,
    'last_modified': s.lastModified?.millisecondsSinceEpoch == null
        ? null
        : (s.lastModified!.millisecondsSinceEpoch ~/ 1000).toString(),
    'backdrop_path': s.backdrop == null ? null : [s.backdrop],
  };

  void dispose() => _api?.close();
}
