#!/usr/bin/env python3
"""Admit the exact signed sensor module package in a compose container only.

Image assembly checks integrity; machine-trust and hardware acceptance remain required.
It never enrolls keys or loads a module. All ordinary image/boot gates still apply.
"""
import argparse
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile

from module import (CERTIFICATE, KERNEL, KERNEL_EVR, KERNEL_VERSION, PACKAGE_RELEASE,
                    RELATIVE, VENDOR, metadata, regular,
                    require, run, sha, unpack, verify_signature)

HERE = Path(__file__).resolve().parent
NAME = 'kmod-moos-smocf05'
NVR = f'{NAME}-{KERNEL_VERSION}-{PACKAGE_RELEASE}'
MANIFEST = json.loads((HERE / 'manifest.json').read_text())
FILES = {RELATIVE, CERTIFICATE, f'usr/share/licenses/{NAME}/COPYING',
         f'usr/share/licenses/{NAME}/GPL-2.0', f'usr/share/doc/{NAME}/PROVENANCE.json'}
REQUIRES = {f'kernel-uname-r = {KERNEL}', f'kernel-modules-core = {KERNEL_EVR}'}


def certificate():
    require(sha(regular(HERE / 'module.der', 100000)) ==
            MANIFEST['certificate_der_sha256'] ==
            'b8c98812edf59a6e3e96321a5dcd718cf70204baa25af00189d3fa8cc4d1a535',
            'production certificate drift')
    der = subprocess.run(['openssl', 'x509', '-in', str(HERE / 'module.pem'),
                          '-outform', 'DER'], check=True, capture_output=True, timeout=10).stdout
    require(der == (HERE / 'module.der').read_bytes(), 'PEM/DER certificate mismatch')


def extracted(root):
    certificate()
    module = regular(root / RELATIVE)
    require(sha(module) == MANIFEST['compressed_sha256'], 'packaged module bytes changed')
    data = unpack(module)
    import hashlib
    require(hashlib.sha256(data).hexdigest() == MANIFEST['signed_sha256'],
            'signed module bytes changed')
    require(verify_signature(data, HERE / 'module.pem') == MANIFEST['stripped_sha256'],
            'packaged signature/payload mismatch')
    require(sha(regular(root / CERTIFICATE, 100000)) == MANIFEST['certificate_der_sha256'],
            'packaged public certificate drift')
    result = metadata(module)
    require('acpi*:SMOCF05:*' in result['alias'], 'missing SMOCF05 alias')
    provenance = json.loads((root / f'usr/share/doc/{NAME}/PROVENANCE.json').read_text())
    for field in ('schema', 'kernel', 'upstream_commit', 'compiled_sha256', 'stripped_sha256',
                  'signed_sha256', 'compressed_sha256', 'certificate_der_sha256', 'native_proof_sha256'):
        require(provenance[field] == MANIFEST[field], 'packaged provenance drift: ' + field)
    require(b'GNU GENERAL PUBLIC LICENSE' in
            (root / f'usr/share/licenses/{NAME}/GPL-2.0').read_bytes(), 'missing full GPL text')
    return result


def package_check(package):
    package = regular(package, 1000000)
    require(sha(package) == MANIFEST['rpm_sha256'] and
            package.stat().st_size == MANIFEST['rpm_bytes'], 'RPM bytes drift')
    require(run(['rpm', '-qp', '--qf', '%{NAME}-%{VERSION}-%{RELEASE}.%{ARCH}', str(package)]) ==
            NVR + '.x86_64', 'unexpected RPM identity')
    paths = run(['rpm', '-qpl', str(package)]).splitlines()
    require(len(paths) == len(FILES) and set(paths) == {'/' + name for name in FILES},
            'unexpected RPM file set')
    for line in run(['rpm', '-qp', '--dump', str(package)]).splitlines():
        columns = line.split()
        require(len(columns) == 11 and columns[0] in paths and
                int(columns[4], 8) == stat.S_IFREG | 0o644 and
                columns[5:7] == ['root', 'root'] and columns[10] == 'X',
                'unsafe RPM payload metadata')
    require(not run(['rpm', '-qp', '--scripts', str(package)]) and
            not run(['rpm', '-qp', '--triggers', str(package)]), 'unexpected RPM script/trigger')
    requirements = set(run(['rpm', '-qp', '--requires', str(package)]).splitlines())
    require(REQUIRES <= requirements and all(item in REQUIRES or item.startswith('rpmlib(')
            for item in requirements), 'unexpected RPM dependencies')
    with tempfile.TemporaryDirectory(prefix='moos-sensor-rpm-') as directory:
        root = Path(directory)
        with tempfile.TemporaryFile() as archive:
            subprocess.run(['rpm2cpio', str(package)], check=True, stdout=archive, timeout=30)
            archive.seek(0)
            subprocess.run(['cpio', '-idm', '--quiet', '--no-absolute-filenames',
                            '--no-preserve-owner'], cwd=root, stdin=archive, check=True, timeout=30)
        return extracted(root)


def vendor_baseline():
    root = Path('/usr/lib/modules') / KERNEL
    require(run(['rpm', '-q', '--qf', '%{VERSION}-%{RELEASE}.%{ARCH}', 'kernel-core']) == KERNEL and
            run(['rpm', '-q', '--qf', '%{VERSION}-%{RELEASE}.%{ARCH}', 'kernel-modules-core']) == KERNEL,
            'kernel/core package does not match reviewed ABI')
    paths = {'vendor_kernel_sha256': root / 'vmlinuz',
             'vendor_core_sha256': root / 'kernel/drivers/iio/imu/st_lsm6dsx/st_lsm6dsx.ko.xz',
             'vendor_transport_sha256': Path('/') / VENDOR}
    for field, path in paths.items():
        require(sha(regular(path, 30 * 1024 * 1024)) == MANIFEST[field], 'stock kernel/module drift: ' + field)
    return {field: sha(path) for field, path in paths.items()}


def resolution():
    selected = Path(run(['modinfo', '-k', KERNEL, '-n', 'st_lsm6dsx_i2c']))
    require(selected.resolve() == (Path('/') / RELATIVE).resolve(), 'depmod selected another transport')
    require(run(['modprobe', '-S', KERNEL, '--resolve-alias', 'acpi:SMOCF05:']) ==
            'st_lsm6dsx_i2c', 'SMOCF05 alias not uniquely resolved')
    lines = run(['modprobe', '-S', KERNEL, '--show-depends', 'st_lsm6dsx_i2c']).splitlines()
    require(any(line.startswith('insmod ') and Path(line.split()[1]).resolve() ==
                (Path('/') / RELATIVE).resolve() for line in lines), 'missing override dependency')
    require(any(line.startswith('insmod ') and '/kernel/drivers/iio/imu/st_lsm6dsx/st_lsm6dsx.ko' in
                line for line in lines), 'missing vendor core dependency')
    return lines


def compose(package):
    require(os.getuid() == 0 and os.environ.get('MOOS_SENSOR_COMPOSE') == '1' and
            Path('/run/.containerenv').is_file() and not Path('/run/ostree-booted').exists(),
            'sensor package installation is restricted to an explicit compose container')
    baseline = vendor_baseline()
    require(not (Path('/') / RELATIVE).exists() and not (Path('/') / RELATIVE).is_symlink(),
            'refuse existing module override')
    require(not run(['find', '/usr/lib/modules/' + KERNEL + '/updates',
                     '-name', 'st_lsm6dsx_i2c.ko*']) if Path('/usr/lib/modules/' + KERNEL + '/updates').exists()
            else True, 'existing transport override')
    package_check(package)
    run(['rpm', '-Uvh', '--test', str(package)])
    run(['rpm', '-Uvh', str(package)])
    require(not run(['rpm', '-V', NAME]), 'installed module RPM verification failed')
    require(vendor_baseline() == baseline, 'vendor kernel/module changed during transaction')
    result = extracted(Path('/'))
    vendor = metadata(Path('/') / VENDOR)
    require(set(result['alias']) - set(vendor['alias']) == {'acpi*:SMOCF05:*'} and
            not set(vendor['alias']) - set(result['alias']), 'vendor alias loss or extra change')
    run(['depmod', '-a', KERNEL])
    proof = {'schema': 1, 'rpm_sha256': sha(package), 'vendor_bytes_unchanged': True,
             'selected': RELATIVE, 'dependencies': resolution(), 'signature_verified': True,
             'kernel_trust': False, 'module_loaded': False, 'physical_sensor_acceptance': False}
    receipt = Path('/usr/share/moos/hardware/smocf05-module.json')
    require(not receipt.exists() and not receipt.is_symlink(), 'existing module receipt')
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps(proof))


def installed():
    vendor_baseline()
    require(run(['rpm', '-q', '--qf', '%{NAME}-%{VERSION}-%{RELEASE}.%{ARCH}', NAME]) ==
            NVR + '.x86_64', 'installed RPM identity drift')
    require(not run(['rpm', '-V', NAME]), 'installed RPM bytes changed')
    extracted(Path('/'))
    resolution()
    receipt = json.loads(regular(Path('/usr/share/moos/hardware/smocf05-module.json')).read_text())
    require(receipt['signature_verified'] is True and receipt['vendor_bytes_unchanged'] is True and
            receipt['rpm_sha256'] == MANIFEST['rpm_sha256'] and receipt['kernel_trust'] is False and
            receipt['module_loaded'] is False and receipt['physical_sensor_acceptance'] is False,
            'invalid module build receipt or unproved runtime claim')
    print('MoOS: exact sensor module package/signature/depmod verified; native trust/probe remain separate')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('check-package', 'compose', 'verify-installed'))
    parser.add_argument('package', type=Path, nargs='?')
    args = parser.parse_args()
    package = args.package.absolute() if args.package else None
    if args.action == 'verify-installed':
        require(package is None, 'verify-installed takes no package')
        installed()
    elif args.action == 'compose':
        require(package is not None, 'missing RPM')
        compose(package)
    else:
        require(package is not None, 'missing RPM')
        print(json.dumps(package_check(package)))
