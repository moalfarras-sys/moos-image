#!/usr/bin/env python3
"""Build-only native package manifest/install authority for the reviewed boot fix."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

BASE = '24.004.60-24.fc44'
FIXED = '24.004.60-24.1.moos1.fc44'
SOURCE = 'e45ef414519b4c9d441b086fbb6b3456df523d61890c9cc3876c069f0eaf57a4'


def command(argv):
    return subprocess.check_output(argv, text=True).strip()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metadata(path):
    return command(['rpm', '-qp', '--qf', '%{NAME} %{VERSION}-%{RELEASE} %{ARCH}', str(path)]).split()


def collect(folder, output):
    import shutil
    arch = command(['rpm', '--eval', '%{_arch}'])
    assert arch in ('x86_64', 'aarch64'), arch
    packages = []
    for rpm in sorted(folder.rglob('*.rpm')):
        name, version, target = metadata(rpm)
        if any(name.endswith(end) for end in ('-devel', '-debuginfo', '-debugsource')):
            continue
        assert name.startswith('plymouth') and version == FIXED and target in (arch, 'noarch')
        destination = output / rpm.name
        shutil.copy2(rpm, destination)
        packages.append({'name': name, 'file': rpm.name, 'arch': target, 'sha256': sha(destination)})
    required = {'plymouth', 'plymouth-core-libs', 'plymouth-scripts', 'plymouth-plugin-script',
                'plymouth-plugin-two-step', 'plymouth-system-theme'}
    assert required <= {item['name'] for item in packages}
    manifest = {'schema': 1, 'base': BASE, 'fixed': FIXED, 'arch': arch,
                'source_sha256': SOURCE, 'packages': packages}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')


def install(folder):
    manifest = json.loads((folder / 'manifest.json').read_text())
    arch = command(['rpm', '--eval', '%{_arch}'])
    assert manifest['schema'] == 1 and manifest['arch'] == arch
    assert manifest['base'] == BASE and manifest['fixed'] == FIXED
    assert manifest['source_sha256'] == SOURCE
    # Never pin a later upstream package backwards or overwrite an unknown version.
    current = command(['rpm', '-q', '--qf', '%{VERSION}-%{RELEASE}', 'plymouth-core-libs'])
    assert current == BASE, f'unreviewed Plymouth base: {current}'
    owned = set(command(['rpm', '-qa', '--qf', '%{NAME}\n', 'plymouth*']).splitlines())
    selected = []
    for item in manifest['packages']:
        if item['name'] not in owned:
            continue
        path = folder / item['file']
        assert path.parent == folder and path.is_file()
        assert sha(path) == item['sha256']
        assert metadata(path) == [item['name'], FIXED, item['arch']]
        selected.append(path)
    assert {metadata(path)[0] for path in selected} == owned, 'missing installed subpackage'
    # Replace only the subpackages this edition already owns. No devel, theme or
    # renderer is added implicitly; the final MoOS identity scrub still owns assets.
    subprocess.run(['dnf5', '-y', 'install', '--setopt=install_weak_deps=False',
                    *map(str, selected)], check=True)
    for name in sorted(owned):
        actual = command(['rpm', '-q', '--qf', '%{VERSION}-%{RELEASE}', name])
        assert actual == FIXED, f'boot fix did not reach {name}: {actual}'
    # The final initramfs gate additionally proves these exact library bytes reached it.
    lib = Path('/usr/lib64/libply-splash-core.so.5.0.0')
    record = {'schema': 1, 'base': BASE, 'fixed': FIXED, 'source_sha256': SOURCE,
              'library_sha256': sha(lib), 'packages': sorted(owned)}
    target = Path('/usr/share/moos/plymouth-frame-lifetime.json')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(record, indent=2) + '\n')
    print('MoOS Plymouth frame-lifetime packages installed and read back')


if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] == 'collect':
        collect(Path(sys.argv[2]), Path(sys.argv[3]))
    elif len(sys.argv) == 3 and sys.argv[1] == 'install':
        install(Path(sys.argv[2]))
    else:
        raise SystemExit('usage: plymouth_rpms.py collect INPUT OUTPUT | install INPUT')
