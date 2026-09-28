"""Paired Echo transport for the Mira desktop. Commands stay on its asyncio loop."""
import asyncio
import os
import socket
import sys
import threading
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

    def command(self, kind, name, value=None):
        async def work():
            try:
                if not self.online:
                    raise RuntimeError('offline')
                entity = self.entities[name]
                args = {'key': entity.key, 'device_id': entity.device_id}
                if kind == 'wake':
                    self.api.button_command(**args)
                    self.command_state.emit('wake', 'sent')
                elif kind == 'number':
                    self.api.number_command(**args, state=float(value))
                elif kind == 'switch':
                    self.api.switch_command(**args, state=bool(value))
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
