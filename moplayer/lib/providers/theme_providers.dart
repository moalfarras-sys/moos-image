import 'dart:async';
import 'dart:io';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/theme/app_colors.dart';
import '../core/theme/palette.dart';
import 'core_providers.dart';

/// The palette the app is drawn in, kept in step with the desktop.
///
/// When the owner switches MoOS from Amethyst to Aurora, Plasma rewrites
/// `kdeglobals`; this watches the file and recolours MoPlayer while it runs,
/// the way every other window on the desktop recolours. The watch is on the
/// config *directory*, because Plasma replaces the file rather than writing
/// into it, and a watch on the old inode would never fire again.
final paletteProvider = NotifierProvider<PaletteController, Palette>(
  PaletteController.new,
);

class PaletteController extends Notifier<Palette> {
  StreamSubscription<FileSystemEvent>? _watch;
  Timer? _debounce;

  @override
  Palette build() {
    final fromSystem = ref.watch(
      settingsProvider.select((s) => s.accentFromSystem),
    );
    ref.onDispose(() {
      _watch?.cancel();
      _debounce?.cancel();
    });
    final palette = fromSystem ? Palette.fromDesktop() : Palette.ember;
    AppColors.palette = palette;
    if (fromSystem) _watchDesktop();
    return palette;
  }

  void _watchDesktop() {
    final file = Palette.kdeglobalsFile();
    if (file == null) return;
    try {
      _watch = file.parent.watch().listen((event) {
        if (!event.path.endsWith('/kdeglobals')) return;
        // Plasma writes the file several times while applying a theme.
        _debounce?.cancel();
        _debounce = Timer(const Duration(milliseconds: 600), () {
          final next = Palette.fromDesktop();
          if (next == state) return;
          AppColors.palette = next;
          state = next;
        });
      });
    } on Object {
      // Not every filesystem can be watched; the palette then updates on the
      // next launch instead of live.
    }
  }
}
