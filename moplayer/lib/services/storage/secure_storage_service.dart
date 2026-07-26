import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';

import '../../core/constants/app_constants.dart';
import '../../models/playlist_config.dart';

/// Private, application-owned storage for playlist credentials and the device
/// id.
///
/// MoPlayer deliberately does not use Secret Service/libsecret on Linux. On
/// Plasma that service is backed by KWallet, so merely starting the player can
/// open a wallet password dialog. An IPTV player must not interrupt login with
/// an unrelated desktop prompt.
///
/// The store lives below `$XDG_DATA_HOME/moplayer/private`, the directory is
/// mode 0700 and the JSON file is mode 0600. Writes use a same-directory
/// temporary file followed by an atomic rename, so losing power cannot leave a
/// half-written account list. If any filesystem or permission operation fails,
/// the service stays alive in memory and [degraded] becomes true; bootstrap is
/// never allowed to fail because local persistence is unavailable.
class SecureStorageService {
  SecureStorageService({String? filePath})
    : _file = File(filePath ?? _defaultFilePath());

  final File _file;

  Map<String, String>? _values;
  Future<void> _pending = Future<void>.value();
  bool _degraded = false;

  bool get degraded => _degraded;

  /// Useful to explain persistence failures without exposing any credential.
  String get storageDirectory => _file.parent.path;

  static String _defaultFilePath() {
    final xdg = Platform.environment['XDG_DATA_HOME'];
    final base = (xdg != null && xdg.isNotEmpty)
        ? xdg
        : '${Platform.environment['HOME'] ?? '.'}/.local/share';
    return '$base/moplayer/private/credentials.json';
  }

  Future<T> _serial<T>(Future<T> Function() action) {
    final result = _pending.then((_) => action());
    _pending = result.then<void>((_) {}, onError: (_) {});
    return result;
  }

  Future<void> _load() async {
    if (_values != null) return;

    try {
      await _prepareDirectory();
      if (!await _file.exists()) {
        _values = <String, String>{};
        return;
      }
      await _setMode(_file.path, '0600');
      final raw = await _file.readAsString();
      if (raw.trim().isEmpty) {
        _values = <String, String>{};
        return;
      }
      final decoded = jsonDecode(raw);
      if (decoded is! Map) throw const FormatException('expected an object');
      _values = decoded.map(
        (key, value) => MapEntry(key.toString(), value.toString()),
      );
    } on Object catch (error) {
      _values = <String, String>{};
      _markDegraded('read', error);
    }
  }

  Future<void> _prepareDirectory() async {
    await _file.parent.create(recursive: true);
    await _setMode(_file.parent.path, '0700');
  }

  Future<void> _setMode(String path, String mode) async {
    if (!Platform.isLinux && !Platform.isMacOS) return;
    final result = await Process.run('/usr/bin/chmod', [mode, '--', path]);
    if (result.exitCode != 0) {
      throw FileSystemException('could not set private permissions', path);
    }
  }

  Future<String?> _read(String key) => _serial(() async {
    await _load();
    return _values![key];
  });

  Future<bool> _write(String key, String value) => _serial(() async {
    await _load();
    if (_degraded) return false;
    _values![key] = value;
    return _persist();
  });

  Future<bool> _delete(String key) => _serial(() async {
    await _load();
    if (_degraded) return false;
    if (_values!.remove(key) == null) return true;
    return _persist();
  });

  Future<bool> _persist() async {
    final temporary = File(
      '${_file.path}.tmp-${pid.toString()}-${DateTime.now().microsecondsSinceEpoch}',
    );
    try {
      await _prepareDirectory();
      await temporary.create();
      await _setMode(temporary.path, '0600');
      await temporary.writeAsString(jsonEncode(_values), flush: true);
      await temporary.rename(_file.path);
      await _setMode(_file.path, '0600');
      return true;
    } on Object catch (error) {
      try {
        if (await temporary.exists()) await temporary.delete();
      } on Object {
        // The original persistence error is the useful one.
      }
      _markDegraded('write', error);
      return false;
    }
  }

  void _markDegraded(String operation, Object error) {
    final first = !_degraded;
    _degraded = true;
    if (first) {
      debugPrint(
        'PrivateStorage: $operation failed ($error). '
        'Changes remain session-only; MoPlayer will continue.',
      );
    }
  }

  // --- Playlists -----------------------------------------------------------

  Future<List<PlaylistConfig>> readPlaylists() async {
    final raw = await _read(StorageKeys.playlists);
    if (raw == null || raw.isEmpty) return const [];
    try {
      final list = jsonDecode(raw) as List<dynamic>;
      return list
          .whereType<Map>()
          .map((e) => PlaylistConfig.fromJson(Map<String, dynamic>.from(e)))
          .toList();
    } catch (_) {
      return const [];
    }
  }

  Future<bool> writePlaylists(List<PlaylistConfig> playlists) async {
    final encoded = jsonEncode(playlists.map((e) => e.toJson()).toList());
    return _write(StorageKeys.playlists, encoded);
  }

  Future<PlaylistConfig?> readActivePlaylist() async {
    final raw = await _read(StorageKeys.activePlaylist);
    if (raw == null || raw.isEmpty) return null;
    try {
      return PlaylistConfig.fromJson(
        Map<String, dynamic>.from(jsonDecode(raw) as Map),
      );
    } catch (_) {
      return null;
    }
  }

  Future<bool> writeActivePlaylist(PlaylistConfig? config) async {
    if (config == null) return _delete(StorageKeys.activePlaylist);
    return _write(StorageKeys.activePlaylist, jsonEncode(config.toJson()));
  }

  // --- Device id -----------------------------------------------------------

  Future<String?> readDeviceId() => _read(StorageKeys.deviceId);

  Future<bool> writeDeviceId(String id) => _write(StorageKeys.deviceId, id);

  Future<void> clearAll() async {
    await _delete(StorageKeys.activePlaylist);
    await _delete(StorageKeys.playlists);
  }
}
