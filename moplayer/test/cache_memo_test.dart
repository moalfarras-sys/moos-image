// What a cache read actually costs on a real catalogue.
//
// `CacheService.getList` decoded its envelope from scratch on every call. That is
// invisible on a demo playlist and it is a freeze on a real one: the maintainer's
// panel returns 20,187 films, and *search* asks for the films, the series and the
// channels — three envelopes, ~22 MB of JSON — on the UI isolate, after every
// debounced keystroke.
//
// This test measures the second read of the same key. It is a benchmark, so it
// asserts a ratio rather than a wall-clock number: the machine it runs on is not
// the machine it was written on.

import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:hive_ce/hive.dart';
import 'package:moplayer_moos/services/cache/cache_service.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late CacheService cache;

  setUp(() async {
    // A real Hive box on a temp dir — the memo has to survive a genuine box read,
    // and an in-memory fake would prove nothing about the thing being fixed.
    final dir = Directory.systemTemp.createTempSync('moplayer_cache_test');
    cache = CacheService();
    await cache.init(path: dir.path);
  });

  tearDown(() async {
    await Hive.close();
  });

  test('a second read of the same key does not decode it again', () async {
    // 20,000 rows, the shape a panel actually returns.
    final rows = [
      for (var i = 0; i < 20000; i++)
        {
          'num': i,
          'name': 'A film with a reasonably long name $i',
          'stream_id': 500000 + i,
          'stream_icon': 'https://image.tmdb.org/t/p/w600/$i.jpg',
          'rating': '7.$i',
          'added': '178000000$i',
          'category_id': '${i % 70}',
          'container_extension': 'mkv',
        },
    ];
    await cache.putList('vod_all', rows);

    final first = Stopwatch()..start();
    final a = cache.getList('vod_all');
    first.stop();

    final second = Stopwatch()..start();
    final b = cache.getList('vod_all');
    second.stop();

    // ignore: avoid_print
    print(
      '  first read: ${first.elapsedMilliseconds}ms · '
      'second read: ${second.elapsedMicroseconds}µs',
    );

    expect(a, hasLength(20000));
    expect(b, hasLength(20000));
    expect(b!.first['name'], a!.first['name']);

    // The second read is the one search pays, over and over. It must be free.
    expect(
      second.elapsedMicroseconds,
      lessThan(first.elapsedMicroseconds ~/ 10),
      reason:
          'the second read cost ${second.elapsedMilliseconds}ms against '
          '${first.elapsedMilliseconds}ms for the first — the envelope is being '
          'decoded again on every call, and search calls it three times per '
          'keystroke',
    );
  });

  test(
    'a write invalidates the memo — a stale read is worse than a slow one',
    () async {
      await cache.putList('k', [
        {'name': 'before'},
      ]);
      expect(cache.getList('k')!.first['name'], 'before');

      await cache.putList('k', [
        {'name': 'after'},
      ]);
      expect(
        cache.getList('k')!.first['name'],
        'after',
        reason: 'the memo served a value the cache no longer holds',
      );
    },
  );

  test('an expired entry is still expired, memo or not', () async {
    await cache.putList('k', [
      {'name': 'x'},
    ]);
    // Warm the memo, then ask with a TTL that the entry cannot satisfy.
    expect(cache.getList('k'), isNotNull);
    expect(
      cache.getList('k', ttl: Duration.zero),
      isNull,
      reason: 'the memo outlived the TTL it was supposed to respect',
    );
  });

  test(
    'the envelope on disk is still plain JSON — nothing changed on disk',
    () async {
      await cache.putList('k', [
        {'name': 'x'},
      ]);
      final raw = Hive.box<String>('mp_cache').get('k')!;
      final decoded = jsonDecode(raw) as Map<String, dynamic>;
      expect(decoded['ts'], isA<int>());
      expect(decoded['data'], isA<List<dynamic>>());
    },
  );
}
