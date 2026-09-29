"""The agent approvals inbox against a stand-in agent API (moai_agent.request patched; no service).

The stand-in follows moai_runtime.Runtime: approvals are rows {id, session, command (JSON), cwd,
expires, task, warning, allowed, created}; resolve takes exactly {id, decision}, only 'allow-once'
or 'deny', and answers 'approval is no longer pending' for an unknown, answered or expired id.
`/api/tasks?status=running` lists the agent tasks that run now (moai-agent-api list_tasks).

The last class loads the real ActionCards.qml with a stand-in `mira` and checks the two promises
of an agent card on screen: the request is shown open, as plain text, and an Allow button is only
ever on screen for the one request that is open.
"""
import json
import os
import re
import tempfile
import threading
import time
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_QUICK_BACKEND', 'software')
os.environ['MIRA_TEST_MODE'] = '1'
_config = tempfile.TemporaryDirectory(prefix='mira-inbox-test-')
os.environ['XDG_CONFIG_HOME'] = _config.name

from PySide6.QtCore import (Q_ARG, Q_RETURN_ARG, Property, QCoreApplication, QMetaObject,  # noqa: E402
                            QObject, QSettings, Qt, QUrl, Slot)
from PySide6.QtGui import QGuiApplication  # noqa: E402

import i18n  # noqa: E402
import inbox  # noqa: E402

APP = QGuiApplication.instance() or QGuiApplication([])
QSettings.setDefaultFormat(QSettings.IniFormat)
QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, _config.name)
ROOT = Path(__file__).resolve().parent
ALLOWED_PATHS = {('GET', '/api/approvals'), ('GET', '/api/tasks'), ('POST', '/api/approval/resolve')}


def action_roles():
    """The roles of controller.actions (the model ActionCards shows)."""
    source = (ROOT / 'controller.py').read_text()
    roles = re.search(r"self\.actions = DictListModel\(\[(.*?)\]", source, re.S).group(1)
    return re.findall(r"'([a-z]+)'", roles)


def pump(predicate=lambda: False, timeout=2.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        QCoreApplication.processEvents()
        if predicate():
            return True
        time.sleep(0.005)
    QCoreApplication.processEvents()
    return predicate()


class Clock:
    def __init__(self):
        self.t = 1_800_000_000.0

    def __call__(self):
        return self.t


class FakeAgent:
    """moai-agent-api's approvals, in memory (runtime semantics)."""

    def __init__(self, clock):
        self.clock = clock
        self.rows = {}
        self.decisions = {}
        self.calls = []
        self.queries = []
        self.unreachable = False
        self.tasks = []            # what /api/tasks?status=running lists (or an error dict)
        self.lock = threading.Lock()
        self.hold = None          # a threading.Event the resolve waits on (to test in-flight answers)

    def now_ms(self):
        return int(self.clock() * 1000)

    def add_run(self, command, project='moos-image', cwd='/var/home/moos/moos-image', ttl=120):
        aid = str(uuid.uuid4())
        payload = json.dumps({'tool': 'run_command', 'arguments': {'project': project, 'command': command}},
                             ensure_ascii=False)
        self.rows[aid] = {'id': aid, 'session': str(uuid.uuid4()), 'command': payload, 'cwd': cwd,
                          'expires': self.now_ms() + ttl * 1000, 'task': '', 'warning': inbox.RUNTIME_WARNING,
                          'allowed': ['allow-once', 'deny'], 'created': 0}
        return aid

    def add_write(self, path, content, sha256=''):
        aid = str(uuid.uuid4())
        payload = json.dumps({'tool': 'write_file', 'arguments': {'project': 'site', 'path': path,
                                                                  'content': content, 'sha256': sha256}})
        self.rows[aid] = {'id': aid, 'session': 's', 'command': payload, 'cwd': '/var/home/moos/site',
                          'expires': self.now_ms() + 120000, 'task': '', 'warning': inbox.RUNTIME_WARNING,
                          'allowed': ['allow-once', 'deny'], 'created': 0}
        return aid

    def request(self, method, path, body=None, query=None, timeout=15):
        with self.lock:
            self.calls.append((method, path, body))
            self.queries.append((path, query))
        if self.unreachable:
            return {'error': 'agent_unreachable', 'detail': 'URLError'}
        if (method, path) == ('GET', '/api/tasks'):
            return self.tasks
        if (method, path) == ('GET', '/api/approvals'):
            now = self.now_ms()
            return [dict(r) for r in self.rows.values() if r['id'] not in self.decisions and r['expires'] > now]
        if (method, path) == ('POST', '/api/approval/resolve'):
            if self.hold is not None:
                self.hold.wait(2)
            if set(body) != {'id', 'decision'} or body['decision'] not in ('allow-once', 'deny'):
                return {'error': 'only one-time approval or deny is allowed'}
            row = self.rows.get(body['id'])
            if row is None or body['id'] in self.decisions or row['expires'] <= self.now_ms():
                return {'error': 'approval is no longer pending'}
            self.decisions[body['id']] = body['decision']
            return {'ok': True, **body}
        return {'error': 'not found'}

    def resolves(self):
        return [c for c in self.calls if c[1] == '/api/approval/resolve']

    def task_reads(self):
        return [c for c in self.calls if c[1] == '/api/tasks']


class InboxTest(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.agent = FakeAgent(self.clock)
        self.patcher = patch('moai_agent.request', side_effect=self.agent.request)
        self.patcher.start()
        self.box = inbox.AgentInbox(live=True, clock=self.clock)
        self.arrived, self.gone, self.resolved = [], [], []
        self.box.arrived.connect(lambda item: self.arrived.append(dict(item)))
        self.box.gone.connect(lambda aid, why: self.gone.append((aid, why)))
        self.box.resolved.connect(lambda aid, d, r: self.resolved.append((aid, d, dict(r))))
        self.s = i18n.table('en')

    def tearDown(self):
        self.box.stop()
        pump(lambda: not self.box._polling, 2)
        self.patcher.stop()
        for method, path, _ in self.agent.calls:
            self.assertIn((method, path), ALLOWED_PATHS)      # nothing else of the agent API is touched
        for path, query in self.agent.queries:
            if path == '/api/tasks':
                self.assertEqual(query, {'status': 'running'})   # a plain read of the running tasks

    def start(self):
        self.box.start()
        self.assertTrue(pump(lambda: self.box.status == 'online' and not self.box._polling))

    def poll(self):
        before = len([c for c in self.agent.calls if c[1] == '/api/approvals'])
        self.box.poll()
        self.assertTrue(pump(lambda: len([c for c in self.agent.calls if c[1] == '/api/approvals']) > before
                             and not self.box._polling))

    # ── the shapes of the service ───────────────────────────────────
    def test_runtime_command_is_shown_exactly(self):
        command = "git log --oneline -3 | grep 'fix' && echo \"تم\" > /tmp/out.txt"
        aid = self.agent.add_run(command)
        self.start()
        self.assertEqual(self.box.count, 1)
        item = self.box.items[0]
        self.assertEqual(item['id'], aid)
        self.assertEqual(item['tool'], 'run_command')
        self.assertEqual(item['command'], command)            # the exact text that will run
        self.assertEqual(item['cwd'], '/var/home/moos/moos-image')
        self.assertEqual(item['project'], 'moos-image')
        self.assertEqual(item['expires'], self.agent.rows[aid]['expires'])
        self.assertEqual(item['allowed'], ['allow-once', 'deny'])
        self.assertFalse(item['hidden'])
        self.assertEqual([a['id'] for a in self.arrived], [aid])

    def test_write_file_shows_path_content_and_whether_it_replaces(self):
        new = self.agent.add_write('docs/new.md', 'line one\nline two\n')
        old = self.agent.add_write('README.md', 'x', sha256='ab' * 32)
        self.start()
        items = {i['id']: i for i in self.box.items}
        self.assertEqual(items[new]['tool'], 'write_file')
        self.assertEqual(items[new]['path'], 'docs/new.md')
        self.assertEqual(items[new]['command'], 'line one\nline two\n')
        self.assertTrue(items[new]['new_file'])
        self.assertFalse(items[old]['new_file'])
        line = inbox.context_line(items[new], self.s)
        self.assertIn('\u2066docs/new.md\u2069', line)          # a path stays left-to-right in Arabic
        self.assertIn(self.s['agent_approval_new_file'], line)
        self.assertIn('Lines: 2', line)
        self.assertIn(self.s['agent_approval_replace'], inbox.context_line(items[old], self.s))
        # the file, then the folder on a line of its own: both whole, never cut
        first, folder = line.split('\n')
        self.assertTrue(first.startswith('\u2066docs/new.md'))
        self.assertEqual(folder, 'In \u2066/var/home/moos/site\u2069')

    def test_gateway_rows_and_never_allow_always(self):
        now = int(self.clock() * 1000)
        row = {'id': str(uuid.uuid4()), 'task': str(uuid.uuid4()), 'command': 'npm test', 'cwd': '/p',
               'warning': 'Gateway says: review it', 'allowed': ['allow-once', 'allow-always', 'deny'],
               'created': now - 5000, 'expires': now + 60000}
        item = inbox.normalize(row, now)
        self.assertEqual(item['tool'], 'exec')
        self.assertEqual(item['command'], 'npm test')
        self.assertEqual(item['task'], row['task'])
        self.assertEqual(item['allowed'], ['allow-once', 'deny'])
        self.assertNotIn('allow-always', inbox.DECISIONS)
        self.assertIn('Gateway says: review it', inbox.safety_note(item, self.s))   # its own warning, word for word
        self.assertEqual(inbox.review_text(item), '$ npm test')
        self.assertEqual(inbox.title(item, self.s), self.s['agent_approval_run'])

    def test_rows_that_cannot_be_answered_are_not_shown(self):
        now = int(self.clock() * 1000)
        good = {'id': str(uuid.uuid4()), 'command': 'ls', 'expires': now + 1000}
        self.assertIsNotNone(inbox.normalize(good, now))
        self.assertIsNone(inbox.normalize({**good, 'id': 'x; rm -rf /'}, now))
        self.assertIsNone(inbox.normalize({**good, 'expires': now}, now))
        self.assertIsNone(inbox.normalize('not a row', now))
        other = inbox.normalize({**good, 'command': json.dumps({'tool': 'delete_all', 'arguments': {'x': '1'}})}, now)
        self.assertEqual(other['tool'], 'request')                # an unknown tool is read word for word
        self.assertIn('delete_all', inbox.review_text(other))
        self.assertEqual(inbox.title(other, self.s), self.s['agent_approval_title'])
        broken = inbox.normalize({**good, 'command': json.dumps({'tool': 'run_command', 'arguments': {}})}, now)
        self.assertEqual(broken['tool'], 'request')

    def test_hidden_characters_are_revealed_and_block_the_notification_allow(self):
        text, hidden = inbox.reveal('echo safe‮;rm -rf ~‬')
        self.assertTrue(hidden)
        self.assertIn('⟦U+202E⟧', text)
        self.assertEqual(inbox.reveal('a\r\nb\tc\n'), ('a\r\nb\tc\n', False))
        self.assertTrue(inbox.reveal('shown\rhidden')[1])          # a lone CR can overwrite what is seen
        # characters that are not "format" or "control" but still show nothing, or look like a space
        for ch in ('\ufe0f', '\ufe00', '\U000e0100', '\U000e01ef',     # variation selectors (text smuggling)
                   '\u115f', '\u1160', '\u3164', '\uffa0',               # Hangul fillers (invisible identifiers)
                   '\u00a0', '\u2000', '\u200a', '\u3000', '\u2800',     # non-ASCII spaces, blank braille
                   '\u034f', '\u0378'):                                  # grapheme joiner, unassigned
            shown, flagged = inbox.reveal('rm' + ch + 'x')
            self.assertTrue(flagged, hex(ord(ch)))
            self.assertEqual(shown, f'rm⟦U+{ord(ch):04X}⟧x')
        # ordinary Arabic, with its vowel marks, and plain ASCII are not flagged
        self.assertEqual(inbox.reveal('echo "مَرْحَباً بِكَ" && ls -la'), ('echo "مَرْحَباً بِكَ" && ls -la', False))
        aid = self.agent.add_run('echo ok​')
        self.start()
        item = self.box.item(aid)
        self.assertTrue(item['hidden'])
        self.assertIn('⟦U+200B⟧', inbox.card(item, self.s)['output'])
        self.assertIn(self.s['agent_approval_hidden'], inbox.card(item, self.s)['reason'])
        self.assertFalse(inbox.notification(item, self.s)['can_allow'])

    def test_notification_escapes_markup_and_allows_only_what_fits(self):
        now = int(self.clock() * 1000)

        def row(command):
            return inbox.normalize({'id': str(uuid.uuid4()), 'command': command, 'expires': now + 9000}, now)
        short = row('echo <b>hi</b> & ls')
        note = inbox.notification(short, self.s)
        self.assertTrue(note['can_allow'])
        self.assertIn('&lt;b&gt;hi&lt;/b&gt; &amp; ls', note['body'])
        self.assertNotIn('<b>', note['body'])
        self.assertTrue(inbox.notification(row('make\nmake install'), self.s)['can_allow'])   # a plain line break survives
        long = row('x' * 400)
        self.assertFalse(inbox.notification(long, self.s)['can_allow'])
        self.assertIn(self.s['agent_approval_notify_review'], inbox.notification(long, self.s)['body'])
        # Plasma collapses whitespace runs and drops indentation: such a command is allowed only on its card
        for command in ("printf 'a  b'", "printf 'a\tb'", 'if true\n  then ls', 'ls\n\nrm x', ' ls', 'ls ', 'ls\r\nrm x'):
            note = inbox.notification(row(command), self.s)
            self.assertFalse(note['can_allow'], repr(command))
            self.assertIn(self.s['agent_approval_notify_spacing'], note['body'], repr(command))
        # a request that is not a command is never allowed from a notice, and never shown as one
        other = inbox.normalize({'id': str(uuid.uuid4()), 'expires': now + 9000,
                                 'command': json.dumps({'tool': 'delete_all', 'arguments': {'x': '1'}})}, now)
        note = inbox.notification(other, self.s)
        self.assertFalse(note['can_allow'])
        self.assertNotIn('$ ', note['body'])
        self.assertIn(self.s['agent_approval_notify_request'], note['body'])
        write = inbox.normalize({'id': str(uuid.uuid4()), 'expires': now + 9000, 'command': json.dumps(
            {'tool': 'write_file', 'arguments': {'path': 'a.txt', 'content': 'x'}})}, now)
        self.assertFalse(inbox.notification(write, self.s)['can_allow'])

    def test_notice_lives_only_as_long_as_the_request(self):
        now = int(self.clock() * 1000)
        self.assertEqual(inbox.notice_ttl_ms({'expires': now + 90000}, now), 90000)
        self.assertEqual(inbox.notice_ttl_ms({'expires': now - 5}, now), 1000)
        self.assertEqual(inbox.notice_ttl_ms({'expires': 0}, now), 120000)

    def test_failures_are_told_in_words_not_codes(self):
        self.assertEqual(inbox.failure_text('agent_unreachable', self.s),
                         self.s['agent_approval_failed'] + ': ' + self.s['agent_approval_unreachable'])
        for code in ('http_500', 'unexpected_reply', 'OpenClaw Gateway is not configured', ''):
            self.assertEqual(inbox.failure_text(code, self.s), self.s['agent_approval_failed'])
        self.assertEqual(inbox.waiting_text(3, self.s), 'Agent requests waiting for your approval: 3')

    def test_card_matches_the_action_cards_model(self):
        roles = action_roles()
        aid = self.agent.add_run('make check')
        self.start()
        row = inbox.card(self.box.item(aid), self.s)
        self.assertEqual(sorted(row), sorted(roles))
        self.assertEqual(row['aid'], inbox.card_id(aid))
        self.assertEqual(inbox.approval_id(row['aid']), aid)
        self.assertEqual(inbox.approval_id('p0123456789'), '')      # a Mo AI card is not an agent card
        self.assertEqual(row['kind'], 'agent')
        self.assertEqual(row['stage'], 'ask')
        self.assertEqual(row['output'], '$ make check')
        self.assertEqual(row['expires'], self.agent.rows[aid]['expires'])
        self.assertEqual(row['title'], self.s['agent_approval_run'])
        self.assertIn('/var/home/moos/moos-image', row['detail'])
        self.assertEqual(row['reason'], self.s['agent_approval_run_note'])

    # ── polling ─────────────────────────────────────────────────────
    def test_reads_fast_while_busy_and_slow_otherwise(self):
        self.start()
        self.assertEqual(self.box._timer.interval(), inbox.IDLE_MS)
        self.box.busy(True, 'turn')
        pump(lambda: self.box.active)
        self.assertTrue(self.box.active)
        self.assertEqual(self.box._timer.interval(), inbox.FAST_MS)
        self.box.busy(False, 'turn')
        pump(lambda: not self.box.active)
        self.poll()
        self.assertEqual(self.box._timer.interval(), inbox.FAST_MS)   # lingers after the work ends
        self.clock.t += inbox.LINGER_S + 1
        self.poll()
        self.assertEqual(self.box._timer.interval(), inbox.IDLE_MS)
        self.agent.add_run('ls')
        self.poll()
        self.assertEqual(self.box._timer.interval(), inbox.FAST_MS)   # something waits: keep it current

    def test_a_running_agent_task_keeps_reads_fast(self):
        """A started task runs for minutes after Mira's turn ended; its approvals must not wait 20 s."""
        self.agent.tasks = [{'id': str(uuid.uuid4()), 'title': 'fix the build', 'status': 'running'}]
        self.start()
        self.assertTrue(self.box.tasksRunning)
        self.assertTrue(self.box.active)
        self.assertEqual(self.box._timer.interval(), inbox.FAST_MS)
        self.clock.t += inbox.TASK_CHECK_S + 1
        self.poll()
        self.assertEqual(self.box._timer.interval(), inbox.FAST_MS)      # still running: still fast
        self.agent.tasks = []                                             # the task ended
        self.clock.t += inbox.TASK_CHECK_S + 1
        self.poll()
        self.assertFalse(self.box.tasksRunning)
        self.assertEqual(self.box._timer.interval(), inbox.FAST_MS)      # lingers a little
        self.clock.t += inbox.LINGER_S + 1
        self.poll()
        self.assertEqual(self.box._timer.interval(), inbox.IDLE_MS)

    def test_running_tasks_are_read_sparingly_and_a_failed_read_is_not_running(self):
        self.start()
        self.poll()
        self.poll()
        self.assertEqual(len(self.agent.task_reads()), 1)                # at most every TASK_CHECK_S
        self.clock.t += inbox.TASK_CHECK_S + 1
        self.poll()
        self.assertEqual(len(self.agent.task_reads()), 2)
        self.agent.tasks = {'error': 'not found'}                          # an older agent API
        self.clock.t += inbox.TASK_CHECK_S + 1
        self.poll()
        self.assertFalse(self.box.tasksRunning)
        self.assertEqual(self.box.status, 'online')                      # the approvals themselves still read fine

    def test_reads_stay_fast_after_an_answer(self):
        """After an answer the agent's next write or command follows at once: keep reading fast."""
        aid = self.agent.add_run('pytest -q')
        self.start()
        self.assertTrue(self.box.resolve(aid, 'allow-once'))
        self.assertTrue(pump(lambda: self.resolved and not self.box._polling))
        self.poll()
        self.assertEqual(self.box.count, 0)
        self.assertEqual(self.box._timer.interval(), inbox.FAST_MS)
        self.clock.t += inbox.AFTER_ANSWER_S - 10
        self.poll()
        self.assertEqual(self.box._timer.interval(), inbox.FAST_MS)
        self.clock.t += 11
        self.poll()
        self.assertEqual(self.box._timer.interval(), inbox.IDLE_MS)

    def test_a_stale_read_cannot_revive_an_answered_request(self):
        aid = self.agent.add_run('ls')
        self.start()
        stale = [dict(self.agent.rows[aid])]                              # a read that began before the answer
        self.assertTrue(self.box.resolve(aid, 'deny'))
        self.assertTrue(pump(lambda: self.resolved))
        self.box._on_poll({'approvals': stale, 'tasks': None})            # ...and is delivered after it
        self.assertEqual(self.box.count, 0)
        self.assertEqual(len(self.arrived), 1)                            # announced once, when it came
        self.poll()
        self.assertEqual(self.gone, [])                                   # answered here: never "gone"

    def test_several_sources_keep_it_busy(self):
        self.start()
        self.box.busy(True, 'turn')
        self.box.busy(True, 'workbench')
        self.box.busy(False, 'turn')
        pump(lambda: self.box._sources == {'workbench'})
        self.assertTrue(self.box.active)

    def test_busy_from_another_thread_lands_on_the_qt_thread(self):
        self.start()
        seen = []

        class Sources(set):
            def add(self, value):
                seen.append(threading.current_thread() is threading.main_thread())
                super().add(value)
        self.box._sources = Sources()
        worker = threading.Thread(target=lambda: self.box.busy(True, 'voice'))
        worker.start()
        worker.join()
        self.assertTrue(pump(lambda: 'voice' in self.box._sources))
        self.assertEqual(seen, [True])
        self.assertEqual(self.box._timer.interval(), inbox.FAST_MS)

    def test_arrivals_are_announced_once(self):
        self.agent.add_run('ls')
        self.start()
        self.poll()
        self.poll()
        self.assertEqual(len(self.arrived), 1)

    def test_unreachable_keeps_items_and_reports_it(self):
        aid = self.agent.add_run('ls')
        self.start()
        self.agent.unreachable = True
        self.poll()
        self.assertEqual(self.box.status, 'unreachable')
        self.assertIsNotNone(self.box.item(aid))         # it still expires on its own time
        self.agent.unreachable = False
        self.poll()
        self.assertEqual(self.box.status, 'online')
        self.assertEqual(self.box.error, '')

    def test_service_error_is_reported(self):
        with patch('moai_agent.request', return_value={'error': 'OpenClaw Gateway is not configured'}):
            self.box.start()
            self.assertTrue(pump(lambda: self.box.status == 'error'))
        self.assertIn('not configured', self.box.error)

    # ── the owner's answer ──────────────────────────────────────────
    def test_allow_once_sends_exactly_id_and_decision(self):
        aid = self.agent.add_run('pytest -q')
        self.start()
        self.assertTrue(self.box.resolve(aid, 'allow-once'))
        self.assertTrue(pump(lambda: self.resolved))
        self.assertEqual(self.agent.resolves(), [('POST', '/api/approval/resolve', {'id': aid, 'decision': 'allow-once'})])
        self.assertEqual(self.resolved[0][:2], (aid, 'allow-once'))
        self.assertEqual(self.resolved[0][2]['status'], 'ok')
        self.assertEqual(self.agent.decisions, {aid: 'allow-once'})
        self.assertIsNone(self.box.item(aid))
        self.assertEqual(self.gone, [])                 # answered here, not "gone"

    def test_deny(self):
        aid = self.agent.add_run('rm -rf build')
        self.start()
        self.assertTrue(self.box.resolve(aid, 'deny'))
        self.assertTrue(pump(lambda: self.resolved))
        self.assertEqual(self.resolved[0][2]['status'], 'ok')
        self.assertEqual(self.agent.decisions, {aid: 'deny'})

    def test_one_answer_only_while_it_is_on_its_way(self):
        aid = self.agent.add_run('make')
        self.start()
        self.agent.hold = threading.Event()
        self.assertTrue(self.box.resolve(aid, 'deny'))
        pump(lambda: self.box.items and self.box.items[0]['resolving'] == 'deny', 1)
        self.assertEqual(self.box.items[0]['resolving'], 'deny')
        self.assertFalse(self.box.resolve(aid, 'allow-once'))
        self.assertFalse(self.box.resolve(aid, 'deny'))
        self.agent.hold.set()
        self.assertTrue(pump(lambda: self.resolved))
        self.assertEqual(len(self.agent.resolves()), 1)
        self.assertEqual(self.agent.decisions, {aid: 'deny'})

    def test_an_answer_on_its_way_is_never_reported_gone(self):
        """While an answer travels, its request may leave the queue or expire; that is not "gone":
        the answer's own `resolved` tells what happened."""
        listed, expiring = self.agent.add_run('make'), self.agent.add_run('make install', ttl=30)
        self.start()
        self.agent.hold = threading.Event()                 # both answers stay on their way
        self.assertTrue(self.box.resolve(listed, 'deny'))
        self.assertTrue(self.box.resolve(expiring, 'deny'))
        self.agent.decisions[listed] = 'deny'               # the service took it; its reply is still coming
        self.poll()                                         # a read no longer lists it
        self.assertEqual(self.gone, [])
        self.clock.t += 31                                  # the other one expires meanwhile
        self.box._tick()                                    # the local clock drops it
        self.assertIsNone(self.box.item(expiring))
        self.assertTrue(pump(lambda: not self.box._polling))
        self.assertEqual(self.gone, [])
        self.agent.hold.set()
        self.assertTrue(pump(lambda: len(self.resolved) == 2))
        self.assertEqual({r[2]['status'] for r in self.resolved}, {'gone'})
        self.assertEqual(self.gone, [])

    def test_qml_cannot_answer_directly(self):
        """Only the card's buttons (controller.approveAction/rejectAction) reach resolve()."""
        meta = self.box.metaObject()
        names = {bytes(meta.method(i).name().data()).decode() for i in range(meta.methodCount())}
        for name in ('resolve', 'start', 'stop'):
            self.assertNotIn(name, names)                  # no page may answer, or switch the inbox off
        self.assertIn('poll', names)

    def test_refused_answers_send_nothing(self):
        aid = self.agent.add_run('ls')
        self.start()
        self.assertFalse(self.box.resolve(aid, 'allow-always'))
        self.assertFalse(self.box.resolve(aid, 'yes'))
        self.assertFalse(self.box.resolve(str(uuid.uuid4()), 'allow-once'))   # never shown here
        self.assertFalse(self.box.resolve('../../etc', 'deny'))
        self.clock.t += 121                                                    # expired
        self.assertFalse(self.box.resolve(aid, 'allow-once'))
        pump(timeout=0.2)
        self.assertEqual(self.agent.resolves(), [])

    def test_a_request_too_long_to_read_cannot_be_allowed(self):
        aid = self.agent.add_run('echo ' + 'y' * inbox.MAX_SHOWN)
        self.start()
        item = self.box.item(aid)
        self.assertFalse(item['complete'])
        self.assertIn(self.s['agent_approval_too_long'], inbox.safety_note(item, self.s))
        self.assertFalse(self.box.resolve(aid, 'allow-once'))
        self.assertTrue(self.box.resolve(aid, 'deny'))            # denying is always possible
        self.assertTrue(pump(lambda: self.resolved))
        self.assertEqual(self.agent.decisions, {aid: 'deny'})

    def test_answer_after_it_ended_elsewhere_is_gone(self):
        aid = self.agent.add_run('ls')
        self.start()
        self.agent.decisions[aid] = 'deny'          # answered from Mo AI's own window meanwhile
        self.assertTrue(self.box.resolve(aid, 'allow-once'))
        self.assertTrue(pump(lambda: self.resolved))
        self.assertEqual(self.resolved[0][2]['status'], 'gone')
        self.assertIsNone(self.box.item(aid))
        self.assertEqual(self.agent.decisions[aid], 'deny')          # nothing changed by this answer

    def test_failed_answer_keeps_the_item_answerable(self):
        aid = self.agent.add_run('ls')
        self.start()
        self.agent.unreachable = True
        self.assertTrue(self.box.resolve(aid, 'allow-once'))
        self.assertTrue(pump(lambda: self.resolved))
        self.assertEqual(self.resolved[0][2]['status'], 'error')
        self.assertEqual(self.resolved[0][2]['error'], 'agent_unreachable')
        self.assertEqual(self.box.item(aid)['resolving'], '')
        self.agent.unreachable = False
        self.assertTrue(self.box.resolve(aid, 'deny'))
        self.assertTrue(pump(lambda: len(self.resolved) == 2))
        self.assertEqual(self.agent.decisions, {aid: 'deny'})

    def test_unexpected_reply_is_not_success(self):
        self.assertEqual(inbox._classify({'ok': True, 'id': 'a', 'decision': 'deny'}, 'a', 'allow-once')['status'], 'error')
        self.assertEqual(inbox._classify({'ok': False}, 'a', 'deny')['status'], 'error')
        self.assertEqual(inbox._classify(None, 'a', 'deny')['status'], 'error')
        self.assertEqual(inbox._classify([], 'a', 'deny')['status'], 'error')

    # ── expiry: nothing is ever allowed by default ─────────────────
    def test_expired_items_drop_out_on_time_and_nothing_is_allowed(self):
        aid = self.agent.add_run('ls', ttl=30)
        self.start()
        self.clock.t += 31
        self.box._tick()                             # between polls: the local clock alone drops it
        self.assertIsNone(self.box.item(aid))
        self.assertEqual(self.box.count, 0)
        self.assertEqual(self.gone, [(aid, 'expired')])
        pump(lambda: not self.box._polling)
        self.assertEqual(self.agent.resolves(), [])

    def test_answered_elsewhere_is_reported(self):
        aid = self.agent.add_run('ls')
        self.start()
        self.agent.decisions[aid] = 'allow-once'     # Mo AI's own window, or a phone channel
        self.poll()
        self.assertEqual(self.gone, [(aid, 'elsewhere')])
        self.assertEqual(self.box.count, 0)

    # ── review / test mode ──────────────────────────────────────────
    def test_review_mode_touches_nothing(self):
        box = inbox.AgentInbox()                     # MIRA_TEST_MODE=1: not live
        with patch('moai_agent.request', side_effect=AssertionError('no service in review mode')):
            box.start()
            box.busy(True)
            box.poll()
            pump(timeout=0.2)
            self.assertEqual(box.count, 0)
            box.review()
            self.assertEqual(box.count, 2)
            for item in box.items:
                self.assertIn('sample', json.dumps(item))       # visibly sample
                self.assertFalse(box.resolve(item['id'], 'allow-once'))
        self.assertEqual({i['tool'] for i in box.items}, {'run_command', 'write_file'})

    # ── words ───────────────────────────────────────────────────────
    def test_strings_are_bilingual_and_merged(self):
        ar, en = i18n.table('ar'), i18n.table('en')
        arabic = re.compile('[؀-ۿ]')
        for key, (a, e) in inbox.STRINGS.items():
            self.assertTrue(a.strip() and e.strip(), key)
            self.assertTrue(arabic.search(a), key)
            self.assertEqual(ar[key], a)
            self.assertEqual(en[key], e)
            for word in ('Fedora', 'Red Hat'):
                self.assertNotIn(word, a + e)
        self.assertEqual(en['agent_approval_title'], 'The agent asks for your permission')
        # the caption reads "Waiting for your approval: <title>": one colon, a whole sentence
        for key in ('agent_approval_run', 'agent_approval_write', 'agent_approval_title'):
            self.assertNotIn(':', en[key] + ar[key], key)


class ControllerGlueTest(unittest.TestCase):
    """The controller's side: an approval becomes a card, and the card's buttons answer the agent."""

    def setUp(self):
        import controller as ctl
        from review_fakes import FakeBridge
        QSettings('MoOS', 'Mira').clear()
        self.agent = FakeAgent(time.time)
        self.patcher = patch('moai_agent.request', side_effect=self.agent.request)
        self.patcher.start()
        with patch.object(inbox, 'TEST_MODE', False):       # the controller's inbox reads the stand-in agent
            self.c = ctl.Controller(bridge_class=FakeBridge)
        self.c.chat.clear()
        self.toasts = []
        self.c.toast.connect(lambda kind, text: self.toasts.append((kind, text)))
        self.s = self.c._s
        self.c.inbox.start()               # Controller.start() does this outside test mode
        self.assertTrue(pump(lambda: self.c.inbox.status == 'online' and not self.c.inbox._polling))

    def tearDown(self):
        self.c.inbox.stop()
        pump(lambda: not self.c.inbox._polling, 2)
        self.patcher.stop()

    def poll(self):
        before = len(self.agent.calls)
        self.c.inbox.poll()
        self.assertTrue(pump(lambda: len(self.agent.calls) > before and not self.c.inbox._polling))
        pump(timeout=0.05)

    def card(self, approval):
        row = self.c.actions.find(inbox.card_id(approval))
        return self.c.actions.get(row) if row >= 0 else None

    def test_an_approval_becomes_a_card(self):
        aid = self.agent.add_run('npm run build')
        self.poll()
        card = self.card(aid)
        self.assertEqual((card['kind'], card['stage'], card['category']), ('agent', 'ask', 'agent_confirm'))
        self.assertEqual(card['output'], '$ npm run build')
        self.assertEqual(card['expires'], self.agent.rows[aid]['expires'])
        self.assertEqual(self.c.inboxCount, 1)
        self.assertTrue(any(kind == 'pending' for kind, _ in self.toasts))
        self.poll()
        self.assertEqual(self.c.actions.count, 1)            # one card per approval

    def test_approve_allows_once_and_shows_what_the_agent_confirmed(self):
        aid = self.agent.add_run('pytest')
        self.poll()
        self.c.approveAction(inbox.card_id(aid))
        self.assertEqual(self.card(aid)['stage'], 'running')
        self.assertTrue(pump(lambda: self.card(aid)['stage'] == 'ok'))
        self.assertEqual(self.agent.decisions, {aid: 'allow-once'})
        self.assertEqual(self.card(aid)['summary'], self.s['agent_approval_allowed'])
        self.c.approveAction(inbox.card_id(aid))              # a second tap sends nothing
        pump(timeout=0.1)
        self.assertEqual(len(self.agent.resolves()), 1)

    def test_reject_denies(self):
        aid = self.agent.add_run('rm -rf dist')
        self.poll()
        self.c.rejectAction(inbox.card_id(aid))
        self.assertTrue(pump(lambda: self.card(aid)['stage'] == 'cancelled'))
        self.assertEqual(self.agent.decisions, {aid: 'deny'})
        self.assertEqual(self.card(aid)['summary'], self.s['agent_approval_denied'])

    def test_answered_elsewhere_closes_the_card(self):
        aid = self.agent.add_run('ls')
        self.poll()
        self.agent.decisions[aid] = 'deny'
        self.poll()
        self.assertEqual(self.card(aid)['stage'], 'expired')
        self.assertEqual(self.card(aid)['summary'], self.s['agent_approval_elsewhere'])
        self.assertEqual(self.agent.resolves(), [])

    def test_a_failed_answer_gives_the_buttons_back(self):
        aid = self.agent.add_run('ls')
        self.poll()
        self.agent.unreachable = True
        self.c.approveAction(inbox.card_id(aid))
        self.assertTrue(pump(lambda: self.card(aid)['stage'] == 'ask'))
        errors = [text for kind, text in self.toasts if kind == 'error']
        self.assertEqual(errors, [inbox.failure_text('agent_unreachable', self.s)])   # words, not a code
        self.assertNotIn('agent_unreachable', ' '.join(errors))
        self.agent.unreachable = False
        self.c.rejectAction(inbox.card_id(aid))
        self.assertTrue(pump(lambda: self.card(aid)['stage'] == 'cancelled'))
        self.assertEqual(self.agent.decisions, {aid: 'deny'})

    def test_yes_by_voice_never_allows_and_no_denies_all(self):
        first, second = self.agent.add_run('make'), self.agent.add_run('make install')
        self.poll()
        self.assertEqual(self.c._caption, inbox.waiting_text(2, self.s))       # two waiting: said as a count
        spoken = []
        self.c.announce = lambda text, attempt=0: spoken.append(text)
        self.assertTrue(self.c._answer_pending('نعم', spoken=False))
        pump(timeout=0.1)
        self.assertEqual(self.agent.resolves(), [])
        self.assertIn(self.s['agent_approval_voice'], [row['text'] for row in self.c.chat.rows()])
        self.assertEqual(spoken, [])                                           # typed: nothing to say aloud
        self.assertTrue(self.c._answer_pending('لا', spoken=True))
        self.assertEqual(spoken, [self.s['agent_approval_voice_denied']])     # heard on the Echo as well
        self.assertTrue(pump(lambda: len(self.agent.decisions) == 2))
        self.assertEqual(self.agent.decisions, {first: 'deny', second: 'deny'})
        texts = [row['text'] for row in self.c.chat.rows()]
        self.assertNotIn(self.s['act_cancelled_say'], texts)                   # no claim before the agent confirms
        self.assertTrue(pump(lambda: [row['text'] for row in self.c.chat.rows()].count(self.s['agent_approval_denied']) == 2))
        self.assertFalse(self.c._answer_pending('كم الساعة؟', spoken=False))

    def test_the_notice_allows_only_what_it_shows_and_closes_with_the_request(self):
        import io
        import controller as ctl
        commands = []

        class Process:
            def __init__(self, command, **_):
                commands.append(command)
                self.stdout = io.StringIO('')

            def wait(self):
                return 0
        plain, spaced = self.agent.add_run('npm test'), self.agent.add_run("printf 'a  b'")
        with patch.object(ctl, 'TEST_MODE', False), patch.object(ctl.subprocess, 'Popen', Process):
            self.poll()
            self.assertTrue(pump(lambda: len(commands) == 2))
        by_body = {command[-1]: command for command in commands}
        shown = next(c for body, c in by_body.items() if '$ npm test' in body)
        hidden = next(c for body, c in by_body.items() if self.s['agent_approval_notify_spacing'] in body)
        self.assertIn('approve=' + self.s['agent_approval_allow'], shown)
        self.assertFalse(any(str(arg).startswith('approve=') for arg in hidden))      # Deny only
        self.assertIn('reject=' + self.s['agent_approval_deny'], hidden)
        for command in commands:
            ttl = int(command[command.index('-t') + 1])
            self.assertTrue(100000 < ttl <= 120000, ttl)                             # the request's own 120 s

    def test_a_working_turn_reads_the_queue_fast(self):
        self.c._on_voice('thinking', '')
        self.assertTrue(pump(lambda: 'turn' in self.c.inbox._sources))
        self.c._on_voice('ready', '')
        self.assertTrue(pump(lambda: not self.c.inbox._sources))



# ─── the agent card on screen (ActionCards.qml) ─────────────────────
ACTION_CARDS = ROOT / 'qml' / 'Mira' / 'ActionCards.qml'
WRAPPER = """
import QtQuick
import Mira
Item {
    width: 760; height: 480
    Rectangle { anchors.fill: parent; color: "black" }
    ActionCards { objectName: "cards"; width: 640; x: 60; anchors.bottom: parent.bottom; anchors.bottomMargin: 20 }
}
"""


class StubMira(QObject):
    """Only what ActionCards.qml reads and calls; the buttons are recorded, nothing runs."""

    def __init__(self, rows, words):
        super().__init__()
        from models import DictListModel
        self._model = DictListModel(action_roles(), key='aid', parent=self)
        self._model.set_rows(rows)
        self._words = words
        self.calls = []

    actionModel = Property(QObject, lambda self: self._model, constant=True)
    s = Property('QVariantMap', lambda self: self._words, constant=True)
    motion = Property(bool, lambda self: False, constant=True)

    @Slot(str)
    def approveAction(self, aid):
        self.calls.append(('approve', aid))

    @Slot(str)
    def rejectAction(self, aid):
        self.calls.append(('reject', aid))

    @Slot(str)
    def dismissAction(self, aid):
        self.calls.append(('dismiss', aid))


def _named(root, name):
    found, todo = [], [root]
    while todo:
        item = todo.pop()
        if item.objectName() == name:
            found.append(item)
        todo.extend(item.childItems())
    return found


def _card_of(item):
    """The card (ListView delegate) an item belongs to."""
    while item is not None:
        value = item.property('aid')
        if isinstance(value, str) and value:
            return item
        item = item.parentItem()
    return None


def _card_aid(item):
    card = _card_of(item)
    return card.property('aid') if card is not None else ''


def _plain(edit):
    """What the TextEdit really displays, as plain text (markup would be rendered, not shown)."""
    length = int(edit.property('length'))
    try:
        return QMetaObject.invokeMethod(edit, 'getText', Qt.DirectConnection, Q_RETURN_ARG('QString'),
                                        Q_ARG(int, 0), Q_ARG(int, length))
    except (TypeError, RuntimeError):
        return None


class ActionCardsQmlTest(unittest.TestCase):
    def setUp(self):
        from PySide6.QtCore import qInstallMessageHandler
        from PySide6.QtQuick import QQuickView
        self.messages = []
        self.previous = qInstallMessageHandler(lambda mode, context, text: self.messages.append(text))
        self.s = i18n.table('en')
        now = int(time.time() * 1000)
        run = {'id': str(uuid.uuid4()), 'expires': now + 60000, 'cwd': '/var/home/moos/site',
               'warning': inbox.RUNTIME_WARNING, 'command': json.dumps(
                   {'tool': 'run_command', 'arguments': {'command': 'echo <b>x</b> && cat <<EOF\n&amp; <i>y</i>\nEOF'}})}
        write = {'id': str(uuid.uuid4()), 'expires': now + 100000, 'cwd': '/var/home/moos/site',
                 'warning': inbox.RUNTIME_WARNING, 'command': json.dumps({'tool': 'write_file', 'arguments': {
                     'path': 'index.html', 'content': '<!DOCTYPE html>\n<h1 style="font-size:40px">Big</h1>\n'}})}
        self.run_card = inbox.card(inbox.normalize(run, now), self.s)
        self.write_card = inbox.card(inbox.normalize(write, now), self.s)
        self.mira = StubMira([self.write_card, self.run_card], self.s)
        self.scratch = tempfile.TemporaryDirectory(prefix='mira-inbox-cards-')
        wrapper = Path(self.scratch.name) / 'cards.qml'
        wrapper.write_text(WRAPPER)
        self.view = QQuickView()
        self.view.engine().addImportPath(str(ROOT / 'qml'))
        self.view.rootContext().setContextProperty('mira', self.mira)
        self.view.setSource(QUrl.fromLocalFile(str(wrapper)))
        self.assertEqual(self.view.status(), QQuickView.Ready, self.messages)
        self.view.show()
        self.root = self.view.rootObject()

    def tearDown(self):
        from PySide6.QtCore import qInstallMessageHandler
        self.view.close()
        self.view.deleteLater()
        pump(timeout=0.1)
        qInstallMessageHandler(self.previous)
        self.scratch.cleanup()
        errors = [m for m in self.messages if any(w in m for w in ('Error', 'error', 'is not defined', 'Cannot'))]
        self.assertEqual(errors, [])

    def visible(self, name):
        return [item for item in _named(self.root, name) if item.isVisible()]

    def click(self, button):
        QMetaObject.invokeMethod(button, 'click', Qt.DirectConnection)
        pump(timeout=0.05)

    def test_only_the_open_request_can_be_allowed_and_it_reads_as_plain_text(self):
        # the request that expires first opens by itself; the other waits folded, with no Allow
        self.assertTrue(pump(lambda: len(self.visible('allowOnce')) == 1, 3))
        allow = self.visible('allowOnce')[0]
        self.assertEqual(_card_aid(allow), self.run_card['aid'])
        self.assertFalse(allow.isEnabled())                   # alive only a moment after it opens
        self.click(allow)
        self.assertEqual(self.mira.calls, [])
        self.assertTrue(pump(lambda: allow.isEnabled(), 3))
        # its exact request is open (never behind a toggle) and shown as text, not rendered markup
        boxes = self.visible('requestText')
        self.assertEqual([_card_aid(b) for b in boxes], [self.run_card['aid']])
        self.assertEqual(boxes[0].property('text'), self.run_card['output'])
        self.assertEqual(int(boxes[0].property('length')), len(self.run_card['output']))
        shown = _plain(boxes[0])
        if shown is not None:
            self.assertEqual(shown, self.run_card['output'])
        self.assertTrue(boxes[0].property('activeFocusOnTab'))   # the keyboard reaches the request too
        folded = [b for b in self.visible('showRequest')]
        self.assertEqual([_card_aid(b) for b in folded], [self.write_card['aid']])
        self.click(allow)
        self.assertEqual(self.mira.calls, [('approve', self.run_card['aid'])])
        # opening the other request folds this one: its Allow leaves the screen
        self.click(folded[0])
        self.assertTrue(pump(lambda: [_card_aid(a) for a in self.visible('allowOnce')] == [self.write_card['aid']], 3))
        self.assertEqual([_card_aid(b) for b in self.visible('showRequest')], [self.run_card['aid']])
        box = self.visible('requestText')
        self.assertEqual([_card_aid(b) for b in box], [self.write_card['aid']])
        self.assertEqual(int(box[0].property('length')), len(self.write_card['output']))   # HTML source, as text
        allow = self.visible('allowOnce')[0]
        self.assertTrue(pump(lambda: allow.isEnabled(), 3))
        self.click(allow)
        self.assertEqual(self.mira.calls[-1], ('approve', self.write_card['aid']))

    def test_the_cards_never_grow_past_their_room(self):
        """Two requests do not fit a short window: the stack keeps to its room and scrolls,
        and the open request is brought whole into view with its Allow."""
        cards = _named(self.root, 'cards')[0]
        self.assertTrue(pump(lambda: len(self.visible('allowOnce')) == 1 and self.visible('allowOnce')[0].isEnabled(), 3))
        self.assertLessEqual(cards.height(), cards.property('maxHeight') + 0.5)
        self.assertLessEqual(cards.property('maxHeight'), self.root.height())
        allow = self.visible('allowOnce')[0]
        top = allow.mapToItem(cards, 0, 0).y()
        self.assertGreaterEqual(top, 0)                                    # the Allow is inside the stack...
        self.assertLessEqual(top + allow.height(), cards.height() + 0.5)
        head = _card_of(allow).mapToItem(cards, 0, 0).y()
        self.assertGreaterEqual(head, -0.5)                                # ...and so are its title and place

if __name__ == '__main__':
    unittest.main()
