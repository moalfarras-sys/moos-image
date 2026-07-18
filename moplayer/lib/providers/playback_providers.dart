import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/utils/app_logger.dart';
import '../models/library_items.dart';
import '../models/live_channel.dart';
import '../models/media_kind.dart';
import '../models/series.dart';
import '../models/vod_movie.dart';
import '../services/player/player_service.dart';
import '../services/system/mpris.dart';
import 'content_providers.dart';
import 'core_providers.dart';
import 'library_providers.dart';
import 'system_providers.dart';

/// Everything the app knows about what is on screen right now.
class NowPlaying {
  const NowPlaying({
    required this.media,
    required this.refId,
    this.imageUrl,
    this.payload = const {},
    this.trackProgress = true,
    this.seasonEpisodes,
    this.episodeIndex,
    this.series,
  });

  final PlayableMedia media;

  /// The catalogue id this came from — a stream id, a movie id, an episode id.
  /// Favourites, history and resume positions are all keyed on it.
  final String refId;
  final String? imageUrl;
  final Map<String, dynamic> payload;

  /// False for live: a channel has no position worth remembering.
  final bool trackProgress;

  final List<Episode>? seasonEpisodes;
  final int? episodeIndex;
  final SeriesItem? series;

  MediaKind get kind => media.kind;
  bool get isLive => media.isLive;

  bool get hasNext {
    final eps = seasonEpisodes;
    final i = episodeIndex;
    return eps != null && i != null && i + 1 < eps.length;
  }

  bool get hasPrevious => (episodeIndex ?? 0) > 0 && seasonEpisodes != null;
}

/// Is the player taking the whole window, or sitting in the mini bar?
///
/// This is *not* a route. See `lib/app/routes.dart`: on a desktop, closing the
/// player must not stop the stream, so the player is a mode the shell is in.
enum PlayerView { hidden, mini, expanded }

final playerViewProvider = NotifierProvider<PlayerViewController, PlayerView>(
  PlayerViewController.new,
);

class PlayerViewController extends Notifier<PlayerView> {
  @override
  PlayerView build() => PlayerView.hidden;

  void expand() => state = PlayerView.expanded;
  void minimise() => state = PlayerView.mini;
  void hide() => state = PlayerView.hidden;
}

/// Fullscreen is window state, not app state — but the UI has to know, so it is
/// mirrored here and pushed to the window manager by [PlaybackController].
final fullscreenProvider = NotifierProvider<FullscreenController, bool>(
  FullscreenController.new,
);

class FullscreenController extends Notifier<bool> {
  @override
  bool build() => false;

  Future<void> set(bool value) async {
    if (state == value) return;
    state = value;
    await ref.read(desktopServiceProvider).setFullscreen(value);
  }

  Future<void> toggle() => set(!state);
}

/// The desktop's media control surface, wired to this app's player.
///
/// Built here rather than in `system_providers` because the handlers have to
/// reach the [PlaybackController] — the desktop's Next button means "next
/// episode", which the player itself knows nothing about.
final mprisProvider = Provider<MprisService>((ref) {
  final player = ref.watch(playerServiceProvider);

  final service = MprisService(
    positionUs: () => player.position.inMicroseconds,
    handlers: MprisHandlers(
      onPlay: player.play,
      onPause: player.pause,
      onPlayPause: player.playOrPause,
      onStop: () => ref.read(playbackProvider.notifier).stop(),
      onNext: () => ref.read(playbackProvider.notifier).next(),
      onPrevious: () => ref.read(playbackProvider.notifier).previous(),
      onSeek: (us) => player.seekBy(Duration(microseconds: us)),
      onSetPosition: (us) => player.seek(Duration(microseconds: us)),
      // MPRIS volume is 0–1; media_kit's is 0–100.
      onVolume: (v) => player.setVolume(v * 100),
      onRaise: () async {
        await ref.read(desktopServiceProvider).raise();
        ref.read(playerViewProvider.notifier).expand();
      },
      onQuit: () async => ref.read(playbackProvider.notifier).stop(),
    ),
  );

  ref.onDispose(service.dispose);
  return service;
});

final playbackProvider = NotifierProvider<PlaybackController, NowPlaying?>(
  PlaybackController.new,
);

/// Owns *when* something plays, as opposed to [PlayerService], which owns *how*.
///
/// It is the only place that:
///   * writes history and resume positions,
///   * tells the desktop what is playing (MPRIS, window title, screen-saver),
///   * recovers a stream that died, and
///   * decides what comes next.
///
/// All of that has to keep working while the user browses other screens, which
/// is why it lives in a provider and not in the player widget.
class PlaybackController extends Notifier<NowPlaying?> {
  static const _progressInterval = Duration(seconds: 5);
  static const _maxRetries = 3;

  /// A live channel that has been buffering this long is not buffering, it is
  /// dead. IPTV panels drop connections without closing them, and mpv will wait
  /// on that socket indefinitely.
  static const _stallTimeout = Duration(seconds: 18);

  final List<StreamSubscription<Object?>> _subs = [];
  Timer? _progressTimer;
  Timer? _stallTimer;
  int _retries = 0;

  @override
  NowPlaying? build() {
    final player = ref.watch(playerServiceProvider);
    final mpris = ref.watch(mprisProvider);
    final desktop = ref.watch(desktopServiceProvider);

    // MPRIS (panel + media-key control) only when the user enabled it — the
    // "Media keys" toggle must actually gate registration, not be a dead switch.
    // Best-effort; a session with no D-Bus simply has no media keys.
    if (ref.read(settingsProvider).mediaKeys) {
      unawaited(mpris.start());
    }

    _subs.addAll([
      player.playingStream.listen((playing) {
        if (state == null) return;
        mpris.setStatus(playing ? MprisStatus.playing : MprisStatus.paused);
        // Only hold the screen awake while pixels are actually changing AND the
        // user asked us to ("Keep the screen awake" toggle). Read fresh each
        // event so the toggle is honoured from the next play/pause on. An
        // inhibitor left on through a pause is how a laptop cooks in a bag.
        desktop.setKeepAwake(playing && ref.read(settingsProvider).keepAwake);
        if (playing) _retries = 0;
      }),
      player.volumeStream.listen((v) => mpris.setVolume(v / 100)),
      player.completedStream.listen((done) {
        if (done && state != null) unawaited(_onCompleted());
      }),
      player.errorStream.listen((message) {
        if (message.isNotEmpty && state != null) unawaited(_recover(message));
      }),
      player.bufferingStream.listen(_watchForStall),
    ]);

    ref.onDispose(() {
      for (final sub in _subs) {
        sub.cancel();
      }
      _progressTimer?.cancel();
      _stallTimer?.cancel();
    });

    return null;
  }

  PlayerService get _player => ref.read(playerServiceProvider);

  // ── Opening things ─────────────────────────────────────────────────────────

  Future<void> _start(NowPlaying next) async {
    _retries = 0;
    state = next;
    ref.read(playerViewProvider.notifier).expand();

    await _player.open(next.media);
    await _announce(next);

    _progressTimer?.cancel();
    if (next.trackProgress) {
      _progressTimer = Timer.periodic(_progressInterval, (_) => _saveProgress());
    }

    // History is written on open, not on finish: a user who watched ten minutes
    // and gave up still watched it, and the row is what "Continue watching"
    // hangs off.
    await ref
        .read(libraryActionsProvider)
        .recordHistory(
          HistoryItem(
            playlistId: _playlistId,
            kind: next.kind,
            refId: next.refId,
            title: next.media.title,
            imageUrl: next.imageUrl,
            payload: next.payload,
          ),
        );
  }

  String get _playlistId => ref.read(activePlaylistProvider)?.id ?? '';

  Future<void> _announce(NowPlaying next) async {
    final mpris = ref.read(mprisProvider);
    await mpris.setMetadata(
      MprisMetadata(
        trackId: '${next.kind.wire}_${next.refId}',
        title: next.media.title,
        artist: next.media.subtitle,
        artUrl: next.imageUrl,
        lengthUs: next.isLive ? 0 : _player.duration.inMicroseconds,
      ),
      canGoNext: next.hasNext,
      canGoPrevious: next.hasPrevious,
      canSeek: !next.isLive,
    );
    await mpris.setStatus(MprisStatus.playing);
    await ref.read(desktopServiceProvider).setTitle(next.media.title);
  }

  /// Play a bare URL, with no catalogue behind it.
  ///
  /// This is `moplayer https://…/master.m3u8` — and the seam anything else in
  /// MoOS can drive the player through. It is treated as live: there is no
  /// catalogue entry to hang a resume position off, and nothing to put in
  /// history that the user could ever click again.
  Future<void> playDirect(String url, {String? title}) async {
    await _start(
      NowPlaying(
        media: PlayableMedia(
          url: url,
          title: title ?? Uri.tryParse(url)?.pathSegments.last ?? url,
          kind: MediaKind.live,
        ),
        refId: url,
        trackProgress: false,
      ),
    );
  }

  Future<void> playLive(LiveChannel channel) async {
    final repo = ref.read(contentRepositoryProvider);
    if (repo == null) return;
    final settings = ref.read(settingsProvider);

    if (settings.rememberLastChannel) {
      await ref.read(settingsRepositoryProvider).setLastLiveChannelId(channel.streamId);
    }

    await _start(
      NowPlaying(
        media: PlayableMedia(
          url: repo.liveUrl(channel, hls: settings.preferHls),
          title: channel.name,
          subtitle: null,
          artUrl: channel.logo,
          kind: MediaKind.live,
        ),
        refId: channel.streamId,
        imageUrl: channel.logo,
        payload: channel.toPayload(),
        trackProgress: false,
      ),
    );
  }

  Future<void> playMovie(VodMovie movie, {bool fromStart = false}) async {
    final repo = ref.read(contentRepositoryProvider);
    if (repo == null) return;

    final resume = fromStart
        ? Duration.zero
        : ref.read(libraryActionsProvider).resumePosition(MediaKind.movie, movie.streamId);

    await _start(
      NowPlaying(
        media: PlayableMedia(
          url: repo.movieUrl(movie),
          title: movie.name,
          subtitle: movie.year,
          artUrl: movie.poster,
          kind: MediaKind.movie,
          startAt: resume,
        ),
        refId: movie.streamId,
        imageUrl: movie.poster,
        payload: movie.toPayload(),
      ),
    );
  }

  Future<void> playEpisode({
    required SeriesItem series,
    required List<Episode> seasonEpisodes,
    required int index,
    bool fromStart = false,
  }) async {
    final repo = ref.read(contentRepositoryProvider);
    if (repo == null || index < 0 || index >= seasonEpisodes.length) return;

    final episode = seasonEpisodes[index];
    final resume = fromStart
        ? Duration.zero
        : ref.read(libraryActionsProvider).resumePosition(MediaKind.episode, episode.id);

    await _start(
      NowPlaying(
        media: PlayableMedia(
          url: repo.episodeUrl(episode),
          title: series.name,
          subtitle: 'S${episode.seasonNumber} · E${episode.episodeNum} — ${episode.title}',
          artUrl: episode.image ?? series.cover,
          kind: MediaKind.episode,
          startAt: resume,
        ),
        refId: episode.id,
        imageUrl: episode.image ?? series.cover,
        payload: {
          ...episode.toPayload(),
          'seriesName': series.name,
          'seriesCover': series.cover,
        },
        seasonEpisodes: seasonEpisodes,
        episodeIndex: index,
        series: series,
      ),
    );
  }

  /// Resume a "Continue watching" row. The row carries the payload it was made
  /// from, so nothing has to be re-fetched from the panel to restart it.
  Future<void> resume(ContinueWatchingItem item) async {
    switch (item.kind) {
      case MediaKind.movie:
        await playMovie(VodMovie.fromPayload(item.payload));
      case MediaKind.episode:
        final repo = ref.read(contentRepositoryProvider);
        if (repo == null) return;
        final episode = Episode.fromPayload(item.payload);
        await _start(
          NowPlaying(
            media: PlayableMedia(
              url: repo.episodeUrl(episode),
              title: (item.payload['seriesName'] as String?) ?? item.title,
              subtitle: 'S${episode.seasonNumber} · E${episode.episodeNum}',
              artUrl: item.imageUrl,
              kind: MediaKind.episode,
              startAt: item.position,
            ),
            refId: episode.id,
            imageUrl: item.imageUrl,
            payload: item.payload,
          ),
        );
      case MediaKind.live:
      case MediaKind.series:
        // Neither is resumable: a channel has no past, and a series is a folder.
        break;
    }
  }

  // ── Transport ──────────────────────────────────────────────────────────────

  Future<void> next() async {
    final current = state;
    if (current == null || !current.hasNext) return;
    await playEpisode(
      series: current.series!,
      seasonEpisodes: current.seasonEpisodes!,
      index: current.episodeIndex! + 1,
      fromStart: true,
    );
  }

  Future<void> previous() async {
    final current = state;
    if (current == null || !current.hasPrevious) return;
    await playEpisode(
      series: current.series!,
      seasonEpisodes: current.seasonEpisodes!,
      index: current.episodeIndex! - 1,
      fromStart: true,
    );
  }

  Future<void> stop() async {
    await _saveProgress();
    _progressTimer?.cancel();
    _stallTimer?.cancel();
    _progressTimer = null;

    await _player.stop();
    state = null;

    ref.read(playerViewProvider.notifier).hide();
    await ref.read(fullscreenProvider.notifier).set(false);

    final mpris = ref.read(mprisProvider);
    await mpris.setStatus(MprisStatus.stopped);
    await mpris.setMetadata(null);
    await ref.read(desktopServiceProvider).setTitle(null);
    await ref.read(desktopServiceProvider).setKeepAwake(false);
  }

  Future<void> seek(Duration to) async {
    await _player.seek(to);
    await ref.read(mprisProvider).seeked(to.inMicroseconds);
  }

  Future<void> seekBy(Duration delta) async {
    await _player.seekBy(delta);
    await ref.read(mprisProvider).seeked(_player.position.inMicroseconds);
  }

  // ── Keeping the stream alive ───────────────────────────────────────────────

  Future<void> _onCompleted() async {
    final current = state;
    if (current == null) return;

    if (current.trackProgress) {
      // A finished item must not linger in "Continue watching".
      await ref.read(libraryActionsProvider).removeContinue(current.kind, current.refId);
    }

    if (ref.read(settingsProvider).autoplayNext && current.hasNext) {
      await next();
      return;
    }
    await stop();
  }

  /// A stream that failed is usually a stream that will work on the next try —
  /// an IPTV panel drops connections constantly. Retry with a backoff, then give
  /// up and let the UI say so.
  Future<void> _recover(String message) async {
    final current = state;
    if (current == null) return;

    if (_retries >= _maxRetries) {
      log.e('playback: giving up on ${current.media.title} after $_retries retries: $message');
      return;
    }

    _retries++;
    final wait = Duration(seconds: 2 * _retries);
    log.w('playback: $message — retry $_retries/$_maxRetries in ${wait.inSeconds}s');
    await Future<void>.delayed(wait);

    if (state != current) return; // the user moved on while we waited
    final resumeAt = current.isLive ? Duration.zero : _player.position;
    await _player.open(current.media.copyWith(startAt: resumeAt));
  }

  void _watchForStall(bool buffering) {
    _stallTimer?.cancel();
    if (!buffering || state == null) return;
    _stallTimer = Timer(_stallTimeout, () {
      final current = state;
      if (current == null || !_player.isBuffering) return;
      unawaited(_recover('stalled for ${_stallTimeout.inSeconds}s'));
    });
  }

  Future<void> _saveProgress() async {
    final current = state;
    if (current == null || !current.trackProgress) return;

    final position = _player.position;
    final duration = _player.duration;
    // Below five seconds there is nothing worth resuming, and a duration of zero
    // means the demuxer has not reported one yet.
    if (duration <= Duration.zero || position <= const Duration(seconds: 5)) return;

    await ref
        .read(libraryActionsProvider)
        .saveProgress(
          ContinueWatchingItem(
            playlistId: _playlistId,
            kind: current.kind,
            refId: current.refId,
            title: current.media.title,
            imageUrl: current.imageUrl,
            payload: current.payload,
            positionSecs: position.inSeconds,
            durationSecs: duration.inSeconds,
          ),
        );
  }
}
