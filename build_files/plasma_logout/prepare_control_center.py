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


def digest(data):
    return hashlib.sha256(data).hexdigest()


def prepare(tree, payload, review):
    admission = review.get('control_center')
    if admission is None:
        # These are explicitly retained logout-only reviews, not a claim that a
        # new UI was qualified against an older native containment.
        return {'enabled': False, 'base': review['base']}
    assert review['base'] == '6.8.3-1.fc44', 'unreviewed native tray version'
    assert set(admission) == {'upstream_sha256', 'cmake_sha256'}
    assert set(admission['upstream_sha256']) == REPLACED
    native = tree / 'applets/systemtray'
    qml = native / 'qml'
    source_files = {name: qml / name for name in REPLACED}
    cmake = native / 'CMakeLists.txt'
    for name, path in source_files.items():
        assert path.is_file() and not path.is_symlink(), f'unsafe native tray source: {name}'
        assert digest(path.read_bytes()) == admission['upstream_sha256'][name], f'unreviewed native tray source: {name}'
    assert cmake.is_file() and not cmake.is_symlink()
    cmake_text = cmake.read_text()
    assert digest(cmake.read_bytes()) == admission['cmake_sha256'], 'unreviewed native tray CMake'
    assert payload.is_dir() and not payload.is_symlink()
    files = list(payload.iterdir())
    assert {p.name for p in files} == REPLACED | ADDED, 'unexpected or missing MoOS tray source'
    assert all(p.is_file() and not p.is_symlink() for p in files), 'unsafe MoOS tray source'
    assert not any((qml / name).exists() or (qml / name).is_symlink() for name in ADDED), 'native tray source collision'
    anchor = '    RESOURCES\n        main.xml\n'
    assert cmake_text.count(anchor) == 1
    # Materialize every input and validate UTF-8 before the first mutation.
    content = {p.name: p.read_bytes() for p in files}
    for name, data in content.items():
        assert data and re.fullmatch(r'[A-Za-z][A-Za-z0-9]*\.qml', name)
        data.decode('utf-8')
    cmake_text = cmake_text.replace(anchor, ''.join(f'        qml/{name}\n' for name in sorted(ADDED)) + anchor, 1)
    for name, data in content.items():
        (qml / name).write_bytes(data)
    cmake.write_text(cmake_text)
    record = {'enabled': True, 'base': review['base'],
              'upstream_sha256': admission['upstream_sha256'],
              'qml_sha256': {name: digest(data) for name, data in sorted(content.items())},
              'cmake_sha256': digest(cmake.read_bytes())}
    return record


if __name__ == '__main__':
    assert len(sys.argv) == 5, 'usage: prepare_control_center.py TREE QML_PAYLOAD SOURCE_REVIEW RECEIPT'
    record = prepare(Path(sys.argv[1]), Path(sys.argv[2]), json.loads(Path(sys.argv[3]).read_text()))
    Path(sys.argv[4]).write_text(json.dumps(record, indent=2) + '\n')
    print('MoOS native tray source admission: ' + ('prepared' if record['enabled'] else 'retained logout-only review'))
