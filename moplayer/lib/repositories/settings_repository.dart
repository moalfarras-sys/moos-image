import '../core/constants/app_constants.dart';
import '../services/cache/cache_service.dart';

/// Player / app preferences persisted in the local settings box.
class AppSettings {
  const AppSettings({
    this.preferHls = true,
    this.autoplayNext = true,
    this.rememberLastChannel = true,
    this.compactLivePreview = true,
    this.compactGrids = true,
    this.syncOnLaunch = true,
    this.cinematicMotion = true,
    this.keepAwake = true,
    this.mediaKeys = true,
  });

  final bool preferHls;
  final bool autoplayNext;
  final bool rememberLastChannel;
  final bool compactLivePreview;
  final bool compactGrids;
  final bool syncOnLaunch;
  final bool cinematicMotion;

  /// Inhibit the screen-saver while a video is playing.
  final bool keepAwake;

  /// Publish MPRIS2, which is what binds the keyboard's media keys and Plasma's
  /// media applet to this player.
  final bool mediaKeys;

  AppSettings copyWith({
    bool? preferHls,
    bool? autoplayNext,
    bool? rememberLastChannel,
    bool? compactLivePreview,
    bool? compactGrids,
    bool? syncOnLaunch,
    bool? cinematicMotion,
    bool? keepAwake,
    bool? mediaKeys,
  }) => AppSettings(
    preferHls: preferHls ?? this.preferHls,
    autoplayNext: autoplayNext ?? this.autoplayNext,
    rememberLastChannel: rememberLastChannel ?? this.rememberLastChannel,
    compactLivePreview: compactLivePreview ?? this.compactLivePreview,
    compactGrids: compactGrids ?? this.compactGrids,
    syncOnLaunch: syncOnLaunch ?? this.syncOnLaunch,
    cinematicMotion: cinematicMotion ?? this.cinematicMotion,
    keepAwake: keepAwake ?? this.keepAwake,
    mediaKeys: mediaKeys ?? this.mediaKeys,
  );
}

class SettingsRepository {
  SettingsRepository(this._cache);

  final CacheService _cache;

  AppSettings read() => AppSettings(
    preferHls: _cache.settingOr(StorageKeys.preferHls, true),
    autoplayNext: _cache.settingOr(StorageKeys.autoplayNext, true),
    rememberLastChannel: _cache.settingOr(
      StorageKeys.rememberLastChannel,
      true,
    ),
    compactLivePreview: _cache.settingOr(StorageKeys.compactLivePreview, true),
    compactGrids: _cache.settingOr(StorageKeys.compactGrids, true),
    syncOnLaunch: _cache.settingOr(StorageKeys.syncOnLaunch, true),
    cinematicMotion: _cache.settingOr(StorageKeys.cinematicMotion, true),
    keepAwake: _cache.settingOr(StorageKeys.keepAwake, true),
    mediaKeys: _cache.settingOr(StorageKeys.mediaKeys, true),
  );

  Future<void> setKeepAwake(bool value) =>
      _cache.setSetting(StorageKeys.keepAwake, value);

  Future<void> setMediaKeys(bool value) =>
      _cache.setSetting(StorageKeys.mediaKeys, value);

  Future<void> setPreferHls(bool value) =>
      _cache.setSetting(StorageKeys.preferHls, value);

  Future<void> setAutoplayNext(bool value) =>
      _cache.setSetting(StorageKeys.autoplayNext, value);

  Future<void> setRememberLastChannel(bool value) =>
      _cache.setSetting(StorageKeys.rememberLastChannel, value);

  Future<void> setCompactLivePreview(bool value) =>
      _cache.setSetting(StorageKeys.compactLivePreview, value);

  Future<void> setCompactGrids(bool value) =>
      _cache.setSetting(StorageKeys.compactGrids, value);

  Future<void> setSyncOnLaunch(bool value) =>
      _cache.setSetting(StorageKeys.syncOnLaunch, value);

  Future<void> setCinematicMotion(bool value) =>
      _cache.setSetting(StorageKeys.cinematicMotion, value);

  String? get lastLiveChannelId =>
      _cache.settingOr<String?>(StorageKeys.lastLiveChannelId, null);

  Future<void> setLastLiveChannelId(String id) =>
      _cache.setSetting(StorageKeys.lastLiveChannelId, id);

  Future<void> clearCache() => _cache.clearCatalogCache();

  Future<void> wipeAll() => _cache.wipeUserData();
}
