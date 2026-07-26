import 'dart:io';

import '../../core/utils/app_logger.dart';
import '../../core/utils/app_paths.dart';

/// A marker on disk that says "a GPU-frame-path start is in progress".
///
/// MoPlayer renders mpv's frames into a GL texture Flutter samples directly.
/// That path is correct and it is what keeps the picture whole — but the way it
/// has historically failed on NVIDIA is the reason this class exists: the driver
/// takes the entire process, with no exception, no coredump and no last log
/// line. Nothing running inside that process can catch it, so there is exactly
/// one place left to notice it — **the launch afterwards**.
///
/// Hence a file, written before the video texture is created and removed once
/// playback has proven itself. A file still present at startup means the run
/// that wrote it never reached either proof.
///
/// It counts rather than latching on the first failure because a power cut, an
/// `Alt+F4` mid-frame or a `pkill` looks identical to a driver crash from here,
/// and none of those should silently cost the user their picture quality. Two in
/// a row is the signal; one is noise.
class VideoPathProbe {
  VideoPathProbe({String? path, this.tripAfter = 2})
    : path = path ?? '${appDataDir()}/video-path.probe';

  /// Consecutive unproven starts before the GPU path is abandoned.
  final int tripAfter;

  final String path;

  bool _cleared = false;

  /// Whether [healthy] has already been recorded for this run.
  bool get isCleared => _cleared;

  /// How many consecutive starts failed to prove themselves.
  ///
  /// A home that cannot be read is survivable everywhere else in this app, and
  /// it is not going to be the thing that decides how video is rendered either:
  /// an unreadable probe counts as zero, i.e. "go ahead".
  int get failures {
    try {
      final file = File(path);
      if (!file.existsSync()) return 0;
      final parsed = int.tryParse(file.readAsStringSync().trim());
      if (parsed == null || parsed < 0) return 0;
      return parsed;
    } on Object {
      return 0;
    }
  }

  /// Whether the GPU path has failed often enough to stop trying it.
  bool get isTripped => failures >= tripAfter;

  /// Record that a GPU-path start is beginning. Undone by [healthy].
  void armed() {
    try {
      final file = File(path);
      file.parent.createSync(recursive: true);
      file.writeAsStringSync('${failures + 1}');
    } on Object catch (e) {
      log.w('video: could not write the frame-path probe ($e)');
    }
  }

  /// The GPU path survived.
  ///
  /// Forgets every previous failure rather than decrementing: a driver update
  /// that fixes the crash should restore the good path immediately, not after as
  /// many good runs as there were bad ones.
  void healthy() {
    if (_cleared) return;
    _cleared = true;
    try {
      final file = File(path);
      if (file.existsSync()) file.deleteSync();
    } on Object catch (e) {
      log.w('video: could not clear the frame-path probe ($e)');
    }
  }
}
