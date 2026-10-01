import 'dart:async';
import 'dart:convert';

import 'package:dio/dio.dart';

import '../../core/config/app_config.dart';
import '../../core/error/failures.dart';
import '../../core/utils/app_logger.dart';
import '../../core/utils/json_x.dart';
import '../../models/category.dart';
import '../../models/live_channel.dart';
import '../../models/series.dart';
import '../../models/vod_movie.dart';
import 'stalker_identity.dart';
import 'stalker_models.dart';
import 'stalker_portal_address.dart';

export 'stalker_models.dart';

/// A client for MAC-address ("Stalker" / Ministra, MAG-style) IPTV portals.
///
/// The portal authenticates a *device*, not a user: the MAC address travels in
/// a cookie, a handshake returns a bearer token, and `get_profile` activates
/// that token for the MAC. Everything after that is
/// `GET <endpoint>?type=…&action=…` answering `{"js": …}`.
///
/// Like `XtreamApi`, every transport problem becomes a typed [Failure], a
/// transient timeout is retried once, and response shapes are read leniently:
/// resold panels mislabel content types, prepend byte-order marks and PHP
/// notices, and send `js` as an object, a list, `false` or a string.
///
/// ## The play-link contract
///
/// A portal stream has no stable URL: the `cmd` a list returns must be turned
/// into a short-lived address by `create_link` at play time. Items produced
/// here therefore carry an opaque `stalker://` link in `directUrl` (see
/// [isStalkerUrl]); the player hands it to [resolve] just before opening it.
///
/// * live — `stalker://itv?cmd=<cmd>`
/// * movie — `stalker://vod?cmd=<cmd>`
/// * episode — `stalker://vod?cmd=<cmd>&series=<n>` when a series is one
///   `cmd` plus episode numbers, `stalker://vod?cmd=<episode cmd>` when every
///   episode has its own, or (only when a portal lists an episode without a
///   `cmd`) `stalker://vod?module=…&movie_id=…&season_id=…&episode_id=…`,
///   whose file is looked up at play time.
///
/// Ids carry a `stk_` / `stkv_` / `stks_` / `stke_` prefix so a portal item
/// can never collide with an Xtream id in favourites or history.
///
/// Nothing here logs the MAC address, the token, or a URL.
class StalkerApi {
  StalkerApi({
    required String portalUrl,
    required String macAddress,
    Dio? dio,
    String? timezone,
  }) : _address = StalkerPortalAddress.parse(portalUrl),
       _identity = StalkerIdentity.fromMac(macAddress),
       _timezone = (timezone == null || timezone.trim().isEmpty)
           ? defaultTimezone
           : timezone.trim(),
       _dio =
           dio ??
           Dio(
             BaseOptions(
               connectTimeout: AppConfig.connectTimeout,
               receiveTimeout: AppConfig.receiveTimeout,
             ),
           );

  static const String defaultTimezone = 'Europe/Berlin';

  /// What a MAG250's built-in browser sends. Portals check it; several refuse
  /// anything that does not look like a set-top box.
  static const String userAgent =
      'Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 '
      '(KHTML, like Gecko) MAG200 stbapp ver: 2 rev: 250 Safari/533.3';
  static const String xUserAgent = 'Model: MAG250; Link: WiFi';

  static const String _livePrefix = 'stk_';
  static const String _moviePrefix = 'stkv_';
  static const String _seriesPrefix = 'stks_';
  static const String _episodePrefix = 'stke_';

  /// Pagination is a fallback path; this bounds a portal that ignores `p`.
  static const int _maxChannelPages = 500;
  static const int _maxSeriesPages = 20;

  /// True for the opaque play links this client puts in `directUrl`.
  static bool isStalkerUrl(String url) =>
      url.trimLeft().toLowerCase().startsWith('stalker://');

  /// True for ids minted by this client (channels, movies, series, episodes).
  static bool isStalkerId(String id) =>
      id.startsWith(_livePrefix) ||
      id.startsWith(_moviePrefix) ||
      id.startsWith(_seriesPrefix) ||
      id.startsWith(_episodePrefix);

  final StalkerPortalAddress? _address;
  final StalkerIdentity? _identity;
  final String _timezone;
  final Dio _dio;

  Uri? _endpoint;
  String? _token;
  String? _random;
  bool _ready = false;
  int _generation = 0;
  Future<StalkerAccount>? _inflight;
  StalkerAccount? _account;

  /// null until probed; false when the portal has no `type=series` module and
  /// series are the `is_series` entries of the VOD list.
  bool? _seriesModule;
  final Map<String, _SeriesSource> _seriesSources = {};
  final Map<String, MovieDetail> _movieDetails = {};

  /// The API file that answered the handshake, once connected.
  Uri? get endpoint => _endpoint;

  /// The account read by the last successful [connect].
  StalkerAccount? get account => _account;

  // --- Session -------------------------------------------------------------

  /// Handshake, then `get_profile`, then (best effort) `account_info`.
  ///
  /// Throws [Failure.auth] for an invalid, unknown or blocked MAC, and
  /// [Failure.network] / [Failure.timeout] when the portal cannot be reached.
  /// Concurrent callers share one handshake. Every other method connects on
  /// first use, so calling this first is optional.
  Future<StalkerAccount> connect() {
    return _inflight ??= _openSession().whenComplete(() => _inflight = null);
  }

  Future<StalkerAccount> _openSession() async {
    if (_identity == null) {
      throw Failure.auth(
        'The MAC address is not valid. It needs 12 hexadecimal digits, '
        'like 00:1A:79:12:34:56.',
      );
    }
    if (_address == null) {
      throw Failure.network('The portal address is not a valid web address.');
    }
    _ready = false;
    Map<String, dynamic>? profile;
    // A token the portal does not activate (js == false / 401) gets exactly
    // one fresh handshake — the same rule every later call follows.
    for (var attempt = 0; attempt < 2 && profile == null; attempt++) {
      await _handshake();
      profile = await _profile();
    }
    if (profile == null) {
      throw Failure.auth(
        'The portal did not accept this device. Check the MAC address.',
      );
    }
    _checkBlocked(profile);
    final info = await _accountInfo();
    final account = _accountFrom(profile, info);
    _account = account;
    _ready = true;
    _generation++;
    log.i('Stalker portal connected via $_endpointKind');
    return account;
  }

  Future<void> _handshake() async {
    final known = _endpoint;
    final candidates = known != null ? [known] : _address!.candidates;
    var refused = false;
    for (final candidate in candidates) {
      // A network or timeout failure propagates: every candidate is on the
      // same host, so the next path would only wait out the same timeout.
      final reply = await _send(candidate, const {
        'type': 'stb',
        'action': 'handshake',
        'token': '',
        'prehash': '0',
      });
      if (reply.isRefusal) {
        refused = true;
        continue;
      }
      if (!reply.isOk) continue;
      final envelope = _envelope(reply.body);
      // An HTML page or an unrelated JSON API: not the portal, try the next.
      if (envelope == null || !envelope.hasJs) continue;
      final js = envelope.js;
      final token = js is Map ? JsonX.asStringOrNull(js['token']) : null;
      if (token == null) {
        throw Failure.auth(
          'The portal refused the handshake for this MAC address.',
        );
      }
      _endpoint = candidate;
      _token = token;
      _random = js is Map ? JsonX.asStringOrNull(js['random']) : null;
      return;
    }
    if (refused) {
      throw Failure.auth(
        'The portal refused this device. Check the MAC address and the '
        'portal address.',
      );
    }
    throw Failure.server(
      'No MAC portal answered at this address. Check the portal address.',
    );
  }

  /// null means "token not accepted" (401/403, `Authorization failed.`, or
  /// `js` that is not a profile object).
  Future<Map<String, dynamic>?> _profile() async {
    final identity = _identity!;
    final now = DateTime.now().millisecondsSinceEpoch ~/ 1000;
    final reply = await _send(_endpoint!, {
      'type': 'stb',
      'action': 'get_profile',
      'hd': '1',
      'ver':
          'ImageDescription: 0.2.18-r23-250; ImageDate: Wed Aug 29 10:49:53 '
          'EEST 2018; PORTAL version: 5.6.2; API Version: JS API version: '
          '343; STB API version: 146; Player Engine version: 0x58c',
      'num_banks': '2',
      'sn': identity.serialNumber,
      'stb_type': 'MAG250',
      'image_version': '218',
      'video_out': 'hdmi',
      'device_id': identity.deviceId,
      'device_id2': identity.deviceId2,
      'signature': identity.signature,
      'auth_second_step': '1',
      'hw_version': '1.7-BD-00',
      'not_valid_token': '0',
      'metrics': jsonEncode({
        'mac': identity.mac,
        'sn': identity.serialNumber,
        'type': 'STB',
        'model': 'MAG250',
        'uid': identity.deviceId,
        'random': _random ?? '',
      }),
      'hw_version_2': identity.hwVersion2,
      'timestamp': '$now',
      'api_signature': '262',
      'prehash': '',
    }, token: _token);
    if (reply.isRefusal) return null;
    final js = _decode(reply);
    return js is Map ? Map<String, dynamic>.from(js) : null;
  }

  void _checkBlocked(Map<String, dynamic> profile) {
    final status = JsonX.asInt(profile['status']);
    final blockMsg = _plainText(profile['block_msg']);
    if (status == 0 && blockMsg == null) return;
    throw Failure.auth(
      blockMsg ??
          _plainText(profile['msg']) ??
          'This MAC address is not registered on the portal, or its '
              'subscription is blocked.',
    );
  }

  Future<Map<String, dynamic>> _accountInfo() async {
    try {
      final reply = await _send(_endpoint!, const {
        'type': 'account_info',
        'action': 'get_main_info',
      }, token: _token);
      if (!reply.isOk || reply.isRefusal) return const {};
      final js = _decode(reply);
      return js is Map ? Map<String, dynamic>.from(js) : const {};
    } on Failure catch (e) {
      log.d('Stalker account info unavailable (${e.kind.name})');
      return const {};
    }
  }

  StalkerAccount _accountFrom(
    Map<String, dynamic> profile,
    Map<String, dynamic> info,
  ) {
    String? pick(List<String> keys) {
      for (final source in [info, profile]) {
        for (final key in keys) {
          final value = JsonX.asStringOrNull(source[key]);
          if (value != null) return value;
        }
      }
      return null;
    }

    DateTime? expires;
    for (final key in const [
      'end_date',
      'expire_billing_date',
      'expire_date',
      'exp_date',
    ]) {
      expires ??= _parseDate(info[key]) ?? _parseDate(profile[key]);
    }
    // Xtream-based MAC panels put the expiry text in account_info's `phone`
    // ("December 31, 2026, 11:59 pm"). A real phone number is digits only,
    // which is why numbers are not read as timestamps here.
    expires ??= _parseDate(info['phone'], allowNumeric: false);

    final portalStatus = JsonX.asStringOrNull(info['status']);
    final String status;
    if (portalStatus != null && int.tryParse(portalStatus) == null) {
      status = portalStatus;
    } else if (expires != null && expires.isBefore(DateTime.now())) {
      status = 'Expired';
    } else {
      status = 'Active';
    }
    return StalkerAccount(
      login: pick(const ['login', 'fname']),
      status: status,
      expiresAt: expires,
      tariff: pick(const ['tariff_plan', 'tariff_plan_name', 'tariff']),
      balance: pick(const ['account_balance', 'balance']),
    );
  }

  Future<void> _ensureSession() async {
    final pending = _inflight;
    if (pending != null) {
      await pending;
      return;
    }
    if (!_ready) await connect();
  }

  /// Re-handshakes unless another caller already did since [seenGeneration].
  Future<void> _renew(int seenGeneration) async {
    final pending = _inflight;
    if (pending != null) {
      await pending;
      return;
    }
    if (_generation != seenGeneration) return;
    log.i('Stalker token refused; handshaking again');
    await connect();
  }

  /// A session-managed API call: connects on first use and re-handshakes
  /// once when the portal refuses the token.
  Future<dynamic> _call(Map<String, String> params) async {
    await _ensureSession();
    var renewed = false;
    while (true) {
      final generation = _generation;
      final reply = await _send(_endpoint!, params, token: _token);
      if (reply.isRefusal) {
        if (renewed) {
          throw Failure.auth(
            'The portal stopped accepting this device. Reconnect the source.',
          );
        }
        renewed = true;
        await _renew(generation);
        continue;
      }
      return _decode(reply);
    }
  }

  // --- Live ----------------------------------------------------------------

  /// `itv/get_genres`, without the portal's own "All" (`*`) genre.
  Future<List<Category>> liveGenres() async =>
      _categories(await _call(const {'type': 'itv', 'action': 'get_genres'}));

  /// Every channel. `get_all_channels` answers in one request on most
  /// portals; when it is empty or unreadable the paginated `get_ordered_list`
  /// is walked instead.
  Future<List<LiveChannel>> liveChannels() async {
    var raw = const <Map<String, dynamic>>[];
    try {
      raw = _items(
        await _call(const {'type': 'itv', 'action': 'get_all_channels'}),
      );
    } on Failure catch (e) {
      if (!_isContentFailure(e)) rethrow;
      log.d('Stalker get_all_channels unusable (${e.kind.name}); paging');
    }
    if (raw.isEmpty) {
      raw = await _allPages(const {
        'type': 'itv',
        'action': 'get_ordered_list',
        'genre': '*',
        'force_ch_link_check': '',
        'fav': '0',
        'sortby': 'number',
        'hd': '0',
      }, maxPages: _maxChannelPages);
    }
    final seen = <String>{};
    final channels = <LiveChannel>[];
    for (final item in raw) {
      final channel = _channel(item);
      if (channel != null && seen.add(channel.streamId)) channels.add(channel);
    }
    return channels;
  }

  LiveChannel? _channel(Map<String, dynamic> item) {
    final id = JsonX.asStringOrNull(item['id']);
    final cmd = _cmdOf(item);
    if (id == null || cmd == null) return null;
    return LiveChannel(
      streamId: '$_livePrefix$id',
      name: JsonX.asStringOrNull(item['name']) ?? id,
      logo: _absoluteUrl(item['logo'], bareFileDir: '/misc/logos/320/'),
      categoryId: JsonX.asStringOrNull(item['tv_genre_id']),
      epgChannelId: JsonX.asStringOrNull(item['xmltv_id']),
      number: JsonX.asIntOrNull(item['number']),
      directUrl: _link('itv', cmd),
      tvArchive: JsonX.asBool(item['tv_archive']),
    );
  }

  // --- VOD -----------------------------------------------------------------

  Future<List<Category>> vodCategories() async => _categories(
    await _call(const {'type': 'vod', 'action': 'get_categories'}),
  );

  /// One page of movies. Series the portal mixes into the VOD list
  /// (`is_series`) are left out — they are served by [seriesPage].
  Future<StalkerPage<VodMovie>> vodPage(
    String categoryId, {
    int page = 1,
  }) async {
    final p = page < 1 ? 1 : page;
    final data = _pageData(await _call(_listParams('vod', categoryId, p)), p);
    final movies = <VodMovie>[];
    for (final item in data.items) {
      if (JsonX.asBool(item['is_series'])) continue;
      final movie = _movie(item);
      if (movie != null) movies.add(movie);
    }
    return StalkerPage(
      items: movies,
      page: p,
      totalItems: data.total,
      perPage: data.perPage,
    );
  }

  /// The metadata a movie's list entry carried (plot, cast, director, genre,
  /// running time). Portals have no separate detail call, so this is served
  /// from what [vodPage] already read; an unseen movie gets a bare detail.
  MovieDetail movieDetail(VodMovie movie) =>
      _movieDetails[movie.streamId] ?? MovieDetail(movie: movie);

  VodMovie? _movie(Map<String, dynamic> item) {
    final id = JsonX.asStringOrNull(item['id']);
    final cmd = _cmdOf(item);
    if (id == null || cmd == null) return null;
    final movie = VodMovie(
      streamId: '$_moviePrefix$id',
      name:
          JsonX.asStringOrNull(item['name']) ??
          JsonX.asStringOrNull(item['o_name']) ??
          id,
      poster: _poster(item),
      categoryId: JsonX.asStringOrNull(item['category_id']),
      rating: _rating(item),
      year: _year(item['year']),
      added: _parseDate(item['added']),
      directUrl: _link('vod', cmd),
    );
    _movieDetails[movie.streamId] = MovieDetail(
      movie: movie,
      plot: _plainText(item['description']),
      cast: JsonX.asStringOrNull(item['actors']),
      director: JsonX.asStringOrNull(item['director']),
      genre: JsonX.asStringOrNull(item['genres_str']),
      releaseDate: JsonX.asStringOrNull(item['year']),
      durationSecs: _durationSecs(item['time']),
      country: JsonX.asStringOrNull(item['country']),
    );
    return movie;
  }

  // --- Series --------------------------------------------------------------

  /// `series/get_categories`; a portal without a series module gets its VOD
  /// categories instead, and [seriesPage] then returns their `is_series`
  /// entries.
  Future<List<Category>> seriesCategories() async =>
      await _seriesModuleCategories() ?? await vodCategories();

  Future<StalkerPage<SeriesItem>> seriesPage(
    String categoryId, {
    int page = 1,
  }) async {
    final p = page < 1 ? 1 : page;
    final module = await _seriesModuleName();
    final data = _pageData(await _call(_listParams(module, categoryId, p)), p);
    final series = <SeriesItem>[];
    for (final item in data.items) {
      if (module == 'vod' && !JsonX.asBool(item['is_series'])) continue;
      final entry = _series(item, module);
      if (entry != null) series.add(entry);
    }
    return StalkerPage(
      items: series,
      page: p,
      totalItems: data.total,
      perPage: data.perPage,
    );
  }

  /// Seasons, episodes and each episode's play link.
  ///
  /// Two portal shapes exist. The classic one lists a series as a single
  /// `cmd` plus `series: [1, 2, 3…]` episode numbers and needs no further
  /// request. The modern one is walked with `get_ordered_list`:
  /// `movie_id=<series>` lists seasons, `season_id=<season>` lists episodes.
  /// A season that itself carries `series: […]` and a `cmd` (Xtream-based
  /// panels) is expanded like the classic shape.
  Future<StalkerSeriesDetail> seriesDetail(SeriesItem series) async {
    final source =
        _seriesSources[series.seriesId] ??
        _SeriesSource(
          rawId: series.seriesId.startsWith(_seriesPrefix)
              ? series.seriesId.substring(_seriesPrefix.length)
              : series.seriesId,
          module: await _seriesModuleName(),
        );
    final urls = <String, String>{};
    final List<Season> seasons;
    final cmd = source.cmd;
    if (cmd != null && source.episodes.isNotEmpty) {
      seasons = [
        _numberedSeason(
          source,
          seasonNo: 1,
          cmd: cmd,
          numbers: source.episodes,
          title: series.name,
          urls: urls,
        ),
      ];
    } else {
      seasons = await _walkSeasons(source, series.name, urls);
    }
    return StalkerSeriesDetail(
      detail: SeriesDetail(series: series, seasons: seasons),
      episodeUrls: urls,
    );
  }

  Future<List<Category>?> _seriesModuleCategories() async {
    if (_seriesModule == false) return null;
    List<Category>? categories;
    try {
      categories = _categories(
        await _call(const {'type': 'series', 'action': 'get_categories'}),
      );
    } on Failure catch (e) {
      if (!_isContentFailure(e)) rethrow;
    }
    if (categories != null && categories.isNotEmpty) {
      _seriesModule = true;
      return categories;
    }
    _seriesModule = false;
    log.i('Stalker portal has no series module; using VOD series');
    return null;
  }

  Future<String> _seriesModuleName() async {
    if (_seriesModule == null) await _seriesModuleCategories();
    return _seriesModule == true ? 'series' : 'vod';
  }

  SeriesItem? _series(Map<String, dynamic> item, String module) {
    final id = JsonX.asStringOrNull(item['id']);
    if (id == null) return null;
    final seriesId = '$_seriesPrefix$id';
    _seriesSources[seriesId] = _SeriesSource(
      rawId: id,
      module: module,
      cmd: _cmdOf(item),
      episodes: _numbers(item['series']),
    );
    return SeriesItem(
      seriesId: seriesId,
      name:
          JsonX.asStringOrNull(item['name']) ??
          JsonX.asStringOrNull(item['o_name']) ??
          id,
      cover: _poster(item),
      categoryId: JsonX.asStringOrNull(item['category_id']),
      rating: _rating(item),
      plot: _plainText(item['description']),
      genre: JsonX.asStringOrNull(item['genres_str']),
      releaseDate: _year(item['year']) ?? JsonX.asStringOrNull(item['year']),
      lastModified: _parseDate(item['added']),
    );
  }

  Future<List<Season>> _walkSeasons(
    _SeriesSource source,
    String title,
    Map<String, String> urls,
  ) async {
    final base = {
      'type': source.module,
      'action': 'get_ordered_list',
      'movie_id': source.rawId,
    };
    final top = await _allPages({
      ...base,
      'season_id': '0',
      'episode_id': '0',
    }, maxPages: _maxSeriesPages);

    final seasons = <Season>[];
    final used = <int>{};
    final loose = <Episode>[];
    for (var i = 0; i < top.length; i++) {
      final item = top[i];
      if (JsonX.asBool(item['is_episode'])) {
        loose.add(
          _episode(
            item,
            source,
            seasonNo: 1,
            seasonId: '0',
            index: loose.length,
            title: title,
            urls: urls,
          ),
        );
        continue;
      }
      final number = _claim(_seasonNumber(item) ?? i + 1, used);
      final name = JsonX.asStringOrNull(item['name']);
      final cover = _poster(item);
      final cmd = _cmdOf(item);
      final numbers = _numbers(item['series']);
      if (cmd != null && numbers.isNotEmpty) {
        seasons.add(
          _numberedSeason(
            source,
            seasonNo: number,
            cmd: cmd,
            numbers: numbers,
            title: title,
            urls: urls,
            name: name,
            cover: cover,
          ),
        );
        continue;
      }
      final seasonId = JsonX.asStringOrNull(item['id']) ?? '$number';
      final children = await _allPages({
        ...base,
        'season_id': seasonId,
        'episode_id': '0',
      }, maxPages: _maxSeriesPages);
      final episodes = <Episode>[
        for (var j = 0; j < children.length; j++)
          _episode(
            children[j],
            source,
            seasonNo: number,
            seasonId: seasonId,
            index: j,
            title: title,
            urls: urls,
          ),
      ];
      if (episodes.isEmpty && cmd != null) {
        // A "season" with no children and its own cmd is a playable item.
        episodes.add(
          _episode(
            item,
            source,
            seasonNo: number,
            seasonId: seasonId,
            index: 0,
            title: title,
            urls: urls,
          ),
        );
      }
      if (episodes.isEmpty) continue;
      episodes.sort((a, b) => a.episodeNum.compareTo(b.episodeNum));
      seasons.add(
        Season(number: number, episodes: episodes, name: name, cover: cover),
      );
    }
    if (loose.isNotEmpty) {
      loose.sort((a, b) => a.episodeNum.compareTo(b.episodeNum));
      seasons.add(Season(number: _claim(1, used), episodes: loose));
    }
    final seriesCmd = source.cmd;
    if (seasons.isEmpty && seriesCmd != null) {
      // Nothing listed below the series, but the series itself plays.
      const number = 1;
      final id = '$_episodePrefix${source.rawId}_${number}_1';
      urls[id] = _link('vod', seriesCmd);
      seasons.add(
        Season(
          number: number,
          episodes: [
            Episode(id: id, title: title, episodeNum: 1, seasonNumber: number),
          ],
        ),
      );
    }
    seasons.sort((a, b) => a.number.compareTo(b.number));
    return seasons;
  }

  Season _numberedSeason(
    _SeriesSource source, {
    required int seasonNo,
    required String cmd,
    required List<int> numbers,
    required String title,
    required Map<String, String> urls,
    String? name,
    String? cover,
  }) {
    final episodes = <Episode>[];
    for (final n in numbers) {
      final id = '$_episodePrefix${source.rawId}_${seasonNo}_$n';
      urls[id] = _link('vod', cmd, series: '$n');
      episodes.add(
        Episode(id: id, title: title, episodeNum: n, seasonNumber: seasonNo),
      );
    }
    return Season(
      number: seasonNo,
      episodes: episodes,
      name: name,
      cover: cover,
    );
  }

  Episode _episode(
    Map<String, dynamic> item,
    _SeriesSource source, {
    required int seasonNo,
    required String seasonId,
    required int index,
    required String title,
    required Map<String, String> urls,
  }) {
    final rawId = JsonX.asStringOrNull(item['id']);
    final number =
        JsonX.asIntOrNull(item['series_number']) ??
        JsonX.asIntOrNull(item['episode_number']) ??
        index + 1;
    final id = rawId != null
        ? '$_episodePrefix$rawId'
        : '$_episodePrefix${source.rawId}_${seasonNo}_$number';
    final cmd = _cmdOf(item);
    urls[id] = cmd != null
        ? _link('vod', cmd)
        : _fileLink(source.module, source.rawId, seasonId, rawId ?? '$number');
    return Episode(
      id: id,
      title: JsonX.asStringOrNull(item['name']) ?? title,
      episodeNum: number,
      seasonNumber: seasonNo,
      durationSecs: _durationSecs(item['time']),
      plot: _plainText(item['description']),
      image: _poster(item),
      rating: _rating(item),
      added: _parseDate(item['added']),
    );
  }

  static int? _seasonNumber(Map<String, dynamic> item) {
    final explicit =
        JsonX.asIntOrNull(item['season_number']) ??
        JsonX.asIntOrNull(item['season_num']);
    if (explicit != null) return explicit;
    final id = JsonX.asString(item['id']);
    if (id.contains(':')) {
      final last = int.tryParse(id.substring(id.lastIndexOf(':') + 1));
      if (last != null) return last;
    }
    final name = JsonX.asString(item['name']);
    final match = RegExp(
      r'(?:season|saison|staffel|temporada|stagione|sezon\w*|сезон|الموسم|موسم)'
      r'\D{0,3}(\d{1,3})',
      caseSensitive: false,
      unicode: true,
    ).firstMatch(name);
    return match == null ? null : int.tryParse(match.group(1)!);
  }

  static int _claim(int wanted, Set<int> used) {
    var n = wanted;
    while (!used.add(n)) {
      n++;
    }
    return n;
  }

  // --- Playback ------------------------------------------------------------

  /// Turns a `stalker://` link into the address the player opens, through
  /// `create_link`.
  ///
  /// A portal that answers with a `localhost` address (or an empty `stream=`)
  /// did not resolve the stream: that is a [Failure.server], never a URL the
  /// player would then fail on. When `create_link` fails but the item's own
  /// `cmd` already named a real host, that address is played instead.
  Future<String> resolve(String stalkerUrl) async {
    final link = _StalkerLink.parse(stalkerUrl);
    if (link == null) {
      throw Failure.parse('This is not a MAC portal play link.');
    }
    final cmd = link.cmd ?? await _episodeFileCmd(link);
    // A fallback plays the item's base address — for an episode chosen by
    // number that would be the wrong episode, so there is none.
    final fallback = link.series.isEmpty ? _playableIn(cmd) : null;
    try {
      final js = await _call({
        'type': link.type,
        'action': 'create_link',
        'cmd': cmd,
        'series': link.series,
        'forced_storage': '0',
        'disable_ad': '0',
        'download': '0',
      });
      final url = _createLinkResult(js);
      return url;
    } on Failure catch (e) {
      if (fallback == null) rethrow;
      log.w(
        'Stalker create_link failed (${e.kind.name}); using listed address',
      );
      return fallback;
    }
  }

  Future<String> _episodeFileCmd(_StalkerLink link) async {
    final movieId = link.movieId;
    final episodeId = link.episodeId;
    if (movieId == null || episodeId == null) {
      throw Failure.parse('This MAC portal play link is incomplete.');
    }
    final files = await _allPages({
      'type': link.module,
      'action': 'get_ordered_list',
      'movie_id': movieId,
      'season_id': link.seasonId ?? '0',
      'episode_id': episodeId,
    }, maxPages: 1);
    for (final file in files) {
      final cmd = _cmdOf(file);
      if (cmd != null) return cmd;
    }
    throw Failure.server('The portal lists no playable file for this episode.');
  }

  String _createLinkResult(dynamic js) {
    String? raw;
    String? error;
    if (js is Map) {
      raw = JsonX.asStringOrNull(js['cmd']);
      error = JsonX.asStringOrNull(js['error']);
    } else if (js is String) {
      raw = JsonX.asStringOrNull(js);
    }
    final url = _playableIn(raw);
    if (url != null) return url;
    throw Failure.server(
      error != null
          ? 'The portal could not open this stream ($error).'
          : 'The portal did not give a playable address for this stream.',
    );
  }

  static final RegExp _urlPattern = RegExp(
    r'(?:https?|rtmps?|rtsp|rtp|udp|mms)://\S+',
    caseSensitive: false,
  );

  /// The stream address inside a `cmd` such as `ffmpeg http://host/…`, or
  /// null when there is none or it points at the box itself (`localhost`),
  /// which is how a portal says "resolve me with create_link".
  static String? _playableIn(String? cmd) {
    if (cmd == null) return null;
    final match = _urlPattern.firstMatch(cmd);
    if (match == null) return null;
    final url = match.group(0)!;
    try {
      final uri = Uri.parse(url);
      final host = uri.host.toLowerCase();
      if (host.isEmpty ||
          host == 'localhost' ||
          host.startsWith('127.') ||
          host == '0.0.0.0' ||
          host == '::1') {
        return null;
      }
      final stream = uri.queryParameters['stream'];
      if (stream != null && stream.trim().isEmpty) return null;
    } on FormatException {
      return null;
    } on ArgumentError {
      return null;
    }
    return url;
  }

  void close() => _dio.close(force: true);

  // --- Transport -----------------------------------------------------------

  Future<_Reply> _send(
    Uri endpoint,
    Map<String, String> params, {
    String? token,
    int attempt = 0,
  }) async {
    final uri = endpoint.replace(
      queryParameters: {...params, 'JsHttpRequest': '1-xml'},
    );
    try {
      final res = await _dio.getUri<dynamic>(
        uri,
        options: Options(
          responseType: ResponseType.bytes,
          headers: _headers(endpoint, token),
          validateStatus: (_) => true,
        ),
      );
      return _Reply(res.statusCode ?? 0, _bodyText(res.data));
    } on DioException catch (e) {
      if (_isTransient(e) && attempt == 0) {
        log.w('Stalker portal slow to answer, retrying once: ${e.type.name}');
        return _send(endpoint, params, token: token, attempt: 1);
      }
      throw _mapDioError(e);
    }
  }

  Map<String, String> _headers(Uri endpoint, String? token) {
    final root = StalkerPortalAddress.rootPathOf(endpoint);
    return {
      'User-Agent': userAgent,
      'X-User-Agent': xUserAgent,
      'Referer': '${endpoint.origin}$root/c/',
      'Accept': '*/*',
      'Cookie':
          'mac=${Uri.encodeComponent(_identity!.mac)}; stb_lang=en; '
          'timezone=${Uri.encodeComponent(_timezone)}',
      if (token != null) 'Authorization': 'Bearer $token',
    };
  }

  static String _bodyText(dynamic data) {
    if (data == null) return '';
    if (data is String) return data;
    if (data is List<int>) return utf8.decode(data, allowMalformed: true);
    // A caller-supplied Dio with its own transformer may hand back JSON.
    try {
      return jsonEncode(data);
    } on Object {
      return '';
    }
  }

  dynamic _decode(_Reply reply) {
    if (!reply.isOk) {
      throw Failure.server('The portal answered with HTTP ${reply.status}.');
    }
    final envelope = _envelope(reply.body);
    if (envelope == null) {
      throw Failure.parse('The portal sent a response MoPlayer cannot read.');
    }
    return envelope.js;
  }

  /// JSON from a body that may carry a BOM, a text/html label, or PHP notices
  /// around the object. null when there is no JSON in it at all.
  static _Envelope? _envelope(String body) {
    final text = _cleanBody(body);
    if (text.isEmpty) return null;
    var decoded = _tryJson(text);
    if (decoded == null) {
      final start = text.indexOf('{');
      final end = text.lastIndexOf('}');
      if (start >= 0 && end > start) {
        decoded = _tryJson(text.substring(start, end + 1));
      }
    }
    if (decoded == null) return null;
    if (decoded is Map && decoded.containsKey('js')) {
      return _Envelope(decoded['js'], hasJs: true);
    }
    return _Envelope(decoded, hasJs: false);
  }

  static dynamic _tryJson(String text) {
    try {
      return jsonDecode(text);
    } on FormatException {
      return null;
    }
  }

  bool _isTransient(DioException e) =>
      e.type == DioExceptionType.connectionTimeout ||
      e.type == DioExceptionType.receiveTimeout ||
      e.type == DioExceptionType.sendTimeout;

  Failure _mapDioError(DioException e) {
    switch (e.type) {
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.receiveTimeout:
      case DioExceptionType.sendTimeout:
        return Failure.timeout();
      case DioExceptionType.connectionError:
        return Failure.network();
      case DioExceptionType.badResponse:
        final code = e.response?.statusCode ?? 0;
        if (code == 401 || code == 403) return Failure.auth();
        return Failure.server('Server error (HTTP $code).');
      case DioExceptionType.cancel:
        return Failure.server('Request cancelled.');
      case DioExceptionType.badCertificate:
        return Failure.server('The portal has an invalid SSL certificate.');
      case DioExceptionType.unknown:
        return Failure.network(
          'Could not reach the portal. Check the address.',
        );
      // Dio adds members to this enum between minor versions; see XtreamApi.
      default:
        return Failure.network(
          'Could not reach the portal. Check the address.',
        );
    }
  }

  // --- Parsing -------------------------------------------------------------

  static bool _isContentFailure(Failure e) =>
      e.kind == FailureKind.parse || e.kind == FailureKind.server;

  /// The entries of a `js` that is a list, `{data: [...]}`, or a PHP array
  /// serialised as an object with numeric keys. Anything else is empty.
  static List<Map<String, dynamic>> _items(dynamic js) {
    var raw = js;
    if (raw is Map && raw['data'] != null) raw = raw['data'];
    Iterable<dynamic> values = const [];
    if (raw is List) {
      values = raw;
    } else if (raw is Map &&
        raw.isNotEmpty &&
        raw.keys.every((k) => int.tryParse('$k') != null)) {
      values = raw.values;
    }
    return [
      for (final value in values)
        if (value is Map) Map<String, dynamic>.from(value),
    ];
  }

  static _PageData _pageData(dynamic js, int page) {
    final items = _items(js);
    var total = 0;
    var perPage = 0;
    if (js is Map) {
      total = JsonX.asInt(js['total_items']);
      perPage = JsonX.asInt(js['max_page_items']);
    }
    if (perPage <= 0) perPage = items.length;
    final seen = (page - 1) * perPage + items.length;
    if (total < seen) total = seen;
    return _PageData(items, total, perPage);
  }

  Future<List<Map<String, dynamic>>> _allPages(
    Map<String, String> params, {
    required int maxPages,
  }) async {
    final out = <Map<String, dynamic>>[];
    final ids = <String>{};
    for (var page = 1; page <= maxPages; page++) {
      final data = _pageData(await _call({...params, 'p': '$page'}), page);
      var added = 0;
      for (final item in data.items) {
        final id = JsonX.asString(item['id']);
        if (id.isEmpty || ids.add(id)) {
          out.add(item);
          added++;
        }
      }
      // A portal that ignores `p` repeats page 1: stop when nothing is new.
      if (added == 0 || page * data.perPage >= data.total) break;
    }
    return out;
  }

  Map<String, String> _listParams(String type, String categoryId, int page) {
    final all =
        categoryId.isEmpty || categoryId == Category.allId || categoryId == '*';
    return {
      'type': type,
      'action': 'get_ordered_list',
      'category': all ? '*' : categoryId,
      'genre': '*',
      'sortby': 'added',
      'p': '$page',
    };
  }

  static List<Category> _categories(dynamic js) {
    final categories = <Category>[];
    for (final item in _items(js)) {
      final id = JsonX.asStringOrNull(item['id']);
      if (id == null || id == '*') continue;
      categories.add(
        Category(
          id: id,
          name:
              JsonX.asStringOrNull(item['title']) ??
              JsonX.asStringOrNull(item['name']) ??
              'Unknown',
        ),
      );
    }
    return categories;
  }

  static String? _cmdOf(Map<String, dynamic> item) {
    final cmd = JsonX.asStringOrNull(item['cmd']);
    if (cmd != null) return cmd;
    for (final entry in JsonX.asList(item['cmds'])) {
      if (entry is Map) {
        final url =
            JsonX.asStringOrNull(entry['url']) ??
            JsonX.asStringOrNull(entry['cmd']);
        if (url != null) return url;
      }
    }
    return null;
  }

  static String _link(String type, String cmd, {String? series}) {
    final query = 'cmd=${Uri.encodeQueryComponent(cmd)}';
    return series == null
        ? 'stalker://$type?$query'
        : 'stalker://$type?$query&series=${Uri.encodeQueryComponent(series)}';
  }

  static String _fileLink(
    String module,
    String movieId,
    String seasonId,
    String episodeId,
  ) {
    final query = Uri(
      queryParameters: {
        'module': module,
        'movie_id': movieId,
        'season_id': seasonId,
        'episode_id': episodeId,
      },
    ).query;
    return 'stalker://vod?$query';
  }

  String get _rootPath {
    final endpoint = _endpoint;
    if (endpoint != null) return StalkerPortalAddress.rootPathOf(endpoint);
    return _address?.basePath ?? '';
  }

  String get _endpointKind {
    final path = _endpoint?.path ?? '';
    return path.endsWith('portal.php') ? 'portal.php' : 'server/load.php';
  }

  /// Portals send logos and posters as full URLs, host-relative paths, or —
  /// for channel logos on older installs — a bare file name under
  /// `<portal root>/misc/logos/320/`.
  String? _absoluteUrl(dynamic raw, {String? bareFileDir}) {
    final value = JsonX.asStringOrNull(raw);
    if (value == null) return null;
    final lower = value.toLowerCase();
    if (lower.startsWith('http://') || lower.startsWith('https://')) {
      return value;
    }
    final origin = _endpoint?.origin ?? _address?.origin.origin;
    if (origin == null) return null;
    if (value.startsWith('//')) {
      return '${Uri.parse(origin).scheme}:$value';
    }
    if (value.startsWith('/')) return '$origin$value';
    if (bareFileDir != null && !value.contains('/')) {
      return '$origin$_rootPath$bareFileDir$value';
    }
    return '$origin$_rootPath/$value';
  }

  String? _poster(Map<String, dynamic> item) =>
      _absoluteUrl(item['screenshot_uri']) ??
      _absoluteUrl(item['cover']) ??
      _absoluteUrl(item['pic']) ??
      _absoluteUrl(item['screenshot']);

  static double? _rating(Map<String, dynamic> item) {
    for (final key in const ['rating_imdb', 'rating_kinopoisk', 'rating']) {
      final value = JsonX.asDoubleOrNull(item[key]);
      if (value != null && value > 0) return value;
    }
    return null;
  }

  static String? _year(dynamic raw) {
    final text = JsonX.asStringOrNull(raw);
    if (text == null) return null;
    return RegExp(r'(?:19|20)\d{2}').firstMatch(text)?.group(0);
  }

  /// `time` is minutes on Ministra; some panels send `hh:mm[:ss]`.
  static int? _durationSecs(dynamic raw) {
    final text = JsonX.asStringOrNull(raw);
    if (text == null) return null;
    if (text.contains(':')) {
      final parts = text.split(':').map(int.tryParse).toList();
      if (parts.any((p) => p == null)) return null;
      var secs = 0;
      for (final p in parts) {
        secs = secs * 60 + p!;
      }
      if (parts.length == 2) secs *= 60; // hh:mm
      return secs > 0 ? secs : null;
    }
    final minutes = JsonX.asIntOrNull(text);
    return minutes != null && minutes > 0 ? minutes * 60 : null;
  }

  static List<int> _numbers(dynamic raw) {
    Iterable<dynamic> values;
    if (raw is List) {
      values = raw;
    } else if (raw is String) {
      values = raw.split(',');
    } else {
      return const [];
    }
    final numbers = <int>{};
    for (final value in values) {
      final n = JsonX.asIntOrNull(value);
      if (n != null && n >= 0) numbers.add(n);
    }
    return numbers.toList()..sort();
  }

  static String? _plainText(dynamic raw) {
    final text = JsonX.asStringOrNull(raw);
    if (text == null) return null;
    final plain = text
        .replaceAll(RegExp(r'<br\s*/?>', caseSensitive: false), ' ')
        .replaceAll(RegExp(r'<[^>]*>'), '')
        .replaceAll(RegExp(r'\s+'), ' ')
        .trim();
    return plain.isEmpty ? null : plain;
  }

  static const Map<String, int> _months = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6, //
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
  };

  /// Unix seconds, `yyyy-mm-dd[ hh:mm[:ss]]` (a zero date is "none"), or
  /// `Month d, yyyy[, h:mm am]`.
  static DateTime? _parseDate(dynamic raw, {bool allowNumeric = true}) {
    final text = JsonX.asStringOrNull(raw);
    if (text == null) return null;
    if (RegExp(r'^\d+$').hasMatch(text)) {
      if (!allowNumeric) return null;
      final secs = int.tryParse(text);
      if (secs == null || secs <= 0) return null;
      return DateTime.fromMillisecondsSinceEpoch(secs * 1000);
    }
    final iso = RegExp(
      r'^(\d{4})-(\d{1,2})-(\d{1,2})(?:[ T](\d{1,2}):(\d{2})(?::(\d{2}))?)?',
    ).firstMatch(text);
    if (iso != null) {
      final year = int.parse(iso.group(1)!);
      final month = int.parse(iso.group(2)!);
      final day = int.parse(iso.group(3)!);
      if (year == 0 || month < 1 || month > 12 || day < 1 || day > 31) {
        return null;
      }
      return DateTime(
        year,
        month,
        day,
        int.tryParse(iso.group(4) ?? '') ?? 0,
        int.tryParse(iso.group(5) ?? '') ?? 0,
        int.tryParse(iso.group(6) ?? '') ?? 0,
      );
    }
    final named = RegExp(
      r'^([A-Za-z]{3,})\.?\s+(\d{1,2}),?\s+(\d{4})'
      r'(?:,?\s+(\d{1,2}):(\d{2})\s*([ap]m)?)?',
      caseSensitive: false,
    ).firstMatch(text);
    if (named != null) {
      final month = _months[named.group(1)!.substring(0, 3).toLowerCase()];
      if (month == null) return null;
      var hour = int.tryParse(named.group(4) ?? '') ?? 0;
      final meridiem = named.group(6)?.toLowerCase();
      if (meridiem == 'pm' && hour < 12) hour += 12;
      if (meridiem == 'am' && hour == 12) hour = 0;
      return DateTime(
        int.parse(named.group(3)!),
        month,
        int.parse(named.group(2)!),
        hour,
        int.tryParse(named.group(5) ?? '') ?? 0,
      );
    }
    return null;
  }
}

String _cleanBody(String body) {
  var text = body.trim();
  while (text.startsWith('﻿')) {
    text = text.substring(1).trimLeft();
  }
  return text;
}

class _Reply {
  _Reply(this.status, this.body);

  final int status;
  final String body;

  bool get isOk => status >= 200 && status < 300;

  /// The portal refusing the token: 401/403, or Ministra's plain-text
  /// `Authorization failed.` answer with a 200.
  bool get isRefusal {
    if (status == 401 || status == 403) return true;
    if (!isOk) return false;
    final text = _cleanBody(body);
    if (text.startsWith('{') || text.startsWith('[')) return false;
    return text.toLowerCase().contains('authorization failed');
  }
}

class _Envelope {
  const _Envelope(this.js, {required this.hasJs});

  final dynamic js;
  final bool hasJs;
}

class _PageData {
  const _PageData(this.items, this.total, this.perPage);

  final List<Map<String, dynamic>> items;
  final int total;
  final int perPage;
}

class _SeriesSource {
  const _SeriesSource({
    required this.rawId,
    required this.module,
    this.cmd,
    this.episodes = const [],
  });

  final String rawId;

  /// `series` or `vod` — the `type` its seasons are listed under.
  final String module;
  final String? cmd;
  final List<int> episodes;
}

class _StalkerLink {
  const _StalkerLink({
    required this.type,
    required this.series,
    required this.module,
    this.cmd,
    this.movieId,
    this.seasonId,
    this.episodeId,
  });

  final String type;
  final String? cmd;
  final String series;
  final String module;
  final String? movieId;
  final String? seasonId;
  final String? episodeId;

  static _StalkerLink? parse(String url) {
    final Uri uri;
    try {
      uri = Uri.parse(url.trim());
    } on FormatException {
      return null;
    }
    if (uri.scheme.toLowerCase() != 'stalker') return null;
    final type = uri.host.toLowerCase();
    if (type != 'itv' && type != 'vod') return null;
    final Map<String, String> query;
    try {
      query = uri.queryParameters;
    } on ArgumentError {
      return null;
    }
    final cmd = JsonX.asStringOrNull(query['cmd']);
    final episodeId = JsonX.asStringOrNull(query['episode_id']);
    if (cmd == null && episodeId == null) return null;
    final module = query['module'] == 'series' ? 'series' : 'vod';
    return _StalkerLink(
      type: type,
      cmd: cmd,
      series: query['series']?.trim() ?? '',
      module: module,
      movieId: JsonX.asStringOrNull(query['movie_id']),
      seasonId: JsonX.asStringOrNull(query['season_id']),
      episodeId: episodeId,
    );
  }
}
