import 'package:flutter/material.dart';

import '../core/theme/app_colors.dart';

/// The app's canvas: the Nova Cinema scene gradient, with two ember blooms
/// bleeding in from opposite corners.
///
/// The blooms are `IgnorePointer`-wrapped and painted with a radial gradient
/// rather than a blurred layer — a `BackdropFilter` this large would cost a
/// full-screen save-layer on every frame, and this thing is behind *everything*.
class SceneBackdrop extends StatelessWidget {
  const SceneBackdrop({super.key, required this.child, this.showGlow = true});

  final Widget child;
  final bool showGlow;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: const BoxDecoration(gradient: AppColors.sceneGradient),
      child: Stack(
        children: [
          if (showGlow) ...[
            const Positioned(
              top: -140,
              left: -100,
              child: _Bloom(color: AppColors.primary, size: 420, opacity: 0.13),
            ),
            const Positioned(
              bottom: -160,
              right: -120,
              child: _Bloom(color: AppColors.ember, size: 480, opacity: 0.10),
            ),
          ],
          Positioned.fill(child: child),
        ],
      ),
    );
  }
}

class _Bloom extends StatelessWidget {
  const _Bloom({required this.color, required this.size, required this.opacity});

  final Color color;
  final double size;
  final double opacity;

  @override
  Widget build(BuildContext context) {
    return IgnorePointer(
      child: Container(
        width: size,
        height: size,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          gradient: AppColors.glow(color, opacity: opacity),
        ),
      ),
    );
  }
}
