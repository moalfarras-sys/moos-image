"""Instant desktop control for Mira — everything here is read-only or reversible, so none of
it needs the owner's confirmation. Every backend is a FIXED program called with validated
arguments; no string from the model ever reaches a shell.

    media('toggle')                  play/pause the active MPRIS player (busctl/D-Bus)
    clipboard_read() / clipboard_write(text)   wl-paste / wl-copy, text only
    find_files('تقرير')              Baloo (baloosearch6) inside $HOME, else a bounded scandir
    open_path(path) / open_url(url)  xdg-open, detached, home/https only
    list_windows() / focus_window(q) / close_window(q)   KWin scripting over D-Bus
    system_volume_app(app, value)    per-application volume via pactl (optional)

Each function returns {'status', 'summary'(Arabic), ...} and never raises.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import subprocess
import time
from pathlib import Path
from typing import Optional

HOME = Path.home()
MEDIA_ROOTS = ('/run/media', '/media', '/mnt')
_SCRATCH = Path(os.environ.get('XDG_RUNTIME_DIR', '/tmp')) / 'mira-desktop'
_BUS = 'org.kde.KWin'

# ─── small helpers ────────────────────────────────────────────────────


def _run(argv, timeout=8.0, want_bytes=False):
    """Run a fixed program with a fixed argument LIST (never a shell). Returns
    (returncode, stdout, stderr). Raises nothing but TimeoutExpired's caller handles it."""
    proc = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=timeout)
    out = proc.stdout if want_bytes else proc.stdout.decode('utf-8', 'replace')
    err = proc.stderr.decode('utf-8', 'replace')
    return proc.returncode, out, err


def _err(summary_ar, error='error', status='error', **extra):
    return dict({'status': status, 'error': error, 'summary': summary_ar}, **extra)


def _session_bus_ok() -> bool:
    return bool(os.environ.get('WAYLAND_DISPLAY') or os.environ.get('DBUS_SESSION_BUS_ADDRESS')
                or (Path('/run/user') / str(os.getuid()) / 'bus').exists())


# ─── D-Bus through busctl (present on every Plasma session) ────────────
# busctl --user is used rather than a Python binding so the module has no import-time
# dependency on dbus/jeepney; --json=short gives parseable replies.


def _busctl(argv, timeout=6.0):
    code, out, err = _run(['busctl', '--user', '--json=short'] + argv, timeout=timeout)
    if code != 0:
        raise RuntimeError((err or out or 'busctl failed').strip()[:200])
    return json.loads(out) if out.strip() else {}


def _dbus_names() -> list[str]:
    data = _busctl(['call', 'org.freedesktop.DBus', '/org/freedesktop/DBus',
                    'org.freedesktop.DBus', 'ListNames'])
    return list(data.get('data', [[]])[0])


def _prop(service, path, interface, name):
    data = _busctl(['get-property', service, path, interface, name])
    return data.get('data', data) if isinstance(data, dict) else data


# ─── MPRIS media control ──────────────────────────────────────────────
_MPRIS_PREFIX = 'org.mpris.MediaPlayer2.'
_MPRIS_PATH = '/org/mpris/MediaPlayer2'
_PLAYER_IFACE = 'org.mpris.MediaPlayer2.Player'
_MEDIA_METHOD = {'play': 'Play', 'pause': 'Pause', 'toggle': 'PlayPause', 'playpause': 'PlayPause',
                 'next': 'Next', 'previous': 'Previous', 'prev': 'Previous', 'stop': 'Stop'}
_STATE_AR = {'Playing': 'يعمل', 'Paused': 'متوقف مؤقتاً', 'Stopped': 'متوقف'}


def _mpris_players() -> list[str]:
    return sorted(n for n in _dbus_names() if n.startswith(_MPRIS_PREFIX)
                  and not n.startswith(_MPRIS_PREFIX + 'playerctld'))


def _player_short(service: str) -> str:
    tail = service[len(_MPRIS_PREFIX):]
    return tail.split('.')[0]


def _player_status(service: str) -> dict:
    try:
        state = _prop(service, _MPRIS_PATH, _PLAYER_IFACE, 'PlaybackStatus') or ''
    except (RuntimeError, ValueError):
        state = ''
    title = artist = ''
    try:
        meta = _prop(service, _MPRIS_PATH, _PLAYER_IFACE, 'Metadata') or {}
        if isinstance(meta, dict):
            title = str(meta.get('xesam:title', '') or '')
            art = meta.get('xesam:artist')
            if isinstance(art, (list, tuple)):
                artist = ', '.join(str(a) for a in art)
            elif art:
                artist = str(art)
    except (RuntimeError, ValueError):
        pass
    return {'service': service, 'player': _player_short(service), 'state': state,
            'title': title.strip(), 'artist': artist.strip()}


def _pick_player(players: list[str], want: Optional[str]) -> Optional[str]:
    if want:
        want = want.lower()
        for service in players:
            if want in _player_short(service).lower():
                return service
        return None
    statuses = [_player_status(p) for p in players]
    for row in statuses:
        if row['state'] == 'Playing':
            return row['service']
    for row in statuses:
        if row['state'] == 'Paused':
            return row['service']
    return players[-1] if players else None


def media(action: str, player: Optional[str] = None) -> dict:
    """MPRIS control over the session bus. `action` in play/pause/toggle/next/previous/stop/status.
    Picks the playing player, else the most recently paused, else the last seen; lists on ambiguity."""
    action = str(action or '').strip().lower()
    if action not in _MEDIA_METHOD and action != 'status':
        return _err('إجراء وسائط غير مدعوم', 'bad_action', status='unsupported')
    if player is not None and not isinstance(player, str):
        return _err('اسم المشغّل غير صالح', 'bad_player')
    if not _session_bus_ok():
        return _err('لا توجد جلسة سطح مكتب', 'no_session', status='unsupported')
    try:
        players = _mpris_players()
    except (RuntimeError, ValueError, subprocess.SubprocessError, OSError) as exc:
        return _err('تعذّر الوصول لناقل الجلسة', type(exc).__name__)
    if not players:
        return _err('لا يوجد مشغّل وسائط يعمل الآن', 'no_player', status='unsupported', players=[])
    target = _pick_player(players, player)
    if target is None:
        names = [_player_short(p) for p in players]
        return {'status': 'partial', 'error': 'ambiguous', 'players': names,
                'summary': 'أكثر من مشغّل: ' + ' · '.join(names) + ' — حدّد أيّهم'}
    if action == 'status':
        st = _player_status(target)
        now = (st['title'] + (' — ' + st['artist'] if st['artist'] else '')).strip()
        label = _STATE_AR.get(st['state'], st['state'] or 'غير معروف')
        summary = f"{st['player']}: {label}" + (f" · {now}" if now else '')
        return dict(st, status='ok', players=[_player_short(p) for p in players], summary=summary)
    try:
        _busctl(['call', target, _MPRIS_PATH, _PLAYER_IFACE, _MEDIA_METHOD[action]])
    except (RuntimeError, ValueError, subprocess.SubprocessError, OSError) as exc:
        return _err('تعذّر إرسال أمر الوسائط', type(exc).__name__)
    verb = {'play': 'تشغيل', 'pause': 'إيقاف مؤقت', 'toggle': 'تبديل التشغيل', 'playpause': 'تبديل التشغيل',
            'next': 'التالي', 'previous': 'السابق', 'prev': 'السابق', 'stop': 'إيقاف'}[action]
    # An MPRIS method has no return value; read the state back so ok means observed.
    state = _player_status(target)['state']
    return {'status': 'ok', 'action': action, 'player': _player_short(target), 'state': state,
            'summary': f'{verb} · {_player_short(target)}' + (f' ({_STATE_AR.get(state, state)})' if state else '')}


# ─── clipboard ────────────────────────────────────────────────────────


def clipboard_read(limit: int = 4000) -> dict:
    """Read the Wayland clipboard as text. Reports honestly when it holds non-text content."""
    try:
        limit = max(1, min(int(limit), 100000))
    except (TypeError, ValueError):
        limit = 4000
    try:
        code, types_out, _ = _run(['wl-paste', '--list-types'], timeout=5)
    except (subprocess.SubprocessError, OSError, FileNotFoundError) as exc:
        return _err('تعذّر قراءة الحافظة', type(exc).__name__)
    types = [t.strip() for t in types_out.splitlines() if t.strip()]
    if code != 0 or not types:
        return {'status': 'ok', 'text': '', 'empty': True, 'summary': 'الحافظة فارغة'}
    if not any(t.startswith('text/') or t in ('TEXT', 'STRING', 'UTF8_STRING') for t in types):
        kind = types[0]
        return {'status': 'unsupported', 'error': 'non_text', 'types': types[:8],
                'summary': f'الحافظة تحتوي محتوى غير نصّي ({kind})'}
    try:
        code, out, _ = _run(['wl-paste', '--no-newline', '--type', 'text/plain'], timeout=5)
        if code != 0 or not out:
            code, out, _ = _run(['wl-paste', '--no-newline'], timeout=5)
    except (subprocess.SubprocessError, OSError) as exc:
        return _err('تعذّر قراءة الحافظة', type(exc).__name__)
    text = out
    truncated = len(text) > limit
    text = text[:limit]
    n = len(text)
    return {'status': 'ok', 'text': text, 'length': n, 'truncated': truncated,
            'summary': (f'قرأت الحافظة: {n} حرفاً' + ('…' if truncated else '')) if n else 'الحافظة فارغة'}


def clipboard_write(text: str) -> dict:
    if not isinstance(text, str):
        return _err('النص غير صالح', 'bad_text')
    if len(text) > 100000:
        return _err('النص أطول من الحد', 'too_long')
    try:
        proc = subprocess.run(['wl-copy', '--type', 'text/plain;charset=utf-8'],
                              input=text.encode('utf-8'), stdout=subprocess.DEVNULL,
                              stderr=subprocess.PIPE, timeout=5)
    except (subprocess.SubprocessError, OSError) as exc:
        return _err('تعذّر الكتابة إلى الحافظة', type(exc).__name__)
    if proc.returncode != 0:
        return _err('تعذّر الكتابة إلى الحافظة', 'wl_copy_failed')
    return {'status': 'ok', 'length': len(text), 'summary': f'نسخت {len(text)} حرفاً إلى الحافظة'}


# ─── file search ──────────────────────────────────────────────────────
_SEARCH_DIRS = ('Documents', 'Downloads', 'Desktop', 'Pictures', 'Music', 'Videos')
_SCANDIR_MAX = 5000


def _inside_home(path: Path) -> bool:
    try:
        resolved = path.resolve()
    except (OSError, RuntimeError):
        return False
    if resolved == HOME or HOME in resolved.parents:
        return True
    return any(str(resolved).startswith(root + '/') for root in MEDIA_ROOTS)


def _describe_file(path: Path) -> Optional[dict]:
    try:
        st = path.stat()
    except OSError:
        return None
    return {'path': str(path), 'name': path.name, 'size': st.st_size,
            'modified': time.strftime('%Y-%m-%d %H:%M', time.localtime(st.st_mtime)),
            'mtime': st.st_mtime, 'is_dir': path.is_dir()}


def _baloo_search(query: str, limit: int) -> Optional[list[dict]]:
    """Baloo results restricted to $HOME, or None when Baloo is unavailable/unindexed."""
    if not (Path('/usr/bin/baloosearch6').exists() or Path('/bin/baloosearch6').exists()):
        return None
    try:
        code, out, err = _run(['baloosearch6', '-l', str(limit * 3), '-d', str(HOME),
                               '-s', 'time', query], timeout=8)
    except (subprocess.SubprocessError, OSError, FileNotFoundError):
        return None
    if code != 0 and not out.strip():
        # An unconfigured/disabled indexer prints an error and no paths.
        return None
    rows = []
    for line in out.splitlines():
        line = line.strip()
        if line.startswith('file://'):
            line = line[len('file://'):]
        if not line.startswith('/'):        # skip banners/empty lines, keep only real paths
            continue
        p = Path(line)
        if not _inside_home(p):
            continue
        info = _describe_file(p)
        if info:
            rows.append(info)
        if len(rows) >= limit:
            break
    return rows


def _scandir_search(query: str, limit: int) -> list[dict]:
    needle = query.lower()
    seen = 0
    rows: list[dict] = []
    stack = [HOME / d for d in _SEARCH_DIRS if (HOME / d).is_dir()]
    while stack and seen < _SCANDIR_MAX and len(rows) < limit:
        base = stack.pop(0)
        try:
            with os.scandir(base) as it:
                for entry in it:
                    seen += 1
                    if seen > _SCANDIR_MAX:
                        break
                    name = entry.name
                    if name.startswith('.'):
                        continue
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(Path(entry.path))
                    except OSError:
                        pass
                    if needle in name.lower():
                        info = _describe_file(Path(entry.path))
                        if info:
                            rows.append(info)
                            if len(rows) >= limit:
                                break
        except OSError:
            continue
    rows.sort(key=lambda r: r['mtime'], reverse=True)
    return rows[:limit]


def find_files(query: str, limit: int = 10) -> dict:
    """Find files in the owner's home by name/content. Baloo first, bounded scandir as fallback."""
    query = ' '.join(str(query or '').split())
    if not query:
        return _err('لا يوجد ما يُبحث عنه', 'empty_query')
    try:
        limit = max(1, min(int(limit), 50))
    except (TypeError, ValueError):
        limit = 10
    source = 'baloo'
    rows = _baloo_search(query, limit)
    if rows is None:
        source, rows = 'scandir', _scandir_search(query, limit)
    if not rows:
        return {'status': 'ok', 'files': [], 'count': 0, 'source': source,
                'summary': f'لم أجد ملفات تطابق «{query}»'}
    public = [{k: r[k] for k in ('path', 'name', 'size', 'modified', 'is_dir')} for r in rows]
    return {'status': 'ok', 'files': public, 'count': len(public), 'source': source,
            'summary': f'وجدت {len(public)} ملفاً لـ «{query}» ({"بالو" if source == "baloo" else "مسح"})'}


# ─── open path / url ──────────────────────────────────────────────────


def _detached_open(target: str) -> tuple[bool, str]:
    """xdg-open, detached so it outlives this process. moai-open first (it fixes the
    Wayland/X env for a sandboxed caller), plain xdg-open via systemd-run as fallback."""
    if Path('/usr/bin/moai-open').exists():
        try:
            code, _, _ = _run(['moai-open', 'xdg-open', target], timeout=10)
            if code == 0:
                return True, 'moai-open'
        except (subprocess.SubprocessError, OSError):
            pass
    try:
        unit = 'mira-open-' + secrets.token_hex(4)
        code, out, err = _run(['systemd-run', '--user', '--collect', '--quiet',
                               '--unit=' + unit, '--', 'xdg-open', target], timeout=10)
        if code == 0:
            return True, 'systemd-run'
    except (subprocess.SubprocessError, OSError):
        pass
    try:
        subprocess.Popen(['xdg-open', target], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
        return True, 'xdg-open'
    except (subprocess.SubprocessError, OSError) as exc:
        return False, type(exc).__name__


_CODE_SUFFIXES = {'.desktop', '.sh', '.bash', '.zsh', '.py', '.pl', '.rb', '.js', '.appimage', '.run', '.bin', '.exe',
                  '.msi', '.bat', '.cmd', '.com', '.jar', '.flatpakref', '.flatpakrepo', '.rpm', '.deb', '.apk',
                  '.kwinscript', '.plasmoid', '.service'}


def _runs_code(path: Path) -> bool:
    """True for a file whose default "open" executes something (launchers, scripts, programs)."""
    if path.is_dir():
        return False
    if path.suffix.lower() in _CODE_SUFFIXES:
        return True
    try:
        if os.access(path, os.X_OK):
            return True
        with open(path, 'rb') as stream:
            head = stream.read(4)
    except OSError:
        return True
    return head.startswith(b'#!') or head == b'\x7fELF' or head.startswith(b'MZ')


def open_path(path: str) -> dict:
    """Open an existing path inside the owner's home or removable media, detached."""
    if not isinstance(path, str) or not path.strip():
        return _err('لا يوجد مسار', 'empty_path')
    p = Path(os.path.expanduser(path.strip()))
    if not p.exists():
        return _err('المسار غير موجود', 'not_found')
    if not _inside_home(p):
        return _err('يُسمح فقط بمسارات داخل مجلد المالك أو وسائط مركّبة', 'outside_home')
    if _runs_code(p.resolve()):
        # Opening a launcher, script or program is running it: never on a model's word.
        return _err('هذا ملف يشغّل برنامجاً؛ افتحه بنفسك إن أردت', 'executable', status='unsupported')
    ok, how = _detached_open(str(p.resolve()))
    if not ok:
        return _err('تعذّر فتح المسار', how)
    return {'status': 'ok', 'path': str(p), 'via': how, 'summary': f'فتحت {p.name}'}


def open_url(url: str) -> dict:
    """Open an http/https URL in the default browser, detached."""
    if not isinstance(url, str) or not url.strip():
        return _err('لا يوجد رابط', 'empty_url')
    url = url.strip()
    if not re.match(r'^https?://[^\s]+$', url, re.I) or len(url) > 4000:
        return _err('يُسمح فقط بروابط http أو https', 'bad_url')
    ok, how = _detached_open(url)
    if not ok:
        return _err('تعذّر فتح الرابط', how)
    host = re.sub(r'^https?://', '', url).split('/')[0]
    return {'status': 'ok', 'url': url, 'via': how, 'summary': f'فتحت الرابط · {host}'}


# ─── KWin windows ─────────────────────────────────────────────────────
# Window listing/focus/close go through KWin's scripting service. A tiny JS script reads
# workspace.windowList() and reports the JSON back to a private, random D-Bus interface that
# this process owns, so the reply is authenticated to us and never touches the clipboard.
# Verified on the live 6.7.5 Wayland session (2026-09-29): loadScript + Script.run + a
# callDBus reply round-trips in ~2 ms.

_WINDOWS_JS = r'''
var out = [];
try {
  var list = workspace.windowList ? workspace.windowList() : workspace.clientList();
  for (var i = 0; i < list.length; i++) {
    var w = list[i];
    try {
      out.push({
        id: String(w.internalId),
        caption: String(w.caption || ''),
        cls: String(w.resourceClass || ''),
        name: String(w.resourceName || ''),
        desktopFile: String(w.desktopFileName || ''),
        pid: (w.pid || 0),
        normal: !!w.normalWindow,
        dialog: !!w.dialog,
        skipTaskbar: !!w.skipTaskbar,
        minimized: !!w.minimized,
        active: (w === workspace.activeWindow)
      });
    } catch (e1) {}
  }
} catch (e2) {}
callDBus(%(dest)s, %(path)s, %(iface)s, "report", %(token)s, JSON.stringify(out));
'''

_ACTION_JS = r'''
try {
  var list = workspace.windowList ? workspace.windowList() : workspace.clientList();
  var done = 0, hit = "";
  for (var i = 0; i < list.length; i++) {
    var w = list[i];
    if (String(w.internalId) === %(wid)s) {
      hit = String(w.caption || '');
      if (%(mode)s === "close") { w.closeWindow(); done = 1; }
      else {
        if (typeof workspace.activeWindow !== "undefined") { workspace.activeWindow = w; }
        else if (workspace.forceActivateWindow) { workspace.forceActivateWindow(w); }
        if (w.minimized) { w.minimized = false; }
        done = 1;
      }
      break;
    }
  }
  callDBus(%(dest)s, %(path)s, %(iface)s, "report", %(token)s, JSON.stringify({done: done, caption: hit}));
} catch (e) {
  callDBus(%(dest)s, %(path)s, %(iface)s, "report", %(token)s, JSON.stringify({done: 0, error: String(e)}));
}
'''


def _kwin_available() -> bool:
    try:
        return _BUS in _dbus_names()
    except (RuntimeError, ValueError, subprocess.SubprocessError, OSError):
        return False


def _run_kwin_script(js_template: str, subst: dict, timeout: float = 6.0) -> Optional[dict]:
    """Load a one-shot KWin script that reports one JSON payload back to a private interface
    this process owns. Returns the decoded payload, or None on any failure. Requires jeepney
    (system site-package); falls back to None (callers report unsupported) if it is missing."""
    try:
        from jeepney import DBusAddress, new_method_call, new_method_return, MatchRule
        from jeepney.io.blocking import open_dbus_connection
    except ImportError:
        return None
    token = secrets.token_hex(8)
    iface = 'org.moos.Mira.Windows'
    obj_path = '/org/moos/Mira/Windows'
    _SCRATCH.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(_SCRATCH, 0o700)
    except OSError:
        pass
    script_path = _SCRATCH / ('kwin-' + token + '.js')
    conn = None
    plugin = 'mira-kwin-' + token
    scripting = None
    try:
        conn = open_dbus_connection(bus='SESSION')
        fields = {'dest': json.dumps(conn.unique_name), 'path': json.dumps(obj_path),
                  'iface': json.dumps(iface), 'token': json.dumps(token)}
        fields.update({k: json.dumps(v) for k, v in subst.items()})
        script_path.write_text(js_template % fields, encoding='utf-8')
        try:
            os.chmod(script_path, 0o600)
        except OSError:
            pass
        from jeepney import DBusAddress as _A
        scripting = _A('/Scripting', bus_name=_BUS, interface='org.kde.kwin.Scripting')
        rule = MatchRule(type='method_call', interface=iface, member='report')
        with conn.filter(rule) as queue:
            reply = conn.send_and_get_reply(
                new_method_call(scripting, 'loadScript', 'ss', (str(script_path), plugin)),
                timeout=timeout)
            script_id = reply.body[0]
            script_obj = DBusAddress(f'/Scripting/Script{script_id}', bus_name=_BUS,
                                     interface='org.kde.kwin.Script')
            conn.send_and_get_reply(new_method_call(script_obj, 'run'), timeout=timeout)
            msg = conn.recv_until_filtered(queue, timeout=timeout)
            conn.send(new_method_return(msg))
            got_token, payload = msg.body
        if got_token != token:
            return None
        return json.loads(payload)
    except Exception:
        return None
    finally:
        try:
            if conn is not None and scripting is not None:
                conn.send_and_get_reply(new_method_call(scripting, 'unloadScript', 's', (plugin,)),
                                        timeout=2)
        except Exception:
            pass
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        try:
            script_path.unlink(missing_ok=True)
        except OSError:
            pass


def _real_windows(raw: list[dict]) -> list[dict]:
    """Windows a person would call windows: normal, not skipped, with a caption."""
    out = []
    for w in raw:
        if not isinstance(w, dict):
            continue
        if w.get('skipTaskbar') and not w.get('normal'):
            continue
        if not w.get('normal') and not w.get('dialog'):
            continue
        if not (w.get('caption') or '').strip():
            continue
        out.append(w)
    return out


def list_windows() -> dict:
    """List the open application windows via KWin scripting."""
    if not _session_bus_ok() or not _kwin_available():
        return _err('لا توجد جلسة KWin', 'no_kwin', status='unsupported')
    payload = _run_kwin_script(_WINDOWS_JS, {})
    if payload is None or not isinstance(payload, list):
        return _err('تعذّر قراءة النوافذ من KWin', 'kwin_failed', status='unsupported')
    wins = _real_windows(payload)
    public = [{'id': w['id'], 'title': w.get('caption', ''), 'app': w.get('cls', ''),
               'active': bool(w.get('active')), 'minimized': bool(w.get('minimized'))} for w in wins]
    if not public:
        return {'status': 'ok', 'windows': [], 'count': 0, 'summary': 'لا توجد نوافذ مفتوحة'}
    titles = ' · '.join(w['title'][:30] for w in public[:4])
    return {'status': 'ok', 'windows': public, 'count': len(public),
            'summary': f'{len(public)} نافذة مفتوحة: {titles}'}


def _match_window(query: str) -> tuple[Optional[dict], list[dict], list[dict]]:
    """Return (single match or None, all matches, all real windows)."""
    payload = _run_kwin_script(_WINDOWS_JS, {})
    if payload is None or not isinstance(payload, list):
        return None, [], []
    wins = _real_windows(payload)
    needle = ' '.join(str(query or '').split()).lower()
    if not needle:
        return None, [], wins
    matches = [w for w in wins if needle in (w.get('caption', '') + ' ' + w.get('cls', '')
                                             + ' ' + w.get('desktopFile', '')).lower()]
    # Prefer a class/desktop-file match when several captions coincide.
    exact = [w for w in matches if needle == w.get('cls', '').lower()
             or needle == w.get('desktopFile', '').lower()]
    if len(exact) == 1:
        return exact[0], matches, wins
    if len(matches) == 1:
        return matches[0], matches, wins
    return None, matches, wins


def _window_action(query: str, mode: str, verb_ar: str) -> dict:
    if not isinstance(query, str) or not query.strip():
        return _err('حدّد النافذة', 'empty_query')
    if not _session_bus_ok() or not _kwin_available():
        return _err('لا توجد جلسة KWin', 'no_kwin', status='unsupported')
    match, matches, wins = _match_window(query)
    if not wins and not matches:
        return _err('تعذّر قراءة النوافذ من KWin', 'kwin_failed', status='unsupported')
    if match is None:
        if not matches:
            return _err(f'لا توجد نافذة تطابق «{query}»', 'no_match', status='partial')
        names = ' · '.join(w.get('caption', '')[:30] for w in matches[:5])
        return {'status': 'partial', 'error': 'ambiguous',
                'windows': [{'id': w['id'], 'title': w.get('caption', '')} for w in matches],
                'summary': f'عدة نوافذ تطابق «{query}»: {names} — حدّد واحدة'}
    payload = _run_kwin_script(_ACTION_JS, {'wid': match['id'], 'mode': mode})
    if not isinstance(payload, dict) or not payload.get('done'):
        return _err(f'تعذّر {verb_ar} النافذة', 'action_failed', status='partial',
                    title=match.get('caption', ''))
    return {'status': 'ok', 'title': match.get('caption', ''), 'app': match.get('cls', ''),
            'summary': f'{verb_ar} · {match.get("caption", "")[:40]}'}


def focus_window(query: str) -> dict:
    """Raise and focus the window whose title/class matches `query`."""
    return _window_action(query, 'focus', 'فعّلت')


def close_window(query: str) -> dict:
    """Ask the window whose title/class matches `query` to close (the app may prompt to save)."""
    return _window_action(query, 'close', 'أغلقت')


# ─── per-application volume (optional) ─────────────────────────────────


def system_volume_app(app: str, value) -> dict:
    """Set one application's output volume (0–100) via pactl sink-inputs. Reversible."""
    if not isinstance(app, str) or not app.strip():
        return _err('حدّد التطبيق', 'empty_app')
    try:
        value = int(round(float(value)))
    except (TypeError, ValueError):
        return _err('القيمة يجب أن تكون رقماً بين 0 و100', 'bad_value')
    if not 0 <= value <= 100:
        return _err('القيمة بين 0 و100', 'out_of_range')
    try:
        code, out, _ = _run(['pactl', '-f', 'json', 'list', 'sink-inputs'], timeout=6)
    except (subprocess.SubprocessError, OSError, FileNotFoundError) as exc:
        return _err('تعذّر قراءة قنوات الصوت', type(exc).__name__)
    try:
        inputs = json.loads(out or '[]')
    except ValueError:
        return _err('تعذّر قراءة قنوات الصوت', 'bad_json')
    needle = app.strip().lower()
    hits = []
    for si in inputs:
        props = si.get('properties', {}) if isinstance(si, dict) else {}
        haystack = ' '.join(str(props.get(k, '')) for k in
                            ('application.name', 'application.process.binary', 'media.name')).lower()
        if needle in haystack:
            hits.append(si)
    if not hits:
        return _err(f'لا يوجد تطبيق صوتي باسم «{app}»', 'no_app', status='partial')
    changed = 0
    for si in hits:
        sid = si.get('index')
        if sid is None:
            continue
        try:
            rc, _, _ = _run(['pactl', 'set-sink-input-volume', str(sid), f'{value}%'], timeout=5)
            if rc == 0:
                changed += 1
        except (subprocess.SubprocessError, OSError):
            pass
    if not changed:
        return _err('تعذّر ضبط مستوى صوت التطبيق', 'set_failed', status='partial')
    return {'status': 'ok', 'app': app, 'value': value, 'streams': changed,
            'summary': f'ضبطت صوت {app} على {value}%'}
