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

/// The bar along the bottom of the shell while a stream is playing and the user
/// is somewhere else.
///
/// It renders the *live video surface*, not a thumbnail of it. There is exactly
/// one `VideoController` in the app and only one widget mounts it at a time — the
/// full player when expanded, this bar when not — so the picture is genuinely
/// still running here, at 208×117, while the user browses the guide. That is the
/// whole point: on a desktop, leaving the player should cost you nothing.
class MiniPlayer extends ConsumerWidget {
  const MiniPlayer({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(stringsProvider);
    final now = ref.watch(playbackProvider);
    final player = ref.watch(playerServiceProvider);
    final playback = ref.read(playbackProvider.notifier);

    if (now == null) return const SizedBox.shrink();

    return Container(
      height: 84,
      decoration: const BoxDecoration(
        color: AppColors.surface1,
        border: Border(top: BorderSide(color: AppColors.borderSubtle)),
      ),
      child: Row(
        children: [
          FocusSurface(
            onTap: () => ref.read(playerViewProvider.notifier).expand(),
            semanticLabel: s.miniPlayer,
            scale: 1,
            bloom: false,
            child: Padding(
              padding: const EdgeInsets.all(Nova.space3),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(Nova.radiusControl),
                child: SizedBox(
                  width: 104,
                  height: 58,
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

          Expanded(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    if (now.isLive) ...[
                      LiveBadge(label: s.onAir),
                      const SizedBox(width: Nova.space2),
                    ],
                    Flexible(
                      child: Text(
                        now.media.title,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: AppText.control,
                      ),
                    ),
                  ],
                ),
                if (now.media.subtitle != null)
                  Text(
                    now.media.subtitle!,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: AppText.caption,
                  ),
                if (now.isLive && now.liveChannels.length > 1)
                  Text(
                    '${(now.liveChannelIndex ?? 0) + 1} / '
                    '${now.liveChannels.length}',
                    style: AppText.caption.copyWith(color: AppColors.textMuted),
                    textDirection: TextDirection.ltr,
                  ),
                if (!now.isLive) ...[
                  const SizedBox(height: Nova.space2),
                  _MiniProgress(),
                ],
              ],
            ),
          ),

          const SizedBox(width: Nova.space4),

          if (now.hasPrevious || now.hasNext)
            IconPill(
              icon: Icons.skip_previous_rounded,
              tooltip: now.isLive ? s.previousChannel : s.previousEpisode,
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
              size: 46,
              filled: true,
              onPressed: player.playOrPause,
            ),
          ),

          if (now.hasPrevious || now.hasNext)
            IconPill(
              icon: Icons.skip_next_rounded,
              tooltip: now.isLive ? s.nextChannel : s.nextEpisode,
              onPressed: now.hasNext ? playback.next : null,
            ),

          const SizedBox(width: Nova.space2),
          IconPill(
            icon: Icons.open_in_full_rounded,
            tooltip: s.fullscreen,
            onPressed: () => ref.read(playerViewProvider.notifier).expand(),
          ),
          IconPill(
            icon: Icons.close_rounded,
            tooltip: s.stop,
            onPressed: playback.stop,
          ),
          const SizedBox(width: Nova.space3),
        ],
      ),
    );
  }
}

class _MiniProgress extends ConsumerWidget {
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
            Text(
              Fmt.duration(position),
              style: AppText.timecode.copyWith(fontSize: 10.5),
            ),
            const SizedBox(width: Nova.space2),
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
              Fmt.duration(duration),
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
