import 'dart:async';
import 'dart:math' as math;

import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/routes.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/baked_gradient.dart';
import '../../core/theme/app_typography.dart';
import '../../core/theme/glass.dart';
import '../../core/theme/motion.dart';
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
      error: (error, _) => ErrorView(
        strings: s,
        error: error,
        onRetry: refresh,
        // Expired/invalid-subscription failures can't be fixed by Retry — offer
        // the Settings route that can (change or re-enter the source).
        onOpenSettings: () => context.go(Routes.settings),
      ),
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

        final top = ref.watch(topRatedMoviesProvider);
        final playback = ref.read(playbackProvider.notifier);
        final actions = ref.read(libraryActionsProvider);

        bool isFavorite(MediaKind kind, String refId) =>
            favorites.any((f) => f.kind == kind && f.refId == refId);

        final resumeHero = resumable.isEmpty ? null : resumable.first;
        // The spotlight: what to continue, then the best-rated films with
        // artwork, and — for a source that is only channels — its channels.
        // A playlist's films carry no rating; they still deserve the stage.
        final spotlightMovies = (top.isNotEmpty ? top : newestMovies)
            .where((m) => (m.poster ?? '').trim().isNotEmpty)
            .take(resumeHero == null ? 6 : 5)
            .toList();
        final liveHeroes = spotlightMovies.isEmpty && resumeHero == null
            ? [
                ?pickLiveHero(live),
                ...live
                    .where((c) => (c.logo ?? '').trim().isNotEmpty)
                    .skip(1)
                    .take(4),
              ]
            : const <LiveChannel>[];
        final slideCount =
            (resumeHero == null ? 0 : 1) +
            spotlightMovies.length +
            liveHeroes.length;

        Widget slide(int index, double reveal, Widget? pager) {
          var i = index;
          if (resumeHero != null) {
            if (i == 0) {
              return HomeHero(
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
                reveal: reveal,
                pager: pager,
              );
            }
            i -= 1;
          }
          if (i < spotlightMovies.length) {
            final movieHero = spotlightMovies[i];
            // List endpoints only carry the poster. Upgrade the film to its
            // cinematic backdrop and story as soon as the cached detail
            // arrives; the page never blocks on this second request.
            final heroDetail = ref
                .watch(movieDetailProvider(movieHero))
                .valueOrNull;
            return HomeHero(
              eyebrow: s.featured,
              title: movieHero.name,
              meta: _movieMeta(movieHero, heroDetail),
              imageUrl: heroDetail?.backdrop ?? movieHero.poster,
              description: heroDetail?.plot,
              playLabel: s.play,
              onPlay: () => playback.playMovie(movieHero),
              infoLabel: s.moreInfo,
              onInfo: () => context.push(Routes.movieDetail, extra: movieHero),
              motion: motion,
              reveal: reveal,
              pager: pager,
            );
          }
          final liveHero = liveHeroes[i - spotlightMovies.length];
          return HomeHero(
            eyebrow: s.onAir,
            title: liveHero.name,
            meta: s.liveChannelsAvailable(live.length),
            logoUrl: liveHero.logo,
            playLabel: s.play,
            onPlay: () => playback.playLive(liveHero, channels: live),
            infoLabel: s.channels,
            onInfo: () => context.go(Routes.live),
            motion: motion,
            reveal: reveal,
            pager: pager,
          );
        }

        return ListView(
          // The shell hands this screen the mini player's height when it is
          // showing (see `main_shell.dart`), and the last rail — "continue
          // watching", the row most likely to be wanted — must scroll clear of
          // it. Only the *bottom* is padded: the hero is deliberately full
          // bleed.
          padding: EdgeInsets.only(
            bottom: MediaQuery.paddingOf(context).bottom + Nova.space5,
          ),
          children: [
            if (slideCount > 0)
              HeroCarousel(
                count: slideCount,
                motion: motion,
                builder: (context, index, reveal, pager) =>
                    slide(index, reveal, pager),
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
                        playback.playLive(channel, channels: live);
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
                      itemBuilder: (context, i) =>
                          _LiveCard(channel: live[i], channels: live),
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
                        isFavorite: isFavorite(
                          MediaKind.movie,
                          top[i].streamId,
                        ),
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

    final matchStrip = matches.isEmpty
        ? null
        : MatchStrip(matches: matches, strings: strings, onPlay: onPlayMatch);
    final weatherTile = weather == null
        ? null
        : WeatherTile(
            weather: weather!,
            strings: strings,
            width: narrow ? double.infinity : 260,
          );

    if (narrow) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (matchStrip != null) ...[
            SectionHeader(title: title),
            const SizedBox(height: Nova.space4),
            matchStrip,
          ],
          if (matchStrip != null && weatherTile != null)
            const SizedBox(height: Nova.space4),
          ?weatherTile,
        ],
      );
    }

    return Row(
      // Bottom-aligned, so the weather tile lines up with the fixture cards
      // rather than with the heading that sits above them.
      //
      // Deliberately not `stretch`: this row is built inside a ListView, where
      // the cross axis is unbounded, and stretching a child into that made the
      // strip paint outside its box and straight through the rail below it.
      // `end` needs no bounded height — every child here already has one
      // (MatchStrip is a fixed 128, the tile is intrinsic).
      crossAxisAlignment: CrossAxisAlignment.end,
      children: [
        // The weather leads. It used to trail, which put the strip's scrolling
        // cut edge directly against the tile: the half-visible fixture read as
        // a broken card rather than as "there is more, scroll". Leading it puts
        // that cut at the window's own edge, where an overflowing rail is
        // supposed to end.
        if (weatherTile != null) ...[
          weatherTile,
          const SizedBox(width: Nova.space4),
        ],
        if (matchStrip != null)
          Expanded(
            // The heading belongs to the fixtures alone. Spanning the whole row
            // put "today's matches" over the weather too, which said the
            // temperature was one of the day's fixtures.
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                SectionHeader(title: title),
                const SizedBox(height: Nova.space4),
                matchStrip,
              ],
            ),
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

String _movieMeta(VodMovie movie, [MovieDetail? detail]) {
  final year = (movie.year != null && movie.year!.isNotEmpty)
      ? movie.year!
      : (detail?.releaseDate != null && detail!.releaseDate!.length >= 4
            ? detail.releaseDate!.substring(0, 4)
            : null);
  final minutes = (detail?.durationSecs ?? 0) ~/ 60;
  final genre = detail?.genre?.split(RegExp(r'[,/|]')).first.trim();
  return [
    ?year,
    if ((movie.rating ?? 0) > 0) '★ ${movie.rating!.toStringAsFixed(1)}',
    if (genre != null && genre.isNotEmpty) genre,
    if (minutes > 0)
      '${minutes ~/ 60 > 0 ? '${minutes ~/ 60}h ' : ''}${minutes % 60}m',
  ].join('   ·   ');
}

/// The full-bleed opener: one slide of the spotlight.
///
/// The artwork fills the width, a baked scrim keeps the leading side legible
/// (see `baked_gradient.dart` for why it is baked), and the copy stands on the
/// scrim, bottom-leading. When the slide changes, the artwork cross-fades and
/// the copy rises into place — the artwork through the image's own paint alpha
/// and the copy through its text colour, so neither costs an offscreen layer.
class HomeHero extends StatelessWidget {
  const HomeHero({
    super.key,
    required this.eyebrow,
    required this.title,
    required this.meta,
    required this.playLabel,
    required this.onPlay,
    required this.infoLabel,
    required this.motion,
    this.imageUrl,
    this.logoUrl,
    this.description,
    this.progress,
    this.onInfo,
    this.reveal = 1,
    this.pager,
  });

  final String eyebrow;
  final String title;
  final String meta;
  final String playLabel;
  final VoidCallback onPlay;
  final String infoLabel;
  final bool motion;
  final String? imageUrl;
  final String? description;

  /// A channel's logo, when the hero is a live channel. It is drawn as a mark
  /// above the copy — *not* as the backdrop. A logo is a transparent PNG of
  /// unknowable aspect (see [NetworkPoster.logoMode]); stretched to fill a
  /// 1400×345 hero it is beheaded, and the one picture the channel has is the
  /// one thing the hero must not ruin.
  final String? logoUrl;

  final double? progress;
  final VoidCallback? onInfo;

  /// 0 → 1 as the slide's copy arrives.
  final double reveal;

  /// The spotlight's page dots, when there is more than one slide.
  final Widget? pager;

  @override
  Widget build(BuildContext context) {
    final size = MediaQuery.sizeOf(context);
    final height = (size.height * 0.58).clamp(360.0, 660.0);
    final hasLogo = logoUrl != null && logoUrl!.trim().isNotEmpty;
    final t = motion ? reveal.clamp(0.0, 1.0) : 1.0;
    Color ink(Color c) => c.withValues(alpha: c.a * t);

    return SizedBox(
      height: height,
      child: Stack(
        fit: StackFit.expand,
        children: [
          if (hasLogo)
            GradientFill(gradient: AppColors.heroPlate)
          else
            _HeroArt(url: imageUrl, motion: motion),
          GradientFill(
            gradient: LinearGradient(
              begin: AlignmentDirectional.centerStart,
              end: AlignmentDirectional.centerEnd,
              colors: AppColors.heroScrim.colors,
              stops: AppColors.heroScrim.stops,
            ),
          ),
          GradientFill(gradient: AppColors.heroFloor),
          if (hasLogo)
            PositionedDirectional(
              end: Nova.space7,
              top: 0,
              bottom: 0,
              child: Center(
                child: SizedBox(
                  width: math.min(360, size.width * 0.26),
                  height: math.min(220, height * 0.46),
                  child: NetworkPoster(
                    url: logoUrl,
                    title: title,
                    logoMode: true,
                    radius: Nova.radiusPanel,
                    background: AppColors.surface2.withValues(alpha: 0.6),
                  ),
                ),
              ),
            ),
          PositionedDirectional(
            start: Nova.space7,
            end: Nova.space7,
            bottom: Nova.space6,
            child: Align(
              alignment: AlignmentDirectional.bottomStart,
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 660),
                child: Transform.translate(
                  // The rise is vertical. A horizontal one would have a
                  // direction, and a direction is wrong half the time in a
                  // layout that is also mirrored.
                  offset: Offset(0, (1 - t) * 16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      _Eyebrow(label: eyebrow, reveal: t),
                      const SizedBox(height: Nova.space3),
                      Text(
                        title,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: AppText.display.copyWith(
                          fontSize: size.width < 900 ? 30 : 42,
                          fontWeight: FontWeight.w800,
                          height: 1.06,
                          color: ink(AppColors.textPrimary),
                        ),
                      ),
                      if (meta.isNotEmpty) ...[
                        const SizedBox(height: Nova.space3),
                        Text(
                          meta,
                          style: AppText.subtitle.copyWith(
                            color: ink(AppColors.textSecondary),
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ],
                      if (description != null &&
                          description!.trim().isNotEmpty) ...[
                        const SizedBox(height: Nova.space3),
                        Text(
                          description!.trim(),
                          maxLines: 3,
                          overflow: TextOverflow.ellipsis,
                          style: AppText.body.copyWith(
                            color: ink(AppColors.textSecondary),
                            fontSize: 15,
                            height: 1.55,
                          ),
                        ),
                      ],
                      if (progress != null) ...[
                        const SizedBox(height: Nova.space4),
                        SizedBox(
                          width: 280,
                          child: ProgressBar(value: progress!),
                        ),
                      ],
                      const SizedBox(height: Nova.space5),
                      Wrap(
                        spacing: Nova.space3,
                        runSpacing: Nova.space3,
                        crossAxisAlignment: WrapCrossAlignment.center,
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
          ),
          if (pager != null)
            PositionedDirectional(
              end: Nova.space7,
              bottom: Nova.space6 + 10,
              child: pager!,
            ),
        ],
      ),
    );
  }
}

/// The small capsule above the title: what kind of thing this slide is.
class _Eyebrow extends StatelessWidget {
  const _Eyebrow({required this.label, required this.reveal});

  final String label;
  final double reveal;

  @override
  Widget build(BuildContext context) {
    final accent = AppColors.primary;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: accent.withValues(alpha: 0.16 * reveal),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: accent.withValues(alpha: 0.45 * reveal)),
      ),
      child: Text(
        label.toUpperCase(),
        style: AppText.label.copyWith(
          color: AppColors.primaryBright.withValues(alpha: reveal),
          letterSpacing: 1.2,
          fontSize: 11.5,
        ),
      ),
    );
  }
}

/// The hero's artwork. When the URL changes the new picture fades in over the
/// old one through the image's own opacity — a paint alpha, not an `Opacity`
/// widget, so the cross-fade costs no offscreen layer.
class _HeroArt extends StatefulWidget {
  const _HeroArt({required this.url, required this.motion});

  final String? url;
  final bool motion;

  @override
  State<_HeroArt> createState() => _HeroArtState();
}

class _HeroArtState extends State<_HeroArt>
    with SingleTickerProviderStateMixin {
  late final AnimationController _fade = AnimationController(
    vsync: this,
    duration: Nova.hero,
    value: 1,
  )..addStatusListener(_onFade);
  String? _previous;

  void _onFade(AnimationStatus status) {
    if (status == AnimationStatus.completed && _previous != null && mounted) {
      setState(() => _previous = null);
    }
  }

  @override
  void didUpdateWidget(covariant _HeroArt old) {
    super.didUpdateWidget(old);
    if (old.url != widget.url) {
      _previous = old.url;
      if (widget.motion && !Motion.isReduced(context)) {
        _fade.forward(from: 0);
      } else {
        _fade.value = 1;
      }
    }
  }

  @override
  void dispose() {
    _fade.dispose();
    super.dispose();
  }

  ImageProvider? _provider(String? url, double width) {
    final link = url?.trim();
    if (link == null || link.isEmpty) return null;
    return ResizeImage(
      CachedNetworkImageProvider(link),
      width: width.round(),
      policy: ResizeImagePolicy.fit,
    );
  }

  @override
  Widget build(BuildContext context) {
    final width = math.min(
      1920.0,
      MediaQuery.sizeOf(context).width * MediaQuery.devicePixelRatioOf(context),
    );
    final current = _provider(widget.url, width);
    final previous = _provider(_previous, width);
    Widget image(ImageProvider provider, Animation<double>? opacity) => Image(
      image: provider,
      fit: BoxFit.cover,
      alignment: const Alignment(0.3, -0.35),
      filterQuality: FilterQuality.medium,
      opacity: opacity,
      gaplessPlayback: true,
      errorBuilder: (_, _, _) => const SizedBox.expand(),
    );
    return ColoredBox(
      color: AppColors.surface1,
      child: Stack(
        fit: StackFit.expand,
        children: [
          if (previous != null && _fade.isAnimating) image(previous, null),
          if (current != null) image(current, _fade),
        ],
      ),
    );
  }
}

/// The spotlight: up to a handful of heroes, one at a time.
///
/// It advances on its own every few seconds while the pointer is not over it
/// and motion is allowed — a timer, not a ticker, so an idle page repaints
/// once per slide and not sixty times a second — and the dots take it anywhere
/// directly.
class HeroCarousel extends StatefulWidget {
  const HeroCarousel({
    super.key,
    required this.count,
    required this.builder,
    required this.motion,
  });

  final int count;
  final bool motion;
  final Widget Function(
    BuildContext context,
    int index,
    double reveal,
    Widget? pager,
  )
  builder;

  @override
  State<HeroCarousel> createState() => _HeroCarouselState();
}

class _HeroCarouselState extends State<HeroCarousel>
    with SingleTickerProviderStateMixin {
  static const _interval = Duration(seconds: 9);

  late final AnimationController _reveal = AnimationController(
    vsync: this,
    duration: Nova.panel,
    value: 1,
  )..addListener(() => setState(() {}));
  Timer? _timer;
  int _index = 0;
  bool _hovered = false;

  @override
  void initState() {
    super.initState();
    _schedule();
  }

  @override
  void didUpdateWidget(covariant HeroCarousel old) {
    super.didUpdateWidget(old);
    if (_index >= widget.count) _index = 0;
    if (old.count != widget.count || old.motion != widget.motion) _schedule();
  }

  void _schedule() {
    _timer?.cancel();
    if (widget.count < 2 || !widget.motion) return;
    _timer = Timer.periodic(_interval, (_) {
      if (!mounted || _hovered || Motion.isReduced(context)) return;
      _go(_index + 1);
    });
  }

  void _go(int index) {
    if (widget.count == 0) return;
    setState(() => _index = index % widget.count);
    if (widget.motion && !Motion.isReduced(context)) {
      _reveal.forward(from: 0);
    }
  }

  @override
  void dispose() {
    _timer?.cancel();
    _reveal.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (widget.count == 0) return const SizedBox.shrink();
    final pager = widget.count < 2
        ? null
        : _PagerDots(count: widget.count, index: _index, onSelect: _go);
    return MouseRegion(
      onEnter: (_) => _hovered = true,
      onExit: (_) => _hovered = false,
      child: widget.builder(
        context,
        _index,
        Curves.easeOutCubic.transform(_reveal.value),
        pager,
      ),
    );
  }
}

class _PagerDots extends StatelessWidget {
  const _PagerDots({
    required this.count,
    required this.index,
    required this.onSelect,
  });

  final int count;
  final int index;
  final ValueChanged<int> onSelect;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        for (var i = 0; i < count; i++)
          Semantics(
            button: true,
            selected: i == index,
            label: '${i + 1} / $count',
            child: MouseRegion(
              cursor: SystemMouseCursors.click,
              child: GestureDetector(
                onTap: () => onSelect(i),
                child: Padding(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 3,
                    vertical: 10,
                  ),
                  child: AnimatedContainer(
                    duration: Motion.duration(context, Nova.panel),
                    curve: Ease.enter,
                    width: i == index ? 26 : 8,
                    height: 8,
                    decoration: BoxDecoration(
                      color: i == index
                          ? AppColors.primary
                          : AppColors.textPrimary.withValues(alpha: 0.28),
                      borderRadius: BorderRadius.circular(4),
                    ),
                  ),
                ),
              ),
            ),
          ),
      ],
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
  const _LiveCard({required this.channel, required this.channels});

  final LiveChannel channel;
  final List<LiveChannel> channels;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(stringsProvider);

    return NovaCard(
      padding: const EdgeInsets.all(Nova.space3),
      onTap: () => ref
          .read(playbackProvider.notifier)
          .playLive(channel, channels: channels),
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
      badge: (movie.rating ?? 0) > 0
          ? RatingBadge(rating: movie.rating!)
          : null,
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
