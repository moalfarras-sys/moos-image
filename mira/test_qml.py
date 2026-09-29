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

import i18n
import pages  # noqa: E402
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


_controller = []
_offline = []


def setUpModule():
    """No test here may reach the owner's live moai-control (127.0.0.1:8079): the pages' reads and
    the controller's health check answer 'unreachable', the same as on a machine without it."""
    from unittest import mock
    import moai_tools
    stub = mock.patch.object(moai_tools, '_request',
                             lambda *a, **k: (0, {'error': 'moai_control_unreachable', 'detail': 'test'}))
    stub.start()
    _offline.append(stub)


def tearDownModule():
    while _offline:
        _offline.pop().stop()


def controller_pages():
    """One controller (stand-in bridge) whose page objects the route gate can inspect."""
    if not _controller:
        _controller.append(Controller(bridge_class=FakeBridge))
    return _controller[0]


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
            text = re.sub(r'(?m)^\s*//.*$', '', path.read_text())      # comments are not buttons
            called |= set(re.findall(r'\bmira\.(\w+)\s*\(', text))
            read |= set(re.findall(r'\bmira\.(\w+)\b(?!\s*\()', text))
            strings |= set(re.findall(r'\bmira\.s\.(\w+)', text))
        self.assertTrue(called, 'no routes found — the scan is broken')
        self.assertEqual(sorted(called - slots), [], 'buttons call routes the controller does not implement')
        self.assertEqual(sorted(read - props - slots), [], 'bindings read properties the controller does not expose')
        words = i18n.table('ar')
        missing = sorted(k for k in strings if k not in words)
        self.assertEqual(missing, [], 'interface text keys missing from i18n (or a page module\'s STRINGS)')
        # Each page's QML calls slots of its own page object (mira.<name>Page.<slot>(...)).
        for name, prop in pages.PAGES:
            page = getattr(controller_pages(), prop, None)
            if page is None:
                continue
            page_meta = page.metaObject()
            page_slots = {bytes(page_meta.method(i).name().data()).decode() for i in range(page_meta.methodCount())}
            used = set()
            for path in QML:
                used |= set(re.findall(r'\bmira\.' + prop + r'\.(\w+)\s*\(', path.read_text()))
            self.assertEqual(sorted(used - page_slots), [], f'{prop}: buttons call slots the page does not implement')

    def test_cards_stand_clear_of_the_conversation_and_the_composer(self):
        """Owner cards over the stage sit between the context rail and the conversation, never over
        either; they stay above the composer however far it grows; the stage caption does not show
        through their gaps; and beside an open page they still stay above the composer."""
        from PySide6.QtCore import QPointF, QRectF
        from PySide6.QtQuick import QQuickItem
        import inbox
        messages = Messages()
        previous = qInstallMessageHandler(messages)
        try:
            controller = Controller(bridge_class=FakeBridge)
            engine = QQmlApplicationEngine()
            engine.addImageProvider('mira', FaceProvider())
            engine.addImportPath(str(ROOT / 'qml'))
            engine.rootContext().setContextProperty('mira', controller)
            engine.load(QUrl.fromLocalFile(str(ROOT / 'qml' / 'Main.qml')))
            window = engine.rootObjects()[0]
            window.setWidth(1480)
            window.setHeight(920)

            def settle(seconds=0.4):
                end = time.monotonic() + seconds
                while time.monotonic() < end:
                    QCoreApplication.processEvents()
                    time.sleep(0.01)

            def shown(name):
                items = [i for i in window.findChildren(QQuickItem, name) if i.isVisible()]
                self.assertTrue(items, name)
                return items[0]

            def rect(item):
                at = item.mapToScene(QPointF(0, 0))
                return QRectF(at.x(), at.y(), item.width(), item.height())

            controller.actions.set_rows([inbox.card(item, controller._s) for item in inbox.review_items()]
                                        + [{'aid': 'p-test', 'kind': 'moai', 'name': 'install_app', 'title': 'Install',
                                            'detail': 'VLC', 'reason': '', 'stage': 'ask', 'category': 'user_confirm',
                                            'summary': '', 'output': '', 'started': 0, 'expires': 0, 'origin': 'mira'}])
            field = shown('composer')
            for lines in (1, 5):
                field.setProperty('text', '\n'.join('line %d' % n for n in range(lines)))
                settle()
                cards, bar = rect(shown('actionCards')), rect(shown('composerBar'))
                self.assertLessEqual(cards.bottom(), bar.top() - 11, f'a card covers a {lines}-line composer')
                self.assertGreaterEqual(cards.top(), rect(window.findChild(QQuickItem, 'conversationPanel')).top() - 1)
                for name in ('conversationPanel', 'contextRail'):
                    self.assertFalse(cards.intersects(rect(shown(name))), f'a card covers the {name}')
                self.assertFalse(window.findChild(QQuickItem, 'stageCaption').isVisible(),
                                 'the stage caption shows through the cards')
            self.assertFalse(shown('actionCards').property('overText'), 'on the stage the cards stay glass')

            def lines():                        # ListView delegates live in the visual tree only
                found, todo = [], [window.contentItem()]
                while todo:
                    item = todo.pop()
                    if item.objectName() == 'answerLine' and item.isVisible():
                        found.append(item)
                    todo.extend(item.childItems())
                return found
            self.assertEqual(lines(), [], 'a wide card moved its answers off its line')
            window.setProperty('sheet', 'system')
            settle()
            cards, bar = rect(shown('actionCards')), rect(shown('composerBar'))
            self.assertLessEqual(cards.bottom(), bar.top() - 11, 'beside a page, a card covers the composer')
            # over the conversation's words: solid cards, and the narrow card answers on its own line
            self.assertTrue(shown('actionCards').property('overText'), 'the chat reads through the cards')
            controller.actions.set_rows([row for row in controller.actions.rows() if row['aid'] == 'p-test'])
            settle()
            cards = rect(shown('actionCards'))
            found = lines()
            self.assertEqual(len(found), 1, 'the narrow card lost its answers')
            self.assertLessEqual(rect(found[0]).right(), cards.right() + 1)
            self.assertGreaterEqual(rect(found[0]).left(), cards.left() - 1)
            window.setProperty('sheet', '')
            controller.actions.set_rows([])
            settle()
            self.assertTrue(window.findChild(QQuickItem, 'stageCaption').isVisible(), 'the caption never comes back')
            engine.deleteLater()
            settle(0.1)
        finally:
            qInstallMessageHandler(previous)
        self.assertEqual(messages.fatal(), [])

    def test_escape_in_a_task_field_keeps_the_page_and_the_words(self):
        """Escape while typing a Workbench task leaves the field and keeps every word; only an Escape
        from outside a field with words closes the page, as the terminal line already did."""
        from PySide6.QtQuick import QQuickItem
        from PySide6.QtTest import QTest
        from PySide6.QtCore import Qt
        messages = Messages()
        previous = qInstallMessageHandler(messages)
        try:
            controller = Controller(bridge_class=FakeBridge)
            page = getattr(controller, 'workbenchPage', None)
            self.assertIsNotNone(page, 'the controller has no Workbench page')
            engine = QQmlApplicationEngine()
            engine.addImageProvider('mira', FaceProvider())
            engine.addImportPath(str(ROOT / 'qml'))
            engine.rootContext().setContextProperty('mira', controller)
            engine.load(QUrl.fromLocalFile(str(ROOT / 'qml' / 'Main.qml')))
            window = engine.rootObjects()[0]
            window.requestActivate()

            def settle(seconds=0.4):
                end = time.monotonic() + seconds
                while time.monotonic() < end:
                    QCoreApplication.processEvents()
                    time.sleep(0.01)
            window.setProperty('sheet', 'workbench')
            settle()
            page.setTab('tasks')
            settle()
            for name in ('taskTitle', 'taskDetails'):
                window.setProperty('sheet', 'workbench')
                settle(0.2)
                field = next(i for i in window.findChildren(QQuickItem, name) if i.isVisible())
                field.forceActiveFocus()
                field.setProperty('text', 'build the thing')
                settle(0.1)
                self.assertTrue(field.hasActiveFocus(), name)
                QTest.keyClick(window, Qt.Key_Escape)
                settle(0.1)
                self.assertEqual(window.property('sheet'), 'workbench', f'Escape in {name} closed the page')
                self.assertEqual(field.property('text'), 'build the thing', f'Escape in {name} lost the words')
                self.assertFalse(field.hasActiveFocus(), f'Escape did not leave {name}')
                QTest.keyClick(window, Qt.Key_Escape)
                settle(0.1)
                self.assertEqual(window.property('sheet'), '', 'the next Escape no longer closes the page')
            engine.deleteLater()
            settle(0.1)
        finally:
            qInstallMessageHandler(previous)
        self.assertEqual(messages.fatal(), [])

    def test_every_module_type_instantiates(self):
        """Every type the Mira module declares is created once, whether a page uses it yet or not: a
        broken shared component (Tile once redeclared AbstractButton's FINAL `icon`) fails here,
        not on the day a page first adopts it and the whole window stops loading."""
        types, singletons = [], []
        for line in (ROOT / 'qml' / 'Mira' / 'qmldir').read_text().splitlines():
            parts = line.split()
            if len(parts) == 4 and parts[0] == 'singleton':
                singletons.append(parts[1])
            elif len(parts) == 3 and parts[2].endswith('.qml'):
                types.append((parts[0], parts[2]))
        self.assertIn(('Tile', 'Tile.qml'), types, 'the qmldir scan is broken')
        self.assertIn('Theme', singletons, 'the qmldir scan is broken')
        engine = self._probe_engine()
        failures = {}
        for name, file in types:
            text = (ROOT / 'qml' / 'Mira' / file).read_text()
            # a delegate's required roles get neutral values, as a model row would give them
            required = re.findall(r'(?m)^    required property (\w+) (\w+)', text)
            neutral = {'string': '""', 'int': '0', 'real': '0', 'double': '0', 'bool': 'false'}
            props = ''.join(f'; {prop}: {neutral.get(kind, "null")}' for kind, prop in required)
            problems = self._instantiate(engine, name, f'{name} {{ width: 900; height: 700{props} }}')
            if problems:
                failures[name] = problems
        for name in singletons:
            problems = self._instantiate(engine, name, f'Item {{ property var probe: {name} }}')
            if problems:
                failures[name] = problems
        engine.deleteLater()
        self.assertEqual(failures, {}, 'module types that cannot be created')

    def test_the_type_probe_bites(self):
        # The exact mistake Tile shipped: a property that overrides AbstractButton's FINAL `icon`.
        engine = self._probe_engine()
        broken = self._instantiate(engine, 'broken', 'AbstractButton { property string icon: "sparkle" }')
        missing = self._instantiate(engine, 'missing', 'NoSuchMiraType {}')
        engine.deleteLater()
        self.assertTrue(broken, 'a FINAL override was not caught')
        self.assertTrue(missing, 'an unknown type was not caught')

    def test_an_icon_outside_a_clip_is_not_drawn(self):
        """Qt Quick's software scene graph (ARM, machines without a GPU) once drew a Shape icon that
        had scrolled out of a page over the dock. An Icon below a clipping Flickable must leave the
        window there untouched, and the Icon inside it must still be drawn."""
        from PySide6.QtQml import QQmlComponent
        from PySide6.QtQuick import QSGRendererInterface
        engine = self._probe_engine()
        source = (b'import QtQuick\nimport Mira\n'
                  b'Window { width: 200; height: 200; visible: true; color: "black"\n'
                  b'    Flickable { width: 200; height: 100; clip: true; contentHeight: 400\n'
                  b'        Column { spacing: 0\n'
                  b'            Icon { name: "chat"; size: 40; color: "white" }\n'
                  b'            Item { width: 1; height: 90 }\n'
                  b'            Icon { name: "chat"; size: 40; color: "white" } } } }\n')
        component = QQmlComponent(engine)
        component.setData(source, QUrl.fromLocalFile(str(ROOT / 'qml' / 'probe-clip.qml')))
        window = component.create()
        self.assertIsNotNone(window, [e.toString() for e in component.errors()])
        try:
            if window.rendererInterface().graphicsApi() != QSGRendererInterface.GraphicsApi.Software:
                self.skipTest('not the software scene graph')
            end = time.monotonic() + 0.6
            while time.monotonic() < end:
                QCoreApplication.processEvents()
                time.sleep(0.01)
            image = window.grabWindow()
            scale = image.devicePixelRatio()

            def lit(top, bottom):
                return sum(1 for y in range(int(top * scale), int(bottom * scale))
                           for x in range(0, int(60 * scale)) if image.pixelColor(x, y).lightness() > 60)
            self.assertGreater(lit(0, 40), 20, 'the icon inside the clip is not drawn at all')
            self.assertEqual(lit(104, 200), 0, 'an icon outside the clip was drawn')
        finally:
            window.deleteLater()
            engine.deleteLater()
            QCoreApplication.processEvents()

    def _probe_engine(self):
        from PySide6.QtQml import QQmlEngine
        engine = QQmlEngine()
        engine.addImageProvider('mira', FaceProvider())
        engine.addImportPath(str(ROOT / 'qml'))
        engine.rootContext().setContextProperty('mira', controller_pages())
        return engine

    def _instantiate(self, engine, name, body):
        """Create `body` once inside a hidden window; every error and fatal warning it caused."""
        from PySide6.QtQml import QQmlComponent
        source = ('import QtQuick\nimport QtQuick.Window\nimport QtQuick.Controls.Basic\nimport Mira\n'
                  f'Window {{ width: 1000; height: 800; visible: false\n    {body}\n}}\n')
        messages = Messages()
        previous = qInstallMessageHandler(messages)
        try:
            component = QQmlComponent(engine)
            component.setData(source.encode(), QUrl.fromLocalFile(str(ROOT / 'qml' / f'probe-{name}.qml')))
            created = component.create()
            errors = [error.toString() for error in component.errors()]
            end = time.monotonic() + 0.15
            while time.monotonic() < end:
                QCoreApplication.processEvents()
                time.sleep(0.01)
            if created is not None:
                created.deleteLater()
                QCoreApplication.processEvents()
        finally:
            qInstallMessageHandler(previous)
        if created is None and not errors:
            errors = ['not created']
        return errors + messages.fatal()

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
            for sheet in ('home', 'pc', 'apps', 'system', 'workbench', 'connect', 'brain', 'settings', ''):
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
