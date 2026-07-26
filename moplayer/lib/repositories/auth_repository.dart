import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter/services.dart';

import '../core/config/app_config.dart';
import '../core/error/failures.dart';
import '../core/error/result.dart';
import '../core/utils/app_logger.dart';
import '../models/playlist_config.dart';
import '../services/m3u/m3u_parser.dart';
import '../services/storage/secure_storage_service.dart';
import '../services/supabase/supabase_service.dart';
import '../services/xtream/xtream_api.dart';

/// Owns the set of saved playlists, the active one, and the login/validation
/// logic for both Xtream and M3U sources.
class AuthRepository {
  AuthRepository(this._secure, this._supabase);

  final SecureStorageService _secure;
  final SupabaseService _supabase;

  /// The saved sources, with any duplicates healed on the way out.
  ///
  /// [saveAndActivate] no longer creates them, but the machines that ran the
  /// builds that did are real and their Settings screen lists the same playlist
  /// several times. Collapsing on read — and writing the collapsed list back —
  /// fixes those without a migration step that everyone else pays for. The first
  /// entry wins because it is the oldest, and it is the one the user's favourites
  /// are keyed to.
  Future<List<PlaylistConfig>> playlists() async {
    final stored = await _secure.readPlaylists();
    final seen = <String>{};
    final unique = [
      for (final playlist in stored)
        if (seen.add(playlist.identityKey)) playlist,
    ];
    if (unique.length != stored.length) {
      await _secure.writePlaylists(unique);
    }
    return unique;
  }

  Future<PlaylistConfig?> activePlaylist() => _secure.readActivePlaylist();

  /// Validates Xtream credentials by hitting `player_api.php`.
  Future<Result<XtreamAccountInfo>> testXtream(PlaylistConfig config) async {
    if (config.normalizedServer.isEmpty ||
        config.username.isEmpty ||
        config.password.isEmpty) {
      return Err(
        Failure.auth('Please fill in the server, username and password.'),
      );
    }
    final api = XtreamApi(config);
    try {
      final info = await api.authenticate();
      return Ok(info);
    } on Failure catch (f) {
      return Err(f);
    } catch (e) {
      log.e('testXtream failed: ${safeLogMessage(e)}');
      return Err(Failure.server(safeLogMessage(e)));
    } finally {
      api.close();
    }
  }

  /// Validates an M3U URL by fetching and parsing it, returning the channel
  /// count discovered.
  Future<Result<int>> testM3u(PlaylistConfig config) async {
    final url = config.m3uUrl.trim();
    if (url.isEmpty) {
      return Err(Failure.parse('Please enter a playlist URL.'));
    }
    final dio = _m3uDio();
    try {
      final body = await _readM3uBody(url, dio);
      if (!body.contains('#EXTINF') && !body.contains('#EXTM3U')) {
        return Err(
          Failure.parse('That URL did not return a valid M3U playlist.'),
        );
      }
      final parsed = M3uParser.parse(body);
      if (parsed.channels.isEmpty) {
        return Err(Failure.parse('No channels found in that playlist.'));
      }
      return Ok(parsed.channels.length);
    } on DioException catch (e) {
      if (e.type == DioExceptionType.connectionTimeout ||
          e.type == DioExceptionType.receiveTimeout) {
        return Err(Failure.timeout());
      }
      return Err(Failure.network('Could not download the playlist.'));
    } catch (e) {
      return Err(Failure.parse('$e'));
    } finally {
      dio.close(force: true);
    }
  }

  Dio _m3uDio() => Dio(
    BaseOptions(
      connectTimeout: AppConfig.connectTimeout,
      receiveTimeout: AppConfig.receiveTimeout,
      responseType: ResponseType.plain,
      headers: const {'User-Agent': 'MoPlayerPro/1.0'},
    ),
  );

  Future<String> _readM3uBody(String url, Dio dio) async {
    if (url.startsWith('asset://')) {
      final asset = 'assets/${url.substring('asset://'.length)}';
      return rootBundle.loadString(asset);
    }
    // A playlist opened from Dolphin. The `.desktop` file registers MoPlayer as
    // a handler for `application/x-mpegurl`, and a handler that cannot read a
    // local file is a handler that does nothing.
    if (url.startsWith('file://') || url.startsWith('/')) {
      return File(Uri.parse(url).toFilePath()).readAsString();
    }
    final res = await dio.get<String>(url);
    return res.data ?? '';
  }

  /// Persists a playlist and makes it the active source.
  ///
  /// Matching is on [PlaylistConfig.identityKey], not on the id. The id is minted
  /// at the call site — `pl_<micros>` from the login form, `file_<micros>` from a
  /// `.m3u` handed over by Dolphin — so an id match only ever happened when the
  /// caller already had the stored object in hand. Everything else appended.
  /// Opening the same playlist file three times therefore produced three
  /// identical rows in Settings, each with its own id, and the user could delete
  /// two of them and still have one left. Re-using the stored row's id keeps its
  /// favourites and resume positions attached, which are keyed on it.
  Future<bool> saveAndActivate(PlaylistConfig config) async {
    final list = [...await _secure.readPlaylists()];
    final existingIndex = list.indexWhere(
      (p) => p.identityKey == config.identityKey,
    );

    final PlaylistConfig stamped;
    if (existingIndex >= 0) {
      final existing = list[existingIndex];
      stamped = PlaylistConfig(
        id: existing.id,
        type: config.type,
        name: config.name,
        serverUrl: config.serverUrl,
        username: config.username,
        password: config.password,
        m3uUrl: config.m3uUrl,
        createdAt: existing.createdAt ?? DateTime.now(),
      );
      list[existingIndex] = stamped;
    } else {
      stamped = config.copyWith(createdAt: config.createdAt ?? DateTime.now());
      list.add(stamped);
    }

    final listSaved = await _secure.writePlaylists(list);
    final activeSaved = await _secure.writeActivePlaylist(stamped);
    return listSaved && activeSaved;
  }

  Future<void> setActive(PlaylistConfig config) =>
      _secure.writeActivePlaylist(config);

  Future<void> removePlaylist(String id) async {
    final list = [...await _secure.readPlaylists()];
    list.removeWhere((p) => p.id == id);
    await _secure.writePlaylists(list);
    final active = await _secure.readActivePlaylist();
    if (active?.id == id) {
      await _secure.writeActivePlaylist(list.isNotEmpty ? list.first : null);
    }
  }

  /// Clears the active session (keeps saved playlists so the user can pick one
  /// again) — used by Settings → Logout.
  Future<void> logout() async {
    await _secure.writeActivePlaylist(null);
  }

  bool get cloudEnabled => _supabase.enabled;
}
