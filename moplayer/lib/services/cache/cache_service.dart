import 'dart:convert';
import 'dart:io';

import 'package:hive_ce_flutter/hive_flutter.dart';

import '../../core/constants/app_constants.dart';
import '../../core/utils/app_logger.dart';

/// The small subset of a Hive string box the repositories need.
///
/// Having this seam is what lets startup fall back to process memory when the
/// data directory is read-only or a box is corrupt. Playback does not depend on
/// a writable disk.
abstract interface class CacheStringStore {
  Iterable<String> get values;
  int get length;
  String? get(String key);
  bool containsKey(String key);
  Future<void> put(String key, String value);
  Future<void> delete(String key);
  Future<void> clear();
}

class _HiveStringStore implements CacheStringStore {
  _HiveStringStore(this.box);

  final Box<String> box;

  @override
  Iterable<String> get values => box.values;

  @override
  int get length => box.length;

  @override
  String? get(String key) => box.get(key);

  @override
  bool containsKey(String key) => box.containsKey(key);

  @override
  Future<void> put(String key, String value) => box.put(key, value);

  @override
  Future<void> delete(String key) => box.delete(key);

  @override
  Future<void> clear() async {
    await box.clear();
  }
}

class _MemoryStringStore implements CacheStringStore {
  final Map<String, String> _values = {};

  @override
  Iterable<String> get values => _values.values;

  @override
  int get length => _values.length;

  @override
  String? get(String key) => _values[key];

  @override
  bool containsKey(String key) => _values.containsKey(key);

  @override
  Future<void> put(String key, String value) async {
    _values[key] = value;
  }

  @override
  Future<void> delete(String key) async {
    _values.remove(key);
  }

  @override
  Future<void> clear() async {
    _values.clear();
  }
}

abstract interface class _ValueStore {
  Object? get(String key);
  Future<void> put(String key, Object? value);
  Future<void> clear();
}

class _HiveValueStore implements _ValueStore {
  _HiveValueStore(this.box);

  final Box<dynamic> box;

  @override
  Object? get(String key) => box.get(key);

  @override
  Future<void> put(String key, Object? value) => box.put(key, value);

  @override
  Future<void> clear() async {
    await box.clear();
  }
}

class _MemoryValueStore implements _ValueStore {
  final Map<String, Object?> _values = {};

  @override
  Object? get(String key) => _values[key];

  @override
  Future<void> put(String key, Object? value) async {
    _values[key] = value;
  }

  @override
  Future<void> clear() async {
    _values.clear();
  }
}

/// On-device cache built on Hive. Catalog responses are stored as JSON strings
/// with a timestamp so the UI can render instantly from cache and refresh in
/// the background. The favourites / history / continue-watching boxes hold one
/// JSON entry per item keyed by a stable composite key.
class CacheService {
  CacheStringStore? _cache;
  CacheStringStore? _favorites;
  CacheStringStore? _history;
  CacheStringStore? _continue;
  _ValueStore? _settings;

  bool get isReady => _cache != null;
  bool _isPersistent = true;
  bool get isPersistent => _isPersistent;

  Future<void> init({String? path}) async {
    _isPersistent = true;
    try {
      if (path == null) {
        await Hive.initFlutter('moplayer');
      } else {
        await Directory(path).create(recursive: true);
        Hive.init(path);
      }
      _cache = _HiveStringStore(
        await Hive.openBox<String>(StorageKeys.boxCache),
      );
      _favorites = _HiveStringStore(
        await Hive.openBox<String>(StorageKeys.boxFavorites),
      );
      _history = _HiveStringStore(
        await Hive.openBox<String>(StorageKeys.boxHistory),
      );
      _continue = _HiveStringStore(
        await Hive.openBox<String>(StorageKeys.boxContinue),
      );
      _settings = _HiveValueStore(
        await Hive.openBox<dynamic>(StorageKeys.boxSettings),
      );
    } on Object catch (error) {
      // A corrupt box, a read-only home, or a full disk costs persistence for
      // this session; it must never cost the player itself. Close any boxes that
      // opened before the failure and keep a complete in-memory store so every
      // repository remains usable.
      log.w(
        'cache unavailable, continuing in memory: ${safeLogMessage(error)}',
      );
      try {
        await Hive.close();
      } on Object {
        // The fallback below owns no Hive resource.
      }
      _isPersistent = false;
      _cache = _MemoryStringStore();
      _favorites = _MemoryStringStore();
      _history = _MemoryStringStore();
      _continue = _MemoryStringStore();
      _settings = _MemoryValueStore();
    }
  }

  CacheStringStore get favorites => _favorites!;
  CacheStringStore get history => _history!;
  CacheStringStore get continueWatching => _continue!;

  // --- Catalog cache (TTL-aware) ------------------------------------------

  Future<void> putList(String key, List<Map<String, dynamic>> data) async {
    final envelope = jsonEncode({
      'ts': DateTime.now().millisecondsSinceEpoch,
      'data': data,
    });
    await _cache!.put(key, envelope);
  }

  /// The last decode of each key, so a second read of the same envelope is free.
  ///
  /// This is not an optimisation looking for a problem. The maintainer's panel
  /// returns 20,187 films, and a *search* asks for the films, the series and the
  /// channels — three envelopes, some 22 MB of JSON — on the UI isolate, after
  /// every debounced keystroke. Decoded from scratch each time, that is a freeze
  /// per letter typed. Category switching pays it too, every time the user goes
  /// back to a group they have already seen.
  ///
  /// Validated by **identity of the raw string**, not by a timer. Hive holds its
  /// values in memory, so `box.get(key)` hands back the same `String` instance
  /// until something writes over it — and a write replaces the instance, which
  /// misses the memo. There is no staleness window to reason about and nothing to
  /// invalidate by hand: if the bytes on disk changed, the memo is skipped.
  final Map<String, ({String raw, List<Map<String, dynamic>> rows})> _decoded =
      {};

  /// Returns cached rows or null when missing / expired beyond [ttl].
  List<Map<String, dynamic>>? getList(String key, {Duration? ttl}) {
    final raw = _cache!.get(key);
    if (raw == null) return null;

    final memo = _decoded[key];
    if (memo != null && identical(memo.raw, raw)) {
      // The TTL is still the envelope's, not the memo's — an entry that has aged
      // out is expired whether or not we happen to have it decoded.
      if (ttl != null && _isExpired(raw, ttl)) return null;
      return memo.rows;
    }

    try {
      final map = jsonDecode(raw) as Map<String, dynamic>;
      if (ttl != null) {
        final ts = (map['ts'] as num?)?.toInt() ?? 0;
        final age = DateTime.now().millisecondsSinceEpoch - ts;
        if (age >= ttl.inMilliseconds) return null;
      }
      final rows = (map['data'] as List<dynamic>)
          .whereType<Map>()
          .map((e) => Map<String, dynamic>.from(e))
          .toList();

      // One key's decode is worth tens of megabytes; a dozen of them is not worth
      // holding. The catalogue the user is *in* is the one that matters.
      if (_decoded.length >= 8) _decoded.remove(_decoded.keys.first);
      _decoded[key] = (raw: raw, rows: rows);
      return rows;
    } catch (_) {
      return null;
    }
  }

  /// The envelope's own timestamp, read without decoding the payload behind it —
  /// the whole point of the memo is not to touch that payload again.
  bool _isExpired(String raw, Duration ttl) {
    final match = RegExp(r'"ts"\s*:\s*(\d+)').firstMatch(raw);
    final ts = int.tryParse(match?.group(1) ?? '') ?? 0;
    return DateTime.now().millisecondsSinceEpoch - ts >= ttl.inMilliseconds;
  }

  /// A document that is not a list of rows — the XMLTV guide, which is ~1 MB of
  /// XML. Stored as text and parsed by the caller (on a background isolate), so
  /// that re-encoding it into JSON just to satisfy [putList] is not the cost of
  /// having a programme guide.
  Future<void> putText(String key, String value) async {
    await _cache!.put(
      key,
      jsonEncode({'ts': DateTime.now().millisecondsSinceEpoch, 'text': value}),
    );
  }

  String? getText(String key, {Duration? ttl}) {
    final raw = _cache!.get(key);
    if (raw == null) return null;
    try {
      final map = jsonDecode(raw) as Map<String, dynamic>;
      if (ttl != null) {
        final ts = (map['ts'] as num?)?.toInt() ?? 0;
        final age = DateTime.now().millisecondsSinceEpoch - ts;
        if (age >= ttl.inMilliseconds) return null;
      }
      return map['text'] as String?;
    } catch (_) {
      return null;
    }
  }

  Future<void> putJson(String key, Map<String, dynamic> data) =>
      _cache!.put(key, jsonEncode(data));

  Map<String, dynamic>? getJson(String key) {
    final raw = _cache!.get(key);
    if (raw == null) return null;
    try {
      return Map<String, dynamic>.from(jsonDecode(raw) as Map);
    } catch (_) {
      return null;
    }
  }

  Future<void> clearCatalogCache() => _cache!.clear();

  // --- Library boxes -------------------------------------------------------

  List<Map<String, dynamic>> readBox(CacheStringStore box) {
    return box.values
        .map((v) {
          try {
            return Map<String, dynamic>.from(jsonDecode(v) as Map);
          } catch (_) {
            return <String, dynamic>{};
          }
        })
        .where((m) => m.isNotEmpty)
        .toList();
  }

  Future<void> putBoxItem(
    CacheStringStore box,
    String key,
    Map<String, dynamic> value,
  ) => box.put(key, jsonEncode(value));

  Future<void> deleteBoxItem(CacheStringStore box, String key) =>
      box.delete(key);

  // --- Settings ------------------------------------------------------------

  T settingOr<T>(String key, T fallback) {
    final v = _settings!.get(key);
    if (v is T) return v;
    return fallback;
  }

  Future<void> setSetting(String key, dynamic value) =>
      _settings!.put(key, value);

  Future<void> wipeUserData() async {
    await _favorites?.clear();
    await _history?.clear();
    await _continue?.clear();
    await _cache?.clear();
  }
}
