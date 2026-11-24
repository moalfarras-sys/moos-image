"""Mira Neural OS — desktop entry point, and the MoOS assistant.

A Qt Quick (GPU) interface over the same verified backends: the paired Echo voice satellite,
Gemini, Home Assistant and every Mo AI tool through its own executor. Mira IS Mo AI's app now:
she wears its desktop id and icon (org.moos.moai, one dock icon, Meta+Space) and answers its
launcher (`moai --panel device|apps|compat|remote|dev|chat`, `--ask TEXT`). One window per
user; a second launch raises it on the asked page (or, from the local wake listener, starts a
voice turn).
"""
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault('QT_QUICK_CONTROLS_STYLE', 'Basic')

from PySide6.QtCore import QTimer, QUrl  # noqa: E402
from PySide6.QtGui import QIcon  # noqa: E402
from PySide6.QtQuick import QQuickImageProvider  # noqa: E402
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon  # noqa: E402
from PySide6.QtNetwork import QLocalServer, QLocalSocket  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402

TEST_MODE = os.environ.get('MIRA_TEST_MODE') == '1'
DESKTOP_ID = 'org.moos.moai'        # Mo AI's launcher, shortcut and dock identity are Mira's
ICON_NAME = 'moos-moai'


def app_icon():
    """Mo AI's mark from the MoOS icon theme; Mira's own picture only if the theme lacks it."""
    icon = QIcon.fromTheme(ICON_NAME)
    return icon if not icon.isNull() else QIcon(str(ROOT / 'mira-icon-v2.png'))


class ThemeIconProvider(QQuickImageProvider):
    """image://icon/<name>: one icon from the desktop's theme, for QML."""

    def __init__(self):
        super().__init__(QQuickImageProvider.Pixmap)

    def requestPixmap(self, name, size, requested):
        edge = max(requested.width(), requested.height()) if requested.isValid() else 0
        edge = edge if edge > 0 else 128
        icon = QIcon.fromTheme(name) if re.fullmatch(r'[A-Za-z0-9._-]{1,80}', name or '') else QIcon()
        pixmap = (icon if not icon.isNull() else app_icon()).pixmap(edge, edge)
        if size is not None:
            size.setWidth(pixmap.width())
            size.setHeight(pixmap.height())
        return pixmap


def launch_request(argv):
    """What a launcher asked for — Mo AI's `--panel NAME`, `--device`, `--ask TEXT`, and Plasma's
    and Dolphin's `--background`, `--ask-about PATH…`, `--add-project DIR` — or {}.

    Read once, left to right: an option that takes a value consumes it. moos-open turns
    moos://ai/ask/<text> into `--ask "<text>"`, so words a web page chose are never read as
    `--install-improved-wake`, `--add-project` or any other option.
    """
    request = {}
    args = [str(a) for a in argv]
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ('--panel', '--ask'):
            if i + 1 < len(args):
                request[arg[2:]] = args[i + 1]
            i += 2
            continue
        if arg.startswith(('--panel=', '--ask=')):
            key, value = arg[2:].split('=', 1)
            request[key] = value
        elif arg == '--device':
            request['panel'] = 'device'
        elif arg == '--install-improved-wake':
            request['wake'] = 'improved'     # local only: offers the improved «ميرا» model to the Echo
        elif arg == '--wake-rollback':
            request['wake'] = 'rollback'     # local only: back to the proven «ميرا» model alone
        i += 1
    # Plasma's and Dolphin's arguments, by the same rule (kde_integration.launch_extras). An
    # explicit --panel wins over the page they imply.
    try:
        import kde_integration
        extras = kde_integration.launch_extras(args)
    except Exception as exc:   # never fatal: Mo AI's own arguments still work
        print('Mira KDE integration:', type(exc).__name__, exc, file=sys.stderr, flush=True)
        extras = {}
    for key, value in extras.items():
        request.setdefault(key, value)
    if 'panel' in request and not re.fullmatch(r'[a-z]{1,16}', request['panel']):
        del request['panel']
    return request


def option(name, default=None):
    for arg in sys.argv:
        if arg.startswith(name + '='):
            return arg.split('=', 1)[1]
    return default


def main():
    app = QApplication(sys.argv)
    app.setApplicationName('Mira')
    app.setOrganizationName('MoOS')
    app.setDesktopFileName(DESKTOP_ID)
    app.setWindowIcon(app_icon())
    request = launch_request(sys.argv[1:])
    start_hidden = bool(request.pop('background', False))   # login start: the tray, not the window
    message = b'open:' + json.dumps(request).encode() if request else b'show'

    socket_name = os.environ.get('MIRA_INSTANCE') or f'mo-dot-desktop-{os.getuid()}'
    existing = QLocalSocket()
    existing.connectToServer(socket_name)
    if existing.waitForConnected(300):
        if start_hidden and not request:
            return 0          # the login start found her already running: nothing to raise
        existing.write(message)
        existing.waitForBytesWritten(300)
        return 0
    QLocalServer.removeServer(socket_name)
    instance = QLocalServer()
    instance.setSocketOptions(QLocalServer.UserAccessOption)
    instance.listen(socket_name)

    from mira_bridge import paired
    if not TEST_MODE and paired():   # the model/announcement server exists only for a paired Echo
        import echo_http
        echo_http.start()

    from controller import Controller
    from faces import FaceProvider
    bridge_class = None
    if TEST_MODE:
        from review_fakes import FakeBridge
        bridge_class = FakeBridge
    controller = Controller(bridge_class=bridge_class)

    engine = QQmlApplicationEngine()
    # Match moos-qml-shell: native Kirigami policy with explicit Basic controls.
    engine.setProperty("_kirigamiTheme", "org.kde.desktop")
    engine.addImageProvider('mira', FaceProvider())
    engine.addImageProvider('icon', ThemeIconProvider())
    engine.addImportPath(str(ROOT / 'qml'))
    engine.rootContext().setContextProperty('mira', controller)
    engine.rootContext().setContextProperty('miraApplication', app)
    engine.load(QUrl.fromLocalFile(str(ROOT / 'qml' / 'Main.qml')))
    if not engine.rootObjects():
        print('Mira: the interface failed to load', file=sys.stderr, flush=True)
        return 1
    window = engine.rootObjects()[0]
    if start_hidden:
        window.hide()     # before the first frame: Meta+Space, the dock, the tray and D-Bus open her
    controller.start()
    if request:
        QTimer.singleShot(300, lambda: controller.handle_instance_command(message))

    def raise_window():
        window.showNormal()
        window.raise_()
        window.requestActivate()

    def activate():
        conn = instance.nextPendingConnection()
        if not conn:
            return

        def receive():
            command = bytes(conn.readAll()).strip()
            if command.startswith(b'snapshot:'):
                # Review hook: save this window's own pixels (never the rest of the desktop),
                # only into Mira's cache directory.
                target = Path(command[9:].decode('utf-8', 'replace')).expanduser()
                allowed = Path.home() / '.cache' / 'mira'
                if target.resolve().parent == allowed.resolve():
                    allowed.mkdir(parents=True, exist_ok=True)
                    conn.write(b'ok' if window.grabWindow().save(str(target)) else b'failed')
                else:
                    conn.write(b'refused')
                conn.flush()
                conn.disconnectFromServer()
                return
            controller.handle_instance_command(command)
            raise_window()
            conn.disconnectFromServer()
        conn.readyRead.connect(receive)
    instance.newConnection.connect(activate)
    app.aboutToQuit.connect(controller.shutdown)

    # Desktop apps reach her on the session bus: org.moos.Mira /Mira (kde_integration.start_dbus).
    # Public voice requests raise her window. The Island has its own visible
    # controls and authenticates Plasma before starting or stopping a turn.
    def dbus_show(panel):
        if panel:
            controller.handle_instance_command(b'open:' + json.dumps({'panel': panel}).encode())
        raise_window()

    def dbus_prefill(text):
        raise_window()
        controller.prefill.emit(text)

    def dbus_talk():
        raise_window()
        controller.talk()

    dbus = None
    if controller.kde is not None:
        import kde_integration
        dbus = kde_integration.start_dbus({
            'show': dbus_show, 'prefill': dbus_prefill, 'talk': dbus_talk, 'stop': controller.stop,
            'island_state': controller.island_voice_state,
            'island_talk': controller.start_island_voice,
            'island_stop': controller.stop_island_voice,
        })
        if dbus is not None:
            controller.islandVoiceChanged.connect(dbus.IslandVoiceChanged.emit)
        if not TEST_MODE:
            controller.kde.set_dbus_active(dbus is not None)
        app.aboutToQuit.connect(lambda: kde_integration.stop_dbus(dbus))

    # With a paired Echo (or the PC wake listener) Mira keeps listening when her window is closed:
    # the tray brings her back or quits her. Without one there is nothing to listen for, so closing
    # the window ends her like any other app. Started at sign-in without a window, the tray is her
    # way back, so she has one then too.
    tray = None
    background = (paired() or controller.settings.value('local_wake_enabled', False, type=bool)
                  or start_hidden)
    if start_hidden and not TEST_MODE:
        app.setQuitOnLastWindowClosed(False)
        controller.keep_running = True

    def make_tray(attempt=0):
        nonlocal tray
        if not QSystemTrayIcon.isSystemTrayAvailable():
            # At sign-in the shell's tray can arrive a moment after her: look again for a minute.
            if start_hidden and attempt < 30:
                QTimer.singleShot(2000, lambda: make_tray(attempt + 1))
            return
        app.setQuitOnLastWindowClosed(False)
        tray = QSystemTrayIcon(app_icon(), app)
        tray.setToolTip('Mira · ميرا')
        menu = QMenu()
        tray._menu = menu      # the menu lives as long as the icon

        def build_menu():
            menu.clear()
            s = controller.s
            menu.addAction(s['tray_show']).triggered.connect(raise_window)
            menu.addAction(s['talk']).triggered.connect(controller.talk)
            menu.addSeparator()
            menu.addAction(s['tray_quit']).triggered.connect(app.quit)
        build_menu()
        controller.langChanged.connect(build_menu)
        tray.setContextMenu(menu)
        tray.activated.connect(lambda reason: raise_window() if reason == QSystemTrayIcon.Trigger else None)
        tray.show()
        controller.keep_running = True

    if not TEST_MODE and background:
        make_tray()

    if TEST_MODE:
        import review_fakes
        review_fakes.stage(controller, window, option('--scene', 'idle'))
    capture = option('--capture')
    if capture:
        delay = int(option('--capture-delay', '2500'))

        def grab():
            window.grabWindow().save(capture)
            print('Mira capture:', capture, flush=True)
            if '--keep' not in sys.argv:
                app.quit()
        QTimer.singleShot(delay, grab)
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
