import 'dart:convert';
import 'dart:typed_data';

import '../../core/config/app_config.dart';
import '../../core/error/failures.dart';
import '../../models/category.dart';
import '../../models/live_channel.dart';
import '../../models/series.dart';
import '../../models/vod_movie.dart';
import '../catalog/catalog_files.dart';
import '../catalog/http_fetch.dart';
import '../catalog/shelf.dart';

/// Which part of a catalogue a job is about.
enum CatalogSection { live, movies, series }

/// Everything a background isolate needs to fetch or reload one section of an
/// Xtream catalogue. Plain strings only — this object is copied into the
/// isolate.
class XtreamShelfJob {
  const XtreamShelfJob({
    required this.server,
    required this.username,
    required this.password,
    required this.cacheRoot,
    required this.namespace,
    required this.section,
  });

  final String server;
  final String username;
  final String password;
  final String cacheRoot;
  final String namespace;
  final CatalogSection section;

  String get _streamsAction => switch (section) {
    CatalogSection.live => 'get_live_streams',
    CatalogSection.movies => 'get_vod_streams',
    CatalogSection.series => 'get_series',
  };

  String get _categoriesAction => switch (section) {
    CatalogSection.live => 'get_live_categories',
    CatalogSection.movies => 'get_vod_categories',
    CatalogSection.series => 'get_series_categories',
  };

  String get streamsFile => '${section.name}.json';
  String get categoriesFile => '${section.name}_categories.json';

  Uri _api(String action) => Uri.parse('$server/player_api.php').replace(
    queryParameters: {
      'username': username,
      'password': password,
      'action': action,
    },
  );
}

/// The section as the cache last saw it, or null when there is no copy.
/// Runs inside an isolate.
Shelf<Object>? loadCachedXtreamShelf(XtreamShelfJob job) {
  final files = CatalogFiles(job.cacheRoot);
  final streams = files.read(job.namespace, job.streamsFile);
  if (streams == null) return null;
  final categories = files.read(job.namespace, job.categoriesFile);
  final written = files.modified(job.namespace, job.streamsFile);
  try {
    return _buildShelf(job.section, streams, categories, written);
  } on Object {
    // A corrupt copy is a cache miss, never a broken library.
    files.delete(job.namespace, job.streamsFile);
    return null;
  }
}

/// Fetches the section from the panel, caches the panel's own bytes, and
/// builds the shelf. Runs inside an isolate.
Future<Shelf<Object>> fetchXtreamShelf(XtreamShelfJob job) async {
  const headers = {'User-Agent': AppConfig.apiUserAgent};
  // Categories are a few kilobytes; a panel that fails them still has a
  // perfectly good catalogue, grouped by the ids its items carry.
  Uint8List? categories;
  try {
    categories = await fetchBytes(
      job._api(job._categoriesAction),
      headers: headers,
    );
  } on Failure catch (failure) {
    if (failure.kind == FailureKind.auth) rethrow;
    categories = null;
  }
  final streams = await fetchBytes(
    job._api(job._streamsAction),
    headers: headers,
  );
  final shelf = _buildShelf(job.section, streams, categories, DateTime.now());

  final files = CatalogFiles(job.cacheRoot);
  files.write(job.namespace, job.streamsFile, streams);
  if (categories != null) {
    files.write(job.namespace, job.categoriesFile, categories);
  }
  return shelf;
}

Shelf<Object> _buildShelf(
  CatalogSection section,
  Uint8List streamsBytes,
  Uint8List? categoriesBytes,
  DateTime? fetchedAt,
) {
  final rows = decodeXtreamList(streamsBytes);
  final declared = categoriesBytes == null
      ? const <Category>[]
      : [
          for (final row in decodeXtreamList(categoriesBytes))
            if (row is Map) Category.fromXtream(Map<String, dynamic>.from(row)),
        ];

  switch (section) {
    case CatalogSection.live:
      final items = [
        for (final row in rows)
          if (row is Map)
            LiveChannel.fromXtream(Map<String, dynamic>.from(row)),
      ];
      return Shelf<LiveChannel>.build(
        items: items,
        categoryOf: (c) => c.categoryId,
        nameOf: (c) => c.name,
        declared: declared,
        fetchedAt: fetchedAt,
      );
    case CatalogSection.movies:
      final items = newestFirst([
        for (final row in rows)
          if (row is Map) VodMovie.fromXtream(Map<String, dynamic>.from(row)),
      ], (m) => m.added);
      return Shelf<VodMovie>.build(
        items: items,
        categoryOf: (m) => m.categoryId,
        nameOf: (m) => m.name,
        declared: declared,
        fetchedAt: fetchedAt,
      );
    case CatalogSection.series:
      final items = newestFirst([
        for (final row in rows)
          if (row is Map) SeriesItem.fromXtream(Map<String, dynamic>.from(row)),
      ], (s) => s.lastModified);
      return Shelf<SeriesItem>.build(
        items: items,
        categoryOf: (s) => s.categoryId,
        nameOf: (s) => s.name,
        declared: declared,
        fetchedAt: fetchedAt,
      );
  }
}

/// A panel's list answer, tolerating the shapes panels actually send: a bare
/// array, an array wrapped in an object, an empty object for "nothing", a BOM,
/// or an HTML error page (which decodes to nothing rather than throwing).
List<dynamic> decodeXtreamList(Uint8List bytes) {
  final text = const Utf8Decoder(allowMalformed: true).convert(bytes).trim();
  if (text.isEmpty) return const [];
  final body = text.codeUnitAt(0) == 0xFEFF ? text.substring(1) : text;
  final Object? data;
  try {
    data = jsonDecode(body);
  } on FormatException {
    throw Failure.parse('Server returned an unreadable response.');
  }
  if (data is List) return data;
  if (data is Map) {
    if (data['user_info'] is Map) {
      final auth = data['user_info']['auth'];
      if (auth == 0 || auth == '0') throw Failure.auth();
    }
    for (final value in data.values) {
      if (value is List) return value;
    }
  }
  return const [];
}

/// Newest first, by whatever timestamp the panel stamped the item with.
///
/// This is the order the catalogue is *served* in, not a view preference, and it
/// is here because of what the panel's own order actually is. Asked for all
/// 20,187 films, this subscription answers with its recorded football matches
/// first — thirty-two of them, every one carrying the identical FIFA artwork. A
/// user opening the film wall met a grid of the same picture repeated, and
/// concluded the app had failed to load. Sorted by `added`, the same request
/// opens on *The Real Charlie Chaplin*, *48 Hrs.*, *Remi Nobody's Boy*.
///
/// A panel that stamps nothing keeps its own order, which is already
/// newest-first by convention — sorting undated items to the bottom would empty
/// the wall on exactly the panels that need it most.
List<T> newestFirst<T>(List<T> items, DateTime? Function(T) stamp) {
  final dated = <T>[];
  final undated = <T>[];
  for (final item in items) {
    (stamp(item) == null ? undated : dated).add(item);
  }
  if (dated.isEmpty) return items;
  dated.sort((a, b) => stamp(b)!.compareTo(stamp(a)!));
  return [...dated, ...undated];
}
