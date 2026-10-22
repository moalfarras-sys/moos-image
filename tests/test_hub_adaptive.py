#!/usr/bin/env python3
"""Exercise actual Qt layout/locale behavior; installed-desktop proof stays separate."""
from pathlib import Path
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'system_files/usr/share/plasma/wallpapers/org.moos.ui2.wallpaper/contents/ui'


def native_driver():
    from PySide6.QtCore import QObject, QUrl, QDateTime, QLocale, QTimer, Qt, qInstallMessageHandler
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply
    from PySide6.QtQml import QQmlComponent, QQmlEngine, QQmlNetworkAccessManagerFactory
    from PySide6.QtQuick import QQuickWindow
    from PySide6.QtTest import QTest

    # Geometry tests must not locate the developer or contact weather providers.
    class DeniedReply(QNetworkReply):
        def __init__(self, request, parent):
            super().__init__(parent)
            self.setRequest(request)
            self.setUrl(request.url())
            self.setError(QNetworkReply.ContentAccessDenied, 'Network disabled in layout test')
            QTimer.singleShot(0, self.finish)

        def finish(self):
            self.setFinished(True)
            self.errorOccurred.emit(self.error())
            self.finished.emit()

    class Network(QNetworkAccessManager):
        def createRequest(self, operation, request, data=None):
            return DeniedReply(request, self)

    class Factory(QQmlNetworkAccessManagerFactory):
        def create(self, parent):
            return Network(parent)

    messages = []
    qInstallMessageHandler(lambda kind, context, message: messages.append(message))
    app = QGuiApplication([])
    engine = QQmlEngine()
    engine.addImportPath(str(ROOT / 'system_files/usr/lib64/qt6/qml'))
    factory = Factory()
    engine.setNetworkAccessManagerFactory(factory)
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(PACKAGE / 'DashboardBento.qml')))
    assert not component.isError(), [e.toString() for e in component.errors()]
    root = component.create()
    assert root is not None, [e.toString() for e in component.errors()]
    window = QQuickWindow()
    root.setParentItem(window.contentItem())
    window.show()
    date = QDateTime.fromString('2026-10-22T12:34:00', 'yyyy-MM-ddTHH:mm:ss')
    assert root.setProperty('now', date)
    count = 0
    for compact in (False, True):
        assert root.setProperty('compact', compact)
        for flags in range(1, 8):
            for bit, key in enumerate(('showClock', 'showWeather', 'showSystem')):
                assert root.setProperty(key, bool(flags & (1 << bit)))
            app.processEvents()
            width, height = root.implicitWidth(), root.implicitHeight()
            root.setWidth(width)
            root.setHeight(height)
            window.resize(round(width), round(height))
            QTest.qWait(40)
            cards = [root.findChild(QObject, name) for name in
                     ('hubClockCard', 'hubWeatherCard', 'hubSystemCard')]
            rects = []
            for bit, card in enumerate(cards):
                assert card is not None
                if not flags & (1 << bit):
                    assert not card.isVisible()
                    continue
                rect = card.mapRectToItem(root, card.boundingRect())
                assert rect.width() > 100 and rect.height() > 100, (compact, flags, rect)
                assert rect.left() >= -1 and rect.top() >= -1, (compact, flags, rect)
                assert rect.right() <= width+1 and rect.bottom() <= height+1, (compact, flags, rect)
                for previous in rects:
                    overlap = previous.intersected(rect)
                    assert overlap.width() < 1 or overlap.height() < 1, (compact, flags, rects, rect)
                rects.append(rect)
            assert abs(max(rect.bottom() for rect in rects) - height) <= 1, (compact, flags, rects)
            if len(rects) == 1:
                assert abs(rects[0].width() - width) <= 1, (compact, flags, rects)
            if flags & 4:
                # Card bounds alone passed while the actual portrait desktop
                # clipped its disk gauge. Check the real metric items too.
                system = cards[2]
                for name in ('hubMetricCpu', 'hubMetricMemory', 'hubMetricDisk'):
                    metric = root.findChild(QObject, name)
                    assert metric is not None
                    rect = metric.mapRectToItem(system, metric.boundingRect())
                    assert rect.left() >= -1 and rect.top() >= -1, (compact, flags, name, rect)
                    assert rect.right() <= system.width()+1 and rect.bottom() <= system.height()+1, (compact, flags, name, rect)
            if flags == 7:
                clock, weather, system = cards
                if compact:
                    assert weather.y() >= clock.y()+clock.height()-1
                    assert abs(weather.y()-system.y()) < 1
                else:
                    assert abs(clock.y()-weather.y()) < 1
                    assert system.y() >= max(clock.y()+clock.height(), weather.y()+weather.height())-1
            count += 1
    local_date = root.findChild(QObject, 'hubLocalDate')
    locale = QLocale(sys.argv[2])
    expected = locale.toString(date.date(), QLocale.LongFormat)
    assert local_date.property('text') == expected, (local_date.property('text'), expected)
    # QQuickText's enum has no PySide converter; read the real QML value through
    # its JS wrapper instead of mistaking that binding limitation for a UI error.
    assert engine.newQObject(local_date).property('horizontalAlignment').toInt() == Qt.AlignHCenter.value
    # Restore a fixed single-row layout in this private Qt object. The portrait
    # acceptance predicate must reject it, even though the QML still loads.
    grid = root.findChild(QObject, 'hubAdaptiveGrid')
    assert grid.setProperty('columns', 5)
    QTest.qWait(40)
    clock, weather, _ = cards
    assert weather.y() < clock.y()+clock.height()-1, 'Broken-layout control did not reproduce'
    assert not any(any(token in message for token in ('ReferenceError', 'TypeError',
                   'Binding loop', 'Unable to assign', 'Cannot anchor')) for message in messages), messages
    window.close()
    print(json.dumps(dict(locale=sys.argv[2], native_layout_cases=count, localized_date=True,
                          fixed_row_negative_refused=True)))


class NativeHub(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec('PySide6'), 'native Qt/PySide6 unavailable')
    def test_native_geometry_and_localized_calendar(self):
        for language in ('ar', 'en'):
            with self.subTest(language=language), tempfile.TemporaryDirectory(prefix='moos-hub-') as tmp:
                env = dict(PATH='/usr/bin:/bin', HOME=tmp, XDG_CONFIG_HOME=tmp+'/config',
                           XDG_DATA_HOME=tmp+'/data', XDG_CACHE_HOME=tmp+'/cache',
                           XDG_RUNTIME_DIR=tmp, DBUS_SESSION_BUS_ADDRESS='unix:path='+tmp+'/absent',
                           LANG='ar_SA.UTF-8' if language == 'ar' else 'en_US.UTF-8',
                           LANGUAGE=language, QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software',
                           QML_DISABLE_DISK_CACHE='1')
                result = subprocess.run([sys.executable, __file__, '--native-driver', language],
                                        env=env, capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
                self.assertEqual(json.loads(result.stdout)['native_layout_cases'], 14)


if __name__ == '__main__':
    if sys.argv[1:2] == ['--native-driver']:
        native_driver()
    else:
        unittest.main()
