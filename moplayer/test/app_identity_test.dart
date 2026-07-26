import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:moplayer_moos/core/config/app_config.dart';

/// The app id is written down in four places that cannot see each other: Dart,
/// CMake, the `.desktop` file, and the MPRIS bus name. When they agree, Plasma
/// shows the MoPlayer icon in the taskbar and the media applet can raise the
/// window. When one of them drifts — a rename, a `flutter create` that
/// regenerates the runner — the app still builds, still runs, and quietly wears
/// a generic Qt-looking icon with media controls that go nowhere.
///
/// That failure is invisible to every other test in this repo, and it is the
/// exact failure MoOS's own `moos-qml-shell` was written to prevent for the QML
/// apps. So it gets a test.
void main() {
  group('application identity', () {
    const appId = 'org.moos.moplayer';

    /// The *icon* name is deliberately not the app id. MoOS's own
    /// `verify_identity.py` requires a first-party launcher's `Icon=` to begin
    /// with `moos-`, which is how the image proves at build time that no app is
    /// wearing an inherited Fedora icon. The two names are independent — Plasma
    /// matches the window by app_id and only then reads `Icon=` — and this test
    /// is what stops someone "fixing" the inconsistency and silently failing the
    /// image's gate.
    const iconName = 'moos-moplayer';

    final desktop = File(
      'packaging/moos/org.moos.moplayer.desktop',
    ).readAsStringSync();

    test('AppConfig is the source of truth', () {
      expect(AppConfig.appId, appId);
    });

    test('the network identity tracks the package release', () {
      final manifest = File('pubspec.yaml').readAsStringSync();
      final version = RegExp(
        r'^version:\s*([^+\s]+)',
        multiLine: true,
      ).firstMatch(manifest)!.group(1)!;
      final release = version.split('.').take(2).join('.');

      expect(
        AppConfig.userAgent,
        'MoPlayer/$release (MoOS)',
        reason:
            'IPTV panels see the User-Agent, so it must not report an old app '
            'release after pubspec.yaml is bumped',
      );
    });

    test('the GTK runner is built with the same id', () {
      final cmake = File('linux/CMakeLists.txt').readAsStringSync();
      expect(
        cmake,
        contains('set(APPLICATION_ID "$appId")'),
        reason: 'linux/CMakeLists.txt must set APPLICATION_ID to $appId',
      );
    });

    test(
      'Linux closes before Flutter tears down an invalid NVIDIA EGL surface',
      () {
        final runner = File(
          'linux/runner/my_application.cc',
        ).readAsStringSync();
        expect(runner, contains('close_before_flutter_egl_teardown'));
        expect(
          runner,
          contains('g_signal_connect(window, "delete-event"'),
          reason:
              'KWin and the in-app close button must share the guarded path',
        );
        expect(
          runner,
          contains('_exit(EXIT_SUCCESS)'),
          reason:
              'normal GTK destruction re-enters Flutter after Wayland has '
              'invalidated the EGL surface and aborts inside libepoxy on NVIDIA',
        );
      },
    );

    test('a second launch forwards URLs and sections to the running app', () {
      final runner = File('linux/runner/my_application.cc').readAsStringSync();
      final shell = File('lib/app/main_shell.dart').readAsStringSync();

      expect(runner, contains('G_APPLICATION_HANDLES_COMMAND_LINE'));
      expect(runner, contains('my_application_command_line'));
      expect(runner, contains('org.moos.moplayer/activation'));
      expect(runner, contains('fl_method_channel_invoke_method'));
      expect(
        shell,
        contains("MethodChannel(\n    'org.moos.moplayer/activation'"),
      );
      expect(shell, contains('LaunchArgs.parse('));
      expect(shell, contains('playDirect(url)'));
    });

    test('the launcher entry matches the window it launches', () {
      expect(
        desktop,
        contains('StartupWMClass=$appId'),
        reason: 'Plasma matches the window to this launcher by StartupWMClass',
      );
      expect(
        desktop,
        contains('Icon=$iconName'),
        reason: "MoOS's verify_identity.py requires a moos- prefixed icon",
      );
      expect(desktop, contains('Exec=moplayer'));
    });

    test('the launcher speaks all three of the app\'s languages', () {
      // MoOS ships Arabic and English on every surface, and MoPlayer adds German.
      // An app whose *interface* is trilingual but whose launcher is not is an
      // app that is only translated where someone happened to look.
      for (final key in ['GenericName', 'Comment', 'Keywords']) {
        for (final lang in ['ar', 'de']) {
          expect(
            desktop,
            contains('$key[$lang]='),
            reason: '$key has no $lang translation',
          );
        }
      }
    });

    test('every jump-list action resolves to a real section', () {
      // A `.desktop` file is a contract. MoOS's AGENTS.md records what happens
      // when it is not honoured: eleven buttons once shipped that opened routes
      // nobody had implemented, popped an error and did nothing — and every gate
      // was green. So each action's Exec must name a section `LaunchArgs` parses.
      final sections = File('lib/app/launch_args.dart').readAsStringSync();

      final actions = RegExp(
        r'^Exec=moplayer --section (\w+)$',
        multiLine: true,
      ).allMatches(desktop).map((m) => m.group(1)!).toList();

      expect(
        actions,
        containsAll([
          'live',
          'movies',
          'series',
          'search',
          'favorites',
          'settings',
        ]),
        reason: 'the six non-home destinations need launcher jump-list actions',
      );

      for (final action in actions) {
        expect(
          sections,
          contains("'$action'"),
          reason:
              "the launcher promises --section $action, but launch_args.dart "
              'does not parse it',
        );
        expect(
          desktop,
          contains('[Desktop Action ${_titleCase(action)}]'),
          reason: 'the $action action has no [Desktop Action] group',
        );
      }
    });

    test('the MPRIS bus name is derived from the app, not hardcoded twice', () {
      // org.mpris.MediaPlayer2.<name> — the suffix the desktop binds media keys
      // to. It has no dots by spec; a copy of the full app id here would make
      // the bus name invalid and the whole registration fail silently.
      expect(AppConfig.mprisName, isNot(contains('.')));
      expect(AppConfig.mprisName, 'moplayer');
    });

    test('the icon set covers the sizes Plasma actually asks for', () {
      // 22 and 24 are the panel; 48 is Kickoff; 512 is the overview and the
      // "about" dialogs. A missing size does not fall back gracefully — Plasma
      // scales the nearest one and it looks it.
      for (final size in [16, 22, 24, 32, 48, 64, 128, 256, 512]) {
        final icon = File(
          'packaging/moos/icons/hicolor/${size}x$size/apps/$iconName.png',
        );
        expect(icon.existsSync(), isTrue, reason: 'missing the ${size}px icon');
      }

      // And the scalable one, which is what a 4K Kickoff and a HiDPI Alt-Tab
      // actually reach for.
      expect(
        File(
          'packaging/moos/icons/hicolor/scalable/apps/$iconName.svg',
        ).existsSync(),
        isTrue,
        reason: 'missing the scalable icon',
      );
    });

    test('the app has AppStream metadata, or it has no entry in Discover', () {
      final metainfo = File('packaging/moos/org.moos.moplayer.metainfo.xml');
      expect(metainfo.existsSync(), isTrue);

      final xml = metainfo.readAsStringSync();
      expect(xml, contains('<id>$appId</id>'));
      expect(
        xml,
        contains(
          '<launchable type="desktop-id">org.moos.moplayer.desktop</launchable>',
        ),
        reason: 'the metadata must point at the launcher it describes',
      );
      expect(
        xml,
        contains('<icon type="stock">$iconName</icon>'),
        reason: 'the software centre would otherwise show no icon',
      );
      expect(
        xml,
        contains(
          '<url type="homepage">https://github.com/moalfarras-sys/MoPlayerMoOS</url>',
        ),
        reason: 'AppStream rejects a first-party app with no homepage URL',
      );
    });
  });
}

String _titleCase(String value) => value[0].toUpperCase() + value.substring(1);
