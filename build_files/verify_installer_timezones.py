#!/usr/bin/env python3
"""Hold selectable tzdata coverage and the real Arabic/English Qt search path."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time


def validate(catalog, zone_tab):
    if catalog.stat().st_size > 1024 * 1024:
        raise ValueError('timezone labels exceed the bounded data budget')
    data = json.loads(catalog.read_text())
    if data.get('schema') != 1 or data.get('license') != 'Unicode-3.0':
        raise ValueError('unknown localized timezone data schema/provenance')
    labels = data.get('zones')
    if not isinstance(labels, dict) or len(labels) < 300:
        raise ValueError('incomplete localized timezone data')
    for name, entry in labels.items():
        if (not re.fullmatch(r'[A-Za-z0-9_+.-]+(?:/[A-Za-z0-9_+.-]+)+', name)
                or any(part in ('.', '..') for part in name.split('/'))):
            raise ValueError('invalid timezone identifier')
        if not isinstance(entry, dict) or set(entry) != {'ar', 'en'}:
            raise ValueError('both languages are required for every zone')
        if any(not isinstance(value, str) or not value or len(value) > 200
               for value in entry.values()):
            raise ValueError('invalid localized timezone label')
    selected = {row.split('\t')[2] for row in zone_tab.read_text().splitlines()
                if row and not row.startswith('#')}
    missing = selected - labels.keys()
    if missing:
        raise ValueError('selectable tzdata zones without reviewed labels: ' + ', '.join(sorted(missing)))
    for name, needle in [('Europe/Berlin', 'برلين'), ('Asia/Riyadh', 'الرياض'),
                         ('Asia/Damascus', 'دمشق')]:
        if needle not in labels[name]['ar']:
            raise ValueError('missing Arabic exemplar city: ' + name)
    return len(selected)


def probe(qml, catalog, language, output):
    from PySide6.QtCore import QEvent, QLocale, QPoint, QPointF, Qt, qInstallMessageHandler
    from PySide6.QtGui import QGuiApplication, QInputMethodEvent
    from PySide6.QtQuick import QQuickItem, QQuickWindow
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtTest import QTest
    QLocale.setDefault(QLocale('ar_SA' if language == 'ar' else 'en_US'))
    app = QGuiApplication([]); app.setLayoutDirection(QLocale().textDirection())
    warnings = []; previous = qInstallMessageHandler(lambda mode, context, message: warnings.append(message))
    engine = QQmlApplicationEngine()
    engine.setInitialProperties({'step': 5, 'lang': language, 'zoneLabelsPath': str(catalog)})
    try:
        engine.load(str(qml)); assert engine.rootObjects(), warnings
        root = engine.rootObjects()[0]; root.setWidth(1080); root.setHeight(760); root.requestActivate()
        def find_item(name):
            # Dynamic delegates belong to the visual tree, not necessarily the
            # root's QObject ownership tree. Inspect the real rendered controls.
            def walk(item):
                if item.objectName() == name: return item
                for child in item.childItems():
                    found = walk(child)
                    if found is not None: return found
                return None
            return walk(root.contentItem())
        def pump(predicate, deadline=4):
            limit = time.monotonic() + deadline
            while time.monotonic() < limit:
                app.processEvents(); time.sleep(.01)
                if predicate(): return
            raise AssertionError('native timezone transition did not finish')
        pump(lambda: root.property('zoneLabelsReady'))
        search = find_item('installerZoneSearch')
        listing = find_item('installerZoneList')
        next_button = find_item('installerNavNext')
        assert search and listing and next_button
        initial = root.property('tz')
        def enter(text):
            search.forceActiveFocus()
            QTest.keyClick(root, Qt.Key_A, Qt.ControlModifier)
            QTest.keyClick(root, Qt.Key_Backspace)
            event = QInputMethodEvent(); event.setCommitString(text)
            QGuiApplication.sendEvent(search, event)
            pump(lambda: root.property('zoneFilter') == text)
        for query, expected in [('برلين', 'Europe/Berlin'), ('بِرْلِين', 'Europe/Berlin'),
                                ('Berlin', 'Europe/Berlin'), ('برلين المانيا', 'Europe/Berlin'),
                                ('europe/BERLIN', 'Europe/Berlin'), ('الرياض', 'Asia/Riyadh'),
                                ('Riyadh', 'Asia/Riyadh'), ('دمشق', 'Asia/Damascus')]:
            enter(query)
            pump(lambda: listing.property('count') == 1)
            pump(lambda: find_item('installerZoneChoice_' + expected) is not None)
            assert root.property('tz') == initial, 'filter silently changed the selected zone'
        enter('برلين')
        pump(lambda: listing.property('count') == 1)
        if initial != 'Europe/Berlin':
            assert not next_button.property('enabled'), 'unmatched starting guess can still continue'
        choice = find_item('installerZoneChoice_Europe/Berlin')
        point = choice.mapToScene(QPointF(choice.width()/2, choice.height()/2))
        assert 0 <= point.x() < root.width() and 0 <= point.y() < root.height()
        QTest.mouseClick(root, Qt.LeftButton, Qt.NoModifier, QPoint(round(point.x()), round(point.y())))
        pump(lambda: root.property('tz') == 'Europe/Berlin' and next_button.property('enabled'))
        root.setProperty('lang', 'en' if language == 'ar' else 'ar')
        app.processEvents()
        assert root.property('tz') == 'Europe/Berlin'
        if output:
            frame = root.grabWindow(); assert not frame.isNull()
            assert frame.save(str(output / ('timezone-language-switch-' + language + '.png')))
        enter('moos-no-city-match'); pump(lambda: listing.property('count') == 0)
        assert not next_button.property('enabled') and root.property('tz') == 'Europe/Berlin'
        enter(''); pump(lambda: next_button.property('enabled'))
        faults = [w for w in warnings if any(word in w for word in
                  ('ReferenceError', 'TypeError', 'Binding loop', 'binding loop', 'Unable to assign'))]
        assert not faults, faults
        print(json.dumps({'language': language, 'queries': 8, 'real_row_click': True,
                          'selected_iana': root.property('tz'), 'unmatched_guess_blocked': True,
                          'language_switch_preserves_selection': True}))
        root.close()
    finally:
        for window in engine.rootObjects(): window.close()
        engine.deleteLater(); app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        qInstallMessageHandler(previous)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--catalog', type=Path, default=Path('/usr/share/moos/installer-timezones.json'))
    parser.add_argument('--tab', type=Path, default=Path('/usr/share/zoneinfo/zone1970.tab'))
    parser.add_argument('--qml', type=Path, default=Path('/usr/share/moos/apps/installer/main.qml'))
    parser.add_argument('--native', action='store_true')
    parser.add_argument('--probe', choices=('ar', 'en'))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(); count = validate(args.catalog, args.tab)
    if args.probe:
        probe(args.qml.resolve(), args.catalog.resolve(), args.probe, args.output)
    elif args.native:
        if args.output: args.output.mkdir(parents=True, exist_ok=True)
        for language in ('ar', 'en'):
            with tempfile.TemporaryDirectory(prefix='moos-timezone-native-') as profile:
                base = Path(profile)
                for name in ('home', 'runtime', 'cache', 'data', 'config'):
                    (base/name).mkdir(mode=0o700)
                env = {'PATH': os.environ['PATH'], 'HOME': str(base/'home'),
                       'XDG_RUNTIME_DIR': str(base/'runtime'), 'XDG_CACHE_HOME': str(base/'cache'),
                       'XDG_CONFIG_HOME': str(base/'config'), 'XDG_DATA_HOME': str(base/'data'),
                       'QT_QPA_PLATFORM': 'offscreen', 'QT_QUICK_BACKEND': 'software',
                       'QT_QUICK_CONTROLS_STYLE': 'Basic', 'QML_DISABLE_DISK_CACHE': '1',
                       'QML_XHR_ALLOW_FILE_READ': '1', 'LANG': 'ar_SA.UTF-8' if language == 'ar' else 'en_US.UTF-8'}
                command = ['dbus-run-session', '--', sys.executable, str(Path(__file__).resolve()),
                           '--catalog', str(args.catalog.resolve()), '--tab', str(args.tab.resolve()),
                           '--qml', str(args.qml.resolve()), '--probe', language]
                if args.output: command += ['--output', str(args.output.resolve())]
                subprocess.run(command, env=env, check=True, timeout=30)
    print('MoOS installer timezone gate passed: ' + str(count) + ' selectable zones covered')


if __name__ == '__main__':
    main()
