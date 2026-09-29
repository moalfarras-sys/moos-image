"""Mira Companion's Qt side: the bridge between Mira's controller and the server thread.

- `ControllerAdapter` reads the controller only on the Qt thread (from its notify signals and
  models) and keeps a copy that the server thread reads under a lock. A phone's request reaches
  the controller's own slot through `QMetaObject.invokeMethod(..., Qt.QueuedConnection)`, so it
  runs on the Qt thread exactly like a desktop button, with the desktop's validation behind it.
- `CompanionService` owns the pairing token, starts and stops the server, and gives the
  Settings panel one plain map (`state()`): enabled, running state and its reason, address,
  pairing link and QR modules, and how many phones are connected.
"""
import copy
import json
import os
import threading
import time
from datetime import datetime

from PySide6.QtCore import QBuffer, QIODevice, QMetaObject, QObject, Q_ARG, Qt, QTimer, Signal, Slot

from .server import LOOPBACK, CompanionServer, Tailnet, TokenStore, find_tailscale

SNAPSHOT_CHAT = 30
MAX_CHAT_TEXT = 8000
LEVEL_INTERVAL_MS = 125           # at most 8 level updates a second, only while a phone listens
CHAT_FIELDS = ('role', 'text', 'time', 'status', 'title', 'tool')
DEVICE_FIELDS = ('entity_id', 'name', 'domain', 'state', 'available', 'is_on', 'brightness', 'color_capable',
                 'dimmable', 'rgb', 'volume', 'volume_capable', 'play_capable', 'pause_capable', 'on_capable',
                 'off_capable', 'group')
# The desktop's own words, so the phone says exactly what the desktop says.
SHARED_TEXT = ('app_title', 'phase_idle', 'phase_listening', 'phase_thinking', 'phase_speaking', 'phase_executing',
               'phase_error', 'phase_offline', 'talk', 'stop', 'send', 'home', 'conversation', 'you', 'mira',
               'action', 'pending', 'failed', 'empty_chat_title', 'empty_chat_body', 'lights', 'lights_on_of',
               'all_on', 'all_off', 'tv', 'unavailable', 'devices_available', 'brightness', 'color', 'volume',
               'play', 'pause', 'state_on', 'state_off', 'state_playing', 'state_paused', 'state_idle',
               'checking', 'no_devices', 'refresh', 'weather', 'weather_unset', 'humidity', 'wind', 'turn_on',
               'turn_off', 'svc_echo', 'svc_home', 'svc_moai', 'svc_brain', 'online', 'offline', 'connecting',
               'act_waiting', 'act_approve', 'act_reject', 'act_password', 'act_running', 'act_expired',
               'act_cancelled', 'act_change')
ACTION_FIELDS = ('aid', 'title', 'detail', 'stage', 'category', 'summary', 'expires')


def _plain(value):
    """A JSON-safe deep copy (the server thread never shares an object with the Qt thread)."""
    try:
        return json.loads(json.dumps(value, ensure_ascii=False, default=str))
    except (TypeError, ValueError):
        return None


def _model_rows(model, first=0, last=None):
    count = model.rowCount()
    last = count - 1 if last is None else min(last, count - 1)
    getter = getattr(model, 'get', None)
    if callable(getter):
        return [getter(i) for i in range(first, last + 1)]
    roles = {int(role): bytes(name).decode() for role, name in model.roleNames().items()}
    return [{name: model.data(model.index(i, 0), role) for role, name in roles.items()}
            for i in range(first, last + 1)]


def _chat_row(item):
    row = {key: str(item.get(key) or '') for key in CHAT_FIELDS}
    row['text'] = row['text'][:MAX_CHAT_TEXT]
    return row


def _device_row(item):
    return _plain({key: item.get(key) for key in DEVICE_FIELDS})


def _encode(image, fmt):
    buffer = QBuffer()
    buffer.open(QIODevice.WriteOnly)
    ok = image.save(buffer, 'WEBP' if fmt == 'webp' else 'PNG', 85 if fmt == 'webp' else -1)
    data = bytes(buffer.data()) if ok else b''
    buffer.close()
    return data


def webp_supported():
    from PySide6.QtGui import QImageWriter
    return b'webp' in [bytes(f).lower() for f in QImageWriter.supportedImageFormats()]


class FaceRenderer:
    """Mira's portraits for the phone, encoded once per (style, expression, size, format).

    It owns a private `faces.FaceLibrary` (never the one QML draws from) and runs on the server's
    render thread. The decoded sheets are released after a quiet minute and a half; only the small
    encoded images stay. PNG is the documented route; WebP (4–9× smaller for these portraits) is
    what the phone asks for when this computer can write it.
    """
    SIZES = (256, 512)
    FORMATS = ('png', 'webp')

    def __init__(self, idle_release=90.0):
        self._lock = threading.Lock()
        self._encoded = {}
        self._library = None
        self._last = 0.0
        self._idle_release = idle_release
        self.format = 'webp' if webp_supported() else 'png'

    def image(self, style, expression, size=256, fmt='png'):
        from faces import EXPRESSIONS, STYLES, FaceLibrary
        if style not in STYLES or expression not in EXPRESSIONS or size not in self.SIZES or fmt not in self.FORMATS:
            return None
        key = (style, expression, size, fmt)
        with self._lock:
            cached = self._encoded.get(key)
            if cached is not None:
                return cached
            if self._library is None:
                self._library = FaceLibrary()
            portrait = self._library.portrait(style, expression, size)
            self._library.cache.clear()
            data = _encode(portrait, fmt)
            if data:
                self._encoded[key] = data
            self._last = time.monotonic()
            return data or None

    def png(self, style, expression, size=256):
        return self.image(style, expression, size, 'png')

    def trim(self):
        with self._lock:
            if self._library is not None and time.monotonic() - self._last > self._idle_release:
                self._library = None


class ControllerAdapter(QObject):
    """The server's `backend`: Mira's state for the phone and a queued route to her slots."""

    def __init__(self, controller, faces=None, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.faces = faces or FaceRenderer()
        self._lock = threading.Lock()
        self._sink = None
        self._state = {}
        self._chat = []            # [(seq, row)] mirroring the chat model row for row
        self._seq = 0
        self._devices = []
        self._dirty = set()
        self._level = 0.0
        self._level_sent = 0.0
        self._flush_timer = QTimer(self, singleShot=True, interval=0, timeout=self._flush)
        self._level_timer = QTimer(self, singleShot=True, interval=LEVEL_INTERVAL_MS, timeout=self._flush_level)
        self._devices_timer = QTimer(self, singleShot=True, interval=40, timeout=self._read_devices)

        self._connections = []
        c = controller
        for name, slot in (('phaseChanged', self._on_phase), ('statusChanged', self._on_status),
                           ('captionChanged', self._on_caption), ('moodChanged', self._on_mood),
                           ('faceChanged', self._on_face), ('langChanged', self._on_lang),
                           ('servicesChanged', self._on_services), ('weatherChanged', self._on_weather),
                           ('homeChanged', self._on_home), ('echoChanged', self._on_echo),
                           ('busyChanged', self._on_busy), ('levelChanged', self._on_level),
                           ('toast', self._on_toast)):
            signal = getattr(c, name, None)
            if signal is not None:
                self._connect(signal, slot)
        chat = c.chatModel
        self._connect(chat.rowsInserted, self._on_chat_inserted)
        self._connect(chat.rowsRemoved, self._on_chat_removed)
        self._connect(chat.modelReset, self._on_chat_reset)
        self._connect(chat.dataChanged, self._on_chat_changed)
        devices = c.deviceModel
        for signal in (devices.modelReset, devices.rowsInserted, devices.rowsRemoved, devices.dataChanged):
            self._connect(signal, self._on_devices)
        # System changes waiting for the owner: the phone shows the same cards and may answer them.
        actions = getattr(c, 'actionModel', None)
        if actions is not None:
            for signal in (actions.modelReset, actions.rowsInserted, actions.rowsRemoved, actions.dataChanged):
                self._connect(signal, self._on_actions)

        with self._lock:
            self._state = self._read(('phase', 'status', 'caption', 'captionRole', 'mood', 'faceStyle', 'lang',
                                      's', 'services', 'weather', 'home', 'echo', 'busy', 'actions'))
            self._state['level'] = 0.0
            self._chat = [(self._next(), _chat_row(row)) for row in _model_rows(chat)]
            self._devices = [_device_row(row) for row in _model_rows(devices)]

    def _connect(self, signal, slot):
        signal.connect(slot)
        self._connections.append((signal, slot))

    def close(self):
        """Stop observing the controller (Qt thread): no more events, no more timers."""
        self._sink = None
        for timer in (self._flush_timer, self._level_timer, self._devices_timer):
            timer.stop()
        for signal, slot in self._connections:
            try:
                signal.disconnect(slot)
            except (RuntimeError, TypeError):
                pass
        self._connections = []

    # ── the server side (any thread) ────────────────────────────────
    def attach(self, sink):
        """`sink(event, data)` is the running server's thread-safe publish()."""
        self._sink = sink

    def detach(self):
        self._sink = None

    def snapshot(self):
        with self._lock:
            state = copy.deepcopy(self._state)
            state['chat'] = [dict(row, seq=seq) for seq, row in self._chat[-SNAPSHOT_CHAT:]]
            state['devices'] = copy.deepcopy(self._devices)
        state['version'] = 1
        state['faceFormat'] = self.faces.format
        return state

    def devices(self):
        with self._lock:
            return copy.deepcopy(self._devices)

    def device(self, entity_id):
        with self._lock:
            for row in self._devices:
                if row.get('entity_id') == entity_id:
                    return dict(row)
        return None

    def _invoke(self, method, *args):
        try:
            return bool(QMetaObject.invokeMethod(self.controller, method, Qt.QueuedConnection, *args))
        except (RuntimeError, TypeError):   # the controller is gone (the app is quitting)
            return False

    def send(self, text):
        return self._invoke('send', Q_ARG(str, text))

    def talk(self):
        return self._invoke('talk')

    def stop(self):
        return self._invoke('stop')

    def home_action(self, entity_id, action, value, color):
        return self._invoke('homeAction', Q_ARG(str, entity_id), Q_ARG(str, action), Q_ARG(float, float(value)),
                            Q_ARG(str, color))

    def all_lights(self, on):
        return self._invoke('allLights', Q_ARG(bool, bool(on)))

    def answer_action(self, aid, approve):
        """The owner's answer from his paired phone: the same slots as the card's buttons."""
        return self._invoke('approveAction' if approve else 'rejectAction', Q_ARG(str, aid))

    def refresh_home(self):
        return self._invoke('refreshHome')

    def face_image(self, style, expression, size=256, fmt='png'):
        return self.faces.image(style, expression, size, fmt)

    def housekeeping(self):
        self.faces.trim()

    # ── the Qt side ─────────────────────────────────────────────────
    def _next(self):
        self._seq += 1
        return self._seq

    def _emit(self, event, data):
        sink = self._sink
        if sink is not None:
            sink(event, data)

    def _read(self, keys):
        c = self.controller
        out = {}
        for key in keys:
            if key == 's':
                table = getattr(c, 's', None) or {}
                out['s'] = {k: str(v) for k, v in dict(table).items() if k in SHARED_TEXT}
            elif key == 'echo':
                echo = getattr(c, 'echo', None) or {}
                out['echo'] = {'online': echo.get('online') is True, 'voice_enabled': echo.get('voice_enabled') is not False}
            elif key == 'busy':
                out['busy'] = bool(getattr(c, 'busy', False))
            elif key == 'actions':
                model = getattr(c, 'actionModel', None)
                rows = _model_rows(model) if model is not None else []
                out['actions'] = [{k: _plain(row.get(k)) for k in ACTION_FIELDS} for row in rows[:6]]
            else:
                out[key] = _plain(getattr(c, key, None))
        return out

    def _changed(self, keys):
        values = self._read(keys)
        with self._lock:
            self._state.update(values)
        self._dirty.update(keys)
        if not self._flush_timer.isActive():
            self._flush_timer.start()

    def _flush(self):
        keys, self._dirty = self._dirty, set()
        with self._lock:
            data = {key: copy.deepcopy(self._state[key]) for key in keys if key in self._state}
        if data:
            self._emit('state', data)

    @Slot()
    def _on_actions(self, *args):
        self._changed(('actions',))

    @Slot()
    def _on_phase(self):
        self._changed(('phase',))

    @Slot()
    def _on_status(self):
        self._changed(('status',))

    @Slot()
    def _on_caption(self):
        self._changed(('caption', 'captionRole'))

    @Slot()
    def _on_mood(self):
        self._changed(('mood',))

    @Slot()
    def _on_face(self):
        self._changed(('faceStyle',))

    @Slot()
    def _on_lang(self):
        self._changed(('lang', 's'))

    @Slot()
    def _on_services(self):
        self._changed(('services',))

    @Slot()
    def _on_weather(self):
        self._changed(('weather',))

    @Slot()
    def _on_home(self):
        self._changed(('home',))

    @Slot()
    def _on_echo(self):
        self._changed(('echo',))

    @Slot()
    def _on_busy(self):
        self._changed(('busy',))

    @Slot()
    def _on_level(self):
        try:
            level = max(0.0, min(1.0, float(self.controller.level)))
        except (TypeError, ValueError):
            return
        self._level = level
        with self._lock:
            self._state['level'] = round(level, 3)
        if self._sink is not None and not self._level_timer.isActive():
            self._level_timer.start()

    def _flush_level(self):
        value = round(self._level, 2)
        if abs(value - self._level_sent) >= 0.03 or (value == 0.0 and self._level_sent != 0.0):
            self._level_sent = value
            self._emit('level', {'level': value})

    @Slot(str, str)
    def _on_toast(self, kind, text):
        self._emit('toast', {'kind': str(kind)[:16], 'text': str(text)[:300]})

    def _on_chat_inserted(self, parent, first, last):
        rows = [(self._next(), _chat_row(row)) for row in _model_rows(self.controller.chatModel, first, last)]
        with self._lock:
            self._chat[first:first] = rows
        for seq, row in rows:
            self._emit('chat', dict(row, seq=seq))

    def _on_chat_removed(self, parent, first, last):
        with self._lock:
            del self._chat[first:last + 1]

    def _on_chat_reset(self):
        rows = [(self._next(), _chat_row(row)) for row in _model_rows(self.controller.chatModel)]
        with self._lock:
            self._chat = rows
            recent = [dict(row, seq=seq) for seq, row in rows[-SNAPSHOT_CHAT:]]
        self._emit('chat_reset', {'rows': recent})

    def _on_chat_changed(self, top_left, bottom_right, roles=()):
        first, last = top_left.row(), bottom_right.row()
        fresh = _model_rows(self.controller.chatModel, first, last)
        updated = []
        with self._lock:
            for offset, item in enumerate(fresh):
                index = first + offset
                if 0 <= index < len(self._chat):
                    seq = self._chat[index][0]
                    self._chat[index] = (seq, _chat_row(item))
                    updated.append(dict(self._chat[index][1], seq=seq))
        for row in updated:
            self._emit('chat_update', row)

    def _on_devices(self, *args):
        if not self._devices_timer.isActive():
            self._devices_timer.start()

    def _read_devices(self):
        rows = [_device_row(row) for row in _model_rows(self.controller.deviceModel)]
        with self._lock:
            self._devices = rows
        self._emit('devices', {'devices': copy.deepcopy(rows)})


# ── QR code (optional dependency) ───────────────────────────────────────────────────────────────
def qr_available():
    try:
        import segno  # noqa: F401
    except ImportError:
        return False
    return True


def qr_code(text):
    """The QR modules as horizontal runs of dark cells: {'size': n, 'runs': [[x, y, width], ...]}.

    Drawn by QML as crisp rectangles at any scale. None when `segno` is not installed; the panel
    then shows the link as text instead.
    """
    try:
        import segno
    except ImportError:
        return None
    rows = [list(row) for row in segno.make_qr(text, error='m').matrix_iter(scale=1, border=0)]
    runs = []
    for y, row in enumerate(rows):
        x, n = 0, len(row)
        while x < n:
            if row[x]:
                start = x
                while x < n and row[x]:
                    x += 1
                runs.append([start, y, x - start])
            else:
                x += 1
    return {'size': len(rows), 'runs': runs}


# ── the Settings panel's words ──────────────────────────────────────────────────────────────────
PANEL_TEXT = {
    'section': ('الهاتف', 'Phone'),
    'title': ('ميرا على هاتفك', 'Mira on your phone'),
    'subtitle': ('ميرا على الـ iPhone عبر شبكة Tailscale الخاصة بك', 'Mira on your iPhone, over your private Tailscale network'),
    'enable': ('تشغيل واجهة الهاتف', 'Phone interface'),
    'state_off': ('متوقفة', 'Off'),
    'state_starting': ('تبدأ…', 'Starting…'),
    'state_waiting': ('بانتظار Tailscale', 'Waiting for Tailscale'),
    'state_running': ('تعمل', 'On'),
    'state_error': ('تعذّر التشغيل', 'Could not start'),
    'reason_not_installed': ('Tailscale غير مثبّت على هذا الكمبيوتر، لذلك تبقى واجهة الهاتف متوقفة.',
                             'Tailscale is not installed on this computer, so the phone interface stays off.'),
    'reason_not_connected': ('Tailscale غير متصل على هذا الكمبيوتر. تبدأ الواجهة وحدها حين يتصل.',
                             'Tailscale is not connected on this computer. The interface starts by itself once it is.'),
    'reason_port_busy': ('المنفذ {port} يستخدمه برنامج آخر. سأعيد المحاولة.',
                         'Port {port} is in use by another program. Retrying.'),
    'reason_refused_address': ('هذا ليس عنوان Tailscale، فلن تُفتح الواجهة عليه.',
                               'That is not a Tailscale address, so the interface will not open on it.'),
    'reason_failed': ('تعذّر فتح الخادم. سأعيد المحاولة.', 'The server could not start. Retrying.'),
    'phones_none': ('لا يوجد هاتف متصل الآن', 'No phone connected right now'),
    'phones_one': ('هاتف واحد متصل الآن', 'One phone connected now'),
    'phones_two': ('هاتفان متصلان الآن', 'Two phones connected now'),
    'phones_many': ('{n} هواتف متصلة الآن', '{n} phones connected now'),
    'pair_title': ('إقران الهاتف', 'Pair your phone'),
    'pair_steps': ('وجّه كاميرا الـ iPhone إلى الرمز وافتح الرابط في Safari. لتبقى ميرا على الشاشة الرئيسية: مشاركة ← إضافة إلى الشاشة الرئيسية.',
                   'Point the iPhone camera at the code and open the link in Safari. To keep Mira on your Home Screen: Share → Add to Home Screen.'),
    'show_code': ('إظهار رمز الإقران', 'Show pairing code'),
    'hide_code': ('إخفاء الرمز', 'Hide code'),
    'code_hidden': ('الرمز مخفي حتى تطلبه، ويختفي وحده بعد دقيقتين.',
                    'The code stays hidden until you ask for it, and hides itself after two minutes.'),
    'rotate': ('تغيير الرمز', 'Change code'),
    'rotate_confirm': ('اضغط مجدداً للتأكيد', 'Press again to confirm'),
    'rotate_note': ('تغيير الرمز يفصل كل هاتف مقترن؛ امسح الرمز الجديد لإعادة الإقران.',
                    'Changing the code signs out every paired phone; scan the new code to pair again.'),
    'qr_missing': ('لا يمكن رسم رمز QR على هذا الكمبيوتر. افتح هذا الرابط في Safari على الهاتف:',
                   'The QR code cannot be drawn on this computer. Open this link in Safari on the phone:'),
    'link': ('رابط الإقران', 'Pairing link'),
    'address': ('العنوان', 'Address'),
    'note_title': ('ما يستطيعه الهاتف', 'What the phone can do'),
    'note': ('لا يمكن الوصول إليها إلا من شبكة Tailscale الخاصة بك. يستطيع الهاتف المحادثة والتحدّث والتحكم بالبيت؛ أما أوامر الكمبيوتر فتبقى خاضعة لقواعد التأكيد في Mo AI.',
             "Reachable only on your Tailscale network; the phone can chat, talk and control the house; computer actions still pass Mo AI's confirmation rules."),
    'note_brain': ('ما تكتبه على الهاتف يمر بعقل ميرا نفسه كما على الكمبيوتر، وليس للهاتف طريق مباشر إلى أدوات الكمبيوتر.',
                   "What you type on the phone goes through Mira's own brain, exactly as on the desktop; the phone has no direct route to the computer's tools."),
    'last_paired': ('آخر إقران: {time}', 'Last paired: {time}'),
    'paired_notice': ('اقترن هاتف بميرا ({ip})', 'A phone paired with Mira ({ip})'),
}


def panel_text(lang):
    index = 1 if lang == 'en' else 0
    return {key: pair[index] for key, pair in PANEL_TEXT.items()}


class CompanionService(QObject):
    """What the desktop app holds: the adapter, the token store and the server's lifecycle.

    `state()` is the plain map the Settings panel binds to (via the controller's `companion`
    property); `changed` fires on the Qt thread whenever it changes. `notice(kind, text)` reports
    security-relevant events (a phone paired) for the desktop's toasts.
    """
    changed = Signal()
    notice = Signal(str, str)
    _queued = Signal(object)

    def __init__(self, controller, config_path=None, host=None, port=None, server_factory=CompanionServer,
                 parent=None):
        super().__init__(parent if parent is not None else controller)
        self.controller = controller
        self.store = TokenStore(config_path)
        self.adapter = ControllerAdapter(controller, parent=self)
        self.server = None
        self._server_factory = server_factory
        self._port = port
        self._host = self._loopback_override(host if host is not None else os.environ.get('MIRA_COMPANION_HOST'))
        self._generation = 0
        self._status = ('off', '')
        self._endpoint = None
        self._clients = 0
        self._last_paired = ''
        self._qr_for = (None, None)
        self._qr_available = qr_available()
        self._queued.connect(self._run_queued, Qt.QueuedConnection)
        lang_changed = getattr(controller, 'langChanged', None)
        if lang_changed is not None:
            lang_changed.connect(self._rebuild)
        self._state = {}
        self._rebuild()

    @staticmethod
    def _loopback_override(value):
        if not value:
            return None
        if value == LOOPBACK:
            return LOOPBACK
        print('Mira companion: MIRA_COMPANION_HOST accepts only 127.0.0.1; ignored', flush=True)
        return None

    # ── controller-facing API (Qt thread) ───────────────────────────
    def state(self):
        return copy.deepcopy(self._state)

    def start(self):
        """Call once the controller has started: brings the server up if the owner enabled it."""
        if self.store.enabled and self.server is None:
            self._start_server()
            self._rebuild()

    def set_enabled(self, enabled):
        enabled = bool(enabled)
        if enabled != self.store.enabled:
            self.store.set_enabled(enabled)
        if enabled and self.server is None:
            self._start_server()
        elif not enabled and self.server is not None:
            self._stop_server(timeout=0.5)
            self._status = ('off', '')
        self._rebuild()

    def rotate_token(self):
        self.store.rotate()
        self._qr_for = (None, None)
        if self.server is not None:
            self.server.close_streams('rotated')
        self._rebuild()

    def shutdown(self):
        """The app is quitting: stop the server and stop observing the controller."""
        self._stop_server(timeout=1.5)
        self.adapter.close()

    # ── server lifecycle ────────────────────────────────────────────
    def _start_server(self):
        self.store.ensure_token()
        self._generation += 1
        generation = self._generation
        if self._host:
            host = self._host

            def discover():
                return Tailnet(host, ('localhost',), '')
            probe = (lambda _host: True)
        else:
            discover, probe = find_tailscale, None

        def queued(fn):
            return lambda *args: self._queued.emit(lambda: fn(generation, *args))

        self.server = self._server_factory(
            self.adapter, self.store, port=self._port if self._port is not None else self.store.port,
            discover=discover,
            probe=probe, on_status=queued(self._on_server_status), on_clients=queued(self._on_clients),
            on_paired=queued(self._on_paired))
        self.adapter.attach(self.server.publish)
        self._status = ('starting', '')
        self.server.start()

    def _stop_server(self, timeout):
        server, self.server = self.server, None
        self._generation += 1
        self.adapter.detach()
        self._endpoint = None
        self._clients = 0
        if server is not None:
            server.stop(timeout)

    @Slot(object)
    def _run_queued(self, fn):
        fn()

    def _on_server_status(self, generation, state, detail):
        if generation != self._generation:
            return
        if state == 'running':
            self._endpoint = (detail['host'], detail['port'])
            self._status = ('running', '')
        elif state in ('waiting', 'error'):
            self._endpoint = None
            self._status = (state, str(detail or ''))
        elif state == 'starting':
            self._status = ('starting', '')
        elif state == 'stopped':          # the thread ended while the owner still wants it on
            self._endpoint = None
            self._status = ('error', 'failed')
        self._rebuild()

    def _on_clients(self, generation, count):
        if generation == self._generation:
            self._clients = int(count)
            self._rebuild()

    def _on_paired(self, generation, peer):
        if generation != self._generation:
            return
        self._last_paired = datetime.now().strftime('%H:%M')
        self.notice.emit('ok', panel_text(self._lang())['paired_notice'].format(ip=peer))
        self._rebuild()

    # ── the panel's map ─────────────────────────────────────────────
    def _lang(self):
        lang = getattr(self.controller, 'lang', 'ar')
        return lang if lang in ('ar', 'en') else 'ar'

    def _qr(self, url):
        if self._qr_for[0] != url:
            self._qr_for = (url, qr_code(url) if url else None)
        return self._qr_for[1]

    def _rebuild(self):
        text = panel_text(self._lang())
        enabled = self.store.enabled
        state, reason = self._status if enabled else ('off', '')
        address = url = ''
        if state == 'running' and self._endpoint:
            host, port = self._endpoint
            address = f'http://{host}:{port}'
            token = self.store.token
            url = f'{address}/pair?t={token}' if token else ''
        qr = self._qr(url) if url else None
        reason_text = ''
        if reason:
            template = text.get('reason_' + reason, text['reason_failed'])
            reason_text = template.format(port=self._port if self._port is not None else self.store.port)
        clients = self._clients if state == 'running' else 0
        phones = (text['phones_none'] if clients == 0 else text['phones_one'] if clients == 1
                  else text['phones_two'] if clients == 2 else text['phones_many'].format(n=clients))
        self._state = {
            'enabled': enabled,
            'state': state,
            'label': text['state_' + state],
            'reason': reason_text,
            'address': address,
            'url': url,
            'qr': qr or {'size': 0, 'runs': []},
            'qrAvailable': self._qr_available,
            'clients': clients,
            'phones': phones,
            'lastPaired': text['last_paired'].format(time=self._last_paired) if self._last_paired else '',
            'text': text,
        }
        self.changed.emit()
