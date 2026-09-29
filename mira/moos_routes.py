"""Open a MoOS route (moos://…) the owner clicked in Mira's window — only from a fixed list.

moos-open is MoOS's router; these are the routes Mira's pages may hand it. A route built from a
file (App Drop, a signed RPM) carries a file URL that moos-open validates again. Every pattern is
matched against the WHOLE url (re.fullmatch), and test_moos_routes proves each one reaches a case
in moos-open: a route the router does not declare is a dead button.
"""
import re
import subprocess
import urllib.parse
from pathlib import Path

_ALLOWED = [
    # (moplayer was listed here, but moos-open has had no app/moplayer arm since 2026-09-24.)
    r'moos://app/(store|remote|updater|recovery|moai)',
    r'moos://dev/(code|codex|claude|opencode)',
    # …inside a project registered in Mo AI's workspace (the Workbench's chosen project): moos-open
    # resolves the id to a folder inside $HOME itself; no part of the URL is ever used as a path.
    r'moos://dev/(code|codex|claude|opencode)/[0-9a-f]{20}',
    r'moos://remote/(start|stop|restart|fast-on|fast-off)',
    r'moos://agent/whatsapp-login',
    r'moos://settings/[a-z0-9][a-z0-9-]{0,39}',
    # The daily check's RDP/VNC finding: moos-open asks the owner first, then turns off the
    # desktop sharing that is not MoOS's (moos-remote-guard off). Mo PC Remote stays.
    r'moos://privacy/stop-sharing',
    r'moos://apps/install-(file|rpm)/file%3A%2F%2F%2F[A-Za-z0-9%._~\-]{1,600}',
]
_PATTERNS = [re.compile(pattern) for pattern in _ALLOWED]

# One real URL (at least) for every pattern above: test_moos_routes fails when a pattern has none,
# and checks each against moos-open's cases; the repo's user-experience gate can read the same list
# to count Mira as the emitter of the routes only Mira opens (moos://dev/<agent>/<project id>).
EXAMPLES = (
    'moos://app/store', 'moos://app/remote', 'moos://app/updater', 'moos://app/recovery', 'moos://app/moai',
    'moos://dev/code', 'moos://dev/codex', 'moos://dev/claude', 'moos://dev/opencode',
    'moos://dev/code/0123456789abcdef0123', 'moos://dev/codex/0123456789abcdef0123',
    'moos://dev/claude/0123456789abcdef0123', 'moos://dev/opencode/0123456789abcdef0123',
    'moos://remote/start', 'moos://remote/stop', 'moos://remote/restart', 'moos://remote/fast-on',
    'moos://remote/fast-off',
    'moos://agent/whatsapp-login',
    'moos://settings/update', 'moos://settings/assistant', 'moos://settings/remote', 'moos://settings/whats-new',
    'moos://privacy/stop-sharing',
    'moos://apps/install-file/file%3A%2F%2F%2Fvar%2Fhome%2Fowner%2FDownloads%2FTool.AppImage',
    'moos://apps/install-rpm/file%3A%2F%2F%2Fvar%2Fhome%2Fowner%2FDownloads%2Fpkg-1.0-1.x86_64.rpm',
)


def allowed(url):
    return isinstance(url, str) and any(pattern.fullmatch(url) for pattern in _PATTERNS)


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
