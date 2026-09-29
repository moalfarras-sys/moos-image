"""The Workbench page (pages/workbench.py) against stand-in backends — nothing here reaches the agent
service, moai-control or moos-open.

What is proven: the agent service's answers become the state QML draws; a file is read and a diff
computed only by their own slots (both are audited reads); an older answer never overwrites a newer
one; only the owner's field writes to his terminal and never to the agent's; a coding-agent install
is an approval card or an explanation, never a direct run; polling runs only while the page is on
screen; errors carry the backend's reason.
"""
import os
import re
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ['MIRA_TEST_MODE'] = '1'

from PySide6.QtGui import QGuiApplication  # noqa: E402

APP = QGuiApplication.instance() or QGuiApplication([])

import i18n  # noqa: E402
from pages import base  # noqa: E402
from pages import workbench as wb  # noqa: E402

PID = 'ea6e19fda493e98f82e2'
PID2 = '0b5c7d2e41f9a8c3d6e1'
TASK = '3f2b8c1a-9d4e-4f6a-8b2c-1e5d7a9c3b40'
TERM = '1d2c3b4a-5e6f-4a7b-8c9d-0e1f2a3b4c5d'
AGENT_TERM = '9e8d7c6b-5a4f-4e3d-2c1b-0a9f8e7d6c5b'
SESSION = 'a3a3342e-88bb-4c97-aecd-487a99787f28'


class Recorder:
    def __init__(self):
        self.calls = []

    def emit(self, *args):
        self.calls.append(args)


class FakeHost:
    def __init__(self, lang='ar', card=True):
        self.lang = lang
        self.s = i18n.table(lang)
        self.toast, self.prefill, self.showSheet = Recorder(), Recorder(), Recorder()
        self.confirmations = []
        self.card = {'id': 'card-1'} if card else None
        self.sent = []

    def request_confirmation(self, item):
        self.confirmations.append(item)
        return self.card

    def send(self, text):      # must never be used by this page
        self.sent.append(text)


class FakeAgent:
    """The agent service (moai_agent.request) with fixed answers per route; every call is recorded."""

    def __init__(self):
        self.calls = []
        self.answers = {
            '/api/status': {'services': {'moai': True}, 'openclaw_installed': False},
            '/api/config': {'permissions': {'tier': 'full', 'web': False},
                            'cloud': {'provider': 'openrouter-free', 'has_key': True},
                            'providers': [{'id': 'openrouter-free', 'name': 'OpenRouter (مجاني فقط | free only)'}]},
            '/api/approvals': [{'id': 'a1'}, {'id': 'a2'}],
            '/api/projects': [{'id': PID, 'name': 'MoOS', 'path': '/home/o/moos', 'pinned': True, 'archived': False},
                              {'id': PID2, 'name': 'Mira', 'path': '/home/o/mira', 'pinned': False, 'archived': False},
                              {'id': 'not-a-project-id', 'name': 'bad'}],
            '/api/project/files': {'path': '', 'parent': '', 'truncated': False,
                                   'entries': [{'name': 'docs', 'path': 'docs', 'type': 'directory', 'size': 0},
                                               {'name': 'README.md', 'path': 'README.md', 'type': 'file', 'size': 2048}]},
            '/api/project/file': {'path': 'README.md', 'size': 7, 'content': '# MoOS\n'},
            # measured shapes of `git status --short`: a spaced name and every non-ASCII byte are C-quoted
            '/api/project/git-status': {'status': ' M README.md\n?? new.py\nA  docs/a.md\n D old.txt\n'
                                                  'R  "old name.txt" -> "new name.txt"\n?? "a b.txt"\n'
                                                  '?? "\\331\\205\\331\\204\\331\\201.txt"\n'},
            '/api/project/git-diff': {'path': '', 'unstaged': 'diff --git a/README.md b/README.md\n@@ -1 +1 @@\n-old\n+new\n ctx',
                                      'staged': ''},
            '/api/tasks': [{'id': TASK, 'title': 'Add tests', 'description': 'd', 'project': PID, 'status': 'pending',
                            'steps': [{'id': 1, 'title': 's1', 'status': 'pending'}], 'tools': [{'name': 'git_diff'}],
                            'error': '', 'result': '', 'updated': 100}],
            '/api/terminals': [{'id': TERM, 'title': 'MoOS', 'cwd': '/home/o/moos', 'running': True, 'exit_code': None},
                               {'id': AGENT_TERM, 'title': 'Mo AI: pytest', 'cwd': '/home/o/moos', 'running': False,
                                'exit_code': 0}],
            '/api/terminal/output': {'id': TERM, 'output': '\x1b[1mmoai$\x1b[0m ls\r\nREADME.md\r\n', 'offset': 42,
                                     'running': True, 'exit_code': None},
            '/api/sessions': [{'id': SESSION, 'key': 'mira-desktop-owner', 'label': 'Check Git', 'updated': 100,
                               'pinned': False}],
            '/api/session': [
                {'role': 'user', 'text': 'check git', 'ts': 100},
                {'role': 'tool', 'text': 'git_status', 'status': 'running', 'ts': 101},
                {'role': 'tool', 'text': 'git_status\n{"status": " M a"}', 'status': 'success', 'ts': 102},
                {'role': 'tool', 'text': 'run_command: waiting for owner approval', 'status': 'pending', 'ts': 103},
                {'role': 'tool', 'text': '⚙ read_file\n{"path": "a"}', 'status': 'running', 'ts': '2026-09-29T10:00:00Z'},
                {'role': 'tool', 'text': '✕ read_file\nnot found', 'status': 'error', 'ts': '2026-09-29T10:00:01Z'},
                {'role': 'assistant', 'text': 'One file changed.', 'ts': 104},
                {'role': 'system', 'text': 'hidden'}],
            '/api/project/upsert': {'ok': True, 'id': PID2, 'name': 'Mira', 'path': '/home/o/mira', 'pinned': False,
                                    'archived': False},
            '/api/task/create': {'ok': True, 'id': TASK},
            '/api/task/action': {'ok': True, 'id': TASK, 'status': 'running'},
            '/api/terminal/start': {'ok': True, 'id': TERM, 'title': 'MoOS', 'cwd': '/home/o/moos', 'running': True},
            '/api/terminal/write': {'ok': True, 'id': TERM},
            '/api/terminal/stop': {'ok': True, 'id': TERM, 'running': False},
        }

    def request(self, method, route, body=None, query=None, timeout=15):
        """moai_agent.request: the one door both of its get() and post() go through."""
        self.calls.append((method, route, body if method == 'POST' else dict(query or {})))
        return self.answers.get(route, {'error': 'not found'})

    def paths(self, method=None):
        return [c[1] for c in self.calls if method is None or c[0] == method]

    def last(self, path):
        return next(c for c in reversed(self.calls) if c[1] == path)


def quick(gateway=True, cloud=True, agents=None):
    return {'brains': {'gateway': gateway, 'cloud': cloud},
            'agents': agents if agents is not None else {'codex': True, 'claude': False, 'opencode': True, 'hermes': True}}


class WorkbenchCase(unittest.TestCase):
    NAMES = {'install_codex', 'install_claude_code', 'install_opencode', 'install_hermes', 'install_app'}
    # what the schemas say approving each install does (moai_tools.consequence); '' = nothing declared
    CONSEQUENCES = {('install_hermes', 'ar'): 'ينزّل Hermes الرسمي (قرابة 400 ميغابايت) لحسابك ويتحقق من كل ملف بالتجزئة.',
                    ('install_hermes', 'en'): 'Downloads the official Hermes (about 400 MB) for your account.'}

    def setUp(self):
        self.agent = FakeAgent()
        self.quick = quick()
        self.routes = []
        self.route_result = {'status': 'ok'}
        self.executed = []
        patches = [
            mock.patch.object(wb.moai_agent, 'request', self.agent.request),
            mock.patch.object(wb.moai_tools, 'get', lambda path, timeout=20: self.quick if path == '/quick' else {'error': 'x'}),
            mock.patch.object(wb.moai_tools, 'names', lambda: set(self.NAMES)),
            mock.patch.object(wb.moai_tools, 'execute', lambda *a, **k: self.executed.append(a) or {'status': 'ok'}),
            mock.patch.object(wb.moai_tools, 'consequence', lambda name, lang='ar': self.CONSEQUENCES.get((name, lang), '')),
            mock.patch.object(wb.moos_routes, 'open_route', lambda url: self.routes.append(url) or self.route_result),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.host = FakeHost()
        self.page = self.make_page(self.host)

    @staticmethod
    def make_page(host, deferred=None):
        page = wb.WorkbenchPage(host)
        if deferred is None:
            def run(tag, fn, *args, **kwargs):    # synchronous: the answer arrives before run() returns
                page._done.emit(tag, fn(*args, **kwargs))
        else:
            def run(tag, fn, *args, **kwargs):    # held: the test delivers answers in the order it wants
                deferred.append((tag, fn(*args, **kwargs)))
        page.run = run
        return page

    @property
    def st(self):
        return self.page.state

    def toasts(self, kind=None):
        return [c for c in self.host.toast.calls if kind is None or c[0] == kind]


class Readiness(WorkbenchCase):
    def test_ready_with_tier_web_provider_and_approvals(self):
        self.page.refresh()
        self.assertEqual(self.st['ready'], 'ready')
        self.assertEqual(self.st['readyReason'], 'wb_reason_ready')
        self.assertEqual((self.st['tier'], self.st['web'], self.st['provider']), ('full', False, 'OpenRouter'))
        self.assertEqual(self.st['approvals'], 2)
        self.assertFalse(self.st['loading'])

    def test_offline_when_the_service_does_not_answer(self):
        self.agent.answers['/api/status'] = {'error': 'agent_unreachable', 'detail': 'URLError'}
        self.page.refresh()
        self.assertEqual((self.st['ready'], self.st['readyReason']), ('offline', 'wb_reason_offline'))
        self.assertEqual(self.st['approvals'], 0)

    def test_setup_when_gateway_or_brain_is_missing(self):
        self.quick = quick(gateway=False)
        self.page.refresh()
        self.assertEqual((self.st['ready'], self.st['readyReason']), ('setup', 'wb_reason_gateway'))
        self.quick = quick(cloud=False)
        self.page.refresh()
        self.assertEqual((self.st['ready'], self.st['readyReason']), ('setup', 'wb_reason_key'))

    def test_falls_back_to_the_agent_service_when_moai_control_is_silent(self):
        self.quick = {'error': 'moai_control_unreachable'}
        self.agent.answers['/api/config']['cloud']['has_key'] = False
        self.page.refresh()
        self.assertEqual(self.st['readyReason'], 'wb_reason_key')
        self.assertTrue(all(not a['known'] for a in self.st['agents']))

    def test_unknown_tier_is_custom_never_dressed_as_safe(self):
        self.agent.answers['/api/config']['permissions']['tier'] = 'hand-edited'
        self.page.refresh()
        self.assertEqual(self.st['tier'], 'custom')

    def test_coding_agents_from_quick_and_the_declared_tools(self):
        self.quick = quick(agents={'codex': True, 'claude': False})
        self.page.refresh()
        agents = {a['key']: a for a in self.st['agents']}
        self.assertTrue(agents['codex']['installed'] and agents['codex']['canRun'])
        self.assertEqual((agents['claude']['install'], agents['claude']['tool']), ('tool', 'install_claude_code'))
        self.assertFalse(agents['opencode']['known'])
        self.assertTrue(agents['hermes']['engine'])
        self.assertFalse(agents['hermes']['canRun'])     # no moos://dev/hermes route exists

    def test_change_permissions_opens_the_assistant_settings(self):
        self.page.changePermissions()
        self.assertEqual(self.routes, ['moos://settings/assistant'])
        self.route_result = {'status': 'error', 'error': 'route_not_allowed'}
        self.page.changePermissions()
        self.assertEqual(self.toasts('error')[-1][1], self.host.s['wb_err_route'])

    def test_activation_in_review_mode_reads_nothing(self):
        self.page.activated()
        self.assertEqual(self.agent.calls, [])


class Projects(WorkbenchCase):
    def test_refresh_selects_the_first_project_and_reads_it(self):
        self.page.refresh()
        self.assertEqual([p['id'] for p in self.st['projects']], [PID, PID2])   # a malformed id is dropped
        self.assertEqual((self.st['project'], self.st['projectName'], self.st['projectPinned']), (PID, 'MoOS', True))
        self.assertEqual(self.agent.last('/api/project/files')[2], {'project': PID, 'path': ''})
        self.assertEqual(self.agent.last('/api/project/git-status')[2], {'project': PID})
        self.assertEqual(self.agent.last('/api/tasks')[2], {'project': PID})
        self.assertEqual([e['name'] for e in self.st['entries']], ['docs', 'README.md'])
        self.assertEqual(self.st['gitRows'][0], {'code': 'M', 'path': 'README.md', 'oldPath': '', 'label': 'README.md',
                                                 'kind': 'modified', 'staged': False})

    def test_no_file_is_read_and_no_diff_computed_without_a_click(self):
        self.page.refresh()
        self.page.selectProject(PID2)
        for tab in wb.TABS:
            self.page.setTab(tab)
        self.assertNotIn('/api/project/file', self.agent.paths())
        self.assertNotIn('/api/project/git-diff', self.agent.paths())
        self.assertNotIn('/api/channels', self.agent.paths())

    def test_add_a_project_from_the_folder_dialog(self):
        self.page.refresh()
        self.page.addProject('file:///home/o/my%20site')
        self.assertEqual(self.agent.last('/api/project/upsert')[2], {'path': '/home/o/my site', 'archived': False})
        self.assertEqual(self.toasts('ok')[-1][1], self.host.s['wb_project_added'] + ' · Mira')
        self.assertEqual(self.st['project'], PID2)          # the new project is chosen

    def test_a_folder_outside_home_is_refused_with_the_reason(self):
        self.agent.answers['/api/project/upsert'] = {'error': 'project must be inside the real home directory'}
        self.page.addProject('/etc')
        self.assertEqual(self.toasts('error')[-1][1], self.host.s['wb_err_home'])
        self.assertEqual(self.toasts('ok'), [])

    def test_pin_and_archive_send_the_canonical_path(self):
        self.page.refresh()
        self.page.pinProject(PID2, True)
        self.assertEqual(self.agent.last('/api/project/upsert')[2], {'id': PID2, 'path': '/home/o/mira', 'pinned': True})
        self.agent.answers['/api/project/upsert'] = {'ok': True, 'id': PID, 'name': 'MoOS', 'archived': True}
        self.agent.answers['/api/projects'] = self.agent.answers['/api/projects'][1:2]
        self.page.selectProject(PID)
        self.page.archiveProject(PID, True)
        self.assertEqual(self.agent.last('/api/project/upsert')[2], {'id': PID, 'path': '/home/o/moos', 'archived': True})
        self.assertEqual(self.st['project'], PID2)          # the archived one left the list: the next is chosen

    def test_unknown_project_changes_nothing(self):
        self.page.refresh()
        before = len(self.agent.calls)
        self.page.pinProject('ffffffffffffffffffff', True)
        self.page.selectProject('ffffffffffffffffffff')
        self.assertEqual(len(self.agent.calls), before)

    def test_ask_mira_fills_the_composer_and_never_sends(self):
        self.page.refresh()
        self.page.askAboutProject()
        self.page.askReview()
        self.assertEqual(len(self.host.prefill.calls), 2)
        self.assertIn('«MoOS»', self.host.prefill.calls[0][0])
        self.assertIn('/home/o/moos', self.host.prefill.calls[0][0])
        self.assertEqual(self.host.sent, [])
        english = self.make_page(FakeHost('en'))
        english.refresh()
        english.askAboutProject()
        self.assertTrue(english.host.prefill.calls[0][0].startswith('Inspect my registered project "MoOS"'))


class FilesAndGit(WorkbenchCase):
    def setUp(self):
        super().setUp()
        self.page.refresh()

    def test_navigation_and_parent(self):
        self.agent.answers['/api/project/files'] = {'path': 'docs/a', 'parent': 'docs', 'entries': [], 'truncated': True}
        self.page.openDir('docs/a')
        self.assertEqual((self.st['dirPath'], self.st['dirParent'], self.st['truncated']), ('docs/a', 'docs', True))
        self.page.goUp()
        self.assertEqual(self.agent.last('/api/project/files')[2], {'project': PID, 'path': 'docs'})

    def test_preview_on_click_with_the_backend_reasons(self):
        self.page.previewFile('README.md')
        self.assertEqual(self.agent.last('/api/project/file')[2], {'project': PID, 'path': 'README.md'})
        self.assertEqual((self.st['previewText'], self.st['previewSize']), ('# MoOS\n', 7))
        self.agent.answers['/api/project/file'] = {'error': 'binary project files are not previewed'}
        self.page.previewFile('logo.png')
        self.assertEqual((self.st['previewError'], self.st['previewText']), (self.host.s['wb_err_binary'], ''))
        self.page.closePreview()
        self.assertEqual(self.st['previewPath'], '')

    def test_a_long_file_is_cut_and_says_so(self):
        self.agent.answers['/api/project/file'] = {'path': 'big.txt', 'size': 200000, 'content': 'x' * 200000}
        self.page.previewFile('big.txt')
        self.assertEqual(len(self.st['previewText']), wb.MAX_PREVIEW)
        self.assertTrue(self.st['previewCut'])

    def test_git_rows_kinds_and_a_folder_that_is_not_a_repository(self):
        kinds = {r['path']: r['kind'] for r in self.st['gitRows']}
        self.assertEqual(kinds, {'README.md': 'modified', 'new.py': 'new', 'docs/a.md': 'added', 'old.txt': 'deleted',
                                 'new name.txt': 'renamed', 'a b.txt': 'new', 'ملف.txt': 'new'})
        self.assertTrue(next(r for r in self.st['gitRows'] if r['path'] == 'docs/a.md')['staged'])
        self.assertEqual(self.st['gitCountText'], '7 تغييرات')
        self.agent.answers['/api/project/git-status'] = {'error': 'project is not a Git worktree'}
        self.page.refreshGit()
        self.assertTrue(self.st['gitNotRepo'])
        self.assertEqual((self.st['gitError'], self.st['gitRows']), ('', []))

    def test_diff_only_on_click_coloured_and_closable(self):
        self.page.showDiff('README.md')
        self.assertEqual(self.agent.last('/api/project/git-diff')[2], {'project': PID, 'path': 'README.md'})
        self.assertEqual([line['k'] for line in self.st['diff']], ['head', 'meta', 'hunk', 'del', 'add', 'ctx'])
        self.assertEqual(self.st['diff'][0]['t'], self.host.s['wb_unstaged'])
        self.page.closeDiff()
        self.assertFalse(self.st['diffShown'])
        self.assertEqual(self.st['diff'], [])

    def test_the_service_failing_shows_its_reason(self):
        self.agent.answers['/api/project/files'] = {'error': 'agent_unreachable', 'detail': 'URLError'}
        self.page.openDir('docs')
        self.assertEqual(self.st['filesError'], self.host.s['wb_err_unreachable'])
        self.agent.answers['/api/project/files'] = {'error': 'something new'}
        self.page.openDir('docs')
        self.assertEqual(self.st['filesError'], self.host.s['wb_err_prefix'] + 'something new')


class StaleAnswers(WorkbenchCase):
    def test_an_older_answer_never_overwrites_a_newer_one(self):
        held = []
        page = self.make_page(self.host, deferred=held)
        page.update(project=PID)
        self.agent.answers['/api/project/files'] = {'path': 'a', 'parent': '', 'entries': [{'name': 'A', 'path': 'a/A', 'type': 'file'}]}
        page.openDir('a')
        self.agent.answers['/api/project/files'] = {'path': 'b', 'parent': '', 'entries': [{'name': 'B', 'path': 'b/B', 'type': 'file'}]}
        page.openDir('b')
        for tag, result in reversed(held):          # the newer answer arrives first
            page._done.emit(tag, result)
        self.assertEqual(page.state['dirPath'], 'b')
        self.assertEqual([e['name'] for e in page.state['entries']], ['B'])

    def _held_page(self):
        held = []
        page = self.make_page(self.host, deferred=held)
        page.update(projects=[{'id': PID, 'name': 'MoOS', 'path': '/p', 'pinned': False, 'archived': False},
                              {'id': PID2, 'name': 'Mira', 'path': '/q', 'pinned': False, 'archived': False}], project=PID)
        return page, held

    def test_a_closed_preview_drops_the_answer_on_the_way(self):
        page, held = self._held_page()
        page.previewFile('README.md')
        page.closePreview()
        for tag, result in held:
            page._done.emit(tag, result)
        self.assertEqual((page.state['previewText'], page.state['previewPath']), ('', ''))

    def test_a_closed_diff_drops_the_answer_on_the_way(self):
        page, held = self._held_page()
        page.showDiff('')
        page.closeDiff()
        for tag, result in held:
            page._done.emit(tag, result)
        self.assertFalse(page.state['diffShown'])
        self.assertEqual(page.state['diff'], [])

    def test_a_switched_project_drops_what_was_on_the_way_for_the_old_one(self):
        page, held = self._held_page()
        page.previewFile('README.md')
        page.showDiff('')
        page.selectProject(PID2)
        for tag, result in held:
            page._done.emit(tag, result)
        self.assertEqual(page.state['previewText'], '')
        self.assertEqual(page.state['diff'], [])
        self.assertEqual(page.state['project'], PID2)

    def test_a_poll_does_not_pile_up_behind_a_slow_answer(self):
        held = []
        page = self.make_page(self.host, deferred=held)
        page._poll_tasks()
        page._poll_tasks()
        self.assertEqual([t.split(':')[0] for t, _ in held].count('tasks'), 1)
        self.assertEqual([t.split(':')[0] for t, _ in held].count('approvals'), 1)

    def test_writes_are_never_dropped(self):
        held = []
        page = self.make_page(self.host, deferred=held)
        page.update(terminal=TERM, termRunning=True)
        page.sendTerminal('a')
        page.sendTerminal('b')
        self.assertEqual([t for t, _ in held], [f'termwrite:{TERM}', f'termwrite:{TERM}'])

    def test_an_identical_poll_emits_nothing_and_lists_signal_alone(self):
        seen = []
        self.page.changed.connect(lambda: seen.append('state'))
        self.page.tasksChanged.connect(lambda: seen.append('tasks'))
        self.page.entriesChanged.connect(lambda: seen.append('entries'))
        self.page.update(tasks=[{'id': 1}])
        self.page.update(tasks=[{'id': 1}])
        self.assertEqual(seen, ['state', 'tasks'])
        self.page.update(tab='git')
        self.assertEqual(seen, ['state', 'tasks', 'state'])


class Tasks(WorkbenchCase):
    def setUp(self):
        super().setUp()
        self.page.refresh()

    def test_task_rows(self):
        task = self.st['tasks'][0]
        self.assertEqual((task['status'], task['tone'], task['actions']), ('pending', 'info', ['start']))
        self.assertEqual((task['projectName'], task['tools'], task['steps'][0]['title']), ('MoOS', ['git_diff'], 's1'))
        self.assertEqual(self.st['running'], 0)

    def test_create_needs_a_title_and_sends_the_owner_words(self):
        self.page.createTask('   ', '', '')
        self.assertNotIn('/api/task/create', self.agent.paths())
        self.assertEqual(self.toasts('error')[-1][1], self.host.s['wb_task_needs_title'])
        self.page.createTask('  Add   tests ', ' cover it ', 'read\n\n  write  it \n')
        self.assertEqual(self.agent.last('/api/task/create')[2],
                         {'title': 'Add tests', 'description': 'cover it', 'steps': ['read', 'write it'], 'project': PID})
        self.assertEqual(self.toasts('ok')[-1][1], self.host.s['wb_task_created'])
        self.assertFalse(self.st['creating'])

    def test_only_the_actions_the_status_allows(self):
        self.page.taskAction(TASK, 'pause')                 # a pending task cannot be paused
        self.page.taskAction('nope', 'start')
        self.assertNotIn('/api/task/action', self.agent.paths())
        self.page.taskAction(TASK, 'start')
        self.assertEqual(self.agent.last('/api/task/action')[2], {'id': TASK, 'action': 'start'})
        self.assertEqual(self.toasts('pending')[-1][1], self.host.s['wb_now_running'])
        self.assertEqual(self.st['taskBusy'], '')

    def test_a_refused_action_says_why(self):
        self.agent.answers['/api/task/action'] = {'error': 'task is already running'}
        self.page.taskAction(TASK, 'start')
        self.assertEqual(self.toasts('error')[-1][1], self.host.s['wb_err_running'])

    def test_scope_all_reads_every_project(self):
        self.page.setTasksScope('all')
        self.assertEqual(self.agent.last('/api/tasks')[2], {})
        self.page.setTasksScope('bogus')
        self.assertEqual(self.st['tasksScope'], 'all')

    def test_show_its_work_opens_the_task_session(self):
        self.page.showTaskWork(TASK)
        self.assertEqual(self.st['tab'], 'sessions')
        self.assertEqual(self.agent.last('/api/session')[2], {'id': 'moai-task-' + TASK})
        self.assertEqual(self.st['sessionLabel'], 'Add tests')

    def test_ask_about_a_failed_task_carries_its_error(self):
        self.agent.answers['/api/tasks'][0].update(status='failed', error='Verification incomplete')
        self.page.loadTasks()
        self.page.askAboutTask(TASK)
        text = self.host.prefill.calls[-1][0]
        self.assertIn('«Add tests»', text)
        self.assertIn('Verification incomplete', text)
        self.assertEqual(self.st['tasks'][0]['actions'], ['start'])


class Polling(WorkbenchCase):
    def setUp(self):
        super().setUp()
        patcher = mock.patch.object(base, 'TEST_MODE', False)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_tasks_poll_only_while_one_runs_and_the_page_is_shown(self):
        self.agent.answers['/api/tasks'][0]['status'] = 'running'
        self.page.setShown(True)
        self.page.refresh()
        self.assertEqual(self.st['running'], 1)
        self.assertTrue(self.page._task_timer.isActive())
        self.assertEqual(self.page._task_timer.interval(), 2000)
        self.page.setShown(False)
        self.assertFalse(self.page._task_timer.isActive())
        self.page.setShown(True)
        self.agent.answers['/api/tasks'][0]['status'] = 'completed'
        self.page._poll_tasks()
        self.assertFalse(self.page._task_timer.isActive())

    def test_terminal_polls_only_on_its_tab(self):
        self.page.setShown(True)
        self.page.refresh()
        self.assertEqual(self.st['terminal'], TERM)         # the owner's running terminal, not the agent's
        self.assertFalse(self.page._term_timer.isActive())
        self.page.setTab('terminal')
        self.assertTrue(self.page._term_timer.isActive())
        self.assertEqual(self.page._term_timer.interval(), 300)
        self.page.setTab('files')
        self.assertFalse(self.page._term_timer.isActive())

    def test_an_install_card_is_followed_only_while_the_page_is_shown(self):
        self.page.refresh()
        self.page.installAgent('claude')
        self.assertFalse(self.page._agent_timer.isActive())         # not on screen yet
        self.page.setShown(True)
        self.assertTrue(self.page._agent_timer.isActive())
        self.assertEqual(self.page._agent_timer.interval(), 5000)
        self.page.setShown(False)
        self.assertFalse(self.page._agent_timer.isActive())
        self.page.setShown(True)
        self.quick = quick(agents={'claude': True})
        self.page._poll_agents()
        self.assertFalse(self.page._agent_timer.isActive())         # installed: nothing left to follow

    def test_choosing_changes_or_files_reads_them_again(self):
        self.page.refresh()
        status, folder = self.agent.paths().count('/api/project/git-status'), self.agent.paths().count('/api/project/files')
        self.page.setTab('git')
        self.page.setTab('files')
        self.page.setTab('git')
        self.assertEqual(self.agent.paths().count('/api/project/git-status'), status + 2)
        self.assertEqual(self.agent.paths().count('/api/project/files'), folder + 1)
        self.assertNotIn('/api/project/file', self.agent.paths())
        self.assertNotIn('/api/project/git-diff', self.agent.paths())

    def test_review_mode_never_starts_a_timer(self):
        with mock.patch.object(base, 'TEST_MODE', True):
            self.page.setShown(True)
            self.page.update(running=2, tab='terminal', terminal=TERM, termRunning=True)
            self.page._sync_timers()
            self.assertFalse(self.page._task_timer.isActive() or self.page._term_timer.isActive())


class Terminal(WorkbenchCase):
    def setUp(self):
        super().setUp()
        self.page.refresh()

    def test_output_is_cleaned_and_the_offset_advances(self):
        self.assertEqual(self.st['termOutput'], 'moai$ ls\nREADME.md\n')
        self.assertEqual(self.agent.last('/api/terminal/output')[2], {'id': TERM, 'offset': '0'})
        self.page._poll_terminal()
        self.assertEqual(self.agent.last('/api/terminal/output')[2], {'id': TERM, 'offset': '42'})

    def test_only_the_owner_field_writes_and_never_to_the_agent_terminal(self):
        self.page.sendTerminal('ls -la')
        self.page.interruptTerminal()
        writes = [c[2] for c in self.agent.calls if c[1] == '/api/terminal/write']
        self.assertEqual(writes, [{'id': TERM, 'input': 'ls -la\n'}, {'id': TERM, 'input': '\x03'}])
        self.page.selectTerminal(AGENT_TERM)
        self.assertTrue(self.st['termAgent'])
        self.page.sendTerminal('rm -rf ~')
        self.assertEqual(len([c for c in self.agent.calls if c[1] == '/api/terminal/write']), 2)
        self.page.stopTerminal()
        self.assertNotIn('/api/terminal/stop', self.agent.paths())

    def test_new_terminal_opens_in_the_project(self):
        self.page.newTerminal()
        self.assertEqual(self.agent.last('/api/terminal/start')[2], {'project': PID})
        self.assertEqual(self.st['terminal'], TERM)
        self.assertFalse(self.st['termStarting'])

    def test_an_ended_terminal_takes_no_input_and_stop_reads_back(self):
        self.agent.answers['/api/terminal/output'] = {'id': TERM, 'output': 'bye\n', 'offset': 50, 'running': False,
                                                      'exit_code': 0}
        self.page._poll_terminal()
        self.assertFalse(self.st['termRunning'])
        self.assertEqual(self.st['termExit'], 0)
        before = len(self.agent.calls)
        self.page.sendTerminal('ls')
        self.assertEqual(len(self.agent.calls), before)

    def test_stop_and_a_failed_write(self):
        self.page.stopTerminal()
        self.assertEqual(self.agent.last('/api/terminal/stop')[2], {'id': TERM})
        self.page.update(termRunning=True)
        self.agent.answers['/api/terminal/write'] = {'error': 'terminal has exited'}
        self.page.sendTerminal('ls')
        self.assertEqual(self.st['termError'], self.host.s['wb_term_exited'])

    def test_clean_terminal(self):
        self.assertEqual(wb.clean_terminal('\x1b[31mred\x1b[0m\r\nab\bc\x1b]0;title\x07\x07'), 'red\nac')


def without_project_routes():
    """moos_routes as an image whose moos-open cannot open an agent inside a project yet."""
    allowed = wb.moos_routes.allowed
    return mock.patch.object(wb.moos_routes, 'allowed',
                             lambda url: allowed(url) and not re.fullmatch(r'moos://dev/[a-z]+/[0-9a-f]{20}', str(url)))


class CodingAgents(WorkbenchCase):
    def setUp(self):
        super().setUp()
        self.page.refresh()

    def test_run_opens_the_fixed_route(self):
        # moos_routes allows moos://dev/<agent>/<project id> now: Run opens the agent in the chosen project.
        self.page.openAgent('codex')
        self.page.openAgent('code')
        self.assertEqual(self.routes, ['moos://dev/codex/' + PID, 'moos://dev/code/' + PID])
        self.routes.clear()
        with without_project_routes():               # an older moos-open: the plain route, never a dead one
            self.page.refresh()
            self.page.openAgent('codex')
            self.page.openAgent('code')
        self.assertEqual(self.routes, ['moos://dev/codex', 'moos://dev/code'])
        self.assertTrue(all(c[0] == 'info' for c in self.toasts()))
        self.route_result = {'status': 'error', 'error': 'route_not_allowed'}
        self.page.openAgent('hermes')
        self.assertEqual(self.toasts('error')[-1][1], self.host.s['wb_err_route'])

    def test_install_is_an_approval_card_and_runs_nothing(self):
        self.page.installAgent('claude')
        item = self.host.confirmations[-1]
        self.assertEqual((item['kind'], item['name'], item['args'], item['origin']),
                         ('moai', 'install_claude_code', {}, 'workbench'))
        # no consequence declared for it: the page's own sentence, never an empty card
        self.assertIn('Claude Code', item['detail'])
        self.assertEqual(self.executed, [])
        self.assertEqual(self.routes, [])
        self.assertEqual((self.st['agentNoteKey'], self.st['agentNote']), ('claude', self.host.s['wb_install_asked']))

    def test_without_a_declared_tool_it_explains_and_runs_nothing(self):
        self.NAMES = set()
        self.page.refresh()
        self.page.update(agents=[dict(a, installed=False) if a['key'] == 'codex' else a for a in self.st['agents']])
        self.page.installAgent('codex')
        self.assertEqual(self.host.confirmations, [])
        self.assertEqual((self.routes, self.executed), ([], []))
        self.assertTrue(self.st['agentNote'].endswith('moai-do install-codex'))

    def test_a_refused_card_is_reported(self):
        page = self.make_page(FakeHost(card=False))
        page.refresh()
        page.installAgent('claude')
        self.assertEqual(page.host.toast.calls[-1][0], 'error')

    def test_an_installed_agent_is_not_installed_again(self):
        self.page.installAgent('codex')
        self.assertEqual((self.host.confirmations, self.routes), ([], []))


class Sessions(WorkbenchCase):
    def setUp(self):
        super().setUp()
        self.page.refresh()

    def test_list_and_transcript_with_one_line_per_tool_call(self):
        self.assertEqual(self.st['sessions'][0]['label'], 'Check Git')
        self.page.openSession(SESSION)
        self.assertEqual(self.agent.last('/api/session')[2], {'id': SESSION})
        rows = self.st['transcript']
        self.assertEqual([(r['role'], r.get('tool', ''), r['status']) for r in rows], [
            ('user', '', ''), ('tool', 'git_status', 'success'), ('tool', 'run_command', 'pending'),
            ('tool', 'read_file', 'error'), ('assistant', '', '')])
        self.assertEqual(rows[1]['body'], '{"status": " M a"}')
        self.page.closeSession()
        self.assertEqual((self.st['session'], self.st['transcript']), ('', []))

    def test_a_missing_session_says_why(self):
        self.agent.answers['/api/session'] = {'error': 'agent_unreachable'}
        self.page.openSession(SESSION)
        self.assertEqual(self.st['transcriptError'], self.host.s['wb_err_unreachable'])


class GitNames(WorkbenchCase):
    """What `git status --short` really prints (measured 2026-09-29 in a scratch repository) becomes
    the real file name, and a click sends that name, never Git's quoting, to the diff."""

    def test_quoted_arabic_renamed_copied_and_conflicted_rows(self):
        rows = wb.git_rows('?? "a b.txt"\n?? "\\331\\205\\331\\204\\331\\201.txt"\n'
                           'R  plain.txt -> "\\331\\205\\330\\254\\331\\204\\330\\257 \\330\\254.txt"\n'
                           'R  "old name.txt" -> "new name.txt"\n?? "quo\\"te.txt"\n?? "t\\tb.txt"\n'
                           'C  src.py -> copy.py\nUU both.py\n?? "raw مجلد/ملف.txt"\n… output truncated …\n')
        self.assertEqual([r['path'] for r in rows],
                         ['a b.txt', 'ملف.txt', 'مجلد ج.txt', 'new name.txt', 'quo"te.txt', 't\tb.txt', 'copy.py',
                          'both.py', 'raw مجلد/ملف.txt'])
        renamed = rows[3]
        self.assertEqual((renamed['kind'], renamed['oldPath'], renamed['code']), ('renamed', 'old name.txt', 'R'))
        self.assertEqual(renamed['label'], wb.LRM + 'old name.txt → new name.txt')
        self.assertEqual((rows[2]['oldPath'], rows[6]['kind'], rows[6]['oldPath']), ('plain.txt', 'copied', 'src.py'))
        self.assertEqual(rows[7]['kind'], 'conflict')
        self.assertEqual(rows[0]['label'], 'a b.txt')

    def test_git_path_leaves_plain_and_broken_names_alone(self):
        self.assertEqual(wb.git_path('docs/a.md'), 'docs/a.md')
        self.assertEqual(wb.git_path('"unterminated'), '"unterminated')
        self.assertEqual(wb.git_path('"bad\\xZZ"'), 'bad\\xZZ')     # a malformed escape is shown, not raised

    def test_a_click_sends_the_real_name(self):
        self.page.refresh()
        self.page.openChange('ملف.txt')             # new (untracked): no diff is computed at all
        self.assertNotIn('/api/project/git-diff', self.agent.paths())
        self.assertEqual((self.st['diffShown'], self.st['diffNote'], self.st['diffPath']), (True, 'new', 'ملف.txt'))
        self.page.openChange('new name.txt')
        self.assertEqual(self.agent.last('/api/project/git-diff')[2], {'project': PID, 'path': 'new name.txt'})
        self.assertEqual(self.st['diffLabel'], wb.LRM + 'old name.txt → new name.txt')
        self.assertEqual(self.st['diffNote'], '')
        self.page.openChange('README.md')
        self.assertEqual(self.agent.last('/api/project/git-diff')[2], {'project': PID, 'path': 'README.md'})
        before = len(self.agent.calls)
        self.page.openChange('not in the list')
        self.assertEqual(len(self.agent.calls), before)

    def test_a_deleted_file_says_it_is_gone_and_offers_the_whole_diff(self):
        self.page.refresh()
        self.agent.answers['/api/project/git-diff'] = {'error': 'project entry does not exist'}
        self.page.openChange('old.txt')
        self.assertEqual(self.agent.last('/api/project/git-diff')[2], {'project': PID, 'path': 'old.txt'})
        self.assertEqual((self.st['diffNote'], self.st['diffError'], self.st['diffLoading']), ('gone', '', False))
        # a service that can diff a deleted name by itself shows it like any other
        self.agent.answers['/api/project/git-diff'] = {'unstaged': 'diff --git a/old.txt b/old.txt\ndeleted file mode 100644\n-x',
                                                       'staged': ''}
        self.page.openChange('old.txt')
        self.assertEqual((self.st['diffNote'], [line['k'] for line in self.st['diff']]), ('', ['head', 'meta', 'meta', 'del']))
        # the same reason about a file that is not a deletion is an error the owner reads
        self.agent.answers['/api/project/git-diff'] = {'error': 'project entry does not exist'}
        self.page.openChange('README.md')
        self.assertEqual((self.st['diffNote'], self.st['diffError']), ('', self.host.s['wb_err_entry_gone']))

    def test_read_a_new_file_opens_it_in_files_beside_its_folder(self):
        self.page.refresh()
        self.page.previewChange('docs/a b.txt')
        self.assertEqual(self.st['tab'], 'files')
        self.assertEqual(self.agent.last('/api/project/files')[2], {'project': PID, 'path': 'docs'})
        self.assertEqual(self.agent.last('/api/project/file')[2], {'project': PID, 'path': 'docs/a b.txt'})

    def test_counts_read_naturally(self):
        ar = {n: wb.changes_text(n, 'ar') for n in (1, 2, 3, 10, 11, 99, 100, 101, 103, 111)}
        self.assertEqual(ar, {1: 'تغيير واحد', 2: 'تغييران', 3: '3 تغييرات', 10: '10 تغييرات', 11: '11 تغييراً',
                              99: '99 تغييراً', 100: '100 تغيير', 101: '101 تغيير', 103: '103 تغييرات', 111: '111 تغييراً'})
        self.assertEqual([wb.changes_text(n, 'en') for n in (1, 2, 7)], ['1 change', '2 changes', '7 changes'])


class Freshness(WorkbenchCase):
    """Read again means read again: the open folder and the Git list of the same project too."""

    def test_refresh_rereads_the_open_folder_and_git_of_the_same_project(self):
        self.page.refresh()
        self.agent.answers['/api/project/files'] = {'path': 'docs', 'parent': '', 'truncated': False,
                                                    'entries': [{'name': 'a.md', 'path': 'docs/a.md', 'type': 'file'}]}
        self.page.openDir('docs')
        self.agent.answers['/api/project/files'] = {'path': 'docs', 'parent': '', 'truncated': False,
                                                    'entries': [{'name': 'a.md', 'path': 'docs/a.md', 'type': 'file'},
                                                                {'name': 'b.md', 'path': 'docs/b.md', 'type': 'file'}]}
        self.agent.answers['/api/project/git-status'] = {'status': '?? docs/b.md\n'}
        self.page.previewFile('docs/a.md')
        reads = self.agent.paths().count('/api/project/file')
        self.page.refresh()
        self.assertEqual(self.st['project'], PID)
        self.assertEqual(self.agent.last('/api/project/files')[2], {'project': PID, 'path': 'docs'})
        self.assertEqual([e['name'] for e in self.st['entries']], ['a.md', 'b.md'])
        self.assertEqual([r['path'] for r in self.st['gitRows']], ['docs/b.md'])
        self.assertEqual(self.st['gitCountText'], 'تغيير واحد')
        self.assertEqual(self.agent.paths().count('/api/project/file'), reads)     # the preview is never re-read
        self.assertNotIn('/api/project/git-diff', self.agent.paths())

    def test_pinning_does_not_reread_the_folder(self):
        self.page.refresh()
        before = self.agent.paths().count('/api/project/files')
        self.agent.answers['/api/project/upsert'] = {'ok': True, 'id': PID, 'name': 'MoOS', 'pinned': False}
        self.page.pinProject(PID, False)
        self.assertEqual(self.agent.paths().count('/api/project/files'), before)

    def test_a_vanished_folder_falls_back_to_the_root(self):
        self.page.refresh()
        self.page.update(dirPath='gone/dir')
        answers = {'gone/dir': {'error': 'project entry does not exist'},
                   '': {'path': '', 'parent': '', 'entries': [{'name': 'README.md', 'path': 'README.md', 'type': 'file'}]}}
        request = self.agent.request

        def files(method, route, body=None, query=None, timeout=15):
            if route == '/api/project/files':
                self.agent.calls.append((method, route, dict(query or {})))
                return answers[query['path']]
            return request(method, route, body, query, timeout)
        with mock.patch.object(wb.moai_agent, 'request', files):
            self.page.refresh()
        self.assertEqual((self.st['dirPath'], self.st['filesError']), ('', ''))
        self.assertEqual([e['name'] for e in self.st['entries']], ['README.md'])


class Errors(WorkbenchCase):
    def test_backend_reasons_become_the_owner_words(self):
        for reason, key in (('project entry does not exist', 'wb_err_entry_gone'),
                            ('project path escapes its root', 'wb_err_escapes'),
                            ('project entry is not a directory', 'wb_err_not_dir'),
                            ('invalid task title', 'wb_err_task_title'),
                            ('task description is too long', 'wb_err_task_long'),
                            ('unknown task project', 'wb_err_project_gone'),
                            ('task project no longer exists', 'wb_err_task_folder'),
                            ('invalid terminal input', 'wb_err_term_input'),
                            ('terminal input failed', 'wb_err_term_write'),
                            ('could not list project directory: [Errno 13] Permission denied', 'wb_err_list')):
            self.assertEqual(self.page._reason({'error': reason}), self.host.s[key], reason)
        self.assertEqual(self.page._reason({'error': 'brand new'}), self.host.s['wb_err_prefix'] + 'brand new')

    def test_timestamps_never_raise(self):
        self.assertEqual(wb.when(1_700_000_000_000), wb.when(1_700_000_000))     # milliseconds
        for value in (10 ** 30, float('inf'), float('nan'), 'garbage', True, -5, None, {}):
            self.assertEqual(wb.when(value), '', value)
        self.page.on_sessions('sessions:1:', [{'id': 's', 'updated': 'soon'}, {'id': 't', 'updated': 10 ** 40}])
        self.assertEqual([r['when'] for r in self.st['sessions']], ['', ''])
        rows = wb.transcript_rows([{'role': 'user', 'text': 'hi', 'ts': 1_700_000_000_123}])
        self.assertTrue(rows[0]['when'])


class TaskForm(WorkbenchCase):
    def setUp(self):
        super().setUp()
        self.page.refresh()
        self.created = []
        self.page.taskCreated.connect(lambda: self.created.append(True))

    def test_a_failed_create_keeps_the_owner_words(self):
        for reason in ({'error': 'agent_unreachable'}, {'error': 'invalid task title'}, {'error': 'unknown task project'}):
            self.agent.answers['/api/task/create'] = reason
            self.page.createTask('Add tests', 'd', '')
        self.assertEqual(self.created, [])
        self.assertEqual(self.toasts('error')[-1][1], self.host.s['wb_err_project_gone'])

    def test_only_an_accepted_task_clears_the_form(self):
        self.page.createTask('Add tests', 'd', '')
        self.assertEqual(self.created, [True])


class ReAddArchived(WorkbenchCase):
    def test_adding_an_archived_folder_again_brings_it_back_and_selects_it(self):
        self.page.refresh()
        state = {'archived': True}

        def request(method, route, body=None, query=None, timeout=15):
            self.agent.calls.append((method, route, body if method == 'POST' else dict(query or {})))
            project = {'id': PID2, 'name': 'Mira', 'path': '/home/o/mira', 'pinned': False}
            if route == '/api/project/upsert':
                state['archived'] = bool(body.get('archived', state['archived']))    # the service keeps the flag
                return {'ok': True, **project, 'archived': state['archived']}
            if route == '/api/projects':
                listed = [p for p in self.agent.answers['/api/projects'][:1]]
                return listed + ([] if state['archived'] else [dict(project, archived=False)])
            return self.agent.answers.get(route, {'error': 'not found'})
        with mock.patch.object(wb.moai_agent, 'request', request):
            self.page.addProject('/home/o/mira')
        self.assertFalse(state['archived'])
        self.assertEqual(self.st['project'], PID2)


class InstallNote(WorkbenchCase):
    """An install card's note lives only as long as it is true."""

    def setUp(self):
        super().setUp()
        self.page.refresh()
        self.page.installAgent('claude')

    def test_the_note_ends_when_moai_control_reads_it_installed(self):
        self.assertIn('claude', self.page._install_watch)
        self.quick = quick(agents={'claude': False, 'codex': True})
        self.page._poll_agents()
        self.assertEqual(self.st['agentNote'], self.host.s['wb_install_asked'])     # still waiting: nothing claimed
        self.quick = {'error': 'moai_control_unreachable'}
        self.page._poll_agents()
        self.assertEqual(self.st['agentNote'], self.host.s['wb_install_asked'])
        self.quick = quick(agents={'claude': True, 'codex': True})
        self.page._poll_agents()
        self.assertEqual((self.st['agentNote'], self.st['agentNoteKey']), ('', ''))
        self.assertTrue(next(a for a in self.st['agents'] if a['key'] == 'claude')['installed'])
        self.assertEqual(self.toasts('ok')[-1][1], self.host.s['wb_agent_now_installed'] + ' Claude Code')
        self.assertEqual(self.page._install_watch, {})

    def test_after_the_card_and_the_job_could_have_ended_it_says_not_yet(self):
        self.quick = quick(agents={'claude': False})
        self.page._install_watch['claude']['deadline'] = 0
        self.page._poll_agents()
        self.assertEqual(self.st['agentNote'], self.host.s['wb_install_not_yet'])
        self.assertEqual(self.page._install_watch, {})

    def test_the_controller_word_on_the_outcome(self):
        self.page._on_action_finished('install_codex', 'error')      # not this page's install
        self.assertEqual(self.st['agentNote'], self.host.s['wb_install_asked'])
        self.page._on_action_finished('install_claude_code', 'cancelled')
        self.assertEqual(self.st['agentNote'], self.host.s['wb_install_cancelled'])
        self.page.installAgent('claude')
        self.page._on_action_finished('install_claude_code', 'error')
        self.assertEqual(self.st['agentNote'], self.host.s['wb_install_failed'])
        self.page.installAgent('claude')
        self.quick = quick(agents={'claude': True})
        self.page._on_action_finished('install_claude_code', 'ok')    # 'ok' is checked against /quick
        self.assertEqual(self.st['agentNote'], '')

    def test_a_host_signal_reaches_the_page(self):
        from PySide6.QtCore import QObject, Signal as QtSignal

        class SignalHost(QObject):
            actionFinished = QtSignal(str, str)
        host = SignalHost()
        for name in ('lang', 's', 'toast', 'prefill', 'showSheet', 'confirmations', 'card', 'sent'):
            setattr(host, name, getattr(self.host, name))
        host.request_confirmation = self.host.request_confirmation
        page = self.make_page(host)
        page.refresh()
        page.installAgent('claude')
        host.actionFinished.emit('install_claude_code', 'expired')
        self.assertEqual(page.state['agentNote'], self.host.s['wb_install_cancelled'])

    def test_the_card_says_what_approving_really_does(self):
        self.page.update(agents=[dict(a, installed=False) if a['key'] == 'hermes' else a for a in self.st['agents']])
        self.page.installAgent('hermes')
        self.assertEqual(self.host.confirmations[-1]['detail'], self.CONSEQUENCES[('install_hermes', 'ar')])
        english = self.make_page(FakeHost('en'))
        english.refresh()
        english.update(agents=[dict(a, installed=False) if a['key'] == 'hermes' else a for a in english.state['agents']])
        english.installAgent('hermes')
        self.assertEqual(english.host.confirmations[-1]['detail'], self.CONSEQUENCES[('install_hermes', 'en')])


class Terminals(WorkbenchCase):
    """Dozens of the agent's command terminals never bury the owner's own."""

    def many(self):
        rows = [{'id': TERM, 'title': 'MoOS', 'cwd': '/p', 'running': True, 'exit_code': None, 'created': 500}]
        rows += [{'id': f'00000000-0000-4000-8000-{n:012d}', 'title': f'Mo AI: cmd {n}', 'cwd': '/p',
                  'running': False, 'exit_code': 0, 'created': 100 + n} for n in range(12)]
        rows += [{'id': '11111111-0000-4000-8000-000000000000', 'title': 'old shell', 'cwd': '/p', 'running': False,
                  'exit_code': 0, 'created': 50}]
        return rows

    def test_only_the_newest_agent_terminals_and_the_owner_ones(self):
        self.agent.answers['/api/terminals'] = self.many()
        self.page.refresh()
        titles = [t['title'] for t in self.st['terminals']]
        self.assertEqual(titles, ['MoOS', 'Mo AI: cmd 11', 'Mo AI: cmd 10', 'Mo AI: cmd 9', 'Mo AI: cmd 8'])
        self.assertEqual(self.st['termsHidden'], 9)      # 8 older agent runs + an ended shell of another session
        self.page.setShowAllTerms(True)
        self.assertEqual((len(self.st['terminals']), self.st['termsHidden']), (14, 0))
        self.page.setShowAllTerms(False)
        self.page.selectTerminal('00000000-0000-4000-8000-000000000001')    # the one on screen stays listed
        self.assertIn('Mo AI: cmd 1', [t['title'] for t in self.st['terminals']])

    def test_an_owner_terminal_that_ended_in_this_session_stays(self):
        self.agent.answers['/api/terminals'] = self.many()
        self.page.refresh()
        self.agent.answers['/api/terminals'] = [dict(t, running=False) if t['id'] == TERM else t for t in self.many()]
        self.page.update(terminal='')
        self.page.setTab('terminal')
        self.page._read('terms', wb.agent_get, '/api/terminals')
        self.assertIn('MoOS', [t['title'] for t in self.st['terminals']])
        self.assertNotIn('old shell', [t['title'] for t in self.st['terminals']])

    def test_ctrl_l_clears_only_the_view(self):
        self.page.refresh()
        writes = self.agent.paths().count('/api/terminal/write')
        self.page.clearTerminalView()
        self.assertEqual(self.st['termOutput'], '')
        self.assertEqual(self.agent.paths().count('/api/terminal/write'), writes)
        self.page._poll_terminal()                  # new output still arrives after it
        self.assertTrue(self.st['termOutput'])


class AgentFolder(WorkbenchCase):
    def test_run_opens_in_the_project_when_moos_open_can(self):
        allowed = wb.moos_routes.allowed
        with mock.patch.object(wb.moos_routes, 'allowed',
                               lambda url: bool(re.fullmatch(r'moos://dev/(code|codex|claude|opencode)/[0-9a-f]{20}', url))
                               or allowed(url)):
            self.page.refresh()
            self.assertTrue(self.st['agentsInProject'])
            self.page.openAgent('codex')
            self.page.openAgent('code')
        self.assertEqual(self.routes, ['moos://dev/codex/' + PID, 'moos://dev/code/' + PID])
        self.assertTrue(self.toasts('info')[-1][1].endswith(' · MoOS'))

    def test_without_that_route_it_says_where_it_opens(self):
        self.enterContext(without_project_routes())
        self.page.refresh()
        self.assertFalse(self.st['agentsInProject'])
        self.page.openAgent('codex')
        self.assertEqual(self.routes, ['moos://dev/codex'])
        self.assertFalse(self.toasts('info')[-1][1].endswith(' · MoOS'))


class Threads(WorkbenchCase):
    def test_the_tool_list_is_read_on_the_qt_thread_only(self):
        import threading
        seen = []
        page = wb.WorkbenchPage(self.host)

        def run(tag, fn, *args, **kwargs):             # a real worker thread
            box = []
            worker = threading.Thread(target=lambda: box.append(fn(*args, **kwargs)))
            worker.start()
            worker.join()
            page._done.emit(tag, box[0])
        page.run = run
        with mock.patch.object(wb.moai_tools, 'names', lambda: seen.append(threading.current_thread()) or set(self.NAMES)):
            page.refresh()
        self.assertTrue(seen)
        self.assertTrue(all(thread is threading.main_thread() for thread in seen))
        self.assertEqual(next(a for a in page.state['agents'] if a['key'] == 'claude')['tool'], 'install_claude_code')


class RealRequest(unittest.TestCase):
    def test_agent_get_carries_the_path_query_and_the_agent_header(self):
        import io
        import json
        seen = []

        class Answer(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        def open_(request, timeout=None):
            seen.append(request)
            return Answer(json.dumps({'entries': []}).encode())
        with mock.patch.object(wb.moai_agent._OPENER, 'open', open_):
            self.assertEqual(wb.agent_get('/api/project/files', {'project': PID, 'path': 'docs/a b'}), {'entries': []})
        url = seen[0].full_url
        self.assertTrue(url.startswith('http://127.0.0.1:'), url)
        self.assertIn('path=docs%2Fa+b', url)
        self.assertEqual(seen[0].get_header('X-moai-agent'), '1')
        self.assertEqual(seen[0].get_method(), 'GET')


class Words(unittest.TestCase):
    def test_every_word_in_both_languages_and_no_foreign_os_name(self):
        for key, pair in wb.STRINGS.items():
            self.assertEqual(len(pair), 2, key)
            self.assertTrue(all(isinstance(w, str) and w.strip() for w in pair), key)
            self.assertFalse(any(name in w for w in pair for name in ('Fedora', 'Red Hat', 'fedora')), key)
        for key in ('wb_reason_ready', 'wb_reason_offline', 'wb_reason_gateway', 'wb_reason_key'):
            self.assertIn(key, wb.STRINGS)
        for key in wb.ERRORS.values():
            self.assertIn(key, wb.STRINGS)
        merged = i18n.table('en')
        self.assertEqual(merged['wb_tab_terminal'], 'Terminal')

    def test_review_fills_every_part_of_the_page(self):
        page = wb.WorkbenchPage(FakeHost())
        with mock.patch.object(wb.moos_routes, 'open_route', side_effect=AssertionError('review opens nothing')):
            page.review()
        state = page.state
        for key in ('projects', 'entries', 'gitRows', 'diff', 'tasks', 'terminals', 'agents', 'sessions', 'transcript'):
            self.assertTrue(state[key], key)
        self.assertEqual(state['ready'], 'ready')


if __name__ == '__main__':
    unittest.main()
