/// How mpv is told to handle interlaced video.
///
/// The default is [auto] and that choice is load-bearing for an IPTV player —
/// see `PlayerService._tuneForIptv`. It is exposed to the user because the
/// automatic answer depends on the stream announcing its own field order
/// honestly, and a re-encoded channel frequently does not: some claim
/// progressive while sending fields, and some claim interlaced while sending
/// progressive frames that then get needlessly softened.
enum DeinterlaceMode {
  /// Never deinterlace. Correct for genuinely progressive video, and the right
  /// answer when a channel is mislabelled interlaced and looks soft.
  off('no'),

  /// Deinterlace only streams that say they are interlaced. The default.
  auto('auto'),

  /// Always deinterlace, whatever the stream claims. The escape hatch for a
  /// channel that combs visibly while announcing itself progressive.
  on('yes');

  const DeinterlaceMode(this.mpvValue);

  /// The literal mpv property value. Kept next to the enum so the mapping
  /// cannot drift from what is actually sent to the engine.
  final String mpvValue;
}

/// The picture controls mpv applies during rendering.
///
/// mpv calls these the video equalizer and applies them on the GPU while
/// drawing, so they cost nothing and take effect on the next frame — unlike a
/// filter chain, which has to be rebuilt.
enum PictureAdjustment {
  brightness('brightness'),
  contrast('contrast'),
  saturation('saturation'),
  gamma('gamma');

  const PictureAdjustment(this.mpvProperty);

  /// The literal mpv property. Each takes -100..100 and defaults to 0.
  final String mpvProperty;
}

/// How far a live stream can currently be scrubbed, and where in that window
/// the viewer is.
///
/// A live channel has no duration to seek against — the seek bar's usual
/// arithmetic does not apply. What it has instead is a *moving window*: mpv
/// holds packets from [start] up to the newest it has demuxed at [edge], and
/// both ends advance in real time. The window also grows for the first few
/// minutes a channel is open, until it reaches the configured back-buffer
/// ceiling, so this has to be read from the engine rather than assumed.
class TimeshiftWindow {
  const TimeshiftWindow({
    required this.start,
    required this.edge,
    required this.position,
  });

  static const empty = TimeshiftWindow(
    start: Duration.zero,
    edge: Duration.zero,
    position: Duration.zero,
  );

  /// Earliest point mpv can still seek to.
  final Duration start;

  /// The live edge — the newest demuxed timestamp.
  final Duration edge;

  /// Where playback currently is.
  final Duration position;

  Duration get span => edge - start;

  /// How far behind live the viewer is.
  Duration get behind {
    final value = edge - position;
    return value.isNegative ? Duration.zero : value;
  }

  /// Whether there is enough of a window to be worth offering a scrub.
  ///
  /// Below a couple of seconds the bar would be a control that cannot move,
  /// which reads as broken rather than as not-yet-ready.
  bool get isSeekable => span.inMilliseconds > 2000;

  /// Treated as live when within a second of the edge: a stream is never
  /// exactly at its newest packet, and a "back to live" button that stays lit
  /// while the user is watching live is a button that looks stuck.
  bool get isAtLiveEdge => behind.inMilliseconds < 1000;
}

/// A snapshot of what the playback engine is doing, read live from mpv.
///
/// Every serious player has this screen — mpv's own `i`, VLC's statistics,
/// Kodi's codec overlay — for a reason that is not vanity: "the video is not
/// smooth" has at least four unrelated causes, and they are indistinguishable
/// from the outside. Software decoding, a source that is genuinely 720p, a
/// network that is starving the cache and a display running at a frequency the
/// frame rate does not divide all look identical to a viewer, and produce
/// completely different numbers here.
class PlaybackStats {
  const PlaybackStats({
    this.hwdec,
    this.videoCodec,
    this.width,
    this.height,
    this.containerFps,
    this.currentFps,
    this.droppedFrames,
    this.decoderDroppedFrames,
    this.videoBitrate,
    this.audioCodec,
    this.audioChannels,
    this.cacheSeconds,
    this.pixelFormat,
  });

  /// The active hardware decoder (`nvdec`, `vaapi`, …), or null for software.
  ///
  /// The single most useful number on this screen. If this is null on a 4K
  /// stream, nothing else about the pipeline matters until it is not.
  final String? hwdec;

  final String? videoCodec;
  final int? width;
  final int? height;

  /// What the container claims, against what is being displayed. A [currentFps]
  /// well below [containerFps] is the machine failing to keep up; the two being
  /// equal while playback still looks wrong points at pacing, not throughput.
  final double? containerFps;
  final double? currentFps;

  /// Frames the output dropped to stay in sync, and frames the decoder never
  /// finished. The second is the more serious of the two.
  final int? droppedFrames;
  final int? decoderDroppedFrames;

  final double? videoBitrate;
  final String? audioCodec;
  final int? audioChannels;

  /// Seconds of stream buffered ahead. On IPTV this is the number that predicts
  /// a stall before the viewer sees one.
  final double? cacheSeconds;

  final String? pixelFormat;

  bool get isHardwareDecoded => hwdec != null && hwdec!.isNotEmpty;

  String? get resolution =>
      (width != null && height != null && width! > 0 && height! > 0)
      ? '$width×$height'
      : null;

  /// The marketing name for the height, which is what a viewer recognises.
  String? get qualityLabel {
    final h = height;
    if (h == null || h <= 0) return null;
    if (h >= 2000) return '4K';
    if (h >= 1400) return '1440p';
    if (h >= 1000) return '1080p';
    if (h >= 700) return '720p';
    if (h >= 500) return '576p';
    return '${h}p';
  }
}
