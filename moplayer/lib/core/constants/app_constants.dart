/// App-wide constant keys for caches, preferences and secure storage.
class StorageKeys {
  const StorageKeys._();

  // Secure storage (encrypted) — real credentials only
  static const String activePlaylist = 'active_playlist';
  static const String playlists = 'saved_playlists';

  // Plain on-disk install token (NOT a secret). Kept out of the keyring so a
  // fresh MoOS live session never has to create a wallet just to mint an id —
  // see DeviceService.
  static const String deviceId = 'device_id';

  // Hive boxes
  static const String boxCache = 'mp_cache';
  static const String boxFavorites = 'mp_favorites';
  static const String boxHistory = 'mp_history';
  static const String boxContinue = 'mp_continue';
  static const String boxSettings = 'mp_settings';

  // Settings keys
  static const String lastLiveChannelId = 'last_live_channel_id';
  static const String preferHls = 'prefer_hls';
  static const String autoplayNext = 'autoplay_next';
  static const String rememberLastChannel = 'remember_last_channel';
  static const String compactLivePreview = 'compact_live_preview';
  static const String compactGrids = 'compact_grids';
  static const String syncOnLaunch = 'sync_on_launch';
  static const String cinematicMotion = 'cinematic_motion';

  // MoOS desktop settings
  static const String language = 'language';
  static const String keepAwake = 'keep_awake';
  static const String mediaKeys = 'media_keys';
  static const String lastVolume = 'last_volume';

  /// Where the window was when it was last closed, as `x,y,w,h,maximized`.
  /// Restored before the first frame — see `DesktopService.showWindow`.
  static const String windowGeometry = 'window_geometry';

  /// Start a channel preview when one is selected in the Live screen.
  static const String previewAutoplay = 'preview_autoplay';

  /// Recent search terms, newest first. Local only — a search history is one of
  /// the more revealing things an app can hold, and it never leaves the machine.
  static const String searchHistory = 'search_history';
}

/// Time-to-live for cached catalog responses before a refresh is suggested.
class CacheTtl {
  const CacheTtl._();

  static const Duration categories = Duration(hours: 12);
  static const Duration streams = Duration(hours: 6);
  static const Duration info = Duration(hours: 24);
}
