"""Private firmware transaction evidence; no device/network commands live here."""
import contextlib
import fcntl
import json
import os
from pathlib import Path
import stat
import tempfile
import time

STATES = frozenset(('checking', 'none', 'available', 'installing', 'updated',
                    'cancelled', 'failed', 'interrupted'))
ACTIVE = frozenset(('checking', 'available', 'installing'))
REASONS = frozenset(('', 'metadata', 'query', 'install', 'permission', 'unavailable'))
UNKNOWN = {'known': False, 'state': '', 'updated': 0, 'reason': '', 'busy': False}


class BusyError(Exception):
    pass


def state_path():
    base = Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state')))
    return base / 'moos/firmware-updates.json'


def _process_start(pid):
    try:
        text = Path(f'/proc/{pid}/stat').read_text()
        fields = text[text.rindex(')') + 2:].split()
        # A dead child can retain its PID/start identity until its parent reaps
        # it. That process cannot finish the transaction or write a result.
        return '' if fields[0] in ('Z', 'X', 'x') else fields[19]
    except (OSError, ValueError, IndexError):
        return ''


def _boot_id():
    try:
        return Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    except OSError:
        return ''


def _read(path):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as stream:
            info = os.fstat(stream.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                    or info.st_mode & 0o077 or info.st_size > 16384):
                return None
            data = json.loads(stream.read(16385))
        if (not isinstance(data, dict) or type(data.get('schema')) is not int
                or data['schema'] != 1):
            return None
        updated, pid = data.get('updated'), data.get('pid')
        if (type(updated) is not int or not 0 < updated <= time.time() + 5
                or type(pid) is not int or pid <= 0
                or data.get('state') not in STATES or data.get('reason') not in REASONS
                or not isinstance(data.get('start'), str)
                or not isinstance(data.get('boot'), str)):
            return None
        return data
    except (OSError, ValueError, TypeError):
        return None


def _active(data):
    return bool(data and data['state'] in ACTIVE and data['start']
                and data['boot'] and data['boot'] == _boot_id()
                and data['start'] == _process_start(data['pid']))


def read_state(path=None):
    data = _read(path or state_path())
    if data is None:
        return dict(UNKNOWN)
    state = data['state']
    if state in ('checking', 'installing') and not _active(data):
        state = 'interrupted'
    return {'known': True, 'state': state, 'updated': data['updated'],
            'reason': data['reason'], 'busy': _active(data)}


def record(state, reason='', *, pid=None, path=None):
    if state not in STATES or reason not in REASONS:
        raise ValueError('invalid firmware state')
    path = Path(path or state_path())
    pid = os.getpid() if pid is None else pid
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    lock = os.open(path.parent / 'firmware-updates.lock',
                   os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(lock, 'a') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise BusyError('firmware state is being written') from error
        previous = _read(path)
        if _active(previous) and previous['pid'] != pid:
            raise BusyError('another firmware transaction is active')
        data = {'schema': 1, 'state': state, 'reason': reason,
                'updated': int(time.time()), 'pid': pid,
                'start': _process_start(pid), 'boot': _boot_id()}
        fd, temporary = tempfile.mkstemp(prefix='.firmware-', dir=path.parent)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(data, stream)
                stream.write('\n')
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
            directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(temporary)
