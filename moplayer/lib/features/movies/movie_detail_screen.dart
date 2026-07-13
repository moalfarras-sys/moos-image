import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/routes.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_typography.dart';
import '../../core/theme/nova.dart';
import '../../core/utils/formatters.dart';
import '../../models/library_items.dart';
import '../../models/media_kind.dart';
import '../../models/vod_movie.dart';
import '../../providers/content_providers.dart';
import '../../providers/core_providers.dart';
import '../../providers/library_providers.dart';
import '../../providers/playback_providers.dart';
import '../../providers/system_providers.dart';
import '../../widgets/buttons.dart';
import '../../widgets/media_card.dart';
import '../../widgets/network_poster.dart';
import '../../widgets/state_views.dart';

const double _posterWidth = 232;
const double _copyMaxWidth = 720;
const double _factsMaxWidth = 980;
const double _factLabelWidth = 96;

/// One movie, over its own artwork.
///
/// The screen is unreachable from an M3U source — there is no VOD catalogue to
/// open it from — and it is not special-cased for one: `movieInfo` throws
/// `Failure.notConfigured` there, and [ErrorView] already says exactly that.
class MovieDetailScreen extends ConsumerWidget {
  const MovieDetailScreen({super.key, required this.movie});

  final VodMovie movie;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(stringsProvider);
    final detail = ref.watch(movieDetailProvider(movie));

    return Stack(
      children: [
        // The grid already handed us a poster, so the hero is painted from it
        // and upgraded to the backdrop when `get_vod_info` lands. The
        // alternative is a black rectangle for as long as the panel takes.
        Positioned.fill(
          child: _HeroBackdrop(
            url: detail.valueOrNull?.backdrop ?? movie.poster,
          ),
        ),
        Positioned.fill(
          child: detail.when(
            loading: () => const LoadingView(),
            error: (error, _) => ErrorView(
              strings: s,
              error: error,
              onRetry: () => ref.invalidate(movieDetailProvider(movie)),
            ),
            data: (data) => _Body(detail: data),
          ),
        ),

        // Outside the AsyncValue: a movie whose details failed to load still has
        // to be a screen the user can leave.
        PositionedDirectional(
          top: Nova.space4,
          start: Nova.space4,
          child: _BackButton(label: s.back),
        ),
      ],
    );
  }
}

class _Body extends ConsumerWidget {
  const _Body({required this.detail});

  final MovieDetail detail;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(stringsProvider);

    // Favourites and resume positions are repository state; watching the counter
    // is what repaints the heart and the button's label after a toggle or a save.
    ref.watch(libraryRefreshProvider);
    final library = ref.read(libraryActionsProvider);
    final playlistId = ref.watch(activePlaylistProvider)?.id;
    final playback = ref.read(playbackProvider.notifier);

    // `get_vod_info` is what carries the true container extension, so the movie
    // that gets *played* is the enriched one, not the row from the grid.
    final movie = detail.movie;
    final resume = library.resumePosition(MediaKind.movie, movie.streamId);
    final favorite = library.isFavorite(MediaKind.movie, movie.streamId);

    final rating = movie.rating ?? 0;
    final year = movie.year?.trim() ?? '';
    final runtime = Fmt.runtimeMinutes((detail.durationSecs ?? 0) ~/ 60);

    return SingleChildScrollView(
      padding: const EdgeInsetsDirectional.fromSTEB(
        Nova.space6,
        // Clears the back button, which floats over this scroll view.
        Nova.space6 + Nova.space6,
        Nova.space6,
        Nova.space6,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              SizedBox(
                width: _posterWidth,
                child: AspectRatio(
                  aspectRatio: 2 / 3,
                  child: NetworkPoster(
                    url: movie.poster,
                    title: movie.name,
                    radius: Nova.radiusPanel,
                  ),
                ),
              ),
              const SizedBox(width: Nova.space6),
              Expanded(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: _copyMaxWidth),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(movie.name, style: AppText.display),
                      const SizedBox(height: Nova.space4),
                      _MetaRow(
                        items: [
                          if (rating > 0) RatingBadge(rating: rating),
                          if (year.isNotEmpty)
                            Text(year, style: AppText.subtitle),
                          if (runtime.isNotEmpty)
                            Text(runtime, style: AppText.subtitle),
                        ],
                      ),
                      const SizedBox(height: Nova.space5),
                      Wrap(
                        spacing: Nova.space3,
                        runSpacing: Nova.space3,
                        crossAxisAlignment: WrapCrossAlignment.center,
                        children: [
                          EmberButton(
                            label: resume > Duration.zero
                                ? s.resumeAt(Fmt.duration(resume))
                                : s.play,
                            icon: Icons.play_arrow_rounded,
                            onPressed: () => playback.playMovie(movie),
                          ),
                          // Worth a button only when there is something to skip:
                          // with no resume point it is the primary action twice.
                          if (resume > Duration.zero)
                            GhostButton(
                              label: s.playFromStart,
                              icon: Icons.replay_rounded,
                              onPressed: () =>
                                  playback.playMovie(movie, fromStart: true),
                            ),
                          IconPill(
                            icon: favorite
                                ? Icons.favorite_rounded
                                : Icons.favorite_border_rounded,
                            active: favorite,
                            tooltip: favorite
                                ? s.removeFromFavorites
                                : s.addToFavorites,
                            onPressed: playlistId == null
                                ? null
                                : () => library.toggleFavorite(
                                    FavoriteItem(
                                      playlistId: playlistId,
                                      kind: MediaKind.movie,
                                      refId: movie.streamId,
                                      title: movie.name,
                                      imageUrl: movie.poster,
                                      payload: movie.toPayload(),
                                    ),
                                  ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: Nova.space6),
          ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: _factsMaxWidth),
            child: _Facts(
              plotLabel: s.plot,
              plot: detail.plot,
              facts: [
                (s.cast, detail.cast),
                (s.director, detail.director),
                (s.genre, detail.genre),
                (s.released, detail.releaseDate),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// The artwork behind the copy.
///
/// [AppColors.heroScrim] ramps from opaque to clear along a plain
/// left-to-right [Alignment], which in Arabic would darken the edge the text is
/// *not* on. Mirroring the painted scrim — rather than declaring the gradient a
/// second time with its colours reversed — keeps the opaque end under the copy
/// in both directions.
class _HeroBackdrop extends StatelessWidget {
  const _HeroBackdrop({required this.url});

  final String? url;

  @override
  Widget build(BuildContext context) {
    final link = url;
    final rtl = Directionality.of(context) == TextDirection.rtl;

    Widget scrim = const DecoratedBox(
      decoration: BoxDecoration(gradient: AppColors.heroScrim),
    );
    if (rtl) scrim = Transform.flip(flipX: true, child: scrim);

    return Stack(
      fit: StackFit.expand,
      children: [
        if (link != null && link.isNotEmpty)
          CachedNetworkImage(
            imageUrl: link,
            fit: BoxFit.cover,
            alignment: Alignment.topCenter,
            memCacheWidth: 1280,
            fadeInDuration: Nova.slow,
            placeholder: (_, _) => const ColoredBox(color: AppColors.surface0),
            errorWidget: (_, _, _) =>
                const ColoredBox(color: AppColors.surface0),
          ),
        // Vertical scrim first: the page scrolls, and the facts at the bottom
        // need a floor under them as much as the title needs a wall behind it.
        const DecoratedBox(
          decoration: BoxDecoration(gradient: AppColors.posterScrim),
        ),
        IgnorePointer(child: scrim),
      ],
    );
  }
}

class _BackButton extends StatelessWidget {
  const _BackButton({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    // The glyph is not auto-mirrored, and in Arabic "back" points the other way.
    final rtl = Directionality.of(context) == TextDirection.rtl;

    return IconPill(
      icon: rtl ? Icons.arrow_forward_rounded : Icons.arrow_back_rounded,
      tooltip: label,
      onPressed: () {
        // Restored into this route by the shell, there is nothing on the stack
        // to pop back to.
        if (context.canPop()) {
          context.pop();
        } else {
          context.go(Routes.movies);
        }
      },
    );
  }
}

/// `★ 7.4 · 2019 · 1h 45m`, in whichever of those the panel actually sent.
class _MetaRow extends StatelessWidget {
  const _MetaRow({required this.items});

  final List<Widget> items;

  @override
  Widget build(BuildContext context) {
    final children = <Widget>[];
    for (var i = 0; i < items.length; i++) {
      if (i > 0) children.add(Text('·', style: AppText.caption));
      children.add(items[i]);
    }

    return Wrap(
      spacing: Nova.space3,
      runSpacing: Nova.space2,
      crossAxisAlignment: WrapCrossAlignment.center,
      children: children,
    );
  }
}

/// The plot, then the label/value rows. A panel fills in whichever of these it
/// feels like, so an absent one is dropped rather than drawn with a blank value.
class _Facts extends StatelessWidget {
  const _Facts({
    required this.plotLabel,
    required this.plot,
    required this.facts,
  });

  final String plotLabel;
  final String? plot;
  final List<(String, String?)> facts;

  @override
  Widget build(BuildContext context) {
    final story = plot?.trim() ?? '';
    final rows = facts
        .where((fact) => (fact.$2?.trim() ?? '').isNotEmpty)
        .toList();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (story.isNotEmpty) ...[
          Text(plotLabel, style: AppText.label),
          const SizedBox(height: Nova.space2),
          Text(story, style: AppText.body),
          const SizedBox(height: Nova.space5),
        ],
        for (final fact in rows)
          Padding(
            padding: const EdgeInsets.only(bottom: Nova.space2),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                SizedBox(
                  width: _factLabelWidth,
                  child: Text(fact.$1, style: AppText.label),
                ),
                Expanded(child: Text(fact.$2!.trim(), style: AppText.body)),
              ],
            ),
          ),
      ],
    );
  }
}
