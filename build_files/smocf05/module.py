#!/usr/bin/env python3
"""Exact SMOCF05 module integrity. Kernel trust is a separate native predicate."""
import hashlib
import lzma
from pathlib import Path
import struct
import subprocess
import tempfile

MAGIC = b'~Module signature appended~\n'
LIMIT = 2 * 1024 * 1024
KERNEL = '7.3.4-200.fc44.x86_64'
# Every package/source name derives from this one reviewed stock kernel.
KERNEL_VERSION, KERNEL_RELEASE = KERNEL.rsplit('.', 1)[0].split('-', 1)
KERNEL_EVR = f'{KERNEL_VERSION}-{KERNEL_RELEASE}'
PACKAGE_RELEASE = '200.1.moos1.fc44'
VERMAGIC = KERNEL + ' SMP preempt mod_unload'
RELATIVE = f'usr/lib/modules/{KERNEL}/updates/moos/st_lsm6dsx_i2c.ko.xz'
VENDOR = f'usr/lib/modules/{KERNEL}/kernel/drivers/iio/imu/st_lsm6dsx/st_lsm6dsx_i2c.ko.xz'
CERTIFICATE = 'usr/share/moos/keys/moos-hardware-2026.der'


def require(value, message):
    if not value:
        raise ValueError(message)


def run(args, **kwargs):
    return subprocess.run(args, check=True, capture_output=True, text=True,
                          timeout=60, **kwargs).stdout.strip()


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def regular(path, limit=LIMIT):
    path = Path(path)
    require(path.is_file() and not path.is_symlink() and
            0 < path.stat().st_size <= limit, 'missing/linked/oversized input: ' + str(path))
    return path


def unpack(path):
    data = regular(path).read_bytes()
    if Path(path).suffix == '.xz':
        decoder = lzma.LZMADecompressor(memlimit=64 * 1024 * 1024)
        data = decoder.decompress(data, max_length=LIMIT + 1)
        require(decoder.eof and not decoder.unused_data, 'oversized or trailing module stream')
    require(len(data) <= LIMIT, 'oversized uncompressed module')
    return data


def split_signature(data):
    require(40 < len(data) <= LIMIT and data.endswith(MAGIC), 'missing module signature')
    header = data[-len(MAGIC)-12:-len(MAGIC)]
    algorithm, hash_id, kind, signer_len, key_len, padding, size = struct.unpack('>BBBBB3sI', header)
    require((algorithm, hash_id, kind, signer_len, key_len, padding) ==
            (0, 0, 2, 0, 0, b'\0\0\0'), 'unsupported module signature trailer')
    end = len(data) - len(MAGIC) - 12
    require(0 < size < end, 'invalid signature length')
    payload, signature = data[:end-size], data[end-size:end]
    require(payload.startswith(b'\x7fELF'), 'not an ELF module')
    return payload, signature


def verify_signature(data, certificate):
    certificate = regular(certificate, 100000)
    certificate.read_bytes()  # Unreadable input cannot masquerade as a wrong-key proof.
    run(['openssl', 'x509', '-in', str(certificate), '-noout'])
    payload, signature = split_signature(data)
    with tempfile.TemporaryDirectory(prefix='moos-module-signature-') as directory:
        directory = Path(directory)
        (directory / 'payload').write_bytes(payload)
        (directory / 'signature').write_bytes(signature)
        # This verifies exact key/content, not a CA chain or enrollment. An
        # embedded other signer must never replace the selected certificate.
        run(['openssl', 'cms', '-verify', '-binary', '-inform', 'DER',
             '-in', str(directory / 'signature'), '-content', str(directory / 'payload'),
             '-certfile', str(certificate), '-nointern', '-noverify', '-out', '/dev/null'])
    return hashlib.sha256(payload).hexdigest()


def metadata(path):
    result = {name: run(['modinfo', '-F', name, str(path)])
              for name in ('name', 'depends', 'vermagic', 'import_ns', 'alias')}
    require(result['name'] == 'st_lsm6dsx_i2c' and result['depends'] == 'st_lsm6dsx' and
            result['vermagic'] == VERMAGIC and result['import_ns'] == 'IIO_LSM6DSX',
            'module owner/ABI/dependency/namespace drift')
    result['alias'] = sorted(result['alias'].splitlines())
    return result
