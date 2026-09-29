"""Optional: natural voices for the synthetic corpus from Gemini TTS (prebuilt voices, styles).

    python gemini_tts.py [--max-calls 45] [--dry-run]

Reads the API key from ~/.config/mo-dot/gemini.json (MIRA_GEMINI_CONFIG) inside this process and
never prints or stores it. Each call asks ONE prebuilt voice to read a short list of phrases with
pauses in one style; the audio (24 kHz PCM) and what was asked are cached under
<cache>/gemini/<job>.npz, so a call is never repeated. synth_corpus.py segments the cached audio
into utterances and checks each with Whisper; nothing here trains anything.

Calls are spread over the TTS models the key can use and paced below the free tier's 3 requests per
minute per model. A 429 (quota) response is recorded in <cache>/gemini/errors.jsonl (key removed)
and that model is skipped for the rest of the run. Six voices are only ever used for evaluation.
"""
import argparse
import base64
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np

import wakelib as wl

MODELS = ['gemini-2.5-flash-preview-tts', 'gemini-3.1-flash-tts-preview', 'gemini-3.8-flash-tts']
VOICES = ['Zephyr', 'Puck', 'Charon', 'Kore', 'Fenrir', 'Leda', 'Orus', 'Aoede', 'Callirrhoe', 'Autonoe',
          'Enceladus', 'Iapetus', 'Umbriel', 'Algieba', 'Despina', 'Erinome', 'Algenib', 'Rasalgethi',
          'Laomedeia', 'Achernar', 'Alnilam', 'Schedar', 'Gacrux', 'Pulcherrima', 'Achird',
          'Zubenelgenubi', 'Vindemiatrix', 'Sadachbia', 'Sadaltager', 'Sulafat']
HOLDOUT_VOICES = {'Charon', 'Leda', 'Puck', 'Sulafat', 'Achird', 'Gacrux'}
STYLES = ['Read these Arabic words calmly', 'Read these Arabic words quickly',
          'Read these Arabic words slowly and clearly', 'Read these Arabic words softly, almost whispering',
          'Read these Arabic words cheerfully', 'Read these Arabic words in a tired, flat voice',
          'Call out these Arabic words as if calling someone in another room',
          'Read these Arabic words with an Egyptian accent', 'Read these Arabic words with a Levantine accent',
          'Read these Arabic words with a Gulf accent']
POSITIVE = ['ميرا.', 'ميرا؟', 'ميرا!', 'ميرا.', 'يا ميرا.', 'هاي ميرا.', 'ميرا…', 'يا ميرا!']
NEGATIVE = {
    'A': 'أميرة. سميرة. مرة. مريم. ميرال. أمير. مين. مرحبا. كاميرا. ميراث.',
    'B': 'ميرنا. مرايا. ميري. ميرو. ميار. نورا. سارة. ريم. ليرة. بيرة.',
    'C': 'يا أميرة. يا سميرة. يا مريم. هاي مريم. يا أمير. يا سارة. يا ريم. هاي سارة. أليكسا. يا أليكسا.',
    'D': 'فين المفتاح. شغل التلفزيون. الجو حلو النهارده. مين اللي بيتكلم. أنا جاي حالا. الكاميرا على الترابيزة. شفت الأميرة. مرة تانية.',
}


def jobs():
    """The fixed plan: positives from every voice, negatives from a few, most useful first."""
    rng = np.random.default_rng(29)
    train = [v for v in VOICES if v not in HOLDOUT_VOICES]
    hold = sorted(HOLDOUT_VOICES)
    out = []

    def pos(voice, k):
        phrases = list(rng.permutation(POSITIVE))
        out.append(dict(kind='positive', voice=voice, style=STYLES[k % len(STYLES)], text=' '.join(phrases),
                        expected=len(phrases), holdout=voice in HOLDOUT_VOICES))

    def neg(voice, key, k):
        out.append(dict(kind='negative', voice=voice, style=STYLES[k % len(STYLES)], text=NEGATIVE[key],
                        expected=NEGATIVE[key].count('.'), list=key, holdout=voice in HOLDOUT_VOICES))
    for k, v in enumerate(train[:12]):
        pos(v, k)
    for k, v in enumerate(hold[:2]):
        pos(v, k + 3)
    for k, key in enumerate('ABCD'):
        neg(train[12 + k], key, k)
    for k, v in enumerate(train[12:]):
        pos(v, k + 5)
    for k, v in enumerate(hold[2:]):
        pos(v, k + 7)
    for k, key in enumerate('ABCD'):
        neg(train[k], key, k + 2)
        neg(hold[k], key, k + 4)
    for j in out:
        j['id'] = hashlib.sha256(json.dumps([j['voice'], j['style'], j['text']], ensure_ascii=False).encode()).hexdigest()[:16]
    return out


def call(key, model, job):
    url = f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'
    prompt = f"{job['style']}, with a pause of about one second between them:\n{job['text']}"
    body = {'contents': [{'parts': [{'text': prompt}]}],
            'generationConfig': {'responseModalities': ['AUDIO'],
                                 'speechConfig': {'voiceConfig': {'prebuiltVoiceConfig': {'voiceName': job['voice']}}}}}
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json', 'x-goog-api-key': key})
    try:
        r = json.load(urllib.request.urlopen(req, timeout=180))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors='replace').replace(key, '<key>')[:3000], None, None
    except OSError as e:
        return 0, type(e).__name__, None, None
    try:
        part = r['candidates'][0]['content']['parts'][0]['inlineData']
    except (KeyError, IndexError):
        return 200, 'no audio in the response', None, None
    raw, mime = base64.b64decode(part['data']), part.get('mimeType', '')
    if raw[:4] == b'RIFF':                       # some models answer with a WAV container
        import io
        import wave
        with wave.open(io.BytesIO(raw)) as w:
            rate, ch = w.getframerate(), w.getnchannels()
            pcm = np.frombuffer(w.readframes(w.getnframes()), '<i2')
            if ch > 1:
                pcm = pcm.reshape(-1, ch).mean(axis=1).astype('<i2')
    else:                                        # audio/L16;codec=pcm;rate=24000
        rate = int(mime.split('rate=')[-1].split(';')[0]) if 'rate=' in mime else 24000
        pcm = np.frombuffer(raw, '<i2')
    return 200, '', pcm, dict(rate=rate, mime=mime, usage=r.get('usageMetadata'))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--max-calls', type=int, default=45)
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--holdout-first', action='store_true', help='evaluation voices before training voices')
    ap.add_argument('--skip-models', default='', help='comma-separated models not to call (e.g. out of quota today)')
    a = ap.parse_args()
    out = wl.cache_root() / 'gemini'
    out.mkdir(parents=True, exist_ok=True)
    plan = jobs()
    todo = [j for j in plan if not (out / f"{j['id']}.npz").exists()]
    if a.holdout_first:
        todo.sort(key=lambda j: (j['kind'] != 'positive', not j['holdout']))
    wl.log(f'{len(plan)} jobs planned, {len(todo)} not cached yet')
    if a.dry_run or not todo:
        return
    cfg = Path(os.environ.get('MIRA_GEMINI_CONFIG', Path.home() / '.config/mo-dot/gemini.json'))
    key = json.loads(cfg.read_text())['api_key']
    alive = [m for m in MODELS if m not in a.skip_models.split(',')]
    last = {m: 0.0 for m in MODELS}
    calls = 0
    retries = {}
    for job in todo:
        while alive and calls < a.max_calls:
            model = min(alive, key=lambda m: last[m])
            time.sleep(max(0.0, last[model] + 21 - time.time()))
            last[model] = time.time()
            calls += 1
            code, err, pcm, info = call(key, model, job)
            if pcm is not None:
                np.savez(out / f"{job['id']}.npz", pcm=pcm, meta=json.dumps(dict(job, model=model, **info), ensure_ascii=False))
                wl.log(f"{model} {job['voice']:14s} {job['kind']:8s} {len(pcm) / info['rate']:.1f}s")
                break
            with open(out / 'errors.jsonl', 'a') as f:
                f.write(json.dumps(dict(at=time.strftime('%Y-%m-%dT%H:%M:%S'), model=model, code=code, error=err)) + '\n')
            if (code in (0, 200) or code >= 500) and retries.get(job['id'], 0) < 2:
                retries[job['id']] = retries.get(job['id'], 0) + 1
                wl.log(f'{model}: HTTP {code}, retrying')
                continue
            wl.log(f'{model}: HTTP {code}, model skipped for this run (see errors.jsonl)')
            alive.remove(model)
        if not alive or calls >= a.max_calls:
            break
    done = sum((out / f"{j['id']}.npz").exists() for j in plan)
    wl.log(f'{calls} calls made; {done}/{len(plan)} jobs cached; models still usable: {alive}')


if __name__ == '__main__':
    main()
