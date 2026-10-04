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
import re
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

# The owner-facing name of every Mo AI tool: cards, the System centre, tool events. test_tools fails
# when the schemas declare a tool that either table lacks (the English UI used to show "get system status").
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
    # Coding agents, set-up, updates and Mo PC Remote.
    'install_codex': 'تثبيت Codex', 'install_claude_code': 'تثبيت Claude Code', 'install_opencode': 'تثبيت OpenCode',
    'install_hermes': 'تثبيت Hermes', 'install_openclaw': 'تثبيت وكيل الهاتف OpenClaw',
    'smart_setup': 'الإعداد الذكي للتطبيقات', 'check_system_update': 'البحث عن تحديث MoOS',
    'restart_computer': 'إعادة تشغيل الكمبيوتر', 'install_rpm': 'تثبيت حزمة RPM موقّعة',
    'remote_control': 'Mo PC Remote', 'fast_remote': 'الوضع السريع في Mo PC Remote',
    'desktop_size': 'حجم سطح المكتب السحابي',
    # The desktop's hands (W9.10).
    'list_windows': 'النوافذ وأسطح المكتب', 'window_action': 'نافذة', 'move_window_to_desktop': 'نقل نافذة',
    'go_to_desktop': 'الانتقال إلى سطح مكتب', 'add_or_remove_desktop': 'أسطح المكتب', 'control_media': 'الوسائط',
    'lock_screen': 'قفل الشاشة', 'set_reminder': 'تذكير', 'manage_reminders': 'التذكيرات',
    'open_web_page': 'فتح صفحة ويب', 'open_folder': 'فتح مجلد', 'set_animation_speed': 'سرعة الحركة',
    'set_screen_lock': 'القفل التلقائي للشاشة', 'set_click_mode': 'نمط النقر',
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
    'get_system_status': 'Computer status', 'memory_status': 'Memory', 'disk_status': 'Disk space',
    'network_status': 'Network', 'top_processes': 'Busiest programs', 'list_failed_units': 'Failed services',
    'unit_status': 'Service status', 'read_journal': 'System log', 'read_moos_log': 'MoOS log',
    'list_installed_apps': 'Installed apps', 'list_skills': 'Repair guides', 'read_skill': 'Repair guide',
    'set_volume': 'Computer volume', 'set_mute': 'Mute sound', 'set_brightness': 'Brightness',
    'toggle_night_light': 'Night light', 'set_theme_mode': 'System appearance', 'take_screenshot': 'Screenshot',
    'open_app': 'Open an app', 'show_windows': 'Show windows', 'arrange_windows': 'Arrange windows',
    'switch_desktop': 'Switch desktop', 'switch_keyboard_layout': 'Keyboard language', 'set_motion': 'Interface motion',
    'set_glass_clarity': 'Glass clarity', 'set_power_profile': 'Power mode', 'open_settings': 'Settings',
    'install_codex': 'Install Codex', 'install_claude_code': 'Install Claude Code', 'install_opencode': 'Install OpenCode',
    'install_hermes': 'Install Hermes', 'install_openclaw': 'Install the OpenClaw phone agent',
    'smart_setup': 'Smart app setup', 'check_system_update': 'Check for a MoOS update',
    'restart_computer': 'Restart the computer', 'install_rpm': 'Install a signed RPM package',
    'remote_control': 'Mo PC Remote', 'fast_remote': 'Mo PC Remote fast mode',
    'desktop_size': 'Cloud desktop size',
    'list_windows': 'Windows and desktops', 'window_action': 'Window', 'move_window_to_desktop': 'Move a window',
    'go_to_desktop': 'Go to a desktop', 'add_or_remove_desktop': 'Desktops', 'control_media': 'Media',
    'lock_screen': 'Lock the screen', 'set_reminder': 'Reminder', 'manage_reminders': 'Reminders',
    'open_web_page': 'Open a web page', 'open_folder': 'Open a folder', 'set_animation_speed': 'Animation speed',
    'set_screen_lock': 'Automatic screen lock', 'set_click_mode': 'Click mode',
}

# What approving a system change will do, in the owner's words. The schemas are the authority
# (`_moos['consequence_ar'|'consequence_en']`); these answer only while the installed image's schemas
# carry none. Each line was checked against the moai-do action it describes (2026-09-29).
CONSEQUENCES_AR = {
    'install_app': 'ينزّل التطبيق من المتجر ويثبّته لحسابك؛ تستطيع إزالته متى شئت.',
    'uninstall_app': 'يحذف التطبيق لحسابك عبر Mo Store؛ تستطيع إعادة تثبيته في أي وقت.',
    'update_apps': 'يحدّث كل تطبيقاتك عبر Mo Store؛ قد يستغرق بضع دقائق.',
    'fix_audio': 'يعيد تشغيل خدمات الصوت فينقطع الصوت لحظة، بلا صلاحيات مسؤول.',
    'optimize_system': 'يحذف البيانات غير المستخدمة والسجلات الأقدم من 7 أيام؛ ملفاتك الشخصية لا تُمسّ، وقد تُطلب كلمة المرور لتقليص السجلات.',
    'setup_gaming': 'يثبّت من المتجر ما ينقص فقط من Steam وBottles وLutris وProtonUp.',
    'setup_windows': 'يثبّت Bottles لتشغيل برامج ويندوز.',
    'system_update': 'يجهّز تحديث MoOS موقّعاً يُطبَّق عند إعادة التشغيل؛ النسخة الحالية تبقى للرجوع. يطلب كلمة المرور.',
    'system_rollback': 'يرجع إلى نسخة MoOS السابقة عند إعادة التشغيل التالية. يطلب كلمة المرور.',
    'install_nvidia': 'ينتقل إلى نسخة MoOS الخاصة بـ NVIDIA عند إعادة التشغيل؛ النسخة الحالية تبقى للرجوع. يطلب كلمة المرور.',
    'update_firmware': 'يثبّت تحديثات البرامج الثابتة للأجهزة، ولا يمكن التراجع عنها. يطلب كلمة المرور.',
    'setup_waydroid': 'يهيّئ ويشغّل بيئة تطبيقات أندرويد. يطلب كلمة المرور.',
    'remote_anywhere': 'يعطي هذا الكمبيوتر عنوان HTTPS على شبكتك الخاصة في Tailscale ليعمل التحكم من بيانات الجوال؛ لا شيء يُنشر على الإنترنت العام.',
    'toggle_wifi': 'إطفاء الواي فاي يقطع أي تحكم بهذا الكمبيوتر عن بعد.',
    'toggle_bluetooth': 'إطفاء البلوتوث يوقف لوحة المفاتيح والماوس اللاسلكيين فوراً.',
    'set_do_not_disturb': 'تشغيله يُسكت كل الإشعارات حتى تطفئه بنفسك.',
    'set_mic_mute': 'إعادة الميكروفون تلغي الكتم الذي اخترته.',
    'install_codex': 'يثبّت Codex لحسابك فقط داخل مجلدك، بلا صلاحيات مسؤول.',
    'install_claude_code': 'يثبّت Claude Code لحسابك فقط داخل مجلدك، بلا صلاحيات مسؤول.',
    'install_opencode': 'يثبّت OpenCode لحسابك ويوصله بعقل Mo AI السحابي المجاني، بلا صلاحيات مسؤول.',
    'install_hermes': 'ينزّل Hermes الرسمي (قرابة 400 ميغابايت) لحسابك ويتحقق من كل ملف بالتجزئة.',
    'install_openclaw': 'يثبّت وكيل الهاتف لتراسل الكمبيوتر من تليجرام، في مجلدك وبلا كلمة مرور؛ يحتاج عقلاً سحابياً مضبوطاً أولاً.',
    'smart_setup': 'يثبّت من المتجر التطبيقات الأساسية الناقصة حسب عتاد جهازك، بلا صلاحيات مسؤول.',
    'restart_computer': 'يعيد تشغيل الكمبيوتر الآن: البرامج المفتوحة تُغلق، فاحفظ عملك أولاً.',
    'install_rpm': 'يتحقق من توقيع الحزمة ويجهّزها في نسخة جديدة تظهر بعد إعادة التشغيل؛ النسخة الحالية تبقى للرجوع. يطلب كلمة المرور.',
}
CONSEQUENCES_EN = {
    'install_app': 'Downloads the app from the store and installs it for your account; you can remove it any time.',
    'uninstall_app': 'Removes the app for your account through Mo Store; you can reinstall it any time.',
    'update_apps': 'Updates all your apps through Mo Store; this can take a few minutes.',
    'fix_audio': 'Restarts the sound services, so sound drops for a moment. No administrator rights.',
    'optimize_system': 'Removes unused data and logs older than 7 days; your personal files are untouched, and trimming the logs may ask for your password.',
    'setup_gaming': 'Installs whichever of Steam, Bottles, Lutris and ProtonUp are missing, from the store.',
    'setup_windows': 'Installs Bottles to run Windows programs.',
    'system_update': 'Stages a signed MoOS update that applies when you restart; the current version stays for rollback. Asks for your password.',
    'system_rollback': 'Returns to the previous MoOS version at the next restart. Asks for your password.',
    'install_nvidia': 'Moves to the MoOS NVIDIA edition at the next restart; the current version stays for rollback. Asks for your password.',
    'update_firmware': 'Installs device firmware updates, which cannot be undone. Asks for your password.',
    'setup_waydroid': 'Sets up and starts the Android app environment. Asks for your password.',
    'remote_anywhere': 'Gives this computer an HTTPS name on your private Tailscale network so the remote works over mobile data; nothing is published to the public internet.',
    'toggle_wifi': 'Turning Wi-Fi off cuts any remote control of this computer.',
    'toggle_bluetooth': 'Turning Bluetooth off stops wireless keyboards and mice at once.',
    'set_do_not_disturb': 'Turning it on silences every notification until you turn it off.',
    'set_mic_mute': 'Unmuting undoes the microphone mute you chose.',
    'install_codex': 'Installs Codex for your account only, inside your home folder, without administrator rights.',
    'install_claude_code': 'Installs Claude Code for your account only, inside your home folder, without administrator rights.',
    'install_opencode': "Installs OpenCode for your account and connects it to Mo AI's free cloud brain, without administrator rights.",
    'install_hermes': 'Downloads the official Hermes (about 400 MB) for your account and verifies every file by hash.',
    'install_openclaw': 'Installs the phone agent so you can message this computer from Telegram, in your home folder with no password; it needs a cloud brain set up first.',
    'smart_setup': 'Installs, from the store, the essential apps your hardware plan says are missing. No administrator rights.',
    'restart_computer': 'Restarts the computer now: open programs close, so save your work first.',
    'install_rpm': 'Verifies the package signature and stages it in a new version that appears after a restart; the current version stays for rollback. Asks for your password.',
}

# Coding agents moai-control reports (`/quick` agents), as the owner knows them.
AGENT_NAMES = {'codex': 'Codex', 'claude': 'Claude Code', 'opencode': 'OpenCode', 'hermes': 'Hermes',
               'openclaw': 'OpenClaw'}


def title(name, lang='ar'):
    table = TITLES_EN if lang == 'en' else TITLES_AR
    return table.get(name) or name.replace('_', ' ')


def consequence(name, lang='ar'):
    """One sentence on what approving `name` will do, for the owner's card and the model's answer.
    The installed schemas' own `consequence_ar` / `consequence_en` win; '' when nothing is known."""
    info = meta(name) or {}
    text = info.get('consequence_en' if lang == 'en' else 'consequence_ar')
    if isinstance(text, str) and text.strip():
        return ' '.join(text.split())[:300]
    return (CONSEQUENCES_EN if lang == 'en' else CONSEQUENCES_AR).get(name, '')


# ─── identity: this computer runs MoOS ──────────────────────────────────────
# One wording for every model that speaks for Mira (her voice and text brains, the researcher).
# It is passive on purpose, so it reads the same in a feminine persona and a neutral researcher.
# The absolute form ("never name any Linux distribution") made Mira evasive about a friend's laptop
# or a server; what is forbidden is linking another system to THIS computer. The base's own name
# is never left to a prompt: scrub_identity removes it from everything a model reads.
IDENTITY = (
    'هوية النظام: كمبيوتر المالك يعمل بنظام MoOS، وهو نظام تشغيل كامل بذاته؛ لا يوصف أبداً بأنه نظام آخر '
    'أو مبني على نظام آخر، ولا تُسمّى أي توزيعة أخرى على أنها نظامه أو أساسه، ولا يُخمَّن أساسه من أسماء الأدوات '
    'أو الحزم، وتُذكر نواته رقماً فقط (مثل 7.2.7-200) بلا أي لاحقة. أنظمة التشغيل الأخرى يمكن الحديث عنها '
    'كموضوع عام (لكمبيوتر صديق أو لخادم) دون ربطها بهذا الكمبيوتر، وويندوز وأندرويد تُذكر كبرامج وتطبيقات يشغّلها MoOS. ',
    "Identity: the owner's computer runs MoOS, a complete operating system of its own. Never say it is, or is "
    'based on, another system; never name another distribution as its system or base, and never guess its base '
    'from tool or package names; give its kernel as a number only. Other operating systems may be discussed as '
    "general topics (a friend's laptop, a server) without linking them to this computer. ")

# A kernel release carries the base's build tag and the architecture (7.2.7-200.<tag>.x86_64).
# The owner reads "7.2.7-200": the rest is plumbing (AGENTS.md, the identity contract).
_DIST_TAG = re.compile(r'(?<=\d)\.(?:fc|el)\d+(?:_\d+)*')
_ARCH_TAIL = re.compile(r'\.(?:x86_64|aarch64|ppc64le|s390x|i686|noarch)$')
# The base distribution's names as its tools print them (journal, rpm-ostree, dnf remotes, the
# kernel's build line) and as a model writes them in Arabic; the same set the image's firewall
# forbids (build_files/verify_no_foreign_identity.py). A letter may not touch the Latin names (so
# "hundred hats" stays), but '_' and digits may (os-release's *_SUPPORT_PRODUCT keys, a remote named <base>44).
# «ريد هات» only as its own words: «أريد هاتفاً» ("I want a phone") contains the same letters.
_BASE_NAME = re.compile(
    r'(?<![a-z])(?:fedora(?:[ _-]?(?:linux|project|kinoite|atomic|silverblue|workstation))?'
    r'|red[ _-]?hat(?:,? inc\b\.?)?|rhel|kinoite|silverblue)(?![a-z])'
    r'|فيدورا(?:\s+لينكس)?|(?<![؀-ۿ])ريد\s*هات(?![؀-ۿ])', re.I)


def clean_kernel(value):
    """A kernel release as a number only: '7.2.7-200.fc44.x86_64' -> '7.2.7-200'."""
    text = ' '.join(str(value or '').split())[:80]
    return _ARCH_TAIL.sub('', _DIST_TAG.sub('', text))


def scrub_identity(value):
    """What a model reads or the owner sees, as MoOS: no base release tag ('…-200.fc44…' -> '…-200…')
    and no base name (-> 'MoOS'). Strings, and the strings inside lists and dicts (keys stay)."""
    if isinstance(value, str):
        return _BASE_NAME.sub('MoOS', _DIST_TAG.sub('', value))
    if isinstance(value, dict):
        return {key: scrub_identity(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [scrub_identity(item) for item in value]
    return value


# What a PAGE shows goes one step further than what a model reads: the architecture that follows a
# release tag leaves with it ('pipewire-1.4.9-1.<tag>.x86_64' -> 'pipewire-1.4.9-1'), and a tag
# standing on its own ('… on the <tag> base') goes too. Letters inside a word stay ('fcitx5', 'shelf').
_RELEASE_TAG = re.compile(r'(?:(?<=\d)|(?<![\w.]))\.(?:fc|el)\d+(?:_\d+)*'
                          r'(?:\.(?:x86_64|aarch64|ppc64le|s390x|i686|noarch))?(?!\w)')


def clean_identity(text):
    """Backend text as the owner may read it on a page: no base release tag (with its architecture),
    no base distribution's name (-> 'MoOS'). The one cleaner every page uses, built on scrub_identity
    (the structured form for what a model reads). Never apply it to store search results: a
    third-party app's name and id must stay exact to be installed or removed."""
    return scrub_identity(_RELEASE_TAG.sub('', '' if text is None else str(text)))


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
    """Mo Store's own catalogue search (Flathub, else the local remotes): real ids to install.
    Results are never identity-scrubbed: a third-party app's name and id stay exact. `icon` is the
    store's picture URL (the Apps page accepts only Flathub's media host); `note` is MoOS's own
    bilingual remark (a desktop mismatch, or why MoOS picks this app)."""
    from urllib.parse import quote
    query = ' '.join(str(query or '').split())[:80]
    if not query:
        return {'status': 'error', 'error': 'empty_query', 'summary': 'لا يوجد اسم للبحث'}
    code, body = _request('/search?q=' + quote(query), timeout=30)
    if code != 200:
        return {'status': 'error', 'error': body.get('error', f'http_{code}'), 'summary': 'تعذّر البحث في المتجر'}
    apps = [{key: item.get(key) for key in ('id', 'name', 'summary', 'installed', 'verified', 'installs', 'recommended',
                                            'icon', 'note')}
            for item in (body.get('results') or [])[:limit] if isinstance(item, dict) and item.get('id')]
    if not apps:
        return {'status': 'ok', 'apps': [], 'summary': 'لم أجد تطبيقاً بهذا الاسم في المتجر'}
    return {'status': 'ok', 'apps': apps, 'source': body.get('source'),
            'summary': 'وجدت في المتجر: ' + '، '.join(str(a['name']) for a in apps[:3])}


def _local(text, lang='ar'):
    """Mo AI's services answer "عربي | English"; keep the owner's half."""
    parts = str(text or '').split(' | ', 1)
    return parts[0] if lang != 'en' or len(parts) == 1 else parts[1]


def _tool_for_fix(url):
    """A device-plan fix is a `moos://do/<moai-do verb>` link; name the tool that runs that verb."""
    match = re.fullmatch(r'moos://do/([a-z0-9-]{1,40})', str(url or ''))
    if not match:
        return ''
    for schema in _load():
        info = schema['_moos']
        if info.get('executor') == 'moai-do' and info.get('command') == match.group(1):
            return schema['function']['name']
    return ''


# A device-plan action of these severities is a problem; anything else ('info': KVM acceleration,
# more memory, a firmware tip) is a suggestion. A healthy machine has no problems, only suggestions.
PROBLEM_SEVERITIES = ('important', 'warning')


def is_problem(action):
    return isinstance(action, dict) and action.get('severity') in PROBLEM_SEVERITIES


def plan_summary(plan, lang='ar'):
    """The device plan (GPU and driver, devices without a driver, firmware, missing apps), short.
    `problems` are important/warning actions, `suggestions` the info tips; each keeps its severity."""
    if not isinstance(plan, dict):
        return None
    actions = [a for a in (plan.get('actions') or []) if isinstance(a, dict)]

    def row(action):
        return {'severity': action.get('severity'), 'title': _local(action.get('title'), lang),
                'fix_tool': _tool_for_fix(action.get('url'))}
    return scrub_identity({
        'health': plan.get('health'),
        'driver': plan.get('driver_status' if lang == 'en' else 'driver_status_ar') or plan.get('driver_status'),
        'problems': [row(a) for a in actions if is_problem(a)][:6],
        'suggestions': [row(a) for a in actions if not is_problem(a)][:4],
        'missing_recommended_apps': [str(x) for x in (plan.get('missing_recommended_apps') or [])[:8]],
    })


# Time budgets of the read endpoints the health report chains. tools.py gives the whole report 90 s:
# /health (20) + /scan (12) + /diagnose (50; moos-selfcheck itself stops at 45) = 82 in the worst case.
HEALTH_TIMEOUT_S, SCAN_TIMEOUT_S, DIAGNOSE_TIMEOUT_S = 20, 12, 50


def selfcheck(lang='ar'):
    """MoOS's own self-check (moos-selfcheck through /diagnose): read-only, up to ~45 s."""
    body = get('/diagnose', timeout=DIAGNOSE_TIMEOUT_S)
    if not isinstance(body, dict) or body.get('error'):
        return {'status': 'error', 'error': body.get('error', 'shape') if isinstance(body, dict) else 'shape'}
    issues = [scrub_identity(_local(i, lang))[:200] for i in (body.get('issues') or [])[:8] if isinstance(i, str)]
    return {'status': 'ok', 'healthy': bool(body.get('healthy')), 'passed': body.get('ok'),
            'broken': body.get('fail'), 'issues': issues}


def health(lang='ar', deep=False):
    """The daily check, short: this MoOS, its updates, what needs attention, what uses the machine,
    and the device plan. `deep` adds MoOS's self-check (slower). Every text is scrubbed of the base."""
    code, body = _request('/health', timeout=HEALTH_TIMEOUT_S)
    report = body.get('report') if code == 200 and isinstance(body, dict) else None
    if not isinstance(report, dict):
        return {'status': 'error', 'error': body.get('error', f'http_{code}') if isinstance(body, dict) else 'shape',
                'summary': 'تعذّر قراءة الفحص اليومي', 'summary_en': 'Could not read the daily check'}
    system, updates, summary = report.get('system') or {}, report.get('updates') or {}, report.get('summary') or {}
    out = {
        'status': 'ok',
        'checked_at': report.get('generated_at'),
        'moos': {'version': system.get('version'), 'signed': system.get('signed'),
                 'kernel': clean_kernel(system.get('kernel')) or None,
                 'update_staged_for_restart': bool(summary.get('system_update_staged') or system.get('staged')),
                 'rollback_kept': system.get('rollback')},
        'updates': {'automatic_nightly_system_update': updates.get('nightly_system_update'),
                    'last_nightly_result': updates.get('last_nightly_result'),
                    # systemd says 'success' for a unit that never ran: a run happened only when this is set.
                    'last_nightly_run': updates.get('last_nightly_run') or None,
                    'app_updates_waiting': summary.get('app_updates', len(updates.get('apps') or []))},
        'attention': summary.get('status'),
        'findings': [{'severity': f.get('severity'), 'title': _local(f.get('title'), lang)}
                     for f in (report.get('findings') or [])[:8] if isinstance(f, dict)],
        'busiest': [{'name': r.get('name'), 'cpu_percent': r.get('cpu_percent'), 'memory_mb': r.get('rss_mb')}
                    for r in ((report.get('resources') or {}).get('top_cpu') or [])[:3] if isinstance(r, dict)],
    }
    scan = get('/scan', timeout=SCAN_TIMEOUT_S)
    plan = plan_summary(scan.get('device_plan'), lang) if isinstance(scan, dict) else None
    if plan is not None:
        out['device_plan'] = plan
    if deep:
        out['selfcheck'] = selfcheck(lang)
    out = scrub_identity(out)
    staged = out['moos']['update_staged_for_restart']
    version = ' '.join(str(out['moos'].get('version') or '').split())
    text = (f'MoOS {version} · ' + ('تحديث جاهز بعد إعادة التشغيل' if staged else 'لا تحديث بانتظار إعادة التشغيل') +
            f" · ملاحظات: {len(out['findings'])}")
    english = (f'MoOS {version} · ' + ('an update is ready after a restart' if staged else 'no update waiting for a restart') +
               f" · {len(out['findings'])} findings")
    if plan is not None:
        problems, suggestions = len(plan['problems']), len(plan['suggestions'])
        text += f' · خطة الجهاز: مشكلات {problems}، اقتراحات {suggestions}'
        english += f' · device plan: {problems} problems, {suggestions} suggestions'
    if deep and out['selfcheck'].get('status') == 'ok':
        broken = out['selfcheck'].get('broken') or 0
        text += f' · الفحص الذاتي: أعطال {broken}'
        english += f' · self-check: {broken} failures'
    out['summary'], out['summary_en'] = text, english
    return out


def _cpu_name(value):
    text = re.sub(r'\((?:R|TM|tm|r)\)', '', str(value or ''))
    text = re.sub(r'\s+(?:CPU\s+)?@\s*[\d.]+\s*GHz$', '', ' '.join(text.split()))
    return text[:60]


def _gpu_name(pci, fallback=''):
    """'01:00.0 VGA … [0300]: NVIDIA Corporation TU104 [GeForce RTX 2080 SUPER] [10de:1e81] (rev a1)'
    -> 'NVIDIA GeForce RTX 2080 SUPER'."""
    text = ' '.join(str(pci or '').split())
    text = re.sub(r'^\S+\s+.*?\[[0-9a-fA-F]{4}\]:\s*', '', text)
    text = re.sub(r'\s*\[[0-9a-fA-F]{4}:[0-9a-fA-F]{4}\].*$', '', text).strip()
    if not text:
        return ' '.join(str(fallback or '').split())[:60]
    lower = text.lower()
    vendor = ('NVIDIA' if 'nvidia' in lower else 'AMD' if ('amd' in lower or 'ati]' in lower) else
              'Intel' if 'intel' in lower else '')
    names = [n for n in re.findall(r'\[([^\]]+)\]', text) if n not in ('AMD/ATI',)]
    if names:
        model = names[-1].strip()
        text = model if not vendor or model.lower().startswith(vendor.lower()) else f'{vendor} {model}'
    return text[:60]


def machine_facts(timeout=6):
    """This computer in one read: MoOS version and edition, CPU, memory, disk, GPU and driver,
    Mo PC Remote, the coding agents and the device plan (moai-control /scan and /quick, read-only).
    Every kernel is a number only. {'status': 'error', ...} when moai-control cannot answer."""
    scan = get('/scan', timeout=timeout)
    if not isinstance(scan, dict) or scan.get('error'):
        return {'status': 'error', 'error': scan.get('error', 'shape') if isinstance(scan, dict) else 'shape'}
    quick = get('/quick', timeout=min(timeout, 5))
    quick = quick if isinstance(quick, dict) and not quick.get('error') else {}
    plan = scan.get('device_plan') if isinstance(scan.get('device_plan'), dict) else {}
    remote = quick.get('remote') if isinstance(quick.get('remote'), dict) else scan.get('remote')
    agents = quick.get('agents') if isinstance(quick.get('agents'), dict) else scan.get('agents')
    agents = agents if isinstance(agents, dict) else {}
    disk = scan.get('disk') if isinstance(scan.get('disk'), dict) else {}
    checked = (scan.get('health') or {}).get('summary') or {}
    actions = [a for a in (plan.get('actions') or []) if isinstance(a, dict)]
    return scrub_identity({
        'status': 'ok',
        'version': ' '.join(str(scan.get('version') or '').split())[:40],
        'nvidia_edition': plan.get('nvidia_image') if 'nvidia_image' in plan else None,
        'arch': str(scan.get('arch') or ''),
        'kernel': clean_kernel(scan.get('kernel')),
        'cpu': _cpu_name(scan.get('cpu')),
        'threads': scan.get('cores'),
        'ram_gb': plan.get('memory_gib') or scan.get('mem_gb'),
        'disk_free_gb': disk.get('free_gb'),
        'disk_total_gb': disk.get('total_gb'),
        'gpu': _gpu_name(plan.get('gpu'), scan.get('gpu')),
        'driver_status': plan.get('driver_status'),
        'driver_status_ar': plan.get('driver_status_ar'),
        'remote_running': bool(remote.get('active')) if isinstance(remote, dict) else None,
        'agents_installed': [label for key, label in AGENT_NAMES.items() if agents.get(key) is True],
        'agents_missing': [label for key, label in AGENT_NAMES.items() if agents.get(key) is False],
        'plan_health': plan.get('health'),
        'plan_pending': bool(scan.get('device_plan_pending')),
        'plan_problems': sum(1 for a in actions if is_problem(a)),
        'plan_important': sum(1 for a in actions if a.get('severity') == 'important'),
        'plan_suggestions': sum(1 for a in actions if not is_problem(a)),
        'missing_recommended_apps': len(plan.get('missing_recommended_apps') or []),
        'health_status': checked.get('status'),
        'health_findings': sum(int(v or 0) for k, v in (checked.get('counts') or {}).items()
                               if k in PROBLEM_SEVERITIES and isinstance(v, (int, float))),
        'update_staged': bool(checked.get('system_update_staged')),
        'app_updates': checked.get('app_updates'),
    })


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
        output = body.get('output', '')
        # An approved change's output is only ever shown to the owner (his card), so it is scrubbed here.
        # A read's output stays exact: pages parse it (app ids such as org.<base>project.* must survive),
        # and tools.py scrubs what the model reads.
        return {'status': status, 'exit_code': body.get('exit_code'),
                'output': scrub_identity(output) if confirmed else output,
                'duration_ms': body.get('duration_ms'), 'summary': ('تم: ' if status == 'ok' else 'تعذّر: ') + title(name)}
    if code == 409:
        return {'status': 'error', 'error': 'busy', 'summary': 'عملية أخرى ما زالت تعمل؛ انتظر انتهاءها'}
    return {'status': 'error', 'error': body.get('error', f'http_{code}'), 'summary': 'تعذّر: ' + title(name)}


def job(job_id):
    code, body = _request(f'/tool/job?id={job_id}', timeout=10)
    if code != 200:
        return {'status': 'error', 'error': body.get('error', f'http_{code}')}
    state = body.get('status')
    # A job is an approved change; its output reaches only the owner's card and Mira's announcement.
    return {'status': 'pending' if state == 'running' else 'ok' if state == 'ok' else 'error', 'state': state,
            'exit_code': body.get('exit_code'), 'output': scrub_identity(body.get('output', '')), 'tool': body.get('tool'),
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
