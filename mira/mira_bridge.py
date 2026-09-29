"""Paired Echo transport for the Mira desktop. Commands stay on its asyncio loop."""
import asyncio
import hashlib
import hmac
import json
import os
import socket
import sys
import threading
import time
from pathlib import Path

from PySide6.QtCore import QObject, Signal
from aioesphomeapi import APIClient, MediaPlayerCommand


IP = os.environ.get('MIRA_ECHO_HOST', '192.168.3.83')
KEY = Path.home() / '.config/mo-dot/device.key'


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
        self.heartbeat_task = None
        self.thread = threading.Thread(target=self.run, daemon=True)

    def start(self):
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
                elif kind == 'tone':
                    peer = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    try:
                        peer.connect((IP, 6053))
                        host = peer.getsockname()[0]
                    finally:
                        peer.close()
                    self.api.media_player_command(**args, media_url=f'http://{host}:18769/tone.wav')
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
                peer = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                try:
                    peer.connect((IP, 6053))
                    host = peer.getsockname()[0]
                finally:
                    peer.close()
                offer = ExternalWakeWord(id=model_id, wake_word=phrase, trained_languages=list(languages),
                                         model_type='openwakeword', model_size=len(raw),
                                         model_hash=hashlib.sha256(raw).hexdigest(),
                                         url=f'http://{host}:18769/models/{model_id}.json')
                await self.api.get_voice_assistant_configuration(8, [offer])
                await self.api.set_voice_assistant_configuration(list(active))
                cfg = None
                for _ in range(20):
                    await asyncio.sleep(1)
                    cfg = await self.api.get_voice_assistant_configuration(8, [offer])
                    if list(cfg.active_wake_words) == list(active):
                        break
                result = {'active': list(cfg.active_wake_words) if cfg else [],
                          'requested': list(active),
                          'installed': model_id in {w.id for w in cfg.available_wake_words} if cfg else False}
                ok = result['active'] == list(active)
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
