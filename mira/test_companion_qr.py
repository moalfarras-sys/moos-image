"""Pairing pixels and controls in the real CompanionPanel, on a private Qt window.

Every child owns its HOME, XDG paths and bus. Its pairing URL/token are synthetic;
no controller, listener, device, owner credential or clipboard is accessed.
Default gates need Qt and Mira's existing segno dependency, not an image decoder.
MIRA_NATIVE_KDE_PROOF=1 requires native KDE Light/Dark palette publication.
MIRA_NATIVE_QR_DECODE=1 additionally requires libzbar and exact payload decoding.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent
OVERLAY = ROOT.parent / 'system_files'


class CompanionQrTest(unittest.TestCase):
    def run_case(self, family, *, old_policy=False, wrong_style=False):
        native = os.environ.get('MIRA_NATIVE_KDE_PROOF') == '1'
        colors = OVERLAY / 'usr/share/color-schemes' / (family + '.colors')
        if not colors.exists():
            colors = Path('/usr/share/color-schemes') / (family + '.colors')
        if native:
            self.assertTrue(colors.is_file(), 'native KDE colour input unavailable')
        with tempfile.TemporaryDirectory(prefix='mira-companion-qr-') as temp:
            base = Path(temp)
            for name in ('home', 'config', 'cache', 'data', 'state', 'run'):
                (base / name).mkdir(mode=0o700)
            (base / 'config/kdeglobals').write_text(colors.read_text() if colors.exists() else '')
            env = os.environ.copy()
            for key in ('DISPLAY', 'WAYLAND_DISPLAY', 'SESSION_MANAGER', 'QT_PLUGIN_PATH',
                        'QT_STYLE_OVERRIDE', 'MIRA_COMPANION_HOST'):
                env.pop(key, None)
            env.update(HOME=str(base / 'home'), XDG_CONFIG_HOME=str(base / 'config'),
                       XDG_CONFIG_DIRS=str(base / 'config'), XDG_DATA_DIRS='/usr/share',
                       XDG_DATA_HOME=str(base / 'data'), XDG_CACHE_HOME=str(base / 'cache'),
                       XDG_STATE_HOME=str(base / 'state'), XDG_RUNTIME_DIR=str(base / 'run'),
                       QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software',
                       QT_QUICK_CONTROLS_STYLE='Basic', QML_DISABLE_DISK_CACHE='1',
                       QT_QPA_PLATFORMTHEME='kde' if native and not wrong_style else 'generic',
                       QML_IMPORT_PATH=str(OVERLAY / 'usr/lib64/qt6/qml'),
                       DBUS_SESSION_BUS_ADDRESS='unix:path=' + str(base / 'run/absent'))
            command = ['dbus-run-session', '--', sys.executable, str(Path(__file__).resolve()),
                       '--probe', family, 'old-policy' if old_policy else 'fixed']
            result = subprocess.run(command, env=env, text=True, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, timeout=25)
            output = result.stdout + result.stderr
            if wrong_style:
                self.assertNotEqual(result.returncode, 0, output)
                self.assertIn('native KDE palette unavailable', output)
            elif old_policy:
                self.assertNotEqual(result.returncode, 0, output)
                self.assertIn('QR module is not black', output)
            else:
                self.assertEqual(result.returncode, 0, output)
                self.assertIn('MIRA_COMPANION_QR_PASS', result.stdout)

    def test_light_pixels_hidden_expiry_and_two_click_rotation(self):
        self.run_case('MoOSUI2AuroraLight')

    def test_dark_pixels_hidden_expiry_and_two_click_rotation(self):
        self.run_case('MoOSUI2Aurora')

    def test_light_rejects_old_palette_coloured_modules(self):
        self.run_case('MoOSUI2AuroraLight', old_policy=True)

    if os.environ.get('MIRA_NATIVE_KDE_PROOF') == '1':
        def test_generic_style_is_not_native_kde_palette_acceptance(self):
            self.run_case('MoOSUI2AuroraLight', wrong_style=True)


def decode_qr(image):
    """Optional installed decoder; never install a provider or write a QR image."""
    import ctypes
    from PySide6.QtGui import QImage

    library = ctypes.CDLL('libzbar.so.0')
    library.zbar_image_scanner_create.restype = ctypes.c_void_p
    library.zbar_image_create.restype = ctypes.c_void_p
    signatures = {
        'zbar_image_scanner_set_config': [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int],
        'zbar_image_set_format': [ctypes.c_void_p, ctypes.c_ulong],
        'zbar_image_set_size': [ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint],
        'zbar_image_set_data': [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong, ctypes.c_void_p],
        'zbar_scan_image': [ctypes.c_void_p, ctypes.c_void_p],
        'zbar_image_first_symbol': [ctypes.c_void_p],
        'zbar_symbol_get_data': [ctypes.c_void_p],
        'zbar_image_destroy': [ctypes.c_void_p],
        'zbar_image_scanner_destroy': [ctypes.c_void_p],
    }
    for name, arguments in signatures.items():
        getattr(library, name).argtypes = arguments
    library.zbar_image_first_symbol.restype = ctypes.c_void_p
    library.zbar_symbol_get_data.restype = ctypes.c_char_p
    gray = image.convertToFormat(QImage.Format_Grayscale8)
    raw = b''.join(bytes(gray.constBits()[row * gray.bytesPerLine():
                                         row * gray.bytesPerLine() + gray.width()])
                   for row in range(gray.height()))
    buffer = ctypes.create_string_buffer(raw)
    scanner, frame = library.zbar_image_scanner_create(), library.zbar_image_create()
    assert scanner and frame, 'native QR decoder allocation failed'
    try:
        library.zbar_image_scanner_set_config(scanner, 0, 0, 1)
        library.zbar_image_set_format(frame, int.from_bytes(b'Y800', 'little'))
        library.zbar_image_set_size(frame, gray.width(), gray.height())
        library.zbar_image_set_data(frame, buffer, len(raw), None)
        library.zbar_scan_image(scanner, frame)
        symbol = library.zbar_image_first_symbol(frame)
        return library.zbar_symbol_get_data(symbol).decode() if symbol else None
    finally:
        library.zbar_image_destroy(frame)
        library.zbar_image_scanner_destroy(scanner)


def probe(family, policy):
    import configparser
    import time
    from PySide6.QtCore import QObject, Property, QPoint, QPointF, Qt, QUrl, Slot, qInstallMessageHandler
    from PySide6.QtGui import QColor, QImage, QPalette
    from PySide6.QtWidgets import QApplication
    from PySide6.QtQml import QQmlComponent
    from PySide6.QtQuick import QQuickItem, QQuickView
    from PySide6.QtTest import QTest
    from companion.adapter import panel_text, qr_code

    url = 'http://100.64.0.123:18770/pair?token=' + 'QR-fixture_NotAnOwnerSecret_0123456789abcdefghi'
    qr = qr_code(url)
    assert qr and qr['runs'], 'Mira QR generation unavailable'

    class FakeCompanion(QObject):
        rotations = 0

        @Slot()
        def rotateCompanionCode(self):
            self.rotations += 1

        @Slot(bool)
        def setCompanionEnabled(self, enabled):
            pass

        @Property('QVariantMap', constant=True)
        def companion(self):
            return {'enabled': True, 'state': 'running', 'url': url, 'qr': qr,
                    'text': panel_text('en'), 'label': 'Private QR fixture',
                    'address': '100.64.0.123:18770', 'phones': '0 phones'}

    app = QApplication([])
    app.setApplicationName('MiraCompanionQrPrivateProof')
    app.setOrganizationName('MoOSPrivateReview')
    if os.environ.get('MIRA_NATIVE_KDE_PROOF') == '1':
        colors = configparser.ConfigParser(interpolation=None, strict=False)
        colors.read(Path(os.environ['XDG_CONFIG_HOME']) / 'kdeglobals')
        rgb = [int(v) for v in colors['Colors:Window']['BackgroundNormal'].split(',')]
        assert app.palette().window().color() == QColor(*rgb), 'native KDE palette unavailable'
    else:
        palette = QPalette(app.palette())
        palette.setColor(QPalette.Window, QColor('#c3d5e5' if family.endswith('Light') else '#192436'))
        app.setPalette(palette)
    messages = []
    old_handler = qInstallMessageHandler(lambda kind, context, text: messages.append(text))
    view = QQuickView()
    view.engine().addImportPath(str(ROOT / 'qml'))
    fake = FakeCompanion()
    view.rootContext().setContextProperty('mira', fake)
    view.rootContext().setContextProperty('miraApplication', app)
    source_path = ROOT / 'qml/Mira/CompanionPanel.qml'
    source = source_path.read_bytes()
    if policy == 'old-policy':
        assert source.count(b'color: "black"') == 1, 'old policy control location changed'
        source = source.replace(b'color: "black"', b'color: Theme.bg0')
    component = QQmlComponent(view.engine())
    component.setData(source, QUrl.fromLocalFile(str(source_path)))
    assert not component.isError(), str(component.errors())
    root = component.create()
    assert root is not None, str(component.errors())
    view.setContent(QUrl.fromLocalFile(str(source_path)), component, root)
    view.setResizeMode(QQuickView.SizeRootObjectToView)
    view.resize(460, 1200)
    view.show()

    def settle(seconds=.13):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            app.processEvents()
            time.sleep(.003)

    settle()
    box = next(item for item in root.findChildren(QQuickItem) if item.property('n') == qr['size'])
    assert not root.property('revealed') and not box.isVisible(), 'QR revealed without request'
    root.setProperty('revealed', True)
    settle()
    assert box.isVisible(), 'requested QR is hidden'
    capture = box.grabToImage()
    assert capture is not None, 'QR item grab failed'
    settle()
    image = capture.image()
    assert not image.isNull(), 'QR image did not paint'
    cell, offset = int(box.property('cell')), int(box.property('offset'))
    assert cell > 0 and offset >= 4 * cell, 'QR lacks an integer grid or four-module quiet zone'
    dark = {(x, y) for start, y, length in qr['runs'] for x in range(start, start + length)}
    for y in range(qr['size']):
        for x in range(qr['size']):
            actual = image.pixelColor(offset + x * cell + cell // 2, offset + y * cell + cell // 2)
            if (x, y) in dark:
                assert actual == QColor('black'), 'QR module is not black: ' + actual.name()
            else:
                assert actual == QColor('white'), 'QR light module is not white'
    middle = offset + qr['size'] * cell // 2
    for border in (offset - 4 * cell + 1, offset + (qr['size'] + 4) * cell - 1):
        assert image.pixelColor(border, middle) == QColor('white'), 'QR quiet zone is not white'
        assert image.pixelColor(middle, border) == QColor('white'), 'QR quiet zone is not white'
    if os.environ.get('MIRA_NATIVE_QR_DECODE') == '1':
        assert decode_qr(image) == url, 'native decoder returned a different pairing payload'
        blank = QImage(image)
        blank.fill(QColor('white'))
        assert decode_qr(blank) is None, 'native decoder accepted a blank negative'
    root.setProperty('revealed', False)
    settle()
    assert not box.isVisible(), 'hidden QR still paints'
    hide = next(item for item in root.findChildren(QObject) if item.property('interval') == 120000)
    disarm = next(item for item in root.findChildren(QObject) if item.property('interval') == 5000)
    # Verify the production intervals, then accelerate only these private objects.
    hide.setProperty('interval', 30)
    root.setProperty('revealed', True)
    settle()
    assert not root.property('revealed') and not box.isVisible(), 'QR expiry failed'
    rotate = next(item for item in root.findChildren(QQuickItem)
                  if item.property('text') == panel_text('en')['rotate']
                  and item.metaObject().indexOfSignal('clicked()') >= 0)

    def click():
        at = rotate.mapToScene(QPointF(rotate.width() / 2, rotate.height() / 2))
        QTest.mouseClick(view, Qt.LeftButton, Qt.NoModifier, QPoint(round(at.x()), round(at.y())))
        app.processEvents()

    click()
    assert root.property('armed') and fake.rotations == 0, 'first click rotated pairing token'
    click()
    assert not root.property('armed') and fake.rotations == 1, 'confirmed rotation did not route once'
    click()
    assert root.property('armed'), 'rotation did not arm'
    disarm.setProperty('interval', 30)
    settle()
    assert not root.property('armed') and fake.rotations == 1, 'expired rotation still armed'
    errors = ('ReferenceError', 'TypeError', 'Unable to assign', 'Cannot assign', 'is not defined')
    assert not [line for line in messages if any(error in line for error in errors)], str(messages)
    view.close()
    view.setSource(QUrl())
    app.processEvents()
    qInstallMessageHandler(old_handler)
    print('MIRA_COMPANION_QR_PASS:', family, 'black/white hidden expiry two-click rotation',
          'decoded' if os.environ.get('MIRA_NATIVE_QR_DECODE') == '1' else 'pixels')


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--probe':
        probe(sys.argv[2], sys.argv[3])
    else:
        unittest.main()
