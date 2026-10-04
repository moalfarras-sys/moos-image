#!/usr/bin/env python3
"""SDK-only: actual rebuilt script parser accepts theme and rejects BOM fixture."""
import json
import os
from pathlib import Path
import resource
import subprocess
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
root = Path('/work/plymouth-script-proof')
root.mkdir()
manifest = json.loads(Path('/out/manifest.json').read_text())
for name in ('plymouth-plugin-script', 'plymouth-core-libs', 'plymouth-graphics-libs'):
    package = next(p for p in manifest['packages'] if p['name'] == name)
    payload = subprocess.check_output(['rpm2cpio', '/out/' + package['file']])
    subprocess.run(['cpio', '-idm', '--no-absolute-filenames', '--no-preserve-owner'],
                   input=payload, cwd=root, capture_output=True, check=True)
subprocess.run(['gcc', '-Wall', '-Wextra', '-Werror', '/src/script-parser.c',
                '-ldl', '-o', str(root / 'parse')], check=True)
script = Path('/src/moos.script')
negative = root / 'bom.script'
negative.write_bytes(b'\xef\xbb\xbf' + script.read_bytes())
trials = []
for path, expected in ((script, 0), (negative, 71)):
    result = subprocess.run([str(root / 'parse'), str(root / 'usr/lib64/plymouth/script.so'),
                             str(path)], capture_output=True, text=True, timeout=10,
                            env=dict(os.environ, LD_LIBRARY_PATH=str(root / 'usr/lib64')))
    (root / (path.stem + '.log')).write_text(result.stdout + result.stderr)
    trials.append({'fixture': path.name, 'exit': result.returncode, 'expected': expected})
    if result.returncode != expected:
        print(f'{path.name}: native parser failure: {result.stderr}', flush=True)
proof = {'schema': 1, 'scope': 'actual rebuilt native script parser; not boot/pixel proof',
         'trials': trials, 'passed': all(t['exit'] == t['expected'] for t in trials)}
Path('/out/proof/script.json').write_text(json.dumps(proof, indent=2) + '\n')
print(json.dumps(proof))
raise SystemExit(0 if proof['passed'] else 1)
