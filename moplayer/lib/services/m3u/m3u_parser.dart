import 'dart:convert';
import 'dart:typed_data';

import '../../models/category.dart';
import '../../models/live_channel.dart';
import '../../models/series.dart';
import '../../models/vod_movie.dart';
import '../catalog/shelf.dart';

/// The live half of a playlist, in the shape the login probe and older callers
/// expect: channels, and the categories derived from their `group-title`.
class M3uResult {
  const M3uResult({required this.channels, required this.categories});

  final List<LiveChannel> channels;
  final List<Category> categories;
}

/// A whole playlist, sorted into what it actually contains.
///
/// An IPTV playlist is not only channels. A panel's `m3u_plus` export carries
/// the entire account — on the owner's subscription 12,975 channels, 20,301
/// films and 362,879 episode files — and treating every line as a channel is how
/// MoPlayer once showed "395,424 channels" whose first entry was a notice about
/// server updates, with the film and series pages empty. Entries are sorted by
/// what their address and tags say they are (see [M3uParser.kindOf]); episodes
/// are gathered into their series, so a series is one poster with seasons, not
/// three hundred rows.
class M3uLibrary {
  const M3uLibrary({
    required this.live,
    required this.movies,
    required this.series,
    required this.episodes,
    this.guideUrl,
  });

  final Shelf<LiveChannel> live;
  final Shelf<VodMovie> movies;
  final Shelf<SeriesItem> series;

  /// Episodes of each series in [series], keyed by `seriesId`, in season and
  /// episode order. Each episode carries its own `directUrl`.
  final Map<String, List<Episode>> episodes;

  /// The XMLTV guide the playlist's header points at (`url-tvg`/`x-tvg-url`),
  /// the only programme guide a plain playlist can have.
  final String? guideUrl;

  static final M3uLibrary empty = M3uLibrary(
    live: Shelf.empty(),
    movies: Shelf.empty(),
    series: Shelf.empty(),
    episodes: const {},
  );

  int get totalEntries =>
      live.length +
      movies.length +
      episodes.values.fold<int>(0, (sum, list) => sum + list.length);
}

enum M3uEntryKind { live, movie, episode }

/// One `#EXTINF` and the address under it.
class M3uEntry {
  const M3uEntry({
    required this.name,
    required this.url,
    this.logo,
    this.group,
    this.tvgId,
    this.type,
  });

  final String name;
  final String url;
  final String? logo;
  final String? group;
  final String? tvgId;

  /// The `tvg-type` / `type` attribute a few exporters write (`movie`, `series`,
  /// `live`). Trusted over every other signal when present.
  final String? type;
}

/// A fast, allocation-light M3U / M3U8 extended playlist parser.
///
/// Handles the common attribute set (`tvg-id`, `tvg-name`, `tvg-logo`,
/// `group-title`, `tvg-type`) plus the trailing display name after the comma,
/// and is tolerant of blank lines, comments and `#EXTVLCOPT`/`#EXTGRP`
/// directives. It is meant to run on a background isolate: a large playlist is
/// hundreds of thousands of lines, and none of them belong on the thread that
/// draws the window.
class M3uParser {
  const M3uParser._();

  static final RegExp _attr = RegExp(
    r'''([a-zA-Z0-9_-]+)=("([^"]*)"|'([^']*)'|([^,\s]+))''',
  );

  /// Decodes raw playlist bytes, tolerating a BOM and invalid UTF-8.
  static String decode(Uint8List bytes) {
    var start = 0;
    if (bytes.length >= 3 &&
        bytes[0] == 0xEF &&
        bytes[1] == 0xBB &&
        bytes[2] == 0xBF) {
      start = 3;
    }
    return const Utf8Decoder(
      allowMalformed: true,
    ).convert(bytes, start, bytes.length);
  }

  /// Whether [content] looks like a playlist at all.
  static bool looksLikePlaylist(String content) {
    final head = content.length > 4096 ? content.substring(0, 4096) : content;
    return head.contains('#EXTM3U') || head.contains('#EXTINF');
  }

  /// The guide address in the `#EXTM3U` header, if the playlist names one.
  static String? guideUrlOf(String content) {
    final end = content.indexOf('\n');
    final header = (end < 0 ? content : content.substring(0, end)).trim();
    if (!header.startsWith('#EXTM3U')) return null;
    for (final m in _attr.allMatches(header)) {
      final key = m.group(1)!.toLowerCase();
      if (key != 'url-tvg' && key != 'x-tvg-url' && key != 'tvg-url') continue;
      final value = (m.group(3) ?? m.group(4) ?? m.group(5) ?? '').trim();
      // Several exporters list more than one guide, comma separated; the
      // first is the one they consider primary.
      final first = value.split(',').first.trim();
      if (first.startsWith('http://') || first.startsWith('https://')) {
        return first;
      }
    }
    return null;
  }

  /// Every entry in [content], in file order.
  static List<M3uEntry> entries(String content) {
    final out = <M3uEntry>[];
    String? name;
    String? logo;
    String? group;
    String? tvgId;
    String? type;
    String? extGrp;

    var lineStart = 0;
    final length = content.length;
    while (lineStart < length) {
      var lineEnd = content.indexOf('\n', lineStart);
      if (lineEnd < 0) lineEnd = length;
      final line = content.substring(lineStart, lineEnd).trim();
      lineStart = lineEnd + 1;
      if (line.isEmpty) continue;

      if (line.startsWith('#EXTINF')) {
        final commaIndex = _nameComma(line);
        final head = commaIndex >= 0 ? line.substring(0, commaIndex) : line;
        final attrs = <String, String>{};
        for (final m in _attr.allMatches(head)) {
          attrs[m.group(1)!.toLowerCase()] =
              m.group(3) ?? m.group(4) ?? m.group(5) ?? '';
        }
        final trailing = commaIndex >= 0
            ? line.substring(commaIndex + 1).trim()
            : '';
        name = trailing.isNotEmpty
            ? trailing
            : (_nullable(attrs['tvg-name']) ?? 'Channel');
        logo = _nullable(attrs['tvg-logo']);
        group = _nullable(attrs['group-title']);
        tvgId = _nullable(attrs['tvg-id']);
        type = _nullable(attrs['tvg-type'] ?? attrs['type']);
        continue;
      }

      if (line.startsWith('#EXTGRP:')) {
        extGrp = _nullable(line.substring('#EXTGRP:'.length));
        continue;
      }

      // Every other directive or comment.
      if (line.startsWith('#')) continue;

      out.add(
        M3uEntry(
          name: name ?? 'Channel',
          url: line,
          logo: logo,
          group: group ?? extGrp,
          tvgId: tvgId,
          type: type,
        ),
      );
      name = null;
      logo = null;
      group = null;
      tvgId = null;
      type = null;
      extGrp = null;
    }
    return out;
  }

  /// The comma that separates the attributes from the display name — the first
  /// one outside a quoted attribute value. `lastIndexOf(',')` got this wrong for
  /// every title that itself contains a comma.
  static int _nameComma(String line) {
    var quote = 0;
    for (var i = 0; i < line.length; i++) {
      final c = line.codeUnitAt(i);
      if (quote != 0) {
        if (c == quote) quote = 0;
        continue;
      }
      if (c == 0x22 || c == 0x27) {
        // Only an attribute value opens a quote: `key="…"`.
        if (i > 0 && line.codeUnitAt(i - 1) == 0x3D) quote = c;
        continue;
      }
      if (c == 0x2C) return i;
    }
    return -1;
  }

  static const _videoFileExtensions = {
    'mp4',
    'mkv',
    'avi',
    'mov',
    'm4v',
    'wmv',
    'flv',
    'mpg',
    'mpeg',
    'webm',
    'divx',
    '3gp',
    'vob',
  };

  static final RegExp _episodeMark = RegExp(
    r'(?:^|[\s._\-\[(|])(?:s|season\s*)(\d{1,2})[\s._\-]*(?:e|ep|episode\s*)(\d{1,4})(?![0-9])',
    caseSensitive: false,
  );
  static final RegExp _crossMark = RegExp(
    r'(?:^|[\s._\-\[(])(\d{1,2})x(\d{1,3})(?![0-9])',
    caseSensitive: false,
  );
  static final RegExp _arabicEpisode = RegExp(
    r'(?:الحلقة|الحلقه|حلقة|حلقه)\s*(\d{1,4})',
  );
  static final RegExp _arabicSeason = RegExp(r'(?:الموسم|موسم)\s*(\d{1,2})');

  /// What an entry is.
  ///
  /// In order of trust: an explicit `tvg-type`; the Xtream path the address was
  /// minted on (`/movie/`, `/series/`, `/live/`); an episode marker in the title
  /// on a video file; a video-file extension; then a live stream.
  static M3uEntryKind kindOf(M3uEntry entry) {
    final type = entry.type?.toLowerCase();
    if (type != null) {
      if (type.startsWith('movie') || type == 'vod') return M3uEntryKind.movie;
      if (type.startsWith('serie')) return M3uEntryKind.episode;
      if (type.startsWith('live') || type == 'tv') return M3uEntryKind.live;
    }
    final url = entry.url;
    final path = url.split('?').first.toLowerCase();
    if (path.contains('/series/')) return M3uEntryKind.episode;
    if (path.contains('/movie/') || path.contains('/movies/')) {
      return M3uEntryKind.movie;
    }
    if (path.contains('/live/')) return M3uEntryKind.live;

    final ext = extensionOf(url);
    if (_videoFileExtensions.contains(ext)) {
      return episodeMarker(entry.name) != null
          ? M3uEntryKind.episode
          : M3uEntryKind.movie;
    }
    return M3uEntryKind.live;
  }

  /// `(series, season, episode)` read from a title, or null.
  static ({String series, int season, int episode})? episodeMarker(
    String title,
  ) {
    final latin =
        _episodeMark.firstMatch(title) ?? _crossMark.firstMatch(title);
    if (latin != null) {
      final series = _cleanSeriesName(title.substring(0, latin.start));
      if (series.isEmpty) return null;
      return (
        series: series,
        season: int.parse(latin.group(1)!),
        episode: int.parse(latin.group(2)!),
      );
    }
    final arabic = _arabicEpisode.firstMatch(title);
    if (arabic != null) {
      final season = _arabicSeason.firstMatch(title);
      final cut = season != null && season.start < arabic.start
          ? season.start
          : arabic.start;
      final series = _cleanSeriesName(title.substring(0, cut));
      if (series.isEmpty) return null;
      return (
        series: series,
        season: season == null ? 1 : int.parse(season.group(1)!),
        episode: int.parse(arabic.group(1)!),
      );
    }
    return null;
  }

  static String _cleanSeriesName(String raw) {
    var name = raw.trim();
    while (name.isNotEmpty && ' -_|.:([–'.contains(name[name.length - 1])) {
      name = name.substring(0, name.length - 1).trimRight();
    }
    return name;
  }

  static final RegExp _year = RegExp(r'[(\[]((?:19|20)\d{2})[)\]]');

  /// Sorts a playlist into live channels, films and series. Run it on a
  /// background isolate.
  static M3uLibrary parseLibrary(String content) {
    final live = <LiveChannel>[];
    final movies = <VodMovie>[];
    final seriesOrder = <String>[];
    final seriesById = <String, SeriesItem>{};
    final episodes = <String, List<Episode>>{};

    for (final entry in entries(content)) {
      final group = entry.group?.trim();
      switch (kindOf(entry)) {
        case M3uEntryKind.live:
          live.add(_channel(entry));
        case M3uEntryKind.movie:
          final year = _year.firstMatch(entry.name)?.group(1);
          movies.add(
            VodMovie(
              streamId: 'm3u_${stableIdOf(entry.url)}',
              name: entry.name,
              poster: entry.logo,
              categoryId: group ?? 'Uncategorized',
              year: year,
              containerExtension: extensionOf(entry.url),
              directUrl: entry.url,
            ),
          );
        case M3uEntryKind.episode:
          final marker = episodeMarker(entry.name);
          final seriesName = marker?.series ?? entry.name;
          final category = group ?? 'Uncategorized';
          final seriesId =
              'm3us_${stableIdOf('${seriesName.toLowerCase()}|$category')}';
          if (!seriesById.containsKey(seriesId)) {
            seriesOrder.add(seriesId);
            seriesById[seriesId] = SeriesItem(
              seriesId: seriesId,
              name: seriesName,
              cover: entry.logo,
              categoryId: category,
            );
          }
          final list = episodes.putIfAbsent(seriesId, () => <Episode>[]);
          list.add(
            Episode(
              id: 'm3u_${stableIdOf(entry.url)}',
              title: entry.name,
              episodeNum: marker?.episode ?? list.length + 1,
              seasonNumber: marker?.season ?? 1,
              containerExtension: extensionOf(entry.url),
              image: entry.logo,
              directUrl: entry.url,
            ),
          );
      }
    }

    for (final list in episodes.values) {
      list.sort((a, b) {
        final bySeason = a.seasonNumber.compareTo(b.seasonNumber);
        return bySeason != 0 ? bySeason : a.episodeNum.compareTo(b.episodeNum);
      });
    }

    final now = DateTime.now();
    return M3uLibrary(
      live: Shelf.build(
        items: live,
        categoryOf: (c) => c.categoryId,
        nameOf: (c) => c.name,
        fetchedAt: now,
      ),
      movies: Shelf.build(
        items: movies,
        categoryOf: (m) => m.categoryId,
        nameOf: (m) => m.name,
        fetchedAt: now,
      ),
      series: Shelf.build(
        items: [for (final id in seriesOrder) seriesById[id]!],
        categoryOf: (s) => s.categoryId,
        nameOf: (s) => s.name,
        fetchedAt: now,
      ),
      episodes: episodes,
      guideUrl: guideUrlOf(content),
    );
  }

  /// The live channels of [content]. Kept for the callers that only need a
  /// channel list, like the login probe and the tests.
  static M3uResult parse(String content) {
    final shelf = parseLibrary(content).live;
    return M3uResult(channels: shelf.items, categories: shelf.categories);
  }

  static LiveChannel _channel(M3uEntry entry) => LiveChannel(
    streamId: 'm3u_${stableIdOf(entry.url)}',
    name: entry.name,
    logo: entry.logo,
    categoryId: (entry.group ?? 'Uncategorized').trim(),
    epgChannelId: entry.tvgId,
    directUrl: entry.url,
    containerExtension: extensionOf(entry.url),
  );

  static String? _nullable(String? v) {
    if (v == null) return null;
    final t = v.trim();
    return t.isEmpty ? null : t;
  }

  static String extensionOf(String url) {
    final clean = url.split('?').first;
    final slash = clean.lastIndexOf('/');
    final dot = clean.lastIndexOf('.');
    if (dot < 0 || dot < slash) return 'ts';
    final ext = clean.substring(dot + 1).toLowerCase();
    if (ext.isEmpty || ext.length > 5) return 'ts';
    return ext;
  }

  /// FNV-1a over the address. Favourites, history and resume positions are
  /// keyed on it, so it must not depend on list position.
  static String stableIdOf(String value) {
    var hash = 0x811c9dc5;
    for (final unit in value.codeUnits) {
      hash ^= unit;
      hash = (hash * 0x01000193) & 0xffffffff;
    }
    return hash.toRadixString(16).padLeft(8, '0');
  }
}
