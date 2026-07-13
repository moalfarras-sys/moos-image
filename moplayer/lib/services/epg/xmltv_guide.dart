import 'package:xml/xml.dart';

import '../../models/epg_entry.dart';
import '../../models/live_match.dart';

/// The panel's whole programme guide, parsed once and indexed.
///
/// Why XMLTV at all, when the Xtream API has `get_short_epg`? Because on the
/// panel this app is actually tested against, `get_short_epg` returns `[]` and
/// `get_simple_data_table` returns `[]` — for every channel — while `xmltv.php`
/// returns 2,587 programmes across 30 channels, including 306 fixtures. A guide
/// that is "empty" through one endpoint and complete through another is not an
/// empty guide; it is an endpoint the panel does not implement. The API is still
/// tried first (panels that do implement it answer faster and per-channel), and
/// this is the fallback that makes the guide appear at all.
class EpgGuide {
  const EpgGuide({required this.byChannel, required this.matches});

  /// Programmes per XMLTV channel id, ascending by start time. The key is
  /// lower-cased: panels write `beIN SPORTS 1.qa` in the guide and
  /// `BEIN SPORTS 1.qa` in the stream list, and a case-sensitive lookup finds
  /// nothing while both files look correct.
  final Map<String, List<EpgEntry>> byChannel;

  /// Every fixture in the guide, in start order, **without** a stream id — the
  /// guide does not know the user's catalogue. Joined against it by the caller.
  final List<LiveMatch> matches;

  static const empty = EpgGuide(byChannel: {}, matches: []);

  bool get isEmpty => byChannel.isEmpty;

  List<EpgEntry> forChannel(String? epgChannelId) {
    final key = epgChannelId?.trim().toLowerCase();
    if (key == null || key.isEmpty) return const [];
    return byChannel[key] ?? const [];
  }

  EpgEntry? nowOn(String? epgChannelId) {
    for (final entry in forChannel(epgChannelId)) {
      if (entry.isLiveNow) return entry;
    }
    return null;
  }

  /// Parses an XMLTV document. Pure and top-level-callable, so it can be handed
  /// to `compute()` — 1.1 MB of XML on the UI isolate is a dropped frame at
  /// launch, on the one screen the user is looking at.
  static EpgGuide parse(String xml) {
    if (xml.trim().isEmpty) return empty;

    final XmlDocument document;
    try {
      document = XmlDocument.parse(xml);
    } on XmlException {
      // A panel that answers `xmltv.php` with an HTML error page is a panel
      // without a guide, not a crash.
      return empty;
    }

    final byChannel = <String, List<EpgEntry>>{};
    final matches = <LiveMatch>[];

    // Panels publish the same programme twice. Not a rare panel and not a bad
    // one — the maintainer's own guide lists `Germany vs Spain` on beIN SPORTS 1
    // at 13:45 in two identical <programme> elements, and so it does for most of
    // the evening's fixtures. Rendered faithfully that is a match strip showing
    // every game twice, which reads as a bug in *this* app. Deduped on what makes
    // a programme the same programme: the channel, the minute, and the title.
    final seenProgrammes = <String>{};

    for (final programme in document.findAllElements('programme')) {
      final channel = programme.getAttribute('channel')?.trim();
      if (channel == null || channel.isEmpty) continue;

      final start = _time(programme.getAttribute('start'));
      if (start == null) continue;
      final stop =
          _time(programme.getAttribute('stop')) ??
          start.add(const Duration(minutes: 30));

      final title = _text(programme, 'title');
      if (title.isEmpty) continue;

      final fingerprint =
          '${channel.toLowerCase()}|${start.millisecondsSinceEpoch}|$title';
      if (!seenProgrammes.add(fingerprint)) continue;

      final key = channel.toLowerCase();
      (byChannel[key] ??= <EpgEntry>[]).add(
        EpgEntry(
          title: title,
          start: start,
          end: stop,
          description: _text(programme, 'desc'),
        ),
      );

      final fixture = LiveMatch.tryParse(
        title,
        start: start,
        end: stop,
        epgChannelId: channel,
      );
      if (fixture != null) matches.add(fixture);
    }

    for (final entries in byChannel.values) {
      entries.sort((a, b) => a.start.compareTo(b.start));
    }
    matches.sort((a, b) => a.start.compareTo(b.start));

    return EpgGuide(byChannel: byChannel, matches: matches);
  }

  /// XMLTV time: `20260713004500 +0200`. The offset is not optional in practice
  /// and it is not the viewer's — a guide parsed as local time puts a 22:00
  /// kick-off at 20:00 for a user one zone over, which is exactly the kind of
  /// wrong that looks right.
  static DateTime? _time(String? raw) {
    final value = raw?.trim();
    if (value == null || value.length < 14) return null;

    final digits = value.substring(0, 14);
    final year = int.tryParse(digits.substring(0, 4));
    final month = int.tryParse(digits.substring(4, 6));
    final day = int.tryParse(digits.substring(6, 8));
    final hour = int.tryParse(digits.substring(8, 10));
    final minute = int.tryParse(digits.substring(10, 12));
    final second = int.tryParse(digits.substring(12, 14));
    if (year == null ||
        month == null ||
        day == null ||
        hour == null ||
        minute == null ||
        second == null) {
      return null;
    }

    var utc = DateTime.utc(year, month, day, hour, minute, second);

    final offset = value.length >= 20 ? value.substring(15, 20) : '';
    final sign = value.length >= 16 ? value[15] : '';
    if (offset.length == 5 && (sign == '+' || sign == '-')) {
      final oh = int.tryParse(offset.substring(1, 3)) ?? 0;
      final om = int.tryParse(offset.substring(3, 5)) ?? 0;
      final delta = Duration(hours: oh, minutes: om);
      utc = sign == '+' ? utc.subtract(delta) : utc.add(delta);
    }

    return utc.toLocal();
  }

  static String _text(XmlElement programme, String name) {
    final node = programme.getElement(name);
    return node?.innerText.trim() ?? '';
  }
}
