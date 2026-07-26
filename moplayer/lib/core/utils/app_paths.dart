import 'dart:io';

/// Where MoPlayer keeps its own files on disk.
///
/// `Hive.initFlutter()` — and anything else built on path_provider — would put
/// them under `getApplicationDocumentsDirectory()`, which on Linux is **the
/// user's Documents folder**, localised: the first run of this app created
/// `~/Dokumente/moplayer/`. That is not a bug in Hive; it is path_provider
/// faithfully answering a question that only makes sense on iOS. On a
/// freedesktop system, application state belongs in `$XDG_DATA_HOME`, and a
/// video player has no business writing a lock file into a folder the user
/// backs up and syncs.
///
/// This lives here, rather than staying private to `bootstrap()`, because it is
/// now the answer for *every* store the app owns — the cache, the credentials
/// file and the video-path probe all resolve through it, so there is one place
/// to be right instead of three places to drift.
String appDataDir() {
  final xdg = Platform.environment['XDG_DATA_HOME'];
  final base = (xdg != null && xdg.isNotEmpty)
      ? xdg
      : '${Platform.environment['HOME'] ?? '.'}/.local/share';
  // Deliberately does not create the directory: `bootstrap()` must survive a
  // read-only or missing home, and its callers own their own fallbacks.
  return Directory('$base/moplayer').path;
}
