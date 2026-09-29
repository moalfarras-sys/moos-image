"""Turn a short Arabic sentence into a spoken WAV for the Echo speaker.

Mira's own voice replies come from the Live model; this is for *announcements* the app plays on
its own — a reminder firing, a routine's spoken line — where there is no live session. Gemini
TTS reads the text with the prebuilt voice `Aoede`; the audio is written as a private 16-bit PCM
WAV under ~/.cache/mira/announce/<id>.wav (0600) and served later, by the app, to the Echo only.

    result = synthesize('انتهى مؤقّت الفرن')
    if result['status'] == 'ok':
        play(result['path_16k'])            # 16 kHz mono, the Echo's rate
    else:
        chime_and_notify(...)               # caller's fallback

When TTS is unavailable (no key, quota, network) `synthesize` returns {'status': 'unsupported'}
so the caller plays a chime and shows a desktop notification instead of failing silently.
"""
from __future__ import annotations

import base64
import io
import json
import os
import secrets
import time
import urllib.error
import urllib.request
import wave
from pathlib import Path
from typing import Optional

CACHE_DIR = Path(os.environ.get('MIRA_ANNOUNCE_DIR',
                                Path.home() / '.cache' / 'mira' / 'announce'))
GEMINI_CONFIG = Path(os.environ.get('MIRA_GEMINI_CONFIG', Path.home() / '.config/mo-dot/gemini.json'))
# Newest first; the key's free tier is ~10 requests/day PER MODEL (measured 2026-09-29), so
# trying several models multiplies the daily budget. A model out of quota (429) is skipped.
MODELS = ('gemini-2.5-flash-preview-tts', 'gemini-3.1-flash-tts-preview',
          'gemini-3.8-flash-tts', 'gemini-3.8-flash-lite-tts', 'gemini-2.5-pro-preview-tts')
DEFAULT_VOICE = 'Aoede'
ECHO_RATE = 16000
MAX_TEXT = 600
MAX_AGE_S = 3600
_API = 'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'


# ─── private WAV writing (same contract as live_voice.write_private_wav) ─


def _write_private_wav(path: Path, pcm: bytes, rate: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path.parent, 0o700)
    except OSError:
        pass
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'wb') as raw, wave.open(raw, 'wb') as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes(pcm)
    os.chmod(path, 0o600)


# ─── resampling to the Echo's 16 kHz ──────────────────────────────────


def to_16k_mono(pcm: bytes, in_rate: int) -> bytes:
    """Downsample S16LE mono PCM to 16 kHz. Uses live_voice's polyphase resampler when the
    app is loaded, else a NumPy linear resample, else returns the input unchanged."""
    if in_rate == ECHO_RATE or not pcm:
        return pcm
    try:                                   # the proven, click-free resampler when it is importable
        import live_voice
        return live_voice.Resampler(in_rate, ECHO_RATE).process(pcm)
    except Exception:
        pass
    try:
        import numpy as np
        samples = np.frombuffer(pcm, dtype='<i2').astype(np.float64)
        n_out = max(1, int(round(len(samples) * ECHO_RATE / in_rate)))
        x_old = np.arange(len(samples))
        x_new = np.linspace(0, len(samples) - 1, n_out)
        out = np.interp(x_new, x_old, samples)
        return np.clip(np.rint(out), -32768, 32767).astype('<i2').tobytes()
    except Exception:
        return pcm


SPEAKER_RATE = 48000   # the Echo's music stream takes 48 kHz; announcements go at 16 kHz (path_16k)


def speaker_wav(path) -> bytes:
    """The announcement as a 48 kHz mono 16-bit WAV, the rate the Echo's media player accepts."""
    with wave.open(str(path), 'rb') as source:
        rate, pcm = source.getframerate(), source.readframes(source.getnframes())
    if rate != SPEAKER_RATE:
        import numpy as np
        samples = np.frombuffer(pcm, dtype='<i2').astype(np.float64)
        count = max(1, int(round(len(samples) * SPEAKER_RATE / rate)))
        pcm = np.clip(np.rint(np.interp(np.linspace(0, len(samples) - 1, count), np.arange(len(samples)), samples)),
                      -32768, 32767).astype('<i2').tobytes()
    out = io.BytesIO()
    with wave.open(out, 'wb') as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(SPEAKER_RATE)
        target.writeframes(pcm)
    return out.getvalue()


# ─── Gemini TTS ───────────────────────────────────────────────────────


def _read_key() -> Optional[str]:
    try:
        return json.loads(GEMINI_CONFIG.read_text())['api_key']
    except (OSError, ValueError, KeyError):
        return None


def _decode_audio(part: dict) -> Optional[tuple[bytes, int]]:
    raw = base64.b64decode(part['data'])
    mime = part.get('mimeType', '')
    if raw[:4] == b'RIFF':                              # some models answer with a WAV container
        try:
            with wave.open(io.BytesIO(raw)) as w:
                rate, ch = w.getframerate(), w.getnchannels()
                pcm = w.readframes(w.getnframes())
        except (wave.Error, EOFError):
            return None
        if ch > 1:                                     # fold to mono
            import array
            samples = array.array('h', pcm)
            pcm = array.array('h', [sum(samples[i::ch]) // ch for i in range(0, len(samples), ch)][:len(samples) // ch]).tobytes()
        return pcm, rate
    rate = 24000
    if 'rate=' in mime:
        try:
            rate = int(mime.split('rate=')[-1].split(';')[0])
        except ValueError:
            rate = 24000
    return raw, rate


def _call(key: str, model: str, text: str, voice: str, timeout: float) -> tuple[int, str, Optional[bytes], int]:
    """One TTS request. Returns (http_code, error, pcm|None, rate). Never raises for HTTP/network."""
    body = {'contents': [{'parts': [{'text': text}]}],
            'generationConfig': {'responseModalities': ['AUDIO'],
                                 'speechConfig': {'voiceConfig': {'prebuiltVoiceConfig': {'voiceName': voice}}}}}
    req = urllib.request.Request(_API.format(model=model), data=json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json', 'x-goog-api-key': key})
    try:
        response = json.load(urllib.request.urlopen(req, timeout=timeout))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode('utf-8', 'replace')[:200] if hasattr(exc, 'read') else ''
        return exc.code, detail.replace(key, '<key>'), None, 0
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return 0, type(exc).__name__, None, 0
    try:
        part = response['candidates'][0]['content']['parts'][0]['inlineData']
    except (KeyError, IndexError, TypeError):
        return 200, 'no_audio', None, 0
    decoded = _decode_audio(part)
    if decoded is None:
        return 200, 'bad_audio', None, 0
    return 200, '', decoded[0], decoded[1]


def cleanup(max_age_s: int = MAX_AGE_S) -> int:
    """Delete announcement WAVs older than max_age_s. Returns how many were removed."""
    removed = 0
    now = time.time()
    try:
        entries = list(CACHE_DIR.glob('*.wav'))
    except OSError:
        return 0
    for path in entries:
        try:
            if now - path.stat().st_mtime > max_age_s:
                path.unlink()
                removed += 1
        except OSError:
            pass
    return removed


def synthesize(text: str, voice: str = DEFAULT_VOICE, timeout: float = 30.0,
               also_16k: bool = True) -> dict:
    """Speak `text` (Arabic) to a private WAV. Returns:
        {'status':'ok', 'path', 'path_16k', 'rate', 'duration_s', 'model', 'latency_ms', ...}
        {'status':'unsupported', 'error', 'summary'}  when TTS cannot be used (caller chimes).
        {'status':'error', ...}                        for a bad argument.
    """
    text = ' '.join(str(text or '').split())
    if not text:
        return {'status': 'error', 'error': 'empty', 'summary': 'لا يوجد نص لِنُطقه'}
    if len(text) > MAX_TEXT:
        text = text[:MAX_TEXT]
    if not isinstance(voice, str) or not voice.isascii() or not voice.isalpha():
        voice = DEFAULT_VOICE
    key = _read_key()
    if not key:
        return {'status': 'unsupported', 'error': 'no_key',
                'summary': 'خدمة النطق غير متاحة · سيُشغَّل تنبيه بدلاً منها'}
    cleanup()
    started = time.monotonic()
    last = 'no_model'
    for model in MODELS:
        code, err, pcm, rate = _call(key, model, text, voice, timeout)
        if pcm:
            latency_ms = int((time.monotonic() - started) * 1000)
            uid = secrets.token_hex(6)
            path = CACHE_DIR / f'{uid}.wav'
            _write_private_wav(path, pcm, rate)
            duration_s = round(len(pcm) / 2 / max(1, rate), 2)
            out = {'status': 'ok', 'id': uid, 'path': str(path), 'rate': rate,
                   'duration_s': duration_s, 'model': model, 'voice': voice,
                   'latency_ms': latency_ms, 'text': text,
                   'summary': f'جهّزت النطق ({duration_s} ث · {model.split("-")[1]})'}
            if also_16k:
                pcm16 = to_16k_mono(pcm, rate)
                path16 = CACHE_DIR / f'{uid}.16k.wav'
                _write_private_wav(path16, pcm16, ECHO_RATE)
                out['path_16k'] = str(path16)
            return out
        last = f'{model}:{code}:{err}'[:120]
    return {'status': 'unsupported', 'error': last,
            'summary': 'تعذّر تجهيز النطق الآن · سيُشغَّل تنبيه بدلاً منه'}
