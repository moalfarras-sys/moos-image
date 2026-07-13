import 'dart:io';
import 'dart:ui' show PlatformDispatcher;

import 'package:flutter/widgets.dart' show Color, Rect, Size;
import 'package:screen_retriever/screen_retriever.dart';
import 'package:wakelock_plus/wakelock_plus.dart';
import 'package:window_manager/window_manager.dart';

import '../../core/config/app_config.dart';
import '../../core/utils/app_logger.dart';

/// Where the window was when the user last closed it.
class WindowGeometry {
  const WindowGeometry({required this.rect, required this.maximized});

  final Rect rect;
  final bool maximized;

  /// Guards against restoring a window onto a display that is no longer there.
  /// A rectangle at `x = 3800` is perfectly valid until the second monitor is
  /// unplugged, at which point it is a window the user cannot see and cannot
  /// reach — and the only symptom is that the app "did not start".
  bool get isSane =>
      rect.width >= 640 &&
      rect.height >= 480 &&
      rect.width <= 16384 &&
      rect.height <= 16384 &&
      rect.left > -8192 &&
      rect.top > -8192;

  String encode() =>
      '${rect.left},${rect.top},${rect.width},${rect.height},$maximized';

  static WindowGeometry? decode(String? raw) {
    if (raw == null || raw.isEmpty) return null;
    final parts = raw.split(',');
    if (parts.length != 5) return null;
    final numbers = parts.take(4).map(double.tryParse).toList();
    if (numbers.any((n) => n == null)) return null;
    return WindowGeometry(
      rect: Rect.fromLTWH(numbers[0]!, numbers[1]!, numbers[2]!, numbers[3]!),
      maximized: parts[4] == 'true',
    );
  }
}

/// The app's relationship with the MoOS desktop: the window, the screen-saver,
/// and the title Plasma shows in the task switcher.
///
/// Everything here is best-effort. MoPlayer has to keep playing on a session
/// with no window manager, no screen-saver service, and no portal — so each call
/// is wrapped and a failure is logged, never thrown.
class DesktopService {
  DesktopService();

  bool _fullscreen = false;
  bool _inhibiting = false;

  bool get isFullscreen => _fullscreen;

  /// Whether the window wears MoPlayer's own chrome or KWin's.
  ///
  /// Frameless is the product decision: MoPlayer draws a cinematic caption bar
  /// that carries the logo, the source status and the window buttons, and a
  /// second, system-drawn title bar above it would be a duplicated header on the
  /// one app in the image that is supposed to look like a screen rather than a
  /// window.
  ///
  /// It is a real trade and it is worth naming: server-side decoration gives you
  /// KWin's snapping, its shadow and its resize borders for free, and going
  /// frameless means re-implementing all three (see [startResizing] and
  /// `WindowChrome`). `MOPLAYER_SSD=1` hands the window back to KWin for anyone
  /// debugging a compositor that will not cooperate.
  static bool get useSystemDecoration =>
      Platform.environment['MOPLAYER_SSD'] == '1';

  /// The desktop's usable area, in the units [windowManager] sizes windows in.
  ///
  /// **Not** `PlatformDispatcher…display`. That is the trap this method exists to
  /// avoid: on the maintainer's 4K panel — Wayland, fractional scaling, 275% —
  /// Flutter reports the display as `1396x785 @3.0x`, and the obvious
  /// `size / devicePixelRatio` yields a *465x261* desktop. Sizing a window from
  /// that produced a 428x240 window: a real, shipped-looking application the size
  /// of a dialog box, laid out for a screen that does not exist.
  ///
  /// `screen_retriever` answers in the same coordinate space `window_manager`
  /// speaks, which is the only space in which "make the window 1280 wide" and
  /// "the screen is 1397 wide" can be compared at all.
  static Future<Size?> _workArea() async {
    try {
      final display = await screenRetriever.getPrimaryDisplay();
      // `visibleSize` excludes the panels — MoOS's dock lives at the foot of the
      // screen, and a window sized to the *full* display opens underneath it.
      final area = display.visibleSize ?? display.size;
      if (area.width < 320 || area.height < 240) return null;
      return area;
    } on Object catch (e) {
      log.w('could not read the display: $e');
      return null;
    }
  }

  /// Called once, before the first frame. Does **not** show the window — the
  /// saved geometry is not known until the cache is open, and mapping the window
  /// twice makes Plasma animate it twice. [showWindow] finishes the job.
  static Future<void> initWindow() async {
    if (!Platform.isLinux) return;

    const preferred = Size(1440, 900);
    const floor = Size(880, 560);

    final area = await _workArea();

    // The preferred size is a *ceiling*, not a demand: 92% of the work area, so
    // a window on a small desktop still has an edge to grab, and one on a large
    // desktop does not open the size of a television.
    final size = area == null
        ? preferred
        : Size(
            preferred.width.clamp(560.0, area.width * 0.92),
            preferred.height.clamp(420.0, area.height * 0.92),
          );

    // And the floor is clamped too. A minimum size larger than the screen is a
    // window the user cannot resize to fit the screen it is already on.
    final minimum = area == null
        ? floor
        : Size(
            floor.width.clamp(360.0, area.width),
            floor.height.clamp(280.0, area.height),
          );

    try {
      await windowManager.ensureInitialized();
      await windowManager.waitUntilReadyToShow(
        WindowOptions(
          size: size,
          minimumSize: minimum,
          center: true,
          title: 'MoPlayer',
          backgroundColor: const Color(0xFF070809),

          // Deliberately `normal`, even though the window is frameless.
          //
          // `TitleBarStyle.hidden` makes window_manager call
          // `gtk_window_set_decorated(false)`, which on a Wayland session does
          // nothing at all (see `linux/runner/my_application.cc` for why) — and
          // *would* fight the client-side-decoration trick that does work, by
          // undecorating the window GTK is drawing our empty titlebar into.
          // The decoration is settled in C, before the engine starts; from here
          // the correct thing to do is leave it alone.
          titleBarStyle: TitleBarStyle.normal,
        ),
        () async {},
      );
    } on Exception catch (e) {
      log.w('window_manager unavailable: $e');
    }
  }

  /// Restore the geometry the user left the window in, then map it.
  ///
  /// Best-effort in every direction: a saved rectangle that no longer fits any
  /// attached display is discarded rather than restored off-screen, and any
  /// failure here still ends with a visible window — an app that will not show
  /// itself because it could not remember where it was is a broken app.
  static Future<void> showWindow(WindowGeometry? saved) async {
    if (!Platform.isLinux) return;
    try {
      if (saved != null && saved.isSane && await _fitsOnAnyDisplay(saved.rect)) {
        if (saved.maximized) {
          await windowManager.maximize();
        } else {
          await windowManager.setBounds(saved.rect);
        }
      }
    } on Exception catch (e) {
      log.w('restoring window geometry failed: $e');
    } finally {
      try {
        await windowManager.show();
        await windowManager.focus();
      } on Exception catch (e) {
        log.w('showing the window failed: $e');
      }
    }

    // One line, once, on stderr — where a desktop application's startup banner
    // belongs, and where it survives a release build.
    //
    // It is the line that would have caught the window opening off the side of a
    // 4K panel scaled to 275%, and there is no other way to see the numbers the
    // compositor actually handed the app. It names no credential.
    final display = PlatformDispatcher.instance.implicitView?.display;
    final bounds = await windowManager.getBounds();
    if (display != null) {
      final logical = display.size / display.devicePixelRatio;
      stderr.writeln(
        'moplayer: display ${display.size.width.toInt()}x'
        '${display.size.height.toInt()} @${display.devicePixelRatio}x '
        '(logical ${logical.width.toInt()}x${logical.height.toInt()}) · '
        'window ${bounds.width.toInt()}x${bounds.height.toInt()} '
        'at ${bounds.left.toInt()},${bounds.top.toInt()}',
      );
    }
  }

  /// Would the saved rectangle still land somewhere the user can see?
  ///
  /// The user's display can change between two runs of the app — a monitor is
  /// unplugged, a scale factor is changed, a laptop is undocked — and a window
  /// restored onto a screen that is no longer attached is a window that "did not
  /// open" as far as the person in front of it is concerned.
  static Future<bool> _fitsOnAnyDisplay(Rect rect) async {
    final area = await _workArea();
    if (area == null) return true;

    // Its top-left has to land on the desktop, and it must not be wider or
    // taller than the desktop itself.
    return rect.left < area.width - 80 &&
        rect.top < area.height - 60 &&
        rect.width <= area.width + 1 &&
        rect.height <= area.height + 1;
  }

  /// The current geometry, for persisting on exit.
  Future<WindowGeometry?> geometry() async {
    if (!Platform.isLinux) return null;
    try {
      final maximized = await windowManager.isMaximized();
      final bounds = await windowManager.getBounds();
      return WindowGeometry(rect: bounds, maximized: maximized);
    } on Exception catch (e) {
      log.w('reading window geometry failed: $e');
      return null;
    }
  }

  /// Move the window by dragging the caption bar.
  Future<void> startDragging() async {
    try {
      await windowManager.startDragging();
    } on Exception catch (e) {
      log.w('startDragging failed: $e');
    }
  }

  /// Resize from an edge. This is what a frameless window has to pay for: with
  /// no server-side decoration there are no resize borders, so the app draws its
  /// own hit areas and asks GTK to begin the drag.
  Future<void> startResizing(ResizeEdge edge) async {
    try {
      await windowManager.startResizing(edge);
    } on Exception catch (e) {
      log.w('startResizing failed: $e');
    }
  }

  Future<bool> isMaximized() async {
    try {
      return await windowManager.isMaximized();
    } on Exception {
      return false;
    }
  }

  Future<void> toggleMaximize() async {
    try {
      if (await windowManager.isMaximized()) {
        await windowManager.unmaximize();
      } else {
        await windowManager.maximize();
      }
    } on Exception catch (e) {
      log.w('toggleMaximize failed: $e');
    }
  }

  Future<void> minimize() async {
    try {
      await windowManager.minimize();
    } on Exception catch (e) {
      log.w('minimize failed: $e');
    }
  }

  Future<void> close() async {
    try {
      await windowManager.close();
    } on Exception catch (e) {
      log.w('close failed: $e');
    }
  }

  Future<void> setFullscreen(bool value) async {
    if (_fullscreen == value) return;
    _fullscreen = value;
    try {
      await windowManager.setFullScreen(value);
    } on Exception catch (e) {
      log.w('fullscreen toggle failed: $e');
    }
  }

  Future<void> toggleFullscreen() => setFullscreen(!_fullscreen);

  /// Window title. Plasma's task manager and Alt-Tab read this, so a MoOS user
  /// glancing at the taskbar sees the channel, not just "MoPlayer".
  Future<void> setTitle(String? nowPlaying) async {
    final title = nowPlaying == null || nowPlaying.isEmpty
        ? 'MoPlayer'
        : '$nowPlaying — MoPlayer';
    try {
      await windowManager.setTitle(title);
    } on Exception catch (e) {
      log.w('setTitle failed: $e');
    }
  }

  Future<void> raise() async {
    try {
      await windowManager.show();
      await windowManager.focus();
    } on Exception catch (e) {
      log.w('raise failed: $e');
    }
  }

  /// Hold off the screen-saver while a video is on screen.
  ///
  /// `wakelock_plus` speaks `org.freedesktop.ScreenSaver.Inhibit`, which is
  /// exactly what Plasma's power management listens to — the same call Dragon
  /// Player and VLC make. It is *not* held while paused: an inhibitor that
  /// outlives playback is how a laptop ends up awake in a bag.
  Future<void> setKeepAwake(bool value) async {
    if (_inhibiting == value) return;
    _inhibiting = value;
    try {
      await WakelockPlus.toggle(enable: value);
    } on Exception catch (e) {
      // A session with no screen-saver service (a bare compositor, a VM) throws
      // here. The video keeps playing; the screen may blank. Not fatal.
      log.w('screen-saver inhibit failed: $e');
      _inhibiting = false;
    }
  }

  /// A one-line summary for the Settings screen, so the user can see what the
  /// app actually managed to hook into rather than what it hoped to.
  Map<String, bool> integrationStatus({required bool mprisActive}) => {
    'moos': AppConfig.isMoOS,
    'plasma': AppConfig.isPlasma,
    'wayland': AppConfig.isWayland,
    'mpris': mprisActive,
  };

  Future<void> dispose() async {
    await setKeepAwake(false);
  }
}
