#!/usr/bin/env python3
"""Install only the edition's existing, exactly reviewed Plasma subpackages."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

BASE = '6.7.5-1.fc44'
FIXED = '6.7.5-1.1.moos1.fc44'
SOURCE = '7ed5cf4427c852286f9835ebb2a6bc1482758dcde411318ad8e4a5b2517c9263'
CORE = {'plasma-workspace', 'plasma-workspace-common', 'plasma-workspace-libs', 'libkworkspace6'}
# The vendor source also produces its existing theme/doc subpackages. Replace
# them only if the edition already owns them; the final identity scrub still
# removes the vendor theme. Never publish those names in the runtime receipt.
VENDOR_PACKAGES = CORE | {'plasma-workspace-doc', 'plasma-lookandfeel-fedora', 'sddm-wayland-plasma'}


def command(argv):
    return subprocess.check_output(argv, text=True).strip()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metadata(path):
    return command(['rpm', '-qp', '--qf', '%{NAME} %{VERSION}-%{RELEASE} %{ARCH}', str(path)]).split()


def collect(folder, output):
    arch = command(['rpm', '--eval', '%{_arch}'])
    assert arch in ('x86_64', 'aarch64'), arch
    packages = []
    for package in sorted(folder.rglob('*.rpm')):
        name, version, target = metadata(package)
        if any(name.endswith(end) for end in ('-devel', '-debuginfo', '-debugsource')):
            continue
        assert name in VENDOR_PACKAGES and version == FIXED and target in (arch, 'noarch'), (name, version, target)
        destination = output / package.name
        shutil.copy2(package, destination)
        packages.append({'name': name, 'file': package.name, 'arch': target, 'sha256': sha(destination)})
    assert CORE <= {item['name'] for item in packages}
    (output / 'manifest.json').write_text(json.dumps({
        'schema': 1, 'base': BASE, 'fixed': FIXED, 'arch': arch,
        'source_sha256': SOURCE, 'packages': packages,
    }, indent=2) + '\n')


def install(folder, root=Path('/')):
    manifest = json.loads((folder / 'manifest.json').read_text())
    arch = command(['rpm', '--eval', '%{_arch}'])
    assert manifest['schema'] == 1 and manifest['arch'] == arch
    assert manifest['base'] == BASE and manifest['fixed'] == FIXED
    assert manifest['source_sha256'] == SOURCE
    installed = set(command(['rpm', '-qa', '--qf', '%{NAME}\n']).splitlines())
    owned = installed & VENDOR_PACKAGES
    assert CORE <= owned, 'missing native Plasma runtime package'
    for name in sorted(owned):
        current = command(['rpm', '-q', '--qf', '%{VERSION}-%{RELEASE}', name])
        assert current == BASE, f'unreviewed Plasma package {name}: {current}'
        source = command(['rpm', '-q', '--qf', '%{SOURCERPM}', name])
        assert source == f'plasma-workspace-{BASE}.src.rpm', f'unreviewed Plasma source {name}: {source}'
    selected = []
    names = set()
    for item in manifest['packages']:
        if item['name'] not in owned:
            continue
        path = folder / item['file']
        assert path.parent == folder and path.is_file() and not path.is_symlink()
        assert item['name'] not in names, 'duplicate subpackage'
        assert sha(path) == item['sha256']
        assert metadata(path) == [item['name'], FIXED, item['arch']]
        names.add(item['name'])
        selected.append(path)
    assert names == owned, 'missing installed Plasma subpackage'
    subprocess.run(['dnf5', '-y', 'install', '--setopt=install_weak_deps=False',
                    *map(str, selected)], check=True)
    for name in sorted(owned):
        actual = command(['rpm', '-q', '--qf', '%{VERSION}-%{RELEASE}', name])
        assert actual == FIXED, f'logout fix did not reach {name}: {actual}'
    worker = root / 'usr/bin/plasma-shutdown'
    record = {'schema': 1, 'base': BASE, 'fixed': FIXED, 'source_sha256': SOURCE,
              'worker_sha256': sha(worker), 'packages': sorted(owned & CORE)}
    target = root / 'usr/share/moos/plasma-logout-transaction.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(record, indent=2) + '\n')
    print('MoOS native Plasma logout transaction installed and read back')


def verify(root=Path('/')):
    record = json.loads((root / 'usr/share/moos/plasma-logout-transaction.json').read_text())
    assert record['schema'] == 1 and record['base'] == BASE and record['fixed'] == FIXED
    assert record['source_sha256'] == SOURCE
    worker = root / 'usr/bin/plasma-shutdown'
    assert sha(worker) == record['worker_sha256'], 'logout worker changed after package install'
    activation = (root / 'usr/share/dbus-1/services/org.kde.Shutdown.service').read_text().splitlines()
    assert activation.count('Exec=/usr/bin/plasma-shutdown') == 1, 'D-Bus does not launch the verified worker'
    for name in record['packages']:
        assert command(['rpm', '-q', '--qf', '%{VERSION}-%{RELEASE}', name]) == FIXED
    # Read the RPM database's own payload digest as well as our install receipt.
    rows = command(['rpm', '-q', '--dump', 'plasma-workspace']).splitlines()
    matches = [row.split() for row in rows if row.split()[0] == '/usr/bin/plasma-shutdown']
    assert len(matches) == 1 and matches[0][3] == sha(worker), 'worker differs from its native RPM'
    print('MoOS native Plasma logout RPM and final worker bytes verified')


if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] == 'collect':
        collect(Path(sys.argv[2]), Path(sys.argv[3]))
    elif len(sys.argv) == 3 and sys.argv[1] == 'install':
        install(Path(sys.argv[2]))
    elif len(sys.argv) == 2 and sys.argv[1] == 'verify':
        verify()
    else:
        raise SystemExit('usage: rpms.py collect INPUT OUTPUT | install INPUT | verify')
