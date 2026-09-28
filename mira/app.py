"""Mira Neural OS — desktop entry point.

A Qt Quick (GPU) interface over the same verified backends: the paired Echo voice satellite,
Gemini, Home Assistant and Mo AI's fixed executor. One window per user; a second launch raises
it (or, from the local wake listener, starts a voice turn).
"""
import math
import os
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
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon  # noqa: E402
from PySide6.QtNetwork import QLocalServer, QLocalSocket  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402

from mira_bridge import IP  # noqa: E402

TEST_MODE = os.environ.get('MIRA_TEST_MODE') == '1'


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
            data = (ROOT / self.path.lstrip('/')).read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', 'application/octet-stream')
            self.end_headers()
            self.wfile.write(data)
        else:
            self.send_error(404)


def option(name, default=None):
    for arg in sys.argv:
        if arg.startswith(name + '='):
            return arg.split('=', 1)[1]
    return default


def main():
    app = QApplication(sys.argv)
    app.setApplicationName('Mira')
    app.setOrganizationName('MoOS')
    app.setDesktopFileName('mira')
    app.setWindowIcon(QIcon(str(ROOT / 'mira-icon-v2.png')))

    socket_name = os.environ.get('MIRA_INSTANCE') or f'mo-dot-desktop-{os.getuid()}'
    existing = QLocalSocket()
    existing.connectToServer(socket_name)
    if existing.waitForConnected(300):
        existing.write(b'show')
        existing.waitForBytesWritten(300)
        return 0
    QLocalServer.removeServer(socket_name)
    instance = QLocalServer()
    instance.setSocketOptions(QLocalServer.UserAccessOption)
    instance.listen(socket_name)

    if not TEST_MODE:
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
    engine.addImportPath(str(ROOT / 'qml'))
    engine.rootContext().setContextProperty('mira', controller)
    engine.load(QUrl.fromLocalFile(str(ROOT / 'qml' / 'Main.qml')))
    if not engine.rootObjects():
        print('Mira: the interface failed to load', file=sys.stderr, flush=True)
        return 1
    window = engine.rootObjects()[0]
    controller.start()

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
        tray = QSystemTrayIcon(QIcon(str(ROOT / 'mira-icon-v2.png')), app)
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
