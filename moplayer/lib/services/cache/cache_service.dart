import 'dart:convert';
import 'dart:io';

import 'package:hive_ce_flutter/hive_flutter.dart';

import '../../core/constants/app_constants.dart';
import '../../core/utils/app_logger.dart';
import '../catalog/catalog_files.dart';

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

/// The app's small persistent state, on Hive: favourites, history, continue
/// watching and settings, each one JSON entry per item keyed by a stable
/// composite key.
///
/// **The catalogue is not here any more.** It used to be — as JSON strings in
/// an `mp_cache` box — and Hive keeps every open box in memory and appends every
/// write to one log. On the owner's station that box grew to 278 MB, and opening
/// it at launch took six seconds of a blank window and 1.4 GB of memory before
/// the first frame. The catalogue now lives in per-document files read on a
/// background isolate (see `ContentRepository`); [init] deletes the old box
/// before Hive can load it.
class CacheService {
  CacheStringStore? _favorites;
  CacheStringStore? _history;
  CacheStringStore? _continue;
  _ValueStore? _settings;

  bool get isReady => _favorites != null;
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
      _dropLegacyCatalogue(path);
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
      _favorites = _MemoryStringStore();
      _history = _MemoryStringStore();
      _continue = _MemoryStringStore();
      _settings = _MemoryValueStore();
    }
  }

  CacheStringStore get favorites => _favorites!;
  CacheStringStore get history => _history!;
  CacheStringStore get continueWatching => _continue!;

  // --- Catalogue ------------------------------------------------------------

  /// Forgets every source's catalogue. The catalogue itself lives in plain
  /// files under `$XDG_CACHE_HOME/moplayer/catalog` (see [CatalogFiles]), not
  /// in Hive; this is the one door Settings has to it.
  Future<void> clearCatalogCache() async => CatalogFiles.forUser().clear();

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
    await clearCatalogCache();
  }

  /// Removes the retired catalogue box without opening it. Opening it is the
  /// cost being removed; a file the app no longer reads is simply deleted.
  static void _dropLegacyCatalogue(String? path) {
    if (path == null) return;
    for (final name in const ['mp_cache.hive', 'mp_cache.lock']) {
      try {
        final file = File('$path/$name');
        if (file.existsSync()) file.deleteSync();
      } on FileSystemException {
        // A read-only home keeps the stale file; nothing reads it.
      }
    }
  }
}
