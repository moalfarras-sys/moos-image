import 'package:flutter/material.dart';
import 'package:flutter/scheduler.dart';

import '../core/theme/app_colors.dart';
import '../core/theme/motion.dart';
import '../core/theme/nova.dart';

/// One clock for every skeleton on screen.
///
/// The obvious implementation gives each shimmering box its own
/// [AnimationController]. A poster grid is forty cards of three boxes each, so
/// the obvious implementation is a hundred and twenty tickers, a hundred and
/// twenty `setState`s per frame, and a loading screen that is measurably more
/// expensive than the content it is standing in for.
///
/// This is one ticker, one [ValueNotifier], and a reference count. It also means
/// every skeleton on screen shimmers *in phase*, which is what makes the wall
/// read as one surface catching the light rather than as forty blinking boxes.
class _ShimmerClock {
  const _ShimmerClock._();

  static const Duration period = Duration(milliseconds: 1400);

  static final ValueNotifier<double> phase = ValueNotifier<double>(0);
  static Ticker? _ticker;
  static int _refs = 0;

  static void attach() {
    _refs++;
    _ticker ??= Ticker(_tick)..start();
  }

  static void detach() {
    _refs--;
    if (_refs > 0) return;
    _refs = 0;
    _ticker?.dispose();
    _ticker = null;
    phase.value = 0;
  }

  static void _tick(Duration elapsed) {
    phase.value =
        (elapsed.inMilliseconds % period.inMilliseconds) /
        period.inMilliseconds;
  }
}

/// Slides the shimmer band across the box.
class _Sweep extends GradientTransform {
  const _Sweep(this.t, this.rtl);

  final double t;
  final bool rtl;

  @override
  Matrix4 transform(Rect bounds, {TextDirection? textDirection}) {
    // -1 → 1 of the box's width, so the band enters off one edge and leaves off
    // the other instead of fading in over the middle.
    final travel = bounds.width * (t * 2 - 1);
    return Matrix4.translationValues(rtl ? -travel : travel, 0, 0);
  }
}

/// A shimmering placeholder box — the atom every skeleton below is built from.
///
/// Under reduced motion it stops moving and becomes a plain plate. It never
/// becomes *nothing*: the shape is the promise about what is coming, and that
/// promise is the whole point of a skeleton.
class SkeletonBox extends StatefulWidget {
  const SkeletonBox({
    super.key,
    this.width = double.infinity,
    this.height = 16,
    this.radius = Nova.radiusControl,
  });

  final double width;
  final double height;
  final double radius;

  @override
  State<SkeletonBox> createState() => _SkeletonBoxState();
}

class _SkeletonBoxState extends State<SkeletonBox> {
  bool _attached = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _setAttached(!Motion.isReduced(context));
  }

  @override
  void dispose() {
    _setAttached(false);
    super.dispose();
  }

  void _setAttached(bool value) {
    if (value == _attached) return;
    _attached = value;
    if (value) {
      _ShimmerClock.attach();
    } else {
      _ShimmerClock.detach();
    }
  }

  @override
  Widget build(BuildContext context) {
    final radius = BorderRadius.circular(widget.radius);
    final rtl = Directionality.of(context) == TextDirection.rtl;

    if (!_attached) {
      return Container(
        width: widget.width,
        height: widget.height,
        decoration: BoxDecoration(color: AppColors.surface2, borderRadius: radius),
      );
    }

    return RepaintBoundary(
      child: ValueListenableBuilder<double>(
        valueListenable: _ShimmerClock.phase,
        builder: (context, t, _) => Container(
          width: widget.width,
          height: widget.height,
          decoration: BoxDecoration(
            borderRadius: radius,
            gradient: LinearGradient(
              begin: Alignment.centerLeft,
              end: Alignment.centerRight,
              colors: const [
                AppColors.surface2,
                AppColors.surface3,
                AppColors.surface2,
              ],
              stops: const [0.15, 0.5, 0.85],
              transform: _Sweep(t, rtl),
            ),
          ),
        ),
      ),
    );
  }
}

/// The skeleton of one poster: artwork, a title line, a metadata line. The exact
/// shape of a [PosterCard], to the pixel, so that nothing moves when the real
/// cards land on top of it.
class PosterCardSkeleton extends StatelessWidget {
  const PosterCardSkeleton({super.key, this.aspectRatio = 2 / 3});

  final double aspectRatio;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        AspectRatio(
          aspectRatio: aspectRatio,
          child: const SkeletonBox(radius: Nova.radiusCard),
        ),
        const SizedBox(height: Nova.space2),
        const SkeletonBox(width: 108, height: 12, radius: 4),
        const SizedBox(height: Nova.space1 + 2),
        const SkeletonBox(width: 52, height: 9, radius: 4),
      ],
    );
  }
}

/// The 16:9 counterpart.
class LandscapeCardSkeleton extends StatelessWidget {
  const LandscapeCardSkeleton({super.key});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        const AspectRatio(
          aspectRatio: 16 / 9,
          child: SkeletonBox(radius: Nova.radiusCard),
        ),
        const SizedBox(height: Nova.space3),
        const SkeletonBox(width: 132, height: 12, radius: 4),
        const SizedBox(height: Nova.space1 + 2),
        const SkeletonBox(width: 64, height: 9, radius: 4),
      ],
    );
  }
}

/// A poster wall, loading. The column count is derived exactly as the real grid
/// derives it, so the skeleton and the content agree about the layout.
class PosterGridSkeleton extends StatelessWidget {
  const PosterGridSkeleton({
    super.key,
    this.count = 18,
    this.maxItemWidth = 190,
    this.spacing = Nova.space4,
    this.aspectRatio = 2 / 3,
    this.labelHeight = 48,
    this.padding,
    this.scrollable = true,
  });

  final int count;
  final double maxItemWidth;
  final double spacing;
  final double aspectRatio;

  /// The room a card's two lines of type take under its artwork.
  final double labelHeight;

  final EdgeInsetsGeometry? padding;

  /// Off when the skeleton is dropped inside a page that already scrolls.
  final bool scrollable;

  @override
  Widget build(BuildContext context) {
    final dock = MediaQuery.paddingOf(context).bottom;

    return LayoutBuilder(
      builder: (context, constraints) {
        final width = constraints.maxWidth;
        final columns = (width / (maxItemWidth + spacing)).floor().clamp(2, 12);
        final itemWidth = (width - spacing * (columns - 1)) / columns;
        final extent = itemWidth / aspectRatio + labelHeight;

        return GridView.builder(
          padding:
              padding ??
              EdgeInsets.only(bottom: dock + Nova.space5, top: Nova.space1),
          // A skeleton is never scrolled: there is nothing under the fold of a
          // thing that does not exist yet.
          physics: const NeverScrollableScrollPhysics(),
          shrinkWrap: !scrollable,
          gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: columns,
            mainAxisSpacing: spacing,
            crossAxisSpacing: spacing,
            mainAxisExtent: extent,
          ),
          itemCount: count,
          itemBuilder: (context, _) =>
              PosterCardSkeleton(aspectRatio: aspectRatio),
        );
      },
    );
  }
}

/// A shelf, loading — header line included, because the header is part of the
/// shape and a skeleton that omits it makes the page jump when it arrives.
class RailSkeleton extends StatelessWidget {
  const RailSkeleton({
    super.key,
    this.itemWidth = 170,
    this.height = 300,
    this.count = 6,
    this.aspectRatio = 2 / 3,
    this.spacing = Nova.space4,
    this.header = true,
  });

  final double itemWidth;
  final double height;
  final int count;
  final double aspectRatio;
  final double spacing;
  final bool header;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        if (header) ...[
          const SkeletonBox(width: 160, height: 17, radius: 5),
          const SizedBox(height: Nova.space3 + 2),
        ],
        SizedBox(
          height: height,
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            physics: const NeverScrollableScrollPhysics(),
            padding: EdgeInsets.zero,
            itemCount: count,
            separatorBuilder: (_, _) => SizedBox(width: spacing),
            itemBuilder: (context, _) => SizedBox(
              width: itemWidth,
              child: PosterCardSkeleton(aspectRatio: aspectRatio),
            ),
          ),
        ),
      ],
    );
  }
}

/// A list of rows, loading — a channel list, a search result, a season.
class ListSkeleton extends StatelessWidget {
  const ListSkeleton({
    super.key,
    this.count = 10,
    this.rowHeight = 60,
    this.leadingWidth = 42,
    this.padding,
    this.scrollable = true,
  });

  final int count;
  final double rowHeight;

  /// The logo or thumbnail at the leading edge. Zero for a plain list.
  final double leadingWidth;

  final EdgeInsetsGeometry? padding;
  final bool scrollable;

  @override
  Widget build(BuildContext context) {
    final dock = MediaQuery.paddingOf(context).bottom;

    return ListView.separated(
      padding: padding ?? EdgeInsets.only(bottom: dock + Nova.space5),
      physics: const NeverScrollableScrollPhysics(),
      shrinkWrap: !scrollable,
      itemCount: count,
      separatorBuilder: (_, _) => const SizedBox(height: Nova.space2),
      itemBuilder: (context, _) => SizedBox(
        height: rowHeight,
        child: Row(
          children: [
            if (leadingWidth > 0) ...[
              SkeletonBox(
                width: leadingWidth,
                height: leadingWidth,
                radius: Nova.radiusControl - 2,
              ),
              const SizedBox(width: Nova.space3),
            ],
            const Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  SkeletonBox(width: 200, height: 12, radius: 4),
                  SizedBox(height: Nova.space2),
                  SkeletonBox(width: 120, height: 9, radius: 4),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// A detail page, loading: the hero, the poster, the title block, the actions.
///
/// This is the skeleton that matters most. A film's detail page is the one
/// screen a user opens *expecting* to wait, and the one where a bare spinner on
/// black looks most like a crash.
class DetailSkeleton extends StatelessWidget {
  const DetailSkeleton({super.key, this.heroHeight = 420});

  final double heroHeight;

  @override
  Widget build(BuildContext context) {
    final dock = MediaQuery.paddingOf(context).bottom;

    return SingleChildScrollView(
      physics: const NeverScrollableScrollPhysics(),
      padding: EdgeInsets.only(bottom: dock + Nova.space5),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            height: heroHeight,
            child: Stack(
              fit: StackFit.expand,
              children: [
                const SkeletonBox(radius: 0),
                // The floor, so the hero does not end at a hard line — exactly as
                // the real one does not.
                const DecoratedBox(
                  decoration: BoxDecoration(gradient: AppColors.heroFloor),
                ),
                PositionedDirectional(
                  start: Nova.space6,
                  end: Nova.space6,
                  bottom: Nova.space6,
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      const SizedBox(
                        width: 180,
                        child: AspectRatio(
                          aspectRatio: 2 / 3,
                          child: SkeletonBox(radius: Nova.radiusCard),
                        ),
                      ),
                      const SizedBox(width: Nova.space5),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            const SkeletonBox(width: 320, height: 30, radius: 6),
                            const SizedBox(height: Nova.space3),
                            const SkeletonBox(width: 200, height: 12, radius: 4),
                            const SizedBox(height: Nova.space5),
                            Row(
                              children: const [
                                SkeletonBox(
                                  width: 132,
                                  height: 44,
                                  radius: Nova.radiusControl,
                                ),
                                SizedBox(width: Nova.space3),
                                SkeletonBox(
                                  width: 108,
                                  height: 44,
                                  radius: Nova.radiusControl,
                                ),
                              ],
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          const Padding(
            padding: EdgeInsets.all(Nova.space6),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                SkeletonBox(height: 12, radius: 4),
                SizedBox(height: Nova.space3),
                SkeletonBox(height: 12, radius: 4),
                SizedBox(height: Nova.space3),
                SkeletonBox(width: 260, height: 12, radius: 4),
                SizedBox(height: Nova.space6),
                RailSkeleton(itemWidth: 150, height: 265, count: 5),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
