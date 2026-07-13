import 'dart:async';

import 'package:flutter/material.dart';

import '../core/l10n/strings.dart';
import '../core/theme/app_colors.dart';
import '../core/theme/app_typography.dart';
import '../core/theme/motion.dart';
import '../core/theme/nova.dart';
import '../models/live_match.dart';

/// Today's football, as a row of cards that are each one press from playing.
///
/// The fixtures come out of the panel's own programme guide, joined against the
/// user's own channel list, so every card here **is a channel the subscription
/// carries**. That is the whole design: a match card that cannot be pressed is a
/// disappointment dressed up as a feature, and it is the reason this does not
/// use a sports API — an API knows the score, but it does not know which of
/// *your* channels is showing the game.
class MatchStrip extends StatelessWidget {
  const MatchStrip({
    super.key,
    required this.matches,
    required this.strings,
    required this.onPlay,
    this.height = 128,
  });

  final List<LiveMatch> matches;
  final S strings;
  final void Function(LiveMatch match) onPlay;
  final double height;

  @override
  Widget build(BuildContext context) {
    if (matches.isEmpty) return const SizedBox.shrink();

    return SizedBox(
      height: height,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: EdgeInsets.zero,
        itemCount: matches.length,
        separatorBuilder: (_, _) => const SizedBox(width: Nova.space4),
        itemBuilder: (context, i) => _MatchCard(
          match: matches[i],
          strings: strings,
          onPlay: () => onPlay(matches[i]),
        ),
      ),
    );
  }
}

class _MatchCard extends StatefulWidget {
  const _MatchCard({
    required this.match,
    required this.strings,
    required this.onPlay,
  });

  final LiveMatch match;
  final S strings;
  final VoidCallback onPlay;

  @override
  State<_MatchCard> createState() => _MatchCardState();
}

class _MatchCardState extends State<_MatchCard> {
  bool _hovered = false;
  bool _focused = false;

  /// A kick-off time is only wrong for one minute, but "LIVE" is wrong until the
  /// screen is rebuilt — and nothing else on the home page rebuilds it. The card
  /// that says a match is on air is the one card that has to keep its own time.
  Timer? _tick;

  @override
  void initState() {
    super.initState();
    _tick = Timer.periodic(const Duration(seconds: 30), (_) {
      if (mounted) setState(() {});
    });
  }

  @override
  void dispose() {
    _tick?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final s = widget.strings;
    final match = widget.match;
    final live = match.isLiveNow;
    final lifted = _hovered || _focused;

    return FocusableActionDetector(
      onShowFocusHighlight: (v) => setState(() => _focused = v),
      onShowHoverHighlight: (v) => setState(() => _hovered = v),
      actions: {
        ActivateIntent: CallbackAction<ActivateIntent>(
          onInvoke: (_) {
            widget.onPlay();
            return null;
          },
        ),
      },
      child: GestureDetector(
        onTap: widget.onPlay,
        child: AnimatedContainer(
          duration: Motion.duration(context, Nova.hover),
          curve: Ease.enter,
          width: 300,
          padding: const EdgeInsets.all(Nova.space4),
          decoration: BoxDecoration(
            color: lifted ? AppColors.surfaceWarm : AppColors.surface2,
            borderRadius: BorderRadius.circular(Nova.radiusCard),
            border: Border.all(
              color: _focused
                  ? AppColors.focus
                  : live
                  ? AppColors.live.withValues(alpha: 0.55)
                  : AppColors.borderSubtle,
              width: _focused ? 2 : 1,
            ),
            boxShadow: lifted
                ? [
                    BoxShadow(
                      color: Colors.black.withValues(alpha: 0.45),
                      blurRadius: 22,
                      offset: const Offset(0, 8),
                    ),
                  ]
                : null,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Row(
                children: [
                  if (live)
                    const _OnAirDot()
                  else
                    Icon(
                      Icons.schedule_rounded,
                      size: 13,
                      color: AppColors.textMuted,
                    ),
                  const SizedBox(width: Nova.space2),
                  Text(
                    live ? s.onAir : _clock(match.start),
                    style: AppText.label.copyWith(
                      color: live ? AppColors.live : AppColors.textSecondary,
                      letterSpacing: live ? 1.2 : 0.4,
                    ),
                  ),
                  const Spacer(),
                  // The channel's *name*, not its logo.
                  //
                  // The logo was tried and it is the wrong thing here: half the
                  // sports channels on a panel carry a logo URL that 404s, and
                  // NetworkPoster then does its job and draws the initials —
                  // which for `beIN SPORTS FR 2` is a plate reading "--". A
                  // two-dash plate on four cards in a row looks like the app
                  // failed to load something. The name always resolves, and it
                  // is the thing the viewer is actually asking for: *which
                  // channel is this on*.
                  if (match.channelName != null)
                    Flexible(
                      child: Text(
                        match.channelName!,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        textAlign: TextAlign.end,
                        style: AppText.caption.copyWith(
                          color: AppColors.textMuted,
                        ),
                      ),
                    ),
                ],
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _Team(name: match.home),
                  const SizedBox(height: Nova.space1),
                  _Team(name: match.away),
                ],
              ),
              if (match.competition != null)
                Text(
                  match.competition!,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppText.caption.copyWith(color: AppColors.textMuted),
                ),
            ],
          ),
        ),
      ),
    );
  }

  /// 24-hour, zero-padded, and always in Latin digits: a kick-off time sits next
  /// to a scoreline and a channel number, and mixing digit systems inside one
  /// card is harder to scan than either system alone.
  static String _clock(DateTime t) =>
      '${t.hour.toString().padLeft(2, '0')}:${t.minute.toString().padLeft(2, '0')}';
}

class _Team extends StatelessWidget {
  const _Team({required this.name});

  final String name;

  @override
  Widget build(BuildContext context) {
    return Text(
      name,
      maxLines: 1,
      overflow: TextOverflow.ellipsis,
      style: AppText.control.copyWith(
        color: AppColors.textPrimary,
        fontWeight: FontWeight.w600,
      ),
    );
  }
}

/// The one thing on the card that moves. It is a state, not a decoration: a
/// static red dot and a live red dot look identical in a screenshot, and the
/// user is trying to answer "is it on *now*".
class _OnAirDot extends StatefulWidget {
  const _OnAirDot();

  @override
  State<_OnAirDot> createState() => _OnAirDotState();
}

class _OnAirDotState extends State<_OnAirDot>
    with SingleTickerProviderStateMixin {
  late final AnimationController _pulse = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1400),
  )..repeat(reverse: true);

  @override
  void dispose() {
    _pulse.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (Motion.isReduced(context)) {
      return const _Dot(opacity: 1);
    }
    return AnimatedBuilder(
      animation: _pulse,
      builder: (_, _) => _Dot(opacity: 0.45 + 0.55 * _pulse.value),
    );
  }
}

class _Dot extends StatelessWidget {
  const _Dot({required this.opacity});

  final double opacity;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 8,
      height: 8,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: AppColors.live.withValues(alpha: opacity),
        boxShadow: [
          BoxShadow(
            color: AppColors.live.withValues(alpha: opacity * 0.5),
            blurRadius: 8,
            spreadRadius: 1,
          ),
        ],
      ),
    );
  }
}
