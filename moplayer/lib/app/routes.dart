/// Every route in the app, in one place.
///
/// The player is **not** a route. On a phone it was: you opened a channel, the
/// player took the screen, and leaving it stopped playback. On a desktop that is
/// wrong — the user expects to browse while a channel keeps running, exactly as
/// they would in a browser tab. So playback is app-scoped state
/// (`playbackProvider`) rendered by the shell, and "the player" is a *mode* of
/// the shell rather than a place you navigate to.
class Routes {
  const Routes._();

  static const String login = '/login';
  static const String home = '/home';
  static const String live = '/live';
  static const String movies = '/movies';
  static const String series = '/series';
  static const String search = '/search';
  static const String favorites = '/favorites';
  static const String settings = '/settings';

  static const String movieDetail = '/movie';
  static const String seriesDetail = '/series-detail';
}
