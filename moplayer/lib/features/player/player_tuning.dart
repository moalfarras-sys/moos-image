import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';

import '../../core/l10n/strings.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_typography.dart';
import '../../core/theme/nova.dart';
import '../../services/player/playback_stats.dart';
import '../../services/player/player_service.dart';

/// A labelled row with a minus/plus pair around a live value.
///
/// Used for the three settings a viewer only ever adjusts *while watching* and
/// against what they are seeing — subtitle timing, lip sync, subtitle size. A
/// slider would be wrong for all three: the useful adjustments are small, exact
/// and repeated, and a slider on a dark overlay is neither.
class NudgeRow extends StatelessWidget {
  const NudgeRow({
    super.key,
    required this.icon,
    required this.label,
    required this.value,
    required this.onDecrease,
    required this.onIncrease,
    required this.decreaseLabel,
    required this.increaseLabel,
    this.onReset,
    this.resetTooltip,
  }) : assert(
         onReset == null || resetTooltip != null,
         'A reset action needs a localized accessible label.',
       );

  final IconData icon;
  final String label;
  final String value;
  final VoidCallback onDecrease;
  final VoidCallback onIncrease;
  final String decreaseLabel;
  final String increaseLabel;
  final VoidCallback? onReset;
  final String? resetTooltip;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: Nova.space2),
      child: Row(
        children: [
          Icon(icon, size: 18, color: AppColors.textSecondary),
          const SizedBox(width: Nova.space2),
          Expanded(child: Text(label, style: AppText.control)),
          _RoundStep(
            icon: Icons.remove_rounded,
            label: decreaseLabel,
            onTap: onDecrease,
          ),
          // The value is fixed-width and always left-to-right: a signed number
          // that jumps around as its digit count changes is hard to nudge
          // towards a target, and a negative sign must not be reordered by an
          // Arabic layout.
          SizedBox(
            width: 74,
            child: Text(
              value,
              textAlign: TextAlign.center,
              textDirection: TextDirection.ltr,
              style: AppText.control.copyWith(
                fontWeight: FontWeight.w700,
                fontFeatures: const [FontFeature.tabularFigures()],
              ),
            ),
          ),
          _RoundStep(
            icon: Icons.add_rounded,
            label: increaseLabel,
            onTap: onIncrease,
          ),
          if (onReset != null) ...[
            const SizedBox(width: Nova.space1),
            _RoundStep(
              icon: Icons.settings_backup_restore_rounded,
              label: resetTooltip!,
              onTap: onReset!,
            ),
          ],
        ],
      ),
    );
  }
}

class _RoundStep extends StatelessWidget {
  const _RoundStep({
    required this.icon,
    required this.label,
    required this.onTap,
  });

  final IconData icon;
  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: label,
      excludeFromSemantics: true,
      child: Semantics(
        button: true,
        label: label,
        child: SizedBox.square(
          dimension: 40,
          child: Material(
            color: AppColors.surface3,
            shape: const CircleBorder(),
            child: InkWell(
              customBorder: const CircleBorder(),
              onTap: onTap,
              child: Center(
                child: Icon(icon, size: 17, color: AppColors.textPrimary),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// Where MoPlayer writes recordings and stills.
///
/// `$XDG_VIDEOS_DIR`/`$XDG_PICTURES_DIR` would be more correct still, but those
/// need `xdg-user-dir` and are frequently unset; Videos and Pictures under HOME
/// are what a freedesktop session creates by default. Unlike application
/// *state* — which must never go in the user's own folders, see
/// `core/utils/app_paths.dart` — a recording is a document the user made and
/// belongs somewhere they can find it.
String mediaOutputDir(String kind) {
  final home = Platform.environment['HOME'] ?? '.';
  return '$home/$kind/MoPlayer';
}

/// A file name that sorts chronologically and cannot collide.
String stampedName(String title, String extension, DateTime now) {
  final safe = title
      .replaceAll(RegExp(r'[/\\:*?"<>|]'), '-')
      .replaceAll(RegExp(r'\s+'), ' ')
      .trim();
  final clipped = safe.length > 60 ? safe.substring(0, 60) : safe;
  String two(int v) => v.toString().padLeft(2, '0');
  final stamp =
      '${now.year}-${two(now.month)}-${two(now.day)} '
      '${two(now.hour)}${two(now.minute)}${two(now.second)}';
  return '${clipped.isEmpty ? "MoPlayer" : clipped} $stamp.$extension';
}

/// Stops playback after a chosen delay.
///
/// Owned here rather than in [PlayerService] because it is a *session*
/// intention, not a property of the pipeline: switching channel should not
/// cancel it, but closing the player should. It pauses rather than quitting —
/// someone who falls asleep to a film wants to find it where they left it, not
/// to find the application gone.
class SleepTimer extends ChangeNotifier {
  Timer? _timer;
  DateTime? _firesAt;

  Duration? get remaining {
    final at = _firesAt;
    if (at == null) return null;
    final left = at.difference(DateTime.now());
    return left.isNegative ? Duration.zero : left;
  }

  bool get isActive => _timer?.isActive ?? false;

  void set(Duration? duration, {required VoidCallback onFire}) {
    _timer?.cancel();
    if (duration == null) {
      _timer = null;
      _firesAt = null;
      notifyListeners();
      return;
    }
    _firesAt = DateTime.now().add(duration);
    _timer = Timer(duration, () {
      _firesAt = null;
      onFire();
      notifyListeners();
    });
    notifyListeners();
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }
}

/// The live engine readout.
///
/// Polls rather than observes because mpv's counters are counters, not events:
/// there is no "the dropped-frame total changed" notification to subscribe to,
/// and a once-a-second sample is both cheap and faster than a viewer can read.
/// The timer only exists while the panel is on screen.
class PlaybackStatsView extends StatefulWidget {
  const PlaybackStatsView({
    super.key,
    required this.player,
    required this.strings,
  });

  final PlayerService player;
  final S strings;

  @override
  State<PlaybackStatsView> createState() => _PlaybackStatsViewState();
}

class _PlaybackStatsViewState extends State<PlaybackStatsView> {
  Timer? _timer;
  PlaybackStats? _stats;

  @override
  void initState() {
    super.initState();
    unawaited(_refresh());
    _timer = Timer.periodic(const Duration(seconds: 1), (_) => _refresh());
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _refresh() async {
    final stats = await widget.player.readStats();
    if (!mounted) return;
    setState(() => _stats = stats);
  }

  @override
  Widget build(BuildContext context) =>
      PlaybackStatsBody(stats: _stats, strings: widget.strings);
}

/// The rendering half of [PlaybackStatsView], with no engine attached.
///
/// Split out so the readout can be tested: the polling half needs a live
/// libmpv, which a widget test cannot have, while the part that decides what
/// turns amber and what a missing value looks like is exactly the part worth
/// testing.
class PlaybackStatsBody extends StatelessWidget {
  const PlaybackStatsBody({
    super.key,
    required this.stats,
    required this.strings,
  });

  final PlaybackStats? stats;
  final S strings;

  @override
  Widget build(BuildContext context) {
    final s = strings;
    final stats = this.stats;
    if (stats == null || stats.resolution == null) {
      return Text(
        s.statsUnavailable,
        style: AppText.control.copyWith(color: AppColors.textMuted),
      );
    }

    final dropped = stats.droppedFrames ?? 0;
    final decoderDropped = stats.decoderDroppedFrames ?? 0;
    final totalDropped = dropped + decoderDropped;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _StatRow(
          label: s.statsDecoder,
          // The most important line here. Software decoding of a 4K stream is
          // the difference between a smooth picture and an unwatchable one, and
          // it is invisible from anywhere else in the app.
          value: stats.isHardwareDecoded
              ? '${s.statsHardware} · ${stats.hwdec}'
              : s.statsSoftware,
          tone: stats.isHardwareDecoded ? _Tone.good : _Tone.warn,
        ),
        _StatRow(
          label: s.statsResolution,
          value: [
            stats.resolution,
            if (stats.qualityLabel != null) '(${stats.qualityLabel})',
            if (stats.videoCodec != null) '· ${stats.videoCodec}',
          ].whereType<String>().join(' '),
        ),
        _StatRow(
          label: s.statsFrameRate,
          value: _fps(stats),
          // Displaying materially fewer frames than the source contains is the
          // machine failing to keep up, which is exactly the complaint this
          // panel exists to make answerable.
          tone: _fpsTone(stats),
        ),
        _StatRow(
          label: s.statsDropped,
          value: '$totalDropped',
          tone: totalDropped == 0
              ? _Tone.good
              : (totalDropped > 60 ? _Tone.warn : _Tone.neutral),
        ),
        if (stats.videoBitrate != null)
          _StatRow(
            label: s.statsBitrate,
            value: '${(stats.videoBitrate! / 1000000).toStringAsFixed(1)} Mb/s',
          ),
        if (stats.cacheSeconds != null)
          _StatRow(
            label: s.statsBuffer,
            value: '${stats.cacheSeconds!.toStringAsFixed(1)} s',
            tone: stats.cacheSeconds! < 1 ? _Tone.warn : _Tone.neutral,
          ),
        if (stats.audioCodec != null)
          _StatRow(
            label: s.statsAudio,
            value: [
              stats.audioCodec,
              if (stats.audioChannels != null) '· ${stats.audioChannels}ch',
            ].whereType<String>().join(' '),
          ),
      ],
    );
  }

  String _fps(PlaybackStats stats) {
    final current = stats.currentFps;
    final container = stats.containerFps;
    if (current == null && container == null) return '—';
    if (current == null) return container!.toStringAsFixed(2);
    if (container == null) return current.toStringAsFixed(1);
    return '${current.toStringAsFixed(1)} / ${container.toStringAsFixed(2)}';
  }

  _Tone _fpsTone(PlaybackStats stats) {
    final current = stats.currentFps;
    final container = stats.containerFps;
    if (current == null || container == null || container <= 0) {
      return _Tone.neutral;
    }
    return current < container * 0.9 ? _Tone.warn : _Tone.good;
  }
}

enum _Tone { neutral, good, warn }

class _StatRow extends StatelessWidget {
  const _StatRow({
    required this.label,
    required this.value,
    this.tone = _Tone.neutral,
  });

  final String label;
  final String value;
  final _Tone tone;

  @override
  Widget build(BuildContext context) {
    final colour = switch (tone) {
      _Tone.good => AppColors.success,
      _Tone.warn => AppColors.warning,
      _Tone.neutral => AppColors.textPrimary,
    };
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: Nova.space1),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            flex: 2,
            child: Text(
              label,
              style: AppText.control.copyWith(color: AppColors.textSecondary),
            ),
          ),
          Expanded(
            flex: 3,
            child: Text(
              value,
              textDirection: TextDirection.ltr,
              textAlign: TextAlign.start,
              style: AppText.control.copyWith(
                color: colour,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
