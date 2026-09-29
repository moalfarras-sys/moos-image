"""Wake-triggered Gemini Live -> encrypted Echo voice satellite. Fixed tools only.

One Gemini Live session serves every follow-up turn of a conversation: a new
`start` from the Echo within IDLE_CLOSE_S of the last turn reuses it (no
connect, no history re-send). A session that is closed, stale, dirty (a turn
was cut mid-answer), too old or told to go away is replaced; within the
conversation window the replacement resumes the server context with the latest
session-resumption handle. The Echo is told to listen as soon as local setup
succeeds; its microphone audio waits in the turn queue while a session connects.

Echo stream: S16LE mono 16 kHz in 512-byte blocks, paced at real time with a
small lead. Gemini's 24 kHz reply goes through a stateful polyphase low-pass
resampler (numpy when installed, a pure-Python fallback otherwise).
"""
import asyncio
import collections
import json
import math
import os
import sys
import time
from array import array
from operator import mul
from pathlib import Path

from google import genai
from google.genai import types
from aioesphomeapi import VoiceAssistantEventType as E

import tools

try:
    import numpy as np
except ImportError:  # the pure-Python paths below are complete
    np = None

ROOT = Path(__file__).resolve().parents[1]
GEMINI_CONFIG = Path.home() / '.config/mo-dot/gemini.json'

ECHO_RATE = 16000
ECHO_BLOCK = 512              # bytes per Echo audio message
MIC_GAIN = 4                  # measured quiet array speech; clipped, never wrapped
QUEUE_ITEMS = 512             # mic chunks buffered while a session connects
IDLE_CLOSE_S = 45.0           # keep the session for the Echo's 20 s follow-up
MAX_LINK_AGE_S = 540.0        # Live connections are recycled before ~10 min
RESUME_MAX_AGE_S = 600.0      # never resume from an older handle
CONNECT_TIMEOUT_S = 12.0
CONNECT_BUDGET_S = 20.0       # all connect attempts of one turn together
PING_TIMEOUT_S = 1.5
MIC_IDLE_S = 25.0             # no microphone chunk at all before the reply
NO_REPLY_S = 8.0              # mic closed, nothing heard, no model content
NO_SPEECH_S = 2.5             # same, when this session reports VAD and saw no speech
REPLY_WAIT_S = 12.0           # mic closed, speech heard, no reply yet
STALL_S = 12.0                # the reply (or a tool result) started, then silence
TURN_LIMIT_S = 240.0
PARTIAL_INTERVAL_S = 0.12     # caption throttle
LEVEL_INTERVAL_S = 0.066      # ~15 level events per second
CAPTURE_MAX_S = 15.0          # the Echo keeps one listening window open for at most 15 s
CAPTURE_ARM_S = 25.0          # an armed recording expires if no listening window starts
PLAYBACK_LEAD_S = 0.25        # device-side cushion for Gemini delivery jitter (no added latency)
HISTORY_TURNS = 12
DEAF_PEAK = 1500              # raw mic peak (before gain) that counts as someone speaking
DEAF_LOUD_S = 1.5             # loud audio with no server speech-start while the mic is open
DEAF_MIN_LOUD_S = 0.3         # the same once the mic closed
DEAF_TICK_S = 0.5             # how often a listening turn re-checks for a deaf session
REPLAY_LIMIT = ECHO_RATE * 2 * 60   # turn audio kept for a replay (60 s)
TRANSCRIPTION_LANGUAGES = ['ar-EG']
PREFERRED_WAKE = ('mira_ar_owner', 'mira_ar_experimental')  # the owner wants Mira only (2026-09-29): never Alexa
SETUP_REJECTED = (400, 1007, 1008)                  # Live close codes for a refused setup

_BIG_ENDIAN = sys.byteorder == 'big'


# ─── PCM helpers (S16LE) ──────────────────────────────────────────────
def _samples(data):
    if len(data) & 1:
        data = data[:-1]
    out = array('h')
    out.frombytes(data)
    if _BIG_ENDIAN:
        out.byteswap()
    return out


def _to_bytes(samples):
    if _BIG_ENDIAN:
        samples = array('h', samples)
        samples.byteswap()
    return samples.tobytes()


def pcm_peak(data):
    """Largest absolute sample of an S16LE buffer."""
    if len(data) < 2:
        return 0
    if np is not None:
        values = np.frombuffer(data[:len(data) & ~1], dtype='<i2')
        return int(max(int(values.max()), -int(values.min())))
    values = _samples(data)
    return max(max(values), -min(values))


def pcm_rms(data):
    if len(data) < 2:
        return 0.0
    if np is not None:
        values = np.frombuffer(data[:len(data) & ~1], dtype='<i2').astype(np.float64)
        return float(np.sqrt(np.mean(values * values)))
    values = _samples(data)
    return math.sqrt(sum(map(mul, values, values)) / len(values))


def amplify(data, gain=MIC_GAIN):
    """Multiply S16LE samples by `gain`, clipping at the int16 limits."""
    if np is not None:
        values = np.frombuffer(data[:len(data) & ~1], dtype='<i2').astype(np.int32) * gain
        np.clip(values, -32768, 32767, out=values)
        return values.astype('<i2').tobytes()
    values = _samples(data)
    high, low = 32767 // gain, -(32768 // gain)
    return _to_bytes(array('h', [v * gain if low <= v <= high else (32767 if v > 0 else -32768)
                                 for v in values]))


def write_private_wav(path, pcm, rate=ECHO_RATE):
    """16-bit mono WAV readable only by the owner (0600, directory 0700)."""
    import wave
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'wb') as raw, wave.open(raw, 'wb') as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes(pcm)
    os.chmod(path, 0o600)


def _bessel_i0(x):
    total = term = 1.0
    k = 1
    quarter = x * x / 4.0
    while term > 1e-12 * total:
        term *= quarter / (k * k)
        total += term
        k += 1
    return total


class Resampler:
    """Stateful rational polyphase resampler for mono S16LE (e.g. 24 kHz -> 16 kHz).

    Upsample by L, Kaiser-windowed sinc low-pass (~60 dB stopband) below the
    lower Nyquist rate, downsample by M; only the needed outputs are computed.
    Keep one instance per continuous stream: the filter history carries across
    chunks, so chunk boundaries do not click. Odd trailing bytes are carried.
    """

    ATTENUATION_DB = 60.0

    def __init__(self, in_rate=24000, out_rate=ECHO_RATE, use_numpy=None):
        g = math.gcd(in_rate, out_rate)
        self.up, self.down = out_rate // g, in_rate // g
        self.in_rate, self.out_rate = in_rate, out_rate
        self.use_numpy = (np is not None) if use_numpy is None else bool(use_numpy and np is not None)
        self._odd = b''
        self._total = 0          # input samples consumed
        self._next = 0           # next output index
        if self.up == self.down:
            self.taps_per_phase = 0
            return
        nyquist = min(in_rate, out_rate) / 2.0
        rate = float(in_rate * self.up)
        cutoff = 0.9625 * nyquist / rate          # -6 dB point, normalised to the upsampled rate
        width = 2 * 0.1125 * nyquist / rate       # transition band
        count = int(math.ceil((self.ATTENUATION_DB - 7.95) / (2.285 * 2 * math.pi * width))) + 1
        count = int(math.ceil(count / self.up) * self.up)
        beta = 0.1102 * (self.ATTENUATION_DB - 8.7)
        centre = (count - 1) / 2.0
        norm = _bessel_i0(beta)
        taps = []
        for i in range(count):
            x = i - centre
            ideal = 2 * cutoff * (math.sin(2 * math.pi * cutoff * x) / (2 * math.pi * cutoff * x) if x else 1.0)
            ratio = 2 * i / (count - 1) - 1
            taps.append(self.up * ideal * _bessel_i0(beta * math.sqrt(max(0.0, 1 - ratio * ratio))) / norm)
        self.taps_per_phase = count // self.up
        # phases[p][j] multiplies x[i_hi - (T-1) + j]: reversed polyphase components.
        self.phases = [list(reversed(taps[p::self.up])) for p in range(self.up)]
        self._history = [0.0] * (self.taps_per_phase - 1)
        if self.use_numpy:
            self._np_phases = [np.asarray(phase, dtype=np.float64) for phase in self.phases]
            self._np_history = np.zeros(self.taps_per_phase - 1, dtype=np.float64)

    def process(self, data):
        """Resample a chunk; returns S16LE bytes (possibly empty)."""
        data = self._odd + data
        if len(data) & 1:
            self._odd, data = data[-1:], data[:-1]
        else:
            self._odd = b''
        if not data:
            return b''
        if self.taps_per_phase == 0:
            return data
        if self.use_numpy:
            return self._process_numpy(np.frombuffer(data, dtype='<i2').astype(np.float64))
        return self._process_python(_samples(data))

    def _outputs(self, count):
        """Output indices computable once `count` more input samples arrived."""
        base = self._total - (self.taps_per_phase - 1)   # input index of buffer[0]
        self._total += count
        last = (self._total * self.up - 1) // self.down
        first = self._next
        self._next = last + 1
        return base, first, last

    def _process_numpy(self, fresh):
        taps = self.taps_per_phase
        buffer = np.concatenate([self._np_history, fresh])
        base, first, last = self._outputs(len(fresh))
        self._np_history = buffer[len(buffer) - (taps - 1):] if taps > 1 else buffer[:0]
        if last < first:
            return b''
        index = np.arange(first, last + 1, dtype=np.int64) * self.down
        start = index // self.up - base - (taps - 1)
        phase = index % self.up
        windows = np.lib.stride_tricks.sliding_window_view(buffer, taps)
        out = np.empty(len(index), dtype=np.float64)
        for p in range(self.up):
            chosen = phase == p
            if chosen.any():
                out[chosen] = windows[start[chosen]] @ self._np_phases[p]
        return np.clip(np.rint(out), -32768, 32767).astype('<i2').tobytes()

    def _process_python(self, fresh):
        taps = self.taps_per_phase
        buffer = self._history + [float(v) for v in fresh]
        base, first, last = self._outputs(len(fresh))
        self._history = buffer[len(buffer) - (taps - 1):] if taps > 1 else []
        out = array('h')
        up, down, phases = self.up, self.down, self.phases
        for n in range(first, last + 1):
            k = n * down
            s = k // up - base - (taps - 1)
            value = sum(map(mul, phases[k % up], buffer[s:s + taps]))
            out.append(32767 if value >= 32767 else -32768 if value <= -32768 else int(round(value)))
        return _to_bytes(out)


def _mime_rate(mime, default=24000):
    for part in (mime or '').split(';'):
        key, _, value = part.strip().partition('=')
        if key == 'rate' and value.isdigit():
            return int(value)
    return default


# ─── playback ─────────────────────────────────────────────────────────
class _Player:
    """Paces 16 kHz reply audio to the Echo at real time and reports levels
    on the device's playback clock (not when a packet arrived)."""

    def __init__(self, send, say_level, lead=None):
        self.send = send
        self.say_level = say_level
        self.lead = PLAYBACK_LEAD_S if lead is None else lead
        self.buffer = bytearray()
        self.wake = asyncio.Event()
        self.finished = False
        self.sent = 0
        self.underruns = 0
        self.clock = 0.0                      # when the device finishes what was sent
        self.levels = collections.deque()     # (play_at, level)
        self.last_level = 0.0

    def push(self, data):
        if data:
            self.buffer += data
            self.wake.set()

    def clear(self):
        dropped = len(self.buffer)
        self.buffer.clear()
        self.levels.clear()
        return dropped

    def finish(self):
        self.finished = True
        self.wake.set()

    def remaining_s(self):
        return len(self.buffer) / (ECHO_RATE * 2) + max(0.0, self.clock - time.monotonic())

    def _levels_due(self, now):
        due = None
        while self.levels and self.levels[0][0] <= now:
            due = self.levels.popleft()[1]
        if due is not None and now - self.last_level >= LEVEL_INTERVAL_S:
            self.last_level = now
            self.say_level(due)

    async def run(self):
        bytes_per_s = ECHO_RATE * 2
        while True:
            if len(self.buffer) >= ECHO_BLOCK or (self.finished and self.buffer):
                block = bytes(self.buffer[:ECHO_BLOCK])
                del self.buffer[:ECHO_BLOCK]
                now = time.monotonic()
                if self.clock < now:
                    if self.sent:
                        self.underruns += 1
                    self.clock = now
                ahead = self.clock - now
                if ahead > self.lead:
                    await asyncio.sleep(ahead - self.lead)
                    now = time.monotonic()
                self._levels_due(now)
                self.send(block)
                self.levels.append((self.clock, min(1.0, pcm_peak(block) / 16000)))
                self.sent += len(block)
                self.clock += len(block) / bytes_per_s
                continue
            if self.finished:
                break
            self.wake.clear()
            await self.wake.wait()
        # Let the device play what it has, reporting levels on its clock.
        while True:
            now = time.monotonic()
            self._levels_due(now)
            if now >= self.clock:
                break
            await asyncio.sleep(min(0.05, self.clock - now))
        self.say_level(0.0)


class _Captions:
    """Throttled partial captions; `flush` shows the latest pending text."""

    def __init__(self, say, interval=None):
        self.say = say
        self.interval = PARTIAL_INTERVAL_S if interval is None else interval
        self.last = {}
        self.shown = {}
        self.pending = {}

    def update(self, kind, text):
        text = text.strip()
        if not text or self.shown.get(kind) == text:
            return
        if time.monotonic() - self.last.get(kind, -1e9) >= self.interval:
            self._show(kind, text)
        else:
            self.pending[kind] = text

    def tick(self):
        now = time.monotonic()
        for kind in list(self.pending):
            if now - self.last.get(kind, -1e9) >= self.interval:
                self._show(kind, self.pending[kind])

    def flush(self, kind=None):
        for name in ([kind] if kind else list(self.pending)):
            if name in self.pending:
                self._show(name, self.pending[name])

    def _show(self, kind, text):
        self.pending.pop(kind, None)
        self.last[kind] = time.monotonic()
        self.shown[kind] = text
        self.say(kind, text)


# ─── one Gemini Live connection ───────────────────────────────────────
_CLOSED = object()
_SENDER_DONE = object()
_TIMEOUT = object()


class _LiveLink:
    """Owns one Live websocket. A single reader task feeds `inbox`, observes
    resumption handles and go-away notices, and marks the link closed."""

    def __init__(self, client, model, config, voice_name, *, resumed=False, advanced=True):
        self.client = client
        self.model = model
        self.config = config
        self.voice_name = voice_name
        self.resumed = resumed
        self.advanced = advanced
        self.history_mode = 'resumed' if resumed else ('initial' if advanced else 'inline')
        self.session = None
        self.inbox = asyncio.Queue()
        self.ready = asyncio.Event()
        self.task = None
        self.exc = None
        self.closed = False
        self.dirty = False
        self.idle_closed = False
        self.go_away = False
        self.vad_seen = False           # the server sends voice-activity signals
        self.created = time.monotonic()
        self.last_used = self.created
        self.resume_handle = None
        self.handle_at = 0.0

    async def open(self, timeout=CONNECT_TIMEOUT_S):
        self.task = asyncio.create_task(self._own())
        try:
            await asyncio.wait_for(self.ready.wait(), timeout)
        except asyncio.TimeoutError:
            await self.close()
            raise TimeoutError('live connect timed out') from None
        if self.session is None:
            await self.close()
            raise self.exc or ConnectionError('live session closed')

    async def _own(self):
        try:
            async with self.client.aio.live.connect(model=self.model, config=self.config) as session:
                self.session = session
                self.ready.set()
                while True:
                    async for message in session.receive():
                        self._observe(message)
                        self.inbox.put_nowait(message)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # never stringified: Live URLs can carry the key
            self.exc = exc
        finally:
            self.closed = True
            self.ready.set()
            self.inbox.put_nowait(_CLOSED)

    def _observe(self, message):
        update = getattr(message, 'session_resumption_update', None)
        if update is not None and update.resumable and update.new_handle:
            self.resume_handle = update.new_handle
            self.handle_at = time.monotonic()
        if getattr(message, 'go_away', None) is not None:
            self.go_away = True
        if getattr(message, 'voice_activity', None) is not None or \
                getattr(message, 'voice_activity_detection_signal', None) is not None:
            self.vad_seen = True

    def usable(self, voice_name, now):
        return (not self.closed and not self.dirty and not self.go_away and self.session is not None
                and self.task is not None and not self.task.done() and self.voice_name == voice_name
                and now - self.created < MAX_LINK_AGE_S and now - self.last_used < IDLE_CLOSE_S)

    def drain_stale(self):
        """Discard queued messages; report model output that belonged to no turn."""
        stale = False
        while True:
            try:
                item = self.inbox.get_nowait()
            except asyncio.QueueEmpty:
                return stale
            if item is _CLOSED:
                stale = True
                continue
            content = getattr(item, 'server_content', None)
            if getattr(item, 'tool_call', None) or (content is not None and (content.model_turn or content.output_transcription)):
                stale = True

    async def alive(self, timeout=PING_TIMEOUT_S):
        if self.closed or self.session is None:
            return False
        socket = getattr(self.session, '_ws', None)
        ping = getattr(socket, 'ping', None)
        if ping is None:
            return True
        try:
            waiter = await ping()
            await asyncio.wait_for(waiter, timeout)
            return True
        except asyncio.CancelledError:
            raise
        except Exception:
            return False

    async def close(self):
        self.closed = True
        if self.task is not None and not self.task.done():
            self.task.cancel()
            await asyncio.wait({self.task}, timeout=3)
        try:
            await self.client.aio.aclose()
        except Exception:
            pass


# ─── the voice satellite ──────────────────────────────────────────────
class LiveVoice:
    def __init__(self, api, entities, emit, voice_name='Aoede'):
        self.api = api
        self.entities = entities
        self.emit = emit
        self.unsubscribe = None
        self.turn = None
        self.enabled = False
        self.last_stats = {}
        self.test_text = None
        self.history = []
        self.voice_name = voice_name
        self.next_local_source = None
        self.lang = 'ar'            # owner interface language for the persona
        self.city = None            # owner weather city for the persona
        self.allowed_tools = None   # optional tool allowlist (diagnostics)
        self.request_confirmation = None   # the owner's cards for system changes (tools.ToolContext)
        self.mic_gain = MIC_GAIN    # the Echo's array is quiet; a desk microphone needs none (desk_voice)
        self.wake_hint = 'هَي ميرا'
        self.link = None
        self._advanced = True       # resumption/compression/history setup accepted
        self._vad_supported = False # the Live model reports voice activity
        self._idle_task = None
        self._closing = set()
        self.capture = None         # an armed voice-enrolment recording (see arm_capture)

    # ── small utilities ──────────────────────────────────────────────
    def _say(self, kind, text):
        try:
            self.emit(kind, text)
        except Exception:
            pass

    def event(self, name, data=None):
        if self.api.is_connected:
            try:
                self.api.send_voice_assistant_event(getattr(E, 'VOICE_ASSISTANT_' + name), data or {})
            except Exception:
                pass

    def _ready_text(self):
        return 'قل «' + self.wake_hint + '» ثم سؤالك'

    # ── enable / disable ─────────────────────────────────────────────
    async def enable(self):
        if self.enabled:
            self._say('ready', self._ready_text())
            return
        cfg = await self.api.get_voice_assistant_configuration(8)
        if not list(cfg.active_wake_words or []):
            # Only an empty selection is repaired. Any active wake word — the
            # owner's [alexa, mira_ar_experimental] included — is left alone.
            ids = {word.id for word in cfg.available_wake_words}
            limit = getattr(cfg, 'max_active_wake_words', 0) or 2
            choice = [word for word in PREFERRED_WAKE if word in ids][:limit]
            if not choice and 'hey_mira' in ids:
                choice = ['hey_mira']
            if choice:
                await self.api.set_voice_assistant_configuration(choice)
            else:
                await self._install_hey_mira()
        cfg = await self.api.get_voice_assistant_configuration(8)
        labels = {word.id: word.wake_word for word in cfg.available_wake_words}
        self.wake_hint = ' / '.join(labels.get(word, word) for word in cfg.active_wake_words) or 'هَي ميرا'
        self._say('wake', self._ready_text())
        for name, value in [('reply_delivery_1', 'Streamed')]:
            if name in self.entities:
                entity = self.entities[name]
                self.api.select_command(entity.key, value, device_id=entity.device_id)
        # Device end-of-speech closes its own microphone stream.
        if 'microphone_end_of_speech' in self.entities:
            entity = self.entities['microphone_end_of_speech']
            self.api.switch_command(entity.key, True, device_id=entity.device_id)
        if 'follow_up_1' in self.entities:
            entity = self.entities['follow_up_1']
            self.api.number_command(entity.key, 20, device_id=entity.device_id)
        self.unsubscribe = self.api.subscribe_voice_assistant(
            handle_start=self.start, handle_stop=self.stop, handle_audio=self.audio)
        self.enabled = True
        self._say('ready', self._ready_text())

    async def _install_hey_mira(self):
        """No wake word is active and none is installed: offer the Mira model."""
        import hashlib
        import socket
        from aioesphomeapi.model import VoiceAssistantExternalWakeWord as ExternalWakeWord
        from mira_bridge import IP
        raw = (Path(__file__).parent / 'hey_mira.tflite').read_bytes()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.connect((IP, 6053))
            host = sock.getsockname()[0]
        finally:
            sock.close()
        offer = ExternalWakeWord(id='hey_mira', wake_word='Hey Mira', trained_languages=['en'],
                                 model_type='openwakeword', model_size=len(raw),
                                 model_hash=hashlib.sha256(raw).hexdigest(),
                                 url=f'http://{host}:18769/hey_mira.json')
        await self.api.get_voice_assistant_configuration(8, [offer])
        await self.api.set_voice_assistant_configuration(['hey_mira'])
        await asyncio.sleep(4)
        cfg = await self.api.get_voice_assistant_configuration(8)
        if 'hey_mira' not in cfg.active_wake_words:
            raise RuntimeError('Mira wake model installation failed')

    async def disable(self):
        self.enabled = False
        if self.api.is_connected and 'follow_up_1' in self.entities:
            entity = self.entities['follow_up_1']
            try:
                self.api.number_command(entity.key, 0, device_id=entity.device_id)
            except Exception:
                pass
        if self.unsubscribe:
            self.unsubscribe()
            self.unsubscribe = None
        self._cancel_idle()
        turn = self.turn
        if turn:
            turn['task'].cancel()
            self.turn = None
            await asyncio.wait({turn['task']}, timeout=2)
        await self._drop_link('disabled')
        self._say('off', 'المحادثة الصوتية متوقفة')

    # ── Echo pipeline callbacks ──────────────────────────────────────
    async def start(self, conversation_id=None, flags=0, audio_settings=None, wake_word_phrase=None):
        """Echo asks us to listen. Returns 0 (API audio) or None on failure; never raises."""
        try:
            return await self._start()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._say('error', 'تعذّر بدء الاستماع: ' + type(exc).__name__)
            return None

    async def _start(self):
        spec, self.capture = self.capture, None
        if spec and time.monotonic() - spec['armed_at'] < CAPTURE_ARM_S:
            return await self._start_capture(spec)
        self._say('activating', 'وصل طلب الاستماع من Echo · أهيّئ المحادثة')
        old = self.turn
        if old and old.get('task'):
            old['superseded'] = True   # the Echo already runs the new pipeline: no ERROR event
            old['task'].cancel()
            await asyncio.wait({old['task']}, timeout=1.5)
        self._cancel_idle()
        local_source = self.next_local_source
        self.next_local_source = None
        t = {'ready': asyncio.Event(), 'queue': asyncio.Queue(QUEUE_ITEMS), 'done': False, 'out': 0,
             'input': 0, 'peak': 0, 'reply': '', 'heard': '', 'interim': '', 'started': time.monotonic(),
             'tts': False, 'test_text': self.test_text, 'local_source': local_source,
             'input_source': 'pc_pending' if local_source else 'echo',
             'echo_buffer': collections.deque(maxlen=50), 'phase': 'connecting', 'stats': {},
             'tool_log': [], 'cancelled_calls': set(), 'interrupted': 0}
        self.test_text = None
        self.turn = t
        t['task'] = asyncio.create_task(self.run(t))
        if local_source:
            t['capture_task'] = asyncio.create_task(self.capture_local(t, local_source))
        try:
            await asyncio.wait_for(t['ready'].wait(), 15)
        except asyncio.TimeoutError:
            t['error'] = 'setup_timeout'
            t['task'].cancel()
            return None
        if t.get('error'):
            return None
        self.event('RUN_START')
        self.event('STT_START')
        self._say('listening', 'ميكروفون الكمبيوتر · أسمعك…' if local_source else 'أسمعك…')
        return 0

    async def audio(self, data, data2=None):
        t = self.turn
        if not t or t['done'] or t['tts']:
            return
        if t.get('capture'):
            self._capture_audio(t, data)
            return
        if t.get('local_source'):
            t['echo_buffer'].append(data)
            return
        await self.enqueue_audio(t, data)

    async def enqueue_audio(self, t, data):
        # No await before put_nowait: aioesphomeapi schedules one task per chunk
        # and this keeps them in arrival order.
        if not t or t['done'] or t['tts']:
            return
        t['input'] += len(data)
        peak = pcm_peak(data)
        if peak > t['peak']:
            t['peak'] = peak
        if peak >= DEAF_PEAK:
            t['loud_s'] = t.get('loud_s', 0.0) + len(data) / (ECHO_RATE * 2)
        now = time.monotonic()
        if now - t.get('last_level', 0) >= LEVEL_INTERVAL_S:
            t['last_level'] = now
            self._say('level', str(min(1, peak / 5000)))
        # Controlled gain compensates the array's measured quiet speech.
        data = amplify(data, self.mic_gain)
        try:
            t['queue'].put_nowait(data)
        except asyncio.QueueFull:
            t['error'] = 'audio_queue_full'
            if t.get('task'):
                t['task'].cancel()
            self._say('error', 'الاتصال بطيء؛ أعد المحاولة')

    async def capture_local(self, t, source):
        """Receive PCM from the wake listener's single microphone capture stream."""
        writer = None
        cancelled = False
        fallback = False
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_unix_connection(f'/run/user/{os.getuid()}/mira-pcm.sock'), 3)
            started = time.monotonic()
            probe = []
            while len(probe) < 8 and time.monotonic() - started < 2.5:
                try:
                    probe.append(await asyncio.wait_for(reader.readexactly(3200), 1.5))
                except (asyncio.IncompleteReadError, asyncio.TimeoutError):
                    break
            if len(probe) < 8:
                fallback = True
            else:
                t['input_source'] = 'pc'
                t['echo_buffer'].clear()
            noise = 90.0
            voiced = 0
            quiet = 0
            pending = collections.deque(probe)
            while self.turn is t and not t['done'] and time.monotonic() - started < 14:
                if fallback:
                    break
                if pending:
                    data = pending.popleft()
                else:
                    try:
                        data = await asyncio.wait_for(reader.readexactly(3200), 3)
                    except (asyncio.IncompleteReadError, asyncio.TimeoutError):
                        break
                level = pcm_rms(data)
                speaking = level > max(85.0, noise * 1.6)
                if not speaking and voiced == 0:
                    noise = .98 * noise + .02 * level
                await self.enqueue_audio(t, data)
                if speaking:
                    voiced += 1
                    quiet = 0
                elif voiced:
                    quiet += 1
                if voiced >= 2 and quiet >= 10:
                    break
        except (OSError, ValueError):
            fallback = True
        except asyncio.CancelledError:
            cancelled = True
            raise
        finally:
            if writer:
                writer.close()
                try:
                    await writer.wait_closed()
                except OSError:
                    pass
            if self.turn is t and not t['done'] and not cancelled:
                if fallback or t['input'] == 0:
                    for frame in t['echo_buffer']:
                        await self.enqueue_audio(t, frame)
                    t['echo_buffer'].clear()
                    t['local_source'] = None
                    t['input_source'] = 'echo_fallback'
                    self._say('listening', 'Echo · بث الكمبيوتر بطيء أو غير متاح')
                    if t.pop('echo_stop_pending', False):
                        await self.stop(False)
                else:
                    await self.stop(False, local=True)

    async def stop(self, abort, local=False):
        t = self.turn
        if not t:
            return
        if t.get('capture'):
            await self._finish_capture(t, 'aborted' if abort else 'echo_closed')
            return
        if abort:
            if t.get('task'):
                t['task'].cancel()
            return
        # Echo's own silence detector cannot close a PC microphone turn.
        if t.get('local_source') and not local:
            t['echo_stop_pending'] = True
            return
        if not t['done']:
            t['done'] = True
            await t['queue'].put(None)
            if not t.get('tts') and t.get('phase', 'listening') in ('connecting', 'listening'):
                self._say('thinking', 'أفكر في طلبك…')

    # ── voice enrolment: record the owner through the Echo, locally ──
    def arm_capture(self, path, max_s=CAPTURE_MAX_S):
        """Record the NEXT Echo listening window to `path` (16 kHz mono S16LE WAV) instead of
        sending it to Gemini. Used to teach the wake word the owner's voice; nothing leaves this
        computer. The Echo's end-of-speech cut is paused so the whole window is kept."""
        self.capture = {'path': Path(path), 'max_s': float(max_s), 'armed_at': time.monotonic()}
        self._end_of_speech(False)

    def disarm_capture(self):
        if self.capture:
            self.capture = None
            self._end_of_speech(True)

    def _end_of_speech(self, on):
        entity = self.entities.get('microphone_end_of_speech')
        if entity is not None and self.api.is_connected:
            try:
                self.api.switch_command(entity.key, bool(on), device_id=entity.device_id)
            except Exception:
                pass

    async def _start_capture(self, spec):
        old = self.turn
        if old and old.get('task'):
            old['superseded'] = True
            old['task'].cancel()
            await asyncio.wait({old['task']}, timeout=1.5)
        t = {'capture': spec, 'data': bytearray(), 'started': time.monotonic(), 'done': False,
             'tts': False, 'peak': 0, 'input': 0}
        self.turn = t
        t['task'] = asyncio.create_task(self._capture_guard(t))
        self.event('RUN_START')
        self.event('STT_START')
        self._say('listening', 'أسجّل صوتك للتدريب… قل «ميرا» بهدوء كل ثانيتين')
        return 0

    def _capture_audio(self, t, data):
        limit = int(t['capture']['max_s'] * ECHO_RATE * 2)
        room = limit - len(t['data'])
        if room > 0:
            t['data'] += data[:room]
        t['input'] += len(data)
        peak = pcm_peak(data)
        t['peak'] = max(t['peak'], peak)
        now = time.monotonic()
        if now - t.get('last_level', 0) >= LEVEL_INTERVAL_S:
            t['last_level'] = now
            self._say('level', str(min(1, peak / 5000)))

    async def _capture_guard(self, t):
        await asyncio.sleep(t['capture']['max_s'] + 2.0)
        await self._finish_capture(t, 'time_limit')

    async def _finish_capture(self, t, why):
        if t['done']:
            return
        t['done'] = True
        task = t.get('task')
        if task and task is not asyncio.current_task():
            task.cancel()
        self._end_of_speech(True)
        path = t['capture']['path']
        seconds = len(t['data']) / (ECHO_RATE * 2)
        result = {'path': str(path), 'seconds': round(seconds, 2), 'peak': t['peak'], 'why': why,
                  'status': 'ok' if seconds >= 2.0 else 'too_short'}
        try:
            write_private_wav(path, bytes(t['data']))
        except OSError as exc:
            result.update(status='error', error=type(exc).__name__)
        self.event('RUN_END')
        if self.turn is t:
            self.turn = None
        self._say('capture', json.dumps(result, ensure_ascii=False))
        self._say('ready', self._ready_text())

    # ── fixed Echo controls ──────────────────────────────────────────
    def device_command(self, args):
        """Send one fixed speaker/ring command; returns {'ok', 'sent_to_device'}. No readback."""
        action = args.get('action')
        value = args.get('value')
        speaker = self.entities.get('speaker')
        if action == 'set_volume':
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 100:
                raise ValueError('volume must be 0–100')
            if speaker is None:
                raise RuntimeError('Echo speaker entity missing')
            self.api.media_player_command(speaker.key, volume=value / 100, device_id=speaker.device_id)
        elif action in ('light_on', 'light_off'):
            ring = self.entities['ring']
            self.api.light_command(ring.key, state=action == 'light_on', brightness=.25, rgb=(.2, .5, 1),
                                   color_mode=35, device_id=ring.device_id)
        elif action == 'stop_music':
            from aioesphomeapi import MediaPlayerCommand
            if speaker is None:
                raise RuntimeError('Echo speaker entity missing')
            self.api.media_player_command(speaker.key, command=MediaPlayerCommand.STOP, device_id=speaker.device_id)
        else:
            raise ValueError('unsupported fixed action')
        return {'ok': True, 'sent_to_device': True}

    def control(self, args):
        """Legacy surface: device_command plus an `action` event."""
        result = self.device_command(args)
        self._say('action', f"تم إرسال التحكم للجهاز: {args.get('action')}")
        return result

    # ── session management ───────────────────────────────────────────
    def _load_config(self):
        config = json.loads(GEMINI_CONFIG.read_text())
        if not isinstance(config, dict) or not config.get('api_key') or not config.get('model'):
            raise ValueError('gemini.json needs api_key and model')
        return config

    def _make_client(self, config):
        return genai.Client(api_key=config['api_key'])

    def _setup(self, handle, advanced):
        setup = {
            'response_modalities': ['AUDIO'],
            'speech_config': {'voice_config': {'prebuilt_voice_config': {'voice_name': self.voice_name}}},
            'input_audio_transcription': {'language_codes': list(TRANSCRIPTION_LANGUAGES)},
            'output_audio_transcription': {},
            'realtime_input_config': {'automatic_activity_detection': {
                'start_of_speech_sensitivity': 'START_SENSITIVITY_HIGH',
                'end_of_speech_sensitivity': 'END_SENSITIVITY_LOW',
                'prefix_padding_ms': 300, 'silence_duration_ms': 1000}},
            'system_instruction': tools.system_instruction(self.lang, self.city, channel='voice'),
            'tools': [{'function_declarations': tools.live_declarations(blocking=advanced)}],
        }
        if advanced:
            setup['session_resumption'] = {'handle': handle} if handle else {}
            setup['context_window_compression'] = {'sliding_window': {}}
            if not handle:
                setup['history_config'] = {'initial_history_in_client_content': True}
        return setup

    async def _connect(self, config, handle):
        """Open a link: resume with `handle` if given, else fresh; drop the
        advanced setup once if the server refuses it."""
        from google.genai import errors as genai_errors
        attempts = []
        if handle:
            attempts.append((handle, True))
        attempts.append((None, self._advanced))
        deadline = time.monotonic() + CONNECT_BUDGET_S
        last = None
        index = 0
        while index < len(attempts):
            use_handle, advanced = attempts[index]
            index += 1
            remaining = deadline - time.monotonic()
            if remaining <= 0.5:
                break
            link = _LiveLink(self._make_client(config), config['model'], self._setup(use_handle, advanced),
                             self.voice_name, resumed=bool(use_handle), advanced=advanced)
            try:
                await link.open(min(CONNECT_TIMEOUT_S, remaining))
            except asyncio.CancelledError:
                await link.close()
                raise
            except Exception as exc:
                last = exc
                await link.close()
                if (advanced and not use_handle and isinstance(exc, genai_errors.APIError)
                        and exc.code in SETUP_REJECTED and (None, False) not in attempts):
                    attempts.append((None, False))
                continue
            if not advanced and self._advanced:
                self._advanced = False  # this model refuses the advanced setup; stop trying
            if not use_handle:
                await self._seed(link)
            return link
        raise last or TimeoutError('live connect budget exhausted')

    async def _seed(self, link):
        turns = tools.conversation_turns(HISTORY_TURNS)
        if link.history_mode == 'initial':
            # history_config: the server waits for this turn_complete before realtime input.
            await link.session.send_client_content(turns=turns or None, turn_complete=True)
        elif turns:
            await link.session.send_client_content(turns=turns, turn_complete=False)

    async def _acquire(self, t, config):
        """A usable link for this turn: reuse, resume or connect."""
        now = time.monotonic()
        link = self.link
        handle = None
        if link is not None:
            stale = link.drain_stale()
            if not stale and link.usable(self.voice_name, now):
                checked = time.monotonic()
                if await link.alive():
                    link.last_used = time.monotonic()
                    t['stats']['ping_ms'] = int((link.last_used - checked) * 1000)
                    t['session'] = 'reused'
                    self._say('session', json.dumps({'state': 'reused'}))
                    return link
            if (link.resume_handle and not link.idle_closed and link.voice_name == self.voice_name
                    and now - link.last_used < IDLE_CLOSE_S and now - link.handle_at < RESUME_MAX_AGE_S):
                handle = link.resume_handle
            self.link = None
            self._close_later(link)
        new = await self._connect(config, handle)
        self.link = new
        t['session'] = 'resumed' if new.resumed else 'fresh'
        self._say('session', json.dumps({'state': t['session'], 'features': 'advanced' if new.advanced else 'plain'}))
        return new

    def _close_later(self, link):
        task = asyncio.create_task(link.close())
        self._closing.add(task)
        task.add_done_callback(self._closing.discard)

    async def _drop_link(self, reason):
        link = self.link
        self.link = None
        if link is not None:
            await link.close()
            self._say('session', json.dumps({'state': 'closed', 'reason': reason}))

    def _cancel_idle(self):
        if self._idle_task is not None and not self._idle_task.done():
            self._idle_task.cancel()
        self._idle_task = None

    def _arm_idle_close(self, link):
        self._cancel_idle()
        self._idle_task = asyncio.create_task(self._idle_close(link))

    async def _idle_close(self, link):
        await asyncio.sleep(IDLE_CLOSE_S)
        if self.link is link and self.turn is None:
            link.idle_closed = True
            await self._drop_link('idle')

    # ── one turn ─────────────────────────────────────────────────────
    async def run(self, t):
        try:
            await self._run(t)
        except asyncio.CancelledError:
            t['error'] = t.get('error') or 'cancelled'
            link = t.get('link')
            if link is not None and t.get('phase') != 'draining':
                link.dirty = True
            if not t.get('superseded'):
                self.event('ERROR', {'code': 'cancelled', 'message': 'المحادثة أوقفت'})
                self._say('ready' if self.enabled else 'off', 'توقفت المحادثة')
        except Exception as exc:
            # Setup, config and connect failures all land here. Only the class
            # name is shown: Live exception text can contain the key in a URL.
            t['error'] = type(exc).__name__
            link = t.get('link')
            if link is not None:
                link.dirty = True
            self.event('ERROR', {'code': 'gemini_unavailable', 'message': 'تعذّر الاتصال بالصوت'})
            self._say('error', 'تعذّر الصوت: ' + type(exc).__name__)
        finally:
            t['ready'].set()
            for key in ('capture_task', 'sender', 'player_task'):
                task = t.get(key)
                if task is not None and not task.done():
                    task.cancel()
            self._finish_stats(t)
            if self.turn is t:
                self.turn = None
            link = t.get('link')
            if link is not None and link is self.link and self.turn is None and link.dirty:
                self._arm_idle_close(link)   # a dirty link is replaced at the next turn anyway

    async def _run(self, t):
        config = self._load_config()          # a missing/invalid file fails before listening
        t['ready'].set()                      # the Echo streams now; audio waits in the queue
        async with asyncio.timeout(TURN_LIMIT_S):
            link = await self._acquire(t, config)
            t['link'] = link
            t['stats']['connect_ms'] = int((time.monotonic() - t['started']) * 1000)
            t['phase'] = 'listening'
            t['sender'] = asyncio.create_task(self._send(t, link))
            if t['test_text']:
                if link.history_mode == 'inline':
                    await link.session.send_client_content(
                        turns={'role': 'user', 'parts': [{'text': t['test_text']}]}, turn_complete=True)
                else:
                    await link.session.send_realtime_input(text=t['test_text'])
                t['input_ended'] = True
                t['input_end_at'] = time.monotonic()
            player = _Player(self._send_audio, lambda value: self._say('level', f'{value:.3f}'))
            t['player'] = player
            t['player_task'] = asyncio.create_task(player.run())
            captions = t['captions'] = _Captions(self._say)
            while True:
                clean = await self._converse(t, link, captions)
                if clean != 'deaf':
                    break
                # Measured on gemini-3.1-flash-live: a reused session can stop hearing
                # (no voice-activity events for clear speech). Replace it once and
                # replay this turn's audio; a fresh or resumed session hears it.
                t['retried'] = True
                t['stats']['deaf_retry'] = t['session']
                link.dirty = True
                sender = t.get('sender')
                if sender is not None and not sender.done():
                    sender.cancel()
                    await asyncio.wait({sender}, timeout=1)
                link = await self._acquire(t, config)
                t['link'] = link
                t['sender'] = asyncio.create_task(self._send(t, link, replay=True))
            if not clean:
                link.dirty = True
            t['phase'] = 'draining'
            await self._drain(t, link)
            t['phase'] = 'closing'
            link.last_used = time.monotonic()
            if link is self.link:
                self._arm_idle_close(link)
            if t['tts']:
                self.event('TTS_START', {'text': t['reply']})
                self.event('TTS_STREAM_END')
            self.event('RUN_END')
            if t['reply'] and (t['test_text'] or t['heard']):
                self.history.extend([{'role': 'user', 'parts': [{'text': t['test_text'] or t['heard']}]},
                                     {'role': 'model', 'parts': [{'text': t['reply']}]}])
                self.history = self.history[-12:]
            self._say('ready', self._ready_text())

    def _send_audio(self, block):
        if self.api.is_connected:
            self.api.send_voice_assistant_audio(block)

    async def _send(self, t, link, replay=False):
        """Microphone queue -> Live realtime input. Coalesces what queued up while
        connecting and keeps the turn's audio so a replacement session can replay it."""
        session = link.session
        kept = t.setdefault('sent_audio', [])
        if replay:
            pending = b''.join(kept)
            for i in range(0, len(pending), 16000):
                await session.send_realtime_input(audio=types.Blob(data=pending[i:i + 16000],
                                                                   mime_type='audio/pcm;rate=16000'))
            if t.get('input_ended'):
                await session.send_realtime_input(audio_stream_end=True)
                t['input_end_at'] = time.monotonic()
                return
        while True:
            try:
                data = await asyncio.wait_for(t['queue'].get(), MIC_IDLE_S)
            except asyncio.TimeoutError:
                if t['tts'] or t.get('got_output'):
                    return  # the answer is under way; the Echo simply kept its mic open
                raise TimeoutError('device microphone did not close within its listening window')
            end = data is None
            chunk = b'' if end else data
            while not end and len(chunk) < 16000 and not t['queue'].empty():
                more = t['queue'].get_nowait()
                if more is None:
                    end = True
                else:
                    chunk += more
            if chunk:
                if t.get('sent_bytes', 0) + len(chunk) <= REPLAY_LIMIT:
                    kept.append(chunk)
                    t['sent_bytes'] = t.get('sent_bytes', 0) + len(chunk)
                await session.send_realtime_input(audio=types.Blob(data=chunk, mime_type='audio/pcm;rate=16000'))
                t['last_input_at'] = time.monotonic()
            if end:
                await session.send_realtime_input(audio_stream_end=True)
                t['input_ended'] = True
                t['input_end_at'] = time.monotonic()
                return

    def _budget(self, t):
        """How long to wait for the next server message before ending the turn."""
        if t.get('phase') == 'after_interrupt':
            return NO_REPLY_S
        if not t.get('input_ended'):
            return MIC_IDLE_S + 5
        if not t.get('got_output'):
            if t['heard'] or t['interim'] or t['tool_log'] or t.get('speech_detected'):
                return REPLY_WAIT_S
            link = t.get('link')
            if link is not None and link.vad_seen:
                return NO_SPEECH_S
            return NO_REPLY_S
        return STALL_S

    async def _next(self, t, link, timeout):
        try:
            return link.inbox.get_nowait()    # never report a timeout over a queued message
        except asyncio.QueueEmpty:
            pass
        getter = asyncio.ensure_future(link.inbox.get())
        waiters = {getter}
        sender = t.get('sender')
        if sender is not None and not sender.done():
            waiters.add(sender)
        done, _ = await asyncio.wait(waiters, timeout=timeout, return_when=asyncio.FIRST_COMPLETED)
        if getter in done:
            return getter.result()
        getter.cancel()
        if sender is not None and sender in done:
            if sender.exception() is not None:
                raise sender.exception()
            return _SENDER_DONE
        return _TIMEOUT

    def _deaf(self, t):
        """The server reports voice activity, yet heard nothing of loud mic audio."""
        if t.get('retried') or not self._vad_supported or t.get('speech_detected'):
            return False
        if t['heard'] or t['interim'] or t.get('got_output') or t['tts']:
            return False
        loud = t.get('loud_s', 0.0)
        return loud >= (DEAF_MIN_LOUD_S if t.get('input_ended') else DEAF_LOUD_S)

    async def _converse(self, t, link, captions):
        """Consume server messages until the answer is complete. Returns True
        when the server ended the turn cleanly and the session may be reused,
        False when it did not, or 'deaf' when the session must be replaced."""
        progress = time.monotonic()
        while True:
            captions.tick()
            budget = self._budget(t)
            wait = budget - (time.monotonic() - progress)
            checking = not t.get('retried') and self._vad_supported and not t.get('speech_detected')
            item = await self._next(t, link, max(0.0, min(wait, DEAF_TICK_S) if checking else wait))
            if item is _SENDER_DONE:
                progress = time.monotonic()
                continue
            if item is _TIMEOUT:
                if self._deaf(t):
                    return 'deaf'
                if time.monotonic() - progress < self._budget(t):
                    continue
                if t.get('phase') == 'after_interrupt':
                    t['outcome'] = 'interrupted'
                    return True   # the server already completed the interrupted turn
                t['outcome'] = 'stalled' if t['tts'] else 'no_reply'
                # Nothing heard and nothing generated: the session holds no pending answer.
                return not (t['tts'] or t.get('got_output') or t['heard'] or t['interim'] or t.get('speech_detected'))
            if item is _CLOSED:
                if t['tts']:
                    t['outcome'] = 'closed_mid_reply'
                    return False
                raise ConnectionError('live session closed')
            progress = time.monotonic()
            activity = item.voice_activity
            signal = item.voice_activity_detection_signal
            if activity is not None or signal is not None:
                self._vad_supported = True
                kind = str(getattr(activity.voice_activity_type, 'value', '')) if activity is not None else \
                    str(getattr(signal.vad_signal_type, 'value', ''))
                if 'START' in kind or kind.endswith('SOS'):
                    t['speech_detected'] = True
                elif 'END' in kind or kind.endswith('EOS'):
                    t['speech_end_at'] = progress
            if item.tool_call_cancellation and item.tool_call_cancellation.ids:
                t['cancelled_calls'].update(item.tool_call_cancellation.ids)
            if item.tool_call:
                await self._run_tools(t, link, item.tool_call, captions)
                progress = time.monotonic()   # a slow tool is not a silent server
            content = item.server_content
            if content is None:
                continue
            if content.interim_input_transcription and content.interim_input_transcription.text:
                t['interim'] = content.interim_input_transcription.text
                captions.update('partial_heard', t['heard'] + t['interim'])
            if content.input_transcription and content.input_transcription.text:
                t['heard'] += content.input_transcription.text
                t['interim'] = ''
                captions.update('partial_heard', t['heard'])
            if content.output_transcription and content.output_transcription.text:
                t['got_output'] = True
                t['reply'] += content.output_transcription.text
                captions.update('partial_reply', t['reply'])
            if content.interrupted:
                self._interrupted(t)
            if content.model_turn and content.model_turn.parts:
                for part in content.model_turn.parts:
                    blob = part.inline_data
                    if blob is not None and blob.data:
                        self._reply_audio(t, blob, captions)
            if self._complete(content):
                outcome = self._turn_outcome(t, content)
                if outcome is not None:
                    t['outcome'] = outcome
                    captions.flush()
                    return True

    @staticmethod
    def _complete(content):
        status = content.interaction_status
        if status is not None:
            value = str(getattr(status, 'value', status))
            if value != 'INTERACTION_STATUS_UNSPECIFIED':
                return value == 'IDLE'
        return bool(content.turn_complete)

    def _turn_outcome(self, t, content):
        """Decide whether a completed server turn ends our turn (None: keep going)."""
        reason = content.turn_complete_reason
        reason = str(getattr(reason, 'value', reason)) if reason is not None else ''
        if t['interrupted'] and not t.get('audio_after_interrupt'):
            t['phase'] = 'after_interrupt'   # the answer to the interruption may follow
            return None
        if t['tts']:
            return 'replied'
        if reason in ('MALFORMED_FUNCTION_CALL', 'RESPONSE_REJECTED', 'PROHIBITED_INPUT_CONTENT'):
            t['stats']['turn_complete_reason'] = reason
            return 'no_reply'
        if t.get('input_ended') and not t['tool_log']:
            return 'no_reply'
        if content.waiting_for_input and t.get('input_ended'):
            return 'no_reply'
        return None  # e.g. an empty VAD turn while the owner is still speaking

    def _interrupted(self, t):
        """Barge-in: stop the queued reply now and tell the UI."""
        player = t.get('player')
        dropped = player.clear() if player else 0
        t['interrupted'] += 1
        t['audio_after_interrupt'] = False
        t['stats']['interrupted_dropped_bytes'] = t['stats'].get('interrupted_dropped_bytes', 0) + dropped
        self._say('interrupted', 'توقفتُ لأسمعك')
        self._say('thinking', 'أفكر في طلبك…')

    def _reply_audio(self, t, blob, captions):
        now = time.monotonic()
        t['got_output'] = True
        if not t['tts']:
            t['tts'] = True
            t['first_audio_at'] = now
            t['last_input_before_audio'] = t.get('last_input_at')
            captions.flush('partial_heard')
            self.event('STT_END', {'text': t['heard']})
            self.event('TTS_START', {'text': t['reply']})
            self.event('TTS_STREAM_START')
        if t['interrupted']:
            t['audio_after_interrupt'] = True
        if t.get('phase') != 'speaking':
            t['phase'] = 'speaking'
            self._say('speaking', 'ميرا ترد…')
        rate = _mime_rate(blob.mime_type)
        resampler = t.get('resampler')
        if resampler is None or resampler.in_rate != rate:
            resampler = t['resampler'] = Resampler(rate, ECHO_RATE)
        t['player'].push(resampler.process(blob.data))

    async def _run_tools(self, t, link, tool_call, captions):
        captions.flush()
        t['got_output'] = True
        t['phase'] = 'tool'
        self._say('executing', 'أنفّذ الطلب…')
        allowed = frozenset(self.allowed_tools) if self.allowed_tools is not None else None
        ctx = tools.ToolContext(emit=self._say, device_control=self.device_command,
                                on_long_task=lambda: self.event('STT_END', {'text': t['heard']}),
                                allowed_tools=allowed, request_confirmation=self.request_confirmation)
        started = time.monotonic()
        replies = []
        for call in tool_call.function_calls or []:
            if call.id and call.id in t['cancelled_calls']:
                continue
            result = await tools.run_tool(call.name, dict(call.args or {}), ctx)
            t['tool_log'].append({'name': call.name, 'status': result['status']})
            replies.append(types.FunctionResponse(id=call.id, name=call.name, response=result))
        t['stats']['tool_ms'] = t['stats'].get('tool_ms', 0) + int((time.monotonic() - started) * 1000)
        if replies:
            await link.session.send_tool_response(function_responses=replies)
        t['phase'] = 'responding'
        self._say('thinking', 'أتحقق من النتيجة…')

    async def _drain(self, t, link):
        """Play out the reply; keep late transcripts that arrive meanwhile."""
        player = t['player']
        player.finish()
        task = t['player_task']
        deadline = time.monotonic() + player.remaining_s() + 5
        while not task.done():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                task.cancel()
                break
            getter = asyncio.ensure_future(link.inbox.get())
            done, _ = await asyncio.wait({getter, task}, timeout=remaining, return_when=asyncio.FIRST_COMPLETED)
            if getter not in done:
                getter.cancel()
                continue
            item = getter.result()
            if item is _CLOSED:
                link.closed = True
                continue
            content = getattr(item, 'server_content', None)
            if content is None:
                if getattr(item, 'tool_call', None):
                    link.dirty = True
                continue
            if content.input_transcription and content.input_transcription.text:
                t['heard'] += content.input_transcription.text
            if content.output_transcription and content.output_transcription.text:
                t['reply'] += content.output_transcription.text
            if content.model_turn:
                link.dirty = True   # output after completion belongs to no turn
        if task.done() and not task.cancelled() and task.exception() is not None:
            raise task.exception()
        captions = t.get('captions')
        if captions is not None:
            captions.flush()

    def _finish_stats(self, t):
        now = time.monotonic()
        player = t.get('player')
        if player is not None:
            t['out'] = player.sent
        # One spoken turn is one conversation entry.
        if t['heard'].strip():
            self._say('heard', t['heard'].strip())
        if t['reply'].strip():
            self._say('reply', t['reply'].strip())
        first = t.get('first_audio_at')
        first_ms = since_start = None
        first_ref = None
        if first:
            # From the end of the owner's speech: the server's VAD end-of-activity
            # when reported, else the moment the mic closed, else the last mic chunk.
            for first_ref, reference in (('vad_end', t.get('speech_end_at')), ('mic_closed', t.get('input_end_at')),
                                         ('last_audio', t.get('last_input_before_audio'))):
                if reference and reference <= first:
                    break
            else:
                first_ref, reference = 'turn_start', t['started']
            first_ms = int((first - reference) * 1000)
            since_start = int((first - t['started']) * 1000)
        link = t.get('link')
        stats = {'microphone_bytes': t['input'], 'microphone_peak': t['peak'], 'reply_bytes': t['out'],
                 'elapsed_s': round(now - t['started'], 2), 'input_source': t['input_source'],
                 'heard': t['heard'], 'reply': t['reply'], 'error': t.get('error'),
                 'outcome': t.get('outcome'), 'session': t.get('session'),
                 'session_features': ('advanced' if link.advanced else 'plain') if link is not None else None,
                 'connect_ms': t['stats'].get('connect_ms'), 'first_audio_ms': first_ms,
                 'first_audio_ref': first_ref,
                 'first_audio_since_start_ms': since_start, 'turn_ms': int((now - t['started']) * 1000),
                 'tool_ms': t['stats'].get('tool_ms', 0), 'tools': t['tool_log'],
                 'interrupted': t['interrupted'],
                 'playback_underruns': player.underruns if player is not None else 0,
                 'reply_audio_s': round(t['out'] / (ECHO_RATE * 2), 2)}
        for key in ('ping_ms', 'turn_complete_reason', 'interrupted_dropped_bytes', 'deaf_retry'):
            if key in t['stats']:
                stats[key] = t['stats'][key]
        if t.get('outcome') == 'no_reply':
            stats['notice'] = ('فهمت كلامك لكن لم يصل رد؛ أعد المحاولة' if t['heard'].strip()
                               else 'لم أسمع سؤالاً واضحاً')
        elif t.get('outcome') in ('stalled', 'closed_mid_reply'):
            stats['notice'] = 'انقطع الرد قبل أن يكتمل'
        self.last_stats = stats
        self._say('stats', json.dumps(stats, ensure_ascii=False))
