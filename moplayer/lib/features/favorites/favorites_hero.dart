import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/routes.dart';
import '../../core/l10n/strings.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_typography.dart';
import '../../core/theme/motion.dart';
import '../../core/theme/nova.dart';
import '../../models/library_items.dart';
import '../../models/live_channel.dart';
import '../../models/media_kind.dart';
import '../../models/series.dart';
import '../../models/vod_movie.dart';
import '../../providers/library_providers.dart';
import '../../providers/playback_providers.dart';
import '../../providers/system_providers.dart';
import '../../widgets/backdrop.dart';
import '../../widgets/buttons.dart';
import '../../widgets/media_card.dart';
import '../../widgets/network_poster.dart';

/// The newest favourite, at the size of a poster on a wall.
///
/// Three things here are decisions rather than decoration:
///
///  * **The artwork is ambience, and the poster is the picture.** A panel gives
///    a film a 2:3 poster and nothing else; cropped to a 21:9 hero it is a
///    close-up of somebody's chin. So the poster is *blurred* into the backdrop
///    and shown again, sharp, at its own aspect on the trailing edge — which is
///    also the edge [AppColors.heroScrim] leaves bright, and it flips in Arabic
///    along with everything else.
///  * **A channel gets the plate, not the backdrop.** A channel's only picture
///    is a transparent logo. Stretched across a hero it is a smear, so it keeps
///    [AppColors.heroPlate] behind it and stays a logo.
///  * **The item is the newest favourite, not a recommendation.** This screen
///    does not rank anything. The hero is the last thing the user kept, which is
///    a fact the app already knows and does not have to invent.
class FavoriteHero extends ConsumerWidget {
  const FavoriteHero({super.key, required this.item});

  final FavoriteItem item;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(stringsProvider);
    final actions = ref.read(libraryActionsProvider);
    final playback = ref.read(playbackProvider.notifier);

    final isLive = item.kind == MediaKind.live;
    final art = item.imageUrl?.trim();
    final hasArt = !isLive && art != null && art.isNotEmpty;

    // Tall enough to be a hero, short enough that the first shelf still shows a
    // sliver of itself under it — the thing that tells the user to scroll.
    final height = (MediaQuery.sizeOf(context).height * 0.44).clamp(
      300.0,
      460.0,
    );

    final artBox = height - Nova.space5 * 2;
    final artWidth = (isLive ? artBox : artBox * 2 / 3).clamp(120.0, 200.0);

    return SizedBox(
      height: height,
      child: LayoutBuilder(
        builder: (context, constraints) {
          // Under ~760 px the sharp poster and the copy would fight for the same
          // pixels. The backdrop already carries the artwork; the poster is what
          // goes.
          final wide = constraints.maxWidth >= 760;
          final copyWidth = wide
              ? (constraints.maxWidth * 0.52).clamp(320.0, 620.0)
              : constraints.maxWidth - Nova.space6 * 2;

          return Stack(
            fit: StackFit.expand,
            children: [
              if (hasArt)
                Backdrop(
                  imageUrl: art,
                  // Softened: it is the light in the room, not the picture on
                  // the wall. The sharp poster beside it is the picture.
                  blur: 26,
                  darken: 0.18,
                )
              else ...[
                const DecoratedBox(
                  decoration: BoxDecoration(gradient: AppColors.heroPlate),
                ),
                const DecoratedBox(
                  decoration: BoxDecoration(gradient: AppColors.heroFloor),
                ),
              ],

              if (wide)
                PositionedDirectional(
                  end: Nova.space6,
                  top: 0,
                  bottom: 0,
                  child: Center(
                    child: _HeroArt(
                      item: item,
                      width: artWidth,
                      logoMode: isLive,
                    ),
                  ),
                ),

              PositionedDirectional(
                start: Nova.space6,
                bottom: Nova.space6,
                child: SizedBox(
                  width: copyWidth,
                  child: ScaleFadeIn(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            if (isLive) ...[
                              LiveBadge(label: s.onAir),
                              const SizedBox(width: Nova.space2 + 2),
                            ],
                            Flexible(
                              child: Text(
                                s.yourFavorites,
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: AppText.label.copyWith(
                                  color: AppColors.primaryBright,
                                  letterSpacing: 2,
                                ),
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: Nova.space3),

                        Text(
                          item.title,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: AppText.display,
                        ),

                        if (item.subtitle != null &&
                            item.subtitle!.isNotEmpty) ...[
                          const SizedBox(height: Nova.space2),
                          Text(
                            item.subtitle!,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: AppText.body,
                          ),
                        ],

                        const SizedBox(height: Nova.space5),
                        Wrap(
                          spacing: Nova.space3,
                          runSpacing: Nova.space3,
                          crossAxisAlignment: WrapCrossAlignment.center,
                          children: [
                            ..._actions(context, s, playback),
                            GhostButton(
                              label: s.removeFromFavorites,
                              // Filled, because it *is* set: this button turns
                              // it off, and the state it shows is the state the
                              // item is in.
                              icon: Icons.favorite_rounded,
                              onPressed: () =>
                                  actions.removeFavorite(item.kind, item.refId),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ],
          );
        },
      ),
    );
  }

  /// What the hero's primary button does, which is not the same thing for all
  /// three kinds: a film and a channel *play*; a series **opens**, because a
  /// series is a folder and playing a folder is not a thing.
  ///
  /// An episode never reaches here — it is favourited as its series — and if one
  /// somehow did, it gets no primary action rather than a button built out of
  /// the wrong payload.
  List<Widget> _actions(BuildContext context, S s, PlaybackController playback) {
    switch (item.kind) {
      case MediaKind.live:
        return [
          EmberButton(
            label: s.play,
            icon: Icons.play_arrow_rounded,
            onPressed: () => playback.playLive(
              LiveChannel.fromPayload(item.payload),
            ),
          ),
        ];

      case MediaKind.movie:
        final movie = VodMovie.fromPayload(item.payload);
        return [
          EmberButton(
            label: s.play,
            icon: Icons.play_arrow_rounded,
            onPressed: () => playback.playMovie(movie),
          ),
          GhostButton(
            label: s.moreInfo,
            icon: Icons.info_outline_rounded,
            onPressed: () => context.push(Routes.movieDetail, extra: movie),
          ),
        ];

      case MediaKind.series:
        return [
          EmberButton(
            label: s.moreInfo,
            icon: Icons.playlist_play_rounded,
            onPressed: () => context.push(
              Routes.seriesDetail,
              extra: SeriesItem.fromPayload(item.payload),
            ),
          ),
        ];

      case MediaKind.episode:
        return const [];
    }
  }
}

/// The sharp copy of the artwork, on the edge the scrim leaves lit.
class _HeroArt extends StatelessWidget {
  const _HeroArt({
    required this.item,
    required this.width,
    required this.logoMode,
  });

  final FavoriteItem item;
  final double width;

  /// A channel logo is letterboxed on its plate rather than cropped to a poster.
  final bool logoMode;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: width,
      child: AspectRatio(
        aspectRatio: logoMode ? 1 : 2 / 3,
        child: DecoratedBox(
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(Nova.radiusCard),
            boxShadow: [
              // The poster sits *above* the backdrop it was blurred into, and a
              // shadow is the only thing that says so.
              BoxShadow(
                color: AppColors.surface0.withValues(alpha: 0.62),
                blurRadius: 34,
                spreadRadius: -8,
                offset: const Offset(0, 14),
              ),
            ],
          ),
          child: NetworkPoster(
            url: item.imageUrl,
            title: item.title,
            width: width,
            radius: Nova.radiusCard,
            logoMode: logoMode,
            // The backdrop behind it owns the crossfade; a second fade here
            // would make the same image arrive twice.
            fadeIn: false,
          ),
        ),
      ),
    );
  }
}
