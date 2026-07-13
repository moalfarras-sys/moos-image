import 'dart:io';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/playlist_config.dart';
import '../services/source/source_link.dart';
import 'routes.dart';

/// What the desktop asked for when it launched us.
///
/// Two entry points in `org.moos.moplayer.desktop` depend on this file:
///
///   * `Actions=Live;Movies;Series` — the right-click jump list on the MoPlayer
///     icon, which runs `moplayer --section live`.
///   * `MimeType=application/x-mpegurl;…` and `Exec=moplayer %U` — opening a
///     `.m3u` from Dolphin, which runs `moplayer /home/mo/tv.m3u`.
///
/// Neither is decoration. MoOS's own `AGENTS.md` records what happens when a
/// launcher promises a route nobody implemented: eleven buttons once shipped
/// that popped an error and did nothing. A `.desktop` entry is a contract, and
/// this is the half of it that lives in the app.
class LaunchArgs {
  const LaunchArgs({this.section, this.playlist, this.playUrl});

  /// The route to open on, from `--section`.
  final String? section;

  /// A playlist handed to us by the file manager.
  final PlaylistConfig? playlist;

  /// A single stream to play straight away: `moplayer https://…/master.m3u8`.
  ///
  /// This is what every desktop video player does with a URL on its command
  /// line, and it is the seam the rest of MoOS drives MoPlayer through — a
  /// `moos://` route, a Mo AI action, or a script can hand it a stream without
  /// knowing anything about Xtream.
  final String? playUrl;

  static const LaunchArgs none = LaunchArgs();

  String get initialRoute => section ?? Routes.home;

  static LaunchArgs parse(List<String> args) {
    String? section;
    PlaylistConfig? playlist;
    String? playUrl;

    for (var i = 0; i < args.length; i++) {
      final arg = args[i];

      if (arg == '--section' && i + 1 < args.length) {
        section = _route(args[++i]);
        continue;
      }
      if (arg.startsWith('--section=')) {
        section = _route(arg.substring('--section='.length));
        continue;
      }
      // A stream is checked first. `.m3u8` is an HLS manifest — one stream — and
      // SourceLink would happily import it as a playlist containing itself.
      if (_looksLikeStream(arg)) {
        playUrl = arg;
        continue;
      }
      final source = SourceLink.parse(arg);
      if (source != null) {
        playlist = source;
      }
    }

    return LaunchArgs(section: section, playlist: playlist, playUrl: playUrl);
  }

  /// A playable stream, as opposed to a playlist of them. `.m3u8` is HLS and is
  /// deliberately *not* here — it is caught by [_looksLikePlaylist] first, which
  /// is wrong for a bare HLS manifest, so the order of the two checks in [parse]
  /// matters: `.m3u8` means HLS-stream, `.m3u` means playlist-of-streams.
  static bool _looksLikeStream(String arg) {
    if (arg.startsWith('-')) return false;
    final path = arg.split('?').first.toLowerCase();
    const playable = ['.m3u8', '.ts', '.mp4', '.mkv', '.avi', '.mov', '.webm'];
    if (!playable.any(path.endsWith)) return false;
    return arg.startsWith('http') || File(arg).existsSync();
  }

  static String? _route(String value) => switch (value.toLowerCase()) {
    'live' => Routes.live,
    'movies' => Routes.movies,
    'series' => Routes.series,
    'search' => Routes.search,
    'favorites' => Routes.favorites,
    'settings' => Routes.settings,
    'home' => Routes.home,
    // An unknown section is not worth failing a launch over — the app opens on
    // the home screen, which is what the user would have got anyway.
    _ => null,
  };

  // What a playlist *is* now lives in SourceLink, which the login screen uses
  // too. It also normalises a bare relative path ("./tv.m3u") to an absolute
  // file URI — a path relative to the directory the app happened to be launched
  // from stops resolving the moment it is launched from Kickoff, and the config
  // is persisted.
}

/// Overridden in `main()`. Read by the router for its initial location.
final launchArgsProvider = Provider<LaunchArgs>((ref) => LaunchArgs.none);
