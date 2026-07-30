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
import '../../core/theme/motion.dart';
import '../../core/theme/nova.dart';
import '../../core/utils/formatters.dart';
import '../../providers/playback_providers.dart';
import '../../providers/system_providers.dart';
import '../../services/player/playback_stats.dart';
import '../../services/player/player_service.dart';
import '../../services/system/file_chooser.dart';
import '../../widgets/accessible_visibility.dart';
import '../../widgets/buttons.dart';
import '../../widgets/media_card.dart';
import '../../widgets/toast.dart';
import 'player_tuning.dart';

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
  StreamSubscription<bool>? _playingSub;
  bool _controlsVisible = true;
  bool _optionsVisible = false;
  PlayerFitMode _fitMode = PlayerFitMode.fit;

  /// Owned by the overlay, not the service: a sleep timer is an intention about
  /// this sitting, so changing channel must not cancel it but leaving the player
  /// must.
  final SleepTimer _sleepTimer = SleepTimer();

  @override
  void initState() {
    super.initState();
    _playingSub = ref.read(playerServiceProvider).playingStream.listen((
      playing,
    ) {
      if (!mounted) return;
      if (playing) {
        _restartIdleTimer();
        return;
      }

      // Pause can arrive from a media key or Plasma while the pointer is still.
      // A paused frame must never remain with a hidden way out.
      _idleTimer?.cancel();
      if (!_controlsVisible) {
        setState(() => _controlsVisible = true);
      }
    });
    _restartIdleTimer();
  }

  @override
  void dispose() {
    _idleTimer?.cancel();
    _playingSub?.cancel();
    _sleepTimer.dispose();
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
        // The settings panel had no key at all, which made every control inside
        // it — tracks, sync, deinterlacing, statistics — reachable only with the
        // mouse, on the one screen where the mouse is meant to disappear.
        const SingleActivator(LogicalKeyboardKey.keyO): _toggleOptions,
        const SingleActivator(LogicalKeyboardKey.keyN): _playback.next,
        const SingleActivator(LogicalKeyboardKey.keyP): _playback.previous,
        const SingleActivator(LogicalKeyboardKey.pageDown): _playback.next,
        const SingleActivator(LogicalKeyboardKey.pageUp): _playback.previous,
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
                    duration: Motion.duration(context, Nova.normal),
                    child: AccessibleVisibility(
                      visible: _controlsVisible,
                      child: _Controls(
                        now: now,
                        player: player,
                        strings: s,
                        onInteract: _restartIdleTimer,
                        onLeave: _leave,
                        optionsVisible: _optionsVisible,
                        fitMode: _fitMode,
                        onToggleOptions: _toggleOptions,
                        sleepTimer: _sleepTimer,
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
    required this.sleepTimer,
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
  final SleepTimer sleepTimer;

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
                            // Recording and a pending sleep timer are states
                            // the user set once and then forgets. Leaving them
                            // visible only inside the options panel is how a
                            // player ends up recording all night, or stopping
                            // in the middle of a match because of a timer set
                            // an hour ago.
                            _StatusPips(
                              player: player,
                              strings: strings,
                              sleepTimer: sleepTimer,
                            ),
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
                        if (now.isLive && now.liveChannels.length > 1)
                          Text(
                            '${(now.liveChannelIndex ?? 0) + 1} / '
                            '${now.liveChannels.length}',
                            style: AppText.caption.copyWith(
                              color: Colors.white60,
                            ),
                            textDirection: TextDirection.ltr,
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
                    if (now.isLive)
                      _LiveTimeshiftBar(player: player, onInteract: onInteract)
                    else
                      _SeekBar(player: player, onInteract: onInteract),
                    const SizedBox(height: Nova.space2),
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
            offset: optionsVisible || Motion.isReduced(context)
                ? Offset.zero
                : const Offset(0.12, 0),
            duration: Motion.duration(context, Nova.panel),
            curve: Curves.easeOutCubic,
            child: AnimatedOpacity(
              opacity: optionsVisible ? 1 : 0,
              duration: Motion.duration(context, Nova.panel),
              child: AccessibleVisibility(
                visible: optionsVisible,
                child: _PlayerOptionsPanel(
                  player: player,
                  strings: strings,
                  isLive: now.isLive,
                  fitMode: fitMode,
                  onFitChanged: onFitChanged,
                  onInteract: onInteract,
                  sleepTimer: sleepTimer,
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
              tooltip: now.isLive
                  ? strings.previousChannel
                  : strings.previousEpisode,
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
              tooltip: now.isLive ? strings.nextChannel : strings.nextEpisode,
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

/// Small always-visible badges for state the user set and then stopped
/// thinking about: recording in progress, and a sleep timer that is going to
/// stop playback.
///
/// Both tick once a second, and only while they have something to say —
/// nothing is built at all in the ordinary case where neither is active.
class _StatusPips extends StatefulWidget {
  const _StatusPips({
    required this.player,
    required this.strings,
    required this.sleepTimer,
  });

  final PlayerService player;
  final S strings;
  final SleepTimer sleepTimer;

  @override
  State<_StatusPips> createState() => _StatusPipsState();
}

class _StatusPipsState extends State<_StatusPips> {
  Timer? _tick;

  @override
  void initState() {
    super.initState();
    _tick = Timer.periodic(
      const Duration(seconds: 1),
      (_) => mounted ? setState(() {}) : null,
    );
  }

  @override
  void dispose() {
    _tick?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final s = widget.strings;
    final recording = widget.player.isRecording;
    final remaining = widget.sleepTimer.remaining;
    if (!recording && remaining == null) return const SizedBox.shrink();

    return Padding(
      padding: const EdgeInsetsDirectional.only(end: Nova.space2),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (recording)
            _Pip(
              icon: Icons.fiber_manual_record_rounded,
              label: s.recording,
              colour: AppColors.danger,
            ),
          if (remaining != null) ...[
            if (recording) const SizedBox(width: Nova.space2),
            _Pip(
              icon: Icons.bedtime_rounded,
              label: Fmt.duration(remaining),
              colour: AppColors.primary,
            ),
          ],
        ],
      ),
    );
  }
}

class _Pip extends StatelessWidget {
  const _Pip({required this.icon, required this.label, required this.colour});

  final IconData icon;
  final String label;
  final Color colour;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: Nova.space2, vertical: 2),
      decoration: BoxDecoration(
        color: colour.withValues(alpha: 0.16),
        borderRadius: BorderRadius.circular(Nova.radiusControl),
        border: Border.all(color: colour.withValues(alpha: 0.5)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 13, color: colour),
          const SizedBox(width: 4),
          Text(
            label,
            style: AppText.caption.copyWith(
              color: colour,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }
}

/// The seek bar for a live channel.
///
/// A live stream has no duration, so the ordinary bar disables itself and the
/// timeshift buffer — which mpv is already keeping — stays unreachable. This one
/// scrubs the *window* instead: from the earliest packet mpv still holds to the
/// live edge, both of which move in real time.
///
/// Polled rather than driven by the position stream, because the two ends of the
/// window are mpv properties with no stream behind them. Twice a second is
/// smoother than the eye needs on a bar this wide and costs two property reads.
class _LiveTimeshiftBar extends ConsumerStatefulWidget {
  const _LiveTimeshiftBar({required this.player, required this.onInteract});

  final PlayerService player;
  final VoidCallback onInteract;

  @override
  ConsumerState<_LiveTimeshiftBar> createState() => _LiveTimeshiftBarState();
}

class _LiveTimeshiftBarState extends ConsumerState<_LiveTimeshiftBar> {
  Timer? _poll;
  TimeshiftWindow _window = TimeshiftWindow.empty;

  /// Where the user has dragged to, while they are dragging.
  ///
  /// Without this the bar fights the pointer: the poll below would keep
  /// overwriting the thumb with the still-unchanged playback position, and the
  /// handle would spring back under the finger.
  double? _dragging;

  @override
  void initState() {
    super.initState();
    unawaited(_refresh());
    _poll = Timer.periodic(
      const Duration(milliseconds: 500),
      (_) => _refresh(),
    );
  }

  @override
  void dispose() {
    _poll?.cancel();
    super.dispose();
  }

  Future<void> _refresh() async {
    final window = await widget.player.timeshiftWindow();
    if (!mounted) return;
    setState(() => _window = window);
  }

  @override
  Widget build(BuildContext context) {
    final s = ref.watch(stringsProvider);
    final window = _window;

    if (!window.isSeekable) {
      // A channel that has only just opened has no window yet. Say it is live
      // rather than showing a bar that cannot move.
      return Row(
        children: [
          const _LiveDot(),
          const SizedBox(width: Nova.space2),
          Text(s.onAir, style: AppText.timecode),
        ],
      );
    }

    final start = window.start.inMilliseconds.toDouble();
    final edge = window.edge.inMilliseconds.toDouble();
    final position =
        _dragging ??
        window.position.inMilliseconds.toDouble().clamp(start, edge);
    final atEdge = _dragging == null && window.isAtLiveEdge;

    return Row(
      children: [
        // How far behind live, which is the only timecode that means anything
        // on a live stream — an absolute position would be the stream's own
        // clock, which is not a number anyone can use.
        SizedBox(
          width: 64,
          child: Text(
            atEdge ? s.onAir : '-${Fmt.duration(window.behind)}',
            textAlign: TextAlign.center,
            style: AppText.timecode.copyWith(
              color: atEdge ? AppColors.primary : AppColors.textPrimary,
            ),
          ),
        ),
        Expanded(
          child: SliderTheme(
            data: SliderTheme.of(context).copyWith(
              trackHeight: 4,
              overlayShape: const RoundSliderOverlayShape(overlayRadius: 12),
            ),
            child: Slider(
              value: position.clamp(start, edge),
              min: start,
              max: edge,
              onChangeStart: (v) {
                widget.onInteract();
                setState(() => _dragging = v);
              },
              onChanged: (v) {
                widget.onInteract();
                setState(() => _dragging = v);
              },
              onChangeEnd: (v) {
                widget.onInteract();
                setState(() => _dragging = null);
                unawaited(
                  ref
                      .read(playbackProvider.notifier)
                      .seek(Duration(milliseconds: v.round())),
                );
              },
            ),
          ),
        ),
        // Only offered when it would do something.
        if (!atEdge)
          TextButton.icon(
            onPressed: () {
              widget.onInteract();
              unawaited(widget.player.seekToLiveEdge());
            },
            icon: const Icon(Icons.skip_next_rounded, size: 18),
            label: Text(s.backToLive, style: AppText.control),
            style: TextButton.styleFrom(foregroundColor: AppColors.primary),
          )
        else
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: Nova.space2),
            child: Text(
              Fmt.duration(window.span),
              style: AppText.timecode.copyWith(color: AppColors.textMuted),
            ),
          ),
      ],
    );
  }
}

class _LiveDot extends StatelessWidget {
  const _LiveDot();

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 8,
      height: 8,
      decoration: const BoxDecoration(
        color: AppColors.primary,
        shape: BoxShape.circle,
      ),
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
    required this.sleepTimer,
  });

  final PlayerService player;
  final S strings;
  final bool isLive;
  final PlayerFitMode fitMode;
  final ValueChanged<PlayerFitMode> onFitChanged;
  final VoidCallback onInteract;
  final SleepTimer sleepTimer;

  static const _rates = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0];

  /// A video variant named the way a viewer thinks about it.
  ///
  /// mpv reports a video track's title as whatever the container said, which for
  /// an HLS variant playlist is usually nothing useful. The height is the thing
  /// people actually choose by, so it leads; the bitrate disambiguates the two
  /// 1080p variants a panel often offers.
  String _videoLabel(VideoTrack track, int index) {
    final parts = <String>[];
    final height = track.h;
    if (height != null && height > 0) {
      parts.add(switch (height) {
        >= 2000 => '4K',
        >= 1400 => '1440p',
        >= 1000 => '1080p',
        >= 700 => '720p',
        >= 500 => '576p',
        _ => '${height}p',
      });
    }
    final bitrate = track.bitrate;
    if (bitrate != null && bitrate > 0) {
      parts.add('${(bitrate / 1000000).toStringAsFixed(1)} Mb/s');
    }
    if (parts.isEmpty) {
      final title = track.title?.trim();
      if (title != null && title.isNotEmpty) return title;
      return '#${index + 1}';
    }
    return parts.join(' · ');
  }

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
              // Only worth showing when the stream actually carries a choice.
              // A single-variant channel with a "Quality" heading over one row
              // is a control that looks broken rather than one that is absent.
              final video = tracks.video
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
                      if (video.length > 1) ...[
                        _OptionHeading(
                          icon: Icons.high_quality_rounded,
                          label: strings.quality,
                        ),
                        const SizedBox(height: Nova.space2),
                        _TrackRow(
                          label: strings.qualityAuto,
                          selected: selected.video.id == 'auto',
                          onTap: () {
                            onInteract();
                            player.setVideoTrack(VideoTrack.auto());
                          },
                        ),
                        for (var i = 0; i < video.length; i++)
                          _TrackRow(
                            label: _videoLabel(video[i], i),
                            selected: selected.video.id == video[i].id,
                            onTap: () {
                              onInteract();
                              player.setVideoTrack(video[i]);
                            },
                          ),
                        const SizedBox(height: Nova.space5),
                      ],
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
          const SizedBox(height: Nova.space5),
          _PictureAndSyncSection(
            player: player,
            strings: strings,
            onInteract: onInteract,
          ),
          const SizedBox(height: Nova.space5),
          _ToolsSection(
            player: player,
            strings: strings,
            isLive: isLive,
            sleepTimer: sleepTimer,
            onInteract: onInteract,
          ),
          const SizedBox(height: Nova.space5),
          const Divider(color: AppColors.borderSubtle),
          const SizedBox(height: Nova.space3),
          _OptionHeading(
            icon: Icons.insights_rounded,
            label: strings.playbackStats,
          ),
          const SizedBox(height: Nova.space2),
          PlaybackStatsView(player: player, strings: strings),
        ],
      ),
    );
  }
}

/// Recording, stills, picture-in-picture, external subtitles and the sleep
/// timer — the things a viewer *does* with what is playing, as opposed to how it
/// is decoded.
class _ToolsSection extends ConsumerStatefulWidget {
  const _ToolsSection({
    required this.player,
    required this.strings,
    required this.isLive,
    required this.sleepTimer,
    required this.onInteract,
  });

  final PlayerService player;
  final S strings;
  final bool isLive;
  final SleepTimer sleepTimer;
  final VoidCallback onInteract;

  @override
  ConsumerState<_ToolsSection> createState() => _ToolsSectionState();
}

class _ToolsSectionState extends ConsumerState<_ToolsSection> {
  static const _sleepChoices = [15, 30, 45, 60, 90];
  bool _busy = false;

  String get _title => widget.player.current?.title ?? 'MoPlayer';

  Future<void> _toggleRecording() async {
    final s = widget.strings;
    final player = widget.player;
    widget.onInteract();
    if (player.isRecording) {
      final path = player.recordingPath;
      await player.stopRecording();
      if (!mounted) return;
      setState(() {});
      Toast.show(
        context,
        message: s.recordingSaved(path ?? ''),
        icon: Icons.fiber_manual_record_rounded,
        kind: ToastKind.success,
      );
      return;
    }
    // `.mkv` and not `.ts` or `.mp4`: Matroska is the container that survives
    // being cut off mid-write, which is the normal way a recording of live TV
    // ends. An interrupted mp4 has no index and plays nowhere.
    final path =
        '${mediaOutputDir("Videos")}/${stampedName(_title, "mkv", DateTime.now())}';
    final started = await player.startRecording(path);
    if (!mounted) return;
    setState(() {});
    Toast.show(
      context,
      message: started ? s.recording : s.recordingFailed,
      icon: Icons.fiber_manual_record_rounded,
      kind: started ? ToastKind.success : ToastKind.danger,
    );
  }

  Future<void> _screenshot() async {
    final s = widget.strings;
    widget.onInteract();
    final path =
        '${mediaOutputDir("Pictures")}/${stampedName(_title, "png", DateTime.now())}';
    final ok = await widget.player.takeScreenshot(path);
    if (!mounted) return;
    Toast.show(
      context,
      message: ok ? s.screenshotSaved(path) : s.screenshotFailed,
      icon: Icons.photo_camera_rounded,
      kind: ok ? ToastKind.success : ToastKind.danger,
    );
  }

  Future<void> _loadSubtitleFile() async {
    final s = widget.strings;
    widget.onInteract();
    setState(() => _busy = true);
    final chooser = FileChooser();
    try {
      final path = await chooser.openFile(
        title: s.loadSubtitleFile,
        filterName: s.subtitleFileFilter,
        extensions: const ['srt', 'ass', 'ssa', 'sub', 'vtt', 'idx'],
      );
      if (path == null) return;
      await widget.player.addSubtitleFile(path);
      if (!mounted) return;
      Toast.show(
        context,
        message: s.subtitleFileLoaded,
        icon: Icons.closed_caption_rounded,
        kind: ToastKind.success,
      );
    } finally {
      await chooser.close();
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _togglePip() async {
    widget.onInteract();
    final desktop = ref.read(desktopServiceProvider);
    await desktop.setPictureInPicture(!desktop.isPictureInPicture);
    if (mounted) setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    final s = widget.strings;
    final player = widget.player;
    final desktop = ref.watch(desktopServiceProvider);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _OptionHeading(icon: Icons.build_rounded, label: s.playerOptions),
        const SizedBox(height: Nova.space3),
        Wrap(
          spacing: Nova.space2,
          runSpacing: Nova.space2,
          children: [
            _OptionChoice(
              label: player.isRecording ? s.stopRecording : s.record,
              selected: player.isRecording,
              onTap: _toggleRecording,
            ),
            _OptionChoice(
              label: s.screenshot,
              selected: false,
              onTap: _screenshot,
            ),
            _OptionChoice(
              label: s.pictureInPicture,
              selected: desktop.isPictureInPicture,
              onTap: _togglePip,
            ),
            _OptionChoice(
              label: s.loadSubtitleFile,
              selected: false,
              onTap: _busy ? () {} : _loadSubtitleFile,
            ),
          ],
        ),
        if (widget.isLive) ...[
          const SizedBox(height: Nova.space4),
          _OptionHeading(icon: Icons.history_rounded, label: s.timeshift),
          const SizedBox(height: Nova.space1),
          Text(
            s.timeshiftHint,
            style: AppText.caption.copyWith(color: AppColors.textMuted),
          ),
          const SizedBox(height: Nova.space2),
          // Read live rather than cached: how far back a channel can go grows as
          // it stays open, and an offer of "5 minutes" thirty seconds in is a
          // seek that silently does nothing.
          FutureBuilder<Duration>(
            future: player.timeshiftAvailable(),
            builder: (context, snapshot) {
              final available = snapshot.data ?? Duration.zero;
              return Text(
                s.timeshiftAvailable(Fmt.duration(available)),
                style: AppText.control.copyWith(color: AppColors.textSecondary),
              );
            },
          ),
        ],
        const SizedBox(height: Nova.space4),
        _OptionHeading(icon: Icons.bedtime_rounded, label: s.sleepTimer),
        const SizedBox(height: Nova.space3),
        AnimatedBuilder(
          animation: widget.sleepTimer,
          builder: (context, _) {
            final timer = widget.sleepTimer;
            return Wrap(
              spacing: Nova.space2,
              runSpacing: Nova.space2,
              children: [
                _OptionChoice(
                  label: s.sleepTimerOff,
                  selected: !timer.isActive,
                  onTap: () {
                    widget.onInteract();
                    timer.set(null, onFire: () {});
                  },
                ),
                for (final minutes in _sleepChoices)
                  _OptionChoice(
                    label: s.sleepTimerIn(minutes),
                    selected:
                        timer.isActive &&
                        (timer.remaining ?? Duration.zero).inMinutes ==
                            minutes - 1,
                    onTap: () {
                      widget.onInteract();
                      timer.set(
                        Duration(minutes: minutes),
                        onFire: player.pause,
                      );
                    },
                  ),
              ],
            );
          },
        ),
      ],
    );
  }
}

/// Deinterlacing, lip sync and subtitle presentation.
///
/// Grouped together because they are the settings a viewer reaches for *at* a
/// stream that is misbehaving, as opposed to the track lists above, which are
/// about what to play rather than how it looks.
///
/// Stateful because every value here lives in mpv, not in the app: they are read
/// back from the engine on open so the panel shows what is actually in force,
/// including anything a previous channel left set.
class _PictureAndSyncSection extends StatefulWidget {
  const _PictureAndSyncSection({
    required this.player,
    required this.strings,
    required this.onInteract,
  });

  final PlayerService player;
  final S strings;
  final VoidCallback onInteract;

  @override
  State<_PictureAndSyncSection> createState() => _PictureAndSyncSectionState();
}

class _PictureAndSyncSectionState extends State<_PictureAndSyncSection> {
  DeinterlaceMode _deinterlace = DeinterlaceMode.auto;
  double _subDelay = 0;
  double _audioDelay = 0;
  double _subScale = 1;
  bool _subBackground = true;
  bool _loudness = false;
  final Map<PictureAdjustment, int> _picture = {};

  @override
  void initState() {
    super.initState();
    unawaited(_load());
  }

  Future<void> _load() async {
    final player = widget.player;
    final results = await Future.wait([
      player.deinterlace,
      player.subtitleDelay,
      player.audioDelay,
      player.subtitleScale,
    ]);
    // Read back from mpv rather than assumed, so the panel shows what is
    // actually in force — including anything a previous channel left set.
    final picture = <PictureAdjustment, int>{};
    for (final which in PictureAdjustment.values) {
      picture[which] = await player.pictureAdjustment(which);
    }
    if (!mounted) return;
    setState(() {
      _deinterlace = results[0] as DeinterlaceMode;
      _subDelay = results[1] as double;
      _audioDelay = results[2] as double;
      _subScale = results[3] as double;
      _picture
        ..clear()
        ..addAll(picture);
    });
  }

  void _act(VoidCallback change) {
    widget.onInteract();
    setState(change);
  }

  String _seconds(double value) =>
      '${value >= 0 ? '+' : '−'}${value.abs().toStringAsFixed(2)}s';

  @override
  Widget build(BuildContext context) {
    final s = widget.strings;
    final player = widget.player;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _OptionHeading(icon: Icons.blur_linear_rounded, label: s.deinterlace),
        const SizedBox(height: Nova.space1),
        Text(
          s.deinterlaceHint,
          style: AppText.caption.copyWith(color: AppColors.textMuted),
        ),
        const SizedBox(height: Nova.space3),
        Wrap(
          spacing: Nova.space2,
          runSpacing: Nova.space2,
          children: [
            for (final entry in <(DeinterlaceMode, String)>[
              (DeinterlaceMode.auto, s.deinterlaceAuto),
              (DeinterlaceMode.on, s.deinterlaceOn),
              (DeinterlaceMode.off, s.deinterlaceOff),
            ])
              _OptionChoice(
                label: entry.$2,
                selected: _deinterlace == entry.$1,
                onTap: () => _act(() {
                  _deinterlace = entry.$1;
                  unawaited(player.setDeinterlace(entry.$1));
                }),
              ),
          ],
        ),
        const SizedBox(height: Nova.space4),
        _OptionHeading(icon: Icons.sync_rounded, label: s.audioDelay),
        NudgeRow(
          icon: Icons.volume_up_rounded,
          label: s.audioDelay,
          value: _seconds(_audioDelay),
          decreaseLabel: s.decreaseSetting(s.audioDelay),
          increaseLabel: s.increaseSetting(s.audioDelay),
          onDecrease: () => _act(() {
            _audioDelay -= 0.05;
            unawaited(player.setAudioDelay(_audioDelay));
          }),
          onIncrease: () => _act(() {
            _audioDelay += 0.05;
            unawaited(player.setAudioDelay(_audioDelay));
          }),
          onReset: () => _act(() {
            _audioDelay = 0;
            unawaited(player.setAudioDelay(0));
          }),
          resetTooltip: s.resetSetting(s.audioDelay),
        ),
        NudgeRow(
          icon: Icons.closed_caption_rounded,
          label: s.subtitleDelay,
          value: _seconds(_subDelay),
          decreaseLabel: s.decreaseSetting(s.subtitleDelay),
          increaseLabel: s.increaseSetting(s.subtitleDelay),
          onDecrease: () => _act(() {
            _subDelay -= 0.1;
            unawaited(player.setSubtitleDelay(_subDelay));
          }),
          onIncrease: () => _act(() {
            _subDelay += 0.1;
            unawaited(player.setSubtitleDelay(_subDelay));
          }),
          onReset: () => _act(() {
            _subDelay = 0;
            unawaited(player.setSubtitleDelay(0));
          }),
          resetTooltip: s.resetSetting(s.subtitleDelay),
        ),
        NudgeRow(
          icon: Icons.format_size_rounded,
          label: s.subtitleSize,
          value: '${(_subScale * 100).round()}%',
          decreaseLabel: s.decreaseSetting(s.subtitleSize),
          increaseLabel: s.increaseSetting(s.subtitleSize),
          onDecrease: () => _act(() {
            _subScale = (_subScale - 0.1).clamp(0.25, 4);
            unawaited(player.setSubtitleScale(_subScale));
          }),
          onIncrease: () => _act(() {
            _subScale = (_subScale + 0.1).clamp(0.25, 4);
            unawaited(player.setSubtitleScale(_subScale));
          }),
          onReset: () => _act(() {
            _subScale = 1;
            unawaited(player.setSubtitleScale(1));
          }),
          resetTooltip: s.resetSetting(s.subtitleSize),
        ),
        SwitchListTile.adaptive(
          contentPadding: EdgeInsets.zero,
          dense: true,
          value: _subBackground,
          activeThumbColor: AppColors.primary,
          title: Text(s.subtitleBackground, style: AppText.control),
          onChanged: (value) => _act(() {
            _subBackground = value;
            unawaited(player.setSubtitleBackground(value));
          }),
        ),
        const SizedBox(height: Nova.space4),
        _OptionHeading(icon: Icons.tune_rounded, label: s.pictureAdjust),
        for (final entry in <(PictureAdjustment, String)>[
          (PictureAdjustment.brightness, s.brightness),
          (PictureAdjustment.contrast, s.contrast),
          (PictureAdjustment.saturation, s.saturation),
          (PictureAdjustment.gamma, s.gamma),
        ])
          NudgeRow(
            icon: Icons.circle_outlined,
            label: entry.$2,
            value: '${_picture[entry.$1] ?? 0}',
            decreaseLabel: s.decreaseSetting(entry.$2),
            increaseLabel: s.increaseSetting(entry.$2),
            onDecrease: () => _act(() {
              final next = ((_picture[entry.$1] ?? 0) - 5).clamp(-100, 100);
              _picture[entry.$1] = next;
              unawaited(player.setPictureAdjustment(entry.$1, next));
            }),
            onIncrease: () => _act(() {
              final next = ((_picture[entry.$1] ?? 0) + 5).clamp(-100, 100);
              _picture[entry.$1] = next;
              unawaited(player.setPictureAdjustment(entry.$1, next));
            }),
            onReset: () => _act(() {
              _picture[entry.$1] = 0;
              unawaited(player.setPictureAdjustment(entry.$1, 0));
            }),
            resetTooltip: s.resetSetting(entry.$2),
          ),
        const SizedBox(height: Nova.space4),
        _OptionHeading(
          icon: Icons.graphic_eq_rounded,
          label: s.loudnessNormalisation,
        ),
        const SizedBox(height: Nova.space1),
        Text(
          s.loudnessHint,
          style: AppText.caption.copyWith(color: AppColors.textMuted),
        ),
        SwitchListTile.adaptive(
          contentPadding: EdgeInsets.zero,
          dense: true,
          value: _loudness,
          activeThumbColor: AppColors.primary,
          title: Text(s.loudnessNormalisation, style: AppText.control),
          onChanged: (value) => _act(() {
            _loudness = value;
            unawaited(player.setLoudnessNormalisation(value));
          }),
        ),
      ],
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
    return Semantics(
      container: true,
      excludeSemantics: true,
      button: true,
      selected: selected,
      label: label,
      onTap: onTap,
      child: Material(
        color: selected ? AppColors.primary : AppColors.surface3,
        borderRadius: BorderRadius.circular(Nova.radiusControl),
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(Nova.radiusControl),
          child: ConstrainedBox(
            constraints: const BoxConstraints(minHeight: 40),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: Nova.space3),
              child: Center(
                child: Text(
                  label,
                  textDirection: textDirection,
                  style: AppText.control.copyWith(
                    color: selected ? AppColors.onEmber : AppColors.textPrimary,
                    fontWeight: selected ? FontWeight.w700 : FontWeight.w500,
                  ),
                ),
              ),
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
    return Semantics(
      container: true,
      excludeSemantics: true,
      button: true,
      selected: selected,
      label: label,
      onTap: onTap,
      child: Material(
        color: selected
            ? AppColors.primary.withValues(alpha: 0.12)
            : Colors.transparent,
        borderRadius: BorderRadius.circular(Nova.radiusControl),
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(Nova.radiusControl),
          child: ConstrainedBox(
            constraints: const BoxConstraints(minHeight: 40),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: Nova.space3),
              child: Row(
                children: [
                  Icon(
                    selected
                        ? Icons.check_circle_rounded
                        : Icons.circle_outlined,
                    size: 17,
                    color: selected ? AppColors.primary : AppColors.textMuted,
                  ),
                  const SizedBox(width: Nova.space2),
                  Flexible(
                    child: Text(
                      label,
                      overflow: TextOverflow.ellipsis,
                      style: AppText.control.copyWith(
                        color: selected
                            ? AppColors.primary
                            : AppColors.textPrimary,
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
