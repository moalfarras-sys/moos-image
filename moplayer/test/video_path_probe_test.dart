import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:moplayer_moos/services/player/video_path_probe.dart';

/// MoPlayer renders video through a GL texture, and the historical way that
/// fails on NVIDIA is the process disappearing — no exception, no coredump,
/// nothing to assert on from inside. [VideoPathProbe] is the entire safety net
/// for that, and a safety net nobody has pulled on is a decoration.
///
/// So this exercises the two things the net has to get right, which pull in
/// opposite directions: it must give up after repeated silent deaths, and it
/// must **not** give up because the user closed the window early twice.
void main() {
  group('VideoPathProbe', () {
    late Directory dir;
    late String path;

    setUp(() {
      dir = Directory.systemTemp.createTempSync('moplayer-probe');
      path = '${dir.path}/video-path.probe';
    });

    tearDown(() => dir.deleteSync(recursive: true));

    VideoPathProbe probe() => VideoPathProbe(path: path);

    test('a machine that has never run the app tries the GPU path', () {
      expect(probe().failures, 0);
      expect(probe().isTripped, isFalse);
    });

    test('one silent death is treated as noise, not a verdict', () {
      probe().armed(); // launch 1: armed, then the process vanishes.
      expect(probe().isTripped, isFalse, reason: 'one crash could be a pkill');
    });

    test('two consecutive silent deaths fall back to the CPU path', () {
      probe().armed();
      probe().armed();
      expect(probe().failures, 2);
      expect(probe().isTripped, isTrue);
    });

    test('healthy playback forgives every earlier failure at once', () {
      probe().armed();
      probe().armed();
      expect(probe().isTripped, isTrue);

      // A driver update fixes the crash. The next good run must restore the
      // good path immediately — not after as many good runs as there were bad.
      final good = probe()..armed();
      good.healthy();

      expect(probe().failures, 0);
      expect(probe().isTripped, isFalse);
      expect(File(path).existsSync(), isFalse);
    });

    test('a clean run leaves nothing behind for the next one to find', () {
      final first = probe()..armed();
      first.healthy();
      final second = probe()..armed();
      second.healthy();
      expect(probe().failures, 0);
    });

    test('healthy is idempotent — dispose may follow the health timer', () {
      final p = probe()..armed();
      p.healthy();
      expect(p.isCleared, isTrue);
      p.healthy(); // PlayerService.dispose() calls this too. Must not throw.
      expect(probe().failures, 0);
    });

    test('an unwritable home never decides how video is rendered', () {
      // `bootstrap()` is required to survive a read-only or missing home. The
      // frame path is not the exception: an unreadable probe means "go ahead".
      final unwritable = VideoPathProbe(path: '/proc/moplayer/video.probe');
      expect(unwritable.failures, 0);
      expect(unwritable.isTripped, isFalse);
      expect(unwritable.armed, returnsNormally);
      expect(unwritable.healthy, returnsNormally);
    });

    test('browsing the library is not a driver crash', () {
      // The regression this pins: the probe used to clear only after ten
      // unbroken seconds of playback, so opening MoPlayer to look at something
      // and closing it sooner counted as an unproven GPU start. Twice in a row
      // tripped it, and the maintainer's RTX 2080 rendered video on the CPU
      // from 2026-07-26 to 2026-08-03 without a single real driver crash.
      //
      // PlayerService now calls healthy() the moment real videoParams arrive —
      // frame parameters mean the shared GL texture was created and a decoded
      // frame came through it, which IS the window the driver takes the
      // process in. One frame is the proof; ten seconds was a guess.
      final p1 = probe();
      p1.armed();
      p1.healthy(); // first frame presented, well under ten seconds
      expect(probe().failures, 0, reason: 'a proven start must leave nothing behind');

      // And two such sessions in a row must still leave the GPU path armed.
      final p2 = probe();
      p2.armed();
      p2.healthy();
      expect(probe().isTripped, isFalse);
      expect(probe().failures, 0);
    });

    test('two genuinely unproven starts still trip the guard', () {
      // The other half of the contract: this guard exists because the GL path
      // really did take the process down on an RTX 2080. Narrowing what counts
      // as an attempt must not disarm it.
      probe().armed();
      probe().armed();
      expect(probe().isTripped, isTrue);
    });

    test('a corrupt probe counts as zero rather than stranding the user', () {
      File(path).writeAsStringSync('not a number');
      expect(probe().failures, 0);
      expect(probe().isTripped, isFalse);
    });
  });
}
