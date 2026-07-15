import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../../core/constants/app_constants.dart';
import '../../core/utils/app_logger.dart';
import '../../models/playlist_config.dart';

/// Encrypted storage for the only things that truly need it: playlist
/// credentials (an Xtream account's username + password). Backed by the iOS
/// Keychain on device and the Secret Service (KWallet / gnome-keyring) on the
/// Linux desktop.
///
/// Every access here is best-effort. On a fresh MoOS live session the Secret
/// Service can be uninitialised, and the first *write* is what pops KWallet's
/// "create a wallet" dialog — which the user is free to dismiss. When that
/// happens, or when the keyring is otherwise locked or absent, a read must
/// degrade to "nothing saved" and a write must fail quietly rather than throw
/// and take the whole app down with it. The device id — which is not a secret —
/// deliberately lives outside the keyring (see DeviceService), so a plain launch
/// never has to touch the Secret Service at all.
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

  Future<void> writePlaylists(List<PlaylistConfig> playlists) async {
    final encoded = jsonEncode(playlists.map((e) => e.toJson()).toList());
    await _write(StorageKeys.playlists, encoded);
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

  Future<void> writeActivePlaylist(PlaylistConfig? config) async {
    if (config == null) {
      await _delete(StorageKeys.activePlaylist);
      return;
    }
    await _write(StorageKeys.activePlaylist, jsonEncode(config.toJson()));
  }

  Future<void> clearAll() async {
    await _delete(StorageKeys.activePlaylist);
    await _delete(StorageKeys.playlists);
  }

  // --- Best-effort keyring access ------------------------------------------
  // The Secret Service can be locked, cancelled or missing. None of that is
  // fatal here: a failed read means "nothing saved", a failed write means "not
  // persisted this run". Boot, and every screen, carries on either way.

  Future<String?> _read(String key) async {
    try {
      return await _storage.read(key: key);
    } catch (e) {
      log.w('keyring read failed for "$key" — treating as empty: $e');
      return null;
    }
  }

  Future<void> _write(String key, String value) async {
    try {
      await _storage.write(key: key, value: value);
    } catch (e) {
      log.w('keyring write failed for "$key" — not persisted: $e');
    }
  }

  Future<void> _delete(String key) async {
    try {
      await _storage.delete(key: key);
    } catch (e) {
      log.w('keyring delete failed for "$key": $e');
    }
  }
}
