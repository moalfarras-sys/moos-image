import 'package:flutter_test/flutter_test.dart';
import 'package:moplayer_moos/services/m3u/m3u_parser.dart';

/// M3U in the wild is not a format, it is a habit. These are the shapes real
/// IPTV providers actually emit — including the ones that would make a strict
/// parser throw and take the whole channel list with it.
void main() {
  group('M3uParser', () {
    test('parses the common #EXTINF shape', () {
      const playlist = '''
#EXTM3U
#EXTINF:-1 tvg-id="bbc1.uk" tvg-logo="http://logos/bbc1.png" group-title="UK",BBC One
http://panel.example/live/user/pass/1.ts
#EXTINF:-1 tvg-id="bbc2.uk" group-title="UK",BBC Two
http://panel.example/live/user/pass/2.ts
''';

      final result = M3uParser.parse(playlist);

      expect(result.channels, hasLength(2));
      expect(result.channels.first.name, 'BBC One');
      expect(result.channels.first.logo, 'http://logos/bbc1.png');
      expect(result.channels.first.epgChannelId, 'bbc1.uk');
      expect(result.channels.first.directUrl, 'http://panel.example/live/user/pass/1.ts');
      expect(result.categories.map((c) => c.name), contains('UK'));
    });

    test('a channel with no group still lands somewhere', () {
      const playlist = '''
#EXTM3U
#EXTINF:-1,Orphan Channel
http://panel.example/live/user/pass/9.ts
''';

      final result = M3uParser.parse(playlist);

      expect(result.channels, hasLength(1));
      // The alternative — dropping it — is how a user ends up with a playlist
      // that silently has fewer channels than the file they pasted.
      expect(result.channels.single.categoryId, isNotNull);
      expect(result.categories, isNotEmpty);
    });

    test('ids are stable across parses of the same playlist', () {
      const playlist = '''
#EXTM3U
#EXTINF:-1,Channel
http://panel.example/live/user/pass/1.ts
''';

      final first = M3uParser.parse(playlist).channels.single.streamId;
      final second = M3uParser.parse(playlist).channels.single.streamId;

      // Favourites and resume positions are keyed on this id. If it were derived
      // from list position or a counter, re-importing the same playlist would
      // orphan every favourite the user had.
      expect(first, second);
    });

    test('junk between entries does not abort the parse', () {
      const playlist = '''
#EXTM3U
# a comment nobody asked for
#EXTVLCOPT:network-caching=1000
#EXTINF:-1,Good Channel
http://panel.example/live/user/pass/1.ts

#EXTINF:-1,Another
http://panel.example/live/user/pass/2.ts
''';

      final result = M3uParser.parse(playlist);
      expect(result.channels, hasLength(2));
    });

    test('an empty playlist is empty, not an exception', () {
      final result = M3uParser.parse('#EXTM3U\n');
      expect(result.channels, isEmpty);
      expect(result.categories, isEmpty);
    });
  });
}
