"""Owner-taught preferences and device names. Knowledge only, never capabilities."""
import json, os, re
from datetime import datetime, timezone
from pathlib import Path

DIR = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'mo-dot'
CONFIG = DIR / 'mira-memory.json'
PROFILE = DIR / 'mira-profile.txt'
CONVERSATION = DIR / 'mira-conversation.jsonl'
COLORS = {'pink','purple','blue','green','yellow','orange','red','white'}


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
    if not 2 <= len(alias) <= 40 or not re.fullmatch(r'[\w\-\s\u0600-\u06ff]+', alias):
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


def add_message(role, text):
    if role not in ('user', 'mira', 'action', 'error') or not text.strip():
        return
    DIR.mkdir(parents=True, exist_ok=True)
    record = {'time': datetime.now(timezone.utc).isoformat(), 'role': role,
              'text': text[:4000]}
    payload = (json.dumps(record, ensure_ascii=False) + '\n').encode('utf-8')
    fd = os.open(CONVERSATION, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        os.write(fd, payload)
    finally:
        os.close(fd)
    os.chmod(CONVERSATION, 0o600)
    # Keep a bounded local history; no cloud sync or audio recording.
    if CONVERSATION.stat().st_size > 1_000_000:
        rows = CONVERSATION.read_bytes().splitlines()[-200:]
        temp = CONVERSATION.with_suffix('.tmp')
        temp.write_bytes(b'\n'.join(rows) + b'\n')
        os.chmod(temp, 0o600)
        temp.replace(CONVERSATION)


def recent_messages(limit=20):
    if not CONVERSATION.exists():
        return []
    limit = max(1, min(limit, 200))
    rows = CONVERSATION.read_text(encoding='utf-8').splitlines()[-max(200,limit * 8):]
    out = []
    previous = None
    for row in rows:
        try:
            item = json.loads(row)
            if item.get('role') in ('user','mira') and isinstance(item.get('text'),str):
                if (item['role'] == 'mira' and previous and previous.get('role') == 'mira'
                        and out and out[-1]['role'] == 'mira'):
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
        except (ValueError, TypeError):
            continue
    return out[-limit:]
