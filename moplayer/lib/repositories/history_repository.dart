import '../models/library_items.dart';
import '../models/media_kind.dart';
import '../services/cache/cache_service.dart';
import '../services/supabase/supabase_service.dart';

/// Watch history — a recency-ordered log of opened/played content.
class HistoryRepository {
  HistoryRepository(this._cache, this._supabase);

  final CacheService _cache;
  final SupabaseService _supabase;

  static const _table = 'watch_history';
  static const _conflict = 'user_id,playlist_id,kind,ref_id';
  static const _maxLocal = 200;

  List<HistoryItem> all(String playlistId) {
    final items =
        _cache
            .readBox(_cache.history)
            .map(HistoryItem.fromJson)
            .where((h) => h.playlistId == playlistId)
            .toList()
          ..sort((a, b) => b.watchedAt.compareTo(a.watchedAt));
    return items;
  }

  Future<void> record(HistoryItem item) async {
    await _cache.putBoxItem(_cache.history, item.key, item.toJson());
    await _supabase.upsertRow(_table, item.toJson(), onConflict: _conflict);
    await _trim();
  }

  Future<void> clear() async {
    await _cache.history.clear();
  }

  Future<void> _trim() async {
    final box = _cache.history;
    if (box.length <= _maxLocal) return;
    final entries = _cache.readBox(box).map(HistoryItem.fromJson).toList()
      ..sort((a, b) => a.watchedAt.compareTo(b.watchedAt));
    final excess = box.length - _maxLocal;
    for (var i = 0; i < excess; i++) {
      await box.delete(entries[i].key);
    }
  }

  Future<void> syncFromCloud(String playlistId) async {
    if (!_supabase.enabled) return;
    final rows = await _supabase.fetchRows(
      _table,
      playlistId: playlistId,
      orderBy: 'watched_at',
      limit: _maxLocal,
    );
    for (final row in rows) {
      final item = HistoryItem.fromJson(row);
      await _cache.putBoxItem(_cache.history, item.key, item.toJson());
    }
  }
}

/// Resumable playback positions for movies and episodes.
class ContinueWatchingRepository {
  ContinueWatchingRepository(this._cache, this._supabase);

  final CacheService _cache;
  final SupabaseService _supabase;

  static const _table = 'continue_watching';
  static const _conflict = 'user_id,playlist_id,kind,ref_id';

  List<ContinueWatchingItem> all(String playlistId) {
    final items =
        _cache
            .readBox(_cache.continueWatching)
            .map(ContinueWatchingItem.fromJson)
            .where((c) => c.playlistId == playlistId && !c.isFinished)
            .toList()
          ..sort((a, b) => b.updatedAt.compareTo(a.updatedAt));
    return items;
  }

  ContinueWatchingItem? find(String playlistId, MediaKind kind, String refId) {
    final key = '$playlistId:${kind.wire}:$refId';
    final raw = _cache.continueWatching.get(key);
    if (raw == null) return null;
    try {
      return all(playlistId).firstWhere((e) => e.key == key);
    } catch (_) {
      return null;
    }
  }

  Duration resumePosition(String playlistId, MediaKind kind, String refId) {
    final item = find(playlistId, kind, refId);
    if (item == null || item.isFinished) return Duration.zero;
    return item.position;
  }

  Future<void> save(ContinueWatchingItem item) async {
    if (item.isFinished) {
      await remove(item.playlistId, item.kind, item.refId);
      return;
    }
    await _cache.putBoxItem(_cache.continueWatching, item.key, item.toJson());
    await _supabase.upsertRow(_table, item.toJson(), onConflict: _conflict);
  }

  Future<void> remove(String playlistId, MediaKind kind, String refId) async {
    final key = '$playlistId:${kind.wire}:$refId';
    await _cache.deleteBoxItem(_cache.continueWatching, key);
    await _supabase.deleteRow(
      _table,
      playlistId: playlistId,
      kind: kind.wire,
      refId: refId,
    );
  }

  Future<void> syncFromCloud(String playlistId) async {
    if (!_supabase.enabled) return;
    final rows = await _supabase.fetchRows(
      _table,
      playlistId: playlistId,
      orderBy: 'updated_at',
    );
    for (final row in rows) {
      final item = ContinueWatchingItem.fromJson(row);
      await _cache.putBoxItem(_cache.continueWatching, item.key, item.toJson());
    }
  }
}
