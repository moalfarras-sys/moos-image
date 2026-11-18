#!/usr/bin/env python3
"""Review exact RPM versus final OCI PE bytes, without installing either.

An unchanged kernel-core RPM can precede an upstream-base signature append.
This proof is deliberately separate from admit.py: production admission still
compares the complete file to one exact digest, with no PE normalization.
This tool proves retained bytes; it does not establish machine trust or boot.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import tarfile

ROOT = Path(__file__).resolve().parents[2]


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def pe_parts(data):
    require(512 <= len(data) <= 30 * 1024 * 1024 and data[:2] == b'MZ', 'invalid bounded PE')
    header = struct.unpack_from('<I', data, 0x3c)[0]
    require(header + 24 + 152 <= len(data) and data[header:header + 4] == b'PE\0\0', 'invalid PE header')
    optional = header + 24
    require(struct.unpack_from('<H', data, optional)[0] == 0x20b, 'not PE32+')
    checksum, directory = optional + 64, optional + 112 + 4 * 8
    start, length = struct.unpack_from('<II', data, directory)
    require(directory + 8 < start <= len(data) and start % 8 == 0 and start + length == len(data),
            'invalid certificate extent or trailing bytes')
    certificates = []
    offset = start
    while offset < len(data):
        require(offset + 8 <= len(data), 'truncated certificate')
        size, revision, kind = struct.unpack_from('<IHH', data, offset)
        require(8 < size <= len(data) - offset and revision == 0x200 and kind == 2,
                'invalid WIN_CERTIFICATE')
        end = offset + ((size + 7) & ~7)
        require(end <= len(data) and not any(data[offset + size:end]), 'invalid certificate padding')
        certificates.append(data[offset:end])
        offset = end
    require(offset == len(data) and certificates, 'incomplete certificate table')
    return (data[:checksum] + data[checksum + 4:directory] + data[directory + 8:start], certificates)


def review(rpm_kernel, base_kernel, oci_manifest, layer, manifest):
    old, new = rpm_kernel.read_bytes(), base_kernel.read_bytes()
    require(digest(old) == manifest['vendor_rpm_kernel_sha256'], 'unreviewed RPM kernel')
    require(digest(new) == manifest['vendor_kernel_sha256'], 'unreviewed final kernel')
    body_old, certs_old = pe_parts(old)
    body_new, certs_new = pe_parts(new)
    require(body_old == body_new and digest(body_new) == manifest['vendor_kernel_pe_body_sha256'],
            'executable or other non-certificate bytes changed')
    require(certs_new[:len(certs_old)] == certs_old and len(certs_new) == len(certs_old) + 1,
            'original signature changed or unexpected added signatures')
    require(digest(oci_manifest.read_bytes()) == manifest['vendor_base_manifest_sha256'], 'base manifest drift')
    oci = json.loads(oci_manifest.read_bytes())
    expected_layer = manifest['vendor_base_kernel_layer']
    require(any(item['digest'] == expected_layer for item in oci['layers']), 'kernel layer not in base manifest')
    with layer.open('rb') as stream:
        require('sha256:' + hashlib.file_digest(stream, 'sha256').hexdigest() == expected_layer, 'base layer drift')
    kernel_path = 'usr/lib/modules/' + manifest['kernel'] + '/vmlinuz'
    with tarfile.open(layer) as archive:
        member = archive.getmember(kernel_path)
        require(member.isfile() and member.size == len(new), 'unexpected final kernel layer entry')
        require(archive.extractfile(member).read() == new, 'kernel differs from exact final base layer')
    return {'rpm_kernel_sha256': digest(old), 'final_base_kernel_sha256': digest(new),
            'non_certificate_bytes_identical': True, 'original_signature_bytes_retained': True,
            'certificates_before': len(certs_old), 'certificates_after': len(certs_new),
            'exact_oci_manifest_and_layer': True, 'machine_trust': 'not tested', 'boot': 'not tested'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('rpm-kernel', 'base-kernel', 'oci-manifest', 'layer'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads((ROOT / 'build_files/smocf05/manifest.json').read_bytes())
    print(json.dumps(review(args.rpm_kernel, args.base_kernel, args.oci_manifest, args.layer, manifest), indent=2))
