/// A football match, read out of the programme guide the panel already ships.
///
/// The home screen's match strip is built from this and nothing else — no
/// third-party sports API, no key, no account. The reason is not frugality: a
/// match from an external feed is a *fact*, while a match from the guide is a
/// **button**. The guide entry names the channel it is on, and that channel is
/// in the user's own subscription, so tapping the match tunes it. A score from
/// an API cannot do that, and would also disagree with the guide the moment the
/// panel moved a fixture.
class LiveMatch {
  const LiveMatch({
    required this.home,
    required this.away,
    required this.start,
    required this.end,
    required this.epgChannelId,
    this.competition,
    this.channelName,
    this.streamId,
    this.channelLogo,
  });

  final String home;
  final String away;
  final DateTime start;
  final DateTime end;

  /// The XMLTV channel this fixture is on. Resolved against the user's live
  /// catalogue to fill [streamId] — a match on a channel the subscription does
  /// not carry is not shown at all, because it is not a button.
  final String epgChannelId;

  final String? competition;
  final String? channelName;
  final String? streamId;
  final String? channelLogo;

  bool get isLiveNow {
    final now = DateTime.now();
    return now.isAfter(start) && now.isBefore(end);
  }

  bool get isFinished => DateTime.now().isAfter(end);

  /// How far through the match we are, 0..1. Drives the pulsing bar on a
  /// fixture that is on air.
  double get progress {
    final total = end.difference(start).inSeconds;
    if (total <= 0) return 0;
    final elapsed = DateTime.now().difference(start).inSeconds;
    return (elapsed / total).clamp(0.0, 1.0);
  }

  LiveMatch withChannel({
    required String streamId,
    required String channelName,
    String? channelLogo,
  }) => LiveMatch(
    home: home,
    away: away,
    start: start,
    end: end,
    epgChannelId: epgChannelId,
    competition: competition,
    channelName: channelName,
    streamId: streamId,
    channelLogo: channelLogo,
  );

  /// The separators a fixture is written with, in the guides this app has
  /// actually seen. Order matters: ` vs. ` must be tried before ` v ` or the
  /// shorter one splits the longer one's stem.
  static final _separators = <RegExp>[
    RegExp(r'\s+vs\.?\s+', caseSensitive: false),
    RegExp(r'\s+ضدّ?\s+'),
    RegExp(r'\s+v\s+', caseSensitive: false),
    RegExp(r'\s+-\s+vs\s+-\s+', caseSensitive: false),
  ];

  /// Reads a fixture out of an EPG title, or returns null if it is not one.
  ///
  /// The titles look like:
  ///   `Liverpool vs Real Madrid - UEFA Champions League 2025/26 - MD4`
  ///   `Al Ahli (KSA) vs FC Machida Zelvia (JPN) - AFC Champions League - Final`
  ///
  /// The competition is whatever follows the first ` - ` **after** the fixture,
  /// which is why the title is split on the separator first and the tail second.
  /// Splitting on ` - ` first would cut `Saint-Gilloise` in half.
  static LiveMatch? tryParse(
    String title, {
    required DateTime start,
    required DateTime end,
    required String epgChannelId,
  }) {
    final clean = title.trim();
    if (clean.isEmpty) return null;

    for (final separator in _separators) {
      final match = separator.firstMatch(clean);
      if (match == null) continue;

      final home = clean.substring(0, match.start).trim();
      var tail = clean.substring(match.end).trim();
      if (home.isEmpty || tail.isEmpty) continue;

      String? competition;
      final dash = tail.indexOf(' - ');
      if (dash > 0) {
        competition = tail.substring(dash + 3).trim();
        tail = tail.substring(0, dash).trim();
      }

      // A one-word "home" like "Live" or a tail that is only a competition is
      // not a fixture — `Live v Studio` is a programme, not a match. Two names
      // is the floor.
      if (home.length < 2 || tail.length < 2) continue;

      return LiveMatch(
        home: home,
        away: tail,
        start: start,
        end: end,
        epgChannelId: epgChannelId,
        competition: (competition?.isEmpty ?? true) ? null : competition,
      );
    }
    return null;
  }
}
