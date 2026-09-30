import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
// window_manager ships a `WindowCaption` of its own — a GNOME-looking bar we
// explicitly do not want. Hidden so the frame imported from `window_chrome.dart`
// remains unambiguously MoPlayer's.
import 'package:window_manager/window_manager.dart' hide WindowCaption;

import '../core/constants/app_constants.dart';
import '../core/theme/app_colors.dart';
import '../core/theme/glass.dart';
import '../core/theme/nova.dart';
import '../core/utils/app_logger.dart';
import '../features/player/mini_player.dart';
import '../features/player/player_overlay.dart';
import '../providers/core_providers.dart';
import '../providers/playback_providers.dart';
import '../providers/shell_providers.dart';
import '../providers/system_providers.dart';
import '../widgets/mo_icons.dart';
import '../widgets/nav_rail.dart';
import '../widgets/source_switcher.dart';
import 'launch_args.dart';
import 'routes.dart';
import 'window_chrome.dart';

/// The frame every screen lives in.
///
/// One frame and one panel. The **frame** is the caption along the top and
/// the navigation rail down the start edge, in one colour; the **panel** is the
/// page, inset into the frame with a rounded leading corner, over the ambient
/// scene. Layers, bottom to top:
///
///  1. The frame (caption + [NavRail]).
///  2. The page, inside the panel. When the mini player floats over the foot
///     of the panel, the shell hands the page its height as bottom padding so
///     the last row can always be scrolled clear of it — the shell pays that
///     price so that no screen has to remember to.
///  3. The mini player.
///  4. **The player**, when it is expanded — which covers all of the above,
///     because it is the one screen that is meant to be the whole machine.
class MainShell extends ConsumerStatefulWidget {
  const MainShell({super.key, required this.child});

  final Widget child;

  @override
  ConsumerState<MainShell> createState() => _MainShellState();
}

class _MainShellState extends ConsumerState<MainShell> with WindowListener {
  static const _activationChannel = MethodChannel(
    'org.moos.moplayer/activation',
  );

  /// Owned here, not by the rail: F6 has to move focus onto the *selected*
  /// destination, and the rail is rebuilt on every navigation.
  final List<FocusNode> _railNodes = List.generate(
    7,
    (i) => FocusNode(debugLabel: 'rail-$i'),
  );

  /// Where focus was before it jumped to the rail, so that Escape can put it
  /// back where the user left it rather than at the top of the page.
  FocusNode? _contentFocus;

  @override
  void initState() {
    super.initState();
    windowManager.addListener(this);
    _activationChannel.setMethodCallHandler(_handleActivation);

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
    _activationChannel.setMethodCallHandler(null);
    _geometryDebounce?.cancel();
    windowManager.removeListener(this);
    for (final node in _railNodes) {
      node.dispose();
    }
    super.dispose();
  }

  Future<void> _handleActivation(MethodCall call) async {
    if (call.method != 'activate' || call.arguments is! List) return;

    final args = LaunchArgs.parse(
      (call.arguments as List).whereType<String>().toList(),
    );
    log.i(
      'activation: section=${args.section} '
      'playlist=${args.playlist != null} stream=${args.playUrl != null}',
    );
    await ref.read(desktopServiceProvider).raise();
    if (!mounted) return;

    final playlist = args.playlist;
    if (playlist != null) {
      await ref.read(activePlaylistProvider.notifier).activate(playlist);
      if (!mounted) return;
      context.go(Routes.home);
    } else if (args.section != null) {
      context.go(args.section!);
    }

    final url = args.playUrl;
    if (url != null) {
      await ref.read(playbackProvider.notifier).playDirect(url);
    }
  }

  // The caption bar's maximize glyph, and the shell's resize edges, both depend
  // on this — and the window can be maximized by the compositor (a double-click
  // on the panel, a keyboard shortcut, tiling) without the app being asked.
  @override
  void onWindowMaximize() => _syncMaximized(true);

  @override
  void onWindowUnmaximize() => _syncMaximized(false);

  @override
  void onWindowEnterFullScreen() =>
      ref.read(fullscreenProvider.notifier).sync(true);

  @override
  void onWindowLeaveFullScreen() =>
      ref.read(fullscreenProvider.notifier).sync(false);

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

  void _focusRail() {
    final destinations = _destinations(ref);
    final location = GoRouterState.of(context).matchedLocation;
    final index = destinations.indexWhere((d) => d.route == location);

    _contentFocus = FocusManager.instance.primaryFocus;
    _railNodes[index < 0 ? 0 : index].requestFocus();
  }

  void _leaveRail() {
    final previous = _contentFocus;
    if (previous != null && previous.context != null) {
      previous.requestFocus();
    } else {
      FocusScope.of(context).focusInDirection(TraversalDirection.right);
    }
  }

  List<NavDestination> _destinations(WidgetRef ref) {
    final s = ref.watch(stringsProvider);

    // Seven, in this order, and Home is one of them: the way back to the front
    // page must be the same size and in the same place as the way to
    // everywhere else. A logo that doubles as "home" is a thing you learn; a
    // destination is a thing you see.
    return [
      NavDestination(
        icon: MoIcon.home,
        label: s.home,
        route: Routes.home,
        shortcut: 'Ctrl+1',
      ),
      NavDestination(
        icon: MoIcon.live,
        label: s.live,
        route: Routes.live,
        shortcut: 'Ctrl+2',
      ),
      NavDestination(
        icon: MoIcon.movies,
        label: s.movies,
        route: Routes.movies,
        shortcut: 'Ctrl+3',
      ),
      NavDestination(
        icon: MoIcon.series,
        label: s.series,
        route: Routes.series,
        shortcut: 'Ctrl+4',
      ),
      NavDestination(
        icon: MoIcon.favorites,
        label: s.favorites,
        route: Routes.favorites,
        shortcut: 'Ctrl+5',
      ),
      NavDestination(
        icon: MoIcon.search,
        label: s.search,
        route: Routes.search,
        shortcut: 'Ctrl+F',
      ),
      NavDestination(
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
    final location = GoRouterState.of(context).matchedLocation;
    final now = ref.watch(playbackProvider);

    // Immersive: the player has the window, and every piece of desktop chrome
    // gets out of the way — including MoPlayer's own. A caption bar over a
    // full-screen film is the same mistake as a taskbar over one.
    final immersive = fullscreen || view == PlayerView.expanded;

    // Live TV shows a playing channel on its own stage; a second, smaller copy
    // of the same picture in the corner would only compete with it.
    final onLiveStage = location == Routes.live && (now?.isLive ?? false);
    final showMini = view == PlayerView.mini && !immersive && !onLiveStage;
    final bottomReserve = showMini ? MiniPlayer.reserve : 0.0;

    final destinations = _destinations(ref);

    return FramelessWindowFrame(
      onHome: () => context.go(Routes.home),
      onSearch: () => context.go(Routes.search),
      breadcrumb: _breadcrumb(ref, location),
      showCaption: !immersive,
      resizeEnabled: !immersive,
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

          // The rail, from anywhere. Without this, a user three hundred posters
          // deep would have to arrow through all of them to reach Settings —
          // which is exactly the failure that makes remote-driven apps unusable.
          // F6 is the desktop's own "next region" key, so it is the one a
          // keyboard user will already try.
          const SingleActivator(LogicalKeyboardKey.f6): _focusRail,
          const SingleActivator(LogicalKeyboardKey.home, control: true): () =>
              context.go(Routes.home),
        },
        // Shortcuts only fire for a focus inside them. Nothing on a freshly
        // opened page has focus, so the shell holds it until the user moves it
        // somewhere — otherwise Ctrl+2 does nothing until something is clicked.
        child: Focus(
          autofocus: true,
          debugLabel: 'shell',
          child: Stack(
            children: [
              Positioned.fill(
                child: Row(
                  children: [
                    if (!immersive)
                      NavRail(
                        destinations: destinations,
                        currentRoute: location,
                        focusNodes: _railNodes,
                        onSelect: context.go,
                        onEscape: _leaveRail,
                        footer: const SourceSwitcher(),
                      ),
                    Expanded(
                      child: _ContentPanel(
                        framed: !immersive,
                        child: Stack(
                          children: [
                            Positioned.fill(
                              child: MediaQuery(
                                // Every scrolling screen reads this and adds it
                                // to the bottom of its scroll padding, which is
                                // how the last row of a grid ends up *above* the
                                // mini player instead of under it. The shell
                                // owns the number because it owns the player.
                                data: MediaQuery.of(context).copyWith(
                                  padding: MediaQuery.paddingOf(
                                    context,
                                  ).copyWith(bottom: bottomReserve),
                                ),
                                child: widget.child,
                              ),
                            ),
                            if (showMini)
                              const PositionedDirectional(
                                end: Nova.space5,
                                bottom: Nova.space5,
                                child: MiniPlayer(),
                              ),
                          ],
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              if (view == PlayerView.expanded)
                const Positioned.fill(child: PlayerOverlay()),
            ],
          ),
        ),
      ),
    );
  }

  /// The caption bar's title: where the user is. Home is simply MoPlayer.
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

/// The page, inset into the frame: a rounded leading corner, a hairline edge,
/// and the ambient scene behind whatever the page draws.
class _ContentPanel extends StatelessWidget {
  const _ContentPanel({required this.child, required this.framed});

  final Widget child;
  final bool framed;

  static const double radius = 20;

  @override
  Widget build(BuildContext context) {
    if (!framed) return ColoredBox(color: AppColors.surface0, child: child);
    final corner = const BorderRadiusDirectional.only(
      topStart: Radius.circular(radius),
    ).resolve(Directionality.of(context));
    return DecoratedBox(
      position: DecorationPosition.foreground,
      decoration: BoxDecoration(
        borderRadius: corner,
        border: Border.all(color: AppColors.borderSubtle),
      ),
      child: ClipRRect(
        borderRadius: corner,
        child: AmbientScene(child: child),
      ),
    );
  }
}
