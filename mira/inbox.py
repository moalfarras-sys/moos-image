"""The agent's approvals inbox: every file write and every command the Mo AI agent asks for,
in front of the owner while it can still be answered.

The Mo AI agent (Hermes, driven by moai-agent-api's runtime, `usr/lib/moai/moai_runtime.py`) parks
each `write_file` and each sandboxed `run_command` as one approval row and waits 120 s for the
owner. Without an answer it runs nothing and the agent's task fails with "approval expired". Mira
started those tasks (`moai_project_task`), so Mira must show those questions. This module reads
the queue and sends the owner's answer back. The controller turns every item into a card on
ActionCards (kind 'agent').

The shapes, matched exactly to the service (`usr/bin/moai-agent-api`, `moai_runtime.Runtime`):

    GET  /api/approvals -> [{id, session, command, cwd, expires, task, warning, allowed, created}, ...]
         runtime (every current MoOS): `command` is JSON {"tool": "run_command"|"write_file",
         "arguments": {...}}; `expires` is epoch ms, 120 s after the request; `allowed` is
         ['allow-once', 'deny']; `task` is ''. The older OpenClaw path sends the literal shell
         command, a task id, its own warning and no session.
    GET  /api/tasks?status=running -> [{id, title, status: 'running', ...}, ...]   (read-only)
         A started task runs up to 700 s and asks for approvals all along, long after Mira's own
         turn ended, so a running task keeps the queue read fast.
    POST /api/approval/resolve {id, decision}  (exactly these two keys)
         -> {ok: true, id, decision}
         -> {error: 'approval is no longer pending'}   expired, or answered somewhere else
         -> {error: 'agent_unreachable', ...}           the service is not running

What this module guarantees:
- Nothing is ever allowed except by an explicit resolve(id, 'allow-once') for an item that is
  still pending here. resolve() is a Python method, deliberately NOT a Qt slot: QML reaches it only
  through the card's own buttons (controller.approveAction / rejectAction), never directly.
  The decisions are one-time only: 'allow-always' is never sent or offered, and a request whose
  full text is too long to show cannot be allowed.
- A decision is sent once. While it is on its way the item is marked `resolving` and a second
  answer is refused. `resolved` reports only what the service answered. An answered request is
  never announced again by a read that started before the answer (`_settled`).
- Expired items drop out on time, even between polls. An item whose answer is on its way is never
  reported `gone`: its own `resolved` tells what happened.
- The queue is read every 1.5 s while agent work is active (busy(), or an agent task the service
  reports running), for 15 s after it, for 120 s after every answer (the agent usually asks
  again at once) and while anything waits. Otherwise it is read every 20 s. Only one read is in
  flight at a time.
- Every public method may be called from any thread. Signals reach the Qt thread only.
- Under MIRA_TEST_MODE nothing touches the machine (review() fills visibly sample items).
"""
from __future__ import annotations

import html
import json
import os
import re
import threading
import time
import unicodedata

from PySide6.QtCore import QObject, Property, QTimer, Signal, Slot

TEST_MODE = os.environ.get('MIRA_TEST_MODE') == '1'

FAST_MS = 1500              # while agent work is active, or anything waits
IDLE_MS = 20000             # otherwise
LINGER_S = 15.0             # keep reading fast this long after the work ends
AFTER_ANSWER_S = 120.0      # ... and this long after an answer: a working agent asks again at once
TASK_CHECK_S = 6.0          # how often the service's running tasks are read (at most)
SETTLED_S = 20.0            # longer than a read may take (15 s): a stale read cannot revive an answer
TASK_SOURCE = 'agent-task'  # the busy source a running agent task holds
MAX_ITEMS = 50
MAX_SHOWN = 16000           # the longest request the owner can be shown whole (runtime caps at 12,000)
NOTIFY_CHARS = 300          # a notification may offer "allow" only when the whole command fits in it
NOTIFY_LINES = 6
DECISIONS = ('allow-once', 'deny')
CARD_PREFIX = 'agent-'
_ID = re.compile(r'[0-9a-fA-F-]{36}')
# Plasma's notification server turns every '\n' into a line break and then collapses every other
# run of whitespace to one space (and drops it at both ends). A command whose whitespace that would
# change cannot be allowed from a notice: what is read there must be exactly what runs.
_NOTICE_SPACING = re.compile(r'\s{2,}|[^\S \n]|^\s|\s$')
# The runtime's own fixed warning text. It is replaced by a translated, tool-specific note.
# Any other warning, such as the gateway's, is shown word for word.
RUNTIME_WARNING = ('Agent action: review the complete command or file change. '
                   'Runs as your user; no elevated access.')

STRINGS = {
    'agent_approval_title': ('الوكيل يطلب إذنك', 'The agent asks for your permission'),
    'agent_approval_run': ('الوكيل يريد تشغيل أمر', 'The agent wants to run a command'),
    'agent_approval_write': ('الوكيل يريد كتابة ملف', 'The agent wants to write a file'),
    'agent_approval_badge': ('الوكيل · مرة واحدة', 'Agent · once'),
    'agent_approval_allow': ('اسمح مرة واحدة', 'Allow once'),
    'agent_approval_deny': ('ارفض', 'Deny'),
    'agent_approval_review': ('اعرض الطلب', 'Show request'),
    'agent_approval_collapsed': ('افتح الطلب واقرأه كاملاً قبل أن تسمح به.',
                                 'Open the request and read all of it before you allow it.'),
    'agent_approval_left': ('يبقى {t} للرد؛ بعدها لا يُنفَّذ شيء', '{t} left to answer; after that nothing runs'),
    'agent_approval_project': ('المشروع', 'Project'),
    'agent_approval_in': ('في', 'In'),
    'agent_approval_new_file': ('ملف جديد', 'new file'),
    'agent_approval_replace': ('يستبدل الملف الحالي', 'replaces the current file'),
    'agent_approval_lines': ('الأسطر: {n}', 'Lines: {n}'),
    'agent_approval_run_note': ('يعمل مرة واحدة بصلاحياتك داخل صندوق معزول: مجلد المشروع فقط قابل للكتابة، '
                                'بلا شبكة ولا مجلد المنزل ولا كلمات سر ولا صلاحيات مدير، ويتوقف بعد 60 ثانية.',
                                'Runs once as you, inside a sandbox: only the project folder is writable; no network, '
                                'home folder, passwords or administrator rights; it stops after 60 seconds.'),
    'agent_approval_write_note': ('يكتب هذا الملف مرة واحدة داخل المشروع، ويُرفض إن تغيّر الملف أثناء مراجعتك.',
                                  'Writes this one file inside the project, once; refused if the file changes while you review it.'),
    'agent_approval_hidden': ('تنبيه: في النص محارف مخفية، ظاهرة هنا بشكل ⟦U+…⟧. لا تسمح إن لم تفهمها.',
                              'Warning: the text contains hidden characters, shown here as ⟦U+…⟧. Do not allow it unless you understand them.'),
    'agent_approval_too_long': ('الطلب أطول من أن يُعرض كاملاً، فلا يمكن السماح به. ارفضه واطلب تغييراً أصغر.',
                                'This request is too long to show in full, so it cannot be allowed. Deny it and ask for a smaller change.'),
    'agent_approval_notify_review': ('الأمر طويل؛ راجعه كاملاً في نافذة ميرا قبل السماح.',
                                     'The command is long; review it in full in Mira before allowing it.'),
    'agent_approval_notify_spacing': ('مسافات هذا الأمر لا تظهر هنا كما هي؛ راجعه في نافذة ميرا قبل السماح.',
                                      "This command's spacing cannot be shown exactly here; review it in Mira before allowing it."),
    'agent_approval_notify_request': ('راجع الطلب كاملاً في نافذة ميرا قبل السماح.',
                                      'Review the full request in Mira before allowing it.'),
    'agent_approval_notify_file': ('راجع محتوى الملف كاملاً في نافذة ميرا قبل السماح.',
                                   "Review the file's full content in Mira before allowing it."),
    'agent_approval_notify_hidden': ('في الطلب محارف مخفية؛ راجعه في نافذة ميرا.',
                                     'The request contains hidden characters; review it in Mira.'),
    'agent_approval_sending': ('جارٍ إرسال قرارك إلى الوكيل…', 'Sending your decision to the agent…'),
    'agent_approval_allowed': ('سمحت مرة واحدة؛ الوكيل ينفّذه الآن وسيذكر نتيجته.',
                               'Allowed once; the agent runs it now and will report its result.'),
    'agent_approval_denied': ('رفضت؛ لم يُنفَّذ شيء.', 'Denied; nothing ran.'),
    'agent_approval_gone': ('لم يعد الطلب بانتظارك؛ لم يُنفَّذ بقرارك هذا.',
                            'The request is no longer waiting; your answer did not run it.'),
    'agent_approval_elsewhere': ('لم يعد بانتظارك: أُجيب من مكان آخر أو توقّف الوكيل.',
                                 'No longer waiting: answered elsewhere, or the agent stopped.'),
    'agent_approval_failed': ('تعذّر إرسال قرارك إلى الوكيل', 'Could not send your decision to the agent'),
    'agent_approval_unreachable': ('وكيل Mo AI لا يستجيب الآن', 'The Mo AI agent is not answering right now'),
    'agent_approval_voice': ('أوامر الوكيل تُراجع على بطاقتها: اقرأ الأمر كاملاً ثم اضغط «اسمح مرة واحدة». أما «لا» فترفضها كلها.',
                             'Agent commands are allowed only on their card, after you read the exact command. Saying “no” denies them all.'),
    'agent_approval_voice_denied': ('أرسلت رفضك لطلبات الوكيل المنتظرة.', 'Sent your denial of the waiting agent requests.'),
    'agent_approval_waiting': ('طلبات الوكيل بانتظار موافقتك: {n}', 'Agent requests waiting for your approval: {n}'),
}


# ─── pure helpers (no Qt, no network) ─────────────────────────────────
def card_id(approval_id: str) -> str:
    """The ActionCards key of an agent approval."""
    return CARD_PREFIX + str(approval_id)


def approval_id(card: str) -> str:
    """The agent approval behind an ActionCards key ('' when the key is not an agent card)."""
    card = str(card or '')
    if not card.startswith(CARD_PREFIX):
        return ''
    value = card[len(CARD_PREFIX):]
    return value if _ID.fullmatch(value) else ''


# Characters of letter or mark categories that render as nothing, or as a blank: Hangul fillers
# (known from invisible-identifier backdoors), the combining grapheme joiner, Khmer inherent vowels,
# Mongolian variation selectors and the blank braille cell.
_BLANK = frozenset((0x034F, 0x115F, 0x1160, 0x17B4, 0x17B5, 0x180B, 0x180C, 0x180D, 0x180F,
                    0x2800, 0x3164, 0xFFA0))


def _invisible(ch: str) -> bool:
    code = ord(ch)
    category = unicodedata.category(ch)
    if category in ('Cf', 'Cc', 'Co', 'Cs', 'Cn', 'Zl', 'Zp'):
        return True                               # format/control/private/unassigned, line separators
    if category == 'Zs' and ch != ' ':
        return True                               # no-break, en/em, ideographic… spaces look like ' '
    if 0xFE00 <= code <= 0xFE0F or 0xE0100 <= code <= 0xE01EF:
        return True                               # variation selectors (used to smuggle text)
    return code in _BLANK


def reveal(text: str) -> tuple[str, bool]:
    """The text with every invisible or look-alike character made visible, and whether there were any.

    Bidirectional overrides, zero-width and control characters, variation selectors, blank
    fillers and spaces other than ' ' could make a command look different from what runs. Each is
    written as ⟦U+XXXX⟧. Newlines and tabs are kept.
    """
    out, hidden = [], False
    text = str(text or '')
    for index, ch in enumerate(text):
        if ch in '\n\t' or (ch == '\r' and text[index + 1:index + 2] == '\n'):
            out.append(ch)      # a line break (Windows' CR LF too); a lone CR can hide text, so it shows
        elif _invisible(ch):
            out.append(f'⟦U+{ord(ch):04X}⟧')
            hidden = True
        else:
            out.append(ch)
    return ''.join(out), hidden


def normalize(row, now_ms: int):
    """One API row → the item Mira shows, or None when it cannot be shown or answered."""
    if not isinstance(row, dict):
        return None
    aid = str(row.get('id') or '')
    if not _ID.fullmatch(aid):
        return None
    try:
        expires = int(row.get('expires') or 0)
    except (TypeError, ValueError):
        expires = 0
    if expires and expires <= now_ms:
        return None
    try:
        created = int(row.get('created') or 0)
    except (TypeError, ValueError):
        created = 0
    raw = str(row.get('command') or '')
    # The gateway path sends the literal shell command; the runtime sends JSON {tool, arguments}.
    tool, project, path, command, new_file = 'exec', '', '', raw, False
    payload = None
    if raw.lstrip().startswith('{'):
        try:
            payload = json.loads(raw)
        except ValueError:
            payload = None
    if isinstance(payload, dict) and isinstance(payload.get('tool'), str) \
            and isinstance(payload.get('arguments'), dict):
        args = payload['arguments']
        project = str(args.get('project') or '')[:200]
        # Any other tool, or a request that does not have its tool's fields: the owner reads the
        # whole request, word for word, under the general title.
        tool = 'request'
        if payload['tool'] == 'run_command' and isinstance(args.get('command'), str) and args['command'].strip():
            tool, command = 'run_command', args['command']
        elif payload['tool'] == 'write_file' and isinstance(args.get('path'), str) \
                and isinstance(args.get('content'), str):
            tool, path, command = 'write_file', args['path'][:1000], args['content']
            new_file = not args.get('sha256')
    allowed = [d for d in (row.get('allowed') or []) if d in DECISIONS] or list(DECISIONS)
    shown, hidden = reveal(command)
    return {
        'id': aid,
        'session': str(row.get('session') or '')[:120],
        'task': str(row.get('task') or '')[:120],
        'tool': tool,
        'project': project,
        'path': path,
        'command': command,              # exact, as it will run or be written
        'shown': shown,                  # the same, with hidden characters made visible
        'hidden': hidden,
        'complete': len(command) <= MAX_SHOWN,
        'new_file': new_file,
        'cwd': str(row.get('cwd') or '')[:1000],
        'warning': str(row.get('warning') or '')[:2000],
        'allowed': allowed,
        'created': created,
        'expires': expires,
        'resolving': '',
    }


def title(item: dict, s: dict) -> str:
    key = {'run_command': 'agent_approval_run', 'exec': 'agent_approval_run',
           'write_file': 'agent_approval_write'}.get(item.get('tool'), 'agent_approval_title')
    return s.get(key, key)


def _ltr(text: str) -> str:
    """A path kept left-to-right inside an Arabic line (a Unicode isolate; the slash stays in front)."""
    return '⁦' + text + '⁩' if text else ''


def context_line(item: dict, s: dict) -> str:
    """Where it happens, whole (the card wraps it; the exact request itself is `review_text`):
    for a file its path, whether it is new and its length; then, on a line of its own, the folder."""
    parts = []
    if item.get('tool') == 'write_file':
        lines = item['command'].count('\n') + (1 if item['command'] and not item['command'].endswith('\n') else 0)
        parts.append(_ltr(reveal(item.get('path', ''))[0]))
        parts.append(s.get('agent_approval_new_file' if item.get('new_file') else 'agent_approval_replace', ''))
        parts.append(s.get('agent_approval_lines', '{n}').replace('{n}', str(lines)))
    # The folder is the precise fact; the project's registered name stands in only without one.
    place = ''
    if item.get('cwd'):
        place = s.get('agent_approval_in', '') + ' ' + _ltr(reveal(item['cwd'])[0])
    elif item.get('project'):
        place = s.get('agent_approval_project', '') + ' ' + _ltr(reveal(item['project'])[0])
    return '\n'.join(p for p in (' · '.join(p for p in parts if p.strip()), place) if p.strip())


def safety_note(item: dict, s: dict) -> str:
    """What allowing it means, in the owner's language, plus every warning that applies."""
    notes = []
    if not item.get('complete', True):
        notes.append(s.get('agent_approval_too_long', ''))
    if item.get('hidden'):
        notes.append(s.get('agent_approval_hidden', ''))
    warning = item.get('warning', '')
    if warning and warning != RUNTIME_WARNING:
        notes.append(reveal(warning)[0])
    elif item.get('tool') == 'run_command':
        notes.append(s.get('agent_approval_run_note', ''))
    elif item.get('tool') == 'write_file':
        notes.append(s.get('agent_approval_write_note', ''))
    elif warning:
        notes.append(warning)
    return '\n'.join(n for n in notes if n)


def review_text(item: dict) -> str:
    """The exact request as the owner reads it: the command, or the file's full new content."""
    shown = item.get('shown', '')
    if not item.get('complete', True):
        return shown[:MAX_SHOWN] + '\n…'
    if item.get('tool') in ('run_command', 'exec'):
        return '$ ' + shown
    return shown


def card(item: dict, s: dict) -> dict:
    """The ActionCards row of one waiting approval (controller.actions roles, kind 'agent')."""
    return {'aid': card_id(item['id']), 'kind': 'agent', 'name': item.get('tool', ''),
            'title': title(item, s), 'detail': context_line(item, s), 'reason': safety_note(item, s),
            'stage': 'ask', 'category': 'agent_confirm', 'summary': '', 'output': review_text(item),
            'started': 0, 'expires': int(item.get('expires') or 0), 'origin': 'agent'}


def notification(item: dict, s: dict) -> dict:
    """A desktop notification for it. It offers 'allow' only for a command whose every character
    reaches the notice unchanged: complete, no hidden characters, short, and no whitespace that
    Plasma would collapse. A file, or any other request, is only ever allowed on its card."""
    shown = item.get('shown', '')
    command = item.get('tool') in ('run_command', 'exec')
    short = 0 < len(shown) <= NOTIFY_CHARS and shown.count('\n') < NOTIFY_LINES
    spacing = bool(_NOTICE_SPACING.search(shown))
    fits = command and short and item.get('complete', True) and not item.get('hidden') and not spacing
    if fits:
        first = '$ ' + shown
    elif item.get('hidden'):
        first = s.get('agent_approval_notify_hidden', '')
    elif item.get('tool') == 'write_file':
        first = s.get('agent_approval_notify_file', '')
    elif not command:
        first = s.get('agent_approval_notify_request', '')
    elif spacing and short and item.get('complete', True):
        first = s.get('agent_approval_notify_spacing', '')
    else:
        first = s.get('agent_approval_notify_review', '')
    lines = [first]
    context = context_line(item, s)
    if context:
        lines.append(context)
    # Plasma renders a subset of HTML in a notification body: escape, so what is read is what runs.
    return {'title': title(item, s), 'body': html.escape('\n'.join(lines), quote=False), 'can_allow': bool(fits)}


def notice_ttl_ms(item: dict, now_ms: int) -> int:
    """How long a notification about it may stay up: never past the moment it stops waiting."""
    expires = int(item.get('expires') or 0)
    return max(1000, expires - now_ms) if expires else 120000


def failure_text(error: str, s: dict) -> str:
    """What the owner reads when an answer could not be delivered. Never a raw backend code:
    the service's words may be English, or name an engine; the caller logs the code instead."""
    base = s.get('agent_approval_failed', '')
    if error == 'agent_unreachable':
        return base + ': ' + s.get('agent_approval_unreachable', '')
    return base


def waiting_text(n: int, s: dict) -> str:
    return s.get('agent_approval_waiting', '{n}').replace('{n}', str(int(n)))


def review_items(now_ms: int | None = None) -> list[dict]:
    """Visibly sample approvals for review renders (MIRA_TEST_MODE); never sent anywhere."""
    now_ms = int(time.time() * 1000) if now_ms is None else now_ms
    rows = [
        {'id': '00000000-0000-4000-8000-00000000a001', 'session': 'sample', 'task': '',
         'command': json.dumps({'tool': 'run_command', 'arguments': {
             'project': 'sample-project', 'command': 'python3 -m pytest tests/ -q  # sample'}}),
         'cwd': '/var/home/sample/Projects/sample-project', 'warning': RUNTIME_WARNING,
         'allowed': list(DECISIONS), 'created': 0, 'expires': now_ms + 96000},
        {'id': '00000000-0000-4000-8000-00000000a002', 'session': 'sample', 'task': '',
         'command': json.dumps({'tool': 'write_file', 'arguments': {
             'project': 'sample-project', 'path': 'docs/sample/getting-started.md', 'sha256': 'sample',
             'content': '# Sample project\n\nThis text is sample review data.\n\n'
                        + ''.join(f'- sample step {n}\n' for n in range(1, 13))}}),
         'cwd': '/var/home/sample/Projects/sample-project', 'warning': RUNTIME_WARNING,
         'allowed': list(DECISIONS), 'created': 0, 'expires': now_ms + 118000},
    ]
    return [item for item in (normalize(row, now_ms) for row in rows) if item]


def _classify(result, approval: str, decision: str) -> dict:
    """The service's answer to one resolve → {'status': 'ok'|'gone'|'error', 'error': str}."""
    if isinstance(result, dict) and result.get('ok') is True \
            and result.get('id') == approval and result.get('decision') == decision:
        return {'status': 'ok', 'error': ''}
    error = result.get('error') if isinstance(result, dict) else ''
    if isinstance(error, str) and 'no longer pending' in error:
        return {'status': 'gone', 'error': error}
    if isinstance(result, dict) and result.get('ok') is True:
        return {'status': 'error', 'error': 'unexpected_reply'}
    return {'status': 'error', 'error': str(error or 'unexpected_reply')[:300]}


# ─── the inbox ───────────────────────────────────────────────────────
class AgentInbox(QObject):
    """The approvals the Mo AI agent waits for, kept current. See the module docstring."""
    changed = Signal()
    arrived = Signal('QVariantMap')              # a new item appeared (show it)
    gone = Signal(str, str)                      # approval id, 'expired' | 'elsewhere' (not answered here)
    resolved = Signal(str, str, 'QVariantMap')   # approval id, decision, {'status': ok|gone|error, 'error'}
    _done = Signal(str, object)                  # worker → Qt thread
    _busy_request = Signal(bool, str)
    _poke = Signal()                             # poll now (queued onto the Qt thread)
    _refresh = Signal()                          # emit `changed` on the Qt thread

    def __init__(self, parent=None, live=None, clock=time.time):
        super().__init__(parent)
        self._live = (not TEST_MODE) if live is None else bool(live)
        self._clock = clock
        self._lock = threading.Lock()
        self._items: dict[str, dict] = {}
        self._inflight: dict[str, str] = {}      # approval id → decision on its way
        self._settled: dict[str, float] = {}     # approval id → until when a read may not revive it
        self._sources: set[str] = set()
        self._linger_until = 0.0
        self._next_task_check = 0.0
        self._polling = False
        self._running = False
        self._status = 'idle'                    # idle | online | unreachable | error
        self._error = ''
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._tick)
        self._done.connect(self._deliver)
        self._busy_request.connect(self._apply_busy)
        self._poke.connect(self._on_poke)
        self._refresh.connect(self.changed)

    # ── what QML and the controller read ───────────────────────────
    def _now_ms(self) -> int:
        return int(self._clock() * 1000)

    def _get_items(self):
        with self._lock:
            return [dict(v) for v in sorted(self._items.values(), key=lambda v: (v['expires'] or 0, v['id']))]
    items = Property('QVariantList', _get_items, notify=changed)
    count = Property(int, lambda self: len(self._items), notify=changed)
    status = Property(str, lambda self: self._status, notify=changed)
    error = Property(str, lambda self: self._error, notify=changed)
    active = Property(bool, lambda self: bool(self._sources), notify=changed)
    tasksRunning = Property(bool, lambda self: TASK_SOURCE in self._sources, notify=changed)

    def item(self, approval: str):
        """The pending item (a copy), or None when it is not pending here any more."""
        with self._lock:
            value = self._items.get(str(approval or ''))
            if value is None or (value['expires'] and value['expires'] <= self._now_ms()):
                return None
            return dict(value)

    # ── lifecycle (the controller's, from Python: no page may switch the inbox off) ──
    def start(self):
        """Begin reading the queue (Qt thread). Does nothing in review/test mode."""
        if not self._live or self._running:
            return
        self._running = True
        self._tick()

    def stop(self):
        self._running = False
        self._timer.stop()

    @Slot(bool)
    @Slot(bool, str)
    def busy(self, active=True, source='mira'):
        """Agent work started (True) or ended (False); any thread. Several sources may be active."""
        self._busy_request.emit(bool(active), str(source or 'mira'))

    @Slot()
    def poll(self):
        """Read the queue now (any thread)."""
        self._poke.emit()

    # Not a Slot: see the module docstring. Only the controller's card buttons call it.
    def resolve(self, approval: str, decision: str) -> bool:
        """Send the OWNER's answer, once; any thread. True when it was sent (the result arrives as
        `resolved`), False when it was refused here: unknown or expired id, a decision already on
        its way, a decision this request does not allow, or a request too long to be read whole."""
        approval, decision = str(approval or ''), str(decision or '')
        if decision not in DECISIONS or not _ID.fullmatch(approval) or not self._live:
            return False
        with self._lock:
            value = self._items.get(approval)
            if value is None or (value['expires'] and value['expires'] <= self._now_ms()):
                return False
            if approval in self._inflight or decision not in value['allowed']:
                return False
            if decision == 'allow-once' and not value['complete']:
                return False
            self._inflight[approval] = decision
            value['resolving'] = decision
        self._refresh.emit()       # QML shows the item as resolving (on the Qt thread)
        self._work('resolve:' + approval + ':' + decision, self._post_resolve, approval, decision)
        return True

    def review(self):
        """Visibly sample items for review renders (MIRA_TEST_MODE only)."""
        with self._lock:
            self._items = {item['id']: item for item in review_items(self._now_ms())}
            self._status = 'online'
        self.changed.emit()

    # ── Qt thread ───────────────────────────────────────────────────
    def _fast(self) -> bool:
        return bool(self._sources) or bool(self._items) or self._clock() < self._linger_until

    def _schedule(self, soon=False):
        if not self._running:
            return
        interval = FAST_MS if (soon or self._fast()) else IDLE_MS
        if not self._timer.isActive() or self._timer.remainingTime() > interval:
            self._timer.start(interval)

    def _set_source(self, source, active):
        """Qt thread only. When the last source ends, the reads stay fast a little longer."""
        if active:
            self._sources.add(source)
        elif source in self._sources:
            self._sources.discard(source)
            if not self._sources:
                self._linger_until = max(self._linger_until, self._clock() + LINGER_S)

    @Slot(bool, str)
    def _apply_busy(self, active, source):
        self._set_source(source, active)
        self._schedule()
        self.changed.emit()

    @Slot()
    def _on_poke(self):
        self._prune()
        self.changed.emit()
        if self._running and not self._polling:
            self._timer.stop()
            self._tick()

    def _prune(self):
        """Drop what expired; each one is reported as gone('expired'), unless its answer is on its way."""
        now = self._now_ms()
        with self._lock:
            dead = [k for k, v in self._items.items() if v['expires'] and v['expires'] <= now]
            for key in dead:
                del self._items[key]
        for key in dead:
            if key not in self._inflight:
                self.gone.emit(key, 'expired')
        return bool(dead)

    @Slot()
    def _tick(self):
        if self._prune():
            self.changed.emit()
        if not self._running:
            return
        if self._polling:
            self._schedule()
            return
        self._polling = True
        now = self._clock()
        with_tasks = now >= self._next_task_check
        if with_tasks:
            self._next_task_check = now + TASK_CHECK_S
        self._work('poll', self._fetch, with_tasks)

    def _work(self, tag, fn, *args):
        def run():
            try:
                result = fn(*args)
            except Exception as exc:       # the backend's own words, never a traceback
                result = {'error': str(exc)[:300] if isinstance(exc, (ValueError, RuntimeError)) else type(exc).__name__}
            self._done.emit(tag, result)
        threading.Thread(target=run, daemon=True, name='mira-inbox').start()

    @staticmethod
    def _fetch(with_tasks=False):
        """Worker thread: the queue, and (at most every TASK_CHECK_S) the tasks that run now.
        Both are plain reads: /api/tasks lists the workspace file and changes nothing."""
        import moai_agent
        approvals = moai_agent.get('/api/approvals')
        tasks = moai_agent.get('/api/tasks', status='running') if with_tasks else None
        return {'approvals': approvals, 'tasks': tasks}

    @staticmethod
    def _post_resolve(approval, decision):
        import moai_agent
        return moai_agent.post('/api/approval/resolve', {'id': approval, 'decision': decision})

    @Slot(str, object)
    def _deliver(self, tag, result):
        if tag == 'poll':
            self._on_poll(result)
        elif tag.startswith('resolve:'):
            _, approval, decision = tag.split(':', 2)
            self._on_resolve(approval, decision, result)

    def _note_tasks(self, tasks):
        """A running agent task keeps the reads fast; a read that fails counts as none running."""
        running = isinstance(tasks, list) and any(
            isinstance(t, dict) and t.get('status') == 'running' for t in tasks)
        self._set_source(TASK_SOURCE, running)

    def _on_poll(self, result):
        self._polling = False
        if isinstance(result, dict) and 'approvals' in result:
            approvals, tasks = result['approvals'], result.get('tasks')
        else:
            approvals, tasks = result, None
        if tasks is not None:
            self._note_tasks(tasks)
        if isinstance(approvals, list):
            now = self._now_ms()
            clock = self._clock()
            self._settled = {k: until for k, until in self._settled.items() if until > clock}
            fresh = {}
            for row in approvals[:MAX_ITEMS * 2]:
                item = normalize(row, now)
                # A read that started before an answer still lists what was answered: skip it.
                if item is not None and item['id'] not in self._settled and len(fresh) < MAX_ITEMS:
                    fresh[item['id']] = item
            with self._lock:
                old = self._items
                for key, item in fresh.items():
                    if key in self._inflight:
                        item['resolving'] = self._inflight[key]
                self._items = fresh
            new = [fresh[k] for k in fresh if k not in old]
            left = [(k, old[k]) for k in old if k not in fresh]
            self._status, self._error = 'online', ''
            for key, value in left:
                if key not in self._inflight:
                    expired = value['expires'] and value['expires'] <= now + 1000
                    self.gone.emit(key, 'expired' if expired else 'elsewhere')
            for item in sorted(new, key=lambda v: (v['created'], v['expires'])):
                self.arrived.emit(dict(item))
        else:
            # Keep what is shown: each item still expires on time, and an answer reports its own error.
            error = approvals.get('error') if isinstance(approvals, dict) else 'bad_reply'
            self._status = 'unreachable' if error == 'agent_unreachable' else 'error'
            self._error = str(error or 'bad_reply')[:300]
        self.changed.emit()
        self._schedule()

    def _on_resolve(self, approval, decision, result):
        outcome = _classify(result, approval, decision)
        with self._lock:
            self._inflight.pop(approval, None)
            value = self._items.get(approval)
            if outcome['status'] in ('ok', 'gone'):
                self._items.pop(approval, None)
            elif value is not None:
                value['resolving'] = ''       # still pending: the owner may answer again
        if outcome['status'] in ('ok', 'gone'):
            self._settled[approval] = self._clock() + SETTLED_S
        if outcome['status'] == 'ok':
            # Allowed or denied, the agent's turn goes on and its next write or command follows at once.
            self._linger_until = max(self._linger_until, self._clock() + AFTER_ANSWER_S)
        if outcome['status'] == 'error' and outcome['error'] == 'agent_unreachable':
            self._status, self._error = 'unreachable', 'agent_unreachable'
        self.resolved.emit(approval, decision, {**outcome, 'id': approval, 'decision': decision})
        self.changed.emit()
        if self._running and not self._polling:
            self._schedule(soon=True)
