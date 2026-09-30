// The MAC-portal client, driven against a simulated Stalker/Ministra portal.
//
// No network: every request goes to [_FakePortal], a Dio adapter that answers
// the way real portals do — including the ways they misbehave (text/html
// labels, byte-order marks, PHP notices, 404s on the wrong API file, a token
// that silently expires, `localhost` links that were never resolved).
import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:moplayer_moos/core/error/failures.dart';
import 'package:moplayer_moos/models/category.dart';
import 'package:moplayer_moos/models/series.dart';
import 'package:moplayer_moos/services/stalker/stalker_api.dart';
import 'package:moplayer_moos/services/stalker/stalker_identity.dart';
import 'package:moplayer_moos/services/stalker/stalker_portal_address.dart';

const _mac = '00:1a:79:ab:cd:ef';
const _encodedMac = 'mac=00%3A1A%3A79%3AAB%3ACD%3AEF';

class _Res {
  const _Res(
    this.body, {
    this.status = 200,
    this.contentType = 'application/json',
  });

  _Res.js(Object? js, {String contentType = 'application/json'})
    : this(jsonEncode({'js': js}), contentType: contentType);

  final String body;
  final int status;
  final String contentType;
}

typedef _Handler = FutureOr<_Res> Function(Map<String, String> query);

/// A portal whose API lives at [apiPath]; every other path answers
/// [missStatus] with an HTML page, as a web server does.
class _FakePortal implements HttpClientAdapter {
  _FakePortal({this.apiPath = '/portal.php', this.missStatus = 404});

  final String apiPath;
  final int missStatus;
  final List<RequestOptions> requests = [];
  final Map<String, _Handler> routes = {};

  /// Registers [handler] for `type/action` [key]; chains, so a test reads as
  /// a list of routes.
  _FakePortal on(String key, _Handler handler) {
    routes[key] = handler;
    return this;
  }

  int handshakes = 0;

  /// The token the portal currently accepts. Tests overwrite it to simulate a
  /// portal that forgot the session.
  String? token;

  /// Ministra's other refusal: a 200 whose body is `Authorization failed.`.
  bool refuseAsText = false;

  List<RequestOptions> calls(String type, String action) => [
    for (final r in requests)
      if (r.uri.queryParameters['type'] == type &&
          r.uri.queryParameters['action'] == action)
        r,
  ];

  static final Map<String, _Handler> _defaults = {
    'stb/get_profile': (_) =>
        _Res.js({'id': '1', 'status': 0, 'login': 'owner', 'block_msg': ''}),
    'account_info/get_main_info': (_) =>
        _Res.js({'end_date': '2027-03-01 00:00:00', 'tariff_plan': 'Full'}),
  };

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    requests.add(options);
    // Real I/O is asynchronous; so is this, which lets concurrent callers
    // interleave the way they would against a portal.
    await Future<void>.delayed(Duration.zero);
    if (options.uri.path != apiPath) {
      return _respond(
        _Res(
          '<html><body>Not here</body></html>',
          status: missStatus,
          contentType: 'text/html',
        ),
      );
    }
    final q = options.uri.queryParameters;
    final key = '${q['type']}/${q['action']}';
    if (key == 'stb/handshake') {
      final custom = routes[key];
      if (custom != null) return _respond(await custom(q));
      handshakes++;
      token = 'tok$handshakes';
      return _respond(_Res.js({'token': token, 'random': 'rnd$handshakes'}));
    }
    if (token == null || options.headers['Authorization'] != 'Bearer $token') {
      return _respond(
        refuseAsText
            ? const _Res('Authorization failed.', contentType: 'text/html')
            : const _Res('', status: 401, contentType: 'text/html'),
      );
    }
    final handler = routes[key] ?? _defaults[key];
    return _respond(handler == null ? _Res.js(const []) : await handler(q));
  }

  ResponseBody _respond(_Res res) => ResponseBody.fromString(
    res.body,
    res.status,
    headers: {
      Headers.contentTypeHeader: [res.contentType],
    },
  );

  @override
  void close({bool force = false}) {}
}

/// An adapter that fails every request at the transport level.
class _BrokenNetwork implements HttpClientAdapter {
  _BrokenNetwork(this.type);

  final DioExceptionType type;
  int calls = 0;

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    calls++;
    throw DioException(requestOptions: options, type: type);
  }

  @override
  void close({bool force = false}) {}
}

StalkerApi _api(
  HttpClientAdapter adapter, {
  String url = 'http://portal.test:8080/c/',
  String mac = _mac,
  String? timezone,
}) {
  final dio = Dio()..httpClientAdapter = adapter;
  return StalkerApi(
    portalUrl: url,
    macAddress: mac,
    dio: dio,
    timezone: timezone,
  );
}

Matcher _failure(FailureKind kind, [Pattern? message]) => isA<Failure>()
    .having((f) => f.kind, 'kind', kind)
    .having(
      (f) => message == null || f.message.contains(message),
      'message contains $message',
      isTrue,
    );

String? _cmdOf(String? stalkerUrl) =>
    Uri.parse(stalkerUrl!).queryParameters['cmd'];

void main() {
  group('portal address', () {
    List<String> paths(String input) => [
      for (final uri in StalkerPortalAddress.parse(input)!.candidates)
        uri.toString(),
    ];

    test('a /c/ address tries portal.php, then server/load.php', () {
      expect(paths('http://portal.test:8080/c/'), [
        'http://portal.test:8080/portal.php',
        'http://portal.test:8080/server/load.php',
        'http://portal.test:8080/stalker_portal/server/load.php',
      ]);
    });

    test('a bare host gets a scheme', () {
      final address = StalkerPortalAddress.parse('  portal.test:8080 ')!;
      expect(address.origin.toString(), 'http://portal.test:8080');
      expect(address.basePath, '');
      expect(
        address.candidates.first.toString(),
        'http://portal.test:8080/portal.php',
      );
    });

    test('a Ministra client page resolves under /stalker_portal', () {
      final address = StalkerPortalAddress.parse(
        'http://portal.test/stalker_portal/c/index.html',
      )!;
      expect(address.basePath, '/stalker_portal');
      expect(paths('http://portal.test/stalker_portal/c/index.html'), [
        'http://portal.test/stalker_portal/portal.php',
        'http://portal.test/stalker_portal/server/load.php',
        'http://portal.test/portal.php',
        'http://portal.test/server/load.php',
      ]);
    });

    test('an API file typed directly is tried first', () {
      expect(
        paths('https://portal.test/stalker_portal/server/load.php').first,
        'https://portal.test/stalker_portal/server/load.php',
      );
      expect(
        StalkerPortalAddress.rootPathOf(
          Uri.parse('https://portal.test/stalker_portal/server/load.php'),
        ),
        '/stalker_portal',
      );
      expect(
        StalkerPortalAddress.rootPathOf(Uri.parse('http://h/portal.php')),
        '',
      );
    });

    test('non-web addresses are refused', () {
      expect(StalkerPortalAddress.parse(''), isNull);
      expect(StalkerPortalAddress.parse('ftp://portal.test/c/'), isNull);
      expect(StalkerPortalAddress.parse('http://'), isNull);
    });
  });

  group('device identity', () {
    test('SHA-256 matches the FIPS 180-2 vectors', () {
      expect(
        sha256Hex(''),
        'E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855',
      );
      expect(
        sha256Hex('abc'),
        'BA7816BF8F01CFEA414140DE5DAE2223B00361A396177A9CB410FF61F20015AD',
      );
      expect(
        sha256Hex('abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq'),
        '248D6A61D20638B8E5C026930C3E6039A33CE45964FF2167F6ECEDD419DB06C1',
      );
      expect(
        sha256Hex(
          'abcdefghbcdefghicdefghijdefghijkefghijklfghijklmghijklmn'
          'hijklmnoijklmnopjklmnopqklmnopqrlmnopqrsmnopqrstnopqrstu',
        ),
        'CF5B16A778AF8380036CE59E7B0492370B249B11E8F07A51AFAC45037AFEE9D1',
      );
    });

    test('MACs normalise; anything else is refused', () {
      for (final input in [
        '00:1a:79:ab:cd:ef',
        '001A79ABCDEF',
        ' 00-1A-79-AB-CD-EF ',
      ]) {
        expect(StalkerIdentity.normalizeMac(input), '00:1A:79:AB:CD:EF');
      }
      expect(StalkerIdentity.normalizeMac('00:1A:79:AB:CD'), isNull);
      expect(StalkerIdentity.normalizeMac('00:1A:79:AB:CD:EG'), isNull);
    });

    test('the derived identity is deterministic and MAG-shaped', () {
      final a = StalkerIdentity.fromMac('00:1a:79:ab:cd:ef')!;
      final b = StalkerIdentity.fromMac('001A79ABCDEF')!;
      final other = StalkerIdentity.fromMac('00:1A:79:00:00:01')!;
      expect(a.serialNumber, b.serialNumber);
      expect(a.deviceId, b.deviceId);
      expect(a.signature, b.signature);
      expect(a.serialNumber, matches(RegExp(r'^[0-9A-F]{13}$')));
      expect(a.deviceId, matches(RegExp(r'^[0-9A-F]{64}$')));
      expect(a.hwVersion2, matches(RegExp(r'^[0-9A-F]{40}$')));
      expect(other.deviceId, isNot(a.deviceId));
      expect(other.serialNumber, isNot(a.serialNumber));
    });
  });

  group('connect', () {
    test('handshakes, then activates the token with get_profile', () async {
      final portal = _FakePortal();
      final api = _api(portal);
      final account = await api.connect();

      final handshake = portal.calls('stb', 'handshake').single;
      expect(handshake.headers['Authorization'], isNull);
      expect(handshake.uri.queryParameters['JsHttpRequest'], '1-xml');
      expect(handshake.uri.queryParameters['token'], '');
      expect(handshake.uri.queryParameters['prehash'], '0');

      for (final request in portal.requests) {
        expect(request.headers['User-Agent'], StalkerApi.userAgent);
        expect(request.headers['X-User-Agent'], 'Model: MAG250; Link: WiFi');
        expect(request.headers['Referer'], 'http://portal.test:8080/c/');
        final cookie = request.headers['Cookie'] as String;
        expect(cookie, contains(_encodedMac));
        expect(cookie, contains('stb_lang=en'));
        expect(cookie, contains('timezone=Europe%2FBerlin'));
      }

      final profile = portal.calls('stb', 'get_profile').single;
      expect(profile.headers['Authorization'], 'Bearer tok1');
      final identity = StalkerIdentity.fromMac(_mac)!;
      final q = profile.uri.queryParameters;
      expect(q['sn'], identity.serialNumber);
      expect(q['device_id'], identity.deviceId);
      expect(q['device_id2'], identity.deviceId);
      expect(q['signature'], identity.signature);
      expect(q['stb_type'], 'MAG250');
      expect(q['auth_second_step'], '1');
      expect(q['api_signature'], '262');
      expect(int.parse(q['timestamp']!), greaterThan(1700000000));
      final metrics = jsonDecode(q['metrics']!) as Map<String, dynamic>;
      expect(metrics['random'], 'rnd1');

      expect(account.login, 'owner');
      expect(account.tariff, 'Full');
      expect(account.expiresAt, DateTime(2027, 3, 1));
      expect(account.status, 'Active');
      expect(api.account, same(account));
      expect(api.endpoint.toString(), 'http://portal.test:8080/portal.php');
    });

    test('reads the expiry Xtream-based panels put in `phone`', () async {
      final portal = _FakePortal().on(
        'account_info/get_main_info',
        (_) => _Res.js({'phone': 'December 31, 2026, 11:59 pm'}),
      );
      final account = await _api(portal, timezone: 'Asia/Dubai').connect();
      expect(account.expiresAt, DateTime(2026, 12, 31, 23, 59));
      expect(
        portal.requests.first.headers['Cookie'],
        contains('timezone=Asia%2FDubai'),
      );
    });

    test('a blocked MAC is an auth failure carrying the portal message', () {
      final portal = _FakePortal().on(
        'stb/get_profile',
        (_) => _Res.js({
          'status': 1,
          'block_msg': 'Your STB is <b>blocked</b>.<br>Call support.',
        }),
      );
      expect(
        _api(portal).connect(),
        throwsA(
          _failure(FailureKind.auth, 'Your STB is blocked. Call support.'),
        ),
      );
    });

    test('an invalid MAC fails before any request', () async {
      final portal = _FakePortal();
      await expectLater(
        _api(portal, mac: 'not-a-mac').connect(),
        throwsA(_failure(FailureKind.auth, 'MAC address')),
      );
      expect(portal.requests, isEmpty);
    });

    test('a profile of js:false gets exactly one fresh handshake', () async {
      var profiles = 0;
      final portal = _FakePortal().on(
        'stb/get_profile',
        (_) => ++profiles == 1 ? _Res.js(false) : _Res.js({'status': 0}),
      );
      final account = await _api(portal).connect();
      expect(account.status, 'Active');
      expect(portal.handshakes, 2);
      expect(
        portal.calls('stb', 'get_profile').last.headers['Authorization'],
        'Bearer tok2',
      );
    });

    test('a profile that stays js:false is an auth failure', () async {
      final portal = _FakePortal().on('stb/get_profile', (_) => _Res.js(false));
      await expectLater(
        _api(portal).connect(),
        throwsA(_failure(FailureKind.auth)),
      );
      expect(portal.handshakes, 2);
    });

    test('falls back from portal.php (404) to server/load.php', () async {
      final portal = _FakePortal(apiPath: '/stalker_portal/server/load.php').on(
        'itv/get_all_channels',
        (_) => _Res.js({
          'data': [
            {'id': '1', 'name': 'One', 'cmd': 'ffrt x', 'logo': '8.png'},
          ],
        }),
      );
      final api = _api(portal, url: 'http://portal.test/stalker_portal/c/');
      await api.connect();
      expect(portal.requests.map((r) => r.uri.path).take(2).toList(), [
        '/stalker_portal/portal.php',
        '/stalker_portal/server/load.php',
      ]);
      expect(api.endpoint!.path, '/stalker_portal/server/load.php');

      final before = portal.requests.length;
      final channels = await api.liveChannels();
      final later = portal.requests.skip(before).toList();
      expect(later, isNotEmpty);
      for (final r in later) {
        expect(r.uri.path, '/stalker_portal/server/load.php');
        expect(r.headers['Referer'], 'http://portal.test/stalker_portal/c/');
      }
      expect(
        channels.single.logo,
        'http://portal.test/stalker_portal/misc/logos/320/8.png',
      );
    });

    test('an HTML page with status 200 is not mistaken for the API', () async {
      final portal = _FakePortal(apiPath: '/server/load.php', missStatus: 200);
      final api = _api(portal);
      await api.connect();
      expect(api.endpoint!.path, '/server/load.php');
    });

    test('no API anywhere is a server failure, not a hang', () async {
      final portal = _FakePortal(apiPath: '/elsewhere.php');
      await expectLater(
        _api(portal).connect(),
        throwsA(_failure(FailureKind.server, 'No MAC portal')),
      );
      expect(portal.requests.length, 3);
    });

    test('an unreachable host is a network failure after one try', () async {
      final adapter = _BrokenNetwork(DioExceptionType.connectionError);
      await expectLater(
        _api(adapter).connect(),
        throwsA(_failure(FailureKind.network)),
      );
      expect(adapter.calls, 1);
    });

    test('a timeout is retried once, then reported', () async {
      final adapter = _BrokenNetwork(DioExceptionType.receiveTimeout);
      await expectLater(
        _api(adapter).connect(),
        throwsA(_failure(FailureKind.timeout)),
      );
      expect(adapter.calls, 2);
    });
  });

  group('token renewal', () {
    test('a 401 re-handshakes once and retries with the new token', () async {
      final portal = _FakePortal().on(
        'itv/get_genres',
        (_) => _Res.js([
          {'id': '5', 'title': 'News'},
        ]),
      );
      final api = _api(portal);
      await api.connect();
      portal.token = 'forgotten';

      final genres = await api.liveGenres();
      expect(genres.single.name, 'News');
      expect(portal.handshakes, 2);
      final calls = portal.calls('itv', 'get_genres');
      expect(calls.map((r) => r.headers['Authorization']), [
        'Bearer tok1',
        'Bearer tok2',
      ]);
      expect(portal.calls('stb', 'get_profile').length, 2);
    });

    test('so does a plain-text "Authorization failed."', () async {
      final portal = _FakePortal()..refuseAsText = true;
      final api = _api(portal);
      await api.connect();
      portal.token = 'forgotten';
      await api.vodCategories();
      expect(portal.handshakes, 2);
    });

    test('a refusal that survives renewal is an auth failure', () async {
      final portal = _FakePortal().on(
        'itv/get_genres',
        (_) => const _Res('', status: 403, contentType: 'text/html'),
      );
      final api = _api(portal);
      await expectLater(api.liveGenres(), throwsA(_failure(FailureKind.auth)));
      expect(portal.handshakes, 2);
    });

    test('concurrent first calls share one handshake', () async {
      final portal = _FakePortal();
      final api = _api(portal);
      await Future.wait([
        api.liveGenres(),
        api.vodCategories(),
        api.liveGenres(),
      ]);
      expect(portal.handshakes, 1);
    });
  });

  group('lenient responses', () {
    test('an empty body is a parse failure', () {
      final portal = _FakePortal().on('itv/get_genres', (_) => const _Res(''));
      expect(_api(portal).liveGenres(), throwsA(_failure(FailureKind.parse)));
    });

    test('a non-JSON body is a parse failure', () {
      final portal = _FakePortal().on(
        'itv/get_genres',
        (_) => const _Res('<html>oops</html>', contentType: 'text/html'),
      );
      expect(_api(portal).liveGenres(), throwsA(_failure(FailureKind.parse)));
    });

    test('PHP notices before the JSON are skipped', () async {
      final portal = _FakePortal().on(
        'itv/get_genres',
        (_) => _Res(
          '<br />\n<b>Notice</b>: Undefined index: x in load.php<br />\n'
          '${jsonEncode({
            'js': [
              {'id': '5', 'title': 'News'},
            ],
          })}',
          contentType: 'text/html',
        ),
      );
      final genres = await _api(portal).liveGenres();
      expect(genres.single.id, '5');
    });

    test('an HTTP error on a data call is a server failure', () {
      final portal = _FakePortal().on(
        'vod/get_categories',
        (_) => const _Res('boom', status: 500, contentType: 'text/html'),
      );
      expect(
        _api(portal).vodCategories(),
        throwsA(_failure(FailureKind.server, '500')),
      );
    });
  });

  group('live', () {
    test('genres drop the "All" entry and keep string ids', () async {
      final portal = _FakePortal().on(
        'itv/get_genres',
        (_) => _Res.js([
          {'id': '*', 'title': 'All'},
          {'id': '5', 'title': 'News'},
          {'id': 12, 'title': 'Sport'},
        ]),
      );
      final genres = await _api(portal).liveGenres();
      expect(genres.map((c) => c.id), ['5', '12']);
      expect(genres.map((c) => c.name), ['News', 'Sport']);
    });

    test('channels read text/html + BOM and resolve relative logos', () async {
      final portal = _FakePortal().on(
        'itv/get_all_channels',
        (_) => _Res(
          '﻿${jsonEncode({
            'js': {
              'total_items': 5,
              'data': [
                {'id': '1001', 'name': 'Alpha', 'number': '7', 'cmd': 'ffrt http://localhost/ch/1001_', 'logo': '/stalker_portal/misc/logos/320/1001.png', 'tv_genre_id': '5', 'xmltv_id': 'alpha.de', 'tv_archive': '1'},
                {'id': '1002', 'name': 'Beta', 'cmd': 'ffmpeg http://real.test/2.ts', 'logo': '1002.png', 'tv_archive': 0},
                {'id': '1003', 'name': 'Gamma', 'cmd': 'x', 'logo': '//cdn.test/3.png'},
                {'id': '1004', 'name': 'Delta', 'cmd': 'x', 'logo': 'https://cdn.test/4.png'},
                {'id': '1005', 'name': 'No command', 'cmd': ''},
              ],
            },
          })}',
          contentType: 'text/html; charset=UTF-8',
        ),
      );
      final channels = await _api(portal).liveChannels();
      expect(channels.map((c) => c.streamId), [
        'stk_1001',
        'stk_1002',
        'stk_1003',
        'stk_1004',
      ]);
      final alpha = channels.first;
      expect(alpha.name, 'Alpha');
      expect(alpha.number, 7);
      expect(alpha.categoryId, '5');
      expect(alpha.epgChannelId, 'alpha.de');
      expect(alpha.tvArchive, isTrue);
      expect(alpha.directUrl, startsWith('stalker://itv?cmd='));
      expect(StalkerApi.isStalkerUrl(alpha.directUrl!), isTrue);
      expect(_cmdOf(alpha.directUrl), 'ffrt http://localhost/ch/1001_');
      expect(
        alpha.logo,
        'http://portal.test:8080/stalker_portal/misc/logos/320/1001.png',
      );
      expect(
        channels[1].logo,
        'http://portal.test:8080/misc/logos/320/1002.png',
      );
      expect(channels[1].tvArchive, isFalse);
      expect(channels[2].logo, 'http://cdn.test/3.png');
      expect(channels[3].logo, 'https://cdn.test/4.png');
    });

    test('an empty get_all_channels falls back to the paged list', () async {
      final portal = _FakePortal()
          .on('itv/get_all_channels', (_) => _Res.js({'data': []}))
          .on(
            'itv/get_ordered_list',
            (q) => _Res.js({
              'total_items': 3,
              'max_page_items': 2,
              'cur_page': 0,
              'data': q['p'] == '1'
                  ? [
                      {'id': '1', 'name': 'One', 'cmd': 'ffrt a'},
                      {'id': '2', 'name': 'Two', 'cmd': 'ffrt b'},
                    ]
                  : [
                      {'id': '3', 'name': 'Three', 'cmd': 'ffrt c'},
                    ],
            }),
          );
      final channels = await _api(portal).liveChannels();
      expect(channels.map((c) => c.name), ['One', 'Two', 'Three']);
      final pages = portal.calls('itv', 'get_ordered_list');
      expect(pages.map((r) => r.uri.queryParameters['p']), ['1', '2']);
      expect(pages.first.uri.queryParameters['genre'], '*');
    });
  });

  group('vod', () {
    Map<String, dynamic> vodPageJs(Map<String, String> q) => {
      'total_items': 3,
      'max_page_items': 2,
      'selected_item': 0,
      'cur_page': 0,
      'data': q['p'] == '1'
          ? [
              {
                'id': '1',
                'name': 'Film One',
                'cmd': '/media/1.mpg',
                'screenshot_uri': '/stalker_portal/screenshots/1.jpg',
                'rating_imdb': '7.4',
                'year': '2019-05-01',
                'added': '2024-02-03 10:20:30',
                'category_id': '10',
                'is_series': '0',
                'description': 'A film.',
                'director': 'Someone',
                'actors': 'A, B',
                'genres_str': 'Drama',
                'time': '120',
              },
              {
                'id': '2',
                'name': 'Show In VOD',
                'cmd': '/media/2.mpg',
                'is_series': '1',
                'series': [1, 2],
              },
            ]
          : [
              {
                'id': '3',
                'name': 'Film Three',
                'cmd': 'ffmpeg http://real.test/3.mp4',
                'pic': 'https://img.test/3.jpg',
                'rating_imdb': 'N/A',
                'rating_kinopoisk': '6.1',
              },
            ],
    };

    test('pages movies and leaves series out', () async {
      final portal = _FakePortal()
          .on(
            'vod/get_categories',
            (_) => _Res.js([
              {'id': '*', 'title': 'All'},
              {'id': '10', 'title': 'Films'},
            ]),
          )
          .on('vod/get_ordered_list', (q) => _Res.js(vodPageJs(q)));
      final api = _api(portal);

      final categories = await api.vodCategories();
      expect(categories.map((c) => c.id), ['10']);

      final first = await api.vodPage('10');
      expect(first.items.map((m) => m.streamId), ['stkv_1']);
      expect(first.page, 1);
      expect(first.perPage, 2);
      expect(first.totalItems, 3);
      expect(first.hasMore, isTrue);
      final film = first.items.single;
      expect(
        film.poster,
        'http://portal.test:8080/stalker_portal/screenshots/1.jpg',
      );
      expect(film.rating, 7.4);
      expect(film.year, '2019');
      expect(film.added, DateTime(2024, 2, 3, 10, 20, 30));
      expect(film.categoryId, '10');
      expect(_cmdOf(film.directUrl), '/media/1.mpg');
      expect(film.directUrl, startsWith('stalker://vod?'));

      final detail = api.movieDetail(film);
      expect(detail.plot, 'A film.');
      expect(detail.director, 'Someone');
      expect(detail.cast, 'A, B');
      expect(detail.genre, 'Drama');
      expect(detail.durationSecs, 7200);

      final second = await api.vodPage('10', page: 2);
      expect(second.items.single.streamId, 'stkv_3');
      expect(second.items.single.rating, 6.1);
      expect(second.items.single.poster, 'https://img.test/3.jpg');
      expect(second.hasMore, isFalse);

      final q = portal.calls('vod', 'get_ordered_list').first.uri;
      expect(q.queryParameters['category'], '10');
      expect(q.queryParameters['p'], '1');
    });

    test('the synthetic "All" category asks the portal for *', () async {
      final portal = _FakePortal();
      await _api(portal).vodPage(Category.allId);
      expect(
        portal
            .calls('vod', 'get_ordered_list')
            .single
            .uri
            .queryParameters['category'],
        '*',
      );
    });
  });

  group('series', () {
    test('classic series expand from `series: [..]` with no request', () async {
      final portal = _FakePortal()
          .on(
            'series/get_categories',
            (_) => _Res.js([
              {'id': '*', 'title': 'All'},
              {'id': '20', 'title': 'Shows'},
            ]),
          )
          .on(
            'series/get_ordered_list',
            (_) => _Res.js({
              'total_items': 1,
              'max_page_items': 14,
              'data': [
                {
                  'id': '55',
                  'name': 'Classic Show',
                  'cmd': '/media/classic.mpg',
                  'series': [3, 1, 2],
                  'screenshot_uri': '/stalker_portal/screenshots/55.jpg',
                  'description': 'Plot.',
                  'genres_str': 'Comedy',
                  'year': '2011',
                },
              ],
            }),
          );
      final api = _api(portal);
      expect((await api.seriesCategories()).map((c) => c.id), ['20']);

      final page = await api.seriesPage('20');
      final show = page.items.single;
      expect(show.seriesId, 'stks_55');
      expect(show.plot, 'Plot.');
      expect(show.genre, 'Comedy');
      expect(show.releaseDate, '2011');
      expect(
        show.cover,
        'http://portal.test:8080/stalker_portal/screenshots/55.jpg',
      );

      final before = portal.requests.length;
      final result = await api.seriesDetail(show);
      expect(portal.requests.length, before);
      expect(result.detail.series, same(show));
      final season = result.detail.seasons.single;
      expect(season.number, 1);
      expect(season.episodes.map((e) => e.episodeNum), [1, 2, 3]);
      expect(season.episodes.map((e) => e.id), [
        'stke_55_1_1',
        'stke_55_1_2',
        'stke_55_1_3',
      ]);
      final url = Uri.parse(result.episodeUrls['stke_55_1_2']!);
      expect(url.scheme, 'stalker');
      expect(url.host, 'vod');
      expect(url.queryParameters['cmd'], '/media/classic.mpg');
      expect(url.queryParameters['series'], '2');
    });

    test('without a series module, series come from the VOD list', () async {
      final portal = _FakePortal()
          .on(
            'vod/get_categories',
            (_) => _Res.js([
              {'id': '10', 'title': 'Everything'},
            ]),
          )
          .on(
            'vod/get_ordered_list',
            (_) => _Res.js({
              'total_items': 2,
              'max_page_items': 14,
              'data': [
                {'id': '1', 'name': 'Film', 'cmd': '/media/1.mpg'},
                {
                  'id': '2',
                  'name': 'Show',
                  'cmd': '/media/2.mpg',
                  'is_series': 1,
                  'series': ['1', '2'],
                },
              ],
            }),
          );
      final api = _api(portal);
      final categories = await api.seriesCategories();
      expect(categories.single.name, 'Everything');

      final page = await api.seriesPage('10');
      expect(page.items.single.seriesId, 'stks_2');
      expect(portal.calls('series', 'get_ordered_list'), isEmpty);

      final result = await api.seriesDetail(page.items.single);
      expect(result.episodeUrls.length, 2);
      expect(
        Uri.parse(result.episodeUrls['stke_2_1_1']!).queryParameters['series'],
        '1',
      );
    });

    test('modern series walk seasons, episodes and files', () async {
      final portal = _FakePortal()
          .on(
            'series/get_categories',
            (_) => _Res.js([
              {'id': '20', 'title': 'Shows'},
            ]),
          )
          .on('series/get_ordered_list', (q) {
            final movie = q['movie_id'];
            final season = q['season_id'];
            final episode = q['episode_id'];
            if (movie == null) {
              return _Res.js({
                'total_items': 1,
                'max_page_items': 14,
                'data': [
                  {'id': '77', 'name': 'Modern Show'},
                ],
              });
            }
            if (season == '0') {
              return _Res.js({
                'total_items': 2,
                'max_page_items': 14,
                'data': [
                  {'id': '77:1', 'name': 'Season 1', 'is_season': true},
                  {
                    'id': '77:2',
                    'name': 'Season 2',
                    'series': [1, 2],
                    'cmd': 'eyJzZWFzb24iOjJ9',
                  },
                ],
              });
            }
            if (season == '77:1' && episode == '0') {
              return _Res.js({
                'total_items': 2,
                'max_page_items': 14,
                'data': [
                  {
                    'id': '502',
                    'name': 'Second',
                    'series_number': '2',
                    'is_episode': true,
                  },
                  {
                    'id': '501',
                    'name': 'Pilot',
                    'series_number': 1,
                    'cmd': 'ffmpeg http://media.test/ep501.mkv',
                    'time': '42',
                  },
                ],
              });
            }
            if (episode == '502') {
              return _Res.js({
                'total_items': 1,
                'max_page_items': 14,
                'data': [
                  {'id': '9001', 'cmd': 'ffmpeg http://media.test/ep502.mkv'},
                ],
              });
            }
            return _Res.js(const []);
          })
          .on(
            'vod/create_link',
            (q) => q['cmd'] == 'ffmpeg http://media.test/ep502.mkv'
                ? _Res.js({'cmd': 'ffmpeg http://cdn.test/ep502.mkv?t=x'})
                : _Res.js({'cmd': '', 'error': 'nothing_to_play'}),
          );
      final api = _api(portal);
      final show = (await api.seriesPage('20')).items.single;
      final result = await api.seriesDetail(show);

      final seasons = result.detail.seasons;
      expect(seasons.map((s) => s.number), [1, 2]);
      expect(seasons.first.name, 'Season 1');
      final first = seasons.first.episodes;
      expect(first.map((e) => e.id), ['stke_501', 'stke_502']);
      expect(first.map((e) => e.title), ['Pilot', 'Second']);
      expect(first.first.durationSecs, 42 * 60);
      expect(
        _cmdOf(result.episodeUrls['stke_501']),
        'ffmpeg http://media.test/ep501.mkv',
      );
      final lazy = Uri.parse(result.episodeUrls['stke_502']!);
      expect(lazy.queryParameters['episode_id'], '502');
      expect(lazy.queryParameters['season_id'], '77:1');
      expect(lazy.queryParameters['module'], 'series');

      expect(seasons.last.episodes.map((e) => e.id), [
        'stke_77_2_1',
        'stke_77_2_2',
      ]);
      final numbered = Uri.parse(result.episodeUrls['stke_77_2_2']!);
      expect(numbered.queryParameters['cmd'], 'eyJzZWFzb24iOjJ9');
      expect(numbered.queryParameters['series'], '2');

      // The episode listed without a cmd has its file looked up at play time.
      final url = await api.resolve(result.episodeUrls['stke_502']!);
      expect(url, 'http://cdn.test/ep502.mkv?t=x');
      final link = portal.calls('vod', 'create_link').single.uri;
      expect(link.queryParameters['cmd'], 'ffmpeg http://media.test/ep502.mkv');
      expect(link.queryParameters['series'], '');
    });

    test('a favourite restored without its list entry still opens', () async {
      final portal = _FakePortal()
          .on(
            'series/get_categories',
            (_) => _Res.js([
              {'id': '20', 'title': 'Shows'},
            ]),
          )
          .on(
            'series/get_ordered_list',
            (q) => q['movie_id'] == '91'
                ? _Res.js({
                    'total_items': 1,
                    'max_page_items': 14,
                    'data': [
                      {
                        'id': '91:1',
                        'name': 'Season 1',
                        'series': [1],
                        'cmd': 'c91',
                      },
                    ],
                  })
                : _Res.js(const []),
          );
      final result = await _api(
        portal,
      ).seriesDetail(const SeriesItem(seriesId: 'stks_91', name: 'Saved'));
      expect(result.detail.seasons.single.episodes.single.id, 'stke_91_1_1');
      expect(result.detail.seasons.single.episodes.single.title, 'Saved');
    });
  });

  group('resolve', () {
    const live = 'stalker://itv?cmd=ffrt+http%3A%2F%2Flocalhost%2Fch%2F1001_';

    test('create_link answers with the playable address', () async {
      final portal = _FakePortal().on(
        'itv/create_link',
        (_) => _Res.js({
          'id': '1001',
          'cmd': 'ffmpeg  http://stream.test/live/1001.ts?play_token=abc ',
        }),
      );
      final url = await _api(portal).resolve(live);
      expect(url, 'http://stream.test/live/1001.ts?play_token=abc');

      final request = portal.calls('itv', 'create_link').single;
      final q = request.uri.queryParameters;
      expect(q['cmd'], 'ffrt http://localhost/ch/1001_');
      expect(q['series'], '');
      expect(q['forced_storage'], '0');
      expect(q['disable_ad'], '0');
      expect(q['download'], '0');
      expect(q['JsHttpRequest'], '1-xml');
      expect(request.headers['Authorization'], 'Bearer tok1');
      expect(request.headers['Cookie'], contains(_encodedMac));
    });

    test('an episode sends its number as `series`', () async {
      final portal = _FakePortal().on(
        'vod/create_link',
        (q) =>
            _Res.js({'cmd': 'auto https://vod.test/show/e${q['series']}.mp4'}),
      );
      final url = await _api(
        portal,
      ).resolve('stalker://vod?cmd=%2Fmedia%2Fclassic.mpg&series=3');
      expect(url, 'https://vod.test/show/e3.mp4');
      expect(
        portal.calls('vod', 'create_link').single.uri.queryParameters['cmd'],
        '/media/classic.mpg',
      );
    });

    test('an unresolved localhost answer is a server failure', () async {
      final portal = _FakePortal().on(
        'itv/create_link',
        (_) => _Res.js({'cmd': 'ffmpeg http://localhost/ch/1001_'}),
      );
      await expectLater(
        _api(portal).resolve(live),
        throwsA(_failure(FailureKind.server)),
      );
    });

    test('an empty stream= answer is a server failure', () async {
      final portal = _FakePortal().on(
        'itv/create_link',
        (_) => _Res.js({
          'cmd': 'ffmpeg http://stream.test/play/live.php?mac=x&stream=&e=ts',
        }),
      );
      await expectLater(
        _api(portal).resolve(live),
        throwsA(_failure(FailureKind.server)),
      );
    });

    test(
      'a real address in the cmd is the fallback when create_link fails',
      () async {
        final portal = _FakePortal().on(
          'itv/create_link',
          (_) => _Res.js({'cmd': '', 'error': 'link_fault'}),
        );
        final url = await _api(portal).resolve(
          'stalker://itv?cmd=ffmpeg+http%3A%2F%2Freal.test%2Flive%2F2.ts',
        );
        expect(url, 'http://real.test/live/2.ts');
      },
    );

    test('a numbered episode never falls back to the base address', () async {
      final portal = _FakePortal().on(
        'vod/create_link',
        (_) => _Res.js({'cmd': '', 'error': 'nothing_to_play'}),
      );
      await expectLater(
        _api(portal).resolve(
          'stalker://vod?cmd=ffmpeg+http%3A%2F%2Freal.test%2Fs.mkv&series=2',
        ),
        throwsA(_failure(FailureKind.server, 'nothing_to_play')),
      );
    });

    test('only stalker:// links are accepted', () async {
      expect(StalkerApi.isStalkerUrl(live), isTrue);
      expect(StalkerApi.isStalkerUrl('http://real.test/1.ts'), isFalse);
      expect(StalkerApi.isStalkerId('stk_1'), isTrue);
      expect(StalkerApi.isStalkerId('stke_55_1_2'), isTrue);
      expect(StalkerApi.isStalkerId('1234'), isFalse);
      final portal = _FakePortal();
      await expectLater(
        _api(portal).resolve('http://real.test/1.ts'),
        throwsA(_failure(FailureKind.parse)),
      );
      expect(portal.requests, isEmpty);
    });
  });
}
