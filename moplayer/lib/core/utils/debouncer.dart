import 'dart:async';

import 'package:flutter/foundation.dart';

/// Debounces rapid calls (used by the search field) to a single trailing call.
class Debouncer {
  Debouncer({this.delay = const Duration(milliseconds: 350)});

  final Duration delay;
  Timer? _timer;

  void run(VoidCallback action) {
    _timer?.cancel();
    _timer = Timer(delay, action);
  }

  void dispose() => _timer?.cancel();
}
