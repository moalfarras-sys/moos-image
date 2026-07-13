import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/routes.dart';
import '../../core/theme/nova.dart';
import '../../models/media_kind.dart';
import '../../providers/core_providers.dart';
import '../../providers/library_providers.dart';
import '../../providers/system_providers.dart';
import '../../widgets/buttons.dart';
import '../../widgets/state_views.dart';
import 'favorites_hero.dart';
import 'favorites_shelves.dart';

/// Everything the user kept — a shelf, not a report.
///
/// The old screen was a `ListView` of sections with a grid inside each one, and
/// it read like an inventory. This one leads with the thing they kept *last*, at
/// the size of a poster on a wall, and puts the rest underneath it in the same
/// cards the rest of the app is built from. Favourites is the one screen where
/// every single item is something the user chose on purpose, and it should look
/// like it.
///
/// A favourite carries the payload it was made from, so a card here can be
/// played without going back to the panel for it — which is what makes this
/// screen work when the provider is down.
class FavoritesScreen extends ConsumerWidget {
  const FavoritesScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(stringsProvider);
    final favorites = ref.watch(favoritesProvider);
    final compact = ref.watch(settingsProvider).compactGrids;

    if (favorites.isEmpty) {
      return EmptyView(
        title: s.favorites,
        message: s.emptyFavorites,
        icon: Icons.favorite_border_rounded,
        // An empty state with no way out is a dead end with better type.
        action: EmberButton(
          label: s.emptyFavoritesAction,
          icon: Icons.explore_outlined,
          onPressed: () => context.go(Routes.home),
        ),
      );
    }

    // The repository hands these back newest first, which is the only order a
    // hero can honestly be picked from: it is *the last thing you kept*, not a
    // recommendation the app invented.
    final hero = favorites.first;
    final live = favorites.where((f) => f.kind == MediaKind.live).toList();
    final movies = favorites.where((f) => f.kind == MediaKind.movie).toList();
    final series = favorites.where((f) => f.kind == MediaKind.series).toList();

    return ListView(
      // The dock floats over the foot of the window and the shell hands this
      // screen its height. A list that ignores it hides its own last row under
      // the glass.
      padding: EdgeInsets.only(
        bottom: MediaQuery.paddingOf(context).bottom + Nova.space5,
      ),
      children: [
        // Full bleed: the hero runs to the edges of the window, and only the
        // shelves under it take the page's gutter.
        FavoriteHero(item: hero),
        const SizedBox(height: Nova.space6),
        Padding(
          padding: const EdgeInsetsDirectional.symmetric(
            horizontal: Nova.space6,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (live.isNotEmpty) ...[
                ChannelShelf(items: live),
                const SizedBox(height: Nova.space6),
              ],
              if (movies.isNotEmpty) ...[
                PosterShelf(
                  title: s.movies,
                  subtitle: s.moviesCount(movies.length),
                  items: movies,
                  compact: compact,
                ),
                const SizedBox(height: Nova.space6),
              ],
              if (series.isNotEmpty)
                PosterShelf(
                  title: s.series,
                  subtitle: s.seriesCount(series.length),
                  items: series,
                  compact: compact,
                ),
            ],
          ),
        ),
      ],
    );
  }
}
