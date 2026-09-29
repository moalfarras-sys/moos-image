"""This PC — the computer Mira is running on, as one page.

Live levels (volume, mute, brightness, night light), the quick controls (radios, do not disturb,
microphone, theme, power profile, keyboard layout, screenshot, wallpaper motion, glass clarity),
the windows and desktops, what is playing, the hardware, the diagnostics and a file search.

Every value shown is a read-back: `get_system_status` through Mo AI's executor (polled every 5 s
while the page is on screen), `/scan` for the hardware, KWin for the windows, MPRIS for media, and
the desktop's own config files for motion, clarity and the night-light mode (the same places
`moos-theme` and KWin read them). A control is "done" only when that read-back shows the new
value; otherwise it says it was sent and not yet confirmed, or why it failed.

A value the executor wants the owner to approve (Wi-Fi or Bluetooth off, do not disturb on, the
microphone back on) and closing a window never run from here: they become an ActionCards card
that says what will happen.

Everything a backend writes is cleaned for the identity contract before it reaches the state:
kernels and packages lose the base's release tag and a base distribution's name never shows.
"""
import json
import os
import re
import time
from pathlib import Path

from PySide6.QtCore import QTimer, Slot

from pages.base import Page, TEST_MODE

POLL_MS = 5000
CARD_TTL = 180          # seconds an ActionCards card waits for the owner (controller.CONFIRM_TTL)
APPROVAL_S = 200        # a card lives 180 s; its job then has a little time to land
SETTLE_S = 30           # a change the desktop applies after answering (theme) settles within this

STRINGS = {
    'pcp_title': ('هذا الكمبيوتر', 'This PC'),
    'pcp_sub': ('كل شيء على جهازك في مكان واحد · كل قيمة هنا مقروءة من الجهاز نفسه',
                'Everything on this computer in one place · every value is read back from the machine'),
    'pcp_refresh': ('تحديث', 'Refresh'),
    'pcp_read_at': ('قُرئ', 'Read'),
    'pcp_reading': ('أقرأ…', 'Reading…'),
    'pcp_sample': ('بيانات مثال', 'Sample data'),
    # the executor is not answering (the banner's title follows the reason)
    'pcp_offline': ('لا أصل إلى أدوات الكمبيوتر', "Can't reach the computer's tools"),
    'pcp_offline_slow': ('أدوات الكمبيوتر بطيئة الآن', "The computer's tools are slow right now"),
    'pcp_offline_old': ('بعض القراءات تحتاج نسخة MoOS أحدث', 'Some readings need a newer MoOS'),
    'pcp_offline_other': ('تعذّرت قراءة حالة الكمبيوتر', "Couldn't read the computer's state"),
    'pcp_offline_hint': ('سأحاول مجدداً كل بضع ثوانٍ.', "I'll try again every few seconds."),
    # levels
    'pcp_levels': ('الصوت والشاشة', 'Sound and screen'),
    'pcp_volume': ('مستوى الصوت', 'Volume'),
    'pcp_mute': ('كتم الصوت', 'Mute'),
    'pcp_unmute': ('إعادة الصوت', 'Unmute'),
    'pcp_muted': ('مكتوم', 'Muted'),
    'pcp_brightness': ('السطوع', 'Brightness'),
    'pcp_no_brightness': ('لا تسمح هذه الشاشة بضبط السطوع من هنا', "This screen's brightness can't be set from here"),
    'pcp_night_light': ('الضوء الليلي', 'Night light'),
    'pcp_night_on': ('دائم', 'Always on'),
    'pcp_night_warm': ('دافئ الآن', 'Warm now'),
    'pcp_night_settings': ('إعدادات الضوء الليلي', 'Night light settings'),
    # quick controls
    'pcp_controls': ('التحكم السريع', 'Quick controls'),
    'pcp_wifi': ('واي فاي', 'Wi-Fi'),
    'pcp_bluetooth': ('بلوتوث', 'Bluetooth'),
    'pcp_dnd': ('عدم الإزعاج', 'Do not disturb'),
    'pcp_mic': ('الميكروفون', 'Microphone'),
    'pcp_keyboard': ('لغة الكتابة', 'Keyboard layout'),
    'pcp_keyboard_next': ('بدّل إلى اللغة التالية', 'Switch to the next layout'),
    'pcp_screenshot': ('لقطة شاشة', 'Screenshot'),
    'pcp_screenshot_sub': ('تُحفظ في الصور', 'Saved to Pictures'),
    'pcp_networks': ('الشبكات', 'Networks'),
    'pcp_networks_sub': ('اختر شبكة', 'Choose a network'),
    'pcp_settings': ('الإعدادات', 'Settings'),
    'pcp_settings_sub': ('كل إعدادات MoOS', 'All of MoOS Settings'),
    'pcp_sound_settings': ('إعدادات الصوت', 'Sound settings'),
    'pcp_display_settings': ('إعدادات الشاشة', 'Display settings'),
    'pcp_window_settings': ('سلوك النوافذ', 'Window behaviour'),
    'pcp_about': ('عن هذا الكمبيوتر', 'About this computer'),
    'pcp_on': ('يعمل', 'On'),
    'pcp_off': ('متوقف', 'Off'),
    'pcp_mic_live': ('يسمع', 'Listening'),
    'pcp_mic_muted': ('مكتوم', 'Muted'),
    'pcp_unknown': ('غير متاح هنا', 'Not available here'),
    'pcp_no_reading': ('لا قراءة الآن', 'No reading right now'),
    'pcp_waiting': ('بانتظار موافقتك', 'Waiting for your approval'),
    'pcp_card_open': ('البطاقة ما زالت أمامك: وافق عليها أو ارفضها هناك', 'The card is still waiting: approve or reject it there'),
    'pcp_card_closed': ('أُغلقت البطاقة ولا تُظهر القراءة أي تغيير (رُفضت أو انتهت مهلتها أو تعذّرت)',
                        "The card closed and the reading shows no change (rejected, expired or failed)"),
    'pcp_card_rejected': ('لم يتغيّر شيء: لم توافق على البطاقة', "Nothing changed: the card wasn't approved"),
    'pcp_card_expired': ('انتهت مهلة البطاقة ولم يتغيّر شيء', 'The card expired and nothing changed'),
    'pcp_applying': ('يُطبَّق…', 'Applying…'),
    'pcp_needs_ok': ('يحتاج موافقتك', 'Needs your approval'),
    'pcp_theme': ('المظهر', 'Appearance'),
    'pcp_dark': ('داكن', 'Dark'),
    'pcp_light': ('فاتح', 'Light'),
    'pcp_auto': ('تلقائي', 'Automatic'),
    'pcp_power': ('وضع الطاقة', 'Power mode'),
    'pcp_saver': ('توفير', 'Saver'),
    'pcp_balanced': ('متوازن', 'Balanced'),
    'pcp_performance': ('أداء', 'Performance'),
    'pcp_motion': ('حركة الخلفية', 'Wallpaper motion'),
    'pcp_still': ('ثابتة', 'Still'),
    'pcp_gentle': ('هادئة', 'Gentle'),
    'pcp_alive': ('حيّة', 'Alive'),
    'pcp_clarity': ('شفافية الزجاج', 'Glass clarity'),
    'pcp_clear': ('شفاف', 'Clear'),
    'pcp_solid': ('معتم', 'Solid'),
    'pcp_now': ('الحالي', 'Now'),
    # windows
    'pcp_windows': ('النوافذ وأسطح المكتب', 'Windows and desktops'),
    'pcp_overview': ('نظرة عامة', 'Overview'),
    'pcp_grid': ('كل الأسطح', 'All desktops'),
    'pcp_show_desktop': ('إظهار سطح المكتب', 'Show desktop'),
    'pcp_arrange': ('ترتيب', 'Arrange'),
    'pcp_halves': ('نصفان', 'Halves'),
    'pcp_thirds': ('أثلاث', 'Thirds'),
    'pcp_quarters': ('أرباع', 'Quarters'),
    'pcp_view': ('العرض', 'View'),
    'pcp_desktops': ('أسطح المكتب', 'Desktops'),
    'pcp_desktop_prev': ('السطح السابق', 'Previous desktop'),
    'pcp_desktop_next': ('السطح التالي', 'Next desktop'),
    'pcp_open_windows': ('النوافذ المفتوحة', 'Open windows'),
    'pcp_no_windows': ('لا توجد نوافذ مفتوحة', 'No open windows'),
    'pcp_focus': ('انتقل إليها', 'Focus'),
    'pcp_close': ('إغلاق', 'Close'),
    'pcp_active': ('الحالية', 'Active'),
    'pcp_minimized': ('مصغّرة', 'Minimised'),
    'pcp_same_title': ('عنوانها يشبه نافذة أخرى؛ اخترها من النظرة العامة',
                       'Its title matches another window; pick it in the Overview'),
    # media
    'pcp_media': ('يُشغَّل الآن', 'Now playing'),
    'pcp_no_media': ('لا يوجد مشغّل وسائط يعمل الآن', 'No media player is running'),
    'pcp_playing': ('قيد التشغيل', 'Playing'),
    'pcp_paused': ('متوقف مؤقتاً', 'Paused'),
    'pcp_stopped': ('متوقف', 'Stopped'),
    'pcp_play': ('تشغيل', 'Play'),
    'pcp_pause': ('إيقاف مؤقت', 'Pause'),
    'pcp_next': ('التالي', 'Next'),
    'pcp_previous': ('السابق', 'Previous'),
    'pcp_untitled': ('بلا عنوان', 'Untitled'),
    # hardware
    'pcp_hardware': ('العتاد', 'Hardware'),
    'pcp_cpu': ('المعالج', 'Processor'),
    'pcp_cores': ('نوى منطقية', 'Logical cores'),
    'pcp_memory': ('الذاكرة', 'Memory'),
    'pcp_gpu': ('كرت الشاشة', 'Graphics'),
    'pcp_driver': ('التعريف', 'Driver'),
    'pcp_disk': ('التخزين', 'Storage'),
    'pcp_free_of': ('متاح من', 'free of'),
    'pcp_kernel': ('النواة', 'Kernel'),
    'pcp_version': ('إصدار MoOS', 'MoOS version'),
    'pcp_b': ('ب', 'B'),
    'pcp_kb': ('ك.ب', 'KB'),
    'pcp_mb': ('م.ب', 'MB'),
    'pcp_gb': ('غ.ب', 'GB'),
    'pcp_no_hardware': ('تعذّرت قراءة العتاد', "Couldn't read the hardware"),
    # diagnostics
    'pcp_diag': ('الفحص والسجلات', 'Checks and logs'),
    'pcp_diag_sub': ('قراءة فقط · لا شيء هنا يغيّر الجهاز', 'Read only · nothing here changes the computer'),
    'pcp_proc_cpu': ('الأكثر استهلاكاً للمعالج', 'Top by processor'),
    'pcp_proc_mem': ('الأكثر استهلاكاً للذاكرة', 'Top by memory'),
    'pcp_mem': ('الذاكرة والضغط', 'Memory and pressure'),
    'pcp_disks': ('مساحة الأقراص', 'Disk space'),
    'pcp_net': ('حالة الشبكة', 'Network state'),
    'pcp_failed': ('الخدمات المتعطّلة', 'Failed services'),
    'pcp_diag_empty': ('اختر فحصاً لتظهر نتيجته الحقيقية هنا', 'Pick a check to see its real output here'),
    'pcp_unit': ('حالة خدمة', 'Service status'),
    'pcp_unit_hint': ('اسم الخدمة، مثل pipewire أو NetworkManager', 'Service name, e.g. pipewire or NetworkManager'),
    'pcp_unit_user': ('خدمة المستخدم', 'User service'),
    'pcp_unit_bad': ('اسم خدمة غير صالح', 'Not a valid service name'),
    'pcp_show': ('اعرض', 'Show'),
    'pcp_journal': ('سجل النظام', 'System journal'),
    'pcp_journal_unit': ('خدمة (اختياري)', 'Service (optional)'),
    'pcp_severity': ('الشدة', 'Severity'),
    'pcp_since': ('المدة', 'Period'),
    'pcp_prio_err': ('أخطاء', 'Errors'),
    'pcp_prio_warning': ('تحذيرات', 'Warnings'),
    'pcp_prio_info': ('الكل', 'All'),
    'pcp_since_boot': ('منذ الإقلاع', 'This boot'),
    'pcp_since_1h': ('آخر ساعة', 'Last hour'),
    'pcp_since_24h': ('آخر 24 ساعة', 'Last 24 hours'),
    'pcp_since_7d': ('آخر أسبوع', 'Last week'),
    'pcp_read': ('اقرأ', 'Read'),
    'pcp_logs': ('سجلات MoOS', 'MoOS logs'),
    'pcp_log_moai': ('Mo AI', 'Mo AI'),
    'pcp_log_theme': ('المظهر', 'Theme'),
    'pcp_log_store': ('المتجر', 'Store'),
    'pcp_log_remote': ('التحكم عن بعد', 'Remote'),
    # files
    'pcp_files': ('الملفات', 'Files'),
    'pcp_files_hint': ('ابحث في ملفاتك بالاسم…', 'Search your files by name…'),
    'pcp_search': ('بحث', 'Search'),
    'pcp_open': ('فتح', 'Open'),
    'pcp_open_folder': ('المجلد', 'Folder'),
    'pcp_no_files': ('لا ملفات تطابق البحث', 'No files match'),
    'pcp_files_empty': ('ابحث عن مستند أو صورة أو مجلد داخل مجلدك', 'Find a document, picture or folder in your home'),
    'pcp_folder': ('مجلد', 'Folder'),
    'pcp_working': ('يعمل…', 'Working…'),
}

# ── fixed choices (the executor's own enums) ─────────────────────────────
TOGGLE_TOOLS = {'wifi': 'toggle_wifi', 'bluetooth': 'toggle_bluetooth', 'dnd': 'set_do_not_disturb',
                'mic': 'set_mic_mute'}
THEMES = ('dark', 'light', 'auto')
POWER = ('power-saver', 'balanced', 'performance')
MOTION = ('still', 'gentle', 'alive')
CLARITY = ('clear', 'balanced', 'solid')
NIGHT = ('off', 'on', 'auto')
VIEWS = ('overview', 'grid', 'show-desktop')
LAYOUTS = ('halves', 'thirds', 'quarters', 'main', 'centre')
DIRECTIONS = ('next', 'previous')
MEDIA = ('play', 'pause', 'toggle', 'next', 'previous')
CHECKS = {'top_processes:cpu': ('top_processes', {'by': 'cpu'}),
          'top_processes:memory': ('top_processes', {'by': 'memory'}),
          'memory_status': ('memory_status', {}), 'disk_status': ('disk_status', {}),
          'network_status': ('network_status', {}), 'list_failed_units': ('list_failed_units', {})}
LOGS = ('moai', 'theme', 'store', 'remote')
PRIORITIES = ('err', 'warning', 'info')
SINCE = ('boot', '1h', '24h', '7d')
UNIT = re.compile(r'[A-Za-z0-9@._:\-]{1,120}\.(service|timer|socket|path|target|mount|slice|scope)')
UNIT_SUFFIXES = ('.service', '.timer', '.socket', '.path', '.target', '.mount', '.slice', '.scope')
WINDOW_ID = re.compile(r'[A-Za-z0-9{}\-]{1,64}')        # KWin's internalId (a UUID in braces)
MOTION_BY_MODE = {'0': 'still', '1': 'gentle', '2': 'alive'}
SETTINGS_PAGE = re.compile(r'[a-z][a-z-]{1,39}')     # the executor checks it against the registry's pages
SETTINGS_GROUP = {'audio': 'levels', 'display': 'levels', 'night-light': 'levels', 'window-behavior': 'windows',
                  'desktops': 'windows', 'about': 'hardware', 'storage': 'hardware'}
LOOK_KEYS = ('motion', 'clarity', 'night')             # read from config files, not get_system_status
NO_READBACK = ('switch_keyboard_layout', 'show_windows', 'arrange_windows', 'switch_desktop', 'open_settings',
               'take_screenshot')
LEVELS = ('volume', 'brightness')                     # a newer value waits for the running one, never dropped

# Reasons, in both languages, for the failures the backends name.
WHY = {
    'moai_control_unreachable': ('خدمة Mo AI التنفيذية لا تجيب', "Mo AI's executor is not answering"),
    'busy': ('عملية أخرى ما زالت تعمل؛ انتظر انتهاءها', 'Another action is still running; wait for it to end'),
    'no_session': ('لا توجد جلسة سطح مكتب', 'No desktop session'),
    'no_kwin': ('مدير النوافذ لا يجيب', 'The window manager is not answering'),
    'kwin_failed': ('تعذّرت قراءة النوافذ من مدير النوافذ', "Couldn't read the windows from the window manager"),
    'action_failed': ('رفض مدير النوافذ الطلب', 'The window manager refused'),
    'no_player': ('لا يوجد مشغّل وسائط يعمل الآن', 'No media player is running'),
    'bad_player': ('هذا المشغّل لم يعد موجوداً', 'That player is no longer there'),
    'bad_action': ('هذا الإجراء غير مدعوم', 'That action is not supported'),
    'ambiguous': ('أكثر من نافذة أو مشغّل يطابق؛ لم أفعل شيئاً', 'More than one match; nothing was done'),
    'same_title': ('نافذة أخرى تحمل عنواناً مشابهاً؛ اخترها من النظرة العامة',
                   'Another window has a matching title; pick it in the Overview'),
    'no_match': ('لم تعد هذه النافذة مفتوحة', 'That window is no longer open'),
    'caption_changed': ('تغيّر عنوان النافذة منذ عرضها؛ لم أفعل شيئاً', "The window's title changed since it was listed; nothing was done"),
    'bad_window': ('هذه النافذة لم تعد في القائمة', 'That window is no longer in the list'),
    'not_found': ('الملف غير موجود', 'The file does not exist'),
    'empty_path': ('لم يُحدَّد ملف', 'No file was given'),
    'outside_home': ('يُسمح فقط بالملفات داخل مجلدك', 'Only files inside your home can be opened'),
    'executable': ('هذا ملف يشغّل برنامجاً؛ افتحه بنفسك إن أردت', 'That file runs a program; open it yourself if you mean to'),
    'empty_query': ('اكتب ما تبحث عنه', 'Type what to look for'),
    'unknown_file': ('هذا الملف ليس من نتائج البحث', 'That file is not in the search results'),
    'unsupported': ('غير مدعوم على هذا الكمبيوتر', 'Not supported on this computer'),
    'no_card': ('تعذّر وضع الطلب أمامك للموافقة', "Couldn't put the request in front of you"),
    'shape': ('ردّ غير متوقع من الجهاز', 'Unexpected reply from the computer'),
    'timeout': ('لم تُجب الأداة في الوقت المحدد', 'The tool took too long to answer'),
    'missing': ('نسخة MoOS هذه لا تعرف هذه الأداة بعد', "This MoOS version doesn't have this tool yet"),
    'invalid': ('رفضت الأداة هذه القيمة', 'The tool refused this value'),
    'failed': ('تعذّر تشغيل الأداة', "The tool couldn't run"),
    'generic': ('تعذّر التنفيذ', "Couldn't do it"),
}

# What an approval card asks for, in words (never the executor's raw enum).
ACTIONS = {
    ('toggle_wifi', 'off'): ('إيقاف الواي فاي', 'Turn Wi-Fi off'),
    ('toggle_wifi', 'on'): ('تشغيل الواي فاي', 'Turn Wi-Fi on'),
    ('toggle_bluetooth', 'off'): ('إيقاف البلوتوث', 'Turn Bluetooth off'),
    ('toggle_bluetooth', 'on'): ('تشغيل البلوتوث', 'Turn Bluetooth on'),
    ('set_do_not_disturb', 'on'): ('تشغيل عدم الإزعاج', 'Turn on Do not disturb'),
    ('set_do_not_disturb', 'off'): ('إيقاف عدم الإزعاج', 'Turn off Do not disturb'),
    ('set_mic_mute', 'unmute'): ('إعادة تشغيل الميكروفون', 'Turn the microphone back on'),
    ('set_mic_mute', 'mute'): ('كتم الميكروفون', 'Mute the microphone'),
    ('set_mute', 'mute'): ('كتم الصوت', 'Mute the sound'),
    ('set_mute', 'unmute'): ('إعادة الصوت', 'Unmute the sound'),
    ('toggle_night_light', 'on'): ('تشغيل الضوء الليلي دائماً', 'Keep the night light on'),
    ('toggle_night_light', 'off'): ('إيقاف الضوء الليلي', 'Turn the night light off'),
    ('toggle_night_light', 'auto'): ('الضوء الليلي حسب الوقت', 'Night light on its schedule'),
}
VALUE_WORDS = {'dark': 'pcp_dark', 'light': 'pcp_light', 'auto': 'pcp_auto', 'power-saver': 'pcp_saver',
               'balanced': 'pcp_balanced', 'performance': 'pcp_performance', 'still': 'pcp_still',
               'gentle': 'pcp_gentle', 'alive': 'pcp_alive', 'clear': 'pcp_clear', 'solid': 'pcp_solid',
               'on': 'pcp_on', 'off': 'pcp_off'}

# ── identity: what the owner reads says MoOS ─────────────────────────────
# A package or kernel release carries the base's build tag (7.2.7-200.<tag>.x86_64), and a journal
# or a compiler string can name the base distribution. Neither may reach the screen (AGENTS.md).
# The names live in ONE place, moai_tools (clean_identity, built on scrub_identity), so every page
# and every model-facing text says it the same way.
_DIST_TAG = re.compile(r'(?<=\d)\.(?:fc|el)\d+(?:_\d+)*(?:\.(?:x86_64|aarch64|noarch|i686|ppc64le|s390x))?(?![\w])')


def clean(text):
    """Backend text as the owner may read it: no base release tag, no base distribution's name."""
    import moai_tools
    shared = getattr(moai_tools, 'clean_identity', None)
    if callable(shared):
        return shared(text)
    # An older moai_tools without clean_identity: its scrub_identity knows the names; the release
    # tag's architecture tail is removed here first.
    return moai_tools.scrub_identity(_DIST_TAG.sub('', '' if text is None else str(text)))


def _code(result):
    """The reason a backend gave, as one WHY key ('' when it is none of them)."""
    code = str(result.get('error') or '')
    if code in WHY:
        return code
    low = code.lower()
    if low.startswith('tool execution timed out') or low in ('http_504', 'timeout', 'timeouterror'):
        return 'timeout'
    if low.startswith('unknown tool') or low == 'http_404':
        return 'missing'
    if low.startswith('invalid arguments') or low == 'http_400':
        return 'invalid'
    if low.startswith('execution failed') or low == 'http_500':
        return 'failed'
    return ''


def _why(result, lang):
    """One short sentence saying why something did not happen, in the owner's language."""
    en = lang == 'en'
    if not isinstance(result, dict):
        return WHY['shape'][en]
    code = _code(result)
    if code:
        return WHY[code][en]
    text = str(result.get('output') or '').strip()
    if text:
        line = text.splitlines()[-1].strip()
        line = re.sub(r'^(moos-control|moos-inspect|moai-do):\s*', '', line)
        line = clean(_half(line, lang)).strip()
        if line:
            return line[:240]
    if result.get('exit_code') not in (None, 0):
        return WHY['failed'][en]
    return WHY['generic'][en]


def status_code(result):
    """Why get_system_status could not be read: unreachable | timeout | missing | other."""
    code = _code(result) if isinstance(result, dict) else ''
    return {'moai_control_unreachable': 'unreachable', 'timeout': 'timeout', 'missing': 'missing'}.get(code, 'other')


def _half(text, lang):
    """MoOS's services answer "عربي | English" (sometimes after an emoji); keep the owner's half."""
    text = str(text or '').strip()
    parts = text.split(' | ', 1)
    if len(parts) == 1:
        return text
    return parts[1].strip() if lang == 'en' else parts[0].strip()


def parse_status(result):
    """get_system_status → {volume, muted, brightness, night_light, wifi, bluetooth, theme, dnd,
    mic_muted, power_profile}; None for any value this machine cannot tell. None when unreadable."""
    if not isinstance(result, dict) or result.get('status') != 'ok':
        return None
    try:
        raw = json.loads(result.get('output') or '')
    except (TypeError, ValueError):
        return None
    if not isinstance(raw, dict):
        return None
    out = {}
    for key in ('volume', 'brightness'):
        value = raw.get(key)
        out[key] = round(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None
    for key in ('muted', 'night_light', 'wifi', 'bluetooth', 'dnd', 'mic_muted'):
        value = raw.get(key)
        out[key] = value if isinstance(value, bool) else None
    for key in ('theme', 'power_profile'):
        value = raw.get(key)
        out[key] = value if isinstance(value, str) and value else None
    return out


def theme_family(theme):
    """A MoOS look's read-back name → dark | light | auto (None when unknown)."""
    if not theme:
        return None
    if theme == 'auto':
        return 'auto'
    if theme in ('light', 'daylight') or theme.endswith('-light'):
        return 'light'
    return 'dark'


def toggle_on(status, key):
    """Is this quick control on, from the read-back? None when the machine cannot tell."""
    if not status:
        return None
    if key == 'mic':
        muted = status.get('mic_muted')
        return None if muted is None else not muted
    value = status.get(key)
    return value if isinstance(value, bool) else None


SYSTEM_CONFIG = Path('/etc/xdg')      # the system-wide KDE defaults under the user's own config


def _config_home():
    return Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config')


def _ini_value(text, group, key):
    """The last `key=` inside `[group]` of a KDE config text ('' when absent)."""
    current, value = '', ''
    for line in text.splitlines():
        line = line.strip()
        if line.startswith('['):
            current = line
        elif current == group and line.startswith(key + '='):
            value = line.split('=', 1)[1].strip()
    return value


def read_night(config=None, system=None):
    """The night-light MODE as KWin reads it (kwinrc [NightColor]): off | on (Constant) | auto (any
    schedule). The user's file wins over the system default, and Active defaults to false."""
    config = Path(config) if config else _config_home()
    system = Path(system) if system else SYSTEM_CONFIG
    active, mode = '', ''
    for folder in (Path(system), config):          # later wins, as KConfig cascades
        try:
            text = (folder / 'kwinrc').read_text(encoding='utf-8', errors='replace')
        except OSError:
            continue
        active = _ini_value(text, '[NightColor]', 'Active') or active
        mode = _ini_value(text, '[NightColor]', 'Mode') or mode
    if active.lower() not in ('true', '1'):
        return 'off'
    return 'on' if mode == 'Constant' else 'auto'


def read_look(config=None):
    """Wallpaper motion, glass clarity and the night-light mode, read where they are applied from:
    the MoOS wallpaper's MotionMode in Plasma's desktop config (every MoOS desktop must agree),
    moos-appearancerc's [Material] Clarity (unset means clear) and kwinrc's [NightColor].
    None for what cannot be told."""
    config = Path(config) if config else _config_home()
    look = {'motion': None, 'clarity': None, 'night': None}
    try:
        text = (config / 'moos-appearancerc').read_text(encoding='utf-8', errors='replace')
        value = _ini_value(text, '[Material]', 'Clarity')
        look['clarity'] = value if value in CLARITY else ('clear' if value == '' else None)
    except OSError:
        look['clarity'] = None
    try:
        look['night'] = read_night(config)
    except OSError:
        look['night'] = None
    try:
        text = (config / 'plasma-org.kde.plasma.desktop-appletsrc').read_text(encoding='utf-8', errors='replace')
    except OSError:
        return look
    plugins, modes, section = {}, {}, None
    for line in text.splitlines():
        line = line.strip()
        head = re.fullmatch(r'\[Containments\]\[(\d+)\](.*)', line)
        if head:
            section = (head.group(1), head.group(2))
            continue
        if line.startswith('['):
            section = None
            continue
        if section is None or '=' not in line:
            continue
        key, value = line.split('=', 1)
        if section[1] == '' and key == 'wallpaperplugin':
            plugins[section[0]] = value.strip()
        elif section[1] == '[Wallpaper][org.moos.ui2.wallpaper][General]' and key == 'MotionMode':
            modes[section[0]] = value.strip()
    seen = {modes.get(cid, '1') for cid, plugin in plugins.items() if plugin == 'org.moos.ui2.wallpaper'}
    if len(seen) == 1:
        look['motion'] = MOTION_BY_MODE.get(seen.pop())
    return look


def _gpu(scan, plan):
    """The graphics card as a person names it (Mo AI's own reading of /scan's device plan)."""
    import moai_tools
    name = moai_tools._gpu_name(plan.get('gpu'), scan.get('gpu'))
    name = re.sub(r'\b(?:Corporation|Corp\.|Inc\.|Advanced Micro Devices,?)\s*', '', str(name or ''))
    return clean(' '.join(name.split()).strip(' ,'))


def hardware_from_scan(scan):
    """/scan → the hardware facts the page shows (only what /scan reports), in both languages where
    /scan words them, so a language switch never shows a stale one."""
    import moai_tools
    if not isinstance(scan, dict) or scan.get('error'):
        return None
    plan = scan.get('device_plan') if isinstance(scan.get('device_plan'), dict) else {}
    disk = scan.get('disk') if isinstance(scan.get('disk'), dict) else {}
    memory = plan.get('memory_gib') or scan.get('mem_gb')
    driver_en = clean(plan.get('driver_status') or '')
    return {
        'cpu': clean(moai_tools._cpu_name(scan.get('cpu'))),
        'cores': int(scan['cores']) if isinstance(scan.get('cores'), int) else None,
        'memory_gb': memory if isinstance(memory, (int, float)) and memory > 0 else None,
        'gpu': _gpu(scan, plan),
        'driver_en': driver_en,
        'driver_ar': clean(plan.get('driver_status_ar') or '') or driver_en,
        'disk_total_gb': disk.get('total_gb') if isinstance(disk.get('total_gb'), (int, float)) else None,
        'disk_free_gb': disk.get('free_gb') if isinstance(disk.get('free_gb'), (int, float)) else None,
        'kernel': moai_tools.clean_kernel(scan.get('kernel')),
        'version': clean(' '.join(str(scan.get('version') or '').split())[:40]),
        'arch': str(scan.get('arch') or ''),
    }


def mark_ambiguous(rows):
    """desktop_tools finds a window by its title as a substring of every window's caption and class:
    a row whose title is also inside another row cannot be told apart by title."""
    for row in rows:
        needle = ' '.join(row['title'].split()).lower()
        row['unique'] = bool(needle) and not any(
            needle in (other['title'] + ' ' + other['app']).lower() for other in rows if other is not row)
    return rows


def _desktop(name):
    import desktop_tools
    fn = getattr(desktop_tools, name, None)
    return fn if callable(fn) else None


class PcPage(Page):
    def __init__(self, host, parent=None):
        super().__init__(host, parent)
        self._timer = QTimer(self)
        self._timer.setInterval(POLL_MS)
        self._timer.timeout.connect(self._poll)
        self._reading = False
        self._ticks = 0
        self._stamp = 0.0        # when the status now shown was read (a slower, older read never replaces it)
        self._expect = {}        # key -> {'want', 'until', 'why': 'approval' | 'settle', 'card', 'since'}
        self._queued = {}        # level key -> (tool, args, want) the owner asked for while one was running
        self._cards = {}         # card id -> control key ('close:<window id>' for a window)
        self._files = set()      # paths the last search returned: the only ones this page opens
        self._files_seq = 0
        self._windows_seq = 0
        self._raw = {}           # the last failing backend answer per field, to say it again in another language
        changed = getattr(host, 'langChanged', None)
        if changed is not None:
            changed.connect(self._relocalize)

    def initial(self):
        return {
            'status': {}, 'statusState': 'idle', 'statusError': '', 'statusCode': '', 'readAt': '',
            'look': {'motion': None, 'clarity': None, 'night': None},
            'busy': {},          # control key -> True while it runs
            'wanted': {},        # level key -> the value on its way (running or queued)
            'awaiting': {},      # control key -> 'approval' | 'settle'
            'notes': {},         # group -> {'status': ok|pending|error|info, 'text': str}
            'windows': [], 'windowsState': 'idle', 'windowsError': '',
            'media': {}, 'mediaState': 'idle',
            'hardware': {}, 'hardwareState': 'idle',
            'outputs': {},       # diagnostics slot (checks|unit|journal|logs) -> {'tool', 'status', 'text'}
            'running': {},       # diagnostics slot -> the check running there
            'files': [], 'filesState': 'idle', 'filesQuery': '', 'filesError': '',
            'layout': '',        # the keyboard layout the last switch read back
            'sample': False,
        }

    # ── lifecycle ────────────────────────────────────────────────────
    def activated(self):
        if TEST_MODE:
            return
        self.refresh()
        self._timer.start()

    @Slot()
    def hidden(self):
        """The page left the screen (another page, or the window was hidden): stop polling."""
        self._timer.stop()

    @Slot()
    def resume(self):
        """The window came back while this page is showing: read now and poll again."""
        if TEST_MODE:
            return
        if not self._timer.isActive():
            self._timer.start()
            self._poll()

    @Slot()
    def refresh(self):
        self.refreshStatus()
        self.refreshWindows()
        self.refreshMedia()
        self.refreshHardware()

    def _poll(self):
        self._ticks += 1
        self.refreshStatus()
        if self._ticks % 3 == 0:      # what plays and which windows are open change on their own
            self.refreshMedia()
            self.refreshWindows()

    # ── read-backs ───────────────────────────────────────────────────
    @Slot()
    def refreshStatus(self):
        if self._reading:
            return
        self._reading = True
        if not self._state['status']:
            self.update(statusState='loading')
        self.run('status', self._read_status)

    @staticmethod
    def _read_status():
        import moai_tools
        stamp = time.monotonic()
        result = moai_tools.execute('get_system_status', {})
        return {'result': result, 'read': parse_status(result), 'look': read_look(), 'stamp': stamp}

    def on_status(self, tag, result):
        self._reading = False
        stamp = result.get('stamp', 0.0) if isinstance(result, dict) else 0.0
        if stamp and stamp < self._stamp:
            return      # a control's read-back landed while this older read was on its way
        status = result.get('read') if isinstance(result, dict) else None
        look = result.get('look') if isinstance(result, dict) else None
        fields = {}
        if look:
            fields['look'] = look
        if status is None:
            raw = result.get('result', result) if isinstance(result, dict) else result
            self._raw['status'] = raw
            fields.update(statusState='error', statusError=_why(raw, self.lang), statusCode=status_code(raw))
            self.update(**fields)
            return
        self._stamp = max(self._stamp, stamp)
        self._raw.pop('status', None)
        fields.update(status=status, statusState='ok', statusError='', statusCode='', readAt=time.strftime('%H:%M:%S'))
        self.update(**fields)
        self._settle()

    def _matches(self, key, want, status=None, look=None):
        status = self._state['status'] if status is None else status
        look = self._state['look'] if look is None else look
        if key in TOGGLE_TOOLS:
            return toggle_on(status, key) == want
        if key == 'volume':
            return status.get('volume') == want
        if key == 'mute':
            return status.get('muted') == want
        if key == 'brightness':
            return isinstance(status.get('brightness'), int) and abs(status['brightness'] - want) <= 1
        if key == 'theme':
            return theme_family(status.get('theme')) == want
        if key == 'power':
            return status.get('power_profile') == want
        if key in LOOK_KEYS:
            return look.get(key) == want
        return False

    def _settle(self):
        """Clear the waits the read-back now answers (or that ran out of time)."""
        if not self._expect:
            return
        now = time.monotonic()
        notes = dict(self._state['notes'])
        for key, wait in list(self._expect.items()):
            if wait['why'] == 'close':          # a close card: only its own answer (action_update) speaks
                if now > wait['until']:
                    del self._expect[key]
                continue
            if self._matches(key, wait['want']):
                del self._expect[key]
                notes[self._group(key)] = {'status': 'ok', 'text': self._done_text(key, wait['want'])}
            elif wait['why'] == 'approval' and not self._card_live(wait) and now <= wait['until']:
                # the card left the owner's view (approved, rejected or expired): watch the read-back a while
                wait.update(why='settle', until=min(wait['until'], now + SETTLE_S), card_closed=True)
            elif now > wait['until']:
                del self._expect[key]
                if wait['why'] == 'settle' and not wait.get('card_closed'):
                    notes[self._group(key)] = {'status': 'pending', 'text': self._not_seen_text(key)}
                else:
                    notes[self._group(key)] = {'status': 'info', 'text': self.text('pcp_card_closed')}
        self.update(awaiting=self._awaiting(), notes=notes)

    def _awaiting(self):
        """control key -> 'approval' | 'settle', for the tiles (a window's close card is not a control)."""
        return {k: w['why'] for k, w in self._expect.items() if w['why'] != 'close'}

    # ── levels ───────────────────────────────────────────────────────
    @Slot(int)
    def setVolume(self, value):
        value = max(0, min(100, int(value)))
        self._control('volume', 'set_volume', {'value': str(value)}, value)

    @Slot()
    def toggleMute(self):
        muted = self._state['status'].get('muted')
        if muted is None:
            return
        self._control('mute', 'set_mute', {'value': 'unmute' if muted else 'mute'}, not muted)

    @Slot(int)
    def setBrightness(self, value):
        value = max(5, min(100, int(value)))
        self._control('brightness', 'set_brightness', {'value': str(value)}, value)

    @Slot(str)
    def setNightLight(self, mode):
        """off, on (warm all the time) or auto (Plasma's own day/night schedule)."""
        if mode in NIGHT:
            self._control('night', 'toggle_night_light', {'value': mode}, mode)

    # ── quick controls ───────────────────────────────────────────────
    @Slot(str, bool)
    def setToggle(self, key, on):
        if key not in TOGGLE_TOOLS:
            return
        if key == 'mic':
            args = {'value': 'unmute' if on else 'mute'}
        else:
            args = {'value': 'on' if on else 'off'}
        self._control(key, TOGGLE_TOOLS[key], args, bool(on))

    @Slot(str)
    def setTheme(self, mode):
        if mode in THEMES:
            self._control('theme', 'set_theme_mode', {'value': mode}, mode)

    @Slot(str)
    def setPowerProfile(self, profile):
        if profile in POWER:
            self._control('power', 'set_power_profile', {'profile': profile}, profile)

    @Slot(str)
    def setMotion(self, level):
        if level in MOTION:
            self._control('motion', 'set_motion', {'level': level}, level)

    @Slot(str)
    def setClarity(self, level):
        if level in CLARITY:
            self._control('clarity', 'set_glass_clarity', {'level': level}, level)

    @Slot()
    def nextKeyboardLayout(self):
        self._control('keyboard', 'switch_keyboard_layout', {}, None)

    @Slot()
    def screenshot(self):
        self._control('screenshot', 'take_screenshot', {}, None)

    @Slot(str)
    def openSettings(self, page):
        """One page of MoOS Settings (display, audio, window behaviour, about …), opened by Mo AI's
        executor, which answers only after the page opened."""
        if SETTINGS_PAGE.fullmatch(page or ''):
            self._control('settings:' + page, 'open_settings', {'page': page}, None)

    # ── windows and desktops ─────────────────────────────────────────
    @Slot(str)
    def showWindows(self, view):
        if view in VIEWS:
            self._control('view:' + view, 'show_windows', {'view': view}, None)

    @Slot(str)
    def arrange(self, layout):
        if layout in LAYOUTS:
            self._control('arrange:' + layout, 'arrange_windows', {'layout': layout}, None)

    @Slot(str)
    def switchDesktop(self, direction):
        if direction in DIRECTIONS:
            self._control('desktop:' + direction, 'switch_desktop', {'direction': direction}, None)

    @Slot()
    def refreshWindows(self):
        if self._state['windowsState'] != 'ok':
            self.update(windowsState='loading')
        import desktop_tools
        self._windows_seq += 1
        self.run(f'windows:{self._windows_seq}', desktop_tools.list_windows)

    def on_windows(self, tag, result):
        if tag != f'windows:{self._windows_seq}':
            return      # an older read (the tick, a refresh after focus) landed after a newer one
        if isinstance(result, dict) and result.get('status') == 'ok':
            rows = [{'id': str(w.get('id', '')), 'title': ' '.join(str(w.get('title') or '').split()),
                     'app': str(w.get('app') or ''), 'active': bool(w.get('active')),
                     'minimized': bool(w.get('minimized'))}
                    for w in (result.get('windows') or []) if isinstance(w, dict) and w.get('title')]
            mark_ambiguous(rows)
            by_id = {'focus': bool(_desktop('focus_window_id')), 'close': bool(_desktop('close_window_id'))}
            for row in rows:
                ok_id = bool(WINDOW_ID.fullmatch(row['id']))
                row['canFocus'] = (by_id['focus'] and ok_id) or row['unique']
                row['canClose'] = (by_id['close'] and ok_id) or row['unique']
            self._raw.pop('windows', None)
            self.update(windows=rows, windowsState='ok', windowsError='')
        else:
            self._raw['windows'] = result
            self.update(windows=[], windowsState='error', windowsError=_why(result, self.lang))

    def _window(self, wid):
        return next((w for w in self._state['windows'] if w['id'] == wid), None)

    @Slot(str, str)
    def focusWindow(self, wid, title):
        """Raise one window of the list: by KWin's own id when desktop_tools can, else by a title no
        other window shares (a shared title would reach the wrong window, or none)."""
        row = self._window(str(wid or ''))
        if row is None:
            self._note('windows', 'error', WHY['no_match'][self.lang == 'en'])
            return
        by_id = _desktop('focus_window_id')
        if by_id and WINDOW_ID.fullmatch(row['id']):
            call, args = by_id, (row['id'], row['title'])
        elif row['unique']:
            import desktop_tools
            call, args = desktop_tools.focus_window, (row['title'],)
        else:
            self._note('windows', 'error', WHY['same_title'][self.lang == 'en'])
            return
        self._busy('focus:' + row['id'], True)
        self.run('focus:' + row['id'], call, *args)

    def on_focus(self, tag, result):
        self._busy(tag, False)
        ok = isinstance(result, dict) and result.get('status') == 'ok'
        title = str(result.get('title', '')) if isinstance(result, dict) else ''
        text = ((('انتقلت إلى «' + title + '»') if self.lang != 'en' else ('Focused «' + title + '»')) if ok
                else _why(result, self.lang))
        self._note('windows', 'ok' if ok else 'error', text)
        self.refreshWindows()

    @Slot(str, str)
    def closeWindow(self, wid, title):
        """Closing a window can lose unsaved work: it is the owner's decision, on a card that names it."""
        row = self._window(str(wid or ''))
        if row is None:
            self._note('windows', 'error', WHY['no_match'][self.lang == 'en'])
            return
        by_id = bool(_desktop('close_window_id')) and bool(WINDOW_ID.fullmatch(row['id']))
        if not by_id and not row['unique']:
            self._note('windows', 'error', WHY['same_title'][self.lang == 'en'])
            return
        key = 'close:' + row['id']
        wait = self._expect.get(key)
        if wait and self._card_live(wait):
            self._note('windows', 'pending', self.text('pcp_card_open'))
            return
        name = row['title'][:120]
        detail = (f'ستطلب ميرا من النافذة «{name}» أن تُغلق؛ قد يسألك التطبيق عن حفظ عملك، وما لم يُحفظ قد يضيع.'
                  if self.lang != 'en' else
                  f'Mira will ask the window «{name}» to close; the app may ask you to save, and unsaved work can be lost.')
        args = {'query': name}
        if by_id:
            args['id'] = row['id']
        card = self.host.request_confirmation({'kind': 'desktop', 'name': 'close_window', 'args': args,
                                               'detail': detail, 'origin': 'pc'})
        if not card:
            self._note('windows', 'error', WHY['no_card'][self.lang == 'en'])
            return
        card_id = str(card.get('id') or '') if isinstance(card, dict) else ''
        self._expect[key] = {'want': None, 'until': time.monotonic() + CARD_TTL, 'why': 'close',
                             'card': card_id, 'since': time.monotonic(), 'title': name}
        if card_id:
            self._cards[card_id] = key
        self._note('windows', 'pending', self.text('pcp_waiting') + ' · ' + name)

    # ── media ────────────────────────────────────────────────────────
    @Slot()
    def refreshMedia(self):
        import desktop_tools
        self.run('media:status', desktop_tools.media, 'status')

    @Slot(str)
    def media(self, action):
        if action not in MEDIA:
            return
        player = self._state['media'].get('player') or None
        self._busy('media', True)
        self.run('media:' + action, self._media_call, action, player)

    @staticmethod
    def _media_call(action, player):
        import desktop_tools
        result = desktop_tools.media(action, player)
        if isinstance(result, dict) and result.get('status') == 'ok':
            return {'action': result, 'now': desktop_tools.media('status', player)}
        return {'action': result, 'now': None}

    def on_media(self, tag, result):
        action = tag.split(':', 1)[1]
        if action == 'status':
            self._show_media(result)
            return
        self._busy('media', False)
        done = result.get('action') if isinstance(result, dict) else None
        if isinstance(done, dict) and done.get('status') == 'ok':
            self._show_media(result.get('now') or {})
            self._note('media', 'ok', self._media_line(done))
        else:
            self._note('media', 'error', _why(done, self.lang))

    def _show_media(self, result):
        if isinstance(result, dict) and result.get('status') == 'ok':
            self._raw.pop('media', None)
            self.update(mediaState='ok', media={
                'player': str(result.get('player') or ''), 'state': str(result.get('state') or ''),
                'title': str(result.get('title') or ''), 'artist': str(result.get('artist') or ''),
                'players': [str(p) for p in (result.get('players') or [])]})
        elif isinstance(result, dict) and result.get('error') in ('no_player', 'no_session'):
            self.update(mediaState='none', media={})
        elif isinstance(result, dict) and result.get('error') == 'ambiguous':
            self.update(mediaState='none', media={'players': [str(p) for p in (result.get('players') or [])]})
        else:
            self._raw['media'] = result
            self.update(mediaState='error', media={'error': _why(result, self.lang)})

    def _media_line(self, done):
        state = {'Playing': 'pcp_playing', 'Paused': 'pcp_paused', 'Stopped': 'pcp_stopped'}.get(done.get('state'))
        return str(done.get('player') or '') + (' · ' + self.text(state) if state else '')

    # ── hardware ─────────────────────────────────────────────────────
    @Slot()
    def refreshHardware(self):
        import moai_tools
        if not self._state['hardware']:
            self.update(hardwareState='loading')
        self.run('hardware', moai_tools.get, '/scan', 30)

    def on_hardware(self, tag, result):
        hardware = hardware_from_scan(result)
        if hardware is None:
            self.update(hardwareState='error')
        else:
            self.update(hardware=hardware, hardwareState='ok')

    # ── diagnostics (read only) ──────────────────────────────────────
    @Slot(str)
    def runCheck(self, check):
        if check in CHECKS:
            tool, args = CHECKS[check]
            self._diagnose('checks', check, tool, args)

    @Slot(str, bool)
    def unitStatus(self, name, user):
        unit = self._unit(name)
        if unit is None:
            self._output('unit', 'unit_status', 'error', self.text('pcp_unit_bad'), raw='unit_bad')
            return
        args = {'name': unit}
        if user:
            args['user'] = True
        self._diagnose('unit', 'unit_status', 'unit_status', args)

    @Slot(str, str, str, bool)
    def readJournal(self, unit, priority, since, user):
        args = {'lines': 80}
        if str(unit or '').strip():
            name = self._unit(unit)
            if name is None:
                self._output('journal', 'read_journal', 'error', self.text('pcp_unit_bad'), raw='unit_bad')
                return
            args['unit'] = name
            if user:
                args['user'] = True
        if priority in PRIORITIES:
            args['priority'] = priority
        if since in SINCE:
            args['since'] = since
        self._diagnose('journal', 'read_journal', 'read_journal', args)

    @Slot(str)
    def readLog(self, name):
        if name in LOGS:
            self._diagnose('logs', 'log:' + name, 'read_moos_log', {'name': name})

    @staticmethod
    def _unit(name):
        """'pipewire' → 'pipewire.service'; anything that is not a unit name → None."""
        name = str(name or '').strip()
        if name and not name.endswith(UNIT_SUFFIXES):
            name += '.service'
        return name if UNIT.fullmatch(name) else None

    def _diagnose(self, slot, check, tool, args):
        if self._state['running'].get(slot):
            return
        self.update(running={**self._state['running'], slot: check})
        self.run('diag:' + slot + ':' + check, self._diag_call, tool, args)

    @staticmethod
    def _diag_call(tool, args):
        import moai_tools
        return {'tool': tool, 'args': args, 'result': moai_tools.execute(tool, args)}

    def on_diag(self, tag, result):
        _, slot, check = tag.split(':', 2)
        running = dict(self._state['running'])
        running.pop(slot, None)
        self.update(running=running)
        answer = result.get('result') if isinstance(result, dict) and 'result' in result else result
        if isinstance(answer, dict) and answer.get('status') == 'confirm':
            # A read never needs approval today; if the executor says otherwise, the owner decides.
            card = self._card(result['tool'], result['args'])
            self._output(slot, check, 'pending' if card else 'error',
                         self.text('pcp_waiting') if card else WHY['no_card'][self.lang == 'en'],
                         raw='waiting' if card else 'no_card')
        elif isinstance(answer, dict) and answer.get('status') == 'ok':
            self._output(slot, check, 'ok', clean(str(answer.get('output') or '')).rstrip() or '—')
        else:
            self._output(slot, check, 'error', _why(answer, self.lang), raw=answer)

    def _output(self, slot, check, status, text, raw=None):
        self._raw['out:' + slot] = raw
        self.update(outputs={**self._state['outputs'], slot: {'tool': check, 'status': status, 'text': text}})

    # ── files ────────────────────────────────────────────────────────
    @Slot(str)
    def findFiles(self, query):
        query = ' '.join(str(query or '').split())[:120]
        if not query:
            self._raw['files'] = {'error': 'empty_query'}
            self.update(filesState='error', filesError=WHY['empty_query'][self.lang == 'en'], files=[])
            return
        import desktop_tools
        self._files_seq += 1
        self.update(filesState='loading', filesQuery=query, filesError='')
        self.run(f'files:{self._files_seq}', desktop_tools.find_files, query, 20)

    def on_files(self, tag, result):
        if tag != f'files:{self._files_seq}':
            return      # an earlier, slower search: its results belong to a query no longer shown
        if isinstance(result, dict) and result.get('status') == 'ok':
            rows = []
            for f in result.get('files') or []:
                if not isinstance(f, dict) or not f.get('path'):
                    continue
                path = str(f['path'])
                size = f.get('size')
                rows.append({'path': path, 'name': str(f.get('name') or Path(path).name),
                             'folder': str(Path(path).parent).replace(str(Path.home()), '~', 1),
                             'bytes': size if isinstance(size, (int, float)) and not isinstance(size, bool) else -1,
                             'modified': str(f.get('modified') or ''), 'dir': bool(f.get('is_dir'))})
            self._files = {r['path'] for r in rows}
            self._raw.pop('files', None)
            self.update(files=rows, filesState='ok', filesError='')
        else:
            self._files = set()
            self._raw['files'] = result
            self.update(files=[], filesState='error', filesError=_why(result, self.lang))

    @Slot(str, bool)
    def openFile(self, path, folder):
        if path not in self._files:
            self._note('files', 'error', WHY['unknown_file'][self.lang == 'en'])
            return
        target = str(Path(path).parent) if folder else path
        import desktop_tools
        self._busy('open:' + path, True)
        self.run('open:' + path, desktop_tools.open_path, target)

    def on_open(self, tag, result):
        self._busy(tag, False)
        ok = isinstance(result, dict) and result.get('status') == 'ok'
        name = Path(str(result.get('path') or '')).name if ok else ''
        self._note('files', 'ok' if ok else 'error',
                   (('فتحت ' if self.lang != 'en' else 'Opened ') + name) if ok else _why(result, self.lang))

    # ── one control: approval, execution, read-back ──────────────────
    def _control(self, key, tool, args, want):
        """Run one instant control through Mo AI's executor, or park it for the owner's approval."""
        import moai_tools
        if self._state['busy'].get(key):
            if key in LEVELS:
                # the owner moved on while the last value was on its way: send his latest after it
                self._queued[key] = (tool, dict(args), want)
                self.update(wanted={**self._state['wanted'], key: want})
            return
        moai_tools.names()      # loads the image's schemas, so the value rules (confirm_values) apply
        if moai_tools.needs_confirmation(tool, args):
            self._ask(key, tool, args, want)
            return
        self._busy(key, True)
        if key in LEVELS:
            self.update(wanted={**self._state['wanted'], key: want})
        self.run('ctl:' + key, self._apply, tool, args, key in LOOK_KEYS)

    @staticmethod
    def _apply(tool, args, look):
        import moai_tools
        result = moai_tools.execute(tool, args)
        out = {'tool': tool, 'args': args, 'result': result}
        if not isinstance(result, dict) or result.get('status') != 'ok':
            return out
        if tool == 'take_screenshot':
            found = re.search(r'Screenshot saved:\s*(\S.*)$', str(result.get('output') or ''), re.M)
            out['file'] = found.group(1).strip() if found else ''
            out['saved'] = bool(found) and Path(out['file']).is_file()
        elif tool not in NO_READBACK:
            out['stamp'] = time.monotonic()
            out['read'] = parse_status(moai_tools.execute('get_system_status', {}))
            if look:
                out['look'] = read_look()
        return out

    def on_ctl(self, tag, result):
        key = tag.split(':', 1)[1]
        self._busy(key, False)
        try:
            self._ctl_done(key, result)
        finally:
            self._next_level(key)

    def _next_level(self, key):
        """After a level answered: send the owner's newest value if it differs, else let the slider go."""
        if key not in LEVELS:
            return
        queued = self._queued.pop(key, None)
        if queued and not self._matches(key, queued[2]):
            self._control(key, *queued)
            return
        wanted = dict(self._state['wanted'])
        wanted.pop(key, None)
        self.update(wanted=wanted)

    def _ctl_done(self, key, result):
        group = self._group(key)
        answer = result.get('result') if isinstance(result, dict) and 'result' in result else result
        if not isinstance(answer, dict):
            self._note(group, 'error', WHY['shape'][self.lang == 'en'])
            return
        if answer.get('status') == 'confirm':
            self._ask(key, result['tool'], result['args'], self._want(key, result['args']))
            return
        if answer.get('status') != 'ok':
            self._note(group, 'error', _why(answer, self.lang))
            self.host.toast.emit('error', _why(answer, self.lang))
            return
        fields = {}
        stamp = result.get('stamp', 0.0)
        if result.get('read') and stamp >= self._stamp:
            self._stamp = stamp
            fields.update(status=result['read'], readAt=time.strftime('%H:%M:%S'), statusState='ok',
                          statusError='', statusCode='')
            if result.get('look'):
                fields['look'] = result['look']
        if fields:
            self.update(**fields)
        if key == 'screenshot':
            if result.get('saved'):
                self._note(group, 'ok', ('حُفظت اللقطة: ' if self.lang != 'en' else 'Screenshot saved: ')
                           + Path(result['file']).name)
            else:
                self._note(group, 'pending', 'أُرسل الطلب، لكن الملف لم يظهر بعد' if self.lang != 'en'
                           else "Sent, but the file hasn't appeared yet")
            return
        if key == 'keyboard' or key.startswith(('view:', 'arrange:', 'desktop:', 'settings:')):
            # These answer only after they happened (keyboard reads its layout back itself).
            if key == 'keyboard':
                self._raw['layout'] = str(answer.get('output') or '')
            text = self._said(answer.get('output'))
            if key == 'keyboard':
                self.update(layout=text.split(':', 1)[-1].strip())
            self._note(group, 'ok', text)
            if key.startswith('arrange:'):
                self.refreshWindows()
            return
        want = self._want(key, result['args'])
        if self._matches(key, want):
            self._expect.pop(key, None)
            self._note(group, 'ok', self._done_text(key, want))
        else:
            # The executor answered, the read-back does not show it yet (a theme applies after
            # answering): keep watching for a while, and say so.
            self._expect[key] = {'want': want, 'until': time.monotonic() + SETTLE_S, 'why': 'settle'}
            self._note(group, 'pending', self.text('pcp_applying'))
        self.update(awaiting=self._awaiting())

    def _said(self, output):
        """A control's own one-line answer in the owner's language, cleaned ('Done' when it said nothing)."""
        text = re.sub(r'^\W+', '', _half(output or '', self.lang)).strip()
        return clean(text) or ('تم' if self.lang != 'en' else 'Done')

    # ── the owner's approval ─────────────────────────────────────────
    def _detail(self, tool, args):
        """What the card asks, in words, and what approving it will do (never a raw enum value)."""
        import moai_tools
        en = self.lang == 'en'
        value = next((str(args[k]) for k in ('value', 'profile', 'level') if k in args), None)
        action = ACTIONS.get((tool, value))
        if action:
            text = action[en]
        else:
            text = moai_tools.title(tool, self.lang)
            if tool in ('set_volume', 'set_brightness') and value is not None and value.isdigit():
                text += f': {value}%'
            elif value in VALUE_WORDS:
                text += ': ' + self.text(VALUE_WORDS[value])
            elif args.get('name') or args.get('unit'):
                text += ': ' + str(args.get('name') or args.get('unit'))[:120]
        said = moai_tools.consequence(tool, self.lang) if callable(getattr(moai_tools, 'consequence', None)) else ''
        rules = ((moai_tools.meta(tool) or {}).get('confirm_values') or {})
        if said and rules and not any(str(args.get(arg)) in values for arg, values in rules.items()):
            said = ''       # the consequence speaks of the risky value; this is the other one
        return text + (' · ' + said if said else '')

    def _card(self, tool, args):
        """Put one Mo AI change in front of the owner (an ActionCards card); nothing runs here."""
        return self.host.request_confirmation({'kind': 'moai', 'name': tool, 'args': dict(args),
                                               'detail': self._detail(tool, args), 'origin': 'pc'})

    def _card_live(self, wait):
        """Is the card behind this wait still in front of the owner? The controller knows
        (host.card_waiting); without it, a card is assumed live for its whole lifetime."""
        ask = getattr(self.host, 'card_waiting', None)
        if callable(ask) and wait.get('card'):
            try:
                return bool(ask(wait['card']))
            except Exception:
                pass
        return time.monotonic() - wait.get('since', 0) < CARD_TTL

    def _ask(self, key, tool, args, want):
        import moai_tools
        group = self._group(key)
        wait = self._expect.get(key)
        if wait and wait['why'] == 'approval' and wait['want'] == want and self._card_live(wait):
            self._note(group, 'pending', self.text('pcp_card_open'))
            return      # the card is already in front of the owner
        card = self._card(tool, args)
        if not card:
            self._note(group, 'error', WHY['no_card'][self.lang == 'en'])
            return
        card_id = str(card.get('id') or '') if isinstance(card, dict) else ''
        if card_id:
            self._cards[card_id] = key
        if want is not None:
            now = time.monotonic()
            self._expect[key] = {'want': want, 'until': now + APPROVAL_S, 'why': 'approval', 'since': now,
                                 'card': card_id}
            self.update(awaiting=self._awaiting())
        self._note(group, 'pending', self.text('pcp_waiting') + ' · ' + moai_tools.title(tool, self.lang))

    def action_update(self, card_id, stage, summary='', output=''):
        """The controller's word on a card this page raised: running, ok, error, cancelled, expired, or
        still-running (the job outlived the controller's wait: it goes on, and no end will be told)."""
        key = self._cards.get(card_id)
        if key is None:
            return
        en = self.lang == 'en'
        if stage == 'still-running':
            self._cards.pop(card_id, None)
            self._expect.pop(key, None)
            self._note(self._group(key), 'pending', clean(summary) or self.text('pcp_applying'))
            self.update(awaiting=self._awaiting())
            if key.startswith('close:'):
                self.refreshWindows()
            else:
                self.refreshStatus()
            return
        if stage != 'running':
            self._cards.pop(card_id, None)
        if key.startswith('close:'):
            wait = self._expect.get(key) or {}
            if stage == 'running':
                return
            self._expect.pop(key, None)
            title = wait.get('title', '')
            if stage == 'ok':
                self._note('windows', 'ok', ('طلبت إغلاق «' + title + '»') if not en else ('Asked «' + title + '» to close'))
                self.refreshWindows()
            else:
                self._note('windows', 'info' if stage in ('cancelled', 'expired') else 'error',
                           self._card_end(stage, summary, output))
            return
        group = self._group(key)
        wait = self._expect.get(key)
        now = time.monotonic()
        if stage in ('running', 'ok'):
            if wait:
                wait.update(why='settle', until=now + SETTLE_S, card_closed=False)
                self._note(group, 'pending', self.text('pcp_applying'))
            if stage == 'ok':
                self.refreshStatus()
        else:
            self._expect.pop(key, None)
            self._note(group, 'info' if stage in ('cancelled', 'expired') else 'error',
                       self._card_end(stage, summary, output))
        self.update(awaiting=self._awaiting())

    def _card_end(self, stage, summary, output):
        if stage == 'cancelled':
            return self.text('pcp_card_rejected')
        if stage == 'expired':
            return self.text('pcp_card_expired')
        said = _why({'output': output}, self.lang) if str(output or '').strip() else ''
        return said or clean(summary) or WHY['failed'][self.lang == 'en']

    @staticmethod
    def _want(key, args):
        value = args.get('value', args.get('profile', args.get('level')))
        if key in ('wifi', 'bluetooth', 'dnd'):
            return value == 'on'
        if key == 'mic':
            return value == 'unmute'
        if key == 'mute':
            return value == 'mute'
        if key in LEVELS:
            try:
                return int(value)
            except (TypeError, ValueError):
                return None
        return value

    @staticmethod
    def _group(key):
        if key in ('volume', 'mute', 'brightness', 'night'):
            return 'levels'
        if key.startswith(('view:', 'arrange:', 'desktop:', 'close:')):
            return 'windows'
        if key.startswith('settings:'):
            return SETTINGS_GROUP.get(key.split(':', 1)[1], 'controls')
        return 'controls'

    def _done_text(self, key, want):
        en = self.lang == 'en'
        if key == 'volume':
            return (f'الصوت الآن {want}%' if not en else f'Volume is now {want}%')
        if key == 'brightness':
            level = self._state['status'].get('brightness', want)
            return (f'السطوع الآن {level}%' if not en else f'Brightness is now {level}%')
        if key == 'mute':
            return self.text('pcp_muted') if want else (('عاد الصوت' if not en else 'Sound is back'))
        names = {'wifi': 'pcp_wifi', 'bluetooth': 'pcp_bluetooth', 'night': 'pcp_night_light', 'dnd': 'pcp_dnd',
                 'mic': 'pcp_mic', 'theme': 'pcp_theme', 'power': 'pcp_power', 'motion': 'pcp_motion',
                 'clarity': 'pcp_clarity'}
        label = self.text(names.get(key, key))
        if isinstance(want, bool):
            if key == 'mic':
                value = self.text('pcp_mic_live' if want else 'pcp_mic_muted')
            else:
                value = self.text('pcp_on' if want else 'pcp_off')
        elif key == 'night':
            value = self.text({'on': 'pcp_night_on', 'off': 'pcp_off', 'auto': 'pcp_auto'}.get(want, 'pcp_unknown'))
        else:
            value = self.text(VALUE_WORDS.get(want, 'pcp_unknown'))
        return f'{label}: {value}' + (' · تأكدت' if not en else ' · confirmed')

    def _not_seen_text(self, key):
        return ('أُرسل الأمر، لكن القراءة لا تُظهر التغيير' if self.lang != 'en'
                else "Sent, but the read-back doesn't show the change")

    # ── the owner switched the language ──────────────────────────────
    def _relocalize(self):
        """Say again, in the new language, what the page says in words; drop one-off notes."""
        lang = self.lang
        fields = {'notes': {}}
        if 'status' in self._raw and self._state['statusState'] == 'error':
            fields['statusError'] = _why(self._raw['status'], lang)
        if 'windows' in self._raw and self._state['windowsState'] == 'error':
            fields['windowsError'] = _why(self._raw['windows'], lang)
        if 'files' in self._raw and self._state['filesState'] == 'error':
            fields['filesError'] = _why(self._raw['files'], lang)
        if 'media' in self._raw and self._state['mediaState'] == 'error':
            fields['media'] = {'error': _why(self._raw['media'], lang)}
        if self._raw.get('layout'):
            fields['layout'] = self._said(self._raw['layout']).split(':', 1)[-1].strip()
        outputs = dict(self._state['outputs'])
        for slot, entry in outputs.items():
            raw = self._raw.get('out:' + slot)
            if raw is None or entry.get('status') == 'ok':
                continue
            text = (self.text('pcp_unit_bad') if raw == 'unit_bad' else self.text('pcp_waiting') if raw == 'waiting'
                    else WHY['no_card'][lang == 'en'] if raw == 'no_card' else _why(raw, lang))
            outputs[slot] = {**entry, 'text': text}
        fields['outputs'] = outputs
        self.update(**fields)

    # ── small state helpers ──────────────────────────────────────────
    def _busy(self, key, on):
        busy = dict(self._state['busy'])
        if on:
            busy[key] = True
        else:
            busy.pop(key, None)
        self.update(busy=busy)

    def _note(self, group, status, text):
        self.update(notes={**self._state['notes'], group: {'status': status, 'text': str(text)}})

    # ── review renders (MIRA_TEST_MODE) ──────────────────────────────
    def review(self):
        en = self.lang == 'en'
        windows = [{'id': '{sample-1}', 'title': 'Sample · Report.odt — LibreOffice Writer', 'app': 'libreoffice-writer',
                    'active': True, 'minimized': False},
                   {'id': '{sample-2}', 'title': 'Sample · ~ : bash — Konsole', 'app': 'org.kde.konsole',
                    'active': False, 'minimized': False},
                   {'id': '{sample-3}', 'title': 'Sample · ~ : bash — Konsole', 'app': 'org.kde.konsole',
                    'active': False, 'minimized': True},
                   {'id': '{sample-4}', 'title': 'Sample · Photos — Dolphin', 'app': 'org.kde.dolphin',
                    'active': False, 'minimized': False}]
        mark_ambiguous(windows)
        for row in windows:
            row['canFocus'] = row['canClose'] = row['unique']
        self.update(
            sample=True,
            status={'volume': 42, 'muted': False, 'brightness': 70, 'night_light': True, 'wifi': True,
                    'bluetooth': True, 'theme': 'dark', 'dnd': False, 'mic_muted': False, 'power_profile': 'balanced'},
            statusState='ok', readAt='12:00:00',
            look={'motion': 'gentle', 'clarity': 'balanced', 'night': 'auto'},
            layout='العربية (مثال)' if not en else 'Arabic (sample)',
            awaiting={'bluetooth': 'approval'},
            notes={'controls': {'status': 'pending', 'text': self.text('pcp_waiting') + ' · '
                                + ('البلوتوث (مثال)' if not en else 'Bluetooth (sample)')},
                   'levels': {'status': 'ok', 'text': 'الصوت الآن 42% (مثال)' if not en else 'Volume is now 42% (sample)'}},
            windows=windows,
            windowsState='ok',
            media={'player': 'vlc', 'state': 'Playing', 'title': 'Sample track', 'artist': 'Sample artist',
                   'players': ['vlc']},
            mediaState='ok',
            hardware={'cpu': 'Sample CPU · 8-core', 'cores': 16, 'memory_gb': 16, 'gpu': 'Sample GPU',
                      'driver_ar': 'تعريف مثال يعمل', 'driver_en': 'Sample driver active',
                      'disk_total_gb': 476, 'disk_free_gb': 194, 'kernel': '7.2.7', 'version': '44.20260927.0',
                      'arch': 'x86_64'},
            hardwareState='ok',
            outputs={'checks': {'tool': 'top_processes:cpu', 'status': 'ok',
                                'text': '== top processes by cpu (sample) ==\n'
                                        '    PID USER          %CPU %MEM        RSS COMMAND\n'
                                        '   2101 owner          21.0  2.1     350112 kwin_wayland\n'
                                        '   3380 owner           8.4  1.2     201344 plasmashell\n'
                                        '   4122 owner           3.1  0.9     148220 mira'}},
            files=[{'path': '/home/sample/Documents/report.odt', 'name': 'report.odt (sample)',
                    'folder': '~/Documents', 'bytes': 49152, 'modified': '2026-09-28 14:10', 'dir': False},
                   {'path': '/home/sample/Pictures/Screenshots', 'name': 'Screenshots (sample)',
                    'folder': '~/Pictures', 'bytes': -1, 'modified': '2026-09-29 09:02', 'dir': True}],
            filesState='ok', filesQuery='report',
        )


PAGE = PcPage
