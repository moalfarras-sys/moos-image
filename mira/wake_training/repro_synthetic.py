"""Rebuild the committed synthetic-only model end to end and compare it with the committed one.

    python repro_synthetic.py [--work DIR] [--fresh]

Runs the untouched generate.py and train.py in a work directory under the cache (never in the
repository): Piper corpus -> TECHO5 Go front end (mira_features_test.go, MIRA_CLIPS mode) -> MLP ->
TFLite. Then scores the committed mira_ar_experimental.tflite and the rebuilt one on the same
synthetic holdout and background windows, with train.py's own metrics plus the device's detection
logic, and checks the Python scoring against echod's engine (TestMiraScore) on a few clips.
Writes <work>/repro-report.json.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

import wakelib as wl

COMMITTED = wl.HERE / 'mira_ar_experimental.tflite'


def run(cmd, cwd, env=None):
    wl.log('$', ' '.join(map(str, cmd)))
    subprocess.run(list(map(str, cmd)), cwd=cwd, env=env, check=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--work', type=Path, default=wl.cache_root() / 'repro')
    ap.add_argument('--fresh', action='store_true', help='regenerate the corpus and retrain')
    a = ap.parse_args()
    root = wl.cache_root()
    work = a.work
    if a.fresh and work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True, exist_ok=True)
    for name in ('generate.py', 'train.py'):
        shutil.copyfile(wl.HERE / name, work / name)
    links = {'ar.onnx': root / 'voices/ar_JO-kareem-medium.onnx',
             'ar.onnx.json': root / 'voices/ar_JO-kareem-medium.onnx.json',
             'negative-validation.npy': root / 'data/validation_set_features.npy'}
    for name, target in links.items():
        if not (work / name).exists():
            os.symlink(target, work / name)

    fe = wl.GoFrontEnd(root)
    if not (work / 'manifest.json').exists():
        run([sys.executable, 'generate.py'], work)
    clips = sorted((work / 'clips').glob('*.wav'))
    if any(not Path(f'{c}.features').exists() for c in clips):
        env = fe._env()
        env['MIRA_CLIPS'] = str(work / 'clips')
        run([fe.go, 'test', './internal/lib/oww/', '-run', '^TestMiraFeatures$', '-count=1', '-v'],
            fe.module, env)
    if not (work / 'mira_ar_experimental.tflite').exists():
        run([sys.executable, 'train.py'], work)
    rebuilt_path = work / 'mira_ar_experimental.tflite'

    manifest = json.loads((work / 'manifest.json').read_text())
    committed = wl.load_tflite_mlp(COMMITTED)
    rebuilt = wl.load_tflite_mlp(rebuilt_path)
    models = {'committed': committed, 'rebuilt': rebuilt}

    # train.py's holdout: every clip whose index is a multiple of 5, with train.py's window choice.
    sel_x, sel_y, clip_peak = [], [], {k: {0: [], 1: []} for k in models}
    for entry in manifest:
        idx = int(entry['file'].split('-')[1])
        if idx % 5:
            continue
        f = np.fromfile(work / 'clips' / (entry['file'] + '.features'), '<f4').reshape(-1, 96)
        win = wl.sliding_windows(f)
        if not len(win):
            continue
        if entry['label']:
            end = int(round((1 + entry['duration'] + .25 - .76) / .08))
            sel = win[np.clip(np.array([end - 2, end, end + 2]) - 16, 0, len(win) - 1)]
        else:
            sel = win[::3]
        sel_x.append(sel)
        sel_y += [entry['label']] * len(sel)
        for k, m in models.items():
            clip_peak[k][entry['label']].append(float(m.predict(win).max()))
    sel_x = np.concatenate(sel_x)
    sel_y = np.array(sel_y)

    bg = np.load(root / 'data/validation_set_features.npy', mmap_mode='r')
    split = int(len(bg) * .8)
    tail = np.asarray(bg[split:], np.float32)          # the 20 % train.py never trained on
    tail_hours = len(tail) * 0.08 / 3600
    stride16 = np.array([bg[j - 16:j].reshape(-1) for j in range(split + 16, len(bg), 16)])
    tail_windows = wl.sliding_windows(tail)

    report = dict(corpus=dict(clips=len(manifest), holdout_clips=len(clip_peak['rebuilt'][0]) + len(clip_peak['rebuilt'][1])),
                  committed_report=json.loads((wl.HERE / 'training-report.json').read_text()),
                  rebuilt_report=json.loads((work / 'training-report.json').read_text()),
                  background_tail_hours=round(tail_hours, 3), models={})
    for k, m in models.items():
        p = m.predict(sel_x)
        tail_scores = m.predict(tail_windows)
        r = dict(
            holdout_positive_recall_windows=round(float((p[sel_y == 1] >= .5).mean()), 4),
            holdout_negative_false_rate_windows=round(float((p[sel_y == 0] >= .5).mean()), 4),
            background_false_windows_stride16=int((m.predict(stride16) >= .5).sum()),
            background_peak_stride16=round(float(m.predict(stride16).max()), 4),
            clip_peak_positive_median=round(float(np.median(clip_peak[k][1])), 4),
            clip_peak_negative_median=round(float(np.median(clip_peak[k][0])), 4))
        for c in (.5, .6, .7):
            hits = wl.detections(tail_scores, c)
            r[f'cut_{c}'] = dict(
                positive_clips_detected=round(float(np.mean(np.array(clip_peak[k][1]) >= c)), 4),
                negative_clips_fired=round(float(np.mean(np.array(clip_peak[k][0]) >= c)), 4),
                background_detections=len(hits),
                background_fa_per_hour=round(len(hits) / tail_hours, 3))
        report['models'][k] = r
    pc = np.corrcoef(committed.predict(sel_x), rebuilt.predict(sel_x))[0, 1]
    report['score_correlation_holdout_windows'] = round(float(pc), 4)

    # Python scoring == echod's engine: score a few holdout clips through TestMiraScore.
    probe = [c for c in clips if int(c.name.split('-')[1]) % 5 == 0][:12]
    pcm = [wl.read_wav(c) for c in probe]
    go_scores = fe.scores(rebuilt_path, pcm)
    py_feats = fe.features(pcm, desc='probe clips')
    diffs = [float(np.max(np.abs(g - rebuilt.scores(f)))) for g, f in zip(go_scores, py_feats)]
    report['device_engine_vs_python_max_abs_diff'] = max(diffs)
    report['files'] = dict(committed_sha256=wl.sha256(COMMITTED), rebuilt_sha256=wl.sha256(rebuilt_path),
                           rebuilt=str(rebuilt_path), sizes=[COMMITTED.stat().st_size, rebuilt_path.stat().st_size])
    wl.dump_json(work / 'repro-report.json', report)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
