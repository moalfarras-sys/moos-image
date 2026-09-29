"""Persistent reminders and timers for Mira, in ~/.config/mo-dot/mira-reminders.json (0600).

A reminder is a message due at a time; a timer is the same thing set by a countdown. Both live
in one private file so they survive a restart of the app or the machine. Nothing here speaks or
notifies: `due(now)` returns the items that have come due (marking them fired and rescheduling a
repeat), and the caller announces them.

    r = Reminders()
    r.add('أطفئ الفرن', parse_when(minutes=20), kind='timer')
    r.add('اجتماع', parse_when(at='19:30'), repeat='weekdays')
    for item in r.due(datetime.now()):   # call this on a tick
        announce(item['text'])
"""
from __future__ import annotations

import json
import os
import re
import secrets
import threading
from datetime import date as _date, datetime, time as _time, timedelta
from pathlib import Path
from typing import Optional, Union

DEFAULT_PATH = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'mo-dot' / 'mira-reminders.json'
MAX_ITEMS = 200
KINDS = ('reminder', 'timer')
REPEATS = (None, 'daily', 'weekdays')
_WEEKDAYS_AR = ['الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت', 'الأحد']


# ─── when helpers ─────────────────────────────────────────────────────


def parse_when(minutes: Optional[float] = None, at: Optional[str] = None,
               date: Optional[str] = None, now: Optional[datetime] = None) -> datetime:
    """A local, timezone-aware due time from exactly one of:
        minutes  — this many minutes from now (a countdown/timer);
        at       — 'HH:MM' today, or tomorrow if that time already passed today;
        date+at  — an ISO date (YYYY-MM-DD), at 'HH:MM' (or midnight).
    Raises ValueError on bad input."""
    base = (now or datetime.now()).astimezone()
    given = [x is not None for x in (minutes, at if date is None else None, date)]
    if date is not None:
        try:
            day = _date.fromisoformat(str(date).strip())
        except ValueError:
            raise ValueError('التاريخ يجب أن يكون بصيغة YYYY-MM-DD') from None
        clock = _parse_hhmm(at) if at else _time(0, 0)
        return datetime.combine(day, clock, tzinfo=base.tzinfo)
    if sum(bool(x) for x in (minutes is not None, at)) != 1:
        raise ValueError('حدّد إمّا عدد الدقائق أو الوقت أو التاريخ')
    if minutes is not None:
        try:
            minutes = float(minutes)
        except (TypeError, ValueError):
            raise ValueError('عدد الدقائق يجب أن يكون رقماً') from None
        if not 0 < minutes <= 60 * 24 * 30:
            raise ValueError('المدة يجب أن تكون بين دقيقة وشهر')
        return base + timedelta(minutes=minutes)
    clock = _parse_hhmm(at)
    due = datetime.combine(base.date(), clock, tzinfo=base.tzinfo)
    if due <= base:
        due += timedelta(days=1)
    return due


def _parse_hhmm(value: str) -> _time:
    text = str(value or '').strip()
    m = re.fullmatch(r'(\d{1,2}):(\d{2})', text)
    if not m:
        raise ValueError('الوقت يجب أن يكون بصيغة HH:MM')
    hour, minute = int(m.group(1)), int(m.group(2))
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError('وقت غير صالح')
    return _time(hour, minute)


def _coerce_due(due: Union[datetime, float, int, str], now: Optional[datetime] = None) -> datetime:
    base = (now or datetime.now()).astimezone()
    if isinstance(due, datetime):
        return due if due.tzinfo else due.replace(tzinfo=base.tzinfo)
    if isinstance(due, bool):
        raise ValueError('وقت غير صالح')
    if isinstance(due, (int, float)):
        return base + timedelta(seconds=float(due))          # a seconds-from-now offset
    if isinstance(due, str):
        try:
            parsed = datetime.fromisoformat(due)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=base.tzinfo)
        except ValueError:
            raise ValueError('تعذّر فهم وقت التذكير') from None
    raise ValueError('وقت غير صالح')


def spoken_when(dt: datetime) -> str:
    """«الساعة 7 و30 دقيقة مساءً» for an Arabic summary."""
    dt = dt.astimezone()
    hour12 = dt.hour % 12 or 12
    h = dt.hour
    period = ('بعد منتصف الليل' if h < 5 else 'صباحاً' if h < 12 else 'ظهراً' if h < 15 else
              'عصراً' if h < 18 else 'مساءً' if h < 21 else 'ليلاً')
    minutes = f'و{dt.minute} دقيقة' if dt.minute else ''
    clock = f'الساعة {hour12}' + (f' {minutes}' if minutes else '') + f' {period}'
    return clock


# ─── the store ────────────────────────────────────────────────────────


class Reminders:
    """Thread-safe reminders/timers persisted to a private JSON file."""

    def __init__(self, path: Union[str, Path, None] = None):
        self.path = Path(path) if path else DEFAULT_PATH
        self._lock = threading.RLock()

    # -- persistence -------------------------------------------------
    def _load(self) -> list[dict]:
        try:
            raw = json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return []
        items = raw.get('reminders', raw) if isinstance(raw, dict) else raw
        return [i for i in items if isinstance(i, dict) and 'id' in i and 'due' in i] if isinstance(items, list) else []

    def _write(self, items: list[dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.path.parent, 0o700)
        except OSError:
            pass
        payload = json.dumps({'version': 1, 'reminders': items}, ensure_ascii=False, indent=1)
        tmp = self.path.with_suffix('.tmp')
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(payload)
        os.chmod(tmp, 0o600)
        os.replace(tmp, self.path)

    # -- public ------------------------------------------------------
    def add(self, text: str, due: Union[datetime, float, int, str], kind: str = 'reminder',
            repeat: Optional[str] = None, label: Optional[str] = None,
            now: Optional[datetime] = None) -> dict:
        text = ' '.join(str(text or '').split())
        if not 1 <= len(text) <= 500:
            raise ValueError('نص التذكير بين حرف و500 حرف')
        if kind not in KINDS:
            raise ValueError('نوع التذكير غير مدعوم')
        if repeat not in REPEATS:
            raise ValueError('نوع التكرار غير مدعوم')
        when = _coerce_due(due, now)
        item = {'id': 't' + secrets.token_hex(5), 'text': text, 'kind': kind,
                'due': when.isoformat(), 'repeat': repeat, 'fired': False,
                'label': (' '.join(str(label).split())[:60] if label else None),
                'created': (now or datetime.now()).astimezone().isoformat()}
        with self._lock:
            items = self._load()
            if len(items) >= MAX_ITEMS:
                raise ValueError('وصلت قائمة التذكيرات إلى حدها')
            items.append(item)
            self._write(items)
        return dict(item, spoken=spoken_when(when))

    def list(self, include_fired: bool = False) -> list[dict]:
        with self._lock:
            items = self._load()
        items.sort(key=lambda i: i.get('due', ''))
        if include_fired:
            return items
        return [i for i in items if not (i.get('fired') and i.get('repeat') in (None, 'none'))]

    def get(self, action_id: str) -> Optional[dict]:
        with self._lock:
            for item in self._load():
                if item['id'] == action_id:
                    return item
        return None

    def cancel(self, selector: str) -> dict:
        """Cancel by id, exact label, or a text substring. Returns what was removed."""
        needle = ' '.join(str(selector or '').split())
        if not needle:
            return {'status': 'error', 'removed': [], 'summary': 'حدّد التذكير المراد إلغاؤه'}
        with self._lock:
            items = self._load()
            low = needle.lower()
            removed = [i for i in items if i['id'] == needle or (i.get('label') or '').lower() == low
                       or low in i.get('text', '').lower()]
            if not removed:
                return {'status': 'partial', 'removed': [], 'summary': f'لا يوجد تذكير يطابق «{needle}»'}
            keep = [i for i in items if i not in removed]
            self._write(keep)
        return {'status': 'ok', 'removed': removed, 'count': len(removed),
                'summary': f'ألغيت {len(removed)} تذكيراً'}

    def _next_occurrence(self, item: dict, after: datetime) -> Optional[datetime]:
        try:
            due = datetime.fromisoformat(item['due'])
        except (KeyError, ValueError):
            return None
        if due.tzinfo is None:
            due = due.replace(tzinfo=after.tzinfo)
        repeat = item.get('repeat')
        if repeat not in ('daily', 'weekdays'):
            return None
        nxt = due
        for _ in range(370):
            nxt = nxt + timedelta(days=1)
            if repeat == 'daily' or nxt.weekday() < 5:      # Mon–Fri
                if nxt > after:
                    return nxt
        return None

    def due(self, now: Optional[datetime] = None) -> list[dict]:
        """Return items whose due time has arrived; mark one-shots fired, reschedule repeats."""
        moment = (now or datetime.now()).astimezone()
        fired_now = []
        with self._lock:
            items = self._load()
            changed = False
            for item in items:
                if item.get('fired'):
                    continue
                try:
                    due = datetime.fromisoformat(item['due'])
                except (KeyError, ValueError):
                    continue
                if due.tzinfo is None:
                    due = due.replace(tzinfo=moment.tzinfo)
                if due <= moment:
                    fired_now.append(dict(item, spoken=spoken_when(due)))
                    nxt = self._next_occurrence(item, moment)
                    if nxt is not None:
                        item['due'] = nxt.isoformat()
                        item['fired'] = False
                    else:
                        item['fired'] = True
                    changed = True
            # Drop long-fired one-shots so the file does not grow without bound.
            if changed:
                keep = [i for i in items if not (i.get('fired') and i.get('repeat') in (None, 'none'))]
                self._write(keep)
        return fired_now

    def next_due(self, now: Optional[datetime] = None) -> Optional[dict]:
        """The soonest not-yet-fired item, or None."""
        moment = (now or datetime.now()).astimezone()
        with self._lock:
            pending = []
            for item in self._load():
                if item.get('fired'):
                    continue
                try:
                    due = datetime.fromisoformat(item['due'])
                except (KeyError, ValueError):
                    continue
                if due.tzinfo is None:
                    due = due.replace(tzinfo=moment.tzinfo)
                pending.append((due, item))
        if not pending:
            return None
        due, item = min(pending, key=lambda p: p[0])
        return dict(item, spoken=spoken_when(due))
