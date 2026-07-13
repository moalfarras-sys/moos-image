import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../features/auth/login_screen.dart';
import '../features/favorites/favorites_screen.dart';
import '../features/home/home_screen.dart';
import '../features/live/live_screen.dart';
import '../features/movies/movie_detail_screen.dart';
import '../features/movies/movies_screen.dart';
import '../features/search/search_screen.dart';
import '../features/series/series_detail_screen.dart';
import '../features/series/series_screen.dart';
import '../features/settings/settings_screen.dart';
import '../models/series.dart';
import '../models/vod_movie.dart';
import '../providers/core_providers.dart';
import 'launch_args.dart';
import 'main_shell.dart';
import 'routes.dart';

final routerProvider = Provider<GoRouter>((ref) {
  return GoRouter(
    // `moplayer --section live` opens on Live TV. The redirect below still
    // bounces it to the login screen if there is no source yet.
    initialLocation: ref.read(launchArgsProvider).initialRoute,
    redirect: (context, state) {
      final loggedIn = ref.read(isLoggedInProvider);
      final onLogin = state.matchedLocation == Routes.login;

      // "Logged in" means: there is a source to play. There is no account.
      if (!loggedIn && !onLogin) return Routes.login;
      // `?add=1` is how Settings adds a second source without being bounced home.
      if (loggedIn && onLogin && state.uri.queryParameters['add'] != '1') {
        return Routes.home;
      }
      return null;
    },
    routes: [
      GoRoute(
        path: Routes.login,
        builder: (context, state) =>
            LoginScreen(isAdditional: state.uri.queryParameters['add'] == '1'),
      ),

      // One shell, one IndexedStack: switching sections on a desktop must not
      // throw away a scroll position or re-fetch a category the user just left.
      ShellRoute(
        builder: (context, state, child) => MainShell(child: child),
        routes: [
          GoRoute(
            path: Routes.home,
            pageBuilder: (c, s) => _fade(s, const HomeScreen()),
          ),
          GoRoute(
            path: Routes.live,
            pageBuilder: (c, s) => _fade(s, const LiveScreen()),
          ),
          GoRoute(
            path: Routes.movies,
            pageBuilder: (c, s) => _fade(s, const MoviesScreen()),
          ),
          GoRoute(
            path: Routes.series,
            pageBuilder: (c, s) => _fade(s, const SeriesScreen()),
          ),
          GoRoute(
            path: Routes.search,
            pageBuilder: (c, s) => _fade(s, const SearchScreen()),
          ),
          GoRoute(
            path: Routes.favorites,
            pageBuilder: (c, s) => _fade(s, const FavoritesScreen()),
          ),
          GoRoute(
            path: Routes.settings,
            pageBuilder: (c, s) => _fade(s, const SettingsScreen()),
          ),
          GoRoute(
            path: Routes.movieDetail,
            pageBuilder: (c, s) =>
                _fade(s, MovieDetailScreen(movie: s.extra! as VodMovie)),
          ),
          GoRoute(
            path: Routes.seriesDetail,
            pageBuilder: (c, s) =>
                _fade(s, SeriesDetailScreen(series: s.extra! as SeriesItem)),
          ),
        ],
      ),
    ],
  );
});

/// A cross-fade, not a slide. A slide has a direction, and a direction is wrong
/// half the time in an app that is also laid out right-to-left.
CustomTransitionPage<void> _fade(GoRouterState state, Widget child) {
  return CustomTransitionPage<void>(
    key: state.pageKey,
    child: child,
    transitionDuration: const Duration(milliseconds: 180),
    transitionsBuilder: (context, animation, secondary, child) =>
        FadeTransition(opacity: animation, child: child),
  );
}
