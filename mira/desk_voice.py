"""Talk to Mira at the computer itself when no Echo is paired: this PC's microphone and speakers.

The same Gemini Live conversation as the Echo path (`live_voice.LiveVoice`, same persona, tools,
captions and owner cards), with this computer standing in for the satellite:

* input  — `pw-record` at 16 kHz mono; a turn ends after the owner stops talking (energy
  endpointing, the same rule as the PC-wake capture) or after MAX_TURN_S;
* output — Mira's reply, already resampled to 16 kHz by LiveVoice, is streamed to `pw-play`.

Half duplex on purpose: without echo cancellation the microphone would hear Mira's own voice, so
microphone audio is dropped from the moment she starts to answer. Nothing is recorded or kept.
"""
import asyncio
import subprocess
import threading
import time

from PySide6.QtCore import QObject, Signal

RATE = 16000
CHUNK = 3200                 # 100 ms of 16-bit mono
MAX_TURN_S = 15.0
START_GRACE_S = 6.0          # time to begin speaking after pressing Talk
RECORD = ['pw-record', '--rate', str(RATE), '--channels', '1', '--format', 's16', '-']
PLAY = ['pw-play', '--rate', str(RATE), '--channels', '1', '--format', 's16', '-']


class DeskApi:
    """The slice of the Echo's API that LiveVoice uses, answered by this computer."""
    is_connected = True

    def __init__(self):
        self.player = None
        self._lock = threading.Lock()

    def send_voice_assistant_event(self, kind, data):
        pass                  # the Echo's ring and chimes; the window shows the state instead

    def send_voice_assistant_audio(self, block):
        with self._lock:
            if self.player is None or self.player.poll() is not None:
                try:
                    self.player = subprocess.Popen(PLAY, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                                   stderr=subprocess.DEVNULL)
                except OSError:
                    self.player = None
                    return
            try:
                self.player.stdin.write(block)
                self.player.stdin.flush()
            except (BrokenPipeError, OSError, ValueError):
                self.player = None

    def close(self):
        with self._lock:
            player, self.player = self.player, None
        if player is not None:
            try:
                player.stdin.close()
            except OSError:
                pass
            player.terminate()


def _rms(data):
    import array
    samples = array.array('h')
    samples.frombytes(data[:len(data) - len(data) % 2])
    if not samples:
        return 0.0
    return (sum(s * s for s in samples) / len(samples)) ** 0.5


class DeskVoice(QObject):
    """One Live conversation at a time from this computer's microphone; emits LiveVoice's events."""
    voice_state = Signal(str, str)

    def __init__(self, voice_name='Aoede', parent=None):
        super().__init__(parent)
        self.api = DeskApi()
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run, name='mira-desk-voice', daemon=True)
        self.voice = None
        self.voice_name = voice_name
        self.lang, self.city, self.request_confirmation = 'ar', None, None
        self._mic = None
        self.thread.start()

    def _run(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def _ensure_voice(self):
        if self.voice is None:
            from live_voice import LiveVoice
            self.voice = LiveVoice(self.api, {}, self.voice_state.emit, self.voice_name)
            self.voice.enabled = True
            self.voice.mic_gain = 1.0
        self.voice.lang, self.voice.city = self.lang, self.city
        self.voice.request_confirmation = self.request_confirmation
        self.voice.voice_name = self.voice_name
        return self.voice

    def talk(self):
        asyncio.run_coroutine_threadsafe(self._talk(), self.loop)

    def stop(self):
        async def work():
            if self._mic is not None and not self._mic.done():
                self._mic.cancel()
            if self.voice is not None:
                await self.voice.stop(True)
        return asyncio.run_coroutine_threadsafe(work(), self.loop)

    def shutdown(self):
        try:
            self.stop().result(timeout=2)     # finish the stop before the loop goes away
        except Exception:
            pass
        self.api.close()
        self.loop.call_soon_threadsafe(self.loop.stop)

    async def _talk(self):
        voice = self._ensure_voice()
        if voice.turn is not None and not voice.turn.get('done'):
            return
        port = await voice.start()
        if port is None:
            return
        self._mic = asyncio.create_task(self._listen(voice, voice.turn))

    async def _listen(self, voice, turn):
        """Microphone → Live until the owner stops talking; then hand the turn to the model."""
        try:
            process = await asyncio.create_subprocess_exec(*RECORD, stdout=asyncio.subprocess.PIPE,
                                                           stderr=asyncio.subprocess.DEVNULL)
        except OSError:
            self.voice_state.emit('error', 'تعذّر فتح ميكروفون الكمبيوتر')
            await voice.stop(True)
            return
        started = time.monotonic()
        noise, voiced, quiet = 90.0, 0, 0
        try:
            while voice.turn is turn and not turn.get('done') and not turn.get('tts'):
                elapsed = time.monotonic() - started
                if elapsed > MAX_TURN_S or (voiced == 0 and elapsed > START_GRACE_S):
                    break
                try:
                    data = await asyncio.wait_for(process.stdout.readexactly(CHUNK), 2)
                except (asyncio.IncompleteReadError, asyncio.TimeoutError):
                    break
                level = _rms(data)
                speaking = level > max(85.0, noise * 1.6)
                if not speaking and voiced == 0:
                    noise = .98 * noise + .02 * level
                await voice.audio(data)
                if speaking:
                    voiced, quiet = voiced + 1, 0
                elif voiced:
                    quiet += 1
                if voiced >= 2 and quiet >= 10:     # a second of quiet after speech
                    break
        finally:
            if process.returncode is None:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), 2)
                except asyncio.TimeoutError:
                    process.kill()
        if voice.turn is turn and not turn.get('done'):
            if voiced == 0:
                await voice.stop(True)               # nothing was said: end quietly
            else:
                await voice.stop(False)
