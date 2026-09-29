"""Open a MoOS route (moos://…) the owner clicked in Mira's window — only from a fixed list.

moos-open is MoOS's router; these are the routes Mira's pages may hand it. A route built from a
file (App Drop, a signed RPM) carries a file URL that moos-open validates again.
"""
import re
import subprocess
import urllib.parse
from pathlib import Path

_ALLOWED = [
    r'moos://app/(store|remote|updater|recovery|moplayer|moai)',
    r'moos://dev/(code|codex|claude|opencode)',
    r'moos://remote/(start|stop|restart|fast-on|fast-off)',
    r'moos://agent/whatsapp-login',
    r'moos://settings/[a-z0-9][a-z0-9-]{0,39}',
    r'moos://apps/install-(file|rpm)/file%3A%2F%2F%2F[A-Za-z0-9%._~\-]{1,600}',
]


def allowed(url):
    return isinstance(url, str) and any(re.fullmatch(p, url) for p in _ALLOWED)


def file_route(kind, path):
    """moos://apps/install-file|install-rpm/<encoded file URL> for a file inside the home folder."""
    resolved = Path(path).expanduser().resolve()
    if Path.home() not in resolved.parents or not resolved.is_file():
        raise ValueError('الملف خارج مجلدك أو غير موجود')
    return f'moos://apps/{kind}/' + urllib.parse.quote(resolved.as_uri(), safe='')


def open_route(url):
    if not allowed(url):
        return {'status': 'error', 'error': 'route_not_allowed'}
    try:
        subprocess.Popen(['moos-open', url], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError as exc:
        return {'status': 'error', 'error': type(exc).__name__}
    return {'status': 'ok'}
