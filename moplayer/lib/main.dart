import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:media_kit/media_kit.dart';

import 'app/app.dart';
import 'app/bootstrap.dart';
import 'app/launch_args.dart';
import 'core/constants/app_constants.dart';
import 'core/utils/app_logger.dart';
import 'providers/core_providers.dart';
import 'services/system/desktop_service.dart';

/// [args] is what the `.desktop` file handed us: `--section live` from the
/// icon's jump list, or an `.m3u` path from Dolphin. See `app/launch_args.dart`.
Future<void> main(List<String> args) async {
  WidgetsFlutterBinding.ensureInitialized();

  // Binds libmpv. On MoOS this resolves to the system `mpv-libs` — the engine
  // the OS already ships — so the app brings no codec stack of its own.
  MediaKit.ensureInitialized();

  // Configure the window before the first frame, but do **not** map it yet: the
  // geometry the user left it in lives in the cache, which is not open until
  // `bootstrap()` has run. Showing it now and moving it afterwards makes Plasma
  // animate the window into place and then animate it a second time.
  await DesktopService.initWindow();

  final launch = LaunchArgs.parse(args);

  // Deliberately *not* the raw argv. An Xtream playlist URL carries the username
  // and the password in its query string, and a user who launches MoPlayer from
  // a terminal — or whose `.desktop` Exec line holds a source — would otherwise
  // be writing their credentials into the journal on every single start.
  log.i(
    'launch: section=${launch.section} '
    'playlist=${launch.playlist != null} stream=${launch.playUrl != null}',
  );

  final boot = await bootstrap(launch);

  // The container is built here rather than by `ProviderScope` so that the saved
  // window geometry can be read from the very same cache the app will use, and
  // the window can be placed *before* its first frame.
  final container = ProviderContainer(overrides: boot.overrides);
  final cache = container.read(cacheServiceProvider);

  await DesktopService.showWindow(
    WindowGeometry.decode(
      cache.settingOr<String?>(StorageKeys.windowGeometry, null),
    ),
  );

  runApp(
    UncontrolledProviderScope(container: container, child: const MoPlayerApp()),
  );
}
