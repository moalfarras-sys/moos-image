import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../services/connectivity/connectivity_service.dart';
import 'core_providers.dart';

/// Reactive state that belongs to the *shell* — the window, the dock, the
/// caption bar and the dashboard's widget strip — as opposed to the content.

final connectivityServiceProvider = Provider<ConnectivityService>(
  (ref) => ConnectivityService(),
);

/// Online / offline, as the platform sees it.
///
/// Note what this is not: proof that the *source* is reachable. A machine can be
/// on a network whose IPTV panel is down, and the two states must not be shown
/// as one — see `sourceReachableProvider`, which actually asks the server.
final connectivityProvider = StreamProvider<bool>((ref) async* {
  final service = ref.watch(connectivityServiceProvider);
  yield await service.isOnline;
  yield* service.onStatusChange;
});

/// The clock in the dashboard's widget strip.
///
/// Ticks once a minute, aligned to the top of the minute rather than to whenever
/// the app happened to start — a clock that changes at :17 past is a clock that
/// is wrong for seventeen seconds out of every sixty.
final clockProvider = StreamProvider<DateTime>((ref) async* {
  yield DateTime.now();
  while (true) {
    final now = DateTime.now();
    final untilNextMinute = Duration(
      seconds: 60 - now.second,
      milliseconds: -now.millisecond,
    );
    await Future<void>.delayed(untilNextMinute);
    yield DateTime.now();
  }
});

/// Whether the window is maximized, so the caption bar can draw the right glyph
/// and the shell can drop its rounded corners and resize edges.
final windowMaximizedProvider = StateProvider<bool>((ref) => false);

/// True when the app should stop moving: the user's own *cinematic motion*
/// setting says so.
///
/// The platform's `MediaQuery.disableAnimations` is the other half of this and
/// is read where the widget is built — see `Motion.isReduced`, which checks both.
final reducedMotionProvider = Provider<bool>(
  (ref) => !ref.watch(settingsProvider).cinematicMotion,
);
