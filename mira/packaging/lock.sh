#!/bin/sh
# Regenerate requirements.lock from the versions pinned in it: download the cp314 wheels for
# x86_64 and aarch64 and record every sha256. Review the diff before committing it.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
pins=$(grep -E '^[a-z0-9-]+==' "$here/requirements.lock" | sed 's/ .*//')
for arch in x86_64 aarch64; do
    mkdir -p "$work/$arch"
    python3 -m pip download -q --no-deps --only-binary=:all: --python-version 3.14 --implementation cp \
        --abi cp314 --platform "manylinux_2_28_$arch" --platform "manylinux_2_17_$arch" \
        --platform "manylinux2014_$arch" -d "$work/$arch" $pins
done
python3 - "$work" "$here/requirements.lock" <<'PY'
import hashlib, re, sys
from collections import defaultdict
from pathlib import Path
work, lock = Path(sys.argv[1]), Path(sys.argv[2])
hashes, versions = defaultdict(set), {}
for wheel in sorted(work.glob('*/*.whl')):
    name, version = wheel.name.split('-')[:2]
    key = re.sub(r'[-_.]+', '-', name).lower()
    versions[key] = version
    hashes[key].add(hashlib.sha256(wheel.read_bytes()).hexdigest())
head = [line for line in lock.read_text().splitlines() if line.startswith('#')] + ['']
body = [' \\\n    '.join([f'{k}=={versions[k]}'] + [f'--hash=sha256:{h}' for h in sorted(hashes[k])]) for k in sorted(hashes)]
lock.write_text('\n'.join(head + body) + '\n')
print(len(body), 'packages locked')
PY
