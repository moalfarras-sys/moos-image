import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:moplayer_moos/core/l10n/strings.dart';
import 'package:moplayer_moos/models/live_match.dart';
import 'package:moplayer_moos/services/weather/weather_service.dart';
import 'package:moplayer_moos/widgets/match_strip.dart';
import 'package:moplayer_moos/widgets/weather_tile.dart';

/// The fixtures strip and the weather tile share one row on the home page, and
/// that row is built inside a `ListView` — an unbounded cross axis.
///
/// Laying it out with `CrossAxisAlignment.stretch` there made the strip paint
/// outside its own box and straight through the rail below it: two rows of
/// posters and two sets of titles drawn on top of each other. It rendered, it
/// threw nothing, and only a screenshot showed it. So the arrangement gets a
/// test that puts it in the same unbounded context the real page does.
void main() {
  final strings = S(Lang.ar);

  final matches = [
    for (var i = 0; i < 6; i++)
      LiveMatch(
        home: 'Team A $i',
        away: 'Team B $i',
        start: DateTime(2026, 7, 26, 20 + i),
        end: DateTime(2026, 7, 26, 22 + i),
        epgChannelId: 'ch$i',
        competition: 'League $i',
        channelName: 'BEIN SPORTS $i',
        streamId: '$i',
      ),
  ];

  const weather = WeatherNow(
    city: 'Berlin',
    temperature: 20,
    code: 61,
    isDay: true,
    high: 26,
    low: 18,
  );

  /// The home page's real context: a vertically scrolling list, so the row's
  /// cross axis is unbounded exactly as it is in production.
  Widget host(Widget child, {double width = 1400}) => MaterialApp(
    home: Directionality(
      textDirection: TextDirection.rtl,
      child: Scaffold(
        body: SizedBox(
          width: width,
          child: ListView(children: [child, const SizedBox(height: 400)]),
        ),
      ),
    ),
  );

  testWidgets('the strip and the tile lay out side by side without overflow', (
    tester,
  ) async {
    await tester.pumpWidget(
      host(
        Row(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            WeatherTile(weather: weather, strings: strings, width: 260),
            const SizedBox(width: 16),
            Expanded(
              child: MatchStrip(
                matches: matches,
                strings: strings,
                onPlay: (_) {},
              ),
            ),
          ],
        ),
      ),
    );
    await tester.pump();

    // An overflow in this row is reported as an exception rather than thrown,
    // so it has to be asked for by name — `pumpWidget` alone stays green.
    expect(tester.takeException(), isNull);
    expect(find.byType(MatchStrip), findsOneWidget);
    expect(find.byType(WeatherTile), findsOneWidget);
  });

  testWidgets('the strip keeps its own height and does not spill downwards', (
    tester,
  ) async {
    await tester.pumpWidget(
      host(
        Row(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            WeatherTile(weather: weather, strings: strings, width: 260),
            const SizedBox(width: 16),
            Expanded(
              child: MatchStrip(
                matches: matches,
                strings: strings,
                onPlay: (_) {},
              ),
            ),
          ],
        ),
      ),
    );
    await tester.pump();

    // 128 is MatchStrip's declared height. When the row stretched it into an
    // unbounded axis this grew without limit, which is what put the fixtures on
    // top of the rail underneath.
    expect(tester.getSize(find.byType(MatchStrip)).height, 128);
  });

  testWidgets('a narrow window stacks them instead of squeezing', (
    tester,
  ) async {
    await tester.pumpWidget(
      host(
        Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            MatchStrip(matches: matches, strings: strings, onPlay: (_) {}),
            const SizedBox(height: 16),
            WeatherTile(
              weather: weather,
              strings: strings,
              width: double.infinity,
            ),
          ],
        ),
        width: 700,
      ),
    );
    await tester.pump();
    expect(tester.takeException(), isNull);
  });
}
