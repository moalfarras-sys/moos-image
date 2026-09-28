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
from that thread (a Qt Signal's emit is safe there).
"""
from __future__ import annotations

import asyncio
import json
import threading
import time
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
SWITCH_REASONS = ('quota', 'server', 'timeout', 'empty')
MAX_ROUNDS = 5            # model calls per question, the last one forced to text
MODEL_TIMEOUT_S = 30.0    # one generate_content call
ASK_TIMEOUT_S = 240.0     # whole Gemini path, tools included
ROUTER_TIMEOUT_S = 120.0  # deterministic fallback (may read back Home Assistant)
AGENT_TIMEOUT_S = 200.0   # Mo AI agent fallback
HISTORY_TURNS = 12
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


class TextBrain:
    """Typed questions through Gemini with Mira's fixed tools.

    client:          optional ready genai-compatible client (tests inject a fake)
    model:           overrides `text_model` from gemini.json
    device_control:  optional Echo control for the `device_control` tool; it is
                     called on this brain's loop and may be async (see
                     `echo_device_control`)
    allowed_tools:   optional allowlist for tool names (others: unsupported)
    """

    def __init__(self, *, client=None, model: Optional[str] = None, config_path: Path = GEMINI_CONFIG,
                 device_control=None, allowed_tools=None, history_turns: int = HISTORY_TURNS):
        self._fixed_client = client
        self._model = model
        self.config_path = Path(config_path)
        self.device_control = device_control
        self.allowed_tools = frozenset(allowed_tools) if allowed_tools is not None else None
        self.history_turns = history_turns
        self._client = None
        self._client_key = None
        self._thinking = THINKING_LEVEL   # None once a model refuses thinking_level

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
            return self._fixed_client, self._model or DEFAULT_TEXT_MODEL
        data = self._config()
        model = self._model or data.get('text_model') or DEFAULT_TEXT_MODEL
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
    async def ask(self, text: str, emit, lang: str = 'ar', city: Optional[str] = None) -> dict:
        """Answer one typed message. Never raises (except cancellation).

        Returns {'status', 'reply', 'tools', 'route', 'model', 'rounds',
        'elapsed_ms', 'fallback_reason'}.
        """
        started = time.monotonic()
        say = _safe_emit(emit)
        en = lang == 'en'
        trace: list[dict] = []
        if not isinstance(text, str) or not text.strip() or len(text) > 6000:
            reply = 'Write a message of 1–6000 characters.' if en else 'اكتب رسالة من حرف إلى 6000 حرف.'
            return self._finish(say, {'status': 'error', 'reply': reply, 'route': 'none'}, trace, started)
        text = text.strip()
        say('thinking', 'Thinking…' if en else 'أفكر…')

        def tool_emit(kind: str, payload: str) -> None:
            if kind == 'tool':
                try:
                    trace.append(json.loads(payload))
                except ValueError:
                    pass
            say(kind, payload)

        ctx = tools.ToolContext(emit=tool_emit, device_control=self.device_control,
                                allowed_tools=self.allowed_tools)
        try:
            async with asyncio.timeout(ASK_TIMEOUT_S):
                models = self._models()
                for index, candidate in enumerate(models):
                    try:
                        reply, model, rounds = await self._gemini(text, say, ctx, lang, city, trace, candidate)
                        break
                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:
                        # Another model may answer only while nothing has acted yet.
                        if trace or index == len(models) - 1 or classify_failure(exc) not in SWITCH_REASONS:
                            raise
            result = {'status': 'ok', 'reply': reply, 'route': 'gemini', 'model': model, 'rounds': rounds}
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
                result = {'status': _worst(item.get('status') for item in trace), 'reply': reply,
                          'route': 'gemini', 'fallback_reason': reason}
            else:
                result = await self._fallback(text, say, reason, en, city)
        return self._finish(say, result, trace, started)

    def _finish(self, say, result: dict, trace: list, started: float) -> dict:
        result.setdefault('model', None)
        result.setdefault('rounds', 0)
        result.setdefault('fallback_reason', None)
        result['tools'] = trace
        result['elapsed_ms'] = int((time.monotonic() - started) * 1000)
        say('reply', json.dumps({'reply': result['reply'], 'status': result['status'],
                                 'route': result['route']}, ensure_ascii=False))
        return result

    # ── Gemini ───────────────────────────────────────────────────────
    def _models(self) -> list:
        """The configured text model first, then the fallbacks (config `text_fallback_models`)."""
        if self._fixed_client is not None:
            return [self._model or DEFAULT_TEXT_MODEL]
        try:
            data = self._config()
        except GeminiUnavailable:
            return [self._model or DEFAULT_TEXT_MODEL]
        first = self._model or data.get('text_model') or DEFAULT_TEXT_MODEL
        extra = data.get('text_fallback_models')
        extra = extra if isinstance(extra, list) else list(FALLBACK_TEXT_MODELS)
        ordered = []
        for name in [first, *extra]:
            if isinstance(name, str) and name.strip() and name not in ordered:
                ordered.append(name.strip())
        return ordered

    async def _gemini(self, text, say, ctx, lang, city, trace, model_name=None):
        from google.genai import types
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
                result = await tools.run_tool(call.name, dict(call.args or {}), ctx)
                parts.append(types.Part(function_response=types.FunctionResponse(
                    id=getattr(call, 'id', None), name=call.name, response=result)))
            contents.append(types.Content(role='user', parts=parts))
            say('thinking', 'Checking the result…' if en else 'أتحقق من النتيجة…')
        raise GeminiUnavailable('empty')  # unreachable: the last round is forced to text

    # ── fallbacks ────────────────────────────────────────────────────
    async def _fallback(self, text, say, reason, en, city=None) -> dict:
        note = REASONS[reason][1 if en else 0]
        say('thinking', (note + ' · trying local commands…') if en else (note + ' · أجرّب الأوامر المحلية…'))
        try:
            import command_router
            routed = await asyncio.wait_for(asyncio.to_thread(command_router.dispatch, text, city), ROUTER_TIMEOUT_S)
        except asyncio.CancelledError:
            raise
        except (ValueError, RuntimeError) as exc:
            # A recognised command with a clear problem (which device, which city…).
            message = tools._safe_error(exc)
            reply = (f'({note}; answered by local commands) {message}' if en else
                     f'({note}؛ أجابت الأوامر المحلية) {message}')
            return {'status': 'error', 'reply': reply, 'route': 'router', 'fallback_reason': reason}
        except Exception:
            routed = None
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
        say('thinking', (note + ' · asking the Mo AI agent…') if en else (note + ' · أسأل وكيل Mo AI…'))
        try:
            import moai_link
            answer = await asyncio.wait_for(asyncio.to_thread(moai_link.ask, text), AGENT_TIMEOUT_S)
            reply = (f'({note}; answered by the Mo AI agent) {answer}' if en else
                     f'({note}؛ أجاب وكيل Mo AI) {answer}')
            return {'status': 'ok', 'reply': reply, 'route': 'moai', 'fallback_reason': reason}
        except asyncio.CancelledError:
            raise
        except Exception as exc:
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


def run_in_thread(text: str, emit, lang: str = 'ar', city: Optional[str] = None, *,
                  on_done: Optional[Callable[[dict], Any]] = None,
                  brain: Optional[TextBrain] = None) -> Future:
    """Ask from any thread (e.g. a QObject slot). Returns a concurrent Future.

    `emit(kind, text)` and `on_done(result)` are called on the brain thread.
    """
    global _runner
    with _lock:
        if _runner is None:
            _runner = _LoopThread()
        runner = _runner
    target = brain or default_brain()
    future = runner.submit(target.ask(text, emit, lang=lang, city=city))
    if on_done is not None:
        def finished(done: Future):
            try:
                result = done.result()
            except BaseException as exc:  # cancelled or a bug: still report honestly
                result = {'status': 'error', 'reply': 'تعذّر إكمال الطلب', 'tools': [], 'route': 'none',
                          'error': type(exc).__name__}
            try:
                on_done(result)
            except Exception:
                pass
        future.add_done_callback(finished)
    return future


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
