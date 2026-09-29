"""Mira Neural OS — desktop entry point, and the MoOS assistant.

A Qt Quick (GPU) interface over the same verified backends: the paired Echo voice satellite,
Gemini, Home Assistant and every Mo AI tool through its own executor. Mira IS Mo AI's app now:
she wears its desktop id and icon (org.moos.moai, one dock icon, Meta+Space) and answers its
launcher (`moai --panel device|apps|compat|remote|dev|chat`, `--ask TEXT`). One window per
user; a second launch raises it on the asked page (or, from the local wake listener, starts a
voice turn).
"""
import json
import math
import os
import re
import struct
import sys
import threading
import wave
from http.server import BaseHTTPRequestHandler, HTTPServer
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

from mira_bridge import IP  # noqa: E402

TEST_MODE = os.environ.get('MIRA_TEST_MODE') == '1'
WAKE_MODELS = Path.home() / '.local/share/mira/wake-models'
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
    """What a launcher asked for — Mo AI's `--panel NAME`, `--device`, `--ask TEXT` — or {}."""
    request = {}
    for i, arg in enumerate(argv):
        if arg in ('--panel', '--ask') and i + 1 < len(argv):
            request[arg[2:]] = argv[i + 1]
        elif arg.startswith(('--panel=', '--ask=')):
            key, value = arg[2:].split('=', 1)
            request[key] = value
        elif arg == '--device':
            request['panel'] = 'device'
        elif arg == '--install-improved-wake':
            request['wake'] = 'improved'     # local only: offers the improved «ميرا» model to the Echo
        elif arg == '--wake-rollback':
            request['wake'] = 'rollback'     # local only: back to the proven «ميرا» model alone
    if 'panel' in request and not re.fullmatch(r'[a-z]{1,16}', request['panel']):
        del request['panel']
    return request


class ToneServer(BaseHTTPRequestHandler):
    """Serves the wake models and a test tone to the paired Echo only."""

    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.client_address[0] != IP:
            self.send_error(403)
            return
        if self.path == '/tone.wav':
            frames = struct.pack('<' + 'h' * 48000,
                                 *[int(16000 * math.sin(2 * math.pi * 440 * i / 48000)) for i in range(48000)])
            self.send_response(200)
            self.send_header('Content-Type', 'audio/wav')
            self.end_headers()
            out = wave.open(self.wfile, 'wb')
            out.setnchannels(1)
            out.setsampwidth(2)
            out.setframerate(48000)
            out.writeframes(frames)
            out.close()
        elif self.path in ('/hey_mira.json', '/hey_mira.tflite'):
            self._send_file(ROOT / self.path.lstrip('/'))
        elif re.fullmatch(r'/announce/[0-9a-f]{12}(\.16k)?\.wav', self.path):
            # A reminder or a finished job, spoken by Gemini TTS (announce.py), for the Echo to play.
            import announce
            self._send_file(announce.CACHE_DIR / self.path.rsplit('/', 1)[1], 'audio/wav')
        elif re.fullmatch(r'/models/[a-z0-9_]{3,40}\.(json|tflite)', self.path):
            # Wake models trained on this PC for the owner's voice; the Echo checks size and SHA-256.
            self._send_file(WAKE_MODELS / self.path.rsplit('/', 1)[1])
        else:
            self.send_error(404)

    def _send_file(self, path, content_type='application/octet-stream'):
        try:
            data = path.read_bytes()
        except OSError:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)


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
    message = b'open:' + json.dumps(request).encode() if request else b'show'

    socket_name = os.environ.get('MIRA_INSTANCE') or f'mo-dot-desktop-{os.getuid()}'
    existing = QLocalSocket()
    existing.connectToServer(socket_name)
    if existing.waitForConnected(300):
        existing.write(message)
        existing.waitForBytesWritten(300)
        return 0
    QLocalServer.removeServer(socket_name)
    instance = QLocalServer()
    instance.setSocketOptions(QLocalServer.UserAccessOption)
    instance.listen(socket_name)

    from mira_bridge import paired
    if not TEST_MODE and paired():   # the model/announcement server exists only for a paired Echo
        server = HTTPServer(('0.0.0.0', 18769), ToneServer)
        threading.Thread(target=server.serve_forever, daemon=True).start()

    from controller import Controller
    from faces import FaceProvider
    bridge_class = None
    if TEST_MODE:
        from review_fakes import FakeBridge
        bridge_class = FakeBridge
    controller = Controller(bridge_class=bridge_class)

    engine = QQmlApplicationEngine()
    engine.addImageProvider('mira', FaceProvider())
    engine.addImageProvider('icon', ThemeIconProvider())
    engine.addImportPath(str(ROOT / 'qml'))
    engine.rootContext().setContextProperty('mira', controller)
    engine.load(QUrl.fromLocalFile(str(ROOT / 'qml' / 'Main.qml')))
    if not engine.rootObjects():
        print('Mira: the interface failed to load', file=sys.stderr, flush=True)
        return 1
    window = engine.rootObjects()[0]
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

    # Mira keeps listening when her window is closed: the tray brings her back or quits her.
    tray = None
    if QSystemTrayIcon.isSystemTrayAvailable() and not TEST_MODE:
        app.setQuitOnLastWindowClosed(False)
        tray = QSystemTrayIcon(app_icon(), app)
        tray.setToolTip('Mira · ميرا')
        menu = QMenu()
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
