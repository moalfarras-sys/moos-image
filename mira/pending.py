"""Owner confirmations: the one path from "Mira proposes" to "the owner approved".

A fixed action the owner must approve (closing a window, running a saved routine, …) is not
executed when the model asks. It is parked here as a pending action with a short lifetime,
shown as a card, and executed only when the OWNER approves: a tap on the card, or his own
transcribed words matched by `is_confirmation`. The model never sees the payload and has no
call that approves anything; `is_confirmation` reads the owner's words, never the model's.
The payload is data for a fixed executor, never a command line.

    pending = PendingActions()
    card = pending.add('close_window', 'إغلاق نافذة كونسول', 'Close the Konsole window', '~ : — كونسول',
                       {'tool': 'close_window', 'args': {'query': 'konsole'}})
    ...
    decision = pending.respond(owner_transcript)   # {'verdict': 'yes', 'item': {...payload...}} or …
"""
from __future__ import annotations

import re
import secrets
import threading
import time
import unicodedata
from typing import Callable, Optional

DEFAULT_TTL = 120.0
MAX_TTL = 900.0
MAX_ITEMS = 20
MAX_WORDS = 4

# ─── the owner's words ────────────────────────────────────────────────
# Everything below is compared AFTER _normalize(): no diacritics or tatweel, one alef, ى→ي,
# ة→ه, lower case, punctuation removed. Keep every entry in that normalized form.
_YES_STRONG = {
    'نعم', 'ايوه', 'ايوا', 'اكيد', 'بالتاكيد', 'اكد', 'اكدي', 'موافق', 'موافقه',
    'نفذ', 'نفذي', 'نفذيه', 'نفذه', 'شغلي', 'yes', 'yeah', 'yep', 'yup', 'confirm', 'confirmed',
    'approve', 'approved', 'sure', 'doit', 'goahead',
}
# Soft words count only beside a strong one: «تمام» or «ok» alone is an acknowledgement.
# «إيه» is yes in the Levant and "what?" in Egypt, so it is soft too.
_YES_SOFT = {'تمام', 'اوكي', 'اوك', 'اه', 'اي', 'ايه', 'ok', 'okay', 'please', 'go', 'now', 'هلا', 'هلق', 'الان', 'حالا',
             'طيب', 'يلا', 'بليز'}
_NO_STRONG = {
    'لا', 'لاء', 'لاا', 'لالا', 'الغي', 'الغيه', 'الغ', 'الغاء', 'كنسل', 'بلاش', 'no', 'nope', 'nah',
    'cancel', 'cancelled', 'dont', 'reject', 'deny', 'stop', 'abort',
}
_NO_SOFT = {'تنفذ', 'تنفذي', 'تنفذيه', 'شكرا', 'thanks', 'thank', 'you', 'please', 'خلاص', 'هلا', 'الان', 'حالا',
            'ما', 'بدي'}
_FILLER = {'يا', 'ميرا', 'mira', 'hey'}
# Multi-word phrases folded into one token before the word rule runs.
_PHRASES = (
    ('do not do it', 'dont'), ("don't do it", 'dont'), ('dont do it', 'dont'), ('do not', 'dont'),
    ("don't", 'dont'), ('do it', 'doit'), ('go ahead', 'goahead'), ('go on', 'goahead'),
    ('no thanks', 'no'), ('no thank you', 'no'),
)

_DIACRITICS = re.compile('[ؐ-ًؚ-ٰٟۖ-ۭـ]')
_PUNCT = re.compile(r'[^\w\s\']+', re.UNICODE)
_AR_DIGITS = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')


def normalize(text: str) -> str:
    """Owner speech in one comparable form (used by is_confirmation)."""
    text = unicodedata.normalize('NFKC', str(text or '')).translate(_AR_DIGITS)
    text = _DIACRITICS.sub('', text)
    text = re.sub('[أإآٱ]', 'ا', text).replace('ى', 'ي').replace('ة', 'ه').replace('ؤ', 'و').replace('ئ', 'ي')
    text = text.replace('’', "'").replace('،', ' ').replace('؛', ' ').replace('؟', ' ')
    text = _PUNCT.sub(' ', text.lower())
    return ' '.join(text.split())


def is_confirmation(text: str) -> Optional[str]:
    """'yes' / 'no' when the OWNER's short utterance is only an answer, else None.

    Strict on purpose: at most four words, every word must belong to the yes (or the no)
    vocabulary or be a filler such as «يا ميرا», and a mix of yes and no words is no answer.
    «نعم الساعة كم؟» is a question, not an approval, so it returns None.
    """
    words = normalize(text).split()
    if not words or len(words) > MAX_WORDS:
        return None
    joined = ' ' + ' '.join(words) + ' '
    for phrase, token in _PHRASES:
        joined = joined.replace(' ' + phrase + ' ', ' ' + token + ' ')
    words = joined.split()
    # «لأ» normalises to «لا»; a repeated «لا لا» or «نعم نعم» is still one answer.
    yes = no = False
    for word in words:
        if word in _FILLER:
            continue
        if word in _YES_STRONG:
            yes = True
        elif word in _NO_STRONG:
            no = True
        elif word in _YES_SOFT or word in _NO_SOFT:
            continue
        else:
            return None                       # an unrelated word: not a bare answer
    if yes == no:                             # neither, or both («لا نعم»)
        return None
    other_soft = _NO_SOFT - _YES_SOFT if yes else _YES_SOFT - _NO_SOFT
    if any(word in other_soft for word in words):
        return None                           # «نعم شكرا» / «لا تمام»: mixed signals
    return 'yes' if yes else 'no'


# ─── the parked actions ───────────────────────────────────────────────
_PUBLIC = ('id', 'kind', 'title_ar', 'title_en', 'detail', 'expires', 'created')


def public_view(item: Optional[dict]) -> Optional[dict]:
    """What a card or the model may see: never the payload."""
    if item is None:
        return None
    return {key: item[key] for key in _PUBLIC if key in item}


class PendingActions:
    """Thread-safe store of actions waiting for the owner. Items expire after `ttl` seconds.

    add() returns the public view (no payload). get()/take() return the whole item, including
    the payload, for the executor only. take() is one-shot: the second take of the same id
    returns None, so one approval can never run an action twice.
    """

    def __init__(self, clock: Callable[[], float] = time.time, max_items: int = MAX_ITEMS):
        self._clock = clock
        self._max = max(1, int(max_items))
        self._items: dict[str, dict] = {}
        self._lock = threading.Lock()

    def _purge(self, now: float) -> None:
        for key in [k for k, v in self._items.items() if v['expires'] <= now]:
            del self._items[key]

    def add(self, kind: str, title_ar: str, title_en: str, detail: str = '', payload=None,
            ttl: float = DEFAULT_TTL) -> dict:
        if not isinstance(kind, str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,39}', kind):
            raise ValueError('نوع الإجراء غير صالح')
        try:
            ttl = float(ttl)
        except (TypeError, ValueError):
            raise ValueError('مدة الانتظار غير صالحة') from None
        if not 1.0 <= ttl <= MAX_TTL:
            raise ValueError('مدة الانتظار بين ثانية و15 دقيقة')
        now = self._clock()
        item = {'id': 'p' + secrets.token_hex(5), 'kind': kind,
                'title_ar': ' '.join(str(title_ar or '').split())[:160],
                'title_en': ' '.join(str(title_en or '').split())[:160],
                'detail': str(detail or '')[:2000], 'payload': payload,
                'created': now, 'expires': now + ttl}
        with self._lock:
            self._purge(now)
            while len(self._items) >= self._max:        # oldest first
                del self._items[min(self._items, key=lambda k: self._items[k]['created'])]
            self._items[item['id']] = item
        return public_view(item)

    def get(self, action_id: str) -> Optional[dict]:
        with self._lock:
            self._purge(self._clock())
            item = self._items.get(action_id)
            return dict(item) if item else None

    def take(self, action_id: str) -> Optional[dict]:
        """Remove and return the item if it exists and has not expired (atomic, one-shot)."""
        with self._lock:
            now = self._clock()
            item = self._items.pop(action_id, None)
            if item is None or item['expires'] <= now:
                return None
            return item

    def reject(self, action_id: str) -> Optional[dict]:
        """Drop the item; returns its public view (None if it was not pending)."""
        with self._lock:
            self._purge(self._clock())
            return public_view(self._items.pop(action_id, None))

    def latest(self) -> Optional[dict]:
        with self._lock:
            self._purge(self._clock())
            if not self._items:
                return None
            return public_view(max(self._items.values(), key=lambda v: v['created']))

    def list(self) -> list[dict]:
        with self._lock:
            self._purge(self._clock())
            return [public_view(v) for v in sorted(self._items.values(), key=lambda v: v['created'])]

    def clear(self) -> int:
        with self._lock:
            count = len(self._items)
            self._items.clear()
            return count

    def respond(self, owner_text: str) -> dict:
        """Apply the owner's spoken answer to what is pending.

        {'verdict': None}                       not an answer; handle the words normally
        {'verdict': 'none'}                     an answer, but nothing is pending
        {'verdict': 'yes', 'item': {...}}       the single pending item, taken (with payload)
        {'verdict': 'ambiguous', 'items': [...]} yes, but several are pending: nothing runs,
                                                the owner chooses on the cards
        {'verdict': 'no', 'items': [...]}       every pending item rejected (the safe side)
        """
        verdict = is_confirmation(owner_text)
        if verdict is None:
            return {'verdict': None}
        with self._lock:
            now = self._clock()
            self._purge(now)
            items = sorted(self._items.values(), key=lambda v: v['created'])
            if not items:
                return {'verdict': 'none'}
            if verdict == 'no':
                self._items.clear()
                return {'verdict': 'no', 'items': [public_view(v) for v in items]}
            if len(items) > 1:
                return {'verdict': 'ambiguous', 'items': [public_view(v) for v in items]}
            item = self._items.pop(items[0]['id'])
            return {'verdict': 'yes', 'item': item}
