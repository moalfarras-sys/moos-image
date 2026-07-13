import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
// window_manager ships a `WindowCaption` of its own — a GNOME-looking bar we
// explicitly do not want. Hidden so that `WindowCaption` in this file is
// unambiguously MoPlayer's.
import 'package:window_manager/window_manager.dart' hide WindowCaption;

import '../core/constants/app_constants.dart';
import '../core/theme/app_colors.dart';
import '../core/theme/glass.dart';
import '../core/theme/motion.dart';
import '../core/theme/nova.dart';
import '../features/player/mini_player.dart';
import '../features/player/player_overlay.dart';
import '../providers/core_providers.dart';
import '../providers/playback_providers.dart';
import '../providers/shell_providers.dart';
import '../providers/system_providers.dart';
import '../services/system/desktop_service.dart';
import '../widgets/glass_dock.dart';
import '../widgets/mo_icons.dart';
import 'launch_args.dart';
import 'routes.dart';
import 'window_chrome.dart';

/// The frame every screen lives in.
///
/// Four layers, bottom to top:
///
///  1. **The ambient scene** — the warm graphite wash, the amber bloom, the
///     vignette and the grain. Drawn once, behind everything.
///  2. **The caption bar and the page.** The page scrolls *under* the dock, and
///     is given the dock's height as bottom padding so its last row can always
///     be scrolled clear of it. That padding is the price of a floating bar and
///     the shell pays it, so that no screen has to remember to.
///  3. **The floating glass dock**, and the mini player above it.
///  4. **The player**, when it is expanded — which covers all of the above,
///     because it is the one screen that is meant to be the whole machine.
class MainShell extends ConsumerStatefulWidget {
  const MainShell({super.key, required this.child});

  final Widget child;

  @override
  ConsumerState<MainShell> createState() => _MainShellState();
}

class _MainShellState extends ConsumerState<MainShell> with WindowListener {
  /// Owned here, not by the dock: F6 has to move focus onto the *selected*
  /// destination, and the dock is rebuilt on every navigation.
  final List<FocusNode> _dockNodes = List.generate(
    6,
    (i) => FocusNode(debugLabel: 'dock-$i'),
  );

  /// Where focus was before it jumped to the dock, so that Escape can put it
  /// back where the user left it rather than at the top of the page.
  FocusNode? _contentFocus;

  @override
  void initState() {
    super.initState();
    windowManager.addListener(this);

    // `moplayer https://…/master.m3u8` starts playing as soon as there is a
    // frame to play into. Not in `main()`: the player has to be able to raise
    // its overlay, which means the shell has to exist first.
    final url = ref.read(launchArgsProvider).playUrl;
    if (url != null) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        ref.read(playbackProvider.notifier).playDirect(url);
      });
    }
  }

  @override
  void dispose() {
    _geometryDebounce?.cancel();
    windowManager.removeListener(this);
    for (final node in _dockNodes) {
      node.dispose();
    }
    super.dispose();
  }

  // The caption bar's maximize glyph, and the shell's resize edges, both depend
  // on this — and the window can be maximized by the compositor (a double-click
  // on the panel, a keyboard shortcut, tiling) without the app being asked.
  @override
  void onWindowMaximize() => _syncMaximized(true);

  @override
  void onWindowUnmaximize() => _syncMaximized(false);

  void _syncMaximized(bool value) {
    if (!mounted) return;
    ref.read(windowMaximizedProvider.notifier).state = value;
    _saveGeometry();
  }

  @override
  void onWindowMoved() => _saveGeometry();

  @override
  void onWindowResized() => _saveGeometry();

  Timer? _geometryDebounce;

  /// Remember where the window was.
  ///
  /// Debounced, and heavily: a resize drag fires this on every frame, and Hive
  /// writes to disk. Saving the geometry of a window the user is still dragging
  /// is a hundred pointless writes for one useful one.
  void _saveGeometry() {
    _geometryDebounce?.cancel();
    _geometryDebounce = Timer(const Duration(milliseconds: 700), () async {
      if (!mounted) return;
      final geometry = await ref.read(desktopServiceProvider).geometry();
      if (geometry == null || !mounted) return;
      await ref
          .read(cacheServiceProvider)
          .setSetting(StorageKeys.windowGeometry, geometry.encode());
    });
  }

  void _focusDock() {
    final destinations = _destinations(ref);
    final location = GoRouterState.of(context).matchedLocation;
    final index = destinations.indexWhere((d) => d.route == location);

    _contentFocus = FocusManager.instance.primaryFocus;
    _dockNodes[index < 0 ? 0 : index].requestFocus();
  }

  void _leaveDock() {
    final previous = _contentFocus;
    if (previous != null && previous.context != null) {
      previous.requestFocus();
    } else {
      FocusScope.of(context).focusInDirection(TraversalDirection.up);
    }
  }

  List<DockDestination> _destinations(WidgetRef ref) {
    final s = ref.watch(stringsProvider);

    // Exactly six, in this order, and Home is not one of them — it is the logo
    // in the caption bar. A seventh "Home" slot is what turns a dock into a
    // website's navigation bar.
    return [
      DockDestination(
        icon: MoIcon.search,
        label: s.search,
        route: Routes.search,
        shortcut: 'Ctrl+F',
      ),
      DockDestination(
        icon: MoIcon.live,
        label: s.live,
        route: Routes.live,
        shortcut: 'Ctrl+2',
      ),
      DockDestination(
        icon: MoIcon.movies,
        label: s.movies,
        route: Routes.movies,
        shortcut: 'Ctrl+3',
      ),
      DockDestination(
        icon: MoIcon.series,
        label: s.series,
        route: Routes.series,
        shortcut: 'Ctrl+4',
      ),
      DockDestination(
        icon: MoIcon.favorites,
        label: s.favorites,
        route: Routes.favorites,
        shortcut: 'Ctrl+5',
      ),
      DockDestination(
        icon: MoIcon.settings,
        label: s.settings,
        route: Routes.settings,
        shortcut: 'Ctrl+,',
      ),
    ];
  }

  @override
  Widget build(BuildContext context) {
    final view = ref.watch(playerViewProvider);
    final fullscreen = ref.watch(fullscreenProvider);
    final maximized = ref.watch(windowMaximizedProvider);
    final reduced = ref.watch(reducedMotionProvider);
    final location = GoRouterState.of(context).matchedLocation;

    // Immersive: the player has the window, and every piece of desktop chrome
    // gets out of the way — including MoPlayer's own. A caption bar over a
    // full-screen film is the same mistake as a taskbar over one.
    final immersive = fullscreen || view == PlayerView.expanded;

    final destinations = _destinations(ref);
    final dockReserve = _dockHeight(context);

    return Motion(
      reduced: reduced,
      child: CallbackShortcuts(
        bindings: {
          // Only Ctrl-chorded shortcuts are global. A bare `F` here would fire
          // while the user is typing in the search box; the player's own
          // single-key shortcuts live inside the player, which has focus when it
          // is the thing on screen.
          const SingleActivator(LogicalKeyboardKey.digit1, control: true): () =>
              context.go(Routes.home),
          const SingleActivator(LogicalKeyboardKey.digit2, control: true): () =>
              context.go(Routes.live),
          const SingleActivator(LogicalKeyboardKey.digit3, control: true): () =>
              context.go(Routes.movies),
          const SingleActivator(LogicalKeyboardKey.digit4, control: true): () =>
              context.go(Routes.series),
          const SingleActivator(LogicalKeyboardKey.digit5, control: true): () =>
              context.go(Routes.favorites),
          const SingleActivator(LogicalKeyboardKey.keyF, control: true): () =>
              context.go(Routes.search),
          const SingleActivator(LogicalKeyboardKey.comma, control: true): () =>
              context.go(Routes.settings),

          // The dock, from anywhere. Without this, a user three hundred posters
          // deep would have to arrow through all of them to reach Settings —
          // which is exactly the failure that makes remote-driven apps unusable.
          // F6 is the desktop's own "next region" key, so it is the one a
          // keyboard user will already try.
          const SingleActivator(LogicalKeyboardKey.f6): _focusDock,
          const SingleActivator(LogicalKeyboardKey.home, control: true): () =>
              context.go(Routes.home),
        },
        child: Scaffold(
          backgroundColor: AppColors.surface0,
          body: ResizeEdges(
            // No edges to pull when the window fills the screen, and arming them
            // there means a click near the top of a maximized window starts a
            // resize the user did not ask for.
            enabled: !maximized && !immersive && !_systemDecorated,
            child: AmbientScene(
              child: Stack(
                children: [
                  Column(
                    children: [
                      if (!immersive)
                        WindowCaption(
                          onHome: () => context.go(Routes.home),
                          breadcrumb: _breadcrumb(ref, location),
                        ),
                      Expanded(
                        child: MediaQuery(
                          // Every scrolling screen reads this and adds it to the
                          // bottom of its scroll padding, which is how the last
                          // row of a grid ends up *above* the dock instead of
                          // under it. The shell owns the number because the shell
                          // owns the dock.
                          data: MediaQuery.of(context).copyWith(
                            padding: MediaQuery.paddingOf(context).copyWith(
                              bottom: dockReserve,
                            ),
                          ),
                          child: widget.child,
                        ),
                      ),
                    ],
                  ),

                  // The mini player rides just above the dock, and is nudged up
                  // by it — the two must never overlap, and the dock is the one
                  // that was there first.
                  if (view == PlayerView.mini && !immersive)
                    Positioned(
                      left: Nova.space5,
                      right: Nova.space5,
                      bottom: dockReserve + Nova.space2,
                      child: const MiniPlayer(),
                    ),

                  if (!immersive)
                    Positioned(
                      bottom: Nova.space5,
                      left: 0,
                      right: 0,
                      child: Center(
                        child: GlassDock(
                          destinations: destinations,
                          currentRoute: location,
                          focusNodes: _dockNodes,
                          onSelect: context.go,
                          onEscape: _leaveDock,
                        ),
                      ),
                    ),

                  if (view == PlayerView.expanded)
                    const Positioned.fill(child: PlayerOverlay()),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  bool get _systemDecorated => DesktopService.useSystemDecoration;

  /// How much room the dock needs at the foot of the window, including its
  /// margin. Kept in one place because three widgets depend on it and a
  /// disagreement between them is a dock that overlaps the mini player.
  double _dockHeight(BuildContext context) {
    final compact = MediaQuery.sizeOf(context).width < 1100;
    // icon (24) + label + indicator + the dock's own vertical padding.
    final dock = compact ? 60.0 : 88.0;
    return dock + Nova.space5 + Nova.space4;
  }

  /// The caption bar's breadcrumb. Only for the places where "MoPlayer" alone
  /// would not tell the user where they are.
  String? _breadcrumb(WidgetRef ref, String location) {
    final s = ref.watch(stringsProvider);
    return switch (location) {
      Routes.live => s.live,
      Routes.movies => s.movies,
      Routes.series => s.series,
      Routes.search => s.search,
      Routes.favorites => s.favorites,
      Routes.settings => s.settings,
      _ => null,
    };
  }
}
