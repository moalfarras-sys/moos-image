#!/usr/bin/env python3
"""Admit the exact native tray source before adding the MoOS presentation.

The native C++ containment, models, applet lifetime and popup container remain
upstream. This runs in the vendor RPM's %build, after its own patches.
"""
import hashlib
import json
from pathlib import Path
import re
import sys


REPLACED = {'main.qml', 'ExpandedRepresentation.qml'}
ADDED = {'CenterBackend.qml', 'CenterTile.qml', 'CenterSlider.qml',
         'CenterNotifications.qml', 'ControlCenterView.qml'}
NOTIFICATION_QML = {'main.qml', 'global/Globals.qml', 'NotificationPopup.qml'}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def prepare(tree, payload, review):
    admission = review.get('control_center')
    if admission is None:
        # These are explicitly retained logout-only reviews, not a claim that a
        # new UI was qualified against an older native containment.
        return {'enabled': False, 'base': review['base']}
    assert review['base'] == '6.8.3-1.fc44', 'unreviewed native tray version'
    assert set(admission) == {'upstream_sha256', 'cmake_sha256', 'notifications_upstream_sha256'}
    assert set(admission['upstream_sha256']) == REPLACED
    assert set(admission['notifications_upstream_sha256']) == NOTIFICATION_QML
    native = tree / 'applets/systemtray'
    qml = native / 'qml'
    source_files = {name: qml / name for name in REPLACED}
    cmake = native / 'CMakeLists.txt'
    for name, path in source_files.items():
        assert path.is_file() and not path.is_symlink(), f'unsafe native tray source: {name}'
        assert digest(path.read_bytes()) == admission['upstream_sha256'][name], f'unreviewed native tray source: {name}'
    notifications = tree / 'applets/notifications'
    for directory in (notifications, notifications / 'global'):
        assert directory.is_dir() and not directory.is_symlink(), 'unsafe native notification source directory'
    for name in NOTIFICATION_QML:
        path = notifications / name
        assert path.is_file() and not path.is_symlink(), f'unsafe native notification source: {name}'
        assert digest(path.read_bytes()) == admission['notifications_upstream_sha256'][name], f'unreviewed native notification source: {name}'
    assert cmake.is_file() and not cmake.is_symlink()
    cmake_text = cmake.read_text()
    assert digest(cmake.read_bytes()) == admission['cmake_sha256'], 'unreviewed native tray CMake'
    assert payload.is_dir() and not payload.is_symlink()
    files = list(payload.iterdir())
    assert {p.name for p in files} == REPLACED | ADDED, 'unexpected or missing MoOS tray source'
    assert all(p.is_file() and not p.is_symlink() for p in files), 'unsafe MoOS tray source'
    notification_payload = payload.parent / 'notification-qml'
    assert notification_payload.is_dir() and not notification_payload.is_symlink(), 'unsafe MoOS notification source directory'
    notification_files = list(notification_payload.rglob('*'))
    assert {p.relative_to(notification_payload).as_posix() for p in notification_files} == NOTIFICATION_QML | {'global'}, 'unexpected or missing MoOS notification source'
    assert (notification_payload / 'global').is_dir() and not (notification_payload / 'global').is_symlink(), 'unsafe MoOS notification source directory'
    assert all((notification_payload / name).is_file() and not (notification_payload / name).is_symlink() for name in NOTIFICATION_QML), 'unsafe MoOS notification source'
    assert not any((qml / name).exists() or (qml / name).is_symlink() for name in ADDED), 'native tray source collision'
    anchor = '    RESOURCES\n        main.xml\n'
    assert cmake_text.count(anchor) == 1
    # Materialize every input and validate UTF-8 before the first mutation.
    content = {p.name: p.read_bytes() for p in files}
    for name, data in content.items():
        assert data and re.fullmatch(r'[A-Za-z][A-Za-z0-9]*\.qml', name)
        data.decode('utf-8')
    notification_content = {name: (notification_payload / name).read_bytes() for name in NOTIFICATION_QML}
    for data in notification_content.values():
        assert data, 'empty MoOS notification source'
        data.decode('utf-8')
    cmake_text = cmake_text.replace(anchor, ''.join(f'        qml/{name}\n' for name in sorted(ADDED)) + anchor, 1)
    for name, data in content.items():
        (qml / name).write_bytes(data)
    for name, data in notification_content.items():
        (notifications / name).write_bytes(data)
    cmake.write_text(cmake_text)
    record = {'enabled': True, 'base': review['base'],
              'upstream_sha256': admission['upstream_sha256'],
              'qml_sha256': {name: digest(data) for name, data in sorted(content.items())},
              'notifications_upstream_sha256': admission['notifications_upstream_sha256'],
              'notifications_qml_sha256': {name: digest(data) for name, data in sorted(notification_content.items())},
              'cmake_sha256': digest(cmake.read_bytes())}
    return record


if __name__ == '__main__':
    assert len(sys.argv) == 5, 'usage: prepare_control_center.py TREE QML_PAYLOAD SOURCE_REVIEW RECEIPT'
    record = prepare(Path(sys.argv[1]), Path(sys.argv[2]), json.loads(Path(sys.argv[3]).read_text()))
    Path(sys.argv[4]).write_text(json.dumps(record, indent=2) + '\n')
    print('MoOS native tray source admission: ' + ('prepared' if record['enabled'] else 'retained logout-only review'))
