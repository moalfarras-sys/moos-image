import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:moplayer_moos/core/l10n/strings.dart';
import 'package:moplayer_moos/features/player/player_tuning.dart';
import 'package:moplayer_moos/services/player/playback_stats.dart';

/// The player's tuning controls and its engine readout.
///
/// These exist because "the video is not smooth" is the report this panel has
/// to answer, and it can only do that if the numbers are right *and* legible in
/// both writing directions. The maintainer's desktop runs Arabic; a readout that
/// reverses a negative delay or mirrors a resolution is worse than none.
Widget _host(Widget child, {TextDirection direction = TextDirection.rtl}) {
  return MaterialApp(
    home: Directionality(
      textDirection: direction,
      child: Scaffold(
        backgroundColor: const Color(0xFF101214),
        body: SingleChildScrollView(child: child),
      ),
    ),
  );
}

void main() {
  final s = S(Lang.ar);
  final en = S(Lang.en);

  group('PlaybackStatsBody', () {
    testWidgets('says so plainly before the first frame is decoded', (
      tester,
    ) async {
      await tester.pumpWidget(
        _host(PlaybackStatsBody(stats: null, strings: s)),
      );
      expect(find.text(s.statsUnavailable), findsOneWidget);
    });

    testWidgets('a stream with no resolution yet is still "not available"', (
      tester,
    ) async {
      // mpv reports codec and cache before it reports width/height. Showing a
      // half-filled table in that window looks like a fault rather than a wait.
      await tester.pumpWidget(
        _host(
          PlaybackStatsBody(
            stats: const PlaybackStats(videoCodec: 'h264'),
            strings: s,
          ),
        ),
      );
      expect(find.text(s.statsUnavailable), findsOneWidget);
    });

    testWidgets('reports hardware decoding, resolution and frame rate', (
      tester,
    ) async {
      await tester.pumpWidget(
        _host(
          PlaybackStatsBody(
            stats: const PlaybackStats(
              hwdec: 'nvdec',
              videoCodec: 'H.264',
              width: 3840,
              height: 2160,
              containerFps: 60,
              currentFps: 59.9,
              droppedFrames: 0,
              decoderDroppedFrames: 0,
              videoBitrate: 24500000,
              audioCodec: 'aac',
              audioChannels: 2,
              cacheSeconds: 18.4,
            ),
            strings: s,
          ),
        ),
      );

      expect(find.textContaining('nvdec'), findsOneWidget);
      expect(find.textContaining(s.statsHardware), findsOneWidget);
      // The label a viewer recognises has to accompany the raw numbers.
      expect(find.textContaining('4K'), findsOneWidget);
      expect(find.textContaining('3840×2160'), findsOneWidget);
      expect(find.textContaining('24.5 Mb/s'), findsOneWidget);
      expect(find.textContaining('18.4 s'), findsOneWidget);
    });

    testWidgets('software decoding is called out, not buried', (tester) async {
      // The single most important line on the panel: a 4K stream on the CPU is
      // the difference between watchable and not, and nothing else in the app
      // reveals it.
      await tester.pumpWidget(
        _host(
          PlaybackStatsBody(
            stats: const PlaybackStats(width: 1920, height: 1080),
            strings: en,
          ),
        ),
      );
      expect(find.text(en.statsSoftware), findsOneWidget);
    });

    testWidgets('dropped frames from both counters are summed', (tester) async {
      await tester.pumpWidget(
        _host(
          PlaybackStatsBody(
            stats: const PlaybackStats(
              width: 1920,
              height: 1080,
              droppedFrames: 12,
              decoderDroppedFrames: 5,
            ),
            strings: s,
          ),
        ),
      );
      // A viewer does not care which stage lost the frame, only that 17 went
      // missing — but summing them is the kind of thing that silently becomes
      // "show one and ignore the other" during a refactor.
      expect(find.text('17'), findsOneWidget);
    });

    testWidgets('lays out in both writing directions', (tester) async {
      const stats = PlaybackStats(
        hwdec: 'vaapi',
        videoCodec: 'HEVC',
        width: 1920,
        height: 1080,
        containerFps: 25,
        currentFps: 25,
        cacheSeconds: 9.5,
      );
      for (final direction in TextDirection.values) {
        await tester.pumpWidget(
          _host(
            PlaybackStatsBody(stats: stats, strings: s),
            direction: direction,
          ),
        );
        expect(tester.takeException(), isNull);
        expect(find.textContaining('1920×1080'), findsOneWidget);
      }
    });
  });

  group('NudgeRow', () {
    testWidgets('minus, plus and reset each fire once', (tester) async {
      var value = 0.0;
      var resets = 0;
      await tester.pumpWidget(
        _host(
          StatefulBuilder(
            builder: (context, setState) => NudgeRow(
              icon: Icons.volume_up_rounded,
              label: s.audioDelay,
              value: value.toStringAsFixed(2),
              decreaseLabel: s.decreaseSetting(s.audioDelay),
              increaseLabel: s.increaseSetting(s.audioDelay),
              onDecrease: () => setState(() => value -= 0.05),
              onIncrease: () => setState(() => value += 0.05),
              onReset: () => setState(() {
                value = 0;
                resets++;
              }),
              resetTooltip: s.resetSetting(s.audioDelay),
            ),
          ),
        ),
      );

      await tester.tap(find.byIcon(Icons.add_rounded));
      await tester.pump();
      expect(value, closeTo(0.05, 1e-9));

      await tester.tap(find.byIcon(Icons.remove_rounded));
      await tester.tap(find.byIcon(Icons.remove_rounded));
      await tester.pump();
      expect(value, closeTo(-0.05, 1e-9));

      await tester.tap(find.byIcon(Icons.settings_backup_restore_rounded));
      await tester.pump();
      expect(value, 0);
      expect(resets, 1);
    });

    testWidgets('a signed value is not reordered by an Arabic layout', (
      tester,
    ) async {
      // `-0.25s` must read as minus a quarter second in Arabic too. Left to the
      // ambient direction, the sign migrates to the wrong end of the number and
      // the control becomes actively misleading.
      await tester.pumpWidget(
        _host(
          NudgeRow(
            icon: Icons.closed_caption_rounded,
            label: s.subtitleDelay,
            value: '−0.25s',
            decreaseLabel: s.decreaseSetting(s.subtitleDelay),
            increaseLabel: s.increaseSetting(s.subtitleDelay),
            onDecrease: () {},
            onIncrease: () {},
          ),
        ),
      );
      final text = tester.widget<Text>(find.text('−0.25s'));
      expect(text.textDirection, TextDirection.ltr);
    });

    testWidgets('step actions have localized semantics and 40 px targets', (
      tester,
    ) async {
      await tester.pumpWidget(
        _host(
          NudgeRow(
            icon: Icons.volume_up_rounded,
            label: s.audioDelay,
            value: '+0.00s',
            decreaseLabel: s.decreaseSetting(s.audioDelay),
            increaseLabel: s.increaseSetting(s.audioDelay),
            onDecrease: () {},
            onIncrease: () {},
            onReset: () {},
            resetTooltip: s.resetSetting(s.audioDelay),
          ),
        ),
      );

      for (final label in [
        s.decreaseSetting(s.audioDelay),
        s.increaseSetting(s.audioDelay),
        s.resetSetting(s.audioDelay),
      ]) {
        final action = find.bySemanticsLabel(label);
        expect(action, findsOneWidget);
        final rect = tester.getRect(action);
        expect(rect.width, greaterThanOrEqualTo(40));
        expect(rect.height, greaterThanOrEqualTo(40));
        expect(tester.getSemantics(action).flagsCollection.isButton, isTrue);
      }
    });

    testWidgets('reset is absent when no handler is given', (tester) async {
      await tester.pumpWidget(
        _host(
          NudgeRow(
            icon: Icons.format_size_rounded,
            label: s.subtitleSize,
            value: '100%',
            decreaseLabel: s.decreaseSetting(s.subtitleSize),
            increaseLabel: s.increaseSetting(s.subtitleSize),
            onDecrease: () {},
            onIncrease: () {},
          ),
        ),
      );
      expect(find.byIcon(Icons.settings_backup_restore_rounded), findsNothing);
    });
  });

  group('PlaybackStats', () {
    test('quality labels follow what a viewer would call the height', () {
      String? label(int h) => PlaybackStats(width: 16, height: h).qualityLabel;
      expect(label(2160), '4K');
      expect(label(1440), '1440p');
      expect(label(1080), '1080p');
      expect(label(720), '720p');
      expect(label(576), '576p');
      expect(label(360), '360p');
    });

    test('a stream with no dimensions has no resolution to show', () {
      const stats = PlaybackStats(width: 0, height: 0);
      expect(stats.resolution, isNull);
      expect(stats.qualityLabel, isNull);
    });

    test('an empty hwdec is software, not a decoder named ""', () {
      expect(const PlaybackStats().isHardwareDecoded, isFalse);
      expect(const PlaybackStats(hwdec: 'nvdec').isHardwareDecoded, isTrue);
    });
  });

  group('stampedName', () {
    final at = DateTime(2026, 7, 26, 20, 5, 9);

    test('sorts chronologically and keeps the title readable', () {
      expect(
        stampedName('Al Jazeera HD', 'mkv', at),
        'Al Jazeera HD 2026-07-26 200509.mkv',
      );
    });

    test('strips characters that are not legal in a file name', () {
      // Channel names really do contain slashes and colons — "beIN SPORTS 1
      // HD: MAX 4/5" is the sort of thing a panel sends — and a recording that
      // silently lands in a directory that does not exist is a lost recording.
      final name = stampedName('beIN: MAX 4/5 <HD>', 'mkv', at);
      expect(name, isNot(contains('/')));
      expect(name, isNot(contains(':')));
      expect(name, isNot(contains('<')));
      expect(name.endsWith('.mkv'), isTrue);
    });

    test('a very long title cannot produce an unopenable path', () {
      final name = stampedName('x' * 400, 'png', at);
      // Comfortably inside every filesystem's 255-byte component limit, with
      // the stamp and extension still attached.
      expect(name.length, lessThan(120));
      expect(name.endsWith('.png'), isTrue);
    });

    test('an empty title still yields a usable name', () {
      expect(stampedName('   ', 'mkv', at), startsWith('MoPlayer '));
    });
  });

  group('SleepTimer', () {
    test('starts inactive and reports nothing remaining', () {
      final timer = SleepTimer();
      addTearDown(timer.dispose);
      expect(timer.isActive, isFalse);
      expect(timer.remaining, isNull);
    });

    test('setting null cancels without firing', () {
      var fired = 0;
      final timer = SleepTimer();
      addTearDown(timer.dispose);
      timer.set(const Duration(minutes: 30), onFire: () => fired++);
      expect(timer.isActive, isTrue);
      timer.set(null, onFire: () => fired++);
      expect(timer.isActive, isFalse);
      expect(fired, 0);
    });

    test('fires once, then reports itself finished', () async {
      var fired = 0;
      final timer = SleepTimer();
      addTearDown(timer.dispose);
      timer.set(const Duration(milliseconds: 20), onFire: () => fired++);
      await Future<void>.delayed(const Duration(milliseconds: 80));
      expect(fired, 1);
      expect(timer.isActive, isFalse);
    });

    test('re-setting replaces rather than stacks', () async {
      var fired = 0;
      final timer = SleepTimer();
      addTearDown(timer.dispose);
      timer.set(const Duration(milliseconds: 20), onFire: () => fired++);
      timer.set(const Duration(milliseconds: 40), onFire: () => fired++);
      await Future<void>.delayed(const Duration(milliseconds: 120));
      // Two timers both firing would stop playback twice and, worse, make the
      // second choice silently lose to the first.
      expect(fired, 1);
    });
  });

  group('mediaOutputDir', () {
    test('recordings go somewhere the user can find them', () {
      // Deliberately the user's own folders, unlike application *state*, which
      // must never go there.
      expect(mediaOutputDir('Videos'), endsWith('/Videos/MoPlayer'));
      expect(mediaOutputDir('Pictures'), endsWith('/Pictures/MoPlayer'));
    });
  });

  group('TimeshiftWindow', () {
    TimeshiftWindow at(int startS, int edgeS, int posS) => TimeshiftWindow(
      start: Duration(seconds: startS),
      edge: Duration(seconds: edgeS),
      position: Duration(seconds: posS),
    );

    test('a channel that just opened offers no scrub', () {
      // The bar must say LIVE rather than render a control that cannot move.
      expect(TimeshiftWindow.empty.isSeekable, isFalse);
      expect(at(100, 101, 101).isSeekable, isFalse);
      expect(at(100, 400, 400).isSeekable, isTrue);
    });

    test('"behind live" is what a viewer can act on, not stream time', () {
      final w = at(100, 400, 340);
      expect(w.behind, const Duration(seconds: 60));
      expect(w.span, const Duration(seconds: 300));
    });

    test('being fractionally past the edge is not negative time', () {
      // mpv's position can momentarily exceed the last demuxed timestamp.
      // A bar showing "-−0:01" would be a bug the user sees.
      final w = TimeshiftWindow(
        start: Duration.zero,
        edge: const Duration(seconds: 10),
        position: const Duration(seconds: 11),
      );
      expect(w.behind, Duration.zero);
      expect(w.behind.isNegative, isFalse);
    });

    test('within a second of the edge counts as live', () {
      // Otherwise "back to live" stays lit while the user is watching live,
      // which reads as a stuck button.
      expect(at(0, 300, 300).isAtLiveEdge, isTrue);
      expect(
        TimeshiftWindow(
          start: Duration.zero,
          edge: const Duration(seconds: 300),
          position: const Duration(milliseconds: 299500),
        ).isAtLiveEdge,
        isTrue,
      );
      expect(at(0, 300, 297).isAtLiveEdge, isFalse);
    });
  });

  group('PictureAdjustment', () {
    test('maps to the mpv video-equalizer property names', () {
      expect(
        PictureAdjustment.values.map((a) => a.mpvProperty),
        containsAll(['brightness', 'contrast', 'saturation', 'gamma']),
      );
    });
  });

  group('DeinterlaceMode', () {
    test('maps to the literal values mpv accepts', () {
      // These strings go straight into `mpv_set_property`. A typo here does not
      // throw — mpv rejects it and the channel keeps combing.
      expect(DeinterlaceMode.auto.mpvValue, 'auto');
      expect(DeinterlaceMode.on.mpvValue, 'yes');
      expect(DeinterlaceMode.off.mpvValue, 'no');
    });
  });
}
