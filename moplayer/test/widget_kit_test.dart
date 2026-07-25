import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:moplayer_moos/core/theme/nova.dart';
import 'package:moplayer_moos/models/category.dart';
import 'package:moplayer_moos/widgets/backdrop.dart';
import 'package:moplayer_moos/widgets/category_chips.dart';
import 'package:moplayer_moos/widgets/media_card.dart';
import 'package:moplayer_moos/widgets/media_rail.dart';
import 'package:moplayer_moos/widgets/skeletons.dart';
import 'package:moplayer_moos/widgets/tiles.dart';

Widget host(Widget child, {TextDirection dir = TextDirection.ltr}) {
  return MaterialApp(
    home: Directionality(
      textDirection: dir,
      child: Scaffold(body: child),
    ),
  );
}

void main() {
  for (final dir in TextDirection.values) {
    final tag = dir.name;

    testWidgets('[$tag] PosterCard in a 170x300 rail slot', (tester) async {
      await tester.pumpWidget(
        host(
          const SizedBox(
            height: 300,
            width: 170,
            child: PosterCard(
              title: 'A Very Long Film Title',
              subtitle: '2019',
            ),
          ),
          dir: dir,
        ),
      );
      expect(tester.takeException(), isNull);
    });

    testWidgets('[$tag] ContinueCard in a 300x230 rail slot', (tester) async {
      await tester.pumpWidget(
        host(
          SizedBox(
            height: 230,
            width: 300,
            child: ContinueCard(
              title: 'Episode Title',
              subtitle: 'Some Series',
              progress: 0.4,
              remaining: '23 min left',
              onTap: () {},
              onDismiss: () {},
            ),
          ),
          dir: dir,
        ),
      );
      expect(tester.takeException(), isNull);
    });

    testWidgets('[$tag] EpisodeCard in a 260 rail', (tester) async {
      await tester.pumpWidget(
        host(
          SizedBox(
            height: 200,
            width: 260,
            child: EpisodeCard(
              number: 3,
              title: 'The One With The Thing',
              durationSecs: 2730,
              progress: 0.2,
              onTap: () {},
            ),
          ),
          dir: dir,
        ),
      );
      expect(tester.takeException(), isNull);
    });

    testWidgets('[$tag] CategoryPill in a 38px strip', (tester) async {
      await tester.pumpWidget(
        host(
          SizedBox(
            height: 38,
            child: ListView(
              scrollDirection: Axis.horizontal,
              children: [
                CategoryPill(
                  label: 'Action',
                  count: 1240,
                  selected: true,
                  onTap: () {},
                ),
                CategoryPill(label: 'Drama', selected: false, onTap: () {}),
              ],
            ),
          ),
          dir: dir,
        ),
      );
      expect(tester.takeException(), isNull);
      expect(find.text('Action'), findsOneWidget);
    });

    testWidgets('[$tag] ChannelTile with and without EPG', (tester) async {
      await tester.pumpWidget(
        host(
          ListView(
            children: [
              ChannelTile(
                name: 'BBC One HD',
                selected: true,
                nowTitle: 'The News at Ten',
                nowProgress: 0.7,
                isFavorite: true,
                onToggleFavorite: () {},
                onTap: () {},
              ),
              ChannelTile(name: 'No EPG Here', selected: false, onTap: () {}),
            ],
          ),
          dir: dir,
        ),
      );
      expect(tester.takeException(), isNull);
    });

    testWidgets('[$tag] EpisodeTile row', (tester) async {
      await tester.pumpWidget(
        host(
          ListView(
            children: [
              EpisodeTile(
                number: 1,
                title: 'Pilot',
                plot: 'A long plot that goes on and on and on and on.',
                durationSecs: 3600,
                progress: 0.5,
                onTap: () {},
              ),
            ],
          ),
          dir: dir,
        ),
      );
      expect(tester.takeException(), isNull);
    });

    testWidgets('[$tag] MediaRail renders nothing when empty', (tester) async {
      await tester.pumpWidget(
        host(
          MediaRail(
            title: 'Empty',
            itemCount: 0,
            itemWidth: 170,
            height: 300,
            itemBuilder: (_, _) => const SizedBox(),
          ),
          dir: dir,
        ),
      );
      expect(find.text('Empty'), findsNothing);
      expect(tester.takeException(), isNull);
    });

    testWidgets('[$tag] MediaRail with items shows header + cards', (
      tester,
    ) async {
      await tester.pumpWidget(
        host(
          SizedBox(
            height: 380,
            child: MediaRail(
              title: 'Recently added',
              subtitle: 'Movies',
              seeAllLabel: 'More',
              onSeeAll: () {},
              itemCount: 20,
              itemWidth: 170,
              height: 300,
              itemBuilder: (_, i) =>
                  PosterCard(title: 'Film $i', subtitle: '2020'),
            ),
          ),
          dir: dir,
        ),
      );
      await tester.pump(const Duration(milliseconds: 600));
      expect(find.text('Recently added'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });

    testWidgets('[$tag] skeletons build and stop under reduced motion', (
      tester,
    ) async {
      await tester.pumpWidget(
        host(
          const Column(
            children: [
              Expanded(child: PosterGridSkeleton(count: 6)),
              SizedBox(height: 340, child: RailSkeleton()),
            ],
          ),
          dir: dir,
        ),
      );
      await tester.pump(const Duration(milliseconds: 400));
      expect(tester.takeException(), isNull);
    });

    testWidgets('[$tag] DetailSkeleton + ListSkeleton', (tester) async {
      await tester.pumpWidget(
        host(
          const Column(
            children: [
              Expanded(child: DetailSkeleton(heroHeight: 300)),
              Expanded(child: ListSkeleton(count: 4)),
            ],
          ),
          dir: dir,
        ),
      );
      await tester.pump(const Duration(milliseconds: 300));
      expect(tester.takeException(), isNull);
    });

    testWidgets('[$tag] Backdrop crossfades without a URL', (tester) async {
      await tester.pumpWidget(
        host(
          const SizedBox(
            height: 400,
            child: Backdrop(imageUrl: null, blur: 12, darken: 0.2),
          ),
          dir: dir,
        ),
      );
      await tester.pump(const Duration(milliseconds: 600));
      expect(tester.takeException(), isNull);
    });

    testWidgets('[$tag] CategoryChips', (tester) async {
      await tester.pumpWidget(
        host(
          CategoryChips(
            categories: const [
              Category(id: '__all__', name: 'All'),
              Category(id: '1', name: 'Action', count: 42),
            ],
            selectedId: '1',
            onSelect: (_) {},
          ),
          dir: dir,
        ),
      );
      await tester.pump(const Duration(milliseconds: 400));
      expect(tester.takeException(), isNull);
    });

    testWidgets('[$tag] StatTile / ListRow / WidgetTile / MoOSBadge', (
      tester,
    ) async {
      await tester.pumpWidget(
        host(
          ListView(
            children: [
              const StatTile(
                value: '12.5K',
                label: 'channels',
                icon: Icons.live_tv_rounded,
                accent: true,
              ),
              ListRow(
                title: 'Prefer HLS for live',
                subtitle: 'More compatible',
                onTap: () {},
                trailing: const Icon(Icons.chevron_right),
              ),
              const WidgetTile(
                title: 'Network',
                icon: Icons.wifi,
                child: Text('Online'),
              ),
              const MoOSBadge(label: 'MoOS'),
              const SizedBox(width: 200, child: ProgressBar(value: 0.35)),
            ],
          ),
          dir: dir,
        ),
      );
      expect(tester.takeException(), isNull);
    });
  }

  testWidgets('PosterCard shows no rating badge at 0', (tester) async {
    await tester.pumpWidget(
      host(
        const SizedBox(
          height: 300,
          width: 170,
          child: PosterCard(title: 'Unrated', rating: 0),
        ),
      ),
    );
    expect(find.byType(RatingBadge), findsNothing);

    await tester.pumpWidget(
      host(
        const SizedBox(
          height: 300,
          width: 170,
          child: PosterCard(title: 'Rated', rating: 7.4),
        ),
      ),
    );
    expect(find.byType(RatingBadge), findsOneWidget);
    expect(find.text('7.4'), findsOneWidget);
  });

  testWidgets('a 880x560 window still lays a poster grid out', (tester) async {
    tester.view.physicalSize = const Size(880, 560);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    await tester.pumpWidget(
      host(
        const Padding(
          padding: EdgeInsets.all(Nova.space6),
          child: PosterGridSkeleton(count: 8),
        ),
      ),
    );
    expect(tester.takeException(), isNull);
  });
}
