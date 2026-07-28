// The link a user is actually handed, in the shapes it is actually handed in.
//
// The case that matters most is the first group: a `get.php` link read as a
// plain M3U playlist yields live channels and *nothing else* — no films, no
// series, no EPG — while the same link read as what it is yields the whole
// panel. The credentials are sitting in the query string either way.

import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:moplayer_moos/models/playlist_config.dart';
import 'package:moplayer_moos/services/source/source_link.dart';

void main() {
  // The bundled demo has to actually be BUNDLED. asset://demo.m3u resolves (in
  // both _readM3uBody implementations) to assets/<name> = assets/demo.m3u, and
  // rootBundle can only find it if pubspec.yaml packs it. This drifted once: the
  // file was git-tracked at assets/demo/demo.m3u, undeclared in pubspec and off
  // the asset:// mapping, so `moplayer asset://demo.m3u` threw "Unable to load
  // asset" in the shipped app while every test passed. Tie the three together.
  group('the bundled demo playlist is shippable', () {
    test('asset://demo.m3u maps to a file that exists and is declared', () {
      // The exact mapping the app uses: asset://<name> -> assets/<name>.
      const url = 'asset://demo.m3u';
      final asset = 'assets/${url.substring('asset://'.length)}';
      expect(asset, 'assets/demo.m3u',
          reason: 'the resolver maps asset://<name> to assets/<name>');
      expect(File(asset).existsSync(), isTrue,
          reason: '$asset must exist at exactly the path asset://demo.m3u loads');

      final pubspec = File('pubspec.yaml').readAsStringSync();
      final declared = pubspec.contains('- assets/demo.m3u') ||
          RegExp(r'-\s*assets/demo/\s*$', multiLine: true).hasMatch(pubspec);
      expect(declared, isTrue,
          reason: 'pubspec.yaml flutter.assets must pack assets/demo.m3u, '
              'or rootBundle.loadString throws "Unable to load asset"');
    });
  });
  group('a link that carries an account is an Xtream account', () {
    test('the shape every subscription is sold in', () {
      final c = SourceLink.parse(
        'http://panel.example:8080/get.php?username=U1&password=P1'
        '&type=m3u_plus&output=m3u8',
      )!;

      expect(c.type, PlaylistType.xtream);
      expect(c.serverUrl, 'http://panel.example:8080');
      expect(c.username, 'U1');
      expect(c.password, 'P1');
      expect(c.name, 'panel.example');
    });

    test('an explicit :80 is kept — a panel that states a port means it', () {
      final c = SourceLink.parse(
        'http://panel.example:80/get.php?username=U&password=P&type=m3u_plus',
      )!;
      // Uri.origin would drop this, and a source that silently changed its own
      // port is a source that stops playing on a server the user can see is up.
      expect(c.serverUrl, 'http://panel.example:80');
    });

    test('player_api.php, https, and a panel with no port', () {
      final c = SourceLink.parse(
        'https://tv.example/player_api.php?username=U&password=P',
      )!;
      expect(c.type, PlaylistType.xtream);
      expect(c.serverUrl, 'https://tv.example');
    });

    test('an unknown endpoint with both credentials is still an account', () {
      // Panels are reskinned constantly. The two query parameters are the proof;
      // the endpoint's name adds nothing to it.
      final c = SourceLink.parse(
        'http://p.example/enigma2.php?username=U&password=P',
      )!;
      expect(c.type, PlaylistType.xtream);
    });

    test('carriesAccount is what the login screen tells the user', () {
      expect(
        SourceLink.carriesAccount(
          'http://p.example/get.php?username=U&password=P&type=m3u_plus',
        ),
        isTrue,
      );
      expect(SourceLink.carriesAccount('http://p.example/list.m3u'), isFalse);
    });
  });

  group('a link that carries no account is a playlist, or nothing', () {
    test('a plain .m3u URL', () {
      final c = SourceLink.parse('http://example.com/lists/tv.m3u')!;
      expect(c.type, PlaylistType.m3u);
      expect(c.m3uUrl, 'http://example.com/lists/tv.m3u');
      expect(c.name, 'tv.m3u');
    });

    test('get.php with a type but no credentials is still just a playlist', () {
      final c = SourceLink.parse('http://p.example/get.php?type=m3u_plus')!;
      expect(c.type, PlaylistType.m3u);
    });

    test('a bare panel URL is not a source — the form asks for the rest', () {
      expect(SourceLink.parse('http://panel.example:8080/c/'), isNull);
      expect(
        SourceLink.panelOrigin('http://panel.example:8080/c/'),
        'http://panel.example:8080',
      );
    });

    test(
      'a bare .m3u path is absolutised — Kickoff launches from elsewhere',
      () {
        final c = SourceLink.parse('assets/demo.m3u')!;
        expect(c.type, PlaylistType.m3u);
        expect(c.m3uUrl, startsWith('file:///'));
        expect(c.m3uUrl, endsWith('assets/demo.m3u'));
      },
    );

    test('asset:// and file:// survive verbatim', () {
      expect(SourceLink.parse('asset://demo.m3u')!.m3uUrl, 'asset://demo.m3u');
      expect(
        SourceLink.parse('file:///tv/list.m3u')!.m3uUrl,
        'file:///tv/list.m3u',
      );
    });

    test('what is not a source at all', () {
      expect(SourceLink.parse(''), isNull);
      expect(SourceLink.parse('   '), isNull);
      expect(SourceLink.parse('hello'), isNull);
      expect(SourceLink.parse('ftp://example.com/tv.m3u'), isNull);
      expect(SourceLink.parse('http://example.com/'), isNull);
    });
  });
}
