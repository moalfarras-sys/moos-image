import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:window_manager/window_manager.dart';

import '../core/theme/app_colors.dart';
import '../core/theme/app_typography.dart';
import '../core/theme/motion.dart';
import '../core/theme/nova.dart';
import '../providers/core_providers.dart';
import '../providers/shell_providers.dart';
import '../providers/system_providers.dart';
import '../services/system/desktop_service.dart';
import '../widgets/app_logo.dart';

/// The desktop frame shared by the catalogue and the source/login flow.
///
/// MoPlayer deliberately asks KWin for a frameless surface, so *every* route has
/// to provide the replacement: caption, compositor drag, window actions and the
/// eight resize edges. Keeping that contract here prevents a route added outside
/// [MainShell] from silently becoming an inescapable borderless window.
class FramelessWindowFrame extends ConsumerStatefulWidget {
  const FramelessWindowFrame({
    super.key,
    required this.child,
    this.onHome,
    this.breadcrumb,
    this.showCaption = true,
    this.resizeEnabled = true,
  });

  final Widget child;
  final VoidCallback? onHome;
  final String? breadcrumb;
  final bool showCaption;
  final bool resizeEnabled;

  @override
  ConsumerState<FramelessWindowFrame> createState() =>
      _FramelessWindowFrameState();
}

class _FramelessWindowFrameState extends ConsumerState<FramelessWindowFrame>
    with WindowListener {
  @override
  void initState() {
    super.initState();
    windowManager.addListener(this);
  }

  @override
  void dispose() {
    windowManager.removeListener(this);
    super.dispose();
  }

  @override
  void onWindowMaximize() => _setMaximized(true);

  @override
  void onWindowUnmaximize() => _setMaximized(false);

  void _setMaximized(bool value) {
    if (!mounted) return;
    ref.read(windowMaximizedProvider.notifier).state = value;
  }

  @override
  Widget build(BuildContext context) {
    final maximized = ref.watch(windowMaximizedProvider);

    return Scaffold(
      backgroundColor: AppColors.surface0,
      body: ResizeEdges(
        enabled:
            widget.resizeEnabled &&
            !maximized &&
            !DesktopService.useSystemDecoration,
        child: Column(
          children: [
            if (widget.showCaption)
              WindowCaption(
                onHome: widget.onHome,
                breadcrumb: widget.breadcrumb,
              ),
            Expanded(child: widget.child),
          ],
        ),
      ),
    );
  }
}

/// MoPlayer's caption bar.
///
/// The window is frameless (see `DesktopService.useSystemDecoration`), so this
/// bar *is* the title bar: it drags the window, it maximizes on a double click,
/// and it carries the three window buttons. It also carries the two things a
/// system title bar could never know — which source is connected, and whether it
/// is answering.
///
/// It is deliberately thin. A caption bar is chrome, and chrome that competes
/// with a hero image has misunderstood which one the user came for.
class WindowCaption extends ConsumerWidget {
  const WindowCaption({super.key, this.onHome, this.breadcrumb});

  /// The logo is the Home action. That is why the dashboard is not a dock slot:
  /// six destinations plus a seventh "Home" is the layout of a website's navbar,
  /// and this is not a website.
  final VoidCallback? onHome;

  final String? breadcrumb;

  static const double height = 46;
  static const double windowControlsWidth =
      Nova.space2 + (_WindowButton.targetSize * 3);

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(stringsProvider);
    final desktop = ref.watch(desktopServiceProvider);

    return SizedBox(
      height: height,
      child: DecoratedBox(
        decoration: const BoxDecoration(
          // Not glass: the caption sits against the top edge of the window,
          // where there is nothing behind it to blur and no light above it to
          // catch. A blur here would cost a save-layer for a visual effect that
          // has no source.
          color: Color(0xE60A0B0D),
          border: Border(bottom: BorderSide(color: AppColors.borderSubtle)),
        ),
        child: Stack(
          fit: StackFit.expand,
          children: [
            // Physical window chrome is not language direction. Reserve the
            // left edge explicitly, then let the identity/status row below
            // inherit RTL normally.
            const Positioned(
              left: 0,
              top: 0,
              bottom: 0,
              width: windowControlsWidth,
              child: Directionality(
                textDirection: TextDirection.ltr,
                child: _WindowButtons(),
              ),
            ),
            Positioned.fill(
              left: windowControlsWidth,
              child: Row(
                children: [
                  const SizedBox(width: Nova.space3),
                  _HomeButton(onTap: onHome, label: s.home),

                  if (breadcrumb != null) ...[
                    const SizedBox(width: Nova.space3),
                    Text('·', style: AppText.caption),
                    const SizedBox(width: Nova.space3),
                    Flexible(
                      child: Text(
                        breadcrumb!,
                        style: AppText.caption.copyWith(
                          color: AppColors.textSecondary,
                        ),
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                  ],

                  // Everything between identity and status is drag surface.
                  Expanded(child: _DragRegion(desktop: desktop)),

                  const _SourceStatus(),
                  const SizedBox(width: Nova.space4),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// The part of the caption that moves the window.
///
/// A `GestureDetector` with `onPanStart` would fight the compositor: on Wayland
/// the move is *begun* by the client and then owned by the server, so the drag
/// has to be handed over on the down event, not tracked frame by frame.
class _DragRegion extends StatelessWidget {
  const _DragRegion({required this.desktop});

  final dynamic desktop;

  @override
  Widget build(BuildContext context) {
    return Listener(
      onPointerDown: (event) {
        if (event.buttons == kPrimaryMouseButton) desktop.startDragging();
      },
      child: GestureDetector(
        behavior: HitTestBehavior.translucent,
        onDoubleTap: () => desktop.toggleMaximize(),
        child: const SizedBox.expand(),
      ),
    );
  }
}

class _HomeButton extends StatefulWidget {
  const _HomeButton({this.onTap, required this.label});

  final VoidCallback? onTap;
  final String label;

  @override
  State<_HomeButton> createState() => _HomeButtonState();
}

class _HomeButtonState extends State<_HomeButton> {
  bool _hovered = false;

  @override
  Widget build(BuildContext context) {
    final identity = Padding(
      padding: const EdgeInsets.symmetric(horizontal: Nova.space2),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          const AppLogo(size: 22),
          const SizedBox(width: Nova.space2),
          Text(
            'MoPlayer',
            style: AppText.control.copyWith(
              fontWeight: FontWeight.w600,
              letterSpacing: 0.2,
            ),
          ),
        ],
      ),
    );

    if (widget.onTap == null) return identity;

    return Tooltip(
      message: widget.label,
      child: MouseRegion(
        cursor: SystemMouseCursors.click,
        onEnter: (_) => setState(() => _hovered = true),
        onExit: (_) => setState(() => _hovered = false),
        child: Semantics(
          button: true,
          label: widget.label,
          child: GestureDetector(
            onTap: widget.onTap!,
            child: AnimatedOpacity(
              duration: Motion.duration(context, Nova.hover),
              opacity: _hovered ? 1.0 : 0.86,
              child: identity,
            ),
          ),
        ),
      ),
    );
  }
}

/// Which source is connected, and whether the machine is on a network.
///
/// Real state, both of them: the name comes from the active playlist and the dot
/// comes from `connectivity_plus`. There is no third "everything is fine" light,
/// because a light that is always green is a light nobody reads.
class _SourceStatus extends ConsumerWidget {
  const _SourceStatus();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(stringsProvider);
    final playlist = ref.watch(activePlaylistProvider);

    if (playlist == null) return const SizedBox.shrink();

    final online = ref.watch(connectivityProvider).value ?? true;
    final color = online ? AppColors.success : AppColors.warning;

    return Tooltip(
      message: online ? s.connected : s.offline,
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 7,
            height: 7,
            decoration: BoxDecoration(
              color: color,
              shape: BoxShape.circle,
              boxShadow: [
                BoxShadow(color: color.withValues(alpha: 0.6), blurRadius: 7),
              ],
            ),
          ),
          const SizedBox(width: Nova.space2),
          ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 220),
            child: Text(
              playlist.name,
              style: AppText.caption,
              overflow: TextOverflow.ellipsis,
              maxLines: 1,
            ),
          ),
        ],
      ),
    );
  }
}

/// Close, minimize, maximize — in the shape MoOS's own window decoration uses,
/// so the app's own caption is not the one window in the session whose buttons
/// look foreign.
class _WindowButtons extends ConsumerWidget {
  const _WindowButtons();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(stringsProvider);
    final desktop = ref.watch(desktopServiceProvider);
    final maximized = ref.watch(windowMaximizedProvider);

    return Padding(
      padding: const EdgeInsets.only(left: Nova.space2),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          _WindowButton(
            kind: _WindowButtonKind.close,
            tooltip: s.windowClose,
            onTap: desktop.close,
          ),
          _WindowButton(
            kind: _WindowButtonKind.minimize,
            tooltip: s.windowMinimize,
            onTap: desktop.minimize,
          ),
          _WindowButton(
            kind: maximized
                ? _WindowButtonKind.restore
                : _WindowButtonKind.maximize,
            tooltip: maximized ? s.windowRestore : s.windowMaximize,
            onTap: () async {
              await desktop.toggleMaximize();
              ref.read(windowMaximizedProvider.notifier).state = await desktop
                  .isMaximized();
            },
          ),
        ],
      ),
    );
  }
}

enum _WindowButtonKind { close, minimize, maximize, restore }

class _WindowButton extends StatefulWidget {
  const _WindowButton({
    required this.kind,
    required this.tooltip,
    required this.onTap,
  });

  final _WindowButtonKind kind;
  final String tooltip;
  final VoidCallback onTap;

  static const double targetSize = 40;
  static const double glyphPlateSize = 20;

  @override
  State<_WindowButton> createState() => _WindowButtonState();
}

class _WindowButtonState extends State<_WindowButton> {
  bool _hovered = false;
  bool _focused = false;
  bool _pressed = false;

  Color get _semanticColor {
    switch (widget.kind) {
      case _WindowButtonKind.close:
        return AppColors.danger;
      case _WindowButtonKind.maximize:
      case _WindowButtonKind.restore:
        return AppColors.primary;
      case _WindowButtonKind.minimize:
        return AppColors.textSecondary;
    }
  }

  @override
  Widget build(BuildContext context) {
    final active = _hovered || _focused || _pressed;
    final semantic = _semanticColor;
    final plateColor = switch ((widget.kind, active, _pressed)) {
      (_, _, true) => semantic.withValues(alpha: 0.82),
      (_WindowButtonKind.close, true, false) => semantic.withValues(
        alpha: 0.20,
      ),
      (_WindowButtonKind.maximize, true, false) ||
      (
        _WindowButtonKind.restore,
        true,
        false,
      ) => semantic.withValues(alpha: 0.18),
      (_WindowButtonKind.minimize, true, false) => AppColors.surface3,
      _ => AppColors.surface2,
    };
    final glyphColor = _pressed
        ? AppColors.surface0
        : active
        ? semantic
        : AppColors.textSecondary;

    return Tooltip(
      message: widget.tooltip,
      child: Semantics(
        button: true,
        label: widget.tooltip,
        child: FocusableActionDetector(
          onShowFocusHighlight: (v) => setState(() => _focused = v),
          onShowHoverHighlight: (v) => setState(() => _hovered = v),
          mouseCursor: SystemMouseCursors.click,
          actions: {
            ActivateIntent: CallbackAction<ActivateIntent>(
              onInvoke: (_) {
                widget.onTap();
                return null;
              },
            ),
          },
          child: GestureDetector(
            onTap: widget.onTap,
            onTapDown: (_) => setState(() => _pressed = true),
            onTapUp: (_) => setState(() => _pressed = false),
            onTapCancel: () => setState(() => _pressed = false),
            behavior: HitTestBehavior.opaque,
            child: SizedBox.square(
              dimension: _WindowButton.targetSize,
              child: Center(
                child: AnimatedScale(
                  duration: Motion.duration(context, Nova.press),
                  scale: _pressed ? 0.92 : 1,
                  curve: Curves.easeOutCubic,
                  child: AnimatedContainer(
                    duration: Motion.duration(context, Nova.hover),
                    width: _WindowButton.glyphPlateSize,
                    height: _WindowButton.glyphPlateSize,
                    decoration: BoxDecoration(
                      color: plateColor,
                      borderRadius: BorderRadius.circular(6.2),
                      border: Border.all(
                        color: _focused
                            ? AppColors.focus
                            : active
                            ? semantic.withValues(alpha: 0.34)
                            : AppColors.borderSubtle,
                        width: _focused ? 2 : 1,
                      ),
                    ),
                    child: CustomPaint(
                      painter: _WindowGlyphPainter(
                        kind: widget.kind,
                        color: glyphColor,
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// Original MoOS window-control geometry.
///
/// These glyphs deliberately do not come from Material or another icon font.
/// A 1.7 px round rail and the 6.2 px plate corner match the Aurorae decoration
/// generated by MoOS itself, so the frameless Flutter surface and native KDE
/// windows speak the same visual language.
class _WindowGlyphPainter extends CustomPainter {
  const _WindowGlyphPainter({required this.kind, required this.color});

  final _WindowButtonKind kind;
  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final paint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.7
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round;

    switch (kind) {
      case _WindowButtonKind.close:
        canvas
          ..drawLine(
            center.translate(-3.1, -3.1),
            center.translate(3.1, 3.1),
            paint,
          )
          ..drawLine(
            center.translate(3.1, -3.1),
            center.translate(-3.1, 3.1),
            paint,
          );
      case _WindowButtonKind.minimize:
        canvas.drawLine(
          center.translate(-3.7, 0),
          center.translate(3.7, 0),
          paint,
        );
      case _WindowButtonKind.maximize:
        canvas.drawRRect(
          RRect.fromRectAndRadius(
            Rect.fromCenter(center: center, width: 7.4, height: 7.4),
            const Radius.circular(1.35),
          ),
          paint,
        );
      case _WindowButtonKind.restore:
        canvas
          ..drawRRect(
            RRect.fromRectAndRadius(
              Rect.fromLTWH(center.dx - 2.0, center.dy - 3.7, 6.0, 6.0),
              const Radius.circular(1.1),
            ),
            paint,
          )
          ..drawRRect(
            RRect.fromRectAndRadius(
              Rect.fromLTWH(center.dx - 4.0, center.dy - 1.7, 6.0, 6.0),
              const Radius.circular(1.1),
            ),
            paint,
          );
    }
  }

  @override
  bool shouldRepaint(covariant _WindowGlyphPainter oldDelegate) {
    return oldDelegate.kind != kind || oldDelegate.color != color;
  }
}

/// The eight resize edges a frameless window has to draw for itself.
///
/// This is the bill for going frameless. KWin's decoration would have provided
/// these; without it, the app owns an 6 px border of hit-testing, hands the
/// pointer the right cursor, and asks GTK to begin a resize drag — which the
/// compositor then owns, exactly as it does for a decorated window.
///
/// Suppressed while maximized or fullscreen: a maximized window has no edges to
/// pull, and leaving the regions armed there means a user who clicks near the
/// top of a maximized window unmaximizes it by accident.
class ResizeEdges extends ConsumerWidget {
  const ResizeEdges({super.key, required this.child, required this.enabled});

  final Widget child;
  final bool enabled;

  static const double _thickness = 6;
  static const double _corner = 16;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (!enabled) return child;
    final desktop = ref.watch(desktopServiceProvider);

    Widget grip({
      required ResizeEdge edge,
      required SystemMouseCursor cursor,
      double? left,
      double? top,
      double? right,
      double? bottom,
      double? width,
      double? height,
    }) {
      return Positioned(
        left: left,
        top: top,
        right: right,
        bottom: bottom,
        width: width,
        height: height,
        child: MouseRegion(
          cursor: cursor,
          child: Listener(
            behavior: HitTestBehavior.translucent,
            onPointerDown: (event) {
              if (event.buttons == kPrimaryMouseButton) {
                desktop.startResizing(edge);
              }
            },
            child: const SizedBox.expand(),
          ),
        ),
      );
    }

    return Stack(
      children: [
        Positioned.fill(child: child),

        grip(
          edge: ResizeEdge.top,
          cursor: SystemMouseCursors.resizeUpDown,
          left: _corner,
          right: _corner,
          top: 0,
          height: _thickness,
        ),
        grip(
          edge: ResizeEdge.bottom,
          cursor: SystemMouseCursors.resizeUpDown,
          left: _corner,
          right: _corner,
          bottom: 0,
          height: _thickness,
        ),
        grip(
          edge: ResizeEdge.left,
          cursor: SystemMouseCursors.resizeLeftRight,
          top: _corner,
          bottom: _corner,
          left: 0,
          width: _thickness,
        ),
        grip(
          edge: ResizeEdge.right,
          cursor: SystemMouseCursors.resizeLeftRight,
          top: _corner,
          bottom: _corner,
          right: 0,
          width: _thickness,
        ),

        grip(
          edge: ResizeEdge.topLeft,
          cursor: SystemMouseCursors.resizeUpLeft,
          top: 0,
          left: 0,
          width: _corner,
          height: _corner,
        ),
        grip(
          edge: ResizeEdge.topRight,
          cursor: SystemMouseCursors.resizeUpRight,
          top: 0,
          right: 0,
          width: _corner,
          height: _corner,
        ),
        grip(
          edge: ResizeEdge.bottomLeft,
          cursor: SystemMouseCursors.resizeDownLeft,
          bottom: 0,
          left: 0,
          width: _corner,
          height: _corner,
        ),
        grip(
          edge: ResizeEdge.bottomRight,
          cursor: SystemMouseCursors.resizeDownRight,
          bottom: 0,
          right: 0,
          width: _corner,
          height: _corner,
        ),
      ],
    );
  }
}
