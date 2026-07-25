import 'package:flutter_test/flutter_test.dart';
import 'package:moplayer_moos/models/playlist_config.dart';

/// Opening the same playlist twice must not produce two sources.
///
/// It did. `moplayer ~/tv.m3u` mints a fresh `file_<micros>` id on every launch,
/// and `saveAndActivate` matched on the id, so Settings ended up listing the same
/// file three times — each row deletable, each one leaving the other two. The fix
/// is [PlaylistConfig.identityKey]: the thing a *user* means by "the same source".
void main() {
  PlaylistConfig m3u(String id, String url) =>
      PlaylistConfig(id: id, type: PlaylistType.m3u, name: 'demo', m3uUrl: url);

  PlaylistConfig xtream(
    String id, {
    required String server,
    required String user,
    String pass = 'p',
  }) => PlaylistConfig(
    id: id,
    type: PlaylistType.xtream,
    name: user,
    serverUrl: server,
    username: user,
    password: pass,
  );

  group('PlaylistConfig.identityKey', () {
    test('the same file opened twice is one source, whatever its id', () {
      final first = m3u('file_1', 'file:///home/mo/tv.m3u');
      final second = m3u('file_2', 'file:///home/mo/tv.m3u');

      expect(first.identityKey, second.identityKey);
    });

    test('two different files are two sources', () {
      expect(
        m3u('file_1', 'file:///home/mo/tv.m3u').identityKey,
        isNot(m3u('file_2', 'file:///home/mo/other.m3u').identityKey),
      );
    });

    test('an Xtream account is its panel plus its user, not its password', () {
      // Re-entering a corrected password is the same account, not a new one —
      // duplicating the row there would strand the favourites keyed to the old id.
      final before = xtream(
        'pl_1',
        server: 'http://panel.tv:8080',
        user: 'mo',
        pass: 'old',
      );
      final after = xtream(
        'pl_2',
        server: 'http://panel.tv:8080',
        user: 'mo',
        pass: 'new',
      );

      expect(before.identityKey, after.identityKey);
    });

    test('the same panel with two accounts is two sources', () {
      expect(
        xtream('pl_1', server: 'http://panel.tv:8080', user: 'mo').identityKey,
        isNot(
          xtream(
            'pl_2',
            server: 'http://panel.tv:8080',
            user: 'sara',
          ).identityKey,
        ),
      );
    });

    test('the panel URL is normalised before it is compared', () {
      // A user who typed the server with a trailing slash once and without it the
      // next time has one account, and expects one row.
      final withSlash = xtream(
        'pl_1',
        server: 'http://panel.tv:8080/',
        user: 'mo',
      );
      final withScheme = xtream('pl_2', server: 'panel.tv:8080', user: 'MO');

      expect(withSlash.identityKey, withScheme.identityKey);
    });

    test('an M3U and an Xtream source never collide', () {
      expect(
        m3u('file_1', 'http://panel.tv:8080').identityKey,
        isNot(
          xtream('pl_1', server: 'http://panel.tv:8080', user: '').identityKey,
        ),
      );
    });
  });
}
