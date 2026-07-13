import 'dart:math';

import 'package:device_info_plus/device_info_plus.dart';
import 'package:flutter/foundation.dart';
import 'package:package_info_plus/package_info_plus.dart';

import '../../core/config/app_config.dart';
import '../storage/secure_storage_service.dart';

/// Provides a stable per-install device id (persisted in the Keychain) plus
/// human-readable device + app metadata for the Settings screen and for the
/// activation flow.
class DeviceService {
  DeviceService(this._secureStorage);

  final SecureStorageService _secureStorage;

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

  Future<void> init() async {
    _cachedId = await _ensureDeviceId();
    await _loadMetadata();
  }

  Future<String> _ensureDeviceId() async {
    final existing = await _secureStorage.readDeviceId();
    if (existing != null &&
        RegExp(r'^MO-D-[A-Z0-9-]{8,40}$').hasMatch(existing)) {
      return existing;
    }
    final id = _generateId();
    await _secureStorage.writeDeviceId(id);
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
