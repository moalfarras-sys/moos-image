import 'dart:io';
import 'dart:typed_data';

import '../../core/config/app_config.dart';
import '../catalog/catalog_files.dart';
import '../catalog/http_fetch.dart';
import '../m3u/m3u_parser.dart';
import 'xmltv_guide.dart';

/// What a background isolate needs to load one XMLTV guide.
class GuideJob {
  const GuideJob({
    required this.url,
    required this.cacheRoot,
    required this.namespace,
  });

  final String url;
  final String cacheRoot;
  final String namespace;

  static const cacheFile = 'guide.xml';
}

/// The cached guide and when it was written, or null. Runs inside an isolate.
({EpgGuide guide, DateTime written})? loadCachedGuide(GuideJob job) {
  final files = CatalogFiles(job.cacheRoot);
  final bytes = files.read(job.namespace, GuideJob.cacheFile);
  if (bytes == null) return null;
  return (
    guide: EpgGuide.parse(M3uParser.decode(_inflate(bytes))),
    written:
        files.modified(job.namespace, GuideJob.cacheFile) ?? DateTime.now(),
  );
}

/// Downloads, caches and parses the guide. Runs inside an isolate.
///
/// A panel without a guide answers with an HTML page or nothing at all; that
/// parses to [EpgGuide.empty] and is not cached, so a panel that adds a guide
/// later is asked again.
Future<EpgGuide> fetchGuide(GuideJob job) async {
  final raw = await fetchBytes(
    Uri.parse(job.url),
    headers: const {'User-Agent': AppConfig.apiUserAgent},
    timeout: const Duration(minutes: 2),
  );
  final bytes = _inflate(raw);
  final guide = EpgGuide.parse(M3uParser.decode(bytes));
  if (!guide.isEmpty) {
    CatalogFiles(job.cacheRoot).write(job.namespace, GuideJob.cacheFile, bytes);
  }
  return guide;
}

/// Guides are often published as `.xml.gz`; a served file is not a
/// Content-Encoding, so the HTTP layer does not undo it.
Uint8List _inflate(Uint8List bytes) {
  if (bytes.length > 2 && bytes[0] == 0x1f && bytes[1] == 0x8b) {
    try {
      return Uint8List.fromList(gzip.decode(bytes));
    } on Object {
      return bytes;
    }
  }
  return bytes;
}
