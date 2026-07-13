import 'dart:io';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../core/config/app_config.dart';
import '../core/utils/app_logger.dart';
import '../providers/core_providers.dart';
import '../services/cache/cache_service.dart';
import '../services/device/device_service.dart';
import '../services/storage/secure_storage_service.dart';
import '../services/supabase/supabase_service.dart';
import 'launch_args.dart';

/// Where the cache and the library live on disk.
///
/// `Hive.initFlutter()` would put them under `getApplicationDocumentsDirectory()`
/// — which on Linux is **the user's Documents folder**, localised: the first run
/// of this app created `~/Dokumente/moplayer/`. That is not a bug in Hive; it is
/// path_provider faithfully answering a question that only makes sense on iOS. On
/// a freedesktop system, application state belongs in `$XDG_DATA_HOME`, and a
/// video player has no business writing a lock file into a folder the user
/// backs up and syncs.
String _appDataDir() {
  final xdg = Platform.environment['XDG_DATA_HOME'];
  final base = (xdg != null && xdg.isNotEmpty)
      ? xdg
      : '${Platform.environment['HOME'] ?? '.'}/.local/share';
  final dir = Directory('$base/moplayer');
  dir.createSync(recursive: true);
  return dir.path;
}

/// What the app needs before it can draw a single frame.
class Boot {
  const Boot(this.overrides);
  final List<Override> overrides;
}

/// Open the stores, learn who this machine is, and find out whether there is a
/// source to log in with — all before the first frame, so the app never shows a
/// spinner for state it already has on disk.
///
/// Nothing in here is allowed to be fatal. A MoOS install with no keyring, no
/// network and no cloud must still start into a usable player.
Future<Boot> bootstrap(LaunchArgs launch) async {
  final secure = SecureStorageService();

  final cache = CacheService();
  await cache.init(path: _appDataDir());

  final device = DeviceService(secure);
  await device.init();

  final supabase = SupabaseService(enabled: AppConfig.hasSupabase);
  if (AppConfig.hasSupabase) {
    try {
      await Supabase.initialize(
        url: AppConfig.supabaseUrl,
        publishableKey: AppConfig.supabasePublishableKey,
        debug: false,
      );
      await supabase.ensureSession();
      await supabase.upsertDevice(
        deviceId: device.deviceId,
        model: device.model,
        os: device.osVersion,
        appVersion: device.appVersion,
      );
    } on Object catch (e) {
      // Cloud sync is a convenience. Losing it costs the user nothing they can
      // see except a stale favourites list on their other device.
      log.w('cloud unavailable, continuing local-only: $e');
    }
  }

  // A playlist opened from the file manager wins over whatever was active: the
  // user just double-clicked it, so it is what they want to see.
  var active = await secure.readActivePlaylist();
  if (launch.playlist != null) {
    final saved = await secure.readPlaylists();
    await secure.writePlaylists([
      ...saved.where((p) => p.m3uUrl != launch.playlist!.m3uUrl),
      launch.playlist!,
    ]);
    await secure.writeActivePlaylist(launch.playlist);
    active = launch.playlist;
  }

  log.i(
    'boot: device=${device.deviceId} source=${active?.name ?? "none"} '
    'route=${launch.initialRoute} '
    'moos=${AppConfig.isMoOS} plasma=${AppConfig.isPlasma} wayland=${AppConfig.isWayland}',
  );

  return Boot([
    cacheServiceProvider.overrideWithValue(cache),
    secureStorageProvider.overrideWithValue(secure),
    supabaseServiceProvider.overrideWithValue(supabase),
    deviceServiceProvider.overrideWithValue(device),
    initialActivePlaylistProvider.overrideWithValue(active),
    launchArgsProvider.overrideWithValue(launch),
  ]);
}
