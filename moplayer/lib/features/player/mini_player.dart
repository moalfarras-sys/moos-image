import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:media_kit_video/media_kit_video.dart';

import '../../core/theme/app_colors.dart';
import '../../core/theme/app_typography.dart';
import '../../core/theme/nova.dart';
import '../../core/utils/formatters.dart';
import '../../providers/playback_providers.dart';
import '../../providers/system_providers.dart';
import '../../widgets/buttons.dart';
import '../../widgets/focus_surface.dart';
import '../../widgets/media_card.dart';

/// The picture-in-picture card that floats at the foot of the page while a
/// stream plays and the user browses.
///
/// It renders the *live video surface*, not a thumbnail of it: there is one
/// `VideoController` in the app, and this card mounts the same texture the
/// full player does. That is the point — on a desktop, leaving the player
/// should cost you nothing, and the channel keeps running in the corner.
///
/// Solid, not glass. It floats over posters that scroll, which is exactly where
/// a backdrop blur would re-render every frame of every scroll.
class MiniPlayer extends ConsumerWidget {
  const MiniPlayer({super.key});

  static const double width = 420;
  static const double height = 92;

  /// Bottom padding the shell gives the page while the card is showing.
  static const double reserve = height + Nova.space5 * 2;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(stringsProvider);
    final now = ref.watch(playbackProvider);
    final player = ref.watch(playerServiceProvider);
    final playback = ref.read(playbackProvider.notifier);

    if (now == null) return const SizedBox.shrink();

    final available = MediaQuery.sizeOf(context).width - Nova.space5 * 2;
    return Container(
      width: available < width ? available : width,
      height: height,
      decoration: BoxDecoration(
        color: AppColors.surface2,
        borderRadius: BorderRadius.circular(Nova.radiusPanel),
        border: Border.all(color: AppColors.borderStrong),
        boxShadow: const [
          BoxShadow(
            color: Color(0x99000000),
            blurRadius: 30,
            offset: Offset(0, 14),
            spreadRadius: -8,
          ),
        ],
      ),
      child: Row(
        children: [
          FocusSurface(
            onTap: () => ref.read(playerViewProvider.notifier).expand(),
            semanticLabel: s.miniPlayer,
            radius: Nova.radiusControl,
            scale: 1,
            bloom: false,
            child: Padding(
              padding: const EdgeInsets.all(Nova.space2),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(Nova.radiusControl),
                child: SizedBox(
                  width: 134,
                  height: 76,
                  child: ColoredBox(
                    color: Colors.black,
                    child: Video(
                      controller: player.controller,
                      controls: NoVideoControls,
                      fit: BoxFit.cover,
                      fill: Colors.black,
                    ),
                  ),
                ),
              ),
            ),
          ),
          const SizedBox(width: Nova.space2),
          Expanded(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (now.isLive) ...[
                  LiveBadge(label: s.onAir),
                  const SizedBox(height: 4),
                ],
                Text(
                  now.media.title,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppText.control.copyWith(fontWeight: FontWeight.w600),
                ),
                if (now.media.subtitle != null)
                  Text(
                    now.media.subtitle!,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: AppText.caption,
                  ),
                if (!now.isLive) ...[
                  const SizedBox(height: 6),
                  const _MiniProgress(),
                ],
              ],
            ),
          ),
          const SizedBox(width: Nova.space2),
          if (now.hasPrevious || now.hasNext)
            IconPill(
              icon: Icons.skip_previous_rounded,
              tooltip: now.isLive ? s.previousChannel : s.previousEpisode,
              size: 36,
              onPressed: now.hasPrevious ? playback.previous : null,
            ),
          StreamBuilder<bool>(
            stream: player.playingStream,
            initialData: player.isPlaying,
            builder: (context, snapshot) => IconPill(
              icon: snapshot.data == true
                  ? Icons.pause_rounded
                  : Icons.play_arrow_rounded,
              tooltip: snapshot.data == true ? s.pause : s.play,
              size: 42,
              filled: true,
              onPressed: player.playOrPause,
            ),
          ),
          if (now.hasPrevious || now.hasNext)
            IconPill(
              icon: Icons.skip_next_rounded,
              tooltip: now.isLive ? s.nextChannel : s.nextEpisode,
              size: 36,
              onPressed: now.hasNext ? playback.next : null,
            ),
          IconPill(
            icon: Icons.close_rounded,
            tooltip: s.stop,
            size: 36,
            onPressed: playback.stop,
          ),
          const SizedBox(width: Nova.space2),
        ],
      ),
    );
  }
}

class _MiniProgress extends ConsumerWidget {
  const _MiniProgress();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final player = ref.watch(playerServiceProvider);

    return StreamBuilder<Duration>(
      stream: player.positionStream,
      initialData: player.position,
      builder: (context, snapshot) {
        final position = snapshot.data ?? Duration.zero;
        final duration = player.duration;
        final value = duration.inMilliseconds <= 0
            ? 0.0
            : position.inMilliseconds / duration.inMilliseconds;

        return Row(
          children: [
            Expanded(
              child: ClipRRect(
                borderRadius: BorderRadius.circular(2),
                child: LinearProgressIndicator(
                  value: value.clamp(0, 1),
                  minHeight: 3,
                  backgroundColor: AppColors.surface3,
                ),
              ),
            ),
            const SizedBox(width: Nova.space2),
            Text(
              Fmt.duration(duration - position),
              textDirection: TextDirection.ltr,
              style: AppText.timecode.copyWith(
                fontSize: 10.5,
                color: AppColors.textMuted,
              ),
            ),
          ],
        );
      },
    );
  }
}
