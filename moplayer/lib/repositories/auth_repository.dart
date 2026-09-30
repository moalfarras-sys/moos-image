import 'dart:isolate';

import 'package:flutter/services.dart';

import '../core/error/failures.dart';
import '../core/error/result.dart';
import '../core/utils/app_logger.dart';
import '../models/playlist_config.dart';
import '../services/catalog/catalog_files.dart';
import '../services/m3u/m3u_catalog.dart';
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
  /// Downloads and sorts a playlist — on a background isolate, and into the
  /// catalogue cache, so the library the user lands on after signing in is the
  /// one this probe already fetched rather than a second download of it.
  ///
  /// It used to download the whole file and parse it on the UI isolate, and
  /// then the library downloaded and parsed it again: for the owner's 121 MB
  /// playlist, two half-minute downloads and a window that stopped responding
  /// in between.
  Future<Result<int>> testM3u(PlaylistConfig config) async {
    final url = config.m3uUrl.trim();
    if (url.isEmpty) {
      return Err(Failure.parse('Please enter a playlist URL.'));
    }
    try {
      final M3uLibrary library;
      if (url.startsWith('asset://')) {
        final text = await rootBundle.loadString(
          'assets/${url.substring('asset://'.length)}',
        );
        library = await _parseText(text);
      } else {
        library = await _fetch(
          M3uLibraryJob(
            url: url,
            cacheRoot: CatalogFiles.forUser().root,
            namespace: config.id,
          ),
        );
      }
      if (library.totalEntries == 0) {
        return Err(Failure.parse('No channels found in that playlist.'));
      }
      return Ok(library.totalEntries);
    } on Failure catch (failure) {
      return Err(failure);
    } on Object catch (error) {
      log.e('testM3u failed: ${safeLogMessage(error)}');
      return Err(Failure.parse('Could not read the playlist data.'));
    }
  }

  static Future<M3uLibrary> _fetch(M3uLibraryJob job) =>
      Isolate.run(() => fetchM3uLibrary(job));

  static Future<M3uLibrary> _parseText(String text) =>
      Isolate.run(() => parseM3uText(text));

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
        macAddress: config.macAddress,
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
