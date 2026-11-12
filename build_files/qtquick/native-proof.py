#!/usr/bin/python3
"""Private native Qt regression, with executed marker and loaded-library proof."""
import argparse
import json
import os
from pathlib import Path
import resource
import subprocess
import tempfile


def validate(result, quick, expect):
    libraries = [line.removeprefix('MOOS_QT_LIBRARY ') for line in result.stderr.splitlines()
                 if line.startswith('MOOS_QT_LIBRARY ')]
    actual = [Path(path).resolve() for path in libraries if '/libQt6Quick.so.' in path]
    if actual != [quick.resolve()]:
        raise ValueError(f'wrong loaded QtQuick library: {actual}')
    marker = 'MOOS_QT_TEARDOWN_NATIVE_EXECUTED true'
    if expect == 'crash':
        if result.returncode != -11 or marker in result.stderr:
            raise ValueError(f'vendor regression did not reproduce SIGSEGV: {result.returncode}')
    elif result.returncode != 0 or result.stderr.splitlines().count(marker) != 1:
        raise ValueError(f'native Qt teardown was not executed successfully: {result.returncode}')
    return {'exit': result.returncode, 'expected': expect, 'libraries': libraries,
            'destruction_executed': marker in result.stderr}


def run(probe, qml, quick, expect, imports=None):
    # No inherited owner HOME, runtime, bus, display, plugin path or credentials.
    with tempfile.TemporaryDirectory(prefix='moos-qt-teardown-') as directory:
        private = Path(directory)
        for name in ('home', 'runtime', 'config', 'data', 'cache'):
            (private / name).mkdir(mode=0o700)
        env = {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8',
               'HOME': str(private / 'home'), 'XDG_RUNTIME_DIR': str(private / 'runtime'),
               'XDG_CONFIG_HOME': str(private / 'config'), 'XDG_DATA_HOME': str(private / 'data'),
               'XDG_CACHE_HOME': str(private / 'cache'), 'QT_QPA_PLATFORM': 'offscreen',
               'QT_QUICK_BACKEND': 'software', 'QML_DISABLE_DISK_CACHE': '1',
               'LD_LIBRARY_PATH': str(quick.parent)}
        if imports is not None:
            env['QML_IMPORT_PATH'] = str(imports)
        def no_core():
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        result = subprocess.run([str(probe.resolve()), str(qml.resolve())], env=env,
                                cwd=private, text=True, capture_output=True, timeout=15,
                                preexec_fn=no_core)
        # QtQuick-only fixture does not use D-Bus or launch a compositor.
        receipt = validate(result, quick, expect)
        print(result.stderr, end='')
        return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe', required=True, type=Path)
    parser.add_argument('--qml', required=True, type=Path)
    parser.add_argument('--quick', required=True, type=Path)
    parser.add_argument('--imports', type=Path)
    parser.add_argument('--expect', choices=('crash', 'pass'), required=True)
    parser.add_argument('--receipt', required=True, type=Path)
    args = parser.parse_args()
    receipt = run(args.probe, args.qml, args.quick, args.expect, args.imports)
    args.receipt.write_text(json.dumps(receipt, indent=2) + '\n')
