import 'package:supabase_flutter/supabase_flutter.dart';

import '../../core/config/app_config.dart';
import '../../core/utils/app_logger.dart';
import '../../models/media_kind.dart';
import '../../models/profile.dart';

/// Wraps the Supabase client. Every method is a safe no-op when Supabase is
/// not configured, so the rest of the app can call it unconditionally and the
/// app remains fully functional in local-only mode.
class SupabaseService {
  SupabaseService({required this.enabled});

  final bool enabled;

  SupabaseClient? get _client => enabled ? Supabase.instance.client : null;

  String? get userId => _client?.auth.currentUser?.id;
  bool get hasSession => userId != null;

  /// Ensures we have an (anonymous) user so per-user rows can be written.
  /// Anonymous sign-in must be enabled in the Supabase dashboard; if it isn't
  /// we degrade to local-only without crashing.
  Future<void> ensureSession() async {
    final client = _client;
    if (client == null) return;
    if (client.auth.currentUser != null) return;
    try {
      await client.auth.signInAnonymously();
    } catch (e) {
      log.w('Supabase anonymous sign-in unavailable: $e');
    }
  }

  Future<Profile?> fetchProfile() async {
    final client = _client;
    final uid = userId;
    if (client == null || uid == null) return null;
    try {
      final row = await client
          .from('profiles')
          .select()
          .eq('id', uid)
          .maybeSingle();
      if (row == null) return null;
      return Profile.fromJson(row);
    } catch (e) {
      log.w('fetchProfile failed: $e');
      return null;
    }
  }

  Future<void> upsertDevice({
    required String deviceId,
    required String model,
    required String os,
    required String appVersion,
  }) async {
    final client = _client;
    final uid = userId;
    if (client == null || uid == null) return;
    try {
      await client.from('devices').upsert({
        'user_id': uid,
        'public_device_id': deviceId,
        'name': model,
        'platform': AppConfig.platform,
        'device_type': AppConfig.deviceType,
        'app_version': appVersion,
        'product_slug': AppConfig.productSlug,
        'last_seen_at': DateTime.now().toUtc().toIso8601String(),
        'updated_at': DateTime.now().toUtc().toIso8601String(),
      }, onConflict: 'public_device_id');
    } catch (e) {
      log.w('upsertDevice failed: $e');
    }
  }

  // --- Generic per-user table helpers -------------------------------------

  Future<List<Map<String, dynamic>>> fetchRows(
    String table, {
    String? playlistId,
    String orderBy = 'created_at',
    bool ascending = false,
    int? limit,
  }) async {
    final client = _client;
    final uid = userId;
    if (client == null || uid == null) return const [];
    if (table == 'favorites') {
      return _fetchFavorites(client, uid, playlistId);
    }
    if (table == 'watch_history') {
      return _fetchHistory(client, uid, playlistId, limit: limit);
    }
    if (table == 'continue_watching') {
      return _fetchContinueWatching(client, uid, playlistId, limit: limit);
    }
    try {
      var query = client.from(table).select().eq('user_id', uid);
      if (playlistId != null) {
        query = query.eq('playlist_id', playlistId);
      }
      final ordered = query.order(orderBy, ascending: ascending);
      final res = limit != null ? await ordered.limit(limit) : await ordered;
      return (res as List)
          .whereType<Map>()
          .map((e) => Map<String, dynamic>.from(e))
          .toList();
    } catch (e) {
      log.w('fetchRows($table) failed: $e');
      return const [];
    }
  }

  Future<void> upsertRow(
    String table,
    Map<String, dynamic> row, {
    required String onConflict,
  }) async {
    final client = _client;
    final uid = userId;
    if (client == null || uid == null) return;
    if (table == 'favorites') {
      await _saveFavorite(client, uid, row);
      return;
    }
    if (table == 'watch_history') {
      await _saveHistory(client, uid, row);
      return;
    }
    if (table == 'continue_watching') {
      await _saveContinueWatching(client, uid, row);
      return;
    }
    try {
      await client.from(table).upsert({
        ...row,
        'user_id': uid,
      }, onConflict: onConflict);
    } catch (e) {
      log.w('upsertRow($table) failed: $e');
    }
  }

  Future<void> deleteRow(
    String table, {
    required String playlistId,
    required String kind,
    required String refId,
  }) async {
    final client = _client;
    final uid = userId;
    if (client == null || uid == null) return;
    if (table == 'favorites') {
      await _deleteContentRow(
        client,
        table,
        uid,
        _platformContentId(playlistId, kind, refId),
      );
      return;
    }
    if (table == 'watch_history') {
      await _deleteContentRow(
        client,
        table,
        uid,
        _platformContentId(playlistId, kind, refId),
      );
      return;
    }
    if (table == 'continue_watching') {
      await _deleteContentRow(
        client,
        'watch_history',
        uid,
        _platformContentId(playlistId, kind, refId),
      );
      return;
    }
    try {
      await client
          .from(table)
          .delete()
          .eq('user_id', uid)
          .eq('playlist_id', playlistId)
          .eq('kind', kind)
          .eq('ref_id', refId);
    } catch (e) {
      log.w('deleteRow($table) failed: $e');
    }
  }

  // --- Activation ----------------------------------------------------------

  /// Records a device activation request and returns whether it was accepted
  /// by the server. The backoffice (or an admin SQL action) later flips the
  /// row's status to `approved` and attaches credentials.
  Future<bool> requestActivation({
    required String deviceId,
    required String code,
  }) async {
    final client = _client;
    if (client == null) return false;
    try {
      await client.from('activation_requests').upsert({
        'device_id': deviceId,
        'code': code,
        'status': 'pending',
        'requested_at': DateTime.now().toUtc().toIso8601String(),
      }, onConflict: 'device_id');
      return true;
    } catch (e) {
      log.w('requestActivation failed: $e');
      return false;
    }
  }

  /// Polls the activation request status. Returns the row (with status and,
  /// when approved, the attached credentials) or null.
  Future<Map<String, dynamic>?> fetchActivation(String deviceId) async {
    final client = _client;
    if (client == null) return null;
    try {
      final row = await client
          .from('activation_requests')
          .select()
          .eq('device_id', deviceId)
          .maybeSingle();
      return row;
    } catch (e) {
      log.w('fetchActivation failed: $e');
      return null;
    }
  }

  // --- Support -------------------------------------------------------------

  Future<bool> sendSupportMessage(String message, {String? email}) async {
    final client = _client;
    if (client == null) return false;
    try {
      await client.from('support_messages').insert({
        'user_id': userId,
        'email': email,
        'message': message,
      });
      return true;
    } catch (e) {
      log.w('sendSupportMessage failed: $e');
      return false;
    }
  }

  // --- Production library table adapters ----------------------------------

  String _platformContentId(String playlistId, String kind, String refId) =>
      '${AppConfig.platform}:$playlistId:$kind:$refId';

  ({String playlistId, String kind, String refId})? _parseContentId(
    String raw, {
    required bool platformScoped,
  }) {
    final parts = raw.split(':');
    final offset = platformScoped && parts.length >= 4 ? 1 : 0;
    if (parts.length < offset + 3) return null;
    return (
      playlistId: parts[offset],
      kind: parts[offset + 1],
      refId: parts.sublist(offset + 2).join(':'),
    );
  }

  Future<List<Map<String, dynamic>>> _fetchFavorites(
    SupabaseClient client,
    String uid,
    String? playlistId,
  ) async {
    if (playlistId == null) return const [];
    try {
      final prefix = '${AppConfig.platform}:$playlistId:%';
      final rows = await client
          .from('favorites')
          .select('content_id,content_type,title,poster_url,created_at')
          .eq('user_id', uid)
          .like('content_id', prefix)
          .order('created_at', ascending: false);
      return rows
          .whereType<Map>()
          .map((row) {
            final parsed = _parseContentId(
              '${row['content_id'] ?? ''}',
              platformScoped: true,
            );
            if (parsed == null) return null;
            return {
              'playlist_id': parsed.playlistId,
              'kind': parsed.kind,
              'ref_id': parsed.refId,
              'title': row['title'],
              'image_url': row['poster_url'],
              'subtitle': null,
              'payload': {
                'streamId': parsed.refId,
                'seriesId': parsed.refId,
                'id': parsed.refId,
                'name': row['title'],
                'title': row['title'],
                'poster': row['poster_url'],
                'cover': row['poster_url'],
                'logo': row['poster_url'],
              },
              'created_at': row['created_at'],
            };
          })
          .nonNulls
          .toList();
    } catch (e) {
      log.w('fetch favorites adapter failed: $e');
      return const [];
    }
  }

  Future<List<Map<String, dynamic>>> _fetchHistory(
    SupabaseClient client,
    String uid,
    String? playlistId, {
    int? limit,
  }) async {
    if (playlistId == null) return const [];
    try {
      final prefix = '${AppConfig.platform}:$playlistId:%';
      var query = client
          .from('watch_history')
          .select('content_id,content_type,title,poster_url,updated_at')
          .eq('user_id', uid)
          .like('content_id', prefix)
          .order('updated_at', ascending: false);
      final rows = limit == null ? await query : await query.limit(limit);
      return rows
          .whereType<Map>()
          .map((row) {
            final parsed = _parseContentId(
              '${row['content_id'] ?? ''}',
              platformScoped: true,
            );
            if (parsed == null) return null;
            return {
              'playlist_id': parsed.playlistId,
              'kind': parsed.kind,
              'ref_id': parsed.refId,
              'title': row['title'],
              'image_url': row['poster_url'],
              'payload': _payloadFromCloudRow(parsed.kind, parsed.refId, row),
              'watched_at': row['updated_at'],
            };
          })
          .nonNulls
          .toList();
    } catch (e) {
      log.w('fetch history adapter failed: $e');
      return const [];
    }
  }

  Future<List<Map<String, dynamic>>> _fetchContinueWatching(
    SupabaseClient client,
    String uid,
    String? playlistId, {
    int? limit,
  }) async {
    if (playlistId == null) return const [];
    try {
      final prefix = '${AppConfig.platform}:$playlistId:%';
      var query = client
          .from('watch_history')
          .select(
            'content_id,content_type,title,poster_url,position_ms,duration_ms,updated_at',
          )
          .eq('user_id', uid)
          .like('content_id', prefix)
          .gt('duration_ms', 0)
          .order('updated_at', ascending: false);
      final rows = limit == null ? await query : await query.limit(limit);
      return rows
          .whereType<Map>()
          .map((row) {
            final parsed = _parseContentId(
              '${row['content_id'] ?? ''}',
              platformScoped: true,
            );
            if (parsed == null) return null;
            final positionMs = (row['position_ms'] as num?)?.toInt() ?? 0;
            final durationMs = (row['duration_ms'] as num?)?.toInt() ?? 0;
            return {
              'playlist_id': parsed.playlistId,
              'kind': parsed.kind,
              'ref_id': parsed.refId,
              'title': row['title'],
              'image_url': row['poster_url'],
              'position_secs': positionMs ~/ 1000,
              'duration_secs': durationMs ~/ 1000,
              'payload': _payloadFromCloudRow(parsed.kind, parsed.refId, row),
              'updated_at': row['updated_at'],
            };
          })
          .nonNulls
          .toList();
    } catch (e) {
      log.w('fetch continue adapter failed: $e');
      return const [];
    }
  }

  Map<String, dynamic> _payloadFromCloudRow(
    String kind,
    String refId,
    Map row,
  ) {
    final title = '${row['title'] ?? ''}';
    final poster = row['poster_url'] as String?;
    final mediaKind = MediaKind.fromWire(kind);
    return switch (mediaKind) {
      MediaKind.live => {'streamId': refId, 'name': title, 'logo': poster},
      MediaKind.movie => {'streamId': refId, 'name': title, 'poster': poster},
      MediaKind.series => {'seriesId': refId, 'name': title, 'cover': poster},
      MediaKind.episode => {
        'id': refId,
        'title': title,
        'image': poster,
        'containerExtension': 'mp4',
      },
    };
  }

  Future<void> _saveFavorite(
    SupabaseClient client,
    String uid,
    Map<String, dynamic> row,
  ) async {
    final contentId = _platformContentId(
      '${row['playlist_id']}',
      '${row['kind']}',
      '${row['ref_id']}',
    );
    try {
      await _deleteContentRow(client, 'favorites', uid, contentId);
      await client.from('favorites').insert({
        'user_id': uid,
        'content_id': contentId,
        'content_type': row['kind'],
        'title': row['title'],
        'poster_url': row['image_url'],
        'created_at': row['created_at'],
      });
    } catch (e) {
      log.w('save favorite adapter failed: $e');
    }
  }

  Future<void> _saveHistory(
    SupabaseClient client,
    String uid,
    Map<String, dynamic> row,
  ) async {
    final contentId = _platformContentId(
      '${row['playlist_id']}',
      '${row['kind']}',
      '${row['ref_id']}',
    );
    try {
      await _deleteContentRow(client, 'watch_history', uid, contentId);
      await client.from('watch_history').insert({
        'user_id': uid,
        'content_id': contentId,
        'content_type': row['kind'],
        'title': row['title'],
        'poster_url': row['image_url'],
        'position_ms': 0,
        'duration_ms': 0,
        'updated_at':
            row['watched_at'] ?? DateTime.now().toUtc().toIso8601String(),
      });
    } catch (e) {
      log.w('save history adapter failed: $e');
    }
  }

  Future<void> _saveContinueWatching(
    SupabaseClient client,
    String uid,
    Map<String, dynamic> row,
  ) async {
    final contentId = _platformContentId(
      '${row['playlist_id']}',
      '${row['kind']}',
      '${row['ref_id']}',
    );
    try {
      await _deleteContentRow(client, 'watch_history', uid, contentId);
      await client.from('watch_history').insert({
        'user_id': uid,
        'content_id': contentId,
        'content_type': row['kind'],
        'title': row['title'],
        'poster_url': row['image_url'],
        'position_ms': ((row['position_secs'] as num?)?.toInt() ?? 0) * 1000,
        'duration_ms': ((row['duration_secs'] as num?)?.toInt() ?? 0) * 1000,
        'updated_at':
            row['updated_at'] ?? DateTime.now().toUtc().toIso8601String(),
      });
    } catch (e) {
      log.w('save continue adapter failed: $e');
    }
  }

  Future<void> _deleteContentRow(
    SupabaseClient client,
    String table,
    String uid,
    String contentId,
  ) async {
    try {
      await client
          .from(table)
          .delete()
          .eq('user_id', uid)
          .eq('content_id', contentId);
    } catch (e) {
      log.w('delete $table adapter failed: $e');
    }
  }
}
