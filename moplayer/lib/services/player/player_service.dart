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
          // The time-based cache below is still bounded by this byte ceiling.
          // 32 MiB held roughly twenty seconds of ordinary 1080p, but only a few
          // seconds of the high-bitrate 4K channels that need the cushion most.
          // 64 MiB remains modest for a desktop player and stops the byte limit
          // from silently defeating the twenty-second IPTV cache.
          bufferSize: 64 * 1024 * 1024,
          title: 'MoPlayer',
        ),
      ) {
    final gpuTexturePath = _useGpuTexturePath();
    _gpuTexturePath = gpuTexturePath;
    _controller = VideoController(
      _player,
      configuration: VideoControllerConfiguration(
        enableHardwareAcceleration: gpuTexturePath,
        // media_kit's Linux software texture is a CPU-rendered pixel buffer.
        // At its built-in 1920x1080 ceiling, a 60 fps stream saturates one core
        // and the producer can overtake Flutter while it copies the same
        // buffer, which appears as horizontal frame breaks. 1280x720 cuts the
        // copy to 44% of those pixels and stays comfortably ahead of the
        // compositor. Decoding remains NVDEC/VAAPI through hwdec below.
        width: gpuTexturePath ? null : 1280,
        height: gpuTexturePath ? null : 720,
      ),
    );
    if (!gpuTexturePath) {
      // media_kit 2.0.1 applies the source dimensions again when video
      // parameters arrive, even when a fixed output size was configured. Put
      // the safe size back after that notification; otherwise the first 1080p
      // frame silently defeats the anti-tearing limit above.
      _safeSizeSubscription = _player.stream.videoParams.listen((params) {
        if ((params.dw ?? 0) <= 0 || (params.dh ?? 0) <= 0) return;
        unawaited(
          Future<void>.delayed(const Duration(milliseconds: 60)).then((
            _,
          ) async {
            await _applySafeOutputSize();
          }),
        );
      });
    }
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
  /// The cost of the CPU copy is real, which is why the safe path is bounded to
  /// 720p below. The cost of the crash is the whole app. On a machine where one
  /// of the two is a coin flip, the choice makes itself.
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
  late final bool _gpuTexturePath;
  late final VideoController _controller;
  StreamSubscription<Object?>? _safeSizeSubscription;
  int _safeOutputWidth = 1280;
  int _safeOutputHeight = 720;

  Player get player => _player;
  VideoController get controller => _controller;

  PlayableMedia? _current;
  PlayableMedia? get current => _current;
  int _mediaGeneration = 0;

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

  /// The mini player is 104×58 logical pixels. Keeping a 720p software texture
  /// alive behind it wastes a full CPU core while the user browses the guide.
  /// A 640×360 surface is still much larger than the preview; expanding the
  /// player restores the clean 720p NVIDIA-safe surface immediately.
  Future<void> setCompactVideoOutput(bool compact) async {
    if (_gpuTexturePath) return;
    _safeOutputWidth = compact ? 640 : 1280;
    _safeOutputHeight = compact ? 360 : 720;
    await _applySafeOutputSize();
  }

  Future<void> _applySafeOutputSize() async {
    if (_gpuTexturePath) return;
    // Force the platform call. The controller's cached width can still say
    // 1280 after its own video-params listener has secretly sent 1920 to native
    // code, so a direct 1280 call is incorrectly treated as a no-op.
    await _controller.setSize();
    await _controller.setSize(
      width: _safeOutputWidth,
      height: _safeOutputHeight,
    );
  }

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
    // Do not show one second, stall, show another second, and repeat. mpv's
    // default starts immediately and resumes an underrun with only one second
    // buffered; unreliable IPTV then looks like a decoder problem. A two-second
    // initial/resume cushion trades a small, visible "Buffering" wait for steady
    // playback once frames begin.
    set('cache-pause', 'yes');
    set('cache-pause-initial', 'yes');
    set('cache-pause-wait', '2');
    // Let mpv pick a hardware decoder, but only one it can prove works —
    // 'auto-safe' is what keeps a broken VAAPI stack from producing a black
    // window instead of falling back to software.
    set('hwdec', 'auto-safe');
  }

  Future<void> open(PlayableMedia media) async {
    final generation = ++_mediaGeneration;
    _current = media;
    await _player.open(
      Media(media.url, httpHeaders: media.headers),
      play: true,
    );
    if (generation != _mediaGeneration || !identical(_current, media)) return;

    if (media.startAt > Duration.zero && !media.isLive) {
      // Seek only once the demuxer knows how long the file is; seeking before
      // that silently lands at zero. The generation check is load-bearing: if
      // the user selects another film while this duration is still unknown, the
      // old resume callback must not seek the new film to the old film's time.
      unawaited(
        _player.stream.duration
            .firstWhere((d) => d > Duration.zero)
            .then((_) async {
              if (generation != _mediaGeneration ||
                  !identical(_current, media)) {
                return;
              }
              await _player.seek(media.startAt);
            })
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
    _mediaGeneration++;
    _current = null;
    await _player.stop();
  }

  Future<void> dispose() async {
    _mediaGeneration++;
    _current = null;
    await _safeSizeSubscription?.cancel();
    await _player.dispose();
  }
}
