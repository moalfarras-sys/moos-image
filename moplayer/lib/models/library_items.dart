import '../core/utils/json_x.dart';
import 'media_kind.dart';

/// Shared identity for any saved library entry. Entries are scoped to the
/// active playlist so two different panels don't collide.
mixin MediaRefMixin {
  String get playlistId;
  MediaKind get kind;
  String get refId;

  /// Stable local cache key.
  String get key => '$playlistId:${kind.wire}:$refId';
}

/// A favourited channel / movie / series.
class FavoriteItem with MediaRefMixin {
  FavoriteItem({
    required this.playlistId,
    required this.kind,
    required this.refId,
    required this.title,
    this.imageUrl,
    this.subtitle,
    Map<String, dynamic>? payload,
    DateTime? createdAt,
  }) : payload = payload ?? const {},
       createdAt = createdAt ?? DateTime.now();

  @override
  final String playlistId;
  @override
  final MediaKind kind;
  @override
  final String refId;

  final String title;
  final String? imageUrl;
  final String? subtitle;
  final Map<String, dynamic> payload;
  final DateTime createdAt;

  Map<String, dynamic> toJson() => {
    'playlist_id': playlistId,
    'kind': kind.wire,
    'ref_id': refId,
    'title': title,
    'image_url': imageUrl,
    'subtitle': subtitle,
    'payload': payload,
    'created_at': createdAt.toIso8601String(),
  };

  factory FavoriteItem.fromJson(Map<String, dynamic> json) => FavoriteItem(
    playlistId: JsonX.asString(json['playlist_id']),
    kind: MediaKind.fromWire(JsonX.asStringOrNull(json['kind'])),
    refId: JsonX.asString(json['ref_id']),
    title: JsonX.asString(json['title']),
    imageUrl: JsonX.asStringOrNull(json['image_url']),
    subtitle: JsonX.asStringOrNull(json['subtitle']),
    payload: _payload(json['payload']),
    createdAt:
        DateTime.tryParse(JsonX.asString(json['created_at'])) ?? DateTime.now(),
  );
}

/// A watch-history entry (anything that was opened/played).
class HistoryItem with MediaRefMixin {
  HistoryItem({
    required this.playlistId,
    required this.kind,
    required this.refId,
    required this.title,
    this.imageUrl,
    Map<String, dynamic>? payload,
    DateTime? watchedAt,
  }) : payload = payload ?? const {},
       watchedAt = watchedAt ?? DateTime.now();

  @override
  final String playlistId;
  @override
  final MediaKind kind;
  @override
  final String refId;

  final String title;
  final String? imageUrl;
  final Map<String, dynamic> payload;
  final DateTime watchedAt;

  Map<String, dynamic> toJson() => {
    'playlist_id': playlistId,
    'kind': kind.wire,
    'ref_id': refId,
    'title': title,
    'image_url': imageUrl,
    'payload': payload,
    'watched_at': watchedAt.toIso8601String(),
  };

  factory HistoryItem.fromJson(Map<String, dynamic> json) => HistoryItem(
    playlistId: JsonX.asString(json['playlist_id']),
    kind: MediaKind.fromWire(JsonX.asStringOrNull(json['kind'])),
    refId: JsonX.asString(json['ref_id']),
    title: JsonX.asString(json['title']),
    imageUrl: JsonX.asStringOrNull(json['image_url']),
    payload: _payload(json['payload']),
    watchedAt:
        DateTime.tryParse(JsonX.asString(json['watched_at'])) ?? DateTime.now(),
  );
}

/// A resumable playback position for a movie or episode.
class ContinueWatchingItem with MediaRefMixin {
  ContinueWatchingItem({
    required this.playlistId,
    required this.kind,
    required this.refId,
    required this.title,
    required this.positionSecs,
    required this.durationSecs,
    this.imageUrl,
    Map<String, dynamic>? payload,
    DateTime? updatedAt,
  }) : payload = payload ?? const {},
       updatedAt = updatedAt ?? DateTime.now();

  @override
  final String playlistId;
  @override
  final MediaKind kind;
  @override
  final String refId;

  final String title;
  final String? imageUrl;
  final int positionSecs;
  final int durationSecs;
  final Map<String, dynamic> payload;
  final DateTime updatedAt;

  double get progress {
    if (durationSecs <= 0) return 0;
    return (positionSecs / durationSecs).clamp(0.0, 1.0);
  }

  /// Considered "finished" past 92% — such items drop off the row.
  bool get isFinished => progress >= 0.92;

  Duration get position => Duration(seconds: positionSecs);

  Map<String, dynamic> toJson() => {
    'playlist_id': playlistId,
    'kind': kind.wire,
    'ref_id': refId,
    'title': title,
    'image_url': imageUrl,
    'position_secs': positionSecs,
    'duration_secs': durationSecs,
    'payload': payload,
    'updated_at': updatedAt.toIso8601String(),
  };

  factory ContinueWatchingItem.fromJson(Map<String, dynamic> json) =>
      ContinueWatchingItem(
        playlistId: JsonX.asString(json['playlist_id']),
        kind: MediaKind.fromWire(JsonX.asStringOrNull(json['kind'])),
        refId: JsonX.asString(json['ref_id']),
        title: JsonX.asString(json['title']),
        imageUrl: JsonX.asStringOrNull(json['image_url']),
        positionSecs: JsonX.asInt(json['position_secs']),
        durationSecs: JsonX.asInt(json['duration_secs']),
        payload: _payload(json['payload']),
        updatedAt:
            DateTime.tryParse(JsonX.asString(json['updated_at'])) ??
            DateTime.now(),
      );
}

Map<String, dynamic> _payload(dynamic raw) {
  if (raw is Map) return Map<String, dynamic>.from(raw);
  return <String, dynamic>{};
}
