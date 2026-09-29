"""Named multi-step routines for Mira, in ~/.config/mo-dot/mira-routines.json (0600).

A routine is a saved list of steps the owner assembled once («صباح الخير» = open the mail app,
read the weather, turn the desk lamp on). Each step names an existing Mira tool and its
arguments; the routine does NOT contain commands, only tool calls the registry already allows.
Running one is done by an injected `runner(tool, args) -> result dict`, so this module never
executes anything itself and cannot widen what the assistant can do.

    r = Routines()
    r.save('صباح الخير', [{'tool': 'computer_open_application', 'args': {'name': 'بريد'}},
                          {'tool': 'current_weather', 'args': {'city': 'دبي'}, 'say': 'الطقس اليوم'}],
           description='روتين الصباح')
    result = r.run('صباح الخير', runner)          # sync
    result = await r.arun('صباح الخير', arunner)  # async
"""
from __future__ import annotations

import asyncio
import inspect
import json
import os
import re
import threading
from pathlib import Path
from typing import Awaitable, Callable, Optional, Union

DEFAULT_PATH = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'mo-dot' / 'mira-routines.json'
MAX_ROUTINES = 60
MAX_STEPS = 12
MAX_DEPTH = 1                       # a routine may call tools, but not nest another routine below depth 1
_STEP_ERROR_STATUSES = ('error', 'unsupported')
_NAME_RE = re.compile(r'[\w\-\s؀-ۿ]{1,60}', re.UNICODE)


def _clean_name(name: str) -> str:
    name = ' '.join(str(name or '').split())
    if not name or not _NAME_RE.fullmatch(name):
        raise ValueError('اسم الروتين غير صالح')
    return name


def _validate_steps(steps) -> list[dict]:
    if not isinstance(steps, (list, tuple)) or not steps:
        raise ValueError('الروتين يحتاج خطوة واحدة على الأقل')
    if len(steps) > MAX_STEPS:
        raise ValueError(f'الحد الأقصى {MAX_STEPS} خطوة')
    out = []
    for raw in steps:
        if not isinstance(raw, dict) or not raw.get('tool'):
            raise ValueError('كل خطوة يجب أن تحدّد أداة')
        tool = str(raw['tool']).strip()
        if not re.fullmatch(r'[a-z][a-z0-9_]{0,49}', tool):
            raise ValueError(f'اسم الأداة «{tool}» غير صالح')
        if tool in ('run_routine', 'routine', 'run'):
            raise ValueError('لا يمكن لخطوة أن تشغّل روتيناً آخر')
        args = raw.get('args', {})
        if args is None:
            args = {}
        if not isinstance(args, dict):
            raise ValueError('وسائط الخطوة يجب أن تكون كائناً')
        step = {'tool': tool, 'args': args}
        if raw.get('say'):
            step['say'] = str(raw['say'])[:200]
        if raw.get('continue_on_error'):
            step['continue_on_error'] = True
        out.append(step)
    return out


class Routines:
    """Thread-safe routine store; running is delegated to an injected runner."""

    def __init__(self, path: Union[str, Path, None] = None):
        self.path = Path(path) if path else DEFAULT_PATH
        self._lock = threading.RLock()

    # -- persistence -------------------------------------------------
    def _load(self) -> dict:
        try:
            raw = json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return {}
        items = raw.get('routines', raw) if isinstance(raw, dict) else {}
        return items if isinstance(items, dict) else {}

    def _write(self, routines: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.path.parent, 0o700)
        except OSError:
            pass
        payload = json.dumps({'version': 1, 'routines': routines}, ensure_ascii=False, indent=1)
        tmp = self.path.with_suffix('.tmp')
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(payload)
        os.chmod(tmp, 0o600)
        os.replace(tmp, self.path)

    # -- public ------------------------------------------------------
    def save(self, name: str, steps, description: str = '') -> dict:
        name = _clean_name(name)
        clean = _validate_steps(steps)
        entry = {'name': name, 'steps': clean,
                 'description': ' '.join(str(description or '').split())[:300]}
        with self._lock:
            routines = self._load()
            if name not in routines and len(routines) >= MAX_ROUTINES:
                raise ValueError('وصلت قائمة الروتينات إلى حدها')
            routines[name] = entry
            self._write(routines)
        return dict(entry, steps_count=len(clean))

    def get(self, name: str) -> Optional[dict]:
        with self._lock:
            routine = self._load().get(_clean_name(name))
        return dict(routine) if routine else None

    def list(self) -> list[dict]:
        with self._lock:
            routines = self._load()
        return [{'name': r['name'], 'description': r.get('description', ''),
                 'steps_count': len(r.get('steps', []))}
                for r in sorted(routines.values(), key=lambda r: r.get('name', ''))]

    def delete(self, name: str) -> dict:
        name = _clean_name(name)
        with self._lock:
            routines = self._load()
            if name not in routines:
                return {'status': 'partial', 'summary': f'لا يوجد روتين اسمه «{name}»'}
            del routines[name]
            self._write(routines)
        return {'status': 'ok', 'name': name, 'summary': f'حذفت الروتين «{name}»'}

    # -- running -----------------------------------------------------
    def _prepare(self, name: str, depth: int) -> dict:
        if depth > MAX_DEPTH:
            raise ValueError('لا يُسمح باستدعاء روتين داخل روتين لأكثر من مستوى')
        routine = self.get(name)
        if routine is None:
            raise KeyError(name)
        return routine

    @staticmethod
    def _finish(name: str, results: list[dict], stopped: bool) -> dict:
        ran = len(results)
        failed = [r for r in results if r['status'] in _STEP_ERROR_STATUSES]
        if stopped:
            status = 'partial'
            summary = f'توقّف الروتين «{name}» عند الخطوة {ran} بسبب خطأ'
        elif failed:
            status = 'partial'
            summary = f'شغّلت «{name}»: {ran} خطوة، فشل {len(failed)}'
        else:
            status = 'ok'
            summary = f'أتممت الروتين «{name}» · {ran} خطوة'
        return {'status': status, 'name': name, 'steps': results, 'ran': ran,
                'failed': len(failed), 'stopped_early': stopped, 'summary': summary}

    @staticmethod
    def _step_result(step: dict, raw) -> dict:
        status = raw.get('status') if isinstance(raw, dict) else None
        if status not in ('ok', 'pending', 'partial', 'error', 'unsupported'):
            status = 'error'
        summary = raw.get('summary') if isinstance(raw, dict) else None
        return {'tool': step['tool'], 'status': status,
                'summary': summary or '', 'say': step.get('say'),
                'result': raw if isinstance(raw, dict) else {'raw': str(raw)[:500]}}

    def run(self, name: str, runner: Callable[[str, dict], dict], depth: int = 0) -> dict:
        """Run a routine synchronously. `runner(tool, args)` returns a result dict.
        Stops at the first error unless that step is marked continue_on_error."""
        routine = self._prepare(name, depth)
        results: list[dict] = []
        stopped = False
        for step in routine['steps']:
            try:
                raw = runner(step['tool'], dict(step.get('args', {})))
                if inspect.isawaitable(raw):
                    raw = asyncio.get_event_loop().run_until_complete(raw)
            except Exception as exc:                        # a broken runner is a failed step, not a crash
                raw = {'status': 'error', 'error': type(exc).__name__,
                       'summary': f'تعذّرت الخطوة {step["tool"]}'}
            res = self._step_result(step, raw)
            results.append(res)
            if res['status'] in _STEP_ERROR_STATUSES and not step.get('continue_on_error'):
                stopped = True
                break
        return self._finish(name, results, stopped)

    async def arun(self, name: str, runner: Callable[[str, dict], Union[dict, Awaitable[dict]]],
                   depth: int = 0) -> dict:
        """Run a routine on the event loop; `runner` may be sync or async."""
        routine = self._prepare(name, depth)
        results: list[dict] = []
        stopped = False
        for step in routine['steps']:
            try:
                raw = runner(step['tool'], dict(step.get('args', {})))
                if inspect.isawaitable(raw):
                    raw = await raw
            except Exception as exc:
                raw = {'status': 'error', 'error': type(exc).__name__,
                       'summary': f'تعذّرت الخطوة {step["tool"]}'}
            res = self._step_result(step, raw)
            results.append(res)
            if res['status'] in _STEP_ERROR_STATUSES and not step.get('continue_on_error'):
                stopped = True
                break
        return self._finish(name, results, stopped)
