#!/usr/bin/env python3
"""SDK-only negative/positive proof using public APIs in the actual RPM library."""
import json
import os
from pathlib import Path
import resource
import subprocess

resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
root = Path('/work/plymouth-package-proof')
root.mkdir()
manifest = json.loads(Path('/out/manifest.json').read_text())
package = next(item for item in manifest['packages'] if item['name'] == 'plymouth-core-libs')
cpio = subprocess.check_output(['rpm2cpio', '/out/' + package['file']])
subprocess.run(['cpio', '-idm', '--no-absolute-filenames', '--no-preserve-owner'],
               input=cpio, cwd=root, capture_output=True, check=True)
source = next(Path('/work/plymouth-proof/source').iterdir())
include = ['-I' + str(source / 'src/libply'), '-I' + str(source / 'src/libply-splash-core')]
fixture = '/src/frame-lifetime-native.c'
subprocess.run(['gcc', '-Wall', '-Wextra', '-Werror', '-fPIC', '-shared', '-DTEST_PLUGIN', *include,
                fixture, '-o', str(root / 'fixture.so')], check=True)
theme = root / 'fixture.plymouth'
theme.write_text('[Plymouth Theme]\nName=Frame lifetime fixture\nModuleName=fixture\n')
subprocess.run(['gcc', '-Wall', '-Wextra', '-Werror', '-rdynamic', *include, fixture,
                '-o', str(root / 'probe'), '-l:libply-splash-core.so.5',
                '-l:libply.so.5', '-ldl'], check=True)
trials = []
for name, library, expected, repeats in (
        ('vendor', '/usr/lib64', 71, 3), ('rebuilt-package', str(root / 'usr/lib64'), 0, 20)):
    for trial in range(repeats):
        result = subprocess.run([str(root / 'probe'), str(theme), str(root) + '/'],
                                env=dict(os.environ, LD_LIBRARY_PATH=library),
                                capture_output=True, text=True, timeout=10)
        (root / f'{name}-{trial}.log').write_text(result.stdout + result.stderr)
        trials.append({'library': name, 'trial': trial, 'exit': result.returncode,
                       'expected': result.returncode == expected})
proof = {'schema': 1, 'scope': 'actual native RPM shared library, no boot/device I/O',
         'trials': trials, 'passed': all(trial['expected'] for trial in trials)}
Path('/out/proof/package.json').write_text(json.dumps(proof, indent=2) + '\n')
print(json.dumps({key: value for key, value in proof.items() if key != 'trials'}))
raise SystemExit(0 if proof['passed'] else 1)
