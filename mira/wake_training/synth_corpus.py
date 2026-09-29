"""Synthetic corpus for the Mira wake word: positives, hard negatives and ordinary speech.

    python synth_corpus.py            # build (or reuse) the cached corpus and print its summary

Dry utterances only (no noise, no room): train_owner.py adds rooms, noise and level per run. Two
parts, each cached under <cache>/synth/<part>-<hash of its spec>/ and rebuilt only when that spec
changes: the Whisper-checked positives (about 50 min to build) and the negatives (a few minutes).

Pronunciation is explicit. For Arabic text Piper runs a diacritizer first, which reads «ميرا» as
"mˈiːran" (tanween). Three of the five positive phrases of the first generate.py were synthesized
that way, and «يا ميرا» always was. Positives here are IPA, checked with the local Whisper model
when it is available (a clip is kept only if Whisper hears Mira in Arabic or English).

Voices (Piper, 16 kHz after resampling):
  ar_JO-kareem-medium        Arabic, 1 speaker                 positives, confusables, words, sentences
  en_US-libritts_r-medium    904 speakers (CC BY 4.0 data)     negatives (+ English "Meera" positives)
  en_US-l2arctic-medium      24 L2 speakers (CC BY-NC 4.0)     negatives (+ "Meera" positives)
The English-voice "Meera" positives are kept but train_owner.py does not train on them by default:
with them the model learned a broad "mi-rV" that fired on "mirror", "Nina", "Vera" and on English
conversation (230 false accepts per hour at 0.6 on the background set).
ar_JO-kareem-low is not used: Whisper heard its «ميرا» as "Lira" 7 times in 8.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

import numpy as np

import wakelib as wl

VERSION = 2          # parts are cached by the hash of their spec; see _part

# (label, ipa, weight). Bare «ميرا» carries most of the weight: it is the phrase that scored lowest.
POSITIVE = {
    'ar_JO-kareem-medium': dict(n=720, variants=[
        ('ميرا', 'mˈiːraː', 4), ('ميرا', 'miːrˈaː', 2),
        ('يا ميرا', 'jˈaː mˈiːraː', 2), ('يا ميرا', 'ja mˈiːraː', 1),
        ('هاي ميرا', 'hˈaːj mˈiːraː', 1), ('هاي ميرا', 'hˈaːi mˈiːraː', 1)]),
    'en_US-libritts_r-medium': dict(n=960, variants=[
        ('ميرا', 'mˈiːɹə', 3), ('ميرا', 'mˈiəɹə', 2), ('ميرا', 'mˈiːɹɑː', 1),
        ('يا ميرا', 'jˈɑː mˈiːɹə', 2), ('يا ميرا', 'jə mˈiːɹə', 1), ('هاي ميرا', 'hˈaɪ mˈiːɹə', 2)]),
    'en_US-l2arctic-medium': dict(n=240, variants=[
        ('ميرا', 'mˈiːɹə', 3), ('ميرا', 'mˈiəɹə', 2), ('هاي ميرا', 'hˈaɪ mˈiːɹə', 1)]),
}

# Arabic words that share sounds with «ميرا», by IPA so each is said the way it is meant.
CONFUSABLE_AR = [
    ('أميرة', 'ʔamˈiːra', 3), ('أميرة', 'ʔamˈiːrat', 1), ('يا أميرة', 'jaː ʔamˈiːra', 2),
    ('سميرة', 'samˈiːra', 3), ('يا سميرة', 'jaː samˈiːra', 1),
    ('مرة', 'mˈarra', 3), ('مرة', 'mˈarrat', 1),
    ('مريم', 'mˈarjam', 3), ('يا مريم', 'jaː mˈarjam', 2), ('هاي مريم', 'hˈaːj mˈarjam', 1),
    ('ميرال', 'miːrˈaːl', 3), ('أمير', 'ʔamˈiːr', 2), ('يا أمير', 'jaː ʔamˈiːr', 1),
    ('مين', 'mˈiːn', 3), ('مين ده', 'mˈiːn dˈa', 1),
    ('مرحبا', 'mˈarħaban', 2), ('مرحبا', 'marħˈaba', 2),
    ('كاميرا', 'kaːmˈiːraː', 3), ('الكاميرا', 'ʔalkaːmˈiːraː', 1), ('ميراث', 'miːrˈaːθ', 2),
    ('ميرنا', 'mˈiːrnaː', 2), ('مرايا', 'maraːjˈaː', 1), ('ميري', 'mˈiːriː', 1), ('ميرو', 'mˈiːruː', 1),
    ('ميار', 'majˈaːr', 1), ('نورا', 'nˈuːra', 1), ('سارة', 'sˈaːra', 1), ('يا سارة', 'jaː sˈaːra', 1),
    ('ريم', 'rˈiːm', 1), ('يا ريم', 'jaː rˈiːm', 1), ('ليرة', 'lˈiːra', 2), ('بيرة', 'bˈiːra', 1),
    ('سيرة', 'sˈiːra', 1), ('حيرة', 'ħˈiːra', 1), ('ميزان', 'miːzˈaːn', 1), ('ميدان', 'miːdˈaːn', 1),
    ('مية', 'mˈajja', 1), ('ماما', 'mˈaːmaː', 1), ('تمام', 'tamˈaːm', 1), ('أمريكا', 'ʔamˈriːkaː', 1),
    ('أليكسا', 'ʔalˈiːksaː', 2), ('يا أليكسا', 'jaː ʔalˈiːksaː', 1), ('هاي', 'hˈaːj', 1), ('يا', 'jˈaː', 1),
]
N_CONFUSABLE_AR = 1100

# English neighbours (text, Piper's own English phonemizer), many speakers.
CONFUSABLE_EN = ['camera', 'mirror', 'Maria', 'Amira', 'Samira', 'Myra', 'Mia', 'Nina', 'Lira', 'Kira',
                 'Sierra', 'America', 'hey Siri', 'Alexa', 'hi Maria', 'meerkat', 'hey Nina', 'hi Amira',
                 'Vera', 'Laura', 'Sara', 'hey Mia', 'mirage', 'miracle', 'hi there', 'hey', 'Emir',
                 'Mary', 'Marie', 'Tamara', 'Elmira', 'Mirabel', 'here we are', 'me too', 'media']

SENTENCES_AR = [
    'كيف حالك', 'شغل الضوء', 'أطفئ التلفاز', 'صباح الخير', 'أنا في البيت', 'أريد أن أذهب إلى المكتب',
    'شكرا', 'لماذا', 'نعم', 'لا', 'ازيك عامل ايه', 'فين المفتاح', 'تعالى هنا', 'الجو حلو النهارده',
    'عايز اشرب مية', 'افتح الباب', 'مساء الخير', 'تصبح على خير', 'الساعة كام', 'انا جعان', 'ماشي',
    'طيب', 'والله', 'إن شاء الله', 'الحمد لله', 'مع السلامة', 'أهلا وسهلا', 'شغل الموسيقى', 'علي الصوت',
    'وطي الصوت', 'بكرة الصبح', 'امبارح بالليل', 'الأكل جاهز', 'فين الريموت', 'اقفل النور', 'خلاص كفاية',
    'هو فيه ايه', 'مش عارف', 'حاضر', 'دقيقة واحدة', 'أنا جاي حالا', 'الأمير وصل إلى المدينة',
    'الأميرة في القصر', 'سمير راح الشغل', 'مرة واحدة بس', 'المرايا في الأوضة', 'كاميرا الموبايل حلوة',
    'مريم بتذاكر', 'ميراث العيلة', 'مين اللي بيتكلم', 'مرحبا بكم في البرنامج', 'نشرة الأخبار', 'الطقس اليوم مشمس',
]

SENTENCES_EN = [
    'hello how are you', 'turn on the light', 'what time is it', 'good morning', 'I am at home',
    'play some music', 'where are my keys', 'come here please', 'the weather is nice today',
    'I would like a glass of water', 'open the door', 'good night', 'thank you very much', 'see you later',
    'can you hear me', 'the camera is on the table', 'look in the mirror', 'Maria is coming tomorrow',
    'we visited America last year', 'the meeting starts at nine', 'turn the volume down', 'stop the timer',
    'what is on the news', 'I am hungry', 'let me think about it', 'that was a miracle',
]

MIRA_HEARD = re.compile(r'(مير|mira|meera|mirah|meara|mera|mirra|miera|myra|mirror)', re.I)


WORDS_AR = ['نعم', 'لا', 'شكرا', 'ماشي', 'طيب', 'حاضر', 'أيوه', 'كده', 'ليه', 'فين', 'إمتى', 'ازاي',
            'ممكن', 'خلاص', 'يلا', 'بس', 'كمان', 'برضه', 'أهلا', 'مرسي', 'تمام', 'آسف', 'لحظة', 'استنى',
            'هنا', 'هناك', 'النهارده', 'بكرة', 'امبارح', 'الصبح', 'بالليل', 'البيت', 'الشغل', 'المطبخ',
            'الأوضة', 'التلفزيون', 'الموبايل', 'الكمبيوتر', 'الباب', 'الشباك', 'النور', 'المية', 'القهوة',
            'الشاي', 'الأكل', 'العربية', 'الشارع', 'السوق', 'المدرسة', 'الجامعة', 'الدكتور', 'مريض',
            'مبسوط', 'زعلان', 'تعبان', 'جعان', 'عطشان', 'بردان', 'حران', 'جميل', 'كبير', 'صغير']
N_WORDS_AR = 300

SENTENCES_EN += [
    'could you turn off the kitchen light', 'I will be back in ten minutes', 'the kids are sleeping',
    'did you feed the cat this morning', 'we need milk and eggs', 'call me when you get there',
    'the train was late again', 'it is going to rain tomorrow', 'put the dishes in the sink',
    'I think the game starts at eight', 'my phone battery is almost empty', 'let us watch a movie tonight',
    'the soup is getting cold', 'can you pass me the salt', 'I forgot my umbrella at work',
    'she is reading a book in the garden', 'the music is too loud', 'what did the doctor say',
    'open the window a little', 'the package arrived this afternoon', 'remember to lock the door',
    'he plays the guitar every evening', 'where did you park the car', 'we should paint the living room',
    'the meeting was moved to friday', 'I am making some tea do you want some', 'the baby is crying',
    'turn on the heating please', 'the store closes at nine', 'I really like this song',
    'how was your day at school', 'the printer is out of paper', 'my mother is visiting on sunday',
    'the television is too loud', 'we are almost out of coffee', 'I need to charge my laptop',
    'the neighbours are having a party', 'dinner will be ready soon', 'the flowers need water',
    'please speak a little slower', 'I cannot find the remote', 'tell me a story',
    'this is the evening news', 'and now the weather for tomorrow', 'the score is two to one',
    'thank you for calling', 'please hold the line', 'the next station is central',
]
WORDS_EN = ['hello', 'yes', 'no', 'okay', 'thanks', 'please', 'sorry', 'water', 'table', 'music', 'news',
            'morning', 'evening', 'coffee', 'remember', 'tomorrow', 'kitchen', 'window', 'garden', 'dinner',
            'mother', 'father', 'brother', 'sister', 'teacher', 'doctor', 'number', 'minute', 'moment',
            'meeting', 'message', 'mister', 'memory', 'minimum', 'miracle', 'mirror', 'nearer', 'clearer',
            'era', 'area', 'aria', 'opera', 'camera', 'cinema', 'drama', 'lemon', 'melon', 'medal', 'metal',
            'middle', 'mean', 'mean it', 'meet her', 'meet you', 'me and her', 'my era', 'dream', 'green',
            'three', 'free', 'tree', 'agree', 'degree', 'really', 'nearly', 'early', 'merry', 'marry',
            'Harry', 'Jerry', 'Terry', 'Kerry', 'Barry', 'Larry', 'Gary', 'Mira Road', 'Miranda', 'Mirza',
            'Amir', 'Samir', 'Omar', 'Emma', 'Mona', 'Nora', 'Dora', 'Laura', 'Lara', 'Tara', 'Sara',
            'Clara', 'Kara', 'Cara', 'Zara', 'Farah', 'Hana', 'Dina', 'Lina', 'Rina', 'Tina', 'Gina',
            'hey', 'hi', 'hi there', 'hey you', 'come here', 'look here', 'over here', 'right here']
# «ميرا» itself is the positive: an English name that IS Mira (Meera, Mira) never goes in a negative list.
WORDS_EN = [w for w in WORDS_EN if w.lower() not in {'mira', 'meera', 'myra'}]
N_WORDS_EN = 600
N_L2_NEGATIVE = 600

NEGATIVE = {
    'confusable': [('ar_JO-kareem-medium', 'ipa', CONFUSABLE_AR, N_CONFUSABLE_AR),
                   ('en_US-libritts_r-medium', 'text', CONFUSABLE_EN, 800),
                   ('en_US-l2arctic-medium', 'text', CONFUSABLE_EN, 200)],
    'speech': [('ar_JO-kareem-medium', 'text', SENTENCES_AR, 400),
               ('ar_JO-kareem-medium', 'text', WORDS_AR, N_WORDS_AR),
               ('en_US-libritts_r-medium', 'text', SENTENCES_EN, 1200),
               ('en_US-libritts_r-medium', 'text', WORDS_EN, N_WORDS_EN),
               ('en_US-l2arctic-medium', 'text', SENTENCES_EN + WORDS_EN, N_L2_NEGATIVE)],
}

MIRA_HEARD = re.compile(r'(مير|mira|meera|mirah|meara|mera|mirra|miera|myra|mirror)', re.I)


def _spec_hash(spec):
    return __import__('hashlib').sha256(json.dumps(spec, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:10]


def _dir(part, spec):
    return wl.cache_root() / 'synth' / f'{part}-{_spec_hash(spec)}'


def _whisper():
    """The local Whisper model Mira's desktop app already has, if present."""
    path = Path(os.environ.get('MIRA_WHISPER_MODEL', Path.home() / '.local/share/mira/wake-model'))
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return None
    if not (path / 'model.bin').exists():
        return None
    return WhisperModel(str(path), device='cpu', compute_type='int8', cpu_threads=max(2, (os.cpu_count() or 4) - 2))


def _heard_mira(model, audio, tmp):
    x = np.concatenate([np.zeros(4000), audio / max(1e-9, np.abs(audio).max()) * 0.4, np.zeros(4000)])
    wl.write_wav(tmp, x)
    texts = []
    for lang in ('ar', 'en'):
        segs, _ = model.transcribe(str(tmp), language=lang, beam_size=3, vad_filter=False,
                                   condition_on_previous_text=False)
        text = ' '.join(s.text.strip() for s in segs)
        texts.append(text)
        if MIRA_HEARD.search(text):
            return True, texts
    return False, texts


def _pick(rng, variants):
    w = np.array([v[-1] for v in variants], float)
    return variants[int(rng.choice(len(variants), p=w / w.sum()))]


class _Sink:
    def __init__(self):
        self.clips, self.meta = [], []

    def add(self, audio, **m):
        x, s, e = wl.trim(audio)
        if e - s < 0.12:
            return False
        self.clips.append(wl.to_int16(x / max(np.abs(x).max(), 1e-9) * 0.5))
        m.update(speech_start=round(s, 4), speech_end=round(e, 4))
        self.meta.append(m)
        return True


def _prosody(rng):
    return dict(length_scale=float(rng.uniform(0.8, 1.3)), noise_scale=float(rng.uniform(0.45, 0.9)),
                noise_w=float(rng.uniform(0.5, 1.0)))


def _build_positives(say):
    rng = np.random.default_rng(20260929 + 1)
    voices, sink = wl.Voices(), _Sink()
    whisper = _whisper()
    say('whisper check:', 'on' if whisper else 'off (faster-whisper or model missing)')
    tmp = wl.cache_root() / 'synth' / 'probe.wav'
    tmp.parent.mkdir(parents=True, exist_ok=True)
    rejected, t0 = {}, time.time()
    for name, spec in POSITIVE.items():
        v = voices.get(name)
        nspk = v.config.num_speakers
        made = tried = 0
        while made < spec['n'] and tried < spec['n'] * 3:
            tried += 1
            label, ipa, _ = _pick(rng, spec['variants'])
            spk = int(rng.integers(0, nspk)) if nspk > 1 else None
            p = _prosody(rng)
            audio = wl.piper_audio(v, ipa=ipa, speaker=spk, **p)
            if whisper is not None:
                ok, texts = _heard_mira(whisper, wl.trim(audio)[0], tmp)
                if not ok:
                    rejected.setdefault(name, []).append(dict(ipa=ipa, speaker=spk, heard=texts))
                    continue
            holdout = (spk % 5 == 0) if spk is not None else (made % 5 == 0)
            if sink.add(audio, voice=name, speaker=spk, text=label, ipa=ipa, label=1, group='positive',
                        holdout=bool(holdout), **p):
                made += 1
        say(f'positives {name}: {made} kept of {tried} ({time.time() - t0:.0f}s)')
    tmp.unlink(missing_ok=True)
    return sink, dict(whisper_check=whisper is not None, rejected_per_voice={k: len(v) for k, v in rejected.items()},
                      rejected=rejected)


def _build_negatives(say):
    rng = np.random.default_rng(20260929 + 2)
    voices, sink = wl.Voices(), _Sink()
    t0 = time.time()
    for group, sources in NEGATIVE.items():
        for name, kind, items, n in sources:
            v = voices.get(name)
            nspk = v.config.num_speakers
            for k in range(n):
                item = _pick(rng, items) if kind == 'ipa' else items[k % len(items)]
                spk = int(rng.integers(0, nspk)) if nspk > 1 else None
                p = _prosody(rng)
                if kind == 'ipa':
                    label, ipa, _ = item
                    audio = wl.piper_audio(v, ipa=ipa, speaker=spk, **p)
                else:
                    label, ipa = item, None
                    audio = wl.piper_audio(v, text=item, speaker=spk, **p)
                holdout = (spk % 5 == 0) if spk is not None else (k % 5 == 0)
                sink.add(audio, voice=name, speaker=spk, text=label, ipa=ipa, label=0, group=group,
                         holdout=bool(holdout), **p)
            say(f'negatives {group} {name}: {n} ({time.time() - t0:.0f}s)')
    return sink, {}


def _migrate_v1_positives(d, say):
    """The first corpus (synth/v1) held these same positives; reuse them instead of an hour of
    Whisper checks."""
    old = wl.cache_root() / 'synth' / 'v1'
    if not (old / 'meta.json').exists():
        return False
    with np.load(old / 'audio.npz') as z:          # decompress once: z[name] re-reads on every access
        audio, off = z['audio'], z['offsets']
    meta = json.loads((old / 'meta.json').read_text())
    keep = [k for k, m in enumerate(meta) if m['group'] == 'positive']
    clips = [audio[off[k]:off[k + 1]].copy() for k in keep]
    metas = [{kk: vv for kk, vv in meta[k].items() if kk != 'id'} for k in keep]
    old_summary = json.loads((old / 'summary.json').read_text())
    rejected = json.loads((old / 'rejected.json').read_text()) if (old / 'rejected.json').exists() else {}
    _save(d, clips, metas, dict(whisper_check=old_summary.get('whisper_check'), migrated_from='v1',
                                rejected_per_voice=old_summary.get('rejected_per_voice'), rejected=rejected))
    say(f'reused {len(clips)} Whisper-checked positives from synth/v1')
    return True


def _save(d, clips, meta, info):
    d.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(d / 'audio.npz', audio=np.concatenate(clips), offsets=np.cumsum([0] + [len(c) for c in clips]))
    wl.dump_json(d / 'meta.json', meta)
    rejected = info.pop('rejected', None)
    if rejected is not None:
        wl.dump_json(d / 'rejected.json', rejected)
    wl.dump_json(d / 'summary.json', dict(info, clips=len(meta)))


def _load(d):
    with np.load(d / 'audio.npz') as z:            # decompress once: z[name] re-reads on every access
        audio, off = z['audio'], z['offsets']
    meta = json.loads((d / 'meta.json').read_text())
    return [audio[off[i]:off[i + 1]] for i in range(len(meta))], meta


def _part(name, spec, builder, force, say):
    d = _dir(name, spec)
    if force or not (d / 'meta.json').exists():
        if name == 'positives' and not force and _migrate_v1_positives(d, say):
            return _load(d)
        t0 = time.time()
        sink, info = builder(say)
        _save(d, sink.clips, sink.meta, dict(info, seconds=round(time.time() - t0)))
    return _load(d)


STANDALONE_MIRA = re.compile(r'^\W*((يا|هاي|hi|hey|ya)\W*)?(ميرا|ميره|ميرى|mira|meera|myra)\W*$', re.I)


def _gemini_calls():
    return sorted((wl.cache_root() / 'gemini').glob('*.npz'))


def _build_gemini(say):
    """Utterances from the cached Gemini TTS calls (gemini_tts.py): one voice and style per call,
    phrases separated by pauses. Each segment is one utterance; positives are kept only if Whisper
    hears Mira, negatives are dropped if Whisper hears nothing but «ميرا»."""
    from scipy.signal import resample_poly
    whisper = _whisper()
    tmp = wl.cache_root() / 'synth' / 'probe.wav'
    tmp.parent.mkdir(parents=True, exist_ok=True)
    sink, counts, rejected = _Sink(), [], []
    for f in _gemini_calls():
        z = np.load(f)
        job = json.loads(str(z['meta']))
        rate = int(job.get('rate', 24000))
        g = __import__('math').gcd(wl.RATE, rate)
        x = resample_poly(z['pcm'].astype(np.float64) / 32768, wl.RATE // g, rate // g)
        segs, _ = wl.segment_speech(wl.to_int16(x), merge_gap=0.2, max_dur=2.5)
        speech = [s for s in segs if s.kind == 'speech']
        counts.append(dict(call=f.stem, voice=job['voice'], kind=job['kind'], expected=job['expected'], found=len(speech)))
        label = 1 if job['kind'] == 'positive' else 0
        for seg in speech:
            clip = x[max(0, int((seg.start - 0.05) * wl.RATE)):int((seg.end + 0.05) * wl.RATE)]
            if whisper is not None:
                heard, texts = _heard_mira(whisper, clip, tmp)
                if label == 1 and not heard:
                    rejected.append(dict(voice=job['voice'], kind='positive', heard=texts))
                    continue
                if label == 0 and any(STANDALONE_MIRA.match(t or '') for t in texts):
                    rejected.append(dict(voice=job['voice'], kind='negative', heard=texts))
                    continue
            sink.add(clip, voice=f"gemini:{job['voice']}", speaker=None, text='ميرا' if label else job.get('list', ''),
                     ipa=None, label=label, group='positive' if label else ('speech' if job.get('list') == 'D' else 'confusable'),
                     holdout=bool(job['holdout']), style=job['style'], tts_model=job['model'])
    tmp.unlink(missing_ok=True)
    say(f"gemini: {len(sink.meta)} utterances from {len(counts)} calls, {len(rejected)} rejected by the Whisper check")
    return sink, dict(calls=counts, rejected=rejected, whisper_check=whisper is not None)


def build(force=False, say=wl.log, gemini=True):
    """The corpus: (clips: list[int16], meta: list[dict]); each part is built once and cached.
    gemini=False leaves the Gemini part out even when calls are cached."""
    pc, pm = _part('positives', POSITIVE, _build_positives, force, say)
    nc, nm = _part('negatives', NEGATIVE, _build_negatives, force, say)
    clips, meta = pc + nc, pm + nm
    calls = [f.name for f in _gemini_calls()] if gemini else []
    if calls:
        gc, gm = _part('gemini', dict(calls=calls, version=1), _build_gemini, force, say)
        clips, meta = clips + gc, meta + gm
    return clips, [dict(m, id=k) for k, m in enumerate(meta)]


def load():
    return build()


def summary(meta):
    out = {}
    for m in meta:
        key = f"{m['group']}:{m['voice']}:{'holdout' if m['holdout'] else 'train'}"
        out[key] = out.get(key, 0) + 1
    return dict(sorted(out.items()))


if __name__ == '__main__':
    clips, meta = build(force='--force' in sys.argv)
    print(json.dumps(summary(meta), indent=2))
    parts = [('positives', POSITIVE), ('negatives', NEGATIVE)]
    if _gemini_calls():
        parts.append(('gemini', dict(calls=[f.name for f in _gemini_calls()], version=1)))
    for part, spec in parts:
        info = json.loads((_dir(part, spec) / 'summary.json').read_text())
        print(part, json.dumps({k: v for k, v in info.items() if k not in ('calls', 'rejected')}, ensure_ascii=False))
