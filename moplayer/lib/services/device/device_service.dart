import 'dart:io';
import 'dart:math';

import 'package:device_info_plus/device_info_plus.dart';
import 'package:flutter/foundation.dart';
import 'package:package_info_plus/package_info_plus.dart';

import '../../core/config/app_config.dart';
import '../storage/secure_storage_service.dart';

/// Provides a stable per-install device id (persisted in private app storage)
/// plus
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

  static final RegExp _idShape = RegExp(r'^MO-D-[A-Z0-9-]{8,40}$');

  /// The device id must be STABLE, and it must never be able to stop the app.
  ///
  /// It used to live in KWallet and nowhere else. Merely reading it could open
  /// a wallet password dialog before the first frame. MoPlayer now owns a
  /// private 0600 store and never contacts Secret Service.
  ///
  /// The id is an identifier, not a credential, so the fallback is an ordinary
  /// file beside the cache. Without it, a machine with unwritable private
  /// storage would invent a new identity on every launch.
  Future<String> _ensureDeviceId() async {
    final stored = await _secureStorage.readDeviceId();
    if (stored != null && _idShape.hasMatch(stored)) {
      return stored;
    }

    final onDisk = _readIdFile();
    if (onDisk != null && _idShape.hasMatch(onDisk)) {
      // Promote the legacy fallback into the private application store.
      await _secureStorage.writeDeviceId(onDisk);
      return onDisk;
    }

    final id = _generateId();
    final storedPrivately = await _secureStorage.writeDeviceId(id);
    if (!storedPrivately) {
      _writeIdFile(id);
    }
    return id;
  }

  /// `$XDG_DATA_HOME/moplayer/device-id` — the same base the cache uses.
  File _idFile() {
    final xdg = Platform.environment['XDG_DATA_HOME'];
    final base = (xdg != null && xdg.isNotEmpty)
        ? xdg
        : '${Platform.environment['HOME'] ?? '.'}/.local/share';
    return File('$base/moplayer/device-id');
  }

  String? _readIdFile() {
    try {
      final file = _idFile();
      if (!file.existsSync()) return null;
      return file.readAsStringSync().trim();
    } on Object {
      return null;
    }
  }

  void _writeIdFile(String id) {
    try {
      final file = _idFile();
      file.parent.createSync(recursive: true);
      file.writeAsStringSync('$id\n', flush: true);
    } on Object catch (e) {
      // Not fatal either: a session-scoped id still beats no app at all.
      debugPrint('DeviceService: could not persist the device id: $e');
    }
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
