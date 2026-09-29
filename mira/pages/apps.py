"""Apps: Mo Store inside Mira.

One page for everything that puts a program on this computer or keeps it current:

- the store search (Mo Store's own catalogue), with Install, Open and Remove on every result;
- the installed applications, read from the machine itself and filtered as the owner types;
- app updates: what MoOS's daily check found waiting, "update all", and "check now";
- what this device should have (the device plan's missing recommended apps);
- an application that arrived as a FILE (App Drop, which asks the owner itself);
- the compatibility hub: Windows games and programs, Android apps, the phone, virtual machines.

Reads run at once. Every change (install, remove, update, set-up) is a card the owner approves
(`host.request_confirmation`); nothing here runs one. A result is "installed" or "removed" only
when the machine's own installed list says so: the page re-reads it while a request is open.

Where MoOS already has one answer, the page asks it instead of guessing: which runtime runs
Windows programs and Android apps, and whether it is ready, is `/usr/libexec/moos-app-engine list`
(the resolver the file-manager runner, App Drop and Mo Store share); the phone link is the image's
own KDE Connect entry (named «الهاتف» / Phone in the menu), never a Flatpak.

The owner reads MoOS's voice here, so runtime and packaging names never appear in the words
(tests/test_app_engines.py's rule): the page says "Windows programs", not the engine behind them.
"""
import json
import os
import platform
import re
import shutil
import subprocess
import time
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl, Slot

import moai_tools
import moos_routes
from pages.base import TEST_MODE, Page

APP_ID = re.compile(r'[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+){2,}')
RPM_MAGIC = b'\xed\xab\xee\xdb'
RPM_FOLDERS = ('Downloads', 'Desktop', 'Documents')     # the only folders moos-open takes an RPM from
ENGINE_RESOLVER = Path('/usr/libexec/moos-app-engine')  # read-only: never installs, launches or writes
PHONE_APP = 'org.kde.kdeconnect.app'                    # the image's own phone link (menu: «الهاتف» / Phone)
FLATHUB_ICON = re.compile(r'https://dl\.flathub\.org/media/[A-Za-z0-9/._-]{1,300}\.(png|svg)')
# moai-control keeps the END of a long tool output, moos-inspect the start; both say so on a line.
TRIM_MARKS = ('earlier output trimmed', 'truncated to')
CARD_WAIT_S = 180          # a card waits this long for the owner (controller.CONFIRM_TTL)
WATCH_S = 30 * 60          # how long an approved install/remove is followed on the installed list
POLL_MS = 8000
REFRESH_EVERY_S = 20       # re-opening the page within this reads nothing again
HEALTH_FAST_MS, HEALTH_SLOW_MS = 4000, 20000
HEALTH_FAST_POLLS, HEALTH_MAX_POLLS = 45, 90   # 3 min every 4 s, then 15 min every 20 s (moos-health: ≤ 15 min)

STRINGS = {
    'apps_sub': ('ابحث وثبّت وافتح وحدّث — وكل تغيير ينتظر موافقتك', 'Find, install, open and update — every change waits for your approval'),
    'apps_open_store': ('Mo Store', 'Mo Store'),
    'apps_open_store_tip': ('افتح متجر MoOS الكامل', 'Open the full MoOS store'),
    'apps_from_file': ('من ملف', 'From a file'),
    'apps_reload': ('اقرأ من جديد', 'Read again'),
    # search
    'apps_search_title': ('ابحث في المتجر', 'Search the store'),
    'apps_search_hint': ('اسم تطبيق أو ما تحتاجه: مونتاج، موسيقى، كاميرا…', 'An app name or what you need: video editor, music, camera…'),
    'apps_search_go': ('ابحث', 'Search'),
    'apps_searching': ('أبحث في المتجر…', 'Searching the store…'),
    'apps_no_results': ('لم أجد تطبيقاً بهذا الاسم في المتجر.', 'The store has no app by that name.'),
    'apps_ask_mira': ('اسأل ميرا', 'Ask Mira'),
    'apps_search_failed': ('تعذّر البحث في المتجر', 'The store search did not answer'),
    'apps_try': ('جرّب:', 'Try:'),
    'apps_q_video': ('مونتاج فيديو', 'Video editing'),
    'apps_q_music': ('موسيقى', 'Music'),
    'apps_q_browser': ('متصفح', 'Browser'),
    'apps_q_office': ('مستندات', 'Office'),
    'apps_q_chat': ('مراسلة', 'Messaging'),
    'apps_q_draw': ('رسم وتصميم', 'Drawing'),
    'apps_results': ('النتائج', 'Results'),
    'apps_clear': ('مسح', 'Clear'),
    'apps_verified': ('ناشر موثّق', 'Verified publisher'),
    'apps_pick': ('اختيار MoOS', 'MoOS pick'),
    'apps_installs': ('تثبيت في الشهر الماضي', 'installs last month'),
    'apps_installed': ('مثبّت', 'Installed'),
    'apps_install': ('تثبيت', 'Install'),
    'apps_open': ('فتح', 'Open'),
    'apps_remove': ('إزالة', 'Remove'),
    'apps_waiting': ('بانتظار موافقتك', 'Waiting for your approval'),
    'apps_following': ('أتابع التنفيذ…', 'Following it…'),
    'apps_opening': ('أفتح…', 'Opening…'),
    'apps_local_source': ('من المصادر المحلية (المتجر غير متصل)', 'From the local sources (the store is offline)'),
    # installed
    'apps_installed_title': ('تطبيقاتك', 'Your apps'),
    'apps_filter': ('صفِّ القائمة…', 'Filter…'),
    'apps_installed_empty': ('لا تطبيقات مثبّتة من المتجر بعد', 'No store apps installed yet'),
    'apps_no_match': ('لا تطبيق يطابق هذا', 'No app matches that'),
    'apps_installed_failed': ('تعذّر قراءة التطبيقات المثبّتة', 'Could not read the installed apps'),
    'apps_installed_partial': ('القائمة ناقصة: وصلني جزء منها فقط، فلن أحكم بغياب تطبيق عنها',
                               'The list is incomplete: only part of it arrived, so an app missing from it may still be installed'),
    'apps_show_all': ('اعرض الكل', 'Show all'),
    'apps_show_less': ('اعرض أقل', 'Show fewer'),
    'apps_system_scope': ('للنظام', 'System'),
    'apps_system_tip': ('مثبّت لكل مستخدمي الجهاز؛ Mo Store يزيل تطبيقات حسابك فقط',
                        'Installed for every user of this computer; Mo Store removes only your own apps'),
    'apps_system_no_remove': ('هذا التطبيق مثبّت للنظام كله؛ Mo Store يزيل تطبيقات حسابك فقط',
                              'This app is installed for the whole system; Mo Store removes only your own apps'),
    # updates
    'apps_updates_title': ('التحديثات', 'Updates'),
    # "one|two|few (3–10)|many" in Arabic; "one|many" in English; %1 is the number
    'apps_updates_n': ('تحديث واحد بانتظارك|تحديثان بانتظارك|%1 تحديثات بانتظارك|%1 تحديثاً بانتظارك',
                       '1 update waiting|%1 updates waiting'),
    'apps_updates_none': ('كل تطبيقاتك محدّثة', 'All your apps are up to date'),
    'apps_updates_unknown': ('لم يعمل الفحص اليومي على هذا الجهاز بعد', 'The daily check has not run on this computer yet'),
    'apps_updates_check_failed': ('آخر فحص لم يصل إلى المتجر، فلا أعرف ما ينتظر التحديث', 'The last check could not reach the store, so what waits for an update is unknown'),
    'apps_updates_failed': ('تعذّر قراءة الفحص اليومي', 'Could not read the daily check'),
    'apps_update_all': ('حدّث الكل', 'Update all'),
    'apps_check_now': ('افحص الآن', 'Check now'),
    'apps_checking_updates': ('أفحص التحديثات… قد يأخذ دقيقة', 'Checking for updates… this can take a minute'),
    'apps_check_slow': ('ما زال الفحص يعمل؛ افتح الصفحة لاحقاً لترى نتيجته', 'The check is still running; open this page again later for its result'),
    'apps_checked': ('آخر فحص', 'Last checked'),
    'apps_ago_now': ('الآن', 'just now'),
    'apps_ago_min': ('دقيقة|دقيقتين|دقائق|دقيقة', 'minute|minutes'),
    'apps_ago_hour': ('ساعة|ساعتين|ساعات|ساعة', 'hour|hours'),
    'apps_ago_day': ('يوم|يومين|أيام|يوماً', 'day|days'),
    'apps_ago': ('قبل %1', '%1 ago'),
    'apps_update_detail': ('يحدّث كل تطبيقات المتجر عبر Mo Store', 'Updates every store app through Mo Store'),
    'apps_update_detail_waiting': ('بانتظار التحديث:', 'waiting:'),
    # recommended
    'apps_rec_title': ('مقترح لهذا الجهاز', 'Recommended for this device'),
    'apps_rec_sub': ('من خطة الجهاز: ما ينقص عتادك واستخدامك', 'From the device plan: what your hardware and use are missing'),
    'apps_rec_all': ('ثبّت الكل', 'Install all'),
    'apps_rec_done': ('كل ما يُقترح لهذا الجهاز مثبّت', 'Everything recommended for this device is installed'),
    'apps_rec_reading': ('أقرأ خطة الجهاز…', 'Reading the device plan…'),
    'apps_rec_failed': ('تعذّر قراءة خطة الجهاز', 'Could not read the device plan'),
    'apps_rec_detail': ('يثبّت ما ينقص هذا الجهاز عبر Mo Store:', 'Installs what this device is missing through Mo Store:'),
    # compatibility
    'apps_compat_title': ('تشغيل كل شيء', 'Run everything'),
    'apps_compat_sub': ('ألعاب وبرامج ويندوز وتطبيقات أندرويد والهاتف والأجهزة الافتراضية', 'Windows games and programs, Android apps, your phone, virtual machines'),
    'apps_c_games': ('ألعاب ويندوز', 'Windows games'),
    'apps_c_games_d': ('Steam وكل ما تحتاجه ألعاب ويندوز', 'Steam and everything Windows games need'),
    'apps_c_windows': ('برامج ويندوز', 'Windows programs'),
    'apps_c_windows_d': ('شغّل برامج ‎.exe في بيئة معزولة', 'Run .exe programs in an isolated space'),
    'apps_c_windows_ready_d': ('انقر مرتين على أي ملف ‎.exe لتشغيله', 'Double-click any .exe file to run it'),
    'apps_c_android': ('تطبيقات أندرويد', 'Android apps'),
    'apps_c_android_d': ('بعد التجهيز: افتح أي ملف ‎.apk بنقرتين', 'After set-up: double-click any .apk file'),
    'apps_c_android_ready_d': ('انقر مرتين على أي ملف ‎.apk لتثبيته', 'Double-click any .apk file to install it'),
    'apps_c_phone': ('ربط الهاتف', 'Your phone'),
    'apps_c_phone_d': ('إشعارات وملفات ورسائل هاتفك هنا', "Your phone's notifications, files and messages here"),
    'apps_c_phone_missing': ('ربط الهاتف غير موجود في نسخة MoOS هذه', 'This MoOS edition has no phone link'),
    'apps_phone_app': ('الهاتف', 'Phone'),
    'apps_phone_devices': ('أجهزتك في صفحة الاتصال', 'Your devices on the Connect page'),
    'apps_c_vm': ('الأجهزة الافتراضية', 'Virtual machines'),
    'apps_c_vm_d': ('تسريع المعالج للمحاكيات والأنظمة الافتراضية', 'CPU acceleration for emulators and virtual machines'),
    'apps_c_vm_off': ('فعّل المحاكاة الافتراضية من إعدادات البرنامج الثابت', 'Turn on CPU virtualization in the firmware settings'),
    'apps_ready': ('جاهز', 'Ready'),
    'apps_needs_setup': ('غير مجهّز', 'Not set up'),
    'apps_unavailable': ('غير متاح', 'Unavailable'),
    'apps_checking': ('أتحقق…', 'Checking…'),
    'apps_unknown': ('تعذّر التحقق', 'Could not check'),
    'apps_set_up': ('جهّز', 'Set up'),
    'apps_admin': ('يطلب كلمة المرور', 'Asks for the password'),
    'apps_setup_games': ('يثبّت Steam وكل ما تحتاجه ألعاب ويندوز عبر Mo Store (ما ينقص فقط)',
                         'Installs Steam and everything Windows games need through Mo Store (only what is missing)'),
    'apps_setup_windows': ('يثبّت بيئة معزولة تشغّل برامج ‎.exe — مرة واحدة، بلا صلاحيات مدير',
                           'Installs an isolated space that runs .exe programs — once, with no admin rights'),
    'apps_setup_android': ('يجهّز تطبيقات أندرويد ويشغّلها — أول مرة ينزّل نحو 1 GB ويطلب كلمة المرور',
                           'Sets up Android apps and starts them — the first time it downloads about 1 GB and asks for the password'),
    # install / remove card details
    'apps_install_store': ('من متجر MoOS، لحسابك فقط — بلا صلاحيات مدير', 'From the MoOS store, for your account only — no admin rights'),
    'apps_install_local': ('من المصادر المحلية عبر Mo Store، لحسابك فقط — بلا صلاحيات مدير',
                           'From the local sources through Mo Store, for your account only — no admin rights'),
    'apps_remove_detail': ('يزيل التطبيق؛ ملفاتك في مجلدك تبقى كما هي', 'Removes the app; your own files stay where they are'),
    # from a file
    'apps_file_title': ('تطبيق من ملف', 'An app from a file'),
    'apps_file_sub': ('أفلت الملف هنا أو اختره — App Drop يسألك قبل أي تثبيت', 'Drop the file here or choose it — App Drop asks you before installing anything'),
    'apps_file_choose': ('اختر ملفاً', 'Choose a file'),
    'apps_file_drop': ('أفلت الملف لتثبيته', 'Drop the file to install it'),
    'apps_file_sent': ('أرسلت الملف إلى نافذة التثبيت — أجب عنها لتكمل', 'Sent to the install window — answer it to continue'),
    'apps_file_sent_rpm': ('أرسلت الحزمة إلى التثبيت الموقّع: يتحقق من التوقيع ويطلب كلمة المرور',
                           'Sent to the signed-package install: it checks the signature and asks for the password'),
    'apps_file_outside': ('اختر ملفاً من داخل مجلدك الشخصي', 'Choose a file inside your home folder'),
    'apps_file_rpm_folder': ('ضع الحزمة في التنزيلات أو سطح المكتب أو المستندات ثم اخترها', 'Put the package in Downloads, Desktop or Documents, then choose it'),
    'apps_file_rpm_name': ('اسم الحزمة يجب أن ينتهي بـ ‎.rpm؛ أعد تسميتها ثم اخترها', 'The package name must end in .rpm; rename it, then choose it'),
    'apps_file_not_yours': ('هذا الملف ليس ملكك؛ انسخه إلى التنزيلات ثم اختر النسخة', 'This file is not yours; copy it to Downloads, then choose the copy'),
    'apps_file_link': ('هذا اختصار لملف؛ اختر الملف نفسه', 'That is a shortcut to a file; choose the file itself'),
    'apps_file_long': ('مسار الملف طويل جداً؛ انقله إلى التنزيلات', 'The file path is too long; move it to Downloads'),
    'apps_file_failed': ('تعذّر فتح نافذة التثبيت', 'Could not open the install window'),
    'apps_file_more': ('أرسلت الملف الأول فقط؛ أفلت الملفات واحداً بعد الآخر', 'Only the first file was sent; drop the files one at a time'),
    'apps_kinds': ('‎.AppImage · ‎.tar/.zip · ‎.flatpakref · ‎.rpm · ‎.exe · ‎.apk', '.AppImage · .tar/.zip · .flatpakref · .rpm · .exe · .apk'),
    # results and notices
    'apps_opened': ('فتحت', 'Opened'),
    'apps_open_failed': ('تعذّر فتح التطبيق', 'Could not open the app'),
    'apps_now_installed': ('ثُبّت الآن', 'is installed now'),
    'apps_now_removed': ('أزيل الآن', 'is removed now'),
    'apps_not_done': ('لم يتغير شيء', 'Nothing changed'),
    'apps_card_refused': ('لا يقبل منفّذ MoOS هذا الطلب', "MoOS's executor does not accept this request"),
    'apps_bad_id': ('معرّف تطبيق غير صالح', 'Not a valid app id'),
    # why a read failed, in the owner's words (never a raw code)
    'apps_err_unreachable': ('خدمة أدوات MoOS لا تجيب', "MoOS's tools service is not answering"),
    'apps_err_store_down': ('المتجر لا يجيب الآن', 'The store is not answering right now'),
    'apps_err_busy': ('عملية أخرى ما زالت تعمل؛ انتظر انتهاءها', 'Another operation is still running; wait for it to end'),
    'apps_err_timeout': ('لم يصل الجواب في الوقت', 'The answer did not come in time'),
}

# Names and one line of purpose for the ids the device plan recommends (brands are not translated).
RECOMMENDED = {
    'org.mozilla.firefox': ('Firefox', 'globe', 'متصفح الإنترنت', 'Web browser'),
    'org.videolan.VLC': ('VLC', 'play', 'يشغّل كل صيغ الفيديو والصوت', 'Plays every video and audio format'),
    'org.libreoffice.LibreOffice': ('LibreOffice', 'book', 'مستندات وجداول وعروض', 'Documents, spreadsheets and slides'),
    'com.github.tchx84.Flatseal': ('Flatseal', 'shield', 'أذونات كل تطبيق', "Each app's permissions"),
    'com.google.AndroidStudio': ('Android Studio', 'rocket', 'بناء تطبيقات أندرويد', 'Build Android apps'),
    'org.gnome.Snapshot': ('Camera', 'face', 'الكاميرا', 'Camera'),
}

# The compatibility hub: (key, glyph, title key, detail key, set-up tool, set-up details key).
COMPAT = [
    ('games', 'play', 'apps_c_games', 'apps_c_games_d', 'setup_gaming', 'apps_setup_games'),
    ('windows', 'grid', 'apps_c_windows', 'apps_c_windows_d', 'setup_windows', 'apps_setup_windows'),
    ('android', 'apps', 'apps_c_android', 'apps_c_android_d', 'setup_waydroid', 'apps_setup_android'),
    ('phone', 'chat', 'apps_c_phone', 'apps_c_phone_d', '', ''),
    ('vm', 'chip', 'apps_c_vm', 'apps_c_vm_d', '', ''),
]
X86_ONLY = ('games', 'windows')      # Steam and Windows programs are built for x86 PCs
ENGINE_KEYS = ('windows', 'android')  # answered by the resolver
STEAM = 'com.valvesoftware.Steam'
REASONS = {'moai_control_unreachable': 'apps_err_unreachable', 'busy': 'apps_err_busy',
           'timeout': 'apps_err_timeout', 'TimeoutExpired': 'apps_err_timeout'}
SHEETS = ('connect',)                # Mira pages this one may send the owner to


def valid_id(app_id):
    return isinstance(app_id, str) and len(app_id) <= 255 and bool(APP_ID.fullmatch(app_id))


def parse_installed(output):
    """An installed-apps listing (application<TAB>name<TAB>version<TAB>scope per line) → (apps, partial).

    `partial` is True when a reader trimmed the listing: then the line next to the trim note is cut
    mid-id and is dropped, and an app ABSENT from the list may still be installed."""
    lines = str(output or '').splitlines()
    partial = False
    drop = set()
    for index, line in enumerate(lines):
        text = line.strip()
        if text.startswith('[') and any(mark in text for mark in TRIM_MARKS):
            partial = True
            drop.add(index)
            # a note after listed lines cut the line before it (first part kept); a note before them
            # cut the line after it (the end kept)
            drop.add(index - 1 if any('\t' in earlier for earlier in lines[:index]) else index + 1)
    apps = []
    seen = set()
    for index, line in enumerate(lines):
        if index in drop:
            continue
        parts = [part.strip() for part in line.split('\t')]
        if len(parts) < 2 or not valid_id(parts[0]) or parts[0] in seen:
            continue
        seen.add(parts[0])
        version = parts[2] if len(parts) > 2 else ''
        apps.append({'id': parts[0], 'name': parts[1] or parts[0],
                     'version': '' if version.startswith('[') else version,     # "[redacted]" says nothing
                     'scope': parts[3] if len(parts) > 3 and parts[3] in ('user', 'system') else ''})
    apps.sort(key=lambda a: a['name'].casefold())
    return apps, partial


def _flatpak_list():
    """The machine's own list, complete and exact (read-only); None when it cannot be read here."""
    flatpak = shutil.which('flatpak')
    if not flatpak:
        return None
    try:
        done = subprocess.run([flatpak, 'list', '--app', '--columns=application,name,version,installation'],
                              capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL,
                              env={**os.environ, 'LC_ALL': 'C.UTF-8'})
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout if done.returncode == 0 else None


def read_installed():
    """Worker thread: the installed applications. The machine's own list first; Mo AI's
    list_installed_apps only when that cannot be read (its output may be trimmed: then `partial`)."""
    listing = _flatpak_list()
    if listing is not None:
        apps, partial = parse_installed(listing)
        return {'status': 'ok', 'apps': apps, 'partial': partial}
    result = moai_tools.execute('list_installed_apps', {})
    if not isinstance(result, dict) or result.get('status') != 'ok':
        return {'status': 'error', 'error': (result or {}).get('error', 'shape') if isinstance(result, dict) else 'shape'}
    apps, partial = parse_installed(result.get('output'))
    return {'status': 'ok', 'apps': apps, 'partial': partial}


def read_engines():
    """Worker thread: MoOS's one answer to "what runs Windows programs / Android apps, and is it
    ready" (moos-app-engine list: read-only, never installs, launches or writes)."""
    if not ENGINE_RESOLVER.is_file():
        return {'status': 'error', 'error': 'no_resolver'}
    try:
        done = subprocess.run([str(ENGINE_RESOLVER), 'list'], capture_output=True, text=True, timeout=90,
                              stdin=subprocess.DEVNULL)
        document = json.loads(done.stdout or '')
    except subprocess.TimeoutExpired:
        return {'status': 'error', 'error': 'timeout'}
    except (OSError, ValueError) as exc:
        return {'status': 'error', 'error': type(exc).__name__}
    engines = {}
    listed = document.get('engines') if isinstance(document, dict) else None
    for engine in listed if isinstance(listed, list) else []:
        if not isinstance(engine, dict) or not isinstance(engine.get('engine'), str):
            continue
        chosen = engine.get('chosen') if isinstance(engine.get('chosen'), dict) else None
        runtimes = [r for r in engine.get('runtimes') or [] if isinstance(r, dict)]
        engines[engine['engine']] = {
            'ready': bool(engine.get('ready')), 'needs_setup': bool(engine.get('needs_setup')),
            'present': any(r.get('present') for r in runtimes),
            'chosen': str(chosen.get('id') or '') if chosen else '',
            'sandboxed': bool(chosen and chosen.get('sandboxed')),
            'provision': bool(engine.get('provision_route')),
        }
    return {'status': 'ok', 'engines': engines}


def _data_dirs():
    home = Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local/share')
    shared = os.environ.get('XDG_DATA_DIRS') or '/usr/local/share:/usr/share'
    return [home, *(Path(item) for item in shared.split(':') if item)]


def phone_native():
    """The image ships KDE Connect (the menu's «الهاتف» / Phone); there is no Flatpak of it to install."""
    if shutil.which('kdeconnect-app'):
        return True
    return any((base / 'applications' / (PHONE_APP + '.desktop')).is_file() for base in _data_dirs())


def local(text, lang):
    """MoOS services answer "عربي | English"; keep the owner's half."""
    halves = str(text or '').split(' | ', 1)
    return halves[1] if lang == 'en' and len(halves) == 2 else halves[0]


def _start_folder():
    """Where the file picker opens: Downloads, where an installer usually is."""
    home = Path.home()
    folder = home / 'Downloads'
    return QUrl.fromLocalFile(str(folder if folder.is_dir() else home)).toString()


def _is_arm():
    return platform.machine().lower() in ('aarch64', 'arm64')


class AppsPage(Page):
    def __init__(self, host, parent=None):
        super().__init__(host, parent)
        self._requests = {}          # key (app id | games | windows | android | __updates__) -> request
        self._have = None            # installed app ids, once read
        self._partial = False        # the last installed list was trimmed: absence proves nothing
        self._scopes = {}            # app id -> user | system
        self._scan_compat = {}
        self._scan_arch = ''
        self._engines = None         # resolver answer: engine -> state; {} after a failed read
        self._engines_reading = False
        self._engines_again = False  # a job ended while a read was out: that answer may predate it
        self._last_refresh = 0.0
        self._health_polls = 0
        self._poll = QTimer(self, interval=POLL_MS, timeout=self._watch)
        self._health_timer = QTimer(self, interval=HEALTH_FAST_MS, singleShot=True, timeout=self._read_health)

    def initial(self):
        return {
            # search
            'query': '', 'searching': False, 'searched': False, 'results': [], 'search_failed': False,
            'search_error': '', 'source': '',
            # installed
            'installed': [], 'installed_loading': False, 'installed_failed': False, 'installed_error': '',
            'installed_read': False, 'installed_partial': False,
            # updates (MoOS's daily check)
            'updates': [], 'updates_checked': False, 'updates_report': False, 'updates_at': '',
            'updates_loading': False, 'updates_failed': False, 'updates_error': '', 'updates_scanning': False,
            'updates_note': '',
            # device plan and compatibility
            'recommended': [], 'scan_loading': False, 'scan_failed': False, 'scan_error': '', 'plan_pending': False,
            'scanned': False, 'compat': [], 'arch': platform.machine(), 'smart_setup': False,
            # what waits on the owner: key -> install | remove | open | setup | update | running
            'pending': {},
            'file_status': '', 'file_tone': '', 'file_folder': _start_folder(),
        }

    # ── reading ─────────────────────────────────────────────────────────
    def activated(self):
        if TEST_MODE:
            return
        if time.monotonic() - self._last_refresh < REFRESH_EVERY_S and self._state.get('installed_read'):
            return
        self.refresh()

    @Slot()
    def refresh(self):
        self._last_refresh = time.monotonic()
        self.update(installed_loading=True, installed_failed=False, installed_error='', scan_loading=True,
                    scan_failed=False, scan_error='', updates_loading=True, updates_failed=False, updates_error='',
                    updates_note='', smart_setup='smart_setup' in moai_tools.names())
        self.run('installed:read', read_installed)
        self.run('scan', moai_tools.get, '/scan', 25)
        self.run('health', moai_tools.get, '/health', 20)
        self._read_engines()

    def _why(self, error):
        """A backend's reason in the owner's words; '' when it would add nothing (a bare code)."""
        code = str(error or '').strip()
        if code in REASONS:
            return self.text(REASONS[code])
        if re.fullmatch(r'http_5\d\d', code):
            return self.text('apps_err_store_down')
        if ' ' in code and len(code) <= 160:
            return local(code, self.lang)
        return ''

    def on_installed(self, tag, result):
        result = result if isinstance(result, dict) else {}
        if result.get('status') != 'ok':
            self.update(installed_loading=False, installed_failed=True, installed_error=self._why(result.get('error')))
            return
        apps = [dict(a) for a in result.get('apps') or [] if isinstance(a, dict) and valid_id(a.get('id'))]
        for app in apps:
            app['icon'] = self._theme_icon(app['id'])
        have = {a['id'] for a in apps}
        self._have = have
        self._partial = bool(result.get('partial'))
        self._scopes = {a['id']: a.get('scope', '') for a in apps}
        self.update(installed=apps, installed_loading=False, installed_failed=False, installed_error='',
                    installed_read=True, installed_partial=self._partial,
                    results=[self._mark(r) for r in self._state['results']],
                    recommended=[r for r in self._state['recommended'] if r['id'] not in have],
                    compat=self._compat_rows())
        self._settle()

    def _mark(self, result):
        """A store result against the installed list (newer than the store's own flag, unless partial)."""
        app_id = result['id']
        installed = app_id in (self._have or set()) or ((self._have is None or self._partial) and result.get('store_installed'))
        return {**result, 'installed': bool(installed), 'scope': self._scopes.get(app_id, '') if installed else ''}

    def on_scan(self, tag, result):
        result = result if isinstance(result, dict) else {'error': 'shape'}
        if 'error' in result and not result.get('compatibility'):
            self.update(scan_loading=False, scan_failed=True, scan_error=self._why(result.get('error')), scanned=True)
            return
        self._scan_compat = dict(result.get('compatibility') or {})
        self._scan_arch = str(result.get('arch') or '')
        plan = result.get('device_plan') if isinstance(result.get('device_plan'), dict) else None
        recommended = []
        for app_id in (plan or {}).get('missing_recommended_apps') or []:
            if not valid_id(app_id) or (self._have is not None and app_id in self._have):
                continue
            name, glyph, why_ar, why_en = RECOMMENDED.get(app_id, (app_id.rsplit('.', 1)[-1], 'package', '', ''))
            recommended.append({'id': app_id, 'name': name, 'glyph': glyph, 'why_ar': why_ar, 'why_en': why_en})
        self.update(scan_loading=False, scan_failed=False, scan_error='', scanned=True,
                    arch=self._scan_arch or platform.machine(),
                    plan_pending=plan is None and bool(result.get('device_plan_pending')),
                    recommended=recommended, compat=self._compat_rows())
        self._settle()

    def _read_engines(self, fresh=False):
        if self._engines_reading:
            self._engines_again = self._engines_again or fresh
            return
        self._engines_reading = True
        self.run('engines', read_engines)

    def on_engines(self, tag, result):
        self._engines_reading = False
        result = result if isinstance(result, dict) else {}
        self._engines = dict(result.get('engines') or {}) if result.get('status') == 'ok' else {}
        self.update(compat=self._compat_rows())
        if self._engines_again:                      # started before a job ended: read once more
            self._engines_again = False
            self._read_engines()
            return
        for request in self._requests.values():
            request.pop('await_engines', None)
        self._settle()

    def on_health(self, tag, result):
        result = result if isinstance(result, dict) else {'error': 'shape'}
        scanning = bool(result.get('scanning'))
        report = result.get('report')
        fields = {'updates_loading': False, 'updates_scanning': scanning}
        if 'error' in result:
            fields.update(updates_failed=True, updates_error=self._why(result['error']), updates=[],
                          updates_checked=False)
        elif isinstance(report, dict):
            updates = report.get('updates') if isinstance(report.get('updates'), dict) else {}
            checked = bool(updates.get('checked'))
            names = [str(n).strip() for n in (updates.get('apps') or []) if str(n).strip()] if checked else []
            fields.update(updates_failed=False, updates_error='', updates=names[:40], updates_checked=checked,
                          updates_report=True, updates_at=str(report.get('generated_at') or ''))
        else:                                        # no daily check has run on this machine yet
            fields.update(updates_failed=False, updates_error='', updates_checked=False, updates_report=False,
                          updates=[], updates_at='')
        if scanning:
            if self._health_polls < HEALTH_MAX_POLLS:   # follow a running check to its end
                self._health_polls += 1
                self._health_timer.start(HEALTH_FAST_MS if self._health_polls <= HEALTH_FAST_POLLS else HEALTH_SLOW_MS)
            else:                                    # longer than moos-health may run: stop claiming it
                self._health_polls = 0
                fields.update(updates_scanning=False, updates_note='apps_check_slow')
        else:
            self._health_polls = 0
            fields['updates_note'] = ''
        self.update(**fields)

    def _read_health(self):
        self.run('health', moai_tools.get, '/health', 20)

    def _arm(self):
        return _is_arm() or self._scan_arch.lower() in ('aarch64', 'arm64')

    def _ready(self, key):
        """Read from the machine; an unknown answer is never 'ready'."""
        if key == 'games':
            if self._have is not None and STEAM in self._have:
                return True
            return (self._have is None or self._partial) and bool(self._scan_compat.get('steam'))
        if key in ENGINE_KEYS:
            return bool((self._engines or {}).get(key, {}).get('ready'))
        if key == 'phone':
            return phone_native()
        return bool(self._scan_compat.get('kvm'))

    def _row_state(self, key, tool, known):
        """ready | setup | unavailable | checking | unknown."""
        if key in ENGINE_KEYS:
            if self._engines is None:
                return 'checking'
            engine = self._engines.get(key)
            if engine is None:
                return 'unknown'
            if engine['ready']:
                return 'ready'
            # A runtime that is installed but needs its one-time download; for Windows programs
            # also an edition that ships none (then the isolated space is the only way).
            offer = engine['needs_setup'] or (key == 'windows' and not engine['present'] and engine['provision'])
            return 'setup' if offer and tool in known else 'unavailable'
        if self._ready(key):
            return 'ready'
        if key == 'games' and tool in known:
            return 'setup'
        return 'unavailable'

    def _compat_rows(self):
        """The hub, from the scan, the resolver, the installed list and the waiting cards.
        Empty until a scan answered."""
        if not self._scan_compat:
            return []
        known = moai_tools.names()
        pending = self._state.get('pending') or {}
        have = self._have or set()
        rows = []
        for key, glyph, title, detail, tool, _setup in COMPAT:
            if key in X86_ONLY and self._arm():
                continue
            state = self._row_state(key, tool, known)
            engine = (self._engines or {}).get(key) or {}
            opens, sheet = '', ''
            if key == 'games' and state == 'ready' and (STEAM in have or self._partial or self._have is None):
                opens = STEAM
            elif key == 'windows' and state == 'ready' and engine.get('chosen') in have:
                opens = engine['chosen']                     # the isolated space is an app of its own
            elif key == 'phone' and state == 'ready':
                opens, sheet = PHONE_APP, 'connect'
            if key == 'vm' and state != 'ready':
                detail = 'apps_c_vm_off'
            elif key == 'windows' and state == 'ready' and not engine.get('sandboxed'):
                detail = 'apps_c_windows_ready_d'
            elif key == 'android' and state == 'ready':
                detail = 'apps_c_android_ready_d'
            elif key == 'phone' and state != 'ready':
                detail = 'apps_c_phone_missing'
            rows.append({'key': key, 'glyph': glyph, 'title': title, 'detail': detail, 'state': state, 'tool': tool,
                         'privileged': bool(tool) and (moai_tools.meta(tool) or {}).get('category') == 'privileged_confirm',
                         'opens': opens, 'sheet': sheet, 'waiting': pending.get(key, '')})
        return rows

    def _set_pending(self, pending):
        self.update(pending=pending)
        self.update(compat=self._compat_rows())

    def _theme_icon(self, app_id):
        try:
            from PySide6.QtGui import QIcon
            return 'image://icon/' + app_id if QIcon.hasThemeIcon(app_id) else ''
        except Exception:
            return ''

    # ── the store ───────────────────────────────────────────────────────
    @Slot(str)
    def search(self, query):
        query = ' '.join(str(query or '').split())[:80]
        if not query:
            self.clearSearch()
            return
        self.update(query=query, searching=True, search_failed=False, search_error='')
        self.run('search:' + query, moai_tools.search_apps, query, 12)

    @Slot()
    def clearSearch(self):
        self.update(query='', searching=False, searched=False, results=[], search_failed=False, search_error='',
                    source='')

    def on_search(self, tag, result):
        query = tag.split(':', 1)[1] if ':' in tag else ''
        if query != self._state.get('query'):
            return                                   # an older search answered after a newer one
        result = result if isinstance(result, dict) else {}
        if result.get('status') != 'ok':
            why = self._why(result.get('error'))
            if why == self.text('apps_err_store_down'):
                why = ''                             # "the store search did not answer" already says it
            self.update(searching=False, searched=True, results=[], search_failed=True, search_error=why)
            return
        results = []
        for app in result.get('apps') or []:
            if not isinstance(app, dict) or not valid_id(app.get('id')):
                continue
            remote = str(app.get('icon') or '')
            try:
                installs = int(app.get('installs') or 0)
            except (TypeError, ValueError):
                installs = 0
            row = self._mark({
                'id': app['id'], 'name': str(app.get('name') or app['id']), 'summary': str(app.get('summary') or ''),
                'verified': bool(app.get('verified')), 'installs': installs, 'store_installed': bool(app.get('installed')),
                'recommended': bool(app.get('recommended')), 'note': local(app.get('note'), self.lang),
            })
            row['icon'] = (self._theme_icon(app['id']) if row['installed'] else '') or (remote if FLATHUB_ICON.fullmatch(remote) else '')
            results.append(row)
        self.update(searching=False, searched=True, results=results, search_failed=False, search_error='',
                    source=str(result.get('source') or ''))

    @Slot(str)
    def askMira(self, query):
        """No store result: the owner hands the need to Mira, who can search by meaning (his click)."""
        query = ' '.join(str(query or '').split())[:120]
        if not query:
            return
        self.host.send(('ابحثي لي في المتجر عن تطبيق: ' if self.lang != 'en' else 'Find me an app in the store for: ') + query)
        self.host.showSheet.emit('')

    @Slot(str)
    def showPage(self, name):
        """Send the owner to another Mira page (only the ones this page links to)."""
        if name in SHEETS:
            self.host.showSheet.emit(name)

    # ── changes: each one a card the owner approves ─────────────────────
    def _name_of(self, key):
        if key == PHONE_APP:
            return self.text('apps_phone_app')
        for source in ('results', 'installed', 'recommended'):
            for app in self._state.get(source) or []:
                if app.get('id') == key and app.get('name'):
                    return app['name']
        row = next((r for r in COMPAT if r[0] == key), None)
        if row is not None:
            return self.text(row[2])
        return RECOMMENDED.get(key, (key,))[0]

    def _busy(self, key):
        """A request blocks a second card only while its card can still be waiting, or its job runs.
        Past the card's lifetime (cancelled or expired, when the controller did not say) it is dropped."""
        request = self._requests.get(key)
        if request is None:
            return False
        if request.get('running') or (request.get('shown') and time.monotonic() - request['at'] < CARD_WAIT_S):
            return True
        self._forget(key)
        return False

    def _ask(self, name, args, detail, key=None, verb=None):
        """Put one system change in front of the owner; remember what it is about."""
        if name not in moai_tools.names():
            self.host.toast.emit('error', self.text('apps_card_refused'))
            return None
        card = self.host.request_confirmation({'kind': 'moai', 'name': name, 'args': dict(args), 'detail': detail,
                                               'origin': 'apps'})
        if not card:
            self.host.toast.emit('error', self.text('apps_card_refused'))
            return None
        if key:
            self._requests[key] = {'verb': verb or name, 'card': card.get('id', ''), 'at': time.monotonic(),
                                   'shown': True}
            self._set_pending({**self._state['pending'], key: verb or name})
            if not self._poll.isActive():
                self._poll.start()
        return card

    @Slot(str)
    def install(self, app_id):
        if not valid_id(app_id):
            self.host.toast.emit('error', self.text('apps_bad_id'))
            return
        if self._busy(app_id):
            return
        where = 'apps_install_local' if self._state.get('source') == 'local' and any(
            r.get('id') == app_id for r in self._state.get('results') or []) else 'apps_install_store'
        self._ask('install_app', {'app_id': app_id}, f'{self._name_of(app_id)} · {app_id}\n{self.text(where)}',
                  app_id, 'install')

    @Slot(str)
    def remove(self, app_id):
        if not valid_id(app_id):
            self.host.toast.emit('error', self.text('apps_bad_id'))
            return
        if self._scopes.get(app_id) == 'system':
            self.host.toast.emit('info', self.text('apps_system_no_remove'))
            return
        if self._busy(app_id):
            return
        self._ask('uninstall_app', {'app_id': app_id},
                  f"{self._name_of(app_id)} · {app_id}\n{self.text('apps_remove_detail')}", app_id, 'remove')

    @Slot(str)
    def openApp(self, app_id):
        if not valid_id(app_id):
            self.host.toast.emit('error', self.text('apps_bad_id'))
            return
        if self._state['pending'].get(app_id) == 'open':
            return
        self.update(pending={**self._state['pending'], app_id: 'open'})
        self.run('open:' + app_id, moai_tools.execute, 'open_app', {'app_id': app_id})

    def on_open(self, tag, result):
        app_id = tag.split(':', 1)[1]
        self.update(pending={k: v for k, v in self._state['pending'].items() if not (k == app_id and v == 'open')})
        result = result if isinstance(result, dict) else {}
        name = self._name_of(app_id)
        if result.get('status') == 'ok':
            self.host.toast.emit('ok', f"{self.text('apps_opened')} {name}")
        elif result.get('status') == 'confirm':
            self._ask('open_app', {'app_id': app_id}, f'{name} · {app_id}')
        else:
            reason = str(result.get('output') or self._why(result.get('error')) or '').strip().splitlines()
            self.host.toast.emit('error', self.text('apps_open_failed') + (f': {reason[-1][:100]}' if reason else ''))

    @Slot()
    def updateAll(self):
        if self._busy('__updates__'):
            return
        waiting = self._state.get('updates') or []
        detail = self.text('apps_update_detail')
        if waiting:
            joined = ('، ' if self.lang != 'en' else ', ').join(waiting[:6]) + ('…' if len(waiting) > 6 else '')
            detail += f" — {self.text('apps_update_detail_waiting')} {joined}"
        self._ask('update_apps', {}, detail, '__updates__', 'update')

    @Slot()
    def checkUpdates(self):
        """Run MoOS's read-only daily check now (the owner's click), then follow it to its end."""
        if self._state.get('updates_scanning'):
            return
        self.update(updates_scanning=True, updates_failed=False, updates_error='', updates_note='')
        self.run('checkstart', moai_tools.post, '/health/scan', {}, 20)

    def on_checkstart(self, tag, result):
        result = result if isinstance(result, dict) else {'error': 'shape'}
        if 'error' in result:
            self.update(updates_scanning=False, updates_failed=True, updates_error=self._why(result['error']))
            return
        self._health_polls = 0
        self._health_timer.start(HEALTH_FAST_MS)

    @Slot(str)
    def installRecommended(self, app_id):
        self.install(app_id)

    @Slot()
    def installAllRecommended(self):
        missing = [r['id'] for r in self._state.get('recommended') or [] if not self._busy(r['id'])]
        if not missing:
            return
        if 'smart_setup' in moai_tools.names():
            joined = ('، ' if self.lang != 'en' else ', ').join(self._name_of(a) for a in missing)
            card = self._ask('smart_setup', {}, f"{self.text('apps_rec_detail')} {joined}")
            if card:
                for app_id in missing:
                    self._requests[app_id] = {'verb': 'install', 'card': card.get('id', ''), 'at': time.monotonic(),
                                              'shown': True}
                self._set_pending({**self._state['pending'], **{a: 'install' for a in missing}})
                self._poll.start()
            return
        for app_id in missing:        # one card each: the owner approves exactly what he wants
            self.install(app_id)

    @Slot(str)
    def setup(self, key):
        row = next((r for r in COMPAT if r[0] == key), None)
        if row is None or not row[4] or (key in X86_ONLY and self._arm()) or self._busy(key):
            return
        if self._row_state(key, row[4], moai_tools.names()) != 'setup':
            return                                   # ready, unavailable or unknown: nothing to set up
        self._ask(row[4], {}, self.text(row[5]), key, 'setup')

    # ── a program that arrived as a file ────────────────────────────────
    @Slot('QVariantList')
    def installDropped(self, urls):
        """Several files dropped at once: the first goes to the installer, and the page says so."""
        urls = [str(u.toString() if isinstance(u, QUrl) else u) for u in (urls or [])]
        if not urls:
            return
        self.installFile(urls[0])
        if len(urls) > 1 and self._state.get('file_tone') == 'pending':
            self.update(file_status=f"{self._state['file_status']} · {self.text('apps_file_more')}")

    @Slot(str)
    def installFile(self, url):
        url = str(url or '')
        path = Path(QUrl(url).toLocalFile() if url.startswith('file:') else url).expanduser()
        home = Path.home().resolve()
        if path.is_symlink():                        # moos-open refuses a link; say it before it does
            self.update(file_status=self.text('apps_file_link'), file_tone='error')
            return
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path
        head = b''
        if resolved.is_file() and home in resolved.parents:
            try:
                with open(resolved, 'rb') as handle:
                    head = handle.read(4)
            except OSError:
                head = b''
        if not head:
            self.update(file_status=self.text('apps_file_outside'), file_tone='error')
            return
        try:
            owned = resolved.stat().st_uid == os.getuid()
        except OSError:
            owned = False
        if not owned:
            self.update(file_status=self.text('apps_file_not_yours'), file_tone='error')
            return
        rpm = head == RPM_MAGIC            # what the file IS decides; App Drop checks everything again
        if rpm and not any((home / folder) in resolved.parents for folder in RPM_FOLDERS):
            self.update(file_status=self.text('apps_file_rpm_folder'), file_tone='error')
            return
        if rpm and resolved.suffix != '.rpm':
            self.update(file_status=self.text('apps_file_rpm_name'), file_tone='error')
            return
        try:
            route = moos_routes.file_route('install-rpm' if rpm else 'install-file', str(resolved))
        except ValueError:
            self.update(file_status=self.text('apps_file_outside'), file_tone='error')
            return
        if not moos_routes.allowed(route):
            self.update(file_status=self.text('apps_file_long'), file_tone='error')
            return
        result = moos_routes.open_route(route)
        if result.get('status') == 'ok':
            # Known: the installer was handed the file. Not known: what the owner answers there.
            self.update(file_status=f"{self.text('apps_file_sent_rpm' if rpm else 'apps_file_sent')} — {resolved.name}",
                        file_tone='pending')
        else:
            reason = self._why(result.get('error'))
            self.update(file_status=self.text('apps_file_failed') + (f' — {reason}' if reason else ''), file_tone='error')

    @Slot()
    def openStore(self):
        result = moos_routes.open_route('moos://app/store')
        if result.get('status') != 'ok':
            reason = self._why(result.get('error'))
            self.host.toast.emit('error', 'Mo Store' + (f': {reason}' if reason else ''))

    # ── following what the owner approved, on the machine's own read-back ─
    def _watch(self):
        now = time.monotonic()
        for key, request in list(self._requests.items()):
            if now - request['at'] > WATCH_S or (request['verb'] == 'update' and not request.get('running')
                                                 and now - request['at'] > CARD_WAIT_S):
                self._forget(key)
        if not self._requests:
            self._poll.stop()
            return
        self.run('installed:watch', read_installed)
        if any(k in ENGINE_KEYS for k in self._requests):
            self._read_engines()

    def _settle(self):
        """A read came back: every request it answers is over, and is told as it is."""
        if self._have is None:
            return
        now = time.monotonic()
        for key, request in list(self._requests.items()):
            verb = request['verb']
            done = ((verb == 'install' and key in self._have)
                    or (verb == 'remove' and key not in self._have and not self._partial)
                    or (verb == 'setup' and self._ready(key)))
            if done:
                self._forget(key)
                word = {'install': 'apps_now_installed', 'remove': 'apps_now_removed'}.get(verb, 'apps_ready')
                self.host.toast.emit('ok', f'{self._name_of(key)} · {self.text(word)}')
            elif request.get('ended') and not request.get('await_engines'):
                # The job ended "ok" and the machine still shows no change: say so, stop following.
                self._forget(key)
                self.host.toast.emit('info', f"{self._name_of(key)} · {self.text('apps_not_done')}")
            elif request.get('shown') and now - request['at'] > CARD_WAIT_S:
                # The card cannot be waiting any more: approved (its card follows the job) or expired.
                # Keep following quietly on the installed list, and stop claiming anything here.
                request['shown'] = False
                self._set_pending({k: v for k, v in self._state['pending'].items() if k != key})

    def _forget(self, key):
        self._requests.pop(key, None)
        self._set_pending({k: v for k, v in self._state['pending'].items() if k != key})

    def action_changed(self, action_id, name, stage):
        """The controller tells every page how a card moved on: running | ok | error | cancelled | expired.
        Cards this page did not ask for are ignored."""
        keys = [k for k, r in self._requests.items() if action_id and r.get('card') == action_id]
        if not keys:
            return
        if stage == 'running':
            for key in keys:
                self._requests[key].update(running=True, shown=False)
            self._set_pending({**self._state['pending'], **{k: 'running' for k in keys}})
            return
        if stage != 'ok':
            for key in keys:
                self._forget(key)
            if stage == 'error':
                self.host.toast.emit('error', self.text('apps_not_done'))
            return
        if '__updates__' in keys:
            self._forget('__updates__')
            self.checkUpdates()
        for key in keys:
            if key in self._requests:
                # a set-up the resolver answers is judged on its answer, not on the installed list
                self._requests[key].update(running=False, ended=True, await_engines=key in ENGINE_KEYS)
        # the machine's own lists decide what changed
        if any(k in ENGINE_KEYS for k in keys):
            self._read_engines(fresh=True)
        self.run('installed:read', read_installed)
        if 'games' in keys:
            self.run('scan', moai_tools.get, '/scan', 25)

    # ── review renders (MIRA_TEST_MODE only): visibly sample data ───────
    def review(self):
        ar = self.lang != 'en'
        installed = [
            {'id': 'com.valvesoftware.Steam', 'name': 'Steam', 'version': '1.0.0.87', 'scope': 'user'},
            {'id': 'com.usebottles.bottles', 'name': 'Bottles', 'version': '67.3', 'scope': 'user'},
            {'id': 'com.visualstudio.code', 'name': 'Visual Studio Code', 'version': '1.139.1', 'scope': 'user'},
            {'id': 'com.google.Chrome', 'name': 'Google Chrome', 'version': '154.0', 'scope': 'user'},
            {'id': 'org.telegram.desktop', 'name': 'Telegram Desktop (sample)', 'version': '6.1.3', 'scope': 'user'},
            {'id': 'org.kde.kdenlive', 'name': 'Kdenlive', 'version': '25.08.1', 'scope': 'system'},
            {'id': 'org.gimp.GIMP', 'name': 'GIMP', 'version': '3.0.4', 'scope': 'user'},
            {'id': 'com.spotify.Client', 'name': 'Spotify', 'version': '1.2.63', 'scope': 'user'},
        ]
        for app in installed:
            app['icon'] = self._theme_icon(app['id'])
        self._scopes = {a['id']: a['scope'] for a in installed}
        results = [
            {'id': 'org.kde.kdenlive', 'name': 'Kdenlive', 'summary': 'Video editor', 'verified': True, 'installs': 61230,
             'installed': True, 'store_installed': True, 'scope': 'system', 'recommended': True,
             'icon': self._theme_icon('org.kde.kdenlive'),
             'note': 'محرّر فيديو أصلي لسطح MoOS' if ar else 'A video editor native to the MoOS desktop'},
            {'id': 'org.shotcut.Shotcut', 'name': 'Shotcut', 'summary': 'Video editor (sample)', 'verified': True,
             'installs': 38412, 'installed': False, 'store_installed': False, 'scope': '', 'recommended': False,
             'icon': '', 'note': ''},
            {'id': 'org.openshot.OpenShot', 'name': 'OpenShot Video Editor', 'summary': 'Create and edit videos and movies',
             'verified': False, 'installs': 20110, 'installed': False, 'store_installed': False, 'scope': '',
             'recommended': False, 'icon': '', 'note': ''},
        ]
        recommended = [{'id': app_id, 'name': RECOMMENDED[app_id][0], 'glyph': RECOMMENDED[app_id][1],
                        'why_ar': RECOMMENDED[app_id][2], 'why_en': RECOMMENDED[app_id][3]}
                       for app_id in ('org.mozilla.firefox', 'org.libreoffice.LibreOffice', 'com.github.tchx84.Flatseal')]
        self._scan_compat = {'steam': True, 'waydroid': True, 'kvm': True}
        states = {'games': 'ready', 'windows': 'ready', 'android': 'setup', 'phone': 'ready', 'vm': 'ready'}
        compat = []
        for key, glyph, title, detail, tool, _setup in COMPAT:
            state = states[key]
            compat.append({'key': key, 'glyph': glyph, 'title': title, 'detail': detail, 'state': state, 'tool': tool,
                           'privileged': key == 'android',
                           'opens': {'games': STEAM, 'windows': 'com.usebottles.bottles', 'phone': PHONE_APP}.get(key, ''),
                           'sheet': 'connect' if key == 'phone' else '',
                           'waiting': 'running' if key == 'android' else ''})
        self.update(query='مونتاج فيديو' if ar else 'video editor', searching=False, searched=True, results=results,
                    search_failed=False, search_error='', source='flathub',
                    installed=installed, installed_loading=False, installed_failed=False, installed_error='',
                    installed_read=True, installed_partial=False,
                    updates=['Telegram Desktop', 'Google Chrome', 'Spotify'], updates_checked=True, updates_report=True,
                    updates_at=time.strftime('%Y-%m-%dT%H:%M:%S+00:00', time.gmtime(time.time() - 2 * 3600)),
                    updates_loading=False, updates_failed=False, updates_error='', updates_scanning=False,
                    updates_note='',
                    recommended=recommended, scan_loading=False, scan_failed=False, scan_error='', scanned=True,
                    plan_pending=False, compat=compat, arch='x86_64', smart_setup=False,
                    pending={'org.shotcut.Shotcut': 'install', 'android': 'running'},
                    file_status='', file_tone='')


PAGE = AppsPage
