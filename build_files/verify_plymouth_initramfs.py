#!/usr/bin/env python3
"""Prove the reviewed package and exact fixed library are inside the boot archive."""
import hashlib
import json
import re
from pathlib import Path
import subprocess
import sys

record = json.loads(Path('/usr/share/moos/plymouth-frame-lifetime.json').read_text())
expected = '24.004.60-24.1.moos1.fc44'
assert record['schema'] == 1 and record['fixed'] == expected
library = 'usr/lib64/libply-splash-core.so.5.0.0'
assert hashlib.sha256(Path('/' + library).read_bytes()).hexdigest() == record['library_sha256']
for package in record['packages']:
    assert package.startswith('plymouth')
    actual = subprocess.check_output(['rpm', '-q', '--qf', '%{VERSION}-%{RELEASE}', package], text=True)
    assert actual == expected, f'unfixed Plymouth package: {package}'
archive = subprocess.run(['lsinitrd', '-f', library, sys.argv[1]],
                         capture_output=True, check=True, timeout=240).stdout
assert archive and hashlib.sha256(archive).hexdigest() == record['library_sha256'], \
    'fixed Plymouth library missing or different inside initramfs'
# Prove every literal asset used by the real installed theme, not retired names.
theme = Path('/usr/share/plymouth/themes/moos')
script = (theme / 'moos.script').read_text()
assets = set(re.findall(r'Image\("([^"\n]+)"\)', script))
assert assets, 'theme loads no literal images'
for name in sorted(assets | {'moos.script', 'moos.plymouth', 'logo.png'}):
    assert Path(name).name == name, 'theme asset escapes its directory'
    boot = subprocess.run(['lsinitrd', '-f', 'usr/share/plymouth/themes/moos/' + name,
                           sys.argv[1]], capture_output=True, check=True, timeout=240).stdout
    assert boot == (theme / name).read_bytes(), f'missing or different boot asset: {name}'
print('MoOS Plymouth frame-lifetime gate passed: package, root, boot library and theme bytes agree')
