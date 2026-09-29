"""Owner-taught preferences, device names and the conversation. Knowledge only, never capabilities.

The conversation is one append-only file (`mira-conversation.jsonl`, 0600). Every record carries the
chat it belongs to (`thread`); records written before chats existed carry none and belong to the
default chat, so nothing is migrated or rewritten. The chat index (`mira-threads.json`, 0600) holds
only what the owner chose about a chat (its name, pinned, archived) and which chat is open; a
damaged index is set aside beside it, never overwritten.

The model is fed ONLY the open chat (`recent_messages`): starting a new chat stops older turns from
reaching it. A regenerated reply is hidden by a tombstone record, never by editing history.
"""
import json
import os
import re
import secrets
import threading
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

DIR = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'mo-dot'
CONFIG = DIR / 'mira-memory.json'
PROFILE = DIR / 'mira-profile.txt'
CONVERSATION = DIR / 'mira-conversation.jsonl'
THREADS = DIR / 'mira-threads.json'
COLORS = {'pink','purple','blue','green','yellow','orange','red','white'}

DEFAULT_THREAD = 'main'                 # the chat of every record written before chats existed
ROLES = ('user', 'mira', 'action', 'error')
STATUSES = ('ok', 'pending', 'partial', 'error', 'unsupported')   # tools.STATUSES: what a result may be
TEXT_MAX = 6000                         # one record: what the composer and controller.send accept
TITLE_MAX = 80
MAX_BYTES = 2_000_000                   # the conversation file is trimmed when it grows past this
KEEP_BYTES = 1_200_000                  # newest records a trim keeps
PINNED_BYTES = 600_000                  # records of pinned chats a trim keeps first, wherever they are
_ID = re.compile(r'[A-Za-z0-9_-]{1,40}')
_lock = threading.RLock()


class ThreadNotFound(ValueError):
    """The chat named does not exist (or the name is not a chat id)."""


def load():
    if not CONFIG.exists():
        return {'favorite_color': None, 'aliases': {}}
    data = json.loads(CONFIG.read_text())
    return {'favorite_color': data.get('favorite_color'), 'aliases': data.get('aliases', {})}


def _save(data):
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(CONFIG, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(data, stream, ensure_ascii=False)
    os.chmod(CONFIG, 0o600)


def remember_color(color):
    if color not in COLORS:
        raise ValueError('لون غير مدعوم')
    data = load(); data['favorite_color'] = color; _save(data)
    return {'status': 'ok', 'favorite_color': color}


def remember_alias(alias, entity_id):
    alias = alias.strip().lower()
    if not 2 <= len(alias) <= 40 or not re.fullmatch(r'[\w\-\s؀-ۿ]+', alias):
        raise ValueError('اسم الجهاز غير صالح')
    from home_link import entities
    if entity_id not in {e['entity_id'] for e in entities()}:
        raise ValueError('الجهاز غير موجود')
    data = load()
    if len(data['aliases']) >= 30 and alias not in data['aliases']:
        raise ValueError('وصلت قائمة الأسماء إلى حدها')
    data['aliases'][alias] = entity_id
    _save(data)
    return {'status': 'ok', 'alias': alias, 'entity_id': entity_id}


def profile_text():
    if not PROFILE.exists():
        return ''
    return PROFILE.read_text(encoding='utf-8')[:4000]


def save_profile(content):
    """Owner-edited knowledge; this file never grants tools or OS permissions."""
    if len(content) > 4000:
        raise ValueError('ملف ميرا أطول من 4000 حرف')
    DIR.mkdir(parents=True, exist_ok=True)
    fd = os.open(PROFILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as stream:
        stream.write(content)
    os.chmod(PROFILE, 0o600)


def remember_fact(fact):
    """Persist a fact explicitly taught by the owner, without replacing the profile."""
    if not isinstance(fact, str) or not 2 <= len(fact.strip()) <= 500:
        raise ValueError('المعلومة يجب أن تكون بين حرفين و500 حرف')
    fact = ' '.join(fact.split())
    current = profile_text().strip()
    if fact not in current.splitlines():
        save_profile(current + ('\n' if current else '') + fact)
    return {'status': 'ok', 'remembered': fact}


# ── private files ─────────────────────────────────────────────────────
def _now():
    return datetime.now(timezone.utc).isoformat()


def _write_private(path, data):
    """Replace a private file whole: write a 0600 temp beside it, then rename it over."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data)
    os.chmod(temp, 0o600)
    temp.replace(path)


def _valid_id(value):
    return isinstance(value, str) and bool(_ID.fullmatch(value))


def _meta():
    """The chat index. A missing or damaged index never hides the conversation itself.

    A damaged index is set aside (``mira-threads.json.damaged-<time>``), never overwritten, and a
    fresh one keeps the newest chat open. An index that cannot be read at all (permissions, a
    failing disk) is marked ``readonly``: nothing is saved over it (`_save_meta` refuses).
    """
    try:
        raw = THREADS.read_bytes()
    except FileNotFoundError:
        raw = None
    except OSError:
        return {'current': DEFAULT_THREAD, 'threads': {}, 'readonly': True}
    data = {}
    if raw is not None:
        try:
            data = json.loads(raw.decode('utf-8'))
        except ValueError:                      # bad JSON or bad UTF-8
            data = None
        if not isinstance(data, dict):
            return _recover_meta()
    threads = {}
    for tid, item in (data.get('threads') if isinstance(data.get('threads'), dict) else {}).items():
        if _valid_id(tid) and isinstance(item, dict):
            threads[tid] = {'created': str(item.get('created') or ''),
                            'title': str(item.get('title') or '')[:TITLE_MAX],
                            'pinned': bool(item.get('pinned')), 'archived': bool(item.get('archived'))}
    current = data.get('current')
    return {'current': current if _valid_id(current) else DEFAULT_THREAD, 'threads': threads}


def _recover_meta():
    """Set a damaged index aside and start a fresh one on the chat written to last."""
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + secrets.token_hex(2)
    aside = THREADS.with_name(f'{THREADS.name}.damaged-{stamp}')
    try:
        THREADS.replace(aside)
    except OSError:
        return {'current': DEFAULT_THREAD, 'threads': {}, 'readonly': True}
    meta = {'current': _newest_thread(), 'threads': {}}
    try:
        _save_meta(meta)
    except OSError:
        pass
    return meta


def _newest_thread():
    for line in reversed(_lines()):
        item = _parse(line)
        if item is not None:
            return item['thread']
    return DEFAULT_THREAD


def _save_meta(meta):
    if meta.get('readonly'):
        raise OSError('the chat index could not be read; it is not overwritten')
    _write_private(THREADS, json.dumps({'current': meta['current'], 'threads': meta['threads']},
                                       ensure_ascii=False).encode('utf-8'))


def _entry(meta, tid):
    return meta['threads'].setdefault(tid, {'created': _now(), 'title': '', 'pinned': False, 'archived': False})


def _key(record):
    return record.get('id') or 't:' + str(record.get('time', ''))


def _lines():
    try:
        return CONVERSATION.read_bytes().splitlines()
    except FileNotFoundError:
        return []


def _parse(line):
    try:
        item = json.loads(line.decode('utf-8', 'replace'))
    except ValueError:
        return None
    if not isinstance(item, dict):
        return None
    item['thread'] = item['thread'] if _valid_id(item.get('thread')) else DEFAULT_THREAD
    return item


def _mentions(line, tid):
    """A cheap byte test before parsing: can this line belong to chat `tid`?"""
    if tid == DEFAULT_THREAD and b'"thread"' not in line:
        return True
    return tid.encode() in line


def _records(tid=None, want=None):
    """Stored records, oldest first: all of them, or chat `tid`'s newest (`want` of them at most).

    Tombstones (role 'retract') hide the records they name; they are applied here, never returned.
    """
    lines = _lines()
    if tid is None:
        rows = [item for item in map(_parse, lines) if item is not None]
        hidden = {ref for item in rows if item.get('role') == 'retract' for ref in item.get('ref') or []}
        return [item for item in rows if item.get('role') != 'retract' and _key(item) not in hidden]
    out, hidden = [], set()
    for line in reversed(lines):       # newest first: a tombstone is always newer than what it hides
        if not _mentions(line, tid):
            continue
        item = _parse(line)
        if item is None or item['thread'] != tid:
            continue
        if item.get('role') == 'retract':
            hidden.update(item.get('ref') or [])
            continue
        if _key(item) in hidden:
            continue
        out.append(item)
        if want is not None and len(out) >= want:
            break
    out.reverse()
    return out


def _merge(records, roles):
    """Keep `roles`; join the pieces of one spoken reply (adjacent plain Mira records within 3 s).

    A Mira line with a `tool` (a reminder, a card's answer) is its own entry, never glued to a reply.
    """
    out, previous = [], None
    for item in records:
        if item.get('role') in roles and isinstance(item.get('text'), str):
            if (plain_reply(item) and previous and plain_reply(previous)
                    and out and plain_reply(out[-1])):
                try:
                    earlier = datetime.fromisoformat(previous['time'])
                    later = datetime.fromisoformat(item['time'])
                    adjacent = 0 <= (later - earlier).total_seconds() <= 3
                except (KeyError, ValueError, TypeError):
                    adjacent = False
                if adjacent:
                    out[-1]['text'] += item['text']
                else:
                    out.append(dict(item))
            else:
                out.append(dict(item))
        previous = item
    return out


# ── the conversation ──────────────────────────────────────────────────
def current_thread():
    with _lock:
        return _meta()['current']


def add_message(role, text, status='', title='', tool='', thread=None):
    """Append one record to the open chat (or to `thread`). Returns its id; '' when nothing was stored."""
    if role not in ROLES or not isinstance(text, str) or not text.strip():
        return ''
    with _lock:
        meta = _meta()
        tid = thread if _valid_id(thread) else meta['current']
        record = {'time': _now(), 'role': role, 'text': text[:TEXT_MAX], 'thread': tid, 'id': secrets.token_hex(6)}
        if status in STATUSES:
            record['status'] = status
        if title:
            record['title'] = str(title)[:120]
        if tool:
            record['tool'] = str(tool)[:80]
        _append(record)
        entry = meta['threads'].get(tid)
        # A chat the owner talks in again is not archived (a late result or reminder does not bring it back).
        if not meta.get('readonly') and (entry is None or (entry['archived'] and role == 'user')):
            _entry(meta, tid)['archived'] = False
            _save_meta(meta)
        # Keep a bounded local history; no cloud sync or audio recording.
        if CONVERSATION.stat().st_size > MAX_BYTES:
            _trim(meta)
    return record['id']


def _append(record):
    DIR.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(record, ensure_ascii=False) + '\n').encode('utf-8')
    fd = os.open(CONVERSATION, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        os.write(fd, payload)
    finally:
        os.close(fd)
    os.chmod(CONVERSATION, 0o600)


def _trim(meta):
    """Keep pinned chats first (up to PINNED_BYTES), then the newest records (up to KEEP_BYTES)."""
    lines = _lines()
    pinned = {tid for tid, item in meta['threads'].items() if item['pinned']}
    keep = [False] * len(lines)
    budget = PINNED_BYTES
    for i in range(len(lines) - 1, -1, -1):
        item = _parse(lines[i]) if pinned else None
        if item is not None and item['thread'] in pinned and budget >= len(lines[i]) + 1:
            keep[i] = True
            budget -= len(lines[i]) + 1
    budget = KEEP_BYTES
    for i in range(len(lines) - 1, -1, -1):
        if keep[i]:
            continue
        if budget < len(lines[i]) + 1:
            break
        keep[i] = True
        budget -= len(lines[i]) + 1
    _write_private(CONVERSATION, b''.join(line + b'\n' for line, kept in zip(lines, keep) if kept))


def recent_messages(limit=20):
    """The open chat's newest owner/Mira turns, for the model. Never another chat's."""
    limit = max(1, min(int(limit), 200))
    with _lock:
        tid = _meta()['current']
        records = _records(tid, want=limit * 8)
    return _merge(records, ('user', 'mira'))[-limit:]


def messages(thread=None, limit=200):
    """A chat's entries for the window: words, and the action results that carry a verified status.

    Each item: role, text, time (UTC ISO), status, title, tool, id. Action records written before
    statuses were stored are left out: their outcome is unknown and is never shown as a result.
    """
    limit = max(1, min(int(limit), 500))
    with _lock:
        tid = thread if _valid_id(thread) else _meta()['current']
        records = _records(tid, want=limit * 4)
    out = []
    for item in _merge(records, ROLES):
        status = item.get('status') if item.get('status') in STATUSES else ''
        if item['role'] == 'error':
            status = 'error'
        elif item['role'] == 'action' and not status:
            continue
        out.append({'role': item['role'], 'text': item['text'], 'time': str(item.get('time', '')),
                    'status': status, 'title': str(item.get('title', '')), 'tool': str(item.get('tool', '')),
                    'id': _key(item)})
    return out[-limit:]


def new_thread():
    """Open a fresh chat and return its id. An open chat that is still empty is reused, not multiplied."""
    with _lock:
        meta = _meta()
        current = meta['current']
        if not _records(current, want=1):
            _entry(meta, current)['archived'] = False
            _save_meta(meta)
            return current
        tid = 't' + datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S') + '-' + secrets.token_hex(3)
        _entry(meta, tid)
        meta['current'] = tid
        _save_meta(meta)
        return tid


def _known(meta, tid):
    return tid == DEFAULT_THREAD or tid in meta['threads'] or bool(_records(tid, want=1))


def open_thread(tid):
    """Make `tid` the open chat: the next message, and the model's history, come from it."""
    with _lock:
        meta = _meta()
        if not _valid_id(tid) or not _known(meta, tid):
            raise ThreadNotFound('المحادثة غير موجودة')
        _entry(meta, tid)
        meta['current'] = tid
        _save_meta(meta)
        return tid


def rename_thread(tid, title):
    """Name a chat; an empty name gives back the automatic one (its first question)."""
    title = ' '.join(str(title or '').split())
    if len(title) > TITLE_MAX or any(unicodedata.category(ch) == 'Cc' for ch in title):
        raise ValueError('اسم المحادثة غير صالح (80 حرفاً على الأكثر)')
    return _set(tid, title=title)


def pin_thread(tid, pinned=True):
    return _set(tid, pinned=bool(pinned))


def archive_thread(tid, archived=True):
    return _set(tid, archived=bool(archived))


def _set(tid, **fields):
    with _lock:
        meta = _meta()
        if not _valid_id(tid) or not _known(meta, tid):
            raise ThreadNotFound('المحادثة غير موجودة')
        _entry(meta, tid).update(fields)
        _save_meta(meta)
        return {'status': 'ok', 'id': tid, **fields}


def plain_reply(record):
    """Mira's own words from the model: role 'mira' with no `tool` behind it.

    A fired reminder (tool 'reminder') or the window's own answer to a waiting card (tool 'cards')
    is a Mira line the model never wrote; it is never redone.
    """
    return record.get('role') == 'mira' and not record.get('tool')


def retract_last_reply(thread=None):
    """Take back the last answer of a chat so its question can be asked again; returns the question or ''.

    After the owner's last question the chat may end in Mira's plain words (they are hidden by a
    tombstone, never edited away) or only in errors (a turn to try again: nothing is hidden, the
    errors did happen). Anything else there (an action, a result, a reminder, a card's answer, or
    words and errors mixed) returns '' and changes nothing, so a turn that acted is never run twice.
    """
    with _lock:
        tid = thread if _valid_id(thread) else _meta()['current']
        records = [r for r in _records(tid, want=60) if r.get('role') in ROLES]
        tail = []
        while records and (plain_reply(records[-1]) or records[-1].get('role') == 'error'):
            tail.append(records.pop())
        if not tail or not records or records[-1].get('role') != 'user':
            return ''
        kinds = {r.get('role') for r in tail}
        if len(kinds) > 1:
            return ''
        if kinds == {'mira'}:
            _append({'time': _now(), 'role': 'retract', 'thread': tid, 'ref': [_key(r) for r in tail]})
        return str(records[-1].get('text', ''))


# ── the chat list ─────────────────────────────────────────────────────
def auto_title(text):
    """A chat's automatic name: the first line of its first question (an attached file's body is not)."""
    first = next((line for line in str(text or '').splitlines() if line.strip()), '')
    first = ' '.join(first.split())
    return first if len(first) <= 60 else first[:59].rstrip() + '…'


def _summaries(records):
    info = {}
    for item in records:
        if item.get('role') not in ROLES:
            continue
        row = info.setdefault(item['thread'], {'count': 0, 'first': '', 'updated': '', 'last': ''})
        row['count'] += 1
        row['updated'] = max(row['updated'], str(item.get('time', '')))
        if not row['first'] and item['role'] == 'user':
            row['first'] = str(item.get('text', ''))
        if item['role'] in ('user', 'mira'):
            row['last'] = str(item.get('text', ''))
    return info


def _thread_row(tid, meta, info):
    entry = meta['threads'].get(tid, {})
    summary = info.get(tid, {})
    preview = ' '.join(summary.get('last', '').split())
    return {'id': tid, 'title': entry.get('title') or auto_title(summary.get('first', '')),
            'named': bool(entry.get('title')), 'updated': summary.get('updated') or entry.get('created', ''),
            'pinned': bool(entry.get('pinned')), 'archived': bool(entry.get('archived')),
            'count': summary.get('count', 0), 'preview': preview[:120], 'current': tid == meta['current']}


def _ordered(rows):
    rows.sort(key=lambda row: row['updated'], reverse=True)
    rows.sort(key=lambda row: not row['pinned'])      # stable: pinned first, each part newest first
    return rows


def list_threads(include_archived=False):
    """Every chat, pinned first, then newest first. An empty chat is listed only while it is open."""
    with _lock:
        meta = _meta()
        records = _records()
    info = _summaries(records)
    rows = []
    for tid in set(info) | set(meta['threads']) | {meta['current']}:
        row = _thread_row(tid, meta, info)
        if not row['count'] and not row['current']:
            continue
        if row['archived'] and not include_archived:
            continue
        rows.append(row)
    return _ordered(rows)


_MARKS = re.compile('[ؐ-ًؚ-ٰٟۖ-ۭـ]')
_LETTERS = str.maketrans('أإآٱىة', 'اااايه')


def fold(text):
    """Text as search compares it: case, Arabic diacritics and tatweel, and letter variants ignored."""
    return _MARKS.sub('', unicodedata.normalize('NFKC', str(text)).casefold()).translate(_LETTERS)


def _snippet(text, needle):
    """About 90 characters of `text` around the first match of the folded `needle`."""
    mapping, folded = [], []
    for i, ch in enumerate(text):
        piece = fold(ch)
        folded.append(piece)
        mapping.extend([i] * len(piece))
    at = ''.join(folded).find(needle)
    if at < 0:
        return ' '.join(text.split())[:90]
    start = max(0, mapping[at] - 30)
    end = min(len(text), mapping[min(at + len(needle), len(mapping)) - 1] + 60)
    return ('…' if start else '') + ' '.join(text[start:end].split()) + ('…' if end < len(text) else '')


def search_threads(query, limit=50):
    """Chats whose name or words contain `query` (archived ones too), with the words that matched."""
    needle = fold(' '.join(str(query or '').split()))
    if not needle:
        return []
    with _lock:
        meta = _meta()
        records = _records()
    info = _summaries(records)
    hits = {}
    for item in reversed(records):        # the newest match of each chat is the one shown
        if item.get('role') not in ('user', 'mira') or item['thread'] in hits:
            continue
        if needle in fold(item.get('text', '')):
            hits[item['thread']] = _snippet(str(item['text']), needle)
    for tid, entry in meta['threads'].items():
        if tid not in hits and entry.get('title') and needle in fold(entry['title']):
            hits[tid] = ''
    rows = []
    for tid, snippet in hits.items():
        row = _thread_row(tid, meta, info)
        if row['count'] or row['current']:
            rows.append({**row, 'snippet': snippet})
    return _ordered(rows)[:limit]
