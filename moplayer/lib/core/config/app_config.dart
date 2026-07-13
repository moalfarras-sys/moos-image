import 'dart:io';

/// Build-time configuration.
///
/// Diverges from the iOS app in exactly one way that matters: [platform] is
/// `'linux'`. The iOS build maps `TargetPlatform.linux` to `'web'`, which would
/// have filed every MoOS device's cloud rows under `web:` — a lie that is
/// invisible until you try to answer "which of my devices is this".
class AppConfig {
  const AppConfig._();

  static const String appName = 'MoPlayer';
  static const String appTagline = 'by Moalfarras';
  static const String productSlug = 'moplayer2';

  /// The MoOS application id. It is the `.desktop` file's base name, the
  /// Wayland `app_id`, the MPRIS bus suffix and the icon name — all four have to
  /// agree or Plasma draws a generic icon and the media controls attach to
  /// nothing. See `linux/runner/my_application.cc`.
  static const String appId = 'org.moos.moplayer';

  static const String webBaseUrl = String.fromEnvironment(
    'MOPLAYER_WEB_URL',
    defaultValue: 'https://moalfarras.space',
  );

  static const String supabaseUrl = String.fromEnvironment('SUPABASE_URL');

  static String get supabasePublishableKey {
    const publishable = String.fromEnvironment('SUPABASE_PUBLISHABLE_KEY');
    if (publishable.isNotEmpty) return publishable;
    return const String.fromEnvironment('SUPABASE_ANON_KEY');
  }

  /// Cloud sync is strictly optional. Without these defines the app is a
  /// complete, offline-capable player — which is how it ships by default in the
  /// MoOS image, since the image build has no business holding a project's keys.
  static bool get hasSupabase =>
      supabaseUrl.isNotEmpty && supabasePublishableKey.isNotEmpty;

  static const String platform = 'linux';

  static const String deviceType = 'moos-desktop';

  static const Duration connectTimeout = Duration(seconds: 15);
  static const Duration receiveTimeout = Duration(seconds: 25);

  /// A desktop grid shows far more at once than a phone list, and an Xtream
  /// server returns a category in one shot anyway.
  static const int pageSize = 120;

  /// Sent on every stream request. Some IPTV panels reject an unknown agent, and
  /// several block anything that looks like a browser.
  static const String userAgent = 'MoPlayer/1.0 (MoOS)';

  /// The MPRIS bus name suffix: the player owns
  /// `org.mpris.MediaPlayer2.moplayer`. Kept separate from [appId] because the
  /// spec wants a bare, lower-case token here, not a reverse-DNS id.
  static const String mprisName = 'moplayer';

  // ── What the app is actually running on ───────────────────────────────────
  // Read once, from the session's own environment. These drive nothing about
  // playback; they exist so Settings can *show the user what really hooked up*
  // rather than what the app hoped would. A claim like "integrated with MoOS"
  // that is never checked is exactly the kind of green light MoOS's own build
  // gates exist to forbid.

  static final Map<String, String> _env = Platform.environment;

  /// True only on a real MoOS system. `/etc/os-release` carries `ID=moos`; a
  /// developer running this on plain Fedora gets `false`, and Settings says so.
  static final bool isMoOS = () {
    try {
      final release = File('/etc/os-release');
      if (!release.existsSync()) return false;
      final text = release.readAsStringSync();
      return RegExp(r'^ID=("?)moos\1$', multiLine: true).hasMatch(text) ||
          text.contains('MoOS');
    } on Object {
      return false;
    }
  }();

  static final bool isPlasma =
      (_env['XDG_CURRENT_DESKTOP'] ?? '').toUpperCase().contains('KDE');

  static final bool isWayland =
      (_env['XDG_SESSION_TYPE'] ?? '').toLowerCase() == 'wayland' ||
      (_env['WAYLAND_DISPLAY'] ?? '').isNotEmpty;
}
