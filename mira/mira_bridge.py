"""Paired Echo transport for the Mira desktop. Commands stay on its asyncio loop."""
import asyncio
import hashlib
import hmac
import json
import os
import re
import socket
import sys
import threading
import time
from pathlib import Path

from PySide6.QtCore import QObject, Signal
from aioesphomeapi import APIClient, MediaPlayerCommand


KEY = Path.home() / '.config/mo-dot/device.key'
ECHO_CONFIG = Path.home() / '.config/mo-dot/echo.json'
FIRST_ECHO = '192.168.3.83'   # the first paired Echo predates echo.json


def echo_host():
    """The paired Echo's address, or None on a computer without one (Mira then runs without voice)."""
    if os.environ.get('MIRA_ECHO_HOST'):
        return os.environ['MIRA_ECHO_HOST']
    try:
        host = json.loads(ECHO_CONFIG.read_text()).get('host')
    except (OSError, ValueError, AttributeError):
        host = None
    if isinstance(host, str) and re.fullmatch(r'[A-Za-z0-9.:-]{1,64}', host):
        return host
    return FIRST_ECHO if KEY.exists() else None


IP = echo_host()


def paired():
    return IP is not None and KEY.exists()


class Bridge(QObject):
    connected = Signal(object)
    state = Signal(object)
    error = Signal(str)
    command_state = Signal(str, str)
    voice_state = Signal(str, str)

    def __init__(self, voice_name='Aoede'):
        super().__init__()
        self.loop = asyncio.new_event_loop()
        self.api = None
        self.entities = {}
        self.online = False
        self.voice = None
        self.voice_enabled = True
        self.voice_name = voice_name
        self.lang = 'ar'       # passed to each new voice session's persona
        self.city = None
        self.request_confirmation = None   # set by the controller; handed to every voice session
        self.heartbeat_task = None
        self.thread = threading.Thread(target=self.run, daemon=True)

    def start(self):
        if not paired():
            # No Echo on this computer: Mira is typed chat plus every tool; the pill says so.
            self.error.emit('unpaired')
            return
        self.thread.start()

    def run(self):
        asyncio.set_event_loop(self.loop)
        self.loop.create_task(self.connect())
        self.loop.run_forever()

    async def connect(self):
        while True:
            try:
                self.api = APIClient(IP, 6053, noise_psk=KEY.read_text().strip(), client_info='Mira Desktop')
                await self.api.connect(login=True)
                entities, _ = await self.api.list_entities_services()
                self.entities = {entity.object_id: entity for entity in entities}
                self.online = True
                self.connected.emit(entities)
                self.api.subscribe_states(self.state.emit)
                from live_voice import LiveVoice
                self.voice = LiveVoice(self.api, self.entities, self.voice_state.emit, self.voice_name)
                self.voice.lang = self.lang
                self.voice.city = self.city
                self.voice.request_confirmation = self.request_confirmation
                # The Dot runs its own cloud client when this desktop is absent.
                # Give it the signed handoff before subscribing our pipeline.
                if await self.device_heartbeat():
                    await asyncio.sleep(.7)
                # Heartbeat for as long as this connection lives, even if the Echo's own client
                # was still booting at the first try; otherwise both would claim the voice.
                self.heartbeat_task = asyncio.create_task(self.keep_device_standby())
                if self.voice_enabled and '--capture' not in sys.argv:
                    try:
                        await self.voice.enable()
                    except Exception as exc:
                        self.voice_state.emit('error', 'تعذّر الصوت: ' + type(exc).__name__)
                while self.api.is_connected:
                    await asyncio.sleep(2)
            except Exception as exc:
                self.error.emit('تعذّر الاتصال بالجهاز: ' + type(exc).__name__)
            finally:
                self.online = False
                if self.heartbeat_task:
                    self.heartbeat_task.cancel()
                    self.heartbeat_task = None
                if self.voice:
                    try:
                        await self.voice.disable()
                    except Exception:
                        pass
                    self.voice = None
                if self.api:
                    try:
                        await self.api.disconnect()
                    except Exception:
                        pass
            self.error.emit('غير متصل — نحاول الاتصال مجدداً')
            await asyncio.sleep(5)

    async def device_heartbeat(self):
        writer = None
        try:
            stamp = int(time.time())
            signature = hmac.new(KEY.read_text().strip().encode(),
                                 f'heartbeat:{stamp}'.encode(), hashlib.sha256).hexdigest()
            reader, writer = await asyncio.wait_for(asyncio.open_connection(IP, 8765), 1.5)
            writer.write((f'POST /heartbeat HTTP/1.1\r\nHost: {IP}\r\n'
                          f'X-Mira-Time: {stamp}\r\nX-Mira-Signature: {signature}\r\n'
                          'Content-Length: 0\r\nConnection: close\r\n\r\n').encode())
            await writer.drain()
            response = await asyncio.wait_for(reader.read(256), 1.5)
            return response.startswith(b'HTTP/1.1 200')
        except (OSError, asyncio.TimeoutError):
            return False
        finally:
            if writer:
                writer.close()
                try:
                    await writer.wait_closed()
                except OSError:
                    pass

    async def keep_device_standby(self):
        while self.online:
            await self.device_heartbeat()
            await asyncio.sleep(2)

    def command(self, kind, name, value=None):
        async def work():
            try:
                if not self.online:
                    raise RuntimeError('offline')
                entity = self.entities[name]
                args = {'key': entity.key, 'device_id': entity.device_id}
                if kind == 'wake':
                    if self.voice:
                        # A PC wake keeps using that microphone for the question.
                        # Manual/Echo wake clears any unconsumed local source.
                        self.voice.next_local_source = value if isinstance(value, str) and value else None
                    self.api.button_command(**args)
                    self.command_state.emit('wake', 'sent')
                elif kind == 'number':
                    self.api.number_command(**args, state=float(value))
                elif kind == 'switch':
                    self.api.switch_command(**args, state=bool(value))
                elif kind == 'setup':
                    if name != 'setup_page':
                        raise ValueError('unsupported setup command')
                    self.api.switch_command(**args, state=True)
                    self.command_state.emit('setup', 'sent')
                elif kind == 'select':
                    self.api.select_command(**args, state=value)
                elif kind == 'volume':
                    self.api.media_player_command(**args, volume=value)
                elif kind == 'light':
                    self.api.light_command(**args, state=value, brightness=.25,
                                           rgb=(.15, .5, 1), color_mode=35)
                elif kind == 'stop':
                    self.api.media_player_command(**args, command=MediaPlayerCommand.STOP)
                elif kind in ('tone', 'announce', 'announce_local'):
                    if kind != 'tone' and not (isinstance(value, str) and re.fullmatch(r'[0-9a-f]{12}(\.16k)?\.wav', value)):
                        raise ValueError('invalid announcement')
                    if kind == 'announce_local':
                        # Already handed to the Dot's client: echod plays it from its own loopback.
                        url = f'http://127.0.0.1:8765/asset/{value}'
                    else:
                        peer = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                        try:
                            peer.connect((IP, 6053))
                            host = peer.getsockname()[0]
                        finally:
                            peer.close()
                        url = f'http://{host}:18769/' + ('tone.wav' if kind == 'tone' else 'announce/' + value)
                    # announcement=True: echod plays it as one spoken line over whatever is playing,
                    # converting to the pipeline's voice format, instead of as music (48 kHz stereo only).
                    self.api.media_player_command(**args, media_url=url, announcement=kind != 'tone')
                    self.command_state.emit(kind, 'sent')
                else:
                    raise ValueError('unknown device command')
            except Exception as exc:
                self.command_state.emit(kind, 'error:' + type(exc).__name__)
        asyncio.run_coroutine_threadsafe(work(), self.loop)

    # ── voice enrolment and wake models ──────────────────────────────
    def capture(self, path):
        """Record the next listening window locally (see LiveVoice.arm_capture) and open it."""
        async def work():
            try:
                if not self.online or not self.voice:
                    raise RuntimeError('offline')
                self.voice.arm_capture(path)
                await asyncio.sleep(0.4)  # the end-of-speech pause must land before the window opens
                entity = self.entities['wake_assistant_1']
                self.api.button_command(entity.key, device_id=entity.device_id)
                self.command_state.emit('capture', 'sent')
            except Exception as exc:
                if self.voice:
                    self.voice.disarm_capture()
                self.command_state.emit('capture', 'error:' + type(exc).__name__)
        asyncio.run_coroutine_threadsafe(work(), self.loop)

    def wake_config(self):
        """Read the Echo's installed and active wake words (emitted as JSON)."""
        async def work():
            try:
                if not self.online:
                    raise RuntimeError('offline')
                cfg = await self.api.get_voice_assistant_configuration(8)
                self.command_state.emit('wake_config', json.dumps({
                    'active': list(cfg.active_wake_words),
                    'available': {w.id: w.wake_word for w in cfg.available_wake_words},
                    'max': getattr(cfg, 'max_active_wake_words', 2)}, ensure_ascii=False))
            except Exception as exc:
                self.command_state.emit('wake_config', 'error:' + type(exc).__name__)
        asyncio.run_coroutine_threadsafe(work(), self.loop)

    def install_wake_model(self, model_id, phrase, languages, model_file, active):
        """Offer a trained model to the Echo over its own API (it downloads it from this PC's
        model server, checking size and SHA-256), then select `active` and read the selection back."""
        async def work():
            try:
                if not self.online:
                    raise RuntimeError('offline')
                from aioesphomeapi.model import VoiceAssistantExternalWakeWord as ExternalWakeWord
                raw = Path(model_file).read_bytes()
                manifest = Path(model_file).with_suffix('.json').read_bytes()
                # Preferred: hand both files to the Dot's own client, and let echod fetch them from
                # its loopback — no inbound port on this computer. Fallback: this computer's server.
                try:
                    import device_sync
                    for name, data in ((model_id + '.json', manifest), (model_id + '.tflite', raw)):
                        await asyncio.to_thread(device_sync.put_asset, name, data, IP)
                    url = f'http://127.0.0.1:8765/asset/{model_id}.json'
                except Exception:
                    peer = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    try:
                        peer.connect((IP, 6053))
                        host = peer.getsockname()[0]
                    finally:
                        peer.close()
                    url = f'http://{host}:18769/models/{model_id}.json'
                offer = ExternalWakeWord(id=model_id, wake_word=phrase, trained_languages=list(languages),
                                         model_type='openwakeword', model_size=len(raw),
                                         model_hash=hashlib.sha256(raw).hexdigest(), url=url)
                before = list((await self.api.get_voice_assistant_configuration(8, [offer])).active_wake_words)
                await self.api.set_voice_assistant_configuration(list(active))
                cfg = None
                selected_after_download = False
                for _ in range(30):
                    await asyncio.sleep(1)
                    cfg = await self.api.get_voice_assistant_configuration(8, [offer])
                    if list(cfg.active_wake_words) == list(active):
                        break
                    # The first selection can arrive before the download finished and name a model
                    # the Echo does not have yet; once it lists the model, select again (once).
                    if not selected_after_download and model_id in {w.id for w in cfg.available_wake_words}:
                        selected_after_download = True
                        await self.api.set_voice_assistant_configuration(list(active))
                result = {'active': list(cfg.active_wake_words) if cfg else [],
                          'requested': list(active),
                          'installed': model_id in {w.id for w in cfg.available_wake_words} if cfg else False}
                ok = result['active'] == list(active)
                if not ok and before:
                    # The Echo could not load the new model (it could not fetch it, or refused it) and
                    # shifted what remained into other slots. Put the previous selection back exactly.
                    await self.api.set_voice_assistant_configuration(before)
                    await asyncio.sleep(2)
                    cfg = await self.api.get_voice_assistant_configuration(8)
                    result.update(restored=list(cfg.active_wake_words), previous=before)
                    self.command_state.emit('wake_model', 'error:not_loaded ' + json.dumps(result))
                    return
                self.command_state.emit('wake_model', ('ok:' if ok else 'pending:') + json.dumps(result))
            except Exception as exc:
                self.command_state.emit('wake_model', 'error:' + type(exc).__name__)
        asyncio.run_coroutine_threadsafe(work(), self.loop)

    def select_wake_words(self, active):
        """Change which installed wake words listen (e.g. roll back), with read-back."""
        async def work():
            try:
                if not self.online:
                    raise RuntimeError('offline')
                await self.api.set_voice_assistant_configuration(list(active))
                await asyncio.sleep(2)
                cfg = await self.api.get_voice_assistant_configuration(8)
                result = {'active': list(cfg.active_wake_words), 'requested': list(active)}
                self.command_state.emit('wake_model', ('ok:' if result['active'] == list(active) else 'pending:')
                                        + json.dumps(result))
            except Exception as exc:
                self.command_state.emit('wake_model', 'error:' + type(exc).__name__)
        asyncio.run_coroutine_threadsafe(work(), self.loop)

    def speak(self, line):
        """Say one line on the Echo in Mira's own Live voice (no TTS quota): press the Echo's wake button
        and hand the new turn a text request instead of the microphone. The owner may answer after it,
        as after any reply."""
        async def work():
            if not self.online or self.voice is None:
                self.command_state.emit('speak', 'error:offline')
                return
            self.voice.test_text = line
            entity = self.entities.get('wake_assistant_1')
            if entity is None:
                self.voice.test_text = None
                self.command_state.emit('speak', 'error:no_wake_button')
                return
            self.api.button_command(key=entity.key, device_id=entity.device_id)
            self.command_state.emit('speak', 'sent')
        asyncio.run_coroutine_threadsafe(work(), self.loop)

    def cancel_voice(self):
        if self.voice:
            asyncio.run_coroutine_threadsafe(self.voice.stop(True), self.loop)

    def set_voice(self, enabled):
        self.voice_enabled = enabled
        async def work():
            if not self.voice:
                return
            try:
                if enabled:
                    await self.voice.enable()
                else:
                    await self.voice.disable()
            except Exception as exc:
                self.voice_state.emit('error', 'تعذّر الصوت: ' + type(exc).__name__)
        asyncio.run_coroutine_threadsafe(work(), self.loop)
