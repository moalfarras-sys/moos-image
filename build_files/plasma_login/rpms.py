#!/usr/bin/python3
"""Exact vendor-source frontend rebuild; never replace the PAM/daemon backend."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
PACKAGES = {'plasma-login-manager', 'kcm-plasmalogin'}
KCM = Path('/usr/lib64/qt6/plugins/plasma/kcms/systemsettings/kcm_plasmalogin.so')


def command(arguments):
    return subprocess.check_output(arguments, text=True).strip()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def review(base):
    data = json.loads((HERE / 'sources.json').read_text())
    assert data['schema'] == 1 and base == data['base'], f'unreviewed login-manager source: {base}'
    assert data['base'] == '6.8.1-1.fc44' and data['fixed'] == '6.8.1-1.2.moos1.fc44'
    assert data['arch'] == 'x86_64'
    assert data['source_url'] == ('https://download.copr.fedorainfracloud.org/results/@kdesig/kde-final/'
                                  'fedora-44-x86_64/Packages/p/plasma-login-manager-6.8.1-1.fc44.src.rpm')
    for key in ('source_sha256', 'authentication_source_sha256'):
        assert re.fullmatch(r'[a-f0-9]{64}', data[key])
    assert data['source_signer'] == '96bdf4e8710b8f9ffb11d83ddb51f4cb6c33bdbb'
    return data


def prepared():
    expected = json.loads((HERE / 'prepared-files.json').read_text())
    for filename, digest in expected.items():
        assert filename.startswith('src/frontend/') and '..' not in Path(filename).parts
        assert sha(Path(filename)) == digest, filename
    auth = {}
    for folder in ('src/auth', 'src/helper', 'src/daemon'):
        for path in sorted(Path(folder).rglob('*')):
            if path.is_file():
                auth[str(path)] = sha(path)
    assert auth
    digest = hashlib.sha256(json.dumps(auth, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    assert digest == review('6.8.1-1.fc44')['authentication_source_sha256'], 'native authentication sources changed'
    print('MoOS: exact frontend source and unchanged vendor authentication/helper/daemon verified')


def metadata(path):
    return command(['rpm', '-qp', '--qf', '%{NAME} %{VERSION}-%{RELEASE} %{ARCH}', str(path)]).split()


def collect(folder, output):
    data = review(command(['rpm', '-q', '--qf', '%{VERSION}-%{RELEASE}', 'plasma-login-manager']))
    assert command(['rpm', '--eval', '%{_arch}']) == data['arch']
    output.mkdir(parents=True, exist_ok=True)
    packages = []
    for path in sorted(folder.rglob('*.rpm')):
        name, version, arch = metadata(path)
        if name.endswith(('-devel', '-debuginfo', '-debugsource')):
            continue
        assert name in PACKAGES and version == data['fixed'] and arch == data['arch']
        shutil.copy2(path, output / path.name)
        packages.append({'name': name, 'file': path.name, 'sha256': sha(output / path.name)})
    assert {entry['name'] for entry in packages} == PACKAGES and len(packages) == len(PACKAGES)
    (output / 'manifest.json').write_text(json.dumps({**data, 'packages': packages}, indent=2) + '\n')


def validate_manifest(folder):
    manifest = json.loads((folder / 'manifest.json').read_text())
    data = review(manifest['base'])
    assert all(manifest[key] == value for key, value in data.items())
    assert command(['rpm', '--eval', '%{_arch}']) == data['arch']
    selected = []
    names = set()
    for entry in manifest['packages']:
        name = entry['name']
        assert name in PACKAGES and name not in names
        current = command(['rpm', '-q', '--qf', '%{VERSION}-%{RELEASE} %{SOURCERPM}', name]).split()
        assert current == [data['base'], f'plasma-login-manager-{data["base"]}.src.rpm']
        path = folder / entry['file']
        assert path.parent == folder and path.is_file() and not path.is_symlink()
        assert sha(path) == entry['sha256']
        assert metadata(path) == [name, data['fixed'], data['arch']]
        selected.append(str(path))
        names.add(name)
    assert names == PACKAGES
    return data, selected


def install(folder):
    data, selected = validate_manifest(folder)
    subprocess.run(['dnf5', '-y', 'install', '--setopt=install_weak_deps=False',
                    '--exclude=kernel*', *selected], check=True)
    for name in PACKAGES:
        assert command(['rpm', '-q', '--qf', '%{VERSION}-%{RELEASE}', name]) == data['fixed']
    worker = Path('/usr/libexec/plasma-login-greeter')
    receipt = Path('/usr/share/moos/plasma-login-automatic-fingerprint.json')
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text(json.dumps({**data, 'greeter_sha256': sha(worker),
                                  'kcm_sha256': sha(KCM)}, indent=2) + '\n')
    print('MoOS: native automatic fingerprint frontend installed with vendor backend retained')


def verify_payload(package, path):
    rows = command(['rpm', '-q', '--dump', package]).splitlines()
    matches = [row.split() for row in rows if row.split()[0] == str(path)]
    assert len(matches) == 1 and matches[0][3] == sha(path), str(path)


def verify():
    record = json.loads(Path('/usr/share/moos/plasma-login-automatic-fingerprint.json').read_text())
    data = review(record['base'])
    assert all(record[key] == value for key, value in data.items())
    worker = Path('/usr/libexec/plasma-login-greeter')
    assert sha(worker) == record['greeter_sha256']
    assert sha(KCM) == record['kcm_sha256']
    for name in PACKAGES:
        assert command(['rpm', '-q', '--qf', '%{VERSION}-%{RELEASE}', name]) == data['fixed']
    verify_payload('plasma-login-manager', worker)
    verify_payload('kcm-plasmalogin', KCM)
    for helper in ('moos-configure-fingerprint-login', 'moos-login-fingerprint-capabilities'):
        assert Path('/usr/libexec', helper).is_file()
    dropin = Path('/usr/lib/systemd/system/plasmalogin.service.d/60-moos-fingerprint-auto.conf').read_text()
    assert 'ExecStartPre=-/usr/libexec/moos-login-fingerprint-capabilities' in dropin
    subprocess.run(['/usr/libexec/moos-configure-fingerprint-login', '--check'], check=True)
    print('MoOS: final greeter RPM bytes, policy and optional enrollment activation verified')


if __name__ == '__main__':
    mode = sys.argv[1]
    if mode == 'source':
        print(json.dumps(review(sys.argv[2])))
    elif mode == 'prepared':
        prepared()
    elif mode == 'collect':
        collect(Path(sys.argv[2]), Path(sys.argv[3]))
    elif mode == 'install':
        install(Path(sys.argv[2]))
    elif mode == 'verify':
        verify()
    else:
        raise SystemExit('source NVR | prepared | collect INPUT OUTPUT | install INPUT | verify')
