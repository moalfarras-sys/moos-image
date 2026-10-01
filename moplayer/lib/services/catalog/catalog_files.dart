import 'dart:io';
import 'dart:typed_data';

/// Where a source's catalogue is kept between runs: one plain file per
/// document, under `$XDG_CACHE_HOME/moplayer/catalog/<source>/`.
///
/// **Why files, and why not Hive.** The catalogue used to live in a Hive box,
/// and Hive keeps every box it opens in memory and appends every write to one
/// log. On the owner's station that box reached **278 MB**: twelve rewrites of a
/// 5 MB series list, twelve of the film list, and a 146 MB JSON re-encoding of a
/// 395,424-entry playlist. Opening the app read and decoded all of it on the UI
/// isolate before the first frame — six seconds of a dead window and 1.4 GB of
/// resident memory, before anything was even shown.
///
/// A file per document costs nothing until it is read, it is read on a
/// background isolate, and the bytes on disk are the server's own bytes: a
/// panel's JSON answer is written exactly as it arrived, so caching it costs no
/// re-encode at all. It is a *cache* in the XDG sense — deleting the directory
/// loses nothing a refresh cannot bring back — so it lives under
/// `$XDG_CACHE_HOME`, which backups skip and the user can clear.
///
/// Every method here is plain synchronous `dart:io` and is meant to be called
/// from inside an isolate job; nothing in this class touches Flutter.
class CatalogFiles {
  const CatalogFiles(this.root);

  /// The per-user catalogue root.
  factory CatalogFiles.forUser() => CatalogFiles(defaultRoot());

  final String root;

  static String defaultRoot() {
    final env = Platform.environment;
    final xdg = env['XDG_CACHE_HOME'];
    final base = (xdg != null && xdg.isNotEmpty)
        ? xdg
        : '${env['HOME'] ?? '.'}/.cache';
    return '$base/moplayer/catalog';
  }

  /// A namespace is a source id; anything else in it would be a path.
  String _dir(String namespace) =>
      '$root/${namespace.replaceAll(RegExp(r'[^A-Za-z0-9_.-]'), '_')}';

  String path(String namespace, String name) =>
      '${_dir(namespace)}/${name.replaceAll(RegExp(r'[^A-Za-z0-9_.-]'), '_')}';

  Uint8List? read(String namespace, String name) {
    final file = File(path(namespace, name));
    try {
      return file.existsSync() ? file.readAsBytesSync() : null;
    } on FileSystemException {
      return null;
    }
  }

  /// How long ago [name] was written, or null when it does not exist.
  Duration? age(String namespace, String name) {
    try {
      final stat = File(path(namespace, name)).statSync();
      if (stat.type == FileSystemEntityType.notFound) return null;
      return DateTime.now().difference(stat.modified);
    } on FileSystemException {
      return null;
    }
  }

  DateTime? modified(String namespace, String name) {
    try {
      final stat = File(path(namespace, name)).statSync();
      if (stat.type == FileSystemEntityType.notFound) return null;
      return stat.modified;
    } on FileSystemException {
      return null;
    }
  }

  /// Writes [bytes] atomically: a reader never sees half a catalogue, and a
  /// power cut mid-write leaves the previous copy in place.
  ///
  /// A failure is swallowed on purpose. A read-only or full disk costs the
  /// next launch its head start, never the current session its catalogue.
  bool write(String namespace, String name, List<int> bytes) {
    final target = path(namespace, name);
    final tmp = '$target.tmp$pid';
    try {
      Directory(_dir(namespace)).createSync(recursive: true);
      File(tmp).writeAsBytesSync(bytes, flush: true);
      File(tmp).renameSync(target);
      return true;
    } on FileSystemException {
      try {
        File(tmp).deleteSync();
      } on FileSystemException {
        // Nothing to clean up.
      }
      return false;
    }
  }

  void delete(String namespace, String name) {
    try {
      File(path(namespace, name)).deleteSync();
    } on FileSystemException {
      // Already gone.
    }
  }

  /// Forgets one source's catalogue, or every source's when [namespace] is null.
  void clear([String? namespace]) {
    final dir = Directory(namespace == null ? root : _dir(namespace));
    try {
      if (dir.existsSync()) dir.deleteSync(recursive: true);
    } on FileSystemException {
      // A cache that cannot be cleared is still only a cache.
    }
  }
}
