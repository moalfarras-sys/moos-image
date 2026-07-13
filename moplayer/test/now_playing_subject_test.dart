// The Live screen's pane took its four fields with `previewed?.x ?? playing!.y`.
// That reads as "fall back to the playing stream when nothing is previewed", and
// it is not what it does: `??` falls through whenever the *field* is null, not
// only when the channel is. `logo` and `epgChannelId` are optional on
// LiveChannel — thousands of the 12,653 channels on the owner's panel carry
// neither — so previewing one of them with nothing playing dereferenced a null
// `playing`, threw "Null check operator used on a null value" on every frame, and
// the app segfaulted. It shipped inside the image; this is the test that would
// have stopped it.

import 'package:flutter_test/flutter_test.dart';
import 'package:moplayer_moos/features/live/live_screen.dart';
import 'package:moplayer_moos/models/live_channel.dart';
import 'package:moplayer_moos/models/media_kind.dart';
import 'package:moplayer_moos/providers/playback_providers.dart';
import 'package:moplayer_moos/services/player/player_service.dart';

LiveChannel _ch(String name, {String? logo, String? epg}) => LiveChannel(
      streamId: 's-$name',
      name: name,
      logo: logo,
      epgChannelId: epg,
      directUrl: 'http://x/$name',
    );

NowPlaying _live(String title, String refId, {String? image, String? epg}) => NowPlaying(
      media: PlayableMedia(url: 'http://x/$refId', title: title, kind: MediaKind.live),
      refId: refId,
      imageUrl: image,
      payload: {'epgChannelId': ?epg},
    );

void main() {
  group('resolveNowPlaying', () {
    test('a previewed channel with NO logo and NO epg id, and nothing playing', () {
      // The crash. Every optional field is null and there is no playback to fall
      // back to — which is the ordinary state of the Live screen on first open.
      final subject = resolveNowPlaying(previewed: _ch('Bare'), playing: null);

      expect(subject, isNotNull);
      expect(subject!.title, 'Bare');
      expect(subject.streamId, 's-Bare');
      expect(subject.logo, isNull, reason: 'no logo is a logo the pane can draw around');
      expect(subject.epgChannelId, isNull);
    });

    test('a previewed channel keeps its own fields — it never borrows the stream\'s', () {
      final playing =
          _live('Something else', 's-Other', image: 'http://x/other.png', epg: 'other.epg');

      final subject = resolveNowPlaying(previewed: _ch('Bare'), playing: playing);

      expect(subject!.title, 'Bare');
      expect(subject.streamId, 's-Bare');
      expect(subject.logo, isNull,
          reason: 'borrowing the running stream\'s poster labels the wrong channel');
      expect(subject.epgChannelId, isNull,
          reason: 'borrowing its epg id would show the wrong guide');
    });

    test('nothing previewed: the pane is about whatever is playing', () {
      final playing =
          _live('On air', 's-OnAir', image: 'http://x/onair.png', epg: 'onair.epg');

      final subject = resolveNowPlaying(previewed: null, playing: playing);

      expect(subject!.title, 'On air');
      expect(subject.streamId, 's-OnAir');
      expect(subject.logo, 'http://x/onair.png');
      expect(subject.epgChannelId, 'onair.epg');
    });

    test('nothing previewed and nothing playing — the empty state owns the pane', () {
      expect(resolveNowPlaying(previewed: null, playing: null), isNull);
    });
  });
}
