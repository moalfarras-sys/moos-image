"""Train Mira's Arabic wake word («ميرا» / «يا ميرا» / «هاي ميرا»), on the owner's voice when there is one.

    python train_owner.py --owner DIR --out OUT [--id ID] [--negatives DIR] [--expect N]   # owner model
    python train_owner.py --out OUT --id mira_ar_v2 [--eval-captures DIR]                  # synthetic only

--owner DIR (or a positional OWNER_DIR) holds the owner's captures: 16 kHz mono 16-bit PCM WAV files,
each one Echo listening window (up to ~15 s) with several «ميرا» separated by pauses, possibly
starting with the tail of the Echo's wake sound. A file <name>.json beside <name>.wav with
{"utterances": [[start, end], ...]} (seconds) replaces the automatic segmentation for that file.
Without --owner the model is trained on the synthetic corpus alone.

What it does, in order:
  1. segments every capture by energy (speech band, floor-relative hysteresis thresholds, valley
     splitting), sets aside cut-off, faint and odd-length segments, warns when --expect N differs;
  2. holds out ~25 % of the owner's utterances BY FILE for evaluation;
  3. builds training clips: the owner's utterances augmented (speed +-8 %, level +-12 dB, synthetic
     rooms, noise at 5-20 dB SNR including the owner's own background), the owner's recordings as
     they are, the cached synthetic corpus (synth_corpus.py: Piper and Gemini voices, confusables,
     words and sentences; speaker variation by tape shift), the owner's --negatives, and ACAV100M
     background features. Every clip has real room sound around the word, no digital silence;
  4. computes every embedding with echod's own Go front end (mira_features_test.go, MIRA_PAD=0);
  5. trains the classifier shape the device already runs (16x96 -> FC(RELU) -> FC -> LOGISTIC,
     standardisation folded into the first layer) and exports it as float32 TFLite;
  6. evaluates on data it never trained on: owner holdout (recall per cutoff, per-utterance peaks),
     --eval-captures, synthetic holdout (unseen speakers), false accepts per hour on 10.7 h of
     held-out background, the committed model on the same data, and that echod's engine returns the
     same scores as the Python evaluation;
  7. writes OUT/<id>.tflite, OUT/<id>.json (echod manifest), OUT/report.json, OUT/report.md and
     OUT/train.log, including a recommended cutoff.

Nothing here connects to the Echo. Owner audio is read in place; derived features stay in the cache
directory (MIRA_WAKE_CACHE, else MIRA_WAKE_TRAIN_ENV, else ~/.cache/mira-claude/wake).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

import synth_corpus
import wakelib as wl

CUTOFFS = [round(0.50 + 0.05 * k, 2) for k in range(10)]         # 0.50 .. 0.95
REPORT_CUTOFFS = (0.5, 0.6, 0.7)
COMMITTED = wl.HERE / 'mira_ar_experimental.tflite'
BG_PATH = 'data/validation_set_features.npy'
ACAV_PATH = 'data/acav100m_sample_300x500.npy'

# Relative training weight per row group inside its class; --pos-share splits the total between the
# classes. An empty group's weight goes to the rest of its class.
MASS = {
    'owner_aug': 0.20, 'owner_orig': 0.03, 'synth_pos': 0.12,
    'acav': 0.28, 'confusable': 0.14, 'speech': 0.12, 'bed': 0.03,
    'owner_bg': 0.05, 'owner_neg': 0.03,
}
POSITIVE_GROUPS = {'owner_aug', 'owner_orig', 'synth_pos'}
OWNER_GROUPS = {'owner_aug', 'owner_orig', 'owner_bg', 'owner_neg'}


def key_of(*parts):
    """A stable 63-bit number for a clip, so its augmentation does not depend on what else is in the run."""
    h = hashlib.sha1()
    for p in parts:
        h.update(p.tobytes() if isinstance(p, np.ndarray) else repr(p).encode())
    return int.from_bytes(h.digest()[:8], 'little') >> 1


# ── owner captures ───────────────────────────────────────────────────────────────────────────────

@dataclass
class Capture:
    path: Path
    audio: np.ndarray
    segments: list
    info: dict
    split: str = 'train'
    warnings: list = field(default_factory=list)

    @property
    def utterances(self):
        return [s for s in self.segments if s.kind == 'speech']

    @property
    def name(self):
        return self.path.name


def load_captures(folder, args, say):
    files = sorted(Path(folder).glob('*.wav'))
    if not files:
        raise SystemExit(f'{folder}: no .wav files')
    caps = []
    for f in files:
        x = wl.read_wav(f)
        labels = f.with_suffix('.json')
        if labels.exists():
            spans = json.loads(labels.read_text())['utterances']
            segs = [wl.Segment(float(a), float(b), 'speech', note='labels file') for a, b in spans]
            info = dict(duration=round(len(x) / wl.RATE, 2), labels=labels.name)
        else:
            segs, info = wl.segment_speech(x, merge_gap=args.merge_gap, min_dur=args.min_utt,
                                           max_dur=args.max_utt)
        cap = Capture(f, x, segs, info)
        if 'warning' in info:
            cap.warnings.append(info['warning'])
        n = len(cap.utterances)
        if args.expect is not None and n != args.expect:
            cap.warnings.append(f'found {n} utterances, expected {args.expect}')
        other = [f'{s.kind} {s.start:.2f}-{s.end:.2f}s' for s in segs if s.kind != 'speech']
        say(f'{f.name}: {len(x) / wl.RATE:.1f}s, {n} utterance(s)'
            + (f', set aside: {", ".join(other)}' if other else '')
            + (f'  WARNING: {"; ".join(cap.warnings)}' if cap.warnings else ''))
        caps.append(cap)
    return caps


def split_by_file(caps, frac, seed):
    """Hold out whole files until ~frac of all utterances are held out (at least one file)."""
    usable = [c for c in caps if c.utterances]
    if len(usable) < 2:
        raise SystemExit('need at least two captures with utterances to hold one out by file')
    order = sorted(usable, key=lambda c: hashlib.sha256(f'{seed}:{c.name}'.encode()).hexdigest())
    total = sum(len(c.utterances) for c in usable)
    held = 0
    for c in order:
        if held >= frac * total or held + len(c.utterances) > 0.5 * total and held > 0:
            break
        c.split = 'holdout'
        held += len(c.utterances)
    if all(c.split == 'holdout' for c in usable):
        order[-1].split = 'train'
    return [c for c in caps if c.split == 'train'], [c for c in caps if c.split == 'holdout']


def with_context(cap: Capture, pre=2.5, post=1.0):
    """The capture with some of its own background before and after it, so the windows around the
    first and last utterance hold real room sound rather than the exporter's digital silence.
    Returns (int16 stream, offset seconds)."""
    rng = np.random.default_rng(key_of('context', cap.name))
    bg = wl.background_audio(cap.audio, cap.segments)
    if len(bg) < 0.3 * wl.RATE:
        level = 10 ** (cap.info.get('floor_db', -70) / 20)
        bg = wl.to_int16(wl.colored_noise(rng, 2 * wl.RATE, 'pink') * max(level, 1e-4))
    a = wl.fit_length(wl.to_float(bg), int(pre * wl.RATE), rng)
    b = wl.fit_length(wl.to_float(bg), int(post * wl.RATE), rng)
    x = wl.to_float(cap.audio).copy()
    xf = 160
    ramp = np.linspace(0, 1, xf)
    x[:xf] = x[:xf] * ramp + a[-xf:] * (1 - ramp)
    x[-xf:] = x[-xf:] * (1 - ramp) + b[:xf] * ramp
    return wl.to_int16(np.concatenate([a, x, b])), pre


# ── augmentation ─────────────────────────────────────────────────────────────────────────────────

class NoisePool:
    """Noise beds: the owner's own background, steady synthetic noises and synthetic babble."""

    def __init__(self, owner_backgrounds, babble_sources):
        self.owner = [wl.to_float(b) for b in owner_backgrounds if len(b) >= 0.5 * wl.RATE]
        self.babble_src = babble_sources

    def babble(self, n, rng):
        out = np.zeros(n)
        for _ in range(int(rng.integers(3, 7))):
            src = wl.to_float(self.babble_src[int(rng.integers(len(self.babble_src)))])
            src = src / (wl.active_rms(src) + 1e-9)
            out += wl.fit_length(np.concatenate([src, np.zeros(int(rng.uniform(0.1, 0.6) * wl.RATE))]), n, rng)
        return out / (np.sqrt(np.mean(out ** 2)) + 1e-12)

    def extra(self, n, rng):
        """Unit-RMS noise of a random kind, and its name."""
        kinds = ['pink', 'brown', 'white', 'fan', 'hum'] + (['babble'] * 2 if self.babble_src else [])
        kinds += ['owner'] * 3 if self.owner else []
        kind = kinds[int(rng.integers(len(kinds)))]
        if kind == 'owner':
            y = wl.fit_length(self.owner[int(rng.integers(len(self.owner)))], n, rng)
        elif kind == 'babble':
            y = self.babble(n, rng)
        else:
            y = wl.colored_noise(rng, n, kind)
        return y / (np.sqrt(np.mean(y ** 2)) + 1e-12), kind

    def floor(self, n, rng):
        """A quiet room: the owner's own background at its own level, else soft steady noise."""
        if self.owner and rng.random() < 0.8:
            return wl.fit_length(self.owner[int(rng.integers(len(self.owner)))], n, rng)
        kind = ['pink', 'brown', 'fan'][int(rng.integers(3))]
        return wl.colored_noise(rng, n, kind) * 10 ** (rng.uniform(-68, -48) / 20)


def bed(speech, span, rng, pool, *, owner, augment=True, pre=(2.2, 2.7), post=(0.7, 1.1),
        speech_level=None, min_len=2.6):
    """Place float audio holding an utterance at span=(s, e) seconds into a noise bed.

    owner=True keeps the capture's own level (it already passed the Echo's leveller); synthetic
    speech is first set to the leveller's -23 dBFS target. Augmentation: speed 0.92-1.08, a
    synthetic room (p 0.4 owner / 0.7 synthetic), extra noise at 5-20 dB SNR (p 0.75), level
    +-12 dB (peak kept below -1 dBFS, as the leveller keeps it). Returns (int16 clip, (s, e), meta).
    """
    x = np.asarray(speech, np.float64)
    s, e = span
    if not owner:
        target = speech_level if speech_level is not None else 10 ** (-23 / 20)
        x = x * target / (wl.active_rms(x) + 1e-12)
    meta = {}
    if augment:
        f = float(rng.uniform(0.92, 1.08))
        x = wl.speed(x, f)
        s, e = s / f, e / f
        meta['speed'] = round(f, 3)
        if rng.random() < (0.4 if owner else 0.7):
            ir = wl.synth_rir(rng, rng.uniform(0.15, 0.6) if owner else None)
            x = wl.reverb(np.concatenate([x, np.zeros(int(0.3 * wl.RATE))]), ir)
            meta['room'] = True
    lead = float(rng.uniform(*pre))
    tail = float(rng.uniform(*post))
    start = int((lead - s) * wl.RATE)
    if start < 0:
        x = x[-start:]
        start = 0
    n = max(start + len(x), int((lead + (e - s) + tail) * wl.RATE), int(min_len * wl.RATE))
    mix = pool.floor(n, rng)
    xf = min(160, len(x) // 4)
    if xf:
        ramp = np.linspace(0, 1, xf)
        x = x.copy()
        x[:xf] *= ramp
        x[-xf:] *= ramp[::-1]
    mix[start:start + len(x)] += x
    if augment and rng.random() < 0.75:
        noise, kind = pool.extra(n, rng)
        snr = float(rng.uniform(5, 20))
        mix += noise * wl.active_rms(x) / 10 ** (snr / 20)
        meta.update(noise=kind, snr=round(snr, 1))
    if augment:
        g = 10 ** (rng.uniform(-12, 12) / 20)
        mix *= min(g, 0.89 / (np.abs(mix).max() + 1e-12))
    return wl.to_int16(mix), (lead, lead + (e - s)), meta


def excerpt(cap: Capture, seg, margin=0.3):
    """The utterance with up to `margin` s of its own capture around it."""
    a = max(0.0, seg.start - margin)
    b = min(len(cap.audio) / wl.RATE, seg.end + margin)
    x = wl.to_float(cap.audio[int(a * wl.RATE):int(b * wl.RATE)])
    return x, (seg.start - a, seg.end - a)


# ── windows and labels ───────────────────────────────────────────────────────────────────────────

@dataclass
class Item:
    clip: np.ndarray | None
    group: str                  # a MASS key, 'owner_stream', or 'eval'
    span: tuple | None = None   # utterance (s, e) in clip seconds for positive clips
    val: bool = False
    regions: list | None = None # capture streams: (kind, start, end) of every segment
    meta: dict = field(default_factory=dict)


def label_windows(n_emb, item: Item, pos_window):
    """(indices, labels, groups) of the windows of one clip that train anything."""
    n_win = max(0, n_emb - wl.FRAMES + 1)
    if n_win == 0:
        return np.zeros(0, int), np.zeros(0), []
    idx = np.arange(n_win)
    t_end = wl.window_end_time(idx, pad=0)
    t_start = (wl.STEP * idx + wl.EMB_START) / wl.RATE        # where the window's first embedding starts
    lo, hi = pos_window
    if item.group in ('synth_pos', 'owner_aug'):
        s, e = item.span
        pos = idx[(t_end >= e + lo) & (t_end <= e + hi)]
        bed_only = idx[(t_end < s - 0.05) | (t_start > e + 0.05)]
        return (np.concatenate([pos, bed_only]), np.concatenate([np.ones(len(pos)), np.zeros(len(bed_only))]),
                [item.group] * len(pos) + ['bed'] * len(bed_only))
    if item.group == 'owner_stream':
        # A capture as it was recorded: windows ending just after an utterance are positives and
        # windows touching no segment at all are the owner's room. Windows touching speech elsewhere,
        # or a cut-off / faint / odd-length segment, teach nothing.
        keep, lab, grp = [], [], []
        speech = [(a, b) for k, a, b in item.regions if k == 'speech']
        unsure = [(a, b) for k, a, b in item.regions if k != 'speech']
        for w in idx:
            te, ts = t_end[w], t_start[w]

            def touches(spans):
                return any(ts < b + 0.1 and te > a - 0.1 for a, b in spans)
            if any(e + lo <= te <= e + hi for _, e in speech):
                keep.append(w), lab.append(1), grp.append('owner_orig')
            elif not touches(speech) and not touches(unsure):
                keep.append(w), lab.append(0), grp.append('owner_bg')
        return np.array(keep, int), np.array(lab, float), grp
    # Negative clips: every window.
    return idx, np.zeros(n_win), [item.group] * n_win


def assemble(items, feats, acav, pos_window, groups_used, say, pos_share=0.1, balance_families=False):
    """Rows (float16) for every labelled window, their labels, weights and validation mask."""
    per = []
    total = len(acav)
    for it, f in zip(items, feats):
        idx, lab, grp = label_windows(len(f), it, pos_window)
        per.append((idx, lab, grp))
        total += len(idx)
    X = np.empty((total, wl.FRAMES * wl.EMB), np.float16)
    y = np.empty(total, np.float32)
    g = np.empty(total, object)
    fam = np.empty(total, object)
    val = np.zeros(total, bool)
    X[:len(acav)] = acav.reshape(len(acav), -1)
    y[:len(acav)] = 0
    g[:len(acav)] = 'acav'
    fam[:len(acav)] = ''
    val[:len(acav)] = (np.arange(len(acav)) // 500) % 12 == 0      # whole 500-window chunks
    pos = len(acav)
    for (idx, lab, grp), it, f in zip(per, items, feats):
        if not len(idx):
            continue
        win = wl.sliding_windows(np.asarray(f, np.float32))[idx]
        X[pos:pos + len(idx)] = win
        y[pos:pos + len(idx)] = lab
        g[pos:pos + len(idx)] = grp
        fam[pos:pos + len(idx)] = it.meta.get('family', '')
        val[pos:pos + len(idx)] = it.val
        pos += len(idx)
    groups = {k: int((g == k).sum()) for k in MASS}
    w = np.zeros(total, np.float32)
    for cls in (1, 0):
        names = [k for k in MASS if (k in POSITIVE_GROUPS) == (cls == 1) and groups[k] and k in groups_used]
        mass = sum(MASS[k] for k in names)
        share = pos_share if cls == 1 else 1 - pos_share
        for k in names:
            rows_k = g == k
            fams = sorted(set(fam[rows_k]) - {''})
            if k == 'synth_pos' and len(fams) > 1 and balance_families:
                # Every synthetic voice family (Piper Kareem, Gemini, ...) carries the same weight, so a
                # few natural voices are not drowned by hundreds of clips of one synthetic speaker.
                for f_ in fams:
                    sel = rows_k & (fam == f_) & (y == 1)
                    w[sel] = share * MASS[k] / mass / len(fams) / max(1, sel.sum())
                w[rows_k & (y == 0)] = share * MASS[k] / mass / max(1, groups[k])
            else:
                w[rows_k] = share * MASS[k] / mass / groups[k]
    w *= total / w.sum()
    say('training rows: ' + ', '.join(f'{k} {v}' for k, v in groups.items() if v))
    return X, y, w, val, groups


# ── evaluation ───────────────────────────────────────────────────────────────────────────────────

def utterance_peaks(scores, offset, cap: Capture, next_gap=0.15, after=1.0):
    """Peak score attributed to each utterance, and which windows belong to an utterance."""
    t_end = wl.window_end_time(np.arange(len(scores)), pad=0) - offset
    utts = cap.utterances
    peaks = []
    region = np.zeros(len(scores), bool)
    for k, u in enumerate(utts):
        hi = u.end + after
        if k + 1 < len(utts):
            hi = min(hi, utts[k + 1].start + next_gap)
        m = (t_end >= u.start + 0.15) & (t_end <= hi)
        region |= m
        peaks.append(float(scores[m].max()) if m.any() else 0.0)
    return peaks, region, t_end


def capture_features(caps, fe, desc):
    streams, offsets = [], []
    for c in caps:
        s, off = with_context(c)
        streams.append(s)
        offsets.append(off)
    return streams, offsets, fe.features(streams, pad=0, desc=desc)


def eval_captures(models, caps, feats, offsets):
    """Device-logic peaks per utterance and false detections outside utterances, per model."""
    out = {}
    for name, m in models.items():
        rows, false = [], {c: 0 for c in CUTOFFS}
        for c, f, off in zip(caps, feats, offsets):
            sc = m.scores(f)
            peaks, region, _ = utterance_peaks(sc, off, c)
            for u, p in zip(c.utterances, peaks):
                rows.append(dict(file=c.name, start=u.start, end=u.end, peak=round(p, 4)))
            for cut in CUTOFFS:
                false[cut] += sum(1 for h in wl.detections(sc, cut) if not region[h])
        out[name] = dict(utterances=rows, false_detections=false)
    return out


def capture_summary(res, audio_s):
    out = {}
    for name, r in res.items():
        peaks = np.array([u['peak'] for u in r['utterances']])
        out[name] = dict(
            utterances=int(len(peaks)),
            recall={str(c): round(float(np.mean(peaks >= c)), 4) if len(peaks) else None for c in CUTOFFS},
            recall_ci95={str(c): wl.wilson(int(np.sum(peaks >= c)), len(peaks)) for c in REPORT_CUTOFFS},
            weakest_peak=round(float(peaks.min()), 4) if len(peaks) else None,
            median_peak=round(float(np.median(peaks)), 4) if len(peaks) else None,
            false_detections_outside_utterances={str(c): v for c, v in r['false_detections'].items()})
    per = []
    names = list(res)
    for k, u in enumerate(res[names[0]]['utterances']):
        row = dict(u)
        for other in names[1:]:
            row[f'{other}_peak'] = res[other]['utterances'][k]['peak']
        per.append(row)
    return dict(audio_seconds=round(audio_s, 1), models=out, per_utterance=per)


def eval_synthetic(models, items, feats):
    """Per synthetic holdout clip: positives' peak near the utterance, negatives' peak anywhere."""
    out = {}
    for name, m in models.items():
        res = {}
        for it, f in zip(items, feats):
            sc = m.scores(f)
            if not len(sc):
                continue
            t_end = wl.window_end_time(np.arange(len(sc)), pad=0)
            if it.meta['label'] == 1:
                s, e = it.span
                mask = (t_end >= s + 0.15) & (t_end <= e + 1.0)
                peak = float(sc[mask].max()) if mask.any() else 0.0
            else:
                peak = float(sc.max())
            key = (it.meta['group'], it.meta['voice'], it.meta['text'])
            res.setdefault(key, []).append(peak)
        out[name] = res
    return out


def voice_family(voice):
    return 'gemini' if voice.startswith('gemini:') else voice


def summarize_synthetic(res):
    def rate(peaks, c):
        return round(float(np.mean(np.array(peaks) >= c)), 4)
    table = {}
    for (group, voice, text), peaks in sorted(res.items()):
        table.setdefault(group, {}).setdefault(voice, {})[text] = dict(
            clips=len(peaks), **{f'rate@{c}': rate(peaks, c) for c in REPORT_CUTOFFS},
            median_peak=round(float(np.median(peaks)), 4))
    overall, by_family = {}, {}
    for group in ('positive', 'confusable', 'speech'):
        peaks = [p for (g, _, _), v in res.items() if g == group for p in v]
        if peaks:
            overall[group] = dict(clips=len(peaks), **{f'rate@{c}': rate(peaks, c) for c in CUTOFFS})
        fams = sorted({voice_family(v) for (g, v, _) in res if g == group})
        for fam in fams:
            fp = [p for (g, v, _), vals in res.items() if g == group and voice_family(v) == fam for p in vals]
            by_family.setdefault(group, {})[fam] = dict(clips=len(fp), **{f'rate@{c}': rate(fp, c) for c in REPORT_CUTOFFS},
                                                       median_peak=round(float(np.median(fp)), 4))
    return overall, by_family, table


def background_scores(m, bg, chunk=40000):
    """Scores for every stride-1 window of the continuous background stream (as on the device)."""
    out = []
    for s in range(0, len(bg) - wl.FRAMES + 1, chunk):
        part = np.asarray(bg[s:s + chunk + wl.FRAMES - 1], np.float32)
        out.append(m.scores(part))
    return np.concatenate(out)


def eval_background(models, bg, tail_from):
    hours = len(bg) * 0.08 / 3600
    tail_hours = (len(bg) - tail_from) * 0.08 / 3600
    out = {}
    for name, m in models.items():
        sc = background_scores(m, bg)
        r = dict(hours=round(hours, 3), windows=len(sc), peak=round(float(sc.max()), 4), cutoffs={})
        for c in CUTOFFS:
            hits = wl.detections(sc, c)
            tail_hits = [h for h in hits if h >= tail_from]
            lo, hi = wl.poisson_ci(len(hits))
            r['cutoffs'][str(c)] = dict(
                false_windows=int((sc >= c).sum()), detections=len(hits),
                fa_per_hour=round(len(hits) / hours, 3), fa_per_hour_ci95=[round(lo / hours, 3), round(hi / hours, 3)],
                tail_detections=len(tail_hits), tail_fa_per_hour=round(len(tail_hits) / tail_hours, 3))
        out[name] = r
    return out


def recommend(recall, fa, fa_target, reference, what):
    """The recommended cutoff (README, "Choosing the cutoff")."""
    ok = [c for c in CUTOFFS if fa[c] <= fa_target]
    if not ok:
        c = CUTOFFS[-1]
        return c, (f'no cutoff up to {c} keeps background false accepts at or below {fa_target}/h; '
                   f'{c} is the strictest offered, retrain with more negatives')
    c_min = min(ok)
    if recall.get(c_min) is None or reference is None:
        return c_min, f'lowest cutoff with background false accepts <= {fa_target}/h'
    if recall[c_min] < 1.0 and what == 'the weakest held-out owner utterance':
        return c_min, (f'lowest cutoff with background false accepts <= {fa_target}/h; held-out recall '
                       f'there is {recall[c_min]:.3f}, so no stricter cutoff is suggested')
    target = math.floor((reference - 0.10) * 20 + 1e-9) / 20
    c = min(max(c_min, target), 0.9)
    c = max(x for x in CUTOFFS if x <= c + 1e-9)
    return c, (f'0.10 below {what} (peak {reference:.3f}), rounded down to the 0.05 grid, but not below '
               f'{c_min} (the lowest cutoff with <= {fa_target} false accepts/h on the background set) '
               f'and not above 0.90')


# ── the run ──────────────────────────────────────────────────────────────────────────────────────

def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('owner_dir', type=Path, nargs='?', help='directory of the owner captures (*.wav)')
    ap.add_argument('--owner', type=Path, help='the same as OWNER_DIR')
    ap.add_argument('--out', type=Path, required=True, help='output directory')
    ap.add_argument('--model-id', '--id', dest='model_id', default=None,
                    help='file names and echod model id ([a-z0-9_], 3-40 characters); default '
                         'mira_ar_owner with owner captures, mira_ar_v2 without')
    ap.add_argument('--negatives', type=Path, help='directory of owner clips WITHOUT the wake word (*.wav)')
    ap.add_argument('--expect', type=int, help='utterances expected per capture (warns when different)')
    ap.add_argument('--strict', action='store_true',
                    help='with --expect: leave out captures whose utterance count differs (instead of only warning)')
    ap.add_argument('--eval-captures', type=Path,
                    help='captures (same format as --owner) used ONLY for evaluation, e.g. a stand-in speaker')
    ap.add_argument('--holdout', type=float, default=0.25, help='share of owner utterances held out, by file')
    ap.add_argument('--phrase', default='ميرا', help='wake_word in the manifest (what echod reports)')
    ap.add_argument('--aug', type=int, default=40, help='augmented copies per owner utterance')
    ap.add_argument('--synth-aug', type=int, default=2, help='augmented copies per synthetic (Piper) positive')
    ap.add_argument('--gemini-aug', type=int, default=6, help='augmented copies per Gemini positive (few, natural voices)')
    ap.add_argument('--tape', default='0.84,1.16',
                    help='range of speaker-size factors (tape shift, pitch and formants together) for 60 %% of the '
                         'synthetic positives')
    ap.add_argument('--balance-families', action='store_true',
                    help='give every synthetic voice family the same weight instead of weighting by clip count '
                         '(measured: more Gemini-voice recall, less of everything else)')
    ap.add_argument('--positive-voices', default='ar_JO-kareem-medium,gemini',
                    help='synthetic voices whose «ميرا» clips train (comma-separated; "gemini" = every Gemini '
                         'voice); the other voices add negatives only')
    ap.add_argument('--hidden', type=int, default=32, help='hidden units per ensemble member (the committed model: 32)')
    ap.add_argument('--ensemble', type=int, default=3,
                    help='train this many seeds and average their logits (exported as ONE FC-FC-LOGISTIC model '
                         'with ensemble x hidden units)')
    ap.add_argument('--pos-share', type=float, default=0.1,
                    help='share of the training weight on positives (0.35: ~200 false accepts/h; 0.03: recall collapses)')
    ap.add_argument('--l2', type=float, default=0.01, help='L2 penalty on the weights (added to the gradient)')
    ap.add_argument('--epochs', type=int, default=25, help='most epochs per member (early stopping usually ends sooner)')
    ap.add_argument('--mine-rounds', type=int, default=2,
                    help='hard-negative rounds after training (each: the top 1 %% of negatives x4, up to 6 more epochs)')
    ap.add_argument('--seed', type=int, default=7)
    ap.add_argument('--fa-target', type=float, default=1.0,
                    help='background false accepts per hour allowed when recommending a cutoff')
    ap.add_argument('--pos-window', default='0.08,0.40', help='positive windows end this many seconds after an utterance')
    ap.add_argument('--merge-gap', type=float, default=0.25, help='pauses shorter than this join one utterance')
    ap.add_argument('--min-utt', type=float, default=0.15)
    ap.add_argument('--max-utt', type=float, default=1.8)
    ap.add_argument('--synthetic-only', action='store_true',
                    help='ablation: do not train on the owner captures, only evaluate on their holdout')
    ap.add_argument('--refit-all', action='store_true',
                    help='after evaluating, retrain on every capture (holdout included) and export that model')
    ap.add_argument('--baseline', type=Path, default=COMMITTED, help='model to compare against')
    ap.add_argument('--baseline-cutoff', type=float, default=0.60,
                    help="the baseline's working cutoff on the device (0.60 was measured); without owner captures "
                         "the recommended cutoff keeps false accepts at or below the baseline's there")
    ap.add_argument('--workers', type=int, help='parallel front-end workers (default: all CPUs)')
    args = ap.parse_args(argv)
    args.owner_dir = args.owner_dir or args.owner
    if args.model_id is None:
        args.model_id = 'mira_ar_owner' if args.owner_dir else 'mira_ar_v2'
    if not re.fullmatch(r'[a-z0-9_]{3,40}', args.model_id):
        ap.error('--id must be 3-40 characters of a-z, 0-9 and _ (echod and the Mira model server use it as a file name)')
    if args.synthetic_only and not args.owner_dir:
        ap.error('--synthetic-only is an ablation against owner captures; without --owner every run is synthetic')
    args.pos_window = tuple(float(v) for v in args.pos_window.split(','))
    args.tape = tuple(float(v) for v in args.tape.split(','))
    return args


def uses_voice(voice, wanted):
    return voice in wanted or voice.split(':')[0] in wanted


def prepare(args, say):
    """Everything up to the training rows: captures, split, clips, embeddings. Returns a context."""
    root = wl.cache_root()
    for p in (root / BG_PATH, root / ACAV_PATH):
        if not p.exists():
            raise SystemExit(f'{p} missing; run setup.sh')
    ctx = dict(timings={})
    fe = ctx['fe'] = wl.GoFrontEnd(root, workers=args.workers)

    t0 = time.time()
    caps, train_caps, hold_caps = [], [], []
    if args.owner_dir:
        caps = load_captures(args.owner_dir, args, say)
        usable = caps
        if args.strict and args.expect is not None:
            dropped = [c for c in caps if len(c.utterances) != args.expect]
            for c in dropped:
                c.split = 'excluded'
                c.warnings.append('left out (--strict)')
            say(f'--strict: left out {len(dropped)} capture(s) whose count differs from {args.expect}')
            usable = [c for c in caps if c.split != 'excluded']
        train_caps, hold_caps = split_by_file(usable, args.holdout, args.seed)
        say(f'split by file: {len(train_caps)} capture(s) / {sum(len(c.utterances) for c in train_caps)} utterances '
            f'train, {len(hold_caps)} capture(s) / {sum(len(c.utterances) for c in hold_caps)} utterances held out')
    eval_caps = []
    if args.eval_captures:
        say(f'evaluation-only captures from {args.eval_captures}:')
        eval_caps = load_captures(args.eval_captures, args, say)
        for c in eval_caps:
            c.split = 'eval'
    negs = []
    if args.negatives:
        negs = [(f, wl.read_wav(f)) for f in sorted(args.negatives.glob('*.wav'))]
        say(f'owner negatives: {len(negs)} file(s), {sum(len(x) for _, x in negs) / wl.RATE:.1f}s')
    neg_train = [(f, x) for k, (f, x) in enumerate(negs) if k % 4 != 3 or len(negs) < 4]
    neg_hold = [(f, x) for k, (f, x) in enumerate(negs) if k % 4 == 3 and len(negs) >= 4]
    ctx['timings']['segmentation'] = round(time.time() - t0, 1)

    t0 = time.time()
    syn_clips, syn_meta = synth_corpus.build(say=say)
    wanted = set(args.positive_voices.split(','))
    keep = [k for k, m in enumerate(syn_meta) if m['label'] == 0 or uses_voice(m['voice'], wanted)]
    syn_clips, syn_meta = [syn_clips[k] for k in keep], [syn_meta[k] for k in keep]
    ctx['timings']['synthetic_corpus'] = round(time.time() - t0, 1)

    t0 = time.time()
    use_owner = bool(train_caps) and not args.synthetic_only
    owner_bg = [wl.background_audio(c.audio, c.segments) for c in train_caps] if use_owner else []
    babble = [c for c, m in zip(syn_clips, syn_meta) if m['group'] == 'speech' and not m['holdout']]
    pool = NoisePool(owner_bg, babble)
    items = []

    def rng_for(*parts):
        return np.random.default_rng([args.seed, key_of(*parts)])

    def owner_items(capture_list):
        out = []
        for c in capture_list:
            for u in c.utterances:
                x, span = excerpt(c, u)
                for k in range(args.aug):
                    clip, sp, meta = bed(x, span, rng_for('owner', c.name, round(u.start, 3), k), pool, owner=True)
                    out.append(Item(clip, 'owner_aug', sp, val=(k % 10 == 9), meta=meta))
            stream, off = with_context(c)
            out.append(Item(stream, 'owner_stream', regions=[(s.kind, s.start + off, s.end + off) for s in c.segments]))
        return out
    ctx['owner_items'] = owner_items
    if use_owner:
        items += owner_items(train_caps)
        for f, x in neg_train:
            xf = wl.to_float(x)
            span = (0.0, len(xf) / wl.RATE)
            clip, _, meta = bed(xf, span, rng_for('neg', f.name, -1), pool, owner=True, augment=False,
                                pre=(2.0, 2.6), post=(0.3, 1.0))
            items.append(Item(clip, 'owner_neg', meta=meta))
            for k in range(3):
                clip, _, meta = bed(xf, span, rng_for('neg', f.name, k), pool, owner=True, pre=(2.0, 2.6), post=(0.3, 1.0))
                items.append(Item(clip, 'owner_neg', val=(k == 2), meta=meta))
    syn_hold = []
    eval_pool = NoisePool([], babble)
    for clip, m in zip(syn_clips, syn_meta):
        x = wl.to_float(clip)
        span = (m['speech_start'], m['speech_end'])
        ck = key_of(clip)
        if m['holdout']:
            # The same evaluation clips in every run, whatever the seed.
            c2, sp, meta = bed(x, span, np.random.default_rng(key_of('eval', ck)), eval_pool, owner=False)
            syn_hold.append(Item(c2, 'eval', sp, meta=dict(meta, **m)))
            continue
        val = ck % 10 == 0
        if m['label'] == 1:
            family = voice_family(m['voice'])
            for k in range(args.gemini_aug if family == 'gemini' else args.synth_aug):
                r = rng_for('syn', ck, k)
                x2 = x
                if r.random() < 0.6:             # another speaker size: pitch and formants together
                    x2 = wl.tape_shift(x, float(r.uniform(*args.tape)))
                c2, sp, meta = bed(x2, span, r, pool, owner=False)
                items.append(Item(c2, 'synth_pos', sp, val=val, meta=dict(meta, family=family)))
        else:
            # The word ends up both at the end of some windows (where a positive would fire) and
            # in the middle of later ones.
            c2, _, meta = bed(x, span, rng_for('syn', ck, 0), pool, owner=False, pre=(2.0, 2.6), post=(0.3, 1.2))
            items.append(Item(c2, m['group'], val=val, meta=meta))
    say(f'built {len(items)} training clips ({sum(len(i.clip) for i in items) / wl.RATE / 3600:.2f} h) '
        f'and {len(syn_hold)} synthetic holdout clips')
    ctx['timings']['augmentation'] = round(time.time() - t0, 1)

    t0 = time.time()
    feats = fe.features([i.clip for i in items], pad=0, desc='training clips')
    hold_feats = fe.features([i.clip for i in syn_hold], pad=0, desc='synthetic holdout clips')
    for it in items + syn_hold:
        it.clip = None                      # the embeddings are all that is needed from here on
    cap_eval = {}
    for name, cl in (('holdout', hold_caps), ('eval_captures', eval_caps)):
        if cl:
            streams, offsets, cf = capture_features(cl, fe, f'{name} captures')
            cap_eval[name] = dict(caps=cl, streams=streams, offsets=offsets, feats=cf)
    neg_feats = fe.features([x for _, x in neg_hold], pad=0, desc='held-out owner negatives') if neg_hold else []
    ctx['timings']['front_end'] = round(time.time() - t0, 1)
    used = set(MASS) - (set() if use_owner else OWNER_GROUPS)
    ctx.update(wanted=wanted, caps=caps, train_caps=train_caps, hold_caps=hold_caps, eval_caps=eval_caps, neg_train=neg_train,
               neg_hold=neg_hold, neg_feats=neg_feats, syn_meta=syn_meta, items=items, feats=feats,
               syn_hold=syn_hold, hold_feats=hold_feats, cap_eval=cap_eval, used=used, pool=pool,
               use_owner=use_owner, rng_for=rng_for,
               acav=np.load(root / ACAV_PATH, mmap_mode='r'), bg=np.load(root / BG_PATH, mmap_mode='r'))
    return ctx


def fit(ctx, args, say, items=None, feats=None):
    items = ctx['items'] if items is None else items
    feats = ctx['feats'] if feats is None else feats
    X, y, w, val, rows = assemble(items, feats, ctx['acav'], args.pos_window, ctx['used'], say, pos_share=args.pos_share,
                                  balance_families=args.balance_families)
    members = []
    for k in range(max(1, args.ensemble)):
        if args.ensemble > 1:
            say(f'ensemble member {k + 1}/{args.ensemble}')
        members.append(wl.train_mlp(X, y, w, val, hidden=args.hidden, epochs=args.epochs, seed=args.seed + 1000 * k,
                                    say=say, mine_rounds=args.mine_rounds, l2=args.l2))
    del X, y, w, val
    # Averaging the members' logits is itself one MLP (hidden layers side by side), so the device
    # runs the ensemble as a single classifier with the same three operators.
    return (wl.merge_mlps(members) if len(members) > 1 else members[0]), rows


def evaluate(ctx, models, model_path=None):
    """Every evaluation, for every model in `models` (name -> MLP)."""
    res = dict(captures={}, owner_negatives={})
    for name, ce in ctx['cap_eval'].items():
        r = eval_captures(models, ce['caps'], ce['feats'], ce['offsets'])
        res['captures'][name] = capture_summary(r, sum(len(s) for s in ce['streams']) / wl.RATE)
    if ctx['neg_feats']:
        for name, m in models.items():
            res['owner_negatives'][name] = {str(c): sum(len(wl.detections(m.scores(f), c)) for f in ctx['neg_feats'])
                                            for c in CUTOFFS}
    syn = {}
    wanted = ctx.get('wanted', set())
    for name, r in eval_synthetic(models, ctx['syn_hold'], ctx['hold_feats']).items():
        overall, by_family, table = summarize_synthetic(r)
        syn[name] = dict(overall=overall, by_family=by_family, by_phrase=table)
        # Positives of the voice families the model trains on (unseen speakers or clips of them).
        peaks = np.array([p for (g, v, _), vals in r.items() if g == 'positive' and uses_voice(v, wanted) for p in vals])
        syn[name]['trained_positive'] = dict(
            clips=int(len(peaks)), **{f'rate@{c}': round(float(np.mean(peaks >= c)), 4) for c in CUTOFFS}) if len(peaks) else {}
    res['synthetic'] = syn
    bg = ctx['bg']
    res['background'] = eval_background(models, bg, tail_from=int(len(bg) * 0.8))
    if model_path is not None:
        diffs = []
        for ce in ctx['cap_eval'].values():
            for g, f in zip(ctx['fe'].scores(model_path, ce['streams'], pad=0), ce['feats']):
                diffs.append(float(np.max(np.abs(g - models['new'].scores(f)))))
        res['engine_check'] = dict(max_abs_diff_python_vs_echod_engine=max(diffs) if diffs else None, clips=len(diffs))
    return res


def main(argv=None):
    args = parse_args(argv)
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    started = time.time()
    lines = []

    def say(*a):
        wl.log(*a)
        lines.append(' '.join(map(str, a)))

    ctx = prepare(args, say)
    timings = ctx['timings']
    t0 = time.time()
    mlp, rows = fit(ctx, args, say)
    timings['training'] = round(time.time() - t0, 1)
    model_path = out / f'{args.model_id}.tflite'
    kind = 'owner + synthetic' if ctx['use_owner'] else 'synthetic (Piper + Gemini voices)'
    wl.export_tflite(mlp, model_path, f'Mira Arabic wake word, {kind}; trained {time.strftime("%Y-%m-%d")}')
    exported = wl.load_tflite_mlp(model_path)
    assert np.array_equal(exported.w0, mlp.w0) and np.array_equal(exported.b1, mlp.b1)

    t0 = time.time()
    models = {'new': exported}
    if args.baseline and Path(args.baseline).exists():
        models['baseline'] = wl.load_tflite_mlp(args.baseline)
    res = evaluate(ctx, models, model_path)
    if res['engine_check']['clips'] == 0:
        res['engine_check'] = engine_check_synthetic(ctx, model_path, exported)
    timings['evaluation'] = round(time.time() - t0, 1)

    report = build_report(args, ctx, res, rows, mlp, model_path, out)
    report['timings_s'] = dict(timings, total=round(time.time() - started, 1))

    if args.refit_all and ctx['use_owner'] and ctx['hold_caps']:
        t0 = time.time()
        say('refit on every capture (holdout included)')
        extra = ctx['owner_items'](ctx['hold_caps'])
        extra_feats = ctx['fe'].features([i.clip for i in extra], pad=0, desc='refit clips')
        refit, rows2 = fit(ctx, args, say, items=ctx['items'] + extra, feats=ctx['feats'] + extra_feats)
        evaluated_path = out / f'{args.model_id}.evaluated.tflite'
        model_path.replace(evaluated_path)
        wl.export_tflite(refit, model_path, 'Mira Arabic wake word, owner-adapted, refit on all captures; '
                         f'trained {time.strftime("%Y-%m-%d")}')
        rb = eval_background({'refit': wl.load_tflite_mlp(model_path)}, ctx['bg'], tail_from=int(len(ctx['bg']) * 0.8))
        report['refit'] = dict(file=model_path.name, sha256=wl.sha256(model_path), rows=rows2,
                               evaluated_model=evaluated_path.name, background=rb['refit'],
                               note='holdout numbers describe the evaluated model; the refit model has seen every '
                                    'capture, so only its background numbers are independent')
        report['model'].update(file=model_path.name, sha256=wl.sha256(model_path), bytes=model_path.stat().st_size)
        timings['refit'] = round(time.time() - t0, 1)
        report['timings_s'] = dict(timings, total=round(time.time() - started, 1))

    manifest = dict(wake_word=args.phrase, model=f'{args.model_id}.tflite', trained_languages=['ar'])
    wl.dump_json(out / f'{args.model_id}.json', manifest)
    wl.dump_json(out / 'report.json', report)
    (out / 'report.md').write_text(render_markdown(report))
    (out / 'train.log').write_text('\n'.join(lines) + '\n')
    say(f'wrote {model_path}, {out / f"{args.model_id}.json"}, {out / "report.json"}')
    print(render_markdown(report))
    return report


def engine_check_synthetic(ctx, model_path, model):
    """Without captures: echod's engine vs the Python scoring on twelve fixed synthetic clips."""
    streams = []
    rng = np.random.default_rng(12345)
    v = wl.Voices().get('ar_JO-kareem-medium')
    for ipa in ['mˈiːraː', 'jˈaː mˈiːraː', 'hˈaːj mˈiːraː', 'ʔamˈiːra'] * 3:
        x, s, e = wl.trim(wl.piper_audio(v, ipa=ipa, length_scale=float(rng.uniform(0.9, 1.2))))
        clip, _, _ = bed(x, (s, e), rng, NoisePool([], []), owner=False)
        streams.append(clip)
    feats = ctx['fe'].features(streams, pad=0, desc='engine check clips')
    got = ctx['fe'].scores(model_path, streams, pad=0)
    diffs = [float(np.max(np.abs(g - model.scores(f)))) for g, f in zip(got, feats)]
    return dict(max_abs_diff_python_vs_echod_engine=max(diffs), clips=len(diffs))


def build_report(args, ctx, res, rows, mlp, model_path, out):
    caps = ctx['caps'] + ctx['eval_caps']
    report = dict(
        created=time.strftime('%Y-%m-%dT%H:%M:%S'),
        command=' '.join(sys.argv),
        model=dict(id=args.model_id, file=model_path.name, sha256=wl.sha256(model_path),
                   bytes=model_path.stat().st_size, hidden_units=int(mlp.w0.shape[0]), ensemble=args.ensemble,
                   input=[1, wl.FRAMES, wl.EMB],
                   operators=['FULLY_CONNECTED (fused RELU)', 'FULLY_CONNECTED', 'LOGISTIC'], dtype='float32',
                   trained_on_owner=ctx['use_owner']),
        owner=dict(
            captures=[dict(file=c.name, split=c.split, seconds=round(len(c.audio) / wl.RATE, 2),
                           utterances=len(c.utterances), warnings=c.warnings, levels=c.info,
                           segments=[dict(start=s.start, end=s.end, kind=s.kind, note=s.note) for s in c.segments])
                      for c in caps],
            train_utterances=sum(len(c.utterances) for c in ctx['train_caps']),
            holdout_utterances=sum(len(c.utterances) for c in ctx['hold_caps']), expect=args.expect,
            negatives=dict(train=[f.name for f, _ in ctx['neg_train']], holdout=[f.name for f, _ in ctx['neg_hold']])),
        training=dict(rows=rows, epochs=len(mlp.history), history=mlp.history, positive_window_s=args.pos_window,
                      augment_per_utterance=args.aug, synthetic_augment=args.synth_aug, mass=MASS,
                      positive_share=args.pos_share, l2=args.l2, hard_negative_rounds=args.mine_rounds,
                      hidden_units=args.hidden, seed=args.seed, positive_voices=args.positive_voices,
                      synthetic_corpus=synth_corpus.summary(ctx['syn_meta'])),
        engine_check=res['engine_check'],
        holdout=res['captures'].get('holdout'),
        eval_captures=res['captures'].get('eval_captures'),
        owner_negatives_detections=res['owner_negatives'] or None,
        synthetic_holdout=res['synthetic'],
    )
    report['background'] = dict(
        source='davidscripka/openwakeword_features validation_set_features.npy (CC BY-NC-SA 4.0): DiPCo '
               'dinner-party speech 5.3 h, Santa Barbara conversational English 3.7 h, reverberated MUSDB '
               'music 2 h; openWakeWord front end, equal to echod\'s Go front end within 1e-4',
        estimate='every stride-1 16-embedding window of the continuous stream is scored (one score per 80 ms, '
                 'as on the device); echod\'s logic fires at score >= cutoff and then ignores 14 steps '
                 '(300 ms hold + 800 ms refractory); false accepts per hour = detections / hours, 95 % Poisson '
                 'interval. None of this audio is Arabic, none is the owner\'s home: treat it as a lower bound '
                 'for an Arabic household and read it with the Arabic confusable rates. The committed model '
                 'was trained on the first 80 % of this set, so compare models on tail_* (last 20 %).',
        models=res['background'])
    new_fa = {c: res['background']['new']['cutoffs'][str(c)]['fa_per_hour'] for c in CUTOFFS}
    hold = res['captures'].get('holdout')
    syn_new = res['synthetic']['new']
    if hold:
        rec = {c: hold['models']['new']['recall'][str(c)] for c in CUTOFFS}
        cut, why = recommend(rec, new_fa, args.fa_target, hold['models']['new']['weakest_peak'],
                             'the weakest held-out owner utterance')
    else:
        pos = syn_new.get('trained_positive', {})
        rec = {c: pos.get(f'rate@{c}') for c in CUTOFFS}
        base_bg = res['background'].get('baseline', {}).get('cutoffs', {}).get(str(args.baseline_cutoff))
        if base_bg is not None:
            # "No more false wakes than today": today's model at today's cutoff, on the same audio.
            budget = base_bg['fa_per_hour']
            cut, why = recommend(rec, new_fa, budget, None, '')
            why = (f'lowest cutoff whose background false accepts ({new_fa[cut]}/h) are at or below those of '
                   f'{Path(args.baseline).name} at its working cutoff {args.baseline_cutoff} ({budget}/h, same audio; '
                   f'that model trained on 80 % of it, so its figure is optimistic and this budget strict)')
        else:
            cut, why = recommend(rec, new_fa, args.fa_target, None, '')
        why += ('; no owner recordings yet, so there is no owner utterance to keep a margin under: tune it on '
                'the device from echod\'s near-miss log lines, or retrain with the owner\'s captures')
    playing = max(round(cut - wl.PLAYING_SLACK, 2), wl.DEVICE_MIN_CUTOFF)
    report['cutoff_recommendation'] = dict(
        value=cut, why=why,
        recall_basis='owner holdout' if hold else f'held-out synthetic positives of the trained voices ({args.positive_voices})',
        recall=rec[cut], background_fa_per_hour=new_fa[cut],
        while_playing=dict(cutoff=playing, note='echod lowers the cutoff by 0.10 (never below 0.50) while its '
                                               'echo canceller runs', background_fa_per_hour=new_fa.get(playing)),
        table=[dict(cutoff=c, recall=rec[c], background_fa_per_hour=new_fa[c],
                    confusable_rate=syn_new['overall'].get('confusable', {}).get(f'rate@{c}'),
                    baseline_background_tail_fa_per_hour=res['background'].get('baseline', {}).get('cutoffs', {})
                    .get(str(c), {}).get('tail_fa_per_hour'))
               for c in CUTOFFS])
    # The stable summary for the desktop app (wake_coach.summarize): numbers at the recommended cutoff.
    report['recommended_cutoff'] = cut
    if hold:
        peaks = np.array([u['peak'] for u in hold['per_utterance']])
        report['owner_holdout'] = dict(
            total=int(len(peaks)), hits=int(np.sum(peaks >= cut)),
            by_cutoff={str(c): dict(hits=int(np.sum(peaks >= c)), total=int(len(peaks)),
                                    recall=round(float(np.mean(peaks >= c)), 4) if len(peaks) else None)
                       for c in CUTOFFS})
    else:
        report['owner_holdout'] = None
    report['false_accepts_per_hour_estimate'] = new_fa[cut]
    report['path'] = str((out / 'report.json').resolve())
    return report


def render_markdown(r):
    bg = r['background']['models']
    syn = r['synthetic_holdout']
    hold = r.get('holdout') or {}
    ev = r.get('eval_captures') or {}
    lines = [f"# {r['model']['id']} — training report ({r['created']})", '',
             f"Model `{r['model']['file']}` ({r['model']['bytes']} bytes, sha256 `{r['model']['sha256'][:16]}…`), "
             f"{'trained with owner audio' if r['model']['trained_on_owner'] else 'synthetic voices only'}, "
             f"input 1x16x96, FC({r['model']['hidden_units']}, RELU) → FC → LOGISTIC, float32. "
             f"Python scoring vs echod engine: max |Δ| = {r['engine_check']['max_abs_diff_python_vs_echod_engine']:.1e}.", '']
    if hold:
        lines.append(f"Owner: {r['owner']['train_utterances']} utterances for training, "
                     f"{r['owner']['holdout_utterances']} held out by file.")
    head = ['cutoff']
    if hold:
        head += ['owner holdout recall (new / baseline)']
    if ev:
        head += ['eval captures recall (new / baseline)']
    head += ['synthetic positives (new / baseline)', 'confusables fired (new / baseline)',
             'background FA/h, 10.7 h (new)', 'FA/h last 2.1 h (new / baseline)']
    lines += ['', '| ' + ' | '.join(head) + ' |', '| ' + ' | '.join(['---'] * len(head)) + ' |']
    for c in CUTOFFS:
        k = str(c)
        row = [f'{c:.2f}']
        if hold:
            row.append(f"{hold['models']['new']['recall'][k]} / {hold['models'].get('baseline', {}).get('recall', {}).get(k, '–')}")
        if ev:
            row.append(f"{ev['models']['new']['recall'][k]} / {ev['models'].get('baseline', {}).get('recall', {}).get(k, '–')}")
        sp = lambda who, g: syn.get(who, {}).get('overall', {}).get(g, {}).get(f'rate@{c}', '–')
        row += [f"{sp('new', 'positive')} / {sp('baseline', 'positive')}",
                f"{sp('new', 'confusable')} / {sp('baseline', 'confusable')}",
                f"{bg['new']['cutoffs'][k]['fa_per_hour']}",
                f"{bg['new']['cutoffs'][k]['tail_fa_per_hour']} / {bg.get('baseline', {}).get('cutoffs', {}).get(k, {}).get('tail_fa_per_hour', '–')}"]
        lines.append('| ' + ' | '.join(row) + ' |')
    rc = r['cutoff_recommendation']
    lines += ['', f"**Recommended cutoff: {rc['value']}** — {rc['why']}. While music plays echod uses "
              f"{rc['while_playing']['cutoff']}.", '']
    fam = syn['new'].get('by_family', {})
    if fam:
        lines += ['## Synthetic holdout by voice family (rate at 0.5 / 0.6 / 0.7, new model)', '']
        for group, d in fam.items():
            for f_, v in d.items():
                lines.append(f"- {group} · {f_}: {v['rate@0.5']} / {v['rate@0.6']} / {v['rate@0.7']} "
                             f"({v['clips']} clips, median peak {v['median_peak']})")
        lines.append('')
    for title, block in (('Held-out owner utterances', hold), ('Evaluation captures', ev)):
        if not block:
            continue
        lines += [f'## {title} (peak score)', '', '| file | start | end | new | baseline |', '| --- | --- | --- | --- | --- |']
        for u in block['per_utterance']:
            lines.append(f"| {u['file']} | {u['start']:.2f} | {u['end']:.2f} | {u['peak']:.3f} | {u.get('baseline_peak', '–')} |")
        lines.append('')
    if r['owner']['captures']:
        lines += ['## Captures', '']
        for c in r['owner']['captures']:
            lines.append(f"- {c['file']} ({c['split']}, {c['seconds']} s): {c['utterances']} utterance(s)"
                         + (f" — WARNING: {'; '.join(c['warnings'])}" if c['warnings'] else ''))
        lines.append('')
    lines += ['Timings (s): ' + ', '.join(f'{k} {v}' for k, v in r.get('timings_s', {}).items()), '']
    return '\n'.join(lines)


if __name__ == '__main__':
    main()
