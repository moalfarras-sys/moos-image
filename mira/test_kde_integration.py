"""Mira inside KDE Plasma: launch arguments, Dolphin requests, login start and the D-Bus door.

Every backend is a stand-in: systemctl is a fake runner, the autostart folder, the launcher and
the home folder are temporary, the agent workspace is a recorded function, and the D-Bus tests run
on a private dbus-daemon started here — never the owner's session bus.

The glue classes (AppLaunchRequest, ControllerGlue, QmlReachesKde) prove that what Plasma and
Dolphin hand Mira reaches a real handler: app.py parses it, the controller routes it to mira.kde,
and every mira.kde call in her QML is a slot that exists. A menu entry whose argument nobody reads
is a dead button.
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_QUICK_BACKEND', 'software')
os.environ['MIRA_TEST_MODE'] = '1'
_config = tempfile.TemporaryDirectory(prefix='mira-kde-test-')
os.environ['XDG_CONFIG_HOME'] = _config.name

from PySide6.QtCore import QCoreApplication, QMetaMethod, QObject, QSettings, Signal  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

import kde_integration as kde  # noqa: E402

APP = QGuiApplication.instance() or QGuiApplication([])
QSettings.setDefaultFormat(QSettings.IniFormat)
QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, _config.name)
ROOT = Path(__file__).resolve().parent
LRI, FSI, PDI, RLO, ZWJ, ZWNJ = chr(0x2066), chr(0x2068), chr(0x2069), chr(0x202E), chr(0x200D), chr(0x200C)


def pump(predicate=lambda: False, timeout=2.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        QCoreApplication.processEvents()
        if predicate():
            return True
        time.sleep(0.005)
    return predicate()


def slots_of(meta):
    names = set()
    for i in range(meta.methodCount()):
        method = meta.method(i)
        if method.methodType() in (QMetaMethod.Slot, QMetaMethod.Method):
            names.add(bytes(method.name().data()).decode())
    return names


# ─── launch arguments ───────────────────────────────────────────────────────────────────────
class LaunchExtras(unittest.TestCase):
    def test_background_alone(self):
        self.assertEqual(kde.launch_extras(['--background']), {'background': True})

    def test_ask_about_takes_every_path_until_the_next_flag(self):
        extras = kde.launch_extras(['--ask-about', '/home/a/x.txt', '/home/a/y.pdf', '--background'])
        self.assertEqual(extras['about'], ['/home/a/x.txt', '/home/a/y.pdf'])
        self.assertTrue(extras['background'])
        self.assertEqual(extras['panel'], 'chat')

    def test_ask_about_equals_form_and_cap(self):
        self.assertEqual(kde.launch_extras(['--ask-about=/tmp/a'])['about'], ['/tmp/a'])
        many = ['/p%d' % i for i in range(40)]
        self.assertEqual(len(kde.launch_extras(['--ask-about'] + many)['about']), kde.MAX_PATHS)

    def test_ask_about_without_a_path_is_nothing(self):
        self.assertEqual(kde.launch_extras(['--ask-about']), {})
        self.assertEqual(kde.launch_extras(['--ask-about', '--background']), {'background': True})

    def test_add_project_opens_the_workbench(self):
        self.assertEqual(kde.launch_extras(['--add-project', '/home/a/src']),
                         {'project': '/home/a/src', 'panel': 'workbench'})
        self.assertEqual(kde.launch_extras(['--add-project=/home/a/src'])['project'], '/home/a/src')

    def test_add_project_without_a_folder_is_ignored(self):
        self.assertEqual(kde.launch_extras(['--add-project']), {})
        self.assertEqual(kde.launch_extras(['--add-project', '--background']), {'background': True})

    def test_unrelated_arguments_pass_by(self):
        self.assertEqual(kde.launch_extras(['--panel', 'system', '--ask', 'hi', '--capture=/x.png']), {})

    # moos-open turns moos://ai/ask/<text> into `moai --panel chat --ask "<text>"`, and moai execs
    # `mira` with the same arguments: the text is a web page's, never an option.
    def test_a_link_s_question_is_never_read_as_an_option(self):
        for words in ('--add-project=/var/home/moos', '--ask-about=/var/home/moos/.ssh/id_ed25519',
                      '--background', '--ask-about', '--add-project'):
            with self.subTest(words=words):
                self.assertEqual(kde.launch_extras(['--panel', 'chat', '--ask', words]), {})

    def test_every_value_option_consumes_its_value(self):
        for option in kde.VALUE_OPTIONS:
            with self.subTest(option=option):
                self.assertEqual(kde.launch_extras([option, '--background']), {})
                self.assertEqual(kde.launch_extras([option, '--add-project', '/home/x']), {},
                                 'the stray folder after a consumed value is not a project')

    def test_a_real_option_after_a_value_still_counts(self):
        self.assertEqual(kde.launch_extras(['--ask', 'hi', '--background']), {'background': True})


class Prefill(unittest.TestCase):
    def test_one_clean_line(self):
        self.assertEqual(kde.clean_prefill('  hello\n\tworld  '), 'hello world')

    def test_control_and_direction_characters_are_removed(self):
        self.assertEqual(kde.clean_prefill('a\x00b' + RLO + 'c' + LRI + 'd\x1b'), 'a b c d')

    def test_joiners_stay(self):
        persian = 'می' + ZWNJ + 'خواهم'
        family = chr(0x1F468) + ZWJ + chr(0x1F469) + ZWJ + chr(0x1F467)
        self.assertEqual(kde.clean_prefill(persian + ' ' + family), persian + ' ' + family)

    def test_capped_at_the_composer_limit(self):
        self.assertEqual(len(kde.clean_prefill('x' * 5000)), kde.MAX_PREFILL)

    def test_a_cut_line_never_leaves_an_isolate_open(self):
        text = ' '.join(LRI + '/home/a/' + 'b' * 40 + PDI for _ in range(200))
        line = kde._one_line(text)
        self.assertLessEqual(len(line), kde.MAX_PREFILL)
        depth = 0
        for ch in line:
            depth += ch == LRI
            depth -= ch == PDI
            self.assertGreaterEqual(depth, 0)
        self.assertEqual(depth, 0)

    def test_the_message_limit_is_the_composer_s_and_the_controller_s(self):
        dock = (ROOT / 'qml/Mira/CommandDock.qml').read_text(encoding='utf-8')
        self.assertIn(f'readonly property int maxLength: {kde.MESSAGE_LIMIT}', dock)
        controller = (ROOT / 'controller.py').read_text(encoding='utf-8')
        self.assertIn(f'if len(text) > {kde.MESSAGE_LIMIT}:', controller)


# ─── Dolphin: ask about files ───────────────────────────────────────────────────────────────
class AskAbout(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='mira-kde-about-')
        self.root = Path(self.tmp.name)
        self.home = self.root / 'home'
        self.home.mkdir()
        (self.root / 'notes.md').write_text('# Plan\nship Mira\n', encoding='utf-8')
        (self.root / 'photo.png').write_bytes(b'\x89PNG\r\n\x1a\n\x00\x00')
        (self.root / 'sub').mkdir()
        (self.root / 'sub' / 'other.txt').write_text('x', encoding='utf-8')

    def tearDown(self):
        self.tmp.cleanup()

    def ask(self, paths, lang='en'):
        return kde.about_request([str(p) for p in paths], lang, home=self.home)

    def test_a_small_text_file_is_attached(self):
        request = self.ask([self.root / 'notes.md'])
        self.assertEqual(request['attachment'], {'name': 'notes.md', 'text': '# Plan\nship Mira\n'})
        self.assertEqual(request['text'], 'Tell me about this attached file: “' + FSI + 'notes.md' + PDI + '”')
        self.assertIsNone(request['notice'])

    def test_a_binary_file_is_named_with_its_folder(self):
        request = self.ask([self.root / 'photo.png'], 'ar')
        self.assertIsNone(request['attachment'])
        self.assertIn('«' + FSI + 'photo.png' + PDI + '»', request['text'])
        self.assertIn(LRI + str(self.root) + PDI, request['text'])
        self.assertTrue(request['text'].startswith('حدّثيني'))
        self.assertIsNone(request['notice'], 'naming a picture needs no explanation')

    # The reviewer's render: an Arabic line moved the leading slash of '/var/home/…' to the far end.
    def test_an_arabic_line_keeps_each_path_left_to_right(self):
        folder = self.root / 'مشاريع' / 'Projects'
        folder.mkdir(parents=True)
        (folder / 'a.bin').write_bytes(b'\x00\x01')
        text = self.ask([folder / 'a.bin'], 'ar')['text']
        self.assertIn(LRI + str(folder) + PDI, text)
        self.assertEqual(text.count(LRI) + text.count(FSI), text.count(PDI), 'every isolate is closed')

    def test_a_folder_is_asked_about_as_a_folder(self):
        request = self.ask([self.root / 'sub'])
        self.assertIn('the folder “' + FSI + 'sub' + PDI + '”', request['text'])

    def test_several_files_in_one_folder(self):
        request = self.ask([self.root / 'notes.md', self.root / 'photo.png'])
        self.assertIsNone(request['attachment'])
        self.assertIn('“' + FSI + 'notes.md' + PDI + '”, “' + FSI + 'photo.png' + PDI + '”', request['text'])
        self.assertIn(LRI + str(self.root) + PDI, request['text'])

    def test_files_in_different_folders_keep_their_paths(self):
        request = self.ask([self.root / 'notes.md', self.root / 'sub' / 'other.txt'], 'ar')
        self.assertIn(LRI + str(self.root / 'sub' / 'other.txt') + PDI, request['text'])
        self.assertIn('، ', request['text'])

    def test_a_file_url_is_accepted(self):
        request = kde.about_request(['file://' + str(self.root / 'photo.png')], 'en', home=self.home)
        self.assertIn('photo.png', request['text'])

    def test_missing_relative_remote_and_spoofed_paths_are_refused(self):
        spoof = self.root / ('invoice' + RLO + 'gpj.exe')
        spoof.write_text('x', encoding='utf-8')
        for value in [str(self.root / 'gone.txt'), 'notes.md', 'file://server/share/x',
                      str(spoof), str(self.root / 'notes.md') + '\n--ask evil', '']:
            self.assertIsNone(kde.about_request([value], 'en', home=self.home), value)

    def test_duplicates_collapse(self):
        path = str(self.root / 'photo.png')
        request = kde.about_request([path, path + '/', path], 'en', home=self.home)
        self.assertIn('the file “' + FSI + 'photo.png' + PDI + '”', request['text'])

    # One message holds 6000 characters (CommandDock.maxLength, controller.send). A file the
    # composer could never send is named, not attached.
    def test_a_text_file_too_long_for_one_message_is_named_and_the_owner_is_told(self):
        big = self.root / 'README.md'
        big.write_text('a' * 7000, encoding='utf-8')
        request = self.ask([big])
        self.assertIsNone(request['attachment'])
        self.assertIn(LRI + str(self.root) + PDI, request['text'])
        self.assertEqual(request['notice'], ('kde_ask_too_long', 'README.md'))

    def test_the_largest_file_that_still_fits_is_attached(self):
        path = self.root / 'fit.txt'
        question = kde._one_line(kde.STRINGS['kde_ask_attached'][1].format(name=FSI + 'fit.txt' + PDI))
        room = kde.MESSAGE_LIMIT - kde.TYPING_ROOM - len(question) - len('fit.txt') - 5
        path.write_text('b' * room, encoding='utf-8')
        request = self.ask([path])
        self.assertIsNotNone(request['attachment'])
        # what CommandDock.submit would send, with his own TYPING_ROOM words typed after the question
        typed = request['text'] + 'c' * kde.TYPING_ROOM
        joined = typed + '\n\n[' + request['attachment']['name'] + ']\n' + request['attachment']['text']
        self.assertEqual(len(joined), kde.MESSAGE_LIMIT)
        path.write_text('b' * (room + 1), encoding='utf-8')
        self.assertIsNone(self.ask([path])['attachment'])

    def test_length_is_measured_as_qml_measures_it(self):
        emoji = self.root / 'faces.txt'
        emoji.write_text(chr(0x1F600) * 2900, encoding='utf-8')      # 2900 characters, 5800 in QML
        self.assertIsNone(self.ask([emoji])['attachment'])

    def test_keys_and_passwords_are_named_never_attached(self):
        (self.home / '.ssh').mkdir()
        key = self.home / '.ssh' / 'id_ed25519'
        key.write_text('-----BEGIN OPENSSH PRIVATE KEY-----\nabc\n', encoding='utf-8')
        config = self.home / '.ssh' / 'config'
        config.write_text('Host echo\n', encoding='utf-8')
        project = self.root / 'project'
        project.mkdir()
        env = project / '.env'
        env.write_text('GEMINI_API_KEY=x\n', encoding='utf-8')
        pem = project / 'server.pem'
        pem.write_text('-----BEGIN PRIVATE KEY-----\n', encoding='utf-8')
        cosign = project / 'cosign.key'
        cosign.write_text('encrypted\n', encoding='utf-8')
        linked = project / 'harmless.txt'
        linked.symlink_to(key)
        for path in (key, config, env, pem, cosign, linked):
            with self.subTest(path=path.name):
                request = self.ask([path])
                self.assertIsNone(request['attachment'])
                self.assertEqual(request['notice'], ('kde_ask_private', path.name))
                self.assertNotIn('BEGIN', request['text'])

    def test_an_ordinary_text_file_named_like_code_is_still_attached(self):
        for name in ('test_island_tokens.py', 'tokenizer.py', 'keyboard.txt', 'env.py'):
            path = self.root / name
            path.write_text('x = 1\n', encoding='utf-8')
            self.assertIsNotNone(self.ask([path])['attachment'], name)


# ─── Dolphin: add a project ─────────────────────────────────────────────────────────────────
class AddProject(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='mira-kde-project-')
        base = Path(self.tmp.name)
        self.home = base / 'home'
        (self.home / 'code' / 'moos').mkdir(parents=True)
        (self.home / '.ssh').mkdir()
        (self.home / '.gnupg' / 'private-keys-v1.d').mkdir(parents=True)
        (self.home / 'file.txt').write_text('x', encoding='utf-8')
        (base / 'outside').mkdir()
        (self.home / 'escape').symlink_to(base / 'outside')
        (self.home / 'link-in').symlink_to(self.home / 'code' / 'moos')
        (self.home / 'code' / 'keys').symlink_to(self.home / '.ssh')
        self.calls = []

    def tearDown(self):
        self.tmp.cleanup()

    def post(self, reply):
        def fake(path, body):
            self.calls.append((path, body))
            return reply
        return fake

    def test_a_home_folder_is_added_and_read_back(self):
        folder = self.home / 'code' / 'moos'
        reply = {'ok': True, 'id': 'a' * 20, 'name': 'moos', 'path': str(folder)}
        result = kde.add_project(str(folder), post=self.post(reply), home=self.home)
        self.assertEqual(result, {'status': 'ok', 'id': 'a' * 20, 'name': 'moos', 'path': str(folder)})
        self.assertEqual(self.calls, [('/api/project/upsert', {'path': str(folder.resolve()), 'archived': False})])

    def test_a_symlink_inside_home_resolves_to_its_folder(self):
        reply = {'ok': True, 'id': 'b' * 20, 'name': 'moos'}
        kde.add_project(str(self.home / 'link-in'), post=self.post(reply), home=self.home)
        self.assertEqual(self.calls[0][1]['path'], str((self.home / 'code' / 'moos').resolve()))

    def test_refusals_never_reach_the_workspace(self):
        cases = {
            str(self.home / 'escape'): 'kde_project_outside_home',
            '/': 'kde_project_outside_home',
            str(self.home): 'kde_project_whole_home',
            str(self.home / 'code' / '..'): 'kde_project_whole_home',
            str(self.home / '.ssh'): 'kde_project_private',
            str(self.home / '.gnupg' / 'private-keys-v1.d'): 'kde_project_private',
            str(self.home / 'code' / 'keys'): 'kde_project_private',
            str(self.home / 'file.txt'): 'kde_project_not_folder',
            str(self.home / 'nothing'): 'kde_project_missing',
            'code/moos': 'kde_project_missing',
            '': 'kde_project_missing',
        }
        for value, reason in cases.items():
            result = kde.add_project(value, post=self.post({'ok': True, 'id': 'c' * 20}), home=self.home)
            self.assertEqual((result['status'], result['reason']), ('error', reason), value)
            self.assertIn(reason, kde.STRINGS)
        self.assertEqual(self.calls, [])

    def test_workspace_errors_are_reported_honestly(self):
        folder = str(self.home / 'code')
        unreachable = kde.add_project(folder, post=self.post({'error': 'agent_unreachable', 'detail': 'URLError'}),
                                      home=self.home)
        self.assertEqual(unreachable['reason'], 'kde_project_unreachable')
        refused = kde.add_project(folder, post=self.post({'error': 'project must be inside the real home directory'}),
                                  home=self.home)
        self.assertEqual(refused['reason'], 'kde_project_refused')
        for odd in ({'ok': True, 'id': 'not-an-id'}, {'id': 'd' * 20}, None, ['ok']):
            self.assertEqual(kde.add_project(folder, post=self.post(odd), home=self.home)['status'], 'error', odd)


# ─── login start ────────────────────────────────────────────────────────────────────────────
class FakeSystemctl:
    """systemctl --user for one unit: 'not-found' | 'disabled' | 'enabled' | 'masked'."""

    def __init__(self, state, fail_verbs=()):
        self.state = state
        self.fail_verbs = set(fail_verbs)
        self.calls = []

    def __call__(self, argv, timeout=10.0):
        self.calls.append(list(argv))
        assert argv[:2] == ['systemctl', '--user'] and argv[-1] == kde.UNIT, argv
        verb = argv[2]
        if verb == 'is-enabled':
            if self.state == 'not-found':
                return 4, 'not-found\n', ''
            return (0 if self.state in kde.UNIT_ON else 1), self.state + '\n', ''
        if verb in self.fail_verbs:
            return 1, '', 'Failed to enable unit: Access denied'
        if self.state in ('not-found', 'masked'):
            return 1, '', f'Failed: unit {self.state}'
        self.state = 'enabled' if verb == 'enable' else 'disabled'
        return 0, '', ''


def executable(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('#!/bin/sh\nexit 0\n', encoding='utf-8')
    path.chmod(0o755)
    return path


class Autostart(unittest.TestCase):
    """The user manager's generator runs an entry only when it finds its program on ITS PATH
    (MANAGER_PATH, here a stand-in /usr/bin), so Mira's entry names her launcher absolutely."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='mira-kde-autostart-')
        base = Path(self.tmp.name)
        self.config = base / 'config'
        self.folder = self.config / 'autostart'
        self.folder.mkdir(parents=True)
        self.home = base / 'home'
        self.usr_bin = base / 'usr' / 'bin'
        self.usr_bin.mkdir(parents=True)
        self.launcher = executable(self.home / '.local' / 'bin' / 'mira')   # a per-user install
        self.on_path = lambda name: str(self.launcher) if name == 'mira' else None
        self.nowhere = lambda name: None
        manager = patch.object(kde, 'MANAGER_PATH', (str(self.usr_bin),))
        manager.start()
        self.addCleanup(manager.stop)

    def tearDown(self):
        self.tmp.cleanup()

    def entry(self, name, exec_line, extra=''):
        path = self.folder / name
        path.write_text(f'[Desktop Entry]\nType=Application\nName=X\nExec={exec_line}\n{extra}', encoding='utf-8')
        return path

    def state(self, run, which=None):
        return kde.autostart_state(run, self.config, which or self.on_path, self.home)

    def set(self, enabled, run, which=None):
        return kde.set_autostart(enabled, run, self.config, which or self.on_path, self.home)

    def written(self):
        return kde._desktop_entry(self.folder / kde.AUTOSTART_NAME)

    # unit mode: the image ships mira.service
    def test_unit_mode_turns_on_and_reads_back(self):
        run = FakeSystemctl('disabled')
        self.assertEqual(self.state(run)['mode'], 'unit')
        self.assertFalse(self.state(run)['enabled'])
        result = self.set(True, run)
        self.assertEqual((result['status'], result['reason']), ('ok', 'kde_autostart_on'))
        self.assertTrue(result['enabled'] and result['background'])
        self.assertIn(['systemctl', '--user', 'enable', kde.UNIT], run.calls)
        self.assertEqual(list(self.folder.iterdir()), [], 'the unit mode writes no autostart entry')

    def test_unit_mode_replaces_the_window_opening_entry(self):
        run = FakeSystemctl('disabled')
        legacy = self.entry('mira.desktop', str(self.launcher))
        state = self.state(run)
        self.assertTrue(state['enabled'], 'the older entry already starts Mira at sign-in')
        self.assertTrue(state['window'], 'and it opens her window')
        self.assertEqual(state['legacy'], [str(legacy)])
        result = self.set(True, run)
        self.assertEqual(result['status'], 'ok')
        self.assertFalse(legacy.exists(), 'one mechanism at a time: two would start two copies')
        self.assertEqual(run.state, 'enabled')
        self.assertFalse(result['window'])

    def test_unit_mode_off_means_off(self):
        run = FakeSystemctl('enabled')
        legacy = self.entry('mira-old.desktop', f'{self.launcher} --background')
        result = self.set(False, run)
        self.assertEqual((result['status'], result['enabled']), ('ok', False))
        self.assertFalse(legacy.exists())
        self.assertIn(['systemctl', '--user', 'disable', kde.UNIT], run.calls)

    def test_entries_of_other_programs_are_never_touched(self):
        run = FakeSystemctl('enabled')
        others = [self.entry('moai.desktop', '/usr/bin/moai --panel chat'),
                  self.entry('firefox.desktop', 'firefox %u'),
                  self.entry('miracle.desktop', '/usr/bin/miracle')]
        self.set(False, run)
        self.assertTrue(all(p.exists() for p in others))

    def test_a_hidden_disabled_or_foreign_desktop_entry_does_not_count(self):
        run = FakeSystemctl('disabled')
        self.entry('a.desktop', str(self.launcher), 'Hidden=true\n')
        self.entry('b.desktop', str(self.launcher), 'X-GNOME-Autostart-enabled=false\n')
        self.entry('c.desktop', str(self.launcher), 'OnlyShowIn=GNOME;\n')
        self.entry('d.desktop', str(self.launcher), 'NotShowIn=KDE;\n')
        self.entry('e.desktop', str(self.launcher), 'X-systemd-skip=true\n')
        self.assertFalse(self.state(run)['enabled'])

    # The live station on 2026-09-29: a per-user install, no mira.service, and an entry the
    # generator refused ("could not find TryExec= binary mira") while the switch read ON.
    def test_a_bare_name_the_manager_cannot_find_does_not_count(self):
        run = FakeSystemctl('not-found')
        self.entry('mira.desktop', 'mira --background', 'TryExec=mira\n')
        self.assertFalse(self.state(run)['enabled'], 'the session would never run it')
        executable(self.usr_bin / 'mira')
        self.assertTrue(self.state(run)['enabled'], 'with /usr/bin/mira the generator finds it')

    def test_a_try_exec_the_manager_cannot_find_does_not_count(self):
        run = FakeSystemctl('not-found')
        self.entry('mira.desktop', f'{self.launcher} --background', 'TryExec=mira\n')
        self.assertFalse(self.state(run)['enabled'])

    def test_a_removed_launcher_does_not_count(self):
        run = FakeSystemctl('not-found')
        self.entry('mira.desktop', str(self.home / 'gone' / 'mira') + ' --background')
        self.assertFalse(self.state(run)['enabled'])

    def test_enable_failure_keeps_everything_and_says_why(self):
        run = FakeSystemctl('disabled', fail_verbs={'enable'})
        legacy = self.entry('mira.desktop', str(self.launcher))
        result = self.set(True, run)
        self.assertEqual((result['status'], result['reason']), ('error', 'kde_autostart_failed'))
        self.assertIn('Access denied', result['detail'])
        self.assertTrue(legacy.exists())

    def test_masked_unit_is_unavailable(self):
        run = FakeSystemctl('masked')
        self.assertFalse(self.state(run)['available'])
        result = self.set(True, run)
        self.assertEqual((result['status'], result['reason']), ('error', 'kde_autostart_masked'))
        self.assertEqual({c[2] for c in run.calls}, {'is-enabled'}, 'nothing is enabled behind a mask')

    # xdg mode: a per-user install
    def test_xdg_mode_names_the_launcher_by_its_absolute_path(self):
        run = FakeSystemctl('not-found')
        self.assertEqual(self.state(run)['mode'], 'xdg')
        result = self.set(True, run)
        self.assertEqual((result['status'], result['enabled'], result['background']), ('ok', True, True))
        entry = self.written()
        self.assertEqual(entry['Exec'], f'{self.launcher} --background')
        self.assertEqual(entry['TryExec'], str(self.launcher))
        self.assertTrue(entry['TryExec'].startswith('/'), 'the manager PATH has no ~/.local/bin')
        self.assertEqual(oct((self.folder / kde.AUTOSTART_NAME).stat().st_mode & 0o777), '0o644')
        self.assertEqual([c[2] for c in run.calls if c[2] != 'is-enabled'], [], 'no unit to enable')
        off = self.set(False, run)
        self.assertEqual((off['status'], off['enabled']), ('ok', False))
        self.assertFalse((self.folder / kde.AUTOSTART_NAME).exists())

    def test_a_launcher_path_with_reserved_characters_is_quoted_and_reads_back(self):
        odd = executable(Path(self.tmp.name) / 'my apps' / 'a$b"c\\d' / 'mira')
        run = FakeSystemctl('not-found')
        result = self.set(True, run, which=lambda name: str(odd))
        self.assertEqual((result['status'], result['enabled'], result['background']), ('ok', True, True))
        entry = self.written()
        self.assertTrue(entry['Exec'].startswith('"'), entry['Exec'])
        self.assertEqual(kde._exec_words(entry['Exec']), [str(odd), '--background'])
        self.assertEqual(kde._unescape(entry['TryExec']), str(odd))

    def test_turning_it_on_moves_a_window_opening_start_to_the_background(self):
        run = FakeSystemctl('not-found')
        self.entry('mira.desktop', str(self.launcher))
        self.assertTrue(self.state(run)['window'])
        result = self.set(True, run)
        self.assertEqual((result['status'], result['background'], result['window']), ('ok', True, False))
        self.assertEqual([p.name for p in self.folder.glob('*.desktop')], [kde.AUTOSTART_NAME])

    def test_the_per_user_launcher_is_found_without_path(self):
        self.assertEqual(kde.launcher_path(self.nowhere, self.home), str(self.launcher))
        self.assertEqual(self.state(FakeSystemctl('not-found'), which=self.nowhere)['mode'], 'xdg')

    def test_a_launcher_that_is_not_executable_is_no_launcher(self):
        self.launcher.chmod(0o644)
        self.assertEqual(kde.launcher_path(self.on_path, self.home), '')
        self.assertEqual(kde.launcher_path(lambda name: 'mira', self.home), '', 'a relative answer is refused')

    def test_nothing_to_start_is_unavailable_and_writes_nothing(self):
        self.launcher.unlink()
        run = FakeSystemctl('not-found')
        result = self.set(True, run, which=self.nowhere)
        self.assertEqual((result['status'], result['reason']), ('error', 'kde_autostart_unavailable'))
        self.assertEqual(list(self.folder.iterdir()), [])

    def test_no_user_manager_falls_back_to_the_entry(self):
        def broken(argv, timeout=10.0):
            return 1, '', 'Failed to connect to bus: No medium found'
        state = kde.autostart_state(broken, self.config, self.on_path, self.home)
        self.assertEqual((state['mode'], state['available']), ('xdg', True))
        self.assertIn('Failed to connect', state['error'])


class ExecWords(unittest.TestCase):
    def test_desktop_entry_quoting_round_trips(self):
        for word in ('/usr/bin/mira', '/home/a b/mira', '/x/$HOME/`id`/mira', '/x/50%/mira', '/x/"q"/m\\ira'):
            with self.subTest(word=word):
                self.assertEqual(kde._exec_words(kde._exec_arg(word) + ' --background'), [word, '--background'])

    def test_spec_examples(self):
        self.assertEqual(kde._exec_words('"/opt/my app/mira" %U'), ['/opt/my app/mira', '%U'])
        self.assertEqual(kde._exec_words(r'mira\s--background'), ['mira', '--background'])


# ─── the QML-facing object ──────────────────────────────────────────────────────────────────
class FakeHost(QObject):
    toast = Signal(str, str)
    prefill = Signal(str)

    def __init__(self, lang='en'):
        super().__init__()
        self.lang = lang
        import i18n
        self.s = i18n.table(lang)


class KdePage(unittest.TestCase):
    def setUp(self):
        self.host = FakeHost('en')
        self.page = kde.KdeIntegration(self.host)
        # Run the page's work synchronously so each result is delivered before the assertion.
        self.page.run = lambda tag, fn, *a, **k: self.page._deliver(tag, fn(*a, **k))
        self.toasts, self.prefills, self.attached, self.added = [], [], [], []
        self.host.toast.connect(lambda kind, text: self.toasts.append((kind, text)))
        self.host.prefill.connect(self.prefills.append)
        self.page.attach.connect(lambda name, text: self.attached.append((name, text)))
        self.page.projectAdded.connect(self.added.append)

    def test_strings_reach_the_interface_table(self):
        import i18n
        for lang in ('ar', 'en'):
            table = i18n.table(lang)
            for key in kde.STRINGS:
                self.assertIn(key, table)
        words = ' '.join(v for pair in kde.STRINGS.values() for v in pair)
        self.assertNotIn('Mo AI', words)
        self.assertNotIn('D-Bus', words, 'a bus name is not words for the owner')

    def test_initial_state_renders_off_and_unavailable(self):
        self.assertEqual(self.page.state['autostart'], False)
        self.assertEqual(self.page.state['autostart_available'], False)
        self.assertEqual(self.page.state['autostart_window'], False)

    def test_refresh_maps_the_machine_state(self):
        state = {'available': True, 'mode': 'unit', 'enabled': True, 'background': True, 'masked': False}
        with patch.object(kde, 'autostart_state', return_value=state):
            self.page.refresh()
        self.assertEqual((self.page.state['autostart'], self.page.state['autostart_available'],
                          self.page.state['autostart_mode'], self.page.state['autostart_note'],
                          self.page.state['autostart_window']),
                         (True, True, 'unit', '', False))
        self.assertEqual(self.toasts, [], 'reading is silent')

    def test_refresh_explains_a_window_opening_start_and_unavailability(self):
        with patch.object(kde, 'autostart_state', return_value={'available': True, 'enabled': True, 'background': False}):
            self.page.refresh()
        self.assertEqual(self.page.state['autostart_note'], kde.STRINGS['kde_autostart_window'][1])
        self.assertTrue(self.page.state['autostart_window'], 'Settings offers the fix beside the note')
        with patch.object(kde, 'autostart_state', return_value={'available': False, 'masked': True}):
            self.page.refresh()
        self.assertEqual(self.page.state['autostart_note'], kde.STRINGS['kde_autostart_masked'][1])
        self.assertFalse(self.page.state['autostart_window'])

    def test_switch_on_reports_the_read_back(self):
        with patch.object(kde, 'TEST_MODE', False), \
                patch.object(kde, 'set_autostart', return_value={'status': 'ok', 'reason': 'kde_autostart_on',
                                                                 'available': True, 'enabled': True,
                                                                 'background': True}) as setter:
            self.page.setAutostart(True)
        setter.assert_called_once_with(True)
        self.assertTrue(self.page.state['autostart'])
        self.assertFalse(self.page.state['autostart_busy'])
        self.assertEqual(self.toasts, [('ok', 'Mira will start every time you sign in')])

    def test_switch_failure_is_an_error_and_state_stays_read_back(self):
        with patch.object(kde, 'TEST_MODE', False), \
                patch.object(kde, 'set_autostart', return_value={'status': 'error', 'reason': 'kde_autostart_failed',
                                                                 'available': True, 'enabled': False}):
            self.page.setAutostart(True)
        self.assertFalse(self.page.state['autostart'])
        self.assertEqual(self.toasts, [('error', 'Could not change starting at sign-in')])

    def test_switch_is_ignored_while_busy(self):
        self.page.update(autostart_busy=True)
        with patch.object(kde, 'TEST_MODE', False), patch.object(kde, 'set_autostart') as setter:
            self.page.setAutostart(True)
        setter.assert_not_called()

    # The start-up refresh can land while a change is still on its way.
    def test_a_read_during_a_change_neither_re_enables_the_switch_nor_rewrites_it(self):
        self.page.update(autostart_busy=True, autostart=False)
        self.page._deliver('autostart:read', {'available': True, 'enabled': True, 'background': True})
        self.assertTrue(self.page.state['autostart_busy'], 'the switch stays disabled')
        self.assertFalse(self.page.state['autostart'], 'an older read does not move it')
        self.page._deliver('autostart:set', {'status': 'ok', 'reason': 'kde_autostart_on', 'available': True,
                                             'enabled': True, 'background': True})
        self.assertEqual((self.page.state['autostart_busy'], self.page.state['autostart']), (False, True))

    def test_review_mode_never_touches_the_session(self):
        with patch.object(kde, 'TEST_MODE', True), patch.object(kde, 'set_autostart') as setter:
            self.page.setAutostart(True)
        setter.assert_not_called()
        self.assertTrue(self.page.state['autostart'])

    def test_ask_about_prefills_and_attaches(self):
        with patch.object(kde, 'about_request', return_value={'text': 'Tell me', 'attachment': {'name': 'a.md', 'text': 'x'},
                                                             'notice': None}) as req:
            self.page.ask_about(['/home/a.md'])
        req.assert_called_once_with(['/home/a.md'], 'en')
        self.assertEqual(self.prefills, ['Tell me'])
        self.assertEqual(self.attached, [('a.md', 'x')])
        self.assertEqual(self.toasts, [])

    def test_a_named_file_says_why_it_was_not_attached(self):
        with patch.object(kde, 'about_request', return_value={'text': 'Tell me', 'attachment': None,
                                                             'notice': ('kde_ask_private', 'id_ed25519')}):
            self.page.ask_about(['/home/a/.ssh/id_ed25519'])
        self.assertEqual(self.attached, [])
        self.assertEqual(self.toasts, [('info', 'I did not attach “id_ed25519”: it looks like it keeps a key or a '
                                                'password, so I named it and its folder only.')])

    def test_ask_about_nothing_found_is_an_error_not_a_prefill(self):
        with patch.object(kde, 'about_request', return_value=None):
            self.page.ask_about(['/gone'])
        self.assertEqual(self.prefills, [])
        self.assertEqual(self.toasts, [('error', 'I could not find the file you chose')])

    def test_project_added_is_announced_and_signalled(self):
        with patch.object(kde, 'add_project', return_value={'status': 'ok', 'id': 'e' * 20, 'name': 'moos'}):
            self.page.add_project('/home/a/moos')
        self.assertEqual(self.toasts, [('ok', '“moos” was added to your Workbench projects')])
        self.assertEqual(self.added, ['e' * 20])

    def test_project_failure_names_the_reason(self):
        with patch.object(kde, 'add_project', return_value={'status': 'error', 'reason': 'kde_project_outside_home'}):
            self.page.add_project('/etc')
        self.assertEqual(self.toasts, [('error', 'Could not add the folder as a project: '
                                                 'a project must be inside your home folder')])
        self.assertEqual(self.added, [])

    def test_a_crashed_worker_is_still_an_honest_error(self):
        self.page._deliver('project:add', {'status': 'error', 'error': 'OSError'})
        self.assertEqual(self.toasts[-1][0], 'error')
        self.page._deliver('autostart:set', {'status': 'error', 'error': 'OSError'})
        self.assertEqual(self.toasts[-1], ('error', 'Could not change starting at sign-in'))

    def test_review_fills_visible_state(self):
        self.page.review()
        self.assertTrue(self.page.state['autostart'] and self.page.state['autostart_available'] and self.page.state['dbus'])
        self.assertFalse(self.page.state['autostart_window'])


# ─── the glue: what Plasma and Dolphin hand Mira reaches a handler ─────────────────────────
class AppLaunchRequest(unittest.TestCase):
    """app.launch_request: Mo AI's arguments and kde_integration's, parsed once."""

    @classmethod
    def setUpClass(cls):
        import app
        cls.request = staticmethod(app.launch_request)

    def test_dolphin_s_arguments_reach_the_request(self):
        self.assertEqual(self.request(['--ask-about', '/home/a/x.txt']),
                         {'about': ['/home/a/x.txt'], 'panel': 'chat'})
        self.assertEqual(self.request(['--add-project', '/home/a/src']),
                         {'project': '/home/a/src', 'panel': 'workbench'})
        self.assertEqual(self.request(['--background']), {'background': True})

    def test_an_explicit_panel_wins(self):
        self.assertEqual(self.request(['--panel', 'system', '--ask-about', '/home/a/x.txt'])['panel'], 'system')

    def test_a_link_s_question_stays_a_question(self):
        for words in ('--add-project=/var/home/moos', '--ask-about=/var/home/moos/.ssh/id_ed25519',
                      '--background', '--install-improved-wake', '--wake-rollback', '--device', '--panel'):
            with self.subTest(words=words):
                self.assertEqual(self.request(['--panel', 'chat', '--ask', words]), {'panel': 'chat', 'ask': words})

    def test_mo_ai_s_own_arguments_still_work(self):
        self.assertEqual(self.request(['--device']), {'panel': 'device'})
        self.assertEqual(self.request(['--panel=system', '--ask=hello']), {'panel': 'system', 'ask': 'hello'})
        self.assertEqual(self.request(['--install-improved-wake']), {'wake': 'improved'})
        self.assertEqual(self.request(['--panel', '../x']), {})


class ControllerGlue(unittest.TestCase):
    """The controller owns mira.kde and routes app.py's `open:` requests to it."""

    @classmethod
    def setUpClass(cls):
        from controller import Controller
        from review_fakes import FakeBridge
        cls.controller = Controller(bridge_class=FakeBridge)

    def test_mira_kde_exists(self):
        self.assertIsInstance(self.controller.property('kde'), kde.KdeIntegration)

    def open(self, request):
        calls = []

        class Recorder:
            def ask_about(self, paths):
                calls.append(('about', paths))

            def add_project(self, path):
                calls.append(('project', path))
        with patch.object(self.controller, '_kde', Recorder()):
            self.controller.handle_instance_command(b'open:' + json.dumps(request).encode())
        return calls

    def test_ask_about_reaches_mira_kde(self):
        self.assertEqual(self.open({'about': ['/home/a/x.txt'], 'panel': 'chat'}), [('about', ['/home/a/x.txt'])])

    def test_add_project_reaches_mira_kde(self):
        self.assertEqual(self.open({'project': '/home/a/src', 'panel': 'workbench'}), [('project', '/home/a/src')])

    def test_a_question_alone_reaches_neither(self):
        self.assertEqual(self.open({'ask': '--add-project=/home/a', 'panel': 'chat'}), [])


class QmlReachesKde(unittest.TestCase):
    """Every mira.kde call in Mira's QML is a slot KdeIntegration has, every state key it reads
    exists, and the switch and the composer's attachment are really wired."""

    def setUp(self):
        self.qml = {p: p.read_text(encoding='utf-8') for p in sorted((ROOT / 'qml').rglob('*.qml'))}

    def test_calls_and_reads_exist(self):
        slots = slots_of(kde.KdeIntegration.staticMetaObject)
        keys = set(kde.KdeIntegration(FakeHost()).initial())
        called, read = set(), set()
        for text in self.qml.values():
            called |= set(re.findall(r'\bmira\.kde\.(\w+)\s*\(', text))
            read |= set(re.findall(r'\bmira\.kde\.state\.(\w+)', text))
        self.assertIn('setAutostart', called, 'Settings has no login-start switch')
        self.assertEqual(sorted(called - slots), [], 'QML calls mira.kde slots that do not exist')
        self.assertEqual(sorted(read - keys), [], 'QML reads mira.kde state keys that do not exist')

    def test_the_composer_takes_the_attachment(self):
        main = self.qml[ROOT / 'qml/Main.qml']
        self.assertIsNotNone(re.search(r'target:\s*mira\.kde\b', main), 'Main.qml does not listen to mira.kde')
        self.assertTrue('function onAttach(name, text)' in main, 'the composer never receives the attachment')

    def test_settings_survives_a_missing_integration(self):
        # The controller leaves mira.kde null when kde_integration cannot load: no binding may
        # dereference it unguarded.
        for path, text in self.qml.items():
            for line in text.splitlines():
                if 'mira.kde.state.' in line:
                    self.assertRegex(line, r'mira\.kde\s*\?|mira\.kde\s*!==\s*null|mira\.kde\s*&&',
                                     f'{path.name}: {line.strip()}')


# ─── D-Bus on a private bus ─────────────────────────────────────────────────────────────────
@unittest.skipUnless(shutil.which('dbus-daemon'), 'dbus-daemon is not installed')
class DBusDoor(unittest.TestCase):
    """org.moos.Mira on a bus of its own: the owner's session bus is never touched."""

    @classmethod
    def setUpClass(cls):
        from PySide6.QtDBus import QDBusConnection
        cls.daemon = subprocess.Popen(['dbus-daemon', '--session', '--nofork', '--nopidfile', '--print-address=1'],
                                      stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        cls.address = cls.daemon.stdout.readline().strip()
        cls.server = QDBusConnection.connectToBus(cls.address, 'mira-kde-test-server')
        cls.client = QDBusConnection.connectToBus(cls.address, 'mira-kde-test-client')
        cls.other = QDBusConnection.connectToBus(cls.address, 'mira-kde-test-other')

    @classmethod
    def tearDownClass(cls):
        from PySide6.QtDBus import QDBusConnection
        for name in ('mira-kde-test-server', 'mira-kde-test-client', 'mira-kde-test-other'):
            QDBusConnection.disconnectFromBus(name)
        cls.daemon.terminate()
        cls.daemon.wait(5)

    def setUp(self):
        self.calls = []
        callbacks = {'show': lambda panel: self.calls.append(('show', panel)),
                     'prefill': lambda text: self.calls.append(('prefill', text)),
                     'talk': lambda: self.calls.append(('talk',)),
                     'stop': lambda: self.calls.append(('stop',))}
        self.exported = kde.start_dbus(callbacks, connection=self.server)
        self.assertIsNotNone(self.exported, 'the door opens on a connected bus')

    def tearDown(self):
        kde.stop_dbus(self.exported)

    def call(self, method, *args):
        from PySide6.QtDBus import QDBus, QDBusMessage
        message = QDBusMessage.createMethodCall(kde.SERVICE, kde.OBJECT_PATH, kde.INTERFACE, method)
        if args:
            message.setArguments(list(args))
        reply = self.client.call(message, QDBus.CallMode.BlockWithGui, 5000)
        self.assertNotEqual(reply.type(), QDBusMessage.MessageType.ErrorMessage, reply.errorMessage())
        return reply.arguments()[0] if reply.arguments() else None

    def test_every_method_reaches_its_callback(self):
        self.assertEqual(self.call('Show', 'system'), 'ok')
        self.assertEqual(self.call('Show', ''), 'ok')
        self.assertEqual(self.call('Prefill', '  what is\nthis? '), 'ok')
        self.assertEqual(self.call('Talk'), 'ok')
        self.assertEqual(self.call('Stop'), 'ok')
        self.assertEqual(self.calls, [('show', 'system'), ('show', ''), ('prefill', 'what is this?'),
                                      ('talk',), ('stop',)])

    def test_bad_arguments_are_refused_before_any_callback(self):
        self.assertEqual(self.call('Show', '../../etc'), 'refused')
        self.assertEqual(self.call('Show', 'x' * 40), 'refused')
        self.assertEqual(self.call('Prefill', ' ' + RLO + '\n '), 'empty')
        self.assertEqual(self.calls, [])

    def test_introspection_offers_only_the_four_methods(self):
        from PySide6.QtDBus import QDBus, QDBusMessage
        message = QDBusMessage.createMethodCall(kde.SERVICE, kde.OBJECT_PATH,
                                                'org.freedesktop.DBus.Introspectable', 'Introspect')
        xml = self.client.call(message, QDBus.CallMode.BlockWithGui, 5000).arguments()[0]
        self.assertIn(f'<interface name="{kde.INTERFACE}">', xml)
        for method in ('Show', 'Prefill', 'Talk', 'Stop'):
            self.assertIn(f'<method name="{method}">', xml)
        own = xml.split(f'<interface name="{kde.INTERFACE}">', 1)[1].split('</interface>', 1)[0]
        self.assertEqual(own.count('<method '), 4, own)

    def test_a_failing_callback_answers_failed(self):
        kde.stop_dbus(self.exported)

        def boom():
            raise RuntimeError('window gone')
        self.exported = kde.start_dbus({'talk': boom}, connection=self.server)
        self.assertEqual(self.call('Talk'), 'failed')
        self.assertEqual(self.call('Stop'), 'unavailable')

    def test_a_taken_name_leaves_the_door_closed(self):
        self.assertIsNone(kde.start_dbus({}, connection=self.other))
        self.assertEqual(self.call('Talk'), 'ok', 'the first owner still answers')

    def test_stopping_releases_the_name(self):
        kde.stop_dbus(self.exported)
        second = kde.start_dbus({}, connection=self.other)
        self.assertIsNotNone(second)
        kde.stop_dbus(second)
        self.exported = kde.start_dbus({}, connection=self.server)

    def test_no_bus_is_never_fatal(self):
        from PySide6.QtDBus import QDBusConnection
        dead = QDBusConnection.connectToBus('unix:path=/nonexistent/mira-bus', 'mira-kde-test-dead')
        try:
            self.assertIsNone(kde.start_dbus({}, connection=dead))
        finally:
            QDBusConnection.disconnectFromBus('mira-kde-test-dead')
        kde.stop_dbus(None)

    def test_review_runs_never_claim_the_session_name(self):
        from PySide6.QtDBus import QDBusConnection
        kde.stop_dbus(self.exported)          # the name is free: only the guard can refuse it
        # "The session bus" is this private bus here, so even a broken guard claims nothing real.
        with patch.object(kde, 'TEST_MODE', True), \
                patch.object(QDBusConnection, 'sessionBus', staticmethod(lambda: self.other)):
            claimed = kde.start_dbus({})
        kde.stop_dbus(claimed)
        self.assertIsNone(claimed)
        self.exported = kde.start_dbus({}, connection=self.server)


if __name__ == '__main__':
    unittest.main()
