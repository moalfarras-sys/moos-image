import 'dart:async';

import 'package:dbus/dbus.dart';

import '../../core/utils/app_logger.dart';

/// Opens the desktop's own file dialog, over the XDG desktop portal.
///
/// Deliberately not a Flutter file-picker package. This app runs on Wayland,
/// where a client cannot draw a dialog that browses the user's filesystem on its
/// own terms — the portal is the mechanism the session provides, and using it
/// means the user gets **Plasma's** file dialog, with their bookmarks, their
/// recent folders and their sort order, rather than a second file browser that
/// looks like nothing else on the desktop.
///
/// It is also why this costs no new dependency: `package:dbus` is already here
/// for MPRIS, and the portal is just an interface on the session bus. The same
/// reasoning as `lib/services/system/mpris.dart`.
class FileChooser {
  FileChooser({DBusClient? bus}) : _bus = bus ?? DBusClient.session();

  final DBusClient _bus;

  static const _portalName = 'org.freedesktop.portal.Desktop';
  static const _portalPath = '/org/freedesktop/portal/desktop';
  static const _fileChooser = 'org.freedesktop.portal.FileChooser';

  /// Asks the user for one file and returns its path, or null if they cancelled
  /// or no portal is running.
  ///
  /// A missing portal is not an error worth surfacing: it means the desktop has
  /// no file dialog to offer, and the caller's feature simply does not appear.
  /// Nothing in this app may be fatal because an optional session service is
  /// absent — the same rule `bootstrap()` follows.
  Future<String?> openFile({
    required String title,
    required String filterName,
    required List<String> extensions,
  }) async {
    // The portal answers on a Request object rather than by returning the path,
    // because the dialog outlives the method call. Subscribe *before* asking, or
    // a fast answer arrives before anything is listening.
    final completer = Completer<String?>();
    StreamSubscription<DBusSignal>? subscription;

    try {
      final signals = DBusSignalStream(
        _bus,
        interface: 'org.freedesktop.portal.Request',
        name: 'Response',
      );
      subscription = signals.listen((signal) {
        if (completer.isCompleted) return;
        completer.complete(_pathFromResponse(signal));
      });

      final result = await _bus.callMethod(
        destination: _portalName,
        path: DBusObjectPath(_portalPath),
        interface: _fileChooser,
        name: 'OpenFile',
        values: [
          const DBusString(''), // parent window: no handle under Wayland.
          DBusString(title),
          DBusDict.stringVariant({
            'modal': const DBusBoolean(true),
            'multiple': const DBusBoolean(false),
            'filters': DBusArray(
              DBusSignature('(sa(us))'),
              [
                DBusStruct([
                  DBusString(filterName),
                  DBusArray(
                    DBusSignature('(us)'),
                    [
                      for (final extension in extensions)
                        DBusStruct([
                          // 0 = glob pattern, 1 = MIME type.
                          const DBusUint32(0),
                          DBusString('*.$extension'),
                        ]),
                    ],
                  ),
                ]),
              ],
            ),
          }),
        ],
        replySignature: DBusSignature('o'),
      );
      // The reply is the Request path; the answer arrives on the signal above.
      // Held only to make the call's failure surface here rather than as a
      // dialog that never opens.
      result.returnValues;

      return await completer.future.timeout(
        // A dialog the user leaves open is not a hang, so this is generous. It
        // exists only so a portal that dies mid-dialog cannot leak this future
        // and the subscription behind it forever.
        const Duration(minutes: 10),
        onTimeout: () => null,
      );
    } on Object catch (e) {
      log.w('file chooser: portal unavailable ($e)');
      return null;
    } finally {
      await subscription?.cancel();
    }
  }

  String? _pathFromResponse(DBusSignal signal) {
    if (signal.values.length < 2) return null;
    final code = signal.values[0];
    // 0 is success; 1 is the user cancelling, which is not a failure.
    if (code is! DBusUint32 || code.value != 0) return null;
    final results = signal.values[1];
    if (results is! DBusDict) return null;
    final uris = results.children[const DBusString('uris')];
    if (uris is! DBusVariant) return null;
    final array = uris.value;
    if (array is! DBusArray || array.children.isEmpty) return null;
    final first = array.children.first;
    if (first is! DBusString) return null;
    return _pathFromUri(first.value);
  }

  /// The portal returns a `file://` URI, and mpv wants a path.
  String? _pathFromUri(String uri) {
    if (!uri.startsWith('file://')) return null;
    return Uri.decodeComponent(uri.substring('file://'.length));
  }

  Future<void> close() => _bus.close();
}
