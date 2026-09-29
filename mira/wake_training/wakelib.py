"""Shared pieces of the Mira wake word toolchain.

The Echo Dot runs TECHO5's echod: a Go openWakeWord front end (mel spectrogram + speech embedding,
one 96-value embedding per 80 ms step) feeding a small TFLite classifier over the last 16
embeddings. Everything here is built so that training sees exactly what that engine computes:
features come from echod's own Go code (mira_features_test.go, run through `go test`), and the
classifier is exported with the same operators the device interpreter already accepted.

Nothing here talks to the Echo. Audio, features and models stay under the cache directory
(MIRA_WAKE_CACHE, default ~/.cache/mira-claude/wake); owner recordings are read where they are and
are never copied into the repository.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import subprocess
import tempfile
import time
import wave
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from scipy.signal import butter, fftconvolve, lfilter, resample_poly, sosfiltfilt

HERE = Path(__file__).resolve().parent
RATE = 16000
STEP = 1280          # samples per embedding step (80 ms)
EMB = 96             # embedding width
FRAMES = 16          # embeddings per classifier window (16 x 96 input)
PAD = RATE           # digital silence the exporter puts on each side of a clip (1 s)
# Embedding i of a padded stream depends on stream samples [1280 i + 56, 1280 i + 12456): mel frames
# 8i .. 8i+75, each a 400-sample Hann window on a 160-sample hop. Measured with single-sample
# impulses on a noise bed through the Go front end (README, "Timing"). On digital silence the mel
# model's 80 dB floor, taken relative to the loudest value of each 1760-sample chunk, couples a
# whole chunk, so the dependence there is wider; the device never hears digital silence.
EMB_END = 12456
EMB_START = 56

# echod's detector (feature/detect/engine.go): a score >= cutoff fires, scoring holds 300 ms for the
# peak, then 800 ms refractory. At one score per 80 ms step that is 14 steps from one detection to
# the earliest next one.
DEAD_STEPS = 14
DEVICE_MIN_CUTOFF = 0.5      # Home Assistant's "Wake word sensitivity" number: 0.5 .. 0.99
PLAYING_SLACK = 0.10         # echod lowers the cutoff by this while the echo canceller runs


def cache_root() -> Path:
    """MIRA_WAKE_CACHE, else the desktop app's MIRA_WAKE_TRAIN_ENV, else ~/.cache/mira-claude/wake."""
    for var in ('MIRA_WAKE_CACHE', 'MIRA_WAKE_TRAIN_ENV'):
        if os.environ.get(var):
            return Path(os.environ[var])
    return Path.home() / '.cache/mira-claude/wake'


def log(*args):
    print(time.strftime('%H:%M:%S'), *args, flush=True)


# ── timing ───────────────────────────────────────────────────────────────────────────────────────

def emb_end_time(i, pad=PAD):
    """Seconds into the clip (not the padded stream) at which embedding i's audio ends."""
    return (STEP * np.asarray(i) + EMB_END - pad) / RATE


def window_end_time(w, pad=PAD):
    """Seconds into the clip at which classifier window w (embeddings w .. w+15) ends."""
    return emb_end_time(np.asarray(w) + FRAMES - 1, pad)


def windows_ending_between(n_emb, lo, hi, pad=PAD):
    """Indices of stride-1 windows whose end lies in [lo, hi] seconds of the clip."""
    n_win = max(0, n_emb - FRAMES + 1)
    t = window_end_time(np.arange(n_win), pad)
    return np.flatnonzero((t >= lo) & (t <= hi))


def sliding_windows(feats):
    """(n, 96) embeddings -> (n-15, 1536) classifier inputs, each row a copy."""
    n = len(feats) - FRAMES + 1
    if n <= 0:
        return np.zeros((0, FRAMES * EMB), feats.dtype)
    v = np.lib.stride_tricks.sliding_window_view(feats, (FRAMES, EMB))[:, 0]
    return v.reshape(n, FRAMES * EMB).copy()


# ── WAV ──────────────────────────────────────────────────────────────────────────────────────────

def read_wav(path) -> np.ndarray:
    """A 16 kHz mono 16-bit PCM WAV as int16. Anything else is refused with the reason."""
    with wave.open(str(path), 'rb') as w:
        ch, width, rate, comp = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getcomptype()
        if comp != 'NONE' or width != 2 or ch != 1 or rate != RATE:
            raise ValueError(f'{path}: need 16 kHz mono 16-bit PCM WAV, got {rate} Hz, '
                             f'{ch} channel(s), {8 * width}-bit, compression {comp}')
        return np.frombuffer(w.readframes(w.getnframes()), '<i2').copy()


def write_wav(path, x):
    x = np.asarray(x)
    if x.dtype != np.int16:
        x = to_int16(x)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(x.astype('<i2').tobytes())


def to_int16(x):
    """float in [-1, 1] -> int16, clipped (clipping is what a real front end does too)."""
    return (np.clip(np.asarray(x, np.float64), -1, 1 - 1 / 32768) * 32768).round().astype(np.int16)


def to_float(x):
    return np.asarray(x, np.float64) / 32768.0


def db(power):
    return 10 * np.log10(np.maximum(power, 1e-20))


# ── the device front end, through Go ─────────────────────────────────────────────────────────────

class FrontEndError(RuntimeError):
    pass


class GoFrontEnd:
    """echod's own openWakeWord front end, run by `go test` from a staged copy of the oww package.

    features() returns, per clip, every embedding the engine produced with PAD samples of silence on
    both sides, exactly as the device computes them. Results are cached by content.
    """

    def __init__(self, root: Path | None = None, workers: int | None = None, chunk: int = 3000):
        self.root = Path(root or cache_root())
        self.go = self.root / 'go/bin/go'
        self.module = self.root / 'techo5-echod'
        self.pkg = self.module / 'internal/lib/oww'
        self.workers = workers or os.cpu_count() or 4
        self.chunk = chunk
        self.cache = self.root / 'featcache'
        missing = [p for p in (self.go, self.pkg / 'oww.go', self.pkg / 'assets/embedding_model.tflite')
                   if not p.exists()]
        if missing:
            raise FrontEndError(f'front end not staged ({", ".join(map(str, missing))}); run setup.sh')
        src = HERE / 'mira_features_test.go'
        dst = self.pkg / 'mira_features_test.go'
        if not dst.exists() or dst.read_bytes() != src.read_bytes():
            shutil.copyfile(src, dst)
        h = hashlib.sha256()
        for p in sorted(self.pkg.glob('*.go')) + sorted((self.module / 'internal/lib/tflite').glob('*.go')):
            h.update(p.name.encode() + p.read_bytes())
        for p in sorted((self.pkg / 'assets').glob('*.tflite')):
            h.update(p.read_bytes())
        self.version = h.hexdigest()[:16]
        self.cache.mkdir(parents=True, exist_ok=True)

    def _env(self):
        env = dict(os.environ)
        env.update(GOROOT=str(self.root / 'go'), GOPATH=str(self.root / 'gopath'),
                   GOCACHE=str(self.root / 'gocache'), GOFLAGS='-mod=mod', GOTOOLCHAIN='local',
                   GOPROXY='off', GOTELEMETRY='off', MIRA_WORKERS=str(self.workers),
                   PATH=str(self.root / 'go/bin') + os.pathsep + env.get('PATH', ''))
        return env

    def _run(self, test, prefix, pad, extra=None):
        env = self._env()
        env.update(MIRA_BATCH=str(prefix), MIRA_PAD=str(pad))
        env.update(extra or {})
        cmd = [str(self.go), 'test', './internal/lib/oww/', '-run', f'^{test}$', '-count=1',
               '-timeout', '600m', '-v']
        r = subprocess.run(cmd, cwd=self.module, env=env, capture_output=True, text=True)
        if r.returncode != 0 or f'--- PASS: {test}' not in r.stdout:
            raise FrontEndError(f'go test {test} failed:\n{r.stdout[-3000:]}\n{r.stderr[-3000:]}')

    @staticmethod
    def _write_batch(prefix, clips):
        offsets, off = [], 0
        with open(f'{prefix}.pcm', 'wb') as f:
            for c in clips:
                c = np.asarray(c)
                if c.dtype != np.int16:
                    raise TypeError('clips must be int16')
                f.write(c.astype('<i2').tobytes())
                offsets.append((off, len(c)))
                off += len(c)
        Path(f'{prefix}.idx').write_text(''.join(f'{a} {n}\n' for a, n in offsets))

    @staticmethod
    def _read_batch(data_path, idx_path, width):
        counts = [int(v) for v in Path(idx_path).read_text().split()]
        flat = np.fromfile(data_path, '<f4')
        if flat.size != sum(counts) * width:
            raise FrontEndError(f'{data_path}: {flat.size} values, index says {sum(counts) * width}')
        out, pos = [], 0
        for n in counts:
            out.append(flat[pos:pos + n * width].reshape(n, width) if width > 1 else flat[pos:pos + n])
            pos += n * width
        return out

    def _key(self, kind, clips, pad, extra=b''):
        h = hashlib.sha256(f'{kind}:{self.version}:{pad}:'.encode() + extra)
        for c in clips:
            h.update(len(c).to_bytes(8, 'little'))
            h.update(np.ascontiguousarray(c, '<i2').tobytes())
        return h.hexdigest()[:32]

    def features(self, clips, pad=PAD, desc='clips'):
        """list of int16 arrays -> list of (n_emb, 96) float32 arrays (device-exact)."""
        out = []
        for start in range(0, len(clips), self.chunk):
            part = clips[start:start + self.chunk]
            key = self._key('feats', part, pad)
            hit = self.cache / f'{key}.npz'
            if hit.exists():
                z = np.load(hit)
                flat, counts = z['feats'], z['counts']
                pos = np.concatenate([[0], np.cumsum(counts)])
                out.extend(flat[pos[i]:pos[i + 1]] for i in range(len(counts)))
                continue
            t0 = time.time()
            with tempfile.TemporaryDirectory(dir=self.root) as tmp:
                prefix = Path(tmp) / 'batch'
                self._write_batch(prefix, part)
                self._run('TestMiraFeatures', prefix, pad)
                got = self._read_batch(f'{prefix}.feats', f'{prefix}.fidx', EMB)
            counts = np.array([len(g) for g in got], np.int64)
            flat = np.concatenate(got) if got else np.zeros((0, EMB), np.float32)
            np.savez(hit, feats=flat, counts=counts)
            secs = sum(len(c) for c in part) / RATE
            log(f'front end: {len(part)} {desc} ({secs / 60:.1f} min of audio) in {time.time() - t0:.0f}s')
            out.extend(got)
        return out

    def scores(self, model_path, clips, pad=PAD):
        """Scores echod's engine returns for each clip with the classifier loaded (Engine.Load)."""
        with tempfile.TemporaryDirectory(dir=self.root) as tmp:
            prefix = Path(tmp) / 'batch'
            self._write_batch(prefix, clips)
            self._run('TestMiraScore', prefix, pad, {'MIRA_SCORE_MODEL': str(Path(model_path).resolve())})
            return self._read_batch(f'{prefix}.scores', f'{prefix}.sidx', 1)


# ── DSP and augmentation ─────────────────────────────────────────────────────────────────────────

def resample(x, factor):
    """Resample so the result has ~len(x) * factor samples (polyphase, anti-aliased)."""
    if abs(factor - 1) < 1e-4:
        return np.asarray(x, np.float64).copy()
    frac = np.round(factor * 1000).astype(int)
    g = math.gcd(int(frac), 1000)
    return resample_poly(np.asarray(x, np.float64), int(frac) // g, 1000 // g)


def speed(x, factor):
    """Tape-style speed change: factor 1.08 is 8 % faster (and higher)."""
    return resample(x, 1 / factor)


def time_stretch(x, rate, frame=480, hop=240, tol=160):
    """WSOLA time scaling: returns about len(x) / rate samples at the same pitch."""
    x = np.asarray(x, np.float64)
    if abs(rate - 1) < 1e-3 or len(x) < frame:
        return x.copy()
    win = np.hanning(frame)
    n_out = int(round(len(x) / rate))
    out = np.zeros(n_out + frame)
    norm = np.zeros(n_out + frame)
    off = tol + frame
    xp = np.concatenate([np.zeros(off), x, np.zeros(off + 2 * frame + hop)])
    prev = None
    for out_pos in range(0, n_out, hop):
        ideal = int(round(out_pos * rate))
        if prev is None:
            best = ideal
        else:
            target = xp[off + prev + hop: off + prev + hop + frame]
            lo = max(-off, ideal - tol)
            seg = xp[off + lo: off + ideal + tol + frame]
            corr = np.correlate(seg, target, mode='valid')
            best = lo + int(np.argmax(corr)) if len(corr) else ideal
        out[out_pos:out_pos + frame] += xp[off + best: off + best + frame] * win
        norm[out_pos:out_pos + frame] += win
        prev = best
    norm[norm < 1e-3] = 1
    return (out / norm)[:n_out]


def tape_shift(x, factor):
    """Another speaker size: every frequency (pitch and formants) times factor, duration kept.
    Resampling then WSOLA; no vocoder, so the speech stays as intelligible as the original."""
    x = np.asarray(x, np.float64)
    if abs(factor - 1) < 1e-3:
        return x.copy()
    y = resample(x, 1 / factor)
    return time_stretch(y, len(y) / len(x))


def synth_rir(rng, rt60=None):
    """A simple room: direct path, a few early reflections and an exponential diffuse tail."""
    rt60 = float(rt60 if rt60 is not None else rng.uniform(0.15, 0.8))
    n = int(RATE * min(1.0, 1.1 * rt60))
    t = np.arange(n) / RATE
    ir = np.zeros(n)
    ir[0] = 1.0
    for _ in range(int(rng.integers(3, 9))):
        d = int(RATE * rng.uniform(0.002, 0.035))
        ir[d] += rng.uniform(-0.5, 0.5) * np.exp(-6.9078 * d / RATE / rt60)
    tail = rng.standard_normal(n) * np.exp(-6.9078 * t / rt60)
    tail[:int(0.004 * RATE)] = 0
    tail = lfilter(*butter(1, rng.uniform(3000, 7000), fs=RATE), tail)   # air and wall absorption
    drr = 10 ** (rng.uniform(-2, 10) / 10)                                 # direct-to-reverberant
    tail *= np.sqrt(1.0 / (drr * np.sum(tail ** 2) + 1e-12))
    return ir + tail


def reverb(x, ir):
    return fftconvolve(np.asarray(x, np.float64), ir)[:len(x)]


def colored_noise(rng, n, kind):
    """white | pink | brown | fan | hum: steady noise, unit RMS."""
    if kind == 'hum':
        t = np.arange(n) / RATE
        f0 = rng.choice([50.0, 60.0])
        y = sum(rng.uniform(0.2, 1) / k * np.sin(2 * np.pi * f0 * k * t + rng.uniform(0, 6.3))
                for k in range(1, 8))
        y = y + 0.3 * colored_noise(rng, n, 'pink')
    else:
        spec = np.fft.rfft(rng.standard_normal(n + 1024))
        f = np.fft.rfftfreq(n + 1024, 1 / RATE)
        f[0] = f[1]
        shape = {'white': np.ones_like(f), 'pink': 1 / np.sqrt(f), 'brown': 1 / f,
                 'fan': 1 / np.sqrt(f) / (1 + (f / rng.uniform(300, 1200)) ** 2)}[kind]
        y = np.fft.irfft(spec * shape)[512:512 + n]
    return y / (np.sqrt(np.mean(y ** 2)) + 1e-12)


def active_rms(x, frame=320):
    """RMS over the loudest frames (speech level), not diluted by pauses."""
    x = np.asarray(x, np.float64)
    if len(x) < frame:
        return float(np.sqrt(np.mean(x ** 2) + 1e-20))
    e = np.mean(x[:len(x) // frame * frame].reshape(-1, frame) ** 2, axis=1)
    top = np.sort(e)[len(e) // 2:]
    return float(np.sqrt(np.mean(top) + 1e-20))


def fit_length(noise, n, rng):
    """A noise bed of exactly n samples: a random excerpt, looped with crossfades if too short."""
    noise = np.asarray(noise, np.float64)
    if len(noise) >= n:
        s = int(rng.integers(0, len(noise) - n + 1))
        return noise[s:s + n].copy()
    xf = min(800, len(noise) // 4)
    out = noise.copy()
    while len(out) < n:
        nxt = noise if xf == 0 else noise.copy()
        if xf:
            ramp = np.linspace(0, 1, xf)
            out[-xf:] = out[-xf:] * (1 - ramp) + nxt[:xf] * ramp
            out = np.concatenate([out, nxt[xf:]])
        else:
            out = np.concatenate([out, nxt])
    s = int(rng.integers(0, len(out) - n + 1))
    return out[s:s + n]


# ── segmentation of owner captures ───────────────────────────────────────────────────────────────

@dataclass
class Segment:
    start: float
    end: float
    kind: str = 'speech'          # speech | cut_off | faint | too_short | too_long
    peak_db: float = 0.0
    note: str = ''

    @property
    def dur(self):
        return self.end - self.start


def _frame_db(y, frame=320, hop=160):
    n = 1 + max(0, (len(y) - frame) // hop)
    idx = np.arange(frame)[None, :] + hop * np.arange(n)[:, None]
    return db(np.mean(y[idx] ** 2, axis=1))


def _split_at_valleys(e, a, b, depth_db, min_frames):
    """Split frames [a, b) at energy valleys at least depth_db below the peaks on both sides."""
    if b - a < 2 * min_frames:
        return [(a, b)]
    seg = np.convolve(e[a:b], np.ones(5) / 5, 'same')
    left = np.maximum.accumulate(seg)
    right = np.maximum.accumulate(seg[::-1])[::-1]
    depth = np.minimum(left, right) - seg
    depth[:min_frames] = depth[-min_frames:] = -np.inf
    i = int(np.argmax(depth))
    if depth[i] < depth_db:
        return [(a, b)]
    return (_split_at_valleys(e, a, a + i, depth_db, min_frames) +
            _split_at_valleys(e, a + i, b, depth_db, min_frames))


def segment_speech(x, merge_gap=0.25, min_dur=0.15, max_dur=1.8, pad=0.05, prominence_db=15.0,
                   valley_db=8.0):
    """Energy segmentation of one capture into utterances. Returns (segments, info).

    Speech band 120-4000 Hz, 20 ms frames on a 10 ms hop. The noise floor is the 15th percentile of
    frame energy and the speech level the 99th, so both thresholds follow the room: a region is
    everything above the low threshold around at least 30 ms above the high one, and regions closer
    than merge_gap merge («يا ميرا» is one utterance). A region that is too long, or that touches
    either end of the capture, is split at energy valleys of at least valley_db, which separates
    an utterance from the wake sound's tail or from neighbouring background speech. Labels:
      speech      an utterance
      cut_off     touches the start or end of the capture: the Echo streams only after the loud
                  part of its wake sound, so a sound already running at 0 s is that sound's tail
                  (or speech that began before the window); never a training positive
      faint       peaks more than prominence_db below the loudest speech: television, another
                  room, a voice far away
      too_short / too_long   outside [min_dur, max_dur]
    """
    y = sosfiltfilt(butter(4, [120, 4000], btype='band', fs=RATE, output='sos'), to_float(x))
    e = _frame_db(y)
    dur = len(x) / RATE
    floor, top = float(np.percentile(e, 15)), float(np.percentile(e, 99))
    info = dict(floor_db=round(floor, 1), speech_db=round(top, 1), duration=round(dur, 2))
    if top - floor < 8:
        info['warning'] = 'no speech found: loudest frames are within 8 dB of the floor'
        return [], info
    hi = floor + max(8.0, 0.40 * (top - floor))
    lo = floor + max(4.0, 0.20 * (top - floor))
    info.update(high_db=round(hi, 1), low_db=round(lo, 1))
    above_lo = e >= lo
    above_hi = e >= hi
    runs = []
    i = 0
    while i < len(e):
        if above_lo[i]:
            j = i
            while j < len(e) and above_lo[j]:
                j += 1
            if above_hi[i:j].sum() >= 3:
                runs.append([i, j])
            i = j
        else:
            i += 1
    merged = []
    for a, b in runs:
        if merged and (a - merged[-1][1]) * 0.01 < merge_gap:
            merged[-1][1] = b
        else:
            merged.append([a, b])
    pieces = []
    for a, b in merged:
        at_edge = a * 0.01 <= pad or b * 0.01 >= dur - pad - 0.02
        if (b - a) * 0.01 > max_dur or (at_edge and (b - a) * 0.01 > 0.4):
            pieces.extend(_split_at_valleys(e, a, b, valley_db, min_frames=12))
        else:
            pieces.append((a, b))
    segs = []
    prev_end = 0.0
    for a, b in pieces:
        # Trim each piece to its own frames above the low threshold.
        act = np.flatnonzero(above_lo[a:b])
        if not len(act):
            continue
        a, b = a + act[0], a + act[-1] + 1
        s = max(0.0, a * 0.01 - pad, prev_end)          # pieces of one split region must not overlap
        t = min(dur, b * 0.01 + 0.02 + pad)
        if t - s < 0.02:
            continue
        prev_end = t
        peak = float(e[a:b].max())
        seg = Segment(round(s, 3), round(t, 3), 'speech', round(peak, 1))
        if a * 0.01 <= 0.02 or b * 0.01 + 0.02 >= dur - 0.02:
            seg.kind, seg.note = 'cut_off', 'touches the edge of the capture (wake sound tail or clipped speech)'
        elif peak < top - prominence_db:
            seg.kind, seg.note = 'faint', f'{top - peak:.0f} dB below the loudest speech (background voice?)'
        elif seg.dur < min_dur:
            seg.kind, seg.note = 'too_short', f'{seg.dur:.2f}s'
        elif seg.dur > max_dur:
            seg.kind, seg.note = 'too_long', f'{seg.dur:.2f}s: utterances run together, or not the wake word'
        segs.append(seg)
    return segs, info


def background_mask(n, segments, guard=0.15):
    """True where no segment (of any kind) is within guard seconds."""
    m = np.ones(n, bool)
    for s in segments:
        m[max(0, int((s.start - guard) * RATE)):min(n, int((s.end + guard) * RATE))] = False
    return m


def background_audio(x, segments, min_run=0.3):
    """The capture's non-speech parts, concatenated (runs shorter than min_run are dropped)."""
    m = background_mask(len(x), segments)
    runs, i = [], 0
    while i < len(m):
        if m[i]:
            j = i
            while j < len(m) and m[j]:
                j += 1
            if (j - i) / RATE >= min_run:
                runs.append(x[i:j])
            i = j
        else:
            i += 1
    return np.concatenate(runs) if runs else np.zeros(0, np.int16)


# ── Piper ────────────────────────────────────────────────────────────────────────────────────────

class Voices:
    """Piper voices from the cache, loaded on first use."""

    def __init__(self, root: Path | None = None):
        self.dir = Path(root or cache_root()) / 'voices'
        self._loaded = {}

    def get(self, name):
        if name not in self._loaded:
            from piper import PiperVoice
            path = self.dir / f'{name}.onnx'
            if not path.exists():
                raise FileNotFoundError(f'{path} missing; run setup.sh')
            self._loaded[name] = PiperVoice.load(path)
        return self._loaded[name]


def piper_audio(voice, *, ipa=None, text=None, length_scale=1.0, noise_scale=0.667, noise_w=0.8,
                speaker=None):
    """Synthesize from IPA phonemes (exact pronunciation) or text (Piper's phonemizer), at 16 kHz.

    IPA goes straight to the model. For Arabic text Piper first runs its diacritizer, which reads
    «ميرا» as "mˈiːran" (tanween); the positives therefore always use explicit IPA.
    """
    from piper import SynthesisConfig
    cfg = SynthesisConfig(speaker_id=speaker, length_scale=length_scale, noise_scale=noise_scale,
                          noise_w_scale=noise_w)
    if ipa is not None:
        ids = voice.phonemes_to_ids(list(ipa))
        audio = voice.phoneme_ids_to_audio(ids, cfg)
        if isinstance(audio, tuple):
            audio = audio[0]
        sr = voice.config.sample_rate
    else:
        chunks = list(voice.synthesize(text, cfg))
        audio = np.concatenate([c.audio_float_array for c in chunks])
        sr = chunks[0].sample_rate
    audio = np.asarray(audio, np.float64)
    if sr != RATE:
        g = math.gcd(RATE, sr)
        audio = resample_poly(audio, RATE // g, sr // g)
    return audio


def trim(x, rel=0.02, lead=0.05, tail=0.08):
    """Cut synthetic (digital) silence, keeping short margins. Returns (audio, speech_start, speech_end)."""
    x = np.asarray(x, np.float64)
    act = np.flatnonzero(np.abs(x) > rel * max(np.max(np.abs(x)), 1e-9))
    if not len(act):
        return x, 0.0, len(x) / RATE
    a = max(0, act[0] - int(lead * RATE))
    b = min(len(x), act[-1] + 1 + int(tail * RATE))
    return x[a:b], (act[0] - a) / RATE, (act[-1] + 1 - a) / RATE


# ── the classifier: train, export, load, score ───────────────────────────────────────────────────

@dataclass
class MLP:
    """Folded weights, as on the device: sigmoid(w1 . relu(w0 x + b0) + b1)."""
    w0: np.ndarray            # (H, 1536)
    b0: np.ndarray            # (H,)
    w1: np.ndarray            # (1, H)
    b1: np.ndarray            # (1,)
    history: list = field(default_factory=list)

    def logits(self, X, batch=65536):
        out = np.empty(len(X), np.float32)
        for s in range(0, len(X), batch):
            h = np.maximum(np.asarray(X[s:s + batch], np.float32) @ self.w0.T + self.b0, 0)
            out[s:s + batch] = (h @ self.w1.T + self.b1)[:, 0]
        return out

    def predict(self, X):
        return 1 / (1 + np.exp(-self.logits(X).astype(np.float64)))

    def scores(self, feats):
        """Every score the device would produce for a clip: one per complete 16-embedding window."""
        return self.predict(sliding_windows(np.asarray(feats, np.float32)))


def train_mlp(X, y, w, val, hidden=32, epochs=25, batch=1024, lr=1e-3, weight_decay=1e-3,
              patience=5, seed=0, say=log, mine_rounds=0, mine_top=0.01, mine_boost=4.0, mine_epochs=6, l2=0.0):
    """Weighted BCE, Adam, early stopping on the validation rows; standardisation folded in.

    X: (N, 1536) float16/32 rows; y: 0/1; w: per-row weight; val: bool mask of validation rows.
    mine_rounds > 0: after training, the mine_top share of training negatives that score highest
    get mine_boost times their weight and training continues for mine_epochs (hard negatives).
    """
    mlp = _train_mlp(X, y, w, val, hidden, epochs, batch, lr, weight_decay, patience, seed, say, l2=l2)
    w = np.asarray(w, np.float32).copy()
    neg = np.flatnonzero((np.asarray(y) == 0) & ~val)
    for r in range(mine_rounds):
        scores = np.concatenate([mlp.predict(np.asarray(X[neg[s:s + 65536]], np.float32))
                                 for s in range(0, len(neg), 65536)])
        k = max(1, int(mine_top * len(neg)))
        hard = neg[np.argsort(scores)[-k:]]
        say(f'hard negatives, round {r + 1}: {k} rows, scores {scores[np.argsort(scores)[-k]]:.3f}..{scores.max():.3f}')
        w[hard] *= mine_boost
        mlp = _train_mlp(X, y, w, val, hidden, mine_epochs, batch, lr * 0.5, weight_decay, patience, seed + r + 1,
                         say, init=mlp, l2=l2)
    return mlp


def _train_mlp(X, y, w, val, hidden, epochs, batch, lr, weight_decay, patience, seed, say, init=None, l2=0.0):
    rng = np.random.default_rng(seed)
    tr = np.flatnonzero(~val)
    va = np.flatnonzero(val)
    # Standardisation statistics over the training rows, accumulated in float64 chunks.
    s1 = np.zeros(X.shape[1])
    s2 = np.zeros(X.shape[1])
    for s in range(0, len(tr), 50000):
        c = np.asarray(X[tr[s:s + 50000]], np.float64)
        s1 += c.sum(0)
        s2 += (c * c).sum(0)
    mean = s1 / len(tr)
    std = np.sqrt(np.maximum(s2 / len(tr) - mean ** 2, 0))
    std[std < 1e-6] = 1.0
    mean32, inv32 = mean.astype(np.float32), (1 / std).astype(np.float32)
    d = X.shape[1]
    if init is not None:
        # Continue from folded weights: unfold them with the same statistics.
        W0 = (init.w0 / inv32[None, :]).astype(np.float32)
        B0 = (init.b0 + init.w0 @ mean32).astype(np.float32)
        W1 = init.w1.astype(np.float32).copy()
        B1 = init.b1.astype(np.float32).copy()
    else:
        W0 = (rng.standard_normal((hidden, d)) * np.sqrt(2 / d)).astype(np.float32)
        B0 = np.zeros(hidden, np.float32)
        W1 = (rng.standard_normal((1, hidden)) * np.sqrt(1 / hidden)).astype(np.float32)
        B1 = np.zeros(1, np.float32)
    params = [W0, B0, W1, B1]
    # Adam's moments in float64: in float32 they decay into subnormal numbers, and subnormal
    # arithmetic made later epochs twenty times slower than the first.
    m = [np.zeros(p.shape) for p in params]
    v = [np.zeros(p.shape) for p in params]
    b1m, b2m, eps = 0.9, 0.999, 1e-8
    y32 = np.asarray(y, np.float32)
    w32 = np.asarray(w, np.float32)

    def forward(idx):
        xb = (np.asarray(X[idx], np.float32) - mean32) * inv32
        h = np.maximum(xb @ W0.T + B0, 0)
        z = (h @ W1.T + B1)[:, 0]
        return xb, h, z

    def loss_of(idx):
        tot, wsum = 0.0, 0.0
        for s in range(0, len(idx), 16384):
            part = idx[s:s + 16384]
            _, _, z = forward(part)
            l = np.logaddexp(0, z) - y32[part] * z
            tot += float(np.sum(w32[part] * l))
            wsum += float(np.sum(w32[part]))
        return tot / max(wsum, 1e-12)

    best, best_params, bad, t = np.inf, None, 0, 0
    history = []
    for epoch in range(epochs):
        t0 = time.time()
        order = rng.permutation(tr)
        for s in range(0, len(order), batch):
            idx = np.sort(order[s:s + batch])
            xb, h, z = forward(idx)
            # Clipped for the gradient only: exp(90) and beyond make subnormal probabilities, and the
            # gradient of an example that far on the right side is zero anyway.
            p = 1 / (1 + np.exp(-np.clip(z, -30, 30)))
            wb = w32[idx]
            dz = (wb * (p - y32[idx]) / max(float(wb.sum()), 1e-12)).astype(np.float32)
            gW1 = dz[None, :] @ h
            gB1 = np.array([dz.sum()], np.float32)
            dh = (dz[:, None] * W1) * (h > 0)
            gW0 = dh.T @ xb
            gB0 = dh.sum(0)
            if l2:
                gW0 += l2 * W0            # coupled L2, as scikit-learn's alpha
                gW1 += l2 * W1
            t += 1
            for k, (P, G) in enumerate(zip(params, [gW0, gB0, gW1, gB1])):
                G = G.astype(np.float64)
                m[k] = b1m * m[k] + (1 - b1m) * G
                v[k] = b2m * v[k] + (1 - b2m) * G * G
                mh = m[k] / (1 - b1m ** t)
                vh = v[k] / (1 - b2m ** t)
                if k in (0, 2):
                    P -= lr * weight_decay * P
                P -= (lr * mh / (np.sqrt(vh) + eps)).astype(np.float32)
            if t % 32 == 0:
                # Weights of hidden units that stopped firing decay geometrically into subnormal
                # numbers, and a matrix product over those is many times slower. They are zero anyway.
                for P in (W0, W1):
                    P[np.abs(P) < 1e-30] = 0
        vl = loss_of(va) if len(va) else float('nan')
        history.append(dict(epoch=epoch + 1, val_loss=round(vl, 5), secs=round(time.time() - t0, 1)))
        say(f'epoch {epoch + 1}: validation loss {vl:.5f} ({time.time() - t0:.1f}s)')
        if vl < best - 1e-5:
            best, bad = vl, 0
            best_params = [p.copy() for p in params]
        else:
            bad += 1
            if bad >= patience:
                break
    W0, B0, W1, B1 = best_params or params
    # Fold the standardisation into the first layer: no scaler exists on the device.
    w0 = (W0 * inv32[None, :]).astype('<f4')
    b0 = (B0 - (W0 * inv32[None, :]) @ mean32).astype('<f4')
    return MLP(flush(w0), flush(b0), flush(W1.astype('<f4')), flush(B1.astype('<f4')), history)


def flush(a, tiny=1e-30):
    """Subnormal (and near-subnormal) values to exactly zero."""
    a = np.array(a, copy=True)
    a[np.abs(a) < tiny] = 0
    return a


def merge_mlps(models):
    """One MLP whose logit is the mean of the models' logits: the hidden layers side by side, the
    output layer divided by their number. Same operators (FC, FC, LOGISTIC), wider hidden layer."""
    k = len(models)
    return MLP(np.concatenate([m.w0 for m in models]).astype('<f4'),
               np.concatenate([m.b0 for m in models]).astype('<f4'),
               (np.concatenate([m.w1 for m in models], axis=1) / k).astype('<f4'),
               (np.sum([m.b1 for m in models], axis=0) / k).astype('<f4'),
               history=[h for m in models for h in m.history])


def export_tflite(mlp: MLP, path, description):
    """The same flatbuffer train.py writes: float32, input [1,16,96], FC(RELU) -> FC -> LOGISTIC."""
    import flatbuffers
    import tflite
    hidden = mlp.w0.shape[0]
    b = flatbuffers.Builder(300000)

    def ints(values):
        b.StartVector(4, len(values), 4)
        for val in reversed(values):
            b.PrependInt32(int(val))
        return b.EndVector()

    def offsets(values):
        b.StartVector(4, len(values), 4)
        for val in reversed(values):
            b.PrependUOffsetTRelative(val)
        return b.EndVector()

    buffers = []
    for raw in [b'', mlp.w0.astype('<f4').tobytes(), mlp.b0.astype('<f4').tobytes(),
                mlp.w1.astype('<f4').tobytes(), mlp.b1.astype('<f4').tobytes()]:
        data = b.CreateByteVector(raw)
        tflite.BufferStart(b)
        tflite.BufferAddData(b, data)
        buffers.append(tflite.BufferEnd(b))
    tensors = []
    for name, shape, buf in [('input', [1, FRAMES, EMB], 0), ('w0', [hidden, FRAMES * EMB], 1),
                             ('b0', [hidden], 2), ('hidden', [1, hidden], 0), ('w1', [1, hidden], 3),
                             ('b1', [1], 4), ('logit', [1, 1], 0), ('score', [1, 1], 0)]:
        text = b.CreateString(name)
        dims = ints(shape)
        tflite.TensorStart(b)
        tflite.TensorAddName(b, text)
        tflite.TensorAddShape(b, dims)
        tflite.TensorAddType(b, tflite.TensorType.FLOAT32)
        tflite.TensorAddBuffer(b, buf)
        tensors.append(tflite.TensorEnd(b))
    codes = []
    for code in [tflite.BuiltinOperator.FULLY_CONNECTED, tflite.BuiltinOperator.LOGISTIC]:
        tflite.OperatorCodeStart(b)
        tflite.OperatorCodeAddBuiltinCode(b, code)
        tflite.OperatorCodeAddDeprecatedBuiltinCode(b, code)
        tflite.OperatorCodeAddVersion(b, 1)
        codes.append(tflite.OperatorCodeEnd(b))
    ops = []
    for inputs, output, relu in [([0, 1, 2], 3, True), ([3, 4, 5], 6, False)]:
        tflite.FullyConnectedOptionsStart(b)
        tflite.FullyConnectedOptionsAddFusedActivationFunction(
            b, tflite.ActivationFunctionType.RELU if relu else tflite.ActivationFunctionType.NONE)
        opt = tflite.FullyConnectedOptionsEnd(b)
        iv = ints(inputs)
        ov = ints([output])
        tflite.OperatorStart(b)
        tflite.OperatorAddOpcodeIndex(b, 0)
        tflite.OperatorAddInputs(b, iv)
        tflite.OperatorAddOutputs(b, ov)
        tflite.OperatorAddBuiltinOptionsType(b, tflite.BuiltinOptions.FullyConnectedOptions)
        tflite.OperatorAddBuiltinOptions(b, opt)
        ops.append(tflite.OperatorEnd(b))
    iv = ints([6])
    ov = ints([7])
    tflite.OperatorStart(b)
    tflite.OperatorAddOpcodeIndex(b, 1)
    tflite.OperatorAddInputs(b, iv)
    tflite.OperatorAddOutputs(b, ov)
    ops.append(tflite.OperatorEnd(b))
    tv = offsets(tensors)
    iv = ints([0])
    ov = ints([7])
    opv = offsets(ops)
    tflite.SubGraphStart(b)
    tflite.SubGraphAddTensors(b, tv)
    tflite.SubGraphAddInputs(b, iv)
    tflite.SubGraphAddOutputs(b, ov)
    tflite.SubGraphAddOperators(b, opv)
    graph = tflite.SubGraphEnd(b)
    gv = offsets([graph])
    bv = offsets(buffers)
    cv = offsets(codes)
    desc = b.CreateString(description)
    tflite.ModelStart(b)
    tflite.ModelAddVersion(b, 3)
    tflite.ModelAddSubgraphs(b, gv)
    tflite.ModelAddBuffers(b, bv)
    tflite.ModelAddOperatorCodes(b, cv)
    tflite.ModelAddDescription(b, desc)
    b.Finish(tflite.ModelEnd(b), file_identifier=b'TFL3')
    data = bytes(b.Output())
    Path(path).write_bytes(data)
    return data


def load_tflite_mlp(path) -> MLP:
    """Read back a classifier in export_tflite's layout (also the committed experimental model)."""
    import tflite
    buf = Path(path).read_bytes()
    m = tflite.Model.GetRootAsModel(buf, 0)
    g = m.Subgraphs(0)
    ops = [g.Operators(i) for i in range(g.OperatorsLength())]
    codes = [m.OperatorCodes(op.OpcodeIndex()).BuiltinCode() for op in ops]
    fc, lg = tflite.BuiltinOperator.FULLY_CONNECTED, tflite.BuiltinOperator.LOGISTIC
    if codes != [fc, fc, lg]:
        raise ValueError(f'{path}: operators {codes} are not FC, FC, LOGISTIC')

    def const(t):
        tensor = g.Tensors(t)
        data = m.Buffers(tensor.Buffer()).DataAsNumpy()
        shape = tensor.ShapeAsNumpy()
        return np.frombuffer(data.tobytes(), '<f4').reshape(shape).copy()

    inp = g.Tensors(g.Inputs(0)).ShapeAsNumpy().tolist()
    if inp[1:] != [FRAMES, EMB]:
        raise ValueError(f'{path}: input {inp} is not [1,{FRAMES},{EMB}]')
    w0, b0 = const(ops[0].Inputs(1)), const(ops[0].Inputs(2))
    w1, b1 = const(ops[1].Inputs(1)), const(ops[1].Inputs(2))
    return MLP(w0, b0, w1, b1)


# ── device-logic metrics ─────────────────────────────────────────────────────────────────────────

def detections(scores, cutoff, dead=DEAD_STEPS):
    """Steps at which echod would fire: score >= cutoff, then 14 steps (hold + refractory) deaf."""
    s = np.asarray(scores)
    hits, i = [], 0
    above = np.flatnonzero(s >= cutoff)
    for k in above:
        if k >= i:
            hits.append(int(k))
            i = k + dead
    return hits


def poisson_ci(k, conf=0.95):
    """Exact (Garwood) interval for a Poisson count."""
    from scipy.stats import chi2
    a = 1 - conf
    lo = 0.0 if k == 0 else chi2.ppf(a / 2, 2 * k) / 2
    hi = chi2.ppf(1 - a / 2, 2 * k + 2) / 2
    return float(lo), float(hi)


def wilson(k, n, z=1.96):
    if n == 0:
        return (float('nan'), float('nan'))
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (round(max(0.0, c - h), 4), round(min(1.0, c + h), 4))


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump_json(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, ensure_ascii=False) + '\n')
