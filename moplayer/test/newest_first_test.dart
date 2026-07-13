// The order the catalogue is served in.
//
// Asked for all 20,187 films, the maintainer's panel answers with its recorded
// football matches first — thirty-two of them, every one carrying the identical
// FIFA artwork. The film wall opened on a grid of the same picture repeated,
// which reads as an app that failed to load its images. This is the fix, and
// these are the two cases it must not get wrong.

import 'package:flutter_test/flutter_test.dart';
import 'package:moplayer_moos/repositories/content_repository.dart';

typedef _Item = ({String name, DateTime? added});

void main() {
  group('newestFirst', () {
    test('newest first, by the panel\'s own stamp', () {
      final items = <_Item>[
        (name: 'old', added: DateTime(2020)),
        (name: 'newest', added: DateTime(2026, 7, 13)),
        (name: 'middle', added: DateTime(2024)),
      ];

      expect(
        newestFirst(items, (i) => i.added).map((i) => i.name),
        ['newest', 'middle', 'old'],
      );
    });

    test('a panel that stamps nothing keeps its own order', () {
      // Its order is already newest-first by convention. Sorting undated items
      // to the bottom would empty the wall on exactly the panels that have no
      // other signal.
      final items = <_Item>[
        (name: 'first', added: null),
        (name: 'second', added: null),
      ];

      expect(
        newestFirst(items, (i) => i.added).map((i) => i.name),
        ['first', 'second'],
      );
    });

    test('undated items sink below dated ones, but are not dropped', () {
      final items = <_Item>[
        (name: 'undated', added: null),
        (name: 'dated', added: DateTime(2026)),
      ];

      final sorted = newestFirst(items, (i) => i.added);
      expect(sorted.map((i) => i.name), ['dated', 'undated']);
      expect(sorted, hasLength(2));
    });

    test('an empty catalogue is not an exception', () {
      expect(newestFirst(<_Item>[], (i) => i.added), isEmpty);
    });
  });
}
