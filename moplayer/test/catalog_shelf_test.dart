// The index every catalogue screen reads.
//
// These pin the behaviour the UI depends on: a category is a map read with a
// count, a declared-but-empty panel category is not a dead end on screen, and
// search finds Arabic titles however the alef or the taa marbuta was typed.

import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:moplayer_moos/models/category.dart';
import 'package:moplayer_moos/services/cache/cache_service.dart';
import 'package:moplayer_moos/services/catalog/catalog_files.dart';
import 'package:moplayer_moos/services/catalog/search_key.dart';
import 'package:moplayer_moos/services/catalog/shelf.dart';

typedef _Item = ({String name, String? category});

Shelf<_Item> _shelf(List<_Item> items, {List<Category> declared = const []}) =>
    Shelf.build(
      items: items,
      categoryOf: (i) => i.category,
      nameOf: (i) => i.name,
      declared: declared,
    );

void main() {
  group('Shelf', () {
    test('groups by category and counts each one once', () {
      final shelf = _shelf([
        (name: 'A', category: '1'),
        (name: 'B', category: '2'),
        (name: 'C', category: '1'),
      ]);
      expect(shelf.inCategory('1').map((i) => i.name), ['A', 'C']);
      expect(shelf.inCategory(Category.allId), hasLength(3));
      expect(shelf.inCategory(null), hasLength(3));
      expect(shelf.inCategory('missing'), isEmpty);
      expect({for (final c in shelf.categories) c.id: c.count}, {
        '1': 2,
        '2': 1,
      });
    });

    test('keeps the panel order, drops empty categories, adds unnamed ones', () {
      final shelf = _shelf(
        [
          (name: 'A', category: '7'),
          (name: 'B', category: '3'),
          (name: 'C', category: '99'),
        ],
        declared: const [
          Category(id: '3', name: 'News'),
          Category(id: '5', name: 'Empty'),
          Category(id: '7', name: 'Sport'),
        ],
      );
      expect(shelf.categories.map((c) => c.name), ['News', 'Sport', '99']);
    });

    test('search matches every word, in any order, up to the limit', () {
      final shelf = _shelf([
        (name: 'The Dark Knight — Batman', category: null),
        (name: 'Batman Begins', category: null),
        (name: 'Dark Waters', category: null),
      ]);
      expect(shelf.search('batman dark').map((i) => i.name), [
        'The Dark Knight — Batman',
      ]);
      expect(shelf.search('BATMAN'), hasLength(2));
      expect(shelf.search('batman', limit: 1), hasLength(1));
      expect(shelf.search('   '), isEmpty);
    });

    test('Arabic search ignores alef forms, taa marbuta and harakat', () {
      final shelf = _shelf([
        (name: 'أفلام الأكشن', category: null),
        (name: 'مسلسل الهيبة', category: null),
        (name: 'قناةُ الجزيرة', category: null),
      ]);
      expect(shelf.search('افلام'), hasLength(1));
      expect(shelf.search('الهيبه'), hasLength(1));
      expect(shelf.search('قناة الجزيرة'), hasLength(1));
    });
  });

  test('searchKey folds punctuation and Arabic digits', () {
    expect(searchKey('Spider-Man: No Way Home'), 'spider man no way home');
    expect(searchKey('beIN ٣ HD'), 'bein 3 hd');
    expect(searchKey('إ ـ ى'), 'ا ي');
  });

  group('CatalogFiles', () {
    late Directory dir;
    setUp(() => dir = Directory.systemTemp.createTempSync('moplayer_catalog'));
    tearDown(() => dir.deleteSync(recursive: true));

    test('writes atomically and reads back the same bytes', () {
      final files = CatalogFiles(dir.path);
      expect(files.read('src', 'live.json'), isNull);
      expect(files.write('src', 'live.json', [1, 2, 3]), isTrue);
      expect(files.read('src', 'live.json'), [1, 2, 3]);
      expect(files.age('src', 'live.json')!.inSeconds, lessThan(5));
      final leftovers = Directory(
        '${dir.path}/src',
      ).listSync().map((e) => e.path.split('/').last);
      expect(leftovers, ['live.json'], reason: 'no temporary file survives');
    });

    test('a namespace cannot escape the cache root', () {
      final files = CatalogFiles(dir.path);
      files.write('../../etc', 'x', [1]);
      expect(File('${dir.path}/.._.._etc/x').existsSync(), isTrue);
    });
  });

  test('the retired Hive catalogue box is deleted, never opened', () async {
    final dir = Directory.systemTemp.createTempSync('moplayer_legacy');
    addTearDown(() => dir.deleteSync(recursive: true));
    final legacy = File('${dir.path}/mp_cache.hive')
      ..writeAsBytesSync(List.filled(1024, 7));
    final cache = CacheService();
    await cache.init(path: dir.path);
    expect(legacy.existsSync(), isFalse);
    expect(cache.isPersistent, isTrue);
  });
}
