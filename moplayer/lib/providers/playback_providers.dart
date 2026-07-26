import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/utils/app_logger.dart';
import '../models/category.dart';
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
    this.liveChannels = const [],
    this.liveChannelIndex,
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
  final List<LiveChannel> liveChannels;
  final int? liveChannelIndex;

  MediaKind get kind => media.kind;
  bool get isLive => media.isLive;

  bool get hasNext {
    if (isLive) return liveChannels.length > 1;
    final eps = seasonEpisodes;
    final i = episodeIndex;
    return eps != null && i != null && i + 1 < eps.length;
  }

  bool get hasPrevious {
    if (isLive) return liveChannels.length > 1;
    return (episodeIndex ?? 0) > 0 && seasonEpisodes != null;
  }
}

/// A safe desktop title for a URL handed to MPRIS or the command line.
///
/// `Uri.pathSegments.last` throws for a host-only URL. OpenUri accepts those
/// (redirecting stream endpoints are common), so the title falls back through
/// the last non-empty path segment, host, and finally the original input.
String directMediaTitle(String url) {
  final uri = Uri.tryParse(url);
  if (uri == null) return url;
  final segments = uri.pathSegments
      .where((segment) => segment.trim().isNotEmpty)
      .toList();
  if (segments.isNotEmpty) return segments.last;
  if (uri.host.isNotEmpty) return uri.host;
  return url;
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

  void expand() {
    state = PlayerView.expanded;
    unawaited(ref.read(playerServiceProvider).setCompactVideoOutput(false));
  }

  void minimise() {
    state = PlayerView.mini;
    unawaited(ref.read(playerServiceProvider).setCompactVideoOutput(true));
  }

  void hide() {
    state = PlayerView.hidden;
    unawaited(ref.read(playerServiceProvider).setCompactVideoOutput(true));
  }
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
    final applied = await ref.read(desktopServiceProvider).setFullscreen(value);
    if (applied) state = value;
  }

  Future<void> toggle() => set(!state);

  /// A compositor shortcut can change the window without going through [set].
  void sync(bool value) {
    state = value;
    ref.read(desktopServiceProvider).syncFullscreen(value);
  }
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
      onSeek: (us) => ref
          .read(playbackProvider.notifier)
          .seekBy(Duration(microseconds: us)),
      onSetPosition: (us) =>
          ref.read(playbackProvider.notifier).seek(Duration(microseconds: us)),
      // MPRIS volume is 0–1; media_kit's is 0–100.
      onVolume: (v) => player.setVolume(v * 100),
      onRate: player.setRate,
      onOpenUri: (uri) => ref.read(playbackProvider.notifier).playDirect(uri),
      onRaise: () async {
        await ref.read(desktopServiceProvider).raise();
        // Raising an idle app must not put the shell into an "expanded player"
        // mode with no player to draw. That state hides the caption and dock
        // while showing the home page underneath.
        if (ref.read(playbackProvider) != null) {
          ref.read(playerViewProvider.notifier).expand();
        }
      },
      onQuit: () async {
        await ref.read(playbackProvider.notifier).stop();
        // Let the D-Bus method return before destroying the process. Closing
        // synchronously made a successful Quit look like NoReply to Plasma and
        // playerctl because the connection vanished with its reply in flight.
        Timer(const Duration(milliseconds: 100), () {
          unawaited(ref.read(desktopServiceProvider).close());
        });
      },
    ),
  );

  ref.onDispose(service.dispose);
  return service;
});

final playbackProvider = NotifierProvider<PlaybackController, NowPlaying?>(
  PlaybackController.new,
);

enum PlaybackIssueKind { reconnecting, failed }

class PlaybackIssue {
  const PlaybackIssue({
    required this.kind,
    this.attempt = 0,
    this.maxAttempts = 0,
  });

  final PlaybackIssueKind kind;
  final int attempt;
  final int maxAttempts;
}

final playbackIssueProvider =
    NotifierProvider<PlaybackIssueController, PlaybackIssue?>(
      PlaybackIssueController.new,
    );

class PlaybackIssueController extends Notifier<PlaybackIssue?> {
  @override
  PlaybackIssue? build() => null;

  void clear() => state = null;

  void reconnecting(int attempt, int maxAttempts) {
    state = PlaybackIssue(
      kind: PlaybackIssueKind.reconnecting,
      attempt: attempt,
      maxAttempts: maxAttempts,
    );
  }

  void failed() {
    state = const PlaybackIssue(kind: PlaybackIssueKind.failed);
  }
}

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
  Timer? _stablePlaybackTimer;
  int _retries = 0;
  bool _recovering = false;
  int _recoveryGeneration = 0;
  int? _openingGeneration;
  String _mediaPlaylistId = '';

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

    // Settings change while this long-lived controller stays mounted. Apply
    // desktop integrations immediately instead of waiting for the next
    // play/pause event (or, worse, requiring an application restart).
    ref.listen(settingsProvider, (previous, next) {
      if (previous?.mediaKeys != next.mediaKeys) {
        if (next.mediaKeys) {
          unawaited(mpris.start());
        } else {
          unawaited(mpris.dispose());
        }
      }
      if (previous?.keepAwake != next.keepAwake) {
        unawaited(desktop.setKeepAwake(player.isPlaying && next.keepAwake));
      }
    });

    _subs.addAll([
      player.playingStream.listen((playing) {
        if (state == null) return;
        mpris.setStatus(playing ? MprisStatus.playing : MprisStatus.paused);
        // Only hold the screen awake while pixels are actually changing AND the
        // user asked us to ("Keep the screen awake" toggle). Read fresh each
        // event so the toggle is honoured from the next play/pause on. An
        // inhibitor left on through a pause is how a laptop cooks in a bag.
        desktop.setKeepAwake(playing && ref.read(settingsProvider).keepAwake);
        if (playing) {
          // A single decoded frame is not proof that a flaky stream recovered:
          // resetting the retry budget immediately made a stream that failed
          // every second retry forever. Clear the visible overlay as soon as
          // playback returns, but replenish the budget only after ten stable
          // seconds.
          if (!_recovering) {
            ref.read(playbackIssueProvider.notifier).clear();
          }
          _scheduleStablePlayback();
        } else {
          _stablePlaybackTimer?.cancel();
        }
      }),
      player.volumeStream.listen((v) => mpris.setVolume(v / 100)),
      player.rateStream.listen(mpris.setRate),
      player.completedStream.listen((done) {
        if (done && state != null && _openingGeneration == null) {
          unawaited(_onCompleted());
        }
      }),
      player.errorStream.listen((message) {
        if (message.isNotEmpty && state != null && _openingGeneration == null) {
          unawaited(_recover(message));
        }
      }),
      player.bufferingStream.listen(_watchForStall),
    ]);

    ref.onDispose(() {
      for (final sub in _subs) {
        sub.cancel();
      }
      _progressTimer?.cancel();
      _stallTimer?.cancel();
      _stablePlaybackTimer?.cancel();
    });

    return null;
  }

  PlayerService get _player => ref.read(playerServiceProvider);

  // ── Opening things ─────────────────────────────────────────────────────────

  Future<void> _start(NowPlaying next) async {
    final previousProgress = _progressSnapshot(state);
    final nextPlaylistId = _playlistId;
    final generation = ++_recoveryGeneration;
    _openingGeneration = generation;
    _recovering = false;
    _retries = 0;
    _progressTimer?.cancel();
    _stallTimer?.cancel();
    _stablePlaybackTimer?.cancel();
    _progressTimer = null;
    _stallTimer = null;
    _stablePlaybackTimer = null;
    ref.read(playbackIssueProvider.notifier).clear();

    // Capture before changing [state] or opening another stream. The previous
    // implementation left its five-second timer alive until the new open
    // completed, so it could save the old player's position under the new
    // film's id. Persisting the already-captured item can safely finish in the
    // background without delaying a channel switch.
    if (previousProgress != null) {
      unawaited(
        ref.read(libraryActionsProvider).saveProgress(previousProgress),
      );
    }

    state = next;
    _mediaPlaylistId = nextPlaylistId;
    ref.read(playerViewProvider.notifier).expand();

    try {
      await _player.open(next.media);
    } catch (error) {
      if (generation != _recoveryGeneration || !identical(state, next)) return;
      // Opening a broken stream must become a recoverable player state, never
      // an unhandled asynchronous exception that takes the UI down with it.
      log.w('playback: initial open failed: ${safeLogMessage(error)}');
      ref.read(playbackIssueProvider.notifier).failed();
      return;
    } finally {
      if (_openingGeneration == generation) {
        _openingGeneration = null;
      }
    }

    if (generation != _recoveryGeneration || !identical(state, next)) return;
    await _announce(next);
    if (generation != _recoveryGeneration || !identical(state, next)) return;

    if (_player.isBuffering) _watchForStall(true);

    if (next.trackProgress) {
      _progressTimer = Timer.periodic(
        _progressInterval,
        (_) => _saveProgress(),
      );
    }

    // media_kit may complete `open` before mpv knows the duration. Announce once
    // immediately so the desktop gets the title, then once more when a real
    // length arrives so Plasma's seek bar is not permanently unbounded.
    if (!next.isLive && _player.duration <= Duration.zero) {
      unawaited(
        _player.durationStream
            .firstWhere((duration) => duration > Duration.zero)
            .then((_) async {
              if (generation == _recoveryGeneration && identical(state, next)) {
                await _announce(next);
              }
            })
            .catchError((Object _) {}),
      );
    }

    // History is written on open, not on finish: a user who watched ten minutes
    // and gave up still watched it, and the row is what "Continue watching"
    // hangs off.
    await ref
        .read(libraryActionsProvider)
        .recordHistory(
          HistoryItem(
            playlistId: nextPlaylistId,
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
          title: title ?? directMediaTitle(url),
          kind: MediaKind.live,
        ),
        refId: url,
        trackProgress: false,
      ),
    );
  }

  Future<void> playLive(
    LiveChannel channel, {
    List<LiveChannel>? channels,
  }) async {
    final repo = ref.read(contentRepositoryProvider);
    if (repo == null) return;
    final settings = ref.read(settingsProvider);
    final categoryChannels =
        ref
            .read(liveStreamsProvider(channel.categoryId ?? Category.allId))
            .valueOrNull ??
        const <LiveChannel>[];
    final allChannels =
        ref.read(liveStreamsProvider(Category.allId)).valueOrNull ??
        const <LiveChannel>[];
    final candidates = channels ?? categoryChannels;
    final queue = candidates.any((item) => item.streamId == channel.streamId)
        ? List<LiveChannel>.unmodifiable(candidates)
        : allChannels.any((item) => item.streamId == channel.streamId)
        ? List<LiveChannel>.unmodifiable(allChannels)
        : <LiveChannel>[channel];
    final channelIndex = queue.indexWhere(
      (item) => item.streamId == channel.streamId,
    );

    if (settings.rememberLastChannel) {
      await ref
          .read(settingsRepositoryProvider)
          .setLastLiveChannelId(channel.streamId);
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
        liveChannels: queue,
        liveChannelIndex: channelIndex < 0 ? 0 : channelIndex,
      ),
    );
  }

  Future<void> playMovie(VodMovie movie, {bool fromStart = false}) async {
    final repo = ref.read(contentRepositoryProvider);
    if (repo == null) return;

    final resume = fromStart
        ? Duration.zero
        : ref
              .read(libraryActionsProvider)
              .resumePosition(MediaKind.movie, movie.streamId);

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
        : ref
              .read(libraryActionsProvider)
              .resumePosition(MediaKind.episode, episode.id);

    await _start(
      NowPlaying(
        media: PlayableMedia(
          url: repo.episodeUrl(episode),
          title: series.name,
          subtitle:
              'S${episode.seasonNumber} · E${episode.episodeNum} — ${episode.title}',
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
    if (current.isLive) {
      final channels = current.liveChannels;
      final index = ((current.liveChannelIndex ?? 0) + 1) % channels.length;
      await playLive(channels[index], channels: channels);
      return;
    }
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
    if (current.isLive) {
      final channels = current.liveChannels;
      final index =
          ((current.liveChannelIndex ?? 0) - 1 + channels.length) %
          channels.length;
      await playLive(channels[index], channels: channels);
      return;
    }
    await playEpisode(
      series: current.series!,
      seasonEpisodes: current.seasonEpisodes!,
      index: current.episodeIndex! - 1,
      fromStart: true,
    );
  }

  Future<void> stop() async {
    final progress = _progressSnapshot(state);
    _recoveryGeneration++;
    _openingGeneration = null;
    // Suppress an error/completed event emitted by mpv while it is stopping.
    _recovering = true;
    _retries = 0;
    ref.read(playbackIssueProvider.notifier).clear();
    _progressTimer?.cancel();
    _stallTimer?.cancel();
    _stablePlaybackTimer?.cancel();
    _progressTimer = null;
    _stallTimer = null;
    _stablePlaybackTimer = null;

    if (progress != null) {
      unawaited(ref.read(libraryActionsProvider).saveProgress(progress));
    }
    await _player.stop();
    state = null;
    _mediaPlaylistId = '';
    _recovering = false;

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
      await ref
          .read(libraryActionsProvider)
          .removeContinue(current.kind, current.refId);
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
    if (current == null || _recovering) return;

    if (_retries >= _maxRetries) {
      log.e(
        'playback: giving up after $_retries retries: '
        '${safeLogMessage(message)}',
      );
      ref.read(playbackIssueProvider.notifier).failed();
      return;
    }

    _recovering = true;
    _retries++;
    final generation = _recoveryGeneration;
    final wait = Duration(seconds: 2 * _retries);
    ref
        .read(playbackIssueProvider.notifier)
        .reconnecting(_retries, _maxRetries);
    log.w(
      'playback: ${safeLogMessage(message)} — retry '
      '$_retries/$_maxRetries in ${wait.inSeconds}s',
    );
    await Future<void>.delayed(wait);

    if (state != current || generation != _recoveryGeneration) {
      _recovering = false;
      return;
    }
    final resumeAt = current.isLive ? Duration.zero : _player.position;
    try {
      await _player.open(current.media.copyWith(startAt: resumeAt));
    } catch (error) {
      if (state != current || generation != _recoveryGeneration) {
        _recovering = false;
        return;
      }
      log.w('playback: retry $_retries failed: ${safeLogMessage(error)}');
      _recovering = false;
      if (_retries >= _maxRetries) {
        ref.read(playbackIssueProvider.notifier).failed();
      } else {
        unawaited(_recover('$error'));
      }
      return;
    }

    if (state != current || generation != _recoveryGeneration) {
      _recovering = false;
      return;
    }
    _recovering = false;
    if (_player.isPlaying) {
      ref.read(playbackIssueProvider.notifier).clear();
      _scheduleStablePlayback();
    }
  }

  /// A user-initiated retry does not inherit the automatic backoff and does not
  /// make them wait another six seconds after they have already chosen Retry.
  Future<void> reconnect() async {
    final current = state;
    if (current == null) return;

    _recoveryGeneration++;
    final generation = _recoveryGeneration;
    _recovering = true;
    _retries = 0;
    ref.read(playbackIssueProvider.notifier).reconnecting(1, _maxRetries);
    final resumeAt = current.isLive ? Duration.zero : _player.position;
    try {
      await _player.open(current.media.copyWith(startAt: resumeAt));
      if (generation == _recoveryGeneration && identical(state, current)) {
        ref.read(playbackIssueProvider.notifier).clear();
        _scheduleStablePlayback();
      }
    } catch (error) {
      if (generation != _recoveryGeneration || !identical(state, current)) {
        return;
      }
      log.w('playback: manual reconnect failed: ${safeLogMessage(error)}');
      ref.read(playbackIssueProvider.notifier).failed();
    } finally {
      _recovering = false;
    }
  }

  void _watchForStall(bool buffering) {
    _stallTimer?.cancel();
    _stallTimer = null;
    // Opening has its own error path. Starting an eighteen-second stall timer
    // for the old stream while a replacement is being negotiated is how a late
    // timer used to reopen the wrong item.
    if (!buffering || state == null || _openingGeneration != null) return;
    _stallTimer = Timer(_stallTimeout, () {
      final current = state;
      if (current == null || !_player.isBuffering) return;
      unawaited(_recover('stalled for ${_stallTimeout.inSeconds}s'));
    });
  }

  void _scheduleStablePlayback() {
    _stablePlaybackTimer?.cancel();
    final generation = _recoveryGeneration;
    final current = state;
    _stablePlaybackTimer = Timer(const Duration(seconds: 10), () {
      if (generation != _recoveryGeneration ||
          !identical(state, current) ||
          !_player.isPlaying ||
          _recovering) {
        return;
      }
      _retries = 0;
    });
  }

  Future<void> _saveProgress() async {
    final item = _progressSnapshot(state);
    if (item == null) return;
    await ref.read(libraryActionsProvider).saveProgress(item);
  }

  ContinueWatchingItem? _progressSnapshot(NowPlaying? current) {
    if (current == null || !current.trackProgress) return null;

    final position = _player.position;
    final duration = _player.duration;
    // Below five seconds there is nothing worth resuming, and a duration of zero
    // means the demuxer has not reported one yet.
    if (duration <= Duration.zero || position <= const Duration(seconds: 5)) {
      return null;
    }

    return ContinueWatchingItem(
      playlistId: _mediaPlaylistId,
      kind: current.kind,
      refId: current.refId,
      title: current.media.title,
      imageUrl: current.imageUrl,
      payload: current.payload,
      positionSecs: position.inSeconds,
      durationSecs: duration.inSeconds,
    );
  }
}
