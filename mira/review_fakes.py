"""Review fixtures for MIRA_TEST_MODE=1 only: a stand-in Echo and labelled sample data.

They let the interface be rendered and exercised without touching the owner's Echo, Home
Assistant or computer. Nothing here is used by a normal launch.
"""
import math
import sys

from PySide6.QtCore import QObject, QTimer, Signal


class FakeEntity:
    def __init__(self, key, object_id):
        self.key = key
        self.object_id = object_id
        self.device_id = 0


class FakeBridge(QObject):
    connected = Signal(object)
    state = Signal(object)
    error = Signal(str)
    command_state = Signal(str, str)
    voice_state = Signal(str, str)

    def __init__(self, voice_name='Aoede'):
        super().__init__()
        self.online = False
        self.voice_name = voice_name
        self.voice = None
        self.commands = []

    def start(self):
        self.online = True
        entities = [FakeEntity(i, name) for i, name in enumerate(
            ('speaker', 'wake_threshold_1', 'mic_mute', 'setup_page', 'bluetooth_pairing', 'wake_assistant_1'))]
        QTimer.singleShot(50, lambda: self.connected.emit(entities))
        QTimer.singleShot(80, lambda: self.voice_state.emit('wake', 'قل «Mira» ثم سؤالك'))
        QTimer.singleShot(90, lambda: self.voice_state.emit('ready', ''))

    def command(self, *args):
        self.commands.append(args)

    def set_voice(self, value):
        self.commands.append(('voice', value))
        self.voice_state.emit('ready' if value else 'off', '')

    def cancel_voice(self):
        self.commands.append(('cancel',))

    def capture(self, path):
        self.commands.append(('capture', path))

    def wake_config(self):
        import json
        QTimer.singleShot(20, lambda: self.command_state.emit('wake_config', json.dumps(
            {'active': ['mira_ar_experimental'], 'available': {}, 'max': 2})))

    def install_wake_model(self, model_id, phrase, languages, model_file, active):
        self.commands.append(('install_wake_model', model_id, tuple(active)))

    def select_wake_words(self, active):
        self.commands.append(('select_wake_words', tuple(active)))


SAMPLE_DEVICES = [
    {'entity_id': 'light.buro', 'name': 'Büro', 'state': 'on', 'brightness': 180, 'rgb_color': [255, 90, 175],
     'supported_color_modes': ['hs'], 'supported_features': 0},
    {'entity_id': 'light.fancy_wall_light', 'name': 'Wall light', 'state': 'off', 'brightness': None,
     'supported_color_modes': ['hs'], 'supported_features': 0},
    {'entity_id': 'light.desk', 'name': 'Desk lamp', 'state': 'on', 'brightness': 90, 'rgb_color': [255, 210, 150],
     'supported_color_modes': ['brightness'], 'supported_features': 0},
    {'entity_id': 'light.hall', 'name': 'Hall', 'state': 'unavailable', 'supported_color_modes': ['onoff'], 'supported_features': 0},
    {'entity_id': 'media_player.smart_tv_pro_2', 'name': 'TCL Smart TV', 'state': 'on', 'volume_level': 0.2,
     'supported_features': 128 | 256 | 16384 | 1},
    {'entity_id': 'switch.plug', 'name': 'Tuya plug', 'state': 'off', 'supported_features': 0},
]


def stage(controller, window, scene):
    """Put the interface into a named review scene (sample data is visibly sample data)."""
    size = next((a.split('=', 1)[1] for a in sys.argv if a.startswith('--size=')), '')
    if size:
        w, h = (int(x) for x in size.split('x'))
        window.setWidth(w)
        window.setHeight(h)
    lang = next((a.split('=', 1)[1] for a in sys.argv if a.startswith('--lang=')), '')
    if lang:
        controller.setLang(lang)
    face = next((a.split('=', 1)[1] for a in sys.argv if a.startswith('--face=')), '')
    if face:
        controller.setFace(face)

    rows = controller._devices_from(SAMPLE_DEVICES)
    controller.devices.set_rows(rows)
    controller._entities = {r['entity_id']: r for r in rows}
    controller._update('_home', controller.homeChanged, available=5, total=6, lights_on=2, lights_available=3,
                       tv=next(r for r in rows if r['domain'] == 'media_player'), linked=True)
    controller._set_service('home', 'online')
    controller._set_service('moai', 'online')
    controller._weather = {'ok': True, 'city': 'Berlin', 'temp': 14, 'condition': 'غائم جزئياً' if controller.lang == 'ar' else 'Partly cloudy',
                           'code': 2, 'humidity': 71, 'wind': 12, 'is_day': 0, 'updated': '23:40', 'error': ''}
    controller.weatherChanged.emit()
    controller._update('_pc', controller.pcChanged, volume=42, brightness=80,
                       apps=[{'id': 'com.google.Chrome', 'name': 'Google Chrome'}, {'id': 'org.kde.dolphin', 'name': 'Dolphin'},
                             {'id': 'com.visualstudio.code', 'name': 'Visual Studio Code'}, {'id': 'org.kde.konsole', 'name': 'Konsole'}])
    controller._update('_echo', controller.echoChanged, speaker_volume=45, wake_threshold=70)
    if '--empty' not in sys.argv:
        controller.chat.clear()
        for role, text, status in [
            ('user', 'ميرا، كم ضوء مضاء الآن؟', ''),
            ('action', 'أضواء البيت · المتاح 3 · المضاء 2', 'ok'),
            ('mira', 'في ضوءان مضاءان الآن: المكتب باللون الوردي ومصباح الطاولة. بدك أطفيهم؟', ''),
            ('user', 'خلي ضو المكتب بنفسجي', ''),
            ('action', 'تأكدت: Büro · اللون بنفسجي', 'ok'),
            ('mira', 'تمام، صار ضو المكتب بنفسجي ✨', ''),
        ]:
            controller._add(role, text, status=status, persist=False)

    def voice(kind, text=''):
        controller._on_voice(kind, text)

    # The stand-in Echo reports "ready" shortly after start; play the scene after it.
    QTimer.singleShot(400, lambda: play(scene, voice, controller, window))


def play(scene, voice, controller, window):
    if scene in ('listening', 'thinking', 'speaking', 'executing'):
        voice('listening')
        if scene == 'listening':
            voice('partial_heard', 'ميرا شو رأيك نطفي الأضواء ونشغل')
        if scene in ('thinking', 'executing', 'speaking'):
            voice('heard', 'ميرا شو رأيك نطفي الأضواء ونشغّل التلفزيون؟')
            voice('thinking')
        if scene == 'executing':
            voice('executing')
        if scene == 'speaking':
            voice('speaking')
            voice('partial_reply', 'أكيد! أطفأت الأضواء الثلاثة وشغّلت تلفزيون TCL. سهرة حلوة')
        if scene in ('listening', 'speaking'):
            t = {'v': 0.0}

            def pulse():
                t['v'] += 0.07
                value = abs(math.sin(t['v'] * 3.1)) * (0.55 + 0.45 * math.sin(t['v'] * 0.7))
                voice('level', f'{value:.3f}')
            timer = QTimer(controller, interval=66, timeout=pulse)
            timer.start()
    elif scene == 'error':
        voice('error', 'تعذّر الاتصال بالصوت: TimeoutError')
    elif scene in ('home', 'computer', 'settings'):
        QTimer.singleShot(200, lambda: window.setProperty('sheet', scene))
        section = next((a.split('=', 1)[1] for a in sys.argv if a.startswith('--section=')), '')
        if scene == 'settings' and section.isdigit():
            from PySide6.QtCore import QObject

            def pick():
                sheet = window.findChild(QObject, 'settingsSheet')
                if sheet is not None:
                    sheet.setProperty('section', int(section))
            QTimer.singleShot(700, pick)
    elif scene in ('system', 'actions'):
        stage_system(controller)
        if scene == 'system':
            QTimer.singleShot(200, lambda: window.setProperty('sheet', 'system'))
        stage_actions(controller)
    elif scene == 'offline':
        voice('off')


SAMPLE_OS = ('## system image deployments\n'
             'booted: version 44.20260927.952 · signed origin · moos-nvidia@sha256:91c9ce7b\n'
             'kept for rollback: version 44.20260927.945 · signed origin · moos-nvidia@sha256:b09cdc48\n')


def stage_system(controller):
    """The System sheet with sample store results (visibly sample data; nothing is queried)."""
    controller._update('_system', controller.systemChanged, os=SAMPLE_OS, query='vlc', searching=False,
                       health={'status': 'ok', 'moos': {'update_staged_for_restart': False}, 'findings': []},
                       tool='device_report', status='ok',
                       output='Device report (sample)\nGPU: NVIDIA GeForce · driver 580 · loaded\nAudio: PipeWire running\nNetwork: online',
                       apps=[{'id': 'org.videolan.VLC', 'name': 'VLC', 'summary': 'VLC media player, the open-source multimedia player',
                              'installed': False, 'verified': False, 'installs': 104064},
                             {'id': 'org.telegram.desktop', 'name': 'Telegram Desktop', 'summary': 'Fast. Secure. Powerful.',
                              'installed': True, 'verified': True, 'installs': 90000}])


def stage_actions(controller):
    """Three live cards: one waiting for the owner, one running, one finished (sample data)."""
    import time as _time
    now = int(_time.time() * 1000)
    ar = controller.lang == 'ar'
    controller.actions.set_rows([
        {'aid': 'p-sample-ask', 'kind': 'moai', 'name': 'install_app', 'title': 'تثبيت تطبيق' if ar else 'Install an app',
         'detail': 'VLC · org.videolan.VLC', 'reason': '', 'stage': 'ask', 'category': 'user_confirm', 'summary': '',
         'output': '', 'started': 0, 'expires': now + 150000, 'origin': 'mira'},
        {'aid': 'p-sample-run', 'kind': 'moai', 'name': 'system_update', 'title': 'تحديث MoOS' if ar else 'Update MoOS',
         'detail': '', 'reason': '', 'stage': 'running', 'category': 'privileged_confirm',
         'summary': 'يعمل الآن…' if ar else 'Running…', 'output': '', 'started': now - 42000, 'expires': 0, 'origin': 'system'},
        {'aid': 'p-sample-ok', 'kind': 'moai', 'name': 'fix_audio', 'title': 'إصلاح الصوت' if ar else 'Repair sound',
         'detail': '', 'reason': '', 'stage': 'ok', 'category': 'user_confirm',
         'summary': ('تم بنجاح: إصلاح الصوت' if ar else 'Done: Repair sound'), 'output': 'pipewire restarted (sample)',
         'started': now - 90000, 'expires': 0, 'origin': 'mira'},
    ])
