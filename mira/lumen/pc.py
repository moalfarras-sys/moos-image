"""The computer's own lights: the motherboard's RGB controller and what is plugged into it.

Case fans, strips and the board's own LEDs hang off the motherboard's lighting controller. Lumen
finds the controller by itself (USB ids, no setup), names each header so the owner can rename it
("مراوح الواجهة"), remembers what it showed last and puts it back at login: these controllers
forget everything sent to them at the next power cycle and fall back to their factory animation.

A header's LEDs cannot be read back. What "done" means here is that the controller acknowledged
every report (a USB control transfer that did not fail); the page says so instead of pretending to
have seen the fans change.
"""
from __future__ import annotations

import threading
import time
from typing import Optional

from lumen import colors
from lumen.fusion2 import Fusion2

# What the owner reads before he renames anything.
DEFAULT_NAMES = {
    'D_LED1': ('إضاءة الكيس 1', 'Case lights 1'),
    'D_LED2': ('إضاءة الكيس 2', 'Case lights 2'),
    'LED_C1': ('شريط RGB 1', 'RGB strip 1'),
    'LED_C2': ('شريط RGB 2', 'RGB strip 2'),
}
KIND_WORDS = {'argb': ('مراوح/شريط عنونة ARGB 5V', 'Addressable 5 V header (ARGB)'),
              'rgb': ('منفذ RGB 12V', '12 V RGB header')}


class PcLights:
    """Every controller on this machine, as lights with ids `pc:<zone>`."""

    def __init__(self, store, lang: str = 'ar'):
        self.store = store
        self.lang = lang
        self.controller: Optional[Fusion2] = None
        self.error = ''
        self._lock = threading.Lock()
        self._state: dict[str, dict] = {}
        self._identify_until = 0.0

    # ── discovery ────────────────────────────────────────────────────
    def open(self) -> bool:
        with self._lock:
            if self.controller is not None:
                return True
            try:
                self.controller = Fusion2.open()
            except OSError as exc:
                self.controller, self.error = None, str(exc)
                return False
            if self.controller is None:
                self.error = ''
                return False
            for key, conf in (self.store.get('pc') or {}).get('zones', {}).items():
                zone = self.controller.zones.get(key)
                if zone is not None and isinstance(conf.get('leds'), int) and 1 <= conf['leds'] <= 1024:
                    zone.leds = conf['leds']
            return True

    def present(self) -> bool:
        return self.controller is not None

    def describe(self) -> dict:
        if self.controller is None:
            return {'present': False, 'error': self.error}
        info = self.controller.describe()
        info['present'] = True
        info['maker'] = 'Gigabyte RGB Fusion 2'
        return info

    # ── as lights ────────────────────────────────────────────────────
    def _conf(self, key):
        return ((self.store.get('pc') or {}).get('zones') or {}).get(key) or {}

    def lights(self) -> list[dict]:
        if self.controller is None:
            return []
        out = []
        for key, zone in self.controller.zones.items():
            conf = self._conf(key)
            if conf.get('hidden'):
                continue
            default = DEFAULT_NAMES.get(key, (key, key))[0 if self.lang == 'ar' else 1]
            state = self._state.get(key) or self._remembered(key)
            out.append({
                'id': 'pc:' + key, 'ref': key, 'source': 'pc', 'kind': 'pc',
                'name': conf.get('name') or default, 'default_name': default,
                'room': 'PC', 'online': True, 'group': False, 'members': [],
                'detail': KIND_WORDS[zone.kind][0 if self.lang == 'ar' else 1] + ' · ' + key,
                'caps': {'power': True, 'brightness': True, 'color': True, 'temp': [2000, 6500],
                         'effects': ['breathe', 'flash', 'cycle', 'wave'], 'stream': 'pc',
                         'leds': zone.leds if zone.kind == 'argb' else 1, 'readback': False},
                'state': state,
            })
        return out

    def _remembered(self, key) -> dict:
        last = ((self.store.get('pc') or {}).get('last') or {}).get(key)
        state = dict(last) if isinstance(last, dict) else {'on': None, 'brightness': None, 'rgb': None,
                                                          'kelvin': None, 'effect': None}
        if state.get('effect') not in (None, 'breathe', 'flash', 'cycle', 'wave'):
            state['effect'] = None
        return state

    # ── control ──────────────────────────────────────────────────────
    def apply(self, key: str, *, on=None, rgb=None, brightness=None, kelvin=None, effect=None,
              remember: bool = True) -> dict:
        if self.controller is None or key not in self.controller.zones:
            return {'status': 'error', 'error': 'no such PC light'}
        if effect is not None and effect not in ('none', 'off', 'static', '', 'breathe', 'flash', 'cycle', 'wave'):
            return {'status': 'error', 'error': 'unsupported PC effect'}
        prev = self._state.get(key) or self._remembered(key)
        state = dict(prev)
        if kelvin is not None:
            rgb = colors.kelvin_to_rgb(kelvin)
            state['kelvin'] = int(kelvin)
        elif rgb is not None:
            state['kelvin'] = None
        if rgb is not None:
            state['rgb'] = [int(c) for c in rgb]
        if brightness is not None:
            state['brightness'] = max(0, min(100, int(round(brightness))))
            if state['brightness'] == 0:
                on = False
        if effect is not None:
            state['effect'] = None if effect in ('none', 'off', 'static', '') else effect
        if on is not None:
            state['on'] = bool(on)
        elif rgb is not None or brightness or effect:
            state['on'] = True
        base = state.get('rgb') or [255, 255, 255]
        level = (state.get('brightness') if state.get('brightness') is not None else 100) / 100.0
        try:
            if state.get('on') is False:
                self.controller.off([key])
            else:
                self.controller.set_effect([key], state.get('effect') or 'static', base, int(255 * level))
        except OSError as exc:
            return {'status': 'error', 'error': 'controller: %s' % exc}
        self._state[key] = state
        if remember:
            self._remember(key, state)
        return {'status': 'ok', 'verified': 'controller', 'state': state}

    def _remember(self, key, state):
        pc = dict(self.store.get('pc') or {})
        last = dict(pc.get('last') or {})
        last[key] = state
        pc['last'] = last
        self.store.set('pc', pc)

    def stream(self, frame: dict) -> bool:
        """Many-times-a-second colours ({zone: [(r,g,b), …]}); never remembered."""
        if self.controller is None:
            return False
        try:
            self.controller.stream(frame)
            for key, colours in frame.items():
                if key not in self.controller.zones or not colours:
                    continue
                rgb = [round(sum(c[i] for c in colours) / len(colours)) for i in range(3)]
                level = max(rgb)
                self._state[key] = {'on': level > 0, 'brightness': round(level * 100 / 255),
                                    'rgb': rgb, 'kelvin': None, 'effect': None}
            self.error = ''
            return True
        except OSError as exc:
            self.error = str(exc)
            return False

    def restore(self) -> int:
        """Put back what each header showed last (the board forgot it at power-off)."""
        if self.controller is None:
            return 0
        done = 0
        for key in self.controller.zones:
            last = self._remembered(key)
            if last.get('on') is None:
                continue
            result = self.apply(key, on=last.get('on'), rgb=last.get('rgb'), brightness=last.get('brightness'),
                                effect=last.get('effect') or 'static', remember=False)
            done += result.get('status') == 'ok'
        return done

    def identify(self, key: str, seconds: float = 4.0) -> dict:
        """Flash one header white so the owner can see which fans it is, then put it back."""
        if self.controller is None or key not in self.controller.zones:
            return {'status': 'error', 'error': 'no such PC light'}
        self._identify_until = time.monotonic() + seconds

        def run():
            try:
                self.controller.set_effect([key], 'flash', (255, 255, 255), 255, speed=0)
                time.sleep(seconds)
            except OSError:
                pass
            last = self._state.get(key) or self._remembered(key)
            if last.get('on') is False or last.get('on') is None:
                try:
                    self.controller.off([key])
                except OSError:
                    pass
            else:
                self.apply(key, on=True, rgb=last.get('rgb'), brightness=last.get('brightness'),
                           effect=last.get('effect') or 'static', remember=False)
        threading.Thread(target=run, daemon=True, name='lumen-identify').start()
        return {'status': 'ok', 'seconds': seconds}

    def configure(self, key: str, *, name=None, leds=None, hidden=None) -> dict:
        if self.controller is None or key not in self.controller.zones:
            return {'status': 'error', 'error': 'no such PC light'}
        pc = dict(self.store.get('pc') or {})
        zones = dict(pc.get('zones') or {})
        conf = dict(zones.get(key) or {})
        if name is not None:
            name = str(name).strip()[:40]
            conf['name'] = name or None
        if leds is not None:
            leds = int(leds)
            if not 1 <= leds <= 1024:
                return {'status': 'error', 'error': 'LED count 1–1024'}
            conf['leds'] = leds
            self.controller.zones[key].leds = leds
            self.controller._ready = False      # the count is written on the next start
        if hidden is not None:
            conf['hidden'] = bool(hidden)
        zones[key] = conf
        pc['zones'] = zones
        self.store.set('pc', pc)
        return {'status': 'ok', 'zone': key, 'conf': conf}
