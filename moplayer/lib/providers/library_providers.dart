import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/library_items.dart';
import '../models/media_kind.dart';
import '../repositories/favorites_repository.dart';
import '../repositories/history_repository.dart';
import 'core_providers.dart';

final favoritesRepositoryProvider = Provider<FavoritesRepository>((ref) {
  return FavoritesRepository(
    ref.watch(cacheServiceProvider),
    ref.watch(supabaseServiceProvider),
  );
});

final historyRepositoryProvider = Provider<HistoryRepository>((ref) {
  return HistoryRepository(
    ref.watch(cacheServiceProvider),
    ref.watch(supabaseServiceProvider),
  );
});

final continueWatchingRepositoryProvider = Provider<ContinueWatchingRepository>(
  (ref) {
    return ContinueWatchingRepository(
      ref.watch(cacheServiceProvider),
      ref.watch(supabaseServiceProvider),
    );
  },
);

/// Bumped after any library mutation so the read providers below recompute.
final libraryRefreshProvider = StateProvider<int>((ref) => 0);

final favoritesProvider = Provider<List<FavoriteItem>>((ref) {
  ref.watch(libraryRefreshProvider);
  final cfg = ref.watch(activePlaylistProvider);
  if (cfg == null) return const [];
  return ref.watch(favoritesRepositoryProvider).all(cfg.id);
});

final continueWatchingProvider = Provider<List<ContinueWatchingItem>>((ref) {
  ref.watch(libraryRefreshProvider);
  final cfg = ref.watch(activePlaylistProvider);
  if (cfg == null) return const [];
  return ref.watch(continueWatchingRepositoryProvider).all(cfg.id);
});

final historyProvider = Provider<List<HistoryItem>>((ref) {
  ref.watch(libraryRefreshProvider);
  final cfg = ref.watch(activePlaylistProvider);
  if (cfg == null) return const [];
  return ref.watch(historyRepositoryProvider).all(cfg.id);
});

/// Centralised, ref-aware library mutations that keep the UI in sync.
final libraryActionsProvider = Provider<LibraryActions>(LibraryActions.new);

class LibraryActions {
  LibraryActions(this._ref);
  final Ref _ref;

  bool isFavorite(MediaKind kind, String refId) {
    final cfg = _ref.read(activePlaylistProvider);
    if (cfg == null) return false;
    return _ref
        .read(favoritesRepositoryProvider)
        .isFavorite(cfg.id, kind, refId);
  }

  Future<bool> toggleFavorite(FavoriteItem item) async {
    final now = await _ref.read(favoritesRepositoryProvider).toggle(item);
    _bump();
    return now;
  }

  Future<void> removeFavorite(MediaKind kind, String refId) async {
    final cfg = _ref.read(activePlaylistProvider);
    if (cfg == null) return;
    await _ref.read(favoritesRepositoryProvider).remove(cfg.id, kind, refId);
    _bump();
  }

  Future<void> recordHistory(HistoryItem item) async {
    await _ref.read(historyRepositoryProvider).record(item);
    _bump();
  }

  Future<void> clearHistory() async {
    await _ref.read(historyRepositoryProvider).clear();
    _bump();
  }

  Future<void> saveProgress(ContinueWatchingItem item) async {
    await _ref.read(continueWatchingRepositoryProvider).save(item);
    _bump();
  }

  Future<void> removeContinue(MediaKind kind, String refId) async {
    final cfg = _ref.read(activePlaylistProvider);
    if (cfg == null) return;
    await _ref
        .read(continueWatchingRepositoryProvider)
        .remove(cfg.id, kind, refId);
    _bump();
  }

  Duration resumePosition(MediaKind kind, String refId) {
    final cfg = _ref.read(activePlaylistProvider);
    if (cfg == null) return Duration.zero;
    return _ref
        .read(continueWatchingRepositoryProvider)
        .resumePosition(cfg.id, kind, refId);
  }

  /// Pulls the user's cloud library into the local store (no-op without
  /// Supabase). Safe to call on every launch.
  Future<void> syncFromCloud() async {
    final cfg = _ref.read(activePlaylistProvider);
    if (cfg == null) return;
    await _ref.read(favoritesRepositoryProvider).syncFromCloud(cfg.id);
    await _ref.read(historyRepositoryProvider).syncFromCloud(cfg.id);
    await _ref.read(continueWatchingRepositoryProvider).syncFromCloud(cfg.id);
    _bump();
  }

  void _bump() => _ref.read(libraryRefreshProvider.notifier).state++;
}
