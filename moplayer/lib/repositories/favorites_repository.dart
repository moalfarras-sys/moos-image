import '../models/library_items.dart';
import '../models/media_kind.dart';
import '../services/cache/cache_service.dart';
import '../services/supabase/supabase_service.dart';

/// Favourites, persisted locally (always) and synced to Supabase when enabled.
class FavoritesRepository {
  FavoritesRepository(this._cache, this._supabase);

  final CacheService _cache;
  final SupabaseService _supabase;

  static const _table = 'favorites';
  static const _conflict = 'user_id,playlist_id,kind,ref_id';

  List<FavoriteItem> all(String playlistId) {
    final items =
        _cache
            .readBox(_cache.favorites)
            .map(FavoriteItem.fromJson)
            .where((f) => f.playlistId == playlistId)
            .toList()
          ..sort((a, b) => b.createdAt.compareTo(a.createdAt));
    return items;
  }

  List<FavoriteItem> ofKind(String playlistId, MediaKind kind) =>
      all(playlistId).where((f) => f.kind == kind).toList();

  bool isFavorite(String playlistId, MediaKind kind, String refId) {
    final key = '$playlistId:${kind.wire}:$refId';
    return _cache.favorites.containsKey(key);
  }

  Future<void> add(FavoriteItem item) async {
    await _cache.putBoxItem(_cache.favorites, item.key, item.toJson());
    await _supabase.upsertRow(_table, item.toJson(), onConflict: _conflict);
  }

  Future<void> remove(String playlistId, MediaKind kind, String refId) async {
    final key = '$playlistId:${kind.wire}:$refId';
    await _cache.deleteBoxItem(_cache.favorites, key);
    await _supabase.deleteRow(
      _table,
      playlistId: playlistId,
      kind: kind.wire,
      refId: refId,
    );
  }

  /// Returns the new favourite state (true = now favourited).
  Future<bool> toggle(FavoriteItem item) async {
    if (isFavorite(item.playlistId, item.kind, item.refId)) {
      await remove(item.playlistId, item.kind, item.refId);
      return false;
    }
    await add(item);
    return true;
  }

  /// Pulls cloud favourites into the local store on login / first launch.
  Future<void> syncFromCloud(String playlistId) async {
    if (!_supabase.enabled) return;
    final rows = await _supabase.fetchRows(_table, playlistId: playlistId);
    for (final row in rows) {
      final item = FavoriteItem.fromJson(row);
      await _cache.putBoxItem(_cache.favorites, item.key, item.toJson());
    }
  }
}
