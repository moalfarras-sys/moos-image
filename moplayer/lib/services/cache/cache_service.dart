import 'dart:convert';

import 'package:hive_ce_flutter/hive_flutter.dart';

import '../../core/constants/app_constants.dart';

/// On-device cache built on Hive. Catalog responses are stored as JSON strings
/// with a timestamp so the UI can render instantly from cache and refresh in
/// the background. The favourites / history / continue-watching boxes hold one
/// JSON entry per item keyed by a stable composite key.
class CacheService {
  Box<String>? _cache;
  Box<String>? _favorites;
  Box<String>? _history;
  Box<String>? _continue;
  Box? _settings;

  bool get isReady => _cache != null;

  Future<void> init({String? path}) async {
    if (path == null) {
      await Hive.initFlutter('moplayer');
    } else {
      Hive.init(path);
    }
    _cache = await Hive.openBox<String>(StorageKeys.boxCache);
    _favorites = await Hive.openBox<String>(StorageKeys.boxFavorites);
    _history = await Hive.openBox<String>(StorageKeys.boxHistory);
    _continue = await Hive.openBox<String>(StorageKeys.boxContinue);
    _settings = await Hive.openBox(StorageKeys.boxSettings);
  }

  Box<String> get favorites => _favorites!;
  Box<String> get history => _history!;
  Box<String> get continueWatching => _continue!;
  Box get settings => _settings!;

  // --- Catalog cache (TTL-aware) ------------------------------------------

  Future<void> putList(String key, List<Map<String, dynamic>> data) async {
    final envelope = jsonEncode({
      'ts': DateTime.now().millisecondsSinceEpoch,
      'data': data,
    });
    await _cache!.put(key, envelope);
  }

  /// Returns cached rows or null when missing / expired beyond [ttl].
  List<Map<String, dynamic>>? getList(String key, {Duration? ttl}) {
    final raw = _cache!.get(key);
    if (raw == null) return null;
    try {
      final map = jsonDecode(raw) as Map<String, dynamic>;
      if (ttl != null) {
        final ts = (map['ts'] as num?)?.toInt() ?? 0;
        final age = DateTime.now().millisecondsSinceEpoch - ts;
        if (age > ttl.inMilliseconds) return null;
      }
      return (map['data'] as List<dynamic>)
          .whereType<Map>()
          .map((e) => Map<String, dynamic>.from(e))
          .toList();
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

  List<Map<String, dynamic>> readBox(Box<String> box) {
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
    Box<String> box,
    String key,
    Map<String, dynamic> value,
  ) => box.put(key, jsonEncode(value));

  Future<void> deleteBoxItem(Box<String> box, String key) => box.delete(key);

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
