"""Lumen — every light in the house and in the computer as one system.

The owner thinks in rooms, moods and "the lights", not in integrations. Lumen gathers every light it
can reach into one list with one id scheme:

    ha:<entity_id>   a light Home Assistant knows (Hue, Tuya, ESPHome …), controlled through HA
    hue:<uuid>       a Hue lamp reached directly, when no Home Assistant covers that bridge
    pc:<header>      a lighting header on this computer's motherboard (fans, strips)

and gives them rooms (Home Assistant areas, plus "PC"), groups (Hue rooms/zones, the owner's own
groups), scenes (scenes.py) and one live mode, Screen Sync, where lights follow what the screen
shows. A target is resolved from words — "all", a room, a group, a light's name or alias — so the
voice brain, the typed brain and the page all speak the same language.

What "done" means: a Home Assistant light is ok only when its state read back matches; a PC header
is ok when its controller acknowledged the reports (it cannot be read back, and says so). A light
that is unavailable is reported as such and never counted as a success.

Rates are bounded: Home Assistant/Hue lamps take at most ~8 commands a second in total (the Hue
bridge's own guidance is 10/s), so living scenes move each lamp every few seconds with a matching
transition, and only the Hue Entertainment stream and the PC controller run at video rate.
"""
from __future__ import annotations

import re
import threading
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Optional

from lumen import colors, scenes
from lumen.pc import PcLights
from lumen.store import Store

CLOUD_INTEGRATIONS = {'tuya', 'smartthings', 'lifx_cloud', 'govee', 'tplink_tapo_cloud'}
HA_RATE = 8.0                 # Home Assistant light commands per second, all lamps together
SYNC_HA_INTERVAL = 0.45       # seconds between colour updates of one HA lamp in Screen Sync (no stream)
PC_FPS = 30

ALL_WORDS = {'all', 'everything', 'every light', 'all lights', 'الكل', 'كل', 'كلهم', 'كل الاضواء', 'كل الأضواء',
             'كل الاضاءة', 'كل الإضاءة', 'جميع الاضواء', 'جميع الأضواء', 'الاضواء', 'الأضواء', 'الاضاءة', 'الإضاءة',
             'الضو', 'الضوء', 'الضواو', 'كل شي'}
HOME_WORDS = {'home', 'house', 'room', 'البيت', 'المنزل', 'الغرفة', 'اضواء البيت', 'أضواء البيت', 'ضو البيت'}
PC_WORDS = {'pc', 'computer', 'case', 'rgb', 'الكمبيوتر', 'الكومبيوتر', 'الحاسوب', 'الجهاز', 'الكيس', 'كيس',
            'المراوح', 'مراوح', 'اضاءة الكمبيوتر', 'إضاءة الكمبيوتر', 'اضاءة الكيس', 'إضاءة الكيس', 'ار جي بي'}


def norm(text: str) -> str:
    """A name as a person might type or say it: no case, no hamza variants, no article."""
    text = unicodedata.normalize('NFKC', str(text or '')).strip().lower()
    text = re.sub('[ً-ْـ]', '', text)
    text = text.translate(str.maketrans({'أ': 'ا', 'إ': 'ا', 'آ': 'ا', 'ة': 'ه', 'ى': 'ي', 'ؤ': 'و', 'ئ': 'ي'}))
    words = [w[2:] if w.startswith('ال') and len(w) > 4 else w for w in re.split(r'[\s_\-]+', text) if w]
    return ' '.join(words)


ALL_N = {norm(w) for w in ALL_WORDS}
HOME_N = {norm(w) for w in HOME_WORDS}
PC_N = {norm(w) for w in PC_WORDS}


# ── Home Assistant lights ────────────────────────────────────────────────
def _ha_light(record: dict, attrs: dict, state: str) -> dict:
    modes = attrs.get('supported_color_modes') or []
    temp = None
    if 'color_temp' in modes:
        lo = attrs.get('min_color_temp_kelvin') or 2000
        hi = attrs.get('max_color_temp_kelvin') or 6500
        temp = [int(lo), int(hi)]
    effects = [e for e in (attrs.get('effect_list') or [])
               if isinstance(e, str) and e.lower() not in ('none', 'off', 'no_effect', 'no effect')]
    members = attrs.get('entity_id') if isinstance(attrs.get('entity_id'), list) else []
    on = state == 'on'
    bri = attrs.get('brightness')
    kelvin = attrs.get('color_temp_kelvin') if attrs.get('color_mode') == 'color_temp' else None
    effect = attrs.get('effect')
    # the Echo's own ring is Mira's listening light: a light the owner may set by name, never part of
    # "all the lights" or a scene
    ring = record['entity_id'].startswith('light.mira_') or record.get('kind') == 'ring'
    return {
        'id': 'ha:' + record['entity_id'], 'ref': record['entity_id'], 'source': 'home',
        'kind': 'group' if members else ('ring' if ring else 'lamp'),
        'name': record.get('name') or attrs.get('friendly_name') or record['entity_id'],
        'default_name': record.get('default_name') or attrs.get('friendly_name') or '',
        'room': record.get('area') or '', 'aliases': list(record.get('aliases') or []),
        'online': state not in ('unavailable', 'unknown'),
        'group': bool(members), 'members': ['ha:' + m for m in members],
        'integration': record.get('integration') or '', 'unique_id': record.get('unique_id') or '',
        'detail': ' · '.join(x for x in (record.get('manufacturer'), record.get('model')) if x),
        'caps': {'power': True,
                 'effect_off': next((e for e in (attrs.get('effect_list') or [])
                                     if isinstance(e, str) and e.lower() in ('off', 'none', 'no_effect', 'no effect')), None),
                 'brightness': any(m != 'onoff' for m in modes) or bri is not None,
                 'color': any(m in ('hs', 'xy', 'rgb', 'rgbw', 'rgbww') for m in modes),
                 'temp': temp, 'white': 'white' in modes, 'effects': effects,
                 'stream': None, 'readback': True},
        'state': {'on': on if state in ('on', 'off') else None,
                  'brightness': round(bri * 100 / 255) if (on and isinstance(bri, (int, float))) else (0 if state == 'off' else None),
                  'rgb': list(attrs['rgb_color']) if on and attrs.get('rgb_color') else None,
                  'kelvin': int(kelvin) if on and kelvin else None,
                  'effect': effect if effect and str(effect).lower() not in ('none', 'off', 'no_effect') else None},
    }


class HomeLights:
    """Home Assistant's lights, read in one pass (registry names and rooms + live states)."""

    def __init__(self, hub_loader: Callable):
        self.hub_loader = hub_loader
        self.hub = None
        self.error = ''
        self._records: dict[str, dict] = {}
        self._records_at = 0.0
        self._lock = threading.Lock()

    def _ensure(self):
        if self.hub is None:
            self.hub = self.hub_loader()
        return self.hub

    def linked(self) -> bool:
        try:
            return self._ensure() is not None
        except Exception:
            return False

    def lights(self, registry_age: float = 300.0) -> list[dict]:
        hub = self._ensure()
        if hub is None:
            self.error = 'not linked'
            return []
        try:
            now = time.monotonic()
            if not self._records or now - self._records_at > registry_age:
                records = {}
                for rec in hub.inventory(include_hidden=False):
                    if rec.get('domain') == 'light':
                        records[rec['entity_id']] = rec
                with self._lock:
                    self._records, self._records_at = records, now
            states = {s['entity_id']: s for s in hub.states() if s['entity_id'].startswith('light.')}
        except Exception as exc:     # a home that cannot be reached is a state, not a crash
            self.error = str(exc) or type(exc).__name__
            return []
        self.error = ''
        out = []
        for entity_id, rec in self._records.items():
            st = states.get(entity_id)
            if st is None:
                continue
            out.append(_ha_light(rec, st.get('attributes') or {}, st.get('state', 'unknown')))
        return out

    def invalidate(self):
        self._records_at = 0.0

    def states(self) -> dict:
        hub = self._ensure()
        return {s['entity_id']: s for s in hub.states() if s['entity_id'].startswith('light.')}

    def call(self, light: dict, request: dict, transition: Optional[float] = None) -> None:
        hub = self._ensure()
        entity_id = light['ref']
        if request.get('on') is False:
            data = {'entity_id': entity_id}
            if transition is not None:
                data['transition'] = transition
            hub.call('light', 'turn_off', data)
            return
        data = {'entity_id': entity_id}
        caps = light['caps']
        if request.get('brightness') is not None and caps.get('brightness'):
            data['brightness_pct'] = max(1, min(100, int(round(request['brightness']))))
        if request.get('kelvin') is not None:
            if caps.get('temp'):
                lo, hi = caps['temp']
                data['color_temp_kelvin'] = max(lo, min(hi, int(request['kelvin'])))
            elif caps.get('color'):
                data['rgb_color'] = list(colors.kelvin_to_rgb(request['kelvin']))
        elif request.get('rgb') is not None and caps.get('color'):
            data['rgb_color'] = [int(c) for c in request['rgb']]
        if request.get('effect') is not None:
            wanted = request['effect']
            if wanted in ('none', 'off', ''):
                # Hue calls its "no effect" 'off', other integrations 'None': use the lamp's own word
                if caps.get('effect_off'):
                    data['effect'] = caps['effect_off']
            elif wanted in caps.get('effects', []):
                data['effect'] = wanted
        if request.get('flash'):
            data['flash'] = request['flash']
        if transition is not None:
            data['transition'] = transition
        hub.call('light', 'turn_on', data)


class HueLights:
    """Hue lamps reached directly, through Lumen's own pairing with the bridge.

    Used when no Home Assistant covers that bridge (a fresh MoOS with only a Hue bridge on the
    network): the lamps are then lights of their own (`hue:<uuid>`), read back from the bridge.
    Where Home Assistant already has the bridge, its lamps stay Home Assistant's and the bridge is
    used only for the Entertainment stream."""

    def __init__(self, store, factory=None):
        self.store = store
        self.factory = factory
        self._bridge = None
        self._creds = None
        self.error = ''

    def bridge(self):
        creds = self.store.hue()
        if not creds:
            self._bridge, self._creds = None, None
            return None
        if self._bridge is None or creds != self._creds:
            if self.factory is not None:
                self._bridge = self.factory(creds)
            else:
                from lumen.hue import HueBridge
                self._bridge = HueBridge(creds['host'], creds['app_key'], creds.get('client_key'),
                                         creds.get('bridge_id'), cert_sha256=creds.get('cert_sha256'))
            self._creds = creds
        return self._bridge

    def read(self) -> dict:
        bridge = self.bridge()
        return {l['id']: l for l in bridge.lights()} if bridge is not None else {}

    def lights(self) -> list[dict]:
        try:
            found = self.read()
        except Exception as exc:
            self.error = str(exc) or type(exc).__name__
            return []
        self.error = ''
        out = []
        for lid, l in found.items():
            on = bool(l.get('on')) and l.get('reachable', True)
            rgb = list(colors.xy_to_rgb(*l['xy'])) if on and l.get('xy') and not l.get('mirek') else None
            kelvin = int(round(1_000_000 / l['mirek'])) if on and l.get('mirek') else None
            mr = l.get('mirek_range')
            out.append({
                'id': 'hue:' + lid, 'ref': lid, 'source': 'hue', 'kind': 'lamp', 'name': l.get('name') or lid,
                'default_name': l.get('name') or '', 'room': '', 'aliases': [], 'online': bool(l.get('reachable', True)),
                'group': False, 'members': [], 'integration': 'hue', 'unique_id': lid, 'detail': 'Philips Hue',
                'caps': {'power': True, 'brightness': True, 'color': bool(l.get('gamut') or l.get('xy')),
                         'temp': [int(1_000_000 / mr[1]), int(1_000_000 / mr[0])] if mr else None,
                         'effects': list(l.get('effects') or []), 'effect_off': 'none',
                         'stream': 'hue' if l.get('entertainment') else None, 'readback': True},
                'state': {'on': on, 'brightness': round(l.get('brightness') or 0) if on else 0, 'rgb': rgb,
                          'kelvin': kelvin, 'effect': None},
            })
        return out

    def call(self, light: dict, request: dict, transition=None) -> None:
        bridge = self.bridge()
        if bridge is None:
            raise RuntimeError('the Hue bridge is not paired')
        kw = {'duration_ms': int(transition * 1000) if transition is not None else None}
        if request.get('on') is False:
            bridge.set_light(light['ref'], on=False, **kw)
            return
        effect = request.get('effect')
        bridge.set_light(light['ref'], on=True,
                         rgb=None if request.get('kelvin') is not None else request.get('rgb'),
                         kelvin=request.get('kelvin'), brightness=request.get('brightness'),
                         effect=None if effect in (None, '') else effect, **kw)

    @staticmethod
    def verified(request: dict, seen: dict) -> bool:
        if seen is None:
            return False
        if request.get('on') is False:
            return not seen.get('on')
        if not seen.get('on'):
            return False
        if request.get('brightness') is not None and abs((seen.get('brightness') or 0) - request['brightness']) > 7:
            return False
        if request.get('kelvin') is not None:
            return bool(seen.get('mirek')) and abs(1_000_000 / seen['mirek'] - request['kelvin']) <= max(150, request['kelvin'] * 0.06)
        if request.get('rgb') is not None and seen.get('xy'):
            return colors.close(colors.xy_to_rgb(*seen['xy']), request['rgb'])
        return True


def _verified(light: dict, request: dict, observed: dict) -> bool:
    if observed is None:
        return False
    state = observed.get('state')
    if request.get('on') is False:
        return state == 'off'
    if state != 'on':
        return False
    attrs = observed.get('attributes') or {}
    caps = light['caps']
    if request.get('brightness') is not None and caps.get('brightness'):
        bri = attrs.get('brightness')
        if bri is None or abs(bri * 100 / 255 - request['brightness']) > 7:
            return False
    if request.get('kelvin') is not None and caps.get('temp'):
        k = attrs.get('color_temp_kelvin')
        lo, hi = caps['temp']
        want = max(lo, min(hi, request['kelvin']))
        if attrs.get('color_mode') != 'color_temp' or k is None or abs(k - want) > max(150, want * 0.06):
            return False
    elif request.get('rgb') is not None and caps.get('color'):
        if not colors.close(attrs.get('rgb_color'), request['rgb']):
            return False
    if request.get('effect') and request['effect'] not in ('none', 'off') and request['effect'] in caps.get('effects', []):
        if attrs.get('effect') != request['effect']:
            return False
    return True


def _memory_aliases() -> dict:
    """Names the owner taught Mira («المكتب» → light.fernseher_buro), from her memory file."""
    try:
        import json
        from lumen.store import CONFIG_DIR
        data = json.loads((CONFIG_DIR / 'mira-memory.json').read_text(encoding='utf-8'))
        aliases = data.get('aliases') or {}
        return {str(k): str(v) for k, v in aliases.items() if isinstance(k, str) and isinstance(v, str)}
    except (OSError, ValueError, AttributeError):
        return {}


# ── the engine ───────────────────────────────────────────────────────────
class Engine:
    def __init__(self, store: Optional[Store] = None, *, hub_loader: Optional[Callable] = None,
                 pc: Optional[PcLights] = None, lang: str = 'ar', capture_factory=None, hue_factory=None):
        self.store = store or Store()
        self.lang = lang
        if hub_loader is None:
            import homehub
            hub_loader = homehub.load
        self.home = HomeLights(hub_loader)
        self.hue = HueLights(self.store, hue_factory)
        self.pc = pc or PcLights(self.store, lang)
        self.capture_factory = capture_factory
        self.hue_factory = hue_factory
        self._lights: dict[str, dict] = {}
        self._refreshed = 0.0
        self._lock = threading.RLock()
        self._pool = ThreadPoolExecutor(max_workers=6, thread_name_prefix='lumen-ha')
        self._ha_budget = HA_RATE
        self._ha_budget_at = time.monotonic()
        self._living: dict[str, dict] = {}     # light id → animation (a living scene)
        self._scene: Optional[dict] = None
        self._stop = threading.Event()
        self._wake = threading.Event()          # a living scene began: the director stops idling
        self._director = None
        self.sync = None                        # lumen.syncsession.SyncSession while running

    # ── lifecycle ────────────────────────────────────────────────────
    def start(self) -> None:
        self.pc.open()
        self.pc.restore()
        self.refresh(force=True)
        self._director = threading.Thread(target=self._direct, daemon=True, name='lumen-director')
        self._director.start()
        self._resume_pc_scene()
        self._resume_screen_sync()

    def _resume_screen_sync(self) -> None:
        """House lights resume only when the owner explicitly enabled login Screen Sync."""
        prefs = self.store.get('sync') or {}
        if prefs.get('resume_at_login') is True:
            self.sync_start(mode=prefs.get('mode') or 'video')

    def _resume_pc_scene(self) -> None:
        """A living scene on the computer's own lights keeps moving after a restart or a new login.

        Only the PC: the house's lamps are never changed because the computer started."""
        last = self.store.get('last_scene') or {}
        scene = scenes.find(last.get('id') or '')
        if scene is None or scene.period <= 0 or not scene.palette:
            return
        targets, _ = self.resolve(last.get('target') or 'all')
        pcs = [l['id'] for l in targets if l['source'] == 'pc']
        if pcs:
            try:
                self.scene(scene.id, pcs, last.get('brightness'), remember=False)
            except Exception:
                pass

    def close(self) -> None:
        self._stop.set()
        self._wake.set()
        if self.sync is not None:
            self.sync.stop()
            self.sync = None
        self._pool.shutdown(wait=False, cancel_futures=True)

    # ── inventory ────────────────────────────────────────────────────
    def refresh(self, force: bool = False, max_age: float = 4.0) -> dict:
        with self._lock:
            if not force and time.monotonic() - self._refreshed < max_age and self._lights:
                return self._lights
            if not self.pc.present():
                self.pc.open()
            lights = {}
            for light in self.home.lights(registry_age=0 if force else 300):
                lights[light['id']] = light
            if not any(l.get('integration') == 'hue' for l in lights.values()):
                for light in self.hue.lights():
                    lights[light['id']] = light
            for light in self.pc.lights():
                lights[light['id']] = light
            names = self.store.get('names') or {}
            for lid, name in names.items():
                if lid in lights and name:
                    lights[lid]['name'] = name
            for alias, entity_id in _memory_aliases().items():
                light = lights.get('ha:' + str(entity_id)) or lights.get(str(entity_id))
                if light is not None and alias not in light.setdefault('aliases', []):
                    light['aliases'].append(alias)
            for lid, anim in self._living.items():
                if lid in lights:
                    lights[lid]['living'] = anim['scene'].id
            self._lights = lights
            self._refreshed = time.monotonic()
            return lights

    def leaves(self, lights=None) -> list[dict]:
        lights = lights if lights is not None else self.refresh()
        return [l for l in lights.values() if not l['group']]

    def rooms(self) -> list[dict]:
        out: dict[str, dict] = {}
        for light in self.leaves():
            room = light['room'] or ('بلا غرفة' if self.lang == 'ar' else 'No room')
            entry = out.setdefault(room, {'name': room, 'lights': [], 'on': 0, 'online': 0})
            entry['lights'].append(light['id'])
            entry['online'] += light['online']
            entry['on'] += bool(light['state'].get('on')) and light['online']
        return list(out.values())

    def groups(self) -> list[dict]:
        lights = self.refresh()
        out = []
        for light in lights.values():
            if light['group']:
                members = [m for m in light['members'] if m in lights]
                out.append({'id': light['id'], 'name': light['name'], 'kind': 'home', 'lights': members})
        for name, ids in (self.store.get('groups') or {}).items():
            out.append({'id': 'group:' + name, 'name': name, 'kind': 'owner', 'lights': [i for i in ids if i in lights]})
        return out

    def snapshot(self) -> dict:
        lights = self.refresh()
        leaves = self.leaves(lights)
        return {
            'status': 'ok',
            'lights': sorted(lights.values(), key=lambda l: (l['source'] != 'home', l['group'], l['room'], l['name'])),
            'rooms': self.rooms(),
            'groups': self.groups(),
            'scenes': scenes.catalog(self.lang),
            'scene': dict(self._scene) if self._scene else None,
            'counts': {'lights': len(leaves), 'online': sum(l['online'] for l in leaves),
                       'on': sum(bool(l['state'].get('on')) and l['online'] for l in leaves),
                       'pc': sum(l['source'] == 'pc' for l in leaves)},
            'home': {'linked': self.home.hub is not None or self.home.linked(), 'error': self.home.error},
            'pc': self.pc.describe(),
            'hue': self.hue_status(),
            'sync': self.sync_status(),
        }

    # ── words → lights ───────────────────────────────────────────────
    def resolve(self, target) -> tuple[list[dict], list[str]]:
        lights = self.refresh()
        leaves = {l['id']: l for l in self.leaves(lights)}
        if target is None or target == '' or target == []:
            target = 'all'
        words = target if isinstance(target, list) else re.split(r'\s*[,،+&]\s*|\s+(?:و|and)\s+', str(target))
        chosen: dict[str, dict] = {}
        unknown: list[str] = []
        owner_groups = self.store.get('groups') or {}
        for raw in words:
            if not str(raw).strip():
                continue
            word = norm(raw)
            picked: list[str] = []
            if word in ALL_N:
                picked = [i for i, l in leaves.items() if l['kind'] != 'ring']
            elif word in PC_N:
                picked = [i for i, l in leaves.items() if l['source'] == 'pc']
            elif word in HOME_N:
                picked = [i for i, l in leaves.items() if l['source'] != 'pc' and l['kind'] != 'ring']
            else:
                picked = self._match(raw, word, lights, leaves, owner_groups)
            if picked:
                for i in picked:
                    if i in leaves:
                        chosen[i] = leaves[i]
            else:
                unknown.append(str(raw))
        return list(chosen.values()), unknown

    def _match(self, raw, word, lights, leaves, owner_groups) -> list[str]:
        raw = str(raw).strip()
        if raw in lights:
            return self._expand(raw, lights)
        if ('ha:' + raw) in lights:
            return self._expand('ha:' + raw, lights)
        if raw.startswith('group:') and raw[6:] in owner_groups:
            return [i for i in owner_groups[raw[6:]] if i in leaves]
        for name, ids in owner_groups.items():
            if norm(name) == word:
                return [i for i in ids if i in leaves]
        exact, partial = [], []
        rooms: dict[str, list[str]] = {}
        for light in leaves.values():
            if light['room']:
                rooms.setdefault(norm(light['room']), []).append(light['id'])
        if word in rooms:
            return rooms[word]
        for light in lights.values():
            names = [light['name'], light.get('default_name') or ''] + list(light.get('aliases') or [])
            keys = [norm(n) for n in names if n]
            if word in keys:
                exact.append(light['id'])
            elif any(word and (word in k or k in word) for k in keys if len(k) >= 2):
                partial.append(light['id'])
        pick = exact or (partial if len(partial) <= 3 else [])
        out = []
        for lid in pick:
            out.extend(self._expand(lid, lights))
        return out

    def _expand(self, lid, lights) -> list[str]:
        light = lights.get(lid)
        if light is None:
            return []
        if light['group']:
            return [m for m in light['members'] if m in lights and not lights[m]['group']]
        return [lid]

    # ── control ──────────────────────────────────────────────────────
    def set(self, target=None, *, on=None, color=None, rgb=None, brightness=None, kelvin=None,
            effect=None, transition=None, keep_living: bool = False) -> dict:
        targets, unknown = self.resolve(target)
        if not targets:
            return {'status': 'error', 'error': self._t('ما لقيت ضوءاً بهذا الاسم', 'No light matches that name'),
                    'unknown': unknown, 'results': []}
        if color:
            parsed = colors.parse(color)
            if parsed is None:
                return {'status': 'error', 'error': self._t('لون غير معروف: ', 'Unknown colour: ') + str(color)}
            rgb = parsed.get('rgb', rgb)
            kelvin = parsed.get('kelvin', kelvin)
        request = {'on': on, 'rgb': list(rgb) if rgb else None, 'brightness': brightness, 'kelvin': kelvin,
                   'effect': effect}
        if on is None and (rgb is not None or kelvin is not None or (brightness or 0) > 0 or effect):
            request['on'] = True
        if brightness is not None and brightness <= 0:
            request.update(on=False, brightness=None)
        if not keep_living:
            for light in targets:
                self._living.pop(light['id'], None)
            if self.sync is not None:
                self.sync.release([l['id'] for l in targets])
        result = self._apply([(l, dict(request)) for l in targets], transition=transition)
        result['unknown'] = unknown
        if request['on'] is not False and not keep_living:
            self._scene = None
        return result

    def _apply(self, plan: list[tuple[dict, dict]], transition=None, verify: bool = True) -> dict:
        results = []
        home_jobs, hue_jobs = [], []
        for light, request in plan:
            if not light['online']:
                results.append(self._row(light, 'unavailable'))
                continue
            if light['source'] == 'pc':
                outcome = self.pc.apply(light['ref'], on=request.get('on'), rgb=request.get('rgb'),
                                        brightness=request.get('brightness'), kelvin=request.get('kelvin'),
                                        effect=request.get('effect'))
                results.append(self._row(light, outcome['status'], outcome.get('error'), verified='controller'))
                continue
            if light['source'] == 'hue':
                hue_jobs.append((light, request))
                continue
            home_jobs.append((light, request))
        if home_jobs:
            results.extend(self._apply_home(home_jobs, transition, verify))
        if hue_jobs:
            results.extend(self._apply_hue(hue_jobs, transition))
        ok = sum(r['status'] == 'ok' for r in results)
        status = 'ok' if ok == len(results) else ('partial' if ok else
                                                  ('pending' if any(r['status'] == 'pending' for r in results) else 'error'))
        self._refreshed = 0.0
        return {'status': status, 'confirmed': ok, 'total': len(results), 'results': results}

    def _row(self, light, status, error=None, verified=None) -> dict:
        row = {'id': light['id'], 'name': light['name'], 'status': status}
        if error:
            row['error'] = error
        if verified:
            row['verified'] = verified
        return row

    def _take_budget(self, n: int = 1) -> None:
        """Home Assistant lamps share one command budget (the Hue bridge's own limit)."""
        while True:
            now = time.monotonic()
            self._ha_budget = min(HA_RATE, self._ha_budget + (now - self._ha_budget_at) * HA_RATE)
            self._ha_budget_at = now
            if self._ha_budget >= n:
                self._ha_budget -= n
                return
            time.sleep((n - self._ha_budget) / HA_RATE)

    def _apply_home(self, jobs, transition, verify) -> list[dict]:
        # A Hue room/zone whose every available lamp gets the same request is sent once to the group:
        # one Zigbee broadcast, so the lamps change together instead of one after another.
        calls = []
        remaining = list(jobs)
        by_id = {light['id']: (light, req) for light, req in jobs}
        for group in [l for l in self._lights.values() if l['group'] and l['online'] and l['source'] == 'home']:
            members = [m for m in group['members'] if m in self._lights and self._lights[m]['online']]
            if len(members) < 2 or not all(m in by_id for m in members):
                continue
            reqs = [by_id[m][1] for m in members]
            if any(r != reqs[0] for r in reqs):
                continue
            if any(by_id[m][0]['id'] not in [j[0]['id'] for j in remaining] for m in members):
                continue
            calls.append((group, reqs[0]))
            remaining = [j for j in remaining if j[0]['id'] not in members]
        calls.extend(remaining)
        errors: dict[str, str] = {}

        def send(light, request):
            self._take_budget()
            try:
                self.home.call(light, request, transition)
            except Exception as exc:
                for member in (light['members'] if light['group'] else [light['id']]):
                    errors[member] = str(exc) or type(exc).__name__
        list(self._pool.map(lambda job: send(*job), calls))
        if not verify:
            return [self._row(l, 'error' if l['id'] in errors else 'pending', errors.get(l['id'])) for l, _ in jobs]
        pending = {l['id']: (l, r) for l, r in jobs if l['id'] not in errors}
        verified: set[str] = set()
        deadline = time.monotonic() + 3.5 + (transition or 0)
        time.sleep(0.25)
        while pending and time.monotonic() < deadline:
            try:
                observed = self.home.states()
            except Exception:
                break
            for lid, (light, request) in list(pending.items()):
                if _verified(light, request, observed.get(light['ref'])):
                    verified.add(lid)
                    pending.pop(lid)
            if pending:
                time.sleep(0.4)
        rows = []
        for light, _ in jobs:
            if light['id'] in errors:
                rows.append(self._row(light, 'error', errors[light['id']]))
            elif light['id'] in verified:
                rows.append(self._row(light, 'ok', verified='readback'))
            else:
                rows.append(self._row(light, 'pending'))
        return rows

    def _apply_hue(self, jobs, transition) -> list[dict]:
        errors: dict[str, str] = {}

        def send(light, request):
            self._take_budget()
            try:
                self.hue.call(light, request, transition)
            except Exception as exc:
                errors[light['id']] = str(exc) or type(exc).__name__
        list(self._pool.map(lambda job: send(*job), jobs))
        pending = {l['id']: (l, r) for l, r in jobs if l['id'] not in errors}
        verified: set[str] = set()
        deadline = time.monotonic() + 3.5 + (transition or 0)
        time.sleep(0.3)
        while pending and time.monotonic() < deadline:
            try:
                seen = self.hue.read()
            except Exception:
                break
            for lid, (light, request) in list(pending.items()):
                if HueLights.verified(request, seen.get(light['ref'])):
                    verified.add(lid)
                    pending.pop(lid)
            if pending:
                time.sleep(0.4)
        return [self._row(l, 'error', errors[l['id']]) if l['id'] in errors else
                self._row(l, 'ok', verified='readback') if l['id'] in verified else self._row(l, 'pending')
                for l, _ in jobs]

    # ── scenes ───────────────────────────────────────────────────────
    def scene(self, name: str, target=None, brightness: Optional[int] = None, remember: bool = True) -> dict:
        scene = scenes.find(name)
        if scene is None:
            return {'status': 'error', 'error': self._t('ما في مشهد بهالاسم', 'No scene by that name'),
                    'scenes': [s.id for s in scenes.SCENES]}
        targets, unknown = self.resolve(target or 'all')
        targets = [l for l in targets if l['online']]
        if not targets:
            return {'status': 'error', 'error': self._t('ما في أضواء متاحة', 'No available lights'), 'unknown': unknown}
        if self.sync is not None:
            self.sync.release([l['id'] for l in targets])
        level = scene.brightness if brightness is None else max(1, min(100, int(brightness)))
        palette = scene.rgb_palette()
        plan = []
        ordered = sorted(targets, key=lambda l: (l['source'] == 'pc', l['room'], l['name']))
        home_count = sum(l['source'] != 'pc' for l in ordered)
        for i, light in enumerate(ordered):
            self._living.pop(light['id'], None)
            if light['source'] == 'pc' and scene.pc == 'off':
                plan.append((light, {'on': False}))
                continue
            request = {'on': True, 'brightness': level, 'rgb': None, 'kelvin': None, 'effect': None}
            if scene.kelvin:
                request['kelvin'] = scene.kelvin
            elif palette:
                request['rgb'] = list(palette[i % len(palette)])
            if scene.hue_effect and scene.hue_effect in light['caps'].get('effects', []):
                request['effect'] = scene.hue_effect
            elif light['caps'].get('effects') and light['source'] != 'pc':
                request['effect'] = 'none'
            if light['source'] == 'pc' and scene.pc in ('breathe', 'cycle', 'wave'):
                request['effect'] = scene.pc
            plan.append((light, request))
            if scene.period > 0 and palette and request.get('effect') in (None, 'none'):
                n = home_count if light['source'] != 'pc' else 1
                self._living[light['id']] = {'scene': scene, 'phase': (i / max(1, len(ordered))),
                                             'level': level, 'start': time.monotonic(),
                                             'interval': max(3.0, n / HA_RATE * 2.2), 'due': time.monotonic() + 2.0}
        result = self._apply(plan, transition=1.0)
        if self._living:
            self._wake.set()
        self._scene = {'id': scene.id, 'name': scene.name_ar if self.lang == 'ar' else scene.name_en,
                       'target': target or 'all', 'brightness': level, 'at': time.time()}
        if remember:
            self.store.set('last_scene', self._scene)
        result['scene'] = self._scene
        return result

    def _direct(self) -> None:
        """The director: moves living scenes, a few HA lamps at a time, the PC at video rate.

        With nothing living it sleeps (a refresh every 20 s): an idle engine must not tick 30 times a
        second for nothing."""
        next_refresh = time.monotonic() + 20
        while not self._stop.is_set():
            if self._living:
                self._stop.wait(1.0 / PC_FPS)
            else:
                self._wake.wait(max(0.0, next_refresh - time.monotonic()))
                self._wake.clear()
            if self._stop.is_set():
                return
            now = time.monotonic()
            if now > next_refresh:
                next_refresh = now + 20
                try:
                    self.refresh(force=False, max_age=15)
                except Exception:
                    pass
            if not self._living:
                continue
            pc_frame = {}
            for lid, anim in list(self._living.items()):
                light = self._lights.get(lid)
                if light is None:
                    continue
                scene = anim['scene']
                phase = anim['phase'] + (now - anim['start']) / scene.period
                if light['source'] == 'pc':
                    leds = max(1, light['caps'].get('leds', 1))
                    base = [colors.palette_at(scene.rgb_palette(), phase + k / max(leds, 1) * 0.5)
                            for k in range(leds if leds > 1 else 1)]
                    pc_frame[light['ref']] = [colors.scale(c, anim['level'] / 100) for c in base]
                    continue
                if now < anim['due']:
                    continue
                anim['due'] = now + anim['interval']
                rgb = colors.palette_at(scene.rgb_palette(), phase + anim['interval'] / scene.period)
                request = {'on': True, 'rgb': list(rgb), 'brightness': anim['level']}
                self._pool.submit(self._living_step, light, request, anim['interval'])
            if pc_frame:
                self.pc.stream(pc_frame)

    def _living_step(self, light, request, interval):
        if light['id'] not in self._living:
            return
        self._take_budget()
        backend = self.hue if light['source'] == 'hue' else self.home
        try:
            backend.call(light, request, transition=max(0.5, interval * 0.95))
        except Exception:
            pass

    def stop_living(self, target=None) -> dict:
        if target is None:
            stopped = len(self._living)
            self._living.clear()
        else:
            ids = [l['id'] for l in self.resolve(target)[0]]
            stopped = sum(self._living.pop(i, None) is not None for i in ids)
        return {'status': 'ok', 'stopped': stopped}

    # ── names, rooms, groups ─────────────────────────────────────────
    def rename(self, light_id: str, name: str) -> dict:
        lights = self.refresh()
        light = lights.get(light_id) or next((l for l in lights.values() if l['ref'] == light_id), None)
        if light is None:
            return {'status': 'error', 'error': 'no such light'}
        name = (name or '').strip()[:60]
        if light['source'] == 'pc':
            result = self.pc.configure(light['ref'], name=name)
        else:
            hub = self.home._ensure()
            readback = hub.rename(light['ref'], name or None)
            result = {'status': 'ok', 'readback': readback}
            self.home.invalidate()
        self.refresh(force=True)
        return result

    def set_room(self, light_id: str, room: Optional[str]) -> dict:
        lights = self.refresh()
        light = lights.get(light_id)
        if light is None or light['source'] == 'pc':
            return {'status': 'error', 'error': 'only home lights have rooms'}
        readback = self.home._ensure().set_area(light['ref'], room or None)
        self.home.invalidate()
        self.refresh(force=True)
        return {'status': 'ok', 'readback': readback}

    def save_group(self, name: str, ids: list[str]) -> dict:
        name = (name or '').strip()[:40]
        if not name:
            return {'status': 'error', 'error': 'a group needs a name'}
        lights = self.refresh()
        ids = [i for i in ids if i in lights]
        groups = dict(self.store.get('groups') or {})
        if ids:
            groups[name] = ids
        else:
            groups.pop(name, None)
        self.store.set('groups', groups)
        return {'status': 'ok', 'group': name, 'lights': ids}

    def identify(self, light_id: str) -> dict:
        light = self.refresh().get(light_id)
        if light is None:
            return {'status': 'error', 'error': 'no such light'}
        if light['source'] == 'pc':
            return self.pc.identify(light['ref'])
        self._take_budget()
        if light['source'] == 'hue':
            self.hue.call(light, {'on': True, 'brightness': 100, 'kelvin': 4000})
            return {'status': 'ok'}
        self.home.call(light, {'on': True, 'flash': 'long'})
        return {'status': 'ok'}

    # ── Hue bridge (direct) ──────────────────────────────────────────
    _pairing: dict = {}

    def hue_status(self) -> dict:
        creds = self.store.hue()
        return {'paired': bool(creds), 'streaming': bool(creds.get('client_key')),
                'host': creds.get('host', ''), 'bridge_id': creds.get('bridge_id', ''),
                'pairing': dict(self._pairing)}

    def hue_discover(self) -> dict:
        from lumen import hue
        try:
            return {'status': 'ok', 'bridges': hue.discover(timeout=3.0)}
        except Exception as exc:
            return {'status': 'error', 'error': str(exc) or type(exc).__name__}

    def hue_pair(self, host: Optional[str] = None, timeout: float = 45.0) -> dict:
        """Start pairing: the owner presses the bridge's round button within `timeout` seconds.

        Runs in the background; hue_status()['pairing'] says waiting → done | failed. The keys go to
        lumen-hue.json (0600) and are never returned."""
        from lumen import hue
        if self._pairing.get('state') == 'waiting':
            return {'status': 'pending', 'pairing': dict(self._pairing)}
        if not host:
            found = hue.discover(timeout=3.0)
            if not found:
                return {'status': 'error', 'error': self._t('ما لقيت جسر Hue على الشبكة', 'No Hue bridge found on the network')}
            host = found[0]['host']
        self._pairing = {'state': 'waiting', 'host': host, 'until': time.time() + timeout}
        cancel = threading.Event()
        self._pair_cancel = cancel

        def run():
            try:
                creds = hue.pair(host, timeout=timeout, cancel=cancel)
                self.store.save_hue(creds)
                self._pairing = {'state': 'done', 'host': host}
            except Exception as exc:
                self._pairing = {'state': 'failed', 'host': host, 'error': str(exc) or type(exc).__name__}
        threading.Thread(target=run, daemon=True, name='lumen-hue-pair').start()
        return {'status': 'pending', 'pairing': dict(self._pairing)}

    def hue_forget(self) -> dict:
        cancel = getattr(self, '_pair_cancel', None)
        if cancel is not None:
            cancel.set()
        self.store.forget_hue()
        self._pairing = {}
        return {'status': 'ok'}

    # ── Screen Sync ──────────────────────────────────────────────────
    def sync_status(self) -> dict:
        prefs = self.store.get('sync') or {}
        if self.sync is None:
            state = {'running': False, 'mode': prefs.get('mode', 'video'), 'state': 'idle'}
        else:
            state = self.sync.status()
        return dict(state, resume_at_login=prefs.get('resume_at_login') is True)

    def sync_resume(self, enabled: bool) -> dict:
        prefs = dict(self.store.get('sync') or {})
        prefs['resume_at_login'] = enabled
        self.store.set('sync', prefs)
        return {'status': 'ok', 'sync': self.sync_status()}

    def sync_start(self, mode: str = 'video', target=None, brightness: Optional[float] = None,
                   select_screen: bool = False) -> dict:
        from lumen.syncsession import SyncSession
        if self.sync is not None:
            self.sync.stop()
            self.sync = None
        if select_screen:
            (self.store.dir / 'lumen-screencast.token').unlink(missing_ok=True)
        prefs = dict(self.store.get('sync') or {})
        wanted = target or prefs.get('target') or 'all'
        targets, unknown = self.resolve(wanted)
        targets = [l for l in targets if l['online'] and (l['caps'].get('color') or l['source'] == 'pc')]
        if norm(str(wanted)) in ALL_N | HOME_N:
            # a lamp behind a cloud service (Tuya's) cannot take several colours a second and the
            # service throttles whoever tries: it follows the screen only when named on purpose
            targets = [l for l in targets if l.get('integration') not in CLOUD_INTEGRATIONS]
        if not targets:
            return {'status': 'error', 'error': self._t('ما في أضواء ملوّنة متاحة', 'No colour lights available')}
        for light in targets:
            self._living.pop(light['id'], None)
        self._scene = None
        prefs.update(mode=mode, target=target or prefs.get('target') or 'all')
        if brightness is not None:
            prefs['brightness'] = max(0.1, min(1.0, float(brightness)))
        self.store.set('sync', prefs)
        self.sync = SyncSession(self, targets, mode=mode, brightness=prefs.get('brightness', 1.0),
                                capture_factory=self.capture_factory, hue_factory=self.hue_factory)
        self.sync.start()
        state = self.sync.status()
        status = 'error' if state.get('state') in ('error', 'denied') else (
            'ok' if state.get('state') == 'running' else 'pending')
        return {'status': status, 'sync': state, 'unknown': unknown, 'error': state.get('error', '')}

    def sync_stop(self) -> dict:
        self.sync_resume(False)
        if self.sync is None:
            return {'status': 'ok', 'running': False}
        self.sync.stop()
        self.sync = None
        return {'status': 'ok', 'running': False}

    # ── helpers ──────────────────────────────────────────────────────
    def _t(self, ar, en):
        return ar if self.lang == 'ar' else en
