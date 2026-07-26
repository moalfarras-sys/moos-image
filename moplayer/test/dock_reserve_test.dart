import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

/// The dock floats over the foot of the window, and `main_shell.dart` hands
/// every screen its height through `MediaQuery.padding.bottom`, with a comment
/// stating that "every scrolling screen reads this and adds it to the bottom of
/// its scroll padding".
///
/// Eight of the ten screens did not. The result was the last row of the home
/// page — "continue watching", the row most likely to be wanted — drawn
/// underneath the glass with no way to scroll it clear, and the same on the
/// movie, series, live and search grids.
///
/// It is the kind of contract that is stated in a comment on one file and
/// silently broken in another, and nothing else in this repo would notice: it
/// builds, it runs, and it looks *almost* right. So it gets a test, in the same
/// spirit as `app_identity_test.dart`.
void main() {
  /// Screens that scroll under the dock. `login_screen` is deliberately absent:
  /// it is shown before the shell exists, so there is no dock to clear.
  const scrollingScreens = <String>[
    'lib/features/home/home_screen.dart',
    'lib/features/favorites/favorites_screen.dart',
    'lib/features/live/live_screen.dart',
    'lib/features/movies/movies_screen.dart',
    'lib/features/movies/movie_detail_screen.dart',
    'lib/features/series/series_screen.dart',
    'lib/features/series/series_detail_screen.dart',
    'lib/features/search/search_screen.dart',
    'lib/features/settings/settings_screen.dart',
  ];

  group('every scrolling screen clears the dock', () {
    for (final path in scrollingScreens) {
      test(path.split('/').last, () {
        final source = File(path).readAsStringSync();
        expect(
          source.contains('MediaQuery.paddingOf(context).bottom'),
          isTrue,
          reason:
              '$path scrolls under the floating dock but never reads the '
              'height the shell gives it, so its last row is hidden under the '
              'glass. Add it to the bottom of the scroll padding — see '
              'lib/app/main_shell.dart.',
        );
      });
    }
  });

  test('the shell still provides the padding these screens read', () {
    // The other half of the contract. If the shell stops injecting it, every
    // screen above silently starts padding by zero and the bug returns without
    // a single one of them changing.
    final shell = File('lib/app/main_shell.dart').readAsStringSync();
    expect(shell.contains('padding: MediaQuery.paddingOf('), isTrue);
    expect(shell.contains('bottom: dockReserve'), isTrue);
  });

  test('no scrolling screen zeroes its padding outright', () {
    // `EdgeInsets.zero` is how this regressed in the first place: it reads as a
    // deliberate "no padding wanted" rather than as an oversight.
    for (final path in scrollingScreens) {
      final source = File(path).readAsStringSync();
      expect(
        RegExp(r'padding:\s*EdgeInsets\.zero').hasMatch(source),
        isFalse,
        reason: '$path zeroes a scroll padding; the dock needs room.',
      );
    }
  });
}
