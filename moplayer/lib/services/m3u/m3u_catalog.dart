import 'dart:io';
import 'dart:typed_data';

import '../../core/config/app_config.dart';
import '../../core/error/failures.dart';
import '../catalog/catalog_files.dart';
import '../catalog/http_fetch.dart';
import 'm3u_parser.dart';

/// What a background isolate needs to load one playlist. Plain data only.
class M3uLibraryJob {
  const M3uLibraryJob({
    required this.url,
    required this.cacheRoot,
    required this.namespace,
  });

  final String url;
  final String cacheRoot;
  final String namespace;

  static const cacheFile = 'playlist.m3u';

  bool get isRemote => url.startsWith('http://') || url.startsWith('https://');
  bool get isLocalFile => url.startsWith('file://') || url.startsWith('/');
}

/// The playlist as the cache last saw it, or null. Runs inside an isolate.
///
/// The cached copy is the playlist's own bytes, re-parsed rather than stored
/// parsed: parsing is a background isolate's second or two, and a parsed copy
/// re-encoded as JSON is exactly the 146 MB document that used to be decoded on
/// the UI isolate at every start.
({M3uLibrary library, DateTime written})? loadCachedM3uLibrary(
  M3uLibraryJob job,
) {
  final files = CatalogFiles(job.cacheRoot);
  final bytes = files.read(job.namespace, M3uLibraryJob.cacheFile);
  if (bytes == null) return null;
  final content = M3uParser.decode(bytes);
  if (!M3uParser.looksLikePlaylist(content)) return null;
  return (
    library: M3uParser.parseLibrary(content),
    written:
        files.modified(job.namespace, M3uLibraryJob.cacheFile) ??
        DateTime.now(),
  );
}

/// Downloads (or reads) the playlist, caches it, and sorts it. Runs inside an
/// isolate.
Future<M3uLibrary> fetchM3uLibrary(M3uLibraryJob job) async {
  final Uint8List bytes;
  if (job.isLocalFile) {
    try {
      bytes = File(Uri.parse(job.url).toFilePath()).readAsBytesSync();
    } on Object {
      throw Failure.parse('Could not read the playlist file.');
    }
  } else if (job.isRemote) {
    bytes = await fetchBytes(
      Uri.parse(job.url),
      headers: const {'User-Agent': AppConfig.apiUserAgent},
      timeout: const Duration(minutes: 4),
    );
  } else {
    throw Failure.parse('That is not a playlist address.');
  }

  final content = M3uParser.decode(bytes);
  if (!M3uParser.looksLikePlaylist(content)) {
    throw Failure.parse('That URL did not return a valid M3U playlist.');
  }
  final library = M3uParser.parseLibrary(content);
  if (library.totalEntries == 0) {
    throw Failure.parse('No channels found in that playlist.');
  }
  if (job.isRemote) {
    CatalogFiles(job.cacheRoot).write(
      job.namespace,
      M3uLibraryJob.cacheFile,
      bytes,
    );
  }
  return library;
}

/// Parses a playlist already in memory — the bundled demo, which only the UI
/// isolate's asset bundle can read. Runs inside an isolate.
M3uLibrary parseM3uText(String content) {
  if (!M3uParser.looksLikePlaylist(content)) {
    throw Failure.parse('That URL did not return a valid M3U playlist.');
  }
  return M3uParser.parseLibrary(content);
}
