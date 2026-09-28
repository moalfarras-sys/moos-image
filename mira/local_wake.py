"""Local, wake-word-only microphone listener for Mira.

Audio stays on this computer. Only a matched wake event is sent to the desktop
app; no transcription, recording, or room audio is retained or uploaded here.
The conversational microphone and speaker remain the paired Echo.
"""
import argparse
import collections
import os
import json
import re
import signal
import socket
import subprocess
import time
from pathlib import Path

import numpy as np
from faster_whisper import WhisperModel

RATE = 16000
FRAME_BYTES = RATE * 2 // 10
ALIASES = {'ميرا', 'ميره', 'ميرة', 'ميرى', 'مير', 'ميا', 'ميارا',
           'ميري', 'mira', 'myra', 'meera'}
PREFIXES = {'يا', 'هاي', 'هي', 'hey', 'hi'}


def diagnostic(uid, **state):
    """Coarse health counters only, never audio or recognized words."""
    root = Path(f'/run/user/{uid}')
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


def is_wake(text):
    """Use a word boundary: similar words inside ordinary speech must not wake."""
    normalized = re.sub(r'[\u064b-\u065f\u0670]', '', text.lower())
    normalized = normalized.replace('أ', 'ا').replace('إ', 'ا').replace('آ', 'ا')
    normalized = re.sub(r'[^\u0621-\u064a\w]+', ' ', normalized)
    words = normalized.split()
    if not words:
        return False
    return any(word in ALIASES for word in words)


def transcribe_wake(model, pcm):
    samples = np.frombuffer(pcm, dtype='<i2').astype(np.float32) / 32768.0
    level = float(np.sqrt(np.mean(samples * samples)))
    if level < .001:
        return False
    samples = np.clip(samples * min(20.0, .06 / level), -1, 1)
    segments, _ = model.transcribe(samples, language='ar', beam_size=3,
                                   condition_on_previous_text=False,
                                   initial_prompt='ميرا، يا ميرا، هاي ميرا، ميرا ميرا.',
                                   vad_filter=False)
    accepted = [s.text for s in segments
                if s.no_speech_prob < 0.5 and s.avg_logprob > -1.2]
    if is_wake(' '.join(accepted)):
        return True
    # A bilingual owner may say the English form; retry plausible speech only.
    if accepted:
        segments, _ = model.transcribe(samples, beam_size=2,
                                       condition_on_previous_text=False,
                                       vad_filter=False)
        accepted = [s.text for s in segments
                    if s.no_speech_prob < 0.35 and s.avg_logprob > -1.0]
    return is_wake(' '.join(accepted))


def send_wake(uid):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(1)
        client.connect(f'/tmp/mo-dot-desktop-{uid}')
        client.sendall(b'wake')


def frames(stream):
    while True:
        frame = stream.read(FRAME_BYTES)
        if len(frame) != FRAME_BYTES:
            break
        yield frame


def listen(args, model):
    command = ['parec', '--record', '--raw', '--rate=16000', '--format=s16le',
               '--channels=1', '--device='+args.source,
               '--client-name=Mira Local Wake']
    while os.getppid() == args.parent_pid:
        recorder = subprocess.Popen(command, stdout=subprocess.PIPE,
                                    stderr=subprocess.DEVNULL, bufsize=FRAME_BYTES * 4)
        diagnostic(args.uid, state='capturing', frames=0, last_result='')
        prior = collections.deque(maxlen=4)
        speech = []
        voiced_frames = 0
        quiet = 0
        noise = 100.0
        last_wake = 0.0
        frame_count = 0
        peak_level = 0
        try:
            for frame in frames(recorder.stdout):
                if os.getppid() != args.parent_pid:
                    return
                samples = np.frombuffer(frame, dtype='<i2').astype(np.float32)
                level = float(np.sqrt(np.mean(samples * samples)))
                frame_count += 1
                peak_level = max(peak_level,round(level))
                if frame_count % 30 == 0:
                    diagnostic(args.uid,state='capturing',frames=frame_count,
                               peak_rms=peak_level,noise_rms=round(noise))
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
                if 0.35 <= duration <= 3.7 and voiced_frames >= 2 and time.monotonic() - last_wake > 12:
                    if transcribe_wake(model, b''.join(speech)):
                        try:
                            send_wake(args.uid)
                            last_wake = time.monotonic()
                            diagnostic(args.uid,state='matched',last_result='wake_match',
                                       last_match_at=round(time.time()))
                        except (OSError, TimeoutError):
                            diagnostic(args.uid,state='socket_failed',last_result='socket_failed')
                    else:
                        diagnostic(args.uid,state='capturing',last_result='not_matched')
                speech = []
                voiced_frames = 0
                prior.clear()
        finally:
            recorder.terminate()
            try:
                recorder.wait(timeout=1)
            except subprocess.TimeoutExpired:
                recorder.kill()
                recorder.wait()
            diagnostic(args.uid,state='reconnecting',last_result='microphone_disconnected')
        time.sleep(2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--source', required=True)
    parser.add_argument('--parent-pid', type=int, required=True)
    parser.add_argument('--uid', type=int, required=True)
    args = parser.parse_args()
    signal.signal(signal.SIGTERM, lambda *_: exit(0))
    model = WhisperModel(str(args.model), device='cpu', compute_type='int8',
                         cpu_threads=2, num_workers=1)
    listen(args, model)


if __name__ == '__main__':
    main()
