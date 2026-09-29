"""Self-test of train_owner.py on a synthetic STAND-IN owner. This is not the owner's voice.

    python selftest_owner.py [--files 12] [--work DIR] [--skip-ablation]

No owner audio exists yet, so this makes captures shaped like the real ones: Piper's Arabic voice
(ar_JO-kareem-medium, from IPA) turned into a different, larger speaker (pitch and formants x0.85
by resampling, 7 % slower, with per-utterance variation); six «ميرا» / «يا ميرا» / «هاي ميرا» per
15 s window with 1-2 s pauses; near and far from the Echo (synthetic rooms, RT60 0.45 / 0.7 s);
television babble, a fan or mains hum; the Echo's band limits and leveller (-23 dBFS); and in half
of the windows the tail of the Echo's own wake sound (TECHO5's wake_word_triggered.pcm, CC BY 4.0)
at the start. Four more windows of the same "speaker" saying confusable words and sentences stand
in for --negatives.

Then it runs train_owner.py on them twice, once as intended and once with --synthetic-only (no
owner audio: what the same pipeline gives without the owner's recordings), scores the segmenter
against the known utterance times, and writes <work>/selftest-report.json. Everything stays in the
cache directory.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from scipy.signal import butter, resample_poly, sosfilt

import wakelib as wl

WAKE_SOUND = Path('/var/home/moos/moos-image/test-results/echo-dot/techo5/echod/internal/hardware/speaker/sounds/wake_word_triggered.pcm')
# Mostly bare «ميرا», some with the stress on the last syllable, some «يا» / «هاي ميرا».
PHRASES = [('ميرا', 'mˈiːraː', 4.5), ('ميرا', 'miːrˈaː', 2), ('يا ميرا', 'jˈaː mˈiːraː', 1.5),
           ('هاي ميرا', 'hˈaːj mˈiːraː', 2)]
NEGATIVE = [('أميرة', 'ʔamˈiːra'), ('سميرة', 'samˈiːra'), ('مرة', 'mˈarra'), ('مريم', 'mˈarjam'),
            ('ميرال', 'miːrˈaːl'), ('أمير', 'ʔamˈiːr'), ('مين', 'mˈiːn'), ('مرحبا', 'mˈarħaban'),
            ('كاميرا', 'kaːmˈiːraː'), ('يا سارة', 'jaː sˈaːra')]
SENTENCES = ['فين المفتاح', 'شغل التلفزيون', 'الجو حلو النهارده', 'مين اللي بيتكلم', 'أنا جاي حالا']
# A larger speaker: every frequency (pitch and formants) x0.85 by resampling, the duration put back
# with WSOLA, then 7 % slower. Resampling adds no vocoder artefacts: Whisper still hears "Mira" in
# tape-shifted Kareem (5/6 at x0.88), while a source-filter shift to F0 x0.72 / formants x0.88 made
# it "Mew", "Leo", "Milla" (3/18) and was dropped. A probe of the committed model on this speaker:
# near the Echo it scores >= 0.86 on bare «ميرا», far away (RT60 0.7 s) bare «ميرا» dips to 0.31 and
# final-stress «ميرا» to 0.07, while «يا ميرا» stays >= 0.94 - the owner's pattern on the device.
SPEAKER = dict(vocal_tract=0.85, tempo=0.93)


def say_as_owner(voice, rng, ipa=None, text=None):
    """One utterance of the stand-in speaker, dry, 16 kHz float."""
    a = wl.piper_audio(voice, ipa=ipa, text=text, length_scale=float(rng.uniform(0.9, 1.2)) / SPEAKER['tempo'],
                       noise_scale=float(rng.uniform(0.5, 0.8)), noise_w=float(rng.uniform(0.6, 0.9)))
    x, s, e = wl.trim(a, lead=0.02, tail=0.03)
    x = wl.tape_shift(x, SPEAKER['vocal_tract'] * rng.uniform(0.98, 1.02))
    return x, s, e


def echo_chain(x, rng):
    """The Dot's capture: band limits, then the leveller's gain toward -23 dBFS speech."""
    x = sosfilt(butter(2, [90, 7200], btype='band', fs=wl.RATE, output='sos'), x)
    return x


def room_tone(rng, n, kind):
    base = wl.colored_noise(rng, n, 'pink') * 10 ** (-58 / 20) + wl.colored_noise(rng, n, 'fan') * 10 ** (-62 / 20)
    return base


def make_capture(voice, rng, rooms, babble, wake_sound, n_utts=6, negative=False):
    """One listening window: returns (int16 audio, true utterance list [(start, end, text)])."""
    length = 15.0
    n = int(length * wl.RATE)
    room = rooms[int(rng.integers(len(rooms)))]
    dry = np.zeros(n)
    truth = []
    t = float(rng.uniform(0.5, 1.4))
    k = 0
    while k < n_utts:
        if negative:
            if rng.random() < 0.7:
                text, ipa = NEGATIVE[int(rng.integers(len(NEGATIVE)))]
                x, s, e = say_as_owner(voice, rng, ipa=ipa)
            else:
                text = SENTENCES[int(rng.integers(len(SENTENCES)))]
                x, s, e = say_as_owner(voice, rng, text=text)
        else:
            w = np.array([p[2] for p in PHRASES])
            text, ipa, _ = PHRASES[int(rng.choice(len(PHRASES), p=w / w.sum()))]
            x, s, e = say_as_owner(voice, rng, ipa=ipa)
        a = int(t * wl.RATE)
        if a + len(x) > n - int(0.4 * wl.RATE):
            break
        x = x * 10 ** (rng.uniform(-4, 4) / 20) / (wl.active_rms(x) + 1e-12)
        dry[a:a + len(x)] += x
        truth.append((round(t + s, 3), round(t + e, 3), text))
        t += len(x) / wl.RATE + float(rng.uniform(0.9, 1.9))
        k += 1
    wet = wl.reverb(dry, room)
    speech_rms = wl.active_rms(wet[wet != 0]) if np.any(wet) else 1.0
    noise = room_tone(rng, n, 'tone') * speech_rms / 10 ** (-23 / 20)   # the room at its level before the leveller
    kind = ['quiet', 'tv', 'hum'][int(rng.integers(3))]
    if kind == 'tv':
        noise += wl.reverb(wl.fit_length(babble, n, rng), room) * speech_rms / 10 ** (rng.uniform(16, 24) / 20) / (np.sqrt(np.mean(babble ** 2)) + 1e-12)
    elif kind == 'hum':
        noise += wl.colored_noise(rng, n, rng.choice(['hum', 'fan'])) * speech_rms / 10 ** (rng.uniform(18, 24) / 20)
    y = wet + noise
    chime = False
    if rng.random() < 0.5:
        cut = int(rng.uniform(0.25, 0.45) * wl.RATE)            # the loud part was never streamed
        tail = wake_sound[cut:] * speech_rms * 10 ** (rng.uniform(-6, 0) / 20) / (np.abs(wake_sound).max() + 1e-12)
        y[:len(tail)] += wl.reverb(tail, room)[:n]
        chime = True
    y = echo_chain(y, rng)
    y *= 10 ** (-23 / 20) / (wl.active_rms(y) + 1e-12)
    y *= min(1.0, 0.89 / (np.abs(y).max() + 1e-12))
    return wl.to_int16(y), truth, dict(noise=kind, chime=chime)


def score_segmentation(truth, found):
    """Match found utterances to true ones by overlap."""
    tp, starts, ends, used = 0, [], [], set()
    for a, b, _ in truth:
        best = None
        for k, (c, d) in enumerate(found):
            if k in used:
                continue
            ov = min(b, d) - max(a, c)
            if ov > 0 and (best is None or ov > best[0]):
                best = (ov, k)
        if best:
            used.add(best[1])
            tp += 1
            starts.append(found[best[1]][0] - a)
            ends.append(found[best[1]][1] - b)
    return dict(true=len(truth), found=len(found), matched=tp, missed=len(truth) - tp,
                extra=len(found) - len(used), start_err=starts, end_err=ends)


def truth_recall(report, truth):
    """Recall over the TRUE held-out utterances (the stand-in's ground truth), and whether the
    segments that were not true utterances (television fragments) would fire."""
    rows = report['holdout']['per_utterance']
    files = {r['file'] for r in rows}
    out = {}
    for who, key in (('new', 'peak'), ('baseline', 'baseline_peak')):
        peaks, extras = [], []
        for f in sorted(files):
            found = [r for r in rows if r['file'] == f]
            used = set()
            for a, b, _ in truth[f]['utterances']:
                hit = [k for k, r in enumerate(found) if min(b, r['end']) - max(a, r['start']) > 0]
                used.update(hit)
                peaks.append(max((found[k].get(key, 0.0) for k in hit), default=0.0))
            extras += [r.get(key, 0.0) for k, r in enumerate(found) if k not in used]
        peaks, extras = np.array(peaks), np.array(extras)
        out[who] = dict(true_utterances=len(peaks),
                        recall={c: round(float(np.mean(peaks >= float(c))), 4) for c in ('0.5', '0.6', '0.7', '0.8', '0.9')},
                        weakest=round(float(peaks.min()), 4) if len(peaks) else None,
                        extras_fired={c: f'{int(np.sum(extras >= float(c)))}/{len(extras)}' for c in ('0.5', '0.6', '0.7', '0.8')})
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--files', type=int, default=12)
    ap.add_argument('--work', type=Path, default=wl.cache_root() / 'selftest')
    ap.add_argument('--skip-ablation', action='store_true')
    ap.add_argument('--seed', type=int, default=4242)
    ap.add_argument('--summary-only', action='store_true', help='recompute the summary from finished runs')
    a = ap.parse_args()
    work = a.work
    owner_dir, neg_dir = work / 'standin-owner', work / 'standin-negatives'
    rng = np.random.default_rng(a.seed)
    truth_path = work / 'truth.json'
    if not truth_path.exists():
        owner_dir.mkdir(parents=True, exist_ok=True)
        neg_dir.mkdir(parents=True, exist_ok=True)
        voice = wl.Voices().get('ar_JO-kareem-medium')
        rooms = [wl.synth_rir(np.random.default_rng(1), 0.45), wl.synth_rir(np.random.default_rng(7), 0.7)]
        babble_voice = wl.Voices().get('en_US-libritts_r-medium')
        babble = np.concatenate([wl.piper_audio(babble_voice, text=t, speaker=int(s)) for t, s in
                                 [('and then we went down to the market to buy some bread', 11),
                                  ('the news tonight will cover the weather and the football', 202),
                                  ('she said that the meeting was moved to thursday afternoon', 404)]])
        babble = np.concatenate([babble, wl.piper_audio(voice, text='نشرة الأخبار اليوم عن الطقس والرياضة والاقتصاد')])
        ws = np.frombuffer(WAKE_SOUND.read_bytes(), '<i2').astype(np.float64) / 32768
        wake_sound = resample_poly(ws, 1, 3)                     # 48 kHz -> 16 kHz
        truth = {}
        for k in range(a.files):
            y, tr, info = make_capture(voice, rng, rooms, babble, wake_sound)
            name = f'standin-{k:02d}.wav'
            wl.write_wav(owner_dir / name, y)
            truth[name] = dict(utterances=tr, **info)
        for k in range(4):
            y, tr, info = make_capture(voice, rng, rooms, babble, wake_sound, n_utts=5, negative=True)
            name = f'standin-neg-{k:02d}.wav'
            wl.write_wav(neg_dir / name, y)
            truth[name] = dict(utterances=tr, **info)
        wl.dump_json(truth_path, truth)
    truth = json.loads(truth_path.read_text())

    seg = {}
    for f in sorted(owner_dir.glob('*.wav')):
        segs, _ = wl.segment_speech(wl.read_wav(f))
        found = [(s.start, s.end) for s in segs if s.kind == 'speech']
        seg[f.name] = score_segmentation(truth[f.name]['utterances'], found)
        seg[f.name]['set_aside'] = [f'{s.kind} {s.start:.2f}-{s.end:.2f}' for s in segs if s.kind != 'speech']
    tot = {k: sum(v[k] for v in seg.values()) for k in ('true', 'found', 'matched', 'missed', 'extra')}
    se = np.abs(np.concatenate([v['start_err'] for v in seg.values()]))
    ee = np.abs(np.concatenate([v['end_err'] for v in seg.values()]))
    tot.update(median_abs_start_error_s=round(float(np.median(se)), 3), median_abs_end_error_s=round(float(np.median(ee)), 3),
               p90_abs_end_error_s=round(float(np.percentile(ee, 90)), 3))
    wl.log('segmentation vs truth:', json.dumps(tot))

    runs = {}
    for name, extra in [('owner', []), ('synthetic_only', ['--synthetic-only'])]:
        if name == 'synthetic_only' and a.skip_ablation:
            continue
        out = work / f'out-{name}'
        if not a.summary_only:
            cmd = [sys.executable, str(wl.HERE / 'train_owner.py'), str(owner_dir), '--out', str(out),
                   '--negatives', str(neg_dir), '--expect', '6', *extra]
            wl.log('$', ' '.join(cmd))
            subprocess.run(cmd, check=True)
        if (out / 'report.json').exists():
            report = json.loads((out / 'report.json').read_text())
            runs[name] = dict(seconds=report['timings_s']['total'], report=report)

    summary = dict(note='STAND-IN owner synthesized from Piper with a speaker transformation; NOT the owner',
                   speaker=SPEAKER, captures=len([n for n in truth if not n.startswith('standin-neg')]),
                   segmentation=tot, segmentation_per_file={k: {kk: vv for kk, vv in v.items() if kk not in ('start_err', 'end_err')}
                                                            for k, v in seg.items()}, runs={})
    for name, r in runs.items():
        rep = r['report']
        hm = rep['holdout']['models']
        bg = rep['background']['models']
        row = dict(seconds=r['seconds'], recommended_cutoff=rep['recommended_cutoff'],
                   recommendation=rep['cutoff_recommendation']['why'], model_sha256=rep['model']['sha256'])
        truth_rows = truth_recall(rep, truth)
        for who in hm:
            row[who] = dict(
                true_utterance_recall=truth_rows[who]['recall'],
                background_fragments_fired=truth_rows[who]['extras_fired'],
                holdout_recall={c: hm[who]['recall'][c] for c in ('0.5', '0.6', '0.7')},
                weakest_peak=hm[who]['weakest_peak'], median_peak=hm[who]['median_peak'],
                false_detections_in_holdout_captures={c: hm[who]['false_detections_outside_utterances'][c] for c in ('0.5', '0.6', '0.7')},
                owner_negative_detections=(rep.get('owner_negatives_detections') or {}).get(who),
                background_fa_per_hour={c: bg[who]['cutoffs'][c]['fa_per_hour'] for c in ('0.5', '0.6', '0.7')},
                background_tail_fa_per_hour={c: bg[who]['cutoffs'][c]['tail_fa_per_hour'] for c in ('0.5', '0.6', '0.7')},
                synthetic=rep['synthetic_holdout'][who]['overall'])
        summary['runs'][name] = row
    wl.dump_json(work / 'selftest-report.json', summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
