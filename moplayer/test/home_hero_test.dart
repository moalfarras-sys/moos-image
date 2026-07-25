// The home page opens with a hero. Which one, and — the case this file exists
// for — whether there is one at all.
//
// A plain M3U playlist is live-only: no VOD endpoint, no series, and on a first
// run no watch history. Both of the original heroes (resume, top-rated film) are
// therefore null for it, and the landing page rendered a single rail above a
// screenful of black. That is not an edge case; it is the most common kind of
// IPTV source there is.

import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:moplayer_moos/core/l10n/strings.dart';
import 'package:moplayer_moos/features/home/home_screen.dart';
import 'package:moplayer_moos/models/live_channel.dart';

LiveChannel _ch(String name, {String? logo}) => LiveChannel(
  streamId: name,
  name: name,
  logo: logo,
  directUrl: 'http://x/$name',
);

void main() {
  group('pickLiveHero', () {
    test('a live-only catalogue still gets a hero', () {
      final hero = pickLiveHero([_ch('One'), _ch('Two')]);
      expect(
        hero,
        isNotNull,
        reason: 'an M3U source must not open on an empty page',
      );
      expect(hero!.name, 'One');
    });

    test('a channel with a logo wins — a monogram hero looks unfinished', () {
      final hero = pickLiveHero([
        _ch('No logo'),
        _ch('Blank logo', logo: '   '),
        _ch('Has logo', logo: 'http://x/logo.png'),
      ]);
      expect(hero!.name, 'Has logo');
    });

    test('no channels, no hero — the empty state owns that page', () {
      expect(pickLiveHero(const []), isNull);
    });
  });

  // "5 قناة" is the sentence a machine writes. Arabic counts its nouns, and the
  // hero's own subtitle is the first place a user would see it get this wrong.
  group('the channel count is counted in Arabic', () {
    const ar = S(Lang.ar);

    test('one is a word, two is a dual', () {
      expect(ar.liveChannelsAvailable(1), 'قناة واحدة متاحة');
      expect(ar.liveChannelsAvailable(2), 'قناتان متاحتان');
    });

    test('3–10 take the plural', () {
      expect(ar.liveChannelsAvailable(5), '5 قنوات متاحة');
      expect(ar.liveChannelsAvailable(10), '10 قنوات متاحة');
    });

    test('11 and up go back to the singular', () {
      expect(ar.liveChannelsAvailable(11), '11 قناة متاحة');
      expect(ar.liveChannelsAvailable(240), '240 قناة متاحة');
    });

    test('English and German only ever need the two', () {
      expect(const S(Lang.en).liveChannelsAvailable(1), '1 channel available');
      expect(const S(Lang.en).liveChannelsAvailable(5), '5 channels available');
      expect(const S(Lang.de).liveChannelsAvailable(5), '5 Sender verfügbar');
    });
  });

  // The function above can be perfect and the page still open on black: all it
  // takes is for the branch that renders it to be dropped. A test that only
  // exercises the decision would stay green through exactly that regression —
  // so this one reads the page and checks the decision is actually wired to a
  // hero, with the logo passed as a *mark* and not as the backdrop.
  test('the page renders the live hero, and hands it the logo as a mark', () {
    final src = File('lib/features/home/home_screen.dart').readAsStringSync();
    final code = src
        .split('\n')
        .where((l) => !l.trimLeft().startsWith('//'))
        .join('\n');

    expect(code, contains('pickLiveHero(live)'));
    expect(
      code,
      contains('logoUrl: liveHero.logo'),
      reason: 'a live hero without its logo is a plate with a name on it',
    );
    expect(
      code,
      isNot(contains('imageUrl: liveHero.logo')),
      reason: 'a channel logo stretched across a hero backdrop is beheaded',
    );
  });
}
