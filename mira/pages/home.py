"""Home — every device in the house, in its room, by the name the owner gives it.

Read from Home Assistant's own registry (homehub): the owner's names, rooms (areas), what each device
can really do, and its live state. A name or a room changed here is changed IN Home Assistant, so
every app, every automation and every later conversation with Mira uses it; a device is never
offered a control it does not support (the TV that has no volume level gets volume steps).

Lights are switched through Lumen (the lighting engine) so a light changed here behaves exactly like
one changed from the Lumen page or by voice. Everything else goes straight to Home Assistant and is
read back before the page says "done".
"""
from __future__ import annotations

import time

from PySide6.QtCore import Property, QTimer, Signal, Slot

from pages.base import Page, TEST_MODE

POLL_MS = 5000

STRINGS = {
    'hm_title': ('البيت', 'Home'),
    'hm_sub': ('كل أجهزة بيتك بغرفها وأسمائها — وميرا بتعرف شو بيقدر يعمل كل جهاز',
               'Every device in your home, by room and by your names — Mira knows what each one can do'),
    'hm_devices': ('أجهزة', 'devices'),
    'hm_online': ('متصل', 'online'),
    'hm_rooms': ('غرف', 'rooms'),
    'hm_no_room': ('بلا غرفة', 'No room'),
    'hm_rename': ('إعادة تسمية', 'Rename'),
    'hm_room': ('الغرفة', 'Room'),
    'hm_move': ('انقل إلى غرفة', 'Move to a room'),
    'hm_new_room': ('غرفة جديدة…', 'New room…'),
    'hm_aliases': ('أسماء ثانية للصوت', 'Other names (voice)'),
    'hm_aliases_hint': ('مثلاً: المكتب، ضو الشغل — افصل بفاصلة', 'e.g. office, desk lamp — separate with commas'),
    'hm_can': ('يقدر', 'Can'),
    'hm_save': ('حفظ', 'Save'),
    'hm_cancel': ('إلغاء', 'Cancel'),
    'hm_saved': ('انحفظ في البيت', 'Saved in your home'),
    'hm_done': ('تم', 'Done'),
    'hm_sent': ('أُرسل، لم يتأكد بعد', 'Sent, not confirmed yet'),
    'hm_failed': ('ما زبط', "Didn't work"),
    'hm_unavailable': ('غير متاح', 'Unavailable'),
    'hm_on': ('يعمل', 'On'),
    'hm_off': ('متوقف', 'Off'),
    'hm_lights_page': ('افتح الإضاءة', 'Open Lighting'),
    'hm_activate': ('شغّل', 'Activate'),
    'hm_vol_up': ('رفع الصوت', 'Volume up'),
    'hm_vol_down': ('خفض الصوت', 'Volume down'),
    'hm_tv_home': ('الرئيسية', 'Home screen'),
    'hm_discovered': ('أجهزة جديدة لقيتها على الشبكة', 'New devices found on your network'),
    'hm_add': ('أضف', 'Add'),
    'hm_link_title': ('اربط بيتك', 'Connect your home'),
    'hm_link_sub': ('ميرا تتحكم بالبيت عبر Home Assistant على هذا الجهاز أو على شبكتك',
                    'Mira controls the house through Home Assistant on this computer or your network'),
    'hm_link_found': ('لقيت Home Assistant على هذا الجهاز — أنشئ رمز وصول طويل الأمد من ملفك الشخصي فيه والصقه هنا',
                      'Found Home Assistant on this computer — create a long-lived access token in its profile page and paste it here'),
    'hm_link_none': ('ما في Home Assistant شغال هلق. شغّله أو أدخل عنوانه.', 'No Home Assistant is running now. Start it or enter its address.'),
    'hm_hub_title': ('خلّي هالكمبيوتر مركز البيت', 'Make this computer your home hub'),
    'hm_hub_sub': ('مركز البيت (Home Assistant) بيكتشف أجهزة بيتك لحاله: Hue والتلفزيونات وChromecast وESPHome وغيرها. تحميل لمرة وحدة حوالي 2.5 GB، وبيشتغل كخدمة لحسابك بدون صلاحيات مدير.',
                   'The home hub (Home Assistant) finds your devices by itself: Hue, TVs, Chromecast, ESPHome and more. A one-time download of about 2.5 GB; it runs as a service of your account, with no administrator rights.'),
    'hm_hub_setup': ('جهّز مركز البيت', 'Set up the home hub'),
    'hm_hub_have': ('عندي Home Assistant', 'I already have Home Assistant'),
    'hm_hub_starting': ('عم يتجهّز مركز البيت… التحميل الأول بياخد كم دقيقة', 'Setting up the home hub… the first download takes a few minutes'),
    'hm_hub_account': ('آخر خطوة: حساب لمركز البيت', 'Last step: an account for the home hub'),
    'hm_hub_account_sub': ('الاسم وكلمة السر بيروحوا لمركز البيت بس — ميرا ما بتحفظهم.', 'The name and password go to the home hub only — Mira keeps neither.'),
    'hm_hub_name': ('اسمك', 'Your name'),
    'hm_hub_user': ('اسم المستخدم', 'User name'),
    'hm_hub_pass': ('كلمة السر (8 أحرف أو أكثر)', 'Password (8 characters or more)'),
    'hm_hub_create': ('أنشئ الحساب واربط', 'Create the account and connect'),
    'hm_token': ('رمز الوصول', 'Access token'),
    'hm_url': ('العنوان', 'Address'),
    'hm_connect': ('اربط', 'Connect'),
    'hm_open_ha': ('افتح Home Assistant', 'Open Home Assistant'),
    'hm_sample': ('بيانات مثال', 'Sample data'),
    'hm_scenes': ('مشاهد', 'Scenes'),
    'hm_kind_light': ('ضوء', 'Light'), 'hm_kind_plug': ('مقبس', 'Plug'), 'hm_kind_switch': ('مفتاح', 'Switch'),
    'hm_kind_tv': ('تلفزيون', 'TV'), 'hm_kind_speaker': ('سماعة', 'Speaker'), 'hm_kind_remote': ('ريموت', 'Remote'),
    'hm_kind_scene': ('مشهد', 'Scene'), 'hm_kind_sensor': ('حسّاس', 'Sensor'), 'hm_kind_fan': ('مروحة', 'Fan'),
    'hm_kind_climate': ('تكييف', 'Climate'), 'hm_kind_cover': ('ستارة', 'Cover'),
}

ICONS = {'light': 'bulb', 'plug': 'power', 'switch': 'power', 'tv': 'tv', 'speaker': 'volume', 'remote': 'grid',
         'scene': 'sparkle', 'sensor': 'pulse', 'fan': 'fan', 'climate': 'sun', 'cover': 'layers', 'button': 'bolt'}


def _hub():
    import homehub
    return homehub.load()


BRANDS = {'signify netherlands b.v.': 'Philips Hue', 'signify': 'Philips Hue', 'philips': 'Philips Hue',
          'tuya': 'Tuya', 'espressif': 'ESPHome'}


def _brand(maker) -> str:
    """A maker as people say it: «Philips Hue», not «Signify Netherlands B.V.»."""
    if not maker:
        return ''
    text = str(maker).strip()
    if text.lower() in BRANDS:
        return BRANDS[text.lower()]
    import re
    return re.sub(r'[,\s]+(?:b\.?v\.?|inc\.?|ltd\.?|co\.?|gmbh|llc|corp\.?|corporation)\b.*$', '', text, flags=re.I).strip()


def _level(current: dict) -> int:
    for key in ('brightness', 'volume', 'percentage', 'position'):
        value = current.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return int(value)
    return -1


def _row(rec: dict, lang: str) -> dict:
    caps = rec.get('caps') or {}
    kind = rec.get('kind') or rec.get('domain')
    return {
        'entity_id': rec['entity_id'], 'domain': rec.get('domain'), 'kind': kind,
        'icon': ICONS.get(kind, 'sparkle'), 'name': rec.get('name') or rec['entity_id'],
        'default_name': rec.get('default_name') or '', 'renamed': bool(rec.get('renamed')),
        'room': rec.get('area') or '', 'aliases': list(rec.get('aliases') or []),
        'state': rec.get('state') or '', 'available': bool(rec.get('available')),
        'on': rec.get('state') in ('on', 'playing', 'paused', 'idle', 'home', 'open', 'heat', 'cool', 'auto')
              and bool(rec.get('available')),
        'group': bool(rec.get('is_group')), 'members': len(rec.get('members') or []),
        'summary': rec.get('summary_ar' if lang == 'ar' else 'summary_en') or '',
        'detail': ' · '.join(x for x in (_brand(rec.get('manufacturer')), rec.get('model')) if x),
        'power': bool(caps.get('power')),
        'volume_step': bool(caps.get('volume_step') or caps.get('volume_set')),
        'activate': bool(caps.get('activate') or caps.get('press') or caps.get('run')),
        'level': _level(caps.get('current') or {}),
        'value': str(caps.get('value') or '') if caps.get('read_only') else '',
        'unit': caps.get('unit') or '',
    }


class HomePage(Page):
    # Rooms (with their device cards) and areas are their own properties, emitted only when they
    # change: through `state` every 5 s poll rebuilt every card (see pages/lumen.py).
    roomsChanged = Signal()
    areasChanged = Signal()
    rooms = Property('QVariantList', lambda self: self._lists['rooms'], notify=roomsChanged)
    areas = Property('QVariantList', lambda self: self._lists['areas'], notify=areasChanged)

    def _set_list(self, name, value):
        if self._lists.get(name) != value:
            self._lists[name] = value
            getattr(self, name + 'Changed').emit()

    def __init__(self, host, parent=None):
        self._lists = {'rooms': [], 'areas': []}
        super().__init__(host, parent)
        self._timer = QTimer(self)
        self._timer.setInterval(POLL_MS)
        self._timer.timeout.connect(self.refresh)
        self._reading = False
        self._seq = 0
        changed = getattr(host, 'langChanged', None)
        if changed is not None:
            changed.connect(self.refresh)

    def initial(self):
        return {'ready': False, 'linked': None, 'error': '', 'devices': [], 'discovered': [], 'counts': {},
                'probe': {}, 'busy': '', 'note': {}, 'sample': False}

    # ── lifecycle ────────────────────────────────────────────────────
    def activated(self):
        if TEST_MODE:
            return
        self.refresh()
        self._timer.start()

    @Slot()
    def hidden(self):
        self._timer.stop()

    @Slot()
    def resume(self):
        if TEST_MODE:
            return
        self._timer.start()
        self.refresh()

    @Slot()
    def refresh(self):
        if self._reading:
            return
        self._reading = True
        self.run('read', self._read)

    def _read(self):
        import homehub
        hub = homehub.load()
        if hub is None:
            import homesetup
            return {'status': 'unlinked', 'probe': homehub.probe(timeout=1.5), 'hub': homesetup.status()}
        records = hub.inventory(include_hidden=False)
        areas = hub.areas()
        try:
            discovered = hub.discovered()
        except Exception:
            discovered = []
        return {'status': 'ok', 'records': records, 'areas': areas, 'discovered': discovered, 'url': hub.url}

    def on_read(self, tag, result):
        self._reading = False
        status = result.get('status')
        if status == 'unlinked':
            self._set_list('rooms', [])
            hub = result.get('hub') or {}
            self.update(ready=True, linked=False, probe=result.get('probe') or {}, devices=[], hub=hub)
            # while the hub downloads and starts, read again soon; the regular poll is slower
            if hub.get('stage') in ('installed', 'starting') and not TEST_MODE:
                QTimer.singleShot(3000, self.refresh)
            return
        if status != 'ok':
            self.update(ready=True, linked=True, error=result.get('error') or 'error')
            return
        rows = [_row(r, self.lang) for r in result['records']]
        rooms: dict[str, dict] = {}
        for row in rows:
            name = row['room'] or ''
            room = rooms.setdefault(name, {'name': name, 'devices': [], 'online': 0, 'on': 0})
            room['devices'].append(row)
            room['online'] += row['available']
            room['on'] += row['on']
        ordered = sorted(rooms.values(), key=lambda r: (r['name'] == '', r['name'].casefold()))
        self._set_list('rooms', ordered)
        self._set_list('areas', [{'id': a.get('area_id'), 'name': a.get('name')} for a in result.get('areas') or []])
        fields = dict(ready=True, linked=True, error='', devices=rows,
                      discovered=[{'domain': d.get('domain'), 'title': d.get('title') or d.get('domain')}
                                  for d in result.get('discovered') or []],
                      url=result.get('url') or '',
                      counts={'devices': len(rows), 'online': sum(r['available'] for r in rows),
                              'rooms': len([r for r in ordered if r['name']])})
        if any(self._state.get(k) != v for k, v in fields.items()):
            self.update(**fields)

    # ── doing ────────────────────────────────────────────────────────
    def _act(self, label, fn, *args):
        self._seq += 1
        self.update(busy=label)
        self.run('act:%d' % self._seq, fn, *args)

    def on_act(self, tag, result):
        status = result.get('status', 'error')
        key = {'ok': 'hm_done', 'saved': 'hm_saved', 'pending': 'hm_sent'}.get(status, 'hm_failed')
        text = self.text(key)
        if status == 'error' and result.get('error'):
            text += ' — ' + str(result['error'])[:120]
        self.update(busy='', note={'status': 'ok' if status in ('ok', 'saved') else
                                   ('error' if status == 'error' else 'pending'), 'text': text, 'at': time.time()})
        self.refresh()

    @staticmethod
    def _rename(entity_id, name):
        hub = _hub()
        back = hub.rename(entity_id, name or None)
        if name and back.get('name') != name:
            return {'status': 'pending'}
        return {'status': 'saved', 'readback': back}

    @Slot(str, str)
    def rename(self, entity_id, name):
        self._act('rename:' + entity_id, self._rename, str(entity_id), str(name).strip()[:60])

    @staticmethod
    def _move(entity_id, room):
        back = _hub().set_area(entity_id, room or None)
        return {'status': 'saved', 'readback': back}

    @Slot(str, str)
    def moveTo(self, entity_id, room):
        self._act('room:' + entity_id, self._move, str(entity_id), str(room).strip()[:40])

    @staticmethod
    def _aliases(entity_id, text):
        names = [n.strip() for n in text.replace('،', ',').split(',') if n.strip()][:8]
        _hub().set_aliases(entity_id, names)
        return {'status': 'saved'}

    @Slot(str, str)
    def setAliases(self, entity_id, text):
        self._act('aliases:' + entity_id, self._aliases, str(entity_id), str(text))

    @staticmethod
    def _power(entity_id, on):
        domain = entity_id.split('.', 1)[0]
        if domain == 'light':
            from lumen import client
            result = client.request('set', target=[entity_id], on=bool(on))
            return {'status': result.get('status', 'error'), 'error': result.get('error')}
        hub = _hub()
        hub.call(domain if domain != 'scene' else 'scene', 'turn_on' if on else 'turn_off', {'entity_id': entity_id})
        want = 'on' if on else 'off'
        for _ in range(12):
            time.sleep(0.4)
            if hub.state(entity_id).get('state') == want:
                return {'status': 'ok'}
        return {'status': 'pending'}

    @Slot(str, bool)
    def setPower(self, entity_id, on):
        self._act('power:' + entity_id, self._power, str(entity_id), bool(on))

    @staticmethod
    def _press(entity_id, what):
        hub = _hub()
        domain = entity_id.split('.', 1)[0]
        if what == 'activate' and domain in ('scene', 'script', 'button'):
            hub.call(domain, 'press' if domain == 'button' else 'turn_on', {'entity_id': entity_id})
            return {'status': 'ok'}
        if what in ('volume_up', 'volume_down') and domain == 'media_player':
            hub.call('media_player', what, {'entity_id': entity_id})
            return {'status': 'ok'}
        if what == 'home' and domain == 'media_player':
            remotes = [r for r in hub.inventory() if r['entity_id'].startswith('remote.')]
            if remotes:
                hub.call('remote', 'send_command', {'entity_id': remotes[0]['entity_id'], 'command': 'HOME'})
                return {'status': 'ok'}
        return {'status': 'error', 'error': 'unsupported'}

    @Slot(str, str)
    def press(self, entity_id, what):
        self._act('press:' + entity_id, self._press, str(entity_id), str(what))

    @staticmethod
    def _link(token, url):
        import homehub
        homehub.save(token.strip(), url.strip() or None)
        hub = homehub.load()
        if hub is None:
            return {'status': 'error', 'error': 'token'}
        hub.states()
        return {'status': 'saved'}

    @Slot(str, str)
    def link(self, token, url):
        self._act('link', self._link, str(token), str(url))

    @staticmethod
    def _setup():
        import homesetup
        result = homesetup.install()
        return {'status': 'pending', **result}

    @Slot()
    def setupHub(self):
        """The owner's button: make this computer the home hub (Home Assistant, his own container)."""
        self._act('hub', self._setup)

    @staticmethod
    def _onboard(name, username, password):
        import homesetup
        homesetup.onboard(name, username, password)
        return {'status': 'saved'}

    @Slot(str, str, str)
    def onboard(self, name, username, password):
        self._act('onboard', self._onboard, str(name), str(username), str(password))

    @Slot()
    def openHomeAssistant(self):
        url = self._state.get('url') or (self._state.get('probe') or {}).get('url') or 'http://127.0.0.1:8123'
        try:
            self.host.openUrl(url)
        except Exception:
            pass

    @Slot()
    def openLumen(self):
        self.host.showSheet.emit('lumen')

    # ── review renders (MIRA_TEST_MODE=1) ─────────────────────────────
    def review(self):
        ar = self.lang == 'ar'
        sample = [
            ('light.office', 'المكتب', 'الصالون', 'light', 'on', 'ضوء ملوّن · سطوع · حرارة بيضاء 2000–6500K · تأثيرات: شمعة، نار +8', ['بيرو', 'ضو الشغل']),
            ('light.tv_left', 'يسار التلفزيون', 'الصالون', 'light', 'on', 'ضوء ملوّن · سطوع · حرارة بيضاء', []),
            ('media_player.tv', 'تلفزيون TCL', 'الصالون', 'tv', 'on', 'تلفزيون · تشغيل وإطفاء · رفع الصوت وخفضه · كتم', ['التلفزيون']),
            ('scene.relax', 'استرخاء', 'الصالون', 'scene', 'scening', 'مشهد · تشغيل', []),
            ('light.wall', 'ضو الحيط', 'غرفة النوم', 'light', 'off', 'ضوء ملوّن · سطوع', []),
            ('switch.plug', 'قابس السخان', 'المطبخ', 'plug', 'unavailable', 'مقبس ذكي · تشغيل وإطفاء', []),
            ('sensor.temp', 'حرارة الغرفة', 'غرفة النوم', 'sensor', '21.5', 'حسّاس حرارة · °C', []),
        ]
        rows = []
        for eid, name, room, kind, state, summary, aliases in sample:
            rows.append({'entity_id': eid, 'domain': eid.split('.')[0], 'kind': kind, 'icon': ICONS.get(kind, 'sparkle'),
                         'name': name, 'default_name': 'Hue lamp' if kind == 'light' else '', 'renamed': True,
                         'room': room, 'aliases': aliases, 'state': state, 'available': state != 'unavailable',
                         'on': state == 'on', 'group': False, 'members': 0, 'summary': summary,
                         'detail': 'Signify · LCA001' if kind == 'light' else ('TCL · Android TV' if kind == 'tv' else ''),
                         'power': kind in ('light', 'plug', 'tv'), 'volume_step': kind == 'tv',
                         'activate': kind == 'scene', 'value': state if kind == 'sensor' else '',
                         'level': 80 if state == 'on' and kind == 'light' else -1, 'unit': '°C' if kind == 'sensor' else ''})
        rooms = {}
        for row in rows:
            r = rooms.setdefault(row['room'], {'name': row['room'], 'devices': [], 'online': 0, 'on': 0})
            r['devices'].append(row)
            r['online'] += row['available']
            r['on'] += row['on']
        self._set_list('rooms', list(rooms.values()))
        self._set_list('areas', [{'id': n, 'name': n} for n in rooms])
        self.update(ready=True, linked=True, sample=True, devices=rows,
                    discovered=[{'domain': 'wled', 'title': 'WLED Strip' if not ar else 'شريط WLED'}],
                    counts={'devices': len(rows), 'online': 6, 'rooms': 3})


PAGE = HomePage
