"""Local, wake-word-only microphone listener for Mira.

Audio stays on this computer. Only a matched wake event is sent to the desktop
app; no transcription, recording, or room audio is retained or uploaded here.
The conversational microphone and speaker remain the paired Echo.
"""
import argparse
import collections
import os
import json
import queue
import re
import signal
import socket
import subprocess
import threading
import time
from pathlib import Path

import numpy as np
from faster_whisper import WhisperModel
from faster_whisper.vad import VadOptions, get_speech_timestamps
from capture_policy import SourceWatch

RATE = 16000
FRAME_BYTES = RATE * 2 // 10
ALIASES = {'ميرا', 'ميره', 'ميرة', 'ميرى', 'مير', 'ميا', 'ميارا',
           'ميري', 'mira', 'myra', 'meera'}
PREFIXES = {'يا', 'هاي', 'هي', 'hey', 'hi'}
VAD = VadOptions(threshold=.35, min_speech_duration_ms=120,
                 min_silence_duration_ms=250, speech_pad_ms=100)
_health_lock = threading.Lock()


def runtime_root(uid):
    root = Path(os.environ.get('XDG_RUNTIME_DIR', f'/run/user/{uid}'))
    stat = root.stat()
    if not root.is_absolute() or not root.is_dir() or stat.st_uid != uid or stat.st_mode & 0o077:
        raise ValueError('private runtime directory required')
    return root


def diagnostic(uid, **state):
    with _health_lock:
        _diagnostic(uid, **state)


def _diagnostic(uid, **state):
    """Coarse health counters only, never audio or recognized words."""
    root = runtime_root(uid)
    if not root.exists():
        return
    path = root / 'mira-wake-health.json'
    try:
        current = json.loads(path.read_text()) if path.exists() else {}
        current.update(state)
        current['at'] = round(time.time())
        temp = root / 'mira-wake-health.tmp'
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w') as output:
            json.dump(current, output)
        temp.replace(path)
    except OSError:
        pass


def _one_edit_away(word, target='ميرا'):
    """Allow a single ASR slip on Mira, but never a short common word."""
    if len(word) < 4 or abs(len(word) - len(target)) > 1:
        return False
    if len(word) == len(target):
        return sum(a != b for a, b in zip(word, target)) == 1
    longer, shorter = (word, target) if len(word) > len(target) else (target, word)
    return any(longer[:i] + longer[i + 1:] == shorter for i in range(len(longer)))


def is_wake(text):
    """Match an isolated name, including one recognition error in «ميرا»."""
    normalized = re.sub(r'[\u064b-\u065f\u0670]', '', text.lower())
    normalized = normalized.replace('أ', 'ا').replace('إ', 'ا').replace('آ', 'ا')
    normalized = re.sub(r'[^\u0621-\u064a\w]+', ' ', normalized)
    words = normalized.split()
    if not words:
        return False
    return any(word in ALIASES or
               (i > 0 and words[i - 1] in PREFIXES and _one_edit_away(word))
               for i, word in enumerate(words))


def transcribe_wake(model, pcm):
    samples = np.frombuffer(pcm, dtype='<i2').astype(np.float32) / 32768.0
    level = float(np.sqrt(np.mean(samples * samples)))
    if level < .001:
        return False
    samples = np.clip(samples * min(20.0, .06 / level), -1, 1)
    # Cheap local speech filter before running the far heavier Whisper decoder.
    # The simple energy gate also fires on fans, clicks and music.
    if not get_speech_timestamps(samples, VAD):
        return False
    # Never feed the answer to Whisper as a prompt/hotword: on this short
    # gadget stream that caused repeated false wakes on unrelated room speech.
    for language, beam in (('ar', 4), (None, 3)):
        segments, _ = model.transcribe(
            samples, language=language, beam_size=beam,
            condition_on_previous_text=False,
            vad_filter=False)
        accepted = [s.text for s in segments
                    if s.no_speech_prob < 0.65 and s.avg_logprob > -1.2]
        if is_wake(' '.join(accepted)):
            return True
    return False


def send_wake(uid):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(1)
        client.connect(f'/tmp/mo-dot-desktop-{uid}')
        client.sendall(b'wake')


def audio_path(uid):
    return runtime_root(uid) / 'mira-pcm.sock'


def frames(stream):
    while True:
        frame = stream.read(FRAME_BYTES)
        if len(frame) != FRAME_BYTES:
            break
        yield frame


def offer_speech(pending, pcm, generation=None):
    """Keep at most the newest two phrases; stale room audio cannot wake later."""
    item = (time.monotonic(), pcm, generation)
    try:
        pending.put_nowait(item)
    except queue.Full:
        try:
            pending.get_nowait()
        except queue.Empty:
            pass
        pending.put_nowait(item)


def recognize_loop(args, model, pending, stop_event, watch):
    last_wake = 0.0
    while not stop_event.is_set():
        try:
            captured_at, pcm, generation = pending.get(timeout=.5)
        except queue.Empty:
            continue
        if (not watch.permits(generation) or time.monotonic() - captured_at > 4
                or time.monotonic() - last_wake < 12):
            continue
        try:
            matched = transcribe_wake(model, pcm)
        except Exception:
            if watch.permits(generation):
                diagnostic(args.uid,state='recognition_failed',last_result='recognition_failed')
            continue
        if not watch.permits(generation):
            continue
        if not matched:
            diagnostic(args.uid,last_result='not_matched')
            continue
        try:
            send_wake(args.uid)
            last_wake = time.monotonic()
            diagnostic(args.uid,state='matched',last_result='wake_match',
                       last_match_at=round(time.time()))
        except (OSError, TimeoutError):
            diagnostic(args.uid,state='socket_failed',last_result='socket_failed')


def listen(args, model):
    command = ['parec', '--record', '--raw', '--rate=16000', '--format=s16le',
               '--channels=1', '--device='+args.source,
               '--latency-msec=100', '--process-time-msec=20',
               '--client-name=Mira Local Wake']
    path = audio_path(args.uid)
    if path.exists():
        path.unlink()
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    pending = queue.Queue(maxsize=2)
    stop_event = threading.Event()
    def source_changed(state):
        # A stale phrase must not survive a mute/disconnect/reconnect even if
        # its expensive recognition would finish after the source returns.
        while True:
            try:
                pending.get_nowait()
            except queue.Empty:
                break
        diagnostic(args.uid, state=state.reason, frames=0, frames_per_second=0,
                   last_result='', last_match_at=0)
    watch = SourceWatch(args.source, source_changed)
    worker = threading.Thread(target=recognize_loop,
                              args=(args, model, pending, stop_event, watch), daemon=True)
    worker.start()
    try:
        server.bind(str(path))
        os.chmod(path, 0o600)
        server.listen(1)
        server.setblocking(False)
        diagnostic(args.uid, state='unknown', frames=0, frames_per_second=0,
                   last_result='', last_match_at=0)
        watch.start()
        while os.getppid() == args.parent_pid:
            if watch.wait_ready():
                _capture_loop(args, command, server, pending, watch)
                stop_event.wait(.2)
    finally:
        stop_event.set()
        watch.close()
        worker.join(timeout=2)
        server.close()
        path.unlink(missing_ok=True)


def _capture_loop(args, command, server, pending, watch):
        generation, state = watch.snapshot()
        if not state.allowed:
            return
        recorder = subprocess.Popen(command, stdout=subprocess.PIPE,
                                    stderr=subprocess.DEVNULL, bufsize=FRAME_BYTES * 4)
        prior = collections.deque(maxlen=4)
        speech = []
        voiced_frames = 0
        quiet = 0
        noise = 100.0
        frame_count = 0
        peak_level = 0
        audio_peer = None
        measured_at = time.monotonic()
        measured_frames = 0
        try:
            if not watch.attach_recorder(recorder, generation):
                return
            diagnostic(args.uid, state='capturing', frames=0, last_result='')
            for frame in frames(recorder.stdout):
                if os.getppid() != args.parent_pid or not watch.permits(generation):
                    return
                samples = np.frombuffer(frame, dtype='<i2').astype(np.float32)
                level = float(np.sqrt(np.mean(samples * samples)))
                frame_count += 1
                peak_level = max(peak_level,round(level))
                if frame_count % 30 == 0:
                    now = time.monotonic()
                    fps = round((frame_count - measured_frames) / max(.001, now - measured_at), 1)
                    measured_at, measured_frames = now, frame_count
                    diagnostic(args.uid,state='streaming' if audio_peer else 'capturing',frames=frame_count,
                               peak_rms=peak_level,noise_rms=round(noise),frames_per_second=fps)
                if audio_peer is None:
                    try:
                        audio_peer, _ = server.accept()
                        audio_peer.settimeout(.2)
                        speech.clear();prior.clear();voiced_frames=quiet=0
                        diagnostic(args.uid,state='streaming',last_result='')
                    except BlockingIOError:
                        pass
                if audio_peer is not None:
                    try:
                        audio_peer.sendall(frame)
                    except (OSError, TimeoutError):
                        audio_peer.close();audio_peer=None
                        speech.clear();prior.clear();voiced_frames=quiet=0
                        diagnostic(args.uid,state='capturing',last_result='audio_handoff_ended')
                    continue
                speaking = level > max(85.0, noise * 1.6)
                if not speaking and not speech:
                    noise = 0.98 * noise + 0.02 * level
                if not speech:
                    if speaking:
                        speech = list(prior) + [frame]
                        voiced_frames = 1
                        quiet = 0
                    else:
                        prior.append(frame)
                    continue
                speech.append(frame)
                if speaking:
                    voiced_frames += 1
                quiet = 0 if speaking else quiet + 1
                if quiet < 6 and len(speech) < 36:
                    continue
                duration = len(speech) / 10
                diagnostic(args.uid,state='recognizing',segment_seconds=round(duration,1),
                           peak_rms=peak_level)
                if 0.35 <= duration <= 3.7 and voiced_frames >= 2:
                    offer_speech(pending, b''.join(speech), generation)
                speech = []
                voiced_frames = 0
                prior.clear()
        finally:
            watch.detach_recorder(recorder)
            if audio_peer:
                audio_peer.close()
            recorder.terminate()
            try:
                recorder.wait(timeout=1)
            except subprocess.TimeoutExpired:
                recorder.kill()
                recorder.wait()
            recorder.stdout.close()
            _, state = watch.snapshot()
            diagnostic(args.uid, state='reconnecting' if state.allowed else state.reason,
                       frames_per_second=0, last_result='microphone_disconnected')


class LazyWhisperModel:
    """A muted/quiet listener does not load the wake model into RAM."""
    def __init__(self, path):
        self.path = path
        self.model = None

    def transcribe(self, *args, **kwargs):
        if self.model is None:
            self.model = WhisperModel(str(self.path), device='cpu', compute_type='int8',
                                      cpu_threads=2, num_workers=1)
        return self.model.transcribe(*args, **kwargs)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--source', required=True)
    parser.add_argument('--parent-pid', type=int, required=True)
    parser.add_argument('--uid', type=int, required=True)
    args = parser.parse_args()
    signal.signal(signal.SIGTERM, lambda *_: exit(0))
    model = LazyWhisperModel(args.model)
    listen(args, model)


if __name__ == '__main__':
    main()
