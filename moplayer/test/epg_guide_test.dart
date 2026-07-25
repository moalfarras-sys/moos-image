// The guide, and the fixtures in it — parsed from the shapes the maintainer's
// own panel actually publishes. Every title in this file was copied out of that
// panel's `xmltv.php`, not invented.

import 'package:flutter_test/flutter_test.dart';
import 'package:moplayer_moos/models/live_match.dart';
import 'package:moplayer_moos/services/epg/xmltv_guide.dart';

const _xml = '''
<?xml version="1.0" encoding="utf-8" ?>
<tv generator-info-name="Aroma iptv">
<channel id="beIN SPORTS 1.qa"><display-name>beIN SPORTS 1</display-name></channel>
<channel id="MBC 1 HD.sa"><display-name>MBC 1 HD</display-name></channel>
<programme channel="beIN SPORTS 1.qa" start="20260713004500 +0200" stop="20260713024500 +0200">
  <title>Paris Saint-Germain vs Bayern München - UEFA Champions League 2025/26 - MD4</title>
  <desc>Matchday 4</desc>
</programme>
<programme channel="beIN SPORTS 1.qa" start="20260712230000 +0200" stop="20260713010000 +0200">
  <title>Liverpool vs Real Madrid - UEFA Champions League 2025/26 - MD4</title>
</programme>
<programme channel="MBC 1 HD.sa" start="20260712141500 +0200" stop="20260712150000 +0200">
  <title>بنات عبدالغني:الحلقة 19</title>
</programme>
</tv>
''';

void main() {
  group('EpgGuide.parse', () {
    final guide = EpgGuide.parse(_xml);

    test('programmes are indexed per channel, case-insensitively', () {
      // The panel writes `beIN SPORTS 1.qa` in the guide and `BEIN SPORTS 1.qa`
      // in the stream list. A case-sensitive lookup finds nothing while both
      // files look perfectly correct.
      expect(guide.forChannel('BEIN SPORTS 1.qa'), hasLength(2));
      expect(guide.forChannel('MBC 1 HD.sa'), hasLength(1));
      expect(guide.forChannel('nothing.here'), isEmpty);
      expect(guide.forChannel(null), isEmpty);
    });

    test('entries are sorted by start time, not document order', () {
      final entries = guide.forChannel('beIN SPORTS 1.qa');
      expect(entries.first.title, startsWith('Liverpool'));
      expect(entries.last.title, startsWith('Paris Saint-Germain'));
    });

    test('the XMLTV offset is honoured — not read as local time', () {
      // 00:45 at +0200 is 22:45 UTC the previous day. Read as local time by a
      // viewer one zone over, a kick-off lands an hour out: the kind of wrong
      // that looks right.
      final match = guide.matches.firstWhere((m) => m.home.startsWith('Paris'));
      expect(match.start.toUtc(), DateTime.utc(2026, 7, 12, 22, 45));
    });

    test('a non-fixture programme is not a match', () {
      expect(guide.matches.any((m) => m.home.contains('بنات')), isFalse);
      expect(guide.matches, hasLength(2));
    });

    test('a programme published twice is one programme', () {
      // Not hypothetical: the maintainer's panel lists `Germany vs Spain` on
      // beIN SPORTS 1 at 13:45 in two identical elements, and does the same for
      // most of the evening. Rendered faithfully, the match strip shows every
      // game twice — which reads as a bug in this app, not in the panel.
      final doubled = EpgGuide.parse('''
<tv>
<programme channel="beIN SPORTS 1.qa" start="20260713134500 +0200" stop="20260713153000 +0200">
  <title>Germany vs Spain - Final - UEFA Women's Under-19 Championship</title>
</programme>
<programme channel="beIN SPORTS 1.qa" start="20260713134500 +0200" stop="20260713153000 +0200">
  <title>Germany vs Spain - Final - UEFA Women's Under-19 Championship</title>
</programme>
</tv>
''');
      expect(doubled.forChannel('beIN SPORTS 1.qa'), hasLength(1));
      expect(doubled.matches, hasLength(1));
    });

    test('an HTML error page is an empty guide, not a crash', () {
      expect(
        EpgGuide.parse('<html><body>Forbidden</body></html>').isEmpty,
        isTrue,
      );
      expect(EpgGuide.parse('').isEmpty, isTrue);
      expect(EpgGuide.parse('not xml at all <<<').isEmpty, isTrue);
    });
  });

  group('LiveMatch.tryParse', () {
    LiveMatch? parse(String title) => LiveMatch.tryParse(
      title,
      start: DateTime(2026, 7, 13, 20),
      end: DateTime(2026, 7, 13, 22),
      epgChannelId: 'c',
    );

    test('the fixture is split before the competition, not after', () {
      // Splitting on " - " first would cut Saint-Gilloise in half.
      final m = parse(
        'Atlético de Madrid vs Union Saint-Gilloise - UEFA Champions League 2025/26 - MD4',
      )!;
      expect(m.home, 'Atlético de Madrid');
      expect(m.away, 'Union Saint-Gilloise');
      expect(m.competition, 'UEFA Champions League 2025/26 - MD4');
    });

    test('country tags survive', () {
      final m = parse(
        'Al Ahli (KSA) vs FC Machida Zelvia (JPN) - AFC Champions League Elite - Final',
      )!;
      expect(m.home, 'Al Ahli (KSA)');
      expect(m.away, 'FC Machida Zelvia (JPN)');
    });

    test('Arabic fixtures, and the bare "v" form', () {
      expect(parse('الأهلي ضد الزمالك')!.away, 'الزمالك');
      expect(parse('Spain v Belgium')!.home, 'Spain');
    });

    test('what is not a fixture', () {
      expect(parse('Champions League Magazine'), isNull);
      expect(parse('بنات عبدالغني:الحلقة 19'), isNull);
      expect(parse(''), isNull);
    });
  });
}
