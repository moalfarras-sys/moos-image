"""Screen Sync: the lights follow what the screen shows.

One capture of the desktop (the ScreenCast portal: the owner approves once, MoOS keeps the grant)
is shrunk to a few dozen pixels and read for colour (sync.Analyzer). Each light gets its own part
of the picture: a Hue lamp in an Entertainment area by its measured position in the room, any other
lamp by its place in a left-to-right order, the computer's case fans by the bottom edge of the
picture. Three outputs, each at the rate its hardware can take:

    the PC's lighting controller   every frame (it is on the local USB bus)
    a Hue Entertainment stream     every frame, when Lumen has its own bridge pairing with a client
                                   key (the bridge then drives the lamps at ~25 Hz over Zigbee)
    any other Home Assistant lamp  a few times a second with a matching transition, round-robin,
                                   inside the engine's shared command budget

A light the owner changes by hand during sync leaves the session (release()); stopping puts nothing
back by itself — the lamps keep the last colour, which is what a person expects from "stop".
"""
from __future__ import annotations

import threading
import time
from typing import Optional

from lumen import colors

MODE_FPS = {'video': 30, 'game': 30, 'ambient': 15}


class SyncSession:
    def __init__(self, engine, targets: list[dict], *, mode: str = 'video', brightness: float = 1.0,
                 capture_factory=None, hue_factory=None):
        self.engine = engine
        self.mode = mode if mode in MODE_FPS else 'video'
        self.brightness = brightness
        self.capture_factory = capture_factory
        self.hue_factory = hue_factory
        self.lights = {l['id']: l for l in targets}
        self.regions: dict[str, tuple] = {}
        self.pc_edges: dict[str, int] = {}
        self.latest: dict[str, tuple] = {}
        self.ambient = (0, 0, 0)
        self.capture = None
        self.analyzer = None
        self.stream = None
        self.stream_channels: dict[str, int] = {}      # light id → Hue channel id
        self.stream_error = ''
        self.error = ''
        self.frames = 0
        self.started = 0.0
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._ha_thread = None
        self._terminal_state = ''

    # ── setup ────────────────────────────────────────────────────────
    def _layout(self):
        from lumen.sync import regions_for_names
        home = [l for l in self.lights.values() if l['source'] != 'pc' and l['id'] not in self.stream_channels]
        home.sort(key=lambda l: (l.get('position', 0), l['name']))
        named = regions_for_names([l['id'] for l in home]) if home else {}
        self.regions.update(named)
        for light in self.lights.values():
            if light['source'] == 'pc':
                self.pc_edges[light['id']] = max(1, int(light['caps'].get('leds', 1)))

    def _open_stream(self):
        """A Hue Entertainment stream for the targeted Hue lamps, when Lumen holds a client key."""
        creds = self.engine.store.hue()
        if not creds.get('client_key'):
            return
        try:
            if self.hue_factory is not None:
                bridge = self.hue_factory(creds)
            else:
                from lumen.hue import HueBridge
                bridge = HueBridge(creds['host'], creds['app_key'], creds.get('client_key'), creds.get('bridge_id'),
                                   cert_sha256=creds.get('cert_sha256'))
            by_uuid = {l.get('unique_id'): l['id'] for l in self.lights.values()
                       if l['source'] == 'home' and l.get('integration') == 'hue' and l.get('unique_id')}
            by_uuid.update({l['ref']: l['id'] for l in self.lights.values() if l['source'] == 'hue'})
            best, best_hits = None, 0
            for config in bridge.entertainment_configs():
                hits = sum(any(u in by_uuid for u in ch['lights']) for ch in config['channels'])
                if hits > best_hits:
                    best, best_hits = config, hits
            if best is None:
                return
            from lumen.sync import regions_for_channels
            channel_regions = regions_for_channels(best['channels'])
            for ch in best['channels']:
                for uuid in ch['lights']:
                    if uuid in by_uuid:
                        lid = by_uuid[uuid]
                        self.stream_channels[lid] = ch['id']
                        self.regions[lid] = channel_regions[str(ch['id'])]
            self.stream = bridge.start_stream(best['id'])
        except Exception as exc:          # fall back to Home Assistant for these lamps
            self.stream_error = str(exc) or type(exc).__name__
            self.stream = None
            self.stream_channels.clear()

    def start(self) -> None:
        from lumen.sync import Analyzer
        self.analyzer = Analyzer(self.mode, brightness=self.brightness)
        self._open_stream()
        self._layout()
        if self.capture_factory is not None:
            self.capture = self.capture_factory(self._frame, MODE_FPS[self.mode])
        else:
            from lumen.capture import ScreenCapture
            self.capture = ScreenCapture(self._frame, fps=MODE_FPS[self.mode],
                                         token_path=self.engine.store.dir / 'lumen-screencast.token')
        self.started = time.monotonic()
        self.capture.start()
        self._ha_thread = threading.Thread(target=self._ha_loop, daemon=True, name='lumen-sync-ha')
        self._ha_thread.start()

    # ── every frame ──────────────────────────────────────────────────
    def _frame(self, rgb: bytes, width: int, height: int) -> None:
        if self._stop.is_set():
            return
        try:
            colours = self.analyzer.regions(rgb, width, height, self.regions) if self.regions else {}
            ambient = self.analyzer.ambient(rgb, width, height)
            pc_frame = {}
            for lid, leds in self.pc_edges.items():
                light = self.lights.get(lid)
                if light is None:
                    continue
                if leds > 1:
                    pc_frame[light['ref']] = self.analyzer.gradient(rgb, width, height, leds, 'bottom')
                else:
                    pc_frame[light['ref']] = [ambient]
            with self._lock:
                self.latest.update(colours)
                self.ambient = ambient
                self.frames += 1
            if pc_frame:
                if self.engine.pc.stream(pc_frame) is False:
                    raise OSError(self.engine.pc.error or 'PC controller unavailable')
            if self.stream is not None and self.stream_channels:
                packet = {}
                for lid, channel in self.stream_channels.items():
                    if lid in colours:
                        packet[channel] = colours[lid]
                if packet:
                    self.stream.send(packet)
        except Exception as exc:
            self.error = str(exc) or type(exc).__name__

    def _ha_loop(self) -> None:
        """Home Assistant lamps without a stream: a few updates a second each, smoothly."""
        sent: dict[str, tuple] = {}
        sent_at: dict[str, float] = {}
        while not self._stop.is_set():
            home = [lid for lid, l in self.lights.items()
                    if l['source'] in ('home', 'hue') and lid not in self.stream_channels]
            if not home:
                self._stop.wait(0.5)
                continue
            gap = max(1.0 / 8.0, 0.45 / len(home))
            for lid in home:
                if self._stop.is_set():
                    return
                light = self.lights.get(lid)
                with self._lock:
                    colour = self.latest.get(lid)
                if light is None or colour is None:
                    continue
                # A cloud-polled lamp can join when explicitly selected, but never at the
                # local bridge's update rate. Do not let it consume the shared house budget.
                if light.get('integration') == 'tuya' and time.monotonic() - sent_at.get(lid, 0) < 2:
                    self._stop.wait(gap)
                    continue
                prev = sent.get(lid)
                if prev is not None and max(abs(a - b) for a, b in zip(prev, colour)) < 6:
                    self._stop.wait(gap)
                    continue
                level = max(colour)
                if level <= 0:
                    request = {'on': False}
                else:
                    full = [int(c * 255 / level) for c in colour]
                    request = {'on': True, 'brightness': max(1, round(level * 100 / 255)),
                               'rgb': full, 'effect': 'none'}
                self.engine._take_budget()
                backend = self.engine.hue if light['source'] == 'hue' else self.engine.home
                try:
                    backend.call(light, request, transition=0.4)
                    sent[lid] = colour
                    sent_at[lid] = time.monotonic()
                except Exception as exc:
                    self.error = str(exc) or type(exc).__name__
                self._stop.wait(gap)

    # ── control ──────────────────────────────────────────────────────
    def release(self, ids) -> None:
        for lid in ids:
            self.lights.pop(lid, None)
            self.pc_edges.pop(lid, None)
            self.stream_channels.pop(lid, None)
        if not self.lights:
            self.stop()

    def stop(self) -> None:
        if self._stop.is_set():
            return
        self._stop.set()
        if self.capture is not None:
            try:
                self.capture.stop()
            except Exception:
                pass
        if self.stream is not None:
            try:
                self.stream.close()
            except Exception:
                pass
            self.stream = None

    def status(self) -> dict:
        cap = self.capture
        state = getattr(cap, 'state', 'idle') if cap is not None else 'idle'
        if state in ('error', 'denied') and not self._stop.is_set():
            self._terminal_state = state
            self.error = self.error or getattr(cap, 'error', '') or state
            self.stop()
        state = self._terminal_state or state
        stats = {}
        try:
            stats = cap.stats() if cap is not None else {}
        except Exception:
            pass
        with self._lock:
            preview = {lid: colors.hex_of(c) for lid, c in self.latest.items() if lid in self.lights}
            for lid in self.pc_edges:
                preview[lid] = colors.hex_of(self.ambient)
            ambient = colors.hex_of(self.ambient)
        return {'running': not self._stop.is_set(), 'mode': self.mode, 'state': state,
                'error': self.error or getattr(cap, 'error', '') or '', 'fps': stats.get('fps', 0),
                'frames': self.frames, 'lights': list(self.lights), 'preview': preview, 'ambient': ambient,
                'stream': 'hue' if self.stream is not None else ('ha' if any(
                    l['source'] == 'home' for l in self.lights.values()) else 'pc'),
                'stream_error': self.stream_error, 'brightness': self.brightness}
