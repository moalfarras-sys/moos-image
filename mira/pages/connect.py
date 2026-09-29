"""Connect: every way to reach this computer, and Mira, away from the desk.

Mo PC Remote (the phone drives this PC), Mira on the phone (the companion, read from the controller),
the phone link (the image's own KDE Connect, which MoOS names «الهاتف» / Phone), the message channels
Mo AI's agent answers on (Telegram, WhatsApp) and the Echo speaker (read from the controller).

Every state on the page is read back from its backend:
- Mo PC Remote: moai-control /quick `remote` and the Fast Remote journal file moos-fast-remote keeps.
  When the installed schemas declare `remote_control` / `fast_remote`, a click goes to their executor:
  what the schema confirms (remote on and off, fast on) is an owner card, the rest (restart, fast
  off) runs at once, and the executor's exit status is the result. On an image without those tools
  the click falls back to moos-open's fixed routes (their own MoOS dialog) and read-backs decide.
- channels: the agent's secret-free /api/config (never /api/channels: reading that starts a service);
- the phone link: the image's desktop entry, the running daemon and its own device list.
A system change (reach from outside home, installing the messaging agent) is an owner card, never a
call. The phone link is never installed from here: it is part of the edition that carries it (there
is no store package of it), so an edition without it says so. A card's end reaches the page through `action_changed` when the controller
reports it; without that report a card is followed for its lifetime and then let go, never claimed.
Every note ages: a result goes after NOTE_S, a failure after ERROR_NOTE_S, a pending note with the
process it describes, and a remote note as soon as a read disagrees with it.
"""
import os
import re
import subprocess
import time
from pathlib import Path

from PySide6.QtCore import QTimer, Slot

import moai_agent
import moai_tools
import moos_routes
from pages import base
from pages.base import Page

STRINGS = {
    'cn_sub': ('تحكّم بالكمبيوتر من هاتفك، وخذ ميرا معك، وتابع سماعة Echo في الغرفة',
               'Drive this PC from your phone, take Mira with you, and check on the Echo in the room'),
    'cn_reading': ('أقرأ الحالة…', 'Reading…'),
    'cn_unknown': ('الحالة غير معروفة', 'State unknown'),
    'cn_err_control': ('خدمة أدوات MoOS لا تجيب', "MoOS's tools service is not answering"),
    'cn_err_agent': ('وكيل الرسائل لا يجيب', 'The messaging service is not answering'),
    'cn_err_read': ('تعذّرت قراءة الحالة', 'Could not read the state'),
    'cn_err_route': ('نسخة MoOS هذه لا تقدّم هذا الإجراء', 'This MoOS does not offer that action'),
    'cn_err_router': ('أداة فتح روابط MoOS غير موجودة', "MoOS's link opener is missing"),
    'cn_err_busy': ('عملية أخرى ما زالت تعمل؛ جرّب بعد انتهائها', 'Another task is still running; try again when it ends'),
    'cn_route_failed': ('تعذّر إرسال الأمر', 'Could not send the command'),
    'cn_open_failed': ('تعذّر فتح تطبيق «الهاتف»', 'Could not open the Phone app'),
    'cn_opening': ('أفتح…', 'Opening…'),
    'cn_working': ('أنفّذ…', 'Working…'),
    'cn_card_failed': ('تعذّر عرض بطاقة الموافقة: نسخة MoOS هذه لا تقدّم هذا الإجراء',
                       'Could not show the approval card: this MoOS does not offer that action'),
    'cn_card_waiting': ('بانتظار موافقتك على البطاقة', 'Waiting for your approval on the card'),
    'cn_card_running': ('وافقت؛ MoOS ينفّذ الآن…', 'Approved; MoOS is doing it now…'),
    'cn_card_cancelled': ('أُلغيت البطاقة، ولم يتغيّر شيء', 'The card was cancelled; nothing changed'),
    'cn_card_expired': ('انتهت مهلة البطاقة دون جواب، ولم يتغيّر شيء', 'The card expired without an answer; nothing changed'),
    'cn_not_done': ('لم يتمكّن MoOS من التنفيذ، والتفاصيل في قائمة إجراءات ميرا',
                    "MoOS could not do it; the details are in Mira's action list"),
    'cn_not_done_direct': ('لم يتمكّن MoOS من التنفيذ', 'MoOS could not do it'),
    'cn_stop_waiting': ('توقّف عن الانتظار', 'Stop waiting'),

    # Mo PC Remote
    'cn_remote_sub': ('شاشة الكمبيوتر وفأرته ولوحة مفاتيحه وحافظته على هاتفك',
                      "This PC's screen, mouse, keyboard and clipboard on your phone"),
    'cn_running': ('يعمل', 'Running'),
    'cn_stopped': ('متوقف', 'Stopped'),
    'cn_screen': ('بث الشاشة', 'Screen stream'),
    'cn_permission': ('إذن مشاركة الشاشة', 'Screen-share permission'),
    'cn_fast_state': ('الاتصال السريع مفعّل', 'Fast mode on'),
    'cn_start': ('تشغيل', 'Start'),
    'cn_stop': ('إيقاف', 'Stop'),
    'cn_stop_confirm': ('اضغط ثانية للإيقاف', 'Press again to stop'),
    'cn_stop_warning': ('قد يكون هاتفك متصلاً الآن، والإيقاف يقطع الجلسة. اضغط الزر مرة ثانية خلال 5 ثوانٍ للتأكيد؛ '
                        'ولن يعمل تلقائياً عند الإقلاع التالي.',
                        'Your phone may be connected right now, and stopping ends that session. '
                        'Press the button again within 5 seconds to confirm. It will also not start at the next boot.'),
    'cn_card_start': ('يشغّل Mo PC Remote: يستطيع هاتفك المقترن التحكم بهذا الكمبيوتر، ويبقى يعمل بعد كل إقلاع.',
                      'Starts Mo PC Remote: your paired phone can control this computer, and it keeps running '
                      'after every restart.'),
    'cn_card_stop': ('يوقف Mo PC Remote: ينقطع أي هاتف يتحكم بهذا الكمبيوتر الآن، ولن يعمل تلقائياً عند الإقلاع التالي.',
                     'Stops Mo PC Remote: any phone controlling this computer right now is disconnected, '
                     'and it will not start at the next boot.'),
    'cn_restart': ('إعادة تشغيل', 'Restart'),
    'cn_fast_on': ('تفعيل الاتصال السريع', 'Turn on fast mode'),
    'cn_fast_off': ('إيقاف الاتصال السريع', 'Turn off fast mode'),
    'cn_fast_hint': ('يوقف الضبابية والحركة والرسوم المتحركة، ويبدّل لوحة المفاتيح إلى US ويعلّق العقل المحلي، '
                     'حتى تطفئه فيعود كل شيء كما كان.',
                     'Pauses blur, motion and animations, switches the keyboard to US and suspends the local brain '
                     'until you turn it off, which restores everything as it was.'),
    'cn_fast_now': ('الاتصال السريع يعمل: الضبابية والحركة متوقفة، ولوحة المفاتيح على US، والعقل المحلي معلّق حتى تطفئه.',
                    'Fast mode is on: blur and motion are paused, the keyboard is on US and the local brain is '
                    'suspended until you turn it off.'),
    'cn_open_remote': ('فتح Mo PC Remote', 'Open Mo PC Remote'),
    'cn_remote_settings': ('الإعدادات', 'Settings'),
    'cn_anywhere': ('الوصول من خارج البيت', 'Reach it from outside home'),
    'cn_anywhere_detail': ('يعطي هذا الكمبيوتر اسماً وشهادة HTTPS على شبكة Tailscale الخاصة بك، فيعمل Mo PC Remote '
                           'من بيانات الجوال. لا يُنشر شيء على الإنترنت العام: الوصول لأجهزتك فقط. '
                           'يحتاج Tailscale متصلاً، ويطلب كلمة المرور مرة واحدة.',
                           'Gives this PC an HTTPS name on your private Tailscale network, so Mo PC Remote works '
                           'on mobile data. Nothing is published to the public internet: only your devices reach it. '
                           'Tailscale must be connected, and it asks for your password once.'),
    'cn_anywhere_done': ('تمّ: صار لهذا الكمبيوتر عنوان HTTPS على شبكتك في Tailscale، والعنوان في تفاصيل البطاقة',
                         "Done: this PC has an HTTPS name on your Tailscale network; the address is in the card's details"),
    'cn_wait_dialog': ('أكّد في نافذة MoOS التي فُتحت، ثم أقرأ الحالة…', 'Confirm in the MoOS window that opened; then I read the state…'),
    'cn_wait_readback': ('أُرسل الأمر، أقرأ الحالة…', 'Sent; reading the state back…'),
    'cn_done_running': ('تأكدت: Mo PC Remote يعمل', 'Confirmed: Mo PC Remote is running'),
    'cn_done_stopped': ('تأكدت: Mo PC Remote متوقف', 'Confirmed: Mo PC Remote is stopped'),
    'cn_done_restarted': ('أُرسلت إعادة التشغيل، والخدمة تعمل', 'Restart sent; the service is running'),
    'cn_done_restarted_tool': ('تأكدت: أُعيد تشغيل Mo PC Remote وهو يعمل', 'Confirmed: Mo PC Remote restarted and is running'),
    'cn_done_fast_on': ('تأكدت: الاتصال السريع مفعّل', 'Confirmed: fast mode is on'),
    'cn_done_fast_off': ('تأكدت: عادت المؤثرات ولغة لوحة المفاتيح كما كانت', 'Confirmed: effects and keyboard layout are restored'),
    'cn_not_confirmed': ('لم تتغيّر الحالة: ربما أُلغي التأكيد أو تعذّر التنفيذ',
                         'The state did not change: the confirmation may have been cancelled, or the action failed'),

    # the phone link
    'cn_phone': ('ربط الهاتف', 'Phone link'),
    'cn_phone_sub': ('الإشعارات والملفات والحافظة بين هاتفك وهذا الكمبيوتر، في تطبيق «الهاتف»',
                     'Notifications, files and the clipboard between your phone and this PC, in the Phone app'),
    'cn_phone_builtin': ('مدمج في MoOS', 'Built into MoOS'),
    'cn_phone_local': ('مثبّت على هذا الكمبيوتر', 'Installed on this PC'),
    'cn_phone_missing': ('ليس في هذه النسخة', 'Not in this edition'),
    'cn_phone_missing_note': ('نسخة MoOS هذه لا تحمل ربط الهاتف.', 'This MoOS edition has no phone link.'),
    'cn_phone_paired': ('مقترن', 'Paired'),
    'cn_phone_reachable': ('متصل الآن', 'Connected now'),
    'cn_phone_away': ('بعيد الآن', 'Out of reach'),
    'cn_phone_unpaired': ('غير مقترن', 'Not paired'),
    'cn_phone_none': ('لا يوجد هاتف مقترن بعد. ثبّت KDE Connect على هاتفك، ثم اقترن من تطبيق «الهاتف».',
                      'No phone is paired yet. Install KDE Connect on your phone, then pair from the Phone app.'),
    'cn_phone_daemon_off': ('خدمة الربط لا تعمل؛ افتح تطبيق «الهاتف» لتشغيلها.',
                            'The link service is not running; opening the Phone app starts it.'),
    'cn_phone_devices_unknown': ('قائمة الهواتف تظهر داخل تطبيق «الهاتف».', 'Your phones are listed inside the Phone app.'),
    'cn_open_phone': ('فتح «الهاتف»', 'Open Phone'),
    'cn_ring': ('رنّ الهاتف', 'Ring it'),
    'cn_ring_sent': ('طُلب الرنين على', 'Ring requested on'),
    'cn_ring_failed': ('تعذّر الرنين على', 'Could not ring'),

    # message channels
    'cn_channels': ('قنوات الرسائل', 'Message channels'),
    'cn_channels_sub': ('ميرا تجيبك من تيليجرام وواتساب، بنفس أدواتها وقواعد الموافقة',
                        'Mira answers you on Telegram and WhatsApp, with the same tools and approval rules'),
    'cn_telegram': ('تيليجرام', 'Telegram'),
    'cn_whatsapp': ('واتساب', 'WhatsApp'),
    'cn_on': ('مفعّل', 'On'),
    'cn_off': ('متوقف', 'Off'),
    'cn_not_set': ('غير مُعدّ', 'Not set up'),
    'cn_tg_token_saved': ('البوت محفوظ ومتوقف', 'Bot saved, turned off'),
    'cn_tg_none': ('أنشئ بوتاً من BotFather وضع رمزه في الإعدادات.', 'Create a bot with BotFather and put its token in Settings.'),
    'cn_policy_pairing': ('يقبل من يقترن برمز فقط', 'Accepts only who pairs with a code'),
    'cn_policy_allow': ('يقبل حسابات قائمة السماح فقط (%1)', 'Answers only the accounts on its allow list (%1)'),
    'cn_wa_link': ('اربطه مرة واحدة', 'Link it once'),
    'cn_wa_hint': ('يفتح نافذة فيها رمز QR: امسحه من واتساب ← الأجهزة المرتبطة.',
                   'Opens a window with a QR code: scan it in WhatsApp → Linked devices.'),
    'cn_wa_login': ('ربط واتساب', 'Link WhatsApp'),
    'cn_wa_opened': ('فُتحت نافذة الربط: امسح الرمز من واتساب ← الأجهزة المرتبطة', 'The link window opened: scan the code in WhatsApp → Linked devices'),
    'cn_agent_missing': ('يحتاج وكيل الرسائل', 'Needs the messaging agent'),
    'cn_agent_missing_note': ('واتساب يعمل عبر وكيل الرسائل، وهو غير مثبّت بعد.',
                              'WhatsApp runs through the messaging agent, which is not installed yet.'),
    'cn_agent_setup': ('تجهيز وكيل الرسائل', 'Set up the messaging agent'),
    'cn_agent_detail': ('يثبّت وكيل الرسائل الذي تجيبك ميرا عبره من واتساب وتيليجرام.',
                        'Installs the messaging agent Mira answers you through on WhatsApp and Telegram.'),
    'cn_agent_running': ('وافقت؛ أثبّت وكيل الرسائل…', 'Approved; installing the messaging agent…'),
    'cn_agent_done': ('تأكدت: وكيل الرسائل مثبّت', 'Confirmed: the messaging agent is installed'),
    'cn_setup': ('إعداد القنوات', 'Set up channels'),

    # the Echo
    'cn_echo': ('سماعة Echo', 'Echo speaker'),
    'cn_echo_sub': ('أذنا ميرا وصوتها في الغرفة', "Mira's ears and voice in the room"),
    'cn_online': ('متصلة', 'Online'),
    'cn_offline': ('غير متصلة', 'Offline'),
    'cn_unpaired': ('لا Echo مقترنة', 'No Echo paired'),
    'cn_volume': ('صوت السماعة', 'Speaker volume'),
    'cn_wake_threshold': ('عتبة نداء «ميرا»', 'Wake threshold'),
    'cn_wake_threshold_sub': ('الأقل يستيقظ أسهل', 'lower wakes easier'),
    'cn_mics': ('الميكروفونات', 'Microphones'),
    'cn_muted': ('مكتومة', 'Muted'),
    'cn_listening': ('تسمع', 'Listening'),
    'cn_echo_alone': ('تعمل وحدها والكمبيوتر مطفأ', 'Works on its own while the PC is off'),
    'cn_echo_settings': ('إعدادات الصوت وEcho', 'Voice & Echo settings'),
}

# Mo PC Remote. `tool` is the Mo AI tool and value that does it when the installed schemas declare
# it; `url` is moos-open's fixed route for an image that does not. `want` is the read-back that
# proves the action, `min` how many reads in a row must agree. The routes that ask the owner in a
# MoOS dialog (start, fast-on) get the time a person needs; `run` is how long the executor may take
# once the owner said yes (moos-fast-remote waits up to 30 s for another appearance change and has
# two minutes in moos-control). `card` is the card's words (fast mode: the schema's own, if any).
REMOTE = {
    'start': {'tool': ('remote_control', 'on'), 'url': 'moos://remote/start', 'key': 'active', 'want': True,
              'seconds': 90, 'run': 40, 'dialog': True, 'min': 2, 'done': 'cn_done_running',
              'done_tool': 'cn_done_running', 'card': 'cn_card_start'},
    'stop': {'tool': ('remote_control', 'off'), 'url': 'moos://remote/stop', 'key': 'active', 'want': False,
             'seconds': 20, 'run': 40, 'dialog': False, 'min': 1, 'done': 'cn_done_stopped',
             'done_tool': 'cn_done_stopped', 'card': 'cn_card_stop'},
    # try-restart keeps the service active throughout: a read-back proves "running", never
    # "restarted". Only the executor (it waits for the unit to come back) may say it restarted.
    'restart': {'tool': ('remote_control', 'restart'), 'url': 'moos://remote/restart', 'key': 'active', 'want': True,
                'seconds': 20, 'run': 40, 'dialog': False, 'min': 2, 'done': 'cn_done_restarted',
                'done_tool': 'cn_done_restarted_tool', 'card': '', 'provable': False},
    'fast-on': {'tool': ('fast_remote', 'on'), 'url': 'moos://remote/fast-on', 'key': 'fast', 'want': True,
                'seconds': 90, 'run': 150, 'dialog': True, 'min': 1, 'done': 'cn_done_fast_on',
                'done_tool': 'cn_done_fast_on', 'card': 'cn_fast_hint'},
    'fast-off': {'tool': ('fast_remote', 'off'), 'url': 'moos://remote/fast-off', 'key': 'fast', 'want': False,
                 'seconds': 20, 'run': 150, 'dialog': False, 'min': 1, 'done': 'cn_done_fast_off',
                 'done_tool': 'cn_done_fast_off', 'card': 'cn_fast_hint'},
}
STOP_WINDOW = 5.0            # seconds in which a second Stop click confirms (route fallback only)
FOLLOW_MS = 2000             # read-back interval after a remote action
CARD_WAIT = 180              # how long a card waits for the owner (controller.CONFIRM_TTL)
CARD_MARGIN = 20             # … and a little more before the page lets go of it
NOTE_S = 20                  # how long a confirmation or a neutral note stays
ERROR_NOTE_S = 60            # how long a failure stays (the next refresh clears it sooner)
INSTALL_FOLLOW = 15 * 60     # how long an approved install is followed
READ_EVERY = 15              # seconds between reads of a followed install
PHONE_APP = 'org.kde.kdeconnect.app'          # the image's own entry (named «الهاتف» / Phone)
PHONE_ENTRY = Path('/usr/share/applications') / (PHONE_APP + '.desktop')
PHONE_CLI = Path('/usr/bin/kdeconnect-cli')
DEVICE_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}')
DEVICE_LINE = re.compile(r'^- (.+): ([A-Za-z0-9][A-Za-z0-9_-]{0,79}) \(([^)]*)\)\s*$')
AGENT_TOOL = 'install_openclaw'
C_LOCALE = {'LC_ALL': 'C', 'LANG': 'C', 'LANGUAGE': 'C'}
# A code a backend answers with -> the page's word for it. Any other code is never shown raw.
ERRORS = {'moai_control_unreachable': 'cn_err_control', 'agent_unreachable': 'cn_err_agent',
          'route_not_allowed': 'cn_err_route', 'FileNotFoundError': 'cn_err_router', 'busy': 'cn_err_busy'}
# A note slot's fields: (word key, tone, what it is about). The remote's "about" is a reason word.
NOTE_SLOTS = {'remote': ('remote_note', 'remote_tone', 'remote_reason'), 'anywhere': ('anywhere_note', 'anywhere_tone'),
              'phone': ('phone_note', 'phone_tone', 'phone_about'), 'channel': ('channel_note', 'channel_tone')}
CARD_END = {'cancelled': ('cn_card_cancelled', ''), 'expired': ('cn_card_expired', '')}


# ── reads (worker threads) ────────────────────────────────────────────
def _state_home():
    return Path(os.environ.get('XDG_STATE_HOME') or Path.home() / '.local/state')


def fast_remote_on():
    """moos-fast-remote writes 'applying' into its journal first and 'on' once the profile is in
    place (and deletes the file when applying fails): only 'on' is on."""
    try:
        return (_state_home() / 'moos' / 'fast-remote.on').read_text().strip() == 'on'
    except (OSError, UnicodeDecodeError):
        return False


def read_remote():
    quick = moai_tools.get('/quick', timeout=8)
    fast = fast_remote_on()
    if not isinstance(quick, dict) or quick.get('error') or not isinstance(quick.get('remote'), dict):
        error = quick.get('error') if isinstance(quick, dict) and quick.get('error') else 'shape'
        return {'status': 'error', 'error': error, 'fast': fast}
    remote = quick['remote']
    return {'status': 'ok', 'active': bool(remote.get('active')), 'pipewire': bool(remote.get('pipewire')),
            'portal': bool(remote.get('portal')), 'fast': fast}


def agent_installed():
    path = Path.home() / '.local/bin/openclaw'
    return path.is_file() and os.access(path, os.X_OK)


def read_channels():
    """Telegram from the agent's secret-free configuration; WhatsApp needs the messaging agent installed.
    /api/channels is never read here: it starts the gateway to probe."""
    engine = agent_installed()
    config = moai_agent.get('/api/config')
    if not isinstance(config, dict) or config.get('error'):
        return {'status': 'error', 'error': (config or {}).get('error', 'shape') if isinstance(config, dict) else 'shape',
                'engine': engine}
    telegram = config.get('telegram') if isinstance(config.get('telegram'), dict) else {}
    policy = str(telegram.get('policy') or 'pairing')
    return {'status': 'ok', 'engine': engine,
            'telegram': {'enabled': bool(telegram.get('enabled')), 'has_token': bool(telegram.get('has_token')),
                         'policy': policy if policy in ('pairing', 'allowlist') else 'pairing',
                         'allowed': len(telegram.get('allow') or [])}}


def _daemon_running():
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit():
            continue
        try:
            if (entry / 'comm').read_text().strip() == 'kdeconnectd':
                return True
        except OSError:
            continue
    return False


def list_phones():
    """The phones the running link daemon knows, from its own CLI (C locale, so the words parse)."""
    try:
        out = subprocess.run([str(PHONE_CLI), '--list-devices'], capture_output=True, text=True, timeout=6,
                             env={**os.environ, **C_LOCALE}, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, type(exc).__name__
    if out.returncode != 0:
        return None, f'exit_{out.returncode}'
    devices = []
    for line in out.stdout.splitlines():
        match = DEVICE_LINE.match(line.strip())
        if match:
            words = match.group(3)
            devices.append({'id': match.group(2), 'name': match.group(1)[:60],
                            'paired': re.search(r'\bpaired\b', words) is not None,
                            'reachable': re.search(r'\breachable\b', words) is not None})
    return devices, ''


def read_phone():
    """The phone link: the image's own entry (`system`), or the same app found elsewhere on this PC
    (`local`: moai-control /scan's compatibility.kdeconnect reads its entry in every XDG data dir and
    the program on PATH). There is no store package of it, so nothing here offers an install."""
    system = PHONE_ENTRY.is_file()
    scan = moai_tools.get('/scan', timeout=30)
    scan_ok = isinstance(scan, dict) and not scan.get('error')
    local = not system and bool(((scan.get('compatibility') or {}) if scan_ok else {}).get('kdeconnect'))
    running = _daemon_running() if system else False
    devices, error = (None, '')
    if system and running and PHONE_CLI.is_file():
        devices, error = list_phones()
    return {'status': 'ok' if (scan_ok or system) else 'error',
            'error': '' if (scan_ok or system) else scan.get('error', 'shape'),
            'system': system, 'local': local, 'running': running,
            'devices': devices if devices is not None else [], 'listed': devices is not None, 'list_error': error}


def ring_phone(device_id):
    """Ring one paired phone. The CLI's own words (C locale) stay in the result, never on the page."""
    try:
        out = subprocess.run([str(PHONE_CLI), '--device=' + device_id, '--ring'], capture_output=True, text=True,
                             timeout=10, env={**os.environ, **C_LOCALE}, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {'status': 'error', 'error': type(exc).__name__}
    if out.returncode != 0:
        return {'status': 'error', 'error': (out.stderr or '').strip()[-160:] or f'exit_{out.returncode}'}
    return {'status': 'ok'}


def has_tool(name):
    """Does the installed image's executor offer this Mo AI tool?"""
    try:
        return name in moai_tools.names()
    except Exception:
        return False


class ConnectPage(Page):
    def __init__(self, host, parent=None):
        super().__init__(host, parent)
        self._pending = set()          # reads in flight (never started twice)
        self._loading = set()          # the reads of one refresh (the header's busy ring)
        self._follow = None            # the one Mo PC Remote action being followed
        self._claim = None             # (key, value) the remote note confirmed; a read that disagrees clears it
        self._cards = {}               # card id -> what it is for ('remote:<verb>', 'anywhere', 'agent')
        self._note_until = {}          # note slot -> monotonic time it goes away (0 = with its process)
        self._armed_at = 0.0
        self._agent_until = 0.0        # the messaging agent's install is followed (quietly) until then …
        self._agent_asked_until = 0.0  # … and the page says it waits until then
        self._last_channels_read = 0.0
        self._follow_timer = QTimer(self, interval=FOLLOW_MS, timeout=self._follow_tick)
        self._disarm_timer = QTimer(self, singleShot=True, interval=int(STOP_WINDOW * 1000), timeout=self._disarm)

    def initial(self):
        return {
            'loading': False,
            'remote': {'known': False, 'active': False, 'pipewire': False, 'portal': False, 'fast': False},
            'remote_error': '', 'remote_busy': '', 'remote_phase': '',
            'remote_note': '', 'remote_tone': '', 'remote_reason': '', 'stop_armed': False,
            'anywhere_note': '', 'anywhere_tone': '',
            'channels': {'known': False, 'engine': False, 'error': '',
                         'telegram': {'enabled': False, 'has_token': False, 'policy': 'pairing', 'allowed': 0}},
            'channel_note': '', 'channel_tone': '', 'agent_install': '',
            'phone': {'known': False, 'system': False, 'local': False, 'running': False, 'devices': [],
                      'listed': False, 'error': ''},
            'phone_note': '', 'phone_about': '', 'phone_tone': '', 'ringing': '',
        }

    # ── helpers ──────────────────────────────────────────────────────
    # Notes and errors are stored as word keys (QML shows mira.s[key]) so a language switch re-words
    # them. A code with no word of its own becomes a general word: raw codes never reach the owner.
    def _error_key(self, code):
        return ERRORS.get(code) or ('cn_err_read' if code else '')

    def _reason(self, code):
        """' · <word>' for a code the page knows, '' for any other."""
        return ' · ' + self.text(ERRORS[code]) if code in ERRORS else ''

    def _note(self, slot, key, tone='', about='', life=None):
        """The fields of one note, and its lifetime: a result goes by itself, a pending note with the
        process it describes (or after `life`)."""
        if life is None:
            life = 0 if (tone == 'pending' or not key) else ERROR_NOTE_S if tone == 'error' else NOTE_S
        self._note_until[slot] = time.monotonic() + life if life else 0.0
        names = NOTE_SLOTS[slot]
        fields = {names[0]: key, names[1]: tone if key else ''}
        if len(names) > 2:
            fields[names[2]] = about if key else ''
        return fields

    def _expire_notes(self, now, finished_only=False):
        """Aged notes go (poll); on a refresh every finished note goes."""
        fields = {}
        for slot, names in NOTE_SLOTS.items():
            if not self._state.get(names[0]) or (slot == 'remote' and self._follow is not None):
                continue                                 # a followed action owns its note
            if finished_only:
                gone = self._state.get(names[1]) != 'pending'
            else:
                until = self._note_until.get(slot, 0.0)
                gone = bool(until) and now > until
            if gone:
                fields.update(self._note(slot, ''))
                if slot == 'remote':
                    self._claim = None
                if slot == 'anywhere':
                    self._drop_cards('anywhere')
        if fields:
            self.update(**fields)

    def _release_waits(self, now):
        """An install whose card has outlived its lifetime is no longer waited for (nothing is claimed;
        a quiet read may still find it installed)."""
        fields = {}
        if self._state['agent_install'] and now > self._agent_asked_until:
            fields['agent_install'] = ''
            if self._state['channel_tone'] == 'pending':
                fields.update(self._note('channel', ''))
            self._drop_cards('agent')
        if fields:
            self.update(**fields)

    def _drop_cards(self, purpose):
        for card_id in [k for k, v in self._cards.items() if v == purpose]:
            self._cards.pop(card_id, None)

    def _open(self, url):
        result = moos_routes.open_route(url)
        if result.get('status') != 'ok':
            self.host.toast.emit('error', self.text('cn_route_failed') + self._reason(result.get('error')))
            return False
        return True

    def _card(self, purpose, name, args, detail):
        """One owner card for a system change: its id, or '' when the executor does not take it."""
        card = self.host.request_confirmation({'kind': 'moai', 'name': name, 'args': dict(args), 'detail': detail,
                                               'origin': 'connect'})
        card_id = str(card.get('id') or '') if isinstance(card, dict) else ''
        if card_id:
            self._cards[card_id] = purpose
        return card_id

    def _begin(self, tag, fn, *args):
        self._pending.add(tag)
        self._loading.add(tag)
        self.update(loading=True)
        self.run(tag, fn, *args)

    def _read(self, tag, fn):
        """A quiet read (no busy ring), never two of the same at once."""
        if tag in self._pending:
            return
        self._pending.add(tag)
        self.run(tag, fn)

    def _end(self, tag):
        self._pending.discard(tag)
        if tag in self._loading:
            self._loading.discard(tag)
            if not self._loading:
                self.update(loading=False)

    # ── reading ──────────────────────────────────────────────────────
    @Slot()
    def refresh(self):
        now = time.monotonic()
        self._expire_notes(now, finished_only=True)
        self._release_waits(now)
        self._begin('remote:refresh', read_remote)
        self._begin('channels', read_channels)
        self._begin('phone', read_phone)

    @Slot()
    def poll(self):
        """While the page is on screen (its QML timer): notes age, the remote's state, followed installs."""
        now = time.monotonic()
        self._expire_notes(now)
        self._release_waits(now)
        if base.TEST_MODE:
            return
        if self._follow is None:
            self._read('remote:poll', read_remote)
        if now < self._agent_until and now - self._last_channels_read >= READ_EVERY:
            self._last_channels_read = now
            self._read('channels', read_channels)

    def on_remote(self, tag, result):
        self._end(tag)
        ok = result.get('status') == 'ok'
        before = self._state['remote']
        if ok:
            remote = {'known': True, 'active': result['active'], 'pipewire': result['pipewire'],
                      'portal': result['portal'], 'fast': bool(result.get('fast'))}
            error = ''
        else:
            remote = {**before, 'known': False, 'fast': bool(result.get('fast'))}
            error = self._error_key(result.get('error'))
        fields = {}
        if remote != before or error != self._state['remote_error']:
            fields.update(remote=remote, remote_error=error)   # a poll that reads the same state repaints nothing
        follow = self._follow
        if follow is not None:
            if fields:
                self.update(**fields)
            if tag == 'remote:follow':
                self._follow_read(follow, ok, result)
            return
        if ok and self._state['remote_note']:
            # A note never contradicts the pill: a confirmed state that no longer holds, or any other
            # note once the remote or fast mode changed under it, goes at once.
            if self._claim is not None:
                stale = bool(result.get(self._claim[0])) != self._claim[1]
            else:
                stale = bool(before.get('known')) and (before['active'] != remote['active'] or before['fast'] != remote['fast'])
            if stale:
                fields.update(self._note('remote', ''))
                self._claim = None
        if fields:
            self.update(**fields)

    def _follow_read(self, follow, ok, result):
        match = ok and bool(result.get(follow['key'])) == follow['want']
        follow['hits'] = follow['hits'] + 1 if match else 0
        if follow['provable'] and follow['hits'] >= follow['min']:
            self._finish_follow(follow['done'], 'ok', claim=(follow['key'], follow['want']))
        elif time.monotonic() > follow['deadline']:
            if follow['card']:
                self._cards.pop(follow['card'], None)
            # A restart card that ran out: a read-back cannot tell, so nothing is claimed either way.
            self._finish_follow('cn_not_confirmed' if follow['provable'] else '', 'error')

    def on_channels(self, tag, result):
        self._end(tag)
        fields = {}
        if result.get('status') == 'ok':
            fields['channels'] = {'known': True, 'engine': bool(result.get('engine')), 'error': '',
                                  'telegram': result['telegram']}
        else:
            fields['channels'] = {**self._state['channels'], 'known': False, 'engine': bool(result.get('engine')),
                                  'error': self._error_key(result.get('error'))}
        if result.get('engine') and (self._state['agent_install'] or time.monotonic() < self._agent_until):
            self._agent_until = self._agent_asked_until = 0.0
            self._drop_cards('agent')
            fields.update(agent_install='', **self._note('channel', 'cn_agent_done', 'ok'))
        self.update(**fields)

    def on_phone(self, tag, result):
        self._end(tag)
        phone = {'known': result.get('status') == 'ok', 'system': bool(result.get('system')),
                 'local': bool(result.get('local')), 'running': bool(result.get('running')),
                 'devices': list(result.get('devices') or []), 'listed': bool(result.get('listed')),
                 'error': self._error_key(result.get('error')) if result.get('status') != 'ok' else ''}
        self.update(phone=phone)

    # ── Mo PC Remote ─────────────────────────────────────────────────
    def _remote(self, verb):
        spec = REMOTE[verb]
        if self._follow is not None or self._state['remote_busy']:
            return
        self._claim = None
        name, value = spec['tool']
        if has_tool(name):
            args = {'value': value}
            if moai_tools.needs_confirmation(name, args):
                self._remote_card(verb)
            else:
                self._start_follow(verb, 'run', spec['run'], 'cn_working')
                self.run('act:' + verb, moai_tools.execute, name, args)
            return
        # An image whose executor lacks the tool: moos-open's fixed route, then read-backs decide.
        if not self._open(spec['url']):
            self.update(**self._note('remote', 'cn_route_failed', 'error'))
            return
        self._start_follow(verb, 'dialog' if spec['dialog'] else 'readback', spec['seconds'],
                           'cn_wait_dialog' if spec['dialog'] else 'cn_wait_readback')
        self._follow_timer.start()

    def _start_follow(self, verb, phase, seconds, note, card=''):
        spec = REMOTE[verb]
        executor = phase in ('run', 'card')
        self._follow = {'verb': verb, 'key': spec['key'], 'want': spec['want'], 'min': spec['min'], 'hits': 0,
                        'done': spec['done_tool'] if executor else spec['done'],
                        'provable': spec.get('provable', True) or not executor,
                        'deadline': time.monotonic() + seconds, 'phase': phase, 'card': card}
        self.update(remote_busy=verb, remote_phase=phase, **self._note('remote', note, 'pending'))

    def _remote_card(self, verb):
        spec = REMOTE[verb]
        name, value = spec['tool']
        detail = moai_tools.consequence(name, self.lang) if name == 'fast_remote' else ''
        detail = detail or (self.text(spec['card']) if spec['card'] else moai_tools.consequence(name, self.lang))
        card_id = self._card('remote:' + verb, name, {'value': value}, detail)
        if not card_id:
            self._follow = None
            self.update(remote_busy='', remote_phase='', **self._note('remote', 'cn_card_failed', 'error'))
            return
        self._start_follow(verb, 'card', CARD_WAIT + spec['run'], 'cn_card_waiting', card=card_id)
        self._follow_timer.start()

    def on_act(self, tag, result):
        """The executor's answer to a remote action that needed no card: its exit status is the result."""
        verb = tag.split(':', 1)[1]
        follow = self._follow
        if follow is None or follow['verb'] != verb or follow['phase'] != 'run' or follow['card']:
            return
        status = result.get('status')
        if status == 'ok':
            self._finish_follow(follow['done'], 'ok', claim=(follow['key'], follow['want']))
            self._read('remote:now', read_remote)
        elif status == 'confirm':                     # the executor wants the owner after all
            self._follow = None
            self.update(remote_busy='', remote_phase='')
            self._remote_card(verb)
        elif status == 'pending' or result.get('error') == 'moai_control_unreachable':
            # No answer in time (a slow Fast Remote change, or the service went away): read back.
            follow.update(phase='readback', deadline=time.monotonic() + REMOTE[verb]['run'],
                          done=REMOTE[verb]['done'], provable=True)
            self.update(remote_phase='readback', **self._note('remote', 'cn_wait_readback', 'pending'))
            self._follow_timer.start()
        else:
            self._finish_follow('cn_not_done_direct', 'error', reason=result.get('error'))
            self._read('remote:now', read_remote)

    def _follow_tick(self):
        if self._follow is not None and 'remote:follow' not in self._pending:
            self._pending.add('remote:follow')
            self.run('remote:follow', read_remote)

    def _finish_follow(self, note, tone, claim=None, reason=None):
        self._follow = None
        self._follow_timer.stop()
        self._claim = claim if note else None
        self.update(remote_busy='', remote_phase='', **self._note('remote', note, tone, about=ERRORS.get(reason, '')))

    @Slot()
    def stopWaiting(self):
        """Give the remote buttons back while a card or a MoOS dialog is still unanswered. The card stays
        in Mira's list; approved later, its result is said here and the change is read like any other."""
        if self._follow is None or self._follow['phase'] not in ('card', 'dialog'):
            return
        self._finish_follow('', '')

    @Slot()
    def startRemote(self):
        self._remote('start')

    @Slot()
    def restartRemote(self):
        self._remote('restart')

    @Slot()
    def stopRemote(self):
        """Through the executor Stop is an owner card. On an image without it the owner's phone may be
        using the remote: the first click arms, a second within 5 s stops."""
        if self._follow is not None or self._state['remote_busy']:
            return
        if has_tool(REMOTE['stop']['tool'][0]):
            self._disarm()
            self._remote('stop')
            return
        now = time.monotonic()
        if not self._armed_at or now - self._armed_at > STOP_WINDOW:
            self._armed_at = now
            self._disarm_timer.start()
            self.update(stop_armed=True)
            return
        self._disarm()
        self._remote('stop')

    def _disarm(self):
        self._armed_at = 0.0
        self._disarm_timer.stop()
        if self._state['stop_armed']:
            self.update(stop_armed=False)

    @Slot(bool)
    def setFastRemote(self, on):
        self._remote('fast-on' if on else 'fast-off')

    @Slot()
    def openRemoteApp(self):
        if self._open('moos://app/remote'):
            self.host.toast.emit('info', self.text('cn_opening'))

    @Slot()
    def openRemoteSettings(self):
        if self._open('moos://settings/remote'):
            self.host.toast.emit('info', self.text('cn_opening'))

    @Slot()
    def remoteAnywhere(self):
        if 'anywhere' in self._cards.values() and self._state['anywhere_tone'] == 'pending':
            return                                    # one card at a time
        card_id = self._card('anywhere', 'remote_anywhere', {}, self.text('cn_anywhere_detail'))
        if card_id:
            self.update(**self._note('anywhere', 'cn_card_waiting', 'pending', life=CARD_WAIT + CARD_MARGIN))
        else:
            self.update(**self._note('anywhere', 'cn_card_failed', 'error'))

    # ── the end of a card (the controller reports it, when it does) ──
    def action_changed(self, action_id, name, stage):
        """A card of this page moved on: 'running' once approved, then ok | error | cancelled | expired."""
        purpose = self._cards.get(action_id)
        if purpose is None:
            return
        now = time.monotonic()
        follow = self._follow if (self._follow is not None and self._follow['card'] == action_id) else None
        if stage == 'running':
            if follow is not None:
                follow.update(phase='run', deadline=now + REMOTE[follow['verb']]['run'])
                self.update(remote_phase='run', **self._note('remote', 'cn_card_running', 'pending'))
            elif purpose == 'anywhere':
                self.update(**self._note('anywhere', 'cn_card_running', 'pending', life=INSTALL_FOLLOW))
            elif purpose == 'agent':
                self._agent_until = self._agent_asked_until = now + INSTALL_FOLLOW
                self.update(agent_install='running', **self._note('channel', 'cn_agent_running', 'pending'))
            return
        self._cards.pop(action_id, None)
        ended = CARD_END.get(stage, ('cn_not_done', 'error'))
        if purpose.startswith('remote:'):
            spec = REMOTE[purpose.split(':', 1)[1]]
            if stage == 'ok':
                if follow is not None or not self._state['remote_busy']:
                    self._finish_follow(spec['done_tool'], 'ok', claim=(spec['key'], spec['want']))
                self._read('remote:now', read_remote)
            elif follow is not None:
                self._finish_follow(*ended)
                if stage == 'error':
                    self._read('remote:now', read_remote)
            elif stage == 'error' and not self._state['remote_busy']:
                self.update(**self._note('remote', 'cn_not_done', 'error'))   # approved after he stopped waiting
        elif purpose == 'anywhere':
            key, tone = ('cn_anywhere_done', 'ok') if stage == 'ok' else ended
            self.update(**self._note('anywhere', key, tone, life=3 * NOTE_S if stage == 'ok' else None))
        elif purpose == 'agent':
            self._agent_until = self._agent_asked_until = 0.0
            if stage == 'ok':
                self.update(agent_install='', **self._note('channel', 'cn_agent_done', 'ok'))
                self._read('channels', read_channels)
            else:
                self.update(agent_install='', **self._note('channel', *ended))

    # ── message channels ─────────────────────────────────────────────
    @Slot()
    def setupChannels(self):
        if self._open('moos://settings/assistant'):
            self.host.toast.emit('info', self.text('cn_opening'))

    @Slot()
    def whatsappLogin(self):
        if not self._state['channels'].get('engine'):
            self.setupAgent()
            return
        if self._open('moos://agent/whatsapp-login'):
            self.host.toast.emit('info', self.text('cn_wa_opened'))

    @Slot()
    def setupAgent(self):
        """The messaging agent is installed by its executor on an owner card; an image without that tool
        opens the assistant's settings, where it is set up by hand."""
        if not has_tool(AGENT_TOOL):
            self.setupChannels()
            return
        if self._state['agent_install']:
            return                                    # one card at a time
        detail = ' '.join(filter(None, (self.text('cn_agent_detail'), moai_tools.consequence(AGENT_TOOL, self.lang))))
        card_id = self._card('agent', AGENT_TOOL, {}, detail)
        if card_id:
            now = time.monotonic()
            self._agent_asked_until = now + CARD_WAIT + CARD_MARGIN
            self._agent_until = now + INSTALL_FOLLOW
            self._last_channels_read = now
            self.update(agent_install='asked', **self._note('channel', 'cn_card_waiting', 'pending'))
        else:
            self.update(**self._note('channel', 'cn_card_failed', 'error'))

    # ── the phone link ───────────────────────────────────────────────
    @Slot()
    def openPhoneApp(self):
        phone = self._state['phone']
        if not (phone.get('system') or phone.get('local')):
            return
        self.run('open:' + PHONE_APP, moai_tools.execute, 'open_app', {'app_id': PHONE_APP})

    def on_open(self, tag, result):
        app_id = tag.split(':', 1)[1]
        status = result.get('status')
        if status == 'ok':
            self.host.toast.emit('info', self.text('cn_opening'))
        elif status == 'confirm':
            self._card('open', 'open_app', {'app_id': app_id}, self.text('cn_open_phone'))
        else:
            self.host.toast.emit('error', self.text('cn_open_failed') + self._reason(result.get('error')))

    @Slot(str)
    def ringPhone(self, device_id):
        devices = {d['id']: d for d in self._state['phone'].get('devices', [])}
        device = devices.get(device_id)
        if not DEVICE_ID.fullmatch(device_id or '') or device is None or not (device['paired'] and device['reachable']):
            return
        if self._state['ringing']:
            return
        self.update(ringing=device_id)
        self.run('ring:' + device_id, ring_phone, device_id)

    def on_ring(self, tag, result):
        device_id = tag.split(':', 1)[1]
        name = next((d['name'] for d in self._state['phone'].get('devices', []) if d['id'] == device_id), device_id)
        ok = result.get('status') == 'ok'
        self.update(ringing='', **self._note('phone', 'cn_ring_sent' if ok else 'cn_ring_failed',
                                             'ok' if ok else 'error', about=name))

    # ── the Echo ─────────────────────────────────────────────────────
    @Slot()
    def openSettings(self):
        self.host.showSheet.emit('settings')

    # ── review renders (MIRA_TEST_MODE only): visibly sample data ────
    def review(self, variant=None):
        """MIRA_CONNECT_VARIANT picks what a render shows: sample (default), initial, error, armed, card, fast."""
        variant = variant or os.environ.get('MIRA_CONNECT_VARIANT', 'sample')
        if variant == 'initial':
            return
        devices = [{'id': 'sample_phone_1', 'name': 'iPhone (sample)', 'paired': True, 'reachable': True},
                   {'id': 'sample_tablet_2', 'name': 'Tablet (sample)', 'paired': True, 'reachable': False}]
        state = dict(
            loading=False,
            remote={'known': True, 'active': True, 'pipewire': True, 'portal': True, 'fast': False},
            remote_error='', remote_busy='', remote_phase='', stop_armed=False,
            remote_note='cn_done_running', remote_tone='ok', remote_reason='', anywhere_note='', anywhere_tone='',
            channels={'known': True, 'engine': False, 'error': '',
                      'telegram': {'enabled': True, 'has_token': True, 'policy': 'allowlist', 'allowed': 1}},
            channel_note='', channel_tone='', agent_install='',
            phone={'known': True, 'system': True, 'local': False, 'running': True, 'listed': True, 'error': '',
                   'devices': devices},
            phone_note='cn_ring_sent', phone_about='iPhone (sample)', phone_tone='ok', ringing='')
        if variant == 'error':
            state.update(remote={'known': False, 'active': False, 'pipewire': False, 'portal': False, 'fast': False},
                         remote_error='cn_err_control', remote_note='', remote_tone='',
                         channels={**state['channels'], 'known': False, 'error': 'cn_err_agent'},
                         phone={'known': False, 'system': False, 'local': False, 'running': False, 'listed': False,
                                'devices': [], 'error': 'cn_err_control'},
                         phone_note='', phone_about='', phone_tone='')
        elif variant == 'armed':
            state.update(stop_armed=True, remote_note='', remote_tone='')
        elif variant == 'card':
            state.update(remote={**state['remote'], 'active': False}, remote_busy='start', remote_phase='card',
                         remote_note='cn_card_waiting', remote_tone='pending',
                         anywhere_note='cn_card_waiting', anywhere_tone='pending',
                         channel_note='cn_card_waiting', channel_tone='pending', agent_install='asked',
                         phone={**state['phone'], 'system': False, 'local': False, 'devices': [], 'listed': False},
                         phone_note='', phone_about='', phone_tone='')
        elif variant == 'fast':
            state.update(remote={**state['remote'], 'fast': True}, remote_note='cn_not_done_direct', remote_tone='error',
                         remote_reason='cn_err_busy', channels={**state['channels'], 'engine': True},
                         phone_note='cn_ring_failed', phone_tone='error')
        self.update(**state)


PAGE = ConnectPage
