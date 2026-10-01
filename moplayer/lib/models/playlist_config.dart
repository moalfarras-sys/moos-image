import '../core/utils/json_x.dart';

enum PlaylistType {
  xtream,
  m3u,

  /// A MAG-style middleware portal (Stalker / Ministra), signed in with the
  /// device's MAC address instead of a username and password.
  stalker;

  String get wire => name;
  static PlaylistType fromWire(String? v) => PlaylistType.values.firstWhere(
    (e) => e.wire == v,
    orElse: () => PlaylistType.xtream,
  );
}

/// A saved playlist source. For Xtream it holds server + credentials; for M3U
/// it holds the playlist URL. Passwords are persisted only in MoPlayer's
/// user-private 0600 store (never in logs or the code).
class PlaylistConfig {
  const PlaylistConfig({
    required this.id,
    required this.type,
    required this.name,
    this.serverUrl = '',
    this.username = '',
    this.password = '',
    this.m3uUrl = '',
    this.macAddress = '',
    this.createdAt,
  });

  final String id;
  final PlaylistType type;
  final String name;

  // Xtream
  final String serverUrl;
  final String username;
  final String password;

  // M3U
  final String m3uUrl;

  // Stalker portal: [serverUrl] is the portal, this is the device it knows.
  final String macAddress;

  final DateTime? createdAt;

  bool get isXtream => type == PlaylistType.xtream;
  bool get isStalker => type == PlaylistType.stalker;
  bool get isM3u => type == PlaylistType.m3u;

  /// The Xtream account a playlist link is really a view of, or null.
  ///
  /// A panel's `get.php?username=…&password=…&type=m3u_plus` link is the whole
  /// account flattened into one file — on the owner's server, 395,424 lines
  /// in which every episode of every series is a "channel". Read through the
  /// panel's own API instead, the same account is 12,975 channels, 20,569 films
  /// and 10,834 series, delivered as three small JSON documents with their
  /// categories, artwork and guide. So a playlist link that carries an account
  /// is read as that account, and the flat file is only the fallback for a
  /// panel whose API refuses to answer.
  PlaylistConfig? get xtreamEquivalent {
    if (!isM3u) return null;
    final uri = Uri.tryParse(m3uUrl.trim());
    if (uri == null || (uri.scheme != 'http' && uri.scheme != 'https')) {
      return null;
    }
    String? pick(List<String> keys) {
      for (final key in keys) {
        final value = uri.queryParameters[key]?.trim();
        if (value != null && value.isNotEmpty) return value;
      }
      return null;
    }

    final user = pick(const ['username', 'user']);
    final pass = pick(const ['password', 'pass']);
    if (user == null || pass == null || uri.host.isEmpty) return null;
    final origin = uri.hasPort
        ? '${uri.scheme}://${uri.host}:${uri.port}'
        : '${uri.scheme}://${uri.host}';
    return PlaylistConfig(
      id: id,
      type: PlaylistType.xtream,
      name: name,
      serverUrl: origin,
      username: user,
      password: pass,
      createdAt: createdAt,
    );
  }

  /// Normalised base server URL with scheme and no trailing slash.
  String get normalizedServer {
    var s = serverUrl.trim();
    if (s.isEmpty) return s;
    if (!s.startsWith('http://') && !s.startsWith('https://')) {
      s = 'http://$s';
    }
    while (s.endsWith('/')) {
      s = s.substring(0, s.length - 1);
    }
    return s;
  }

  /// What makes this source *the same source* as another one.
  ///
  /// The [id] cannot answer that: it is minted fresh every time a config is
  /// built, so opening the same `demo.m3u` from Dolphin three times produced
  /// three ids and three identical entries in Settings — one list, one file,
  /// three rows. What a user means by "the same source" is the same panel and
  /// account, or the same playlist URL, and that is what this returns.
  ///
  /// The password is deliberately *not* part of it: changing the password on an
  /// Xtream account does not make it a different account, it makes it the same
  /// account with a corrected credential, and the entry should be updated in
  /// place rather than duplicated.
  String get identityKey => switch (type) {
    PlaylistType.xtream =>
      'xtream:$normalizedServer:${username.trim().toLowerCase()}',
    PlaylistType.m3u => 'm3u:${m3uUrl.trim()}',
    PlaylistType.stalker =>
      'stalker:$normalizedServer:${macAddress.trim().toUpperCase()}',
  };

  PlaylistConfig copyWith({String? name, DateTime? createdAt}) =>
      PlaylistConfig(
        id: id,
        type: type,
        name: name ?? this.name,
        serverUrl: serverUrl,
        username: username,
        password: password,
        m3uUrl: m3uUrl,
        macAddress: macAddress,
        createdAt: createdAt ?? this.createdAt,
      );

  Map<String, dynamic> toJson() => {
    'id': id,
    'type': type.wire,
    'name': name,
    'serverUrl': serverUrl,
    'username': username,
    'password': password,
    'm3uUrl': m3uUrl,
    if (macAddress.isNotEmpty) 'macAddress': macAddress,
    'createdAt': createdAt?.toIso8601String(),
  };

  factory PlaylistConfig.fromJson(Map<String, dynamic> json) => PlaylistConfig(
    id: JsonX.asString(json['id']),
    type: PlaylistType.fromWire(JsonX.asStringOrNull(json['type'])),
    name: JsonX.asString(json['name'], fallback: 'My Playlist'),
    serverUrl: JsonX.asString(json['serverUrl']),
    username: JsonX.asString(json['username']),
    password: JsonX.asString(json['password']),
    m3uUrl: JsonX.asString(json['m3uUrl']),
    macAddress: JsonX.asString(json['macAddress']),
    createdAt: DateTime.tryParse(JsonX.asString(json['createdAt'])),
  );
}

/// Cached Xtream account info from `player_api.php` (the `user_info` block).
class XtreamAccountInfo {
  const XtreamAccountInfo({
    required this.username,
    required this.status,
    this.expiresAt,
    this.maxConnections,
    this.activeConnections,
    this.isTrial = false,
  });

  final String username;
  final String status;
  final DateTime? expiresAt;
  final int? maxConnections;
  final int? activeConnections;
  final bool isTrial;

  bool get isActive => status.toLowerCase() == 'active';

  factory XtreamAccountInfo.fromJson(Map<String, dynamic> userInfo) {
    return XtreamAccountInfo(
      username: JsonX.asString(userInfo['username']),
      status: JsonX.asString(userInfo['status'], fallback: 'Unknown'),
      expiresAt: JsonX.asUnixSeconds(userInfo['exp_date']),
      maxConnections: JsonX.asIntOrNull(userInfo['max_connections']),
      activeConnections: JsonX.asIntOrNull(userInfo['active_cons']),
      isTrial: JsonX.asBool(userInfo['is_trial']),
    );
  }
}
