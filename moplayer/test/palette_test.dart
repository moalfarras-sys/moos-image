// MoPlayer takes its accent from the desktop's MoOS palette.
//
// The palette is chosen by the owner, not by this app, so the app cannot know
// in advance what hue it will be handed. These pin the two promises it makes
// for any hue: the primary gradient carries one readable foreground at every
// stop, and a `kdeglobals` it can read produces the palette it names.

import 'package:flutter/painting.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:moplayer_moos/core/theme/palette.dart';

void main() {
  // MoOS's own families plus hues a KDE user could pick by hand, including
  // the awkward ones: a deep navy, a pale yellow, pure blue.
  const accents = {
    'tidal': Color(0xFF4ED7C8),
    'amethyst': Color(0xFFC084FC),
    'aurora': Color(0xFF69D9A5),
    'ember': Color(0xFFFF8A1F),
    'navy': Color(0xFF1B2A6B),
    'pale': Color(0xFFFFF6B0),
    'blue': Color(0xFF0000FF),
    'red': Color(0xFFE53935),
    'grey': Color(0xFF808080),
  };

  group('every accent keeps its foreground readable', () {
    for (final entry in accents.entries) {
      test(entry.key, () {
        final palette = Palette.from(accent: entry.value);
        for (final stop in [
          palette.accentBright,
          palette.accent,
          palette.accentDeep,
        ]) {
          expect(
            Palette.contrast(palette.onAccent, stop),
            greaterThanOrEqualTo(4.5),
            reason:
                '${entry.key}: #${stop.toARGB32().toRadixString(16)} under '
                '#${palette.onAccent.toARGB32().toRadixString(16)}',
          );
        }
        // And the accent itself reads as a colour on the canvas.
        expect(
          Palette.contrast(palette.accent, palette.canvas),
          greaterThanOrEqualTo(4.5),
        );
      });
    }
  });

  test('an explicit AccentColor wins over the scheme selection colour', () {
    const text = '''
[General]
ColorScheme=MoOSUI2Amethyst
AccentColor=78,215,200

[Colors:Selection]
BackgroundNormal=192,132,252

[Colors:Window]
BackgroundNormal=32,24,41
''';
    final palette = Palette.fromKdeglobals(text)!;
    expect(palette.schemeName, 'MoOSUI2Amethyst');
    expect(
      HSLColor.fromColor(palette.accent).hue,
      closeTo(HSLColor.fromColor(const Color(0xFF4ED7C8)).hue, 3),
    );
  });

  test('without AccentColor the selection colour is the accent', () {
    const text = '''
[Colors:Selection]
BackgroundNormal=192,132,252
''';
    final palette = Palette.fromKdeglobals(text)!;
    expect(
      HSLColor.fromColor(palette.accent).hue,
      closeTo(HSLColor.fromColor(const Color(0xFFC084FC)).hue, 3),
    );
  });

  test('a light scheme does not wash out the always-dark canvas', () {
    const text = '''
[Colors:Selection]
BackgroundNormal=0,109,103
[Colors:Window]
BackgroundNormal=216,235,231
''';
    final palette = Palette.fromKdeglobals(text)!;
    expect(palette.canvas.computeLuminance(), lessThan(0.02));
  });

  test('an unreadable file yields no palette rather than a crash', () {
    expect(Palette.fromKdeglobals(''), isNull);
    expect(Palette.fromKdeglobals('[General]\nAccentColor=nope'), isNull);
  });
}
