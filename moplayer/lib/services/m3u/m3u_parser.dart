import '../../models/category.dart';
import '../../models/live_channel.dart';

/// The result of parsing an M3U playlist: ready-to-play channels grouped into
/// categories derived from their `group-title`.
class M3uResult {
  const M3uResult({required this.channels, required this.categories});

  final List<LiveChannel> channels;
  final List<Category> categories;
}

/// A fast, allocation-light M3U / M3U8 extended playlist parser.
///
/// Handles the common attribute set (`tvg-id`, `tvg-name`, `tvg-logo`,
/// `group-title`) plus the trailing display name after the comma, and is
/// tolerant of blank lines, comments and `#EXTVLCOPT`/`#EXTGRP` directives.
class M3uParser {
  const M3uParser._();

  static final RegExp _attr = RegExp(
    r'''([a-zA-Z0-9_-]+)=("([^"]*)"|'([^']*)'|([^,\s]+))''',
  );

  static M3uResult parse(String content) {
    final lines = content.split(RegExp(r'\r?\n'));
    final channels = <LiveChannel>[];
    final groupOrder = <String>[];
    final groupCounts = <String, int>{};

    String? pendingName;
    String? pendingLogo;
    String? pendingGroup;
    String? pendingTvgId;
    String? pendingExtGrp;

    for (final raw in lines) {
      final line = raw.trim();
      if (line.isEmpty) continue;

      if (line.startsWith('#EXTINF')) {
        final attrs = <String, String>{};
        for (final m in _attr.allMatches(line)) {
          attrs[m.group(1)!.toLowerCase()] =
              m.group(3) ?? m.group(4) ?? m.group(5) ?? '';
        }
        final commaIndex = line.lastIndexOf(',');
        final trailing = commaIndex >= 0
            ? line.substring(commaIndex + 1).trim()
            : '';
        pendingName = trailing.isNotEmpty
            ? trailing
            : (attrs['tvg-name'] ?? 'Channel');
        pendingLogo = _nullable(attrs['tvg-logo']);
        pendingGroup = _nullable(attrs['group-title']);
        pendingTvgId = _nullable(attrs['tvg-id']);
        continue;
      }

      if (line.startsWith('#EXTGRP:')) {
        pendingExtGrp = line.substring('#EXTGRP:'.length).trim();
        continue;
      }

      // Skip every other directive / comment.
      if (line.startsWith('#')) continue;

      // A non-comment line is the stream URL for the pending #EXTINF.
      final url = line;
      final group = (pendingGroup ?? pendingExtGrp ?? 'Uncategorized').trim();
      final name = pendingName ?? 'Channel';

      if (!groupCounts.containsKey(group)) {
        groupOrder.add(group);
      }
      groupCounts[group] = (groupCounts[group] ?? 0) + 1;

      channels.add(
        LiveChannel(
          streamId: 'm3u_${_stableIdOf(url)}',
          name: name,
          logo: pendingLogo,
          categoryId: group,
          epgChannelId: pendingTvgId,
          directUrl: url,
          containerExtension: _extensionOf(url),
        ),
      );

      pendingName = null;
      pendingLogo = null;
      pendingGroup = null;
      pendingTvgId = null;
      pendingExtGrp = null;
    }

    final categories = [
      for (final g in groupOrder)
        Category(id: g, name: g, count: groupCounts[g]),
    ];

    return M3uResult(channels: channels, categories: categories);
  }

  static String? _nullable(String? v) {
    if (v == null) return null;
    final t = v.trim();
    return t.isEmpty ? null : t;
  }

  static String _extensionOf(String url) {
    final clean = url.split('?').first;
    final dot = clean.lastIndexOf('.');
    if (dot < 0) return 'ts';
    final ext = clean.substring(dot + 1).toLowerCase();
    if (ext.length > 5) return 'ts';
    return ext;
  }

  static String _stableIdOf(String value) {
    var hash = 0x811c9dc5;
    for (final unit in value.codeUnits) {
      hash ^= unit;
      hash = (hash * 0x01000193) & 0xffffffff;
    }
    return hash.toRadixString(16).padLeft(8, '0');
  }
}
