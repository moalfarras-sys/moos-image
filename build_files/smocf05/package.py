#!/usr/bin/env python3
"""Package the exact compiled backport with an external protected module key.

No installation, enrollment or private key publication. The resulting RPM is
admitted by exact bytes plus the pinned module signature inside the signed OS.
"""
import argparse
import hashlib
import importlib.util
import json
import lzma
import os
from pathlib import Path
import shutil
import stat
import subprocess

from module import (CERTIFICATE, KERNEL, KERNEL_EVR, KERNEL_VERSION, PACKAGE_RELEASE, RELATIVE,
                    metadata, regular, require, run, sha, verify_signature)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
NAME = 'kmod-moos-smocf05'
NVR = f'{NAME}-{KERNEL_VERSION}-{PACKAGE_RELEASE}'
TARBALL = f'linux-{KERNEL_VERSION}.tar.xz'


def build(module, proof_file, key, output):
    require(os.geteuid() != 0, 'run as the mapped owner, not toolbox root')
    module, proof_file, key = map(regular, (module, proof_file, key))
    require(key.stat().st_uid == os.getuid() and stat.S_IMODE(key.stat().st_mode) == 0o600,
            'signing key must be owned by caller and mode0600')
    proof = json.loads(proof_file.read_text())
    require(proof['kernel'] == KERNEL and proof['fixed']['sha256'] == sha(module),
            'compiled module does not match native old/fixed build receipt')
    original = metadata(module)
    require(set(original['alias']) - set(proof['old']['alias']) == {'acpi*:SMOCF05:*'} and
            not set(proof['old']['alias']) - set(original['alias']), 'unexpected alias delta')
    require(sha(HERE / 'module.der') == 'b8c98812edf59a6e3e96321a5dcd718cf70204baa25af00189d3fa8cc4d1a535',
            'production certificate bytes changed')
    output.mkdir(mode=0o700)
    sources = output / 'SOURCES'
    sources.mkdir()
    plain = output / 'st_lsm6dsx_i2c.ko'
    shutil.copyfile(module, plain)
    run(['strip', '--strip-debug', str(plain)])  # Strip before signing; never afterwards.
    stripped = sha(plain)
    require(metadata(plain) == original, 'stripping changed module metadata')
    sign_file = Path('/usr/src/kernels') / KERNEL / 'scripts/sign-file'
    run([str(sign_file), 'sha256', str(key), str(HERE / 'module.pem'), str(plain)])
    require(verify_signature(plain.read_bytes(), HERE / 'module.pem') == stripped,
            'signed payload differs from stripped module')
    compressed = sources / 'st_lsm6dsx_i2c.ko.xz'
    compressed.write_bytes(lzma.compress(plain.read_bytes(), preset=6, check=lzma.CHECK_CRC32))
    shutil.copyfile(HERE / 'module.der', sources / 'module.der')
    # The native SRPM archive is supplied by the build receipt's existing tree.
    import tarfile
    archive = proof_file.parent / 'source-rpm' / TARBALL
    expected_archive = json.loads((ROOT / 'scripts/review/smocf05-module.json').read_text())['source_members'][TARBALL]
    require(sha(archive) == expected_archive, 'unreviewed license source archive')
    license_names = {'COPYING': 'COPYING', 'LICENSES/preferred/GPL-2.0': 'GPL-2.0'}
    with tarfile.open(archive, 'r|xz') as source:
        for member in source:
            if member.name in {f'linux-{KERNEL_VERSION}/' + name for name in license_names}:
                require(member.isfile() and 0 < member.size < 50000, 'invalid license member')
                name = license_names[member.name.removeprefix(f'linux-{KERNEL_VERSION}/')]
                (sources / name).write_bytes(source.extractfile(member).read())
    for name in license_names.values():
        regular(sources / name, 50000)
    provenance = {'schema': 1, 'kernel': KERNEL, 'upstream_commit':
                  '53c677faa471be1ebfdbbea87dfa3dbe5b0fa2fb',
                  'compiled_sha256': sha(module), 'stripped_sha256': stripped,
                  'signed_sha256': sha(plain), 'compressed_sha256': sha(compressed),
                  'certificate_der_sha256': sha(HERE / 'module.der'),
                  'native_proof_sha256': sha(proof_file),
                  'kernel_trust': 'requires native MOK/keyring readback; never inferred from package'}
    (sources / 'PROVENANCE.json').write_text(json.dumps(provenance, indent=2) + '\n')
    specs = output / 'SPECS'
    specs.mkdir()
    spec = specs / (NAME + '.spec')
    spec.write_text(f'''Name: {NAME}
Version: {KERNEL_VERSION}
Release: {PACKAGE_RELEASE}
Summary: MoOS V3 motion sensor upstream ACPI backport
License: GPL-2.0-only
URL: https://github.com/moalfarras-sys/moos-image
BuildArch: x86_64
Source0: st_lsm6dsx_i2c.ko.xz
Source1: module.der
Source2: COPYING
Source3: PROVENANCE.json
Source4: GPL-2.0
Requires: kernel-uname-r = {KERNEL}
Requires: kernel-modules-core = {KERNEL_EVR}
Provides: kmod-moos-smocf05-uname-r = {KERNEL}
%global debug_package %{{nil}}
%description
Exact upstream SMOCF05 backport for the V3 LSM6DS3TR-C transport.
Preserves the original signed kernel and vendor module. Native module-key
enrollment and physical device acceptance are separate from image signing.
%prep
%build
%install
install -D -m0644 %{{SOURCE0}} %{{buildroot}}/{RELATIVE}
install -D -m0644 %{{SOURCE1}} %{{buildroot}}/{CERTIFICATE}
install -D -m0644 %{{SOURCE2}} %{{buildroot}}/usr/share/licenses/{NAME}/COPYING
install -D -m0644 %{{SOURCE3}} %{{buildroot}}/usr/share/doc/{NAME}/PROVENANCE.json
install -D -m0644 %{{SOURCE4}} %{{buildroot}}/usr/share/licenses/{NAME}/GPL-2.0
%files
/{RELATIVE}
/{CERTIFICATE}
%license /usr/share/licenses/{NAME}/COPYING
%license /usr/share/licenses/{NAME}/GPL-2.0
/usr/share/doc/{NAME}/PROVENANCE.json
''')
    result = subprocess.run(['rpmbuild', '-bb', '--define', '_topdir ' + str(output),
                             '--define', '_buildhost moos-build', str(spec)],
                            capture_output=True, text=True, timeout=120)
    (output / 'rpmbuild.log').write_text(result.stdout + result.stderr)
    result.check_returncode()
    rpms = list((output / 'RPMS').rglob('*.rpm'))
    require(len(rpms) == 1 and rpms[0].name == NVR + '.x86_64.rpm', 'unexpected RPM output')
    package = rpms[0]
    provenance.update(rpm_sha256=sha(package), rpm_bytes=package.stat().st_size,
                      rpm_name=package.name, rpm_header_signed=False,
                      integrity='exact reviewed RPM digest and pinned module PKCS#7; final OS cosign',
                      installed=False, loaded=False, key_enrolled=False)
    (output / 'package-proof.json').write_text(json.dumps(provenance, indent=2) + '\n')
    print(json.dumps(provenance))


if __name__ == '__main__':
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ('module', 'proof', 'key', 'output'):
        parser.add_argument('--' + option, type=Path, required=True)
    args = parser.parse_args()
    build(args.module.resolve(), args.proof.resolve(), args.key.absolute(), args.output.absolute())
