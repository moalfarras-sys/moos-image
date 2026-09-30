// A playlist is sorted into what it contains.
//
// The owner's subscription, exported as `m3u_plus`, is 395,424 entries: 12,975
// channels, 20,301 films and 362,879 episode files. Read as "channels" it filled
// Live TV with every episode of every series and left Films and Series empty.

import 'package:flutter_test/flutter_test.dart';
import 'package:moplayer_moos/services/m3u/m3u_parser.dart';

const _playlist = '''
#EXTM3U url-tvg="http://guide.example/epg.xml.gz,http://other/epg.xml"
#EXTINF:-1 tvg-id="bein1.qa" tvg-logo="http://l/b1.png" group-title="Sport",beIN Sports 1
http://panel.example/live/u/p/101.m3u8
#EXTINF:-1 tvg-logo="http://l/m.jpg" group-title="Movies | 2024",Dune: Part Two (2024)
http://panel.example/movie/u/p/5001.mkv
#EXTINF:-1 group-title="Series EN",Severance S01 E02
http://panel.example/series/u/p/9002.mkv
#EXTINF:-1 group-title="Series EN",Severance S01 E01
http://panel.example/series/u/p/9001.mkv
#EXTINF:-1 group-title="Series EN",Severance S02E01
http://panel.example/series/u/p/9101.mp4
#EXTINF:-1 group-title="مسلسلات",الهيبة الموسم 2 الحلقة 3
http://cdn.example/files/haiba-2-3.mp4
#EXTINF:-1 tvg-type="movie" group-title="Kids",A Stream Tagged As Film
http://cdn.example/stream/abc
#EXTINF:-1 group-title="Home videos",Holiday, beach day
file:///home/me/Videos/beach.mp4
''';

void main() {
  late M3uLibrary library;
  setUpAll(() => library = M3uParser.parseLibrary(_playlist));

  test('channels, films and series each land on their own shelf', () {
    expect(library.live.items.map((c) => c.name), ['beIN Sports 1']);
    expect(library.movies.items.map((m) => m.name), [
      'Dune: Part Two (2024)',
      'A Stream Tagged As Film',
      'Holiday, beach day',
    ]);
    expect(library.series.items.map((s) => s.name), ['Severance', 'الهيبة']);
  });

  test('episodes are gathered under their series in season order', () {
    final severance = library.series.items.first;
    final episodes = library.episodes[severance.seriesId]!;
    expect(
      episodes.map((e) => 'S${e.seasonNumber}E${e.episodeNum}'),
      ['S1E1', 'S1E2', 'S2E1'],
    );
    expect(episodes.first.directUrl, 'http://panel.example/series/u/p/9001.mkv');

    final haiba = library.series.items.last;
    final arabic = library.episodes[haiba.seriesId]!.single;
    expect(arabic.seasonNumber, 2);
    expect(arabic.episodeNum, 3);
  });

  test('films keep their address, year and category', () {
    final dune = library.movies.items.first;
    expect(dune.directUrl, 'http://panel.example/movie/u/p/5001.mkv');
    expect(dune.year, '2024');
    expect(dune.categoryId, 'Movies | 2024');
    expect(dune.containerExtension, 'mkv');
  });

  test('a title with a comma keeps the whole title', () {
    expect(library.movies.items.last.name, 'Holiday, beach day');
  });

  test('the header guide is the first listed address', () {
    expect(library.guideUrl, 'http://guide.example/epg.xml.gz');
  });

  test('categories carry counts for every shelf', () {
    expect(library.series.categories.map((c) => (c.name, c.count)), [
      ('Series EN', 1),
      ('مسلسلات', 1),
    ]);
    expect(library.totalEntries, 1 + 3 + 4);
  });

  test('ids are the address hash, stable across parses', () {
    final again = M3uParser.parseLibrary(_playlist);
    expect(
      again.movies.items.first.streamId,
      library.movies.items.first.streamId,
    );
    expect(library.live.items.single.streamId, startsWith('m3u_'));
  });

  test('episode markers', () {
    expect(M3uParser.episodeMarker('Dark 1x05'), (
      series: 'Dark',
      season: 1,
      episode: 5,
    ));
    expect(M3uParser.episodeMarker('Friends - S10E17 - The Last One'), (
      series: 'Friends',
      season: 10,
      episode: 17,
    ));
    expect(M3uParser.episodeMarker('Formula 1 2024'), isNull);
  });
}
