import 'dart:io' show Platform;

import 'package:flutter/foundation.dart';
import 'package:logger/logger.dart';

/// Shared logger. Verbose in debug, quiet in release — but not *deaf* in
/// release: `MOPLAYER_LOG=info|debug|trace` turns it back on.
///
/// That escape hatch is not a convenience. A release build is the only build a
/// user ever runs, and "it opened off the side of the screen" is a bug that
/// exists only there. Without a way to raise the level on the machine where the
/// fault actually happens, the answer to every field report is "rebuild it in
/// debug and try again", which is not an answer.
Level _level() {
  final requested = Platform.environment['MOPLAYER_LOG']?.toLowerCase();
  return switch (requested) {
    'trace' => Level.trace,
    'debug' => Level.debug,
    'info' => Level.info,
    'warning' => Level.warning,
    'error' => Level.error,
    'off' => Level.off,
    _ => kReleaseMode ? Level.warning : Level.debug,
  };
}

final Logger log = Logger(
  level: _level(),
  printer: PrettyPrinter(
    methodCount: 0,
    errorMethodCount: 6,
    lineLength: 90,
    colors: false,
    printEmojis: true,
    dateTimeFormat: DateTimeFormat.none,
  ),
);

/// Removes stream/source URLs and common credential fields from diagnostics.
///
/// mpv and Dio include the failed URI in many exceptions. Xtream puts the
/// username and password in that URI, while signed M3U links put bearer tokens
/// there. Release warnings go to the session journal even when the optional log
/// file is off, so every call site that logs a network/player exception passes
/// through this function.
String safeLogMessage(Object value) {
  var text = value.toString();
  text = text.replaceAll(
    RegExp(r'(?:https?|rtsp)://[^\s"<>]+', caseSensitive: false),
    '<redacted-url>',
  );
  text = text.replaceAllMapped(
    RegExp(
      r'((?:username|user|password|pass|token|key)=)[^&\s,;]+',
      caseSensitive: false,
    ),
    (match) => '${match.group(1)}<redacted>',
  );
  return text;
}
