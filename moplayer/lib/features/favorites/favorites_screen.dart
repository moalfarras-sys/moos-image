import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/routes.dart';
import '../../core/theme/app_typography.dart';
import '../../core/theme/nova.dart';
import '../../models/library_items.dart';
import '../../models/live_channel.dart';
import '../../models/media_kind.dart';
import '../../models/series.dart';
import '../../models/vod_movie.dart';
import '../../providers/library_providers.dart';
import '../../providers/playback_providers.dart';
import '../../providers/system_providers.dart';
import '../../widgets/media_card.dart';
import '../../widgets/media_rail.dart';
import '../../widgets/state_views.dart';
import '../../widgets/tiles.dart';

/// Everything the user kept, grouped the way they think about it: channels,
/// films, shows.
///
/// A favourite carries the payload it was made from, so a row can be played
/// without going back to the panel for it — which is what makes this screen
/// work when the provider is down.
class FavoritesScreen extends ConsumerWidget {
  const FavoritesScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(stringsProvider);
    final favorites = ref.watch(favoritesProvider);

    final live = favorites.where((f) => f.kind == MediaKind.live).toList();
    final movies = favorites.where((f) => f.kind == MediaKind.movie).toList();
    final series = favorites.where((f) => f.kind == MediaKind.series).toList();

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
          SectionHeader(title: s.favorites),
          const SizedBox(height: Nova.space5),
          Expanded(
            child: favorites.isEmpty
                ? EmptyView(
                    message: s.emptyFavorites,
                    icon: Icons.favorite_border_rounded,
                  )
                : ListView(
                    padding: const EdgeInsets.only(bottom: Nova.space6),
                    children: [
                      if (live.isNotEmpty) _ChannelSection(items: live),
                      if (movies.isNotEmpty)
                        _PosterSection(title: s.movies, items: movies),
                      if (series.isNotEmpty)
                        _PosterSection(title: s.series, items: series),
                    ],
                  ),
          ),
        ],
      ),
    );
  }
}

/// Favourited channels, as rows.
///
/// Not poster cards: a channel is found by reading its name, and the tile is the
/// same one the Live section uses — a favourite should not look like a different
/// kind of thing to the channel it was made from.
class _ChannelSection extends ConsumerWidget {
  const _ChannelSection({required this.items});

  final List<FavoriteItem> items;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(stringsProvider);
    final actions = ref.read(libraryActionsProvider);
    final now = ref.watch(playbackProvider);

    return Padding(
      padding: const EdgeInsets.only(bottom: Nova.space6),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _SectionTitle(title: s.channels, count: items.length),
          const SizedBox(height: Nova.space3),
          for (final item in items)
            ChannelTile(
              name: item.title,
              logoUrl: item.imageUrl,
              selected:
                  now != null &&
                  now.kind == MediaKind.live &&
                  now.refId == item.refId,
              isFavorite: true,
              onToggleFavorite: () =>
                  actions.removeFavorite(item.kind, item.refId),
              onTap: () => ref
                  .read(playbackProvider.notifier)
                  .playLive(LiveChannel.fromPayload(item.payload)),
            ),
        ],
      ),
    );
  }
}

/// Favourited films and shows, as a poster grid that reflows to the window.
class _PosterSection extends ConsumerWidget {
  const _PosterSection({required this.title, required this.items});

  final String title;
  final List<FavoriteItem> items;

  void _open(BuildContext context, WidgetRef ref, FavoriteItem item) {
    switch (item.kind) {
      case MediaKind.movie:
        ref
            .read(playbackProvider.notifier)
            .playMovie(VodMovie.fromPayload(item.payload));
      case MediaKind.series:
        // A series is a folder, not a stream: it opens, it does not play.
        context.push(
          Routes.seriesDetail,
          extra: SeriesItem.fromPayload(item.payload),
        );
      case MediaKind.live:
      case MediaKind.episode:
        // Neither reaches this grid: channels have their own section, and an
        // episode is favourited as its series. Opening one off the wrong payload
        // would build the wrong URL, so this does nothing rather than something
        // wrong.
        break;
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final actions = ref.read(libraryActionsProvider);

    return Padding(
      padding: const EdgeInsets.only(bottom: Nova.space6),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _SectionTitle(title: title, count: items.length),
          const SizedBox(height: Nova.space3),
          LayoutBuilder(
            builder: (context, constraints) {
              const spacing = Nova.space4;
              const maxItemWidth = 180.0;
              final columns = math.max(
                2,
                (constraints.maxWidth / (maxItemWidth + spacing)).floor(),
              );
              final itemWidth =
                  (constraints.maxWidth - spacing * (columns - 1)) / columns;
              // The card is artwork plus two lines of type; the grid has to be
              // told about those lines or the last one clips.
              final extent = itemWidth * 1.5 + 48;

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
                itemCount: items.length,
                itemBuilder: (context, i) {
                  final item = items[i];

                  return PosterCard(
                    title: item.title,
                    subtitle: item.subtitle,
                    imageUrl: item.imageUrl,
                    isFavorite: true,
                    onToggleFavorite: () =>
                        actions.removeFavorite(item.kind, item.refId),
                    onTap: () => _open(context, ref, item),
                    onPlay: item.kind == MediaKind.movie
                        ? () => _open(context, ref, item)
                        : null,
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

class _SectionTitle extends StatelessWidget {
  const _SectionTitle({required this.title, required this.count});

  final String title;
  final int count;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Text(title, style: AppText.section),
        const SizedBox(width: Nova.space3),
        Text('$count', style: AppText.caption, textDirection: TextDirection.ltr),
      ],
    );
  }
}
