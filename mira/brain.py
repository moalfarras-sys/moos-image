"""Mira's typed-chat brain: Gemini with the same fixed tools as the voice path.

The text window gets the persona, honesty rules and tool registry of Gemini
Live (`tools.py`). Function calling is a manual loop (at most MAX_ROUNDS model
calls); every tool runs through `tools.run_tool`, so a result is `ok` only when
it was verified. When Gemini is unreachable (quota, network, auth, timeout,
missing configuration) the question falls back in order to the deterministic
command router and then to the Mo AI agent, and the reply says which path
answered. Nothing here can run a command the model wrote.

Qt integration: call `run_in_thread(text, emit, lang=..., city=...)` from any
thread. It runs on one private asyncio loop thread and calls `emit(kind, text)`
from that thread (a Qt Signal's emit is safe there). It returns a `Turn`:
`turn.cancel()` stops that typed question (`cancel_current()` stops the latest
one), and the answer then finishes with status `cancelled`, saying what had
already happened. A caller may instead pass its own `cancel_event`
(threading.Event) and set it from anywhere.

Which model answers is the owner's choice, kept in QSettings('MoOS', 'Mira'):
`text_model` (one of TEXT_MODEL_IDS, the Gemini model for typed chat; it wins
over gemini.json's `text_model`) and `cloud_model` (the model Mo AI's free
cloud route asks for, sent to moai-gateway as `cloud:<id>`; empty follows Mo
AI's own setting). Every finished answer is published to the listeners of
`add_answer_listener` and kept as `last_answer()`: route, model, status, time.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import threading
import urllib.error
import urllib.request
import time
import weakref
from concurrent.futures import CancelledError as FutureCancelled
from concurrent.futures import Future
from pathlib import Path
from typing import Any, Callable, Optional

import tools

GEMINI_CONFIG = Path.home() / '.config/mo-dot/gemini.json'
DEFAULT_TEXT_MODEL = 'gemini-flash-lite-latest'
# Measured 2026-09-28 on the owner's key: flash-lite answered in 0.7 s, 2.5-flash in 0.9 s, while
# flash-latest (3.8-flash) took 12 s and ran out of quota within a few calls. When a model is out
# of quota or failing before any tool acted, the next one answers instead of giving up.
FALLBACK_TEXT_MODELS = ('gemini-2.5-flash', 'gemini-flash-latest')
# The typed-chat models the owner may choose between (Brain page), fastest first.
TEXT_MODEL_IDS = ('gemini-flash-lite-latest', 'gemini-2.5-flash', 'gemini-flash-latest')
# A model id Mo AI's cloud route may be asked for, in the provider's own spelling (`vendor/name:tag`):
# never a URL, never a `..` segment. moai-gateway's policy checks it again and alone decides free or paid.
CLOUD_MODEL_RE = re.compile(r'[A-Za-z0-9][A-Za-z0-9._@+-]{0,79}(?:/[A-Za-z0-9][A-Za-z0-9._@+-]{0,79}){0,3}'
                            r'(?::[A-Za-z0-9][A-Za-z0-9._-]{0,39})?')
SWITCH_REASONS = ('quota', 'server', 'timeout', 'empty')
MAX_ROUNDS = 5            # model calls per question, the last one forced to text
MODEL_TIMEOUT_S = 30.0    # one generate_content call
ASK_TIMEOUT_S = 240.0     # whole Gemini path, tools included
ROUTER_TIMEOUT_S = 120.0  # deterministic fallback (may read back Home Assistant)
AGENT_TIMEOUT_S = 200.0   # Mo AI agent fallback
HISTORY_TURNS = 12
GATEWAY_PORT = int(os.environ.get('MOAI_GATEWAY_PORT', '8080'))
GATEWAY_TIMEOUT_S = 75.0  # one free-cloud call through moai-gateway
THINKING_LEVEL = 'LOW'    # measured: tool choice 2.2 s at LOW vs 12–17 s at the model default

REASONS = {
    'quota': ('انتهت حصة Gemini الآن', 'Gemini quota is exhausted right now'),
    'auth': ('مفتاح Gemini مرفوض', 'the Gemini key was rejected'),
    'network': ('لا يوجد اتصال بـ Gemini', 'Gemini cannot be reached'),
    'timeout': ('تأخر Gemini في الرد', 'Gemini took too long'),
    'server': ('خوادم Gemini تواجه مشكلة', 'Gemini servers are failing'),
    'config': ('إعداد Gemini غير موجود', 'Gemini is not configured'),
    'empty': ('لم يرسل Gemini رداً', 'Gemini sent no answer'),
    'request': ('رفض Gemini الطلب', 'Gemini rejected the request'),
    'unknown': ('تعذّر الوصول إلى Gemini', 'Gemini is unavailable'),
}


# What a step still running on its own thread is called when the owner stops an answer. Mo AI's
# tools use moai_tools.title; these are Mira's own tools and the two fallback paths.
ROUTER_STEP = '@router'
AGENT_STEP = '@agent'
STEP_TITLES = {
    ROUTER_STEP: ('الأوامر المحلية التي تنفّذ طلبك', 'local commands carrying out your request'),
    AGENT_STEP: ('وكيل Mo AI الذي يعمل على طلبك', 'the Mo AI agent working on your request'),
    'device_control': ('التحكم بـ Echo', 'Echo control'),
    'home_summary': ('حالة المنزل', 'Home summary'),
    'home_devices': ('أجهزة المنزل', 'Home devices'),
    'home_control': ('التحكم بجهاز في المنزل', 'Home device control'),
    'home_lights_all': ('كل أضواء المنزل', 'All the home lights'),
    'lights': ('الإضاءة', 'Lights'),
    'light_scene': ('مشهد إضاءة', 'A lighting scene'),
    'screen_sync': ('مزامنة الأضواء مع الشاشة', 'Screen sync'),
    'home_rename': ('تسمية جهاز في البيت', 'Renaming a home device'),
    'tv_control': ('التحكم بالتلفزيون', 'TV control'),
    'current_weather': ('الطقس', 'Weather'),
    'current_time': ('الوقت', 'Time'),
    'remember_color': ('تذكّر لون', 'Remembering a colour'),
    'remember_device_alias': ('تذكّر اسم جهاز', 'Remembering a device name'),
    'computer_open_application': ('فتح تطبيق', 'Opening an app'),
    'remember_owner_fact': ('تذكّر معلومة عنك', 'Remembering a fact about you'),
    'research': ('بحث في الإنترنت', 'Web research'),
    'look_at_screen': ('النظر إلى الشاشة', 'Looking at the screen'),
    'find_app': ('البحث عن تطبيق', 'Finding an app'),
    'health_report': ('تقرير صحة الكمبيوتر', 'Computer health report'),
    'media_control': ('التحكم بالموسيقى والفيديو', 'Media control'),
    'clipboard': ('الحافظة', 'Clipboard'),
    'find_files': ('البحث عن ملفات', 'Finding files'),
    'open_file': ('فتح ملف', 'Opening a file'),
    'open_link': ('فتح رابط', 'Opening a link'),
    'windows': ('النوافذ المفتوحة', 'Open windows'),
    'app_volume': ('صوت تطبيق', "An app's volume"),
    'reminder': ('تذكير', 'Reminder'),
    'routine': ('روتين', 'Routine'),
    'moai_project_task': ('مهمة لوكيل Mo AI', 'A task for the Mo AI agent'),
}


def step_title(name: str, en: bool) -> str:
    """The owner's words for a step (a tool, local commands, the agent), never a raw tool id."""
    name = str(name or '')
    if name in STEP_TITLES:
        return STEP_TITLES[name][1 if en else 0]
    try:
        import moai_tools
        table = moai_tools.TITLES_EN if en else moai_tools.TITLES_AR
        if name in table:
            return table[name]
    except Exception:
        pass
    return 'a tool' if en else 'إحدى أدوات ميرا'


def _step_phrase(name: str, en: bool) -> str:
    """A step inside a sentence: a tool in quotes, a fallback path as words."""
    title = step_title(name, en)
    return title if name in (ROUTER_STEP, AGENT_STEP) else f'«{title}»'


def _timed_out(exc: BaseException) -> bool:
    """The call gave up waiting, so the other side may still be working (never 'try again')."""
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
        return True
    cause = exc.__cause__
    if isinstance(cause, TimeoutError):
        return True
    return isinstance(cause, urllib.error.URLError) and isinstance(getattr(cause, 'reason', None), TimeoutError)


class GeminiUnavailable(Exception):
    """Gemini cannot answer; `reason` is a REASONS key (never secret text)."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason if reason in REASONS else 'unknown'


def classify_failure(exc: BaseException) -> str:
    """Map an exception to a REASONS key without reading credential-bearing text."""
    if isinstance(exc, GeminiUnavailable):
        return exc.reason
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
        return 'timeout'
    try:
        from google.genai import errors
        if isinstance(exc, errors.APIError):
            code = exc.code if isinstance(exc.code, int) else 0
            status = str(exc.status or '').upper()
            message = str(exc.message or '').lower()
            if code == 429 or 'RESOURCE_EXHAUSTED' in status:
                return 'quota'
            if code in (401, 403) or status in ('PERMISSION_DENIED', 'UNAUTHENTICATED') or 'api key' in message:
                return 'auth'
            if code >= 500:
                return 'server'
            return 'request'
    except ImportError:
        pass
    try:
        import httpx
        if isinstance(exc, httpx.TimeoutException):
            return 'timeout'
        if isinstance(exc, httpx.TransportError):
            return 'network'
    except ImportError:
        pass
    if isinstance(exc, (OSError, ConnectionError)):
        return 'network'
    return 'unknown'


def _safe_emit(emit: Optional[Callable[[str, str], Any]]) -> Callable[[str, str], None]:
    def say(kind: str, text: str) -> None:
        if emit is None:
            return
        try:
            emit(kind, text)
        except Exception:
            pass  # the UI sink must never break the brain
    return say


def _function_calls(response) -> list:
    try:
        parts = response.candidates[0].content.parts or []
    except (AttributeError, IndexError, TypeError):
        return []
    return [part.function_call for part in parts if getattr(part, 'function_call', None)]


def _text(response) -> str:
    try:
        parts = response.candidates[0].content.parts or []
    except (AttributeError, IndexError, TypeError):
        return ''
    return ''.join(part.text for part in parts
                   if getattr(part, 'text', None) and not getattr(part, 'thought', False)).strip()


_ORDER = {'error': 0, 'unsupported': 1, 'pending': 2, 'partial': 3, 'ok': 4}


def _worst(statuses) -> str:
    statuses = [s for s in statuses if s in _ORDER]
    return min(statuses, key=_ORDER.get) if statuses else 'error'


def _openai_schema(node):
    """Gemini's upper-case schema dialect → the JSON schema OpenAI-style tools expect."""
    if not isinstance(node, dict):
        return node
    out = {}
    for key, value in node.items():
        if key == 'type':
            out['type'] = str(value).lower()
        elif key == 'properties':
            out['properties'] = {name: _openai_schema(spec) for name, spec in value.items()}
        elif key == 'items':
            out['items'] = _openai_schema(value)
        elif key in ('description', 'enum', 'required', 'minimum', 'maximum', 'format'):
            out[key] = value
    return out


def openai_tools() -> list:
    return [{'type': 'function', 'function': {
        'name': item['name'], 'description': item['description'],
        'parameters': _openai_schema(item.get('parameters') or {'type': 'OBJECT', 'properties': {}})}}
        for item in tools.DECLARATIONS]


class GatewayUnavailable(Exception):
    """Mo AI's free cloud brain could not answer (class names only, never provider text)."""


def _post_gateway(body: dict) -> dict:
    request = urllib.request.Request(f'http://127.0.0.1:{GATEWAY_PORT}/v1/chat/completions',
                                     data=json.dumps(body).encode('utf-8'),
                                     headers={'Content-Type': 'application/json'})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=GATEWAY_TIMEOUT_S) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise GatewayUnavailable(f'http_{exc.code}') from None
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise GatewayUnavailable(type(exc).__name__) from None


# ─── the owner's choices (QSettings 'MoOS'/'Mira', shared with the window) ─────
def _qsettings():
    """Mira's own settings store, or None where Qt is not installed (the Echo's client)."""
    try:
        from PySide6.QtCore import QSettings
    except ImportError:
        return None
    return QSettings('MoOS', 'Mira')


def _clean_cloud_model(value) -> str:
    value = str(value or '').strip()
    if value.lower().startswith('cloud:'):
        value = value[6:].strip()
    return value if len(value) <= 160 and '..' not in value and CLOUD_MODEL_RE.fullmatch(value) else ''


def preferences() -> dict:
    """{'text_model': id or '', 'cloud_model': id or ''} — only values that pass validation.

    QSettings is reentrant, so every thread reads its own object; a value the page just saved is
    already visible here."""
    settings = _qsettings()
    if settings is None:
        return {'text_model': '', 'cloud_model': ''}
    text_model = str(settings.value('text_model', '') or '').strip()
    return {'text_model': text_model if text_model in TEXT_MODEL_IDS else '',
            'cloud_model': _clean_cloud_model(settings.value('cloud_model', ''))}


def set_text_model(model_id: str) -> str:
    """Keep the owner's typed-chat Gemini model. Raises ValueError for anything not offered."""
    if model_id not in TEXT_MODEL_IDS:
        raise ValueError('unknown text model')
    settings = _qsettings()
    if settings is None:
        raise RuntimeError('settings unavailable')
    settings.setValue('text_model', model_id)
    settings.sync()
    return model_id


def set_cloud_model(model_id: str) -> str:
    """Keep the model Mira's free cloud route asks for; '' = follow Mo AI's own setting."""
    settings = _qsettings()
    if settings is None:
        raise RuntimeError('settings unavailable')
    raw = str(model_id or '').strip()
    if not raw:
        settings.remove('cloud_model')
        settings.sync()
        return ''
    cleaned = _clean_cloud_model(raw)
    if not cleaned:
        raise ValueError('unknown cloud model')
    settings.setValue('cloud_model', cleaned)
    settings.sync()
    return cleaned


def _read_gemini_config(path: Path = None) -> dict:
    try:
        data = json.loads(Path(path or GEMINI_CONFIG).read_text())
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def gemini_settings(path: Path = None) -> dict:
    """What the Brain page may know of gemini.json: whether a key exists and which models are set.
    The key itself never leaves this function."""
    data = _read_gemini_config(path)
    key = data.get('api_key')
    text_model = data.get('text_model')
    voice_model = data.get('model')
    return {'has_key': isinstance(key, str) and bool(key.strip()),
            'voice_model': voice_model.strip() if isinstance(voice_model, str) else '',
            'text_model': text_model.strip() if isinstance(text_model, str) else ''}


def chosen_text_model(path: Path = None) -> tuple:
    """(model, source): the owner's pick in Mira ('mira'), else gemini.json ('config'), else the default."""
    picked = preferences().get('text_model')
    if picked:
        return picked, 'mira'
    configured = gemini_settings(path).get('text_model')
    if configured:
        return configured, 'config'
    return DEFAULT_TEXT_MODEL, 'default'


def _sync_client(api_key: str, timeout_ms: int):
    from google import genai
    from google.genai import types
    return genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=timeout_ms))


def probe_gemini(model: Optional[str] = None, path: Path = None, timeout_s: float = 20.0) -> dict:
    """Prove the saved key answers with `model` (default: the chosen typed model). Blocking; never
    raises. Returns {'status': 'ok'|'error', 'model', 'elapsed_ms', 'reason'?} — `reason` is a
    REASONS key, never the provider's text (which may echo request details)."""
    data = _read_gemini_config(path)
    model = model if model in TEXT_MODEL_IDS else chosen_text_model(path)[0]
    key = data.get('api_key')
    if not isinstance(key, str) or not key.strip():
        return {'status': 'error', 'model': model, 'elapsed_ms': 0, 'reason': 'config'}
    started = time.monotonic()
    try:
        client = _sync_client(key.strip(), int(timeout_s * 1000))
        response = client.models.generate_content(model=model, contents='Reply with the single word: ready')
        text = (getattr(response, 'text', '') or '').strip()
        result = {'status': 'ok' if text else 'error', 'model': model}
        if not text:
            result['reason'] = 'empty'
    except Exception as exc:   # classified, never echoed
        result = {'status': 'error', 'model': model, 'reason': classify_failure(exc)}
    result['elapsed_ms'] = int((time.monotonic() - started) * 1000)
    return result


# ─── which brain answered (the Brain page listens) ───────────────────────────
_answer_lock = threading.Lock()
_listeners: list = []
_last_answer: dict = {}


def add_answer_listener(callback: Callable[[dict], Any]) -> None:
    """Call `callback(summary)` (on the brain thread) after every typed answer. Bound methods are
    held weakly, so a page that goes away stops listening by itself."""
    try:
        ref = weakref.WeakMethod(callback)
    except TypeError:
        ref = (lambda cb=callback: cb)
    with _answer_lock:
        _listeners.append(ref)


def remove_answer_listener(callback: Callable[[dict], Any]) -> None:
    """Stop calling `callback` (a no-op when it was never added or already went away)."""
    with _answer_lock:
        _listeners[:] = [ref for ref in _listeners if ref() is not None and ref() != callback]


def last_answer() -> dict:
    with _answer_lock:
        return dict(_last_answer)


def _publish(summary: dict) -> None:
    global _last_answer
    with _answer_lock:
        _last_answer = dict(summary)
        alive = []
        for ref in _listeners:
            if ref() is not None:
                alive.append(ref)
        _listeners[:] = alive
        callbacks = [ref() for ref in alive]
    for callback in callbacks:
        if callback is None:
            continue
        try:
            callback(dict(summary))
        except Exception:
            pass   # a closed window must never break the brain


class TextBrain:
    """Typed questions through Gemini with Mira's fixed tools.

    client:          optional ready genai-compatible client (tests inject a fake)
    model:           overrides the owner's pick and `text_model` from gemini.json
    device_control:  optional Echo control for the `device_control` tool; it is
                     called on this brain's loop and may be async (see
                     `echo_device_control`)
    allowed_tools:   optional allowlist for tool names (others: unsupported)
    prefs:           optional callable returning the owner's choices (default
                     `preferences`, read again for every question)
    """

    def __init__(self, *, client=None, model: Optional[str] = None, config_path: Path = GEMINI_CONFIG,
                 device_control=None, allowed_tools=None, history_turns: int = HISTORY_TURNS, prefs=None):
        self._fixed_client = client
        self._model = model
        self.config_path = Path(config_path)
        self.device_control = device_control
        self.allowed_tools = frozenset(allowed_tools) if allowed_tools is not None else None
        self.request_confirmation = None   # the owner's cards (see tools.ToolContext)
        self.history_turns = history_turns
        self._prefs = prefs
        self._client = None
        self._client_key = None
        self._thinking = THINKING_LEVEL   # None once a model refuses thinking_level
        self.last: dict = {}              # the summary of this brain's latest answer

    # ── the owner's choices ──────────────────────────────────────────
    def _preferences(self) -> dict:
        try:
            found = (self._prefs or preferences)()
        except Exception:
            return {}
        return found if isinstance(found, dict) else {}

    def _text_model(self, data: Optional[dict] = None) -> str:
        """The first Gemini model to ask: explicit > the owner's pick in Mira > gemini.json > default."""
        picked = self._preferences().get('text_model')
        picked = picked if picked in TEXT_MODEL_IDS else ''
        configured = (data or {}).get('text_model')
        configured = configured.strip() if isinstance(configured, str) else ''
        return self._model or picked or configured or DEFAULT_TEXT_MODEL

    def _cloud_model(self) -> str:
        """The model Mira's free cloud route asks moai-gateway for ('' = Mo AI's own setting)."""
        return _clean_cloud_model(self._preferences().get('cloud_model'))

    # ── configuration ────────────────────────────────────────────────
    def _config(self) -> dict:
        try:
            data = json.loads(self.config_path.read_text())
        except (OSError, ValueError):
            raise GeminiUnavailable('config') from None
        if not isinstance(data, dict) or not isinstance(data.get('api_key'), str) or not data['api_key'].strip():
            raise GeminiUnavailable('config')
        return data

    def _client_and_model(self):
        if self._fixed_client is not None:
            return self._fixed_client, self._text_model()
        data = self._config()
        model = self._text_model(data)
        level = data.get('text_thinking_level')
        if isinstance(level, str) and level.strip():
            level = level.strip().upper()
            if level == 'OFF':
                self._thinking = None
            elif level in ('MINIMAL', 'LOW', 'MEDIUM', 'HIGH') and self._thinking is not None:
                self._thinking = level
        loop = asyncio.get_running_loop()
        stamp = (self.config_path.stat().st_mtime_ns, id(loop))
        if self._client is None or self._client_key != stamp:
            from google import genai
            from google.genai import types
            # The key never leaves this object: not logged, not in any event.
            self._client = genai.Client(api_key=data['api_key'].strip(),
                                        http_options=types.HttpOptions(timeout=int(MODEL_TIMEOUT_S * 1000)))
            self._client_key = stamp
        return self._client, model

    # ── public ───────────────────────────────────────────────────────
    async def ask(self, text: str, emit, lang: str = 'ar', city: Optional[str] = None,
                  cancel: Optional[threading.Event] = None) -> dict:
        """Answer one typed message. Never raises (except a cancellation nobody asked for).

        `cancel`: when this event is set and the task is cancelled (see `Turn.cancel`), the answer
        ends with status 'cancelled' and says what had already happened.

        Returns {'status', 'reply', 'tools', 'route', 'model', 'rounds', 'elapsed_ms',
        'fallback_reason'}; `route` is gemini | moai-cloud | router | moai | none and `model` is
        always a string (the model that answered or was answering, '' when none applies).
        """
        started = time.monotonic()
        say = _safe_emit(emit)
        en = lang == 'en'
        trace: list[dict] = []
        turn = {'route': 'none', 'model': '', 'inflight': ''}
        if not isinstance(text, str) or not text.strip() or len(text) > 6000:
            reply = 'Write a message of 1–6000 characters.' if en else 'اكتب رسالة من حرف إلى 6000 حرف.'
            return self._finish(say, {'status': 'error', 'reply': reply, 'route': 'none'}, trace, started,
                                publish=False)
        text = text.strip()
        if cancel is not None and cancel.is_set():
            return self._finish(say, self._stopped(turn, trace, en), trace, started)
        say('thinking', 'Thinking…' if en else 'أفكر…')

        def tool_emit(kind: str, payload: str) -> None:
            if kind == 'tool':
                try:
                    trace.append(json.loads(payload))
                except ValueError:
                    pass
            say(kind, payload)

        # The owner's language for this message (research answers in it even when the model rewrote
        # the question in English; health_report reads its matching halves); else the window's.
        ctx = tools.ToolContext(emit=tool_emit, device_control=self.device_control,
                                allowed_tools=self.allowed_tools, request_confirmation=self.request_confirmation,
                                lang=tools.message_lang(text, lang))
        try:
            result = await self._answer(text, say, ctx, lang, city, trace, turn)
        except asyncio.CancelledError:
            if cancel is None or not cancel.is_set():
                raise
            task = asyncio.current_task()
            if task is not None:
                task.uncancel()       # the owner's stop is handled here, not a failure of the loop
            result = self._stopped(turn, trace, en)
        return self._finish(say, result, trace, started)

    async def _answer(self, text, say, ctx, lang, city, trace, turn) -> dict:
        en = lang == 'en'
        try:
            async with asyncio.timeout(ASK_TIMEOUT_S):
                models = self._models()
                for index, candidate in enumerate(models):
                    turn.update(route='gemini', model=candidate)
                    try:
                        reply, model, rounds = await self._gemini(text, say, ctx, lang, city, trace, candidate,
                                                                  turn=turn)
                        break
                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:
                        # Another model may answer only while nothing has acted yet.
                        if trace or index == len(models) - 1 or classify_failure(exc) not in SWITCH_REASONS:
                            raise
            return {'status': 'ok', 'reply': reply, 'route': 'gemini', 'model': model, 'rounds': rounds}
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            reason = classify_failure(exc)
            note = REASONS[reason][1 if en else 0]
            if trace:
                # A tool already acted: never re-run the request through another path.
                done = '; '.join(item.get('summary', '') for item in trace)
                reply = (f'{note} before the answer was finished. What happened: {done}' if en else
                         f'{note} قبل أن يكتمل الرد. ما حدث فعلاً: {done}')
                return {'status': _worst(item.get('status') for item in trace), 'reply': reply,
                        'route': 'gemini', 'model': turn.get('model') or '', 'fallback_reason': reason}
            return await self._cloud_then_fallback(text, say, ctx, reason, lang, city, trace, turn)

    async def _cloud_then_fallback(self, text, say, ctx, reason, lang, city, trace, turn=None) -> dict:
        """The same tools on Mo AI's free cloud brain; then the router and the agent."""
        en = lang == 'en'
        note = REASONS[reason][1 if en else 0]
        turn = turn if turn is not None else {}
        turn.update(route='moai-cloud', model=self._cloud_model(), inflight='')
        try:
            reply, model, rounds = await asyncio.wait_for(self._gateway(text, say, ctx, lang, city, trace, turn=turn),
                                                          ASK_TIMEOUT_S)
            if reason != 'config':      # without a key this IS the normal path; say nothing then
                reply = (f'({note}; answered by Mo AI\'s free cloud brain) {reply}' if en else
                         f'({note}؛ أجاب عقل Mo AI السحابي المجاني) {reply}')
            result = {'status': 'ok', 'reply': reply, 'route': 'moai-cloud', 'model': model or turn.get('model') or '',
                      'rounds': rounds, 'fallback_reason': reason}
            if turn.get('model_refused'):
                result['model_refused'] = turn['model_refused']
            return result
        except asyncio.CancelledError:
            raise
        except Exception:
            if trace:
                done = '; '.join(item.get('summary', '') for item in trace)
                reply = (f'{note}, and the free cloud brain stopped before the answer. What happened: {done}' if en else
                         f'{note}، وتوقف العقل السحابي المجاني قبل الرد. ما حدث فعلاً: {done}')
                return {'status': _worst(item.get('status') for item in trace), 'reply': reply,
                        'route': 'moai-cloud', 'model': turn.get('model') or '', 'fallback_reason': reason}
        return await self._fallback(text, say, reason, en, city, turn=turn)

    async def _post(self, body: dict) -> dict:
        """One gateway call, with one more try when a free route hiccups (busy upstream, rate limit)."""
        try:
            return await asyncio.to_thread(_post_gateway, body)
        except GatewayUnavailable as exc:
            if str(exc) not in ('http_429', 'http_500', 'http_502', 'http_503', 'http_504', 'URLError', 'TimeoutError', 'timeout'):
                raise
            await asyncio.sleep(1.2)
            return await asyncio.to_thread(_post_gateway, body)

    async def _gateway(self, text, say, ctx, lang, city, trace, turn=None):
        """The tool loop over moai-gateway (OpenAI chat completions with tools, free models only).

        The owner's chosen model goes as `model: cloud:<id>`; moai-gateway's policy still decides
        what is allowed. If the gateway refuses that model (it left the catalogue, or it is billed
        under a free-only provider), Mo AI's own setting answers and the result says so."""
        en = lang == 'en'
        turn = turn if turn is not None else {}
        requested = self._cloud_model()
        say('thinking', 'Thinking (Mo AI cloud)…' if en else 'أفكر عبر عقل Mo AI…')
        messages = [{'role': 'system', 'content': tools.system_instruction(lang, city, channel='text')}]
        for past in tools.conversation_turns(self.history_turns, drop_trailing_user=text, max_chars=1200):
            messages.append({'role': 'user' if past['role'] == 'user' else 'assistant',
                             'content': past['parts'][0]['text']})
        messages.append({'role': 'user', 'content': text})
        declared = openai_tools()
        for round_no in range(1, MAX_ROUNDS + 1):
            last = round_no == MAX_ROUNDS
            body = {'messages': messages, 'stream': False}
            if requested:
                body['model'] = 'cloud:' + requested
            if not last:
                body.update(tools=declared, tool_choice='auto')
            try:
                data = await self._post(body)
            except GatewayUnavailable as exc:
                # Only the first call, before any tool ran, can mean "that model is refused"; later a 4xx
                # is about this conversation and must not quietly switch models halfway through.
                if (not requested or round_no != 1 or trace
                        or str(exc) not in ('http_400', 'http_404', 'http_409', 'http_422')):
                    raise
                turn['model_refused'] = requested
                requested = ''
                turn['model'] = ''
                body.pop('model', None)
                data = await self._post(body)
            try:
                message = data['choices'][0]['message']
            except (KeyError, IndexError, TypeError):
                raise GatewayUnavailable('shape') from None
            answered = data.get('model') if isinstance(data.get('model'), str) else ''
            if answered:
                turn['model'] = answered
            calls = [c for c in (message.get('tool_calls') or []) if isinstance(c, dict) and c.get('function')]
            if not calls or last:
                reply = str(message.get('content') or '').strip()
                if not reply:
                    if not trace:
                        raise GatewayUnavailable('empty')
                    reply = '; '.join(item.get('summary', '') for item in trace)
                return reply, answered or requested, round_no
            say('executing', 'Working on it…' if en else 'أنفّذ الطلب…')
            messages.append({'role': 'assistant', 'content': message.get('content') or '', 'tool_calls': calls})
            for call in calls:
                name = str(call['function'].get('name') or '')
                try:
                    args = json.loads(call['function'].get('arguments') or '{}')
                except ValueError:
                    args = {}
                turn['inflight'] = name
                result = await tools.run_tool(name, args if isinstance(args, dict) else {}, ctx)
                turn['inflight'] = ''
                messages.append({'role': 'tool', 'tool_call_id': str(call.get('id') or name),
                                 'content': json.dumps(result, ensure_ascii=False, default=str)[:8000]})
            say('thinking', 'Checking the result…' if en else 'أتحقق من النتيجة…')
        raise GatewayUnavailable('empty')

    @staticmethod
    def _stopped(turn: dict, trace: list, en: bool) -> dict:
        """The owner stopped the answer: say so, and what had already happened (never pretend)."""
        done = '; '.join(item.get('summary', '') for item in trace if item.get('summary'))
        reply = 'Stopped.' if en else 'أوقفتُ الرد.'
        if done:
            reply += f' What had already happened: {done}' if en else f' ما حدث فعلاً قبل الإيقاف: {done}'
        if turn.get('inflight'):
            step = _step_phrase(turn['inflight'], en)
            reply += (f' A step that had already started may still finish: {step}.' if en else
                      f' خطوة كانت قد بدأت قد تكتمل رغم الإيقاف: {step}.')
        return {'status': 'cancelled', 'reply': reply, 'route': turn.get('route') or 'none',
                'model': turn.get('model') or '', 'cancelled': True}

    def _finish(self, say, result: dict, trace: list, started: float, publish: bool = True) -> dict:
        result['route'] = result.get('route') or 'none'
        model = result.get('model')
        result['model'] = model if isinstance(model, str) else ''
        result.setdefault('rounds', 0)
        result.setdefault('fallback_reason', None)
        result['tools'] = trace
        result['elapsed_ms'] = int((time.monotonic() - started) * 1000)
        say('reply', json.dumps({'reply': result['reply'], 'status': result['status'],
                                 'route': result['route'], 'model': result['model']}, ensure_ascii=False))
        if publish:
            summary = {'route': result['route'], 'model': result['model'], 'status': result['status'],
                       'elapsed_ms': result['elapsed_ms'], 'fallback_reason': result['fallback_reason'],
                       'rounds': result['rounds'], 'tools': len(trace), 'at': time.time(),
                       'model_refused': result.get('model_refused') or ''}
            self.last = summary
            _publish(summary)
        return result

    # ── Gemini ───────────────────────────────────────────────────────
    def _models(self) -> list:
        """The chosen text model first, then the fallbacks (config `text_fallback_models`)."""
        if self._fixed_client is not None:
            return [self._text_model()]
        try:
            data = self._config()
        except GeminiUnavailable:
            return [self._text_model()]
        first = self._text_model(data)
        extra = data.get('text_fallback_models')
        # The fastest model closes the default chain, so a slower pick never ends the Gemini path early.
        extra = extra if isinstance(extra, list) else [*FALLBACK_TEXT_MODELS, DEFAULT_TEXT_MODEL]
        ordered = []
        for name in [first, *extra]:
            if isinstance(name, str) and name.strip() and name.strip() not in ordered:
                ordered.append(name.strip())
        return ordered

    async def _gemini(self, text, say, ctx, lang, city, trace, model_name=None, turn=None):
        from google.genai import types
        turn = turn if turn is not None else {}
        client, model = self._client_and_model()
        model = model_name or model
        history = tools.conversation_turns(self.history_turns, drop_trailing_user=text, max_chars=1200)
        contents: list = [types.Content(role=turn['role'], parts=[types.Part(text=turn['parts'][0]['text'])])
                          for turn in history]
        contents.append(types.Content(role='user', parts=[types.Part(text=text)]))
        base = dict(system_instruction=tools.system_instruction(lang, city, channel='text'),
                    tools=[types.Tool(function_declarations=tools.DECLARATIONS)],
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                    temperature=0.6)
        en = lang == 'en'
        retried = False
        for round_no in range(1, MAX_ROUNDS + 1):
            last = round_no == MAX_ROUNDS
            while True:
                config = types.GenerateContentConfig(
                    **base,
                    thinking_config=types.ThinkingConfig(thinking_level=self._thinking) if self._thinking else None,
                    tool_config=types.ToolConfig(function_calling_config=types.FunctionCallingConfig(mode='NONE'))
                    if last else None)
                try:
                    response = await asyncio.wait_for(
                        client.aio.models.generate_content(model=model, contents=contents, config=config),
                        MODEL_TIMEOUT_S)
                    break
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    reason = classify_failure(exc)
                    code = getattr(exc, 'code', None)
                    if self._thinking and code == 400 and reason == 'request' and 'thinking' in str(getattr(exc, 'message', '')).lower():
                        self._thinking = None      # this model has no thinking_level; ask again without it
                        continue
                    if reason == 'server' and not retried:
                        retried = True             # one quick retry for a transient 5xx
                        await asyncio.sleep(0.4)
                        continue
                    raise
            calls = _function_calls(response)
            if not calls or last:
                reply = _text(response)
                if not reply:
                    if not trace:
                        raise GeminiUnavailable('empty')
                    reply = ('; '.join(item.get('summary', '') for item in trace))
                return reply, model, round_no
            say('executing', 'Working on it…' if en else 'أنفّذ الطلب…')
            # Keep the model's own content (thought signatures included) in the history.
            contents.append(response.candidates[0].content)
            parts = []
            for call in calls:
                turn['inflight'] = call.name
                result = await tools.run_tool(call.name, dict(call.args or {}), ctx)
                turn['inflight'] = ''
                parts.append(types.Part(function_response=types.FunctionResponse(
                    id=getattr(call, 'id', None), name=call.name, response=result)))
            contents.append(types.Content(role='user', parts=parts))
            say('thinking', 'Checking the result…' if en else 'أتحقق من النتيجة…')
        raise GeminiUnavailable('empty')  # unreachable: the last round is forced to text

    # ── fallbacks ────────────────────────────────────────────────────
    async def _fallback(self, text, say, reason, en, city=None, turn=None) -> dict:
        note = REASONS[reason][1 if en else 0]
        turn = turn if turn is not None else {}
        turn.update(route='router', model='', inflight='')
        say('thinking', (note + ' · trying local commands…') if en else (note + ' · أجرّب الأوامر المحلية…'))
        try:
            import command_router
            # The dispatch runs on its own thread: a stop ends the wait, not the command, so while it runs
            # the owner's stop must say that it may still finish.
            turn['inflight'] = ROUTER_STEP
            routed = await asyncio.wait_for(asyncio.to_thread(command_router.dispatch, text, city), ROUTER_TIMEOUT_S)
        except asyncio.CancelledError:
            raise                          # `inflight` stays: the stop's reply names the running step
        except (asyncio.TimeoutError, TimeoutError):
            # Still running somewhere: never hand the same request to the agent as well.
            turn['inflight'] = ''
            reply = (f'({note}; local commands) The local command did not finish in time and may still complete. '
                     f'Check before asking again.' if en else
                     f'({note}؛ الأوامر المحلية) لم يكتمل الأمر المحلي في الوقت المحدد وقد يكتمل لاحقاً. '
                     f'تحقّق قبل أن تطلبه مرة أخرى.')
            return {'status': 'pending', 'reply': reply, 'route': 'router', 'fallback_reason': reason}
        except (ValueError, RuntimeError) as exc:
            # A recognised command with a clear problem (which device, which city…).
            turn['inflight'] = ''
            message = tools._safe_error(exc)
            reply = (f'({note}; answered by local commands) {message}' if en else
                     f'({note}؛ أجابت الأوامر المحلية) {message}')
            return {'status': 'error', 'reply': reply, 'route': 'router', 'fallback_reason': reason}
        except Exception:
            turn['inflight'] = ''
            routed = None
        else:
            turn['inflight'] = ''
        if routed:
            raw = routed.get('result') if isinstance(routed.get('result'), dict) else {}
            status = raw.get('status') if raw.get('status') in tools.STATUSES else 'error'
            message = str(routed.get('message') or '')
            say('tool', json.dumps({'name': 'command_router', 'status': status, 'summary': message[:200],
                                    'args_preview': str(routed.get('kind') or ''), 'elapsed_ms': 0},
                                   ensure_ascii=False))
            reply = (f'({note}; done by local commands) {message}' if en else
                     f'({note}؛ نُفّذ عبر الأوامر المحلية) {message}')
            return {'status': status, 'reply': reply, 'route': 'router', 'fallback_reason': reason,
                    'kind': routed.get('kind')}
        turn.update(route='moai', model='', inflight=AGENT_STEP)
        say('thinking', (note + ' · asking the Mo AI agent…') if en else (note + ' · أسأل وكيل Mo AI…'))
        try:
            import moai_link
            # The agent may act on this computer (its own tier and approvals decide); a stop ends only
            # the wait, so `inflight` stays set until it has answered.
            answer = await asyncio.wait_for(asyncio.to_thread(moai_link.ask, text), AGENT_TIMEOUT_S)
            turn['inflight'] = ''
            reply = (f'({note}; answered by the Mo AI agent) {answer}' if en else
                     f'({note}؛ أجاب وكيل Mo AI) {answer}')
            return {'status': 'ok', 'reply': reply, 'route': 'moai', 'fallback_reason': reason}
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            turn['inflight'] = ''
            if _timed_out(exc):
                reply = (f'{note}, and the Mo AI agent did not answer in time. It may still be working on your '
                         f'request, so check before asking again.' if en else
                         f'{note}، ولم يرد وكيل Mo AI في الوقت المحدد. قد يكون ما زال يعمل على طلبك، '
                         f'فتحقّق قبل أن تطلبه مرة أخرى.')
                return {'status': 'pending', 'reply': reply, 'route': 'moai', 'fallback_reason': reason}
            reply = (f'{note}, and neither local commands nor the Mo AI agent could answer '
                     f'({type(exc).__name__}). Try again shortly.' if en else
                     f'{note}، ولم تستطع الأوامر المحلية ولا وكيل Mo AI الإجابة ({type(exc).__name__}). حاول بعد قليل.')
            return {'status': 'error', 'reply': reply, 'route': 'none', 'fallback_reason': reason}


# ─── Qt-safe runner ───────────────────────────────────────────────────
class _LoopThread:
    """One private asyncio loop on a daemon thread for every typed question."""

    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run, name='mira-brain', daemon=True)
        self.thread.start()

    def _run(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def submit(self, coro) -> Future:
        return asyncio.run_coroutine_threadsafe(coro, self.loop)


_lock = threading.Lock()
_runner: Optional[_LoopThread] = None
_default: Optional[TextBrain] = None


def default_brain() -> TextBrain:
    global _default
    with _lock:
        if _default is None:
            _default = TextBrain()
        return _default


def set_device_control(device_control) -> None:
    """Give the shared brain an Echo control (e.g. `echo_device_control(bridge)`), or None."""
    default_brain().device_control = device_control


def set_confirmation(request_confirmation) -> None:
    """Give the shared brain the owner's confirmation cards (`Controller.request_confirmation`), or None."""
    default_brain().request_confirmation = request_confirmation


class Turn:
    """One typed question in flight (what `run_in_thread` returns).

    cancel()               stop it: the model call, the fallback or the wait for a tool ends now,
                           and the answer finishes with status 'cancelled', naming what had already
                           happened. A tool that had already started on its own thread may still
                           finish (the reply says so); a system change is never started by a stop,
                           and a card already waiting for the owner stays his to answer.
                           Returns False when the answer had already finished.
    result(timeout=None)   the result dict (as TextBrain.ask returns it)
    done() / cancelled_by_owner / add_done_callback(fn) / cancel_event
    """

    def __init__(self, loop, cancel_event: Optional[threading.Event] = None):
        self.cancel_event = cancel_event if cancel_event is not None else threading.Event()
        self._loop = loop
        self._task: Optional[asyncio.Task] = None
        self.future: Optional[Future] = None

    def cancel(self) -> bool:
        if self.future is not None and self.future.done():
            return False
        self.cancel_event.set()
        try:
            self._loop.call_soon_threadsafe(self._cancel_task)
        except RuntimeError:      # the loop is gone: nothing is running any more
            return False
        return True

    def _cancel_task(self) -> None:
        """On the brain loop. A task not started yet sees the event at its first line instead."""
        if self._task is not None and not self._task.done():
            self._task.cancel()

    @property
    def cancelled_by_owner(self) -> bool:
        return self.cancel_event.is_set()

    def done(self) -> bool:
        return self.future is not None and self.future.done()

    def result(self, timeout: Optional[float] = None) -> dict:
        return self.future.result(timeout)

    def add_done_callback(self, fn: Callable[['Turn'], Any]) -> None:
        self.future.add_done_callback(lambda _future: fn(self))


_current: Optional[Turn] = None
WATCH_INTERVAL_S = 0.15   # how often a caller's own cancel_event is looked at while a turn runs


def run_in_thread(text: str, emit, lang: str = 'ar', city: Optional[str] = None, *,
                  on_done: Optional[Callable[[dict], Any]] = None,
                  brain: Optional[TextBrain] = None,
                  cancel_event: Optional[threading.Event] = None) -> Turn:
    """Ask from any thread (e.g. a QObject slot). Returns a `Turn` (cancel(), result(), done()).

    `emit(kind, text)` and `on_done(result)` are called on the brain thread; a stopped turn still
    ends with its 'reply' event and `on_done` (status 'cancelled'). `cancel_event`, when given, is
    an event the caller may set from anywhere instead of calling `turn.cancel()`.
    """
    global _runner, _current
    with _lock:
        if _runner is None:
            _runner = _LoopThread()
        runner = _runner
    target = brain or default_brain()
    turn = Turn(runner.loop, cancel_event)

    async def watch():
        while not turn.cancel_event.is_set():
            await asyncio.sleep(WATCH_INTERVAL_S)
        turn._cancel_task()

    async def run():
        turn._task = asyncio.current_task()
        watcher = asyncio.ensure_future(watch()) if cancel_event is not None else None
        try:
            return await target.ask(text, emit, lang=lang, city=city, cancel=turn.cancel_event)
        finally:
            if watcher is not None:
                watcher.cancel()

    turn.future = runner.submit(run())
    with _lock:
        _current = turn

    def finished(done: Future):
        global _current
        with _lock:
            if _current is turn:
                _current = None
        if on_done is None:
            return
        try:
            result = done.result()
        except (asyncio.CancelledError, FutureCancelled):
            result = {'status': 'cancelled', 'reply': 'أوقفتُ الرد.' if lang != 'en' else 'Stopped.',
                      'tools': [], 'route': 'none', 'model': '', 'cancelled': True}
        except BaseException as exc:  # a bug: still report honestly
            result = {'status': 'error', 'reply': 'تعذّر إكمال الطلب', 'tools': [], 'route': 'none',
                      'model': '', 'error': type(exc).__name__}
        try:
            on_done(result)
        except Exception:
            pass
    turn.future.add_done_callback(finished)
    return turn


def current_turn() -> Optional[Turn]:
    """The typed question still in flight, if any."""
    with _lock:
        return _current if _current is not None and not _current.done() else None


def cancel_current() -> bool:
    """Stop the typed question in flight (the window's Stop / Esc). False when none is running."""
    turn = current_turn()
    return turn.cancel() if turn is not None else False


def echo_device_control(bridge, timeout: float = 5.0):
    """An async device_control that runs the Echo command on the bridge's own loop.

    `bridge` is mira_bridge.Bridge (attributes `loop`, `online`, `voice`). The
    aioesphomeapi client is not thread-safe, so the command is marshalled.
    """
    async def control(args: dict) -> dict:
        async def on_bridge_loop():
            voice = getattr(bridge, 'voice', None)
            if voice is None or not getattr(bridge, 'online', False):
                raise RuntimeError('Echo غير متصل الآن')
            return voice.device_command(args)
        future = asyncio.run_coroutine_threadsafe(on_bridge_loop(), bridge.loop)
        return await asyncio.wait_for(asyncio.wrap_future(future), timeout)
    return control
