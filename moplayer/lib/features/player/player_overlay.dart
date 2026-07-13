import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:media_kit/media_kit.dart';
import 'package:media_kit_video/media_kit_video.dart';

import '../../core/l10n/strings.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_typography.dart';
import '../../core/theme/nova.dart';
import '../../core/utils/formatters.dart';
import '../../providers/playback_providers.dart';
import '../../providers/system_providers.dart';
import '../../services/player/player_service.dart';
import '../../widgets/buttons.dart';
import '../../widgets/media_card.dart';

/// The player, filling the window.
///
/// It is an overlay rather than a route on purpose (see `app/routes.dart`): the
/// video surface is never torn down when the user leaves, it is only uncovered.
/// Closing this widget hands the very same libmpv pipeline to the mini player,
/// so a channel that took four seconds to negotiate does not have to do it again
/// because someone wanted to look at the guide.
class PlayerOverlay extends ConsumerStatefulWidget {
  const PlayerOverlay({super.key});

  @override
  ConsumerState<PlayerOverlay> createState() => _PlayerOverlayState();
}

class _PlayerOverlayState extends ConsumerState<PlayerOverlay> {
  static const _idleTimeout = Duration(seconds: 3);

  final FocusNode _focus = FocusNode();
  Timer? _idleTimer;
  bool _controlsVisible = true;

  @override
  void initState() {
    super.initState();
    _restartIdleTimer();
  }

  @override
  void dispose() {
    _idleTimer?.cancel();
    _focus.dispose();
    super.dispose();
  }

  /// Controls appear on any pointer movement and go away three seconds later —
  /// but only while something is actually playing. Hiding the controls of a
  /// paused video leaves the user staring at a still frame with no way out.
  void _restartIdleTimer() {
    _idleTimer?.cancel();
    if (!mounted) return;
    if (!_controlsVisible) setState(() => _controlsVisible = true);

    _idleTimer = Timer(_idleTimeout, () {
      if (!mounted) return;
      final playing = ref.read(playerServiceProvider).isPlaying;
      if (playing) setState(() => _controlsVisible = false);
    });
  }

  PlaybackController get _playback => ref.read(playbackProvider.notifier);
  PlayerService get _player => ref.read(playerServiceProvider);

  Future<void> _cycleSubtitles() async {
    final tracks = _player.tracks.subtitle;
    if (tracks.isEmpty) return;
    final current = _player.selectedTrack.subtitle;
    final index = tracks.indexWhere((t) => t.id == current.id);
    await _player.setSubtitleTrack(tracks[(index + 1) % tracks.length]);
  }

  Future<void> _cycleAudio() async {
    final tracks = _player.tracks.audio;
    if (tracks.length < 2) return;
    final current = _player.selectedTrack.audio;
    final index = tracks.indexWhere((t) => t.id == current.id);
    await _player.setAudioTrack(tracks[(index + 1) % tracks.length]);
  }

  Future<void> _nudgeVolume(double delta) async {
    await _player.setVolume((_player.volume + delta).clamp(0, 100));
  }

  Future<void> _nudgeRate(double delta) async {
    await _player.setRate((_player.rate + delta).clamp(0.25, 2.0));
  }

  Future<void> _leave() async {
    // Esc leaves fullscreen first, and only collapses the player if it was
    // already windowed. Anything else and Esc throws the user out of a video
    // they only wanted to un-maximise.
    if (ref.read(fullscreenProvider)) {
      await ref.read(fullscreenProvider.notifier).set(false);
      return;
    }
    ref.read(playerViewProvider.notifier).minimise();
  }

  @override
  Widget build(BuildContext context) {
    final s = ref.watch(stringsProvider);
    final now = ref.watch(playbackProvider);
    final player = ref.watch(playerServiceProvider);

    if (now == null) return const SizedBox.shrink();

    return CallbackShortcuts(
      bindings: {
        const SingleActivator(LogicalKeyboardKey.space): player.playOrPause,
        const SingleActivator(LogicalKeyboardKey.keyK): player.playOrPause,
        const SingleActivator(LogicalKeyboardKey.escape): _leave,
        const SingleActivator(LogicalKeyboardKey.keyF): () =>
            ref.read(fullscreenProvider.notifier).toggle(),
        const SingleActivator(LogicalKeyboardKey.f11): () =>
            ref.read(fullscreenProvider.notifier).toggle(),
        const SingleActivator(LogicalKeyboardKey.keyM): () =>
            _player.setVolume(_player.volume > 0 ? 0 : 100),
        const SingleActivator(LogicalKeyboardKey.keyS): _cycleSubtitles,
        const SingleActivator(LogicalKeyboardKey.keyA): _cycleAudio,
        const SingleActivator(LogicalKeyboardKey.keyN): _playback.next,
        const SingleActivator(LogicalKeyboardKey.keyP): _playback.previous,
        const SingleActivator(LogicalKeyboardKey.arrowRight): () =>
            _playback.seekBy(const Duration(seconds: 10)),
        const SingleActivator(LogicalKeyboardKey.arrowLeft): () =>
            _playback.seekBy(const Duration(seconds: -10)),
        const SingleActivator(LogicalKeyboardKey.arrowRight, shift: true): () =>
            _playback.seekBy(const Duration(minutes: 1)),
        const SingleActivator(LogicalKeyboardKey.arrowLeft, shift: true): () =>
            _playback.seekBy(const Duration(minutes: -1)),
        const SingleActivator(LogicalKeyboardKey.arrowUp): () => _nudgeVolume(5),
        const SingleActivator(LogicalKeyboardKey.arrowDown): () => _nudgeVolume(-5),
        const SingleActivator(LogicalKeyboardKey.bracketRight): () => _nudgeRate(0.25),
        const SingleActivator(LogicalKeyboardKey.bracketLeft): () => _nudgeRate(-0.25),
      },
      child: Focus(
        focusNode: _focus,
        autofocus: true,
        child: MouseRegion(
          cursor: _controlsVisible
              ? SystemMouseCursors.basic
              : SystemMouseCursors.none,
          onHover: (_) => _restartIdleTimer(),
          child: GestureDetector(
            behavior: HitTestBehavior.opaque,
            onTap: player.playOrPause,
            onDoubleTap: () => ref.read(fullscreenProvider.notifier).toggle(),
            child: ColoredBox(
              // Pure black behind the picture, not the app canvas: any tint here
              // is a tint on every frame the user watches.
              color: Colors.black,
              child: Stack(
                fit: StackFit.expand,
                children: [
                  Video(
                    controller: player.controller,
                    controls: NoVideoControls,
                    fit: BoxFit.contain,
                    fill: Colors.black,
                  ),

                  _BufferingLayer(player: player, strings: s),

                  AnimatedOpacity(
                    opacity: _controlsVisible ? 1 : 0,
                    duration: Nova.normal,
                    child: IgnorePointer(
                      ignoring: !_controlsVisible,
                      child: _Controls(
                        now: now,
                        player: player,
                        strings: s,
                        onInteract: _restartIdleTimer,
                        onLeave: _leave,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// The spinner, and the only place the player admits something is wrong.
class _BufferingLayer extends StatelessWidget {
  const _BufferingLayer({required this.player, required this.strings});

  final PlayerService player;
  final S strings;

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<bool>(
      stream: player.bufferingStream,
      initialData: player.isBuffering,
      builder: (context, snapshot) {
        if (snapshot.data != true) return const SizedBox.shrink();
        return Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const SizedBox(
                width: 44,
                height: 44,
                child: CircularProgressIndicator(strokeWidth: 3),
              ),
              const SizedBox(height: Nova.space4),
              Text(
                strings.buffering,
                style: AppText.body.copyWith(color: Colors.white70),
              ),
            ],
          ),
        );
      },
    );
  }
}

class _Controls extends ConsumerWidget {
  const _Controls({
    required this.now,
    required this.player,
    required this.strings,
    required this.onInteract,
    required this.onLeave,
  });

  final NowPlaying now;
  final PlayerService player;
  final S strings;
  final VoidCallback onInteract;
  final VoidCallback onLeave;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final playback = ref.read(playbackProvider.notifier);
    final fullscreen = ref.watch(fullscreenProvider);

    return Column(
      children: [
        // Top: who is on, and the way out.
        Container(
          padding: const EdgeInsets.fromLTRB(
            Nova.space4,
            Nova.space4,
            Nova.space4,
            Nova.space6,
          ),
          decoration: const BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
              colors: [Color(0xCC000000), Color(0x00000000)],
            ),
          ),
          child: Row(
            children: [
              IconPill(
                icon: Icons.keyboard_arrow_down_rounded,
                tooltip: strings.miniPlayer,
                size: 42,
                onPressed: onLeave,
              ),
              const SizedBox(width: Nova.space3),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Row(
                      children: [
                        if (now.isLive) ...[
                          LiveBadge(label: strings.onAir),
                          const SizedBox(width: Nova.space2),
                        ],
                        Flexible(
                          child: Text(
                            now.media.title,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: AppText.title.copyWith(color: Colors.white),
                          ),
                        ),
                      ],
                    ),
                    if (now.media.subtitle != null)
                      Text(
                        now.media.subtitle!,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: AppText.caption.copyWith(color: Colors.white60),
                      ),
                  ],
                ),
              ),
              IconPill(
                icon: Icons.close_rounded,
                tooltip: strings.stop,
                size: 42,
                onPressed: playback.stop,
              ),
            ],
          ),
        ),

        const Spacer(),

        // Bottom: the transport.
        Container(
          padding: const EdgeInsets.fromLTRB(
            Nova.space5,
            Nova.space6,
            Nova.space5,
            Nova.space4,
          ),
          decoration: const BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.bottomCenter,
              end: Alignment.topCenter,
              colors: [Color(0xE6000000), Color(0x00000000)],
            ),
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (!now.isLive) _SeekBar(player: player, onInteract: onInteract),
              const SizedBox(height: Nova.space2),
              Row(
                children: [
                  StreamBuilder<bool>(
                    stream: player.playingStream,
                    initialData: player.isPlaying,
                    builder: (context, snapshot) => IconPill(
                      icon: snapshot.data == true
                          ? Icons.pause_rounded
                          : Icons.play_arrow_rounded,
                      tooltip: snapshot.data == true ? strings.pause : strings.play,
                      size: 52,
                      filled: true,
                      onPressed: player.playOrPause,
                    ),
                  ),
                  const SizedBox(width: Nova.space3),

                  if (now.hasPrevious || now.hasNext) ...[
                    IconPill(
                      icon: Icons.skip_previous_rounded,
                      tooltip: strings.previousEpisode,
                      onPressed: now.hasPrevious ? playback.previous : null,
                    ),
                    IconPill(
                      icon: Icons.skip_next_rounded,
                      tooltip: strings.nextEpisode,
                      onPressed: now.hasNext ? playback.next : null,
                    ),
                    const SizedBox(width: Nova.space2),
                  ],

                  _VolumeControl(player: player, strings: strings),

                  const Spacer(),

                  if (!now.isLive) _RateMenu(player: player, strings: strings),
                  _TrackMenu(player: player, strings: strings),

                  IconPill(
                    icon: fullscreen
                        ? Icons.fullscreen_exit_rounded
                        : Icons.fullscreen_rounded,
                    tooltip: fullscreen ? strings.exitFullscreen : strings.fullscreen,
                    onPressed: () => ref.read(fullscreenProvider.notifier).toggle(),
                  ),
                ],
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _SeekBar extends ConsumerWidget {
  const _SeekBar({required this.player, required this.onInteract});

  final PlayerService player;
  final VoidCallback onInteract;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return StreamBuilder<Duration>(
      stream: player.positionStream,
      initialData: player.position,
      builder: (context, positionSnap) {
        return StreamBuilder<Duration>(
          stream: player.durationStream,
          initialData: player.duration,
          builder: (context, durationSnap) {
            final position = positionSnap.data ?? Duration.zero;
            final duration = durationSnap.data ?? Duration.zero;
            final max = duration.inMilliseconds.toDouble();
            final value = position.inMilliseconds.clamp(0, duration.inMilliseconds);

            return Row(
              children: [
                Text(Fmt.duration(position), style: AppText.timecode),
                Expanded(
                  child: SliderTheme(
                    data: SliderTheme.of(context).copyWith(
                      trackHeight: 4,
                      overlayShape: const RoundSliderOverlayShape(overlayRadius: 12),
                    ),
                    child: Slider(
                      // A zero-length media (a still-negotiating stream) would
                      // make the Slider assert; give it a token range instead.
                      value: max <= 0 ? 0 : value.toDouble(),
                      max: max <= 0 ? 1 : max,
                      onChanged: max <= 0
                          ? null
                          : (v) {
                              onInteract();
                              ref
                                  .read(playbackProvider.notifier)
                                  .seek(Duration(milliseconds: v.round()));
                            },
                    ),
                  ),
                ),
                Text(
                  Fmt.duration(duration),
                  style: AppText.timecode.copyWith(color: AppColors.textSecondary),
                ),
              ],
            );
          },
        );
      },
    );
  }
}

class _VolumeControl extends StatelessWidget {
  const _VolumeControl({required this.player, required this.strings});

  final PlayerService player;
  final S strings;

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<double>(
      stream: player.volumeStream,
      initialData: player.volume,
      builder: (context, snapshot) {
        final volume = snapshot.data ?? 100;
        final muted = volume <= 0;

        return Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            IconPill(
              icon: muted
                  ? Icons.volume_off_rounded
                  : volume < 50
                  ? Icons.volume_down_rounded
                  : Icons.volume_up_rounded,
              tooltip: muted ? strings.unmute : strings.mute,
              onPressed: () => player.setVolume(muted ? 100 : 0),
            ),
            SizedBox(
              width: 110,
              child: Slider(
                value: volume.clamp(0, 100),
                max: 100,
                onChanged: player.setVolume,
              ),
            ),
          ],
        );
      },
    );
  }
}

class _RateMenu extends StatelessWidget {
  const _RateMenu({required this.player, required this.strings});

  final PlayerService player;
  final S strings;

  static const _rates = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0];

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<double>(
      stream: player.rateStream,
      initialData: player.rate,
      builder: (context, snapshot) {
        final rate = snapshot.data ?? 1.0;
        return PopupMenuButton<double>(
          tooltip: strings.speed,
          position: PopupMenuPosition.over,
          onSelected: player.setRate,
          itemBuilder: (context) => [
            for (final r in _rates)
              PopupMenuItem(
                value: r,
                child: Row(
                  children: [
                    if ((r - rate).abs() < 0.01)
                      const Icon(Icons.check_rounded, size: 16, color: AppColors.primary)
                    else
                      const SizedBox(width: 16),
                    const SizedBox(width: Nova.space2),
                    Text('${r}x', textDirection: TextDirection.ltr),
                  ],
                ),
              ),
          ],
          child: SizedBox(
            height: 40,
            child: Center(
              child: Text(
                '${rate}x',
                style: AppText.control.copyWith(
                  color: rate == 1.0 ? AppColors.textSecondary : AppColors.primary,
                ),
                textDirection: TextDirection.ltr,
              ),
            ),
          ),
        );
      },
    );
  }
}

/// Audio and subtitle tracks, in one menu.
///
/// IPTV streams routinely carry three audio tracks and no subtitles, or eight
/// subtitle tracks named `und`. The menu shows whatever the stream declares and
/// says nothing when the stream declares nothing.
class _TrackMenu extends StatelessWidget {
  const _TrackMenu({required this.player, required this.strings});

  final PlayerService player;
  final S strings;

  String _label(dynamic track, int index) {
    final title = (track.title as String?)?.trim();
    final language = (track.language as String?)?.trim();
    if (title != null && title.isNotEmpty) return title;
    if (language != null && language.isNotEmpty && language != 'und') return language;
    return '#${index + 1}';
  }

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<Tracks>(
      stream: player.tracksStream,
      initialData: player.tracks,
      builder: (context, snapshot) {
        final tracks = snapshot.data ?? player.tracks;
        // media_kit always reports an 'auto' and a 'no' pseudo-track; a stream
        // with nothing real to offer has only those.
        final audio = tracks.audio.where((t) => t.id != 'auto' && t.id != 'no').toList();
        final subtitles = tracks.subtitle.where((t) => t.id != 'auto').toList();

        return PopupMenuButton<void Function()>(
          tooltip: strings.subtitles,
          position: PopupMenuPosition.over,
          icon: const Icon(Icons.closed_caption_rounded, size: 22),
          onSelected: (action) => action(),
          itemBuilder: (context) => [
            if (audio.length > 1) ...[
              PopupMenuItem(
                enabled: false,
                height: 32,
                child: Text(strings.audioTrack, style: AppText.label),
              ),
              for (var i = 0; i < audio.length; i++)
                PopupMenuItem(
                  value: () => player.setAudioTrack(audio[i]),
                  child: _TrackRow(
                    label: _label(audio[i], i),
                    selected: player.selectedTrack.audio.id == audio[i].id,
                  ),
                ),
            ],
            if (subtitles.isNotEmpty) ...[
              PopupMenuItem(
                enabled: false,
                height: 32,
                child: Text(strings.subtitles, style: AppText.label),
              ),
              PopupMenuItem(
                value: () => player.setSubtitleTrack(SubtitleTrack.no()),
                child: _TrackRow(
                  label: strings.subtitlesOff,
                  selected: player.selectedTrack.subtitle.id == 'no',
                ),
              ),
              for (var i = 0; i < subtitles.length; i++)
                if (subtitles[i].id != 'no')
                  PopupMenuItem(
                    value: () => player.setSubtitleTrack(subtitles[i]),
                    child: _TrackRow(
                      label: _label(subtitles[i], i),
                      selected: player.selectedTrack.subtitle.id == subtitles[i].id,
                    ),
                  ),
            ],
            if (audio.length <= 1 && subtitles.isEmpty)
              PopupMenuItem(
                enabled: false,
                child: Text(strings.subtitlesOff, style: AppText.body),
              ),
          ],
        );
      },
    );
  }
}

class _TrackRow extends StatelessWidget {
  const _TrackRow({required this.label, required this.selected});

  final String label;
  final bool selected;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        if (selected)
          const Icon(Icons.check_rounded, size: 16, color: AppColors.primary)
        else
          const SizedBox(width: 16),
        const SizedBox(width: Nova.space2),
        Flexible(
          child: Text(
            label,
            overflow: TextOverflow.ellipsis,
            style: AppText.control.copyWith(
              color: selected ? AppColors.primary : AppColors.textPrimary,
            ),
          ),
        ),
      ],
    );
  }
}
