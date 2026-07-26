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

/// Separate invalidation counters.
///
/// Playback persists a continue position every few seconds. A single shared
/// counter used to make that tiny write also decode favourites and history,
/// then rebuild every consumer of them under the full-screen video. Keep each
/// shelf reactive without turning a progress tick into a library-wide refresh.
final favoritesRefreshProvider = StateProvider<int>((ref) => 0);
final historyRefreshProvider = StateProvider<int>((ref) => 0);
final continueRefreshProvider = StateProvider<int>((ref) => 0);

final favoritesProvider = Provider<List<FavoriteItem>>((ref) {
  ref.watch(favoritesRefreshProvider);
  final cfg = ref.watch(activePlaylistProvider);
  if (cfg == null) return const [];
  return ref.watch(favoritesRepositoryProvider).all(cfg.id);
});

final continueWatchingProvider = Provider<List<ContinueWatchingItem>>((ref) {
  ref.watch(continueRefreshProvider);
  final cfg = ref.watch(activePlaylistProvider);
  if (cfg == null) return const [];
  return ref.watch(continueWatchingRepositoryProvider).all(cfg.id);
});

final historyProvider = Provider<List<HistoryItem>>((ref) {
  ref.watch(historyRefreshProvider);
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
    _bumpFavorites();
    return now;
  }

  Future<void> removeFavorite(MediaKind kind, String refId) async {
    final cfg = _ref.read(activePlaylistProvider);
    if (cfg == null) return;
    await _ref.read(favoritesRepositoryProvider).remove(cfg.id, kind, refId);
    _bumpFavorites();
  }

  Future<void> recordHistory(HistoryItem item) async {
    await _ref.read(historyRepositoryProvider).record(item);
    _bumpHistory();
  }

  Future<void> clearHistory() async {
    await _ref.read(historyRepositoryProvider).clear();
    _bumpHistory();
  }

  Future<void> saveProgress(ContinueWatchingItem item) async {
    await _ref.read(continueWatchingRepositoryProvider).save(item);
    _bumpContinue();
  }

  Future<void> removeContinue(MediaKind kind, String refId) async {
    final cfg = _ref.read(activePlaylistProvider);
    if (cfg == null) return;
    await _ref
        .read(continueWatchingRepositoryProvider)
        .remove(cfg.id, kind, refId);
    _bumpContinue();
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
    _bumpFavorites();
    _bumpHistory();
    _bumpContinue();
  }

  void _bumpFavorites() => _ref.read(favoritesRefreshProvider.notifier).state++;
  void _bumpHistory() => _ref.read(historyRefreshProvider.notifier).state++;
  void _bumpContinue() => _ref.read(continueRefreshProvider.notifier).state++;
}
