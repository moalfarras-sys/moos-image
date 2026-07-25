import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../../core/constants/app_constants.dart';
import '../../models/playlist_config.dart';

/// Encrypted storage for sensitive values — playlist credentials and the
/// device id. Backed by the iOS Keychain on device, and by libsecret (the
/// desktop keyring) on Linux.
///
/// **The desktop keyring is not guaranteed to exist.** On Linux, libsecret
/// talks to whatever owns `org.freedesktop.secrets`; if the wallet is disabled
/// or no provider is running, every call throws
/// `PlatformException(Libsecret error, Failed to unlock the keyring)`.
///
/// That is exactly what happened on MoOS: the wallet was off, the name was not
/// even activatable on the session bus, and the very first read — the device id,
/// during bootstrap — threw. The exception escaped `main()`, so the app died
/// after its window existed but before its first frame: **a black window, with
/// no error anywhere the user could see.**
///
/// So no method here throws any more. Reads answer `null`, writes are dropped,
/// and [degraded] goes true so callers can say so out loud. What is deliberately
/// NOT done is a plaintext fallback for credentials: a user who was promised the
/// keyring must not have their IPTV password silently written to a normal file
/// because the keyring was missing. The device id is different — it is an
/// identifier, not a secret — and [DeviceService] keeps it in a plain file so a
/// machine does not change identity every time it starts without a wallet.
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

  bool _degraded = false;

  /// True once any keyring call has failed. The store still answers — with
  /// nothing — so the UI can keep working and tell the user that what they save
  /// will not survive a restart until the system keyring is available again.
  bool get degraded => _degraded;

  Future<String?> _read(String key) async {
    try {
      return await _storage.read(key: key);
    } on Object catch (e) {
      _markDegraded('read', key, e);
      return null;
    }
  }

  Future<bool> _write(String key, String value) async {
    try {
      await _storage.write(key: key, value: value);
      return true;
    } on Object catch (e) {
      _markDegraded('write', key, e);
      return false;
    }
  }

  Future<bool> _delete(String key) async {
    try {
      await _storage.delete(key: key);
      return true;
    } on Object catch (e) {
      _markDegraded('delete', key, e);
      return false;
    }
  }

  void _markDegraded(String op, String key, Object error) {
    final first = !_degraded;
    _degraded = true;
    // Once, not per call: a missing keyring fails every single access, and a
    // log line per access buries the one that explains why.
    if (first) {
      debugPrint(
        'SecureStorage: the system keyring is unavailable ($op $key failed: '
        '$error). Secrets will not be stored this session; the app continues.',
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

  /// Returns false when the keyring rejected the write. Callers that are
  /// confirming a newly-added source must use this instead of claiming it was
  /// saved merely because the source works in memory for this session.
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
    if (config == null) {
      return _delete(StorageKeys.activePlaylist);
    }
    return _write(StorageKeys.activePlaylist, jsonEncode(config.toJson()));
  }

  // --- Device id -----------------------------------------------------------

  Future<String?> readDeviceId() => _read(StorageKeys.deviceId);

  /// Returns whether the id actually reached the keyring, so the caller can
  /// keep its own copy when it did not.
  Future<bool> writeDeviceId(String id) => _write(StorageKeys.deviceId, id);

  Future<void> clearAll() async {
    await _delete(StorageKeys.activePlaylist);
    await _delete(StorageKeys.playlists);
  }
}
