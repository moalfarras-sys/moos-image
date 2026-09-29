"""Download the Piper voices and the background features into the cache (idempotent, checksummed).

    python fetch_data.py

Background features: https://huggingface.co/datasets/davidscripka/openwakeword_features
(CC BY-NC-SA 4.0: personal, non-commercial use only; see README). The 10.7 h validation set is kept
whole for false-accept estimates; training negatives come from a fixed sample of the 2,000 h
ACAV100M file (300 slices of 500 windows at spread-out offsets, ~53 h, 461 MB), fetched with HTTP
range requests instead of downloading 17 GB.
"""
import hashlib
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np

import wakelib as wl

HF = 'https://huggingface.co'
VOICES = {
    'ar_JO-kareem-medium': ('ar/ar_JO/kareem/medium', '9e95cab07b679da603bba17c4dec7ab3111320571964ee95c0379603c086491e'),
    'en_US-libritts_r-medium': ('en/en_US/libritts_r/medium', '10bb85e071d616fcf4071f369f1799d0491492ab3c5d552ec19fb548fac13195'),
    'en_US-l2arctic-medium': ('en/en_US/l2arctic/medium', 'd89f6f124bf1e7735b2179d2141b8001c3e19169d5e743ed6e35624f4c76f044'),
}
FEATURES = f'{HF}/datasets/davidscripka/openwakeword_features/resolve/main'
VALIDATION_SHA = 'a56a8a0f8e0efb91900acc6de4c0cdf4c564842e8475a7d49b36c039e17a690f'
ACAV_SHA = '9d1ad4824dffb248164a3b4ee7be792a04f9969bb71d08e110c9f7748e70e9e8'


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 22), b''):
            h.update(block)
    return h.hexdigest()


def fetch(url, dest, digest=None):
    dest = Path(dest)
    if dest.exists() and (digest is None or sha(dest) == digest):
        return
    tmp = dest.with_suffix(dest.suffix + '.part')
    wl.log('downloading', url)
    with urllib.request.urlopen(url, timeout=120) as r, open(tmp, 'wb') as f:
        while block := r.read(1 << 20):
            f.write(block)
    if digest and sha(tmp) != digest:
        tmp.unlink()
        raise SystemExit(f'{url}: checksum mismatch')
    tmp.replace(dest)


def fetch_acav(dest, chunks=300, rows=500):
    """The same fixed sample every time (seeded offsets), checked against ACAV_SHA."""
    url = f'{FEATURES}/openwakeword_features_ACAV100M_2000_hrs_16bit.npy'
    header, total, rowb = 128, 5625000, 16 * 96 * 2
    if dest.exists() and sha(dest) == ACAV_SHA:
        return
    hdr = urllib.request.urlopen(urllib.request.Request(url, headers={'Range': f'bytes=0-{header - 1}'}), timeout=60).read()
    if b"'descr': '<f2'" not in hdr or b'(5625000, 16, 96)' not in hdr:
        raise SystemExit(f'unexpected ACAV100M header: {hdr!r}')
    rng = np.random.default_rng(20260929)
    starts = np.linspace(0, total - rows, chunks).astype(np.int64)
    starts = np.clip(starts + rng.integers(-rows, rows, size=chunks), 0, total - rows)
    tmp = dest.with_suffix('.part.npy')
    arr = np.lib.format.open_memmap(tmp, mode='w+', dtype='<f2', shape=(chunks * rows, 16, 96))
    t0 = time.time()
    for k, s in enumerate(starts):
        a, b = header + int(s) * rowb, header + (int(s) + rows) * rowb - 1
        for attempt in range(5):
            try:
                req = urllib.request.Request(url, headers={'Range': f'bytes={a}-{b}'})
                data = urllib.request.urlopen(req, timeout=120).read()
                if len(data) == rows * rowb:
                    break
            except OSError:
                time.sleep(2 + 3 * attempt)
        else:
            raise SystemExit(f'ACAV100M slice {k} failed')
        arr[k * rows:(k + 1) * rows] = np.frombuffer(data, '<f2').reshape(rows, 16, 96)
        if k % 50 == 0:
            wl.log(f'ACAV100M slice {k}/{chunks} ({time.time() - t0:.0f}s)')
    arr.flush()
    del arr
    if sha(tmp) != ACAV_SHA:
        raise SystemExit('ACAV100M sample checksum mismatch (the dataset changed?)')
    tmp.replace(dest)


def main():
    root = wl.cache_root()
    (root / 'voices').mkdir(parents=True, exist_ok=True)
    (root / 'data').mkdir(parents=True, exist_ok=True)
    for name, (path, digest) in VOICES.items():
        fetch(f'{HF}/rhasspy/piper-voices/resolve/main/{path}/{name}.onnx', root / f'voices/{name}.onnx', digest)
        fetch(f'{HF}/rhasspy/piper-voices/resolve/main/{path}/{name}.onnx.json', root / f'voices/{name}.onnx.json')
        fetch(f'{HF}/rhasspy/piper-voices/resolve/main/{path}/MODEL_CARD', root / f'voices/MODEL_CARD-{name}')
    fetch(f'{FEATURES}/validation_set_features.npy', root / 'data/validation_set_features.npy', VALIDATION_SHA)
    fetch_acav(root / 'data/acav100m_sample_300x500.npy')
    wl.log('data ready in', root)


if __name__ == '__main__':
    sys.exit(main())
