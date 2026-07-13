import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/routes.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_typography.dart';
import '../../core/theme/nova.dart';
import '../../core/utils/debouncer.dart';
import '../../models/live_channel.dart';
import '../../models/series.dart';
import '../../models/vod_movie.dart';
import '../../providers/content_providers.dart';
import '../../providers/playback_providers.dart';
import '../../providers/system_providers.dart';
import '../../widgets/media_card.dart';
import '../../widgets/media_rail.dart';
import '../../widgets/state_views.dart';

/// One field, three buckets.
///
/// The field is the screen: it takes focus the moment the section opens (Ctrl+F
/// lands here), so a desktop user can type before the page has finished
/// painting.
class SearchScreen extends ConsumerStatefulWidget {
  const SearchScreen({super.key});

  @override
  ConsumerState<SearchScreen> createState() => _SearchScreenState();
}

class _SearchScreenState extends ConsumerState<SearchScreen> {
  final TextEditingController _controller = TextEditingController();
  final Debouncer _debouncer = Debouncer();

  @override
  void initState() {
    super.initState();
    // The query outlives the screen — coming back from a movie's detail page
    // must not hand the user an empty field and an empty grid.
    _controller.text = ref.read(searchQueryProvider);
  }

  @override
  void dispose() {
    _debouncer.dispose();
    _controller.dispose();
    super.dispose();
  }

  void _submit(String value) {
    if (!mounted) return;
    ref.read(searchQueryProvider.notifier).state = value.trim();
  }

  void _clear() {
    _controller.clear();
    _submit('');
  }

  @override
  Widget build(BuildContext context) {
    final s = ref.watch(stringsProvider);
    final query = ref.watch(searchQueryProvider).trim();
    final results = ref.watch(searchResultsProvider);

    return Padding(
      padding: const EdgeInsets.fromLTRB(
        Nova.space6,
        Nova.space6,
        Nova.space6,
        0,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          SectionHeader(title: s.search),
          const SizedBox(height: Nova.space4),
          TextField(
            controller: _controller,
            autofocus: true,
            textInputAction: TextInputAction.search,
            style: AppText.title.copyWith(fontWeight: FontWeight.w500),
            cursorColor: AppColors.primary,
            onChanged: (value) => _debouncer.run(() => _submit(value)),
            onSubmitted: _submit,
            decoration: InputDecoration(
              hintText: s.searchPlaceholder,
              hintStyle: AppText.subtitle.copyWith(color: AppColors.textMuted),
              prefixIcon: const Icon(Icons.search_rounded, size: 22),
              suffixIcon: ValueListenableBuilder<TextEditingValue>(
                valueListenable: _controller,
                builder: (context, value, _) {
                  if (value.text.isEmpty) return const SizedBox.shrink();
                  return IconButton(
                    icon: const Icon(Icons.close_rounded, size: 18),
                    color: AppColors.textMuted,
                    tooltip: s.close,
                    onPressed: _clear,
                  );
                },
              ),
              contentPadding: const EdgeInsets.symmetric(
                horizontal: Nova.space4,
                vertical: Nova.space4,
              ),
            ),
          ),
          const SizedBox(height: Nova.space5),
          Expanded(
            child: query.length < 2
                ? EmptyView(message: s.searchPrompt, icon: Icons.search_rounded)
                : results.when(
                    loading: () => const LoadingView(),
                    error: (error, _) => ErrorView(
                      strings: s,
                      error: error,
                      onRetry: () => ref.invalidate(searchResultsProvider),
                    ),
                    data: (data) => _Results(results: data, query: query),
                  ),
          ),
        ],
      ),
    );
  }
}

class _Results extends ConsumerWidget {
  const _Results({required this.results, required this.query});

  final SearchResults results;
  final String query;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(stringsProvider);
    final playback = ref.read(playbackProvider.notifier);

    final live = results.live;
    final movies = results.movies;
    final series = results.series;

    if (live.isEmpty && movies.isEmpty && series.isEmpty) {
      return EmptyView(
        message: s.noResults(query),
        icon: Icons.search_off_rounded,
      );
    }

    return ListView(
      padding: const EdgeInsets.only(bottom: Nova.space6),
      children: [
        if (live.isNotEmpty)
          _ResultSection(
            title: s.live,
            count: live.length,
            // A channel logo is a wide, transparent PNG; cropping it to a
            // poster's 2:3 would cut half the mark away.
            aspectRatio: 16 / 9,
            maxItemWidth: 240,
            itemCount: live.length,
            itemBuilder: (context, i) {
              final LiveChannel channel = live[i];
              return PosterCard(
                title: channel.name,
                imageUrl: channel.logo,
                aspectRatio: 16 / 9,
                badge: LiveBadge(label: s.onAir),
                onTap: () => playback.playLive(channel),
                onPlay: () => playback.playLive(channel),
              );
            },
          ),
        if (movies.isNotEmpty)
          _ResultSection(
            title: s.movies,
            count: movies.length,
            aspectRatio: 2 / 3,
            maxItemWidth: 180,
            itemCount: movies.length,
            itemBuilder: (context, i) {
              final VodMovie movie = movies[i];
              return PosterCard(
                title: movie.name,
                subtitle: movie.year,
                imageUrl: movie.poster,
                badge: movie.rating != null
                    ? RatingBadge(rating: movie.rating!)
                    : null,
                onTap: () => context.push(Routes.movieDetail, extra: movie),
                onPlay: () => playback.playMovie(movie),
              );
            },
          ),
        if (series.isNotEmpty)
          _ResultSection(
            title: s.series,
            count: series.length,
            aspectRatio: 2 / 3,
            maxItemWidth: 180,
            itemCount: series.length,
            itemBuilder: (context, i) {
              final SeriesItem item = series[i];
              return PosterCard(
                title: item.name,
                imageUrl: item.cover,
                badge: item.rating != null
                    ? RatingBadge(rating: item.rating!)
                    : null,
                onTap: () => context.push(Routes.seriesDetail, extra: item),
              );
            },
          ),
      ],
    );
  }
}

/// A labelled block of poster cards that reflows to the window width.
class _ResultSection extends StatelessWidget {
  const _ResultSection({
    required this.title,
    required this.count,
    required this.itemCount,
    required this.itemBuilder,
    required this.aspectRatio,
    required this.maxItemWidth,
  });

  final String title;
  final int count;
  final int itemCount;
  final Widget Function(BuildContext, int) itemBuilder;
  final double aspectRatio;
  final double maxItemWidth;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: Nova.space6),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(title, style: AppText.section),
              const SizedBox(width: Nova.space3),
              Text('$count', style: AppText.caption),
            ],
          ),
          const SizedBox(height: Nova.space3),
          LayoutBuilder(
            builder: (context, constraints) {
              const spacing = Nova.space4;
              final columns = math.max(
                2,
                (constraints.maxWidth / (maxItemWidth + spacing)).floor(),
              );
              final itemWidth =
                  (constraints.maxWidth - spacing * (columns - 1)) / columns;
              // The card is artwork plus two lines of type; the grid has to be
              // told about those lines or the last one clips.
              final extent = itemWidth / aspectRatio + 48;

              return GridView.builder(
                padding: EdgeInsets.zero,
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                  crossAxisCount: columns,
                  mainAxisSpacing: spacing,
                  crossAxisSpacing: spacing,
                  mainAxisExtent: extent,
                ),
                itemCount: itemCount,
                itemBuilder: itemBuilder,
              );
            },
          ),
        ],
      ),
    );
  }
}
