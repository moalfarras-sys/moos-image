import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../../core/constants/app_constants.dart';
import '../../models/playlist_config.dart';

/// Encrypted storage for sensitive values — playlist credentials and the
/// device id. Backed by the iOS Keychain on device.
class SecureStorageService {
  SecureStorageService([FlutterSecureStorage? storage])
    : _storage =
          storage ??
          const FlutterSecureStorage(
            aOptions: AndroidOptions(encryptedSharedPreferences: true),
            iOptions: IOSOptions(
              accessibility: KeychainAccessibility.first_unlock,
            ),
          );

  final FlutterSecureStorage _storage;

  // --- Playlists -----------------------------------------------------------

  Future<List<PlaylistConfig>> readPlaylists() async {
    final raw = await _storage.read(key: StorageKeys.playlists);
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

  Future<void> writePlaylists(List<PlaylistConfig> playlists) async {
    final encoded = jsonEncode(playlists.map((e) => e.toJson()).toList());
    await _storage.write(key: StorageKeys.playlists, value: encoded);
  }

  Future<PlaylistConfig?> readActivePlaylist() async {
    final raw = await _storage.read(key: StorageKeys.activePlaylist);
    if (raw == null || raw.isEmpty) return null;
    try {
      return PlaylistConfig.fromJson(
        Map<String, dynamic>.from(jsonDecode(raw) as Map),
      );
    } catch (_) {
      return null;
    }
  }

  Future<void> writeActivePlaylist(PlaylistConfig? config) async {
    if (config == null) {
      await _storage.delete(key: StorageKeys.activePlaylist);
      return;
    }
    await _storage.write(
      key: StorageKeys.activePlaylist,
      value: jsonEncode(config.toJson()),
    );
  }

  // --- Device id -----------------------------------------------------------

  Future<String?> readDeviceId() => _storage.read(key: StorageKeys.deviceId);

  Future<void> writeDeviceId(String id) =>
      _storage.write(key: StorageKeys.deviceId, value: id);

  Future<void> clearAll() async {
    await _storage.delete(key: StorageKeys.activePlaylist);
    await _storage.delete(key: StorageKeys.playlists);
  }
}
