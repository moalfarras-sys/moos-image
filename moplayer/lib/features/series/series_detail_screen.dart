import 'dart:math' as math;

import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/routes.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_typography.dart';
import '../../core/theme/nova.dart';
import '../../models/library_items.dart';
import '../../models/media_kind.dart';
import '../../models/series.dart';
import '../../providers/content_providers.dart';
import '../../providers/core_providers.dart';
import '../../providers/library_providers.dart';
import '../../providers/playback_providers.dart';
import '../../providers/system_providers.dart';
import '../../widgets/buttons.dart';
import '../../widgets/media_card.dart';
import '../../widgets/network_poster.dart';
import '../../widgets/state_views.dart';
import '../../widgets/tiles.dart';

const double _posterWidth = 232;
const double _copyMaxWidth = 720;
const double _stripHeight = 38;

/// One series, over its own artwork: the hero, a season selector, and the
/// episodes of whichever season is selected.
///
/// There is no play button on the hero. A series is a folder — the episodes are
/// the actions, and picking one is a decision this screen cannot make for the
/// user without guessing at it.
class SeriesDetailScreen extends ConsumerStatefulWidget {
  const SeriesDetailScreen({super.key, required this.series});

  final SeriesItem series;

  @override
  ConsumerState<SeriesDetailScreen> createState() => _SeriesDetailScreenState();
}

class _SeriesDetailScreenState extends ConsumerState<SeriesDetailScreen> {
  int _seasonIndex = 0;

  @override
  Widget build(BuildContext context) {
    final s = ref.watch(stringsProvider);
    final detail = ref.watch(seriesDetailProvider(widget.series));

    return Stack(
      children: [
        // Painted from the cover the grid already had, so the hero is never a
        // black rectangle while `get_series_info` is in flight.
        Positioned.fill(
          child: _HeroBackdrop(
            url: widget.series.backdrop ?? widget.series.cover,
          ),
        ),
        Positioned.fill(
          child: detail.when(
            loading: () => const LoadingView(),
            error: (error, _) => ErrorView(
              strings: s,
              error: error,
              onRetry: () =>
                  ref.invalidate(seriesDetailProvider(widget.series)),
            ),
            data: _content,
          ),
        ),

        // Outside the AsyncValue: a series whose seasons failed to load still
        // has to be a screen the user can leave.
        PositionedDirectional(
          top: Nova.space4,
          start: Nova.space4,
          child: _BackButton(label: s.back),
        ),
      ],
    );
  }

  Widget _content(SeriesDetail detail) {
    final s = ref.watch(stringsProvider);

    // Favourites are repository state; the counter is what repaints the heart.
    ref.watch(favoritesRefreshProvider);
    final library = ref.read(libraryActionsProvider);
    final playlistId = ref.watch(activePlaylistProvider)?.id;

    // The episode in the *player*, not the one merely selected here: a running
    // episode stays marked as running while the user browses another season.
    final playingId = ref.watch(playbackProvider)?.refId;

    final progress = <String, double>{
      for (final item in ref.watch(continueWatchingProvider))
        if (item.kind == MediaKind.episode) item.refId: item.progress,
    };

    final series = detail.series;
    final seasons = detail.seasons;
    final favorite = library.isFavorite(MediaKind.series, series.seriesId);

    // A panel can drop a season between two loads; an index held in state must
    // not be allowed to outlive the list it points into.
    final index = seasons.isEmpty
        ? 0
        : math.min(_seasonIndex, seasons.length - 1);
    final season = seasons.isEmpty ? null : seasons[index];

    final rating = series.rating ?? 0;
    final released = series.releaseDate?.trim() ?? '';
    final genre = series.genre?.trim() ?? '';
    final plot = series.plot?.trim() ?? '';

    return CustomScrollView(
      slivers: [
        SliverToBoxAdapter(
          child: Padding(
            padding: const EdgeInsetsDirectional.fromSTEB(
              Nova.space6,
              // Clears the back button, which floats over this scroll view.
              Nova.space6 + Nova.space6,
              Nova.space6,
              Nova.space6,
            ),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                SizedBox(
                  width: _posterWidth,
                  child: AspectRatio(
                    aspectRatio: 2 / 3,
                    child: NetworkPoster(
                      url: series.cover,
                      title: series.name,
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
                        Text(series.name, style: AppText.display),
                        const SizedBox(height: Nova.space4),
                        _MetaRow(
                          items: [
                            if (rating > 0) RatingBadge(rating: rating),
                            if (released.isNotEmpty)
                              Text(released, style: AppText.subtitle),
                            if (genre.isNotEmpty)
                              Text(genre, style: AppText.subtitle),
                          ],
                        ),
                        const SizedBox(height: Nova.space4),
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
                                    kind: MediaKind.series,
                                    refId: series.seriesId,
                                    title: series.name,
                                    imageUrl: series.cover,
                                    payload: series.toPayload(),
                                  ),
                                ),
                        ),
                        if (plot.isNotEmpty) ...[
                          const SizedBox(height: Nova.space5),
                          Text(s.plot, style: AppText.label),
                          const SizedBox(height: Nova.space2),
                          Text(plot, style: AppText.body),
                        ],
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),

        if (season == null)
          SliverFillRemaining(
            hasScrollBody: false,
            child: EmptyView(
              message: s.empty,
              icon: Icons.subscriptions_rounded,
            ),
          )
        else ...[
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsetsDirectional.fromSTEB(
                Nova.space6,
                0,
                Nova.space6,
                Nova.space5,
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(s.seasons, style: AppText.section),
                  const SizedBox(height: Nova.space3),
                  SizedBox(
                    height: _stripHeight,
                    child: ListView.separated(
                      scrollDirection: Axis.horizontal,
                      itemCount: seasons.length,
                      separatorBuilder: (_, _) =>
                          const SizedBox(width: Nova.space2),
                      itemBuilder: (context, i) => CategoryPill(
                        // `Season.displayName` is English-only. The number is
                        // the part worth keeping, and it is spoken here in the
                        // interface language.
                        label: seasons[i].number == 0
                            ? s.specials
                            : s.season(seasons[i].number),
                        count: seasons[i].episodes.length,
                        selected: i == index,
                        onTap: () => setState(() => _seasonIndex = i),
                      ),
                    ),
                  ),
                  const SizedBox(height: Nova.space5),
                  Text(s.episodes, style: AppText.section),
                ],
              ),
            ),
          ),
          SliverPadding(
            padding: const EdgeInsetsDirectional.fromSTEB(
              Nova.space6,
              0,
              Nova.space6,
              Nova.space6,
            ),
            sliver: SliverList.builder(
              itemCount: season.episodes.length,
              itemBuilder: (context, i) {
                final episode = season.episodes[i];
                return EpisodeTile(
                  number: episode.episodeNum,
                  title: episode.title,
                  plot: episode.plot,
                  imageUrl: episode.image ?? series.cover,
                  durationSecs: episode.durationSecs,
                  progress: progress[episode.id],
                  playing: playingId == episode.id,
                  // The whole season is handed to the player, not just this
                  // episode: it is what "next episode" and autoplay run on.
                  onTap: () => ref
                      .read(playbackProvider.notifier)
                      .playEpisode(
                        series: series,
                        seasonEpisodes: season.episodes,
                        index: i,
                      ),
                );
              },
            ),
          ),
        ],
      ],
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
        // Vertical scrim first: the episode list scrolls over this, and a column
        // of small text needs a floor under it as much as the title needs a wall.
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
          context.go(Routes.series);
        }
      },
    );
  }
}

/// `★ 8.1 · 2016 · Drama`, in whichever of those the panel actually sent.
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
