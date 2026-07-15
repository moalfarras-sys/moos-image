import 'dart:io';
import 'dart:math';

import 'package:device_info_plus/device_info_plus.dart';
import 'package:flutter/foundation.dart';
import 'package:package_info_plus/package_info_plus.dart';

import '../../core/config/app_config.dart';
import '../../core/constants/app_constants.dart';
import '../../core/utils/app_logger.dart';

/// Provides a stable per-install device id plus human-readable device + app
/// metadata for the Settings screen and for the activation flow.
///
/// The id is a random, opaque install token — **not a secret**. It lives in a
/// plain file under the app's data directory, deliberately NOT in the keyring:
/// a first launch on a MoOS live session must never have to create a wallet just
/// to mint an id, and a dismissed wallet prompt must never be able to abort boot.
/// The keyring is reserved for real Xtream credentials (see SecureStorageService).
class DeviceService {
  DeviceService(this._dataDir);

  /// Application data directory (the same `$XDG_DATA_HOME/moplayer` the cache
  /// uses) — supplied by bootstrap so this service owns no path logic of its own.
  final String _dataDir;

  String? _cachedId;
  String _model = 'Unknown device';
  String _osVersion = '';
  String _appVersion = '';
  String _buildNumber = '';

  String get model => _model;
  String get osVersion => _osVersion;
  String get appVersion => _appVersion;
  String get buildNumber => _buildNumber;
  String get deviceId => _cachedId ?? 'unknown';

  File get _idFile => File('$_dataDir/${StorageKeys.deviceId}');

  Future<void> init() async {
    _cachedId = await _ensureDeviceId();
    await _loadMetadata();
  }

  Future<String> _ensureDeviceId() async {
    try {
      if (await _idFile.exists()) {
        final existing = (await _idFile.readAsString()).trim();
        if (RegExp(r'^MO-D-[A-Z0-9-]{8,40}$').hasMatch(existing)) {
          return existing;
        }
      }
    } catch (e) {
      log.w('could not read device id, minting a fresh one: $e');
    }
    final id = _generateId();
    try {
      await _idFile.writeAsString(id);
    } catch (e) {
      // A read-only or full disk costs us persistence, not a working session:
      // the id stays valid in memory for as long as the app runs.
      log.w('could not persist device id (staying in-memory only): $e');
    }
    return id;
  }

  String _generateId() {
    final rng = Random.secure();
    final bytes = List<int>.generate(16, (_) => rng.nextInt(256));
    final hex = bytes.map((b) => b.toRadixString(16).padLeft(2, '0')).join();
    return 'MO-D-${hex.substring(0, 8).toUpperCase()}-${hex.substring(8, 16).toUpperCase()}-${AppConfig.platform.toUpperCase()}';
  }

  Future<void> _loadMetadata() async {
    try {
      final info = await PackageInfo.fromPlatform();
      _appVersion = info.version;
      _buildNumber = info.buildNumber;
    } catch (_) {
      _appVersion = '1.0.0';
      _buildNumber = '1';
    }

    try {
      final plugin = DeviceInfoPlugin();
      if (kIsWeb) {
        final web = await plugin.webBrowserInfo;
        _model = web.browserName.name;
        _osVersion = web.platform ?? 'Web';
      } else if (defaultTargetPlatform == TargetPlatform.iOS) {
        final ios = await plugin.iosInfo;
        _model = ios.utsname.machine;
        _osVersion = 'iOS ${ios.systemVersion}';
      } else if (defaultTargetPlatform == TargetPlatform.android) {
        final android = await plugin.androidInfo;
        _model = '${android.manufacturer} ${android.model}';
        _osVersion = 'Android ${android.version.release}';
      } else {
        _model = defaultTargetPlatform.name;
        _osVersion = '';
      }
    } catch (_) {
      // Metadata is non-critical.
    }
  }
}
