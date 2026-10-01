// The catalogue as the screens see it, against a real (local) panel.
//
// A plain `test`, not `testWidgets`: the widget binding answers every HTTP
// request with a 400, and these jobs run in background isolates that must talk
// to a real socket.

import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:moplayer_moos/models/playlist_config.dart';
import 'package:moplayer_moos/repositories/content_repository.dart';
import 'package:moplayer_moos/services/catalog/catalog_files.dart';

/// A tiny Xtream panel. [refuseApi] makes `player_api.php` answer the way a
/// panel does for an account it will not serve through the API.
class _Panel {
  _Panel._(this.server);

  final HttpServer server;
  bool refuseApi = false;
  final List<String> hits = [];

  String get origin => 'http://127.0.0.1:${server.port}';

  static Future<_Panel> start() async {
    final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    final panel = _Panel._(server);
    server.listen(panel._handle);
    return panel;
  }

  Future<void> _handle(HttpRequest request) async {
    final path = request.uri.path;
    final action = request.uri.queryParameters['action'] ?? '';
    hits.add('$path?$action');
    final response = request.response;
    Object? body;
    if (path == '/player_api.php') {
      if (refuseApi) {
        body = {
          'user_info': {'auth': 0},
        };
      } else {
        body = switch (action) {
          '' => {
            'user_info': {
              'auth': 1,
              'status': 'Active',
              'username': 'u',
              'exp_date': '1811893244',
            },
          },
          'get_live_categories' => [
            {'category_id': '1', 'category_name': 'News'},
            {'category_id': '2', 'category_name': 'Sport'},
            {'category_id': '9', 'category_name': 'Empty'},
          ],
          'get_live_streams' => [
            {'stream_id': 11, 'name': 'Al Jazeera', 'category_id': '1'},
            {'stream_id': 21, 'name': 'beIN Sports 1', 'category_id': '2'},
            {'stream_id': 22, 'name': 'beIN Sports 2', 'category_id': '2'},
          ],
          'get_vod_categories' => [
            {'category_id': '5', 'category_name': 'Action'},
          ],
          'get_vod_streams' => [
            {
              'stream_id': 1,
              'name': 'Old',
              'category_id': '5',
              'added': '1600000000',
              'container_extension': 'mkv',
            },
            {
              'stream_id': 2,
              'name': 'New',
              'category_id': '5',
              'added': '1700000000',
            },
          ],
          'get_series_categories' => <Object>[],
          'get_series' => [
            {'series_id': 7, 'name': 'Show', 'category_id': '3'},
          ],
          _ => <Object>[],
        };
      }
    } else if (path == '/get.php') {
      response.headers.contentType = ContentType('audio', 'x-mpegurl');
      response.write(
        '#EXTM3U\n#EXTINF:-1 group-title="G",Only Channel\n'
        'http://127.0.0.1:1/live/u/p/1.ts\n',
      );
      await response.close();
      return;
    } else {
      response.statusCode = 404;
      await response.close();
      return;
    }
    response.headers.contentType = ContentType.json;
    response.write(jsonEncode(body));
    await response.close();
  }

  Future<void> stop() => server.close(force: true);
}

void main() {
  late _Panel panel;
  late Directory cacheDir;
  late CatalogFiles files;

  setUp(() async {
    panel = await _Panel.start();
    cacheDir = Directory.systemTemp.createTempSync('moplayer_repo');
    files = CatalogFiles(cacheDir.path);
  });

  tearDown(() async {
    await panel.stop();
    cacheDir.deleteSync(recursive: true);
  });

  PlaylistConfig xtream() => PlaylistConfig(
    id: 'x1',
    type: PlaylistType.xtream,
    name: 'Panel',
    serverUrl: panel.origin,
    username: 'u',
    password: 'p',
  );

  test('sections load on a background isolate, grouped and sorted', () async {
    final repo = ContentRepository(config: xtream(), files: files);
    addTearDown(repo.dispose);

    final live = await repo.liveShelf();
    expect(live.items, hasLength(3));
    expect(live.categories.map((c) => c.name), ['News', 'Sport']);
    expect(
      (await repo.liveStreams(categoryId: '2')).map((c) => c.name),
      ['beIN Sports 1', 'beIN Sports 2'],
    );

    final movies = await repo.movies();
    expect(movies.map((m) => m.name), ['New', 'Old'], reason: 'newest first');

    final found = await repo.search('bein 2');
    expect(found.live.single.name, 'beIN Sports 2');
  });

  test('a second session starts from the cache without the network', () async {
    final config = xtream();
    final first = ContentRepository(config: config, files: files);
    await first.liveShelf();
    first.dispose();
    await panel.stop();

    final second = ContentRepository(
      config: config,
      files: files,
      staleAfter: const Duration(days: 1),
    );
    addTearDown(second.dispose);
    final live = await second.liveShelf();
    expect(live.items, hasLength(3));
  });

  test('a stale cache is served at once and refreshed behind it', () async {
    final first = ContentRepository(config: xtream(), files: files);
    await first.liveShelf();
    first.dispose();
    panel.hits.clear();

    final second = ContentRepository(
      config: xtream(),
      files: files,
      staleAfter: Duration.zero,
    );
    addTearDown(second.dispose);
    final announced = second.changes.first;
    final live = await second.liveShelf();
    expect(live.items, hasLength(3), reason: 'cache first');
    expect(await announced, CatalogSection.live);
    expect(panel.hits, contains('/player_api.php?get_live_streams'));
  });

  test('a playlist link that carries an account is read as that account', () {
    final link = PlaylistConfig(
      id: 'm1',
      type: PlaylistType.m3u,
      name: 'Mo',
      m3uUrl: '${panel.origin}/get.php?username=u&password=p&type=m3u_plus',
    );
    final equivalent = link.xtreamEquivalent!;
    expect(equivalent.serverUrl, panel.origin);
    expect(equivalent.username, 'u');
    expect(equivalent.password, 'p');
    expect(equivalent.isXtream, isTrue);

    final repo = ContentRepository(config: link, files: files);
    addTearDown(repo.dispose);
    expect(repo.mode, SourceMode.xtream);
  });

  test('when the panel refuses the API, the link is read as a playlist', () async {
    panel.refuseApi = true;
    final link = PlaylistConfig(
      id: 'm2',
      type: PlaylistType.m3u,
      name: 'Mo',
      m3uUrl: '${panel.origin}/get.php?username=u&password=p&type=m3u_plus',
    );
    final repo = ContentRepository(config: link, files: files);
    addTearDown(repo.dispose);

    final live = await repo.liveStreams();
    expect(live.single.name, 'Only Channel');
    expect(repo.mode, SourceMode.m3u);

    // And the next session does not ask the API again.
    final next = ContentRepository(config: link, files: files);
    addTearDown(next.dispose);
    expect(next.mode, SourceMode.m3u);
  });

  test('a live channel offers its other stream format', () async {
    final repo = ContentRepository(config: xtream(), files: files);
    addTearDown(repo.dispose);
    final channel = (await repo.liveStreams()).first;
    final target = repo.liveTarget(channel);
    expect(target.url, endsWith('/live/u/p/11.m3u8'));
    expect(target.alternatives.single, endsWith('/live/u/p/11.ts'));
    final ts = repo.liveTarget(channel, preferHls: false);
    expect(ts.url, endsWith('.ts'));
  });

  test('a wrong password is a typed auth failure, not a crash', () async {
    panel.refuseApi = true;
    final repo = ContentRepository(config: xtream(), files: files);
    addTearDown(repo.dispose);
    await expectLater(
      repo.liveShelf(),
      throwsA(
        isA<Object>().having((e) => e.toString(), 'text', contains('auth')),
      ),
    );
  });
}
