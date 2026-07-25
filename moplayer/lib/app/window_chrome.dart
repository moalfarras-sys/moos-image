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
import '../widgets/app_logo.dart';

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
  const WindowCaption({super.key, required this.onHome, this.breadcrumb});

  /// The logo is the Home action. That is why the dashboard is not a dock slot:
  /// six destinations plus a seventh "Home" is the layout of a website's navbar,
  /// and this is not a website.
  final VoidCallback onHome;

  final String? breadcrumb;

  static const double height = 46;

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
        child: Row(
          children: [
            // The window buttons keep the physical position MoOS's own
            // decoration puts them in — leading-left, in both text directions.
            // A user does not re-learn where the close button is because they
            // switched the interface to Arabic.
            const _WindowButtons(),
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

            // Everything between the identity and the status is drag surface.
            Expanded(child: _DragRegion(desktop: desktop)),

            const _SourceStatus(),
            const SizedBox(width: Nova.space4),
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
  const _HomeButton({required this.onTap, required this.label});

  final VoidCallback onTap;
  final String label;

  @override
  State<_HomeButton> createState() => _HomeButtonState();
}

class _HomeButtonState extends State<_HomeButton> {
  bool _hovered = false;

  @override
  Widget build(BuildContext context) {
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
            onTap: widget.onTap,
            child: AnimatedOpacity(
              duration: Motion.duration(context, Nova.hover),
              opacity: _hovered ? 1.0 : 0.86,
              child: Padding(
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
              ),
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
    final online = ref.watch(connectivityProvider).value ?? true;

    if (playlist == null) return const SizedBox.shrink();

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
      padding: const EdgeInsetsDirectional.only(start: Nova.space4),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          _WindowButton(
            color: const Color(0xFFFF5F57),
            icon: Icons.close_rounded,
            tooltip: s.windowClose,
            onTap: desktop.close,
          ),
          const SizedBox(width: Nova.space2),
          _WindowButton(
            color: const Color(0xFFFEBC2E),
            icon: Icons.remove_rounded,
            tooltip: s.windowMinimize,
            onTap: desktop.minimize,
          ),
          const SizedBox(width: Nova.space2),
          _WindowButton(
            color: const Color(0xFF28C840),
            icon: maximized
                ? Icons.close_fullscreen_rounded
                : Icons.open_in_full_rounded,
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

class _WindowButton extends StatefulWidget {
  const _WindowButton({
    required this.color,
    required this.icon,
    required this.tooltip,
    required this.onTap,
  });

  final Color color;
  final IconData icon;
  final String tooltip;
  final VoidCallback onTap;

  @override
  State<_WindowButton> createState() => _WindowButtonState();
}

class _WindowButtonState extends State<_WindowButton> {
  bool _hovered = false;
  bool _focused = false;

  @override
  Widget build(BuildContext context) {
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
            child: Container(
              width: 14,
              height: 14,
              decoration: BoxDecoration(
                color: widget.color,
                shape: BoxShape.circle,
                border: _focused
                    ? Border.all(color: AppColors.focus, width: 2)
                    : null,
              ),
              // The glyph appears on hover, the way it does on the system's own
              // buttons. It is *not* the only affordance: the colours and their
              // order are, and they are legible without hovering — which is what
              // keeps this usable for someone who cannot use a pointer at all.
              child: AnimatedOpacity(
                duration: Motion.duration(context, Nova.hover),
                opacity: _hovered || _focused ? 1 : 0,
                child: Icon(
                  widget.icon,
                  size: 9,
                  color: const Color(0xCC000000),
                ),
              ),
            ),
          ),
        ),
      ),
    );
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
