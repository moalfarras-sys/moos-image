"""Lumen — every light in the house and in the computer, as one page.

The page is a window onto the Lumen engine (`lumen/`, its own user service, so lights keep
following the screen and living scenes keep moving when Mira's window is closed). Everything it
shows is the engine's read-back: Home Assistant's own state for a lamp, the controller's
acknowledgement for the PC's headers (which cannot be read back, and the page says so).

The owner picks lights the way he thinks of them — all of them, a room, a group, one lamp, the PC —
and every control (power, colour, white, brightness, effect, scene, Screen Sync) acts on that pick.
"""
from __future__ import annotations

import colorsys
import time

from PySide6.QtCore import Property, QTimer, Signal, Slot

from pages.base import Page, TEST_MODE

POLL_MS = 2500
SYNC_POLL_MS = 350

STRINGS = {
    'lu_title': ('لومِن · الإضاءة', 'Lumen · Lighting'),
    'lu_sub': ('كل أضواء البيت والكمبيوتر بمكان واحد — مشاهد، ألوان، ومزامنة مع الشاشة',
               'Every light in the house and the computer — scenes, colour and screen sync'),
    'lu_all': ('الكل', 'All'),
    'lu_pc': ('الكمبيوتر', 'PC'),
    'lu_on': ('تشغيل', 'On'),
    'lu_off': ('إطفاء', 'Off'),
    'lu_lights_on': ('مضاء', 'on'),
    'lu_of': ('من', 'of'),
    'lu_selected': ('المختار', 'Selected'),
    'lu_selected_n': ('أضواء مختارة', 'lights selected'),
    'lu_select_hint': ('اختر ضوءاً أو غرفة، أو اترك «الكل»', 'Pick a light or a room, or keep “All”'),
    'lu_color': ('اللون', 'Colour'),
    'lu_white': ('أبيض', 'White'),
    'lu_warm': ('دافئ', 'Warm'),
    'lu_cool': ('بارد', 'Cool'),
    'lu_brightness': ('السطوع', 'Brightness'),
    'lu_effects': ('تأثيرات', 'Effects'),
    'lu_effect_none': ('بلا تأثير', 'No effect'),
    'lu_scenes': ('المشاهد', 'Scenes'),
    'lu_scenes_sub': ('مزاج كامل للغرفة: كل ضوء يأخذ لوناً من اللوحة', 'A mood for the room: each light takes a colour of the palette'),
    'lu_living': ('حيّ', 'Living'),
    'lu_stop_living': ('أوقف الحركة', 'Stop motion'),
    'lu_sync': ('مزامنة الشاشة', 'Screen Sync'),
    'lu_sync_sub': ('الأضواء تتبع ما يظهر على الشاشة — أفلام، ألعاب، أي شي', 'Lights follow what is on the screen — films, games, anything'),
    'lu_sync_start': ('ابدأ المزامنة', 'Start sync'),
    'lu_sync_stop': ('أوقف المزامنة', 'Stop sync'),
    'lu_mode_video': ('فيديو', 'Video'),
    'lu_mode_game': ('ألعاب', 'Games'),
    'lu_mode_ambient': ('هادئ', 'Ambient'),
    'lu_sync_asking': ('وافق على مشاركة الشاشة في النافذة الظاهرة (مرة واحدة فقط)', 'Approve the screen share in the dialog (only once)'),
    'lu_sync_running': ('تتبع الشاشة', 'Following the screen'),
    'lu_sync_denied': ('رُفضت مشاركة الشاشة', 'Screen sharing was declined'),
    'lu_fps': ('إطار/ث', 'fps'),
    'lu_stream_hue': ('بث Hue مباشر', 'Hue live stream'),
    'lu_stream_ha': ('عبر Home Assistant', 'Through Home Assistant'),
    'lu_hue_pair': ('اربط جسر Hue', 'Pair the Hue bridge'),
    'lu_hue_pair_sub': ('لمزامنة أسرع وأنعم: اضغط الزر الدائري على الجسر ثم اضغط هنا',
                        'For faster, smoother sync: press the round button on the bridge, then tap here'),
    'lu_hue_waiting': ('اضغط الزر الدائري على جسر Hue الآن…', 'Press the round button on the Hue bridge now…'),
    'lu_hue_done': ('اترابط جسر Hue — المزامنة صارت بث مباشر', 'Hue bridge paired — sync now streams live'),
    'lu_hue_failed': ('ما انضغط الزر بالوقت. جرّب مرة ثانية.', 'The button was not pressed in time. Try again.'),
    'lu_hue_paired': ('جسر Hue مربوط', 'Hue bridge paired'),
    'lu_pc_title': ('إضاءة الكمبيوتر', 'PC Glow'),
    'lu_pc_sub': ('مراوح الكيس والشرائط الموصولة باللوحة الأم', 'Case fans and strips on the motherboard'),
    'lu_pc_none': ('ما في وحدة إضاءة معروفة على هذا الجهاز', 'No known lighting controller on this computer'),
    'lu_pc_note': ('هذه المنافذ لا تُقرأ: «تم» تعني أن وحدة التحكم استلمت الأمر', 'These headers cannot be read back: “done” means the controller accepted it'),
    'lu_identify': ('حدّد', 'Identify'),
    'lu_identify_tip': ('يومض المنفذ بالأبيض لتعرف أي مراوح هي', 'Flashes the header white so you can see which fans it is'),
    'lu_rename': ('إعادة تسمية', 'Rename'),
    'lu_save': ('حفظ', 'Save'),
    'lu_cancel': ('إلغاء', 'Cancel'),
    'lu_leds': ('عدد الليدات', 'LEDs'),
    'lu_fx_static': ('ثابت', 'Static'),
    'lu_fx_breathe': ('تنفّس', 'Breathe'),
    'lu_fx_flash': ('وميض', 'Flash'),
    'lu_fx_cycle': ('دوران الألوان', 'Colour cycle'),
    'lu_fx_wave': ('موجة', 'Wave'),
    'lu_offline': ('غير متاح', 'Unavailable'),
    'lu_unreachable': ('ما قدرت أوصل لمحرك الإضاءة', "Can't reach the lighting engine"),
    'lu_unreachable_hint': ('عم حاول شغّله… إذا ضل هيك افتح «النظام» وشغّل فحص الصحة.', "Trying to start it… if this stays, run a health check in System."),
    'lu_home_unlinked': ('البيت غير مربوط — أضواء الكمبيوتر فقط', 'Home not linked — PC lights only'),
    'lu_done': ('تم', 'Done'),
    'lu_partial': ('تم جزئياً', 'Partly done'),
    'lu_sent': ('أُرسل، لم يتأكد بعد', 'Sent, not confirmed yet'),
    'lu_failed': ('ما زبط', "Didn't work"),
    'lu_sample': ('بيانات مثال', 'Sample data'),
    'lu_rooms': ('الغرف والمجموعات', 'Rooms and groups'),
    'lu_no_room': ('بلا غرفة', 'No room'),
    'lu_new_group': ('احفظ المختار كمجموعة', 'Save selection as a group'),
    'lu_group_name': ('اسم المجموعة', 'Group name'),
}

FX = ['static', 'breathe', 'flash', 'cycle', 'wave']
HUE_FX_AR = {'candle': 'شمعة', 'fire': 'نار', 'prism': 'منشور', 'sparkle': 'لمعان', 'opal': 'أوبال',
             'glisten': 'بريق', 'underwater': 'تحت الماء', 'cosmos': 'كون', 'sunbeam': 'شعاع شمس',
             'enchant': 'سحر', 'sunrise': 'شروق', 'sunset': 'غروب'}


def _client():
    from lumen import client
    return client


def _display(light: dict) -> dict:
    """What the page paints for one light: its colour, how bright, and words for its state."""
    st = light.get('state') or {}
    on = bool(st.get('on')) and light.get('online', True)
    rgb = st.get('rgb')
    if not rgb and st.get('kelvin'):
        from lumen.colors import kelvin_to_rgb
        rgb = list(kelvin_to_rgb(st['kelvin']))
    if not rgb:
        rgb = [255, 196, 120] if on else [90, 98, 130]
    level = st.get('brightness')
    level = 100 if level is None and on else (level or 0)
    h, s, v = colorsys.rgb_to_hsv(*(c / 255 for c in rgb))
    # paint the hue at full value: brightness is shown by the glow, not by a muddy colour
    r, g, b = colorsys.hsv_to_rgb(h, s, 1.0 if v > 0 else 0)
    out = dict(light)
    out['hex'] = '#%02X%02X%02X' % (int(r * 255), int(g * 255), int(b * 255))
    out['on'] = on
    out['level'] = int(level)
    return out


class LumenPage(Page):
    # The long lists live in their own properties, each with its own signal, emitted only when the
    # list really changed: a Repeater given a new array rebuilds every delegate, and through `state`
    # every 2.5 s poll and every 350 ms sync preview rebuilt all the orbs and scene cards (measured
    # 2026-10-03: the open page cost ~8 % of a core while nothing changed).
    lightsChanged = Signal()
    roomsChanged = Signal()
    groupsChanged = Signal()
    scenesChanged = Signal()
    syncChanged = Signal()

    def _set_list(self, name, value):
        if self._lists.get(name) != value:
            self._lists[name] = value
            getattr(self, name + 'Changed').emit()

    lights = Property('QVariantList', lambda self: self._lists['lights'], notify=lightsChanged)
    rooms = Property('QVariantList', lambda self: self._lists['rooms'], notify=roomsChanged)
    groups = Property('QVariantList', lambda self: self._lists['groups'], notify=groupsChanged)
    scenes = Property('QVariantList', lambda self: self._lists['scenes'], notify=scenesChanged)
    sync = Property('QVariantMap', lambda self: self._lists['sync'], notify=syncChanged)

    def __init__(self, host, parent=None):
        self._lists = {'lights': [], 'rooms': [], 'groups': [], 'scenes': [], 'sync': {'running': False, 'mode': 'video'}}
        super().__init__(host, parent)
        self._timer = QTimer(self)
        self._timer.setInterval(POLL_MS)
        self._timer.timeout.connect(self._poll)
        self._sync_timer = QTimer(self)
        self._sync_timer.setInterval(SYNC_POLL_MS)
        self._sync_timer.timeout.connect(self._poll_sync)
        self._reading = False
        self._sync_reading = False
        self._seq = 0
        changed = getattr(host, 'langChanged', None)
        if changed is not None:
            changed.connect(lambda: self.refresh())

    def initial(self):
        return {'ready': False, 'error': '', 'counts': {}, 'scene': None, 'pc': {}, 'hue': {},
                'home': {}, 'busy': '', 'note': {}, 'sample': False, 'fx': FX}

    # ── lifecycle ────────────────────────────────────────────────────
    def activated(self):
        if TEST_MODE:
            return
        self.refresh()
        self._timer.start()

    @Slot()
    def hidden(self):
        self._timer.stop()
        self._sync_timer.stop()

    @Slot()
    def resume(self):
        if TEST_MODE:
            return
        self._timer.start()
        self.refresh()

    def _poll(self):
        self.refresh()

    @Slot()
    def refresh(self):
        if self._reading:
            return
        self._reading = True
        self.run('snapshot', lambda: _client().request('snapshot', lang=self.lang, timeout=10))

    def on_snapshot(self, tag, result):
        self._reading = False
        if result.get('status') != 'ok':
            self.update(error=result.get('error') or 'error', ready=self._state.get('ready', False))
            return
        lights = [_display(l) for l in result.get('lights', [])]
        for light in lights:
            light['effect_names'] = [{'id': e, 'name': HUE_FX_AR.get(e, e) if self.lang == 'ar' else e}
                                     for e in (light.get('caps') or {}).get('effects', [])]
        sync = result.get('sync') or {}
        self._set_list('lights', lights)
        self._set_list('rooms', result.get('rooms', []))
        self._set_list('groups', result.get('groups', []))
        self._set_list('scenes', result.get('scenes', []))
        self._set_list('sync', sync)
        fields = dict(ready=True, error='', counts=result.get('counts', {}), scene=result.get('scene'),
                      pc=result.get('pc', {}), hue=result.get('hue', {}), home=result.get('home', {}))
        if any(self._state.get(k) != v for k, v in fields.items()):
            self.update(**fields)
        if sync.get('running'):
            if not self._sync_timer.isActive():
                self._sync_timer.start()
        else:
            self._sync_timer.stop()

    def _poll_sync(self):
        if self._sync_reading:
            return
        self._sync_reading = True
        self.run('syncstat', lambda: _client().request('sync_status', timeout=3))

    def on_syncstat(self, tag, result):
        self._sync_reading = False
        if result.get('status') == 'ok':
            sync = result.get('sync') or {}
            self._set_list('sync', sync)
            if not sync.get('running'):
                self._sync_timer.stop()

    # ── doing ────────────────────────────────────────────────────────
    def _act(self, label, op, **args):
        self._seq += 1
        self.update(busy=label)
        self.run('act:%d:%s' % (self._seq, label), lambda: _client().request(op, timeout=20, **args))

    def on_act(self, tag, result):
        self.update(busy='')
        status = result.get('status', 'error')
        words = {'ok': 'lu_done', 'partial': 'lu_partial', 'pending': 'lu_sent'}.get(status, 'lu_failed')
        text = self.text(words)
        if result.get('total'):
            text += ' · %d/%d' % (result.get('confirmed', 0), result['total'])
        if status == 'error' and result.get('error'):
            text += ' — ' + str(result['error'])[:120]
        self.update(note={'status': 'ok' if status == 'ok' else ('error' if status == 'error' else 'pending'),
                          'text': text, 'at': time.time()})
        if 'sync' in result and isinstance(result['sync'], dict):
            self._set_list('sync', result['sync'])
            if result['sync'].get('running'):
                self._sync_timer.start()
        self.refresh()

    @staticmethod
    def _target(ids):
        ids = [str(i) for i in (ids or []) if i]
        return ids or 'all'

    @Slot('QVariantList', bool)
    def setPower(self, ids, on):
        self._act('power', 'set', target=self._target(ids), on=bool(on))

    @Slot('QVariantList', str)
    def setColor(self, ids, hex_colour):
        self._act('color', 'set', target=self._target(ids), color=str(hex_colour))

    @Slot('QVariantList', int)
    def setWhite(self, ids, kelvin):
        self._act('white', 'set', target=self._target(ids), kelvin=int(kelvin))

    @Slot('QVariantList', int)
    def setBrightness(self, ids, value):
        self._act('brightness', 'set', target=self._target(ids), brightness=max(0, min(100, int(value))))

    @Slot('QVariantList', str)
    def setEffect(self, ids, effect):
        self._act('effect', 'set', target=self._target(ids), effect=str(effect) or 'none')

    @Slot(str, 'QVariantList')
    def applyScene(self, scene_id, ids):
        self._act('scene:' + scene_id, 'scene', name=str(scene_id), target=self._target(ids))

    @Slot()
    def stopLiving(self):
        self._act('living', 'stop_living')

    @Slot(str, 'QVariantList')
    def startSync(self, mode, ids):
        self._act('sync', 'sync_start', mode=str(mode or 'video'), target=self._target(ids))

    @Slot()
    def stopSync(self):
        self._act('sync', 'sync_stop')

    @Slot(str, str)
    def rename(self, light_id, name):
        self._act('rename', 'rename', id=str(light_id), name=str(name))

    @Slot(str)
    def identify(self, light_id):
        self._act('identify', 'identify', id=str(light_id))

    @Slot(str, int)
    def setLeds(self, zone, leds):
        self._act('leds', 'pc_configure', zone=str(zone), leds=int(leds))

    @Slot(str, 'QVariantList')
    def saveGroup(self, name, ids):
        self._act('group', 'save_group', name=str(name), ids=[str(i) for i in ids or []])

    @Slot()
    def pairHue(self):
        self._act('hue', 'hue_pair')

    @Slot()
    def forgetHue(self):
        self._act('hue', 'hue_forget')

    # ── review renders (MIRA_TEST_MODE=1) ─────────────────────────────
    def review(self):
        from lumen import scenes
        lights = []
        sample = [
            ('ha:light.office', 'المكتب', 'الصالون', True, [155, 100, 255], 80, ['candle', 'fire', 'prism']),
            ('ha:light.tv_left', 'يسار التلفزيون', 'الصالون', True, [40, 215, 245], 70, ['candle', 'fire']),
            ('ha:light.tv_right', 'يمين التلفزيون', 'الصالون', True, [255, 80, 170], 70, ['candle', 'fire']),
            ('ha:light.floor', 'الأرضية', 'الصالون', False, None, 0, []),
            ('ha:light.wall', 'ضو الحيط', 'غرفة النوم', True, [255, 160, 60], 35, []),
            ('ha:light.strip', 'شريط RGB', 'غرفة النوم', None, None, 0, []),
            ('pc:D_LED1', 'مراوح الواجهة', 'PC', True, [155, 100, 255], 100, []),
            ('pc:D_LED2', 'المروحة الخلفية', 'PC', True, [53, 216, 244], 100, []),
            ('pc:LED_C1', 'شريط RGB 1', 'PC', False, None, 0, []),
        ]
        for lid, name, room, on, rgb, level, fx in sample:
            source = 'pc' if lid.startswith('pc:') else 'home'
            lights.append(_display({
                'id': lid, 'ref': lid.split(':', 1)[1], 'name': name, 'room': room, 'source': source,
                'kind': 'pc' if source == 'pc' else 'lamp', 'online': on is not None, 'group': False, 'members': [],
                'detail': 'Philips Hue · LCA001' if source == 'home' else 'ARGB 5V · ' + lid[3:],
                'caps': {'power': True, 'brightness': True, 'color': True, 'temp': [2000, 6500],
                         'effects': fx, 'stream': 'pc' if source == 'pc' else None,
                         'leds': 32 if source == 'pc' else 1, 'readback': source != 'pc'},
                'state': {'on': bool(on), 'brightness': level, 'rgb': rgb, 'kelvin': None, 'effect': None},
            }))
        for light in lights:
            light['effect_names'] = [{'id': e, 'name': HUE_FX_AR.get(e, e) if self.lang == 'ar' else e}
                                     for e in light['caps']['effects']]
        rooms = {}
        for light in lights:
            r = rooms.setdefault(light['room'], {'name': light['room'], 'lights': [], 'on': 0, 'online': 0})
            r['lights'].append(light['id'])
            r['on'] += light['on']
            r['online'] += light['online']
        self._set_list('lights', lights)
        self._set_list('rooms', list(rooms.values()))
        self._set_list('groups', [{'id': 'group:السهرة', 'name': 'السهرة', 'kind': 'owner',
                                   'lights': ['ha:light.tv_left', 'ha:light.tv_right', 'pc:D_LED1']}])
        self._set_list('scenes', scenes.catalog(self.lang))
        self._set_list('sync', {'running': True, 'mode': 'video', 'state': 'running', 'fps': 30, 'stream': 'ha',
                                'lights': ['ha:light.tv_left', 'ha:light.tv_right', 'pc:D_LED1'],
                                'preview': {'ha:light.tv_left': '#2C7BFF', 'ha:light.tv_right': '#FF5A3C',
                                            'pc:D_LED1': '#8E5BFF'}, 'ambient': '#8E5BFF'})
        self.update(ready=True, sample=True,
                    scene={'id': 'aurora', 'name': 'شفق' if self.lang == 'ar' else 'Aurora'},
                    counts={'lights': 9, 'online': 8, 'on': 6, 'pc': 3},
                    pc={'present': True, 'maker': 'Gigabyte RGB Fusion 2', 'product': 'IT5701', 'firmware': '3.0.27.0'},
                    hue={'paired': False, 'streaming': False},
                    home={'linked': True})


PAGE = LumenPage
