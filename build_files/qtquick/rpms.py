#!/usr/bin/python3
"""Exact vendor QtDeclarative backport, native RPM admission and final readback."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
NAME = 'qt6-qtdeclarative'
PACKAGES = {NAME, NAME + '-devel', NAME + '-static', NAME + '-examples'}
DEBUG = {NAME + '-debugsource'} | {name + '-debuginfo' for name in PACKAGES}
QUICK = Path('/usr/lib64/libQt6Quick.so.6.11.2')
RECEIPT = Path('/usr/share/moos/qtquick-itemview-lifetime.json')
ITEMVIEW = Path('src/quick/items/qquickitemview.cpp')


def require(value, message):
    if not value:
        raise ValueError(message)


def command(argv):
    return subprocess.check_output(argv, text=True).strip()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def review(base):
    data = json.loads((HERE / 'sources.json').read_text())
    require(data['schema'] == 1 and base == data['base'] == '6.11.2-2.fc44',
            f'unreviewed Qt source: {base}')
    require(data['fixed'] == '6.11.2-2.1.moos1.fc44', 'unexpected Qt fixed NVR')
    require(data['architectures'] == ['x86_64', 'aarch64'], 'unreviewed Qt architecture')
    require(data['upstream_commit'] == '83d091dcb160d3f0c4a8bc9df8b8a9a934ac82a1',
            'unexpected Qt upstream correction')
    require(data['source_signer'] == '36f612dcf27f7d1a48a835e4dbfcf71c6d9f90a6',
            'unreviewed Qt publisher key')
    require(data['source_url'] == ('https://kojipkgs.fedoraproject.org/packages/'
            'qt6-qtdeclarative/6.11.2/2.fc44/data/signed/6d9f90a6/src/'
            'qt6-qtdeclarative-6.11.2-2.fc44.src.rpm'), 'unreviewed Qt source URL')
    for key, value in data.items():
        if key.endswith('_sha256'):
            require(isinstance(value, str) and re.fullmatch('[a-f0-9]{64}', value), key)
    return data


def architecture():
    arch = command(['rpm', '--eval', '%{_arch}'])
    require(arch in review('6.11.2-2.fc44')['architectures'], f'unreviewed architecture: {arch}')
    return arch


def sdk(base):
    data = review(base)
    for name in (NAME, NAME + '-devel'):
        require(command(['rpm', '-q', '--qf', '%{VERSION}-%{RELEASE}', name]) == data['base'],
                f'native Qt proof SDK differs from reviewed runtime: {name}')
    require(command(['pkg-config', '--modversion', 'Qt6Quick']) == '6.11.2',
            'native Qt proof requires the reviewed Qt6Quick development package')


def prepare_spec(source, destination):
    data = review('6.11.2-2.fc44')
    require(sha(source) == data['spec_sha256'], 'vendor Qt spec drift')
    text = source.read_text()
    require(text.count('Release: 2%{?dist}') == 1, 'vendor Qt release drift')
    text = text.replace('Release: 2%{?dist}', 'Release: 2.1.moos1%{?dist}')
    require(text.count('%description\n') == 1 and text.count('%build\n') == 1,
            'vendor Qt spec section drift')
    text = text.replace('%description\n', 'Patch2001: moos-itemview-lifetime.patch\n\n%description\n', 1)
    # The entire original spec, configure arguments, compiler flags, subpackages,
    # license installation and vendor patch remain. Only this source hunk changes.
    text = text.replace('%build\n', '%build\npython3 /src/build_files/qtquick/rpms.py prepared\n', 1)
    destination.write_text(text)


def prepared():
    require(sha(ITEMVIEW) == review('6.11.2-2.fc44')['fixed_itemview_sha256'],
            'prepared Qt item-view source differs from reviewed upstream backport')
    print('MoOS: exact Qt item-view upstream backport verified')


def metadata(path):
    return command(['rpm', '-qp', '--qf', '%{NAME} %{VERSION}-%{RELEASE} %{ARCH} %{SOURCERPM}', str(path)]).split()


def package_payload(path):
    rows = command(['rpm', '-qp', '--dump', str(path)]).splitlines()
    matches = [row.split() for row in rows if row.split()[0] == str(QUICK)]
    require(len(matches) == 1 and re.fullmatch('[a-f0-9]{64}', matches[0][3]),
            'RPM has no unique SHA256 QtQuick payload')
    return matches[0][3]


def native(probe, qml, quick, imports):
    spec = importlib.util.spec_from_file_location('qtquick_native', HERE / 'native-proof.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.run(probe, qml, quick, 'pass', imports)


def extract(package, target):
    # Owned native RPM only; do not accept traversal even from a build artifact.
    files = command(['rpm', '-qpl', str(package)]).splitlines()
    require(files and all(name.startswith('/') and '..' not in Path(name).parts for name in files),
            'unsafe RPM file list')
    with tempfile.TemporaryFile() as archive:
        subprocess.run(['rpm2cpio', str(package)], stdout=archive, check=True)
        archive.seek(0)
        subprocess.run(['cpio', '-idm', '--quiet', '--no-absolute-filenames', '--no-preserve-owner'],
                       stdin=archive, cwd=target, check=True)


def collect(folder, output, probe):
    data = review(command(['rpm', '-q', '--qf', '%{VERSION}-%{RELEASE}', NAME]))
    arch = architecture()
    expected_source = f'{NAME}-{data["fixed"]}.src.rpm'
    candidates = {}
    for path in sorted(folder.rglob('*.rpm')):
        require(path.is_file() and not path.is_symlink(), 'linked RPM input')
        name, version, target, source = metadata(path)
        require(name in PACKAGES | DEBUG and version == data['fixed'] and target == arch
                and source == expected_source, f'unreviewed Qt RPM: {path.name}')
        if name in DEBUG:
            continue
        require(name not in candidates, 'duplicate Qt RPM')
        candidates[name] = path
    require(set(candidates) == PACKAGES, 'incomplete original Qt RPM build')
    require(probe.is_file() and not probe.is_symlink(), 'missing native Qt probe')
    with tempfile.TemporaryDirectory(prefix='moos-qt-package-') as temp:
        stage = Path(temp)
        extract(candidates[NAME], stage)
        quick = stage / QUICK.relative_to('/')
        digest = package_payload(candidates[NAME])
        require(sha(quick) == digest, 'extracted QtQuick differs from native RPM')
        proof = native(probe, HERE / 'teardown.qml', quick, stage / 'usr/lib64/qt6/qml')
    require(not output.exists() or not list(output.iterdir()), 'Qt output already occupied')
    output.mkdir(parents=True, exist_ok=True)
    packages = []
    for name, path in sorted(candidates.items()):
        destination = output / path.name
        shutil.copy2(path, destination)
        packages.append({'name': name, 'file': path.name, 'sha256': sha(destination)})
    shutil.copy2(probe, output / 'teardown-probe')
    shutil.copy2(HERE / 'teardown.qml', output / 'teardown.qml')
    manifest = {**data, 'arch': arch, 'packages': packages, 'quick_sha256': digest,
                'probe_sha256': sha(output / 'teardown-probe'),
                'qml_sha256': sha(output / 'teardown.qml'), 'native_proof': proof}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')


def owned_packages(data, arch):
    rows = command(['rpm', '-qa', '--qf', '%{NAME} %{VERSION}-%{RELEASE} %{ARCH} %{SOURCERPM}\n'])
    owned = {}
    for row in rows.splitlines():
        fields = row.split()
        if fields[0] not in PACKAGES:
            continue
        name, version, target, source = fields
        require(name not in owned and version == data['base'] and target == arch
                and source == f'{NAME}-{data["base"]}.src.rpm', f'installed Qt drift: {row}')
        owned[name] = fields
    require(NAME in owned, 'native QtDeclarative runtime is unavailable')
    return owned


def validate_manifest(folder):
    require(folder.is_dir() and not folder.is_symlink(), 'linked/missing Qt artifact directory')
    manifest = json.loads((folder / 'manifest.json').read_text())
    data = review(manifest['base'])
    arch = architecture()
    require(all(manifest.get(key) == value for key, value in data.items()), 'Qt source receipt drift')
    require(manifest['arch'] == arch, 'wrong Qt artifact architecture')
    owned = owned_packages(data, arch)
    paths = {}
    for item in manifest['packages']:
        name, filename = item['name'], item['file']
        require(name in PACKAGES and name not in paths and filename == Path(filename).name,
                'unknown/duplicate/traversing Qt package')
        path = folder / filename
        require(path.is_file() and not path.is_symlink() and sha(path) == item['sha256'],
                'Qt RPM digest/path mismatch')
        require(metadata(path) == [name, data['fixed'], arch, f'{NAME}-{data["fixed"]}.src.rpm'],
                'Qt RPM metadata mismatch')
        paths[name] = path
    require(set(paths) == PACKAGES, 'incomplete Qt artifact set')
    require(package_payload(paths[NAME]) == manifest['quick_sha256'], 'QtQuick payload receipt mismatch')
    for filename, key in [('teardown-probe', 'probe_sha256'), ('teardown.qml', 'qml_sha256')]:
        path = folder / filename
        require(path.is_file() and not path.is_symlink() and sha(path) == manifest[key],
                'native Qt proof artifact mismatch')
    require(manifest['native_proof']['exit'] == 0
            and manifest['native_proof']['destruction_executed'] is True, 'missing packaged Qt proof')
    return data, manifest, {name: paths[name] for name in owned}


def install(folder):
    require(Path('/run/.containerenv').exists() or Path('/.dockerenv').exists(),
            'Qt RPM installation is image-build-only; never mutate the physical host')
    data, manifest, selected = validate_manifest(folder)
    core = Path('/usr/lib64/libQt6Core.so.6').resolve()
    core_digest = sha(core)
    subprocess.run(['dnf5', '-y', 'install', '--setopt=install_weak_deps=False',
                    '--exclude=kernel*', *map(str, selected.values())], check=True)
    require(sha(core) == core_digest, 'QtCore changed during the QtDeclarative transaction')
    for name in selected:
        require(command(['rpm', '-q', '--qf', '%{VERSION}-%{RELEASE} %{ARCH} %{SOURCERPM}', name])
                == f'{data["fixed"]} {manifest["arch"]} {NAME}-{data["fixed"]}.src.rpm',
                'Qt RPM install/readback mismatch')
    verify_payload(manifest['quick_sha256'])
    proof = native(folder / 'teardown-probe', folder / 'teardown.qml', QUICK,
                   Path('/usr/lib64/qt6/qml'))
    record = {**data, 'arch': manifest['arch'], 'packages': sorted(selected),
              'quick_sha256': sha(QUICK), 'native_proof': proof}
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps(record, indent=2) + '\n')
    print('MoOS: native QtQuick teardown RPM installed and regression executed')


def verify_payload(digest):
    require(QUICK.is_file() and not QUICK.is_symlink() and sha(QUICK) == digest,
            'QtQuick runtime bytes differ from receipt')
    rows = command(['rpm', '-q', '--dump', NAME]).splitlines()
    matches = [row.split() for row in rows if row.split()[0] == str(QUICK)]
    require(len(matches) == 1 and matches[0][3] == digest, 'QtQuick differs from installed RPM payload')


def verify():
    record = json.loads(RECEIPT.read_text())
    data = review(record['base'])
    require(all(record.get(key) == value for key, value in data.items()), 'Qt final source receipt drift')
    require(record['arch'] == architecture(), 'Qt final architecture drift')
    names = record['packages']
    require(isinstance(names, list) and NAME in names and len(set(names)) == len(names)
            and set(names) <= PACKAGES, 'Qt final package set drift')
    for name in names:
        require(command(['rpm', '-q', '--qf', '%{VERSION}-%{RELEASE} %{ARCH} %{SOURCERPM}', name])
                == f'{data["fixed"]} {record["arch"]} {NAME}-{data["fixed"]}.src.rpm',
                'Qt final RPM drift')
    require(record['native_proof']['exit'] == 0
            and record['native_proof']['destruction_executed'] is True, 'missing installed Qt proof')
    verify_payload(record['quick_sha256'])
    print('MoOS: final native QtQuick RPM, payload and executed-proof receipt verified')


if __name__ == '__main__':
    mode, *args = sys.argv[1:]
    if mode == 'source' and len(args) == 1:
        print(json.dumps(review(args[0])))
    elif mode == 'sdk' and len(args) == 1:
        sdk(args[0])
    elif mode == 'prepare-spec' and len(args) == 2:
        prepare_spec(*map(Path, args))
    elif mode == 'prepared' and not args:
        prepared()
    elif mode == 'collect' and len(args) == 3:
        collect(*map(Path, args))
    elif mode == 'install' and len(args) == 1:
        install(Path(args[0]))
    elif mode == 'verify' and not args:
        verify()
    else:
        raise SystemExit('usage: source NVR | sdk NVR | prepare-spec IN OUT | prepared | collect RPMS OUT PROBE | install OUT | verify')
