import '../../models/category.dart';
import 'search_key.dart';

/// One section of a catalogue — the live channels, the films or the series —
/// fully indexed and ready to be read from the UI isolate.
///
/// A shelf is **built on a background isolate** and handed back whole. That is
/// the entire point of it. The app used to keep a catalogue as a JSON string in
/// a Hive box and rebuild it on the UI isolate: 20,569 films, 10,834 series and
/// 12,975 channels on the owner's panel meant tens of megabytes decoded, mapped,
/// sorted and filtered on the thread that also draws the window, and a 395,424
/// entry playlist froze it for many seconds at a time. Everything a screen asks
/// of a shelf is now an index lookup:
///
///  * [inCategory] is a map read, not a `where` over the whole catalogue;
///  * category counts are computed once, with the index;
///  * [search] scans titles that were folded for comparison when the shelf was
///    built (see [searchKey]), and stops at the first `limit` hits.
class Shelf<T> {
  Shelf._(
    this.categories,
    this.items,
    this._byCategory,
    this._keys,
    this.fetchedAt,
  );

  /// Builds the indices. Call this on the isolate that produced [items].
  ///
  /// [declared] is the category list the server published, in its order; any
  /// category an item names but the server did not declare is appended, and any
  /// declared category with no items is dropped — a panel's empty categories
  /// are a list of dead ends. Without a declared list (an M3U playlist), the
  /// categories are the items' own, in first-seen order.
  factory Shelf.build({
    required List<T> items,
    required String? Function(T) categoryOf,
    required String Function(T) nameOf,
    List<Category> declared = const [],
    DateTime? fetchedAt,
  }) {
    final byCategory = <String, List<T>>{};
    final firstSeen = <String>[];
    final keys = List<String>.filled(items.length, '', growable: false);
    for (var i = 0; i < items.length; i++) {
      final item = items[i];
      keys[i] = searchKey(nameOf(item));
      final category = categoryOf(item);
      if (category == null || category.isEmpty) continue;
      final bucket = byCategory[category];
      if (bucket == null) {
        byCategory[category] = <T>[item];
        firstSeen.add(category);
      } else {
        bucket.add(item);
      }
    }

    final categories = <Category>[];
    final named = <String>{};
    for (final category in declared) {
      final count = byCategory[category.id]?.length ?? 0;
      if (count == 0 || !named.add(category.id)) continue;
      categories.add(category.copyWith(count: count));
    }
    for (final id in firstSeen) {
      if (named.contains(id)) continue;
      named.add(id);
      categories.add(
        Category(id: id, name: id, count: byCategory[id]!.length),
      );
    }

    return Shelf._(
      List.unmodifiable(categories),
      List.unmodifiable(items),
      byCategory,
      keys,
      fetchedAt ?? DateTime.now(),
    );
  }

  static final Shelf<Never> _empty = Shelf._(
    const [],
    const [],
    const {},
    const [],
    DateTime.fromMillisecondsSinceEpoch(0),
  );

  /// A shelf with nothing on it, for a source that has no such section.
  static Shelf<T> empty<T>() => _empty as Shelf<T>;

  final List<Category> categories;
  final List<T> items;
  final DateTime fetchedAt;
  final Map<String, List<T>> _byCategory;
  final List<String> _keys;

  bool get isEmpty => items.isEmpty;
  int get length => items.length;

  /// Everything in [categoryId], or everything when it is null or "All".
  List<T> inCategory(String? categoryId) {
    if (categoryId == null ||
        categoryId.isEmpty ||
        categoryId == Category.allId) {
      return items;
    }
    return _byCategory[categoryId] ?? const [];
  }

  /// Titles containing every word of [query], in catalogue order.
  ///
  /// Every word, not the whole phrase: "batman dark" finds *The Dark Knight —
  /// Batman*, and an Arabic title typed in a different word order still lands.
  List<T> search(String query, {int limit = 120}) {
    final words = searchKey(
      query,
    ).split(' ').where((w) => w.isNotEmpty).toList(growable: false);
    if (words.isEmpty) return const [];
    final hits = <T>[];
    for (var i = 0; i < _keys.length && hits.length < limit; i++) {
      final key = _keys[i];
      var all = true;
      for (final word in words) {
        if (!key.contains(word)) {
          all = false;
          break;
        }
      }
      if (all) hits.add(items[i]);
    }
    return hits;
  }
}
