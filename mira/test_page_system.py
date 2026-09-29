"""The System page (pages/system.py): what it shows is what MoOS's own services answered, a change only
ever becomes a card the owner approves, and every failure is shown as one.

No real service is reached: moai-control's reads, the executor and the moos:// router are stand-ins.
The report, scan and self-check shapes below are the live station's answers of 2026-09-29, trimmed;
the check_system_update outputs are moai-do's own `check-update` lines.
"""
import copy
import json
import os
import re
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_QUICK_BACKEND', 'software')
os.environ.setdefault('QT_QUICK_CONTROLS_STYLE', 'Basic')
os.environ['MIRA_TEST_MODE'] = '1'
# Never the owner's config: the real Controller below keeps its settings and history here.
_CONFIG = tempfile.TemporaryDirectory(prefix='mira-system-test-')
os.environ['XDG_CONFIG_HOME'] = _CONFIG.name

from PySide6.QtCore import QCoreApplication, QObject, QSettings, QUrl, Signal, qInstallMessageHandler  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

import i18n  # noqa: E402
import moai_tools  # noqa: E402
import moos_routes  # noqa: E402
from pages import system as sysmod  # noqa: E402
from pages.system import SystemPage  # noqa: E402

APP = QGuiApplication.instance() or QGuiApplication([])
QSettings.setDefaultFormat(QSettings.IniFormat)
QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, _CONFIG.name)
ROOT = Path(__file__).resolve().parent
TREE_SCHEMA_FILE = ROOT.parent / 'system_files/usr/lib/moai/moai_tool_schemas.py'
QML = (ROOT / 'qml' / 'Mira' / 'SystemPage.qml').read_text()
AR, EN = i18n.table('ar'), i18n.table('en')

CATEGORIES = {
    'os_state': 'read_only', 'list_skills': 'read_only', 'read_skill': 'read_only', 'list_failed_units': 'read_only',
    'check_drivers': 'read_only', 'inspect_boot': 'read_only', 'net_doctor': 'read_only', 'gpu_report': 'read_only',
    'device_report': 'read_only', 'support_bundle': 'read_only',
    'fix_audio': 'user_confirm', 'update_apps': 'user_confirm',
    'optimize_system': 'privileged_confirm', 'system_update': 'privileged_confirm', 'system_rollback': 'privileged_confirm',
    'install_nvidia': 'privileged_confirm', 'update_firmware': 'privileged_confirm',
}

OS_OUTPUT = ('## system image deployments\n'
             'booted: version 44.20260927.952 · signed origin · moos-nvidia@sha256:91c9ce7b40295397b871bcafe9743bf9\n'
             'kept for rollback: version 44.20260927.945 · signed origin · moos-nvidia@sha256:b09cdc48a1f0aa\n')
OS_STAGED = ('## system image deployments\n'
             'staged: version 44.20260929.960 · signed origin · moos-nvidia@sha256:77aa\n'
             'booted: version 44.20260927.952 · signed origin · moos-nvidia@sha256:91c9\n'
             'kept for rollback: version 44.20260927.945 · signed origin · moos-nvidia@sha256:b09c\n')

REPORT = {
    'schema': 1, 'generated_at': '2026-09-29T18:42:55+00:00',
    'system': {'os': 'MoOS', 'version': '44.20260927.952', 'signed': True, 'staged': '', 'rollback': True,
               'image': 'docker://ghcr.io/moalfarras-sys/moos-nvidia@sha256:91c9', 'kernel': '7.2.7-200'},
    # Measured on the station: Result=success with an empty ExecMainStartTimestamp (no run this boot).
    'updates': {'checked': True, 'apps': [], 'nightly_system_update': True, 'last_nightly_result': 'success'},
    'security': {'selinux': 'Enforcing', 'firewall': 'running', 'open_ports': [
        {'protocol': 'udp', 'address': '0.0.0.0:5353', 'process': 'python3', 'known': 'Avahi'},
        {'protocol': 'udp', 'address': '[::]:5353', 'process': '', 'known': 'Avahi'},
        {'protocol': 'udp', 'address': '0.0.0.0:41641', 'process': '', 'known': 'Tailscale'},
        {'protocol': 'tcp', 'address': '0.0.0.0:8123', 'process': 'python3', 'known': ''},
        {'protocol': 'tcp', 'address': '[::]:8123', 'process': 'python3', 'known': ''},
        {'protocol': 'tcp', 'address': '*:3389', 'process': 'krdpserver', 'known': ''}]},
    'summary': {'status': 'attention', 'counts': {'important': 0, 'warning': 3, 'info': 2}, 'app_updates': 2,
                'system_update_staged': False},
    'findings': [
        {'id': 'open-port-tcp-3389', 'severity': 'warning',
         'title': 'سطح المكتب البعيد (RDP) مفتوح للشبكة | Remote Desktop (RDP) is open to the network',
         'detail': "tcp *:3389 — krdpserver — MoOS's remote desktop is Mo PC Remote", 'action': 'moos://privacy/stop-sharing'},
        {'id': 'open-port-tcp-8123', 'severity': 'warning', 'title': 'منفذ مفتوح على الشبكة | A port is open to the network',
         'detail': 'tcp 0.0.0.0:8123, [::]:8123 — python3', 'action': ''},
        {'id': 'check-incomplete-updates', 'severity': 'warning',
         'title': 'تعذّر إكمال جزء من الفحص | Part of the check could not complete', 'detail': '', 'action': ''},
        {'id': 'app-updates', 'severity': 'info', 'title': 'تحديثات تطبيقات متاحة (2) | App updates available (2)',
         'detail': 'Firefox, VLC', 'action': 'moos://do/update-apps'},
        {'id': 'broad-file-access', 'severity': 'info',
         'title': 'تطبيقات تستطيع قراءة كل ملفاتك (2) | Apps that can read all your files (2)',
         'detail': 'cn.navclub.ldbfx, com.visualstudio.code', 'action': 'moos://settings/permissions'},
    ],
}
SCAN = {'os': 'MoOS', 'version': '44.20260927.952', 'kernel': '7.2.7-200', 'device_plan': {
    'schema': 1, 'health': 'attention', 'architecture': 'x86_64', 'gpu_vendor': 'nvidia',
    'gpu': '01:00.0 VGA compatible controller [0300]: NVIDIA Corporation TU104 [GeForce RTX 2080 SUPER] [10de:1e81] (rev a1)',
    'driver': 'nvidia', 'driver_status': 'NVIDIA proprietary driver active', 'driver_status_ar': 'تعريف NVIDIA الرسمي يعمل',
    'nvidia_image': True, 'firmware_updates': ['UEFI dbx 371 → 409', 'Samsung SSD 980 1B4QFXO7 → 3B4QFXO7'],
    'actions': [{'id': 'firmware-update', 'severity': 'info', 'title': 'تحديث البرامج الثابتة | Firmware updates',
                 'detail': 'UEFI dbx 371 → 409', 'url': 'moos://do/update-firmware'},
                {'id': 'kvm', 'severity': 'info', 'title': 'تسريع محاكي أندرويد | Android emulator acceleration',
                 'detail': 'فعّل المحاكاة | Enable CPU virtualization in firmware.', 'url': ''}]}}
DIAGNOSE = {
    'healthy': False, 'ok': 49, 'fail': 2,
    'issues': ["colour scheme is 'MoOSUI2Aurora', expected MoOSUI2Amethyst",
               'تعذّر تشغيل الفحص | could not run one check'],
    'fixes': [{'id': i, 'label': i, 'read': r} for i, r in (
        ('diagnose-services', True), ('check-drivers', True), ('inspect-boot', True), ('net-doctor', True),
        ('gpu-report', True), ('fix-audio', False), ('optimize', False), ('rollback', False), ('update', False),
        ('no-such-verb', True))],
}
SKILLS_OUTPUT = ('## repair playbooks written for this system (read ONE with read_skill, then follow it)\n'
                 'no-sound — The person hears nothing.\n'
                 'disk-full — The disk is full.\n')

# moai-do check-update's own lines (system_files/usr/bin/moai-do, do_check_update).
CHECK_AVAILABLE = ('═══ فحص تحديثات MoOS (قراءة فقط) | Check for MoOS updates (read-only) ═══\n'
                   'الحالي | Current: MoOS 44.20260927.952 (moos-nvidia)\n'
                   '⬆ نسخة أحدث متاحة | A newer version is available: MoOS 44.20260929.960\n'
                   '  يُنزَّل بتحديث النظام ويُطبَّق عند إعادة التشغيل | A system update downloads it; it applies at the next restart\n'
                   'MOOS_UPDATE state=available edition=moos-nvidia current=44.20260927.952 latest=44.20260929.960 staged=-\n')
CHECK_CURRENT = ('الحالي | Current: MoOS 44.20260927.952 (moos-nvidia)\n'
                 '✓ النظام على أحدث نسخة موقّعة | MoOS is on the latest signed version\n'
                 'MOOS_UPDATE state=current edition=moos-nvidia current=44.20260927.952 latest=44.20260927.952 staged=-\n')
CHECK_UNSIGNED = ('⚠ هذا الكمبيوتر لا يعمل من صورة MoOS رسمية موقّعة، فلا يمكن التحقق من التحديثات له.\n'
                  '⚠ This computer does not run a signed official MoOS image, so updates cannot be verified for it.\n'
                  'MOOS_UPDATE state=unsigned\n')
CHECK_FAILED = ('✗ تعذّر فحص التحديثات | Could not check for updates: registry did not answer\n'
                'MOOS_UPDATE state=unknown\n')


class FakeHost(QObject):
    toast = Signal(str, str)
    prefill = Signal(str)
    showSheet = Signal(str)

    def __init__(self, lang='ar', clock=time.time):
        super().__init__()
        self.lang = lang
        self.s = i18n.table(lang)
        self.clock = clock
        self.asked, self.toasts, self.prefilled = [], [], []
        self.card_ok = True
        self.toast.connect(lambda kind, text: self.toasts.append((kind, text)))
        self.prefill.connect(self.prefilled.append)

    def request_confirmation(self, item):
        """Like Controller.request_confirmation: the card's public view, with pending.py's expiry."""
        self.asked.append(item)
        return {'id': f'p-{len(self.asked)}', 'expires': self.clock() + 180} if self.card_ok else None

    def send(self, text):
        raise AssertionError('the System page never sends for the owner')


class Backend:
    """moai-control, the executor and the router, as stand-ins that record every call."""

    def __init__(self):
        self.gets, self.posts, self.executed, self.opened = [], [], [], []
        self.answers = {'/health': {'report': copy.deepcopy(REPORT), 'scanning': False},
                        '/scan': copy.deepcopy(SCAN), '/diagnose': copy.deepcopy(DIAGNOSE)}
        self.tools = {'os_state': {'status': 'ok', 'output': OS_OUTPUT},
                      'list_skills': {'status': 'ok', 'output': SKILLS_OUTPUT},
                      'read_skill': {'status': 'ok', 'output': '## skill no-sound: No sound\n## Look first\n1. `get_system_status`'},
                      'check_drivers': {'status': 'ok', 'output': 'GPU: NVIDIA · driver nvidia 580 · kernel 7.2.7-200.fc44.x86_64'},
                      'net_doctor': {'status': 'error', 'exit_code': 3, 'output': ''},
                      'check_system_update': {'status': 'ok', 'exit_code': 0, 'output': CHECK_AVAILABLE}}
        self.post_answer = {'started': True, 'scanning': True}

    def get(self, path, timeout=20):
        self.gets.append(path)
        return copy.deepcopy(self.answers.get(path, {'error': 'not found'}))

    def post(self, path, body, timeout=30):
        self.posts.append((path, body))
        return dict(self.post_answer)

    def execute(self, name, args, confirmed=False):
        self.executed.append((name, dict(args or {}), confirmed))
        return copy.deepcopy(self.tools.get(name, {'status': 'error', 'error': 'unknown'}))

    def open_route(self, url):
        self.opened.append(url)
        return {'status': 'ok'} if moos_routes.allowed(url) else {'status': 'error', 'error': 'route_not_allowed'}


class PageTest(unittest.TestCase):
    extra_tools = ()

    def setUp(self):
        self.backend = Backend()
        categories = dict(CATEGORIES)
        for name, category in self.extra_tools:
            categories[name] = category
        self.categories = categories
        patches = [
            mock.patch.object(moai_tools, 'names', lambda: set(categories)),
            mock.patch.object(moai_tools, 'meta', lambda n: {'category': categories[n]} if n in categories else None),
            mock.patch.object(moai_tools, 'needs_confirmation',
                              lambda n, a: categories.get(n) in ('user_confirm', 'privileged_confirm')),
            mock.patch.object(moai_tools, 'get', self.backend.get),
            mock.patch.object(moai_tools, 'post', self.backend.post),
            mock.patch.object(moai_tools, 'execute', self.backend.execute),
            mock.patch.object(moos_routes, 'open_route', self.backend.open_route),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        self.wall = [1_790_000_000.0]
        self.host = FakeHost(clock=lambda: self.wall[0])
        self.page = SystemPage(self.host)
        self.clock = [1000.0]
        self.page._clock = lambda: self.clock[0]
        self.page._wall = lambda: self.wall[0]
        # Worker threads answered at once, on this thread (the threaded path has its own test).
        self.page.run = lambda tag, fn, *a, **k: self.page._deliver(tag, fn(*a, **k))

    @property
    def st(self):
        return self.page._state

    def english(self):
        self.host.lang, self.host.s = 'en', EN


class Helpers(unittest.TestCase):
    def test_os_state_lines(self):
        found = sysmod.parse_os(OS_STAGED)
        self.assertEqual(found['booted'], {'version': '44.20260927.952', 'signed': True, 'edition': 'moos-nvidia', 'digest': '91c9'})
        self.assertEqual(found['staged']['version'], '44.20260929.960')
        self.assertEqual(found['kept']['version'], '44.20260927.945')
        odd = sysmod.parse_os('booted: version ? · UNSIGNED or local origin · unknown image')
        self.assertEqual(odd['booted'], {'version': '', 'signed': False, 'edition': '', 'digest': ''})
        self.assertEqual(sysmod.parse_os('## nothing here'), {})

    def test_editions_never_carry_a_registry_tag_or_digest(self):
        for image in ('docker://ghcr.io/moalfarras-sys/moos-nvidia@sha256:91c9', 'ghcr.io/moalfarras-sys/moos-nvidia:latest',
                      'moos-nvidia', 'ostree-image-signed:docker://ghcr.io/moalfarras-sys/moos-nvidia:stable'):
            self.assertEqual(sysmod.edition(image), 'moos-nvidia', image)
        self.assertEqual(sysmod.edition(''), '')

    def test_identity_is_cleaned(self):
        self.assertEqual(sysmod.clean('kernel 7.2.7-200.fc44.x86_64 up'), 'kernel 7.2.7-200 up')
        self.assertEqual(sysmod.clean('6.11.4-301.fc44'), '6.11.4-301')
        for leak in ('Fedora Linux 44', 'Red Hat, Inc.', 'fedora-project', 'RHEL'):
            self.assertNotRegex(sysmod.clean(leak), r'(?i)fedora|red ?hat|rhel')
        # One cleaner for every page (moai_tools.clean_identity); an older moai_tools still cleans.
        with mock.patch.object(moai_tools, 'clean_identity', lambda text: 'shared:' + str(text)):
            self.assertEqual(sysmod.clean('x'), 'shared:x')
        with mock.patch.object(moai_tools, 'clean_identity', None):
            self.assertEqual(sysmod.clean('kernel 7.2.7-200.fc44.x86_64 up'), 'kernel 7.2.7-200 up')
            for leak in ('Fedora Linux 44', 'Red Hat, Inc.', 'fedora-project', 'RHEL'):
                self.assertNotRegex(sysmod.clean(leak), r'(?i)fedora|red ?hat|rhel')
        self.assertEqual(sysmod.halves('عربي | English'), ('عربي', 'English'))
        self.assertEqual(sysmod.halves('only one'), ('only one', 'only one'))

    def test_times_read_as_today_yesterday_or_a_date(self):
        now = datetime.now().astimezone()
        self.assertEqual(sysmod.when(now.isoformat(), now)['day'], 'today')
        self.assertEqual(sysmod.when((now - timedelta(days=1)).isoformat(), now)['day'], 'yesterday')
        old = sysmod.when((now - timedelta(days=9)).isoformat(), now)
        self.assertEqual((old['day'], old['date']), ('date', (now - timedelta(days=9)).strftime('%Y-%m-%d')))
        self.assertEqual(sysmod.when('not a time'), {})

    def test_gpu_names(self):
        self.assertEqual(sysmod.gpu_name(SCAN['device_plan']['gpu']), 'NVIDIA GeForce RTX 2080 SUPER')
        self.assertEqual(sysmod.gpu_name('03:00.0 VGA compatible controller [0300]: Advanced Micro Devices, Inc. [AMD/ATI] '
                                         'Navi 21 [Radeon RX 6800/6800 XT / 6900 XT] [1002:73bf] (rev c1)'),
                         'AMD Radeon RX 6800/6800 XT / 6900 XT')
        self.assertEqual(sysmod.gpu_name('00:02.0 VGA compatible controller [0300]: Intel Corporation HD Graphics 620 [8086:5916]'),
                         'Intel HD Graphics 620')
        self.assertEqual(sysmod.gpu_name('unavailable'), '')

    def test_the_update_check_line(self):
        self.assertEqual(sysmod.parse_update_check(CHECK_AVAILABLE),
                         {'state': 'available', 'latest': '44.20260929.960', 'staged': '', 'current': '44.20260927.952',
                          'edition': 'moos-nvidia'})
        self.assertEqual(sysmod.parse_update_check(CHECK_UNSIGNED)['state'], 'unsigned')
        self.assertEqual(sysmod.parse_update_check('MOOS_UPDATE state=weird')['state'], 'unknown')
        self.assertEqual(sysmod.parse_update_check('no machine line'), {})

    def test_the_owner_reads_his_own_half(self):
        ar, en = sysmod.owner_lines(CHECK_AVAILABLE)
        self.assertNotIn('MOOS_UPDATE', ar + en)
        self.assertIn('الحالي: MoOS 44.20260927.952 (moos-nvidia)', ar, 'the Arabic label borrows the value')
        self.assertIn('⬆ نسخة أحدث متاحة', ar)
        self.assertNotRegex(ar, r'A newer version|Current:')
        self.assertIn('⬆ A newer version is available: MoOS 44.20260929.960', en)
        self.assertNotRegex(en, r'[\u0600-\u06FF]')
        ar, en = sysmod.owner_lines(CHECK_UNSIGNED)
        self.assertEqual(ar.count('\n'), 0)
        self.assertTrue(ar.startswith('⚠ هذا الكمبيوتر'))
        self.assertTrue(en.startswith('⚠ This computer'))
        ar, en = sysmod.owner_lines(CHECK_FAILED)
        self.assertEqual(ar, '✗ تعذّر فحص التحديثات: registry did not answer')
        self.assertEqual(en, '✗ Could not check for updates: registry did not answer')

    def test_every_fixed_route_is_allowlisted(self):
        for url in sysmod.ROUTES.values():
            self.assertTrue(moos_routes.allowed(url), url)

    def test_words_exist_in_both_languages(self):
        used = set(re.findall(r'\bmira\.s\.(sy_\w+)', QML))
        self.assertTrue(used)
        self.assertEqual(sorted(used - set(sysmod.STRINGS)), [])
        for name in sysmod.PAGE_TOOLS:
            self.assertIn('sy_t_' + name, sysmod.STRINGS, name)
        for name in sysmod.REPAIRS:
            self.assertIn('sy_d_' + name, sysmod.STRINGS, name)
        for state in sysmod.UPDATE_STATES:
            self.assertIn('sy_upd_' + state, sysmod.STRINGS, state)
        # keys the page stores for QML to translate
        stored = set(re.findall(r"""key=['"](sy_\w+)['"]|note_key=['"](sy_\w+)['"]|'key': ['"](sy_\w+)['"]""",
                                (ROOT / 'pages' / 'system.py').read_text()))
        for key in {k for group in stored for k in group if k}:
            self.assertIn(key, sysmod.STRINGS, key)
        shipped = sorted(p.stem for p in (ROOT.parent / 'system_files/usr/share/moos/moai/skills').glob('*.md'))
        for skill in shipped:
            self.assertIn('sy_sk_' + skill, sysmod.STRINGS, skill)
        for key, (ar, en) in sysmod.STRINGS.items():
            self.assertTrue(ar.strip() and en.strip(), key)
            self.assertNotRegex(ar + en, r'(?i)fedora|red ?hat', key)
        self.assertEqual(EN['sy_update'], 'Update MoOS')

    def test_clean_up_never_reads_as_deleting_pictures(self):
        for key in ('sy_d_optimize_system', 'sy_cd_optimize_system'):
            ar, en = sysmod.STRINGS[key]
            self.assertIn('صور الحاويات' if key.startswith('sy_cd') else 'صور حاويات', ar, key)
            self.assertIn('container images', en, key)
            self.assertIn('7', ar + en, key)
        ar, en = sysmod.STRINGS['sy_cd_optimize_system']
        self.assertIn('كلمة المرور', ar)
        self.assertIn('password', en)

    def test_every_button_reaches_a_slot(self):
        page = SystemPage(FakeHost())
        meta = page.metaObject()
        slots = {bytes(meta.method(i).name().data()).decode() for i in range(meta.methodCount())}
        called = set(re.findall(r'\bmira\.systemPage\.(\w+)\s*\(', QML))
        self.assertTrue(called)
        self.assertEqual(sorted(called - slots), [])


class Mapping(PageTest):
    def test_refresh_maps_the_real_shapes(self):
        self.page.refresh()
        st = self.st
        self.assertEqual(st['booted'], {'version': '44.20260927.952', 'signed': True, 'edition': 'moos-nvidia',
                                        'digest': '91c9ce7b4029'})
        self.assertEqual(st['kept']['version'], '44.20260927.945')
        self.assertEqual(st['kernel'], '7.2.7-200')
        self.assertEqual(st['update'], {'known': True, 'staged': False, 'staged_version': '', 'nightly': True,
                                        'last_result': 'success', 'last_run': {}, 'app_updates': 2, 'check': {}})
        health = st['health']
        self.assertEqual((health['state'], health['important'], health['warning'], health['info'], health['incomplete']),
                         ('attention', 0, 2, 2, 1))
        self.assertEqual(health['checked']['date'][:4], '2026')
        self.assertEqual(st['security'], {'known': True, 'selinux': 'Enforcing', 'selinux_tone': 'ok', 'firewall': 'running',
                                          'firewall_tone': 'ok', 'ports': 4, 'ports_known': True, 'unknown_ports': 2})
        by_id = {f['id']: f for f in st['findings']}
        # Offered exactly when Mira's router allows it (moos_routes may list privacy/stop-sharing).
        self.assertEqual(by_id['open-port-tcp-3389']['fix'],
                         'route' if moos_routes.allowed('moos://privacy/stop-sharing') else '')
        self.assertFalse(by_id['open-port-tcp-3389']['fix_page'], 'stop-sharing is an action, not a page')
        self.assertEqual(by_id['open-port-tcp-3389']['title_en'], 'Remote Desktop (RDP) is open to the network')
        self.assertEqual(by_id['open-port-tcp-3389']['title_ar'], 'سطح المكتب البعيد (RDP) مفتوح للشبكة')
        self.assertEqual((by_id['app-updates']['fix'], by_id['app-updates']['fix_tool']), ('tool', 'update_apps'))
        self.assertEqual((by_id['broad-file-access']['fix'], by_id['broad-file-access']['fix_route'],
                          by_id['broad-file-access']['fix_page']), ('route', 'moos://settings/permissions', True))
        self.assertTrue(by_id['check-incomplete-updates']['incomplete'])
        self.assertEqual(st['badge'], '2', 'real warnings only; an unanswered probe is not a warning')
        device = st['device']
        self.assertEqual((device['state'], device['verdict'], device['gpu']), ('done', 'attention', 'NVIDIA GeForce RTX 2080 SUPER'))
        self.assertRegex(device['checked'], r'^\d\d:\d\d$')
        self.assertTrue(device['nvidia_active'] and device['driver_ok'])
        self.assertFalse(device['nvidia_offer'])
        self.assertEqual(device['firmware'], ['UEFI dbx 371 → 409', 'Samsung SSD 980 1B4QFXO7 → 3B4QFXO7'])
        problems = {p['id']: p for p in device['problems']}
        self.assertNotIn('firmware-update', problems, 'pending firmware is its own list, not a second row')
        self.assertEqual(problems['kvm']['fix'], '')
        self.assertEqual(problems['kvm']['detail_en'], 'Enable CPU virtualization in firmware.')
        tiles = [t['name'] for t in st['tiles']]
        self.assertNotIn('install_nvidia', tiles, 'the NVIDIA driver is already active')
        self.assertEqual(tiles, [n for n in sysmod.REPAIRS if n != 'install_nvidia'])
        self.assertEqual(st['tiles'][0], {'name': 'fix_audio', 'icon': 'volume', 'category': 'user_confirm', 'password': False})
        diag = st['diag']
        self.assertEqual((diag['state'], diag['healthy'], diag['ok'], diag['fail']), ('done', False, 49, 2))
        self.assertEqual([f['name'] for f in diag['fixes']],
                         ['list_failed_units', 'check_drivers', 'inspect_boot', 'net_doctor', 'gpu_report', 'fix_audio',
                          'optimize_system', 'system_rollback', 'system_update'])
        self.assertEqual(diag['issues'][1]['title_en'], 'could not run one check')
        self.assertEqual([s['id'] for s in st['skills']], ['no-sound', 'disk-full'])
        self.assertFalse(st['loading'])
        self.assertEqual(sorted(self.backend.gets), ['/diagnose', '/health', '/scan'])
        self.assertEqual([e[0] for e in self.backend.executed], ['os_state', 'list_skills'])
        self.assertTrue(all(not confirmed for *_ignored, confirmed in self.backend.executed))

    def test_cleaning_up_is_marked_as_asking_for_the_password(self):
        self.page.refresh()
        tiles = {t['name']: t for t in self.st['tiles']}
        self.assertTrue(tiles['optimize_system']['password'], 'moai-do escalates to trim the journal')
        self.assertEqual(tiles['optimize_system']['category'], 'privileged_confirm')
        self.assertTrue(tiles['update_firmware']['password'])
        self.assertFalse(tiles['check_drivers']['password'])

    def test_an_older_schema_that_says_user_confirm_still_warns_of_the_password(self):
        self.categories['optimize_system'] = 'user_confirm'      # an installed image from before this change
        self.page.refresh()
        tiles = {t['name']: t for t in self.st['tiles']}
        self.assertEqual(tiles['optimize_system']['category'], 'user_confirm')
        self.assertTrue(tiles['optimize_system']['password'])

    def test_the_fake_categories_match_this_tree_s_schema(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('tree_schemas_for_system_page', TREE_SCHEMA_FILE)
        if spec is None:
            self.fail(f'no schema at {TREE_SCHEMA_FILE}')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        real = {n: meta['category'] for n, meta in module.TOOL_META.items() if n in CATEGORIES}
        self.assertEqual(sorted(real), sorted(CATEGORIES), 'a tool this page shows is not in the schema')
        self.assertEqual({n: CATEGORIES[n] for n in real}, real)

    def test_a_nightly_success_without_a_run_time_is_not_a_run(self):
        self.page.refresh()
        self.assertEqual((self.st['update']['last_result'], self.st['update']['last_run']), ('success', {}))
        stamp = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat(timespec='seconds')
        self.backend.answers['/health']['report']['updates']['last_nightly_run'] = stamp
        self.page.refresh()
        self.assertEqual(self.st['update']['last_run'], sysmod.when(stamp))
        self.assertTrue(self.st['update']['last_run']['time'])

    def test_the_live_kernel_outranks_the_report(self):
        self.backend.answers['/scan']['kernel'] = '7.3.1-100.fc44.x86_64'
        self.page.refresh()
        self.assertEqual(self.st['kernel'], '7.3.1-100', 'the live uname, without its tag')
        self.page._read_health()                         # a later report read must not bring back the old kernel
        self.assertEqual(self.st['kernel'], '7.3.1-100')

    def test_the_report_edition_without_a_tag(self):
        self.backend.tools['os_state'] = {'status': 'error', 'error': 'moai_control_unreachable'}
        self.backend.answers['/health']['report']['system']['image'] = 'docker://ghcr.io/moalfarras-sys/moos-nvidia:latest'
        self.page.refresh()
        self.assertEqual(self.st['booted']['edition'], 'moos-nvidia')

    def test_ports_that_could_not_be_read_are_unknown_not_zero(self):
        report = self.backend.answers['/health']['report']
        report['security']['open_ports'] = []
        report['findings'].append({'id': 'check-incomplete-ports', 'severity': 'warning',
                                   'title': 'تعذّر إكمال جزء من الفحص | Part of the check could not complete',
                                   'detail': 'تعذّر فحص منافذ الشبكة | Could not check network ports', 'action': ''})
        self.page.refresh()
        self.assertEqual((self.st['security']['ports_known'], self.st['security']['ports']), (False, 0))
        report['security'] = {'error': 'OSError: ss'}
        self.page.refresh()
        sec = self.st['security']
        self.assertTrue(sec['known'])
        self.assertEqual((sec['selinux'], sec['firewall'], sec['ports_known']), ('', 'unknown', False))
        report['security'] = {'selinux': 'Permissive', 'firewall': 'not running', 'open_ports': []}
        report['findings'] = []
        self.page.refresh()
        sec = self.st['security']
        self.assertEqual((sec['selinux'], sec['selinux_tone'], sec['firewall'], sec['firewall_tone'], sec['ports_known']),
                         ('Permissive', 'error', 'off', 'error', True))

    def test_the_self_check_is_not_rerun_on_every_visit(self):
        self.page.refresh()
        self.clock[0] += 60
        self.page.refresh()
        self.assertEqual(self.backend.gets.count('/diagnose'), 1)
        self.assertEqual(self.backend.executed.count(('list_skills', {}, False)), 1)
        self.clock[0] += sysmod.DIAG_FRESH_S + 1
        self.page.refresh()
        self.assertEqual(self.backend.gets.count('/diagnose'), 2)

    def test_a_read_already_out_is_not_sent_twice(self):
        held = []
        self.page.run = lambda tag, fn, *a, **k: held.append(tag)      # nothing answers yet
        self.page.refresh()
        self.page.refresh()
        self.page.checkUpdates()
        self.assertEqual(sorted(held), ['diag', 'health', 'os', 'plan', 'skills'])
        self.assertTrue(self.st['loading'])

    def test_a_staged_update_and_its_badge(self):
        self.backend.tools['os_state'] = {'status': 'ok', 'output': OS_STAGED}
        self.backend.answers['/health']['report']['findings'] = []
        self.page.refresh()
        self.assertEqual((self.st['update']['staged'], self.st['update']['staged_version']), (True, '44.20260929.960'))
        self.assertEqual(self.st['badge'], '•')

    def test_the_live_deployments_outrank_an_older_report(self):
        self.backend.answers['/health']['report']['summary']['system_update_staged'] = True
        self.backend.answers['/health']['report']['system']['staged'] = '44.20260929.960'
        self.page.refresh()          # os_state (read first) says nothing is staged any more
        self.assertFalse(self.st['update']['staged'])
        page = SystemPage(self.host)
        page.run = lambda tag, fn, *a, **k: page._deliver(tag, fn(*a, **k))
        self.backend.tools['os_state'] = {'status': 'error', 'error': 'moai_control_unreachable'}
        page.refresh()               # without the live read, the report's word is shown
        self.assertEqual((page._state['update']['staged'], page._state['update']['staged_version']), (True, '44.20260929.960'))
        self.assertEqual(page._state['booted']['version'], '44.20260927.952', 'the version still comes from the report')

    def test_what_the_owner_reads_never_names_the_base(self):
        self.backend.answers['/health']['report']['system']['kernel'] = '7.2.7-200.fc44.x86_64'
        self.backend.answers['/scan']['kernel'] = '7.2.7-200.fc44.x86_64'
        self.backend.answers['/health']['report']['findings'].append(
            {'id': 'x', 'severity': 'info', 'title': 'Fedora Linux keys changed | Fedora Linux keys changed', 'detail': 'Red Hat'})
        self.backend.answers['/scan']['device_plan']['driver_status'] = 'Fedora driver on kernel 7.2.7-200.fc44'
        self.page.refresh()
        self.page.runTool('check_drivers', 'tools')
        shown = json.dumps(self.st, ensure_ascii=False)
        self.assertNotRegex(shown, r'(?i)fedora|red ?hat|\.fc\d\d')
        self.assertEqual(self.st['kernel'], '7.2.7-200')

    def test_nvidia_offer_only_where_it_applies(self):
        plan = self.backend.answers['/scan']['device_plan']
        plan.update(driver='nouveau', nvidia_image=False)
        self.page.refresh()
        self.assertTrue(self.st['device']['nvidia_offer'])
        self.assertIn('install_nvidia', [t['name'] for t in self.st['tiles']])
        plan.update(gpu_vendor='amd', driver='amdgpu')
        self.page.refresh()
        self.assertFalse(self.st['device']['nvidia_offer'])
        self.assertTrue(self.st['device']['driver_ok'])
        self.assertNotIn('install_nvidia', [t['name'] for t in self.st['tiles']])

    def test_failures_are_shown_as_failures(self):
        self.backend.answers = {'/health': {'error': 'moai_control_unreachable'}, '/scan': {'error': 'http_500'},
                                '/diagnose': {'error': 'moai_control_unreachable'}}
        self.backend.tools['os_state'] = {'status': 'error', 'error': 'moai_control_unreachable'}
        self.backend.tools['list_skills'] = {'status': 'error', 'error': 'moai_control_unreachable'}
        self.page.refresh()
        st = self.st
        self.assertEqual(st['os_state'], 'error')
        self.assertEqual(st['booted'], {})
        self.assertEqual((st['health']['state'], st['health']['error']), ('error', 'moai_control_unreachable'))
        self.assertEqual((st['device']['state'], st['device']['error']), ('error', 'http_500'))
        self.assertEqual(st['diag']['state'], 'error')
        self.assertEqual(st['skills_state'], 'error')
        self.assertFalse(st['update']['known'])
        self.assertEqual(st['badge'], '')
        self.assertFalse(st['loading'])

    def test_no_report_yet_and_a_plan_still_being_made(self):
        self.backend.answers['/health'] = {'report': None, 'scanning': False}
        self.backend.answers['/scan'] = {'os': 'MoOS', 'device_plan_pending': True}
        self.page.refresh()
        self.assertEqual(self.st['health']['state'], 'none')
        self.assertEqual(self.st['device']['state'], 'pending')

    def test_opening_the_page_in_review_mode_reads_nothing(self):
        self.page.activated()
        self.assertEqual((self.backend.gets, self.backend.executed), ([], []))
        self.page.review()
        self.assertTrue(self.st['sample'])
        self.assertTrue(self.st['findings'] and self.st['tiles'] and self.st['skills'])
        rdp = next(f for f in self.st['findings'] if f['id'] == 'open-port-tcp-3389')
        self.assertEqual(rdp['fix'], 'route' if moos_routes.allowed('moos://privacy/stop-sharing') else '',
                         'the review render offers only what the live page can')
        self.assertEqual((self.backend.gets, self.backend.executed, self.host.asked), ([], [], []))

    def test_the_state_holds_words_as_keys_not_text(self):
        """A language switch re-renders the page: nothing the page wrote may be fixed in one language."""
        self.backend.answers['/health']['scanning'] = False
        self.page.refresh()
        self.page.checkUpdates()
        self.page.runTool('net_doctor', 'tools')
        self.host.card_ok = False
        self.page.runTool('fix_audio', 'tools')
        self.backend.post_answer = {'error': 'moai_control_unreachable'}
        self.page.scanHealth()
        state = json.dumps({k: self.st[k] for k in ('note_key', 'scan', 'outputs')}, ensure_ascii=False)
        for key in ('sy_check_none', 'sy_scan_failed', 'sy_ask_failed', 'sy_failed'):
            self.assertNotIn(AR[key], state, key)
        self.assertEqual(self.st['note_key'], 'sy_check_none')
        self.assertEqual((self.st['scan']['key'], self.st['scan']['error']), ('sy_scan_failed', 'moai_control_unreachable'))
        self.assertEqual(self.st['outputs']['fix_audio']['key'], 'sy_ask_failed')


class Changes(PageTest):
    def test_a_repair_only_becomes_a_card(self):
        self.page.refresh()
        self.backend.executed.clear()
        self.page.runTool('fix_audio', 'tools')
        self.assertEqual(self.backend.executed, [], 'a change never runs from the page')
        item = self.host.asked[-1]
        self.assertEqual((item['kind'], item['name'], item['args'], item['origin']), ('moai', 'fix_audio', {}, 'system'))
        self.assertEqual(item['detail'], AR['sy_cd_fix_audio'])
        self.assertEqual(self.st['outputs']['fix_audio']['state'], 'waiting')
        self.assertEqual(self.st['outputs']['fix_audio']['origin'], 'tools')
        self.assertTrue(self.page._expiry.isActive(), 'the page watches the card’s time itself')
        self.page.runTool('fix_audio', 'tools')
        self.assertEqual(len(self.host.asked), 1, 'one card per tool while it waits')
        self.assertEqual(self.host.toasts[-1], ('pending', AR['sy_waiting']), 'a second press says why nothing happened')
        self.page._expiry.stop()

    def test_a_card_whose_time_ran_out_frees_the_tool(self):
        """Rejected or expired with no word from the controller: the tile must not stay locked."""
        self.page.runTool('fix_audio', 'tools')
        self.wall[0] += 180 + sysmod.CARD_GRACE_S - 1
        self.page._expire_cards()
        self.assertEqual(self.st['outputs']['fix_audio']['state'], 'waiting', 'still inside the card’s time')
        self.wall[0] += 2
        self.page._expire_cards()
        out = self.st['outputs']['fix_audio']
        self.assertEqual(out['state'], 'lost', 'no word came back, so the page cannot say it was cancelled')
        self.assertFalse(self.page._expiry.isActive())
        self.assertEqual(self.page._cards, {})
        self.page.runTool('fix_audio', 'tools')
        self.assertEqual(len(self.host.asked), 2, 'a second card is asked')
        self.assertEqual(self.st['outputs']['fix_audio']['state'], 'waiting')
        self.page._expiry.stop()

    def test_pressing_again_after_the_card_expired_asks_again_without_the_timer(self):
        for name in ('system_update', 'fix_audio', 'optimize_system', 'update_firmware'):
            self.page.runTool(name, 'tools') if name != 'system_update' else self.page.updateSystem()
        self.page._expiry.stop()                              # the timer never fired (a sleeping machine)
        self.wall[0] += 400
        self.page.updateSystem()
        self.page.runTool('fix_audio', 'tools')
        self.page.runTool('optimize_system', 'tools')
        self.page.runTool('update_firmware', 'device')
        self.assertEqual([a['name'] for a in self.host.asked[4:]],
                         ['system_update', 'fix_audio', 'optimize_system', 'update_firmware'])
        self.page._expiry.stop()

    def test_rollback_from_a_self_check_chip_waits_for_its_expiry_too(self):
        self.page.refresh()
        self.page.runTool('system_rollback', 'diag')
        self.assertEqual(self.host.asked[-1]['name'], 'system_rollback')
        self.wall[0] += 300
        self.page.rollBack()
        self.assertEqual(len(self.host.asked), 2)
        self.page._expiry.stop()

    def test_a_waiting_result_closes_only_once_its_card_is_over(self):
        self.page.runTool('fix_audio', 'tools')
        self.page.closeOutput('fix_audio')
        self.assertIn('fix_audio', self.st['outputs'])
        self.wall[0] += 300
        self.page.closeOutput('fix_audio')
        self.assertNotIn('fix_audio', self.st['outputs'])
        self.assertEqual(self.page._cards, {})
        self.page.runTool('check_drivers', 'tools')
        self.page.closeOutput('check_drivers')
        self.assertNotIn('check_drivers', self.st['outputs'])
        self.page._expiry.stop()

    def test_a_card_without_an_expiry_uses_the_controllers_limit(self):
        self.host.request_confirmation = lambda item: {'id': 'x1'}
        self.page.runTool('fix_audio', 'tools')
        self.assertEqual(self.page._cards['x1']['expires'], self.wall[0] + sysmod.CARD_TTL_S)
        self.host.request_confirmation = lambda item: True    # a card with no id at all is still followed
        self.page.runTool('optimize_system', 'tools')
        self.assertIn('local-optimize_system', self.page._cards)
        self.page._expiry.stop()

    def test_update_and_rollback_cards_say_what_happens(self):
        self.english()
        self.page.refresh()
        self.page.updateSystem()
        detail = self.host.asked[-1]['detail']
        self.assertEqual(self.host.asked[-1]['name'], 'system_update')
        self.assertIn('44.20260927.952', detail)
        self.assertIn('next restart', detail)
        self.assertEqual(self.st['outputs']['system_update']['origin'], 'hero')
        self.page.rollBack()
        self.assertEqual(self.host.asked[-1]['name'], 'system_rollback')
        self.assertIn('44.20260927.945', self.host.asked[-1]['detail'])
        self.page._expiry.stop()

    def test_rollback_needs_a_kept_version_wherever_it_is_asked(self):
        self.backend.tools['os_state'] = {'status': 'ok', 'output': 'booted: version 44.1 · signed origin · moos@sha256:aa'}
        self.page.refresh()
        self.page.rollBack()
        self.page.runTool('system_rollback', 'diag')
        self.assertEqual(self.host.asked, [])
        self.assertEqual(self.host.toasts[-1][1], AR['sy_no_kept'])

    def test_the_firmware_card_lists_devices_and_says_it_cannot_be_undone(self):
        self.english()
        self.page.refresh()
        self.page.runTool('update_firmware', 'device')
        item = self.host.asked[-1]
        self.assertEqual(item['name'], 'update_firmware')
        checked = self.st['device']['checked']
        self.assertIn(f'The device check at {checked} found 2: UEFI dbx 371 → 409; Samsung SSD 980 1B4QFXO7 → 3B4QFXO7.',
                      item['detail'])
        self.assertIn('whatever the device makers offer when it runs', item['detail'])
        self.assertIn('cannot be undone', item['detail'])
        self.assertEqual(self.st['outputs']['update_firmware']['origin'], 'device')
        self.page._expiry.stop()

    def test_no_firmware_device_is_hidden_from_the_card(self):
        self.english()
        eight = [f'Device {i} 1.0 → 2.0' for i in range(8)]
        self.backend.answers['/scan']['device_plan']['firmware_updates'] = eight
        self.page.refresh()
        self.page.runTool('update_firmware', 'device')
        detail = self.host.asked[-1]['detail']
        for name in eight:
            self.assertIn(name, detail)
        self.assertIn('found 8', detail)
        self.page._expiry.stop()
        fourteen = [f'Device {i:02d} 1.0 → 2.0' for i in range(14)]
        self.backend.answers['/scan']['device_plan']['firmware_updates'] = fourteen
        self.page.refresh()
        self.page._release('update_firmware')
        self.page.runTool('update_firmware', 'device')
        detail = self.host.asked[-1]['detail']
        self.assertIn('found 14', detail)
        self.assertIn('Device 09', detail)
        self.assertNotIn('Device 10', detail)
        self.assertIn('and 4 more', detail)
        self.assertLess(len(detail), 2000, 'pending.py keeps 2000 characters of a card')
        self.host.lang, self.host.s = 'ar', AR
        self.page._release('update_firmware')
        self.page.runTool('update_firmware', 'device')
        self.assertIn('و4 غيرها', self.host.asked[-1]['detail'])
        self.assertIn('لا يمكن التراجع', self.host.asked[-1]['detail'])
        self.page._expiry.stop()

    def test_firmware_advice_without_a_list_keeps_its_own_fix(self):
        self.english()
        self.backend.answers['/scan']['device_plan']['firmware_updates'] = []
        self.page.refresh()
        problems = {p['id']: p for p in self.st['device']['problems']}
        self.assertEqual(problems['firmware-update']['fix_tool'], 'update_firmware')
        self.page.fixItem('device', 'firmware-update')
        self.assertEqual(self.host.asked[-1]['name'], 'update_firmware')
        self.assertIn(EN['sy_cd_firmware_any'], self.host.asked[-1]['detail'])
        self.assertIn('whatever the device makers offer', self.host.asked[-1]['detail'])
        self.assertEqual(self.st['outputs']['update_firmware']['origin'], 'device:firmware-update')
        self.page._expiry.stop()

    def test_a_finding_fixes_through_a_tool_or_an_allowlisted_route(self):
        self.page.refresh()
        self.page.fixItem('finding', 'app-updates')
        self.assertEqual(self.host.asked[-1]['name'], 'update_apps')
        self.assertEqual(self.st['outputs']['update_apps']['origin'], 'finding:app-updates')
        self.page.fixItem('finding', 'broad-file-access')
        self.assertEqual(self.backend.opened, ['moos://settings/permissions'])
        self.assertEqual(self.host.toasts[-1], ('ok', AR['sy_opened']), 'opening says it opened')
        self.page.fixItem('finding', 'open-port-tcp-8123')      # no fix exists: nothing happens
        self.page.fixItem('finding', 'no-such-id')
        self.assertEqual(len(self.host.asked), 1)
        self.assertEqual(self.backend.opened, ['moos://settings/permissions'])
        self.page._expiry.stop()

    def test_a_route_outside_the_allowlist_is_never_offered(self):
        report = self.backend.answers['/health']['report']
        report['findings'][0]['action'] = 'moos://evil/run?cmd=rm'
        report['findings'][1]['action'] = 'https://example.com/'
        report['findings'][3]['action'] = 'moos://do/launch-missiles'
        self.page.refresh()
        by_id = {f['id']: f for f in self.st['findings']}
        for fid in ('open-port-tcp-3389', 'open-port-tcp-8123', 'app-updates'):
            self.assertEqual((by_id[fid]['fix'], by_id[fid]['fix_tool'], by_id[fid]['fix_route']), ('', '', ''), fid)
            self.page.fixItem('finding', fid)
        self.assertEqual((self.backend.opened, self.host.asked), ([], []))

    def test_ask_puts_a_question_in_the_composer(self):
        self.page.refresh()
        self.page.askItem('finding', 'open-port-tcp-8123')
        question = self.host.prefilled[-1]
        self.assertIn('منفذ مفتوح على الشبكة', question)
        self.assertIn('tcp 0.0.0.0:8123', question)
        self.page.askItem('issue', '0')
        self.assertIn('MoOSUI2Aurora', self.host.prefilled[-1])
        self.english()
        self.page.askItem('device', 'kvm')
        self.assertTrue(self.host.prefilled[-1].startswith('Mira, MoOS’s device plan says: “Android emulator acceleration”'))
        self.assertEqual(len(self.host.prefilled), 3)

    def test_the_card_can_fail_to_appear(self):
        self.host.card_ok = False
        self.page.runTool('optimize_system', 'tools')
        out = self.st['outputs']['optimize_system']
        self.assertEqual((out['state'], out['key']), ('error', 'sy_ask_failed'))
        self.page.runTool('optimize_system', 'tools')          # nothing is locked by a card that never appeared
        self.assertEqual(len(self.host.asked), 2)

    def test_the_tile_follows_its_card_to_the_real_end(self):
        self.page.refresh()
        self.page.updateSystem()
        card = 'p-1'
        self.page.action_update(card, 'running', 'يعمل الآن…', '')
        self.assertEqual(self.st['outputs']['system_update']['state'], 'running')
        self.wall[0] += 3600                                  # a long job is not "expired" by the page
        self.page._expire_cards()
        self.assertEqual(self.st['outputs']['system_update']['state'], 'running')
        self.backend.executed.clear()
        self.page.action_update(card, 'ok', 'تم تحديث MoOS', 'Staged 44.20260929.960 on fedora-44 .fc44 base')
        out = self.st['outputs']['system_update']
        self.assertEqual((out['state'], out['summary'], out['origin']), ('ok', '', 'hero'))
        self.assertNotRegex(out['text'], r'(?i)fedora|\.fc44')
        self.assertIn(('os_state', {}, False), self.backend.executed, 'a staged update is read back')
        self.page.action_update(card, 'ok', 'again', 'x')                # a finished card is forgotten
        self.assertNotEqual(self.st['outputs']['system_update']['text'], 'x')
        self.page.runTool('fix_audio', 'tools')
        self.page.action_update('p-2', 'cancelled', 'أُلغيت', '')
        self.assertEqual((self.st['outputs']['fix_audio']['state'], self.st['outputs']['fix_audio']['key']),
                         ('cancelled', 'sy_cancelled'))
        self.page.runTool('fix_audio', 'tools')
        self.assertEqual(len(self.host.asked), 3, 'a rejected card frees its tool at once')
        self.page.action_update('p-3', 'expired', 'انتهت المهلة', '')
        self.assertEqual(self.st['outputs']['fix_audio']['key'], 'sy_expired')
        self.page.action_update('p-unknown', 'ok', 'x', 'y')              # another page's card: ignored
        self.page._expiry.stop()

    def test_a_failed_card_keeps_only_its_reason(self):
        self.page.runTool('optimize_system', 'tools')
        self.page.action_update('p-1', 'running', '', '')
        self.page.action_update('p-1', 'error', 'تعذّر: تنظيف وتحرير مساحة (exit 1)', '✗ podman failed')
        out = self.st['outputs']['optimize_system']
        self.assertEqual((out['state'], out['summary'], out['text']), ('error', 'exit 1', '✗ podman failed'))

    def test_a_job_that_outlives_the_controllers_wait_does_not_lock_the_tile(self):
        self.page.updateSystem()
        self.page.action_update('p-1', 'running', '', '')
        self.page.action_update('p-1', 'still-running', 'ما زال يعمل', '')
        out = self.st['outputs']['system_update']
        self.assertEqual((out['state'], out['key']), ('detached', 'sy_still_running'))
        self.assertEqual(self.page._cards, {})
        self.page.closeOutput('system_update')
        self.assertNotIn('system_update', self.st['outputs'])
        self.page.action_update('p-1', 'weird', '', '')                   # unknown words change nothing

    def test_only_this_pages_tools_run_from_a_tile(self):
        for name in ('launch_missiles', 'os_state', 'read_skill', 'list_skills', 'install_app'):
            self.page.runTool(name, 'tools')
        self.assertEqual((self.backend.executed, self.host.asked, self.st['outputs']), ([], [], {}))
        self.page.runTool('setup_gaming', 'diag')             # one of this page's, missing from this image
        out = self.st['outputs']['setup_gaming']
        self.assertEqual((out['state'], out['key']), ('error', 'sy_not_available'))


class Reads(PageTest):
    def test_a_check_runs_at_once_and_shows_its_output_where_it_was_asked(self):
        self.page.runTool('check_drivers', 'diag')
        self.assertEqual(self.backend.executed[-1], ('check_drivers', {}, False))
        out = self.st['outputs']['check_drivers']
        self.assertEqual((out['state'], out['origin']), ('ok', 'diag'))
        self.assertEqual(out['text'], 'GPU: NVIDIA · driver nvidia 580 · kernel 7.2.7-200')
        self.page.runTool('check_drivers', 'evil-origin')
        self.assertEqual(self.st['outputs']['check_drivers']['origin'], 'tools')

    def test_a_running_check_is_not_started_twice(self):
        held = []
        self.page.run = lambda tag, fn, *a, **k: held.append(tag)
        self.page.runTool('check_drivers', 'tools')
        self.page.runTool('check_drivers', 'diag')
        self.assertEqual(held, ['tool:check_drivers'])
        self.assertEqual(self.host.toasts[-1], ('info', AR['sy_running_already']))

    def test_a_failed_check_says_why(self):
        self.page.runTool('net_doctor', 'tools')
        out = self.st['outputs']['net_doctor']
        self.assertEqual((out['state'], out['summary'], out['text']), ('error', 'exit 3', ''))

    def test_the_executor_may_ask_for_approval(self):
        self.backend.tools['gpu_report'] = {'status': 'confirm', 'category': 'user_confirm'}
        self.page.runTool('gpu_report', 'tools')
        self.assertEqual(self.host.asked[-1]['name'], 'gpu_report')
        self.assertEqual(self.st['outputs']['gpu_report']['state'], 'waiting')
        self.page._expiry.stop()

    def test_check_for_updates_without_the_check_tool(self):
        self.page.checkUpdates()
        self.assertEqual((self.st['note_key'], self.st['note_tone'], self.st['checking']), ('sy_check_none', 'ok', False))
        self.assertIn(('os_state', {}, False), self.backend.executed)
        self.assertIn('/health', self.backend.gets)
        self.backend.tools['os_state'] = {'status': 'ok', 'output': OS_STAGED}
        self.page.checkUpdates()
        self.assertEqual((self.st['note_key'], self.st['note_tone']), ('sy_check_staged', 'warn'))

    def test_checking_is_its_own_flag_not_every_read(self):
        held = []
        self.page.run = lambda tag, fn, *a, **k: held.append(tag)
        self.page.runDiagnosis()                              # a 60-second read is out
        self.assertTrue(self.st['loading'])
        self.assertFalse(self.st['checking'], 'the self-check does not grey out "Check for updates"')
        self.page.checkUpdates()
        self.assertTrue(self.st['checking'])

    def test_restart_without_the_restart_tool_opens_the_update_page(self):
        self.page.restartNow()
        self.assertEqual(self.backend.opened, ['moos://settings/update'])
        self.assertEqual(self.host.asked, [])
        self.assertEqual(self.st['note_key'], 'sy_restart_where')

    def test_fixed_pages_only(self):
        self.page.openPage('recovery')
        self.page.openPage('whats_new')
        self.page.openPage('updater')
        self.page.openPage('moos://evil')
        self.assertEqual(self.backend.opened, ['moos://settings/recovery', 'moos://settings/whats-new', 'moos://app/updater'])

    def test_a_route_that_fails_to_open_says_so(self):
        with mock.patch.object(moos_routes, 'open_route', lambda url: {'status': 'error', 'error': 'FileNotFoundError'}):
            self.page.openPage('recovery')
        self.assertEqual(self.host.toasts[-1][0], 'error')
        self.assertIn('FileNotFoundError', self.host.toasts[-1][1])

    def test_playbooks(self):
        self.page.refresh()
        self.page.readSkill('rm -rf')
        self.page.readSkill('boot-problems')             # not in this image's list
        self.assertNotIn('read_skill', [e[0] for e in self.backend.executed])
        self.page.readSkill('no-sound')
        self.assertEqual(self.backend.executed[-1], ('read_skill', {'name': 'no-sound'}, False))
        self.assertEqual(self.st['skill'], {'id': 'no-sound', 'state': 'ok', 'text': '## Look first\n1. `get_system_status`',
                                            'error': ''})
        self.page.askSkill('no-sound')
        self.assertIn('لا يوجد صوت، أو الصوت يخرج من جهاز خاطئ', self.host.prefilled[-1])
        self.page.closeSkill()
        self.assertEqual(self.st['skill']['id'], '')
        self.backend.tools['read_skill'] = {'status': 'error', 'error': 'refused'}
        self.page.readSkill('disk-full')
        self.assertEqual((self.st['skill']['state'], self.st['skill']['error'], self.st['skill']['text']),
                         ('error', 'refused', ''))


class CheckNow(PageTest):
    def test_scan_then_poll_until_a_newer_report(self):
        self.page.refresh()
        with mock.patch.object(self.page._poll, 'start') as start:
            self.page.scanHealth()
        self.assertEqual(self.backend.posts, [('/health/scan', {})])
        start.assert_called_once()
        self.assertTrue(self.st['scan']['running'])
        self.page.scanHealth()
        self.assertEqual(len(self.backend.posts), 1, 'one check at a time')
        self.clock[0] += 6
        self.backend.answers['/health']['scanning'] = True
        self.page._poll_health()
        self.assertEqual((self.st['scan']['running'], self.st['scan']['elapsed']), (True, 6))
        newer = copy.deepcopy(REPORT)
        newer['generated_at'] = '2026-09-29T19:30:00+00:00'
        newer['findings'] = []
        newer['summary']['status'] = 'ok'
        self.backend.answers['/health'] = {'report': newer, 'scanning': False}
        self.clock[0] += 3
        self.page._poll_health()
        self.assertFalse(self.st['scan']['running'])
        self.assertEqual(self.st['scan']['key'], 'sy_scan_done')
        self.assertEqual((self.st['health']['state'], self.st['findings'], self.st['badge']), ('ok', [], ''))
        self.assertFalse(self.page._poll.isActive())
        self.assertEqual(self.host.toasts[-1][0], 'ok')

    def test_a_slow_check_keeps_its_promise_then_gives_up(self):
        self.page.refresh()
        self.page.scanHealth()
        self.backend.answers['/health']['scanning'] = True
        self.clock[0] += sysmod.SCAN_LIMIT_S + 1
        self.page._poll_health()
        self.assertTrue(self.st['scan']['running'], 'still followed: its result will appear here')
        self.assertEqual((self.st['scan']['tone'], self.st['scan']['key']), ('warn', 'sy_scan_slow'))
        self.assertTrue(self.page._poll.isActive())
        self.clock[0] = 1000.0 + sysmod.SCAN_GIVE_UP_S + 1
        self.page._poll_health()
        self.assertFalse(self.st['scan']['running'])
        self.assertEqual(self.st['scan']['key'], 'sy_scan_gave_up')
        self.assertFalse(self.page._poll.isActive())

    def test_a_check_that_ends_without_a_new_report_says_so(self):
        self.page.refresh()
        self.page.scanHealth()
        self.clock[0] += 3
        self.page._poll_health()                              # scanning False, the same generated_at
        self.assertFalse(self.st['scan']['running'])
        self.assertEqual((self.st['scan']['key'], self.st['scan']['tone']), ('sy_scan_no_report', 'error'))
        self.assertFalse(self.page._poll.isActive())

    def test_a_poll_that_fails_is_not_the_end_of_the_check(self):
        self.page.refresh()
        self.page.scanHealth()
        self.backend.answers['/health'] = {'error': 'moai_control_unreachable'}
        self.clock[0] += 3
        self.page._poll_health()
        self.assertTrue(self.st['scan']['running'])
        self.page._stop_scan()

    def test_a_check_that_cannot_start(self):
        self.backend.post_answer = {'error': 'moai_control_unreachable'}
        self.page.scanHealth()
        self.assertFalse(self.st['scan']['running'])
        self.assertEqual(self.st['scan']['tone'], 'error')
        self.assertEqual((self.st['scan']['key'], self.st['scan']['error']), ('sy_scan_failed', 'moai_control_unreachable'))
        self.assertFalse(self.page._poll.isActive())

    def test_a_check_already_running_is_followed(self):
        self.backend.answers['/health']['scanning'] = True
        self.page.refresh()
        self.assertTrue(self.st['scan']['running'])
        self.assertTrue(self.page._poll.isActive())
        self.page._stop_scan()


class WithNewerExecutor(PageTest):
    """An image whose executor declares check_system_update and restart_computer."""
    extra_tools = (('check_system_update', 'read_only'), ('restart_computer', 'user_confirm'))

    def test_a_newer_version_reaches_the_hero(self):
        self.page.refresh()
        self.page.checkUpdates()
        self.assertEqual(self.backend.executed[-1], ('check_system_update', {}, False))
        self.assertIn(('os_state', {}, False), self.backend.executed, 'the deployments are read beside it')
        check = self.st['update']['check']
        self.assertEqual((check['state'], check['latest'], check['current']), ('available', '44.20260929.960', '44.20260927.952'))
        out = self.st['outputs']['check_system_update']
        self.assertEqual((out['state'], out['origin'], out['key'], out['text']), ('ok', 'hero', 'sy_check_done', ''))

    def test_every_answer_of_the_resolver(self):
        cases = ((CHECK_CURRENT, 'ok', 0, 'current'), (CHECK_UNSIGNED, 'ok', 0, 'unsigned'),
                 ('MOOS_UPDATE state=busy edition=moos current=44.1 latest=44.2 staged=-\n', 'ok', 0, 'busy'),
                 ('MOOS_UPDATE state=blocked-downgrade edition=moos current=44.2 latest=44.1 staged=-\n', 'ok', 0,
                  'blocked-downgrade'),
                 ('MOOS_UPDATE state=replace-staged edition=moos current=44.1 latest=44.3 staged=44.2\n', 'ok', 0,
                  'replace-staged'))
        for output, status, code, state in cases:
            self.backend.tools['check_system_update'] = {'status': status, 'exit_code': code, 'output': output}
            self.page.checkUpdates()
            self.assertEqual(self.st['update']['check']['state'], state, state)
            self.assertEqual(self.st['outputs']['check_system_update']['state'], 'ok', state)

    def test_a_check_that_fails_is_shown_in_the_owners_language(self):
        self.backend.tools['check_system_update'] = {'status': 'error', 'exit_code': 1, 'output': CHECK_FAILED}
        self.page.checkUpdates()
        out = self.st['outputs']['check_system_update']
        self.assertEqual((out['state'], out['summary']), ('error', 'exit 1'))
        self.assertEqual(out['text_ar'], '✗ تعذّر فحص التحديثات: registry did not answer')
        self.assertEqual(out['text_en'], '✗ Could not check for updates: registry did not answer')
        self.assertEqual(self.st['update']['check']['state'], 'unknown')
        self.backend.tools['check_system_update'] = {'status': 'error', 'error': 'moai_control_unreachable'}
        self.page.checkUpdates()
        self.assertEqual(self.st['outputs']['check_system_update']['summary'], 'moai_control_unreachable')

    def test_an_update_that_staged_retires_the_old_verdict(self):
        self.page.refresh()
        self.page.checkUpdates()
        self.page.updateSystem()
        self.page.action_update('p-1', 'ok', 'تم', 'staged')
        self.assertEqual(self.st['update']['check'], {})
        self.page._expiry.stop()

    def test_the_executor_restarts(self):
        self.page.restartNow()
        self.assertEqual(self.host.asked[-1]['name'], 'restart_computer')
        self.assertEqual(self.host.asked[-1]['detail'], AR['sy_cd_restart_computer'])
        self.assertEqual(self.backend.opened, [])
        self.page._expiry.stop()


class Threads(PageTest):
    def test_the_real_worker_path_and_the_loading_flag(self):
        page = SystemPage(self.host)
        seen = []
        page.changed.connect(lambda: seen.append(page._state['loading']))
        page.refresh()
        self.assertTrue(page._state['loading'])
        end = time.monotonic() + 5
        while (page._state['loading'] or page._state['diag']['state'] != 'done') and time.monotonic() < end:
            QCoreApplication.processEvents()
            time.sleep(0.01)
        self.assertFalse(page._state['loading'])
        self.assertEqual(page._state['booted']['version'], '44.20260927.952')
        self.assertEqual(page._state['device']['state'], 'done')
        self.assertIn(True, seen)

    def test_a_backend_exception_becomes_an_error_not_a_crash(self):
        page = SystemPage(self.host)

        def boom(*_args, **_kwargs):
            raise OSError('socket')
        with mock.patch.object(moai_tools, 'execute', boom):
            page.runTool('check_drivers', 'tools')
            end = time.monotonic() + 5
            while page._state['outputs'].get('check_drivers', {}).get('state') == 'running' and time.monotonic() < end:
                QCoreApplication.processEvents()
                time.sleep(0.01)
        out = page._state['outputs']['check_drivers']
        self.assertEqual((out['state'], out['summary']), ('error', 'OSError'))

    def test_the_expiry_timer_really_fires(self):
        page = SystemPage(self.host)
        page._wall = lambda: self.wall[0]
        page._expiry.setInterval(10)
        page.runTool('fix_audio', 'tools')
        self.wall[0] += 400
        end = time.monotonic() + 3
        while page._state['outputs']['fix_audio']['state'] == 'waiting' and time.monotonic() < end:
            QCoreApplication.processEvents()
            time.sleep(0.01)
        self.assertEqual(page._state['outputs']['fix_audio']['state'], 'lost')
        self.assertFalse(page._expiry.isActive())


def _controller():
    from controller import Controller
    from review_fakes import FakeBridge
    return Controller(bridge_class=FakeBridge)


class WithTheRealController(unittest.TestCase):
    """The real Controller's cards (pending.py's expiry) and, once controller.py forwards card
    progress to the pages (`_tell_pages`), the whole round trip."""

    def setUp(self):
        self.controller = _controller()
        self.page = self.controller._pages['system']
        self.addCleanup(self.page._expiry.stop)

    def test_a_real_card_carries_the_expiry_the_page_follows(self):
        with mock.patch.object(moai_tools, 'needs_confirmation', lambda n, a: True):
            self.page.runTool('fix_audio', 'tools')
        card_id, card = next(iter(self.page._cards.items()))
        self.assertEqual(card['name'], 'fix_audio')
        self.assertAlmostEqual(card['expires'], time.time() + 180, delta=5)
        self.assertEqual(self.page._state['outputs']['fix_audio']['state'], 'waiting')
        with mock.patch.object(self.page, '_wall', lambda: time.time() + 200):
            self.page._expire_cards()
        self.assertEqual(self.page._state['outputs']['fix_audio']['state'], 'lost')
        self.controller.rejectAction(card_id)

    def test_reject_and_approve_reach_the_tile(self):
        with mock.patch.object(moai_tools, 'needs_confirmation', lambda n, a: True):
            self.page.runTool('fix_audio', 'tools')
        card_id = next(iter(self.page._cards))
        self.controller.rejectAction(card_id)
        self.assertEqual((self.page._state['outputs']['fix_audio']['state'],
                          self.page._state['outputs']['fix_audio']['key']), ('cancelled', 'sy_cancelled'))
        with mock.patch.object(moai_tools, 'needs_confirmation', lambda n, a: True):
            self.page.runTool('fix_audio', 'tools')
        card_id = next(iter(self.page._cards))
        self.controller.worker.run = lambda tag, fn, *a: None           # the job itself never runs here
        self.controller.approveAction(card_id)
        self.assertEqual(self.page._state['outputs']['fix_audio']['state'], 'running')
        self.controller._on_action_done(card_id, {'status': 'ok', 'output': 'restarted', 'name': 'fix_audio'})
        self.assertEqual(self.page._state['outputs']['fix_audio']['state'], 'ok')


class Rendered(unittest.TestCase):
    """SystemPage.qml in the real window, in every state the page can reach: no QML warning at all,
    and the words the hero shows are the ones the state establishes."""

    STATES = ('review', 'initial', 'errors', 'running', 'cancelled', 'lost', 'detached', 'skill-open',
              'skill-error', 'check-available', 'check-unsigned', 'check-failed', 'unknown-ports', 'scan-slow')
    # The page and the shared parts it uses: a warning from any of them in these states is this page's.
    PARTS = ('SystemPage', 'PageFrame', 'Card', 'Glass', 'OutputBox', 'PillButton', 'IconButton', 'StatusPill',
             'SectionTitle', 'Icon', 'T')

    @classmethod
    def setUpClass(cls):
        from PySide6.QtQml import QQmlApplicationEngine
        from faces import FaceProvider
        cls.messages = []
        cls.previous = qInstallMessageHandler(lambda mode, context, message: cls.messages.append(message))
        cls.controller = _controller()
        cls.engine = QQmlApplicationEngine()
        cls.engine.addImageProvider('mira', FaceProvider())
        cls.engine.addImportPath(str(ROOT / 'qml'))
        cls.engine.rootContext().setContextProperty('mira', cls.controller)
        cls.engine.load(QUrl.fromLocalFile(str(ROOT / 'qml' / 'Main.qml')))
        cls.window = cls.engine.rootObjects()[0]
        cls.page = cls.controller._pages['system']
        cls.window.setProperty('sheet', 'system')
        cls.settle(0.5)

    @classmethod
    def tearDownClass(cls):
        cls.page._expiry.stop()
        cls.engine.deleteLater()
        cls.settle(0.1)
        qInstallMessageHandler(cls.previous)

    @staticmethod
    def settle(seconds=0.15):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            QCoreApplication.processEvents()
            time.sleep(0.01)

    def view(self):
        for item in self.window.findChildren(QObject):
            if item.metaObject().className().startswith('SystemPage_QML'):
                return item
        self.fail('SystemPage is not on screen')

    def put(self, name):
        page = self.page
        page._state = dict(page.initial())
        if name == 'initial':
            page.changed.emit()
            return
        page.review()
        outputs = dict(page._state['outputs'])
        blank = {'text': '', 'text_ar': '', 'text_en': '', 'summary': '', 'key': '', 'arg': '', 'at': '20:50'}
        if name == 'errors':
            page.update(os_state='error', booted={}, kept={}, update=page.initial()['update'],
                        health={**page.initial()['health'], 'state': 'error', 'error': 'moai_control_unreachable'},
                        diag={**page._state['diag'], 'state': 'error', 'error': 'http_502'},
                        device={**page.initial()['device'], 'state': 'error', 'error': 'shape'},
                        scan={'running': False, 'elapsed': 0, 'key': 'sy_scan_failed', 'error': 'busy', 'tone': 'error'},
                        security=page._security({'error': 'OSError'}, []), findings=[], skills_state='error', skills=[])
        elif name == 'running':
            outputs.update(fix_audio={**blank, 'state': 'running', 'origin': 'tools'},
                           system_update={**blank, 'state': 'running', 'origin': 'hero'},
                           update_firmware={**blank, 'state': 'waiting', 'origin': 'device'})
            page.update(outputs=outputs, loading=True, checking=True)
        elif name == 'cancelled':
            outputs.update(fix_audio={**blank, 'state': 'cancelled', 'key': 'sy_cancelled', 'origin': 'tools'},
                           system_update={**blank, 'state': 'cancelled', 'key': 'sy_expired', 'origin': 'hero'},
                           net_doctor={**blank, 'state': 'error', 'summary': 'exit 3', 'origin': 'tools'})
            page.update(outputs=outputs)
        elif name == 'lost':
            outputs.update(fix_audio={**blank, 'state': 'lost', 'origin': 'tools'})
            page.update(outputs=outputs)
        elif name == 'detached':
            outputs.update(system_update={**blank, 'state': 'detached', 'key': 'sy_still_running', 'origin': 'hero'})
            page.update(outputs=outputs)
        elif name == 'skill-open':
            page.update(skill={'id': 'no-sound', 'state': 'ok', 'text': '## Look first\n1. `get_system_status`', 'error': ''})
        elif name == 'skill-error':
            page.update(skill={'id': 'no-sound', 'state': 'error', 'text': '', 'error': 'refused'})
        elif name == 'check-available':
            page.update(update={**page._state['update'], 'check': {'state': 'available', 'latest': '44.20260929.960',
                                                                   'staged': '', 'current': '', 'edition': '', 'at': '20:50'}},
                        outputs={**outputs, 'check_system_update': {**blank, 'state': 'ok', 'key': 'sy_check_done',
                                                                    'origin': 'hero'}})
        elif name == 'check-unsigned':
            page.update(update={**page._state['update'], 'check': {'state': 'unsigned', 'at': '20:50'}})
        elif name == 'check-failed':
            ar, en = sysmod.owner_lines(CHECK_FAILED)
            page.update(update={**page._state['update'], 'check': {'state': 'unknown', 'at': '20:50'}},
                        outputs={**outputs, 'check_system_update': {**blank, 'state': 'error', 'summary': 'exit 1',
                                                                    'text_ar': ar, 'text_en': en, 'origin': 'hero'}})
        elif name == 'unknown-ports':
            page.update(security={**page._state['security'], 'ports_known': False, 'ports': 0, 'selinux': 'Permissive',
                                  'selinux_tone': 'error'})
        elif name == 'scan-slow':
            page.update(scan={'running': True, 'elapsed': 95, 'key': 'sy_scan_slow', 'error': '', 'tone': 'warn'})

    def test_every_state_renders_without_a_warning(self):
        for lang in ('ar', 'en'):
            self.controller.setLang(lang)
            for name in self.STATES:
                self.messages.clear()
                self.put(name)
                self.settle()
                for width in (1480, 900):
                    self.window.setWidth(width)
                    self.settle(0.05)
                problems = [m for m in self.messages if any(f'{part}.qml' in m for part in self.PARTS)]
                self.assertEqual(problems, [], f'{lang}/{name}')

    def test_the_hero_says_only_what_the_state_establishes(self):
        self.controller.setLang('en')
        self.put('review')
        page, view = self.page, self.view()
        base = dict(page._state['update'])
        page.update(update={**base, 'check': {}, 'last_result': 'success', 'last_run': {}})
        self.settle()
        self.assertEqual(view.property('updateState'), EN['sy_state_none'], 'Result=success alone is not a run')
        self.assertIn(EN['sy_no_failure'], view.property('nightlyText'))
        self.assertNotIn(EN['sy_last_ok'], view.property('nightlyText'))
        page.update(update={**base, 'check': {}, 'last_result': 'success',
                            'last_run': {'day': 'today', 'date': '2026-09-29', 'time': '04:38'}})
        self.settle()
        self.assertEqual(view.property('updateState'), EN['sy_state_current'])
        self.assertIn(EN['sy_last_ok'] + ' · today · 04:38', view.property('nightlyText'))
        page.update(update={**base, 'last_result': 'exit-code', 'last_run': {}})
        self.settle()
        self.assertIn('ended with an error', view.property('nightlyText'))
        page.update(update={**base, 'check': {'state': 'available', 'latest': '44.20260929.960'}})
        self.settle()
        self.assertIn('44.20260929.960', view.property('updateState'))
        self.assertTrue(view.property('updateState').startswith('Newer version'))
        self.assertTrue(view.property('offerUpdate'))
        page.update(update={**base, 'check': {'state': 'current'}})
        self.settle()
        self.assertEqual(view.property('updateState'), EN['sy_upd_current'])
        self.assertFalse(view.property('offerUpdate'), 'nothing newer: Update MoOS is not the primary action')
        self.assertTrue(view.property('official'))
        page.update(update={**base, 'check': {}})
        self.settle()
        self.assertFalse(view.property('official'), 'a signed transport alone is not "official"')
        page.update(health={**page._state['health'], 'state': 'error', 'error': 'moai_control_unreachable'})
        self.settle()
        self.assertEqual(view.property('healthHead'),
                         EN['sy_health_error'] + ' (' + EN['sy_err_moai_control_unreachable'] + ')')
        self.controller.setLang('ar')
        self.settle()
        self.assertEqual(view.property('healthHead'),
                         AR['sy_health_error'] + ' (' + AR['sy_err_moai_control_unreachable'] + ')',
                         'a language switch re-renders what the page wrote')


if __name__ == '__main__':
    unittest.main()
