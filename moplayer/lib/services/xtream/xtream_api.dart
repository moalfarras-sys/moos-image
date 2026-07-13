import 'dart:convert';

import 'package:dio/dio.dart';

import '../../core/config/app_config.dart';
import '../../core/error/failures.dart';
import '../../core/utils/app_logger.dart';
import '../../core/utils/json_x.dart';
import '../../models/category.dart';
import '../../models/epg_entry.dart';
import '../../models/live_channel.dart';
import '../../models/playlist_config.dart';
import '../../models/series.dart';
import '../../models/vod_movie.dart';
import 'xtream_url_builder.dart';

/// A resilient Xtream Codes API client. Every method maps transport errors to
/// a typed [Failure], retries once on transient timeouts and tolerates the
/// many shapes panels return (objects, arrays, error envelopes).
class XtreamApi {
  XtreamApi(this.config, {Dio? dio})
    : urls = XtreamUrlBuilder(config),
      _dio =
          dio ??
          Dio(
            BaseOptions(
              connectTimeout: AppConfig.connectTimeout,
              receiveTimeout: AppConfig.receiveTimeout,
              responseType: ResponseType.json,
              // Panels frequently mislabel content type; parse leniently.
              headers: const {'User-Agent': 'MoPlayerPro/1.0'},
            ),
          );

  final PlaylistConfig config;
  final XtreamUrlBuilder urls;
  final Dio _dio;

  // --- Auth ----------------------------------------------------------------

  /// Validates credentials and returns the account info. Throws [Failure].
  Future<XtreamAccountInfo> authenticate() async {
    final data = await _getJson(urls.authProbe());
    if (data is! Map) {
      throw Failure.server('Server did not return a valid login response.');
    }
    final userInfo = data['user_info'];
    if (userInfo is! Map) {
      throw Failure.auth('Login rejected by the server.');
    }
    final auth = JsonX.asInt(userInfo['auth'], fallback: 1);
    final status = JsonX.asString(userInfo['status'], fallback: '');
    if (auth == 0 || status.toLowerCase() == 'disabled') {
      throw Failure.auth('Your account is disabled or the password is wrong.');
    }
    return XtreamAccountInfo.fromJson(Map<String, dynamic>.from(userInfo));
  }

  // --- Live ----------------------------------------------------------------

  Future<List<Category>> getLiveCategories() =>
      _categories('get_live_categories');

  Future<List<LiveChannel>> getLiveStreams({String? categoryId}) async {
    final data = await _getList('get_live_streams', categoryId: categoryId);
    return data
        .whereType<Map>()
        .map((e) => LiveChannel.fromXtream(Map<String, dynamic>.from(e)))
        .toList(growable: false);
  }

  // --- VOD -----------------------------------------------------------------

  Future<List<Category>> getVodCategories() =>
      _categories('get_vod_categories');

  Future<List<VodMovie>> getVodStreams({String? categoryId}) async {
    final data = await _getList('get_vod_streams', categoryId: categoryId);
    return data
        .whereType<Map>()
        .map((e) => VodMovie.fromXtream(Map<String, dynamic>.from(e)))
        .toList(growable: false);
  }

  Future<MovieDetail> getVodInfo(VodMovie base) async {
    final data = await _getJson(
      urls.playerApi('get_vod_info', params: {'vod_id': base.streamId}),
    );
    if (data is! Map) throw Failure.parse('Movie details unavailable.');
    return MovieDetail.fromXtream(Map<String, dynamic>.from(data), base);
  }

  // --- Series --------------------------------------------------------------

  Future<List<Category>> getSeriesCategories() =>
      _categories('get_series_categories');

  Future<List<SeriesItem>> getSeries({String? categoryId}) async {
    final data = await _getList('get_series', categoryId: categoryId);
    return data
        .whereType<Map>()
        .map((e) => SeriesItem.fromXtream(Map<String, dynamic>.from(e)))
        .toList(growable: false);
  }

  Future<SeriesDetail> getSeriesInfo(SeriesItem base) async {
    final data = await _getJson(
      urls.playerApi('get_series_info', params: {'series_id': base.seriesId}),
    );
    if (data is! Map) throw Failure.parse('Series details unavailable.');
    return SeriesDetail.fromXtream(Map<String, dynamic>.from(data), base);
  }

  // --- EPG -----------------------------------------------------------------

  Future<List<EpgEntry>> getShortEpg(String streamId, {int limit = 8}) async {
    try {
      final data = await _getJson(
        urls.playerApi(
          'get_short_epg',
          params: {'stream_id': streamId, 'limit': '$limit'},
        ),
      );
      if (data is Map && data['epg_listings'] is List) {
        return (data['epg_listings'] as List)
            .whereType<Map>()
            .map((e) => EpgEntry.fromXtream(Map<String, dynamic>.from(e)))
            .toList();
      }
    } catch (e) {
      // EPG is best-effort; never block playback because it failed.
      log.d('EPG unavailable for $streamId: $e');
    }
    return const [];
  }

  // --- Internals -----------------------------------------------------------

  Future<List<Category>> _categories(String action) async {
    final data = await _getList(action);
    final cats = data
        .whereType<Map>()
        .map((e) => Category.fromXtream(Map<String, dynamic>.from(e)))
        .toList();
    return cats;
  }

  Future<List<dynamic>> _getList(String action, {String? categoryId}) async {
    final params = <String, String>{};
    if (categoryId != null &&
        categoryId.isNotEmpty &&
        categoryId != Category.allId) {
      params['category_id'] = categoryId;
    }
    final data = await _getJson(urls.playerApi(action, params: params));
    if (data is List) return data;
    // Some panels wrap errors as a Map with a message; treat as empty list.
    if (data is Map && data.isEmpty) return const [];
    if (data is Map) return _unwrapList(data, action);
    return const [];
  }

  List<dynamic> _unwrapList(Map<dynamic, dynamic> data, String action) {
    const knownKeys = [
      'data',
      'items',
      'results',
      'streams',
      'categories',
      'available_channels',
      'live_streams',
      'vod_streams',
      'series',
    ];
    final actionKey = action
        .replaceFirst('get_', '')
        .replaceAll('_categories', '_streams');
    for (final key in [action, actionKey, ...knownKeys]) {
      final value = data[key];
      if (value is List) return value;
    }
    for (final value in data.values) {
      if (value is List) return value;
    }
    return const [];
  }

  Future<dynamic> _getJson(Uri uri, {int attempt = 0}) async {
    try {
      final res = await _dio.getUri<dynamic>(uri);
      final body = res.data;
      if (body is String) {
        // Lenient: a few panels send JSON with a text/html content-type.
        return _tryDecode(body);
      }
      return body;
    } on DioException catch (e) {
      if (_isTransient(e) && attempt == 0) {
        log.w('Xtream transient error, retrying once: ${e.type}');
        return _getJson(uri, attempt: 1);
      }
      throw _mapDioError(e);
    } catch (e) {
      throw Failure.server('Unexpected error talking to the server: $e');
    }
  }

  dynamic _tryDecode(String body) {
    final trimmed = body.trim();
    if (trimmed.isEmpty) return const {};
    try {
      // Dio already decodes JSON when content-type is right; this is a fallback
      // for panels that mislabel the response as text/html.
      return jsonDecode(trimmed);
    } catch (_) {
      throw Failure.parse('Server returned an unreadable response.');
    }
  }

  bool _isTransient(DioException e) {
    return e.type == DioExceptionType.connectionTimeout ||
        e.type == DioExceptionType.receiveTimeout ||
        e.type == DioExceptionType.sendTimeout;
  }

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
        return Failure.server('The server has an invalid SSL certificate.');
      case DioExceptionType.unknown:
        return Failure.network('Could not reach the server. Check the URL.');
      // Dio adds members to this enum between minor versions (transformTimeout
      // arrived in 5.9). An unmatched one used to compile and then throw at
      // runtime, inside the one method whose job is to turn a throw into a
      // message.
      default:
        return Failure.network('Could not reach the server. Check the URL.');
    }
  }

  void close() => _dio.close(force: true);
}
