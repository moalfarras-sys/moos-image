// The palette is measured off the mark, and this is what keeps it that way.
//
// A brand colour is the one value in a design system that cannot be argued about
// — it either is the logo's colour or it is not. This test opens the actual PNG,
// samples the flame, and fails if the tokens have drifted away from it. It is the
// only test in this repo that reads an image, and it exists because `ember` was
// #FF6A0F for months: a full 38 points lighter and yellower than the flame it was
// supposed to be, which is exactly the mismatch that makes a brand look
// approximated rather than owned.

import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image/image.dart' as img;
import 'package:moplayer_moos/core/theme/app_colors.dart';

/// How far two colours may sit apart in RGB and still be "the same colour" to an
/// eye looking at a 14 px icon. Generous on purpose: this guards against a token
/// being *replaced*, not against a designer nudging a channel by two.
const _tolerance = 26;

int _distance(Color a, Color b) {
  final dr = ((a.r - b.r) * 255).abs();
  final dg = ((a.g - b.g) * 255).abs();
  final db = ((a.b - b.b) * 255).abs();
  return (dr + dg + db).round();
}

void main() {
  /// The flame's pixels, packed 0xRRGGBB.
  ///
  /// Packed, and not a `List<img.Pixel>`, because iterating an `img.Image` hands
  /// back **the same Pixel object** re-pointed at each position — collecting them
  /// yields a list of N references to the last pixel in the image, which is the
  /// bottom-right corner, which is black. The first version of this test did
  /// exactly that and reported the logo's dominant colour as `#080a09`.
  late List<int> flame;

  setUpAll(() {
    final bytes = File('assets/branding/logo.png').readAsBytesSync();
    final decoded = img.decodePng(bytes)!;

    // The flame only: opaque, and unmistakably warm. Everything else in the
    // lockup is the black plate, the wordmark, or an anti-aliased edge — and the
    // edges are where a naive average goes to die.
    flame = <int>[];
    for (final p in decoded) {
      final r = p.r.round();
      final g = p.g.round();
      final b = p.b.round();
      if (p.a < 200) continue;
      if (r < 120 || (r - b) < 80) continue;
      flame.add((r << 16) | (g << 8) | b);
    }
  });

  test('the mark is not empty — the asset is still there and still a flame', () {
    expect(flame.length, greaterThan(5000));
  });

  test('AppColors.ember is the flame\'s core', () {
    // The single most common colour in the mark.
    final counts = <int, int>{};
    for (final rgb in flame) {
      counts[rgb] = (counts[rgb] ?? 0) + 1;
    }
    final dominant = counts.entries.reduce((a, b) => a.value >= b.value ? a : b).key;
    final core = Color(0xFF000000 | dominant);

    expect(
      _distance(AppColors.ember, core),
      lessThan(_tolerance),
      reason:
          'AppColors.ember (#${AppColors.ember.toARGB32().toRadixString(16)}) has drifted '
          'from the logo\'s dominant colour (#${core.toARGB32().toRadixString(16)}). '
          'The brand is measured, not chosen.',
    );
  });

  test('AppColors.primary is a colour that is actually in the mark', () {
    // Not the core — the core is too dark to read as 14 px text on near-black,
    // which is why `primary` is the flame's lit crown instead. But it has to be
    // a colour the flame *contains*.
    final nearest = flame
        .map((rgb) => _distance(AppColors.primary, Color(0xFF000000 | rgb)))
        .reduce((a, b) => a < b ? a : b);

    expect(
      nearest,
      lessThan(_tolerance),
      reason: 'AppColors.primary is not a colour that appears in the logo at all',
    );
  });

  test('the ember gradient runs the mark\'s own ramp, dark core to lit crown', () {
    final colors = AppColors.emberGradient.colors;
    expect(colors, contains(AppColors.ember));
    expect(colors, contains(AppColors.primary));

    // And in that order: a gradient that runs crown-to-core is the flame upside
    // down, and it is the kind of wrong nobody can name but everybody sees.
    expect(
      colors.indexOf(AppColors.primary),
      lessThan(colors.indexOf(AppColors.ember)),
    );
  });
}
