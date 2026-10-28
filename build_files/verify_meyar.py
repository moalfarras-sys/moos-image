#!/usr/bin/env python3
"""Verify shipped Meyar bytes, Unicode coverage and real terminal cell widths.

Uses only the standard library, so the same gate runs in all four images.
Font tooling is a source-build dependency, never an installed OS dependency.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct


class Sfnt:
    def __init__(self, path: Path):
        self.data = path.read_bytes()
        if self.data[:4] != b'\x00\x01\x00\x00':
            raise ValueError(f'{path.name}: expected TrueType font')
        count = struct.unpack_from('>H', self.data, 4)[0]
        self.tables = {}
        for i in range(count):
            tag, _, start, size = struct.unpack_from('>4sIII', self.data, 12 + i * 16)
            if tag in self.tables or start + size > len(self.data):
                raise ValueError('Invalid or duplicate font table')
            self.tables[tag.decode('ascii')] = self.data[start:start + size]

    def number(self, tag, offset, fmt='H'):
        return struct.unpack_from('>' + fmt, self.tables[tag], offset)[0]

    def cmap(self):
        data = self.tables['cmap']
        records = []
        for i in range(struct.unpack_from('>H', data, 2)[0]):
            platform, encoding, offset = struct.unpack_from('>HHI', data, 4 + i * 8)
            if platform == 0 or (platform == 3 and encoding in (1, 10)):
                records.append(offset)
        result = {}
        for offset in records:
            fmt = struct.unpack_from('>H', data, offset)[0]
            if fmt == 12:
                for i in range(struct.unpack_from('>I', data, offset + 12)[0]):
                    first, last, gid = struct.unpack_from('>III', data, offset + 16 + i * 12)
                    if last > 0x10ffff or first > last:
                        raise ValueError('Invalid Unicode range')
                    result.update((cp, gid + cp - first) for cp in range(first, last + 1))
            elif fmt == 4:
                count = struct.unpack_from('>H', data, offset + 6)[0] // 2
                end = offset + 14
                start = end + count * 2 + 2
                delta = start + count * 2
                ranges = delta + count * 2
                for i in range(count):
                    lo = struct.unpack_from('>H', data, start + i * 2)[0]
                    hi = struct.unpack_from('>H', data, end + i * 2)[0]
                    d = struct.unpack_from('>h', data, delta + i * 2)[0]
                    relative = struct.unpack_from('>H', data, ranges + i * 2)[0]
                    for cp in range(lo, min(hi, 0xfffe) + 1):
                        gid = struct.unpack_from('>H', data, ranges + i * 2 + relative + (cp - lo) * 2)[0] if relative else cp
                        if gid:
                            result[cp] = (gid + d) & 0xffff
        return {cp: gid for cp, gid in result.items() if gid}

    def advance(self, gid):
        count = self.number('hhea', 34)
        return self.number('hmtx', min(gid, count - 1) * 4)

    def family(self):
        data = self.tables['name']; count, strings = struct.unpack_from('>HH', data, 2)
        names = {}
        for i in range(count):
            platform, encoding, language, name, size, offset = struct.unpack_from('>6H', data, 6 + i * 12)
            if platform == 3 and language == 0x409 and name in (1, 16):
                names[name] = data[strings + offset:strings + offset + size].decode('utf-16-be')
        return names.get(16, names.get(1))


def verify(root: Path):
    if root.is_symlink() or not root.is_dir():
        raise ValueError('Font directory must be a real installed directory')
    manifest = json.loads((root / 'manifest.json').read_text())
    if manifest['version'] != '0.300' or manifest['license'] != 'OFL-1.1':
        raise ValueError('Unexpected font delivery version/license')
    files = manifest['files']
    if {p.name for p in root.iterdir()} != set(files) | {'manifest.json'}:
        raise ValueError('Unreviewed font delivery contents')
    for name, receipt in files.items():
        if Path(name).name != name:
            raise ValueError('Invalid manifest entry')
        path = root / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size != receipt['bytes'] or hashlib.sha256(path.read_bytes()).hexdigest() != receipt['sha256']:
            raise ValueError('Font delivery byte mismatch: ' + name)
    policy = json.loads((root / 'terminal-cells.json').read_text())
    expected = {'MeyarSans[wght].ttf': 'Meyar Sans', 'MeyarArabic[wght].ttf': 'Meyar Arabic',
                'MeyarMono[wght].ttf': 'Meyar Mono', 'MeyarMonoArabic-Regular.ttf': 'Meyar Mono Arabic',
                'MeyarMonoArabic-Bold.ttf': 'Meyar Mono Arabic'}
    if {n for n in files if n.endswith('.ttf')} != set(expected):
        raise ValueError('Incomplete Meyar family')
    rows = []
    for name, family in expected.items():
        font = Sfnt(root / name); cmap = font.cmap()
        if font.family() != family or font.number('head', 18) != 1000 or font.number('OS/2', 8) != 0:
            raise ValueError('Wrong family, UPM or embedding permission: ' + name)
        if name in ('MeyarSans[wght].ttf', 'MeyarMono[wght].ttf'):
            # Every encoded point in the retained upstream phonetic blocks,
            # including combining accents, must survive image composition.
            for lo, hi in ((0x250, 0x2b0), (0x1d00, 0x1dc0), (0x300, 0x370), (0xa0, 0x180)):
                # Upstream Mono maps default-ignorable SOFT HYPHEN to gid0.
                # Every visible letter, mark and punctuation point remains required.
                if any(cp not in cmap for cp in range(lo, hi) if cp != 0xad):
                    raise ValueError('Missing Latin/IPA/combining coverage: ' + name)
        if family in ('Meyar Mono', 'Meyar Mono Arabic'):
            widths=policy['positiveWidths'] if family=='Meyar Mono' else policy['arabic']['positiveWidths']
            for cp, cells in widths.items():
                if int(cp) not in cmap or font.advance(cmap[int(cp)]) != cells * 700:
                    raise ValueError('Native terminal cell mismatch: ' + cp)
        if 'Mono' in family:
            if font.number('post', 12, 'I') != 1 or any(font.advance(gid) % 700 for gid in range(font.number('maxp', 4))):
                raise ValueError('Broken monospace metrics: ' + name)
            if (font.number('hhea', 4, 'h'), font.number('hhea', 6, 'h')) != (1600, -768):
                raise ValueError('Mono mark line room changed')
        if 'Arabic' in family and any(ord(c) not in cmap for c in 'ابتثجحخدذرزسشصضطظعغفقكلمنهويأإآءؤئىَُِّّْپژگچ'):
            raise ValueError('Missing Arabic letter or mark')
        if '[wght]' in name:
            data = font.tables['fvar']; start, _, axes = struct.unpack_from('>HHH', data, 4)
            tag, low, default, high = struct.unpack_from('>4siii', data, start)
            if axes != 1 or tag != b'wght' or (low, default, high) != (100 << 16, 400 << 16, 900 << 16):
                raise ValueError('Variable weight range changed')
        rows.append({'family': family, 'glyphs': font.number('maxp', 4), 'unicode': len(cmap)})
    return {'pass': True, 'version': manifest['version'], 'families': rows}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.directory), ensure_ascii=False))
