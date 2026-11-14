"""Talk to Mira at the computer itself when Echo is unavailable: this PC's microphone and speakers.

The same Gemini Live conversation as the Echo path (`live_voice.LiveVoice`, same persona, tools,
captions and owner cards), with this computer standing in for the satellite:

* input  — the existing `parec` capture owner at 16 kHz mono; a turn ends after the owner stops talking (energy
  endpointing, the same rule as the PC-wake capture) or after MAX_TURN_S;
* output — Mira's reply, already resampled to 16 kHz by LiveVoice, is streamed to `pw-play`.

Half duplex on purpose: without echo cancellation the microphone would hear Mira's own voice, so
microphone audio is dropped from the moment she starts to answer. Nothing is recorded or kept.
"""
import asyncio
import array
import math
import os
import json
import select
import subprocess
import threading
import time

from PySide6.QtCore import QObject, Signal
from capture_policy import SourceWatch

RATE = 16000
CHUNK = 3200                 # 100 ms of 16-bit mono
MAX_TURN_S = 15.0
START_GRACE_S = 6.0          # time to begin speaking after pressing Talk
PLAY = ['pw-play', '--raw', '--rate', str(RATE), '--channels', '1', '--format', 's16', '-']
DEFAULT_SOURCE = '@DEFAULT_SOURCE@'
PROBE_MAX_S = 5.0
SOURCE_READY_S = 4.0
READ_TIMEOUT_S = 2.0
WRITE_TIMEOUT_S = .5


class CaptureError(Exception):
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def resolve_source(source):
    """Resolve the desktop preference once. A turn never follows a later default."""
    if not isinstance(source, str) or not source or len(source) > 512:
        raise CaptureError('invalid_source')
    if source == DEFAULT_SOURCE:
        try:
            source = subprocess.run(['pactl', 'get-default-source'], check=True,
                                    capture_output=True, text=True, timeout=3,
                                    env=os.environ | {'LC_ALL': 'C.UTF-8'}).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            raise CaptureError('unknown') from None
    if not source or len(source) > 512 or any(ord(c) <= 32 or ord(c) == 127 for c in source):
        raise CaptureError('invalid_source')
    return source


def record_command(source, seconds):
    # The native target and these properties together forbid moving this stream
    # to another microphone when the selected device/default disappears.
    # pw-cat1.6.11's sample-limit exit never reaches its playback-only drained
    # success path. Do not turn that generic exit1 into success. Reuse the
    # native wake recorder and finish it explicitly after our own byte budget.
    return ['parec', '--record', '--raw', '--rate='+str(RATE), '--format=s16le', '--channels=1',
            '--device='+source, '--latency-msec=100', '--process-time-msec=20',
            '--client-name=Mira microphone', '--property=node.dont-fallback=true',
            '--property=node.dont-reconnect=true']


class _RecorderLease:
    """SourceWatch may revoke a recorder from its subscription thread."""
    def __init__(self, process, loop):
        self.process, self.loop = process, loop

    def terminate(self):
        def stop():
            if self.process.returncode is None:
                try:
                    self.process.terminate()
                except ProcessLookupError:
                    pass
        try:
            self.loop.call_soon_threadsafe(stop)
        except RuntimeError:
            pass  # the owning loop's finally has already reaped its process


class MicrophoneCapture:
    """The one finite, RAM-only recorder shared by a voice turn and the meter."""
    def __init__(self, source=DEFAULT_SOURCE, seconds=MAX_TURN_S):
        self.requested_source = source
        self.source = source if isinstance(source, str) else ''
        self.seconds = seconds
        self.byte_limit, self.received = int(seconds * RATE) * 2, 0
        self.watch = self.process = self.lease = None
        self.generation = None

    async def __aenter__(self):
        try:
            self.source = await asyncio.to_thread(resolve_source, self.requested_source)
            self.watch = SourceWatch(self.source)
            self.watch.start()
            if not await asyncio.to_thread(self.watch.wait_ready, SOURCE_READY_S):
                reason = self.watch.snapshot()[1].reason
                raise CaptureError('changed' if reason == 'ready' else reason)
            self.generation, _state = self.watch.snapshot()
            self.ensure_allowed()
            self.process = await asyncio.create_subprocess_exec(
                *record_command(self.source, self.seconds), stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL)
            self.lease = _RecorderLease(self.process, asyncio.get_running_loop())
            if not self.watch.attach_recorder(self.lease, self.generation):
                self.ensure_allowed()
                raise CaptureError('changed')
            self.ensure_allowed()
            return self
        except OSError:
            await self.close()
            raise CaptureError('capture_failed') from None
        except BaseException:
            await self.close()
            raise

    def ensure_allowed(self):
        if self.watch is None or not self.watch.permits(self.generation):
            reason = self.watch.snapshot()[1].reason if self.watch is not None else 'unknown'
            raise CaptureError('changed' if reason == 'ready' else reason)

    async def read(self, size=CHUNK):
        self.ensure_allowed()
        size = min(size, self.byte_limit - self.received)
        if size <= 0:
            return b''
        try:
            data = await asyncio.wait_for(self.process.stdout.readexactly(size), READ_TIMEOUT_S)
        except asyncio.TimeoutError:
            self.ensure_allowed()
            raise CaptureError('timeout') from None
        except asyncio.IncompleteReadError as exc:
            data = exc.partial
            self.ensure_allowed()
            await self.wait_finished()
        self.ensure_allowed()
        if len(data) % 2:
            raise CaptureError('invalid_audio')
        self.received += len(data)
        return data

    async def finish(self):
        """The meter owns this stop only after receiving its exact PCM budget."""
        self.ensure_allowed()
        if self.received != self.byte_limit:
            raise CaptureError('no_data')
        if self.process.returncode is None:
            try:
                self.process.terminate()
            except ProcessLookupError:
                pass
        await self.wait_finished()  # ordinary nonzero remains a refusal

    async def wait_finished(self):
        try:
            code = await asyncio.wait_for(self.process.wait(), READ_TIMEOUT_S)
        except asyncio.TimeoutError:
            raise CaptureError('timeout') from None
        self.ensure_allowed()
        if code != 0:
            raise CaptureError('capture_failed')

    async def close(self):
        if self.watch is not None and self.lease is not None:
            self.watch.detach_recorder(self.lease)
        try:
            if self.process is not None:
                if self.process.returncode is None:
                    try:
                        self.process.terminate()
                    except ProcessLookupError:
                        pass
                    try:
                        await asyncio.wait_for(self.process.wait(), READ_TIMEOUT_S)
                    except asyncio.TimeoutError:
                        try:
                            self.process.kill()
                        except ProcessLookupError:
                            pass
                        await asyncio.wait_for(self.process.wait(), READ_TIMEOUT_S)
                else:
                    await self.process.wait()
        finally:
            if self.watch is not None:
                await asyncio.to_thread(self.watch.close)

    async def __aexit__(self, *_args):
        await self.close()


async def _probe_microphone(source, seconds):
    started = time.monotonic()
    result = {'status': 'error', 'reason': 'unknown', 'source': source if isinstance(source, str) else '', 'bytes': 0,
              'peak': 0, 'rms': 0.0, 'seconds': seconds}
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not math.isfinite(seconds) \
            or seconds <= 0 or seconds > PROBE_MAX_S or int(seconds * RATE) < 1:
        result.update(reason='invalid_duration', elapsed_ms=0)
        return result
    total_squares, samples = 0, 0
    capture = MicrophoneCapture(source, seconds)
    try:
        async with capture:
            result['source'] = capture.source
            wanted = int(seconds * RATE) * 2
            while result['bytes'] < wanted:
                data = await capture.read(min(CHUNK, wanted - result['bytes']))
                if not data:
                    raise CaptureError('no_data')
                values = array.array('h')
                values.frombytes(data)
                result['bytes'] += len(data)
                samples += len(values)
                result['peak'] = max(result['peak'], max(map(abs, values), default=0))
                total_squares += sum(value * value for value in values)
            await capture.finish()
            result.update(status='ok' if result['peak'] else 'silent',
                          reason='signal' if result['peak'] else 'no_signal')
    except CaptureError as exc:
        result.update(status='error', reason=exc.reason, source=capture.source)
    except (OSError, asyncio.TimeoutError):
        result.update(status='error', reason='cleanup_failed', source=capture.source)
    result.update(rms=round(math.sqrt(total_squares / samples), 2) if samples else 0.0,
                  elapsed_ms=round((time.monotonic() - started) * 1000))
    return result


def probe_microphone(source=DEFAULT_SOURCE, seconds=3):
    """Explicit manual meter: no disk, recognition, cloud, credentials or mute changes."""
    return asyncio.run(_probe_microphone(source, seconds))


class DeskApi:
    """The slice of the Echo's API that LiveVoice uses, answered by this computer."""
    is_connected = True

    def __init__(self):
        self.player = None
        self._lock = threading.Lock()
        self.playback_error = ''
        self.bytes_written = 0

    def reset(self):
        self.playback_error = ''
        self.bytes_written = 0

    def send_voice_assistant_event(self, kind, data):
        pass                  # the Echo's ring and chimes; the window shows the state instead

    def send_voice_assistant_audio(self, block):
        with self._lock:
            if self.playback_error:
                raise RuntimeError('computer_playback_failed')
            if self.player is not None and self.player.poll() is not None:
                self.playback_error = 'computer_playback_failed'
                self.player.wait()
                self.player = None
                raise RuntimeError('computer_playback_failed')
            if self.player is None:
                try:
                    self.player = subprocess.Popen(PLAY, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                                   stderr=subprocess.DEVNULL, bufsize=0)
                except OSError:
                    self.player = None
                    self.playback_error = 'computer_playback_failed'
                    raise RuntimeError('computer_playback_failed') from None
            try:
                self._write(self.player, block)
                self.bytes_written += len(block)
            except (BrokenPipeError, OSError, ValueError):
                player = self.player
                self.player = None
                self.playback_error = 'computer_playback_failed'
                self._reap(player, abort=True)
                raise RuntimeError('computer_playback_failed') from None

    @staticmethod
    def _write(player, block):
        # A missing/unlinked output must not block the voice loop indefinitely
        # in a full stdin pipe. Each write is below POSIX PIPE_BUF and has one
        # owner; FileIO is unbuffered so its close cannot flush a stuck buffer.
        pending = memoryview(block)
        deadline = time.monotonic() + WRITE_TIMEOUT_S
        while pending:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([], [player.stdin], [], remaining)[1]:
                raise TimeoutError('computer_playback_failed')
            count = player.stdin.write(pending[:512])
            if not count:
                raise BrokenPipeError('computer_playback_failed')
            pending = pending[count:]

    @staticmethod
    def _reap(player, *, abort):
        try:
            player.stdin.close()
        except (OSError, ValueError):
            pass
        if abort and player.poll() is None:
            try:
                player.terminate()
            except ProcessLookupError:
                pass
        try:
            code = player.wait(timeout=2)
        except subprocess.TimeoutExpired:
            player.kill()
            player.wait(timeout=2)
            raise RuntimeError('computer_playback_failed') from None
        if not abort and code != 0:
            raise RuntimeError('computer_playback_failed')

    def finish(self):
        with self._lock:
            if self.playback_error:
                raise RuntimeError('computer_playback_failed')
            player, self.player = self.player, None
            if player is not None:
                try:
                    self._reap(player, abort=False)
                except Exception:
                    self.playback_error = 'computer_playback_failed'
                    raise

    def close(self):
        with self._lock:
            player, self.player = self.player, None
        if player is not None:
            self._reap(player, abort=True)


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

    def __init__(self, voice_name='Aoede', parent=None, *, source=DEFAULT_SOURCE):
        super().__init__(parent)
        self.api = DeskApi()
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run, name='mira-desk-voice', daemon=True)
        self.voice = None
        self.voice_name = voice_name
        self.source = source
        self.lang, self.city, self.request_confirmation = 'ar', None, None
        self._mic = None
        self._capture_failed = False
        self._terminal_pending = None
        self._starting = self._stopping = False
        self.thread.start()

    def _run(self):
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_forever()
        finally:
            pending = asyncio.all_tasks(self.loop)
            for task in pending:
                task.cancel()
            if pending:
                self.loop.run_until_complete(asyncio.wait(pending, timeout=2))
            self.loop.close()

    def _ensure_voice(self):
        if self.voice is None:
            from live_voice import LiveVoice
            self.voice = LiveVoice(self.api, {}, self._voice_event, self.voice_name)
            self.voice.enabled = True
            self.voice.mic_gain = 1.0
        self.voice.lang, self.voice.city = self.lang, self.city
        self.voice.request_confirmation = self.request_confirmation
        self.voice.voice_name = self.voice_name
        return self.voice

    def talk(self):
        try:
            return asyncio.run_coroutine_threadsafe(self._talk(), self.loop)
        except RuntimeError:
            self.voice_state.emit('error', self._message('capture_failed'))

    def _voice_event(self, kind, text):
        # LiveVoice announces ready when its task is cancelled. A failed local
        # capture retains its failure instead of becoming a successful ready.
        if kind == 'ready' and self._capture_failed:
            return
        if kind == 'ready' and not self._stopping:
            try:
                self.api.finish()  # end raw PCM and require the native playback exit
            except Exception:
                self._capture_failed = True
                kind, text = 'error', self._message('playback_failed')
        elif kind == 'error':
            try:
                self.api.close()
            except Exception:
                pass  # retain the original voice failure if cleanup also refuses
        if kind == 'stats' and self.api.playback_error:
            try:
                stats = json.loads(text)
                stats.update(error=self.api.playback_error, outcome='playback_failed',
                             reply_bytes=0, playback_bytes_written=self.api.bytes_written)
                text = json.dumps(stats)
            except (TypeError, ValueError, AttributeError):
                pass
        if kind in ('ready', 'error', 'off'):
            self._terminal_pending = (kind, text)
            self._flush_terminal()
            return
        self.voice_state.emit(kind, text)

    def _flush_terminal(self):
        if self._starting or self._stopping or (self._mic is not None and not self._mic.done()):
            return
        terminal, self._terminal_pending = self._terminal_pending, None
        if terminal is not None and not (terminal[0] == 'ready' and self._capture_failed):
            self.voice_state.emit(*terminal)

    def _message(self, reason):
        messages = {
            'muted': ('الميكروفون مكتوم؛ شغّله من إعدادات الصوت إذا أردت التحدث',
                      'The microphone is muted; enable it in Audio settings to talk'),
            'missing': ('الميكروفون المحدد غير متصل', 'The selected microphone is disconnected'),
            'unavailable': ('الميكروفون المحدد غير متاح', 'The selected microphone is unavailable'),
            'unknown': ('تعذّر التحقق من الميكروفون', 'The microphone could not be verified'),
            'changed': ('تغيّر الميكروفون أثناء الاستماع؛ أعد المحاولة',
                        'The microphone changed while listening; try again'),
            'monitor_refused': ('اختر ميكروفوناً بدلاً من صوت مكبرات الجهاز',
                                'Choose a microphone instead of speaker monitor audio'),
            'no_data': ('لم يصل صوت من الميكروفون المحدد', 'No audio arrived from the selected microphone'),
            'timeout': ('تأخرت قراءة الميكروفون؛ أعد المحاولة', 'The microphone read timed out; try again'),
            'playback_failed': ('وصل الرد لكن تعذّر تشغيله على سماعة الكمبيوتر',
                                'The reply arrived but computer playback failed'),
        }
        pair = messages.get(reason, ('تعذّر استخدام ميكروفون الكمبيوتر',
                                     'The computer microphone could not be used'))
        return pair[1 if self.lang == 'en' else 0]

    def stop(self):
        async def work():
            self._stopping = True
            try:
                mic = self._mic
                if mic is not None:
                    if not mic.done():
                        mic.cancel()
                    await asyncio.gather(mic, return_exceptions=True)
                if self.voice is not None:
                    await self.voice.stop(True)
                    task = (self.voice.turn or {}).get('task')
                    if task is not None:
                        await asyncio.wait({task}, timeout=2)
                await asyncio.to_thread(self.api.close)
                if not self._capture_failed:
                    self._terminal_pending = ('ready', 'توقفت المحادثة' if self.lang == 'ar'
                                              else 'Conversation stopped')
            except Exception:
                self._capture_failed = True
                self._terminal_pending = ('error', self._message('cleanup_failed'))
            finally:
                self._stopping = False
                self._flush_terminal()
        return asyncio.run_coroutine_threadsafe(work(), self.loop)

    def shutdown(self):
        stopped = None
        try:
            stopped = self.stop()
            stopped.result(timeout=8)     # reap capture before its loop goes away
        except Exception:
            if stopped is not None and not stopped.done():
                # Do not tear the loop out from under a recorder's finally.
                stopped.add_done_callback(lambda _future: self.loop.call_soon_threadsafe(self.loop.stop))
                return
        self.api.close()
        self.loop.call_soon_threadsafe(self.loop.stop)
        if self.thread is not threading.current_thread():
            self.thread.join(timeout=3)

    async def _talk(self):
        self._starting = True
        try:
            voice = self._ensure_voice()
            if voice.turn is not None and not voice.turn.get('done'):
                return
            prior = self._mic
            if prior is not None:
                if not prior.done():
                    prior.cancel()
                # A cloud turn may close while a local PCM read is pending.
                # Reap that selected source before a new turn can own capture.
                await asyncio.gather(prior, return_exceptions=True)
            self._terminal_pending = None
            self._capture_failed = False
            self.api.reset()
            port = await voice.start()
            if port is None:
                self.voice_state.emit('error', self._message('capture_failed'))
                return
            voice.turn['input_source'] = 'pc'
            self._mic = asyncio.create_task(self._listen(voice, voice.turn, self.source))
            self._mic.add_done_callback(self._mic_finished)
        except asyncio.CancelledError:
            raise
        except Exception:
            self._voice_event('error', self._message('capture_failed'))
        finally:
            self._starting = False
            self._flush_terminal()

    def _mic_finished(self, task):
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception:
            self._capture_failed = True
            self._terminal_pending = ('error', self._message('capture_failed'))
        self._flush_terminal()

    async def _listen(self, voice, turn, source=None):
        """Microphone → Live until the owner stops talking; then hand the turn to the model."""
        started = time.monotonic()
        noise, voiced, quiet, received = 90.0, 0, 0, 0
        try:
            async with MicrophoneCapture(source or self.source) as capture:
                if voice.turn is not turn or turn.get('done'):
                    return
                started = time.monotonic()
                self.voice_state.emit('listening', 'أستمع من ميكروفون الكمبيوتر' if self.lang == 'ar'
                                      else 'Listening through this computer microphone')
                while voice.turn is turn and not turn.get('done') and not turn.get('tts'):
                    elapsed = time.monotonic() - started
                    if elapsed > MAX_TURN_S or received >= MAX_TURN_S * RATE * 2 \
                            or (voiced == 0 and elapsed > START_GRACE_S):
                        break
                    data = await capture.read()
                    if not data:
                        raise CaptureError('no_data')
                    if voice.turn is not turn or turn.get('done') or turn.get('tts'):
                        break  # speech output may have begun while the read awaited PCM
                    level = _rms(data)
                    speaking = level > max(85.0, noise * 1.6)
                    if not speaking and voiced == 0:
                        noise = .98 * noise + .02 * level
                    capture.ensure_allowed()      # no stale chunk across mute/disconnect
                    await voice.audio(data)
                    received += len(data)
                    self.voice_state.emit('level', f'{min(1.0, level / 3000.0):.3f}')
                    if speaking:
                        voiced, quiet = voiced + 1, 0
                    elif voiced:
                        quiet += 1
                    if voiced >= 2 and quiet >= 10:     # a second of quiet after speech
                        break
        except CaptureError as exc:
            self._capture_failed = True
            await voice.stop(True)
            task = turn.get('task')
            if task is not None:
                await asyncio.wait({task}, timeout=2)
            self._voice_event('error', self._message(exc.reason))
            return
        except (OSError, asyncio.TimeoutError):
            self._capture_failed = True
            await voice.stop(True)
            self._voice_event('error', self._message('cleanup_failed'))
            return
        finally:
            self.voice_state.emit('level', '0')
        if voice.turn is turn and not turn.get('done') and not turn.get('tts'):
            if voiced == 0:
                await voice.stop(True)               # nothing was said: end quietly
            else:
                await voice.stop(False)
