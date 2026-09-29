"""The Apps page: store search, installed list, updates, device plan, compatibility hub, files.

Every backend is a fake: nothing here reaches flatpak, moos-app-engine, moai-control, moos-open or
the owner's desktop. Changes must become cards (request_confirmation), never direct calls; results
must be read back.
"""
import os
import re
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ['MIRA_TEST_MODE'] = '1'

from PySide6.QtCore import QCoreApplication, QUrl  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

import i18n  # noqa: E402
import moai_tools  # noqa: E402
import moos_routes  # noqa: E402
from pages import apps  # noqa: E402

APP = QGuiApplication.instance() or QGuiApplication([])
TOOLS = {'install_app', 'uninstall_app', 'update_apps', 'open_app', 'list_installed_apps', 'setup_gaming',
         'setup_windows', 'setup_waydroid'}
META = {'setup_waydroid': {'category': 'privileged_confirm'}, 'install_app': {'category': 'user_confirm'},
        'setup_gaming': {'category': 'user_confirm'}, 'setup_windows': {'category': 'user_confirm'}}
# what `flatpak list --app --columns=application,name,version,installation` prints
LISTING = ('com.valvesoftware.Steam\tSteam\t1.0.0.87\tuser\n'
           'org.videolan.VLC\tVLC\t3.0.21\tuser\n'
           'cn.navclub.ldbfx\tldbfx\t1.0.0\tsystem\n'
           'not an id\tBroken\n'
           'io.github.kolunmi.Bazaar\tبازار\t0.9.6\tuser\n')
SCAN = {'arch': 'x86_64',
        'compatibility': {'waydroid': True, 'kvm': True, 'steam': True, 'bottles': False, 'kdeconnect': False},
        'device_plan': {'missing_recommended_apps': ['org.mozilla.firefox', 'org.videolan.VLC', 'bad id',
                                                     'org.example.Unknown']}}
HEALTH = {'scanning': False, 'report': {'generated_at': '2026-09-29T18:42:55+00:00',
                                        'updates': {'checked': True, 'apps': ['Telegram Desktop', 'Steam']}}}


def engine(ready, needs_setup=False, present=True, chosen='', sandboxed=False, provision=True):
    return {'ready': ready, 'needs_setup': needs_setup, 'present': present, 'chosen': chosen,
            'sandboxed': sandboxed, 'provision': provision}


# a fresh desktop MoOS: the image's own runtime runs .exe files, Android needs its one-time download
ENGINES = {'status': 'ok', 'engines': {'windows': engine(True, chosen='wine'),
                                       'android': engine(False, needs_setup=True),
                                       'linux': engine(True, chosen='flatpak', sandboxed=True)}}
# words MoOS must never say to a person (tests/test_app_engines.py), plus the packaging word
RUNTIME_WORDS = ('wine', 'bottles', 'waydroid', 'proton', 'lutris', 'flatpak', 'qemu', 'bubblewrap')


class Toast:
    def __init__(self):
        self.shown = []

    def emit(self, kind, text):
        self.shown.append((kind, text))


class Signal1:
    def __init__(self):
        self.shown = []

    def emit(self, value):
        self.shown.append(value)


class Host:
    """The part of the controller a page may use (pages/base.py)."""

    def __init__(self, lang='ar'):
        self.lang = lang
        self.s = i18n.table(lang)
        self.toast = Toast()
        self.prefill = Signal1()
        self.showSheet = Signal1()
        self.asked = []
        self.sent = []
        self.refuse = False

    def request_confirmation(self, item):
        self.asked.append(item)
        return None if self.refuse else {'id': f'p{len(self.asked)}', 'expires': time.time() + 180}

    def send(self, text):
        self.sent.append(text)


def sync_page(host=None):
    """A page whose worker calls run inline (the threaded path has its own test)."""
    page = apps.AppsPage(host or Host())
    page.run = lambda tag, fn, *a, **k: page._deliver(tag, fn(*a, **k))
    return page


class Fakes:
    """flatpak / resolver / moai_tools / moos_routes stand-ins; records every call."""

    def __init__(self):
        self.calls = []
        self.listing = LISTING                 # None: flatpak cannot be read here
        self.moai_listing = '## installed applications\n' + LISTING
        self.engines = ENGINES
        self.phone = True
        self.scan = dict(SCAN)
        self.health = dict(HEALTH)
        self.search = {'status': 'ok', 'source': 'flathub', 'apps': [
            {'id': 'org.videolan.VLC', 'name': 'VLC', 'summary': 'Media player', 'installed': False, 'verified': False,
             'installs': 104064, 'recommended': False,
             'icon': 'https://dl.flathub.org/media/org/videolan/VLC/34e7/icons/128x128/org.videolan.VLC.png'},
            {'id': 'org.kde.kdenlive', 'name': 'Kdenlive', 'summary': 'Video editor', 'installed': False,
             'verified': True, 'installs': 61230, 'recommended': True,
             'note': 'محرّر فيديو أصلي | a video editor native to the desktop', 'icon': 'http://evil.example/x.png'},
            {'id': 'cn.navclub.ldbfx', 'name': 'ldbfx', 'summary': 'Database tool', 'installed': True},
            {'id': '../../etc', 'name': 'bad'}]}
        self.open_result = {'status': 'ok', 'output': 'opened'}
        self.routes = []

    def flatpak_list(self):
        self.calls.append(('flatpak',))
        return self.listing

    def read_engines(self):
        self.calls.append(('engines',))
        return self.engines

    def execute(self, name, args, confirmed=False):
        self.calls.append(('execute', name, dict(args or {}), confirmed))
        if name == 'list_installed_apps':
            return {'status': 'ok', 'output': self.moai_listing}
        if name == 'open_app':
            return dict(self.open_result)
        return {'status': 'error', 'error': 'unexpected'}

    def get(self, path, timeout=20):
        self.calls.append(('get', path))
        return {'/scan': self.scan, '/health': self.health}.get(path, {'error': 'http_404'})

    def post(self, path, body, timeout=30):
        self.calls.append(('post', path, body))
        return {'started': True, 'scanning': True}

    def search_apps(self, query, limit=5):
        self.calls.append(('search', query, limit))
        return self.search

    def open_route(self, url):
        self.routes.append(url)
        return {'status': 'ok'}

    def patches(self):
        return [mock.patch.object(apps, '_flatpak_list', self.flatpak_list),
                mock.patch.object(apps, 'read_engines', self.read_engines),
                mock.patch.object(apps, 'phone_native', lambda: self.phone),
                mock.patch.object(moai_tools, 'execute', self.execute),
                mock.patch.object(moai_tools, 'get', self.get),
                mock.patch.object(moai_tools, 'post', self.post),
                mock.patch.object(moai_tools, 'search_apps', self.search_apps),
                mock.patch.object(moai_tools, 'names', lambda: set(TOOLS)),
                mock.patch.object(moai_tools, 'meta', lambda name: META.get(name)),
                mock.patch.object(moos_routes, 'open_route', self.open_route)]


class AppsPageTest(unittest.TestCase):
    def setUp(self):
        self.fakes = Fakes()
        for patch in self.fakes.patches():
            patch.start()
            self.addCleanup(patch.stop)
        self.host = Host()
        self.page = sync_page(self.host)

    def backend_writes(self):
        """Calls that could change the machine (only reads and open_app may run directly)."""
        return [c for c in self.fakes.calls if c[0] == 'execute' and c[1] not in ('list_installed_apps', 'open_app')]

    def hub(self, page=None):
        return {row['key']: row for row in (page or self.page).state['compat']}

    # ── words ───────────────────────────────────────────────────────
    def test_every_word_has_both_languages_and_no_foreign_os_name(self):
        for key, pair in apps.STRINGS.items():
            self.assertTrue(key.startswith('apps_'), key)
            self.assertEqual(len(pair), 2, key)
            self.assertTrue(all(isinstance(w, str) and w.strip() for w in pair), key)
            for word in pair:
                self.assertNotRegex(word.lower(), r'fedora|red hat|ubuntu|windows 1\d', key)
        self.assertEqual(i18n.table('en')['apps_install'], 'Install')
        self.assertEqual(i18n.table('ar')['apps_install'], 'تثبيت')

    def test_moos_never_names_the_engine_behind_a_platform(self):
        """The rule of tests/test_app_engines.py, on this page: a runtime or packaging word may only
        appear as a file name (.flatpakref), never as what MoOS itself says."""
        offenders = []
        for key, pair in apps.STRINGS.items():
            for word in pair:
                prose = re.sub(r'\.(flatpakref|flatpak|appimage)\b', '', word.lower())
                offenders += [(key, brand) for brand in RUNTIME_WORDS if re.search(rf'\b{brand}\b', prose)]
        self.assertEqual(offenders, [])
        self.assertIn('.AppImage', apps.STRINGS['apps_kinds'][1])
        # and every card the page writes itself (install, remove, update, the hub's set-ups)
        for lang in ('ar', 'en'):
            host = Host(lang)
            page = sync_page(host)
            page.refresh()
            page.install('org.mozilla.firefox')
            page.remove('org.videolan.VLC')
            page.updateAll()
            for key in ('games', 'windows', 'android'):
                page._engines = {'windows': engine(False, present=False), 'android': engine(False, needs_setup=True)}
                page._have = set()
                page.setup(key)
            self.assertEqual({a['name'] for a in host.asked},
                             {'install_app', 'uninstall_app', 'update_apps', 'setup_gaming', 'setup_windows', 'setup_waydroid'})
            for card in host.asked:
                fixed = card['detail'].split('\n', 1)[-1].lower()     # the app's own name is data, the rest is MoOS
                for brand in RUNTIME_WORDS + ('flathub',):
                    self.assertNotRegex(fixed, rf'\b{brand}\b', (lang, card['name']))

    def test_activation_in_test_mode_reads_nothing(self):
        self.page.activated()
        self.assertEqual(self.fakes.calls, [])

    # ── reading ─────────────────────────────────────────────────────
    def test_refresh_maps_installed_scan_health_and_engines(self):
        self.page.refresh()
        state = self.page.state
        self.assertEqual([a['id'] for a in state['installed']],
                         ['cn.navclub.ldbfx', 'com.valvesoftware.Steam', 'org.videolan.VLC', 'io.github.kolunmi.Bazaar'])
        self.assertEqual(state['installed'][0]['scope'], 'system')
        self.assertEqual(state['installed'][3]['name'], 'بازار')
        self.assertTrue(state['installed_read'])
        self.assertFalse(state['installed_partial'])
        self.assertFalse(state['installed_loading'] or state['scan_loading'] or state['updates_loading'])
        self.assertNotIn(('execute', 'list_installed_apps', {}, False), self.fakes.calls,
                         'the machine\'s own list is read first: no trimmed tool output')
        # recommended: VLC is installed already, the bad id is dropped, an unknown id keeps a readable name
        self.assertEqual([r['id'] for r in state['recommended']], ['org.mozilla.firefox', 'org.example.Unknown'])
        self.assertEqual(state['recommended'][0]['name'], 'Firefox')
        self.assertEqual(state['recommended'][1]['name'], 'Unknown')
        self.assertEqual(state['updates'], ['Telegram Desktop', 'Steam'])
        self.assertTrue(state['updates_checked'] and state['updates_report'])
        self.assertEqual(state['updates_at'], '2026-09-29T18:42:55+00:00')
        hub = self.hub()
        self.assertEqual(hub['games']['state'], 'ready')
        self.assertEqual(hub['games']['opens'], 'com.valvesoftware.Steam')
        self.assertEqual(hub['windows']['state'], 'ready', 'the image\'s own runtime runs .exe: no download offered')
        self.assertEqual(hub['windows']['opens'], '')
        self.assertEqual(hub['windows']['detail'], 'apps_c_windows_ready_d', 'not "isolated": the image runtime is not')
        self.assertEqual(hub['android']['state'], 'setup')
        self.assertTrue(hub['android']['privileged'])
        self.assertEqual(hub['phone']['state'], 'ready')
        self.assertEqual(hub['vm']['state'], 'ready')
        self.assertEqual(self.backend_writes(), [])

    def test_the_phone_is_the_image_own_link_never_a_download(self):
        self.page.refresh()
        phone = self.hub()['phone']
        self.assertEqual((phone['state'], phone['opens'], phone['sheet'], phone['tool']),
                         ('ready', 'org.kde.kdeconnect.app', 'connect', ''))
        self.page.setup('phone')
        self.assertEqual(self.host.asked, [], 'there is no phone set-up card: the link ships in the image')
        self.page.openApp(phone['opens'])
        self.assertIn(('execute', 'open_app', {'app_id': 'org.kde.kdeconnect.app'}, False), self.fakes.calls)
        self.assertEqual(self.host.toast.shown[-1], ('ok', 'فتحت الهاتف'))
        self.page.showPage('connect')
        self.page.showPage('settings')                                   # not a page this one links to
        self.assertEqual(self.host.showSheet.shown, ['connect'])
        self.fakes.phone = False
        self.page.refresh()
        phone = self.hub()['phone']
        self.assertEqual((phone['state'], phone['opens'], phone['detail']), ('unavailable', '', 'apps_c_phone_missing'))
        self.assertNotIn('org.kde.kdeconnect', apps.RECOMMENDED)

    def test_phone_native_reads_the_desktop_entry(self):
        with tempfile.TemporaryDirectory() as data, \
             mock.patch.object(apps.shutil, 'which', lambda name: None), \
             mock.patch.dict(os.environ, {'XDG_DATA_HOME': data, 'XDG_DATA_DIRS': data}):
            self.assertFalse(PHONE_NATIVE())
            (Path(data) / 'applications').mkdir()
            (Path(data) / 'applications' / 'org.kde.kdeconnect.app.desktop').write_text('[Desktop Entry]\n')
            self.assertTrue(PHONE_NATIVE())

    def test_engines_come_from_the_resolver(self):
        # a machine where the isolated space is installed and Android is ready
        self.fakes.engines = {'status': 'ok', 'engines': {
            'windows': engine(True, chosen='com.usebottles.bottles', sandboxed=True),
            'android': engine(True, chosen='waydroid', sandboxed=True)}}
        self.fakes.listing = LISTING + 'com.usebottles.bottles\tBottles\t67.3\tuser\n'
        self.page.refresh()
        hub = self.hub()
        self.assertEqual((hub['windows']['state'], hub['windows']['opens'], hub['windows']['detail']),
                         ('ready', 'com.usebottles.bottles', 'apps_c_windows_d'))
        self.assertEqual((hub['android']['state'], hub['android']['detail']), ('ready', 'apps_c_android_ready_d'))
        self.page.setup('windows')
        self.page.setup('android')
        self.assertEqual(self.host.asked, [], 'nothing ready is set up again')
        # an edition that ships no Windows runtime, and a machine without the Android runtime
        self.fakes.engines = {'status': 'ok', 'engines': {'windows': engine(False, present=False),
                                                          'android': engine(False, present=False)}}
        self.page.refresh()
        hub = self.hub()
        self.assertEqual(hub['windows']['state'], 'setup')
        self.assertEqual(hub['android']['state'], 'unavailable')
        # the resolver cannot answer: nothing is claimed, nothing is offered
        self.fakes.engines = {'status': 'error', 'error': 'no_resolver'}
        self.page.refresh()
        hub = self.hub()
        self.assertEqual((hub['windows']['state'], hub['android']['state']), ('unknown', 'unknown'))
        self.page.setup('windows')
        self.assertEqual(self.host.asked, [])

    def test_read_engines_maps_the_resolver_output(self):
        output = ('{"engines": [{"engine": "windows", "runtimes": [{"id": "com.usebottles.bottles", "present": false},'
                  ' {"id": "wine", "present": true}], "chosen": {"id": "wine", "sandboxed": false}, "ready": true,'
                  ' "needs_setup": false, "provision_route": "moos://do/setup-windows"},'
                  ' {"engine": "android", "runtimes": [{"id": "waydroid", "present": true}], "chosen": null,'
                  ' "ready": false, "needs_setup": true, "provision_route": "moos://do/setup-waydroid"}], "unsupported": []}')
        done = mock.Mock(stdout=output, returncode=0)
        with tempfile.NamedTemporaryFile() as resolver, \
             mock.patch.object(apps, 'ENGINE_RESOLVER', Path(resolver.name)), \
             mock.patch.object(apps.subprocess, 'run', return_value=done) as run:
            answer = READ_ENGINES()
        self.assertEqual(run.call_args[0][0], [resolver.name, 'list'])
        self.assertEqual(answer['engines']['windows'], engine(True, chosen='wine'))
        self.assertEqual(answer['engines']['android'], engine(False, needs_setup=True, chosen=''))
        with mock.patch.object(apps, 'ENGINE_RESOLVER', Path('/nonexistent/moos-app-engine')):
            self.assertEqual(READ_ENGINES(), {'status': 'error', 'error': 'no_resolver'})

    def test_arm_hides_the_x86_only_rows(self):
        self.fakes.scan = {**SCAN, 'arch': 'aarch64'}
        self.page.refresh()
        keys = [r['key'] for r in self.page.state['compat']]
        self.assertNotIn('games', keys)
        self.assertNotIn('windows', keys)
        self.assertIn('android', keys)
        self.page.setup('games')
        self.assertEqual(self.host.asked, [])
        with mock.patch.object(apps.platform, 'machine', lambda: 'aarch64'):
            page = sync_page(Host())
            page._scan_arch = ''
            page._scan_compat = dict(SCAN['compatibility'])
            self.assertNotIn('windows', [r['key'] for r in page._compat_rows()])

    def test_read_failures_are_shown_in_words_not_codes(self):
        self.fakes.listing = None
        with mock.patch.object(moai_tools, 'execute', lambda *a, **k: {'status': 'error', 'error': 'moai_control_unreachable',
                                                                      'summary': 'تعذّر: التطبيقات المثبتة'}), \
             mock.patch.object(moai_tools, 'get', lambda *a, **k: {'error': 'moai_control_unreachable'}):
            self.page.refresh()
        state = self.page.state
        said = self.host.s['apps_err_unreachable']
        self.assertTrue(state['installed_failed'] and state['scan_failed'] and state['updates_failed'])
        self.assertEqual((state['installed_error'], state['scan_error'], state['updates_error']), (said, said, said))
        self.assertEqual(state['compat'], [])
        self.assertFalse(state['installed_read'])
        with mock.patch.object(moai_tools, 'get', lambda *a, **k: {'error': 'http_404'}):
            self.page.refresh()
        self.assertTrue(self.page.state['scan_failed'])
        self.assertEqual(self.page.state['scan_error'], '', 'a bare code adds nothing to "could not read"')

    def test_a_trimmed_listing_is_partial_and_proves_no_absence(self):
        """moai-control keeps the last 6000 chars: the first apps vanish and the next line is cut."""
        self.fakes.listing = None
        self.fakes.moai_listing = ('[… earlier output trimmed]\nb.tchx84.Flatseal\tFlatseal\t2.3\tuser\n'
                                   'com.valvesoftware.Steam\tSteam\t[redacted]\tuser\n')
        self.page.refresh()
        state = self.page.state
        self.assertEqual([a['id'] for a in state['installed']], ['com.valvesoftware.Steam'])
        self.assertEqual(state['installed'][0]['version'], '', '"[redacted]" is no version')
        self.assertTrue(state['installed_partial'])
        # VLC is not in the partial list: it is not claimed missing, nor removed, nor recommended again
        self.page.remove('org.videolan.VLC')
        self.page._watch()
        self.assertEqual(self.page.state['pending'], {'org.videolan.VLC': 'remove'})
        self.assertFalse(any(kind == 'ok' for kind, _ in self.host.toast.shown))
        self.assertEqual(self.hub()['games']['state'], 'ready')

    def test_parse_installed(self):
        self.assertEqual(apps.parse_installed(''), ([], False))
        self.assertEqual(apps.parse_installed('[flatpak is not available on this machine]'), ([], False))
        parsed, partial = apps.parse_installed('org.b.B\t\t1\norg.a.A\tAlpha\norg.a.A\tDup\n')
        self.assertEqual([(a['id'], a['name']) for a in parsed], [('org.a.A', 'Alpha'), ('org.b.B', 'org.b.B')])
        self.assertFalse(partial)
        # moos-inspect keeps the FIRST part: the line before its note is cut
        parsed, partial = apps.parse_installed('org.a.A\tA\t1\tuser\norg.mozilla.fire\n[truncated to 12 KB; kept the first part]')
        self.assertEqual([a['id'] for a in parsed], ['org.a.A'])
        self.assertTrue(partial)

    def test_no_daily_check_yet_is_not_an_error(self):
        self.fakes.health = {'report': None, 'scanning': False}
        self.page.refresh()
        self.assertFalse(self.page.state['updates_failed'])
        self.assertFalse(self.page.state['updates_checked'] or self.page.state['updates_report'])

    def test_a_check_that_could_not_reach_the_store_is_not_up_to_date(self):
        self.fakes.health = {'scanning': False, 'report': {'generated_at': '2026-09-29T18:42:55+00:00',
                                                           'updates': {'checked': False, 'apps': ['Stale']}}}
        self.page.refresh()
        state = self.page.state
        self.assertTrue(state['updates_report'])
        self.assertFalse(state['updates_checked'])
        self.assertEqual(state['updates'], [], 'an unchecked list is not shown as waiting updates')

    def test_a_health_error_clears_old_update_chips(self):
        self.page.refresh()
        self.assertTrue(self.page.state['updates'])
        self.fakes.health = {'error': 'moai_control_unreachable'}
        self.page.refresh()
        self.assertEqual(self.page.state['updates'], [])
        self.assertTrue(self.page.state['updates_failed'])

    # ── the store ───────────────────────────────────────────────────
    def test_search_maps_results_and_sanitises_icons(self):
        self.page.refresh()
        self.page.search('  video   player ')
        state = self.page.state
        self.assertEqual(state['query'], 'video player')
        self.assertIn(('search', 'video player', 12), self.fakes.calls)
        self.assertEqual([r['id'] for r in state['results']], ['org.videolan.VLC', 'org.kde.kdenlive', 'cn.navclub.ldbfx'])
        vlc, kdenlive, system_app = state['results']
        self.assertTrue(vlc['installed'], 'the installed list is newer than the search')
        self.assertEqual(vlc['scope'], 'user')
        self.assertEqual(system_app['scope'], 'system', 'the scope travels from the installed list')
        self.assertEqual(kdenlive['icon'], '', 'only Flathub media URLs are loaded')
        self.assertEqual(kdenlive['note'], 'محرّر فيديو أصلي')
        self.assertTrue(kdenlive['recommended'])
        self.assertEqual(kdenlive['installs'], 61230)
        self.assertFalse(state['searching'])
        self.assertTrue(state['searched'])

    def test_remote_icon_kept_for_a_store_app_not_installed(self):
        self.page.search('vlc')
        self.assertTrue(self.page.state['results'][0]['icon'].startswith('https://dl.flathub.org/media/'))

    def test_search_error_says_why_once_in_the_owner_language(self):
        self.fakes.search = {'status': 'error', 'error': 'http_502', 'summary': 'تعذّر البحث في المتجر'}
        page = sync_page(Host('en'))
        page.search('vlc')
        self.assertTrue(page.state['search_failed'])
        self.assertEqual(page.state['search_error'], '', '"did not answer" is not said twice')
        self.fakes.search = {'status': 'error', 'error': 'moai_control_unreachable', 'summary': 'تعذّر البحث في المتجر'}
        self.page.search('vlc')
        self.assertEqual(self.page.state['search_error'], self.host.s['apps_err_unreachable'])
        self.assertNotEqual(self.page.state['search_error'], self.host.s['apps_search_failed'])
        self.fakes.search = {'status': 'error', 'error': 'forbidden'}
        self.page.search('vlc')
        self.assertEqual(self.page.state['search_error'], '', 'a bare code is not repeated to the owner')
        self.fakes.search = {'status': 'ok', 'apps': []}
        self.page.search('zzzz')
        self.assertEqual(self.page.state['results'], [])
        self.assertFalse(self.page.state['search_failed'])
        self.page.search('   ')
        self.assertFalse(self.page.state['searched'])

    def test_a_stale_search_answer_is_dropped(self):
        self.page.update(query='new')
        self.page._deliver('search:old', {'status': 'ok', 'apps': [{'id': 'org.old.App', 'name': 'Old'}]})
        self.assertEqual(self.page.state['results'], [])

    def test_ask_mira_sends_only_on_click_and_opens_the_conversation(self):
        self.page.askMira('  برنامج مونتاج ')
        self.assertEqual(self.host.sent, ['ابحثي لي في المتجر عن تطبيق: برنامج مونتاج'])
        self.assertEqual(self.host.showSheet.shown, [''])
        self.page.askMira('   ')
        self.assertEqual(len(self.host.sent), 1)

    # ── changes become cards ────────────────────────────────────────
    def test_install_and_remove_are_cards_never_calls(self):
        self.page.refresh()
        self.page.install('org.mozilla.firefox')
        self.page.remove('org.videolan.VLC')
        self.assertEqual([(a['name'], a['args'], a['origin']) for a in self.host.asked],
                         [('install_app', {'app_id': 'org.mozilla.firefox'}, 'apps'),
                          ('uninstall_app', {'app_id': 'org.videolan.VLC'}, 'apps')])
        self.assertIn('Firefox · org.mozilla.firefox', self.host.asked[0]['detail'])
        self.assertIn(self.host.s['apps_install_store'], self.host.asked[0]['detail'])
        self.assertEqual(self.page.state['pending'], {'org.mozilla.firefox': 'install', 'org.videolan.VLC': 'remove'})
        self.assertEqual(self.backend_writes(), [])
        # asking twice while the card can still wait does not make a second card
        self.page.install('org.mozilla.firefox')
        self.assertEqual(len(self.host.asked), 2)

    def test_an_install_from_the_local_sources_says_so(self):
        self.fakes.search = {**self.fakes.search, 'source': 'local'}
        self.page.search('media')
        self.page.install('org.kde.kdenlive')
        self.assertIn(self.host.s['apps_install_local'], self.host.asked[-1]['detail'])

    def test_a_system_wide_app_is_never_offered_for_removal(self):
        self.page.refresh()
        self.page.remove('cn.navclub.ldbfx')
        self.assertEqual(self.host.asked, [], 'Mo Store would refuse it: no card that can only fail')
        self.assertEqual(self.host.toast.shown[-1], ('info', self.host.s['apps_system_no_remove']))

    def test_invalid_ids_never_reach_a_card(self):
        for bad in ('', 'vlc', 'org.videolan', '../../etc/passwd', 'org.x.y;rm', 'a.b.' + 'c' * 300):
            self.page.install(bad)
            self.page.remove(bad)
            self.page.openApp(bad)
        self.assertEqual(self.host.asked, [])
        self.assertEqual([c for c in self.fakes.calls if c[0] == 'execute'], [])
        self.assertTrue(all(kind == 'error' for kind, _ in self.host.toast.shown))

    def test_a_refused_card_is_said_and_nothing_is_marked(self):
        self.host.refuse = True
        self.page.install('org.mozilla.firefox')
        self.assertEqual(self.page.state['pending'], {})
        self.assertEqual(self.host.toast.shown[-1][0], 'error')

    def test_installed_is_claimed_only_when_the_list_says_so(self):
        self.page.refresh()
        self.page.install('org.mozilla.firefox')
        self.assertTrue(self.page._poll.isActive())
        self.page._watch()                                # still not in the list
        self.assertEqual(self.page.state['pending'], {'org.mozilla.firefox': 'install'})
        self.assertFalse(any(kind == 'ok' for kind, _ in self.host.toast.shown))
        self.fakes.listing = LISTING + 'org.mozilla.firefox\tFirefox\t131\tuser\n'
        self.page._watch()
        self.assertEqual(self.page.state['pending'], {})
        self.assertIn(('ok', 'Firefox · ثُبّت الآن'), self.host.toast.shown)
        self.assertNotIn('org.mozilla.firefox', [r['id'] for r in self.page.state['recommended']])
        self.page._watch()
        self.assertFalse(self.page._poll.isActive())

    def test_removed_is_claimed_only_when_the_list_says_so(self):
        self.page.refresh()
        self.page.remove('org.videolan.VLC')
        self.page._watch()
        self.assertEqual(self.page.state['pending'], {'org.videolan.VLC': 'remove'})
        self.fakes.listing = LISTING.replace('org.videolan.VLC\tVLC\t3.0.21\tuser\n', '')
        self.page._watch()
        self.assertEqual(self.page.state['pending'], {})
        self.assertEqual(self.host.toast.shown[-1][0], 'ok')

    def test_after_the_card_lifetime_the_page_stops_claiming_a_wait(self):
        self.page.refresh()
        self.page.install('org.mozilla.firefox')
        self.page._requests['org.mozilla.firefox']['at'] -= apps.CARD_WAIT_S + 5
        self.page._watch()
        self.assertEqual(self.page.state['pending'], {}, 'no "waiting for approval" once the card cannot wait')
        self.assertIn('org.mozilla.firefox', self.page._requests, 'still followed quietly')
        self.page._requests['org.mozilla.firefox']['at'] -= apps.WATCH_S
        self.page._watch()
        self.assertEqual(self.page._requests, {})

    def test_a_cancelled_card_can_be_asked_again_without_the_controller(self):
        """No hook from the controller: once the card's lifetime passed, Install asks a new card."""
        self.page.refresh()
        self.page.install('org.mozilla.firefox')
        self.page.install('org.mozilla.firefox')
        self.assertEqual(len(self.host.asked), 1)
        self.page._requests['org.mozilla.firefox']['at'] -= apps.CARD_WAIT_S + 1
        self.page.install('org.mozilla.firefox')
        self.assertEqual(len(self.host.asked), 2, 'the owner can ask again')
        self.assertEqual(self.page.state['pending'], {'org.mozilla.firefox': 'install'})
        self.assertEqual(self.page._requests['org.mozilla.firefox']['card'], 'p2')

    def test_the_controller_moves_a_card_on(self):
        self.page.refresh()
        self.page.install('org.mozilla.firefox')
        self.page.action_changed('p1', 'install_app', 'cancelled')
        self.assertEqual(self.page.state['pending'], {})
        self.assertEqual(self.page._requests, {})
        self.page.install('org.mozilla.firefox')                         # at once, a new card
        self.assertEqual(len(self.host.asked), 2)
        self.page.action_changed('p2', 'install_app', 'expired')
        self.assertEqual(self.page.state['pending'], {})
        self.page.remove('org.videolan.VLC')
        self.page.action_changed('p3', 'uninstall_app', 'error')
        self.assertEqual(self.host.toast.shown[-1][0], 'error')
        self.assertEqual(self.page.state['pending'], {})
        calls = len(self.fakes.calls)
        self.page.action_changed('unknown-card', 'install_app', 'ok')      # not ours: ignored
        self.page.action_changed('', 'install_app', 'ok')
        self.assertEqual(len(self.fakes.calls), calls)

    def test_an_approved_job_is_followed_then_told_as_it_ended(self):
        self.page.refresh()
        self.page.install('org.mozilla.firefox')
        self.page.action_changed('p1', 'install_app', 'running')
        self.assertEqual(self.page.state['pending'], {'org.mozilla.firefox': 'running'})
        self.page._requests['org.mozilla.firefox']['at'] -= apps.CARD_WAIT_S + 5
        self.page.install('org.mozilla.firefox')
        self.assertEqual(len(self.host.asked), 1, 'no second card while the approved job runs')
        self.page._watch()
        self.assertEqual(self.page.state['pending'], {'org.mozilla.firefox': 'running'}, 'still followed openly')
        # the job ended "ok" but the machine shows no change: said as it is
        self.page.action_changed('p1', 'install_app', 'ok')
        self.assertEqual(self.page._requests, {})
        self.assertEqual(self.host.toast.shown[-1], ('info', 'Firefox · لم يتغير شيء'))
        # and when it did change, the installed list says so
        self.page.install('org.mozilla.firefox')
        self.page.action_changed('p2', 'install_app', 'running')
        self.fakes.listing = LISTING + 'org.mozilla.firefox\tFirefox\t131\tuser\n'
        self.page.action_changed('p2', 'install_app', 'ok')
        self.assertEqual(self.host.toast.shown[-1], ('ok', 'Firefox · ثُبّت الآن'))

    def test_open_runs_directly_and_reports_the_executor(self):
        self.page.refresh()
        self.page.openApp('org.videolan.VLC')
        self.assertIn(('execute', 'open_app', {'app_id': 'org.videolan.VLC'}, False), self.fakes.calls)
        self.assertEqual(self.host.toast.shown[-1], ('ok', 'فتحت VLC'))
        self.assertEqual(self.page.state['pending'], {})
        self.fakes.open_result = {'status': 'error', 'output': 'line one\nno such app'}
        self.page.openApp('org.videolan.VLC')
        self.assertEqual(self.host.toast.shown[-1], ('error', 'تعذّر فتح التطبيق: no such app'))
        self.fakes.open_result = {'status': 'confirm'}
        self.page.openApp('org.videolan.VLC')
        self.assertEqual(self.host.asked[-1]['name'], 'open_app')

    def test_update_all_is_a_card_naming_what_waits(self):
        self.page.refresh()
        self.page.updateAll()
        self.assertEqual(self.host.asked[-1]['name'], 'update_apps')
        self.assertEqual(self.host.asked[-1]['args'], {})
        self.assertIn('Telegram Desktop', self.host.asked[-1]['detail'])
        self.assertEqual(self.page.state['pending'].get('__updates__'), 'update')
        self.page.updateAll()
        self.assertEqual(len(self.host.asked), 1)
        self.page.action_changed('p1', 'update_apps', 'running')
        self.assertEqual(self.page.state['pending'].get('__updates__'), 'running')
        self.page.action_changed('p1', 'update_apps', 'ok')                 # then the check runs again
        self.assertIn(('post', '/health/scan', {}), self.fakes.calls)
        self.assertEqual(self.page.state['pending'], {})

    def test_check_now_follows_the_daily_check_to_its_end(self):
        self.page.checkUpdates()
        self.assertIn(('post', '/health/scan', {}), self.fakes.calls)
        self.assertTrue(self.page.state['updates_scanning'])
        self.assertTrue(self.page._health_timer.isActive())
        self.page._health_timer.stop()
        self.fakes.health = {**HEALTH, 'scanning': True}
        self.page._read_health()
        self.assertTrue(self.page.state['updates_scanning'])
        self.assertTrue(self.page._health_timer.isActive())
        self.assertEqual(self.page._health_timer.interval(), apps.HEALTH_FAST_MS)
        self.page._health_timer.stop()
        self.fakes.health = HEALTH
        self.page._read_health()
        self.assertFalse(self.page.state['updates_scanning'])
        self.assertFalse(self.page._health_timer.isActive())

    def test_a_check_that_outlasts_the_polls_stops_claiming_it_runs(self):
        self.fakes.health = {**HEALTH, 'scanning': True}
        self.page.checkUpdates()
        self.page._health_polls = apps.HEALTH_FAST_POLLS + 1
        self.page._read_health()
        self.assertEqual(self.page._health_timer.interval(), apps.HEALTH_SLOW_MS, 'slower, not abandoned')
        self.page._health_timer.stop()
        self.page._health_polls = apps.HEALTH_MAX_POLLS
        self.page._read_health()
        self.assertFalse(self.page.state['updates_scanning'], 'the spinner and the disabled button end')
        self.assertEqual(self.page.state['updates_note'], 'apps_check_slow')
        self.assertFalse(self.page._health_timer.isActive())

    def test_install_all_is_one_card_per_app_without_smart_setup(self):
        self.page.refresh()
        self.page.installAllRecommended()
        self.assertEqual([a['args']['app_id'] for a in self.host.asked], ['org.mozilla.firefox', 'org.example.Unknown'])
        self.page.installAllRecommended()
        self.assertEqual(len(self.host.asked), 2, 'nothing is asked twice')

    def test_install_all_uses_smart_setup_when_the_executor_declares_it(self):
        with mock.patch.object(moai_tools, 'names', lambda: set(TOOLS) | {'smart_setup'}):
            self.page.refresh()
            self.page.installAllRecommended()
        self.assertEqual([a['name'] for a in self.host.asked], ['smart_setup'])
        self.assertEqual(self.page.state['pending'], {'org.mozilla.firefox': 'install', 'org.example.Unknown': 'install'})
        self.page.action_changed('p1', 'smart_setup', 'cancelled')
        self.assertEqual(self.page.state['pending'], {}, 'one card, every app it covered is released')

    def test_hub_set_up_asks_with_the_right_tool(self):
        self.fakes.listing = LISTING.replace('com.valvesoftware.Steam\tSteam\t1.0.0.87\tuser\n', '')
        self.fakes.engines = {'status': 'ok', 'engines': {'windows': engine(False, present=False),
                                                          'android': engine(False, needs_setup=True)}}
        self.page.refresh()
        self.assertEqual(self.hub()['games']['state'], 'setup')
        for key in ('games', 'windows', 'android', 'phone', 'vm', 'rm -rf'):
            self.page.setup(key)
        self.assertEqual([(a['name'], a['args']) for a in self.host.asked],
                         [('setup_gaming', {}), ('setup_windows', {}), ('setup_waydroid', {})])
        self.assertIn('كلمة المرور', self.host.asked[2]['detail'])
        hub = self.hub()
        self.assertTrue(all(hub[k]['waiting'] == 'setup' for k in ('games', 'windows', 'android')))
        # set-up is done when the machine says so (the resolver now answers ready)
        self.fakes.engines = {'status': 'ok', 'engines': {'windows': engine(True, chosen='com.usebottles.bottles', sandboxed=True),
                                                          'android': engine(False, needs_setup=True)}}
        self.page._watch()
        hub = self.hub()
        self.assertEqual(hub['windows']['state'], 'ready')
        self.assertEqual(hub['windows']['waiting'], '')
        self.assertEqual(hub['android']['waiting'], 'setup')
        self.assertIn(('ok', 'برامج ويندوز · جاهز'), self.host.toast.shown)

    def test_a_set_up_the_resolver_answers_ends_on_its_answer(self):
        self.fakes.engines = {'status': 'ok', 'engines': {'windows': engine(False, present=False),
                                                          'android': engine(False, needs_setup=True)}}
        self.page.refresh()
        self.page.setup('windows')
        self.page.action_changed('p1', 'setup_windows', 'running')
        self.assertEqual(self.hub()['windows']['waiting'], 'running')
        # a resolver read already out when the job ends may predate it: it settles nothing
        self.page._engines_reading = True
        self.page.action_changed('p1', 'setup_windows', 'ok')
        self.assertIn('windows', self.page._requests)
        self.fakes.engines = {'status': 'ok', 'engines': {'windows': engine(True, chosen='com.usebottles.bottles', sandboxed=True),
                                                          'android': engine(False, needs_setup=True)}}
        self.page._deliver('engines', {'status': 'ok', 'engines': {'windows': engine(False, present=False)}})
        self.assertEqual(self.page._requests, {})
        self.assertEqual(self.host.toast.shown[-1], ('ok', 'برامج ويندوز · جاهز'))
        self.assertEqual(self.hub()['windows']['state'], 'ready')
        # the job ended "ok" and the resolver still says not ready: told as it is
        self.page.setup('android')
        self.page.action_changed('p2', 'setup_waydroid', 'ok')
        self.assertEqual(self.host.toast.shown[-1], ('info', 'تطبيقات أندرويد · لم يتغير شيء'))

    def test_english_details(self):
        page = sync_page(Host('en'))
        page.refresh()
        page.install('org.mozilla.firefox')
        self.assertIn('no admin rights', page.host.asked[-1]['detail'])
        page.openApp('org.videolan.VLC')
        self.assertEqual(page.host.toast.shown[-1], ('ok', 'Opened VLC'))

    # ── an app from a file ──────────────────────────────────────────
    def test_files_go_to_app_drop_and_rpms_to_the_signed_route(self):
        with tempfile.TemporaryDirectory() as home:
            home = Path(home)
            (home / 'Downloads').mkdir()
            appimage = home / 'Downloads' / 'Obsidian 1.8.AppImage'
            appimage.write_bytes(b'\x7fELF\x02\x01\x01\x00AI\x02' + b'\0' * 32)
            rpm = home / 'Downloads' / 'tool.rpm'
            rpm.write_bytes(b'\xed\xab\xee\xdb' + b'\0' * 32)
            stray_rpm = home / 'tool.rpm'
            stray_rpm.write_bytes(b'\xed\xab\xee\xdb' + b'\0' * 32)
            unnamed_rpm = home / 'Downloads' / 'tool.package'
            unnamed_rpm.write_bytes(b'\xed\xab\xee\xdb' + b'\0' * 32)
            link = home / 'Downloads' / 'link.AppImage'
            link.symlink_to(appimage)
            with mock.patch.object(Path, 'home', lambda: home):
                self.page.installFile(QUrl.fromLocalFile(str(appimage)).toString())
                self.assertEqual(self.page.state['file_tone'], 'pending')
                self.assertEqual(self.page.state['file_status'],
                                 f"{self.host.s['apps_file_sent']} — Obsidian 1.8.AppImage")
                self.assertTrue(self.fakes.routes[-1].startswith('moos://apps/install-file/file%3A%2F%2F%2F'))
                self.assertTrue(moos_routes.allowed(self.fakes.routes[-1]))
                self.page.installFile(str(rpm))
                self.assertTrue(self.fakes.routes[-1].startswith('moos://apps/install-rpm/'))
                self.assertIn('التوقيع', self.page.state['file_status'])
                routes = len(self.fakes.routes)
                self.page.installFile(str(stray_rpm))
                self.assertEqual(self.page.state['file_tone'], 'error')
                self.assertEqual(self.page.state['file_status'], self.host.s['apps_file_rpm_folder'])
                self.page.installFile(str(unnamed_rpm))
                self.assertEqual(self.page.state['file_status'], self.host.s['apps_file_rpm_name'])
                self.page.installFile(str(link))
                self.assertEqual(self.page.state['file_status'], self.host.s['apps_file_link'])
                someone_else = os.getuid() + 1
                with mock.patch.object(apps.os, 'getuid', lambda: someone_else):
                    self.page.installFile(str(appimage))
                self.assertEqual(self.page.state['file_status'], self.host.s['apps_file_not_yours'])
                self.page.installFile('/etc/passwd')
                self.assertEqual(self.page.state['file_status'], self.host.s['apps_file_outside'])
                self.page.installFile(str(home / 'Downloads' / 'missing.AppImage'))
                self.assertEqual(self.page.state['file_tone'], 'error')
                deep = home / 'Downloads' / ('ملف' * 40)
                deep.mkdir()
                long_file = deep / 'app.AppImage'
                long_file.write_bytes(b'\x7fELF' + b'\0' * 32)
                self.page.installFile(str(long_file))
                self.assertEqual(self.page.state['file_status'], self.host.s['apps_file_long'])
                self.assertEqual(len(self.fakes.routes), routes, 'refused files open nothing')
                # several dropped at once: the first goes, and the page says only the first did
                self.page.installDropped([QUrl.fromLocalFile(str(appimage)).toString(), str(rpm)])
                self.assertEqual(len(self.fakes.routes), routes + 1)
                self.assertTrue(self.page.state['file_status'].endswith(self.host.s['apps_file_more']))
        self.assertEqual(self.host.asked, [], 'App Drop asks the owner itself: no second card')

    def test_open_store_uses_the_fixed_route(self):
        self.page.openStore()
        self.assertEqual(self.fakes.routes, ['moos://app/store'])
        self.assertTrue(moos_routes.allowed('moos://app/store'))

    # ── review and threads ──────────────────────────────────────────
    def test_review_fills_every_section(self):
        self.page.review()
        state = self.page.state
        for key in ('results', 'installed', 'updates', 'recommended', 'compat'):
            self.assertTrue(state[key], key)
        self.assertTrue(state['searched'] and state['installed_read'] and state['scanned'])
        self.assertEqual(self.fakes.calls, [], 'review data is sample data: nothing is read')
        self.assertEqual({r['key']: r['state'] for r in state['compat']}['phone'], 'ready')

    def test_the_threaded_path_delivers_on_the_qt_thread(self):
        page = apps.AppsPage(Host())
        threads = []
        handler = page.on_installed

        def record(tag, result):
            threads.append(threading.current_thread())
            handler(tag, result)
        page.on_installed = record
        page.refresh()
        end = time.monotonic() + 5
        while time.monotonic() < end and (page.state['installed_loading'] or page.state['scan_loading']
                                          or page.state['updates_loading'] or page._engines_reading):
            QCoreApplication.processEvents()
            time.sleep(0.01)
        self.assertTrue(page.state['installed_read'])
        self.assertEqual(page.state['updates'], ['Telegram Desktop', 'Steam'])
        self.assertEqual(threads, [threading.main_thread()], 'the result is handled on the Qt (main) thread')
        self.assertEqual({r['key']: r['state'] for r in page.state['compat']}['windows'], 'ready')


# the real functions, captured before any test patches the module
PHONE_NATIVE = apps.phone_native
READ_ENGINES = apps.read_engines


if __name__ == '__main__':
    unittest.main()
