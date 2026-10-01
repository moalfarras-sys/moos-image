/// What the owner typed as a "portal URL", turned into the endpoints a MAG box
/// would actually call.
///
/// Portal providers hand out every shape of address: `http://host:8080/c/`,
/// `http://host/stalker_portal/c/index.html`, a bare `host:8080`, or the API
/// file itself. Only one file answers the protocol — `portal.php` on most
/// resold panels, `server/load.php` on a Ministra install, usually under
/// `/stalker_portal/` — and which one it is cannot be known without asking.
/// [candidates] is the ordered list to ask; the client remembers the first one
/// that answers the handshake.
class StalkerPortalAddress {
  const StalkerPortalAddress._({
    required this.origin,
    required this.basePath,
    required this.candidates,
  });

  /// `scheme://host[:port]`, no path.
  final Uri origin;

  /// The directory that holds the portal's `c/` client: `''` for a portal at
  /// the root of the host, `/stalker_portal` for a classic Ministra install.
  final String basePath;

  /// Every API endpoint worth trying, most likely first, without duplicates.
  final List<Uri> candidates;

  static const String _portalFile = 'portal.php';
  static const String _loadFile = 'load.php';

  /// Returns null when [input] cannot be an http(s) portal address.
  static StalkerPortalAddress? parse(String input) {
    var text = input.trim();
    if (text.isEmpty) return null;
    if (!text.contains('://')) text = 'http://$text';
    final uri = Uri.tryParse(text);
    if (uri == null || uri.host.isEmpty) return null;
    final scheme = uri.scheme.toLowerCase();
    if (scheme != 'http' && scheme != 'https') return null;

    final origin = Uri(
      scheme: scheme,
      host: uri.host,
      port: uri.hasPort ? uri.port : null,
    );

    final segments = uri.pathSegments.where((s) => s.isNotEmpty).toList();
    Uri? explicit;
    if (segments.isNotEmpty) {
      final last = segments.last.toLowerCase();
      if (last == _portalFile || last == _loadFile) {
        explicit = origin.replace(path: '/${segments.join('/')}');
      }
      if (last.contains('.')) segments.removeLast();
    }
    if (segments.isNotEmpty && segments.last.toLowerCase() == 'c') {
      segments.removeLast();
    }
    if (segments.isNotEmpty && segments.last.toLowerCase() == 'server') {
      segments.removeLast();
    }
    final basePath = segments.isEmpty ? '' : '/${segments.join('/')}';

    final paths = <String>[
      if (explicit != null) explicit.path,
      '$basePath/$_portalFile',
      '$basePath/server/$_loadFile',
      if (!basePath.toLowerCase().endsWith('/stalker_portal'))
        '$basePath/stalker_portal/server/$_loadFile',
      if (basePath.isNotEmpty) ...[
        '/$_portalFile',
        '/server/$_loadFile',
        '/stalker_portal/server/$_loadFile',
      ],
    ];
    final seen = <String>{};
    final candidates = <Uri>[
      for (final path in paths)
        if (seen.add(path)) origin.replace(path: path),
    ];
    return StalkerPortalAddress._(
      origin: origin,
      basePath: basePath,
      candidates: List.unmodifiable(candidates),
    );
  }

  /// The portal root an [endpoint] belongs to, e.g. `/stalker_portal` for
  /// `/stalker_portal/server/load.php`. Used for the `Referer` a MAG box sends
  /// (`<root>/c/`) and to resolve bare logo file names.
  static String rootPathOf(Uri endpoint) {
    final segments = endpoint.pathSegments.where((s) => s.isNotEmpty).toList();
    if (segments.isNotEmpty && segments.last.contains('.')) {
      segments.removeLast();
    }
    if (segments.isNotEmpty && segments.last.toLowerCase() == 'server') {
      segments.removeLast();
    }
    return segments.isEmpty ? '' : '/${segments.join('/')}';
  }
}
