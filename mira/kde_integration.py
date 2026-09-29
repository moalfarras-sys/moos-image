"""Mira inside KDE Plasma: the pieces that make MoOS and Mira read as one system.

    login start      a per-user switch for `mira --background` at sign-in: the image's systemd user
                     unit (mira.service) when it ships, otherwise an XDG autostart entry naming the
                     launcher by its absolute path, read back from the machine after every change
    Dolphin          «Ask Mira about this» on files and «Add to Mira as a project» on folders
                     (/usr/share/kio/servicemenus/mira-*.desktop run `mira --ask-about %F` and
                     `mira --add-project %f`); the launch arguments are parsed here
    D-Bus            org.moos.Mira at /Mira on the session bus: Show(panel), Prefill(text), Talk(),
                     Stop(), each answered by a callback the app passes in; optional, never fatal

Nothing here changes the system. The login switch writes the owner's own session configuration on
his click; a project is added to Mo AI's agent workspace only for a folder inside his home, on his
own context-menu click; a question about a file is only put in the composer, never sent for him.

Launch arguments are read once, left to right, and an option that takes a value consumes it. A
`moos://ai/ask/<text>` link reaches Mira as `--ask "<text>"`, so words a web page chose are never
read as `--add-project`, `--ask-about` or `--background` (launch_extras).
"""
import os
import re
import shutil
import subprocess
from pathlib import Path

from PySide6.QtCore import ClassInfo, QObject, Signal, Slot

from pages.base import Page, TEST_MODE

UNIT = 'mira.service'
SERVICE = 'org.moos.Mira'
OBJECT_PATH = '/Mira'
INTERFACE = 'org.moos.Mira'
MAX_PATHS = 12                     # files named in one «ask about» question
MAX_PREFILL = 2000                 # the composer's limit, as for `mira --ask`
MESSAGE_LIMIT = 6000               # one message, in characters: CommandDock.maxLength and controller.send
TYPING_ROOM = 400                  # left for the owner's own words beside an attached file
READ_LIMIT = 4 * MESSAGE_LIMIT     # bytes read at most (UTF-8 spends up to four on a character)
LAUNCHER = 'mira'                  # /usr/bin/mira, or ~/.local/bin/mira for a per-user install
AUTOSTART_NAME = 'mira.desktop'
UNIT_ON = ('enabled', 'enabled-runtime')
# Where systemd's xdg-autostart generator finds a bare `Exec=mira`: the user manager's own default
# PATH, never the session's. ~/.local/bin is not on it (measured with the host's generator: "not
# generating unit, could not find TryExec= binary mira"), so Mira's entry names the absolute path.
MANAGER_PATH = ('/usr/local/bin', '/usr/bin', '/usr/local/sbin', '/usr/sbin', '/bin', '/sbin')
# Launcher options whose value is the NEXT argument: app.py's own and the review flags.
VALUE_OPTIONS = ('--panel', '--ask', '--capture', '--capture-delay', '--scene', '--size', '--lang')
# Places and names that keep keys and passwords: a file there is named in a question, never
# attached (one Enter would send it to a cloud model), and a folder there is never a project.
PRIVATE_DIRS = ('.ssh', '.gnupg', '.local/share/keyrings', '.password-store', '.pki', '.aws', '.azure',
                '.kube', '.docker', '.config/gcloud', '.mozilla', '.thunderbird')
PRIVATE_NAME = re.compile(
    r'(?i)^(?:id_[a-z0-9_-]+|.*\.(?:pem|key|p12|pfx|ppk|jks|keystore|kdbx|asc|gpg|ovpn)'
    r'|\.env(?:\..*)?|\.netrc|\.pgpass|\.git-credentials|\.npmrc|\.pypirc|credentials(?:\.json)?'
    r'|.*secret.*|(?:.*[._-])?token(?:\.(?:txt|json))?)$')

STRINGS = {
    # login start (Settings)
    'kde_autostart': ('ابدأ ميرا مع تسجيل الدخول', 'Start Mira when I sign in'),
    'kde_autostart_sub': ('تبدأ ميرا بهدوء في الخلفية وتنتظر في شريط النظام، وتفتح نافذتها حين تطلبها.',
                          'Mira starts quietly in the background and waits in the system tray; her window opens when you ask.'),
    'kde_autostart_unavailable': ('التشغيل مع تسجيل الدخول غير متاح هنا: لم أجد مشغّل ميرا.',
                                  'Starting at sign-in is not available here: Mira’s launcher was not found.'),
    'kde_autostart_masked': ('خدمة ميرا محجوبة في هذه الجلسة؛ فكّ حجبها أولاً.',
                             'Mira’s service is masked in this session; unmask it first.'),
    'kde_autostart_on': ('ستبدأ ميرا مع كل تسجيل دخول', 'Mira will start every time you sign in'),
    'kde_autostart_off': ('لن تبدأ ميرا مع تسجيل الدخول', 'Mira will no longer start at sign-in'),
    'kde_autostart_failed': ('تعذّر تغيير التشغيل مع تسجيل الدخول', 'Could not change starting at sign-in'),
    'kde_autostart_window': ('تبدأ ميرا الآن مع تسجيل الدخول ونافذتها مفتوحة.',
                             'Mira currently starts at sign-in with her window open.'),
    'kde_autostart_fix': ('اجعلها تبدأ في الخلفية', 'Start her in the background'),
    # how to reach Mira from Plasma (Settings)
    'kde_reach_title': ('ميرا في MoOS', 'Mira in MoOS'),
    'kde_reach_keys': ('اضغط Meta+Space لتفتح ميرا من أي مكان في النظام',
                       'Press Meta+Space to open Mira from anywhere in MoOS'),
    'kde_reach_search': ('في بحث الجزيرة: اكتب سؤالك ثم Ctrl+Enter لتسأل ميرا',
                         'In the Island search: type a question, then Ctrl+Enter asks Mira'),
    'kde_reach_files': ('في مدير الملفات (Dolphin): زر الفأرة الأيمن على ملف ← «اسأل ميرا عن هذا»',
                        'In the file manager (Dolphin): right-click a file → “Ask Mira about this”'),
    'kde_reach_folders': ('وعلى مجلد ← «أضِف إلى ميرا كمشروع» ليظهر في الورشة',
                          'On a folder → “Add to Mira as a project” to see it in the Workbench'),
    # Dolphin: ask about files
    'kde_ask_file': ('حدّثيني عن الملف «{name}» في المجلد {folder}', 'Tell me about the file “{name}” in {folder}'),
    'kde_ask_folder': ('حدّثيني عن المجلد «{name}» في {folder}', 'Tell me about the folder “{name}” in {folder}'),
    'kde_ask_attached': ('حدّثيني عن هذا الملف المرفق: «{name}»', 'Tell me about this attached file: “{name}”'),
    'kde_ask_many': ('حدّثيني عن هذه الملفات: {items}', 'Tell me about these files: {items}'),
    'kde_ask_many_in': ('حدّثيني عن هذه الملفات في المجلد {folder}: {items}',
                        'Tell me about these files in {folder}: {items}'),
    'kde_ask_missing': ('لم أجد الملف الذي اخترته', 'I could not find the file you chose'),
    'kde_ask_private': ('لم أُرفق «{name}»: يبدو أنه يحفظ مفتاحاً أو كلمة سر، فذكرت اسمه ومكانه فقط.',
                        'I did not attach “{name}”: it looks like it keeps a key or a password, '
                        'so I named it and its folder only.'),
    'kde_ask_too_long': ('«{name}» أطول من أن يُرفق برسالة واحدة، فذكرت اسمه ومكانه.',
                         '“{name}” is too long to attach to one message, so I named it and its folder.'),
    # Dolphin: add a project
    'kde_project_added': ('أُضيف «{name}» إلى مشاريع الورشة', '“{name}” was added to your Workbench projects'),
    'kde_project_failed': ('تعذّرت إضافة المجلد كمشروع: {reason}', 'Could not add the folder as a project: {reason}'),
    'kde_project_missing': ('المجلد غير موجود', 'the folder does not exist'),
    'kde_project_not_folder': ('هذا ليس مجلداً', 'this is not a folder'),
    'kde_project_outside_home': ('المشروع يجب أن يكون داخل مجلد المنزل', 'a project must be inside your home folder'),
    'kde_project_whole_home': ('اختر مجلد مشروع داخل المنزل، لا المنزل كله',
                               'choose a project folder inside your home, not the whole home'),
    'kde_project_private': ('هذا المجلد يحفظ مفاتيح أو كلمات سر', 'this folder keeps keys or passwords'),
    'kde_project_unreachable': ('خدمة مساحة العمل لا تستجيب', 'the workspace service is not answering'),
    'kde_project_refused': ('رفضت خدمة مساحة العمل الطلب', 'the workspace service refused it'),
}

# Control characters, and the invisible ones that reorder or hide text: direction overrides and
# embeddings, isolates, marks, the zero-width space and the line separators. ZWNJ and ZWJ stay:
# Persian words and emoji sequences need them.
_CONTROL = re.compile(r'[\x00-\x1f\x7f\u061c\u200b\u200e\u200f\u202a-\u202e\u2028\u2029\u2066-\u2069]')
_PANEL = re.compile(r'[a-z]{1,16}')
LRI, FSI, PDI = '\u2066', '\u2068', '\u2069'   # left-to-right isolate, first-strong isolate, pop
_OPENERS = ('\u2066', '\u2067', '\u2068')


def _words(key, lang):
    pair = STRINGS[key]
    return pair[1] if lang == 'en' else pair[0]


def _run(argv, timeout=10.0):
    """(exit code, stdout, stderr) of a short command; never raises."""
    try:
        done = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        return 127, '', f'{argv[0]}: not found'
    except subprocess.TimeoutExpired:
        return 124, '', f'{argv[0]}: timed out'
    except OSError as exc:
        return 126, '', type(exc).__name__
    return done.returncode, done.stdout, done.stderr


def _short(text, limit=160):
    line = ' '.join(str(text or '').split())
    return line[:limit]


def _units(text):
    """A length as QML measures it (UTF-16 code units): CommandDock counts `text.length`."""
    return len(str(text).encode('utf-16-le')) // 2


# ─── launch arguments (app.py) ──────────────────────────────────────────────────────────────
def launch_extras(argv):
    """The launch arguments Plasma and Dolphin use, as a request for app.py's `open:` message.

        --background               start without showing the window (login start)
        --ask-about PATH [PATH…]   Dolphin: a question about these files, put in the composer
        --add-project PATH         Dolphin: add this folder to the Workbench projects

    Read once, left to right. The value of an option that takes one (VALUE_OPTIONS: `--ask TEXT`,
    `--panel NAME`, the review flags) is consumed with it and never read as an option itself:
    `moai --panel chat --ask "--add-project=/home/x"` asks a question, it adds nothing.
    A path is taken as given (validated later, off the Qt thread). An explicit `--panel` wins over
    the page these imply: the caller merges with setdefault.
    """
    extras = {}
    i = 0
    args = [str(a) for a in argv]
    while i < len(args):
        arg = args[i]
        if arg in VALUE_OPTIONS:
            i += 2
            continue
        if arg == '--background':
            extras['background'] = True
        elif arg == '--ask-about':
            paths = []
            i += 1
            while i < len(args) and not args[i].startswith('--'):
                paths.append(args[i])
                i += 1
            if paths:
                extras['about'] = paths[:MAX_PATHS]
                extras.setdefault('panel', 'chat')
            continue
        elif arg.startswith('--ask-about='):
            value = arg.split('=', 1)[1]
            if value:
                extras['about'] = [value]
                extras.setdefault('panel', 'chat')
        elif arg == '--add-project':
            if i + 1 < len(args) and not args[i + 1].startswith('--'):
                extras['project'] = args[i + 1]
                extras['panel'] = 'workbench'
                i += 2
                continue
        elif arg.startswith('--add-project='):
            value = arg.split('=', 1)[1]
            if value:
                extras['project'] = value
                extras['panel'] = 'workbench'
        i += 1
    return extras


def clean_prefill(text):
    """Words from outside (D-Bus Prefill) for the composer: one line, no control, direction or
    isolate characters, capped."""
    return ' '.join(_CONTROL.sub(' ', str(text or '')).split())[:MAX_PREFILL]


def _one_line(text, limit=MAX_PREFILL):
    """Mira's own words for the composer (they may carry her isolates): one line, capped, and never
    an isolate left open where the text was cut."""
    line = ' '.join(str(text).split())
    if len(line) <= limit:
        return line
    cut = line[:limit]
    while True:
        depth = 0
        for ch in cut:
            if ch in _OPENERS:
                depth += 1
            elif ch == PDI and depth:
                depth -= 1
        if len(cut) + depth <= limit:
            return cut + PDI * depth
        cut = cut[:-1]


def _path_words(path):
    """A path reads left to right in either language: without the isolate an Arabic line moved its
    leading slash to the far end ('var/home/…/Projects/')."""
    return LRI + str(path) + PDI


def _name_words(name):
    """A file name keeps its own direction (an Arabic name in an English line, or the reverse)."""
    return FSI + str(name) + PDI


def _local_path(value):
    """An absolute, existing local path from a launcher argument, or None."""
    raw = str(value or '')
    if raw.startswith('file://'):
        from urllib.parse import unquote, urlsplit
        parts = urlsplit(raw)
        if parts.netloc not in ('', 'localhost'):
            return None
        raw = unquote(parts.path)
    if not raw or _CONTROL.search(raw) or not raw.startswith('/'):
        return None
    path = Path(os.path.normpath(raw))
    try:
        return path if path.exists() else None
    except OSError:
        return None


def _private_places(home=None):
    """The folders that keep keys and passwords, as named and as resolved."""
    base = Path(home or Path.home())
    places = []
    for name in PRIVATE_DIRS:
        place = base / name
        places.append(place)
        try:
            places.append(place.resolve())
        except OSError:
            pass
    return places


def is_private(path, home=None):
    """Does this file or folder keep keys or passwords, by its place or by its name?"""
    candidates = [Path(path)]
    try:
        candidates.append(Path(path).resolve())
    except OSError:
        pass
    places = _private_places(home)
    for candidate in candidates:
        if PRIVATE_NAME.match(candidate.name or ''):
            return True
        for place in places:
            if candidate == place or place in candidate.parents:
                return True
    return False


def _text_file(path):
    """The contents of a small UTF-8 text file, or None."""
    try:
        size = path.stat().st_size
        if not path.is_file() or size == 0 or size > READ_LIMIT:
            return None
        content = path.read_text(encoding='utf-8')
    except (OSError, UnicodeError):
        return None
    if '\x00' in content:
        return None
    return content


def _fits(question, name, content):
    """Do the question, the file and room for the owner's own words fit in ONE message, joined the
    way CommandDock.submit joins them: question + "\\n\\n[" + name + "]\\n" + content?"""
    return _units(question) + _units(name) + _units(content) + 5 + TYPING_ROOM <= MESSAGE_LIMIT


def about_request(values, lang='ar', home=None):
    """What «Ask Mira about this» puts in front of the owner: {'text', 'attachment', 'notice'} or None.

    One small text file is attached (its contents go with the question when HE sends it) when it
    fits in one message with room for his words. Anything else is named with its folder, so a tool
    can find or open it, and a file that keeps keys or passwords is never attached. `notice` is
    (key, name) when he should know why a text file was only named.
    """
    paths = []
    for value in list(values or [])[:MAX_PATHS]:
        path = _local_path(value)
        if path is not None and path not in paths:
            paths.append(path)
    if not paths:
        return None
    if len(paths) == 1:
        path = paths[0]
        notice = None
        if path.is_file():
            private = is_private(path, home)
            content = None if private else _text_file(path)
            if content is not None:
                text = _one_line(_words('kde_ask_attached', lang).format(name=_name_words(path.name)))
                if _fits(text, path.name, content):
                    return {'text': text, 'attachment': {'name': path.name, 'text': content}, 'notice': None}
                notice = ('kde_ask_too_long', path.name)
            elif private:
                notice = ('kde_ask_private', path.name)
        key = 'kde_ask_folder' if path.is_dir() else 'kde_ask_file'
        text = _words(key, lang).format(name=_name_words(path.name or str(path)), folder=_path_words(path.parent))
        return {'text': _one_line(text), 'attachment': None, 'notice': notice}
    comma = ', ' if lang == 'en' else '، '
    folders = {p.parent for p in paths}
    if len(folders) == 1:
        quoted = comma.join((f'“{_name_words(p.name)}”' if lang == 'en' else f'«{_name_words(p.name)}»')
                            for p in paths)
        text = _words('kde_ask_many_in', lang).format(folder=_path_words(next(iter(folders))), items=quoted)
    else:
        text = _words('kde_ask_many', lang).format(items=comma.join(_path_words(p) for p in paths))
    return {'text': _one_line(text), 'attachment': None, 'notice': None}


# ─── projects (Dolphin → Workbench) ─────────────────────────────────────────────────────────
def project_folder(value, home=None):
    """(resolved folder, '') for a folder the agent workspace may take, else (None, reason key).

    Inside the home folder only (moai-agent-api checks that again), never the whole home and never
    a place that keeps keys or passwords: the agents read what a project holds."""
    raw = str(value or '')
    path = _local_path(raw)
    if path is None:
        return None, 'kde_project_missing'
    try:
        resolved = path.resolve(strict=True)
        home_real = Path(home or Path.home()).resolve(strict=True)
    except OSError:
        return None, 'kde_project_missing'
    if not resolved.is_dir():
        return None, 'kde_project_not_folder'
    if resolved == home_real:
        return None, 'kde_project_whole_home'
    if home_real not in resolved.parents:
        return None, 'kde_project_outside_home'
    if is_private(resolved, home_real) or is_private(path, home_real):
        return None, 'kde_project_private'
    return resolved, ''


def add_project(value, post=None, home=None):
    """Add a folder to Mo AI's agent workspace (moai-agent-api) and read its answer back."""
    folder, reason = project_folder(value, home)
    if folder is None:
        return {'status': 'error', 'reason': reason, 'path': str(value or '')}
    if post is None:
        import moai_agent
        post = moai_agent.post
    # Re-adding an archived project brings it back: the owner just asked for it.
    result = post('/api/project/upsert', {'path': str(folder), 'archived': False})
    if not isinstance(result, dict):
        return {'status': 'error', 'reason': 'kde_project_refused', 'path': str(folder)}
    if result.get('error'):
        reason = 'kde_project_unreachable' if result.get('error') == 'agent_unreachable' else 'kde_project_refused'
        return {'status': 'error', 'reason': reason, 'detail': _short(result.get('error')), 'path': str(folder)}
    project_id = str(result.get('id') or '')
    if result.get('ok') is not True or not re.fullmatch(r'[0-9a-f]{20}', project_id):
        return {'status': 'error', 'reason': 'kde_project_refused', 'path': str(folder)}
    return {'status': 'ok', 'id': project_id, 'name': str(result.get('name') or folder.name),
            'path': str(result.get('path') or folder)}


# ─── login start ────────────────────────────────────────────────────────────────────────────
def _config_home(config=None):
    if config:
        return Path(config)
    return Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config')


_STRING_ESCAPES = {'s': ' ', 'n': '\n', 't': '\t', 'r': '\r', '\\': '\\'}
_RESERVED = set(' \t\n"\'\\><~|&;$*?#()`')


def _unescape(value):
    """A Desktop Entry string value with its escapes (\\s \\n \\t \\r \\\\) read."""
    out, i = [], 0
    while i < len(value):
        if value[i] == '\\' and i + 1 < len(value) and value[i + 1] in _STRING_ESCAPES:
            out.append(_STRING_ESCAPES[value[i + 1]])
            i += 2
            continue
        out.append(value[i])
        i += 1
    return ''.join(out)


def _exec_words(value):
    """The arguments of an Exec= value, read as the Desktop Entry spec says: the string escapes
    first, then double quotes (inside which \\" \\` \\$ \\\\ are escapes); %% is a percent sign."""
    text = _unescape(value)
    words, word, quoted, started, i = [], [], False, False, 0
    while i < len(text):
        ch = text[i]
        if quoted:
            if ch == '\\' and i + 1 < len(text) and text[i + 1] in '"`$\\':
                word.append(text[i + 1])
                i += 2
                continue
            if ch == '"':
                quoted = False
            else:
                word.append(ch)
        elif ch == '"':
            quoted = started = True
        elif ch in ' \t\n':
            if started:
                words.append(''.join(word))
                word, started = [], False
        else:
            word.append(ch)
            started = True
        i += 1
    if started:
        words.append(''.join(word))
    return [w.replace('%%', '%') for w in words]


def _exec_arg(word):
    """One Exec= argument: quoted when it holds a reserved character, then string-escaped."""
    word = word.replace('%', '%%')
    if any(ch in _RESERVED for ch in word):
        word = '"' + re.sub(r'(["`$\\])', r'\\\1', word) + '"'
    return word.replace('\\', '\\\\')


def _executable(path):
    return os.path.isfile(path) and os.access(path, os.X_OK)


def _resolve(word):
    """The program the autostart generator would run for this Exec/TryExec word, or ''."""
    if not word:
        return ''
    if word.startswith('/'):
        return word if _executable(word) else ''
    if '/' in word:
        return ''
    for folder in MANAGER_PATH:
        candidate = os.path.join(folder, word)
        if _executable(candidate):
            return candidate
    return ''


def launcher_path(which=shutil.which, home=None):
    """The absolute path of Mira's launcher, or '': the one on PATH (the image's /usr/bin/mira, or a
    per-user ~/.local/bin/mira ahead of it), else ~/.local/bin/mira when it exists."""
    candidates = [which(LAUNCHER) or '', str(Path(home or Path.home()) / '.local/bin' / LAUNCHER)]
    for candidate in candidates:
        if candidate and os.path.isabs(candidate) and not _CONTROL.search(candidate) and _executable(candidate):
            return os.path.normpath(candidate)
    return ''


def _desktop_entry(path):
    """The [Desktop Entry] keys of a .desktop file ({} when unreadable)."""
    try:
        lines = path.read_text(encoding='utf-8', errors='replace').splitlines()
    except OSError:
        return {}
    keys, inside = {}, False
    for line in lines:
        line = line.strip()
        if line.startswith('['):
            inside = line == '[Desktop Entry]'
            continue
        if inside and '=' in line and not line.startswith('#'):
            key, value = line.split('=', 1)
            keys.setdefault(key.strip(), value.strip())
    return keys


def _starts_mira(entry):
    words = _exec_words(entry.get('Exec', ''))
    return bool(words) and os.path.basename(words[0]) == LAUNCHER


def _entry_runs(entry):
    """Would the session really run this entry at sign-in? systemd's generator skips a hidden or
    disabled entry, one meant for other desktops, and one whose TryExec or Exec program it cannot
    find on the manager's PATH."""
    if entry.get('Hidden', '').lower() == 'true' or entry.get('X-systemd-skip', '').lower() == 'true':
        return False
    if entry.get('X-GNOME-Autostart-enabled', 'true').lower() == 'false':
        return False
    only = [d for d in entry.get('OnlyShowIn', '').split(';') if d]
    if only and 'KDE' not in only:
        return False
    if 'KDE' in entry.get('NotShowIn', '').split(';'):
        return False
    try_exec = _unescape(entry.get('TryExec', ''))
    if try_exec and not _resolve(try_exec):
        return False
    words = _exec_words(entry.get('Exec', ''))
    return bool(words) and bool(_resolve(words[0]))


def autostart_entries(config=None):
    """[(path, runs, background)] for every XDG autostart entry that names Mira's launcher."""
    folder = _config_home(config) / 'autostart'
    found = []
    try:
        candidates = sorted(folder.glob('*.desktop'))
    except OSError:
        return found
    for path in candidates:
        entry = _desktop_entry(path)
        if not _starts_mira(entry):
            continue
        found.append((path, _entry_runs(entry), '--background' in _exec_words(entry.get('Exec', ''))[1:]))
    return found


def autostart_state(run=_run, config=None, which=shutil.which, home=None):
    """How Mira starts at sign-in, read from the machine.

    mode 'unit'  the image ships mira.service (systemctl --user is-enabled answers for it)
    mode 'xdg'   no unit, but Mira's launcher exists (a per-user install): an autostart entry
    mode ''      neither: the switch is unavailable
    """
    code, out, err = run(['systemctl', '--user', 'is-enabled', UNIT])
    word = (out.strip().splitlines() or [''])[0].strip()
    entries = autostart_entries(config)
    active = [(p, bg) for p, runs, bg in entries if runs]
    launcher = launcher_path(which, home)
    if word and word != 'not-found':
        mode = 'unit'
    elif launcher:
        mode = 'xdg'
    else:
        mode = ''
    unit_on = mode == 'unit' and word in UNIT_ON
    enabled = unit_on or bool(active)
    # at sign-in without the window: the unit always, an entry only with --background
    background = unit_on or (bool(active) and all(bg for _p, bg in active))
    return {
        'available': bool(mode) and word != 'masked',
        'mode': mode,
        'unit': word or 'unknown',
        'enabled': enabled,
        'background': background,
        'window': enabled and not background,
        'launcher': launcher,
        'legacy': [str(p) for p, _bg in active],
        'masked': word == 'masked',
        'error': '' if (word or code == 0) else _short(err or out),
    }


def _write_entry(path, launcher):
    """Mira's autostart entry: her launcher by its absolute path, in TryExec and in Exec."""
    body = ('[Desktop Entry]\n'
            'Type=Application\n'
            'Name=Mira\n'
            'Name[ar]=ميرا\n'
            'Comment=Mira, the MoOS assistant, waiting in the system tray\n'
            'Comment[ar]=ميرا، مساعدة MoOS، تنتظر في شريط النظام\n'
            'TryExec=' + launcher.replace('\\', '\\\\') + '\n'
            'Exec=' + _exec_arg(launcher) + ' --background\n'
            'Icon=moos-moai\n'
            'Terminal=false\n'
            'NoDisplay=true\n'
            'X-GNOME-Autostart-enabled=true\n')
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name('.' + path.name + '.tmp')
    tmp.write_text(body, encoding='utf-8')
    os.chmod(tmp, 0o644)
    os.replace(tmp, path)


def set_autostart(enabled, run=_run, config=None, which=shutil.which, home=None):
    """Turn Mira's sign-in start on or off, then read it back. One mechanism at a time: every
    autostart entry naming Mira's launcher is removed (beside the unit, and before the entry mode
    writes its own), so off means off and on never starts two copies. Turning it on while an older
    entry opens her window moves that start to the background."""
    enabled = bool(enabled)
    state = autostart_state(run, config, which, home)
    if not state['available']:
        reason = 'kde_autostart_masked' if state['masked'] else 'kde_autostart_unavailable'
        return {**state, 'status': 'error', 'reason': reason}
    try:
        if state['mode'] == 'unit':
            code, out, err = run(['systemctl', '--user', 'enable' if enabled else 'disable', UNIT])
            if code != 0:
                return {**state, 'status': 'error', 'reason': 'kde_autostart_failed', 'detail': _short(err or out)}
            for path, _runs, _bg in autostart_entries(config):
                path.unlink(missing_ok=True)
        else:
            for path, _runs, _bg in autostart_entries(config):
                path.unlink(missing_ok=True)
            if enabled:
                _write_entry(_config_home(config) / 'autostart' / AUTOSTART_NAME, state['launcher'])
    except OSError as exc:
        return {**autostart_state(run, config, which, home), 'status': 'error', 'reason': 'kde_autostart_failed',
                'detail': type(exc).__name__}
    after = autostart_state(run, config, which, home)
    if after['enabled'] != enabled or (enabled and not after['background']):
        return {**after, 'status': 'error', 'reason': 'kde_autostart_failed', 'detail': 'read-back'}
    return {**after, 'status': 'ok', 'reason': 'kde_autostart_on' if enabled else 'kde_autostart_off'}


# ─── the QML-facing object: mira.kde ────────────────────────────────────────────────────────
class KdeIntegration(Page):
    """Login start, Dolphin requests and the D-Bus door, for the controller and Settings.

    QML: mira.kde.state.{autostart, autostart_available, autostart_busy, autostart_mode,
         autostart_note, autostart_window, dbus}, mira.kde.setAutostart(bool), mira.kde.refresh(),
         and the signal mira.kde.attach(name, text) for the composer's attachment chip
    """
    attach = Signal(str, str)          # (file name, text) for the composer's attachment chip
    projectAdded = Signal(str)         # project id, after moai-agent-api confirmed it

    def initial(self):
        return {'autostart': False, 'autostart_available': False, 'autostart_busy': False,
                'autostart_mode': '', 'autostart_note': '', 'autostart_window': False, 'dbus': False}

    # login start
    @Slot()
    def refresh(self):
        self.run('autostart:read', autostart_state)

    @Slot(bool)
    def setAutostart(self, enabled):
        if self._state.get('autostart_busy'):
            return
        if TEST_MODE:   # a review render never touches the session
            self.update(autostart=bool(enabled), autostart_window=False, autostart_note='')
            return
        self.update(autostart_busy=True)
        self.run('autostart:set', set_autostart, bool(enabled))

    def on_autostart(self, tag, result):
        if tag != 'autostart:set' and self._state.get('autostart_busy'):
            return      # a change is on its way: its own read-back answers, not an older read
        result = result if isinstance(result, dict) else {}
        note, window = '', False
        if not result.get('available', False):
            note = self.text('kde_autostart_masked' if result.get('masked') else 'kde_autostart_unavailable')
        elif result.get('enabled') and not result.get('background', True):
            note, window = self.text('kde_autostart_window'), True
        self.update(autostart=bool(result.get('enabled')), autostart_available=bool(result.get('available')),
                    autostart_mode=str(result.get('mode') or ''), autostart_busy=False, autostart_note=note,
                    autostart_window=window)
        if tag == 'autostart:set':
            if result.get('status') == 'ok':
                self.host.toast.emit('ok', self.text(result.get('reason') or 'kde_autostart_on'))
            else:
                self.host.toast.emit('error', self.text(result.get('reason') or 'kde_autostart_failed'))

    # Dolphin
    def ask_about(self, paths):
        self.run('about:ask', about_request, [str(p) for p in list(paths or [])[:MAX_PATHS]], self.lang)

    def on_about(self, tag, result):
        if not isinstance(result, dict) or not result.get('text'):
            self.host.toast.emit('error', self.text('kde_ask_missing'))
            return
        self.host.prefill.emit(result['text'])
        attachment = result.get('attachment')
        if isinstance(attachment, dict) and attachment.get('name'):
            self.attach.emit(str(attachment['name']), str(attachment.get('text') or ''))
        notice = result.get('notice')
        if isinstance(notice, (list, tuple)) and len(notice) == 2 and notice[0] in STRINGS:
            self.host.toast.emit('info', self.text(notice[0]).format(name=notice[1]))

    def add_project(self, path):
        self.run('project:add', add_project, str(path or ''))

    def on_project(self, tag, result):
        result = result if isinstance(result, dict) else {'status': 'error', 'reason': 'kde_project_refused'}
        if result.get('status') == 'ok':
            self.host.toast.emit('ok', self.text('kde_project_added').format(name=result.get('name', '')))
            self.projectAdded.emit(str(result.get('id', '')))
        else:
            reason = self.text(result.get('reason') or 'kde_project_refused')
            self.host.toast.emit('error', self.text('kde_project_failed').format(reason=reason))

    # D-Bus
    def set_dbus_active(self, active):
        self.update(dbus=bool(active))

    def review(self):
        self.update(autostart=True, autostart_available=True, autostart_mode='unit', autostart_note='',
                    autostart_window=False, dbus=True)


# ─── D-Bus: org.moos.Mira ───────────────────────────────────────────────────────────────────
@ClassInfo({'D-Bus Interface': INTERFACE})
class MiraBus(QObject):
    """The object exported at /Mira. Every method answers 'ok' or why not: 'refused' (a bad
    argument), 'empty', 'unavailable' (no callback) or 'failed' (the callback raised)."""

    def __init__(self, callbacks, parent=None):
        super().__init__(parent)
        self._callbacks = dict(callbacks or {})
        self.connection = None
        self.service = ''
        self.path = ''

    def _call(self, name, *args):
        fn = self._callbacks.get(name)
        if not callable(fn):
            return 'unavailable'
        try:
            fn(*args)
        except Exception as exc:   # a caller on the bus never sees a traceback
            print('Mira D-Bus:', name, type(exc).__name__, exc, flush=True)
            return 'failed'
        return 'ok'

    @Slot(str, result=str)
    def Show(self, panel):
        panel = str(panel or '').strip().lower()
        if panel and not _PANEL.fullmatch(panel):
            return 'refused'
        return self._call('show', panel)

    @Slot(str, result=str)
    def Prefill(self, text):
        clean = clean_prefill(text)
        if not clean:
            return 'empty'
        return self._call('prefill', clean)

    @Slot(result=str)
    def Talk(self):
        return self._call('talk')

    @Slot(result=str)
    def Stop(self):
        return self._call('stop')


def start_dbus(callbacks, connection=None, service=SERVICE, path=OBJECT_PATH):
    """Export MiraBus on the session bus (or `connection`). Returns the object — keep a reference —
    or None when there is no bus, the name is taken, or this is a review/test run on the live
    session (MIRA_TEST_MODE without an explicit connection). Never raises.

    app.py's callbacks raise her window for Show, Prefill and Talk: a process on the session bus
    never starts her listening while she sits unseen in the tray."""
    if TEST_MODE and connection is None:
        return None
    try:
        from PySide6.QtDBus import QDBusConnection
        bus = connection if connection is not None else QDBusConnection.sessionBus()
        if not bus.isConnected():
            return None
        exported = MiraBus(callbacks)
        if not bus.registerObject(path, exported, QDBusConnection.ExportAllSlots):
            return None
        if not bus.registerService(service):
            bus.unregisterObject(path)
            print(f'Mira D-Bus: {service} is already owned; the door stays closed', flush=True)
            return None
        exported.connection, exported.service, exported.path = bus, service, path
        return exported
    except Exception as exc:
        print('Mira D-Bus:', type(exc).__name__, exc, flush=True)
        return None


def stop_dbus(exported):
    """Release the name and the object (safe on None)."""
    if exported is None or exported.connection is None:
        return
    try:
        exported.connection.unregisterService(exported.service)
        exported.connection.unregisterObject(exported.path)
    except Exception:
        pass
    exported.connection = None
