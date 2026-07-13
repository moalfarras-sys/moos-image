import '../../models/playlist_config.dart';

/// Builds the various URLs an Xtream Codes panel exposes. Different panels are
/// fussy about container extensions, so callers can override `ext`.
class XtreamUrlBuilder {
  const XtreamUrlBuilder(this.config);

  final PlaylistConfig config;

  String get _base => config.normalizedServer;
  String get _user => Uri.encodeComponent(config.username);
  String get _pass => Uri.encodeComponent(config.password);

  /// The JSON API endpoint with the given [action] and optional extra params.
  Uri playerApi(String action, {Map<String, String> params = const {}}) {
    return Uri.parse('$_base/player_api.php').replace(
      queryParameters: {
        'username': config.username,
        'password': config.password,
        'action': action,
        ...params,
      },
    );
  }

  /// Authentication probe (no action) — returns user_info + server_info.
  Uri authProbe() {
    return Uri.parse('$_base/player_api.php').replace(
      queryParameters: {
        'username': config.username,
        'password': config.password,
      },
    );
  }

  /// XMLTV EPG endpoint.
  Uri xmltv() {
    return Uri.parse('$_base/xmltv.php').replace(
      queryParameters: {
        'username': config.username,
        'password': config.password,
      },
    );
  }

  /// `live/{user}/{pass}/{streamId}.{ext}` — `m3u8` for HLS, `ts` otherwise.
  String liveStream(String streamId, {bool hls = true}) {
    final ext = hls ? 'm3u8' : 'ts';
    return '$_base/live/$_user/$_pass/$streamId.$ext';
  }

  /// `movie/{user}/{pass}/{streamId}.{ext}`
  String movieStream(String streamId, {String ext = 'mp4'}) {
    final safeExt = ext.isEmpty ? 'mp4' : ext;
    return '$_base/movie/$_user/$_pass/$streamId.$safeExt';
  }

  /// `series/{user}/{pass}/{episodeId}.{ext}`
  String episodeStream(String episodeId, {String ext = 'mp4'}) {
    final safeExt = ext.isEmpty ? 'mp4' : ext;
    return '$_base/series/$_user/$_pass/$episodeId.$safeExt';
  }

  /// Catch-up / timeshift stream (when the panel advertises `tv_archive`).
  String timeshift(
    String streamId, {
    required int durationMin,
    required String start,
  }) {
    return '$_base/streaming/timeshift.php?username=${config.username}'
        '&password=${config.password}&stream=$streamId'
        '&start=$start&duration=$durationMin';
  }
}
