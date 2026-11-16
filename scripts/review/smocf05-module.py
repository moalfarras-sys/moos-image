#!/usr/bin/env python3
"""Compile the exact old/fixed sensor transport; never install or load either.

Run inside the existing development toolbox with its matching kernel-devel.
The generated review certificate proves cryptography, not machine trust.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = json.loads(Path(__file__).with_suffix('.json').read_text())
PACKET = ROOT / 'docs/hardware/patches/smocf05'
BACKPORT = json.loads((PACKET / 'manifest.json').read_text())
MAGIC = b'~Module signature appended~\n'
LIMIT = 2 * 1024 * 1024


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def run(args, *, cwd=None, timeout=120):
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True,
                          text=True, timeout=timeout).stdout.strip()


def split_signature(data):
    require(40 < len(data) <= LIMIT and data.endswith(MAGIC),
            'missing or oversized kernel signature')
    header = data[-len(MAGIC)-12:-len(MAGIC)]
    algorithm, hash_id, kind, signer_len, key_len, padding, size = struct.unpack(
        '>BBBBB3sI', header)
    require((algorithm, hash_id, kind, signer_len, key_len, padding) ==
            (0, 0, 2, 0, 0, b'\0\0\0'), 'unsupported signature trailer')
    end = len(data) - len(MAGIC) - 12
    require(0 < size < end, 'invalid signature length')
    payload, signature = data[:end-size], data[end-size:end]
    require(payload.startswith(b'\x7fELF'), 'not an ELF module')
    return payload, signature


def verify_signature(data, certificate):
    """Verify exact certificate/content, independently of modinfo's metadata.

    -noverify deliberately skips certificate-chain validation: this function
    reports cryptographic integrity only and must never imply kernel trust.
    -nointern prevents an embedded alternate signer from being selected.
    """
    certificate = Path(certificate)
    require(certificate.is_file() and not certificate.is_symlink() and
            0 < certificate.stat().st_size < 100000, 'missing regular signing certificate')
    # An inaccessible toolbox-owned PEM is not a cryptographic wrong-key proof.
    certificate.read_bytes()
    run(['openssl', 'x509', '-in', str(certificate), '-noout'])
    payload, signature = split_signature(data)
    with tempfile.TemporaryDirectory(prefix='moos-module-cms-') as temporary:
        directory = Path(temporary)
        (directory / 'payload').write_bytes(payload)
        (directory / 'signature').write_bytes(signature)
        run(['openssl', 'cms', '-verify', '-binary', '-inform', 'DER',
             '-in', str(directory / 'signature'), '-content', str(directory / 'payload'),
             '-certfile', str(certificate), '-nointern', '-noverify', '-out', os.devnull])


def metadata(module):
    require(module.stat().st_size <= LIMIT, 'oversized module')
    result = {field: run(['modinfo', '-F', field, str(module)])
              for field in ('name', 'depends', 'vermagic', 'import_ns', 'alias')}
    result['alias'] = sorted(result['alias'].splitlines())
    require(result['name'] == 'st_lsm6dsx_i2c', 'wrong module owner')
    require(result['depends'] == 'st_lsm6dsx', 'wrong core dependency')
    require(result['import_ns'] == 'IIO_LSM6DSX', 'wrong symbol namespace')
    require(result['vermagic'] == MANIFEST['vermagic'], 'wrong kernel ABI')
    result.update(sha256=digest(module), bytes=module.stat().st_size)
    return result


def extract_source(inputs, output):
    for name, expected in MANIFEST['rpms'].items():
        source = inputs / name
        require(source.is_file() and not source.is_symlink(), 'missing regular RPM')
        require(digest(source) == expected, 'RPM digest mismatch: ' + name)
        proof = run(['rpmkeys', '--checksig', '--verbose', str(source)])
        require(MANIFEST['signer'] + ': OK' in proof, 'untrusted source/devel RPM')
        (output / (name + '.signature.txt')).write_text(proof + '\n')
    version = MANIFEST['kernel']
    require(run(['rpm', '-q', '--qf', '%{VERSION}-%{RELEASE}.%{ARCH}',
                 'kernel-devel-' + version]) == version, 'missing exact kernel-devel')
    require(not run(['rpm', '-V', 'kernel-devel-' + version]), 'modified kernel-devel')
    source_dir = output / 'source-rpm'
    source_dir.mkdir()
    srpm = inputs / 'kernel-7.3.3-200.fc44.src.rpm'
    # Bound memory by streaming the trusted RPM payload to disk. Check both
    # producer and consumer; cpio can return zero when no requested member exists.
    with (output / 'source.cpio').open('xb') as stream:
        subprocess.run(['rpm2cpio', str(srpm)], stdout=stream, check=True, timeout=120)
    with (output / 'source.cpio').open('rb') as stream:
        subprocess.run(['cpio', '-idm', '--quiet', '--no-absolute-filenames',
                        '--no-preserve-owner', *('./' + n for n in MANIFEST['source_members'])],
                       cwd=source_dir, stdin=stream, check=True, timeout=120)
    for name, expected in MANIFEST['source_members'].items():
        source = source_dir / name
        require(source.is_file() and not source.is_symlink() and digest(source) == expected,
                'missing/changed source RPM member: ' + name)
    for name in ('patch-7.3-redhat.patch', 'linux-kernel-test.patch'):
        require(b'st_lsm6dsx' not in (source_dir / name).read_bytes(),
                'vendor patch changes the reviewed driver')
    found = {}
    prefix = 'linux-7.3.3/drivers/iio/imu/st_lsm6dsx/'
    with tarfile.open(source_dir / 'linux-7.3.3.tar.xz', 'r|xz') as archive:
        for member in archive:
            if member.name in (prefix + 'st_lsm6dsx_i2c.c', prefix + 'st_lsm6dsx.h'):
                require(member.isfile() and 0 < member.size < 100000 and
                        member.name not in found, 'invalid or duplicated source member')
                found[member.name] = archive.extractfile(member).read()
    require(len(found) == 2, 'incomplete source archive')
    return {Path(name).name: data for name, data in found.items()}


def review(inputs, output):
    output.mkdir(mode=0o700)  # Exclusive: preserve earlier failures/proofs.
    sources = extract_source(inputs, output)
    require(hashlib.sha256(sources['st_lsm6dsx_i2c.c']).hexdigest() ==
            BACKPORT['stock_source_sha256'], 'unexpected stock transport')
    require(hashlib.sha256(sources['st_lsm6dsx.h']).hexdigest() ==
            MANIFEST['header_sha256'], 'unexpected driver header')
    patch = PACKET / '0002-stock-context-backport.patch'
    require(digest(patch) == BACKPORT['backport_patch_sha256'], 'changed backport')
    modules, result = {}, {}
    kernel_dir = Path('/usr/src/kernels') / MANIFEST['kernel']
    for kind in ('old', 'fixed'):
        directory = output / kind / 'drivers/iio/imu/st_lsm6dsx'
        directory.mkdir(parents=True)
        for name, data in sources.items():
            (directory / name).write_bytes(data)
        (directory / 'Kbuild').write_text('obj-m := st_lsm6dsx_i2c.o\n')
        if kind == 'fixed':
            run(['git', 'apply', str(patch)], cwd=output / kind)
            require(digest(directory / 'st_lsm6dsx_i2c.c') ==
                    BACKPORT['accepted_source_sha256'], 'unexpected patched result')
        build = subprocess.run(['make', '-C', str(kernel_dir), 'M=' + str(directory),
                                '-j2', 'modules'], capture_output=True, text=True, timeout=180)
        (output / (kind + '-build.log')).write_text(build.stdout + build.stderr)
        build.check_returncode()
        module = directory / 'st_lsm6dsx_i2c.ko'
        result[kind] = metadata(module)
        modules[kind] = module
    old, fixed = set(result['old']['alias']), set(result['fixed']['alias'])
    require(fixed - old == {'acpi*:SMOCF05:*'} and not old - fixed,
            'unexpected ACPI/OF/I2C alias change')
    # These keys exist only in this private review directory. Never enroll them,
    # publish them, or treat their signature as OS delivery authorization.
    key, cert = output / 'review-only.key', output / 'review-only.pem'
    run(['openssl', 'req', '-new', '-x509', '-newkey', 'rsa:3072', '-noenc',
         '-days', '2', '-subj', '/CN=MoOS sensor REVIEW ONLY - NOT ENROLLED/',
         '-keyout', str(key), '-out', str(cert)])
    key.chmod(0o600)
    signed = output / 'st_lsm6dsx_i2c.review-signed.ko'
    shutil.copyfile(modules['fixed'], signed)
    run([str(kernel_dir / 'scripts/sign-file'), 'sha256', str(key), str(cert), str(signed)])
    verify_signature(signed.read_bytes(), cert)
    require(hashlib.sha256(split_signature(signed.read_bytes())[0]).hexdigest() ==
            result['fixed']['sha256'], 'signed payload differs from compiled module')
    result.update(schema=1, kernel=MANIFEST['kernel'], signed_sha256=digest(signed),
                  certificate_sha256=digest(cert), signature_verified=True,
                  kernel_trust=False, installed=False, loaded=False,
                  physical_sensor_acceptance=False, image_integration=False)
    (output / 'proof.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    arguments = parser.parse_args()
    result = review(arguments.inputs.resolve(), arguments.output.resolve())
    print(json.dumps({name: result[name] for name in
                     ('kernel', 'signature_verified', 'kernel_trust', 'installed', 'loaded')}))
