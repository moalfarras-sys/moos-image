import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:media_kit/media_kit.dart';
import 'package:media_kit_video/media_kit_video.dart';

import '../../core/l10n/strings.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_typography.dart';
import '../../core/theme/glass.dart';
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

enum PlayerFitMode { fit, fill, original }

class _PlayerOverlayState extends ConsumerState<PlayerOverlay> {
  static const _idleTimeout = Duration(seconds: 3);

  final FocusNode _focus = FocusNode();
  Timer? _idleTimer;
  bool _controlsVisible = true;
  bool _optionsVisible = false;
  PlayerFitMode _fitMode = PlayerFitMode.fit;

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
      if (playing && !_optionsVisible) {
        setState(() => _controlsVisible = false);
      }
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

  void _toggleOptions() {
    setState(() {
      _optionsVisible = !_optionsVisible;
      _controlsVisible = true;
    });
    _restartIdleTimer();
  }

  BoxFit get _videoFit => switch (_fitMode) {
    PlayerFitMode.fit => BoxFit.contain,
    PlayerFitMode.fill => BoxFit.cover,
    PlayerFitMode.original => BoxFit.scaleDown,
  };

  @override
  Widget build(BuildContext context) {
    final s = ref.watch(stringsProvider);
    final now = ref.watch(playbackProvider);
    final player = ref.watch(playerServiceProvider);
    final issue = ref.watch(playbackIssueProvider);

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
        const SingleActivator(LogicalKeyboardKey.arrowUp): () =>
            _nudgeVolume(5),
        const SingleActivator(LogicalKeyboardKey.arrowDown): () =>
            _nudgeVolume(-5),
        const SingleActivator(LogicalKeyboardKey.bracketRight): () =>
            _nudgeRate(0.25),
        const SingleActivator(LogicalKeyboardKey.bracketLeft): () =>
            _nudgeRate(-0.25),
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
                    fit: _videoFit,
                    fill: Colors.black,
                  ),

                  _PlaybackStatusLayer(
                    player: player,
                    strings: s,
                    issue: issue,
                    onReconnect: _playback.reconnect,
                  ),

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
                        optionsVisible: _optionsVisible,
                        fitMode: _fitMode,
                        onToggleOptions: _toggleOptions,
                        onFitChanged: (value) {
                          setState(() => _fitMode = value);
                          _restartIdleTimer();
                        },
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

/// Buffering, automatic recovery, and the terminal error action.
class _PlaybackStatusLayer extends StatelessWidget {
  const _PlaybackStatusLayer({
    required this.player,
    required this.strings,
    required this.issue,
    required this.onReconnect,
  });

  final PlayerService player;
  final S strings;
  final PlaybackIssue? issue;
  final VoidCallback onReconnect;

  @override
  Widget build(BuildContext context) {
    if (issue?.kind == PlaybackIssueKind.failed) {
      return Center(
        child: GlassPanel(
          fill: const Color(0xE8121417),
          glow: true,
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 420),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(
                  Icons.signal_wifi_connected_no_internet_4_rounded,
                  size: 42,
                  color: AppColors.primary,
                ),
                const SizedBox(height: Nova.space4),
                Text(
                  strings.playbackFailed,
                  textAlign: TextAlign.center,
                  style: AppText.body.copyWith(color: Colors.white),
                ),
                const SizedBox(height: Nova.space5),
                EmberButton(
                  label: strings.reconnect,
                  icon: Icons.refresh_rounded,
                  onPressed: onReconnect,
                ),
              ],
            ),
          ),
        ),
      );
    }

    if (issue?.kind == PlaybackIssueKind.reconnecting) {
      return _BusyStatus(
        label: strings.reconnectingAttempt(issue!.attempt, issue!.maxAttempts),
      );
    }

    return StreamBuilder<bool>(
      stream: player.bufferingStream,
      initialData: player.isBuffering,
      builder: (context, snapshot) {
        if (snapshot.data != true) return const SizedBox.shrink();
        return _BusyStatus(label: strings.buffering);
      },
    );
  }
}

class _BusyStatus extends StatelessWidget {
  const _BusyStatus({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
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
          Text(label, style: AppText.body.copyWith(color: Colors.white70)),
        ],
      ),
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
    required this.optionsVisible,
    required this.fitMode,
    required this.onToggleOptions,
    required this.onFitChanged,
  });

  final NowPlaying now;
  final PlayerService player;
  final S strings;
  final VoidCallback onInteract;
  final VoidCallback onLeave;
  final bool optionsVisible;
  final PlayerFitMode fitMode;
  final VoidCallback onToggleOptions;
  final ValueChanged<PlayerFitMode> onFitChanged;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final playback = ref.read(playbackProvider.notifier);
    final fullscreen = ref.watch(fullscreenProvider);

    return Stack(
      children: [
        Column(
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
                                style: AppText.title.copyWith(
                                  color: Colors.white,
                                ),
                              ),
                            ),
                          ],
                        ),
                        if (now.media.subtitle != null)
                          Text(
                            now.media.subtitle!,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: AppText.caption.copyWith(
                              color: Colors.white60,
                            ),
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

            _CentreTransport(
              now: now,
              player: player,
              strings: strings,
              playback: playback,
              onInteract: onInteract,
            ),

            const Spacer(),

            Container(
              padding: const EdgeInsets.fromLTRB(
                Nova.space5,
                Nova.space7,
                Nova.space5,
                Nova.space4,
              ),
              decoration: const BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.bottomCenter,
                  end: Alignment.topCenter,
                  colors: [Color(0xF0000000), Color(0x00000000)],
                ),
              ),
              child: GlassPanel(
                padding: const EdgeInsets.symmetric(
                  horizontal: Nova.space4,
                  vertical: Nova.space3,
                ),
                radius: Nova.radiusHero,
                blur: 20,
                fill: const Color(0xD8121417),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    if (!now.isLive)
                      _SeekBar(player: player, onInteract: onInteract),
                    if (!now.isLive) const SizedBox(height: Nova.space2),
                    Row(
                      children: [
                        _VolumeControl(player: player, strings: strings),
                        const Spacer(),
                        IconPill(
                          icon: Icons.tune_rounded,
                          tooltip: strings.playerOptions,
                          filled: optionsVisible,
                          onPressed: onToggleOptions,
                        ),
                        const SizedBox(width: Nova.space2),
                        IconPill(
                          icon: fullscreen
                              ? Icons.fullscreen_exit_rounded
                              : Icons.fullscreen_rounded,
                          tooltip: fullscreen
                              ? strings.exitFullscreen
                              : strings.fullscreen,
                          onPressed: () =>
                              ref.read(fullscreenProvider.notifier).toggle(),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),

        PositionedDirectional(
          top: 92,
          bottom: 150,
          end: Nova.space5,
          width: 340,
          child: AnimatedSlide(
            offset: optionsVisible ? Offset.zero : const Offset(0.12, 0),
            duration: Nova.panel,
            curve: Curves.easeOutCubic,
            child: AnimatedOpacity(
              opacity: optionsVisible ? 1 : 0,
              duration: Nova.panel,
              child: IgnorePointer(
                ignoring: !optionsVisible,
                child: _PlayerOptionsPanel(
                  player: player,
                  strings: strings,
                  isLive: now.isLive,
                  fitMode: fitMode,
                  onFitChanged: onFitChanged,
                  onInteract: onInteract,
                ),
              ),
            ),
          ),
        ),
      ],
    );
  }
}

class _CentreTransport extends StatelessWidget {
  const _CentreTransport({
    required this.now,
    required this.player,
    required this.strings,
    required this.playback,
    required this.onInteract,
  });

  final NowPlaying now;
  final PlayerService player;
  final S strings;
  final PlaybackController playback;
  final VoidCallback onInteract;

  @override
  Widget build(BuildContext context) {
    return GlassPanel(
      padding: const EdgeInsets.symmetric(
        horizontal: Nova.space3,
        vertical: Nova.space2,
      ),
      radius: Nova.radiusDock,
      blur: 18,
      fill: const Color(0xB8121417),
      shadow: false,
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (!now.isLive)
            IconPill(
              icon: Icons.replay_10_rounded,
              tooltip: strings.tenSecondsBack,
              size: 50,
              onPressed: () {
                onInteract();
                playback.seekBy(const Duration(seconds: -10));
              },
            ),
          if (now.hasPrevious)
            IconPill(
              icon: Icons.skip_previous_rounded,
              tooltip: strings.previousEpisode,
              size: 50,
              onPressed: playback.previous,
            ),
          StreamBuilder<bool>(
            stream: player.playingStream,
            initialData: player.isPlaying,
            builder: (context, snapshot) => IconPill(
              icon: snapshot.data == true
                  ? Icons.pause_rounded
                  : Icons.play_arrow_rounded,
              tooltip: snapshot.data == true ? strings.pause : strings.play,
              size: 64,
              filled: true,
              onPressed: () {
                onInteract();
                player.playOrPause();
              },
            ),
          ),
          if (now.hasNext)
            IconPill(
              icon: Icons.skip_next_rounded,
              tooltip: strings.nextEpisode,
              size: 50,
              onPressed: playback.next,
            ),
          if (!now.isLive)
            IconPill(
              icon: Icons.forward_10_rounded,
              tooltip: strings.tenSecondsForward,
              size: 50,
              onPressed: () {
                onInteract();
                playback.seekBy(const Duration(seconds: 10));
              },
            ),
        ],
      ),
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
            final value = position.inMilliseconds.clamp(
              0,
              duration.inMilliseconds,
            );

            return Row(
              children: [
                Text(Fmt.duration(position), style: AppText.timecode),
                Expanded(
                  child: SliderTheme(
                    data: SliderTheme.of(context).copyWith(
                      trackHeight: 4,
                      overlayShape: const RoundSliderOverlayShape(
                        overlayRadius: 12,
                      ),
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
                  style: AppText.timecode.copyWith(
                    color: AppColors.textSecondary,
                  ),
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

class _PlayerOptionsPanel extends StatelessWidget {
  const _PlayerOptionsPanel({
    required this.player,
    required this.strings,
    required this.isLive,
    required this.fitMode,
    required this.onFitChanged,
    required this.onInteract,
  });

  final PlayerService player;
  final S strings;
  final bool isLive;
  final PlayerFitMode fitMode;
  final ValueChanged<PlayerFitMode> onFitChanged;
  final VoidCallback onInteract;

  static const _rates = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0];

  String _label(dynamic track, int index) {
    final title = (track.title as String?)?.trim();
    final language = (track.language as String?)?.trim();
    if (title != null && title.isNotEmpty) return title;
    if (language != null && language.isNotEmpty && language != 'und') {
      return language;
    }
    return '#${index + 1}';
  }

  @override
  Widget build(BuildContext context) {
    return GlassPanel(
      padding: EdgeInsets.zero,
      fill: const Color(0xED121417),
      glow: true,
      child: ListView(
        padding: const EdgeInsets.all(Nova.space4),
        children: [
          Row(
            children: [
              const Icon(Icons.tune_rounded, color: AppColors.primary),
              const SizedBox(width: Nova.space3),
              Expanded(
                child: Text(strings.playerOptions, style: AppText.title),
              ),
            ],
          ),
          const SizedBox(height: Nova.space4),
          const Divider(color: AppColors.borderSubtle),
          const SizedBox(height: Nova.space3),
          _OptionHeading(
            icon: Icons.aspect_ratio_rounded,
            label: strings.aspectRatio,
          ),
          const SizedBox(height: Nova.space3),
          Wrap(
            spacing: Nova.space2,
            runSpacing: Nova.space2,
            children: [
              _OptionChoice(
                label: strings.aspectFit,
                selected: fitMode == PlayerFitMode.fit,
                onTap: () => onFitChanged(PlayerFitMode.fit),
              ),
              _OptionChoice(
                label: strings.aspectFill,
                selected: fitMode == PlayerFitMode.fill,
                onTap: () => onFitChanged(PlayerFitMode.fill),
              ),
              _OptionChoice(
                label: strings.aspectOriginal,
                selected: fitMode == PlayerFitMode.original,
                onTap: () => onFitChanged(PlayerFitMode.original),
              ),
            ],
          ),
          if (!isLive) ...[
            const SizedBox(height: Nova.space5),
            _OptionHeading(icon: Icons.speed_rounded, label: strings.speed),
            const SizedBox(height: Nova.space3),
            StreamBuilder<double>(
              stream: player.rateStream,
              initialData: player.rate,
              builder: (context, snapshot) {
                final rate = snapshot.data ?? 1.0;
                return Wrap(
                  spacing: Nova.space2,
                  runSpacing: Nova.space2,
                  children: [
                    for (final value in _rates)
                      _OptionChoice(
                        label: '${value}x',
                        textDirection: TextDirection.ltr,
                        selected: (value - rate).abs() < 0.01,
                        onTap: () {
                          onInteract();
                          player.setRate(value);
                        },
                      ),
                  ],
                );
              },
            ),
          ],
          const SizedBox(height: Nova.space5),
          StreamBuilder<Tracks>(
            stream: player.tracksStream,
            initialData: player.tracks,
            builder: (context, trackSnapshot) {
              final tracks = trackSnapshot.data ?? player.tracks;
              final audio = tracks.audio
                  .where((track) => track.id != 'auto' && track.id != 'no')
                  .toList();
              final subtitles = tracks.subtitle
                  .where((track) => track.id != 'auto' && track.id != 'no')
                  .toList();

              return StreamBuilder<Track>(
                stream: player.selectedTrackStream,
                initialData: player.selectedTrack,
                builder: (context, selectedSnapshot) {
                  final selected =
                      selectedSnapshot.data ?? player.selectedTrack;
                  return Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      if (audio.isNotEmpty) ...[
                        _OptionHeading(
                          icon: Icons.graphic_eq_rounded,
                          label: strings.audioTrack,
                        ),
                        const SizedBox(height: Nova.space2),
                        for (var i = 0; i < audio.length; i++)
                          _TrackRow(
                            label: _label(audio[i], i),
                            selected: selected.audio.id == audio[i].id,
                            onTap: () {
                              onInteract();
                              player.setAudioTrack(audio[i]);
                            },
                          ),
                        const SizedBox(height: Nova.space5),
                      ],
                      _OptionHeading(
                        icon: Icons.closed_caption_rounded,
                        label: strings.subtitles,
                      ),
                      const SizedBox(height: Nova.space2),
                      _TrackRow(
                        label: strings.subtitlesOff,
                        selected:
                            selected.subtitle.id == 'no' ||
                            selected.subtitle.id.isEmpty,
                        onTap: () {
                          onInteract();
                          player.setSubtitleTrack(SubtitleTrack.no());
                        },
                      ),
                      for (var i = 0; i < subtitles.length; i++)
                        _TrackRow(
                          label: _label(subtitles[i], i),
                          selected: selected.subtitle.id == subtitles[i].id,
                          onTap: () {
                            onInteract();
                            player.setSubtitleTrack(subtitles[i]);
                          },
                        ),
                    ],
                  );
                },
              );
            },
          ),
        ],
      ),
    );
  }
}

class _OptionHeading extends StatelessWidget {
  const _OptionHeading({required this.icon, required this.label});

  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Icon(icon, size: 18, color: AppColors.textSecondary),
        const SizedBox(width: Nova.space2),
        Text(label, style: AppText.label),
      ],
    );
  }
}

class _OptionChoice extends StatelessWidget {
  const _OptionChoice({
    required this.label,
    required this.selected,
    required this.onTap,
    this.textDirection,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;
  final TextDirection? textDirection;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: selected ? AppColors.primary : AppColors.surface3,
      borderRadius: BorderRadius.circular(Nova.radiusControl),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(Nova.radiusControl),
        child: Padding(
          padding: const EdgeInsets.symmetric(
            horizontal: Nova.space3,
            vertical: Nova.space2,
          ),
          child: Text(
            label,
            textDirection: textDirection,
            style: AppText.control.copyWith(
              color: selected ? Colors.black : AppColors.textPrimary,
              fontWeight: selected ? FontWeight.w700 : FontWeight.w500,
            ),
          ),
        ),
      ),
    );
  }
}

class _TrackRow extends StatelessWidget {
  const _TrackRow({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: selected
          ? AppColors.primary.withValues(alpha: 0.12)
          : Colors.transparent,
      borderRadius: BorderRadius.circular(Nova.radiusControl),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(Nova.radiusControl),
        child: Padding(
          padding: const EdgeInsets.symmetric(
            horizontal: Nova.space3,
            vertical: Nova.space2,
          ),
          child: Row(
            children: [
              Icon(
                selected ? Icons.check_circle_rounded : Icons.circle_outlined,
                size: 17,
                color: selected ? AppColors.primary : AppColors.textMuted,
              ),
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
          ),
        ),
      ),
    );
  }
}
