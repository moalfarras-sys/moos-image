import '../../models/series.dart';

/// What a Stalker/Ministra portal says about the subscription behind a MAC.
///
/// Every field is optional: resold panels fill different subsets, and the
/// `account_info` call that carries most of them is not implemented by all of
/// them. A connected account with no fields is still a working account.
class StalkerAccount {
  const StalkerAccount({
    this.login,
    this.status,
    this.expiresAt,
    this.tariff,
    this.balance,
  });

  final String? login;

  /// `Active` or `Expired`, or the portal's own wording when it sends one.
  final String? status;

  /// Null means unknown or unlimited — the portals do not distinguish.
  final DateTime? expiresAt;
  final String? tariff;
  final String? balance;

  bool get isExpired =>
      expiresAt != null && expiresAt!.isBefore(DateTime.now());
}

/// One page of a portal's `get_ordered_list`.
///
/// [items] can be shorter than [perPage] — or even empty while [hasMore] is
/// true — because the client drops entries that belong to another list (a
/// series inside the movie list). Page on [hasMore], never on `items.length`.
class StalkerPage<T> {
  const StalkerPage({
    required this.items,
    required this.page,
    required this.totalItems,
    required this.perPage,
  });

  final List<T> items;

  /// 1-based, as the portal counts.
  final int page;
  final int totalItems;
  final int perPage;

  bool get hasMore => perPage > 0 && page * perPage < totalItems;
}

/// A series with its seasons, plus the play link of every episode.
///
/// [Episode] has no URL field, so the links travel beside the detail:
/// `episodeUrls[episode.id]` is the opaque `stalker://` link to hand to
/// `StalkerApi.resolve` when that episode is played.
class StalkerSeriesDetail {
  const StalkerSeriesDetail({required this.detail, required this.episodeUrls});

  final SeriesDetail detail;
  final Map<String, String> episodeUrls;
}
