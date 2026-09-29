"""Every Mo AI tool, now Mira's: read from MoOS's single source of truth and run by its executor.

MoOS declares its assistant capabilities once, in `/usr/lib/moai/moai_tool_schemas.py`, and runs
them through `moai-control` (127.0.0.1:8079): `moos-inspect` reads, `moos-control` changes the
device instantly and reversibly, `moai-do` changes the system (install, update, repair) and may
ask for the owner's password through Polkit. Mira offers exactly those tools — whatever the
installed image declares — with the same promise: the executor decides what needs the owner's
confirmation, and Mira asks the OWNER, never the model, before it confirms.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
# The installed image is the authority; the MoOS tree next to Mira's source only serves tests and review.
SCHEMA_DIRS = ([Path(os.environ['MIRA_MOAI_SCHEMAS'])] if os.environ.get('MIRA_MOAI_SCHEMAS') else
               [Path('/usr/lib/moai'), ROOT.parent / 'system_files/usr/lib/moai'])
PORT = int(os.environ.get('MOAI_CONTROL_PORT', '8079'))
CONFIRM = ('user_confirm', 'privileged_confirm')


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
_cache = {}

# Arabic names for the confirmation card; anything else falls back to the tool's own name.
TITLES_AR = {
    'install_app': 'تثبيت تطبيق', 'uninstall_app': 'إزالة تطبيق', 'update_apps': 'تحديث التطبيقات',
    'fix_audio': 'إصلاح الصوت', 'optimize_system': 'تنظيف وتحسين النظام', 'setup_gaming': 'تجهيز الألعاب',
    'setup_windows': 'تجهيز برامج ويندوز', 'system_update': 'تحديث MoOS', 'system_rollback': 'الرجوع لإصدار MoOS السابق',
    'install_nvidia': 'تثبيت تعريف NVIDIA', 'update_firmware': 'تحديث البرامج الثابتة', 'setup_waydroid': 'تجهيز تطبيقات أندرويد',
    'remote_anywhere': 'التحكم عن بعد من أي مكان', 'toggle_wifi': 'الواي فاي', 'toggle_bluetooth': 'البلوتوث',
    'set_do_not_disturb': 'عدم الإزعاج', 'set_mic_mute': 'ميكروفون الكمبيوتر', 'device_report': 'تقرير الجهاز',
    'check_drivers': 'فحص التعريفات', 'net_doctor': 'طبيب الشبكة', 'gpu_report': 'تقرير كرت الشاشة',
    'inspect_boot': 'فحص الإقلاع', 'support_bundle': 'حزمة الدعم', 'os_state': 'حالة MoOS',
    'get_system_status': 'حالة الكمبيوتر', 'memory_status': 'الذاكرة', 'disk_status': 'القرص',
    'network_status': 'الشبكة', 'top_processes': 'أكثر البرامج استهلاكاً', 'list_failed_units': 'الخدمات المتعطّلة',
    'unit_status': 'حالة خدمة', 'read_journal': 'سجل النظام', 'read_moos_log': 'سجل MoOS',
    'list_installed_apps': 'التطبيقات المثبتة', 'list_skills': 'أدلة الإصلاح', 'read_skill': 'دليل إصلاح',
    'set_volume': 'صوت الكمبيوتر', 'set_mute': 'كتم الصوت', 'set_brightness': 'السطوع',
    'toggle_night_light': 'الإضاءة الليلية', 'set_theme_mode': 'مظهر النظام', 'take_screenshot': 'لقطة شاشة',
    'open_app': 'فتح تطبيق', 'show_windows': 'عرض النوافذ', 'arrange_windows': 'ترتيب النوافذ',
    'switch_desktop': 'سطح المكتب', 'switch_keyboard_layout': 'لغة لوحة المفاتيح', 'set_motion': 'حركة الواجهة',
    'set_glass_clarity': 'شفافية الزجاج', 'set_power_profile': 'وضع الطاقة', 'open_settings': 'الإعدادات',
}
TITLES_EN = {
    'install_app': 'Install an app', 'uninstall_app': 'Remove an app', 'update_apps': 'Update apps',
    'fix_audio': 'Repair sound', 'optimize_system': 'Clean up and optimise', 'setup_gaming': 'Set up gaming',
    'setup_windows': 'Set up Windows apps', 'system_update': 'Update MoOS', 'system_rollback': 'Roll back MoOS',
    'install_nvidia': 'Install the NVIDIA driver', 'update_firmware': 'Update firmware', 'setup_waydroid': 'Set up Android apps',
    'remote_anywhere': 'Remote control from anywhere', 'toggle_wifi': 'Wi-Fi', 'toggle_bluetooth': 'Bluetooth',
    'set_do_not_disturb': 'Do not disturb', 'set_mic_mute': 'Computer microphone', 'device_report': 'Device report',
    'check_drivers': 'Check drivers', 'net_doctor': 'Network doctor', 'gpu_report': 'Graphics report',
    'inspect_boot': 'Boot check', 'support_bundle': 'Support bundle', 'os_state': 'MoOS state',
}


def title(name, lang='ar'):
    table = TITLES_EN if lang == 'en' else TITLES_AR
    return table.get(name) or name.replace('_', ' ')


def _load():
    if 'schemas' in _cache:
        return _cache['schemas']
    for folder in SCHEMA_DIRS:
        if (folder / 'moai_tool_schemas.py').is_file():
            sys.path.insert(0, str(folder))
            try:
                import moai_tool_schemas
                _cache['module'] = moai_tool_schemas
                _cache['schemas'] = moai_tool_schemas.get_schemas_with_meta()
                return _cache['schemas']
            except Exception:
                pass
            finally:
                if sys.path and sys.path[0] == str(folder):
                    sys.path.pop(0)
    _cache['schemas'] = []
    return _cache['schemas']


def _gemini_schema(node):
    """OpenAI JSON schema → the Gemini dialect (upper-case types, no additionalProperties)."""
    if not isinstance(node, dict):
        return node
    out = {}
    kind = node.get('type')
    if isinstance(kind, list):
        kind = next((k for k in kind if k != 'null'), 'string')
    if kind:
        out['type'] = str(kind).upper()
    for key in ('description', 'enum', 'format', 'minimum', 'maximum'):
        if key in node:
            out[key] = node[key] if key != 'enum' else [str(v) for v in node[key]]
    if 'items' in node:
        out['items'] = _gemini_schema(node['items'])
    if 'properties' in node:
        out['properties'] = {k: _gemini_schema(v) for k, v in node['properties'].items()}
        if node.get('required'):
            out['required'] = list(node['required'])
    return out


def declarations(skip=()):
    """One Gemini function declaration per Mo AI tool the installed image declares."""
    decls = []
    for schema in _load():
        fn = schema['function']
        if fn['name'] in skip:
            continue
        meta = schema['_moos']
        note = {'read_only': ' Reads only; runs at once.', 'control': ' Instant, reversible device control.',
                'user_confirm': " Changes the system: Mira asks the owner to confirm first, then it runs.",
                'privileged_confirm': " Changes the system with administrator rights: the owner confirms, then types his password."}
        text = (fn.get('description') or fn['name']).strip()[:900].rstrip('.')
        decl = {'name': fn['name'], 'description': text + '.' + note.get(meta['category'], '')}
        params = fn.get('parameters') or {}
        if params.get('properties'):
            decl['parameters'] = _gemini_schema(params)
        decls.append(decl)
    return decls


def names():
    return {s['function']['name'] for s in _load()}


def meta(name):
    for schema in _load():
        if schema['function']['name'] == name:
            return schema['_moos']
    return None


def needs_confirmation(name, args):
    module = _cache.get('module')
    if module is not None:
        try:
            return bool(module.needs_confirmation(name, args))
        except Exception:
            return True
    info = meta(name)
    return info is None or info['category'] in CONFIRM


def search_apps(query, limit=5):
    """Mo Store's own catalogue search (Flathub, else the local remotes): real ids to install."""
    from urllib.parse import quote
    query = ' '.join(str(query or '').split())[:80]
    if not query:
        return {'status': 'error', 'error': 'empty_query', 'summary': 'لا يوجد اسم للبحث'}
    code, body = _request('/search?q=' + quote(query), timeout=30)
    if code != 200:
        return {'status': 'error', 'error': body.get('error', f'http_{code}'), 'summary': 'تعذّر البحث في المتجر'}
    apps = [{key: item.get(key) for key in ('id', 'name', 'summary', 'installed', 'verified', 'installs', 'recommended')}
            for item in (body.get('results') or [])[:limit] if isinstance(item, dict) and item.get('id')]
    if not apps:
        return {'status': 'ok', 'apps': [], 'summary': 'لم أجد تطبيقاً بهذا الاسم في المتجر'}
    return {'status': 'ok', 'apps': apps, 'source': body.get('source'),
            'summary': 'وجدت في المتجر: ' + '، '.join(str(a['name']) for a in apps[:3])}


def _local(text, lang='ar'):
    """Mo AI's services answer "عربي | English"; keep the owner's half."""
    parts = str(text or '').split(' | ', 1)
    return parts[0] if lang != 'en' or len(parts) == 1 else parts[1]


def health(lang='ar'):
    """The daily check, short: this MoOS, its updates, what needs attention and what uses the machine."""
    code, body = _request('/health', timeout=20)
    report = body.get('report') if code == 200 and isinstance(body, dict) else None
    if not isinstance(report, dict):
        return {'status': 'error', 'error': body.get('error', f'http_{code}') if isinstance(body, dict) else 'shape',
                'summary': 'تعذّر قراءة الفحص اليومي'}
    system, updates, summary = report.get('system') or {}, report.get('updates') or {}, report.get('summary') or {}
    out = {
        'status': 'ok',
        'checked_at': report.get('generated_at'),
        'moos': {'version': system.get('version'), 'signed': system.get('signed'), 'kernel': system.get('kernel'),
                 'update_staged_for_restart': bool(summary.get('system_update_staged') or system.get('staged')),
                 'rollback_kept': system.get('rollback')},
        'updates': {'automatic_nightly_system_update': updates.get('nightly_system_update'),
                    'last_nightly_result': updates.get('last_nightly_result'),
                    'app_updates_waiting': summary.get('app_updates', len(updates.get('apps') or []))},
        'attention': summary.get('status'),
        'findings': [{'severity': f.get('severity'), 'title': _local(f.get('title'), lang)}
                     for f in (report.get('findings') or [])[:8] if isinstance(f, dict)],
        'busiest': [{'name': r.get('name'), 'cpu_percent': r.get('cpu_percent'), 'memory_mb': r.get('rss_mb')}
                    for r in ((report.get('resources') or {}).get('top_cpu') or [])[:3] if isinstance(r, dict)],
    }
    staged = out['moos']['update_staged_for_restart']
    out['summary'] = (f"MoOS {system.get('version') or ''} · " +
                      ('تحديث جاهز بعد إعادة التشغيل' if staged else 'لا تحديث بانتظار إعادة التشغيل') +
                      f" · {len(out['findings'])} ملاحظات")
    return out


def _request(path, body=None, timeout=30):
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(f'http://127.0.0.1:{PORT}{path}', data=data,
                                     headers={'X-Moai-Control': '1', 'Content-Type': 'application/json'})
    try:
        with _OPENER.open(request, timeout=timeout) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as err:
        try:
            return err.code, json.load(err)
        except ValueError:
            return err.code, {'error': f'http_{err.code}'}
    except (urllib.error.URLError, OSError, ValueError) as err:
        return 0, {'error': 'moai_control_unreachable', 'detail': type(err).__name__}


def get(path, timeout=20):
    """GET one moai-control read endpoint (/quick /scan /diagnose /health /models /measure …).
    Returns the decoded body, or {'error': ...} on any failure."""
    code, body = _request(path, timeout=timeout)
    if code != 200 or not isinstance(body, (dict, list)):
        return {'error': (body or {}).get('error', f'http_{code}') if isinstance(body, dict) else f'http_{code}'}
    return body


def post(path, body, timeout=30):
    """POST to moai-control (/health/scan, /test …). Returns the body or {'error': ...}."""
    code, reply = _request(path, body, timeout=timeout)
    if code not in (200, 202) or not isinstance(reply, (dict, list)):
        return {'error': (reply or {}).get('error', f'http_{code}') if isinstance(reply, dict) else f'http_{code}'}
    return reply


def execute(name, args, confirmed=False):
    """Run one Mo AI tool. Returns a Mira tool result:
    ok/error for reads and controls; `confirm` when the owner must approve first;
    `pending` with a `job` id for an approved system change that is still running."""
    code, body = _request('/tool/execute', {'name': name, 'arguments': args or {}, 'confirmed': bool(confirmed)},
                          timeout=75)
    if code == 403 and body.get('error') == 'confirmation_required':
        return {'status': 'confirm', 'category': body.get('category'), 'summary': 'ينتظر موافقتك: ' + title(name)}
    if code == 202 and body.get('job'):
        return {'status': 'pending', 'job': body['job'], 'summary': 'بدأ التنفيذ: ' + title(name)}
    if code == 200:
        status = 'ok' if body.get('status') == 'ok' else 'error'
        return {'status': status, 'exit_code': body.get('exit_code'), 'output': body.get('output', ''),
                'duration_ms': body.get('duration_ms'), 'summary': ('تم: ' if status == 'ok' else 'تعذّر: ') + title(name)}
    if code == 409:
        return {'status': 'error', 'error': 'busy', 'summary': 'عملية أخرى ما زالت تعمل؛ انتظر انتهاءها'}
    return {'status': 'error', 'error': body.get('error', f'http_{code}'), 'summary': 'تعذّر: ' + title(name)}


def job(job_id):
    code, body = _request(f'/tool/job?id={job_id}', timeout=10)
    if code != 200:
        return {'status': 'error', 'error': body.get('error', f'http_{code}')}
    state = body.get('status')
    return {'status': 'pending' if state == 'running' else 'ok' if state == 'ok' else 'error', 'state': state,
            'exit_code': body.get('exit_code'), 'output': body.get('output', ''), 'tool': body.get('tool'),
            'duration_ms': body.get('duration_ms')}


def wait_job(job_id, timeout=45 * 60, interval=2.0, on_tick=None):
    """Follow an approved job until it really ends (a system update can take many minutes)."""
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        result = job(job_id)
        if result['status'] != 'pending':
            return result
        if on_tick:
            on_tick(result)
        time.sleep(interval)
    return {'status': 'pending', 'error': 'still_running', 'job': job_id}
