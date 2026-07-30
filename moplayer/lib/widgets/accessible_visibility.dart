import 'package:flutter/widgets.dart';

/// Keeps an animated-but-hidden control subtree out of every interaction path.
///
/// Opacity only changes paint, and [IgnorePointer] only changes hit testing.
/// Without the other two guards, Tab can still move into an invisible button
/// and a screen reader can still announce controls that are not on screen.
class AccessibleVisibility extends StatelessWidget {
  const AccessibleVisibility({
    super.key,
    required this.visible,
    required this.child,
  });

  final bool visible;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return ExcludeSemantics(
      excluding: !visible,
      child: ExcludeFocus(
        excluding: !visible,
        child: IgnorePointer(ignoring: !visible, child: child),
      ),
    );
  }
}
