import 'dart:async';
import 'dart:io';

import 'package:media_kit/media_kit.dart';
import 'package:media_kit_video/media_kit_video.dart';

import '../../core/config/app_config.dart';
import '../../core/utils/app_logger.dart';
import '../../models/media_kind.dart';
import 'playback_stats.dart';
import 'video_path_probe.dart';

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
    if (gpuTexturePath) _videoPathProbe.armed();
    _controller = VideoController(
      _player,
      configuration: VideoControllerConfiguration(
        enableHardwareAcceleration: gpuTexturePath,
        // The GPU path renders straight into the texture Flutter samples, so it
        // takes the stream's own resolution. The software fallback cannot: see
        // [_applySafeOutputSize].
        width: gpuTexturePath ? null : 1280,
        height: gpuTexturePath ? null : 720,
      ),
    );
    if (gpuTexturePath) {
      _watchForHealthyPlayback();
    } else {
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
  /// **This used to be off on NVIDIA, and turning it back on is the fix for the
  /// torn picture.** The reason it was off is real and is worth keeping written
  /// down: under media_kit_video 1.x the app died silently on this machine — an
  /// RTX 2080 SUPER on the open kernel module, Plasma Wayland — the moment
  /// media_kit logged `Using H/W rendering` and resized the texture to
  /// 1920x1080. What it did *not* say at the time was why: 1.x rendered mpv's
  /// frames on **Flutter's own EGL context**, and two threads driving one
  /// context is undefined behaviour that NVIDIA's driver answers by taking the
  /// process with it.
  ///
  /// media_kit_video 2.0 renders on an isolated context of its own. The log line
  /// is now `H/W rendering with isolated EGL context.`, and on this machine
  /// (driver 610.43.03) it plays 1080p indefinitely instead of dying in the
  /// first second. `pubspec.yaml` moved to 2.0.1 in the 1.2 overhaul; this guard
  /// simply had not been re-tested against it.
  ///
  /// The CPU path it replaces is not merely slower, it is *incorrect*:
  /// media_kit's `texture_sw_copy_pixels` hands Flutter's raster thread a raw
  /// pointer to the one pixel buffer that mpv's render callback is concurrently
  /// writing into — and takes the buffer's mutex on the writer side only. There
  /// is one buffer and no fence, so a frame Flutter uploads while mpv is midway
  /// through the next one is half old and half new. That is the horizontal break
  /// in the picture. Clamping the surface to 720p (below) shrinks the window the
  /// race can land in, which is why it looked fixed; it cannot close it, and it
  /// pays for the attempt by upscaling every stream from 720p.
  ///
  /// The GL path has no such window: mpv renders into the texture Flutter
  /// samples, and there is no shared CPU buffer to tear.
  ///
  /// Overrides, both without a rebuild:
  ///   * `MOPLAYER_VIDEO_HW=0` — force the CPU path back, if a future driver
  ///     regresses on a machine that cannot wait for a fix.
  ///   * `MOPLAYER_VIDEO_HW=1` — force the GL path on even after the guard below
  ///     has tripped.
  static bool _useGpuTexturePath() {
    final override = Platform.environment['MOPLAYER_VIDEO_HW'];
    if (override == '1') return true;
    if (override == '0') {
      log.i('video: MOPLAYER_VIDEO_HW=0 — using the CPU frame path');
      return false;
    }

    // The safety net. If the GL path ever does take the process down again, it
    // does so before any of this code could react — so the check is made on the
    // *next* launch instead, from a marker the previous one left behind. Two
    // starts in a row that never reached healthy playback and never shut down
    // cleanly, and the app falls back to the CPU path by itself rather than
    // becoming a window that dies every time it is opened.
    if (_videoPathProbe.isTripped) {
      log.w(
        'video: the GPU frame path failed to start twice — falling back to the '
        'CPU path. Re-arm with MOPLAYER_VIDEO_HW=1, or delete '
        '${_videoPathProbe.path}',
      );
      return false;
    }
    return true;
  }

  static final VideoPathProbe _videoPathProbe = VideoPathProbe();

  /// Clears the crash probe once the GL path has demonstrably survived the point
  /// where it used to die — which was within a second or two of the first frame,
  /// right after the texture resized to the video's size.
  ///
  /// Ten seconds of continuous playback is well past that, and is short enough
  /// that an ordinary "open it, play something, watch it" session clears the
  /// marker long before the user closes the window.
  void _watchForHealthyPlayback() {
    _healthySubscription = _player.stream.playing.listen((playing) {
      if (!playing || _videoPathProbe.isCleared) return;
      _healthyTimer?.cancel();
      _healthyTimer = Timer(const Duration(seconds: 10), () {
        if (_player.state.playing) _videoPathProbe.healthy();
      });
    });
  }

  final Player _player;
  late final bool _gpuTexturePath;
  late final VideoController _controller;
  StreamSubscription<Object?>? _safeSizeSubscription;
  StreamSubscription<bool>? _healthySubscription;
  Timer? _healthyTimer;
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

  /// Shrinks the software surface while only the mini player is showing it.
  ///
  /// A no-op on the GPU path, which costs nothing per pixel. On the CPU
  /// fallback the mini player is 104×58 logical pixels, and keeping a 720p
  /// software texture alive behind it wastes a full core while the user browses
  /// the guide. 640×360 is still far larger than the preview; expanding the
  /// player restores the full fallback surface immediately.
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

    // **Deinterlacing.** This is the setting that decides whether a real IPTV
    // subscription looks broken.
    //
    // A very large share of live channels are broadcast 1080i or 576i —
    // interlaced — because that is what the satellite and cable feeds they are
    // restreamed from are. Each frame is two fields captured 20 ms apart. Shown
    // without deinterlacing, anything that moves grows a comb of alternating
    // horizontal lines along its edges, and a viewer describes that exactly the
    // way a torn frame is described: the picture is breaking up.
    //
    // mpv's default is `deinterlace=no`, which is the right default for a file
    // player being handed progressive video and the wrong one for live TV.
    // `auto` deinterlaces only streams that announce themselves as interlaced,
    // so progressive channels and VOD pay nothing for it.
    // Deliberately *not* accompanied by a manual `vf` deinterlacer: mpv inserts
    // its own (bwdif, on 0.38+) for this property, and a hand-set filter chain
    // would deinterlace a second time rather than better.
    set('deinterlace', 'auto');

    // Decode threads: one per core. mpv's default guesses conservatively, and
    // an IPTV panel can hand this app 4K HEVC that the guess cannot sustain.
    set('vd-lavc-threads', '0');

    // **Timeshift.** What lets a live channel be paused and rewound.
    //
    // mpv keeps demuxed packets it has already played in a back buffer, and can
    // seek inside it — so "pause live TV" needs no separate recording pipeline,
    // only somewhere to keep the recent past. mpv's default back buffer is tiny
    // because a file player can simply re-read the file; a live stream cannot.
    //
    // 256 MiB is a few minutes of a typical 6–10 Mb/s channel and a shorter but
    // still useful window on a 4K one. It is a ceiling, not an allocation:
    // nothing is reserved until a stream actually fills it.
    set('demuxer-max-back-bytes', '${256 * 1024 * 1024}');
  }

  /// Frame pacing, chosen per media kind.
  ///
  /// `display-resample` is mpv's smooth path: it resamples audio slightly so
  /// video frames land on real display refreshes, which is what removes the
  /// periodic judder of a 24 or 30 fps film on a 60 Hz panel. It needs a stable
  /// clock, so it is the right choice for VOD.
  ///
  /// A live stream has no such luxury — its clock is the server's, it drifts,
  /// and resampling against a drifting source trades judder for audio artefacts
  /// and eventual desync. Live therefore stays on `audio`, mpv's default, which
  /// keeps A/V locked and tolerates a jittery source.
  void _applyFramePacing(MediaKind kind) {
    final platform = _player.platform;
    if (platform is! NativePlayer) return;
    final mode = kind == MediaKind.live ? 'audio' : 'display-resample';
    platform.setProperty('video-sync', mode).catchError((Object e) {
      log.w('mpv: could not set video-sync=$mode ($e)');
    });
  }

  Future<void> open(PlayableMedia media) async {
    final generation = ++_mediaGeneration;
    _current = media;
    _applyFramePacing(media.kind);
    await _player.open(
      Media(media.url, httpHeaders: media.headers),
      play: true,
    );
    if (generation != _mediaGeneration || !identical(_current, media)) return;

    _logPlaybackSummary(generation);

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

  /// Relative seek, clamped to the media.
  ///
  /// A live stream is no longer refused. With a back buffer configured (see
  /// `_tuneForIptv`) mpv can seek inside the packets it has already played, so
  /// rewinding a goal or catching up after a pause works on live TV exactly as
  /// it does on a film — bounded by [timeshiftAvailable] rather than by a
  /// duration, and clamped by mpv itself at the live edge.
  Future<void> seekBy(Duration delta) async {
    if (_current?.isLive ?? false) {
      // No `max` to clamp against: a live stream's duration is not its live
      // edge. mpv refuses to seek past what it holds, which is the correct
      // boundary and the only one that is actually known here.
      final target = position + delta;
      await _player.seek(target < Duration.zero ? Duration.zero : target);
      return;
    }
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

  Future<void> setVideoTrack(VideoTrack track) => _player.setVideoTrack(track);

  /// Writes one line to the journal describing what the engine settled on.
  ///
  /// mpv's own CLI prints this and it is the first thing anyone asks for in a
  /// bug report: which decoder, what resolution, which frame path. A user
  /// reporting "the picture is bad" cannot be expected to open a panel and read
  /// numbers aloud, but they can be asked for a log — and this is the line that
  /// makes that log worth having.
  ///
  /// Deliberately no URL: `safeLogMessage` exists because an Xtream stream URL
  /// carries the subscription's username and password, and this line goes to
  /// the session journal.
  void _logPlaybackSummary(int generation) {
    unawaited(
      // Wait for a decoded frame — before one exists mpv has no width, no codec
      // and no hwdec to report, so an immediate read would log a row of blanks.
      _player.stream.width
          .firstWhere((w) => (w ?? 0) > 0)
          .timeout(const Duration(seconds: 20))
          .then((_) async {
            if (generation != _mediaGeneration) return;
            final stats = await readStats();
            log.i(
              'playback: ${stats.resolution ?? "?"} '
              '${stats.videoCodec ?? "?"} @ '
              '${stats.containerFps?.toStringAsFixed(2) ?? "?"}fps · '
              'decode=${stats.hwdec ?? "software"} · '
              'frames=${_gpuTexturePath ? "gpu/gl" : "cpu/copy"} · '
              'audio=${stats.audioCodec ?? "?"}',
            );
          })
          .catchError((Object _) {}),
    );
  }

  // ---------------------------------------------------------------------------
  // Fine tuning.
  //
  // Everything below is a live mpv property rather than app state: the engine is
  // the single source of truth, so a value set here survives a track change and
  // is read back by the UI instead of being mirrored in a provider that can
  // drift out of step with what is actually playing.
  // ---------------------------------------------------------------------------

  /// Shifts the subtitles in time, in seconds. Positive shows them later.
  ///
  /// Not a nicety on IPTV: a panel that muxes a subtitle track from a different
  /// source than the video routinely lands it a second or two out, and without
  /// this the track is unusable rather than merely imperfect.
  Future<void> setSubtitleDelay(double seconds) =>
      _setDouble('sub-delay', seconds.clamp(-60, 60));
  Future<double> get subtitleDelay => _getDouble('sub-delay');

  /// Shifts the audio in time, in seconds. Positive plays it later.
  ///
  /// The lip-sync control. Re-encoded live channels drift, and a viewer can see
  /// 100 ms of it.
  Future<void> setAudioDelay(double seconds) =>
      _setDouble('audio-delay', seconds.clamp(-60, 60));
  Future<double> get audioDelay => _getDouble('audio-delay');

  /// Subtitle size as a multiplier of the default.
  Future<void> setSubtitleScale(double scale) =>
      _setDouble('sub-scale', scale.clamp(0.25, 4));
  Future<double> get subtitleScale => _getDouble('sub-scale');

  /// Whether mpv draws a shaded box behind subtitles. On a bright scene white
  /// text on nothing is unreadable, which is why every player that ships
  /// subtitles ships this too.
  Future<void> setSubtitleBackground(bool enabled) async {
    final platform = _player.platform;
    if (platform is! NativePlayer) return;
    await platform
        .setProperty('sub-back-color', enabled ? '#80000000' : '#00000000')
        .catchError((Object e) => log.w('mpv: sub-back-color ($e)'));
  }

  /// Loads a subtitle file the user picked off disk.
  Future<void> addSubtitleFile(String path) async {
    final platform = _player.platform;
    if (platform is! NativePlayer) return;
    // `select` makes it the active track immediately — a user who just chose a
    // file means to see it, not to then find it in a menu.
    await platform.command(['sub-add', path, 'select']).catchError((Object e) {
      log.w('mpv: could not add subtitle file ($e)');
    });
  }

  /// Evens out the loudness difference between channels.
  ///
  /// A real subscription is assembled from dozens of sources with no shared
  /// mastering: a news channel and a film channel can be 15 dB apart, so every
  /// zap is a lunge for the volume key. `dynaudnorm` is a moving-window
  /// normaliser — unlike a compressor it does not pump on dialogue, and unlike
  /// replaygain it needs no scan, which a live stream could never provide.
  ///
  /// Off by default: it is a real alteration of the audio, and someone with a
  /// properly mastered film and a good amplifier should not have it applied
  /// behind their back.
  Future<void> setLoudnessNormalisation(bool enabled) async {
    final platform = _player.platform;
    if (platform is! NativePlayer) return;
    await platform
        // g=7 is a gentler window than the default 31; on speech it keeps the
        // level steady without audibly breathing between sentences.
        .setProperty('af', enabled ? 'dynaudnorm=g=7:f=250:p=0.9' : '')
        .catchError((Object e) => log.w('mpv: af ($e)'));
  }

  /// Picture adjustments, each -100..100, all zero by default.
  ///
  /// These are mpv's own video-equalizer properties, applied by the GPU during
  /// rendering rather than by a filter, so they cost nothing and take effect on
  /// the next frame. They exist because IPTV re-encodes are frequently crushed
  /// or washed out, and the alternative is telling the user to adjust their
  /// monitor for one channel.
  Future<void> setPictureAdjustment(PictureAdjustment which, int value) async {
    final platform = _player.platform;
    if (platform is! NativePlayer) return;
    await platform
        .setProperty(which.mpvProperty, '${value.clamp(-100, 100)}')
        .catchError((Object e) => log.w('mpv: ${which.mpvProperty} ($e)'));
  }

  Future<int> pictureAdjustment(PictureAdjustment which) async =>
      int.tryParse(await _getString(which.mpvProperty)) ?? 0;

  Future<void> resetPictureAdjustments() async {
    for (final which in PictureAdjustment.values) {
      await setPictureAdjustment(which, 0);
    }
  }

  /// Forces the display aspect ratio, or restores the stream's own.
  ///
  /// Needed because a great many channels are 4:3 content carried inside a 16:9
  /// frame with the pillarboxing baked in, or the reverse. No amount of `BoxFit`
  /// on the Flutter side can fix that — the black bars are pixels in the video,
  /// and only the decoder can be told to read the frame differently.
  Future<void> setAspectOverride(String? ratio) async {
    final platform = _player.platform;
    if (platform is! NativePlayer) return;
    await platform
        .setProperty('video-aspect-override', ratio ?? '-1')
        .catchError((Object e) => log.w('mpv: video-aspect-override ($e)'));
  }

  /// Deinterlacing. See `_tuneForIptv` for why this exists and defaults to auto.
  Future<void> setDeinterlace(DeinterlaceMode mode) async {
    final platform = _player.platform;
    if (platform is! NativePlayer) return;
    await platform
        .setProperty('deinterlace', mode.mpvValue)
        .catchError((Object e) => log.w('mpv: deinterlace ($e)'));
  }

  Future<DeinterlaceMode> get deinterlace async {
    final value = await _getString('deinterlace');
    return DeinterlaceMode.values.firstWhere(
      (m) => m.mpvValue == value,
      orElse: () => DeinterlaceMode.auto,
    );
  }

  /// A snapshot of what the engine is actually doing right now.
  ///
  /// This exists because "the video is not smooth" is unanswerable without it.
  /// Whether the GPU is decoding, what the source resolution really is, and how
  /// many frames were dropped are three different faults with the same
  /// symptom, and no amount of reading the code distinguishes them.
  Future<PlaybackStats> readStats() async {
    Future<String> get(String name) => _getString(name);
    final values = await Future.wait([
      get('hwdec-current'),
      get('video-codec'),
      get('width'),
      get('height'),
      get('container-fps'),
      get('estimated-vf-fps'),
      get('frame-drop-count'),
      get('decoder-frame-drop-count'),
      get('video-bitrate'),
      get('audio-codec-name'),
      get('audio-params/channel-count'),
      get('demuxer-cache-duration'),
      get('video-params/pixelformat'),
    ]);
    double? num_(String s) => double.tryParse(s);
    return PlaybackStats(
      hwdec: values[0].isEmpty || values[0] == 'no' ? null : values[0],
      videoCodec: values[1].isEmpty ? null : values[1],
      width: int.tryParse(values[2]),
      height: int.tryParse(values[3]),
      containerFps: num_(values[4]),
      currentFps: num_(values[5]),
      droppedFrames: int.tryParse(values[6]),
      decoderDroppedFrames: int.tryParse(values[7]),
      videoBitrate: num_(values[8]),
      audioCodec: values[9].isEmpty ? null : values[9],
      audioChannels: int.tryParse(values[10]),
      cacheSeconds: num_(values[11]),
      pixelFormat: values[12].isEmpty ? null : values[12],
    );
  }

  // ---------------------------------------------------------------------------
  // Recording, timeshift and stills.
  //
  // All three are libmpv features rather than pipelines this app builds: mpv can
  // already write the stream it is demuxing to a file, seek inside packets it
  // has already played, and save a decoded frame. Reimplementing any of them on
  // top would mean a second connection to the panel and a second decode.
  // ---------------------------------------------------------------------------

  /// Starts writing the stream to [path] while it keeps playing.
  ///
  /// This is a remux, not a re-encode: mpv copies the packets it is already
  /// demuxing, so recording a 4K channel costs almost no CPU and cannot change
  /// the picture. It records what arrives *from now on* — the back buffer is not
  /// flushed into the file, because mpv writes from the current demuxer position
  /// forward.
  Future<bool> startRecording(String path) async {
    final platform = _player.platform;
    if (platform is! NativePlayer) return false;
    try {
      await Directory(File(path).parent.path).create(recursive: true);
      await platform.setProperty('stream-record', path);
      _recordingPath = path;
      log.i('recording: started');
      return true;
    } on Object catch (e) {
      log.w('recording: could not start ($e)');
      return false;
    }
  }

  /// Stops recording. Setting the property empty is what closes the file
  /// cleanly — killing the player instead leaves an unfinalised container.
  Future<void> stopRecording() async {
    final platform = _player.platform;
    if (platform is! NativePlayer) return;
    try {
      await platform.setProperty('stream-record', '');
      log.i('recording: stopped');
    } on Object catch (e) {
      log.w('recording: could not stop ($e)');
    }
    _recordingPath = null;
  }

  String? _recordingPath;
  String? get recordingPath => _recordingPath;
  bool get isRecording => _recordingPath != null;

  /// The live stream's seekable window, read from the engine.
  ///
  /// Derived from what mpv is actually holding rather than from the configured
  /// ceiling: a channel open for ten seconds can be rewound ten seconds,
  /// whatever the buffer would allow. The UI needs the real numbers or it offers
  /// the viewer a seek that silently does nothing.
  Future<TimeshiftWindow> timeshiftWindow() async {
    final start = double.tryParse(await _getString('demuxer-start-time'));
    final edge = double.tryParse(await _getString('demuxer-cache-time'));
    if (start == null || edge == null || edge <= start) {
      return TimeshiftWindow.empty;
    }
    Duration toDuration(double seconds) =>
        Duration(milliseconds: (seconds * 1000).round());
    return TimeshiftWindow(
      start: toDuration(start),
      edge: toDuration(edge),
      position: position,
    );
  }

  /// How far back a live stream can currently be rewound.
  Future<Duration> timeshiftAvailable() async =>
      (await timeshiftWindow()).span;

  /// Jumps to the live edge.
  ///
  /// Seeks slightly *inside* the newest demuxed packet rather than exactly at
  /// it: landing on the very edge leaves nothing buffered ahead, and the stream
  /// stalls on the first moment the network is late.
  Future<void> seekToLiveEdge() async {
    final window = await timeshiftWindow();
    if (window.edge == Duration.zero) return;
    final target = window.edge - const Duration(milliseconds: 1500);
    await _player.seek(target.isNegative ? Duration.zero : target);
  }

  /// Saves the frame on screen to [path].
  ///
  /// `video` rather than `subtitles` or `window`: it captures the decoded frame
  /// at source resolution with no overlay, which is what someone grabbing a
  /// still off a match wants — not a picture of the player's own controls.
  Future<bool> takeScreenshot(String path) async {
    final platform = _player.platform;
    if (platform is! NativePlayer) return false;
    try {
      await Directory(File(path).parent.path).create(recursive: true);
      await platform.command(['screenshot-to-file', path, 'video']);
      return true;
    } on Object catch (e) {
      log.w('screenshot: failed ($e)');
      return false;
    }
  }

  Future<void> _setDouble(String property, double value) async {
    final platform = _player.platform;
    if (platform is! NativePlayer) return;
    await platform.setProperty(property, '$value').catchError((Object e) {
      log.w('mpv: could not set $property ($e)');
    });
  }

  Future<double> _getDouble(String property) async =>
      double.tryParse(await _getString(property)) ?? 0;

  Future<String> _getString(String property) async {
    final platform = _player.platform;
    if (platform is! NativePlayer) return '';
    try {
      return await platform.getProperty(property);
    } on Object {
      // An unset or not-yet-known property is normal, not exceptional: mpv has
      // no `width` until the first frame is decoded.
      return '';
    }
  }

  Future<void> stop() async {
    _mediaGeneration++;
    _current = null;
    await _player.stop();
  }

  Future<void> dispose() async {
    _mediaGeneration++;
    _current = null;
    _healthyTimer?.cancel();
    await _healthySubscription?.cancel();
    await _safeSizeSubscription?.cancel();
    // Reaching here at all means the process was shut down, not killed — which
    // is the other thing the probe accepts as proof the GL path is not fatal.
    // Without it, closing the window inside the ten-second window above would
    // leave a marker behind and read as a crash.
    if (_gpuTexturePath) _videoPathProbe.healthy();
    await _player.dispose();
  }
}
