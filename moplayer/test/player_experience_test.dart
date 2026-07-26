import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:moplayer_moos/core/utils/app_logger.dart';
import 'package:moplayer_moos/models/live_channel.dart';
import 'package:moplayer_moos/models/media_kind.dart';
import 'package:moplayer_moos/providers/playback_providers.dart';
import 'package:moplayer_moos/services/player/player_service.dart';

void main() {
  group('professional player experience', () {
    final overlay = File(
      'lib/features/player/player_overlay.dart',
    ).readAsStringSync();
    final playback = File(
      'lib/providers/playback_providers.dart',
    ).readAsStringSync();
    final router = File('lib/app/router.dart').readAsStringSync();

    test('the transport exposes real seeking and playback options', () {
      expect(overlay, contains('Icons.replay_10_rounded'));
      expect(overlay, contains('Icons.forward_10_rounded'));
      expect(overlay, contains('class _PlayerOptionsPanel'));
      expect(overlay, contains('PlayerFitMode.fill'));
      expect(overlay, contains('player.setAudioTrack'));
      expect(overlay, contains('player.setSubtitleTrack'));
      expect(overlay, contains('player.setRate'));
    });

    test('live TV exposes a wraparound channel queue', () {
      const channels = [
        LiveChannel(streamId: '1', name: 'One'),
        LiveChannel(streamId: '2', name: 'Two'),
      ];
      const now = NowPlaying(
        media: PlayableMedia(
          url: 'https://media.example/1.m3u8',
          title: 'One',
          kind: MediaKind.live,
        ),
        refId: '1',
        trackProgress: false,
        liveChannels: channels,
        liveChannelIndex: 0,
      );

      expect(now.hasPrevious, isTrue);
      expect(now.hasNext, isTrue);
      expect(overlay, contains('LogicalKeyboardKey.pageUp'));
      expect(overlay, contains('LogicalKeyboardKey.pageDown'));
    });

    test('a terminal stream failure has a visible manual recovery path', () {
      expect(playback, contains('PlaybackIssueKind.failed'));
      expect(playback, contains('Future<void> reconnect()'));
      expect(overlay, contains('strings.playbackFailed'));
      expect(overlay, contains('onReconnect'));
    });

    test('raising an idle app does not hide the home chrome', () {
      expect(
        playback,
        contains('if (ref.read(playbackProvider) != null)'),
        reason:
            'MPRIS Raise must expand only when a real player overlay exists',
      );
    });

    test('direct URLs always have a safe title', () {
      expect(
        directMediaTitle(
          'https://media.example/live/channel.m3u8?token=secret',
        ),
        'channel.m3u8',
      );
      expect(directMediaTitle('https://media.example'), 'media.example');
      expect(directMediaTitle('/tmp/film.mkv'), 'film.mkv');
      expect(
        router,
        contains('!playingDirectUrl'),
        reason: 'a clean install must play a direct URL without an IPTV source',
      );
    });

    test('playback diagnostics never persist source credentials', () {
      final safe = safeLogMessage(
        'failed https://panel.example/get.php?username=alice&password=swordfish',
      );
      expect(safe, isNot(contains('alice')));
      expect(safe, isNot(contains('swordfish')));
      expect(safe, contains('<redacted-url>'));
    });

    test('switching media invalidates old resume and recovery work', () {
      final service = File(
        'lib/services/player/player_service.dart',
      ).readAsStringSync();

      expect(service, contains('_mediaGeneration'));
      expect(service, contains('setCompactVideoOutput'));
      expect(service, contains('generation != _mediaGeneration'));
      expect(playback, contains('final previousProgress = _progressSnapshot'));
      expect(playback, contains('_openingGeneration'));
      expect(playback, contains('_stablePlaybackTimer'));
      expect(playback, contains('_mediaPlaylistId'));
    });

    test('MPRIS implements the desktop contracts it advertises', () {
      final mpris = File('lib/services/system/mpris.dart').readAsStringSync();

      expect(mpris, contains("'OpenUri'"));
      expect(mpris, contains('onOpenUri'));
      expect(mpris, contains('onRate'));
      expect(mpris, contains('DBusPropertyAccess.readwrite'));
      expect(mpris, contains('currentTrackPath'));
      expect(playback, contains('desktopServiceProvider).close()'));
    });

    test('the idle home screen has no infinite animation controllers', () {
      final offenders = Directory('lib')
          .listSync(recursive: true)
          .whereType<File>()
          .where((file) => file.path.endsWith('.dart'))
          .where((file) => file.readAsStringSync().contains('.repeat('))
          .map((file) => file.path)
          .toList();

      expect(
        offenders,
        isEmpty,
        reason:
            'an always-running ticker repaints the full desktop surface while '
            'MoPlayer is idle',
      );
    });
  });
}
