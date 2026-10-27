#!/usr/bin/env python3
"""Materialize the reviewed five-font runtime overlay from a qualified build."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent


def package(build, target):
    sources = {f'Meyar{stem}[wght].ttf': build / kind / f'Meyar{stem}[wght].ttf'
               for kind, stem in [('sans', 'Sans'), ('arabic', 'Arabic'), ('mono', 'Mono')]}
    sources.update({f'MeyarMonoArabic-{s}.ttf': build / 'mono-arabic' / f'MeyarMonoArabic-{s}.ttf'
                    for s in ('Regular', 'Bold')})
    sources.update({'OFL-LGC.txt': ROOT / 'upstream-lgc/OFL.txt',
                    'OFL-Arabic.txt': ROOT.parent / 'meyar-arabic/upstream/OFL.txt',
                    'OFL-MonoArabic.txt': ROOT / 'upstream-kawkab/OFL.txt',
                    'README.md': ROOT / 'README.md', 'terminal-cells.json': ROOT / 'terminal-cells.json'})
    if target.is_symlink() or (target.exists() and any(p.name not in set(sources) | {'manifest.json'} or p.is_symlink() or not p.is_file() for p in target.iterdir())):
        raise ValueError('Unknown or linked output contents; preserve them')
    target.mkdir(parents=True, exist_ok=True)
    for name, path in sources.items():
        if path.is_symlink() or not path.is_file():
            raise ValueError('Missing or linked font build input: ' + str(path))
    for name, path in sources.items():
        shutil.copyfile(path, target / name)
    files = {n: {'bytes': (target / n).stat().st_size,
                 'sha256': hashlib.sha256((target / n).read_bytes()).hexdigest()} for n in sorted(sources)}
    (target / 'manifest.json').write_text(json.dumps({'version': '0.300', 'license': 'OFL-1.1',
         'source': 'fonts/meyar-family', 'cellUnits': 700, 'files': files}, indent=2) + '\n')
    print(json.dumps({'fonts': 5, 'files': len(files), 'bytes': sum(v['bytes'] for v in files.values())}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('build', type=Path); parser.add_argument('target', type=Path)
    args = parser.parse_args(); package(args.build, args.target)
