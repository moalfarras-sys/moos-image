import 'dart:async';

import 'package:dbus/dbus.dart';

import '../../core/config/app_config.dart';
import '../../core/utils/app_logger.dart';

/// What MPRIS asks the app to do. Every callback is optional; a null one is
/// reported to the desktop as an unsupported capability (`CanGoNext` and
/// friends), so Plasma greys the button out instead of showing one that does
/// nothing.
class MprisHandlers {
  const MprisHandlers({
    this.onPlay,
    this.onPause,
    this.onPlayPause,
    this.onStop,
    this.onNext,
    this.onPrevious,
    this.onSeek,
    this.onSetPosition,
    this.onVolume,
    this.onRate,
    this.onOpenUri,
    this.onRaise,
    this.onQuit,
  });

  final Future<void> Function()? onPlay;
  final Future<void> Function()? onPause;
  final Future<void> Function()? onPlayPause;
  final Future<void> Function()? onStop;
  final Future<void> Function()? onNext;
  final Future<void> Function()? onPrevious;

  /// Relative seek, in microseconds (MPRIS's unit; may be negative).
  final Future<void> Function(int offsetUs)? onSeek;
  final Future<void> Function(int positionUs)? onSetPosition;
  final Future<void> Function(double volume)? onVolume;
  final Future<void> Function(double rate)? onRate;
  final Future<void> Function(String uri)? onOpenUri;
  final Future<void> Function()? onRaise;
  final Future<void> Function()? onQuit;
}

enum MprisStatus {
  playing('Playing'),
  paused('Paused'),
  stopped('Stopped');

  const MprisStatus(this.wire);
  final String wire;
}

/// What the desktop shows about the current track.
class MprisMetadata {
  const MprisMetadata({
    required this.trackId,
    required this.title,
    this.artist,
    this.album,
    this.artUrl,
    this.lengthUs = 0,
  });

  final String trackId;
  final String title;
  final String? artist;
  final String? album;
  final String? artUrl;

  /// 0 for a live stream — MPRIS's way of saying "unknown/unbounded", which is
  /// what makes Plasma draw a spinner instead of a seek bar that never fills.
  final int lengthUs;
}

/// MPRIS2 — the D-Bus interface every Linux desktop uses to talk to a media
/// player.
///
/// This is the single biggest piece of "MoPlayer belongs to MoOS": implementing
/// it is what makes the play/pause key on the keyboard work, what puts the
/// channel name and poster in Plasma's media applet and on the lock screen, and
/// what lets `playerctl` (and therefore any MoOS script) drive playback.
///
/// It is spoken directly rather than through a package. The interface is ~20
/// members and it is frozen; a wrapper would only hide the one thing that
/// actually matters here — that **every** failure has to be survivable. There is
/// no session bus in a TTY, in a container, or under a broken portal, and a
/// video player that refuses to start because a *notification* channel is
/// missing would be an absurd trade. So [start] never throws, and every method
/// no-ops when the bus never came up.
class MprisService {
  MprisService({required this._handlers, required this.positionUs});

  final MprisHandlers _handlers;

  /// Read on demand: MPRIS's `Position` property is polled by the desktop, and
  /// caching it would make Plasma's progress bar lag the app's own.
  final int Function() positionUs;

  DBusClient? _client;
  _MprisObject? _object;
  Future<void>? _starting;
  int? _startingGeneration;
  bool _wanted = false;
  int _lifecycleGeneration = 0;
  bool get isActive => _object != null;

  MprisStatus _status = MprisStatus.stopped;
  MprisMetadata? _metadata;
  double _volume = 1.0;
  double _rate = 1.0;
  bool _canGoNext = false;
  bool _canGoPrevious = false;
  bool _canSeek = false;

  Future<void> start() async {
    _wanted = true;
    if (_client != null) return;
    final pending = _starting;
    if (pending != null) {
      final pendingGeneration = _startingGeneration;
      await pending;
      // A quick off/on toggle can cancel the old connection while this call is
      // waiting for it. In that one case, establish the newly requested one.
      if (_wanted &&
          _client == null &&
          pendingGeneration != _lifecycleGeneration) {
        await start();
      }
      return;
    }

    final generation = _lifecycleGeneration;
    final connection = _connect(generation);
    _starting = connection;
    _startingGeneration = generation;
    try {
      await connection;
    } finally {
      if (identical(_starting, connection)) {
        _starting = null;
        _startingGeneration = null;
      }
    }
  }

  Future<void> _connect(int generation) async {
    try {
      final client = DBusClient.session();
      final object = _MprisObject(this);

      // doNotQueue: if another MoPlayer already owns the name, we do not want to
      // silently inherit it when that one exits — two windows fighting over one
      // set of media keys is worse than the second window having none.
      final reply = await client.requestName(
        'org.mpris.MediaPlayer2.${AppConfig.mprisName}',
        flags: {DBusRequestNameFlag.doNotQueue},
      );
      if (reply != DBusRequestNameReply.primaryOwner) {
        log.i('MPRIS: another player owns the bus name; media keys disabled');
        await client.close();
        return;
      }

      await client.registerObject(object);
      if (!_wanted || generation != _lifecycleGeneration) {
        await client.close();
        return;
      }
      _client = client;
      _object = object;
      log.i(
        'MPRIS: registered as org.mpris.MediaPlayer2.${AppConfig.mprisName}',
      );
    } on Exception catch (e) {
      // No session bus, or a bus that will not talk to us. Playback is fine.
      log.w('MPRIS unavailable, continuing without desktop media controls: $e');
    }
  }

  Future<void> setStatus(MprisStatus status) async {
    if (_status == status) return;
    _status = status;
    await _emit({'PlaybackStatus': DBusString(status.wire)});
  }

  Future<void> setMetadata(
    MprisMetadata? metadata, {
    bool canGoNext = false,
    bool canGoPrevious = false,
    bool canSeek = false,
  }) async {
    _metadata = metadata;
    _canGoNext = canGoNext;
    _canGoPrevious = canGoPrevious;
    _canSeek = canSeek;
    await _emit({
      'Metadata': _metadataValue(),
      'CanGoNext': DBusBoolean(canGoNext),
      'CanGoPrevious': DBusBoolean(canGoPrevious),
      'CanSeek': DBusBoolean(canSeek),
      'CanPlay': DBusBoolean(metadata != null),
      'CanPause': DBusBoolean(metadata != null),
    });
  }

  Future<void> setVolume(double volume) async {
    if ((_volume - volume).abs() < 0.001) return;
    _volume = volume.clamp(0.0, 1.0);
    await _emit({'Volume': DBusDouble(_volume)});
  }

  Future<void> setRate(double rate) async {
    if ((_rate - rate).abs() < 0.001) return;
    _rate = rate.clamp(0.25, 2.0);
    await _emit({'Rate': DBusDouble(_rate)});
  }

  /// Tell the desktop the position jumped, so its progress bar snaps instead of
  /// drifting until the next poll.
  Future<void> seeked(int positionUs) async {
    final object = _object;
    if (object == null) return;
    try {
      await object.emitSignal('org.mpris.MediaPlayer2.Player', 'Seeked', [
        DBusInt64(positionUs),
      ]);
    } on Exception catch (e) {
      log.w('MPRIS Seeked signal failed: $e');
    }
  }

  Future<void> dispose() async {
    _wanted = false;
    _lifecycleGeneration++;
    final client = _client;
    _client = null;
    _object = null;
    if (client == null) return;
    try {
      await client.close();
    } on Exception catch (_) {
      // The bus is going away with us; nothing to salvage.
    }
  }

  Future<void> _emit(Map<String, DBusValue> changed) async {
    final object = _object;
    if (object == null) return;
    try {
      await object.emitPropertiesChanged(
        'org.mpris.MediaPlayer2.Player',
        changedProperties: changed,
      );
    } on Exception catch (e) {
      log.w('MPRIS property change failed: $e');
    }
  }

  DBusValue _metadataValue() {
    final m = _metadata;
    if (m == null) return DBusDict.stringVariant({});
    return DBusDict.stringVariant({
      // Must be a valid object path — Plasma discards the whole metadata dict if
      // it is not, and the applet then shows an empty player.
      'mpris:trackid': DBusVariant(_trackPath(m)),
      if (m.lengthUs > 0) 'mpris:length': DBusVariant(DBusInt64(m.lengthUs)),
      if (m.artUrl != null && m.artUrl!.isNotEmpty)
        'mpris:artUrl': DBusVariant(DBusString(m.artUrl!)),
      'xesam:title': DBusVariant(DBusString(m.title)),
      if (m.artist != null && m.artist!.isNotEmpty)
        'xesam:artist': DBusVariant(DBusArray.string([m.artist!])),
      if (m.album != null && m.album!.isNotEmpty)
        'xesam:album': DBusVariant(DBusString(m.album!)),
    });
  }

  DBusObjectPath _trackPath(MprisMetadata metadata) =>
      DBusObjectPath('/org/moos/moplayer/track/${_sanitise(metadata.trackId)}');

  DBusObjectPath? get currentTrackPath {
    final metadata = _metadata;
    return metadata == null ? null : _trackPath(metadata);
  }

  /// An object path may only contain `[A-Za-z0-9_]` between slashes. Stream ids
  /// out of an Xtream panel are usually numeric, but an M3U id is a hash of the
  /// URL and can carry anything.
  static String _sanitise(String id) {
    final cleaned = id.replaceAll(RegExp(r'[^A-Za-z0-9_]'), '_');
    return cleaned.isEmpty ? 'unknown' : cleaned;
  }
}

/// The exported object at `/org/mpris/MediaPlayer2`.
class _MprisObject extends DBusObject {
  _MprisObject(this._service)
    : super(DBusObjectPath('/org/mpris/MediaPlayer2'));

  final MprisService _service;

  static const String _root = 'org.mpris.MediaPlayer2';
  static const String _player = 'org.mpris.MediaPlayer2.Player';

  @override
  List<DBusIntrospectInterface> introspect() {
    return [
      DBusIntrospectInterface(
        _root,
        methods: [DBusIntrospectMethod('Raise'), DBusIntrospectMethod('Quit')],
        properties: [
          _prop('CanQuit', 'b'),
          _prop('CanRaise', 'b'),
          _prop('HasTrackList', 'b'),
          _prop('Identity', 's'),
          _prop('DesktopEntry', 's'),
          _prop('SupportedUriSchemes', 'as'),
          _prop('SupportedMimeTypes', 'as'),
        ],
      ),
      DBusIntrospectInterface(
        _player,
        methods: [
          DBusIntrospectMethod('Next'),
          DBusIntrospectMethod('Previous'),
          DBusIntrospectMethod('Pause'),
          DBusIntrospectMethod('PlayPause'),
          DBusIntrospectMethod('Stop'),
          DBusIntrospectMethod('Play'),
          DBusIntrospectMethod(
            'Seek',
            args: [
              DBusIntrospectArgument(
                DBusSignature('x'),
                DBusArgumentDirection.in_,
                name: 'Offset',
              ),
            ],
          ),
          DBusIntrospectMethod(
            'SetPosition',
            args: [
              DBusIntrospectArgument(
                DBusSignature('o'),
                DBusArgumentDirection.in_,
                name: 'TrackId',
              ),
              DBusIntrospectArgument(
                DBusSignature('x'),
                DBusArgumentDirection.in_,
                name: 'Position',
              ),
            ],
          ),
          DBusIntrospectMethod(
            'OpenUri',
            args: [
              DBusIntrospectArgument(
                DBusSignature('s'),
                DBusArgumentDirection.in_,
                name: 'Uri',
              ),
            ],
          ),
        ],
        signals: [
          DBusIntrospectSignal(
            'Seeked',
            args: [
              DBusIntrospectArgument(
                DBusSignature('x'),
                DBusArgumentDirection.out,
                name: 'Position',
              ),
            ],
          ),
        ],
        properties: [
          _prop('PlaybackStatus', 's'),
          _prop('Rate', 'd', access: DBusPropertyAccess.readwrite),
          _prop('Metadata', 'a{sv}'),
          _prop('Volume', 'd', access: DBusPropertyAccess.readwrite),
          _prop('Position', 'x'),
          _prop('MinimumRate', 'd'),
          _prop('MaximumRate', 'd'),
          _prop('CanGoNext', 'b'),
          _prop('CanGoPrevious', 'b'),
          _prop('CanPlay', 'b'),
          _prop('CanPause', 'b'),
          _prop('CanSeek', 'b'),
          _prop('CanControl', 'b'),
        ],
      ),
    ];
  }

  static DBusIntrospectProperty _prop(
    String name,
    String signature, {
    DBusPropertyAccess access = DBusPropertyAccess.read,
  }) => DBusIntrospectProperty(name, DBusSignature(signature), access: access);

  @override
  Future<DBusMethodResponse> handleMethodCall(DBusMethodCall call) async {
    final h = _service._handlers;

    Future<DBusMethodResponse> run(Future<void> Function()? action) async {
      if (action == null) {
        return DBusMethodErrorResponse.failed('not supported');
      }
      await action();
      return DBusMethodSuccessResponse();
    }

    if (call.interface == _root) {
      return switch (call.name) {
        'Raise' => run(h.onRaise),
        'Quit' => run(h.onQuit),
        _ => DBusMethodErrorResponse.unknownMethod(),
      };
    }

    if (call.interface != _player) {
      return DBusMethodErrorResponse.unknownInterface();
    }

    switch (call.name) {
      case 'Play':
        return run(h.onPlay);
      case 'Pause':
        return run(h.onPause);
      case 'PlayPause':
        return run(h.onPlayPause);
      case 'Stop':
        return run(h.onStop);
      case 'Next':
        return run(h.onNext);
      case 'Previous':
        return run(h.onPrevious);
      case 'Seek':
        final onSeek = h.onSeek;
        if (onSeek == null) {
          return DBusMethodErrorResponse.failed('not seekable');
        }
        final offset = call.values.first.asInt64();
        await onSeek(offset);
        return DBusMethodSuccessResponse();
      case 'SetPosition':
        final onSetPosition = h.onSetPosition;
        if (onSetPosition == null) {
          return DBusMethodErrorResponse.failed('not seekable');
        }
        // A stale Plasma applet can send the id of the item that just ended.
        // MPRIS says that must be ignored, otherwise "seek the old film" seeks
        // the first seconds of the new episode instead.
        if (call.values.first.asObjectPath() != _service.currentTrackPath) {
          return DBusMethodSuccessResponse();
        }
        await onSetPosition(call.values[1].asInt64());
        return DBusMethodSuccessResponse();
      case 'OpenUri':
        final onOpenUri = h.onOpenUri;
        if (onOpenUri == null) {
          return DBusMethodErrorResponse.failed(
            'opening URIs is not supported',
          );
        }
        await onOpenUri(call.values.first.asString());
        return DBusMethodSuccessResponse();
      default:
        return DBusMethodErrorResponse.unknownMethod();
    }
  }

  @override
  Future<DBusMethodResponse> getProperty(String interface, String name) async {
    final value = _read(interface, name);
    if (value == null) return DBusMethodErrorResponse.unknownProperty();
    return DBusGetPropertyResponse(value);
  }

  @override
  Future<DBusMethodResponse> getAllProperties(String interface) async {
    final names = switch (interface) {
      _root => const [
        'CanQuit',
        'CanRaise',
        'HasTrackList',
        'Identity',
        'DesktopEntry',
        'SupportedUriSchemes',
        'SupportedMimeTypes',
      ],
      _player => const [
        'PlaybackStatus',
        'Rate',
        'Metadata',
        'Volume',
        'Position',
        'MinimumRate',
        'MaximumRate',
        'CanGoNext',
        'CanGoPrevious',
        'CanPlay',
        'CanPause',
        'CanSeek',
        'CanControl',
      ],
      _ => const <String>[],
    };
    return DBusGetAllPropertiesResponse({
      for (final name in names) name: _read(interface, name)!,
    });
  }

  @override
  Future<DBusMethodResponse> setProperty(
    String interface,
    String name,
    DBusValue value,
  ) async {
    if (interface == _player && name == 'Volume') {
      final onVolume = _service._handlers.onVolume;
      if (onVolume == null) return DBusMethodErrorResponse.propertyReadOnly();
      await onVolume(value.asDouble().clamp(0.0, 1.0));
      return DBusMethodSuccessResponse();
    }
    if (interface == _player && name == 'Rate') {
      final onRate = _service._handlers.onRate;
      if (onRate == null) return DBusMethodErrorResponse.propertyReadOnly();
      final rate = value.asDouble();
      if (!rate.isFinite || rate < 0.25 || rate > 2.0) {
        return DBusMethodErrorResponse.invalidArgs(
          'Rate must be between 0.25 and 2.0',
        );
      }
      await onRate(rate);
      return DBusMethodSuccessResponse();
    }
    return DBusMethodErrorResponse.propertyReadOnly();
  }

  DBusValue? _read(String interface, String name) {
    final s = _service;
    if (interface == _root) {
      return switch (name) {
        'CanQuit' => DBusBoolean(s._handlers.onQuit != null),
        'CanRaise' => DBusBoolean(s._handlers.onRaise != null),
        'HasTrackList' => DBusBoolean(false),
        'Identity' => DBusString('MoPlayer'),
        // Without this, Plasma's applet has no icon and no way back to the app.
        'DesktopEntry' => DBusString(AppConfig.appId),
        'SupportedUriSchemes' => DBusArray.string([
          'http',
          'https',
          'file',
          'rtsp',
        ]),
        'SupportedMimeTypes' => DBusArray.string([
          'video/mp2t',
          'application/x-mpegurl',
          'application/vnd.apple.mpegurl',
          'video/mp4',
          'video/x-matroska',
        ]),
        _ => null,
      };
    }
    if (interface == _player) {
      return switch (name) {
        'PlaybackStatus' => DBusString(s._status.wire),
        'Rate' => DBusDouble(s._rate),
        'Metadata' => s._metadataValue(),
        'Volume' => DBusDouble(s._volume),
        'Position' => DBusInt64(s.positionUs()),
        'MinimumRate' => DBusDouble(0.25),
        'MaximumRate' => DBusDouble(2.0),
        'CanGoNext' => DBusBoolean(s._canGoNext),
        'CanGoPrevious' => DBusBoolean(s._canGoPrevious),
        'CanPlay' => DBusBoolean(s._metadata != null),
        'CanPause' => DBusBoolean(s._metadata != null),
        'CanSeek' => DBusBoolean(s._canSeek),
        'CanControl' => DBusBoolean(true),
        _ => null,
      };
    }
    return null;
  }
}
