import 'package:flutter/services.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:moplayer_moos/models/playlist_config.dart';
import 'package:moplayer_moos/repositories/auth_repository.dart';
import 'package:moplayer_moos/services/storage/secure_storage_service.dart';
import 'package:moplayer_moos/services/supabase/supabase_service.dart';

class _MemoryKeyring extends FlutterSecureStorage {
  _MemoryKeyring({this.rejectWrites = false});

  final bool rejectWrites;
  final Map<String, String> values = {};

  @override
  Future<String?> read({
    required String key,
    IOSOptions? iOptions,
    AndroidOptions? aOptions,
    LinuxOptions? lOptions,
    WebOptions? webOptions,
    MacOsOptions? mOptions,
    WindowsOptions? wOptions,
  }) async => values[key];

  @override
  Future<void> write({
    required String key,
    required String? value,
    IOSOptions? iOptions,
    AndroidOptions? aOptions,
    LinuxOptions? lOptions,
    WebOptions? webOptions,
    MacOsOptions? mOptions,
    WindowsOptions? wOptions,
  }) async {
    if (rejectWrites) {
      throw PlatformException(
        code: 'Libsecret error',
        message: 'Failed to unlock the keyring',
      );
    }
    if (value == null) {
      values.remove(key);
    } else {
      values[key] = value;
    }
  }

  @override
  Future<void> delete({
    required String key,
    IOSOptions? iOptions,
    AndroidOptions? aOptions,
    LinuxOptions? lOptions,
    WebOptions? webOptions,
    MacOsOptions? mOptions,
    WindowsOptions? wOptions,
  }) async {
    if (rejectWrites) {
      throw PlatformException(
        code: 'Libsecret error',
        message: 'Failed to unlock the keyring',
      );
    }
    values.remove(key);
  }
}

PlaylistConfig _source() => PlaylistConfig(
  id: 'pl_1',
  type: PlaylistType.xtream,
  name: 'Home',
  serverUrl: 'https://panel.example',
  username: 'viewer',
  password: 'secret',
);

void main() {
  test(
    'a source is reported saved only after both encrypted writes land',
    () async {
      final storage = SecureStorageService(_MemoryKeyring());
      final repository = AuthRepository(
        storage,
        SupabaseService(enabled: false),
      );

      expect(await repository.saveAndActivate(_source()), isTrue);
      expect(await storage.readPlaylists(), hasLength(1));
      expect((await storage.readActivePlaylist())?.username, 'viewer');
      expect(storage.degraded, isFalse);
    },
  );

  test(
    'an unavailable keyring can no longer masquerade as a saved source',
    () async {
      final storage = SecureStorageService(_MemoryKeyring(rejectWrites: true));
      final repository = AuthRepository(
        storage,
        SupabaseService(enabled: false),
      );

      expect(await repository.saveAndActivate(_source()), isFalse);
      expect(storage.degraded, isTrue);
    },
  );
}
