import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/routes.dart';
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

/// The geometry of the poster wall. The same numbers the Movies and Series
/// screens use, because a favourite must not be a *different size* of the thing
/// it was made from — the eye catches that across two screens long before it can
/// name it.
const double _tileWidth = 180;
const double _tileWidthCompact = 150;
const double _tileRatio = 0.54;
const double _tileRatioCompact = 0.53;

/// Favourited channels, as a shelf.
///
/// A channel keeps the 16:9 card the rest of the app gives it and keeps its
/// name under it — a logo alone is not a channel list, it is a quiz. The one
/// that is currently in the player says so on its own artwork, which is the only
/// mark that survives a shelf being scrolled past at speed.
class ChannelShelf extends ConsumerWidget {
  const ChannelShelf({super.key, required this.items});

  final List<FavoriteItem> items;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(stringsProvider);
    final actions = ref.read(libraryActionsProvider);
    final now = ref.watch(playbackProvider);

    const width = 260.0;

    return MediaRail(
      title: s.channels,
      subtitle: s.liveChannelsAvailable(items.length),
      itemCount: items.length,
      itemWidth: width,
      // The artwork (16:9 of 260) plus the gap and the two lines of type under
      // it. A rail is a fixed-height box and a card is a column; the box has to
      // be told about the type or the last line is cut off.
      height: width * 9 / 16 + Nova.space3 + 42,
      itemBuilder: (context, i) {
        final item = items[i];
        final playing =
            now != null &&
            now.kind == MediaKind.live &&
            now.refId == item.refId;

        return LandscapeCard(
          title: item.title,
          subtitle: item.subtitle,
          imageUrl: item.imageUrl,
          width: width,
          // A channel logo is a transparent PNG of arbitrary aspect: letterbox
          // it, or half of it is gone.
          logoMode: true,
          badge: LiveBadge(label: s.onAir),
          caption: playing ? s.nowPlaying : null,
          isFavorite: true,
          onToggleFavorite: () => actions.removeFavorite(item.kind, item.refId),
          onTap: () => ref
              .read(playbackProvider.notifier)
              .playLive(LiveChannel.fromPayload(item.payload)),
        );
      },
    );
  }
}

/// Favourited films or shows, as a poster wall that reflows to the window.
class PosterShelf extends ConsumerWidget {
  const PosterShelf({
    super.key,
    required this.title,
    required this.subtitle,
    required this.items,
    required this.compact,
  });

  final String title;

  /// The count, in words — never a sentence.
  final String subtitle;

  final List<FavoriteItem> items;

  /// The user's own "compact grids" setting: smaller cards, more of them.
  final bool compact;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final actions = ref.read(libraryActionsProvider);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        SectionHeader(title: title, subtitle: subtitle, dense: true),
        const SizedBox(height: Nova.space4),
        GridView.builder(
          padding: EdgeInsets.zero,
          shrinkWrap: true,
          // The page owns the scroll. A grid that scrolled inside a scrolling
          // page would trap the wheel over the only part of the screen the user
          // is actually looking at.
          physics: const NeverScrollableScrollPhysics(),
          gridDelegate: SliverGridDelegateWithMaxCrossAxisExtent(
            maxCrossAxisExtent: compact ? _tileWidthCompact : _tileWidth,
            childAspectRatio: compact ? _tileRatioCompact : _tileRatio,
            crossAxisSpacing: Nova.space4,
            mainAxisSpacing: Nova.space5,
          ),
          itemCount: items.length,
          itemBuilder: (context, i) {
            final item = items[i];
            final isMovie = item.kind == MediaKind.movie;

            return PosterCard(
              title: item.title,
              subtitle: item.subtitle,
              imageUrl: item.imageUrl,
              // The panel returns 0 for "we do not know", and a wall of
              // zero-star films is a lie about the library — [PosterCard] draws
              // nothing at 0, which is why this may pass it straight through.
              rating: _rating(item),
              isFavorite: true,
              onToggleFavorite: () =>
                  actions.removeFavorite(item.kind, item.refId),
              onTap: () => _open(context, ref, item),
              // A film plays from its card. A series does not: it is a folder,
              // and it opens.
              onPlay: isMovie ? () => _open(context, ref, item) : null,
            );
          },
        ),
      ],
    );
  }

  double? _rating(FavoriteItem item) => switch (item.kind) {
    MediaKind.movie => VodMovie.fromPayload(item.payload).rating,
    MediaKind.series => SeriesItem.fromPayload(item.payload).rating,
    MediaKind.live || MediaKind.episode => null,
  };

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
        // Neither reaches this wall: channels have their own shelf, and an
        // episode is favourited as its series. Opening one off the wrong payload
        // would build the wrong URL, so this does nothing rather than something
        // wrong.
        break;
    }
  }
}
