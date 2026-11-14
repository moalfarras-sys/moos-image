"""Paint populated Mira components, including the old dark-canvas refusals.

The subprocess has private configuration, runtime and D-Bus; its controller uses
review data and cannot contact moai-control. Contrast comes from actual QML ink
over a captured background, not a duplicate token formula. Native KDE mode also
requires the installed platform theme to supply the declared source palette.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent
OVERLAY = ROOT.parent / 'system_files'


class NativeReadingStates(unittest.TestCase):
    def run_palette(self, light):
        family = 'MoOSUI2Aurora' + ('Light' if light else '')
        colors = OVERLAY / 'usr/share/color-schemes' / (family + '.colors')
        if not colors.exists():
            colors = Path('/usr/share/color-schemes') / (family + '.colors')
        native = os.environ.get('MIRA_NATIVE_KDE_PROOF') == '1'
        if native:
            self.assertTrue(colors.exists(), 'native source palette unavailable')
        with tempfile.TemporaryDirectory(prefix='mira-reading-states-') as temporary:
            base = Path(temporary)
            for part in ('home', 'config', 'cache', 'data', 'state', 'run'):
                (base / part).mkdir(mode=0o700)
            (base / 'config/kdeglobals').write_text(
                (colors.read_text() if colors.exists() else '') +
                '\n[KDE]\nAnimationDurationFactor=1\n')
            env = os.environ.copy()
            for key in ('DISPLAY', 'WAYLAND_DISPLAY', 'SESSION_MANAGER', 'QT_PLUGIN_PATH',
                        'QT_STYLE_OVERRIDE', 'DBUS_SESSION_BUS_ADDRESS'):
                env.pop(key, None)
            env.update(HOME=str(base/'home'), XDG_CONFIG_HOME=str(base/'config'),
                       XDG_CONFIG_DIRS=str(base/'config'), XDG_DATA_HOME=str(base/'data'),
                       XDG_CACHE_HOME=str(base/'cache'), XDG_STATE_HOME=str(base/'state'),
                       XDG_RUNTIME_DIR=str(base/'run'), QT_QPA_PLATFORM='offscreen',
                       QT_QPA_PLATFORMTHEME='kde' if native else 'generic',
                       QT_QUICK_BACKEND='software', QT_QUICK_CONTROLS_STYLE='Basic',
                       QML_DISABLE_DISK_CACHE='1', MIRA_TEST_MODE='1',
                       QML_IMPORT_PATH=str(OVERLAY/'usr/lib64/qt6/qml'))
            result = subprocess.run(['dbus-run-session', '--', sys.executable, str(Path(__file__).resolve()),
                                     '--probe', family], env=env, text=True, capture_output=True, timeout=90)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('MIRA_READING_STATES_PASS', result.stdout)
            print(result.stdout.strip(), flush=True)
            if light:
                self.assertIn('old_dark_approval_refused', result.stdout)
                self.assertIn('old_dark_output_refused', result.stdout)

    def test_light_populated_reading_and_motion(self):
        self.run_palette(True)

    def test_dark_populated_reading_and_motion(self):
        self.run_palette(False)


def probe(family):
    import configparser
    import json
    import time
    from unittest.mock import patch
    from PySide6.QtCore import QObject, QPointF, QCoreApplication, QUrl, qInstallMessageHandler
    from PySide6.QtGui import QColor, QFont, QPalette
    from PySide6.QtQml import QQmlApplicationEngine, QQmlComponent
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtWidgets import QApplication
    from controller import Controller
    from faces import FaceProvider
    from review_fakes import FakeBridge, SAMPLE_DEVICES
    import moai_tools

    app = QApplication([])
    app.setApplicationName('MiraPrivateReadingProof')
    app.setOrganizationName('MoOSPrivateReview')
    light = family.endswith('Light')
    if os.environ.get('MIRA_NATIVE_KDE_PROOF') == '1':
        config = configparser.ConfigParser(interpolation=None, strict=False)
        config.read(Path(os.environ['XDG_CONFIG_HOME'])/'kdeglobals')
        rgb = [int(v) for v in config['Colors:Window']['BackgroundNormal'].split(',')]
        assert app.palette().window().color() == QColor(*rgb), 'native palette owner mismatch'
    else:
        # The portable mode drives explicit Qt palette events. Native KDE mode
        # above separately requires the platform to read the source scheme.
        palette = QPalette(app.palette())
        for role, color in ((QPalette.Window, '#c3d5e5' if light else '#192436'),
                            (QPalette.Base, '#cad9e9' if light else '#101723'),
                            (QPalette.AlternateBase, '#cedceb' if light else '#192436'),
                            (QPalette.WindowText, '#14283f' if light else '#edf3fc'),
                            (QPalette.Text, '#14283f' if light else '#edf3fc'),
                            (QPalette.Highlight, '#1647b9' if light else '#20d6f8'),
                            (QPalette.HighlightedText, '#f7fbff' if light else '#101723')):
            palette.setColor(role, QColor(color))
        app.setPalette(palette)
    messages = []
    previous = qInstallMessageHandler(lambda kind, context, text: messages.append(text))
    checks, negatives, old_contrasts, motion_counts = {}, [], {}, []

    def settle(seconds=.08):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            QCoreApplication.processEvents()
            time.sleep(.003)

    def visual_items(root):
        todo = [root]
        while todo:
            item = todo.pop()
            yield item
            todo.extend(item.childItems())

    def rgb(color):
        return color.redF(), color.greenF(), color.blueF()

    def luminance(color):
        return sum(weight * (v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4)
                   for v, weight in zip(color, (.2126, .7152, .0722)))

    def ratio(ink, background):
        a, b = luminance(ink), luminance(background)
        return (max(a, b) + .05) / (min(a, b) + .05)

    with patch.object(moai_tools, '_request', return_value=(0, {'error': 'private-review'})):
        controller = Controller(bridge_class=FakeBridge)
        controller.setLang('en')
        controller._motion = True
        engine = QQmlApplicationEngine()
        engine.setProperty('_kirigamiTheme', 'org.kde.desktop')
        engine.addImageProvider('mira', FaceProvider())
        engine.addImportPath(str(ROOT/'qml'))
        engine.rootContext().setContextProperty('mira', controller)
        engine.rootContext().setContextProperty('miraApplication', app)
        component = QQmlComponent(engine)
        component.setData('''import QtQuick
import QtQuick.Window
import QtQuick.Layouts
import Mira
import org.moos.ui as MoUI
Window {
 id: win; width: 1000; height: 850; visible: true; color: Theme.bg0
 property string scene: "output"
 property QtObject speed: QtObject { property int longDuration: 200 }
 Component.onCompleted: MoUI.Tokens.motionProbe = speed
 function setMotion(on) { speed.longDuration = on ? 200 : 1 }
 readonly property real motion: Theme.motionScale
 Loader {
  id: loader; objectName: "sceneLoader"; anchors.fill: parent; anchors.margins: 24
  sourceComponent: win.scene === "output" ? outputC : win.scene === "approval" ? approvalC
    : win.scene === "toast" ? toastC : win.scene === "home" ? homeC
    : win.scene === "legacyHome" ? legacyHomeC : workbenchC
 }
 Component { id: outputC; ColumnLayout { OutputBox { objectName: "outputCanvas"; text: "نتيجة الأمر · result readback" } Item { Layout.fillHeight: true } } }
 Component { id: approvalC; Item { ActionCards { objectName: "approvalStack"; width: Math.min(parent.width, 720); anchors.centerIn: parent; maxHeight: parent.height; overText: true } } }
 Component { id: toastC; Item { Toasts { objectName: "toastStack"; anchors.centerIn: parent; Component.onCompleted: show("error", "تعذّر التنفيذ · request failed") } } }
 Component { id: homeC; HomePage {} }
 Component { id: legacyHomeC; HomeSheet {} }
 Component { id: workbenchC; WorkbenchPage {} }
}'''.encode(), QUrl.fromLocalFile(str(ROOT/'qml/ReadingProof.qml')))
        win = component.create()
        assert win, str([e.toString() for e in component.errors()])
        settle(.2)

        def text_item(text):
            matches = [item for item in visual_items(win.contentItem())
                       if item.isVisible() and item.property('text') == text
                       and isinstance(item.property('font'), QFont)
                       and isinstance(item.property('color'), QColor)]
            assert matches, 'actual populated text missing: '+text
            return matches[0]

        def reveal(item):
            # Scroll each real clipping owner to the target; never move text or
            # relax clipping. ListView delegates remain actual component data.
            ancestor = item.parentItem()
            while ancestor:
                if ancestor.property('contentY') is not None and ancestor.property('contentHeight') is not None:
                    if float(ancestor.property('contentHeight')) <= ancestor.height():
                        ancestor = ancestor.parentItem()
                        continue
                    position = item.mapToItem(ancestor, QPointF(0, 0))
                    current = float(ancestor.property('contentY'))
                    minimum = float(ancestor.property('originY') or 0)
                    maximum = minimum + float(ancestor.property('contentHeight')) - ancestor.height()
                    wanted = current + position.y() - ancestor.height()/2 + item.height()/2
                    ancestor.setProperty('contentY', min(maximum, max(minimum, wanted)))
                    settle(.03)
                ancestor = ancestor.parentItem()
            settle(.04)

        def contrast(item, label, *, required=True):
            win.setMotion(False)
            settle(.04)
            reveal(item)
            ink = item.property('color')
            assert isinstance(ink, QColor) and ink.isValid(), label+': no native ink'
            bounds = item.mapRectToScene(item.boundingRect())
            assert bounds.width() > 4 and bounds.height() > 4, label+': empty text geometry'
            assert bounds.left() >= 0 and bounds.right() <= win.width()+1, label+': horizontal clipping'
            assert bounds.top() >= 0 and bounds.bottom() <= win.height()+1, label+': vertical clipping'
            alpha = ink.alphaF()
            ancestor = item
            while ancestor:
                alpha *= ancestor.opacity()
                ancestor = ancestor.parentItem()
            original_opacity = item.opacity()
            item.setOpacity(0)
            settle(.025)
            background = win.grabWindow()
            item.setOpacity(original_opacity)
            settle(.025)
            painted = win.grabWindow()
            scale = background.devicePixelRatio()
            from PySide6.QtCore import QRect
            crop = QRect(int(bounds.left()*scale), int(bounds.top()*scale),
                         max(1, int(bounds.width()*scale)), max(1, int(bounds.height()*scale)))
            assert not background.isNull() and painted.copy(crop) != background.copy(crop), label+': no actual painted text'
            samples = []
            for fraction in (.15, .5, .85):
                x, y = int((bounds.left()+bounds.width()*fraction)*scale), int(bounds.center().y()*scale)
                backing = rgb(background.pixelColor(x, y))
                composite = tuple(v*alpha+b*(1-alpha) for v, b in zip(rgb(ink), backing))
                samples.append(ratio(composite, backing))
            measured = min(samples)
            if required:
                assert measured >= 4.5, (f'{label}: painted contrast {measured:.3f}:1 < 4.5:1 '
                    f'ink={ink.name()} alpha={alpha:.3f} background={backing} bounds={bounds}')
                checks[label] = round(measured, 3)
            return measured

        def select(scene):
            win.setProperty('scene', scene)
            settle(.15)

        def moving():
            objects = {obj for item in visual_items(win.contentItem())
                       for obj in [item, *item.findChildren(QObject)]}
            return [obj for obj in objects
                    if 'Animation' in obj.metaObject().className() or 'Animator' in obj.metaObject().className()
                    if obj.property('loops') == -1 and obj.property('running') is True]

        def motion_control(label):
            win.setMotion(True)
            settle(.08)
            active = moving()
            assert active, label+': positive ambient control never ran '+str((controller.motion, win.property('motion')))
            win.setMotion(False)
            settle(.06)
            assert win.property('motion') == 0, label+': native shared off not published'
            assert not moving(), label+': ambient animation remains running after global off'
            motion_counts.append([label, len(active)])

        output = text_item('نتيجة الأمر · result readback')
        contrast(output, 'output')
        if light:
            canvas = win.findChild(QQuickItem, 'outputCanvas')
            current = canvas.property('color')
            canvas.setProperty('color', QColor.fromRgbF(0, 0, 0, .30))
            old_contrasts['output'] = contrast(output, 'old output', required=False)
            assert old_contrasts['output'] < 4.5
            negatives.append('old_dark_output_refused')
            canvas.setProperty('color', current)

        now = time.time()*1000
        controller.actions.set_rows([dict(aid='private-ask', kind='agent', name='review',
            title='موافقة المالك · approval', detail='Private fixture', reason='Read the exact request',
            stage='ask', category='user_confirm', summary='', output='طلب محدد · exact request',
            started=0, expires=now+120000, origin='mira')])
        select('approval')
        settle(.8)
        approval = text_item('موافقة المالك · approval')
        contrast(approval, 'approval title')
        contrast(text_item('طلب محدد · exact request'), 'approval request')
        if light:
            card = approval.parentItem()
            while card and card.property('tint') is None:
                card = card.parentItem()
            assert card, 'actual approval canvas missing'
            current = card.property('tint')
            card.setProperty('tint', QColor.fromRgbF(.055, .066, .145, .985))
            settle(.5)
            old_ratio = contrast(approval, 'old approval', required=False)
            assert old_ratio < 4.5, ('old approval not refused', old_ratio, card.metaObject().className(), card.property('tint'), card.property('color'))
            old_contrasts['approval'] = old_ratio
            negatives.append('old_dark_approval_refused')
            card.setProperty('tint', current)
            settle(.5)
        motion_control('approval breath')
        controller.actions.set_rows([])
        select('toast')
        settle(.3)
        contrast(text_item('تعذّر التنفيذ · request failed'), 'toast')

        home = controller.homePage
        home.review()
        select('home')
        contrast(text_item('المكتب'), 'ON home device')
        home.update(linked=False, hub={'stage':'starting'})
        motion_control('home starting')
        home.review()
        rows = controller._devices_from(SAMPLE_DEVICES[:1])
        controller.devices.set_rows(rows)
        controller._update('_home', controller.homeChanged, linked=True, available=1, total=1,
                           lights_on=1, lights_available=1)
        select('legacyHome')
        contrast(text_item('Büro'), 'ON legacy device')

        workbench = controller.workbenchPage
        workbench.review()
        workbench.update(tab='git', diff=[{'k':'add','t':'+added line'}, {'k':'del','t':'-removed line'}])
        select('workbench')
        contrast(text_item('+added line'), 'diff addition')
        contrast(text_item('-removed line'), 'diff removal')
        workbench.update(tab='tasks')
        settle(.15)
        contrast(text_item('Verification incomplete; inspect the session and continue.'), 'task error')
        motion_control('running task')
        workbench.update(tab='terminal', termOutput='قراءة الطرفية · terminal readback', termTitle='Private terminal', termCwd='')
        settle(.15)
        contrast(text_item('Private terminal'), 'terminal header')
        contrast(text_item('قراءة الطرفية · terminal readback'), 'terminal output')
        workbench.update(termOutput='')
        settle(.1)
        contrast(text_item(controller.s['wb_term_waiting']), 'terminal empty state')
        fatal = [message for message in messages if any(word in message for word in
                 ('ReferenceError', 'TypeError', 'Cannot assign', 'Unable to assign', 'is not a type'))]
        assert not fatal, str(fatal)
        controller.shutdown()
        win.close()
        settle(.04)
    qInstallMessageHandler(previous)
    print('MIRA_READING_STATES_PASS', json.dumps({'family':family, 'painted_contrast':checks,
          'old_controls':negatives, 'old_contrast':old_contrasts,
          'global_off_positive_counts':motion_counts, 'viewport':[1000,850]}, ensure_ascii=True))


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--probe':
        probe(sys.argv[2])
    else:
        unittest.main(verbosity=2)
