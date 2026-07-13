// The wheel belongs to the page.
//
// The rail used to turn a vertical wheel into sideways movement, handing the
// event back only once the shelf hit its end. The home page is a *column* of
// shelves — wherever the cursor rests, it rests on one — so every attempt to
// scroll the page dragged a shelf sideways instead, and everything below the
// fold was unreachable. The owner reported it as "I cannot scroll down".
//
// This is the test that stops it coming back. It builds the real shape: a
// vertical page with a rail inside it, puts the pointer over the rail, and turns
// the wheel.

import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:moplayer_moos/widgets/media_rail.dart';

Widget _page(ScrollController pageController) => MaterialApp(
  home: Scaffold(
    body: ListView(
      controller: pageController,
      children: [
        const SizedBox(height: 400),
        MediaRail(
          title: 'Newest',
          itemCount: 40,
          itemWidth: 150,
          height: 260,
          itemBuilder: (context, i) => ColoredBox(
            color: Colors.grey,
            child: Center(child: Text('$i')),
          ),
        ),
        const SizedBox(height: 900),
      ],
    ),
  ),
);

void main() {
  testWidgets('a wheel over a rail scrolls the PAGE, not the shelf', (
    tester,
  ) async {
    final page = ScrollController();
    addTearDown(page.dispose);

    await tester.pumpWidget(_page(page));
    await tester.pumpAndSettle();

    // The pointer sits squarely on the shelf.
    final rail = find.byType(MediaRail);
    expect(rail, findsOneWidget);
    final over = tester.getCenter(rail);

    final before = page.position.pixels;

    final pointer = TestPointer(1, PointerDeviceKind.mouse);
    pointer.hover(over);
    await tester.sendEventToBinding(pointer.scroll(const Offset(0, 220)));
    await tester.pumpAndSettle();

    expect(
      page.position.pixels,
      greaterThan(before),
      reason: 'the page did not move — the shelf ate the wheel again',
    );
  });

  testWidgets('the shelf itself does not move under a plain wheel', (
    tester,
  ) async {
    final page = ScrollController();
    addTearDown(page.dispose);

    await tester.pumpWidget(_page(page));
    await tester.pumpAndSettle();

    // The rail's own list — the only horizontal Scrollable on screen.
    final railList = find.byWidgetPredicate(
      (w) => w is Scrollable && w.axisDirection == AxisDirection.right,
    );
    expect(railList, findsOneWidget);
    final position = tester.state<ScrollableState>(railList).position;
    final before = position.pixels;

    final pointer = TestPointer(1, PointerDeviceKind.mouse);
    pointer.hover(tester.getCenter(find.byType(MediaRail)));
    await tester.sendEventToBinding(pointer.scroll(const Offset(0, 220)));
    await tester.pumpAndSettle();

    expect(
      position.pixels,
      before,
      reason: 'a plain wheel moved the shelf sideways — that is the whole bug',
    );
  });
}
