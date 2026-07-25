import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/playlist_config.dart';
import '../repositories/auth_repository.dart';
import '../repositories/settings_repository.dart';
import '../services/cache/cache_service.dart';
import '../services/device/device_service.dart';
import '../services/storage/secure_storage_service.dart';
import '../services/supabase/supabase_service.dart';

// --- Singletons (overridden in main with the bootstrapped instances) -------

final cacheServiceProvider = Provider<CacheService>(
  (ref) => throw UnimplementedError('cacheServiceProvider must be overridden'),
);

final secureStorageProvider = Provider<SecureStorageService>(
  (ref) => throw UnimplementedError('secureStorageProvider must be overridden'),
);

final supabaseServiceProvider = Provider<SupabaseService>(
  (ref) =>
      throw UnimplementedError('supabaseServiceProvider must be overridden'),
);

final deviceServiceProvider = Provider<DeviceService>(
  (ref) => throw UnimplementedError('deviceServiceProvider must be overridden'),
);

/// The active playlist loaded during bootstrap; overridden in main.
final initialActivePlaylistProvider = Provider<PlaylistConfig?>((ref) => null);

// --- Repositories --------------------------------------------------------

final authRepositoryProvider = Provider<AuthRepository>((ref) {
  return AuthRepository(
    ref.watch(secureStorageProvider),
    ref.watch(supabaseServiceProvider),
  );
});

final settingsRepositoryProvider = Provider<SettingsRepository>((ref) {
  return SettingsRepository(ref.watch(cacheServiceProvider));
});

// --- Active playlist state ------------------------------------------------

class ActivePlaylistController extends Notifier<PlaylistConfig?> {
  @override
  PlaylistConfig? build() => ref.watch(initialActivePlaylistProvider);

  /// Persists + activates a playlist and triggers a cloud sync of the user's
  /// library for that playlist.
  Future<bool> activate(PlaylistConfig config) async {
    final saved = await ref
        .read(authRepositoryProvider)
        .saveAndActivate(config);
    if (!saved) return false;
    state = config;
    return true;
  }

  Future<void> logout() async {
    await ref.read(authRepositoryProvider).logout();
    state = null;
  }

  Future<void> selectSource(PlaylistConfig config) async {
    await ref.read(authRepositoryProvider).setActive(config);
    state = config;
    ref.read(sourceListRefreshProvider.notifier).state++;
  }

  Future<void> removeSource(String id) async {
    await ref.read(authRepositoryProvider).removePlaylist(id);
    state = await ref.read(authRepositoryProvider).activePlaylist();
    ref.read(sourceListRefreshProvider.notifier).state++;
  }
}

final activePlaylistProvider =
    NotifierProvider<ActivePlaylistController, PlaylistConfig?>(
      ActivePlaylistController.new,
    );

final sourceListRefreshProvider = StateProvider<int>((ref) => 0);

final savedPlaylistsProvider = FutureProvider<List<PlaylistConfig>>((ref) {
  ref.watch(sourceListRefreshProvider);
  return ref.watch(authRepositoryProvider).playlists();
});

final isLoggedInProvider = Provider<bool>((ref) {
  return ref.watch(activePlaylistProvider) != null;
});

// --- Settings state -------------------------------------------------------

class SettingsController extends Notifier<AppSettings> {
  @override
  AppSettings build() => ref.watch(settingsRepositoryProvider).read();

  Future<void> setPreferHls(bool value) async {
    await ref.read(settingsRepositoryProvider).setPreferHls(value);
    state = state.copyWith(preferHls: value);
  }

  Future<void> setAutoplayNext(bool value) async {
    await ref.read(settingsRepositoryProvider).setAutoplayNext(value);
    state = state.copyWith(autoplayNext: value);
  }

  Future<void> setRememberLastChannel(bool value) async {
    await ref.read(settingsRepositoryProvider).setRememberLastChannel(value);
    state = state.copyWith(rememberLastChannel: value);
  }

  Future<void> setCompactLivePreview(bool value) async {
    await ref.read(settingsRepositoryProvider).setCompactLivePreview(value);
    state = state.copyWith(compactLivePreview: value);
  }

  Future<void> setCompactGrids(bool value) async {
    await ref.read(settingsRepositoryProvider).setCompactGrids(value);
    state = state.copyWith(compactGrids: value);
  }

  Future<void> setSyncOnLaunch(bool value) async {
    await ref.read(settingsRepositoryProvider).setSyncOnLaunch(value);
    state = state.copyWith(syncOnLaunch: value);
  }

  Future<void> setCinematicMotion(bool value) async {
    await ref.read(settingsRepositoryProvider).setCinematicMotion(value);
    state = state.copyWith(cinematicMotion: value);
  }

  Future<void> setKeepAwake(bool value) async {
    await ref.read(settingsRepositoryProvider).setKeepAwake(value);
    state = state.copyWith(keepAwake: value);
  }

  Future<void> setMediaKeys(bool value) async {
    await ref.read(settingsRepositoryProvider).setMediaKeys(value);
    state = state.copyWith(mediaKeys: value);
  }
}

final settingsProvider = NotifierProvider<SettingsController, AppSettings>(
  SettingsController.new,
);
