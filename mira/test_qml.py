"""Mira's interface loads, every button reaches a real route, and every string exists.

Three gates, in the spirit of MoOS's own: a QML file that fails to load is a broken app; a call to
`mira.<slot>` that the controller does not implement is a dead button; a `mira.s.<key>` that the
string table does not define is blank text.
"""
import os
import re
import tempfile
import time
import unittest
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_QUICK_BACKEND', 'software')
os.environ['MIRA_TEST_MODE'] = '1'
os.environ.setdefault('QT_QUICK_CONTROLS_STYLE', 'Basic')
_config = tempfile.TemporaryDirectory(prefix='mira-qml-test-')
os.environ['XDG_CONFIG_HOME'] = _config.name

from PySide6.QtCore import QCoreApplication, QMetaMethod, QSettings, QUrl, qInstallMessageHandler  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402

import i18n  # noqa: E402
from controller import Controller  # noqa: E402
from faces import EXPRESSIONS, FaceLibrary, FaceProvider  # noqa: E402
from review_fakes import FakeBridge  # noqa: E402

ROOT = Path(__file__).resolve().parent
QML = sorted((ROOT / 'qml').rglob('*.qml'))
APP = QGuiApplication.instance() or QGuiApplication([])
QSettings.setDefaultFormat(QSettings.IniFormat)
QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, _config.name)
FATAL = ('ReferenceError', 'TypeError', 'is not a type', 'Cannot assign', 'Unable to assign',
         'failed to load', 'is not defined', 'Cannot override', 'Type ', 'unavailable', 'Non-existent')
# The software backend cannot run ShaderEffect; that is expected here and proven on the GPU elsewhere.
IGNORED = ('ShaderEffect', 'shader', 'QRhi', 'rhi', 'qsb')


class Messages:
    def __init__(self):
        self.lines = []

    def __call__(self, mode, context, message):
        if not any(word in message for word in IGNORED):
            self.lines.append(message)

    def fatal(self):
        return [line for line in self.lines if any(word in line for word in FATAL)]


class QmlTest(unittest.TestCase):
    def test_every_route_exists(self):
        slots = set()
        meta = Controller.staticMetaObject
        for i in range(meta.methodCount()):
            method = meta.method(i)
            if method.methodType() in (QMetaMethod.Slot, QMetaMethod.Method):
                slots.add(bytes(method.name().data()).decode() if hasattr(method.name(), 'data') else str(method.name()))
        props = {str(meta.property(i).name()) for i in range(meta.propertyCount())}
        called, read, strings = set(), set(), set()
        for path in QML:
            text = path.read_text()
            called |= set(re.findall(r'\bmira\.(\w+)\s*\(', text))
            read |= set(re.findall(r'\bmira\.(\w+)\b(?!\s*\()', text))
            strings |= set(re.findall(r'\bmira\.s\.(\w+)', text))
        self.assertTrue(called, 'no routes found — the scan is broken')
        self.assertEqual(sorted(called - slots), [], 'buttons call routes the controller does not implement')
        self.assertEqual(sorted(read - props - slots), [], 'bindings read properties the controller does not expose')
        missing = sorted(k for k in strings if k not in i18n.STRINGS)
        self.assertEqual(missing, [], 'interface text keys missing from i18n.STRINGS')

    def test_the_route_gate_bites(self):
        text = 'onClicked: mira.launchMissiles()'
        self.assertEqual(re.findall(r'\bmira\.(\w+)\s*\(', text), ['launchMissiles'])
        self.assertFalse(hasattr(Controller, 'launchMissiles'))

    def test_both_faces_cover_every_expression(self):
        library = FaceLibrary()
        for style in ('rose', 'holo'):
            for name in EXPRESSIONS:
                image = library.portrait(style, name, 256)
                self.assertFalse(image.isNull(), (style, name))
                self.assertEqual((image.width(), image.height()), (256, 256))
                # the face is in the middle of the portrait, not transparent padding
                self.assertGreater(image.pixelColor(128, 110).alpha(), 200, (style, name))

    def test_interface_loads_and_every_surface_opens(self):
        messages = Messages()
        previous = qInstallMessageHandler(messages)
        try:
            controller = Controller(bridge_class=FakeBridge)
            engine = QQmlApplicationEngine()
            engine.addImageProvider('mira', FaceProvider())
            engine.addImportPath(str(ROOT / 'qml'))
            engine.rootContext().setContextProperty('mira', controller)
            engine.load(QUrl.fromLocalFile(str(ROOT / 'qml' / 'Main.qml')))
            self.assertTrue(engine.rootObjects(), messages.lines)
            window = engine.rootObjects()[0]
            controller.start()
            import review_fakes
            review_fakes.stage(controller, window, 'idle')

            def settle(seconds=0.35):
                end = time.monotonic() + seconds
                while time.monotonic() < end:
                    QCoreApplication.processEvents()
                    time.sleep(0.01)
            settle()
            for sheet in ('home', 'computer', 'settings', ''):
                window.setProperty('sheet', sheet)
                settle()
            for lang in ('en', 'ar'):
                controller.setLang(lang)
                settle(0.1)
            controller.toggleFace()
            for kind in ('listening', 'thinking', 'executing', 'speaking', 'ready', 'off', 'ready'):
                controller._on_voice(kind, '')
                settle(0.05)
            controller._on_voice('error', 'اختبار')
            for width in (1600, 1000, 600):
                window.setWidth(width)
                settle(0.1)
            engine.deleteLater()
            settle(0.1)
        finally:
            qInstallMessageHandler(previous)
        self.assertEqual(messages.fatal(), [])


if __name__ == '__main__':
    unittest.main()
