import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:moplayer_moos/models/playlist_config.dart';
import 'package:moplayer_moos/repositories/auth_repository.dart';
import 'package:moplayer_moos/services/storage/secure_storage_service.dart';
import 'package:moplayer_moos/services/supabase/supabase_service.dart';

PlaylistConfig _source() => PlaylistConfig(
  id: 'pl_1',
  type: PlaylistType.xtream,
  name: 'Home',
  serverUrl: 'https://panel.example',
  username: 'viewer',
  password: 'secret',
);

void main() {
  late Directory temporaryDirectory;

  setUp(() {
    temporaryDirectory = Directory.systemTemp.createTempSync(
      'moplayer-private-store-',
    );
  });

  tearDown(() {
    if (temporaryDirectory.existsSync()) {
      temporaryDirectory.deleteSync(recursive: true);
    }
  });

  test('sources survive a restart in a private local store', () async {
    final path = '${temporaryDirectory.path}/private/credentials.json';
    final storage = SecureStorageService(filePath: path);
    final repository = AuthRepository(storage, SupabaseService(enabled: false));

    expect(await repository.saveAndActivate(_source()), isTrue);
    expect(storage.degraded, isFalse);

    final restarted = SecureStorageService(filePath: path);
    expect(await restarted.readPlaylists(), hasLength(1));
    expect((await restarted.readActivePlaylist())?.username, 'viewer');

    if (Platform.isLinux || Platform.isMacOS) {
      expect(FileStat.statSync(path).mode & 0x1ff, 0x180); // 0600
      expect(
        FileStat.statSync(File(path).parent.path).mode & 0x1ff,
        0x1c0,
      ); // 0700
    }
  });

  test('an unwritable private store cannot masquerade as saved', () async {
    final storage = SecureStorageService(
      filePath: '/proc/moplayer-test/credentials.json',
    );
    final repository = AuthRepository(storage, SupabaseService(enabled: false));

    expect(await repository.saveAndActivate(_source()), isFalse);
    expect(storage.degraded, isTrue);
  });

  test('Linux startup has no Secret Service or KWallet plugin', () {
    final manifest = File('pubspec.yaml').readAsStringSync();
    final registrant = File(
      'linux/flutter/generated_plugin_registrant.cc',
    ).readAsStringSync();

    expect(manifest, isNot(contains('flutter_secure_storage')));
    expect(registrant, isNot(contains('secure_storage')));
    expect(registrant, isNot(contains('libsecret')));
  });
}
