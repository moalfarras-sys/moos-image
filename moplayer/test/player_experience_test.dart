import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  group('professional player experience', () {
    final overlay = File(
      'lib/features/player/player_overlay.dart',
    ).readAsStringSync();
    final playback = File(
      'lib/providers/playback_providers.dart',
    ).readAsStringSync();

    test('the transport exposes real seeking and playback options', () {
      expect(overlay, contains('Icons.replay_10_rounded'));
      expect(overlay, contains('Icons.forward_10_rounded'));
      expect(overlay, contains('class _PlayerOptionsPanel'));
      expect(overlay, contains('PlayerFitMode.fill'));
      expect(overlay, contains('player.setAudioTrack'));
      expect(overlay, contains('player.setSubtitleTrack'));
      expect(overlay, contains('player.setRate'));
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
