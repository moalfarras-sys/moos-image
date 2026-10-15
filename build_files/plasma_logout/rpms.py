#!/usr/bin/env python3
"""Install only the edition's existing, exactly reviewed Plasma subpackages."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import re

CORE = {'plasma-workspace', 'plasma-workspace-common', 'plasma-workspace-libs', 'libkworkspace6'}
# The vendor source also produces its existing theme/doc subpackages. Replace
# them only if the edition already owns them; the final identity scrub still
# removes the vendor theme. Never publish those names in the runtime receipt.
VENDOR_PACKAGES = CORE | {'plasma-workspace-doc', 'plasma-lookandfeel-fedora', 'sddm-wayland-plasma'}


def source_review(base):
    """Exact vendor NVRs only. A newer release is a review, never a fallback."""
    registry = json.loads(Path(__file__).with_name('sources.json').read_text())
    assert registry['schema'] == 1
    reviews = registry['sources']
    assert len({entry['base'] for entry in reviews}) == len(reviews), 'duplicate source NVR'
    for entry in reviews:
        assert re.fullmatch(r'6\.[0-9]+\.[0-9]+-[0-9]+\.fc44', entry['base'])
        assert entry['fixed'] == entry['base'].replace('.fc44', '.1.moos1.fc44')
        for key in ('source_sha256', 'prepared_shutdown_sha256'):
            assert re.fullmatch(r'[a-f0-9]{64}', entry[key])
        assert entry['source_url'].startswith((
            'https://kojipkgs.fedoraproject.org/packages/plasma-workspace/',
            'https://download.copr.fedorainfracloud.org/results/@kdesig/kde-beta/',
            'https://download.copr.fedorainfracloud.org/results/@kdesig/kde-final/'))
        assert entry['source_url'].endswith(f'/plasma-workspace-{entry["base"]}.src.rpm')
    matches = [entry for entry in reviews if entry['base'] == base]
    assert len(matches) == 1, f'unreviewed Plasma source NVR: {base}'
    return matches[0]


def command(argv):
    return subprocess.check_output(argv, text=True).strip()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metadata(path):
    return command(['rpm', '-qp', '--qf', '%{NAME} %{VERSION}-%{RELEASE} %{ARCH}', str(path)]).split()


def collect(folder, output):
    arch = command(['rpm', '--eval', '%{_arch}'])
    assert arch in ('x86_64', 'aarch64'), arch
    review = source_review(command(['rpm', '-q', '--qf', '%{VERSION}-%{RELEASE}', 'plasma-workspace']))
    packages = []
    for package in sorted(folder.rglob('*.rpm')):
        name, version, target = metadata(package)
        if any(name.endswith(end) for end in ('-devel', '-debuginfo', '-debugsource')):
            continue
        assert name in VENDOR_PACKAGES and version == review['fixed'] and target in (arch, 'noarch'), (name, version, target)
        destination = output / package.name
        shutil.copy2(package, destination)
        packages.append({'name': name, 'file': package.name, 'arch': target, 'sha256': sha(destination)})
    assert CORE <= {item['name'] for item in packages}
    (output / 'manifest.json').write_text(json.dumps({
        'schema': 1, 'base': review['base'], 'fixed': review['fixed'], 'arch': arch,
        'source_sha256': review['source_sha256'], 'packages': packages,
    }, indent=2) + '\n')


def install(folder, root=Path('/')):
    manifest = json.loads((folder / 'manifest.json').read_text())
    arch = command(['rpm', '--eval', '%{_arch}'])
    review = source_review(manifest['base'])
    assert manifest['schema'] == 1 and manifest['arch'] == arch
    assert manifest['fixed'] == review['fixed']
    assert manifest['source_sha256'] == review['source_sha256']
    installed = set(command(['rpm', '-qa', '--qf', '%{NAME}\n']).splitlines())
    owned = installed & VENDOR_PACKAGES
    assert CORE <= owned, 'missing native Plasma runtime package'
    for name in sorted(owned):
        current = command(['rpm', '-q', '--qf', '%{VERSION}-%{RELEASE}', name])
        assert current == review['base'], f'unreviewed Plasma package {name}: {current}'
        source = command(['rpm', '-q', '--qf', '%{SOURCERPM}', name])
        assert source == f'plasma-workspace-{review["base"]}.src.rpm', f'unreviewed Plasma source {name}: {source}'
    selected = []
    names = set()
    for item in manifest['packages']:
        if item['name'] not in owned:
            continue
        path = folder / item['file']
        assert path.parent == folder and path.is_file() and not path.is_symlink()
        assert item['name'] not in names, 'duplicate subpackage'
        assert sha(path) == item['sha256']
        assert metadata(path) == [item['name'], review['fixed'], item['arch']]
        names.add(item['name'])
        selected.append(path)
    assert names == owned, 'missing installed Plasma subpackage'
    subprocess.run(['dnf5', '-y', 'install', '--setopt=install_weak_deps=False',
                    '--exclude=kernel,kernel-core,kernel-modules,kernel-modules-core,kernel-modules-extra',
                    *map(str, selected)], check=True)
    for name in sorted(owned):
        actual = command(['rpm', '-q', '--qf', '%{VERSION}-%{RELEASE}', name])
        assert actual == review['fixed'], f'logout fix did not reach {name}: {actual}'
    worker = root / 'usr/bin/plasma-shutdown'
    record = {'schema': 1, 'base': review['base'], 'fixed': review['fixed'], 'source_sha256': review['source_sha256'],
              'worker_sha256': sha(worker), 'packages': sorted(owned & CORE)}
    target = root / 'usr/share/moos/plasma-logout-transaction.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(record, indent=2) + '\n')
    print('MoOS native Plasma logout transaction installed and read back')


def verify(root=Path('/')):
    record = json.loads((root / 'usr/share/moos/plasma-logout-transaction.json').read_text())
    review = source_review(record['base'])
    assert record['schema'] == 1 and record['fixed'] == review['fixed']
    assert record['source_sha256'] == review['source_sha256']
    worker = root / 'usr/bin/plasma-shutdown'
    assert sha(worker) == record['worker_sha256'], 'logout worker changed after package install'
    activation = (root / 'usr/share/dbus-1/services/org.kde.Shutdown.service').read_text().splitlines()
    assert activation.count('Exec=/usr/bin/plasma-shutdown') == 1, 'D-Bus does not launch the verified worker'
    for name in record['packages']:
        assert command(['rpm', '-q', '--qf', '%{VERSION}-%{RELEASE}', name]) == review['fixed']
    # Read the RPM database's own payload digest as well as our install receipt.
    rows = command(['rpm', '-q', '--dump', 'plasma-workspace']).splitlines()
    matches = [row.split() for row in rows if row.split()[0] == '/usr/bin/plasma-shutdown']
    assert len(matches) == 1 and matches[0][3] == sha(worker), 'worker differs from its native RPM'
    print('MoOS native Plasma logout RPM and final worker bytes verified')


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == 'source':
        print(json.dumps(source_review(sys.argv[2])))
    elif len(sys.argv) == 4 and sys.argv[1] == 'collect':
        collect(Path(sys.argv[2]), Path(sys.argv[3]))
    elif len(sys.argv) == 3 and sys.argv[1] == 'install':
        install(Path(sys.argv[2]))
    elif len(sys.argv) == 2 and sys.argv[1] == 'verify':
        verify()
    else:
        raise SystemExit('usage: rpms.py source NVR | collect INPUT OUTPUT | install INPUT | verify')
