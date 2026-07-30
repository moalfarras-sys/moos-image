import 'dart:io';
import 'dart:ui' show Tristate;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:moplayer_moos/app/window_chrome.dart';
import 'package:moplayer_moos/core/l10n/strings.dart';
import 'package:moplayer_moos/core/theme/app_colors.dart';
import 'package:moplayer_moos/core/theme/app_theme.dart';
import 'package:moplayer_moos/core/theme/motion.dart';
import 'package:moplayer_moos/features/auth/login_screen.dart';
import 'package:moplayer_moos/providers/system_providers.dart';
import 'package:moplayer_moos/widgets/accessible_visibility.dart';
import 'package:moplayer_moos/widgets/app_logo.dart';
import 'package:moplayer_moos/widgets/buttons.dart';
import 'package:moplayer_moos/widgets/tiles.dart';

double _contrast(Color a, Color b) {
  final light = a.computeLuminance();
  final dark = b.computeLuminance();
  final high = light > dark ? light : dark;
  final low = light > dark ? dark : light;
  return (high + 0.05) / (low + 0.05);
}

Widget _providerHost({
  required Widget child,
  required S strings,
  required TextDirection direction,
}) {
  return ProviderScope(
    overrides: [stringsProvider.overrideWithValue(strings)],
    child: MaterialApp(
      theme: AppTheme.dark,
      home: Directionality(
        textDirection: direction,
        child: Scaffold(body: child),
      ),
    ),
  );
}

void main() {
  group('ember foreground contrast', () {
    test('one token clears WCAG AA at every gradient stop', () {
      for (final stop in AppColors.emberGradient.colors) {
        expect(
          _contrast(AppColors.onEmber, stop),
          greaterThanOrEqualTo(4.5),
          reason:
              'onEmber must remain readable on #'
              '${stop.toARGB32().toRadixString(16)}',
        );
      }
    });

    test('Material primary controls use the same foreground token', () {
      expect(AppTheme.dark.colorScheme.onPrimary, AppColors.onEmber);
    });

    testWidgets('shared gradient controls consume the token', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.dark,
          home: Scaffold(
            body: Column(
              children: [
                EmberButton(
                  label: 'Play',
                  icon: Icons.play_arrow_rounded,
                  onPressed: () {},
                ),
                CategoryPill(label: 'Selected', selected: true, onTap: () {}),
                IconPill(
                  icon: Icons.add_rounded,
                  filled: true,
                  tooltip: 'Add',
                  onPressed: () {},
                ),
              ],
            ),
          ),
        ),
      );

      expect(
        tester.widget<Text>(find.text('Play')).style?.color,
        AppColors.onEmber,
      );
      expect(
        tester.widget<Text>(find.text('Selected')).style?.color,
        AppColors.onEmber,
      );
      expect(
        tester.widget<Icon>(find.byIcon(Icons.add_rounded)).color,
        AppColors.onEmber,
      );
    });
  });

  group('hidden interactive regions', () {
    testWidgets('hidden descendants leave focus and semantics together', (
      tester,
    ) async {
      final hiddenFocus = FocusNode(debugLabel: 'hidden-action');
      final visibleFocus = FocusNode(debugLabel: 'visible-action');
      addTearDown(hiddenFocus.dispose);
      addTearDown(visibleFocus.dispose);

      Future<void> pump({required bool visible}) {
        return tester.pumpWidget(
          MaterialApp(
            home: Column(
              children: [
                AccessibleVisibility(
                  visible: visible,
                  child: TextButton(
                    focusNode: hiddenFocus,
                    onPressed: () {},
                    child: const Text('Hidden action'),
                  ),
                ),
                TextButton(
                  focusNode: visibleFocus,
                  onPressed: () {},
                  child: const Text('Visible action'),
                ),
              ],
            ),
          ),
        );
      }

      await pump(visible: false);
      expect(find.bySemanticsLabel('Hidden action'), findsNothing);
      expect(find.bySemanticsLabel('Visible action'), findsOneWidget);
      hiddenFocus.requestFocus();
      await tester.pump();
      expect(hiddenFocus.hasFocus, isFalse);

      await pump(visible: true);
      expect(find.bySemanticsLabel('Hidden action'), findsOneWidget);
      hiddenFocus.requestFocus();
      await tester.pump();
      expect(hiddenFocus.hasFocus, isTrue);
    });
  });

  group('frameless window chrome', () {
    test('window chrome has no borrowed traffic-light palette or glyphs', () {
      final source = File('lib/app/window_chrome.dart').readAsStringSync();
      for (final borrowedColor in ['FF5F57', 'FEBC2E', '28C840']) {
        expect(source, isNot(contains(borrowedColor)));
      }
      for (final borrowedGlyph in [
        'Icons.close_rounded',
        'Icons.remove_rounded',
        'Icons.open_in_full_rounded',
        'Icons.close_fullscreen_rounded',
      ]) {
        expect(source, isNot(contains(borrowedGlyph)));
      }
      expect(source, contains('class _WindowGlyphPainter'));
    });

    testWidgets('login frame always supplies caption and resize edges', (
      tester,
    ) async {
      const strings = S(Lang.en);
      await tester.pumpWidget(
        _providerHost(
          strings: strings,
          direction: TextDirection.ltr,
          child: const FramelessWindowFrame(
            child: ColoredBox(color: AppColors.surface0),
          ),
        ),
      );

      expect(find.byType(WindowCaption), findsOneWidget);
      expect(find.byType(ResizeEdges), findsOneWidget);
      expect(find.bySemanticsLabel(strings.windowClose), findsOneWidget);
      expect(find.bySemanticsLabel(strings.windowMinimize), findsOneWidget);
      expect(find.bySemanticsLabel(strings.windowMaximize), findsOneWidget);
    });

    testWidgets('window actions stay physical-left and at least 40 px', (
      tester,
    ) async {
      final rects = <TextDirection, List<Rect>>{};

      for (final direction in TextDirection.values) {
        final strings = S(direction == TextDirection.rtl ? Lang.ar : Lang.en);
        await tester.pumpWidget(
          _providerHost(
            strings: strings,
            direction: direction,
            child: const Align(
              alignment: Alignment.topCenter,
              child: WindowCaption(),
            ),
          ),
        );

        final labels = [
          strings.windowClose,
          strings.windowMinimize,
          strings.windowMaximize,
        ];
        rects[direction] = [
          for (final label in labels)
            tester.getRect(find.bySemanticsLabel(label)),
        ];

        for (final rect in rects[direction]!) {
          expect(rect.width, greaterThanOrEqualTo(40));
          expect(rect.height, greaterThanOrEqualTo(40));
          expect(
            rect.right,
            lessThanOrEqualTo(WindowCaption.windowControlsWidth),
          );
        }
      }

      final ltr = rects[TextDirection.ltr]!;
      final rtl = rects[TextDirection.rtl]!;
      for (var index = 0; index < ltr.length; index++) {
        expect(rtl[index].left, closeTo(ltr[index].left, 0.01));
        expect(rtl[index].top, closeTo(ltr[index].top, 0.01));
      }
    });
  });

  group('login method tabs', () {
    for (final direction in TextDirection.values) {
      testWidgets('${direction.name}: arrows select and focus the visual peer', (
        tester,
      ) async {
        final strings = S(direction == TextDirection.rtl ? Lang.ar : Lang.en);

        tester.view.physicalSize = const Size(1000, 900);
        tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);

        await tester.pumpWidget(
          _providerHost(
            strings: strings,
            direction: direction,
            child: const LoginScreen(),
          ),
        );

        final methodNodes = tester
            .widgetList<FocusableActionDetector>(
              find.byType(FocusableActionDetector),
            )
            .map((widget) => widget.focusNode)
            .whereType<FocusNode>()
            .where(
              (node) => node.debugLabel?.startsWith('login-method-') == true,
            )
            .toList();
        expect(methodNodes, hasLength(3));

        methodNodes.first.requestFocus();
        await tester.pump();
        await tester.sendKeyEvent(
          direction == TextDirection.rtl
              ? LogicalKeyboardKey.arrowLeft
              : LogicalKeyboardKey.arrowRight,
        );
        await tester.pump();

        expect(methodNodes[1].hasFocus, isTrue);
        final selected = tester.getSemantics(
          find.bySemanticsLabel(strings.m3u),
        );
        expect(selected.flagsCollection.isButton, isTrue);
        expect(selected.flagsCollection.isSelected, Tristate.isTrue);
        expect(selected.flagsCollection.isFocused, Tristate.isTrue);
        expect(find.text(strings.m3uHint), findsOneWidget);

        // Activation is not pointer-only: Enter on an unselected tab selects it.
        methodNodes.first.requestFocus();
        await tester.pump();
        await tester.sendKeyEvent(LogicalKeyboardKey.enter);
        await tester.pump();
        expect(find.text(strings.xtreamHint), findsOneWidget);
      });
    }
  });

  group('localized identity and reduced motion', () {
    testWidgets('the visible tagline follows Arabic shaping and copy', (
      tester,
    ) async {
      const strings = S(Lang.ar);
      await tester.pumpWidget(
        _providerHost(
          strings: strings,
          direction: TextDirection.rtl,
          child: const AppLogo(showTagline: true, tagline: 'من Moalfarras'),
        ),
      );
      expect(find.text(strings.appTagline), findsOneWidget);
      expect(find.text('by Moalfarras'), findsNothing);
    });

    testWidgets('reduced motion shortens fades and removes lift', (
      tester,
    ) async {
      late Duration duration;
      late double lift;
      await tester.pumpWidget(
        MaterialApp(
          home: Motion(
            reduced: true,
            child: Builder(
              builder: (context) {
                duration = Motion.duration(
                  context,
                  const Duration(milliseconds: 280),
                );
                lift = Motion.lift(context, 1.08);
                return const SizedBox();
              },
            ),
          ),
        ),
      );
      expect(duration, const Duration(milliseconds: 60));
      expect(lift, 1);
    });

    test('the seven audited transitions cannot bypass Motion again', () {
      final paths = [
        'lib/features/auth/login_screen.dart',
        'lib/features/live/live_screen.dart',
        'lib/features/player/player_overlay.dart',
      ];
      for (final path in paths) {
        final source = File(path).readAsStringSync();
        expect(
          RegExp(r'duration:\s*Nova\.').hasMatch(source),
          isFalse,
          reason:
              '$path has a direct Nova duration that ignores reduced motion',
        );
      }

      final router = File('lib/app/router.dart').readAsStringSync();
      expect(router, contains('transitionDuration: Motion.duration('));
      final overlay = File(
        'lib/features/player/player_overlay.dart',
      ).readAsStringSync();
      expect(overlay, contains('optionsVisible || Motion.isReduced(context)'));
    });
  });
}
