"""The one object QML talks to. It owns Mira's state and routes every request to a real backend.

Nothing here claims a result it did not observe: Home actions report Home Assistant's readback,
computer actions report Mo AI's executor status, voice reports what the Echo session did.
"""
import json
import os
import re
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, Property, QSettings, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices, QGuiApplication

import i18n
from models import DictListModel

ROOT = Path(__file__).resolve().parent
TEST_MODE = os.environ.get('MIRA_TEST_MODE') == '1'
FALLBACK_MIC = 'alsa_input.usb-Linux_Foundation_Webcam_gadget-02.mono-fallback'
ACTIVE = ('activating', 'listening', 'thinking', 'executing', 'speaking')
ENROL_DIR = Path.home() / '.local/share/mira/wake-enrol'      # the owner's voice samples (0700/0600)
WAKE_MODELS = Path.home() / '.local/share/mira/wake-models'   # models trained here, served to the Echo
OWNER_MODEL = 'mira_ar_owner'
FALLBACK_WAKE = ['mira_ar_experimental']   # Mira only, by the owner's choice (2026-09-29)


def _prop(kind, attr, signal):
    return Property(kind, lambda self: getattr(self, attr), notify=signal)


def mood_for(text, status='ok'):
    """A light, honest reading of how Mira's reply sounds, for her expression only."""
    t = (text or '').lower()
    if status == 'error' or any(w in t for w in ('عذر', 'آسف', 'اسف', 'تعذ', 'لم أتمكن', 'لم اتمكن', 'للأسف',
                                                  'sorry', "couldn't", 'could not', 'unable')):
        return 'sad'
    if any(w in t for w in ('هه', '😂', '😄', 'نكتة', 'haha', 'joke')):
        return 'playful'
    if any(w in t for w in ('واو', 'رائع', 'مذهل', 'ممتاز', 'wow', 'amazing', 'awesome', '!')):
        return 'excited'
    if any(w in t for w in ('تم', 'شغّلت', 'شغلت', 'أطفأت', 'فتحت', 'حفظت', 'تأكدت', 'done', 'turned', 'opened', 'saved')):
        return 'proud'
    if any(w in t for w in ('أهلا', 'اهلا', 'مرحب', 'شكر', 'حبيب', 'تكرم', 'hello', 'hi ', 'thank')):
        return 'happy'
    if t.rstrip().endswith(('?', '؟')):
        return 'curious'
    return 'reassuring' if len(t) > 160 else 'happy'


class Worker(QObject):
    """Runs a blocking call on a thread and hands the result back on the Qt thread."""
    done = Signal(str, object)

    def run(self, tag, fn, *args, **kwargs):
        def work():
            try:
                result = fn(*args, **kwargs)
            except Exception as exc:  # the backend's message, never a traceback
                result = {'status': 'error',
                          'error': str(exc) if isinstance(exc, (ValueError, RuntimeError)) else type(exc).__name__}
            self.done.emit(tag, result)
        threading.Thread(target=work, daemon=True).start()


class Controller(QObject):
    # ── notify signals ──────────────────────────────────────────────
    phaseChanged = Signal(); levelChanged = Signal(); statusChanged = Signal(); captionChanged = Signal()
    moodChanged = Signal(); faceChanged = Signal(); langChanged = Signal(); motionChanged = Signal()
    servicesChanged = Signal(); weatherChanged = Signal(); homeChanged = Signal(); pcChanged = Signal()
    echoChanged = Signal(); settingsChanged = Signal(); profileChanged = Signal(); busyChanged = Signal()
    enrolChanged = Signal()
    toast = Signal(str, str)          # kind (ok, pending, error, info), text
    focusComposer = Signal()
    companionChanged = Signal()

    def __init__(self, bridge_class=None, parent=None):
        super().__init__(parent)
        self.settings = QSettings('MoOS', 'Mira')
        lang = self.settings.value('language', 'ar')
        self._lang = lang if lang in ('ar', 'en') else 'ar'
        face = self.settings.value('face_style', 'rose')
        self._face = face if face in ('rose', 'holo') else 'rose'
        voice = self.settings.value('voice_name', 'Aoede')
        self._voice_name = voice if voice in ('Aoede', 'Kore', 'Leda') else 'Aoede'
        self._motion = self.settings.value('visual_motion', True, type=bool) and not self._plasma_reduced_motion()
        self._local_wake = self.settings.value('local_wake_enabled', False, type=bool)
        self._city = str(self.settings.value('weather_city', '') or '')
        self._s = i18n.table(self._lang)

        self._phase = 'idle'
        self._voice_phase = 'connecting'
        self._text_phase = None
        self._level = 0.0
        self._status = ''
        self._caption = ''
        self._caption_role = ''
        self._mood = 'neutral'
        self._error_until = 0.0
        self._services = {'echo': 'connecting', 'home': 'connecting', 'moai': 'connecting', 'brain': 'online'}
        self._weather = {'ok': False, 'city': self._city, 'error': '' if self._city else self._s['weather_unset']}
        self._home = {'available': 0, 'total': 0, 'lights_on': 0, 'lights_available': 0, 'tv': None,
                      'message': '', 'busy': False, 'linked': (Path.home() / '.config/mo-dot/home.json').exists()}
        self._pc = {'volume': None, 'brightness': None, 'output': '', 'tool': '', 'status': '', 'busy': False,
                    'apps': [], 'wifi': None, 'bluetooth': None}
        self._echo = {'online': False, 'setup': False, 'mute_available': False, 'muted': False, 'pair': False,
                      'speaker_volume': None, 'wake_threshold': None, 'wake_hint': '', 'state': '',
                      'voice_enabled': True}
        self._wake = {'enabled': self._local_wake, 'sources': [], 'source': str(self.settings.value('local_wake_source', '') or ''),
                      'state': ''}
        self._profile_status = ''
        self._busy = False
        self.keep_running = False
        self._hidden_notice = False
        self._enrol = {'mira': 0, 'other': 0, 'seconds': 0.0, 'recording': '', 'message': '',
                       'training': False, 'report': {}, 'model': '', 'active': [], 'installing': False}
        self._count_enrolment()

        self.chat = DictListModel(['role', 'text', 'time', 'status', 'title', 'tool'])
        self.devices = DictListModel(['entity_id', 'name', 'domain', 'state', 'available', 'is_on', 'brightness',
                                      'color_capable', 'dimmable', 'rgb', 'volume', 'volume_capable',
                                      'play_capable', 'pause_capable', 'on_capable', 'off_capable', 'group'],
                                     key='entity_id')
        self.worker = Worker()
        self.worker.done.connect(self._on_work)
        # Typed-brain events arrive on a worker thread; the signal queues them onto the Qt thread.
        self._brain_event.connect(self._on_brain)
        self._entities = {}
        self._bykey = {}
        self._wake_seq = 0
        self._local_wake_process = None

        from mira_bridge import Bridge
        self.bridge = (bridge_class or Bridge)(self._voice_name)
        self.bridge.lang = self._lang
        self.bridge.city = self._city or None
        if not TEST_MODE:
            try:  # typed requests may drive the Echo speaker/ring through the bridge's own loop
                import brain
                brain.set_device_control(brain.echo_device_control(self.bridge))
            except Exception:
                pass
        self.bridge.connected.connect(self._on_echo_connected)
        self.bridge.state.connect(self._on_echo_state)
        self.bridge.error.connect(self._on_echo_error)
        self.bridge.command_state.connect(self._on_echo_command)
        self.bridge.voice_state.connect(self._on_voice)

        self._restore_chat()
        self._resolve_phase()

        self.caption_timer = QTimer(self, singleShot=True, interval=7000, timeout=self._clear_caption)
        self.mood_timer = QTimer(self, singleShot=True, interval=9000, timeout=lambda: self._set_mood('neutral'))
        self.weather_timer = QTimer(self, interval=300000, timeout=self.refreshWeather)
        self.home_timer = QTimer(self, interval=20000, timeout=self.refreshHome)
        self.wake_health = QTimer(self, interval=5000, timeout=self._check_local_wake)

        # Mira Companion (the phone, over Tailscale): off until the owner turns it on in Settings.
        from companion import CompanionService
        self.companion_service = CompanionService(self)
        self._companion = self.companion_service.state()
        self.companion_service.changed.connect(self._on_companion_changed)
        self.companion_service.notice.connect(self.toast)

    # ── lifecycle ───────────────────────────────────────────────────
    def start(self):
        self.companion_service.start()
        self.bridge.start()
        self._wake['sources'] = self._available_microphones()
        if self._wake['source'] not in self._wake['sources'] and self._wake['sources']:
            self._wake['source'] = self._wake['sources'][0]
        self.settingsChanged.emit()
        if TEST_MODE:
            return
        QTimer.singleShot(800, self.refreshWeather)
        QTimer.singleShot(1200, self.refreshHome)
        QTimer.singleShot(1600, lambda: self.runPc('get_system_status'))
        QTimer.singleShot(2400, self.refreshApps)
        self.weather_timer.start()
        self.home_timer.start()
        if self._local_wake:
            self.start_local_wake()

    def shutdown(self):
        self.companion_service.shutdown()
        self.stop_local_wake()

    # ── properties ──────────────────────────────────────────────────
    phase = _prop(str, '_phase', phaseChanged)
    level = _prop(float, '_level', levelChanged)
    status = _prop(str, '_status', statusChanged)
    caption = _prop(str, '_caption', captionChanged)
    captionRole = _prop(str, '_caption_role', captionChanged)
    mood = _prop(str, '_mood', moodChanged)
    faceStyle = _prop(str, '_face', faceChanged)
    lang = _prop(str, '_lang', langChanged)
    s = _prop('QVariantMap', '_s', langChanged)
    motion = _prop(bool, '_motion', motionChanged)
    services = _prop('QVariantMap', '_services', servicesChanged)
    weather = _prop('QVariantMap', '_weather', weatherChanged)
    home = _prop('QVariantMap', '_home', homeChanged)
    pc = _prop('QVariantMap', '_pc', pcChanged)
    echo = _prop('QVariantMap', '_echo', echoChanged)
    wake = _prop('QVariantMap', '_wake', settingsChanged)
    voiceName = _prop(str, '_voice_name', settingsChanged)
    city = _prop(str, '_city', settingsChanged)
    profileStatus = _prop(str, '_profile_status', profileChanged)
    busy = _prop(bool, '_busy', busyChanged)
    enrol = _prop('QVariantMap', '_enrol', enrolChanged)

    def _get_screen_look(self):
        return self.settings.value('screen_look', False, type=bool)
    screenLook = Property(bool, _get_screen_look, notify=settingsChanged)

    @Slot(bool)
    def setScreenLook(self, allowed):
        self.settings.setValue('screen_look', bool(allowed))
        self.settings.sync()
        self.settingsChanged.emit()
    chatModel = Property(QObject, lambda self: self.chat, constant=True)
    deviceModel = Property(QObject, lambda self: self.devices, constant=True)
    companion = _prop('QVariantMap', '_companion', companionChanged)

    def _get_profile(self):
        from mira_memory import profile_text
        return profile_text()
    profileText = Property(str, _get_profile, notify=profileChanged)

    # ── state ───────────────────────────────────────────────────────
    def _resolve_phase(self):
        vp = self._voice_phase
        if vp in ACTIVE:
            phase = 'thinking' if vp == 'activating' else vp
        elif self._text_phase:
            phase = self._text_phase
        elif time.monotonic() < self._error_until:
            phase = 'error'
        elif vp == 'off':
            phase = 'offline'
        else:
            phase = 'idle'
        if phase != self._phase:
            self._phase = phase
            self.phaseChanged.emit()
        if phase != 'idle' and phase != 'offline':
            status = self._s['phase_' + phase]
        elif vp == 'off':
            status = self._s['hint_voice_off']
        elif not self._echo['online']:
            status = self._s['hint_connecting'] if self._services['echo'] == 'connecting' else self._s['hint_idle_text']
        else:
            status = self._s['hint_idle_voice']
        if status != self._status:
            self._status = status
            self.statusChanged.emit()
        busy = phase in ('thinking', 'executing', 'listening', 'speaking')
        if busy != self._busy:
            self._busy = busy
            self.busyChanged.emit()

    def _flash_error(self, seconds=4.0):
        self._error_until = time.monotonic() + seconds
        self._resolve_phase()
        QTimer.singleShot(int(seconds * 1000) + 50, self._resolve_phase)

    def _set_caption(self, text, role):
        text = (text or '').strip()
        if len(text) > 280:
            text = '…' + text[-278:]
        if text == self._caption and role == self._caption_role:
            return
        self._caption, self._caption_role = text, role
        self.captionChanged.emit()
        self.caption_timer.start()

    def _clear_caption(self):
        if self._phase in ('listening', 'speaking'):
            self.caption_timer.start()
            return
        self._caption, self._caption_role = '', ''
        self.captionChanged.emit()

    def _set_mood(self, mood):
        if mood != self._mood:
            self._mood = mood
            self.moodChanged.emit()
        if mood not in ('neutral', 'sleepy'):
            self.mood_timer.start()

    def _set_service(self, name, value):
        if self._services.get(name) != value:
            self._services = {**self._services, name: value}
            self.servicesChanged.emit()

    def _update(self, attr, signal, **fields):
        setattr(self, attr, {**getattr(self, attr), **fields})
        signal.emit()

    # ── conversation ────────────────────────────────────────────────
    def _add(self, role, text, status='', title='', tool='', persist=True, stamp=None):
        text = (text or '').strip()
        if not text:
            return
        self.chat.append({'role': role, 'text': text, 'time': stamp or datetime.now().strftime('%H:%M'),
                          'status': status, 'title': title, 'tool': tool})
        if self.chat.count > 300:
            self.chat.remove_first(self.chat.count - 300)
        if persist:
            from mira_memory import add_message
            try:
                add_message('action' if role == 'action' else role, text)
            except OSError:
                pass

    def _restore_chat(self):
        try:
            from mira_memory import recent_messages
            for item in recent_messages(24):
                try:  # stored in UTC; show the owner's local time
                    stamp = datetime.fromisoformat(str(item.get('time', ''))).astimezone().strftime('%H:%M')
                except ValueError:
                    stamp = str(item.get('time', ''))[11:16]
                self._add(item['role'], item['text'], stamp=stamp, persist=False)
        except (OSError, ValueError):
            pass

    @Slot(str)
    def send(self, text):
        text = (text or '').strip()
        if not text:
            return
        if len(text) > 6000:
            self.toast.emit('error', 'الرسالة طويلة جداً' if self._lang == 'ar' else 'Message is too long')
            return
        self._add('user', text)
        self._text_phase = 'thinking'
        self._resolve_phase()
        self._run_brain(text)

    def _run_brain(self, text):
        try:
            import brain
        except ImportError:
            brain = None
        if brain is not None and hasattr(brain, 'run_in_thread'):
            self._typed_replied = False
            emit = self._brain_event.emit
            try:
                brain.run_in_thread(text, emit, lang=self._lang, city=self._city or None,
                                    on_done=lambda result: emit('done', json.dumps(result, ensure_ascii=False, default=str)))
            except TypeError:  # an older brain without on_done
                brain.run_in_thread(text, emit, lang=self._lang, city=self._city or None)
            return
        self.worker.run('legacy_text', self._legacy_text, text)

    _brain_event = Signal(str, str)

    def _legacy_text(self, text):
        from command_router import dispatch
        routed = dispatch(text)
        if routed:
            return {'status': routed['result'].get('status', 'error'), 'reply': routed['message'], 'kind': routed.get('kind')}
        from moai_link import ask
        return {'status': 'ok', 'reply': ask(text), 'kind': 'chat'}

    @Slot(str, str)
    def _on_brain(self, kind, payload):
        self._on_voice(kind, payload, typed=True)

    # ── voice events (Echo session and typed brain share one vocabulary) ──
    @Slot(str, str)
    def _on_voice(self, kind, text, typed=False):
        if kind == 'level':
            try:
                value = max(0.0, min(1.0, float(text)))
            except ValueError:
                return
            if abs(value - self._level) > 0.01:
                self._level = value
                self.levelChanged.emit()
            return
        if kind in ('activating', 'listening', 'thinking', 'executing', 'speaking', 'ready', 'off', 'error') and not typed:
            print('Mira voice state:', kind, flush=True)
        if typed:
            if kind in ('thinking', 'executing'):
                self._text_phase = kind
            elif kind in ('reply', 'error', 'ready', 'done'):
                self._text_phase = None
            if kind == 'reply':
                self._typed_replied = True
            if kind == 'done':
                # The brain always finishes with its result; show it if no reply event did.
                try:
                    result = json.loads(text)
                except ValueError:
                    result = {}
                if not getattr(self, '_typed_replied', False) and result.get('reply'):
                    status = result.get('status', 'ok')
                    self._add('mira' if status != 'error' else 'error', result['reply'], status='' if status != 'error' else 'error')
                    self._set_mood(mood_for(result['reply'], status))
                self._typed_replied = False
                self._resolve_phase()
                return
        else:
            if kind in ACTIVE or kind in ('ready', 'off', 'error'):
                self._voice_phase = kind if kind != 'error' else 'ready'
                if kind in ('ready', 'off', 'error', 'thinking', 'executing'):
                    self._level = 0.0
                    self.levelChanged.emit()
            if kind == 'activating':
                self._wake_seq += 1
                self._update('_echo', self.echoChanged, state=self._s['phase_listening'] + ' · ' + datetime.now().strftime('%H:%M:%S'))
            if kind == 'listening':
                self._wake_seq += 1
                self._set_caption('', 'user')
            if kind in ('ready', 'off'):
                self._update('_echo', self.echoChanged, voice_enabled=kind != 'off')
        if kind == 'partial_heard':
            self._set_caption(text, 'user')
        elif kind == 'partial_reply':
            self._set_caption(text, 'mira')
        elif kind == 'heard':
            self._add('user', text)
            self._set_caption(text, 'user')
        elif kind == 'reply':
            status = 'ok'
            if typed and text.startswith('{'):
                try:
                    data = json.loads(text)
                    text, status = data.get('reply', ''), data.get('status', 'ok')
                except ValueError:
                    pass
            self._add('mira', text)
            self._set_caption(text, 'mira')
            self._set_mood(mood_for(text, status))
        elif kind == 'tool':
            try:
                data = json.loads(text)
            except ValueError:
                data = {'summary': text, 'status': 'ok'}
            status = data.get('status', 'ok')
            self._add('action', data.get('summary') or data.get('name', ''), status=status, title=data.get('name', ''), tool=data.get('name', ''))
            if data.get('name', '').startswith('home'):
                QTimer.singleShot(300, self.refreshHome)
            self._set_mood('proud' if status == 'ok' else 'reassuring' if status in ('pending', 'partial') else 'sad')
        elif kind == 'action':
            self._add('action', text, status='ok' if 'error' not in text and 'لم ينفذ' not in text else 'error')
        elif kind == 'wake':
            self._update('_echo', self.echoChanged, wake_hint=text)
        elif kind == 'capture':
            self._on_capture(text)
        elif kind == 'interrupted':
            self._set_caption(text, 'mira')
        elif kind == 'session':
            try:
                session = json.loads(text)
                print('Mira voice session:', session.get('state'), session.get('features') or session.get('reason') or '', flush=True)
            except ValueError:
                pass
        elif kind == 'error':
            self._add('error', text, status='error')
            self._set_caption(text, 'error')
            self._flash_error()
            self._set_mood('sad')
        elif kind == 'stats':
            self._on_stats(text)
        self._resolve_phase()

    def _on_stats(self, text):
        try:
            stats = json.loads(text)
        except ValueError:
            return
        notice = stats.get('notice')
        if notice:
            self.toast.emit('pending', notice)
        received = int(stats.get('microphone_bytes') or 0)
        answered = int(stats.get('reply_bytes') or 0)
        heard = bool(stats.get('heard'))
        print(f"Mira voice result: source={stats.get('input_source')} mic_bytes={received} peak={stats.get('microphone_peak')} "
              f"heard={heard} reply_bytes={answered} outcome={stats.get('outcome')} session={stats.get('session')} "
              f"timing={ {k: stats.get(k) for k in ('connect_ms', 'first_audio_ms', 'first_audio_ref', 'turn_ms', 'tool_ms')} }",
              flush=True)
        if notice:
            return
        if received == 0 and not stats.get('error'):
            self.toast.emit('pending', 'لم يصل صوت من Echo · تأكد أن ميكروفونه غير مكتوم' if self._lang == 'ar'
                            else 'No audio arrived from Echo · check its microphone')
        elif received and not heard and not answered:
            self.toast.emit('pending', 'وصل صوت لكن لم أفهم السؤال · تكلّم قرب Echo بعد أن يضيء' if self._lang == 'ar'
                            else "Audio arrived but I didn't catch a question · speak near Echo after it lights")

    # ── voice controls ──────────────────────────────────────────────
    @Slot()
    def talk(self):
        if self._voice_phase in ACTIVE:
            self.stop()
            return
        if self.bridge.online and self._voice_phase not in ('off',):
            self._wake_seq += 1
            attempt = self._wake_seq
            self.bridge.command('wake', 'wake_assistant_1')
            self._voice_phase = 'activating'
            self._resolve_phase()
            QTimer.singleShot(18000, lambda: self._wake_timeout(attempt))
        elif self._voice_phase == 'off':
            self.toast.emit('info', self._s['hint_voice_off'])
        else:
            self.toast.emit('error', self._s['hint_idle_text'])
            self.focusComposer.emit()

    def _wake_timeout(self, attempt):
        if attempt != self._wake_seq or self._voice_phase in ('listening', 'thinking', 'speaking', 'executing'):
            return
        if self._voice_phase == 'activating':
            self._voice_phase = 'ready'
        self._add('error', 'لم يبدأ Echo الاستماع. تحقّق من اتصاله ثم أعد المحاولة.' if self._lang == 'ar'
                  else 'Echo did not start listening. Check its connection and try again.', status='error')
        self._flash_error()

    @Slot()
    def stop(self):
        self.bridge.cancel_voice()
        if self._voice_phase == 'activating':
            self._voice_phase = 'ready'
        self._resolve_phase()

    @Slot(bool)
    def setVoiceEnabled(self, enabled):
        self.bridge.set_voice(bool(enabled))

    # ── appearance / preferences ────────────────────────────────────
    @Slot(str)
    def setFace(self, style):
        if style in ('rose', 'holo') and style != self._face:
            self._face = style
            self.settings.setValue('face_style', style)
            self.faceChanged.emit()

    @Slot()
    def toggleFace(self):
        self.setFace('holo' if self._face == 'rose' else 'rose')

    @Slot(str)
    def setLang(self, lang):
        if lang in ('ar', 'en') and lang != self._lang:
            self._lang = lang
            self._s = i18n.table(lang)
            self.settings.setValue('language', lang)
            self._persona_changed()
            self.langChanged.emit()
            self._resolve_phase()

    @Slot(bool)
    def setMotion(self, enabled):
        self._motion = bool(enabled)
        self.settings.setValue('visual_motion', self._motion)
        self.motionChanged.emit()

    def _persona_changed(self):
        self.bridge.lang = self._lang
        self.bridge.city = self._city or None
        voice = getattr(self.bridge, 'voice', None)
        if voice is not None:
            voice.lang = self._lang
            voice.city = self._city or None

    @Slot(str)
    def setVoiceName(self, name):
        if name not in ('Aoede', 'Kore', 'Leda'):
            return
        self._voice_name = name
        self.settings.setValue('voice_name', name)
        self.bridge.voice_name = name
        if getattr(self.bridge, 'voice', None):
            self.bridge.voice.voice_name = name
        self.settingsChanged.emit()
        self._sync_device()

    @staticmethod
    def _plasma_reduced_motion():
        try:
            text = (Path.home() / '.config/kdeglobals').read_text()
            match = re.search(r'^AnimationDurationFactor\s*=\s*([0-9.]+)', text, re.M)
            return bool(match) and float(match.group(1)) == 0.0
        except (OSError, ValueError):
            return False

    # ── weather ─────────────────────────────────────────────────────
    @Slot()
    def refreshWeather(self):
        if not self._city:
            self._weather = {'ok': False, 'city': '', 'error': self._s['weather_unset']}
            self.weatherChanged.emit()
            return
        import weather_link
        self.worker.run('weather', weather_link.current, self._city)

    @Slot(str)
    def saveCity(self, city):
        city = (city or '').strip()
        if city and not re.fullmatch(r'[\w\s\-،,.]{2,80}', city, re.UNICODE):
            self.toast.emit('error', 'اسم المدينة غير صالح' if self._lang == 'ar' else 'Invalid city name')
            return
        self._city = city
        self.settings.setValue('weather_city', city)
        self._persona_changed()
        self.settingsChanged.emit()
        self.refreshWeather()
        self._sync_device()

    # ── home ────────────────────────────────────────────────────────
    @Slot()
    def refreshHome(self):
        if TEST_MODE and not getattr(self, 'allow_home_in_tests', False):
            return
        from home_link import entities
        self.worker.run('home_list', entities)

    @Slot(str, str, float, str)
    def homeAction(self, entity_id, action, value=-1.0, color=''):
        from home_link import control
        kwargs = {}
        if action in ('brightness', 'volume'):
            kwargs['value'] = int(round(value))
        if action == 'color':
            kwargs['color'] = color
        self._update('_home', self.homeChanged, busy=True, message=self._s['checking'])
        self.worker.run('home_action', control, entity_id, action, **kwargs)

    @Slot(bool)
    def allLights(self, on):
        from home_link import control_all_lights
        self._update('_home', self.homeChanged, busy=True, message=self._s['checking'])
        self.worker.run('home_all', control_all_lights, 'turn_on' if on else 'turn_off')

    @Slot(str)
    def saveHomeToken(self, token):
        from home_link import save_token
        try:
            save_token(token)
            self._update('_home', self.homeChanged, linked=True)
            self.refreshHome()
        except ValueError as exc:
            self.toast.emit('error', str(exc))

    @Slot()
    def openHomeAssistant(self):
        QDesktopServices.openUrl(QUrl('http://127.0.0.1:8123'))

    def _devices_from(self, items):
        rows = []
        for item in items:
            domain = item['entity_id'].split('.')[0]
            features = item.get('supported_features') or 0
            modes = item.get('supported_color_modes') or []
            available = item['state'] not in ('unavailable', 'unknown')
            rows.append({
                'entity_id': item['entity_id'], 'name': (item.get('name') or item['entity_id']).strip(),
                'domain': domain, 'state': item['state'], 'available': available,
                'is_on': item['state'] in ('on', 'playing', 'paused', 'idle'),
                'brightness': round(item['brightness'] * 100 / 255) if item.get('brightness') is not None else -1,
                'color_capable': domain == 'light' and any(m in modes for m in ('hs', 'xy', 'rgb', 'rgbw', 'rgbww')),
                'dimmable': domain == 'light' and any(m not in ('onoff', 'unknown') for m in modes),
                'rgb': '#%02x%02x%02x' % tuple(item['rgb_color'][:3]) if item.get('rgb_color') else '',
                'volume': round(item['volume_level'] * 100) if item.get('volume_level') is not None else -1,
                'volume_capable': domain == 'media_player' and bool(features & 4),
                'play_capable': domain == 'media_player' and bool(features & 16384),
                'pause_capable': domain == 'media_player' and bool(features & 1),
                'on_capable': domain != 'media_player' or bool(features & 128),
                'off_capable': domain != 'media_player' or bool(features & 256),
                'group': bool(item.get('is_hue_group') and item.get('members')),
            })
        order = {'light': 0, 'media_player': 1, 'switch': 2}
        rows.sort(key=lambda r: (not r['available'], order.get(r['domain'], 3), r['group'], r['name'].lower()))
        return rows

    # ── computer ────────────────────────────────────────────────────
    @Slot(str)
    def runPc(self, name, args=None):
        from moai_link import execute
        if name == 'top_processes' and not args:
            args = {'by': 'cpu'}
        self._update('_pc', self.pcChanged, busy=True, tool=name, status='')
        self.worker.run('pc:' + name, self._pc_call, name, dict(args or {}))

    def _pc_call(self, name, args):
        from moai_link import execute
        result = execute(name, args)
        if name in ('set_volume', 'set_brightness') and result.get('status') == 'ok':
            observed = execute('get_system_status', {})
            key = 'volume' if name == 'set_volume' else 'brightness'
            try:
                value = json.loads(observed.get('output') or '{}')[key]
                if observed.get('status') != 'ok' or round(float(value)) != int(args['value']):
                    return {'status': 'pending', 'error': 'أُرسل الأمر، لكن القراءة لا تؤكد القيمة المطلوبة'}
                return {'status': 'ok', 'output': f'{key}: {round(float(value))}%', 'verified': round(float(value)), 'key': key}
            except (ValueError, TypeError, KeyError, OverflowError):
                return {'status': 'pending', 'error': 'أُرسل الأمر، لكن تعذّرت قراءة القيمة الجديدة'}
        return result

    @Slot(int)
    def setPcVolume(self, value):
        self.runPc('set_volume', {'value': str(max(0, min(100, int(value))))})

    @Slot(int)
    def setPcBrightness(self, value):
        self.runPc('set_brightness', {'value': str(max(5, min(100, int(value))))})

    @Slot()
    def refreshApps(self):
        self.runPc('list_installed_apps')

    @Slot(str)
    def openApp(self, app_id):
        if not re.fullmatch(r'[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)+', app_id or ''):
            return
        self.runPc('open_app', {'app_id': app_id})

    # ── Echo device ─────────────────────────────────────────────────
    @Slot(bool)
    def echoMute(self, on):
        self.bridge.command('switch', 'mic_mute', bool(on))

    @Slot()
    def echoPair(self):
        self.bridge.command('switch', 'bluetooth_pairing', True)
        self.toast.emit('info', 'Echo في وضع الإقران الآن' if self._lang == 'ar' else 'Echo is now pairable')

    @Slot()
    def echoSetup(self):
        if not self.bridge.online:
            self.toast.emit('error', self._s['hint_idle_text'])
            return
        self.bridge.command('setup', 'setup_page')

    @Slot(int)
    def setSpeakerVolume(self, value):
        self.bridge.command('volume', 'speaker', max(0, min(100, int(value))) / 100)

    @Slot(int)
    def setWakeThreshold(self, value):
        self.bridge.command('number', 'wake_threshold_1', max(50, min(99, int(value))) / 100)

    def _on_echo_connected(self, entities):
        self._bykey = {e.key: e for e in entities}
        names = {getattr(e, 'object_id', None) for e in entities}
        self._update('_echo', self.echoChanged, online=True, setup='setup_page' in names,
                     mute_available='mic_mute' in names, pair='bluetooth_pairing' in names,
                     state='Echo متصل' if self._lang == 'ar' else 'Echo connected')
        self._set_service('echo', 'online')
        if self._voice_phase == 'connecting':
            self._voice_phase = 'ready'
        self._resolve_phase()
        self._sync_device()
        if hasattr(self.bridge, 'wake_config'):
            self.bridge.wake_config()

    def _on_echo_state(self, state):
        entity = self._bykey.get(state.key)
        if not entity:
            return
        name = entity.object_id
        if name == 'speaker' and getattr(state, 'volume', None) is not None:
            self._update('_echo', self.echoChanged, speaker_volume=round(state.volume * 100))
        elif name == 'wake_threshold_1' and getattr(state, 'state', None) is not None:
            self._update('_echo', self.echoChanged, wake_threshold=round(state.state * 100))
        elif name == 'mic_mute':
            self._update('_echo', self.echoChanged, muted=bool(state.state))

    def _on_echo_error(self, message):
        self._update('_echo', self.echoChanged, online=False, state=message)
        self._set_service('echo', 'offline')
        if self._voice_phase in ACTIVE or self._voice_phase == 'connecting':
            self._voice_phase = 'ready'
        self._resolve_phase()

    def _on_echo_command(self, kind, status):
        if status.startswith('error:'):
            self._add('error', ('لم يصل الأمر إلى Echo · ' if self._lang == 'ar' else 'Command did not reach Echo · ') + status.split(':', 1)[1], status='error')
            if kind == 'wake':
                self._wake_seq += 1
                if self._voice_phase == 'activating':
                    self._voice_phase = 'ready'
                self._flash_error()
        elif kind == 'capture' and status.startswith('error:'):
            self._update('_enrol', self.enrolChanged, recording='', message=self._s['enrol_failed'])
        elif kind == 'wake_config' and not status.startswith('error:'):
            try:
                self._update('_enrol', self.enrolChanged, active=json.loads(status).get('active', []))
            except ValueError:
                pass
        elif kind == 'wake_model':
            state, _, payload = status.partition(':')
            try:
                data = json.loads(payload) if state in ('ok', 'pending') else {}
            except ValueError:
                data = {}
            self._update('_enrol', self.enrolChanged, installing=False, active=data.get('active', self._enrol['active']),
                         message=self._s['enrol_installed'] if state == 'ok' else self._s['enrol_install_pending'] if state == 'pending'
                         else self._s['enrol_failed'] + ' · ' + payload)
            self.toast.emit('ok' if state == 'ok' else 'pending' if state == 'pending' else 'error', self._enrol['message'])
        elif kind == 'setup' and status == 'sent':
            from mira_bridge import IP
            url = 'http://' + IP + ':8181/setup'
            self._update('_echo', self.echoChanged, setup_url=url)
            QDesktopServices.openUrl(QUrl(url))

    def _sync_device(self):
        """Give the Echo's own client the owner's profile so Mira knows them when the PC is off."""
        if TEST_MODE or os.environ.get('MIRA_NO_DEVICE_SYNC') == '1':
            return
        try:
            import device_sync
        except ImportError:
            return
        from mira_bridge import IP
        from mira_memory import profile_text
        def push():
            return device_sync.push(profile_text(), self._city or None, self._voice_name, host=IP)
        self.worker.run('device_sync', push)

    # ── local PC wake listener (experimental) ───────────────────────
    @Slot(bool)
    def setLocalWake(self, enabled):
        self._local_wake = bool(enabled)
        self.settings.setValue('local_wake_enabled', self._local_wake)
        self._update('_wake', self.settingsChanged, enabled=self._local_wake)
        self.start_local_wake() if enabled else self.stop_local_wake()

    @Slot(str)
    def setMicSource(self, source):
        if not source or source == self._wake['source']:
            return
        self.settings.setValue('local_wake_source', source)
        self._update('_wake', self.settingsChanged, source=source)
        if self._local_wake:
            self.stop_local_wake()
            self.start_local_wake()

    def _available_microphones(self):
        if TEST_MODE:
            return [FALLBACK_MIC]
        try:
            result = subprocess.run(['pactl', '-f', 'json', 'list', 'sources'], capture_output=True, text=True, timeout=3, check=True)
            sources = []
            for item in json.loads(result.stdout):
                name = item.get('name', '')
                if not name or '.monitor' in name:
                    continue
                active = item.get('active_port')
                if any(p.get('name') == active and p.get('availability') == 'not available' for p in item.get('ports') or []):
                    continue
                sources.append(name)
            return sources or [FALLBACK_MIC]
        except (OSError, subprocess.SubprocessError, ValueError, TypeError):
            return [FALLBACK_MIC]

    def start_local_wake(self):
        if self._local_wake_process and self._local_wake_process.poll() is None:
            return
        python = Path.home() / '.local/share/mira/wake-venv/bin/python'
        model = Path.home() / '.local/share/mira/wake-model'
        source = self._wake['source'] or FALLBACK_MIC
        if not python.exists() or not (model / 'model.bin').exists():
            self._update('_wake', self.settingsChanged, state='النداء المحلي غير مثبت' if self._lang == 'ar' else 'Local wake is not installed')
            return
        try:
            self._local_wake_process = subprocess.Popen(
                [str(python), str(ROOT / 'local_wake.py'), '--model', str(model), '--source', source,
                 '--parent-pid', str(os.getpid()), '--uid', str(os.getuid())],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self._update('_wake', self.settingsChanged, state='بدأ المستمع' if self._lang == 'ar' else 'Listener started')
            self.wake_health.start()
        except OSError as exc:
            self._update('_wake', self.settingsChanged, state=type(exc).__name__)

    def stop_local_wake(self):
        worker, self._local_wake_process = self._local_wake_process, None
        self.wake_health.stop()
        if worker and worker.poll() is None:
            worker.terminate()
        self._update('_wake', self.settingsChanged, state='متوقف' if self._lang == 'ar' else 'Stopped')

    def _check_local_wake(self):
        worker = self._local_wake_process
        if worker and worker.poll() is not None:
            self._update('_wake', self.settingsChanged, state='توقف المستمع' if self._lang == 'ar' else 'Listener stopped')
            self.wake_health.stop()
            return
        try:
            health = json.loads(Path(f'/run/user/{os.getuid()}/mira-wake-health.json').read_text())
            fps = health.get('frames_per_second', 0)
            label = (f'يستقبل صوتاً · {fps:.0f} إطار/ث' if self._lang == 'ar' else f'Receiving audio · {fps:.0f} fps')
            if time.time() - health.get('last_match_at', 0) < 30:
                label = 'التقط «ميرا»' if self._lang == 'ar' else 'Heard “Mira”'
            self._update('_wake', self.settingsChanged, state=label)
        except (OSError, ValueError, TypeError):
            pass

    def handle_instance_command(self, command):
        if command == b'wake' and self._local_wake and self._voice_phase == 'ready':
            self._wake_seq += 1
            self.bridge.command('wake', 'wake_assistant_1', self._wake['source'])
            self._voice_phase = 'activating'
            self._resolve_phase()
            return 'wake'
        return 'show'

    # ── teach Mira the owner's voice ────────────────────────────────
    def _count_enrolment(self):
        counts = {}
        seconds = 0.0
        for kind in ('mira', 'other'):
            files = sorted((ENROL_DIR / kind).glob('*.wav')) if (ENROL_DIR / kind).is_dir() else []
            counts[kind] = len(files)
            seconds += sum(max(0, f.stat().st_size - 44) / 32000 for f in files)
        model = WAKE_MODELS / (OWNER_MODEL + '.tflite')
        self._enrol.update(mira=counts['mira'], other=counts['other'], seconds=round(seconds, 1),
                           model=str(model) if model.exists() else '')

    @Slot(str)
    def enrolRecord(self, kind):
        if kind not in ('mira', 'other') or self._enrol['recording']:
            return
        if not self.bridge.online or not hasattr(self.bridge, 'capture'):
            self.toast.emit('error', self._s['hint_idle_text'])
            return
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        self.bridge.capture(str(ENROL_DIR / kind / f'{kind}-{stamp}.wav'))
        self._update('_enrol', self.enrolChanged, recording=kind,
                     message=self._s['enrol_say_mira'] if kind == 'mira' else self._s['enrol_say_other'])

    def _on_capture(self, text):
        try:
            data = json.loads(text)
        except ValueError:
            data = {'status': 'error'}
        self._count_enrolment()
        if data.get('status') != 'ok':
            message = self._s['enrol_failed']
        elif data.get('peak', 0) < 1200:
            message = self._s['enrol_quiet']
        else:
            message = self._s['enrol_saved'].format(seconds=data.get('seconds', 0))
        self._update('_enrol', self.enrolChanged, recording='', message=message)

    @Slot()
    def enrolClear(self):
        for kind in ('mira', 'other'):
            for f in (ENROL_DIR / kind).glob('*.wav') if (ENROL_DIR / kind).is_dir() else []:
                f.unlink(missing_ok=True)
        self._count_enrolment()
        self._update('_enrol', self.enrolChanged, report={}, message=self._s['enrol_cleared'])

    @Slot()
    def enrolTrain(self):
        if self._enrol['training'] or self._enrol['mira'] < 3:
            return
        import wake_coach
        self._update('_enrol', self.enrolChanged, training=True, message=self._s['enrol_training'])
        self.worker.run('wake_train', wake_coach.train, ENROL_DIR, WAKE_MODELS, OWNER_MODEL)

    @Slot()
    def enrolInstall(self):
        model = WAKE_MODELS / (OWNER_MODEL + '.tflite')
        if not model.exists() or not self.bridge.online or self._enrol['installing']:
            return
        active = [OWNER_MODEL, 'mira_ar_experimental']
        self._update('_enrol', self.enrolChanged, installing=True, message=self._s['enrol_installing'])
        self.bridge.install_wake_model(OWNER_MODEL, 'Mira', ['ar'], str(model), active)

    @Slot()
    def enrolRollback(self):
        if not self.bridge.online:
            return
        self._update('_enrol', self.enrolChanged, installing=True, message=self._s['enrol_installing'])
        self.bridge.select_wake_words(FALLBACK_WAKE)

    # ── phone companion ─────────────────────────────────────────────
    def _on_companion_changed(self):
        self._companion = self.companion_service.state()
        self.companionChanged.emit()

    @Slot(bool)
    def setCompanionEnabled(self, enabled):
        self.companion_service.set_enabled(enabled)

    @Slot()
    def rotateCompanionCode(self):
        self.companion_service.rotate_token()

    # ── memory ──────────────────────────────────────────────────────
    @Slot(str)
    def saveProfile(self, text):
        from mira_memory import save_profile
        try:
            save_profile(text)
            self._profile_status = self._s['saved'] + ' · ' + datetime.now().strftime('%H:%M')
            self.profileChanged.emit()
            self.toast.emit('ok', self._profile_status)
            self._sync_device()
        except (OSError, ValueError) as exc:
            self._profile_status = str(exc)
            self.profileChanged.emit()
            self.toast.emit('error', str(exc))

    @Slot(str, result=str)
    def readTextFile(self, url):
        path = Path(QUrl(url).toLocalFile() if url.startswith('file:') else url)
        try:
            if path.stat().st_size > 12000:
                raise ValueError('الملف النصي كبير؛ الحد 12 KB' if self._lang == 'ar' else 'Text file too large (12 KB max)')
            content = path.read_text(encoding='utf-8')
            if '\x00' in content:
                raise ValueError('الملف ليس نصاً' if self._lang == 'ar' else 'Not a text file')
            return content
        except (OSError, UnicodeError, ValueError) as exc:
            self.toast.emit('error', str(exc))
            return ''

    @Slot(result=bool)
    def hideToTray(self):
        """Closing the window keeps Mira listening when a tray exists; say so once."""
        if not self.keep_running:
            return False
        if not self._hidden_notice:
            self._hidden_notice = True
            try:
                subprocess.Popen(['notify-send', '-a', 'Mira', '-i', str(ROOT / 'mira-icon-v2.png'),
                                  self._s['app_title'], self._s['tray_notice']],
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except OSError:
                pass
        return True

    @Slot(str)
    def copyText(self, text):
        QGuiApplication.clipboard().setText(text)
        self.toast.emit('ok', self._s['copied'])

    @Slot()
    def clearView(self):
        self.chat.clear()

    @Slot(str)
    def openUrl(self, url):
        if url.startswith(('https://', 'http://127.0.0.1', 'http://192.168.')):
            QDesktopServices.openUrl(QUrl(url))

    # ── worker results ──────────────────────────────────────────────
    def _on_work(self, tag, result):
        if tag == 'weather':
            if isinstance(result, dict) and result.get('status') == 'ok':
                self._weather = {'ok': True, 'city': result['city'], 'temp': round(float(result['temperature_c'])),
                                 'condition': result.get('condition_ar' if self._lang == 'ar' else 'condition_en') or result.get('condition_ar', ''),
                                 'code': result.get('weather_code', -1), 'humidity': result.get('humidity_percent'),
                                 'wind': round(result['wind_kmh']) if result.get('wind_kmh') is not None else None,
                                 'is_day': result.get('is_day', 1), 'updated': datetime.now().strftime('%H:%M'), 'error': ''}
            else:
                self._weather = {'ok': False, 'city': self._city, 'error': (result or {}).get('error') or 'الطقس غير متاح الآن'}
            self.weatherChanged.emit()
        elif tag == 'home_list':
            if isinstance(result, list):
                rows = self._devices_from(result)
                self.devices.set_rows(rows)
                self._entities = {r['entity_id']: r for r in rows}
                lights = [r for r in rows if r['domain'] == 'light' and not r['group']]
                tv = next((r for r in rows if r['domain'] == 'media_player' and r['available']), None)
                self._update('_home', self.homeChanged, available=sum(r['available'] for r in rows), total=len(rows),
                             lights_on=sum(r['available'] and r['state'] == 'on' for r in lights),
                             lights_available=sum(r['available'] for r in lights),
                             tv=tv, linked=True)
                self._set_service('home', 'online')
            else:
                self._update('_home', self.homeChanged, message=(result or {}).get('error', ''))
                self._set_service('home', 'offline')
        elif tag in ('home_action', 'home_all'):
            ok = isinstance(result, dict) and result.get('status') == 'ok'
            if tag == 'home_all' and isinstance(result, dict) and 'confirmed' in result:
                message = (f"تأكدت من {result['confirmed']}/{result['total']} أضواء" if self._lang == 'ar'
                           else f"Verified {result['confirmed']}/{result['total']} lights")
            elif isinstance(result, dict) and result.get('entity_id'):
                name = self._entities.get(result['entity_id'], {}).get('name', result['entity_id'])
                message = ((('تأكدت: ' if ok else 'أُرسل ولم يتأكد: ') if self._lang == 'ar' else ('Verified: ' if ok else 'Sent, not verified: '))
                           + name)
            else:
                message = (result or {}).get('error', 'تعذّر التنفيذ')
            status = 'ok' if ok else ('pending' if isinstance(result, dict) and result.get('status') in ('pending', 'partial') else 'error')
            self._update('_home', self.homeChanged, busy=False, message=message)
            self._add('action', message, status=status, tool='home')
            self.toast.emit(status, message)
            self._set_mood('proud' if ok else 'reassuring')
            self.refreshHome()
        elif tag.startswith('pc:'):
            self._on_pc(tag[3:], result if isinstance(result, dict) else {'status': 'error'})
        elif tag == 'legacy_text':
            self._text_phase = None
            if result.get('status') == 'error' and not result.get('reply'):
                self._add('error', result.get('error', ''), status='error')
                self._set_mood('sad')
            else:
                self._add('mira' if result.get('kind') == 'chat' else 'action', result.get('reply', ''),
                          status='' if result.get('kind') == 'chat' else result.get('status', 'ok'))
                self._set_caption(result.get('reply', ''), 'mira')
                self._set_mood(mood_for(result.get('reply', ''), result.get('status', 'ok')))
                if result.get('kind') == 'home':
                    self.refreshHome()
            self._resolve_phase()
        elif tag == 'wake_train':
            report = result if isinstance(result, dict) else {'status': 'error'}
            self._count_enrolment()
            ok = report.get('status') == 'ok'
            self._update('_enrol', self.enrolChanged, training=False, report=report,
                         message=self._s['enrol_trained'] if ok else self._s['enrol_failed'] + ' · ' + str(report.get('error', '')))
        elif tag == 'device_sync':
            ok = isinstance(result, dict) and result.get('ok') is True
            self._update('_echo', self.echoChanged, standalone='synced' if ok else 'unavailable')
            facts = result.get('learned') if ok else None
            if facts:
                from mira_memory import remember_fact
                for fact in facts:
                    try:
                        remember_fact(fact)
                    except (OSError, ValueError):
                        pass
                self.profileChanged.emit()

    def _on_pc(self, tool, result):
        status = result.get('status', 'error')
        output = str(result.get('output') or result.get('error') or '')
        fields = {'busy': False, 'tool': tool, 'status': status, 'output': output}
        self._set_service('moai', 'online' if status in ('ok', 'pending') or 'local_api' not in output else 'offline')
        if tool == 'get_system_status' and status == 'ok':
            try:
                values = json.loads(result.get('output') or '{}')
                for key in ('volume', 'brightness'):
                    if isinstance(values.get(key), (int, float)):
                        fields[key] = round(values[key])
                for key in ('wifi', 'bluetooth'):
                    if isinstance(values.get(key), bool):
                        fields[key] = values[key]
            except (ValueError, TypeError):
                pass
        elif tool == 'list_installed_apps':
            apps = []
            if status == 'ok':
                for line in output.splitlines():
                    parts = line.split('\t')
                    if len(parts) >= 2 and re.fullmatch(r'[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)+', parts[0]):
                        apps.append({'id': parts[0], 'name': parts[1]})
            apps.sort(key=lambda a: a['name'].lower())
            fields['apps'] = apps
            fields['output'] = self._pc['output']  # the catalog is not a reading to display
            fields['tool'] = self._pc['tool']
        elif tool in ('set_volume', 'set_brightness'):
            if status == 'ok' and 'verified' in result:
                fields[result['key']] = result['verified']
            self._add('action', output or tool, status=status, tool=tool)
        elif tool == 'open_app':
            self._add('action', output or ('فتحت التطبيق' if status == 'ok' else 'تعذّر فتح التطبيق'), status=status, tool=tool)
            self.toast.emit(status if status in ('ok', 'pending') else 'error', output[:120] or tool)
        self._update('_pc', self.pcChanged, **fields)

