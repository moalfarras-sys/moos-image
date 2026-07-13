import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/routes.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_typography.dart';
import '../../core/theme/glass.dart';
import '../../core/theme/nova.dart';
import '../../models/category.dart';
import '../../core/l10n/strings.dart';
import '../../models/library_items.dart';
import '../../models/live_channel.dart';
import '../../models/live_match.dart';
import '../../models/media_kind.dart';
import '../../models/series.dart';
import '../../models/vod_movie.dart';
import '../../providers/content_providers.dart';
import '../../providers/core_providers.dart';
import '../../providers/library_providers.dart';
import '../../providers/playback_providers.dart';
import '../../providers/system_providers.dart';
import '../../services/weather/weather_service.dart';
import '../../widgets/buttons.dart';
import '../../widgets/match_strip.dart';
import '../../widgets/media_card.dart';
import '../../widgets/media_rail.dart';
import '../../widgets/network_poster.dart';
import '../../widgets/state_views.dart';
import '../../widgets/tiles.dart';
import '../../widgets/weather_tile.dart';

/// A poster on the home page is a *glance*, not a choice: the choosing happens on
/// the film wall, where the same artwork is 180 px wide and there are forty of it.
/// The rails were built at that same 170x300 and the owner's verdict was the right
/// one — on a 1396-logical window that is five cards and almost no page. At 148 it
/// is seven, the shelves below the fold come into view, and the hero above them
/// still leads.
const double _railPoster = 148;

/// The artwork at 2:3, plus the two lines of type under it — which do not scale.
const double _railPosterHeight = 266;

/// The landing page: one hero, then rails.
///
/// The page is assembled from catalogues that arrive independently, and only
/// *live* decides whether it is loading or broken. Live is the one thing every
/// source has — an M3U playlist carries no VOD and no series — and blocking the
/// whole page on a `get_vod_streams` that a panel is slow to answer would leave
/// a user with a perfectly good channel list staring at a spinner. The VOD rails
/// appear when they land, and stay absent if they never do.
class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(stringsProvider);
    final repo = ref.watch(contentRepositoryProvider);

    final channels = ref.watch(liveStreamsProvider(Category.allId));

    // An M3U source has no VOD endpoint at all, so the providers are not even
    // watched for it — the rails below simply do not exist.
    final movies = (repo?.supportsVod ?? false)
        ? ref.watch(moviesProvider(Category.allId)).valueOrNull ??
              const <VodMovie>[]
        : const <VodMovie>[];
    final series = (repo?.supportsSeries ?? false)
        ? ref.watch(seriesListProvider(Category.allId)).valueOrNull ??
              const <SeriesItem>[]
        : const <SeriesItem>[];

    // The newest twenty of each, by the panel's own `added` stamp — the rails a
    // returning viewer actually opens the app for.
    final newestMovies = (repo?.supportsVod ?? false)
        ? ref.watch(newestMoviesProvider).valueOrNull ?? const <VodMovie>[]
        : const <VodMovie>[];
    final newestSeries = (repo?.supportsSeries ?? false)
        ? ref.watch(newestSeriesProvider).valueOrNull ?? const <SeriesItem>[]
        : const <SeriesItem>[];

    // Both widgets are *absent* until they have something true to say. A match
    // strip with a spinner in it, or a weather tile reading "—°", is worse than
    // no widget: it is a promise the page has not kept.
    final matches = ref.watch(matchesTodayProvider).valueOrNull ?? const [];
    final weather = ref.watch(weatherProvider).valueOrNull;

    final resumable = ref.watch(continueWatchingProvider);
    final favorites = ref.watch(favoritesProvider);
    final playlistId = ref.watch(activePlaylistProvider)?.id ?? '';
    final motion = ref.watch(settingsProvider).cinematicMotion;

    void refresh() => ref.read(catalogRefreshProvider.notifier).state++;

    return channels.when(
      loading: () => LoadingView(label: s.loading),
      error: (error, _) => ErrorView(strings: s, error: error, onRetry: refresh),
      data: (live) {
        if (live.isEmpty &&
            movies.isEmpty &&
            series.isEmpty &&
            resumable.isEmpty) {
          return EmptyView(
            message: s.empty,
            icon: Icons.movie_filter_rounded,
            action: GhostButton(
              label: s.refresh,
              icon: Icons.refresh_rounded,
              onPressed: refresh,
            ),
          );
        }

        final top = _topRated(movies);
        final playback = ref.read(playbackProvider.notifier);
        final actions = ref.read(libraryActionsProvider);

        bool isFavorite(MediaKind kind, String refId) =>
            favorites.any((f) => f.kind == kind && f.refId == refId);

        final resumeHero = resumable.isEmpty ? null : resumable.first;
        final movieHero = resumeHero == null && top.isNotEmpty
            ? top.first
            : null;
        final liveHero = resumeHero == null && movieHero == null
            ? pickLiveHero(live)
            : null;

        return ListView(
          padding: EdgeInsets.zero,
          children: [
            if (resumeHero != null)
              _Hero(
                eyebrow: s.continueWatching,
                title: resumeHero.title,
                meta: s.minutesLeft(_minutesLeft(resumeHero)),
                imageUrl: resumeHero.imageUrl,
                progress: resumeHero.progress,
                playLabel: s.resume,
                onPlay: () => playback.resume(resumeHero),
                infoLabel: s.moreInfo,
                // An episode's payload carries no series id (see
                // `Episode.toPayload`), so there is no detail page to send the
                // user to. Rather than a button that goes nowhere, no button.
                onInfo: resumeHero.kind == MediaKind.movie
                    ? () => context.push(
                        Routes.movieDetail,
                        extra: VodMovie.fromPayload(resumeHero.payload),
                      )
                    : null,
                motion: motion,
              )
            else if (movieHero != null)
              _Hero(
                eyebrow: s.featured,
                title: movieHero.name,
                meta: _movieMeta(movieHero),
                imageUrl: movieHero.poster,
                playLabel: s.play,
                onPlay: () => playback.playMovie(movieHero),
                infoLabel: s.moreInfo,
                onInfo: () => context.push(Routes.movieDetail, extra: movieHero),
                motion: motion,
              )
            else if (liveHero != null)
              _Hero(
                eyebrow: s.onAir,
                title: liveHero.name,
                meta: s.liveChannelsAvailable(live.length),
                logoUrl: liveHero.logo,
                playLabel: s.play,
                onPlay: () => playback.playLive(liveHero),
                infoLabel: s.channels,
                onInfo: () => context.go(Routes.live),
                motion: motion,
              ),

            Padding(
              padding: const EdgeInsets.all(Nova.space6),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                spacing: Nova.space6,
                children: [
                  // What is on, and what it is like outside — the two things a
                  // person glances at before choosing what to watch. They share
                  // a row because they answer the same question, and because
                  // the weather does not deserve a rail of its own.
                  if (matches.isNotEmpty || weather != null)
                    _WidgetRow(
                      title: s.todaysMatches,
                      matches: matches,
                      weather: weather,
                      strings: s,
                      onPlayMatch: (match) {
                        final channel = live.firstWhere(
                          (c) => c.streamId == match.streamId,
                          orElse: () => live.first,
                        );
                        playback.playLive(channel);
                      },
                    ),

                  if (resumable.isNotEmpty)
                    MediaRail(
                      title: s.continueWatching,
                      itemCount: resumable.length,
                      itemWidth: 300,
                      height: 230,
                      itemBuilder: (context, i) {
                        final item = resumable[i];
                        return ContinueCard(
                          title: item.title,
                          subtitle: item.payload['seriesName'] as String?,
                          imageUrl: item.imageUrl,
                          progress: item.progress,
                          remaining: s.minutesLeft(_minutesLeft(item)),
                          onTap: () => playback.resume(item),
                          onDismiss: () =>
                              actions.removeContinue(item.kind, item.refId),
                        );
                      },
                    ),

                  if (live.isNotEmpty)
                    MediaRail(
                      title: s.liveNow,
                      itemCount: math.min(live.length, 20),
                      itemWidth: 196,
                      height: 156,
                      seeAllLabel: s.more,
                      onSeeAll: () => context.go(Routes.live),
                      itemBuilder: (context, i) => _LiveCard(channel: live[i]),
                    ),

                  // Newest first, and *only* newest. The old page carried a
                  // "recently added" rail and a "top rated" rail built from the
                  // same twenty-thousand-film list, which meant two rails of
                  // whatever the panel happened to sort first. What a returning
                  // viewer opens the app to see is what turned up since they
                  // last looked.
                  if (newestMovies.isNotEmpty)
                    MediaRail(
                      title: s.newestMovies,
                      subtitle: s.movies,
                      itemCount: newestMovies.length,
                      itemWidth: _railPoster,
                      height: _railPosterHeight,
                      seeAllLabel: s.more,
                      onSeeAll: () => context.go(Routes.movies),
                      itemBuilder: (context, i) => _MovieCard(
                        movie: newestMovies[i],
                        playlistId: playlistId,
                        isFavorite: isFavorite(
                          MediaKind.movie,
                          newestMovies[i].streamId,
                        ),
                      ),
                    ),

                  if (newestSeries.isNotEmpty)
                    MediaRail(
                      title: s.newestSeries,
                      subtitle: s.series,
                      itemCount: newestSeries.length,
                      itemWidth: _railPoster,
                      height: _railPosterHeight,
                      seeAllLabel: s.more,
                      onSeeAll: () => context.go(Routes.series),
                      itemBuilder: (context, i) => _SeriesCard(
                        series: newestSeries[i],
                        playlistId: playlistId,
                        isFavorite: isFavorite(
                          MediaKind.series,
                          newestSeries[i].seriesId,
                        ),
                      ),
                    ),

                  if (top.isNotEmpty)
                    MediaRail(
                      title: s.topRated,
                      subtitle: s.movies,
                      itemCount: top.length,
                      itemWidth: _railPoster,
                      height: _railPosterHeight,
                      seeAllLabel: s.more,
                      onSeeAll: () => context.go(Routes.movies),
                      itemBuilder: (context, i) => _MovieCard(
                        movie: top[i],
                        playlistId: playlistId,
                        isFavorite: isFavorite(MediaKind.movie, top[i].streamId),
                      ),
                    ),
                ],
              ),
            ),
          ],
        );
      },
    );
  }
}

/// The match strip and the weather, side by side.
///
/// The weather is given a fixed width and the football takes the rest: on a
/// narrow window it is the *fixtures* that need the room, and a tile that says
/// "26°" reads at any size.
class _WidgetRow extends StatelessWidget {
  const _WidgetRow({
    required this.title,
    required this.matches,
    required this.weather,
    required this.strings,
    required this.onPlayMatch,
  });

  final String title;
  final List<LiveMatch> matches;
  final WeatherNow? weather;
  final S strings;
  final void Function(LiveMatch) onPlayMatch;

  @override
  Widget build(BuildContext context) {
    final narrow = MediaQuery.sizeOf(context).width < 900;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (matches.isNotEmpty) ...[
          SectionHeader(title: title),
          const SizedBox(height: Nova.space4),
        ],
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (matches.isNotEmpty)
              Expanded(
                child: MatchStrip(
                  matches: matches,
                  strings: strings,
                  onPlay: onPlayMatch,
                ),
              ),
            if (matches.isNotEmpty && weather != null)
              const SizedBox(width: Nova.space4),
            if (weather != null)
              WeatherTile(
                weather: weather!,
                strings: strings,
                width: narrow ? 200 : 260,
              ),
          ],
        ),
      ],
    );
  }
}

/// The channel that opens the page when nothing else can.
///
/// An M3U source is live-only — no VOD, no series — and on a first run there is
/// no history either, so both of the heroes above it are null. That is the most
/// common IPTV source there is, and it was landing on a single rail above a
/// screenful of black.
///
/// A channel that has a logo is preferred: the hero shows the mark, and a hero
/// whose mark is a monogram of the channel's initials looks like a page that
/// failed to load rather than one that was designed.
@visibleForTesting
LiveChannel? pickLiveHero(List<LiveChannel> live) {
  if (live.isEmpty) return null;
  return live.firstWhere(
    (c) => c.logo != null && c.logo!.trim().isNotEmpty,
    orElse: () => live.first,
  );
}

int _minutesLeft(ContinueWatchingItem item) {
  final left = Duration(seconds: item.durationSecs - item.positionSecs);
  return math.max(1, left.inMinutes);
}

String _movieMeta(VodMovie movie) {
  return [
    if (movie.year != null && movie.year!.isNotEmpty) movie.year!,
    if ((movie.rating ?? 0) > 0) '★ ${movie.rating!.toStringAsFixed(1)}',
  ].join('  ·  ');
}

List<VodMovie> _topRated(List<VodMovie> all) {
  final rated = all.where((m) => (m.rating ?? 0) > 0).toList()
    ..sort((a, b) => b.rating!.compareTo(a.rating!));
  return rated.take(24).toList();
}

/// The full-bleed opener.
///
/// Two scrims, not one: [AppColors.heroScrim] runs along the reading axis and is
/// what keeps the copy legible over artwork nobody chose; [AppColors.posterScrim]
/// runs down the image and is what stops the first rail from colliding with the
/// picture's bottom edge.
class _Hero extends StatelessWidget {
  const _Hero({
    required this.eyebrow,
    required this.title,
    required this.meta,
    required this.playLabel,
    required this.onPlay,
    required this.infoLabel,
    required this.motion,
    this.imageUrl,
    this.logoUrl,
    this.progress,
    this.onInfo,
  });

  final String eyebrow;
  final String title;
  final String meta;
  final String playLabel;
  final VoidCallback onPlay;
  final String infoLabel;
  final bool motion;
  final String? imageUrl;

  /// A channel's logo, when the hero is a live channel. It is drawn as a mark
  /// above the copy — *not* as the backdrop. A logo is a transparent PNG of
  /// unknowable aspect (see [NetworkPoster.logoMode]); stretched to fill a
  /// 1400×345 hero it is beheaded, and the one picture the channel has is the
  /// one thing the hero must not ruin.
  final String? logoUrl;

  final double? progress;
  final VoidCallback? onInfo;

  @override
  Widget build(BuildContext context) {
    final height = math.max(320.0, MediaQuery.sizeOf(context).height * 0.44);
    final hasLogo = logoUrl != null && logoUrl!.trim().isNotEmpty;

    return SizedBox(
      height: height,
      child: Stack(
        fit: StackFit.expand,
        children: [
          if (hasLogo)
            const DecoratedBox(
              decoration: BoxDecoration(gradient: AppColors.heroPlate),
            )
          else
            NetworkPoster(url: imageUrl, title: title, radius: 0),
          const DecoratedBox(
            decoration: BoxDecoration(gradient: AppColors.heroScrim),
          ),
          const DecoratedBox(
            decoration: BoxDecoration(gradient: AppColors.posterScrim),
          ),
          PositionedDirectional(
            start: Nova.space6,
            bottom: Nova.space6,
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 620),
              child: TweenAnimationBuilder<double>(
                tween: Tween<double>(begin: 0, end: 1),
                duration: motion ? Nova.slow : Duration.zero,
                curve: Curves.easeOutCubic,
                builder: (context, t, child) => Opacity(
                  opacity: t,
                  // The rise is vertical. A horizontal one would have a
                  // direction, and a direction is wrong half the time in a
                  // layout that is also mirrored.
                  child: Transform.translate(
                    offset: Offset(0, (1 - t) * 18),
                    child: child,
                  ),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    if (hasLogo) ...[
                      SizedBox(
                        width: 148,
                        height: 84,
                        child: NetworkPoster(
                          url: logoUrl,
                          title: title,
                          logoMode: true,
                          width: 148,
                          radius: Nova.radiusControl,
                          background: AppColors.surface2,
                        ),
                      ),
                      const SizedBox(height: Nova.space4),
                    ],
                    Text(
                      eyebrow.toUpperCase(),
                      style: AppText.label.copyWith(
                        color: AppColors.primary,
                        letterSpacing: 1.4,
                      ),
                    ),
                    const SizedBox(height: Nova.space2),
                    Text(
                      title,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: AppText.display,
                    ),
                    if (meta.isNotEmpty) ...[
                      const SizedBox(height: Nova.space2),
                      Text(meta, style: AppText.subtitle),
                    ],
                    if (progress != null) ...[
                      const SizedBox(height: Nova.space3),
                      SizedBox(width: 260, child: ProgressBar(value: progress!)),
                    ],
                    const SizedBox(height: Nova.space5),
                    Row(
                      mainAxisSize: MainAxisSize.min,
                      spacing: Nova.space3,
                      children: [
                        EmberButton(
                          label: playLabel,
                          icon: Icons.play_arrow_rounded,
                          onPressed: onPlay,
                        ),
                        if (onInfo != null)
                          GhostButton(
                            label: infoLabel,
                            icon: Icons.info_outline_rounded,
                            onPressed: onInfo,
                          ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// A channel in the "On air now" rail.
///
/// Not a [PosterCard]: a channel's artwork is a transparent logo of unknowable
/// aspect, and cropping one to fill a poster reliably beheads it. It is
/// letterboxed instead, which is what [NetworkPoster.logoMode] is for.
///
/// The rail carries no EPG either. Twenty cards would mean twenty
/// `get_short_epg` round-trips on the landing page; the guide belongs on the
/// Live screen, where the user actually asked for it.
class _LiveCard extends ConsumerWidget {
  const _LiveCard({required this.channel});

  final LiveChannel channel;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(stringsProvider);

    return NovaCard(
      padding: const EdgeInsets.all(Nova.space3),
      onTap: () => ref.read(playbackProvider.notifier).playLive(channel),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            child: Stack(
              children: [
                Positioned.fill(
                  child: NetworkPoster(
                    url: channel.logo,
                    title: channel.name,
                    logoMode: true,
                    radius: Nova.radiusControl,
                  ),
                ),
                PositionedDirectional(
                  top: Nova.space1,
                  start: Nova.space1,
                  child: LiveBadge(label: s.onAir),
                ),
              ],
            ),
          ),
          const SizedBox(height: Nova.space2),
          Text(
            channel.name,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: AppText.control,
          ),
        ],
      ),
    );
  }
}

class _MovieCard extends ConsumerWidget {
  const _MovieCard({
    required this.movie,
    required this.playlistId,
    required this.isFavorite,
  });

  final VodMovie movie;
  final String playlistId;
  final bool isFavorite;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return PosterCard(
      title: movie.name,
      subtitle: movie.year,
      imageUrl: movie.poster,
      badge: (movie.rating ?? 0) > 0 ? RatingBadge(rating: movie.rating!) : null,
      isFavorite: isFavorite,
      onTap: () => context.push(Routes.movieDetail, extra: movie),
      onPlay: () => ref.read(playbackProvider.notifier).playMovie(movie),
      onToggleFavorite: () => ref
          .read(libraryActionsProvider)
          .toggleFavorite(
            FavoriteItem(
              playlistId: playlistId,
              kind: MediaKind.movie,
              refId: movie.streamId,
              title: movie.name,
              subtitle: movie.year,
              imageUrl: movie.poster,
              payload: movie.toPayload(),
            ),
          ),
    );
  }
}

class _SeriesCard extends ConsumerWidget {
  const _SeriesCard({
    required this.series,
    required this.playlistId,
    required this.isFavorite,
  });

  final SeriesItem series;
  final String playlistId;
  final bool isFavorite;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return PosterCard(
      title: series.name,
      subtitle: series.genre,
      imageUrl: series.cover,
      badge: (series.rating ?? 0) > 0
          ? RatingBadge(rating: series.rating!)
          : null,
      isFavorite: isFavorite,
      // No hover play button: a series is a folder, not a stream. The way in is
      // the detail page, which is where the episodes are.
      onTap: () => context.push(Routes.seriesDetail, extra: series),
      onToggleFavorite: () => ref
          .read(libraryActionsProvider)
          .toggleFavorite(
            FavoriteItem(
              playlistId: playlistId,
              kind: MediaKind.series,
              refId: series.seriesId,
              title: series.name,
              subtitle: series.genre,
              imageUrl: series.cover,
              payload: series.toPayload(),
            ),
          ),
    );
  }
}
