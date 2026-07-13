import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/theme/app_theme.dart';
import '../providers/system_providers.dart';
import 'router.dart';

class MoPlayerApp extends ConsumerWidget {
  const MoPlayerApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final lang = ref.watch(languageProvider);

    return MaterialApp.router(
      title: 'MoPlayer',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.dark,
      darkTheme: AppTheme.dark,
      themeMode: ThemeMode.dark,
      routerConfig: ref.watch(routerProvider),

      locale: lang.locale,
      supportedLocales: const [Locale('ar'), Locale('en'), Locale('de')],
      localizationsDelegates: const [
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],

      // The whole tree flips for Arabic — nav rail, poster rails, seek bar,
      // every icon that points somewhere. `Directionality` here rather than
      // relying on the locale alone, because the shell is built above the
      // Localizations widget that would otherwise supply it.
      builder: (context, child) => Directionality(
        textDirection: lang.direction,
        child: child ?? const SizedBox.shrink(),
      ),
    );
  }
}
