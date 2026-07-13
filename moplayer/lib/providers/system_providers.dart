import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/l10n/strings.dart';
import '../core/constants/app_constants.dart';
import '../services/player/player_service.dart';
import '../services/system/desktop_service.dart';
import 'core_providers.dart';

/// The one [PlayerService] for the whole app.
///
/// App-scoped on purpose: a channel keeps playing while the user browses, and a
/// second libmpv instance would mean a second decode pipeline and a second
/// audio stream.
final playerServiceProvider = Provider<PlayerService>((ref) {
  final service = PlayerService();
  ref.onDispose(service.dispose);
  return service;
});

final desktopServiceProvider = Provider<DesktopService>((ref) {
  final service = DesktopService();
  ref.onDispose(service.dispose);
  return service;
});

/// The interface language. Defaults to the session's (`LANG`), because a MoOS
/// user who set the system to Arabic should not have to set it again here.
class LanguageController extends Notifier<Lang> {
  @override
  Lang build() {
    final cache = ref.read(cacheServiceProvider);
    return Lang.fromWire(cache.settingOr<String?>(StorageKeys.language, null));
  }

  Future<void> set(Lang lang) async {
    if (state == lang) return;
    state = lang;
    await ref.read(cacheServiceProvider).setSetting(StorageKeys.language, lang.name);
  }
}

final languageProvider = NotifierProvider<LanguageController, Lang>(
  LanguageController.new,
);

/// The string table for the current language. Widgets read this, never [Lang].
final stringsProvider = Provider<S>((ref) => S(ref.watch(languageProvider)));
