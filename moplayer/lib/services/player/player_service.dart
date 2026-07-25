import 'dart:async';
import 'dart:io';

import 'package:media_kit/media_kit.dart';
import 'package:media_kit_video/media_kit_video.dart';

import '../../core/config/app_config.dart';
import '../../core/utils/app_logger.dart';
import '../../models/media_kind.dart';

/// A description of something to play.
class PlayableMedia {
  const PlayableMedia({
    required this.url,
    required this.title,
    required this.kind,
    this.subtitle,
    this.artUrl,
    this.startAt = Duration.zero,
    this.headers = const {'User-Agent': AppConfig.userAgent},
  });

  final String url;
  final String title;
  final String? subtitle;

  /// Poster or channel logo. The video surface never shows it — it is what the
  /// desktop's media applet and the mini player display.
  final String? artUrl;
  final MediaKind kind;
  final Duration startAt;
  final Map<String, String> headers;

  bool get isLive => kind == MediaKind.live;

  PlayableMedia copyWith({Duration? startAt}) => PlayableMedia(
    url: url,
    title: title,
    kind: kind,
    subtitle: subtitle,
    artUrl: artUrl,
    startAt: startAt ?? this.startAt,
    headers: headers,
  );
}

/// Wraps one media_kit [Player] and its [VideoController].
///
/// On Linux, media_kit *is* libmpv — the same engine MoOS already ships as
/// `mpv-libs`. That is why this app can play the MPEG-TS and HLS a real IPTV
/// panel serves, which Qt Multimedia's FFmpeg backend regularly cannot.
///
/// There is exactly **one** of these for the whole app, owned by a Riverpod
/// provider. That is what lets a stream survive navigation: leaving the player
/// route hands the same [controller] to the mini player instead of tearing the
/// pipeline down and re-buffering the channel from scratch.
class PlayerService {
  PlayerService()
    : _player = Player(
        configuration: const PlayerConfiguration(
          // Big enough to ride out an IPTV panel's hiccups, small enough that a
          // live channel still starts in about a second.
          bufferSize: 32 * 1024 * 1024,
          title: 'MoPlayer',
        ),
      ) {
    _controller = VideoController(
      _player,
      configuration: VideoControllerConfiguration(
        enableHardwareAcceleration: _useGpuTexturePath(),
      ),
    );
    _tuneForIptv();
  }

  /// Whether mpv hands its frames to Flutter through a shared GL texture.
  ///
  /// This is **not** hardware *decoding* — that is `hwdec`, set below, and it
  /// stays on either way. This is only how the decoded frame reaches the Flutter
  /// texture: a zero-copy GL interop, or a CPU copy.
  ///
  /// It is off by default on NVIDIA because the interop path crashes there. On
  /// this machine — an RTX 2080 SUPER on the open kernel module, under Plasma
  /// Wayland, which is exactly what the MoOS NVIDIA image targets — the app died
  /// silently the moment media_kit logged `Using H/W rendering` and resized the
  /// texture to 1920x1080. It did not crash on the runs where media_kit happened
  /// to fall back to the CPU path, and media_kit's own documentation says as much:
  /// *"disabling the option may improve stability on certain devices"*.
  ///
  /// The cost of the CPU copy is a few percent of one core at 1080p, because the
  /// GPU is still doing the decoding. The cost of the crash is the whole app. On
  /// a machine where one of the two is a coin flip, the choice makes itself.
  ///
  /// `MOPLAYER_VIDEO_HW=1` forces the GL path back on — for when a future driver
  /// or media_kit release fixes it, and to make that testable without a rebuild.
  static bool _useGpuTexturePath() {
    final override = Platform.environment['MOPLAYER_VIDEO_HW'];
    if (override == '1') return true;
    if (override == '0') return false;

    final isNvidia =
        File('/proc/driver/nvidia/version').existsSync() ||
        Directory('/sys/module/nvidia_drm').existsSync();
    if (isNvidia) {
      log.i(
        'video: NVIDIA detected — using the CPU frame path (see PlayerService)',
      );
      return false;
    }
    return true;
  }

  final Player _player;
  late final VideoController _controller;

  Player get player => _player;
  VideoController get controller => _controller;

  PlayableMedia? _current;
  PlayableMedia? get current => _current;

  // Streams the UI listens to.
  Stream<Duration> get positionStream => _player.stream.position;
  Stream<Duration> get durationStream => _player.stream.duration;
  Stream<bool> get bufferingStream => _player.stream.buffering;
  Stream<bool> get playingStream => _player.stream.playing;
  Stream<bool> get completedStream => _player.stream.completed;
  Stream<String> get errorStream => _player.stream.error;
  Stream<Tracks> get tracksStream => _player.stream.tracks;
  Stream<Track> get selectedTrackStream => _player.stream.track;
  Stream<double> get volumeStream => _player.stream.volume;
  Stream<double> get rateStream => _player.stream.rate;

  Duration get position => _player.state.position;
  Duration get duration => _player.state.duration;
  bool get isPlaying => _player.state.playing;
  bool get isBuffering => _player.state.buffering;
  double get volume => _player.state.volume;
  double get rate => _player.state.rate;
  Tracks get tracks => _player.state.tracks;
  Track get selectedTrack => _player.state.track;

  /// mpv options that matter for IPTV and that media_kit's own configuration
  /// cannot express.
  ///
  /// An IPTV panel is not a CDN: it drops connections mid-stream, stalls for
  /// seconds on a channel switch, and often just closes the socket. Left at
  /// mpv's defaults the player hangs on a dead stream forever instead of
  /// surfacing an error the UI can retry.
  void _tuneForIptv() {
    final platform = _player.platform;
    if (platform is! NativePlayer) return;

    void set(String name, String value) {
      platform.setProperty(name, value).catchError((Object e) {
        log.w('mpv: could not set $name=$value ($e)');
      });
    }

    // Fail a dead server in 15 s instead of hanging on it.
    set('network-timeout', '15');
    // Reconnect inside FFmpeg's HTTP layer on a mid-stream drop — the most
    // common IPTV failure, and one the app should not even have to see.
    set(
      'demuxer-lavf-o',
      'reconnect=1,reconnect_streamed=1,reconnect_delay_max=5,reconnect_on_network_error=1',
    );
    set('user-agent', AppConfig.userAgent);
    // A live-edge buffer; without it a channel stutters on every jitter.
    set('cache', 'yes');
    set('cache-secs', '20');
    set('demuxer-readahead-secs', '20');
    // Let mpv pick a hardware decoder, but only one it can prove works —
    // 'auto-safe' is what keeps a broken VAAPI stack from producing a black
    // window instead of falling back to software.
    set('hwdec', 'auto-safe');
  }

  Future<void> open(PlayableMedia media) async {
    _current = media;
    await _player.open(
      Media(media.url, httpHeaders: media.headers),
      play: true,
    );
    if (media.startAt > Duration.zero && !media.isLive) {
      // Seek only once the demuxer knows how long the file is; seeking before
      // that silently lands at zero.
      unawaited(
        _player.stream.duration
            .firstWhere((d) => d > Duration.zero)
            .then((_) => _player.seek(media.startAt))
            .catchError((Object _) {}),
      );
    }
  }

  Future<void> playOrPause() => _player.playOrPause();
  Future<void> play() => _player.play();
  Future<void> pause() => _player.pause();
  Future<void> seek(Duration position) => _player.seek(position);

  /// Relative seek, clamped to the media. A live stream ignores it.
  Future<void> seekBy(Duration delta) async {
    if (_current?.isLive ?? false) return;
    final target = position + delta;
    final max = duration;
    await _player.seek(
      target < Duration.zero
          ? Duration.zero
          : (max > Duration.zero && target > max ? max : target),
    );
  }

  /// media_kit's volume is 0–100, not 0–1.
  Future<void> setVolume(double volume) =>
      _player.setVolume(volume.clamp(0, 100));
  Future<void> setRate(double rate) => _player.setRate(rate);
  Future<void> setAudioTrack(AudioTrack track) => _player.setAudioTrack(track);
  Future<void> setSubtitleTrack(SubtitleTrack track) =>
      _player.setSubtitleTrack(track);

  Future<void> stop() async {
    _current = null;
    await _player.stop();
  }

  Future<void> dispose() async {
    _current = null;
    await _player.dispose();
  }
}
