import 'dart:io';

import '../../models/playlist_config.dart';

/// Turns whatever link the user was actually handed into the strongest source
/// this app can make of it.
///
/// This exists because of what a subscription is sold as. Nobody is given a
/// "server URL, username, password" triplet in three fields — they are given
/// **one link**, and it almost always looks like this:
///
/// ```
/// http://panel.example:8080/get.php?username=U&password=P&type=m3u_plus&output=ts
/// ```
///
/// Pasted into an M3U field, that link *works* — and it is the single most
/// expensive thing a player can let a user do. `get.php` returns live channels
/// and nothing else: no VOD, no series, no EPG, no categories the panel knows
/// about. The user concludes the app cannot show films. The same link, read as
/// what it is — a **panel host plus an account** — unlocks the entire Xtream
/// API, because the credentials were sitting in the query string the whole time.
///
/// So: parse the link, and prefer Xtream whenever the link can prove an account
/// exists. Fall back to a plain playlist only when it genuinely is one.
///
/// One parser, used by both seams that can receive a link — the login screen and
/// the command line (a file manager double-click, `moplayer <link>`). Two copies
/// of this logic would drift, and the one that drifted would be the one the user
/// pasted into.
abstract final class SourceLink {
  /// Panel endpoints that carry the account in their query string. Any of them
  /// is proof of an Xtream panel, and they are all equivalent for our purpose:
  /// what we keep is the origin and the credentials, not the endpoint.
  static const _xtreamEndpoints = {
    'get.php',
    'player_api.php',
    'panel_api.php',
    'portal.php',
    'xmltv.php',
  };

  /// Null when [raw] is not a source at all. The caller decides what to say.
  static PlaylistConfig? parse(String raw, {String? id}) {
    final input = raw.trim();
    if (input.isEmpty) return null;

    // A local file, with or without a scheme. Checked before the URI branch: a
    // Windows-ish or bare path parses as a URI with no host and would otherwise
    // fall through every test below.
    if (!input.contains('://')) {
      if (!_isPlaylistPath(input)) return null;
      final abs = Uri.file(File(input).absolute.path).toString();
      return _m3u(abs, name: _fileName(input), id: id);
    }

    final uri = Uri.tryParse(input);
    if (uri == null) return null;

    // `asset://` and `file://` are playlists or they are nothing.
    //
    // The body is taken after the scheme rather than from `uri.path`: in
    // `asset://demo.m3u` the file name parses as the *host*, and reading the
    // path would find an empty string and reject the app's own bundled demo.
    if (uri.scheme == 'asset' || uri.scheme == 'file') {
      final body = input.substring(input.indexOf('://') + 3);
      if (!_isPlaylistPath(body)) return null;
      return _m3u(input, name: _fileName(body), id: id);
    }

    if (uri.scheme != 'http' && uri.scheme != 'https') return null;
    if (uri.host.isEmpty) return null;

    final user = _firstNonEmpty(uri.queryParameters, const [
      'username',
      'user',
    ]);
    final pass = _firstNonEmpty(uri.queryParameters, const [
      'password',
      'pass',
    ]);
    final endpoint = uri.pathSegments.isEmpty
        ? ''
        : uri.pathSegments.last.toLowerCase();

    // The account is in the link. Take it — this is the whole point of the file.
    //
    // The endpoint check is deliberately *not* required: panels are reskinned
    // constantly and some hand out `/api.php`, `/enigma2.php` or a bare path
    // with the same two query parameters. A username **and** a password on an
    // http(s) URL is an Xtream account with a confidence no endpoint name adds
    // to, and a link that turns out not to be one fails at the login probe —
    // which is a message, not a corrupted source.
    if (user != null && pass != null) {
      return PlaylistConfig(
        id: id ?? _mintId('xtream'),
        type: PlaylistType.xtream,
        name: uri.host,
        serverUrl: _origin(input, uri),
        username: user,
        password: pass,
      );
    }

    // No credentials. A link that still says `type=m3u…` is a playlist link and
    // is worth keeping — this is checked *before* the panel-endpoint bail-out
    // below, because `get.php?type=m3u_plus` is both at once, and it is a
    // perfectly good playlist even though nobody can log in with it.
    if (_isPlaylistPath(uri.path) || _looksLikeM3uQuery(uri)) {
      return _m3u(input, name: _fileName(uri.path, fallback: uri.host), id: id);
    }

    // The shape of a panel endpoint and nothing else: we know *where* the panel
    // is and not *who* the user is. Not a source yet — [panelOrigin] hands the
    // host to the login form so the user only types what the link did not carry.
    if (_xtreamEndpoints.contains(endpoint)) return null;

    return null;
  }

  /// The panel's origin, for a link that names a panel but carries no account
  /// (`http://panel.example:8080/c/`, a bare `player_api.php`). Lets the login
  /// screen fill the server field from a paste and ask only for the credentials.
  static String? panelOrigin(String raw) {
    final uri = Uri.tryParse(raw.trim());
    if (uri == null) return null;
    if (uri.scheme != 'http' && uri.scheme != 'https') return null;
    if (uri.host.isEmpty) return null;
    return _origin(raw.trim(), uri);
  }

  /// Does this link carry an account? Used by the login screen to explain
  /// *why* a pasted M3U link was upgraded to a full Xtream account.
  static bool carriesAccount(String raw) {
    final config = parse(raw);
    return config != null && config.isXtream;
  }

  // ── internals ──────────────────────────────────────────────────────────────

  /// Scheme + host + port, **as the link wrote it**.
  ///
  /// Read off the raw string rather than the parsed [Uri], because Dart's parser
  /// normalises a default port away: `http://panel.example:80` comes back as
  /// `http://panel.example` with `hasPort == false`. That is correct for the web
  /// and wrong here. Panels are routinely published on an explicit `:80` while
  /// the same host answers something else entirely on the implicit one, and a
  /// source that silently dropped its own port is a source that stops playing on
  /// a server the user can see is up.
  static final _origins = RegExp(r'^(https?)://([^/?#@]+@)?([^/?#]+)', caseSensitive: false);

  static String _origin(String raw, Uri uri) {
    final m = _origins.firstMatch(raw.trim());
    if (m == null) return '${uri.scheme}://${uri.host}';
    return '${m.group(1)!.toLowerCase()}://${m.group(3)!}';
  }

  static bool _isPlaylistPath(String path) {
    final p = path.toLowerCase();
    return p.endsWith('.m3u') || p.endsWith('.m3u8');
  }

  /// `…/get.php?type=m3u_plus` with no credentials — a playlist link, and all
  /// that can be made of it.
  static bool _looksLikeM3uQuery(Uri uri) {
    final type = uri.queryParameters['type']?.toLowerCase() ?? '';
    return type.startsWith('m3u');
  }

  static String? _firstNonEmpty(Map<String, String> query, List<String> keys) {
    for (final key in keys) {
      final value = query[key]?.trim();
      if (value != null && value.isNotEmpty) return value;
    }
    return null;
  }

  static String _fileName(String path, {String fallback = 'Playlist'}) {
    final segments = path.split('/').where((s) => s.isNotEmpty).toList();
    return segments.isEmpty ? fallback : segments.last;
  }

  static PlaylistConfig _m3u(String url, {required String name, String? id}) =>
      PlaylistConfig(
        id: id ?? _mintId('m3u'),
        type: PlaylistType.m3u,
        name: name,
        m3uUrl: url,
      );

  static String _mintId(String prefix) =>
      '${prefix}_${DateTime.now().microsecondsSinceEpoch}';
}
